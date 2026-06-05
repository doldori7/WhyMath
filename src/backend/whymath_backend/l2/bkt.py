"""L2 학습자 모델 — BKT(Bayesian Knowledge Tracing) 숙달 확률 추정.

성취기준(개념)별로 학생의 *숨은 숙달 상태*를 베이지안으로 추적한다. 각 풀이 시도(정/오답)를
관측으로 받아 숙달 확률 P(L)을 갱신한다. 산출 P(L)은 `ConceptMasteryHistory.mastery`
(0~1)로 적재되어 학습 곡선(특성 #16)·콘텐츠 라우팅(난이도 조정)의 입력이 된다.

표준 BKT 4-파라미터(Corbett & Anderson 1994):
  - **p_init** `P(L0)`  — 학습 전 사전 숙달 확률(개념 난이도/선수 의존).
  - **p_transit** `P(T)` — 한 번의 학습 기회마다 *미숙달→숙달* 전이 확률(학습 속도).
  - **p_slip** `P(S)`   — 숙달했음에도 *틀릴* 확률(실수).
  - **p_guess** `P(G)`  — 미숙달인데 *맞힐* 확률(찍기).

갱신 2단계(관측 → 학습):
  1. 베이지안 사후: 관측(정/오답)으로 P(L) 보정.
       정답: P(L|✓) = P(L)·(1-S) / [P(L)·(1-S) + (1-P(L))·G]
       오답: P(L|✗) = P(L)·S     / [P(L)·S     + (1-P(L))·(1-G)]
  2. 학습 전이: P(L') = P(L|obs) + (1-P(L|obs))·T  (관측 후 학습 기회 반영).

다음 정답 확률: P(✓) = P(L)·(1-S) + (1-P(L))·G.

*비퇴화 제약* `S + G < 1`: 만족해야 "정답이 숙달 믿음을 *증가*"시키는 BKT 기본 성질이
성립한다(역이면 모델이 비식별·해석 불가). `BktParameters`가 강제한다.

이 슬라이스(L2 첫 슬라이스) 범위: *순수 추정 알고리즘*만(DB/HTTP/시계열 적재·파라미터 적합
[EM/스펙트럴]·DKT 신경망·정서 신호·오개념 매핑은 후속). 외부 의존 0·완전 결정론.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 문헌 전형값(개념별 적합 전까지의 합리적 기본값). 적합은 후속(EM on AttemptEvent 로그).
_DEFAULT_P_INIT = 0.3
_DEFAULT_P_TRANSIT = 0.1
_DEFAULT_P_SLIP = 0.1
_DEFAULT_P_GUESS = 0.2


class BktParameters(BaseModel):
    """BKT 4-파라미터 — 개념(성취기준) 하나의 학습 동역학. 불변(frozen)·전부 [0,1].

    `p_slip + p_guess < 1`(비퇴화)을 강제 — 위반 시 정답이 숙달 믿음을 낮추는 비식별 모델이
    되어 교수학적으로 무의미하다(`ValueError`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    p_init: float = Field(
        default=_DEFAULT_P_INIT, ge=0.0, le=1.0, description="P(L0) 사전 숙달 확률."
    )
    p_transit: float = Field(
        default=_DEFAULT_P_TRANSIT, ge=0.0, le=1.0, description="P(T) 학습 기회당 전이 확률."
    )
    p_slip: float = Field(
        default=_DEFAULT_P_SLIP, ge=0.0, le=1.0, description="P(S) 숙달했어도 틀릴 확률."
    )
    p_guess: float = Field(
        default=_DEFAULT_P_GUESS, ge=0.0, le=1.0, description="P(G) 미숙달인데 맞힐 확률."
    )

    @model_validator(mode="after")
    def _check_non_degenerate(self) -> Self:
        total = self.p_slip + self.p_guess
        if total >= 1.0:
            raise ValueError(
                f"BKT 비퇴화 제약 위반: p_slip({self.p_slip}) + p_guess({self.p_guess}) "
                f"= {total} ≥ 1. 정답이 숙달 믿음을 높이려면 p_slip + p_guess < 1 이어야 합니다."
            )
        return self


DEFAULT_BKT_PARAMETERS = BktParameters()


def posterior_mastery(prior: float, correct: bool, params: BktParameters) -> float:
    """관측(정/오답) 후 *학습 전이 전* 베이지안 사후 숙달 확률 P(L|obs).

    `prior`는 0~1(범위 밖이면 ValueError). 분모는 비퇴화 파라미터에서 항상 양수.
    """
    if not 0.0 <= prior <= 1.0:
        raise ValueError(f"prior(사전 숙달 확률)는 0~1이어야 합니다(받음: {prior}).")
    if correct:
        num = prior * (1.0 - params.p_slip)
        denom = num + (1.0 - prior) * params.p_guess
    else:
        num = prior * params.p_slip
        denom = num + (1.0 - prior) * (1.0 - params.p_guess)
    if denom == 0.0:
        # prior=0·guess=0(정답) 또는 prior=0·slip=0(오답) 등 극단 — 사후=prior(정보 없음).
        return prior
    return num / denom


def apply_learning(posterior: float, params: BktParameters) -> float:
    """학습 전이 — 관측 후 학습 기회가 미숙달분을 p_transit만큼 숙달로 끌어올린다."""
    return posterior + (1.0 - posterior) * params.p_transit


def update_mastery(prior: float, correct: bool, params: BktParameters) -> float:
    """관측 1회 처리 — 사후(`posterior_mastery`) → 학습 전이(`apply_learning`). 새 P(L) 반환."""
    return apply_learning(posterior_mastery(prior, correct, params), params)


def probability_correct(mastery: float, params: BktParameters) -> float:
    """현재 숙달 확률에서 *다음 문항 정답* 확률 P(✓) = P(L)(1-S) + (1-P(L))G."""
    if not 0.0 <= mastery <= 1.0:
        raise ValueError(f"mastery(숙달 확률)는 0~1이어야 합니다(받음: {mastery}).")
    return mastery * (1.0 - params.p_slip) + (1.0 - mastery) * params.p_guess


class BktModel:
    """파라미터를 고정한 BKT 추정기 — `initial_mastery`에서 시작해 관측을 순차 반영.

    상태(현재 숙달 확률)는 호출자가 보유(stateless 추정기) — 같은 모델로 여러 학생·개념을
    추정하며, 각 (학생,개념)의 P(L)을 외부(시계열 DB)가 들고 다닌다.
    """

    def __init__(self, params: BktParameters | None = None) -> None:
        self.params = params or DEFAULT_BKT_PARAMETERS

    @property
    def initial_mastery(self) -> float:
        """관측 전 사전 숙달 확률 P(L0)."""
        return self.params.p_init

    def update(self, prior: float, correct: bool) -> float:
        """관측 1회 반영 — 새 숙달 확률."""
        return update_mastery(prior, correct, self.params)

    def update_sequence(self, observations: list[bool], prior: float | None = None) -> float:
        """관측 시퀀스(정/오답 리스트)를 순차 반영 — 최종 숙달 확률. prior 생략 시 P(L0)."""
        mastery = self.initial_mastery if prior is None else prior
        for correct in observations:
            mastery = self.update(mastery, correct)
        return mastery

    def predict_correct(self, mastery: float) -> float:
        """현재 숙달 확률에서 다음 정답 확률."""
        return probability_correct(mastery, self.params)


__all__ = [
    "DEFAULT_BKT_PARAMETERS",
    "BktModel",
    "BktParameters",
    "apply_learning",
    "posterior_mastery",
    "probability_correct",
    "update_mastery",
]
