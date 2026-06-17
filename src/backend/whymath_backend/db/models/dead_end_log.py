"""WH-S 실패 접근 로그(`dead_end_log`) ORM 모델 — 같은 막다른 길 재진입 차단(§2.3).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.3(실패 접근 로그 — Dead-End Log)·
§3 도구 7(`log_deadend`). 솔버 탐색이 *막다른 길*에 닿으면 `(state_hash, action)` 쌍을 기록하고,
이후 탐색 정책이 이를 *회피*한다. LLM의 고질적 약점(같은 실수 반복)을 상태 관리로 구조 차단한다.

§2.3 정의:
  - `(state_hash, action)` 쌍을 기록 — 어떤 상태에서 어떤 행동이 막다른 길이었는지.
  - 탐색 정책이 이를 회피(중복 탐색 제거 — 하네스-1 "중복 자동 압축·정리"에 해당).

영속 매핑 컨벤션(`solution_node.py` 선례 답습):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`(모든 UUID PK 선례).
  - `problem_id`(UUID NOT NULL·**FK 아님**) — WH-S 오프라인 독립성(§7.5). `solution_nodes`와 동형
    느슨참조. 인덱스는 아래 복합 UNIQUE의 선행 컬럼이 겸한다(별도 problem 인덱스 불요).
  - `state_hash`(Text NOT NULL) — 막다른 상태의 해시(해시 스킴은 솔버 루프가 계약 정의 — 자유형).
  - `action`(Text NOT NULL) — 그 상태에서 막다른 길로 이끈 행동(전략 1스텝). dead-end는 *반드시*
    어떤 행동으로 닿으므로 NOT NULL(루트와 달리 action 없는 dead-end는 없다).
  - `reason`(Text nullable) — 왜 막다른 길인지 진단 메모(선택 — 검증 실패·반례·순환 등).
  - `created_at`(TIMESTAMPTZ NOT NULL·server_default now()) — 기록 시각(운영 메타).

멱등 기록(§2.3 중복 차단의 핵심): `(problem_id, state_hash, action)` **UNIQUE**. 같은 막다른 길을
두 번 기록해도 한 행이다(저장소 `log_dead_end`가 ON CONFLICT DO NOTHING으로 멱등 보장). 이 복합
UNIQUE 인덱스가 `is_dead_end`(정확 매칭 조회)와 `get_dead_ends`(problem_id 선행 prefix 조회)를
모두 커버하므로 별도 인덱스는 두지 않는다.

개인정보 메모(CLAUDE.md 절대 금기 대조): `dead_end_log`는 *시스템 솔버의 내부 탐색 실패 상태*이며
학생 풀이 데이터가 아니다(미성년 PII·동의 대상 아님 — `solution_nodes`와 동일 방침). 암호화·
redaction 불요(평문 적정). 학생 경로 미개입(§7.5)이라 API 노출 0.

범위 밖(후속): 솔버 루프(탐색 정책이 `is_dead_end`로 회피)·§2.2 Verified Lemma Store·해시 스킴
표준화. 본 모듈은 *실패 접근 로그 스키마*만 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class DeadEndLog(Base):
    """WH-S 실패 접근 로그 영속 ORM — §2.3 `dead_end_log`.

    한 행은 *한 막다른 길*: 문제 `problem_id`의 상태 `state_hash`에서 행동 `action`이 dead-end
    였음을 기록한다. `(problem_id, state_hash, action)` UNIQUE로 중복 기록을 한 행으로 접는다
    (멱등). `problem_id`는 *FK가 아닌 느슨참조*(모듈 docstring — WH-S 오프라인 독립성).
    """

    __tablename__ = "dead_end_log"

    # ===== 기본 식별 =====
    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성). 복합 UNIQUE 선행 컬럼이 인덱스 겸함.
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)

    # ===== 막다른 길 식별 (§2.3 (state_hash, action) 쌍) =====
    # 막다른 상태의 해시(해시 스킴은 솔버 루프가 계약 정의 — 자유형 텍스트).
    state_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 그 상태에서 막다른 길로 이끈 행동(전략 1스텝). dead-end는 반드시 행동으로 닿으므로 NOT NULL.
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 왜 막다른 길인지 진단 메모(선택 — 검증 실패·반례·순환 등).
    reason: Mapped[str | None] = mapped_column(sa.Text)

    # ===== 운영 메타 =====
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    # ── 멱등 기록 (§2.3 중복 차단): (problem_id, state_hash, action) UNIQUE ──
    # 이 복합 UNIQUE 인덱스가 is_dead_end(정확 매칭)·get_dead_ends(problem_id prefix)를 겸한다.
    __table_args__ = (
        sa.UniqueConstraint(
            "problem_id",
            "state_hash",
            "action",
            name="uq_dead_end_log_problem_state_action",
        ),
    )


__all__ = ["DeadEndLog"]
