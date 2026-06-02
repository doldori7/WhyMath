"""오개념 카탈로그 — `docs/prompts/misconception_diagnosis.md` "오개념 카탈로그" 정본.

**스코프 정직**(False-attribute 금기, CLAUDE.md): doc에 *명시된* 항목만 코딩(14종).
나머지 16종("..." 자리표시자)은 pedagogy-designer + Kiki 후속(별도 슬라이스). doc 자체가 정본
완결이 아닌 30개 목표로의 부분 명시이므로, 미명시 항목을 *추정 작성*하지 않는다.

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


CATALOG: tuple[Misconception, ...] = _ALGEBRA + _GEOMETRY + _PROBSTAT + _FUNCTION
"""정본 카탈로그(14종) — doc 명시 항목만. 나머지 16종은 후속(pedagogy-designer)."""


CATALOG_BY_ID: dict[str, Misconception] = {m.id: m for m in CATALOG}
"""ID로 O(1) 조회 — 진단 결과·텔레메트리에서 misconception_id로 역참조 시."""
