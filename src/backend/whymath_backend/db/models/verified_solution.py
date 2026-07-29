"""WH-S 검증 풀이 저장소(`verified_solutions`) ORM 모델 — 최종 통과 풀이 경로 보관(§2.4).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.4(검증 풀이 저장소 — Verified Solution
Bank)·§3 도구 8(`finalize`)·§5(자기 진화 학습 데이터)·§7(WH-1 콘텐츠 원천). 솔버가 `finalize`로
조립·검증한 *완전 풀이 경로*를 보관한다. 두 용도: ① 자기 진화 SFT/RL 학습 데이터(§5) ② WH-1
튜터의 콘텐츠 원천(§7). 한 문제의 **다중 풀이 경로**(대수적·기하적·귀납적)를 모두 보관한다 —
풀이 다양성 자체가 자산(§2.4).

★등급의 구조적 차단(§2.4·§3·R-S2 보상 해킹 차단): 저장소 등급은 **verified·unverified 2종뿐**.
`failed`(틀린 과정/오답)는 *완전 풀이가 아니므로* 저장소에 들어오지 않는다 — `finalize`가 거부
한다(스키마 차원에서 failed를 enum에서 배제해 구조적으로 막는다). `unverified`는 §3 격리 등급:
판정 불가 최종 풀이를 *보관하되 학습 데이터로 절대 사용하지 않는다*(`get_verified`가 verified만
반환). `whs/verdict.WhsGrade`(verified/unverified/failed)의 *적재 가능 부분집합*이다.

영속 매핑 컨벤션(`solution_node.py` 선례 답습):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`.
  - `problem_id`(UUID NOT NULL·**FK 아님**·느슨참조) — WH-S 오프라인 독립성(§7.5).
  - `grade`(`whs_solution_grade_enum` — verified/unverified) → `_pg_enum`.
  - `solution_path`(JSONB NOT NULL) — 완전 풀이 경로의 구조화 표현(단계열·중간 상태 — 자유형·
    솔버 루프가 계약 정의. `solution_node.state_repr`와 동형 방침).
  - `strategy_tag`(Text nullable) — 풀이 전략 계열(대수적·기하적·귀납적 — §2.4 다중 풀이 다양성
    태그). None이면 미분류.
  - `answer`(Text nullable) — 최종 답(검색·중복 식별용). 증명 등 답이 없으면 None.
  - `source_root_id`(UUID nullable·**FK 아님**·느슨참조) — 이 풀이가 비롯된 풀이 트리 루트
    (`solution_nodes.id`). FK로 묶지 *않는다*: 저장소는 *내구 자산*(자기진화·WH-1 원천)이라 트리가
    가지치기·GC돼도 살아남아야 한다(트리 삭제에 강결합 금지). 추적용 약참조일 뿐.
  - `created_at`(TIMESTAMPTZ NOT NULL·server_default now()).

다중 풀이(§2.4): `problem_id`에 UNIQUE를 두지 *않는다* — 한 문제에 여러 풀이 경로(여러 전략)를
보관한다. 복합 인덱스 `(problem_id, grade)`가 `get_solutions`(problem_id)·`get_verified`
(problem_id + grade=verified) 둘 다 커버한다.

개인정보 메모(CLAUDE.md): `verified_solutions`는 *시스템이 스스로 푼* 풀이이며 학생 PII가 아니다
(동의·암호화 대상 아님 — `solution_nodes` 동일 방침). 학생 경로 미개입(§7.5·API 노출 0). WH-1
콘텐츠로 *소비*될 때 비로소 표현 계층이 붙는다(후속).

범위 밖(후속): 솔버 `finalize`(검증 후 커밋)·자기진화 데이터 export(§5)·WH-1 콘텐츠 변환(§7)·
중복 풀이 dedup(해시). 본 모듈은 *검증 풀이 저장소 스키마*만 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum


class WhsSolutionGrade(str, Enum):
    """검증 풀이 저장소 등급 — `WhsGrade`(verdict.py)의 *적재 가능 부분집합*(§2.4·§3).

    `failed`는 *의도적으로 없다* — 틀린 과정/오답은 완전 풀이가 아니므로 저장소에 들어오지 않는다
    (`finalize` 거부 + enum 차원 구조 차단·R-S2). 멤버:
      - `VERIFIED`("verified"): Tier1 pass + 전 단계 Tier2 correct(§4). *학습 채택 가능*(§5).
      - `UNVERIFIED`("unverified"): 판정 불가 격리(§3). 보관하되 *학습 데이터 배제*(R-S2).

    값=멤버명(소문자)이라 `_pg_enum` values_callable로 PG enum 라벨이 값과 일치한다.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class VerifiedSolution(Base):
    """WH-S 검증 풀이 저장소 영속 ORM — §2.4 `verified_solutions`.

    한 행은 *한 완전 풀이 경로*: 문제 `problem_id`에 대한 풀이 `solution_path`와 그 최종 등급
    `grade`(verified/unverified). 한 문제에 여러 행(다중 풀이 전략)이 올 수 있다. `problem_id`·
    `source_root_id`는 *FK가 아닌 느슨참조*(내구 자산 — 트리 GC에 비강결합).
    """

    __tablename__ = "verified_solutions"

    # ===== 기본 식별 =====
    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성). 복합 인덱스 (problem_id, grade) 참조.
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)

    # ===== 풀이 + 등급 (§2.4) =====
    # 최종 등급 — verified(학습 채택 가능)·unverified(격리·배제). failed는 enum에 없음(구조 차단).
    grade: Mapped[WhsSolutionGrade] = mapped_column(
        _pg_enum(WhsSolutionGrade, "whs_solution_grade_enum"),
        nullable=False,
    )
    # 완전 풀이 경로의 구조화 표현(단계열·중간 상태 — 자유형 JSONB·솔버 루프가 계약 정의).
    solution_path: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    # 풀이 전략 계열(대수적·기하적·귀납적 — 다중 풀이 다양성 태그). 미분류면 None.
    strategy_tag: Mapped[str | None] = mapped_column(sa.Text)
    # 최종 답(검색·중복 식별). 증명 등 답이 없으면 None.
    answer: Mapped[str | None] = mapped_column(sa.Text)
    # 이 풀이가 비롯된 풀이 트리 루트(solution_nodes.id) — FK 아님(내구 자산·트리 GC 비강결합).
    source_root_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 운영 메타 =====
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    # ── 인덱스 (§2.4 접근 패턴 — 문제별 전체/검증 풀이 조회) ──
    # (problem_id, grade) 복합으로 get_solutions(problem_id)·get_verified(problem_id+verified) 겸용.
    __table_args__ = (sa.Index("idx_verified_solutions_problem_grade", "problem_id", "grade"),)


__all__ = ["VerifiedSolution", "WhsSolutionGrade"]
