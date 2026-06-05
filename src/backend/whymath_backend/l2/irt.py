"""L2 학습자 모델 — IRT(Item Response Theory) 문항 난이도·학생 능력 동시 추정.

BKT(`l2/bkt`)가 *개념별 숙달*을 시간축으로 추적한다면, IRT는 *문항 난이도*와 *학생 능력 θ*를
같은 잠재 척도(logit)에 놓고 추정한다. 한 학생의 응답들(정/오답)에서 능력 θ를, 여러 학생의
응답에서 문항 난이도 b를 추정한다(본 슬라이스는 *능력 추정*만 — 난이도 적합은 후속).

θ의 쓰임: 적응형 문항 선택(학생 능력 근처 난이도 문항이 정보량 최대)·IRT 기반 진단(MasteryState
theta·DB Schema)·BKT와 교차검증.

2PL 모델(2-parameter logistic):
    P(정답 | θ, item) = 1 / (1 + exp(-a·(θ - b)))
  - **b**(difficulty): 난이도 — θ=b에서 정답 확률 0.5. 클수록 어려움.
  - **a**(discrimination): 변별도 — 곡선 기울기(클수록 능력 차를 민감하게 가름). a=1=Rasch(1PL).

능력 추정(MLE·Newton-Raphson): 관측 응답의 로그우도를 최대화하는 θ.
    grad  L'(θ) = Σ aᵢ·(정답ᵢ - Pᵢ)
    info -L''(θ) = Σ aᵢ²·Pᵢ·(1-Pᵢ)   (Fisher 정보)
    θ ← θ + grad/info
  전부 정답/전부 오답이면 MLE가 ±∞로 발산 → 경계값 반환(clamp). θ는 [lower, upper]로 제한.

이 슬라이스(L2 IRT 첫 슬라이스): *순수 추정*만(외부 의존 0·결정론). 범위 밖(후속): 문항 난이도
적합(JMLE/MML)·문항정보함수 기반 적응형 출제·3PL(추측 c)·시계열 적재·BKT 융합.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

_THETA_LOWER = -4.0  # logit 척도 실질 하한(P≈0.018 @ a=1,b=0)
_THETA_UPPER = 4.0  # 상한(P≈0.982)


class IrtItem(BaseModel):
    """2PL 문항 파라미터 — 난이도 b·변별도 a. 불변(frozen)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    difficulty: float = Field(description="b — 난이도(θ=b에서 정답 확률 0.5). logit 척도.")
    discrimination: float = Field(
        default=1.0, gt=0.0, description="a — 변별도(곡선 기울기). 기본 1.0=Rasch(1PL). 양수."
    )


def probability_correct(theta: float, item: IrtItem) -> float:
    """능력 θ인 학생이 `item`을 맞힐 확률 — 2PL 로지스틱."""
    return 1.0 / (1.0 + math.exp(-item.discrimination * (theta - item.difficulty)))


def estimate_ability(
    responses: list[tuple[IrtItem, bool]],
    *,
    initial: float = 0.0,
    max_iter: int = 50,
    tol: float = 1e-6,
    lower: float = _THETA_LOWER,
    upper: float = _THETA_UPPER,
) -> float:
    """관측 응답(문항, 정/오답)들에서 학생 능력 θ를 MLE(Newton-Raphson)로 추정.

    빈 응답이면 `initial`(정보 없음). *전부 정답*이면 `upper`·*전부 오답*이면 `lower`(MLE
    발산 → 경계). 그 외엔 Newton 반복(Fisher 정보로 나눠 갱신)·매 스텝 [lower, upper] clamp·
    스텝<tol이면 수렴 종료. 결정론적(같은 입력→같은 θ).
    """
    if not responses:
        return initial
    if all(correct for _, correct in responses):
        return upper
    if not any(correct for _, correct in responses):
        return lower

    theta = initial
    for _ in range(max_iter):
        grad = 0.0
        info = 0.0  # Fisher 정보(-Hessian)
        for item, correct in responses:
            p = probability_correct(theta, item)
            a = item.discrimination
            grad += a * ((1.0 if correct else 0.0) - p)
            info += a * a * p * (1.0 - p)
        if info <= 1e-12:  # pragma: no cover — 방어적 수치 가드(정상 입력선 도달 불가)
            break  # 정보 0(극단 θ) — 더 못 움직임
        step = grad / info
        theta = min(max(theta + step, lower), upper)
        if abs(step) < tol:
            break
    return theta


__all__ = [
    "IrtItem",
    "estimate_ability",
    "probability_correct",
]
