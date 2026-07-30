"""생성기 identity → `problem_type_id` 결정론 매핑표 (S3-27).

설계 정본: `docs/architecture/ai_content_generation_gap_review.md` D3(백로그 `S3-27`) ·
유보 해제 근거는 `docs/architecture/problem_bank_gap_review.md` §5-③ 편집자 부기(2026-07-30).

**핵심 통찰(D3)**: 17 `problem_type_id`는 *인지 행동* 기준이라 문항 텍스트를 읽어야만 분류할 수
있을 것 같지만, 이 코퍼스의 스켈레톤 생성기는 **생성기(혹은 생성기의 밴드 파라미터) 1종이 인지
행동 1종을 고정 산출**한다 — 그래서 "생성기 identity → 유형" 매핑표 하나로 코퍼스 전체를 텍스트
파싱 없이 결정론 분류할 수 있다. 이 모듈이 그 매핑표(정본)다.

**LLM 0·문항 텍스트 파싱/추론 0** — 아래 딕셔너리 값은 전부 사람(에이전트)이 각 생성기 코드
(`l3/equivalent/*_skeleton_generator.py`)와 `problem_type_graph_v1/problem_types.jsonl`의
`behavior_skills`를 대조해 판단한 *정본*이다. 런타임에는 이 표를 찾아보기만 한다(텍스트 추론 없음).

**코퍼스별 식별 키가 다르다** — 생성기 identity가 레코드에 남기는 흔적이 코퍼스마다 다르기 때문
(재계산 0 원칙 — 이미 있는 데이터만 읽는다):
  - `problem_bank_generated_v0`: `unit_codes`가 생성기 클래스와 1:1(quad 4-variant만 한 클래스
    `SkeletonEquivalentProblemGenerator`를 공유해 `unit_codes=('QUAD-EQ',)`로 합쳐진다 — variant
    는 발문 형식만 바꿀 뿐 인지 행동은 동일하므로 **같은 유형**이 맞다).
  - `problem_bank_conceptual_v0`·`problem_bank_misconception_mc_v0`: 한 생성기 클래스
    (`ConceptualCountMCSkeletonGenerator`·`MisconceptionEvalMCSkeletonGenerator`)가 템플릿
    파라미터별로 *다른* 인지 행동을 낸다 — 템플릿 식별자는 레코드에 직접 없지만, 배치 CLI가
    `target_misconception_ids={kebab}` 1종만 주입해 `distractor_map`의 `misconception_id`가
    템플릿을 1:1로 복원한다(`_distractor_kebab`).
  - `problem_bank_killer_v0`: 코퍼스 전체가 `RootAggregateSkeletonGenerator`(Vieta 합/곱) 1종 —
    `unit_codes=('POLY-ROOT',)` 확인만으로 충분(sum/product·차수 구분은 유형에 영향 없음 — 둘 다
    "공식에 대입해 값을 구하는" 동일 인지 행동).
  - `problem_bank_probability_finite_v0`: `unit_codes`가 확률형/개수형 2 밴드를 가른다.
  - `problem_bank_v1`(4건, 레거시 손저작): 생성기 배치 흔적이 없어 slug로 직접 판단(사람 판단·
    아래 개별 주석에 근거 명시).
  - `problem_bank_rephrased_v0`(429건): **명시 제외** — `S4-14`(변형 계보 영속) 미착지로 원
    생성기를 추적할 길이 없다. 이 모듈의 `classify_record`는 이 코퍼스명을 아예 다루지 않는다
    (호출자가 `EXCLUDED_CORPORA`로 사전 필터링).

경계(CLAUDE.md 7계층·`problem_bank_gap_review.md` §5-③ 판정 유지): 이 모듈은 **관측 축**이다.
`problem_type_node` FK 연결·유형별 생성 확대·추천/출제 로직은 스코프 밖 — 여기서 만드는 것은
`Problem.problem_type_codes`에 넣을 *문자열 참조*뿐이다.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = [
    "ALL_PROBLEM_TYPE_IDS",
    "CORPUS_CONCEPTUAL_V0",
    "CORPUS_GENERATED_V0",
    "CORPUS_KILLER_V0",
    "CORPUS_MISCONCEPTION_MC_V0",
    "CORPUS_PROBABILITY_FINITE_V0",
    "CORPUS_REPHRASED_V0",
    "CORPUS_V1",
    "EXCLUDED_CORPORA",
    "PTYPE_CONDITION_SATISFACTION",
    "PTYPE_CONSTRUCT_OBJECT",
    "PTYPE_COUNT_SOLUTIONS",
    "PTYPE_DETERMINE_COEFFICIENT",
    "PTYPE_ENUMERATE_CASES",
    "PTYPE_EVALUATE_EXPRESSION",
    "PTYPE_EXISTENCE_DECISION",
    "PTYPE_GENERALIZE_PATTERN",
    "PTYPE_INFER_RELATIONSHIP",
    "PTYPE_MODEL_WORD_PROBLEM",
    "PTYPE_OPTIMIZE_CONSTRAINED",
    "PTYPE_OPTIMIZE_EXTREMUM",
    "PTYPE_PROVE_STATEMENT",
    "PTYPE_SKETCH_GRAPH",
    "PTYPE_SOLVE_FOR_UNKNOWN",
    "PTYPE_TRANSFORM_EXPRESSION",
    "PTYPE_VERIFY_CLAIM",
    "TARGET_CORPORA",
    "classify_record",
]

# ──────────────────────────────────────────────────────────────────────────
# 17종 problem_type_id 상수 — 정본은 `data/corpus/problem_type_graph_v1/problem_types.jsonl`
# (재정의 아님·오탈자 방지용 리터럴 상수일 뿐). 문자열 값이 정본과 어긋나면 거버넌스 테스트가
# `problem_types.jsonl`을 읽어 대조한다(`test_problem_type_mapping.py`).
# ──────────────────────────────────────────────────────────────────────────
PTYPE_SOLVE_FOR_UNKNOWN = "ptype.solve-for-unknown"
PTYPE_EVALUATE_EXPRESSION = "ptype.evaluate-expression"
PTYPE_DETERMINE_COEFFICIENT = "ptype.determine-coefficient"
PTYPE_EXISTENCE_DECISION = "ptype.existence-decision"
PTYPE_CONDITION_SATISFACTION = "ptype.condition-satisfaction"
PTYPE_COUNT_SOLUTIONS = "ptype.count-solutions"
PTYPE_ENUMERATE_CASES = "ptype.enumerate-cases"
PTYPE_OPTIMIZE_EXTREMUM = "ptype.optimize-extremum"
PTYPE_OPTIMIZE_CONSTRAINED = "ptype.optimize-constrained"
PTYPE_INFER_RELATIONSHIP = "ptype.infer-relationship"
PTYPE_GENERALIZE_PATTERN = "ptype.generalize-pattern"
PTYPE_PROVE_STATEMENT = "ptype.prove-statement"
PTYPE_MODEL_WORD_PROBLEM = "ptype.model-word-problem"
PTYPE_CONSTRUCT_OBJECT = "ptype.construct-object"
PTYPE_VERIFY_CLAIM = "ptype.verify-claim"
PTYPE_SKETCH_GRAPH = "ptype.sketch-graph"
PTYPE_TRANSFORM_EXPRESSION = "ptype.transform-expression"

ALL_PROBLEM_TYPE_IDS: frozenset[str] = frozenset(
    {
        PTYPE_SOLVE_FOR_UNKNOWN,
        PTYPE_EVALUATE_EXPRESSION,
        PTYPE_DETERMINE_COEFFICIENT,
        PTYPE_EXISTENCE_DECISION,
        PTYPE_CONDITION_SATISFACTION,
        PTYPE_COUNT_SOLUTIONS,
        PTYPE_ENUMERATE_CASES,
        PTYPE_OPTIMIZE_EXTREMUM,
        PTYPE_OPTIMIZE_CONSTRAINED,
        PTYPE_INFER_RELATIONSHIP,
        PTYPE_GENERALIZE_PATTERN,
        PTYPE_PROVE_STATEMENT,
        PTYPE_MODEL_WORD_PROBLEM,
        PTYPE_CONSTRUCT_OBJECT,
        PTYPE_VERIFY_CLAIM,
        PTYPE_SKETCH_GRAPH,
        PTYPE_TRANSFORM_EXPRESSION,
    }
)

# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 디렉터리명 상수 — `data/corpus/problem_bank_*` 관례.
# ──────────────────────────────────────────────────────────────────────────
CORPUS_V1 = "problem_bank_v1"
CORPUS_GENERATED_V0 = "problem_bank_generated_v0"
CORPUS_CONCEPTUAL_V0 = "problem_bank_conceptual_v0"
CORPUS_KILLER_V0 = "problem_bank_killer_v0"
CORPUS_MISCONCEPTION_MC_V0 = "problem_bank_misconception_mc_v0"
CORPUS_PROBABILITY_FINITE_V0 = "problem_bank_probability_finite_v0"
CORPUS_REPHRASED_V0 = "problem_bank_rephrased_v0"

# 백필 대상(결정론 순서) — `problem_bank_rephrased_v0`은 없다(S4-14 미착지·명시 제외).
TARGET_CORPORA: tuple[str, ...] = (
    CORPUS_V1,
    CORPUS_GENERATED_V0,
    CORPUS_CONCEPTUAL_V0,
    CORPUS_KILLER_V0,
    CORPUS_MISCONCEPTION_MC_V0,
    CORPUS_PROBABILITY_FINITE_V0,
)

EXCLUDED_CORPORA: frozenset[str] = frozenset({CORPUS_REPHRASED_V0})


def _unit_codes(record: Mapping[str, object]) -> tuple[str, ...]:
    """레코드의 `unit_codes` → 정렬된 튜플(순서 무관 매핑 키). 부재·비배열은 빈 튜플."""
    raw = record.get("unit_codes")
    if not isinstance(raw, list):
        return ()
    return tuple(sorted(v for v in raw if isinstance(v, str)))


def _distractor_kebab(record: Mapping[str, object]) -> str | None:
    """`distractor_map`이 태깅하는 오개념 kebab 1종을 복원 — 밴드(=생성기 템플릿) 식별자 대리.

    `conceptual_count_mc_batch`·`misconception_mc_batch`의 각 밴드는
    `EquivalenceSpec.target_misconception_ids={kebab}` 정확히 1종만 주입하므로, 저장된 레코드의
    `distractor_map` 오답 전부가 같은 `misconception_id`를 가리킨다(생성기 계약). 0개나 2개 이상
    이면 밴드를 복원할 수 없으므로 `None`(미태깅)을 반환한다 — 침묵 오분류 금지.
    """
    dmap = record.get("distractor_map")
    if not isinstance(dmap, list) or not dmap:
        return None
    kebabs = {
        entry.get("misconception_id")
        for entry in dmap
        if isinstance(entry, dict) and isinstance(entry.get("misconception_id"), str)
    }
    if len(kebabs) != 1:
        return None
    (kebab,) = kebabs
    return kebab


# ──────────────────────────────────────────────────────────────────────────
# `problem_bank_generated_v0` — unit_codes → problem_type_id (harness/problem_corpus_batch.py
# 밴드 대조·2026-07-30 실측: 각 unit_codes 값은 정확히 1개의 스켈레톤 생성기 클래스가 산출한다).
# ──────────────────────────────────────────────────────────────────────────
_GENERATED_V0_UNIT_TO_TYPE: dict[tuple[str, ...], str] = {
    # SkeletonEquivalentProblemGenerator(variant=short_answer/sqrt/multiple_choice/
    # sqrt_multiple_choice 4종 — 전부 같은 클래스, unit_codes로 합쳐짐) — "이차방정식의 두 근 중
    # 하나를 구하시오": 방정식을 풀어 미지수 값을 구하는 전형적 solve-for-unknown
    # (behavior_skills에 quadratic-equation-solving이 정확히 있음).
    ("QUAD-EQ",): PTYPE_SOLVE_FOR_UNKNOWN,
    # CalculusExtremumSkeletonGenerator — "극솟값을 가질 때 그 x의 값을 구하시오": 극값(x좌표)을
    # 찾는 최적화 절차(도함수=0·부호 판정) → optimize-extremum(behavior_skills: completing-square·
    # solution-checking이 이 절차와 정확히 대응).
    ("CALC-EXTREMUM",): PTYPE_OPTIMIZE_EXTREMUM,
    # CalculusExtremumValueSkeletonGenerator — "극댓값을 구하시오"(값 자체) — 같은 극값 판정
    # 절차의 산출물이 x좌표 대신 값일 뿐 인지 행동은 동일 → optimize-extremum.
    ("CALC-EXTREMUM-VALUE",): PTYPE_OPTIMIZE_EXTREMUM,
    # CalculusExtremumMCSkeletonGenerator — 극값(값) 객관식. 오개념(극대·극소 혼동·값↔좌표 혼동)
    # 자체가 "극값 판정" 절차를 표적으로 하므로 optimize-extremum.
    ("CALC-EXTREMUM-MC",): PTYPE_OPTIMIZE_EXTREMUM,
    # CalculusIrrationalExtremumSkeletonGenerator — 임계점이 p±√q인 무리수 극값. 절차 동일
    # (도함수=0의 근을 구해 극대·극소 판정) → optimize-extremum.
    ("CALC-EXTREMUM-IRR",): PTYPE_OPTIMIZE_EXTREMUM,
    # CalculusTangentSlopeSkeletonGenerator — "접선의 기울기가 m인 점의 x좌표를 구하시오": f'(x)=m
    # 이라는 *방정식을 세워 그 해(x)를 구하는* 문제라 극값 판정과 달리 solve-for-unknown이 정확
    # (극대·극소 여부를 안 따진다 — 근 자체가 답).
    ("CALC-TANGENT",): PTYPE_SOLVE_FOR_UNKNOWN,
    # ExponentialEquationSkeletonGenerator — "bˣ=bᵏ를 만족하는 x의 값을 구하시오": 지수방정식을
    # 풀어 미지수 값을 구함 → solve-for-unknown(equation-rearrangement).
    ("EXP-EQ",): PTYPE_SOLVE_FOR_UNKNOWN,
    # LogarithmicEquationSkeletonGenerator — "log_b x=k를 만족하는 x"도 동일하게 방정식 풀이 →
    # solve-for-unknown.
    ("LOG-EQ",): PTYPE_SOLVE_FOR_UNKNOWN,
    # ArithmeticSequenceSkeletonGenerator — "첫째항 a·공차 d일 때 제n항을 구하시오": 방정식을
    # 세울 필요 없이 공식(aₙ=a+(n-1)d)에 값을 대입만 하면 되는 절차 실행형 →
    # evaluate-expression(behavior_skills의 polynomial-arithmetic과 정확 대응).
    ("ARITH-SEQ",): PTYPE_EVALUATE_EXPRESSION,
    # GeometricSequenceSkeletonGenerator — 등비수열 제n항, 동일 논리(공식 대입) → evaluate-expr.
    ("GEO-SEQ",): PTYPE_EVALUATE_EXPRESSION,
    # ArithmeticSumSkeletonGenerator — Sₙ=n(2a+(n-1)d)/2 공식 대입 → evaluate-expression.
    ("ARITH-SUM",): PTYPE_EVALUATE_EXPRESSION,
    # GeometricSumSkeletonGenerator — Sₙ=a(rⁿ-1)/(r-1) 공식 대입 → evaluate-expression.
    ("GEO-SUM",): PTYPE_EVALUATE_EXPRESSION,
    # TrigonometricValueSkeletonGenerator — "sin 210°의 값을 구하시오": 특수각 값을 직접 계산 →
    # evaluate-expression(방정식을 풀 필요 없음 — 단일 함수값 평가).
    ("TRIG-VAL",): PTYPE_EVALUATE_EXPRESSION,
    # TrigonometricEquationSkeletonGenerator — "0°≤x<360°에서 cos x=1/2의 가장 작은 해를 구하시오":
    # 방정식을 풀고 구간 내 해를 선택하는 문제라 quad 근 선택과 동형 → solve-for-unknown.
    ("TRIG-EQ",): PTYPE_SOLVE_FOR_UNKNOWN,
    # InductiveSequenceSkeletonGenerator — (가)(나) 조건 나열 + 점화식으로 수열을 귀납 정의하고
    # 특정 항을 구함: 명시된 공식이 아니라 점화 규칙에서 등차/등비 패턴을 *일반화*한 뒤 계산해야
    # 하므로 ARITH-SEQ류(공식 직접 대입)와 다르다 → generalize-pattern(description이 명시적으로
    # "수열·귀납 관찰형"을 예시로 든다).
    ("IND-SEQ",): PTYPE_GENERALIZE_PATTERN,
}

# ──────────────────────────────────────────────────────────────────────────
# `problem_bank_conceptual_v0` — 오개념 kebab(=`ConceptualCountMCSkeletonGenerator`의
# `CountTemplateKind`) → problem_type_id. 15밴드 전부 `harness/conceptual_count_mc_batch.py`
# `_BANDS`·`l3/equivalent/conceptual_count_mc_generator.py` 대조(2026-07-30 실측).
# ──────────────────────────────────────────────────────────────────────────
_CONCEPTUAL_V0_KEBAB_TO_TYPE: dict[str, str] = {
    # real_root_count — "서로 다른 실근의 개수를 구하시오"(0 또는 1) → count-solutions.
    "discriminant-negative-no-real-root": PTYPE_COUNT_SOLUTIONS,
    # extremum_count — "극값의 개수를 구하시오"(임계점≠극값 함정) → count-solutions.
    "critical-point-implies-extremum": PTYPE_COUNT_SOLUTIONS,
    # excluded_point_count — 정의역에서 제외되는 점의 개수(분모=0) → count-solutions.
    "division-by-zero": PTYPE_COUNT_SOLUTIONS,
    # root_loss_count — 양변을 나눠 잃은 근을 포함한 실제 근 개수 → count-solutions.
    "root-loss-by-dividing": PTYPE_COUNT_SOLUTIONS,
    # is_one_to_one — "실수 전체에서 일대일대응이면 1, 아니면 0": 함수의 성질(역함수 존재와 직결)에
    # 대한 참/거짓 판정 — 오개념("일대일 아니어도 역함수 있음")을 직접 반박하는 주장 검증형이라
    # verify-claim(existence-decision보다 "오개념 주장의 참/거짓을 가른다"는 본질에 더 가깝다).
    "invertibility-without-1-1": PTYPE_VERIFY_CLAIM,
    # geometric_convergence — "등비급수가 수렴하는가"(오개념: 늘 수렴) 참/거짓 → verify-claim.
    "geometric-series-always-converges": PTYPE_VERIFY_CLAIM,
    # limit_equals_value — "극한값=함숫값인가"(불연속 함정) 참/거짓 → verify-claim.
    "limit-equals-function-value": PTYPE_VERIFY_CLAIM,
    # is_differentiable — "연속이면 미분가능한가"(오개념 반박) 참/거짓 → verify-claim.
    "continuity-implies-differentiability": PTYPE_VERIFY_CLAIM,
    # series_converges — "항이 0으로 가면 급수가 수렴하는가"(오개념 반박) 참/거짓 → verify-claim.
    "term-to-zero-implies-convergence": PTYPE_VERIFY_CLAIM,
    # mean_equals_median — "평균=중앙값인가" 참/거짓 → verify-claim.
    "mean-vs-median": PTYPE_VERIFY_CLAIM,
    # events_independent — "배반사건은 독립인가"(오개념 반박) 참/거짓 → verify-claim.
    "mutually-exclusive-implies-independent": PTYPE_VERIFY_CLAIM,
    # conditional_equal — "P(A|B)=P(B|A)인가"(검사 오류) 참/거짓 → verify-claim.
    "prosecutor-fallacy": PTYPE_VERIFY_CLAIM,
    # congruent_by_ratio — "닮음이면 합동인가"(오개념 반박) 참/거짓 → verify-claim.
    "similarity-vs-congruence": PTYPE_VERIFY_CLAIM,
    # dot_product_scalar — "내적이 벡터인가"(오개념 반박·실제는 스칼라) 참/거짓 → verify-claim.
    "dot-product-is-vector": PTYPE_VERIFY_CLAIM,
    # inequality_direction — "부등식 방향이 유지되는가"(음수 곱 함정) 참/거짓 → verify-claim.
    "sign-flip-in-inequality": PTYPE_VERIFY_CLAIM,
}

# ──────────────────────────────────────────────────────────────────────────
# `problem_bank_misconception_mc_v0` — 오개념 kebab(=`MisconceptionEvalMCSkeletonGenerator`의
# `TemplateKind`) → problem_type_id. `harness/misconception_mc_batch.py` `_BANDS` 45종 전수 대조
# (2026-07-30 실측 — 각 발문의 "구하시오" 대상을 확인). 대다수(42종)는 주어진 수·식을 절차대로
# 계산해 값을 내는 evaluate-expression이나, **3종은 예외**(방정식을 "푸는" 문제·경우의 수를
# "세는" 문제라 다른 인지 행동) — 아래 예외 주석 참조.
# ──────────────────────────────────────────────────────────────────────────
_MISCONCEPTION_MC_V0_KEBAB_TO_TYPE: dict[str, str] = {
    "distribution-over-power": PTYPE_EVALUATE_EXPRESSION,  # "(a+b)^2의 값을 구하시오".
    "chain-rule-inner-derivative-omitted": PTYPE_EVALUATE_EXPRESSION,  # "f'(1)의 값을 구하시오".
    "sine-distributes-over-sum": PTYPE_EVALUATE_EXPRESSION,  # "sin(A+B)의 값을 구하시오".
    "exponent-zero": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(a^0 포함 식).
    "square-root-positivity": PTYPE_EVALUATE_EXPRESSION,  # "√((-p)^2)의 값을 구하시오".
    "log-distribution": PTYPE_EVALUATE_EXPRESSION,  # "log_b(...)의 값을 구하시오".
    "composite-function-commutes": PTYPE_EVALUATE_EXPRESSION,  # "(f∘g)(4)의 값을 구하시오".
    "period-of-scaled-sine": PTYPE_EVALUATE_EXPRESSION,  # "함수의 주기를 구하시오"(공식 대입).
    "translation-sign-flip": PTYPE_EVALUATE_EXPRESSION,  # "g(7)의 값을 구하시오".
    "product-rule-naive": PTYPE_EVALUATE_EXPRESSION,  # "x=6에서의 미분계수를 구하시오".
    "fraction-cancellation": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(분수 계산).
    "angle-sum-non-triangle": PTYPE_EVALUATE_EXPRESSION,  # "내각의 크기의 합을 구하시오"(공식).
    "area-perimeter-confusion": PTYPE_EVALUATE_EXPRESSION,  # "직사각형의 넓이를 구하시오".
    "circle-radius-squared": PTYPE_EVALUATE_EXPRESSION,  # "원의 반지름의 길이를 구하시오".
    "gambler-fallacy": PTYPE_EVALUATE_EXPRESSION,  # "다음 시행에서 나올 확률을 구하시오".
    "fraction-addition-naive": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(분수 덧셈).
    "negative-times-negative": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(정수 곱셈).
    "subtract-negative-sign": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(정수 뺄셈).
    "absolute-value-keeps-sign": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(절댓값+정수).
    "sqrt-distributes-over-sum": PTYPE_EVALUATE_EXPRESSION,  # "√(...)의 값을 구하시오".
    "difference-of-squares-confused": PTYPE_EVALUATE_EXPRESSION,  # "x²-a²의 값을 구하시오".
    "exponent-product-multiplies": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(지수 곱).
    "power-of-power-adds": PTYPE_EVALUATE_EXPRESSION,  # "(a^m)^n의 값을 구하시오".
    "negative-square-precedence": PTYPE_EVALUATE_EXPRESSION,  # "-a²+b의 값을 구하시오".
    "distribute-first-term-only": PTYPE_EVALUATE_EXPRESSION,  # "x=k일 때의 값을 구하시오"(분배).
    "negative-distribute-sign": PTYPE_EVALUATE_EXPRESSION,  # "x=k일 때의 값을 구하시오"(음수분배).
    "square-of-difference-no-cross": PTYPE_EVALUATE_EXPRESSION,  # "(a-b)²의 값을 구하시오".
    "midpoint-sum-only": PTYPE_EVALUATE_EXPRESSION,  # "중점의 좌표를 구하시오"(공식 대입).
    "scale-area-linear": PTYPE_EVALUATE_EXPRESSION,  # "넓이의 비를 구하시오"(닮음비²).
    "negative-even-power-sign": PTYPE_EVALUATE_EXPRESSION,  # "(-a)^n의 값을 구하시오".
    "combine-unlike-terms": PTYPE_EVALUATE_EXPRESSION,  # "x=k일 때의 값을 구하시오"(동류항).
    "complete-square-naive": PTYPE_EVALUATE_EXPRESSION,  # "x=k일 때의 값을 구하시오"(완전제곱).
    "conjugate-product-sum": PTYPE_EVALUATE_EXPRESSION,  # "(√a+b)(√a-b)의 값을 구하시오".
    "gcd-lcm-confused": PTYPE_EVALUATE_EXPRESSION,  # "최소공배수를 구하시오"(직접 계산).
    "decimal-mult-place": PTYPE_EVALUATE_EXPRESSION,  # "값을 구하시오"(소수 곱셈).
    "mixed-number-mult-whole": PTYPE_EVALUATE_EXPRESSION,  # "곱한 값을 구하시오"(대분수).
    "remainder-theorem-sign": PTYPE_EVALUATE_EXPRESSION,  # "나머지를 구하시오"(나머지정리 대입).
    "vieta-sign-error": PTYPE_EVALUATE_EXPRESSION,  # "두 근의 합을 구하시오"(Vieta 공식 대입).
    "trapezoid-area-no-half": PTYPE_EVALUATE_EXPRESSION,  # "사다리꼴의 넓이를 구하시오".
    "scale-volume-linear": PTYPE_EVALUATE_EXPRESSION,  # "부피비의 값을 구하시오"(닮음비³).
    "cone-volume-no-third": PTYPE_EVALUATE_EXPRESSION,  # "원뿔의 부피를 구하시오".
    "circle-area-circumference": PTYPE_EVALUATE_EXPRESSION,  # "원의 넓이를 구하시오".
    # ── 예외 3종 — "값을 구하시오"가 아니라 다른 인지 행동 ──
    # transpose-no-sign-change — "일차방정식 x+13=2의 해를 구하시오": 식이 아니라 *방정식*을
    # 풀어 미지수(해)를 구하는 문제라 solve-for-unknown(linear-equation-solving과 정확 대응).
    "transpose-no-sign-change": PTYPE_SOLVE_FOR_UNKNOWN,
    # combination-no-denominator — "서로 다른 n개에서 r개를 뽑는 조합의 수를 구하시오": 배열·
    # 선택의 경우의 수를 세는 문제 → enumerate-cases(behavior_skills와 가족 설명이 정확 대응).
    "combination-no-denominator": PTYPE_ENUMERATE_CASES,
    # same-item-permutation-no-divide — "같은 것이 있는 순열의 경우의 수를 구하시오" → 동일하게
    # enumerate-cases.
    "same-item-permutation-no-divide": PTYPE_ENUMERATE_CASES,
}

# ──────────────────────────────────────────────────────────────────────────
# `problem_bank_probability_finite_v0` — unit_codes → problem_type_id
# (`harness/finite_probability_batch.py` 4밴드 대조 — 확률형 3밴드는 unit_codes 공유).
# ──────────────────────────────────────────────────────────────────────────
_PROBABILITY_FINITE_V0_UNIT_TO_TYPE: dict[tuple[str, ...], str] = {
    # dice-sum-prob·coin-heads-prob·marble-all-red-prob — "확률을 구하시오"(전수 열거로 계산한
    # 값) → evaluate-expression(killer_v0의 Vieta·misconception_mc의 gambler-fallacy와 동일 논리
    # — 절차대로 계산해 값 하나를 낸다).
    ("PROB-FINITE-ENUM",): PTYPE_EVALUATE_EXPRESSION,
    # dice-sum-count — "경우의 수를 구하시오"(두 주사위 합이 특정 값인 경우) → enumerate-cases.
    ("COUNT-FINITE-ENUM",): PTYPE_ENUMERATE_CASES,
}

# ──────────────────────────────────────────────────────────────────────────
# `problem_bank_v1`(4건·레거시 손저작 시드) — slug → problem_type_id. 배치 흔적이 없어 발문
# 원문을 직접 읽고 판단한다(사람 판단 — acceptance가 허용하는 예외 경로).
# ──────────────────────────────────────────────────────────────────────────
_V1_SLUG_TO_TYPE: dict[str, str] = {
    # "이차방정식 ... 두 근 중 큰 근을 구하시오" — 방정식을 풀어 근 값을 구함 → solve-for-unknown.
    "wm-quad-eq-larger-root": PTYPE_SOLVE_FOR_UNKNOWN,
    # "... 두 근 중 작은 근을 구하시오" — 동일 → solve-for-unknown.
    "wm-quad-eq-smaller-root": PTYPE_SOLVE_FOR_UNKNOWN,
    # "이차함수의 그래프의 축이 직선 x=a일 때, a의 값을 구하시오" — 함수를 완전제곱꼴로 바꿔
    # 미정 좌표(축 위치)를 역으로 결정하는 문제 — solve-for-unknown보다
    # determine-coefficient("여러 조건에서 미정계수·상수를 역으로 결정" 완전제곱 스킬과 정확 대응).
    "wm-quad-fn-axis": PTYPE_DETERMINE_COEFFICIENT,
    # "이차방정식의 서로 다른 실근의 개수는?" — 판별식으로 개수를 셈 → count-solutions.
    "wm-quad-eq-root-count-mc": PTYPE_COUNT_SOLUTIONS,
}


def classify_record(corpus_name: str, record: Mapping[str, object]) -> list[str]:
    """(코퍼스명, 레코드) → `problem_type_codes` 값(0개 또는 1개·결정론).

    미태깅(빈 리스트)은 ①`corpus_name`이 이 표에 없는 코퍼스(신규 코퍼스는 매핑표부터 갱신)
    ②`problem_bank_rephrased_v0`(명시 제외) ③밴드 식별 실패(예: `distractor_map`이 여러
    오개념을 태깅해 kebab을 하나로 못 좁히는 경우) 셋 중 하나다 — 조용한 오분류 대신 항상
    빈 리스트로 정직하게 드러낸다.
    """
    ptype: str | None
    if corpus_name == CORPUS_GENERATED_V0:
        ptype = _GENERATED_V0_UNIT_TO_TYPE.get(_unit_codes(record))
    elif corpus_name == CORPUS_CONCEPTUAL_V0:
        kebab = _distractor_kebab(record)
        ptype = _CONCEPTUAL_V0_KEBAB_TO_TYPE.get(kebab) if kebab is not None else None
    elif corpus_name == CORPUS_MISCONCEPTION_MC_V0:
        kebab = _distractor_kebab(record)
        ptype = _MISCONCEPTION_MC_V0_KEBAB_TO_TYPE.get(kebab) if kebab is not None else None
    elif corpus_name == CORPUS_KILLER_V0:
        # RootAggregateSkeletonGenerator 1종뿐인 코퍼스 — unit_codes 확인은 방어적 가드일 뿐
        # (sum/product·차수 구분은 인지 행동에 영향 없어 매핑 키에 안 넣는다).
        ptype = PTYPE_EVALUATE_EXPRESSION if _unit_codes(record) == ("POLY-ROOT",) else None
    elif corpus_name == CORPUS_PROBABILITY_FINITE_V0:
        ptype = _PROBABILITY_FINITE_V0_UNIT_TO_TYPE.get(_unit_codes(record))
    elif corpus_name == CORPUS_V1:
        slug = record.get("slug")
        ptype = _V1_SLUG_TO_TYPE.get(slug) if isinstance(slug, str) else None
    else:
        ptype = None
    return [ptype] if ptype is not None else []
