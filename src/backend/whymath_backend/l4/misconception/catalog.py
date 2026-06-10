"""오개념 카탈로그 — `docs/prompts/misconception_diagnosis.md` "오개념 카탈로그" 정본.

**스코프 정직**(False-attribute 금기, CLAUDE.md): doc에 *명시되고 상세화된* 항목만 코딩(22종).
슬: doc에 수능 핵심 4영역(미적분·수열·삼각함수·벡터, doc #16-23)을 *먼저 정본화*한 뒤
코드로 인코딩(doc-first). 아직 이름만 있고 미상세인 #15(continuity-vs-differentiability)·기타
"..." 자리표시자(30개 목표까지)는 후속 — *미상세 항목을 추정 작성하지 않는다*.

각 `canonical_statement`·`counterexample`은 *자체 생성 기본 수학 사실*(교과서/EBS 본문 복제
금지·CLAUDE.md). 반례는 canonical을 실제로 반증한다(수학적 정합 검증 완료).

각 항목의 `signals`(공출현 substring)는 *전형적인 학생 표기*에서 발견되는 토큰. v1은 규칙 기반
— 임베딩·LLM-judged 매칭은 후속(범위 밖). 토큰은 한국어/ASCII/유니코드(²) 형태를 포괄하기
위해 *공통 분모*(여러 표기 모두에 등장하는 단편)를 선택.
"""

from __future__ import annotations

from whymath_backend.l4.misconception.models import Misconception

# 대수 영역 — doc L24-32 (7종).
_ALGEBRA: tuple[Misconception, ...] = (
    Misconception(
        id="distribution-over-power",
        name_kr="제곱 분배 오류",
        domain="대수",
        canonical_statement="(a+b)² = a² + b²",
        counterexample="a=1, b=1",
        signals=("(a+b)", "a² + b²"),
    ),
    Misconception(
        id="sign-flip-in-inequality",
        name_kr="부등식 부호 미반전",
        domain="대수",
        canonical_statement="음수를 곱해도 부등식 부호가 그대로",
        counterexample="-2 < 1에 -1을 곱하면 2 > -1 (부호 반전)",
        signals=("부등식", "음수", "곱"),
    ),
    Misconception(
        id="division-by-zero",
        name_kr="0 나눗셈 가능성 놓침",
        domain="대수",
        canonical_statement="분모에 변수가 와도 항상 정의됨",
        counterexample="분모 = 0이 되는 값에서 식이 무정의",
        signals=("분모", "0"),
    ),
    Misconception(
        id="square-root-positivity",
        name_kr="제곱근 양수 가정",
        domain="대수",
        canonical_statement="√(x²) = x",
        counterexample="x=-3이면 √(x²) = 3 = |x|, x가 아님",
        signals=("√", "x²"),
    ),
    Misconception(
        id="exponent-zero",
        name_kr="0 지수 0 가정",
        domain="대수",
        canonical_statement="a⁰ = 0",
        counterexample="2⁰ = 1 (a≠0인 모든 a에 대해 a⁰ = 1)",
        signals=("a⁰", "0"),
    ),
    Misconception(
        id="fraction-cancellation",
        name_kr="분자 합 약분 오류",
        domain="대수",
        canonical_statement="(a+b)/a = b",
        counterexample="a=2, b=4: (2+4)/2 = 3 ≠ 4",
        signals=("(a+b)/a", "b"),
    ),
    Misconception(
        id="log-distribution",
        name_kr="로그 합 분배",
        domain="대수",
        canonical_statement="log(a+b) = log a + log b",
        counterexample="a=b=1: log 2 ≠ log 1 + log 1 = 0",
        signals=("log(a+b)", "log a + log b"),
    ),
)

# 기하 영역 — doc L36-39 (3종).
_GEOMETRY: tuple[Misconception, ...] = (
    Misconception(
        id="angle-sum-non-triangle",
        name_kr="비삼각형 각 합 혼동",
        domain="기하",
        canonical_statement="모든 다각형의 내각의 합은 180°",
        counterexample="사각형의 내각의 합은 360° (n각형은 (n-2)×180°)",
        signals=("내각", "180"),
    ),
    Misconception(
        id="similarity-vs-congruence",
        name_kr="닮음·합동 혼동",
        domain="기하",
        canonical_statement="닮은 두 도형은 합동이다",
        counterexample="배율 2인 닮음 삼각형은 합동 아님",
        signals=("닮음", "합동"),
    ),
    Misconception(
        id="area-perimeter-confusion",
        name_kr="둘레 늘면 넓이 늘 가정",
        domain="기하",
        canonical_statement="둘레가 크면 넓이도 크다",
        counterexample="가늘고 긴 직사각형은 둘레 大, 넓이 小 가능",
        signals=("둘레", "넓이"),
    ),
)

# 확률·통계 — doc L42-45 (3종).
_PROBSTAT: tuple[Misconception, ...] = (
    Misconception(
        id="gambler-fallacy",
        name_kr="도박사의 오류",
        domain="확률통계",
        canonical_statement="앞면 5번 연속이면 다음은 뒷면이 더 잘 나온다",
        counterexample="독립시행은 과거 결과와 무관 (P=1/2 유지)",
        signals=("동전", "다음"),
    ),
    Misconception(
        id="prosecutor-fallacy",
        name_kr="검사의 오류",
        domain="확률통계",
        canonical_statement="P(A|B) = P(B|A)",
        counterexample="P(증거|무죄) ≠ P(무죄|증거) (베이즈 정리)",
        signals=("P(A|B)", "P(B|A)"),
    ),
    Misconception(
        id="mean-vs-median",
        name_kr="평균·중앙값 혼동",
        domain="확률통계",
        canonical_statement="평균과 중앙값은 항상 같다",
        counterexample="치우친 분포(소득)에서 평균 ≠ 중앙값",
        signals=("평균", "중앙값"),
    ),
)

# 함수 — doc L48-50 (1종 명시 + "..." 자리표시자).
_FUNCTION: tuple[Misconception, ...] = (
    Misconception(
        id="invertibility-without-1-1",
        name_kr="역함수 무조건 존재",
        domain="함수",
        canonical_statement="모든 함수는 역함수를 갖는다",
        counterexample="f(x) = x²는 일대일 아님(전 정의역에서) → 역함수 없음",
        signals=("역함수", "모든"),
    ),
)


# 미적분 — doc L56-59 (3종·수능 핵심). 슬 추가.
_CALCULUS: tuple[Misconception, ...] = (
    Misconception(
        id="chain-rule-inner-derivative-omitted",
        name_kr="연쇄법칙 내부도함수 누락",
        domain="미적분",
        canonical_statement="d/dx[sin(2x)] = cos(2x)",
        counterexample="정답은 2cos(2x) — 내부함수 2x의 도함수 2가 곱해져야 함",
        signals=("d/dx", "cos(2x)"),
    ),
    Misconception(
        id="product-rule-naive",
        name_kr="곱의 미분 오류",
        domain="미적분",
        canonical_statement="(f·g)′ = f′·g′",
        counterexample="f=g=x: (x²)′ = 2x ≠ 1·1 = 1",
        signals=("(f·g)′", "f′·g′"),
    ),
    Misconception(
        id="limit-equals-function-value",
        name_kr="극한=함숫값 가정",
        domain="미적분",
        canonical_statement="lim_{x→a} f(x) = f(a) (항상)",
        counterexample="f(x)=(x²-1)/(x-1)는 x→1 극한 2지만 f(1) 무정의 (불연속점)",
        signals=("극한", "함숫값"),
    ),
)

# 수열 — doc L62-64 (2종·수능 빈출). 슬 추가.
_SEQUENCE: tuple[Misconception, ...] = (
    Misconception(
        id="geometric-series-always-converges",
        name_kr="등비급수 무조건 수렴",
        domain="수열",
        canonical_statement="무한등비급수는 항상 수렴한다",
        counterexample="공비 r=2면 1+2+4+⋯ 발산 — |r|<1일 때만 수렴",
        signals=("등비급수", "수렴"),
    ),
    Misconception(
        id="term-to-zero-implies-convergence",
        name_kr="항→0이면 수렴 가정",
        domain="수열",
        canonical_statement="일반항이 0에 수렴하면 급수도 수렴한다",
        counterexample="조화급수 Σ1/n은 일반항→0이지만 발산",
        signals=("급수", "수렴"),
    ),
)

# 삼각함수 — doc L67-69 (2종·수능 핵심). 슬 추가.
_TRIG: tuple[Misconception, ...] = (
    Misconception(
        id="sine-distributes-over-sum",
        name_kr="사인 합 분배",
        domain="삼각함수",
        canonical_statement="sin(a+b) = sin a + sin b",
        counterexample="a=b=90°: sin180° = 0 ≠ sin90° + sin90° = 2",
        signals=("sin(a+b)", "sin a + sin b"),
    ),
    Misconception(
        id="period-of-scaled-sine",
        name_kr="주기 변환 무시",
        domain="삼각함수",
        canonical_statement="y=sin(2x)의 주기는 2π",
        counterexample="주기는 π — 계수 2가 주기를 2π/2로 줄임",
        signals=("주기", "2π"),
    ),
)

# 벡터 — doc L72-73 (1종·수능 기하). 슬 추가.
_VECTOR: tuple[Misconception, ...] = (
    Misconception(
        id="dot-product-is-vector",
        name_kr="내적 결과를 벡터로",
        domain="벡터",
        canonical_statement="두 벡터의 내적 a·b는 벡터이다",
        counterexample="내적은 스칼라(실수): a·b = |a||b|cosθ",
        signals=("내적", "벡터"),
    ),
)


CATALOG: tuple[Misconception, ...] = (
    _ALGEBRA + _GEOMETRY + _PROBSTAT + _FUNCTION + _CALCULUS + _SEQUENCE + _TRIG + _VECTOR
)
"""정본 카탈로그(22종) — doc 명시·상세화 항목만. 30개 목표까지 나머지는 후속.

순서 안정성: 신규 수능 영역은 기존 14종 *뒤에* 붙인다(진단 동률 정렬이 대수
distribution-over-power를 첫째로 유지 — 회귀 가드)."""


CATALOG_BY_ID: dict[str, Misconception] = {m.id: m for m in CATALOG}
"""ID로 O(1) 조회 — 진단 결과·텔레메트리에서 misconception_id로 역참조 시."""
