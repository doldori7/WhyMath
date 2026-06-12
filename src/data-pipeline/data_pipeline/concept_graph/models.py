"""개념 그래프 Pydantic 모델 — `Concept` 노드 · `ConceptEdge` 엣지.

정본: `docs/data/concept_graph.md`(§2 모델·§2.4 ID 규약·§5 invariant) +
`schemas/v1.1/concept.schema.yaml`·`schemas/v1.1/edge.schema.yaml`.

컨벤션(ncic/models.py·backend schema 답습): `ConfigDict(extra="forbid",
use_enum_values=True, str_strip_whitespace=True)` · 관계/출처는 `str`-Enum · 불변식은
`@field_validator` · 한국어 docstring.

법적(CLAUDE.md·concept_graph.md §1.1): `standard_codes`는 NCIC 성취기준 *코드*만 가리키고
성취기준 *본문(statement)*은 어느 필드에도 복제하지 않는다. 외부 노출 시 `SOURCE_CITATION`
동봉 의무(공공누리 1유형 승계).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# NCIC 승계 출처 문구(concept_graph.md §1.1) — 그래프 외부 노출·라이선싱 시 동봉 의무.
SOURCE_CITATION: Final[str] = (
    "개념-성취기준 매핑 근거: 교육부 고시 제2022-33호 [수학과 교육과정], "
    "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)"
)

# Universal Concept ID 규약(§2.4): UC.<domain약칭>.<topic>.<concept-slug>.
# 4개 점-구분 파트(UC + 3), 소문자·숫자·하이픈. 한 번 발급 후 변경 금지(다른 자산이 join).
CONCEPT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^UC\.[a-z0-9]+\.[a-z0-9-]+\.[a-z0-9-]+$")


def _require_concept_id(value: str) -> str:
    """concept_id가 UC 규약을 지키는지 검증(노드 PK·엣지 src/dst 공용)."""
    if not CONCEPT_ID_PATTERN.match(value):
        raise ValueError(
            f"concept_id 규약 위반: {value!r}. 예상 'UC.<domain>.<topic>.<slug>' "
            "(소문자·숫자·하이픈, 예: 'UC.calc.limit.epsilon-delta')"
        )
    return value


class Relation(str, Enum):
    """개념 관계 유형 — `edge.schema.yaml` values와 1:1.

    주의: `concept_graph.md` 산문은 '6종'이라 적었으나 §2.2 코드블록과 edge.schema.yaml의
    *열거 값은 7종*이다(notation_variant 포함). 열거를 정본으로 채택한다(산문 카운트는 stale).
    """

    PREREQUISITE = "prerequisite"
    GENERALIZATION = "generalization"
    SPECIALIZATION = "specialization"
    CONTRAST = "contrast"
    APPLICATION = "application"
    COMPOSITION = "composition"
    NOTATION_VARIANT = "notation_variant"


class EvidenceSource(str, Enum):
    """엣지 근거의 출처 계열(`edge.schema.yaml`)."""

    NCIC = "ncic"
    CURRICULUM_MATRIX = "curriculum_matrix"
    MATH_EDUCATION_LITERATURE = "math_education_literature"
    EXPERT_REVIEW = "expert_review"


class ReviewStatus(str, Enum):
    """개념 검수 상태 — 적재 보류 표식(concept_graph_dataset_v1.md §4).

    데이터셋 `definition_provenance`가 "수기 검수"면 `REVIEWED`(우선 적재 후보·114건),
    그 외 자동생성·검수필요 계열이면 `PENDING`(전문가 검수 후 적재·289건). 슬라이스 1은
    이 표식만 *부여*하고 게이팅(보류분 제외 적재)은 후속 슬라이스(적재) 몫이다.
    """

    REVIEWED = "reviewed"
    PENDING = "pending"


# 관계·출처·검수상태 enum의 단일 진실(§2.2 "한 곳에서 관리"). 추가 시 위 Enum만 갱신.
RELATION_TYPES: Final[tuple[str, ...]] = tuple(r.value for r in Relation)
EVIDENCE_SOURCES: Final[tuple[str, ...]] = tuple(e.value for e in EvidenceSource)
REVIEW_STATUSES: Final[tuple[str, ...]] = tuple(s.value for s in ReviewStatus)


class Concept(BaseModel):
    """개념 그래프 노드 — `concept.schema.yaml` + 데이터셋 v1 풍부 필드 확장.

    `concept_id`는 UC 규약 PK(curriculum_entry·textbook_mapping과 공유 키). `name_ko`는
    필수, `name_en/ja`는 **선택(Phase 1 KR 단일언어 데이터 수용)** — 다국 표기는 후속.
    `standard_codes`는 NCIC 성취기준 코드 참조(truth source) — 본문은 복제하지 않는다.

    풍부 필드(데이터셋 v1·concept_graph_dataset_v1.md §2 — 2026-06-12 모델 확장 결정):
    `metaphor`(은유)·`accepted_expressions`(허용표현)·`ccss_code`(매칭 CCSS)·
    `misconception_text`(자유텍스트 오개념 — 카탈로그 코드 `misconception_codes`와 *별개*)·
    `difficulty_tier`(난이도층 0~24)·`review_status`(적재 보류 표식).

    법적·redaction(concept_graph_dataset_v1.md §3·CLAUDE.md): 성취기준 *본문* 근접 복제
    위험인 `description`·`formal_definition`은 이 모델에 **일부러 부재** — 모델에 슬롯이
    없어 구조적으로 재유입이 차단된다(누수 0). 이 부재는 의도이므로 추가 금지.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    concept_id: str = Field(
        ...,
        description="Universal Concept ID (PK). 'UC.<domain>.<topic>.<slug>'. 발급 후 변경 금지.",
    )
    name_ko: str = Field(..., min_length=1, description="한국어 명칭(빈 문자열 금지).")
    name_en: str | None = Field(
        default=None,
        min_length=1,
        description="영어 명칭(다국 join 축). Phase 1 KR은 미보유 — None 허용·빈 문자열 금지.",
    )
    name_ja: str | None = Field(
        default=None,
        min_length=1,
        description="일본어 명칭(다국 정합성 키). Phase 1 KR은 미보유 — None 허용·빈 문자열 금지.",
    )
    domain: str = Field(
        ..., min_length=1, description="영역명(NCIC 영역 어휘와 정렬, 예 '미적분')."
    )
    grade_band_hint: str | None = Field(
        default=None,
        description="전형적 도입 학년군(NCIC grade_band 어휘 재사용). 단정 아닌 힌트.",
    )
    prerequisite_concept_ids: list[str] = Field(
        default_factory=list,
        description="선수개념 concept_id 목록. Edge(prerequisite)와 중복 저장(조회 캐시).",
    )
    misconception_codes: list[str] = Field(
        default_factory=list,
        description="오개념 카탈로그 키(Phase 1 30개 — dangling 가능, 검증은 경고).",
    )
    visualization_card_keys: list[str] = Field(
        default_factory=list,
        description="L5 시각화 자산 키(L1은 참조만 — dangling 가능, 검증은 경고).",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="매핑된 NCIC 성취기준 코드(truth source 연결). 본문은 복제 금지.",
    )
    metaphor: str | None = Field(
        default=None,
        description="개념을 직관화하는 은유(데이터셋 v1 교수학 주석). 비어있을 수 있음.",
    )
    accepted_expressions: str | None = Field(
        default=None,
        description="학생이 개념을 '이해했다'고 볼 허용표현(데이터셋 v1). 비어있을 수 있음.",
    )
    ccss_code: str | None = Field(
        default=None,
        description="매칭 미국 CCSS 코드(국제 비교 축). CCSS 본문(statement)은 복제 금지.",
    )
    misconception_text: str | None = Field(
        default=None,
        description=(
            "자유텍스트 오개념(데이터셋 v1). misconception_codes(카탈로그 키)와 *별개* — "
            "자유텍스트라 30-카탈로그 코드로 강제 매핑하지 않는다(코드화는 후속)."
        ),
    )
    difficulty_tier: int | None = Field(
        default=None,
        ge=0,
        le=24,
        description="난이도층 [0, 24](데이터셋 v1). 0=가장 기초.",
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        description=(
            "적재 보류 표식. definition_provenance가 '수기 검수'면 reviewed, "
            "그 외 자동·검수필요면 pending(§4). 게이팅은 후속 적재 슬라이스 몫."
        ),
    )
    notes: str | None = Field(
        default=None,
        description="전문가 검수 메모. 개념 합치기·쪼개기 이력도 기록(ID 안정성 §3.5).",
    )

    @field_validator("concept_id")
    @classmethod
    def _validate_concept_id(cls, v: str) -> str:
        """concept_id가 UC 규약(§2.4)을 지키는지."""
        return _require_concept_id(v)


class ConceptEdge(BaseModel):
    """개념 그래프 엣지 — `edge.schema.yaml`.

    `(src_concept_id, dst_concept_id, relation)` 복합키. `evidence`는 빈 문자열 금지 —
    근거 없는 엣지를 차단한다(§3.2 관계 판정의 주관성 방어). `strength`는 [0.0, 1.0].
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    src_concept_id: str = Field(..., description="관계 출발 개념(UC concept_id).")
    dst_concept_id: str = Field(..., description="관계 도착 개념(UC concept_id).")
    relation: Relation = Field(..., description="관계 유형(7종 enum). 6종 산문은 stale.")
    strength: float = Field(..., ge=0.0, le=1.0, description="관계 강도 [0.0, 1.0].")
    evidence: str = Field(
        ...,
        min_length=1,
        description="관계 판단 근거(빈 문자열 금지 — 근거 없는 엣지 차단).",
    )
    evidence_source: EvidenceSource = Field(..., description="근거 출처 계열(4종 enum).")

    @field_validator("src_concept_id", "dst_concept_id")
    @classmethod
    def _validate_endpoints(cls, v: str) -> str:
        """엣지 양끝도 UC 규약을 지키는지(노드 PK와 동일 키 공간)."""
        return _require_concept_id(v)
