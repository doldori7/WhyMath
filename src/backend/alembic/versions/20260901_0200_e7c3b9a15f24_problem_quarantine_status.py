"""review_status_enum에 'quarantined' 추가 + problem 격리 사유·시각 좌석 (EOS-71)

검토_18(문제 DB 검토) §24 채택. 운영 중 사후 결함 판정(정답 오류·복수 정답·모호 문장 등)을 받은
문항을 **삭제하지 않고 격리**하는 경로가 없었다 — 상태값이 `pending`/`approved`/`rejected` 3종뿐이라
"한때 승인돼 서빙되던 문항의 회수"를 표현할 자리가 없었고, 그 공백 때문에 실제로 **파괴적 처분**이
일어났다: `docs/data/problem_duplicate_disposition_2026-08.md` §3이 "감사 도구는 review_status를
필터하지 않는다 → 마킹만으로는 목록에서 사라지지 않는다"를 근거로 JSONL 레코드 9건을 물리 제거했다고
자인한다. 이 마이그레이션은 그 파괴적 처분의 구조화된 대안(비파괴 격리)의 영속 좌석이다.

계약 정본: `docs/standards/problem_quarantine_contract.md`.

신규 테이블 없음 — 기존 `problem`에 nullable 컬럼 2개 + enum 값 1개(EOS-48·EOS-57과 동형의
**additive·비파괴** 변경: 기존 행은 전부 NULL 유지, 기존 writer·소비자 무영향).

**`rejected`와 다른 값을 쓰는 이유**: `rejected`는 *애초에 승인받지 못한* 문항(검수 기준 미달·서빙된
적 없음)이고, `quarantined`는 *한때 approved로 서빙되던* 문항의 사후 회수다. 하나로 합치면 "학생이
이미 풀어 본 결함 문항"과 "한 번도 나간 적 없는 탈락 문항"이 같은 글자가 되어, 딸린
`problem_attempt` 기록을 어떻게 다룰지(재채점·θ 재계산 대상인지)를 사후에 구분할 수 없다.

**server_default를 달지 않는 이유(날조 방지 — EOS-48/EOS-57 규약 그대로)**: `quarantined_at`에
`DEFAULT now()`를 달면 PG가 기존 행 전체를 **마이그레이션 시각으로 백필**한다 — 그러면 "격리된 적
없음"과 "이 시각에 격리됨"이 같은 값이 되어 격리 이력이 통째로 날조된다. NULL=미격리가 정직한
상태이며, 관리자 PATCH(`api/problems.py` — `RequireContentAdmin`)가 격리 시점에 채운다.

**CHECK 제약을 걸지 않는 이유**: "`review_status='quarantined'`면 사유·시각이 NOT NULL"은 매력적인
불변식이지만 기존 행·중간 상태(상태만 먼저 바꾸고 사유를 뒤에 쓰는 트랜잭션)와 충돌한다. 사유 기록은
계약 문서 §3의 절차 의무로 두고, 강제가 필요해지면 별도 태스크로 등재한다(가짜 DB CHECK를 만들지
않는다 — `db/models/problem.py` 모듈 docstring의 본문 미보유 불변식 처리와 같은 판단).

**enum ADD VALUE 안전성(PG 16)**: 같은 트랜잭션에서 값을 *추가*만 하고 *사용*하지 않으므로 안전하다
(선례 `b1c2d3e4f5a6` 힌트제공·`d4a71c0f9b32` 문제시도 docstring 동일 근거). 아래 `add_column` 2건은
`problem` 테이블의 TEXT·TIMESTAMPTZ 컬럼이라 새 enum 라벨을 참조하지 않는다. `IF NOT EXISTS`로
재실행 멱등.

**마이그레이션 체인**: 본 리비전은 `d4a71c0f9b32`(EOS-57 attempt_event.skill_ids) 위에 선형으로
쌓인다(저장소 단일 head 관례 — `test_solution_path_orm.py::test_single_head_chain`이 동결).
EOS-57은 `attempt_event`를 건드리고 본 리비전은 `problem`을 건드려 **객체가 겹치지 않으므로** 순서
의존이 없다(병렬 세션이 같은 부모에서 갈라지면 재부모화가 안전한 이유).

**ADR-001 재확인(hypertable 전환 무충돌)**: `problem`은 hypertable 대상이 아니고, nullable 컬럼
추가는 파티션 키·PK를 건드리지 않는다.

upgrade: enum 값 1개 add(멱등) + 컬럼 2개 add(nullable·default 없음).
downgrade: 컬럼 2개 drop(대칭). enum 값은 PG가 제거를 지원하지 않아 관례대로 남긴다(no-op·무손상).

Revision ID: e7c3b9a15f24
Revises: d4a71c0f9b32
Create Date: 2026-09-01 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c3b9a15f24"
down_revision: str | None = "d4a71c0f9b32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # review_status_enum에 'quarantined' 1종 추가(멱등·같은 트랜잭션에서 사용하지 않으므로 안전).
    op.execute("ALTER TYPE review_status_enum ADD VALUE IF NOT EXISTS 'quarantined'")
    # 격리 사유 — 결함의 구체 서술(정답 오류/복수 정답/모호 문장/중복 등). nullable·기본값 없음.
    op.add_column(
        "problem",
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
    )
    # 격리 시각 — 이 시각 *이전* attempt는 결함 문항 응답일 수 있다. 백필 날조 방지로 기본값 없음.
    op.add_column(
        "problem",
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("problem", "quarantined_at")
    op.drop_column("problem", "quarantine_reason")
    # PG는 enum 값 제거 미지원 — 'quarantined'는 남긴다(no-op·관례·데이터 무손상).
