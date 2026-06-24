"""L4 수식 음성화 — 학년별 낭독 프로파일 (교수학 데이터·정본).

"같은 구조를 학년에 맞게 다르게 읽는" 결정의 단일 출처. 모델(계약)은 `schema/speech.py::
GradeProfile`이고, 이 파일은 그 *값*(교수학적 결정)을 보유한다. L3 변환 엔진은 이 프로파일을
함수 인자로 주입받는다(`l4/speech/__init__.py` 배선).

S1 범위: **고등** 프로파일을 완비(MVP 페르소나 A 고3 — 미적분·삼각·지수로그·확통 전 범위). 초등·
중등·대학은 프레임워크 시연용으로 정의하되 사전 충전·세부 규칙은 S3에서 완성한다.
"""

from __future__ import annotations

from whymath_backend.schema.speech import GradeProfile, SpeechGradeBand

# 구조 키 — 엔진이 introduced_constructs 게이팅에 쓰는 어휘(미도입 구조는 unresolved로 표시).
_ARITHMETIC = frozenset({"fraction", "power", "abs", "factorial"})

PROFILES: dict[SpeechGradeBand, GradeProfile] = {
    # 초등 — 지수·근호 미도입. x²은 '엑스 곱하기 엑스'로 전개(power_style="multiply").
    SpeechGradeBand.초등: GradeProfile(
        grade_band=SpeechGradeBand.초등,
        power_style="multiply",
        sqrt_label=None,
        introduced_constructs=_ARITHMETIC,
    ),
    # 중등 — 제곱·루트 도입. 적분·극한·시그마·미분·콤비네이션은 아직 미도입.
    SpeechGradeBand.중등: GradeProfile(
        grade_band=SpeechGradeBand.중등,
        power_style="square",
        sqrt_label="루트",
        introduced_constructs=_ARITHMETIC | {"root", "subscript", "trig"},
    ),
    # 고등 — MVP 기준(고3). 전 구조 도입.
    SpeechGradeBand.고등: GradeProfile(
        grade_band=SpeechGradeBand.고등,
        power_style="square",
        sqrt_label="루트",
        introduced_constructs=_ARITHMETIC
        | {
            "root",
            "subscript",
            "trig",
            "log",
            "integral",
            "sum",
            "product",
            "limit",
            "derivative",
            "binom",
        },
    ),
    # 대학 — 고등 + (집합·논리·선형대수 기호는 S4 사전 확장). 구조 게이팅은 고등과 동일.
    SpeechGradeBand.대학: GradeProfile(
        grade_band=SpeechGradeBand.대학,
        power_style="square",
        sqrt_label="루트",
        introduced_constructs=_ARITHMETIC
        | {
            "root",
            "subscript",
            "trig",
            "log",
            "integral",
            "sum",
            "product",
            "limit",
            "derivative",
            "binom",
        },
    ),
}
