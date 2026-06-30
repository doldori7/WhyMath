"""오개념 진단·개입 — 모델·인터페이스.

`docs/architecture/04_pedagogy_engine.md` §"오개념 진단·개입"(L121-127) + `docs/prompts/
misconception_diagnosis.md` 정본.

핵심 원칙(스펙 L126 + 절대 금지 §): **직접 교정 ❌ / 반례 유도 ✅ / 구체 사례 ✅**.
학생 라벨링("이건 흔한 오개념이야") 금지·재풀이 강요 금지.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MisconceptionDomain = Literal[
    "대수", "기하", "확률통계", "함수", "미적분", "수열", "삼각함수", "벡터"
]
"""오개념 카탈로그 영역 — 정본 prompt doc 분류. 슬: 대수·기하·확률통계·함수 +
수능 핵심(미적분·수열·삼각함수·벡터). doc `### N 영역` 섹션과 1:1."""


class Misconception(BaseModel):
    """카탈로그 단위 — `docs/prompts/misconception_diagnosis.md` 정본 ID·내용 정렬.

    `signals`는 학생 풀이에 *공출현*해야 매칭되는 substring 토큰(AND). 첫 슬라이스의 매칭은
    규칙 기반(임베딩·LLM-judged는 후속) — 토큰 모두 일치 시 confidence=1.0.

    `counterexample`은 *반례*(패턴 1) 어셈블리 입력. `canonical_statement`는 학생 가정 진술.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        description="정본 ID — kebab-case(예: 'distribution-over-power'). doc과 1:1.",
    )
    name_kr: str = Field(description="짧은 한국어 라벨(예: '제곱 분배').")
    domain: MisconceptionDomain = Field(description="카탈로그 영역.")
    canonical_statement: str = Field(
        description="학생이 *암묵적으로 가정한* 잘못된 진술(예: '(a+b)² = a²+b²').",
    )
    counterexample: str = Field(
        description="반례 입력(예: 'a=1, b=1') — 패턴 1 어셈블리에 사용.",
    )
    signals: tuple[str, ...] = Field(
        description=(
            "학생 풀이에 *공출현*해야 매칭되는 substring 토큰(AND). 모두 일치=confidence 1.0."
        ),
    )
    regex_signals: tuple[str, ...] = Field(
        default=(),
        description=(
            "v1.2 보조 탐지 경로 — *정규화된 텍스트*에 `re.search`로 검사하는 정규식(OR). "
            "주로 *거짓 항등식의 수치 대입*(예: `(3+4)²=3²+4²`)을 잡는다. 미설정(기본 빈 튜플) 시 "
            "기존 substring 동작 불변. confidence 분모는 substring `signals` 기준 유지하고 정규식 "
            "매치는 분자에 *가산*(상한 1.0)하므로, 수치 정규식은 기호 substring 케이스와 "
            "*겹치지 않게*(disjoint) 작성해 기존 confidence·matched_signals를 보존한다."
        ),
    )
    canonical_wrong_form: tuple[str, str] | None = Field(
        default=None,
        description=(
            "거짓 항등식의 *머신 검증 가능* 표현 (lhs, rhs) — SymPy syntax(`**`·`sqrt`·`log`). "
            "부여 시 카탈로그 무결성 테스트가 `identity_status`(동치 권위 단일·L3)로 "
            "**not_identity**(SymPy가 거짓임을 *증명*)임을 강제한다 → 'wrong form이 실제로 "
            "틀렸다'를 문자열이 아닌 *기호 권위*로 못 박는다(감사 §7·동치 권위 일원화). 정직 "
            "스코프: SymPy가 가정 없이 반증 가능한 *다항* 거짓 항등식에만 부여(예 `(a+b)²=a²+b²`·"
            "`a⁰=0`). 정의역 의존(`√(x²)=x`)·초월(`log(a+b)`)·유리식은 SymPy 미결정이라 *부여 "
            "안 함*(거짓 머신 검증 주장 금지·regex/substring·semantic 경로가 담당). "
            "`canonical_statement`(표시 문자열)와 별개의 *구조* 표현이다(표현≠의미)."
        ),
    )
    correct_form: str | None = Field(
        default=None,
        description=(
            "오개념의 *정정 형태*(올바른 항등식·식) — identity-shaped 오개념에만 선택 부여. 학생의 "
            "*검증된* clean 풀이에 이 형태가 나타나면 그 오개념을 *강하게* 반박(−1·정밀 귀속)하는 "
            "신호다(`correct_form_present`·tier). 표기는 `signals`와 동일(위첨자·공백 가변)·매칭은 "
            "`_normalize`(NFKC+공백제거)로 흡수. None(기본)이면 정정 탐지 비활성 → 기존(일반 "
            "clean) 약한 반박 동작 불변. 부여 시 *불변식*: `diagnose(correct_form)`이 그 오개념을 "
            "신뢰 게이트(0.65) 이상으로 내면 안 됨(정정이 자기 오개념으로 confident 오진단 금지) — "
            "카탈로그 테스트로 강제. 그래서 `signals`의 LHS만 공유하고 *틀린 RHS*는 미포함하는 "
            "오개념(distribution·log·곱미분·sin 합분배·a⁰)에만 단다."
        ),
    )


class MisconceptionMatch(BaseModel):
    """진단 결과 1건 — misconception + 신뢰도(0-1) + 매칭 신호(디버그·UI)."""

    model_config = ConfigDict(extra="forbid")

    misconception: Misconception
    confidence: float = Field(ge=0.0, le=1.0)
    matched_signals: tuple[str, ...] = Field(
        default_factory=tuple,
        description="실제 매칭된 substring signals 부분집합(디버그·UI 표시 후보).",
    )
    matched_regex_signals: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "v1.2 — 실제 매치된 `regex_signals` 부분집합(디버그·UI). substring `matched_signals`와 "
            "분리해 보관하므로 기존 소비자의 matched_signals 단언은 불변."
        ),
    )
    semantic_similarity: float | None = Field(
        default=None,
        description=(
            "slice 104 — 의미(임베딩) 매칭 경로의 코사인 유사도. substring/regex 경로의 결과는 "
            "*None*(이 필드 미설정)이고, `semantic_matches`가 만든 결과만 코사인 값을 담는다. "
            "선택 필드(기본 None)라 기존 substring 결과·소비자 단언은 불변. **정직 스코프**: 의미 "
            "유사도는 패러프레이즈·동의어 recall만 반영하고 *방향·부정·등치*는 못 가린다(임베딩 "
            "방향맹 — LLM-judged 후속). confidence와 다른 축(이 값은 진단 신뢰가 아니라 표면 "
            "근접도)이니 호출자는 둘을 혼동하지 말 것."
        ),
    )


class InterventionPattern(str, Enum):
    """개입 패턴 4종 — `docs/prompts/misconception_diagnosis.md` "표준 패턴" 정본.

    값은 doc의 패턴 번호 라벨(`pattern_1` ~ `pattern_4`)과 정렬.
    """

    COUNTEREXAMPLE = "counterexample"  # 패턴 1 — 반례 유도
    CONCRETE_CASE = "concrete_case"  # 패턴 2 — 구체 사례
    VISUALIZATION = "visualization"  # 패턴 3 — 시각화 유도
    REVERSE_REASONING = "reverse_reasoning"  # 패턴 4 — 거꾸로 사고


class InterventionDecision(BaseModel):
    """개입 결정 — 패턴 + 학생에게 노출할 프롬프트(반례·구체사례 어셈블리 후).

    `confidence`가 임계 미만이면 호출자(엔진)는 *진단 보류*(None) — 본 모델은 결정된 경우만
    반환된다(스펙 결정트리 L226).
    """

    model_config = ConfigDict(extra="forbid")

    pattern: InterventionPattern
    prompt: str = Field(description="학생에게 노출할 어셈블된 발화(자각 유도형).")
    misconception_id: str = Field(description="진단된 misconception.id — 텔레메트리.")
