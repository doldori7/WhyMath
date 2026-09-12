"""Alignment 통합 조회 HTTP API — 개념↔성취기준 정렬 3축의 *얇은* 합성 표면.

엔드포인트(prefix `/v1/alignments`):
  - GET /v1/alignments — 기존 3축 정렬 재료를 하나의 목록으로 합성 조회.

3축(실측 — CUR-12 acceptance ①과 동일 열거):
  1. `concept_standard_link` — ConceptStandardLink 행(concept_code ↔ norm_id, link_type).
  2. `curriculum_entry`      — CurriculumEntry.national_standard_codes 배열(concept_id ↔ 코드).
  3. `atom_node`             — AtomNode.standard_codes 배열(원자 code ↔ 코드).

── CUR-12 착지 후(통합 함수 경유) ────────────────────────────────────────────
CUR-11 초판은 핸들러가 3축을 각자 SELECT했고, 그 docstring이 "CUR-12가 통합 함수를 세우면 이
핸들러는 그 함수를 경유하도록 갈아끼우는 것이 의도된 진화"라고 미리 지목해 두었다. 그 교체가
끝났다 — 이 핸들러는 이제 **조회 로직을 갖지 않고** `l1/standards/alignment_query.
get_alignments`(단일 진실 원천)를 부른 뒤 HTTP 모델로 옮겨 담기만 한다.
축 간 어휘 통일은 여전히 하지 않는다(Phase 2 물리 테이블 몫) — `standard_ref`는 축마다 다른
어휘(1축=norm_id, 2·3축=official_code 계열)를 *그대로* 실어 나르고, 그 사실을
`standard_ref_kind`로 정직하게 표시한다(조용한 가짜 통일 금지).

정렬·페이지네이션(결정적 — 순서 발명 없이 안정 키만):
  전체 순서 = 축 순서 고정(1→2→3) × 축 내 안정 키 정렬(1축=(concept_code, norm_id, link_type)
  의미 유일키 / 2축=entry_id PK / 3축=code PK, 배열은 저장 순서) — 이 순서는 통합 함수가
  보장한다(`get_alignments`가 축을 값 순으로 돌고 축 내부를 안정 키로 정렬). limit/offset은 이
  합성 순서에 적용한다. 구현은 통합 함수에 축별 `limit=offset+limit`을 주고 합성 후 슬라이스한다
  — 합성 순서가 축-우선(prefix 보존)이라 축별 상한 인출로도 올바른 페이지가 나온다.
  이 방식은 offset+limit 행을 메모리에 올리므로 `offset`에 상한(le=10000)을 둔다 — 무상한
  offset은 축별 인출 폭주가 된다(기존 offset 관례에 상한이 없는 것과 다른 점·사유 명기).

  배열 축의 빈 배열 행은 항목 0건을 낳아 prefix 보존을 깨므로 SQL에서 제외해야 한다 —
  통합 함수의 `require_nonempty=True`가 그 `cardinality(...) > 0` 필터다(행 1건 ≥ 항목 1건
  보장). 기본값이 False인 이유는 반대편 소비처 때문이다: `l2/target_progress`는 빈 배열 행도
  `probed`로 세어야 "매핑 없음"과 "조인 실패"를 구분할 수 있다. 두 요구가 상충하므로 함수가
  플래그로 갈라 두고, 각 소비처가 자기에게 필요한 쪽을 *명시*한다(조용한 기본값 의존 금지).

인가 판단(선례 실측): GET·무인증 — concepts/problems GET "공개 카탈로그" 선례(SEC-07 D1이
GET을 의도적으로 열어 둠). 실리는 것은 개념/원자 식별자와 성취기준 *코드*(사실정보·공공)뿐
이며 본문·학생 데이터·PII가 없다.

7계층: L1 영속 모델의 조회 표면(L5 api) — 수학 로직 없음. 세션 결선은 concepts.py 선례
(`Annotated[AsyncSession, Depends(get_session)]`).
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.session import get_session
from whymath_backend.l1.standards.alignment_query import (
    ALL_AXES,
    get_alignments,
    log_join_stats,
)
from whymath_backend.l1.standards.alignment_query import (
    AlignmentAxis as CoreAlignmentAxis,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/alignments", tags=["alignment"])

# get_session 의존성 — Annotated 메타데이터(B008 회피, concepts.py 선례).
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 축 식별자(요청 필터·응답 표시 공용) — **HTTP 와이어 계약**이라 코어 enum을 그대로 노출하지
# 않고 Literal로 둔다(OpenAPI 스키마 안정). 코어 `alignment_query.AlignmentAxis`와 값이
# 갈리면 안 되므로 `test_alignments.py`가 두 어휘의 일치를 기계로 동결한다.
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
    (어휘 번역은 Phase 2 몫). 조회 자체는 전부 `get_alignments`가 한다 — 이 핸들러는 축 필터와
    페이지 슬라이스, HTTP 모델 변환만 맡는다(조회 로직 복제 0).
    """
    needed = offset + limit
    result = await get_alignments(
        session,
        concept_codes=[concept_key] if concept_key is not None else None,
        outcome_id=standard_ref,
        axes={CoreAlignmentAxis(axis)} if axis is not None else ALL_AXES,
        limit=needed,
        # 페이지네이션의 prefix 보존 요구 — 빈 배열 행을 SQL에서 제외해 "행 1건 ≥ 항목 1건"을
        # 만든다(모듈 docstring). 기본값에 기대지 않고 *명시*한다.
        require_nonempty=True,
    )
    log_join_stats(result.stats, logger=logger, context="api.alignments.list")
    items = [
        AlignmentItem(
            axis=item.axis.value,
            concept_key=item.concept_key,
            standard_ref=item.standard_ref,
            standard_ref_kind=item.standard_ref_kind,
            link_type=item.link_type,
            framework_id=item.framework_id,
        )
        for item in result.alignments
    ]
    return items[offset : offset + limit]
