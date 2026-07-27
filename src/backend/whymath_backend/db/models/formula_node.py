"""수식 노드 *PG 프로젝션* ORM — formula_id 키 안전 메타 (리치 Part 2 Phase 5a).

`problem_type_node`·`skill_node`·`atom_node`·`concept_node`(메타 프로젝션)의 *수식* 짝이다.
data-pipeline `formula_graph`가 자체작성 `formulas.jsonl`을 `graph.json`(canonical 수식 노드)으로
정형화했고, 이 테이블이 그 *안전 메타*를 formula_id 키로 영속 투영한다 — 검색 enrichment·필터·(후속)
수식 참조 백킹. upsert로 멱등 적재한다(`ON CONFLICT(formula_id) DO UPDATE`).

────────────────────────────────────────────────────────────────────────────
canonical-only·ID≠Signature·SymPy 재구현 금지 (핵심 경계)
────────────────────────────────────────────────────────────────────────────
- `formula_id`는 **사람 관리 안정 code**(`formula.<slug>`·SymPy 계산값 아님) — 정체성. 알고리즘이
  바뀌어도 id 불변.
- `canonical_signature`는 검색·dedup **보조** 메타(nullable)일 뿐 정체성이 아니다(ID≠Signature).
- **변형식은 노드화하지 않는다**(변수명·항순서·표기 변이 = 조합폭발 방지). 변형↔canonical 동치는
  런타임 SymPy(`l3/symbolic_equivalence.py`)가 판정 — 이 테이블은 수식의 *정체성·참조*만 담고 CAS·
  재작성 규칙을 내장하지 않는다(SymPy 재구현 금지·`math_dsl_evolution.md` §2.1). 그래서 이 모듈은
  **sympy를 import하지 않는다**(동치 권위는 l3 단일·`test_formula_governance`가 동결).
- `equivalence_class`·`sympy_repr` 컬럼 없음(변형 열거 금지·표준형은 dsl에서 파생).

법적(CLAUDE.md 우선순위 #2): canonical 수식은 **수학적 사실·표준 표기 자체작성**이라 저작권 무관 —
교과서·기출 *본문*을 담지 않는다(`standard_codes`는 연결 코드만). native PG enum 없음(전량 TEXT/
TEXT[]). schema/ 상응 Pydantic 표면 없음(`problem_type_node`·`skill_node` 선례).

인덱스: PK `formula_id`로 충분하되 `family`(수식 그룹핑)는 필터 축이라 보조 인덱스를 둔다.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base

# 수식 메타 검수 상태 기본값 — v1 택소노미는 자체작성이나 검수 전이라 정직하게 'ai_estimated'
# (problem_type_node·skill_node 동형·검수 승격 시 'reviewed'로 갱신·plain text). 게이팅이 비교.
FORMULA_REVIEW_STATUS_DEFAULT: str = "ai_estimated"


class FormulaNode(Base):
    """수식 메타 PG 프로젝션 — formula_id 키 안전 표시·필터 메타(canonical-only·검색 백킹).

    한 행 = 한 canonical 수식 노드의 안전 메타(name_ko·family·latex·dsl·canonical_signature·
    aliases·연결 성취기준 코드). PK(formula_id=`formula.<slug>`)로 멱등 upsert 적재한다. 변형/동치
    슬롯은 두지 않는다(동치는 런타임 SymPy·problem_type_node·skill_node 동형).
    """

    __tablename__ = "formula_node"

    # PK = formula_id(`formula.<slug>`·사람 관리 안정 code·upsert 충돌 키). skill/ptype와 분리.
    formula_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 한국어 표시명(graph.json `name_ko`·필수). 검색 enrichment 핵심 표시 필드.
    name_ko: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 수식 family(그룹·graph.json `family`·필수). 필터·집계 축.
    family: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # canonical 표현의 display LaTeX(graph.json `latex`·필수·화면용 자체작성 표준 표기).
    latex: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # canonical 표현의 SymPy-parseable 식(graph.json `dsl`·필수·동치 판정은 런타임 SymPy).
    dsl: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 검색·dedup 보조 signature(graph.json `canonical_signature`·nullable·정체성 아님·backfill=5b).
    canonical_signature: Mapped[str | None] = mapped_column(sa.Text)
    # 같은 canonical 수식의 display 별칭(graph.json `aliases`·기본 빈 배열·변형 열거 아님).
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 연결 NCIC 성취기준 *코드* 목록(graph.json `standard_codes`·기본 빈 배열·코드는 사실정보).
    standard_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 성립 조건·사용범위(graph.json `constraints`·자체작성 텍스트·무조건 항등식은 빈 배열·S4-06).
    # 유도/증명 슬롯이 아니다 — 유도는 Theorem/Proof 축(P6·D2) 위임(증명 축 이중화 금지).
    constraints: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 암기팁(graph.json `mnemonic`·nullable·자체작성·표준 정착 구절만 — 대부분 NULL·S4-06).
    mnemonic: Mapped[str | None] = mapped_column(sa.Text)
    # 검수 게이팅 — v1 자체작성이나 검수 전이라 기본 'ai_estimated'(ptype 동형·NOT NULL).
    review_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(problem_type_node·skill_node 동형).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # family(수식 family 그룹) 보조 인덱스(검색·집계).
        sa.Index("ix_formula_node_family", "family"),
    )


__all__ = ["FormulaNode", "FORMULA_REVIEW_STATUS_DEFAULT"]
