"""WH-1 2단계 종료 게이트 — 진단-실제 일치율 *유의 개선* 판정(McNemar·라벨 프로브).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4 2단계 *종료 기준* — "진단-실제
일치율이 **베이스라인 대비 유의 개선**". 본 모듈은 그 *판정 좌석*이다. 후보(candidate) 진단
파이프라인이 베이스라인 대비 라벨 프로브셋에서 *통계적으로 유의하게* 더 높은 top-1 일치율
(recall)을 내는지 McNemar 검정으로 가린다 — 단순히 "조금 높다"가 아니라 *유의 개선*만 PASS.

정직 스코프(가장 중요):
  - **오프라인·시스템 지표**다. LIVE 학생별 ground-truth가 아니다 — 라벨 프로브(틀린 진술→
    `expected_id` 오개념)에 매처를 돌려 *top-1 == expected_id* 비율을 잰다. 실제 학생의 진짜
    오개념은 자가보고되지 않아(문항-오개념 태깅·attempt별 진단 기록 부재) LIVE per-user 일치율은
    여전히 데이터 기반이 없다(후속). 이 게이트는 *진단엔진 품질의 회귀/개선*을 잰다.
  - **베이스라인 = substring 매처**(`diagnose` top-1·결정론·항상 가용·보수적 기준선·② 지표와
    동일 신호). **후보 = 주입**(`candidate` Matcher) — 프로덕션은 의미 매처(pgvector 임베딩·더
    높은 recall이나 임베딩 의존)를 주입하고, 테스트는 합성 매처를 주입한다(임베딩 비의존 검증).
  - **McNemar(쌍체 검정)**: 같은 프로브셋을 두 매처가 각각 풀므로 *쌍체*다. 불일치쌍만 본다 —
    b=베이스라인만 맞춤·c=후보만 맞춤. H0(차이 없음) 하에 c~Binom(b+c, 0.5). *단측* 정확
    이항검정으로 "후보가 더 맞춤(c 큼)"의 p값을 내고 `alpha` 미만이면 유의 개선. 정규근사 대신
    정확 이항이라 소표본에도 타당(연속성보정·근사 불요).
  - **날조 0**: 라벨 프로브가 `_MIN_PROBES` 미만이면 NO_DATA(value 없이 판정 보류). 불일치쌍이
    적으면 *유의에 도달 못 해* 자연히 NOT_IMPROVED(과소표본은 거짓 PASS를 내지 않는다).

계층(설계 §1): 횡단 인프라(하네스). L4 진단(`diagnose`·라벨 프로브)을 *조회만* 한다. 범위 밖
(후속): 의미 매처 후보 *결선*(임베딩 provider·integration)·LIVE per-user 일치율(문항-오개념
태깅·attempt 진단 기록)·게이트 결과 API 노출·코호트별 층화.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.l4.misconception.probes import _iter_fp_probes, _iter_recall_probes

__all__ = [
    "AgreementGate",
    "AgreementVerdict",
    "Matcher",
    "Phase2Exit",
    "Phase2ExitVerdict",
    "Phase2Report",
    "PrecisionGuard",
    "PrecisionVerdict",
    "evaluate_agreement_gate",
    "evaluate_phase2_exit",
    "evaluate_precision_guard",
    "run_agreement_gate",
    "run_precision_guard",
    "substring_matcher",
]

# 라벨 프로브가 이보다 적으면 게이트 판정 보류(NO_DATA·날조 0). 너무 적은 프로브로는 일치율
# 자체가 종단 노이즈라 *유의 개선* 판정이 무의미하다(실 프로브셋은 수십 건이라 통과).
_MIN_PROBES = 5

# 유의수준(단측). 후보가 더 맞춘다는 단측 McNemar p가 이 값 미만이면 유의 개선.
_DEFAULT_ALPHA = 0.05

# 매처 = 학생 풀이 진술 → top-1 오개념 id(없으면 None). 베이스라인=substring·후보=주입(의미/합성).
Matcher = Callable[[str], str | None]


def substring_matcher(statement: str) -> str | None:
    """베이스라인 매처 — `diagnose`(substring·결정론) top-1 오개념 id(매치 0이면 None).

    ② 진단정확도 지표와 *동일 신호*(보수적 기준선·임베딩 비의존). 후보 매처(의미)가 이보다
    유의하게 높은 일치율을 내는지가 2단계 종료 기준이다.
    """
    matches = diagnose(statement)
    return matches[0].misconception.id if matches else None


class AgreementVerdict(str, Enum):
    """2단계 종료 게이트 판정 — 유의 개선/비개선/데이터부족(날조 0)."""

    IMPROVED = "improved"
    """🟢 후보가 베이스라인 대비 *유의하게* 높은 일치율(단측 McNemar p < alpha). 2단계 종료 충족."""

    NOT_IMPROVED = "not_improved"
    """🟡 유의 개선 아님 — 동등·악화·또는 개선이나 비유의(과소표본 포함). 종료 기준 미충족."""

    NO_DATA = "no_data"
    """🔴 라벨 프로브 부족(`_MIN_PROBES` 미만) — 판정 보류(가짜 PASS/FAIL 금지)."""


class AgreementGate(BaseModel):
    """진단 일치율 게이트 결과 — 베이스라인 vs 후보 recall + McNemar 유의 판정. 불변(frozen)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: AgreementVerdict = Field(description="유의 개선/비개선/데이터부족.")
    n_probes: int = Field(ge=0, description="평가한 라벨 recall 프로브 수.")
    baseline_recall: float | None = Field(
        default=None, description="베이스라인 top-1 일치율(프로브 0이면 None)."
    )
    candidate_recall: float | None = Field(
        default=None, description="후보 top-1 일치율(프로브 0이면 None)."
    )
    discordant_baseline_only: int = Field(
        ge=0, description="b — 베이스라인만 맞춘 불일치쌍(후보가 놓침)."
    )
    discordant_candidate_only: int = Field(
        ge=0, description="c — 후보만 맞춘 불일치쌍(베이스라인이 놓침)."
    )
    p_value: float | None = Field(
        default=None, description="단측 McNemar 정확 이항 p값(NO_DATA면 None)."
    )
    note: str = Field(description="한국어 판정 근거 — 일치율·불일치쌍·유의수준·정직 스코프.")


def _mcnemar_one_sided_p(b: int, c: int) -> float:
    """단측 McNemar 정확 이항 p값 — "후보가 더 맞춘다(c 큼)" 방향(순수).

    불일치쌍 n=b+c, H0 하에서 후보-우세 횟수 c ~ Binom(n, 0.5). p = P(X >= c) =
    Σ_{k=c}^{n} C(n,k)·0.5ⁿ. 불일치쌍이 없으면(n=0) 차이 증거 없음 → 1.0. 정확 이항이라
    소표본에도 타당(정규근사·연속성보정 불요).
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = math.fsum(math.comb(n, k) for k in range(c, n + 1))
    return tail * (0.5**n)


def evaluate_agreement_gate(
    paired: Sequence[tuple[bool, bool]],
    *,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> AgreementGate:
    """쌍체 (베이스라인 맞춤, 후보 맞춤) 결과 → 유의 개선 판정(순수·결정론·McNemar).

    각 원소는 한 라벨 프로브에서 (베이스라인 top-1==expected, 후보 top-1==expected)다. 절차:
      - 프로브가 `min_probes` 미만이면 **NO_DATA**(일치율은 참고로 채우되 verdict 보류·p None).
      - 불일치쌍 b(베이스라인만)·c(후보만) 집계 → 단측 McNemar p. 후보 일치율 > 베이스라인이고
        p < alpha면 **IMPROVED**, 아니면 **NOT_IMPROVED**(동등·악화·비유의·과소표본 포함).

    유의에 *도달 못 하는* 과소표본은 NOT_IMPROVED로 떨어진다(거짓 PASS 0). 입력 비변형.
    """
    n = len(paired)
    baseline_hits = sum(1 for bh, _ in paired if bh)
    candidate_hits = sum(1 for _, ch in paired if ch)
    b_only = sum(1 for bh, ch in paired if bh and not ch)
    c_only = sum(1 for bh, ch in paired if ch and not bh)
    baseline_recall = baseline_hits / n if n else None
    candidate_recall = candidate_hits / n if n else None

    if n < min_probes:
        return AgreementGate(
            verdict=AgreementVerdict.NO_DATA,
            n_probes=n,
            baseline_recall=baseline_recall,
            candidate_recall=candidate_recall,
            discordant_baseline_only=b_only,
            discordant_candidate_only=c_only,
            p_value=None,
            note=(
                f"라벨 recall 프로브 {n}건 — 최소 {min_probes}건 미만이라 유의 개선 판정 보류"
                "(NO_DATA·가짜 PASS/FAIL 금지). 라벨 프로브가 채워지면 McNemar 게이트 가동. "
                "오프라인·시스템 지표(LIVE per-user ground-truth 아님)."
            ),
        )

    p_value = _mcnemar_one_sided_p(b_only, c_only)
    improved = (
        candidate_recall is not None
        and baseline_recall is not None
        and candidate_recall > baseline_recall
        and p_value < alpha
    )
    verdict = AgreementVerdict.IMPROVED if improved else AgreementVerdict.NOT_IMPROVED
    head = "유의 개선" if improved else "유의 개선 아님"
    return AgreementGate(
        verdict=verdict,
        n_probes=n,
        baseline_recall=baseline_recall,
        candidate_recall=candidate_recall,
        discordant_baseline_only=b_only,
        discordant_candidate_only=c_only,
        p_value=p_value,
        note=(
            f"{head} — 베이스라인 recall {baseline_recall:.4f}·후보 recall {candidate_recall:.4f}"
            f"(프로브 {n}건). 불일치쌍 b(베이스라인만)={b_only}·c(후보만)={c_only}, 단측 McNemar "
            f"정확 이항 p={p_value:.4f} (alpha={alpha}). 쌍체 검정(같은 프로브셋)·과소표본은 "
            "유의 미달로 NOT_IMPROVED(거짓 PASS 0). 오프라인·시스템 지표(LIVE ground-truth 아님)."
        ),
    )


def run_agreement_gate(
    *,
    candidate: Matcher,
    baseline: Matcher = substring_matcher,
    probes: Sequence[tuple[str, str]] | None = None,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> AgreementGate:
    """라벨 프로브셋에 베이스라인·후보 매처를 돌려 쌍체 결과를 만들고 유의 개선 판정.

    `probes`(생략 시 패키지 라벨 recall 프로브 `_iter_recall_probes`)의 각 (statement,
    expected_id)에 두 매처를 적용해 (베이스라인 top-1==expected, 후보 top-1==expected) 쌍을
    만들고 `evaluate_agreement_gate`에 넘긴다. `baseline` 기본은 substring(② 지표 동일 신호·
    결정론). `candidate`는 *주입 필수* — 프로덕션은 의미 매처, 테스트는 합성 매처. 매처가 None을
    반환하면(매치 0) 그 프로브는 자동 miss(expected와 불일치)다(억지 매칭 금지·§3.3 정신).
    """
    probe_list = list(probes) if probes is not None else _iter_recall_probes()
    paired = [
        (baseline(statement) == expected_id, candidate(statement) == expected_id)
        for statement, expected_id in probe_list
    ]
    return evaluate_agreement_gate(paired, alpha=alpha, min_probes=min_probes)


# ──────────────────────────────────────────────────────────────────────────────
# 정밀도(거짓양성) 회귀 가드 — recall만으론 정확성 #1을 못 지킨다
# ──────────────────────────────────────────────────────────────────────────────
# recall 게이트는 후보가 *틀린 진술*을 더 잘 잡는지만 본다. 그러나 후보가 recall을 올리며
# *올바른 진술*에 오개념을 더 많이 오매칭하면(거짓양성↑) 학생을 *틀렸다고 오판*한다 — CLAUDE.md
# 의사결정 우선순위에서 교수학적 정확성(#3·"틀렸다고 거짓 표기 금지")은 학습효과·UX·비용보다
# 위다. 그래서 2단계 종료는 "recall 유의 개선" *그리고* "정밀도 무회귀"를 함께 요구해야 한다.
# 이 가드는 FP 프로브(올바른 진술)에서 후보가 베이스라인보다 *유의하게 더 많이* 오매칭하는지를
# 같은 단측 McNemar로 가린다(방향만 반대 — 후보-우세 FP가 나쁜 신호다).


class PrecisionVerdict(str, Enum):
    """정밀도 회귀 가드 판정 — 무회귀/회귀/데이터부족(날조 0)."""

    NO_REGRESSION = "no_regression"
    """🟢 후보의 거짓양성이 베이스라인보다 *유의하게 많지 않음*. 정밀도 안전(종료 허용 가능)."""

    REGRESSED = "regressed"
    """🔴 후보가 올바른 진술에 오개념을 *유의하게 더* 오매칭(단측 McNemar p<alpha) — 정확성
    #1 위반 위험. recall이 올라도 2단계 종료 *불가*(학생 오판 증가)."""

    NO_DATA = "no_data"
    """🔴 FP 프로브 부족(`_MIN_PROBES` 미만) — 판정 보류(가짜 PASS/FAIL 금지)."""


class PrecisionGuard(BaseModel):
    """정밀도 회귀 가드 결과 — FP 프로브에서 베이스라인 vs 후보 거짓양성률 + McNemar 판정. 불변."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: PrecisionVerdict = Field(description="무회귀/회귀/데이터부족.")
    n_probes: int = Field(ge=0, description="평가한 FP(올바른 진술) 프로브 수.")
    baseline_fp_rate: float | None = Field(
        default=None, description="베이스라인 거짓양성률(프로브 0이면 None)."
    )
    candidate_fp_rate: float | None = Field(
        default=None, description="후보 거짓양성률(프로브 0이면 None)."
    )
    discordant_baseline_only: int = Field(
        ge=0, description="b' — 베이스라인만 오매칭(후보는 옳게 침묵)."
    )
    discordant_candidate_only: int = Field(
        ge=0, description="c' — 후보만 오매칭(후보가 새로 만든 거짓양성·나쁜 신호)."
    )
    p_value: float | None = Field(
        default=None, description="단측 McNemar 정확 이항 p값(후보-우세 FP 방향·NO_DATA면 None)."
    )
    note: str = Field(description="한국어 판정 근거 — FP율·불일치쌍·유의수준·정확성 #1 스코프.")


def evaluate_precision_guard(
    paired_fp: Sequence[tuple[bool, bool]],
    *,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> PrecisionGuard:
    """쌍체 (베이스라인 오매칭, 후보 오매칭) 결과 → 정밀도 회귀 판정(순수·McNemar).

    각 원소는 한 FP 프로브(올바른 진술)에서 (베이스라인이 오개념 매칭함, 후보가 오매칭함)다 —
    True가 *거짓양성*(나쁨). 절차:
      - 프로브가 `min_probes` 미만이면 **NO_DATA**(FP율은 참고로 채우되 verdict 보류·p None).
      - 불일치쌍 b'(베이스라인만 오매칭)·c'(후보만 오매칭) 집계 → 단측 McNemar p. 후보 FP율 >
        베이스라인이고 p < alpha면 **REGRESSED**(정밀도 유의 악화), 아니면 **NO_REGRESSION**.

    recall 게이트와 *같은* `_mcnemar_one_sided_p`를 쓰되 방향이 반대다 — 여기선 후보-우세 불일치
    (c' 큼)가 *나쁜* 신호다(거짓양성 증가). 입력 비변형.
    """
    n = len(paired_fp)
    baseline_fp = sum(1 for bfp, _ in paired_fp if bfp)
    candidate_fp = sum(1 for _, cfp in paired_fp if cfp)
    b_only = sum(1 for bfp, cfp in paired_fp if bfp and not cfp)
    c_only = sum(1 for bfp, cfp in paired_fp if cfp and not bfp)
    baseline_fp_rate = baseline_fp / n if n else None
    candidate_fp_rate = candidate_fp / n if n else None

    if n < min_probes:
        return PrecisionGuard(
            verdict=PrecisionVerdict.NO_DATA,
            n_probes=n,
            baseline_fp_rate=baseline_fp_rate,
            candidate_fp_rate=candidate_fp_rate,
            discordant_baseline_only=b_only,
            discordant_candidate_only=c_only,
            p_value=None,
            note=(
                f"FP 프로브 {n}건 — 최소 {min_probes}건 미만이라 정밀도 회귀 판정 보류"
                "(NO_DATA·가짜 PASS/FAIL 금지). 올바른 진술 프로브가 채워지면 가드 가동."
            ),
        )

    p_value = _mcnemar_one_sided_p(b_only, c_only)
    regressed = (
        candidate_fp_rate is not None
        and baseline_fp_rate is not None
        and candidate_fp_rate > baseline_fp_rate
        and p_value < alpha
    )
    verdict = PrecisionVerdict.REGRESSED if regressed else PrecisionVerdict.NO_REGRESSION
    head = "정밀도 유의 회귀" if regressed else "정밀도 무회귀"
    return PrecisionGuard(
        verdict=verdict,
        n_probes=n,
        baseline_fp_rate=baseline_fp_rate,
        candidate_fp_rate=candidate_fp_rate,
        discordant_baseline_only=b_only,
        discordant_candidate_only=c_only,
        p_value=p_value,
        note=(
            f"{head} — 베이스라인 FP율 {baseline_fp_rate:.4f}·후보 FP율 {candidate_fp_rate:.4f}"
            f"(FP 프로브 {n}건). 불일치쌍 b'(베이스라인만)={b_only}·c'(후보만)={c_only}, 단측 "
            f"McNemar p={p_value:.4f} (alpha={alpha}). 후보-우세 거짓양성이 유의하면 REGRESSED "
            "— 정확성 #1(학생 오판 금지) 보호. 오프라인·시스템 지표(LIVE ground-truth 아님)."
        ),
    )


def run_precision_guard(
    *,
    candidate: Matcher,
    baseline: Matcher = substring_matcher,
    fp_probes: Sequence[str] | None = None,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> PrecisionGuard:
    """FP 프로브셋에 베이스라인·후보를 돌려 쌍체 오매칭 결과를 만들고 정밀도 회귀 판정.

    `fp_probes`(생략 시 패키지 FP 프로브 `_iter_fp_probes` — 올바른 진술)의 각 statement에 두
    매처를 적용해 (베이스라인 매칭됨, 후보 매칭됨) 쌍을 만든다 — 매처가 *non-None* id를 내면
    그 진술에 오개념을 붙인 것이라 *거짓양성*(올바른 진술이므로). `evaluate_precision_guard`에
    넘긴다. `baseline` 기본은 substring(② 지표 동일 신호). `candidate`는 *주입 필수*.
    """
    probe_list = list(fp_probes) if fp_probes is not None else _iter_fp_probes()
    paired = [
        (baseline(statement) is not None, candidate(statement) is not None)
        for statement in probe_list
    ]
    return evaluate_precision_guard(paired, alpha=alpha, min_probes=min_probes)


# ──────────────────────────────────────────────────────────────────────────────
# 2단계 종료 결합 판정 — recall 유의 개선 AND 정밀도 무회귀
# ──────────────────────────────────────────────────────────────────────────────


class Phase2ExitVerdict(str, Enum):
    """2단계 종료 결합 판정 — 충족/미충족/데이터부족."""

    READY = "ready"
    """🟢 recall 유의 개선(IMPROVED) *그리고* 정밀도 무회귀(NO_REGRESSION). 2단계 종료 충족."""

    NOT_READY = "not_ready"
    """🟡 recall 비개선 *또는* 정밀도 회귀 — 종료 기준 미충족. 정밀도 회귀는 정확성 #1 위반
    위험이라 recall이 올라도 종료 불가."""

    NO_DATA = "no_data"
    """🔴 recall 또는 정밀도 가드가 데이터부족(NO_DATA) — 결합 판정 보류(가짜 PASS/FAIL 금지)."""


class Phase2Exit(BaseModel):
    """2단계 종료 결합 결과 — recall 게이트 + 정밀도 가드를 AND로 묶은 최종 판정. 불변."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Phase2ExitVerdict = Field(description="충족/미충족/데이터부족.")
    recall_verdict: AgreementVerdict = Field(description="recall(진단 일치율) 게이트 판정.")
    precision_verdict: PrecisionVerdict = Field(description="정밀도(거짓양성) 회귀 가드 판정.")
    note: str = Field(description="한국어 결합 근거 — 두 축 판정과 종료 가부.")


def evaluate_phase2_exit(recall: AgreementGate, precision: PrecisionGuard) -> Phase2Exit:
    """recall 게이트 + 정밀도 가드 → 2단계 종료 결합 판정(순수).

    **READY**는 recall이 `IMPROVED` *그리고* 정밀도가 `NO_REGRESSION`일 때만. 둘 중 하나라도
    `NO_DATA`면 **NO_DATA**(데이터로 종료를 *certify* 못 함). 그 외(recall 비개선 또는 정밀도
    회귀)는 **NOT_READY**. 정밀도 회귀는 정확성 #1 위반 위험이라 recall 개선을 *덮어쓴다*
    (recall만으론 종료 금지 — 이 결합이 그 안전장치다).
    """
    if recall.verdict is AgreementVerdict.NO_DATA or precision.verdict is PrecisionVerdict.NO_DATA:
        verdict = Phase2ExitVerdict.NO_DATA
        head = "데이터부족 — 종료 판정 보류"
    elif (
        recall.verdict is AgreementVerdict.IMPROVED
        and precision.verdict is PrecisionVerdict.NO_REGRESSION
    ):
        verdict = Phase2ExitVerdict.READY
        head = "2단계 종료 충족"
    else:
        verdict = Phase2ExitVerdict.NOT_READY
        head = "2단계 종료 미충족"
    return Phase2Exit(
        verdict=verdict,
        recall_verdict=recall.verdict,
        precision_verdict=precision.verdict,
        note=(
            f"{head} — recall={recall.verdict.value}·정밀도={precision.verdict.value}. 종료는 "
            "recall 유의 개선 AND 정밀도 무회귀를 함께 요구한다(정밀도 회귀는 정확성 #1 위반 "
            "위험이라 recall 개선을 덮어쓴다). 오프라인·시스템 지표(LIVE ground-truth 아님)."
        ),
    )


class Phase2Report(BaseModel):
    """2단계 종료 *전체* 리포트 — recall 게이트 + 정밀도 가드 + 결합 판정을 한 번에. 불변.

    ops/스크립트가 "2단계 종료 기준 충족?"을 *근거와 함께* 읽도록 세 결과를 묶는다 — 결합
    `decision`만이 아니라 두 축의 일치율·FP율·불일치쌍·p값까지 담아 *왜* 그 판정인지 보인다
    (전역 집계는 HTTP 미노출·ops 스크립트가 직접 호출하는 컨벤션의 직렬화 표면).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    recall: AgreementGate = Field(description="recall(진단 일치율) 게이트 — 전체 수치.")
    precision: PrecisionGuard = Field(description="정밀도(거짓양성) 회귀 가드 — 전체 수치.")
    decision: Phase2Exit = Field(description="결합 종료 판정(recall AND 정밀도).")
