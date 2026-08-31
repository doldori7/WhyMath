"""Alignment 통합 조회 HTTP API — 개념↔성취기준 정렬 3축의 *얇은* 합성 표면.

엔드포인트(prefix `/v1/alignments`):
  - GET /v1/alignments — 기존 3축 정렬 재료를 하나의 목록으로 합성 조회.

3축(실측 — CUR-12 acceptance ①과 동일 열거):
  1. `concept_standard_link` — ConceptStandardLink 행(concept_code ↔ norm_id, link_type).
  2. `curriculum_entry`      — CurriculumEntry.national_standard_codes 배열(concept_id ↔ 코드).
  3. `atom_node`             — AtomNode.standard_codes 배열(원자 code ↔ 코드).

── CUR-12와의 경계(선점 금지 — CUR-11 설계 지침 명기) ────────────────────────
이 엔드포인트는 **기존 조회 재료의 얇은 조합**이다: 핸들러가 3축을 각자 SELECT해 항목으로
평탄화할 뿐, 함수 레벨 통합(`get_alignments(concept_id, framework_id, outcome_id)` 단일 비동기
함수·`l1/standards/alignment_query.py` 신설·api/coach·l2/target_progress·l3 DSL 소비처 정렬·
alignment_type enum·조인 성립 건수 로깅)은 전부 **후속 CUR-12의 몫**이라 여기서 만들지 않는다.
CUR-12가 통합 함수를 세우면 이 핸들러는 그 함수를 경유하도록 갈아끼우는 것이 의도된 진화다.
같은 이유로 축 간 어휘 통일도 시도하지 않는다 — `standard_ref`는 축마다 다른 어휘(1축=norm_id,
2·3축=official_code 계열)를 *그대로* 실어 나르고, 그 사실을 `standard_ref_kind`로 정직하게
표시한다(조용한 가짜 통일 금지).

정렬·페이지네이션(결정적 — 순서 발명 없이 안정 키만):
  전체 순서 = 축 순서 고정(1→2→3) × 축 내 안정 키 정렬(1축=(concept_code, norm_id, link_type)
  의미 유일키 / 2축=entry_id PK / 3축=code PK, 배열은 저장 순서). limit/offset은 이 합성 순서에
  적용한다. 구현은 축별 SELECT에 LIMIT(offset+limit)을 걸고 합성 후 슬라이스한다 — 합성 순서가
  축-우선(prefix 보존)이라 축별 상한 인출로도 올바른 페이지가 나온다. 배열 축은 빈 배열 행이
  항목 0건을 낳아 prefix 보존을 깨므로 SQL에서 `cardinality(...) > 0`으로 제외한다(행 1건 ≥
  항목 1건 보장). 이 방식은 offset+limit 행을 메모리에 올리므로 `offset`에 상한(le=10000)을
  둔다 — 무상한 offset은 축별 인출 폭주가 된다(기존 offset 관례에 상한이 없는 것과 다른 점·
  사유 명기).

인가 판단(선례 실측): GET·무인증 — concepts/problems GET "공개 카탈로그" 선례(SEC-07 D1이
GET을 의도적으로 열어 둠). 실리는 것은 개념/원자 식별자와 성취기준 *코드*(사실정보·공공)뿐
이며 본문·학생 데이터·PII가 없다.

7계층: L1 영속 모델의 조회 표면(L5 api) — 수학 로직 없음. 세션 결선은 concepts.py 선례
(`Annotated[AsyncSession, Depends(get_session)]`).
"""

from __future__ import annotations

from typing import Annotated, Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.curriculum_entry import CurriculumEntry
from whymath_backend.db.session import get_session

router = APIRouter(prefix="/v1/alignments", tags=["alignment"])

# get_session 의존성 — Annotated 메타데이터(B008 회피, concepts.py 선례).
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 축 식별자(요청 필터·응답 표시 공용). 축 순서가 곧 합성 순서다(모듈 docstring).
AlignmentAxis = Literal["concept_standard_link", "curriculum_entry", "atom_node"]

# offset 상한 — 축별 LIMIT(offset+limit) 인출을 메모리 유한하게 묶는다(모듈 docstring 사유).
_MAX_OFFSET = 10_000


class AlignmentItem(BaseModel):
    """정렬 항목 1건 — (개념 키, 성취기준 참조) 쌍 + 축 출처 표시.

    축마다 어휘가 다르다(정직 표시 — 가짜 통일 금지): `concept_key`는 1축=concept_code
    ('UC.*' 계열)·2축=concept_id(개념 그래프 키)·3축=원자 code. `standard_ref`는
    1축=norm_id('2022_2수_01_01')·2·3축=official_code 계열('[2수01-01]'). 소비처가 어휘를
    오인 조인하지 않도록 `standard_ref_kind`를 동봉한다. 어휘 통일은 CUR-12 몫이다.
    """

    model_config = ConfigDict(extra="forbid")

    axis: AlignmentAxis = Field(description="항목이 나온 축 (출처 표시)")
    concept_key: str = Field(description="개념 측 식별자 — 축별 어휘(모델 docstring)")
    standard_ref: str = Field(description="성취기준 측 참조 — 축별 어휘(모델 docstring)")
    standard_ref_kind: Literal["norm_id", "official_code"] = Field(
        description="standard_ref의 어휘 종류 — 1축=norm_id, 2·3축=official_code"
    )
    link_type: str | None = Field(
        default=None,
        description="연결 의미('직접'/'재매핑'/'준용') — concept_standard_link 축만, 그 외 null",
    )
    framework_id: str | None = Field(
        default=None,
        description="셀의 소속 프레임워크 — curriculum_entry 축만(미분류·타 축은 null)",
    )


@router.get(
    "",
    response_model=list[AlignmentItem],
    summary="개념↔성취기준 정렬 통합 조회 (3축 합성)",
)
async def list_alignments(
    session: SessionDep,
    axis: Annotated[
        AlignmentAxis | None,
        Query(description="축 필터 — 지정하면 그 축만 조회(미지정=3축 전부)"),
    ] = None,
    concept_key: Annotated[
        str | None,
        Query(min_length=1, max_length=128, description="개념 측 식별자 필터(축별 어휘 그대로)"),
    ] = None,
    standard_ref: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=64,
            description="성취기준 측 참조 필터(축별 어휘 그대로 — norm_id 또는 official_code)",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="페이지 크기")] = 50,
    offset: Annotated[
        int, Query(ge=0, le=_MAX_OFFSET, description="건너뛸 항목 수(상한 있음 — 모듈 docstring)")
    ] = 0,
) -> list[AlignmentItem]:
    """3축 정렬 재료의 합성 목록 — 축-우선 결정적 순서, limit/offset.

    필터는 셋 다 선택이다(미지정=카탈로그 나열). `concept_key`/`standard_ref`는 축마다 다른
    어휘 컬럼에 *그대로* 대조한다 — norm_id 어휘로 2·3축이 잡히지 않는 것은 정직한 결과다
    (어휘 번역은 CUR-12 몫). 각 축은 필요할 때만 SELECT한다(앞 축에서 offset+limit 항목이
    차면 뒤 축 조회 생략 — 결정적 순서라 안전).
    """
    needed = offset + limit
    items: list[AlignmentItem] = []

    # ── 1축: concept_standard_link (행 1건 = 항목 1건) ──────────────────
    # 축별 stmt/result 변수는 이름을 분리한다 — Select[...]가 엔티티별 제네릭이라
    # 한 변수를 재사용하면 mypy --strict가 뒤 축의 행 타입을 앞 축으로 고정한다.
    if axis in (None, "concept_standard_link"):
        link_stmt = select(ConceptStandardLink)
        if concept_key is not None:
            link_stmt = link_stmt.where(ConceptStandardLink.concept_code == concept_key)
        if standard_ref is not None:
            link_stmt = link_stmt.where(ConceptStandardLink.norm_id == standard_ref)
        link_stmt = link_stmt.order_by(
            ConceptStandardLink.concept_code,
            ConceptStandardLink.norm_id,
            ConceptStandardLink.link_type,
        ).limit(needed)
        link_result = await session.execute(link_stmt)
        for link in link_result.scalars().all():
            items.append(
                AlignmentItem(
                    axis="concept_standard_link",
                    concept_key=link.concept_code,
                    standard_ref=link.norm_id,
                    standard_ref_kind="norm_id",
                    link_type=link.link_type,
                )
            )

    # ── 2축: curriculum_entry.national_standard_codes (배열 평탄화) ─────
    if axis in (None, "curriculum_entry") and len(items) < needed:
        entry_stmt = select(CurriculumEntry).where(
            # 빈 배열·NULL 행 제외 — 행 1건 ≥ 항목 1건이어야 축별 LIMIT 인출이
            # 합성 순서의 prefix를 보존한다(모듈 docstring 페이지네이션 논증).
            sa.func.cardinality(CurriculumEntry.national_standard_codes)
            > 0
        )
        if concept_key is not None:
            entry_stmt = entry_stmt.where(CurriculumEntry.concept_id == concept_key)
        if standard_ref is not None:
            # `x = ANY(배열)` 대조 — ARRAY comparator `.any()`는 관계용 PropComparator.any와
            # 스텁이 충돌해 mypy --strict가 거부하므로 typed 표면인 sa.any_ 비교식을 쓴다.
            entry_stmt = entry_stmt.where(
                sa.literal(standard_ref) == sa.any_(CurriculumEntry.national_standard_codes)
            )
        entry_stmt = entry_stmt.order_by(CurriculumEntry.entry_id).limit(needed)
        entry_result = await session.execute(entry_stmt)
        for entry in entry_result.scalars().all():
            for code in entry.national_standard_codes or []:
                # standard_ref 필터는 SQL이 *행*을 잡고, 항목 수준 대조는 여기서 한다
                # (배열엔 다른 코드도 함께 있을 수 있음 — 행 매칭≠항목 매칭).
                if standard_ref is not None and code != standard_ref:
                    continue
                items.append(
                    AlignmentItem(
                        axis="curriculum_entry",
                        concept_key=entry.concept_id,
                        standard_ref=code,
                        standard_ref_kind="official_code",
                        framework_id=entry.framework_id,
                    )
                )
            if len(items) >= needed:
                break

    # ── 3축: atom_node.standard_codes (배열 평탄화) ─────────────────────
    if axis in (None, "atom_node") and len(items) < needed:
        atom_stmt = select(AtomNode).where(sa.func.cardinality(AtomNode.standard_codes) > 0)
        if concept_key is not None:
            atom_stmt = atom_stmt.where(AtomNode.code == concept_key)
        if standard_ref is not None:
            atom_stmt = atom_stmt.where(
                sa.literal(standard_ref) == sa.any_(AtomNode.standard_codes)
            )
        atom_stmt = atom_stmt.order_by(AtomNode.code).limit(needed)
        atom_result = await session.execute(atom_stmt)
        for atom in atom_result.scalars().all():
            for code in atom.standard_codes or []:
                if standard_ref is not None and code != standard_ref:
                    continue
                items.append(
                    AlignmentItem(
                        axis="atom_node",
                        concept_key=atom.code,
                        standard_ref=code,
                        standard_ref_kind="official_code",
                    )
                )
            if len(items) >= needed:
                break

    return items[offset : offset + limit]
