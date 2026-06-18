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
from whymath_backend.l4.misconception.probes import _iter_recall_probes

__all__ = [
    "AgreementGate",
    "AgreementVerdict",
    "Matcher",
    "evaluate_agreement_gate",
    "run_agreement_gate",
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
