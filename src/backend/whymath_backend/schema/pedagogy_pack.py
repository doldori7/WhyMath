"""교수법 팩(PedagogyPack) 백엔드 Pydantic 계약 — 시더가 packs YAML을 검증·적재하는 형식 게이트.

설계 정본: `docs/reviews/260724_v2_migration_pedagogy_dsl_review.md`(검토서)·ORM
`db/models/pedagogy_dsl.py::PedagogyPack`(영속 좌석). 이 슬라이스(PED-01 후속)는 교수법 팩의
*시더 계약*을 놓는다 — `data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형 팩)을 backend 영속
`pedagogy_pack` 테이블로 멱등 적재하기 전에, 각 팩이 형식·교수학 불변식을 만족하는지 이 Pydantic
모델이 게이트한다(standard_loader의 `AchievementStandard`가 성취기준 코퍼스를 게이트한 것과 동형).

────────────────────────────────────────────────────────────────────────────
필드 명명 규약 (schema 필드명 = ORM 컬럼명 — rename seam 0)
────────────────────────────────────────────────────────────────────────────
`PedagogyPack`의 9개 필드는 ORM `PedagogyPack`(pedagogy_dsl.py)의 9개 컬럼과 *정확히 같은 이름*이다
(k_type·pack_version·api_version·is_stub·socratic_prompt·fading_schedule·forbidden_modes·
required_slots·default_evidence). 따라서 시더는 `record.model_dump()[k]`를 ORM 컬럼 키로 직접
바인딩하며 rename이 없다(misconception 로더가 rename seam 0였던 것과 동형). `k_type`은
`use_enum_values=True`로 직렬화 시 문자열 값("CONCEPT")이 되어 PG native enum 컬럼에 그대로 실린다.

JSONB 직렬화: `required_slots: list[SlotSpec]`는 `model_dump()`가 `list[{type,count}]`(JSON-native
dict 리스트)로 뽑고, `default_evidence`·`fading_schedule`는 이미 dict라 그대로 JSONB에 실린다.

────────────────────────────────────────────────────────────────────────────
교수학 불변식 (`@model_validator(mode="after")` — 시더가 오염 팩을 거부)
────────────────────────────────────────────────────────────────────────────
팩은 *데이터*(코드 아님)라 사람이 YAML로 저작한다. 저작 실수·과목 오염을 형식 게이트에서 잡는다:
  (a) `socratic_prompt`는 반드시 `{domain_example}` 자리표시자를 포함해야 한다 — 발문이 특정
      소단원 예제로 채워질 자리를 비워둔다("유형 불변 발문"·과목 명사 하드코딩 금지의 양성 조건).
  (b) `socratic_prompt`에 SUBJECT_NOUN_BLOCKLIST의 *주제 명사*(이차함수·미분 등)가 들어오면
      거부한다 — 발문은 지식 유형 불변이어야 하며 특정 주제에 묶이면 안 된다(음성 조건).
  (c) `forbidden_modes`의 각 항목은 FORBIDDEN_MODE_VOCAB(폐쇄 어휘)에 속해야 한다 — 런타임 가드가
      읽는 축이라 오탈자·미정의 모드를 차단한다(Kapur/Sweller 제약을 못박는 데이터).
  (d) `required_slots`는 비어 있으면 안 된다 — 팩이 최소 1개 콘텐츠 슬롯을 요구해야 매니페스트가
      의미를 갖는다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import KnowledgeType

# ──────────────────────────────────────────────────────────────────────────
# 폐쇄 어휘: 금지 모드 (forbidden_modes 항목이 반드시 속해야 하는 통제 어휘)
# ──────────────────────────────────────────────────────────────────────────
# 런타임 가드가 읽는 축(Kapur/Sweller 교수학 제약을 데이터로 못박는다). 7 지식유형 팩이 각기
# 자기 유형에 금지되는 교수 모드를 지정한다(예: 개념형은 완전예제 선행 금지·절차형은 생산적 실패
# 금지). 폐쇄 어휘라 오탈자·미정의 모드를 시더가 차단한다 — 확장은 이 상수 갱신 전제.
FORBIDDEN_MODE_VOCAB: frozenset[str] = frozenset(
    {
        "WORKED_EXAMPLE_FIRST",  # 완전예제 선행(개념형 금지 — 정의 암기 유도)
        "PRODUCTIVE_FAILURE",  # 생산적 실패(절차형 금지 — 일부러 헤매게 두기)
        "SINGLE_DIRECTION_DRILL",  # 단방향 반복(표상형 금지 — 한 표현만 훈련)
        "COPY_COMPLETED_PROOF",  # 완성 논증 따라 쓰기(증명형 금지)
        "FORMULA_MEMORIZATION",  # 유형별 공식 암기(모델링형 금지)
        "IMMEDIATE_COORDINATE_REDUCTION",  # 좌표 즉시 환원(공간형 금지)
        "FORMULA_PLUGIN_ONLY",  # 공식 대입만(확률형 금지)
    }
)

# ──────────────────────────────────────────────────────────────────────────
# 주제 명사 블록리스트 (socratic_prompt에 들어오면 거부 — best-effort lint)
# ──────────────────────────────────────────────────────────────────────────
# 소크라테스 발문은 *지식 유형 불변*이어야 한다(과목 명사 하드코딩 금지·특정 소단원 예제는
# `{domain_example}` 자리표시자로 런타임 주입). 이 튜플은 발문에 새어 들어오면 안 되는 대표
# *주제 명사*(TOPIC noun)만 겨냥한다 — best-effort·확장 가능한 lint다. 일반 교수학 어휘
# (좌표·정의·조건·표현 등)는 발문의 정당한 구성요소이므로 *넣지 않는다*(오탐 방지).
SUBJECT_NOUN_BLOCKLIST: tuple[str, ...] = (
    "이차함수",
    "일차함수",
    "삼각함수",
    "지수함수",
    "로그함수",
    "미분",
    "적분",
    "도함수",
    "확률변수",
    "등차수열",
    "등비수열",
    "벡터",
    "행렬",
)

# 발문에 반드시 있어야 하는 자리표시자(특정 소단원 예제가 채워질 자리 — 유형 불변 발문의 양성 조건).
_DOMAIN_EXAMPLE_PLACEHOLDER = "{domain_example}"


# ──────────────────────────────────────────────────────────────────────────
# 보조: SlotSpec (required_slots의 한 항목 — 필요 콘텐츠 슬롯 type·count)
# ──────────────────────────────────────────────────────────────────────────
class SlotSpec(BaseModel):
    """필요 슬롯 매니페스트의 한 항목 — 슬롯 유형(`type`)과 필요 개수(`count`).

    팩이 "이 지식 유형을 가르치려면 어떤 콘텐츠 슬롯이 몇 개 필요한가"를 선언한다(예:
    개념형은 example_pair 4개·contrast_case 2개). `type`은 팩이 정의하는 자유 문자열이라
    enum이 아니다(ORM `pedagogy_content_slot.slot_type`이 TEXT인 것과 정합). `count`는 최소 1
    (슬롯을 요구하려면 1개 이상이어야 의미가 있다). `model_dump()`가 {type,count} dict를 뽑아
    JSONB `required_slots` 배열의 한 원소가 된다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: str = Field(..., description="슬롯 유형(팩 정의 자유 문자열·예: example_pair)")
    count: int = Field(..., ge=1, description="필요 개수(최소 1)")


# ──────────────────────────────────────────────────────────────────────────
# 핵심: PedagogyPack (지식 유형별 교수법 팩의 시더 계약)
# ──────────────────────────────────────────────────────────────────────────
class PedagogyPack(BaseModel):
    """교수법 팩 — 지식 유형(k_type)별 교수 데이터의 시더 계약(ORM `pedagogy_pack` 짝).

    9개 필드는 ORM `PedagogyPack`(pedagogy_dsl.py)의 9개 컬럼과 *같은 이름*이다(rename seam 0 —
    시더가 `model_dump()`를 ORM 컬럼 키로 직접 바인딩). `k_type`은 팩의 PK 축이자 7 지식유형과
    1:1 바인딩 축이다. `is_stub`는 미완성 유형의 자리표시(스텁) 여부다.

    교수학 불변식은 모듈 docstring (a)~(d) 참조 — `@model_validator(mode="after")`가 강제한다.
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 계약의 단일 진실(YAML 오타 키 차단)
        extra="forbid",
        # 직렬화 시 enum 값 그대로(k_type이 "CONCEPT" 문자열로 → PG native enum 컬럼 정합)
        use_enum_values=True,
        # 문자열 양끝 공백 제거(YAML `|` 블록 스칼라의 후행 개행 제거)
        str_strip_whitespace=True,
    )

    # PK 축 = 지식 유형(7유형과 1:1). use_enum_values=True라 검증 후 문자열 값이 된다.
    k_type: KnowledgeType = Field(..., description="지식 유형(7유형 폐쇄 택소노미·팩 PK 축)")
    pack_version: int = Field(default=1, description="팩 버전(기본 1)")
    api_version: str = Field(..., description="팩 API 버전(예: '1.0')")
    is_stub: bool = Field(default=False, description="스텁 팩 여부(미완성 유형 자리표시)")
    socratic_prompt: str = Field(
        ...,
        description="소크라테스 발문 템플릿(과목 명사 금지·{domain_example} 자리표시자 포함)",
    )
    fading_schedule: dict[str, Any] | None = Field(
        default=None,
        description="페이딩(도움 감소) 스케줄(nullable — 팩이 정의)",
    )
    forbidden_modes: list[str] = Field(
        default_factory=list,
        description="금지 모드(런타임 가드·FORBIDDEN_MODE_VOCAB 폐쇄 어휘)",
    )
    required_slots: list[SlotSpec] = Field(
        ...,
        description="필요 슬롯 매니페스트(비어 있으면 안 됨 — 최소 1개)",
    )
    default_evidence: dict[str, Any] = Field(
        ...,
        description="유형별 기본 달성 증거 규격('정답≠달성'의 유형별 기준)",
    )

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _enforce_pedagogy_invariants(self) -> PedagogyPack:
        """교수학 불변식 (a)~(d) 강제 — 시더가 저작 실수·과목 오염 팩을 거부한다.

        분기 (a)·(b)·(c)·(d)는 모듈 docstring 참조. use_enum_values=True라 `self.k_type`은 이미
        문자열 값이므로 오류 메시지에 그대로 담는다.
        """
        # (a) {domain_example} 자리표시자 필수 — 특정 소단원 예제가 채워질 자리(유형 불변 발문).
        if _DOMAIN_EXAMPLE_PLACEHOLDER not in self.socratic_prompt:
            raise ValueError(
                f"교수학 불변식 위반(a): k_type={self.k_type} 팩의 socratic_prompt에 "
                f"필수 자리표시자 '{_DOMAIN_EXAMPLE_PLACEHOLDER}'가 없습니다 — 발문은 특정 "
                "소단원 예제로 채워질 자리를 비워둬야 합니다(주제 하드코딩 금지)."
            )

        # (b) 주제 명사 블록리스트 — 발문에 특정 주제 명사가 새어 들면 거부(유형 불변 위배).
        offenders = [noun for noun in SUBJECT_NOUN_BLOCKLIST if noun in self.socratic_prompt]
        if offenders:
            raise ValueError(
                f"교수학 불변식 위반(b): k_type={self.k_type} 팩의 socratic_prompt에 주제 명사가 "
                f"포함됐습니다: {offenders}. 발문은 지식 유형 불변이어야 하며 특정 주제에 묶이면 "
                "안 됩니다({domain_example} 자리표시자로 런타임 주입하세요)."
            )

        # (c) 금지 모드 폐쇄 어휘 — FORBIDDEN_MODE_VOCAB에 없는 항목 거부(오탈자·미정의 모드 차단).
        unknown_modes = [mode for mode in self.forbidden_modes if mode not in FORBIDDEN_MODE_VOCAB]
        if unknown_modes:
            raise ValueError(
                f"교수학 불변식 위반(c): k_type={self.k_type} 팩의 forbidden_modes에 미정의 모드가 "
                f"있습니다: {unknown_modes}. 허용 어휘: {sorted(FORBIDDEN_MODE_VOCAB)}."
            )

        # (d) required_slots 비어 있으면 안 됨 — 팩은 최소 1개 콘텐츠 슬롯을 요구해야 한다.
        if not self.required_slots:
            raise ValueError(
                f"교수학 불변식 위반(d): k_type={self.k_type} 팩의 required_slots가 비었습니다 — "
                "팩은 최소 1개 필요 슬롯을 선언해야 합니다."
            )

        return self


__all__ = [
    "FORBIDDEN_MODE_VOCAB",
    "SUBJECT_NOUN_BLOCKLIST",
    "PedagogyPack",
    "SlotSpec",
]
