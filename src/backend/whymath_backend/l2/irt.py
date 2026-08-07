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


def theta_to_mastery_proxy(theta: float) -> float:
    """IRT θ → [0,1] 숙달 프록시 — 중앙 난이도(b=0)·단위 변별도(a=1) 정답확률 logistic(θ).

    `probability_correct(θ, IrtItem(difficulty=0, discrimination=1))`의 특수형(Rasch). θ를 BKT
    숙달 P(L)과 *같은 [0,1] 척도*로 환산해 비교한다 — L2 진단(BKT↔IRT 교차검증)·L4 코칭 결정·
    L5 능력 라벨이 공유하는 단일 출처(slice 83에 L4 `_mastery_proxy`·L2 중복 통합).
    """
    return 1.0 / (1.0 + math.exp(-theta))


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


def estimate_difficulty(
    responses: list[tuple[float, bool]],
    *,
    discrimination: float = 1.0,
    initial: float = 0.0,
    max_iter: int = 50,
    tol: float = 1e-6,
    lower: float = _THETA_LOWER,
    upper: float = _THETA_UPPER,
) -> float:
    """관측 응답(학생 능력 θ, 정/오답)들에서 문항 난이도 b를 MLE로 추정 — `estimate_ability`의
    *대칭* (능력 고정·난이도 추정). 문항 보정(item calibration)·JMLE의 b-단계.

    `responses`는 `(학생 능력 θ, 정답 여부)` 쌍. 빈 응답이면 `initial`. *모두 정답*이면 `lower`
    (누구나 맞힘 → 매우 쉬움)·*모두 오답*이면 `upper`(누구도 못 맞힘 → 매우 어려움). Newton:
    `b ← b + Σ -a(정답-P)/Σ a²P(1-P)`(능력 추정과 부호만 반대·정답 많을수록 b↓=쉬워짐).
    매 스텝 [lower, upper] clamp·결정론적. `discrimination`은 이 문항의 a(기본 1.0=Rasch).
    """
    if not responses:
        return initial
    if all(correct for _, correct in responses):
        return lower
    if not any(correct for _, correct in responses):
        return upper

    b = initial
    a = discrimination
    for _ in range(max_iter):
        grad = 0.0
        info = 0.0
        for theta, correct in responses:
            p = 1.0 / (1.0 + math.exp(-a * (theta - b)))
            grad += -a * ((1.0 if correct else 0.0) - p)  # dL/db (능력 추정과 부호 반대)
            info += a * a * p * (1.0 - p)
        if info <= 1e-12:  # pragma: no cover — 방어적 수치 가드(정상 입력선 도달 불가)
            break
        step = grad / info
        b = min(max(b + step, lower), upper)
        if abs(step) < tol:
            break
    return b


def fit_jmle(
    responses: list[tuple[int, int, bool]],
    n_students: int,
    n_items: int,
    *,
    discrimination: float = 1.0,
    max_iter: int = 100,
    tol: float = 1e-3,
) -> tuple[list[float], list[float]]:
    """JMLE(결합 최대우도) 교대 적합 — 응답만으로 능력 θ·난이도 b를 *동시* 추정(문항 자가 보정).

    `responses`는 `(student_index, item_index, 정답)` 희소 삼중쌍(미응답 쌍은 생략 가능). 매 반복:
      ① 현재 난이도로 각 학생 θ 추정(`estimate_ability`)
      ② 현재 능력으로 각 문항 b 추정(`estimate_difficulty`)
      ③ *척도 불확정성*(θ·b 동시 가산 이동 불변) 해소 — 난이도 평균을 0으로 중심화.
    θ·b 변화 최대가 `tol` 미만이면 수렴 종료. `(abilities, difficulties)` 반환.

    응답 없는 학생/문항은 0(추정 정보 없음). 전부 정답/오답 학생·문항은 경계값(clamp)으로 수렴.
    소규모 프로토타입용(응답 1회 그룹화 후 반복은 룩업) — 대규모는 벡터화·MML 후속.
    """
    abilities = [0.0] * n_students
    difficulties = [0.0] * n_items
    if not responses or n_students == 0 or n_items == 0:
        return abilities, difficulties

    # 응답 1회 그룹화: 학생별 [(item_idx, 정답)]·문항별 [(student_idx, 정답)]
    by_student: list[list[tuple[int, bool]]] = [[] for _ in range(n_students)]
    by_item: list[list[tuple[int, bool]]] = [[] for _ in range(n_items)]
    for s_idx, i_idx, correct in responses:
        by_student[s_idx].append((i_idx, correct))
        by_item[i_idx].append((s_idx, correct))

    for _ in range(max_iter):
        max_change = 0.0
        # ① 능력 추정(난이도 고정)
        for s_idx in range(n_students):
            obs = [
                (IrtItem(difficulty=difficulties[i], discrimination=discrimination), c)
                for i, c in by_student[s_idx]
            ]
            new_theta = estimate_ability(obs)
            max_change = max(max_change, abs(new_theta - abilities[s_idx]))
            abilities[s_idx] = new_theta
        # ② 난이도 추정(능력 고정)
        for i_idx in range(n_items):
            obs_b = [(abilities[s], c) for s, c in by_item[i_idx]]
            new_b = estimate_difficulty(obs_b, discrimination=discrimination)
            max_change = max(max_change, abs(new_b - difficulties[i_idx]))
            difficulties[i_idx] = new_b
        # ③ 난이도 중심화(척도 위치 고정) — 응답 있는 문항만 평균에 반영
        active = [difficulties[i] for i in range(n_items) if by_item[i]]
        if active:  # pragma: no branch — 응답 존재 시 항상 참(early return이 빈 응답 차단)
            mean_b = sum(active) / len(active)
            difficulties = [b - mean_b for b in difficulties]
        if max_change < tol:
            break
    return abilities, difficulties


def item_information(theta: float, item: IrtItem) -> float:
    """문항 정보함수 I(θ) = a²·P·(1-P) — 능력 θ에서 이 문항이 주는 측정 정보량.

    P=0.5(θ=b)에서 최대 — 즉 *난이도가 능력과 일치*할 때 가장 정보가 많다(맞힐지 틀릴지
    불확실한 문항이 변별력 최대). 변별도 a가 클수록 정보량↑(a² 가중). 적응형 출제의 핵심.
    """
    p = probability_correct(theta, item)
    return item.discrimination * item.discrimination * p * (1.0 - p)


def total_information(theta: float, items: list[IrtItem]) -> float:
    """검사 정보함수 I(θ) = Σ Iᵢ(θ) — 능력 θ에서 문항 집합이 주는 *총* 측정 정보량.

    개별 문항정보(`item_information`)의 단순 합(문항 응답 독립 가정). 클수록 θ를 정밀하게
    측정한다(표준오차↓). 적응형 검사(CAT)에서 *이미 출제한 문항들*의 정보를 누적해 측정
    정밀도를 가늠한다(중단 규칙·신뢰구간의 입력). 빈 목록이면 0(정보 없음).
    """
    return sum(item_information(theta, item) for item in items)


def ability_standard_error(theta: float, items: list[IrtItem]) -> float:
    """능력 추정 θ의 표준오차 SE(θ) = 1/√I(θ) — 측정 *정밀도*(작을수록 정밀).

    Fisher 정보의 역제곱근(MLE의 점근 표준오차). CAT 중단 규칙의 핵심: SE가 목표(예: 0.3)
    아래로 내려가면 "충분히 정밀하게 측정됨"으로 보고 검사를 종료한다. θ 신뢰구간 θ ± z·SE
    에도 쓰인다. 정보가 0(빈 목록)이면 측정 불가 → `math.inf`(무한 불확실).
    """
    info = total_information(theta, items)
    if info <= 0.0:
        return math.inf
    return 1.0 / math.sqrt(info)


# 학습 목적 성공률 밴드(REC-04) — 문헌값(70~85%), 실측 미보정. S4-15(실응답 난이도 루프)가
# 언젠가 보정하기 전까지는 이 상수 자체가 "band_calibrated=false"의 근거다.
LEARNING_BAND_LOW: float = 0.70
LEARNING_BAND_HIGH: float = 0.85
# 밴드 밖 후보의 가중치 — 0이 아니라 작은 양수다. 완전히 0이면 밴드 안 후보가 하나도 없을 때
# select_weighted_item이 전 후보를 동률 0으로 봐 결정론이 깨진다(전부 배제되는 사고 방지).
LEARNING_BAND_OUT_OF_RANGE_WEIGHT: float = 0.05


def learning_band_weight(
    theta: float,
    item: IrtItem,
    *,
    band_low: float = LEARNING_BAND_LOW,
    band_high: float = LEARNING_BAND_HIGH,
) -> float:
    """학습 목적 가중 — 예상 정답확률이 목표 밴드 안이면 1.0, 밖이면 낮은 가중(REC-04 D4②).

    `select_weighted_item`의 기존 곱 결합 축에 그대로 얹는 가중치다(새 선택기 0) — 약점
    가중·수능 가중과 같은 자리에서 곱해진다. **밴드 상한(`band_high`)이 없으면** 확률이
    1.0에 가까운(지나치게 쉬운) 후보가 그대로 최고 가중을 받아 "쉬운 문제로 정답률을
    꾸미는 장치"가 된다(금기 위반) — 상한을 실측으로 끄면(예: `band_high=1.0`) 이 배제가
    풀리는지가 REC-04 acceptance⑤의 변별력 검증 대상이다.

    `probability_correct(θ, item)`(Rasch 2PL)를 그대로 재사용한다 — 새 확률 모델 0.
    """
    p = probability_correct(theta, item)
    if band_low <= p <= band_high:
        return 1.0
    return LEARNING_BAND_OUT_OF_RANGE_WEIGHT


def select_weighted_item(
    theta: float,
    items: list[IrtItem],
    *,
    weights: list[float] | None = None,
    administered: set[int] | None = None,
) -> int | None:
    """정보량에 *가중치*를 곱해 최대인 미출제 문항 인덱스 — 가중 적응 출제(CAT 확장).

    `item_information(θ, itemᵢ) · weightsᵢ`가 가장 큰 미출제 문항을 선택. 가중치로 *내용 균형*·
    *약점 개념 우선*(BKT 융합)·*노출 통제*·a-층화 등을 IRT 정보량 위에 얹는다. `weights=None`이면
    전부 1.0(= `select_next_item`과 동치). 가중치는 음이 아니어야 한다(가정·미검증). `administered`
    제외·동률은 낮은 인덱스(결정론)·후보 없으면 None. `weights` 길이는 `items`와 같아야 한다.
    """
    if weights is not None and len(weights) != len(items):
        raise ValueError("weights 길이는 items와 같아야 합니다")
    administered = administered or set()
    best_index: int | None = None
    best_score = -math.inf
    for index, item in enumerate(items):
        if index in administered:
            continue
        weight = 1.0 if weights is None else weights[index]
        score = item_information(theta, item) * weight
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def select_next_item(
    theta: float,
    items: list[IrtItem],
    *,
    administered: set[int] | None = None,
) -> int | None:
    """능력 θ에서 *정보량 최대* 문항의 인덱스 — 적응형 다음 문항(CAT 핵심).

    `items` 중 `administered`(이미 출제한 인덱스 집합)를 제외하고 `item_information(θ, ·)`이
    가장 큰 문항의 인덱스를 반환한다. 후보가 없으면(빈 목록·전부 출제) None. 동률은 *낮은
    인덱스*(결정론). θ에 난이도가 가까운 문항이 대체로 선택된다(P≈0.5·정보 최대).

    `select_weighted_item`의 *균등 가중*(weights=None) 특수해 — 위임으로 구현(중복 제거).
    """
    return select_weighted_item(theta, items, administered=administered)


__all__ = [
    "IrtItem",
    "LEARNING_BAND_HIGH",
    "LEARNING_BAND_LOW",
    "LEARNING_BAND_OUT_OF_RANGE_WEIGHT",
    "ability_standard_error",
    "estimate_ability",
    "estimate_difficulty",
    "fit_jmle",
    "item_information",
    "learning_band_weight",
    "probability_correct",
    "select_next_item",
    "select_weighted_item",
    "theta_to_mastery_proxy",
    "total_information",
]
