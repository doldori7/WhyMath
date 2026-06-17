"""WH-S 검증된 중간 결과 저장소(`verified_lemmas`) ORM 모델 — 부분 결과 재사용(§2.2).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.2(검증된 중간 결과 저장소 — Verified
Lemma Store)·§3 도구 7(`log_lemma`). 탐색 중 `verify`를 통과한 *부분 결과*(예: "이 식은 x>0에서
단조증가")를 보관하고, 다른 가지가 같은 보조 목표에 닿으면 *재사용*해 중복 탐색을 제거한다.
난해한 문제일수록 이 재사용이 탐색 효율을 결정한다(하네스-1 큐레이션 세트에 해당).

§2.2 정의:
  - 탐색 중 verify 통과한 부분 결과(중간 보조정리) 보관 — 다른 가지에서 재사용.
  - 재사용으로 중복 탐색 제거(난해 문제일수록 효율 결정).

영속 매핑 컨벤션(`verified_solution.py`·`dead_end_log.py` 선례 답습):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`.
  - `problem_id`(UUID NOT NULL·**FK 아님**·느슨참조) — WH-S 오프라인 독립성(§7.5). 복합 UNIQUE
    선행 컬럼이 인덱스 겸함.
  - `lemma_key`(Text NOT NULL) — 재사용 매칭용 정규화 키(보조 목표 해시·키 스킴은 솔버 루프가
    계약 정의·자유형). `find_lemma`가 이 키로 *재사용 가능한 보조정리*를 정확 조회한다.
  - `lemma_repr`(JSONB NOT NULL) — 검증된 부분 결과의 구조화 표현(자유형·솔버 루프가 계약 정의·
    `solution_node.state_repr`와 동형 방침).
  - `statement`(Text nullable) — 사람이 읽는 보조정리 진술(예 "x>0에서 단조증가"·디버그·WH-1
    콘텐츠 소비용). None이면 미작성.
  - `source_node_id`(UUID nullable·**FK 아님**·느슨참조) — 이 보조정리를 만든 풀이 트리 노드
    (`solution_nodes.id`). FK로 묶지 *않는다*: 저장소는 재사용 자산이라 트리가 가지치기·GC돼도
    살아남아야 한다(트리 삭제 비강결합·`verified_solution.source_root_id` 동형). 추적용 약참조.
  - `created_at`(TIMESTAMPTZ NOT NULL·server_default now()).

★검증 전제(§2.2 "verify를 통과한" — 구조 전제): 본 저장소는 *검증된* 보조정리만 담는다. 등급
컬럼을 두지 않는 이유는 모든 행이 verify 통과 후 적재되기 때문이다(`log_lemma`는 verify 도구
통과 뒤 호출·미검증 부분 결과는 애초에 저장소에 오지 않는다). `verified_solutions`가 unverified를
보관·격리하는 것과 달리, lemma는 재사용 대상이라 *검증된 것만* 둔다(보상 해킹 차단·R-S2 정신).

멱등 적재(§2.2 중복 제거): `(problem_id, lemma_key)` **UNIQUE**. 같은 보조정리를 두 가지가
독립 발견해도 한 행이다(저장소 `log_lemma`가 ON CONFLICT DO NOTHING 멱등). 이 복합 UNIQUE
인덱스가 `find_lemma`(정확 매칭 재사용 조회)·`get_lemmas`(problem_id prefix)를 겸한다.

개인정보 메모(CLAUDE.md): `verified_lemmas`는 *시스템 솔버 내부 중간 산출*이며 학생 PII가 아니다
(동의·암호화·redaction 불요 — `solution_nodes` 동일 방침). 학생 경로 미개입(§7.5·API 노출 0).

범위 밖(후속): 솔버 `verify`/`log_lemma`(검증 후 커밋)·재사용 정책(탐색이 `find_lemma`로 가지치기)·
키 스킴 표준화. 본 모듈은 *검증 보조정리 저장소 스키마*만 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class VerifiedLemma(Base):
    """WH-S 검증된 중간 결과 저장소 영속 ORM — §2.2 `verified_lemmas`.

    한 행은 *한 검증된 보조정리*: 문제 `problem_id`의 부분 결과 `lemma_repr`와 재사용 매칭 키
    `lemma_key`. 두 가지가 같은 보조 목표에 닿으면 `find_lemma(problem_id, lemma_key)`로 재사용
    한다. `problem_id`·`source_node_id`는 *FK가 아닌 느슨참조*(재사용 자산 — 트리 GC 비강결합).
    """

    __tablename__ = "verified_lemmas"

    # ===== 기본 식별 =====
    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성). 복합 UNIQUE 선행 컬럼이 인덱스 겸함.
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)

    # ===== 보조정리 (§2.2 검증된 부분 결과 + 재사용 키) =====
    # 재사용 매칭용 정규화 키(보조 목표 해시·키 스킴은 솔버 루프가 계약 정의·자유형 텍스트).
    lemma_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 검증된 부분 결과의 구조화 표현(자유형 JSONB·솔버 루프가 계약 정의).
    lemma_repr: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # 사람이 읽는 보조정리 진술(예 "x>0에서 단조증가"·디버그·WH-1 콘텐츠). 미작성이면 None.
    statement: Mapped[str | None] = mapped_column(sa.Text)
    # 이 보조정리를 만든 풀이 트리 노드(solution_nodes.id) — FK 아님(재사용 자산·트리 GC 비강결합).
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 운영 메타 =====
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    # ── 멱등 적재 (§2.2 중복 제거): (problem_id, lemma_key) UNIQUE ──
    # 이 복합 UNIQUE 인덱스가 find_lemma(정확 매칭 재사용)·get_lemmas(problem_id prefix)를 겸한다.
    __table_args__ = (
        sa.UniqueConstraint(
            "problem_id",
            "lemma_key",
            name="uq_verified_lemmas_problem_key",
        ),
    )


__all__ = ["VerifiedLemma"]
