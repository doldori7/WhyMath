"""generation_log 재현 좌석 5컬럼 추가 — 생성 Run 재현성 (EOS-55 + #912 P1 보강).

`docs/standards/eos_verification_design_v1.md`가 요구하는 생성 Run 재현 계약("동일 Run
레코드로 재실행 시 동일 입력이 복원된다")의 영속 좌석. 스키마 실재≠적재 배선이 이
태스크의 존재 이유이므로, 적재 배선은 두 생성 경로(`harness/problem_corpus_accumulate`·
`l3/pregenerate`)가 별항으로 결선한다(정본화≠집행 — 통합 테스트
`tests/backend/l3/test_generation_log_wiring.py`가 동결).

**구 행 NULL=미기록(정직)**: 기존 generation_log 행은 재현 재료 없이 적재됐다 — 값을
소급 날조하지 않는다. 전 컬럼 nullable·server_default 없음(additive·data migration 0건,
EOS-54 review_timer_event "미측정=NULL·default 날조 금지" 동형).

컬럼(ORM 정본 `db/models/provenance.py::GenerationLog`와 1:1):
  - `prompt_version` VARCHAR(128) — 실제 사용한 프롬프트 정본 식별자. 별도 버전 체계가
    없으므로(2026-08-30 실측: prompt_template_id 적재 0·Langfuse 프롬프트 버전 미사용)
    정본 자산 내용 해시로 식별(예 'l3.equivalent@sha256:…'). 체계 없는 경로는 NULL.
  - `seed` BIGINT — 실제 쓰인 샘플링 시드만 기록. 현행 두 경로는 seed 스레딩이 없어
    (2026-08-30 실측: 라우터·프로바이더 seed 전달 0) 항상 NULL=미사용(날조 금지).
  - `input_sha256` VARCHAR(64) — 입력 스냅샷 canonical 직렬화의 sha256 hex(무결성 축).
    형식·스냅샷과의 정합은 schema validator가 강제(DB CHECK 미제조 — provenance.py 방침).
  - `input_snapshot` JSONB — **자기완결** 복원 재료: 프롬프트·시스템 *전문(verbatim)* +
    sha256 무결성 핀 + 라우팅 request·스펙 필드 원문(#912 P1-1: 해시만으로는 입력 재구성
    불가 — 자체 문면이라 저작권 무관·행당 수 KB 허용). Python None → SQL NULL은 ORM
    `none_as_null` 선언 소관(SEC-06 거버넌스·gen_meta 선례).
  - `cu_slug` VARCHAR(128) — 생산 CU 조인 정체성(#912 P1-2): 코퍼스 키·review_timer
    `cu_slug`와 동일 산식 → `ops/hit_cu_metrics --generation-log` CU당 토큰·비용 조인이
    성립한다. 정체성 없는 종단(파싱 실패·pregenerate 캐시 시드)은 NULL=미기록.

이 리비전은 PR #912 전용(어떤 DB에도 적용 이력 없음)이라 P1 보강을 새 리비전이 아닌
in-place 수정으로 반영했다(무의미한 2단 체인 방지).

upgrade: nullable 5컬럼 add(additive·기존 행 비파괴). downgrade: 역순 drop(완전 복원).

Revision ID: f4b2d8c1a3e5
Revises: 84c782415837
Create Date: 2026-08-31 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b2d8c1a3e5"
down_revision: str | None = "84c782415837"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 재현 좌석 — 전부 nullable·server_default 없음(구 행 NULL=미기록·소급 날조 금지).
    op.add_column(
        "generation_log",
        sa.Column("prompt_version", sa.String(length=128), nullable=True),
    )
    op.add_column("generation_log", sa.Column("seed", sa.BigInteger(), nullable=True))
    op.add_column(
        "generation_log",
        sa.Column("input_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "generation_log",
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "generation_log",
        sa.Column("cu_slug", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    # upgrade 역순 drop — 완전 복원(대칭).
    op.drop_column("generation_log", "cu_slug")
    op.drop_column("generation_log", "input_snapshot")
    op.drop_column("generation_log", "input_sha256")
    op.drop_column("generation_log", "seed")
    op.drop_column("generation_log", "prompt_version")
