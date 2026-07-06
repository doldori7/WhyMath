"""스켈레톤 rule-based 난이도 추정 — S2-p(결정론·공식 문서화).

스켈레톤 생성기(S2-o)는 v0에서 `difficulty_overall`을 스펙 값 그대로 미러해 코퍼스 161건이
전부 2.5 균일이었다(변별 0 — L2 학습자 모델·검수 큐 우선순위에 무용). 스켈레톤은 자기 수치
(근 유형·계수)를 코드로 확정하므로, 난이도도 같은 수치에서 **결정론 규칙**으로 추정한다.

공식(v1 — 한국 고1 이차방정식 단원 기준·모든 항 가산):

    난이도 = 2.0 (base·정수근 인수분해 기본형)
           + 근 유형   : integer +0.0 · double(중근) +0.3 · rational(기약 유리근) +0.6
                         · irrational(완전제곱꼴 무리근) +1.2
           + 선두계수  : a == 1 +0.0 · a ≥ 2 +0.3 (계수 조작·인수분해 후보 증가)
           + 계수 크기 : max(|a|,|b|,|c|) ≤ 10 +0.0 · ≤ 30 +0.2 · > 30 +0.4 (산술 부담)
    → 소수 1자리 반올림 후 [1.0, 5.0] 클램프

산출 범위는 2.0~3.6(현 풀 기준) — 1~5 척도의 중하~중상부만 쓰는 것은 *정직한 스코프*다:
현 스켈레톤 풀(단일변수 이차·손 인수분해 가능)이 실제로 그 난이도 대역이기 때문이며, 4~5
대역은 결합·해석 축이 필요한 문항(후속 스켈레톤/LLM-first)의 자리다. 근거 없는 척도 전역
사용(과장)을 하지 않는다.

게이트 정합(수학): S2-a 동등성 점수 = 0.4·성취기준 + 0.3·오개념 + 0.2·난이도 + 0.1·답형태,
난이도 성분은 |gap|≤tol(0.5) → 1.0·초과분 /4.0 선형 감쇠. 다른 성분 만점일 때 accepted
(≥0.85) 유지 조건은 |gap| ≤ 3.5 — 스펙 2.5 고정 대비 본 추정기의 최대 gap 1.1이라 밴드별
스펙 난이도 분리 없이 안전하다. 코퍼스 CI 봉인은 자기-정합 스펙(레코드 자신의 난이도)이라
항상 만점 성분이다.

7계층: L3 지역(스켈레톤 전용 헬퍼) — 다른 계층 import 0(순수 함수). 5축 난이도의 나머지 축
(diff_calculation 등)은 범위 밖(미설정 유지 — 추정 근거 없는 축을 날조하지 않는다).
"""

from __future__ import annotations

from typing import Literal

__all__ = ["RootKind", "estimate_difficulty", "estimate_difficulty_extremum"]

RootKind = Literal["integer", "double", "rational", "irrational"]
"""정답 근의 유형 — integer(서로 다른 정수근)·double(중근)·rational(기약 유리근)·
irrational(완전제곱꼴 무리근 p±√q)."""

_BASE = 2.0
_ROOT_KIND_STEP: dict[str, float] = {
    "integer": 0.0,
    "double": 0.3,
    "rational": 0.6,
    "irrational": 1.2,
}
_LEAD_STEP = 0.3  # 선두계수 a ≥ 2
_COEF_MID_STEP = 0.2  # 10 < max|계수| ≤ 30
_COEF_BIG_STEP = 0.4  # max|계수| > 30
_COEF_MID_BOUND = 10
_COEF_BIG_BOUND = 30
_MIN, _MAX = 1.0, 5.0


def estimate_difficulty(
    *,
    root_kind: RootKind,
    lead_coefficient: int,
    max_abs_coefficient: int,
) -> float:
    """스켈레톤 수치 → 종합 난이도(1.0~5.0) — 모듈 docstring 공식의 결정론 구현.

    입력은 스켈레톤이 확정한 수치에서 유도한다(추정 입력의 단일 진실 원천 = 뼈대):
    `root_kind`(근 유형), `lead_coefficient`(전개 선두계수 a>0), `max_abs_coefficient`
    (전개 계수 절댓값 최대 max(|a|,|b|,|c|)).
    """
    score = _BASE + _ROOT_KIND_STEP[root_kind]
    if lead_coefficient >= 2:
        score += _LEAD_STEP
    if max_abs_coefficient > _COEF_BIG_BOUND:
        score += _COEF_BIG_STEP
    elif max_abs_coefficient > _COEF_MID_BOUND:
        score += _COEF_MID_STEP
    return min(_MAX, max(_MIN, round(score, 1)))


# ── 미적분(극값) 스켈레톤 난이도 ─────────────────────────────────────────────
# 극값 문제(삼차함수의 극대·극소 x좌표)는 이차방정식 근보다 한 단계 위다: 도함수를 *구하고*
# f'(x)=0을 풀고 *부호를 판정*해 극대/극소를 가려야 한다(미분+방정식+선택 3단). 그래서 base를
# 이차 근(2.0)보다 높은 3.0으로 둔다(미적분Ⅰ 기본 대역). 킬러(4~5)는 결합·해석축 문항의
# 자리라 여기서 쓰지 않는다(정직 스코프·estimate_difficulty docstring 계승).
#
# 공식(모든 항 가산):
#     난이도 = 3.0 (base·미분+극값 판정)
#            + 임계점 간격 (n−m) : ≤4 +0.0 · ≤8 +0.3 · >8 +0.5 (근·계수 산술 부담)
#            + 계수 크기 max(|b|,|c|) : ≤30 +0.0 · ≤80 +0.3 · >80 +0.5
#     → 소수 1자리 반올림 후 [1.0, 5.0] 클램프  (산출 범위 ~3.0~4.0)
#
# 게이트 정합: estimate_difficulty와 동일한 감쇠 수학(|gap|≤3.5면 타 성분 만점 시 accepted).
# 밴드 스펙 난이도를 산출 중앙(~3.3)에 두면 최대 gap ≤ 0.7 ≪ 3.5라 안전(코퍼스 CI 자기-정합).
_EXTREMUM_BASE = 3.0
_SPREAD_MID_STEP, _SPREAD_BIG_STEP = 0.3, 0.5
_SPREAD_MID_BOUND, _SPREAD_BIG_BOUND = 4, 8
_EXT_COEF_MID_STEP, _EXT_COEF_BIG_STEP = 0.3, 0.5
_EXT_COEF_MID_BOUND, _EXT_COEF_BIG_BOUND = 30, 80


def estimate_difficulty_extremum(*, root_spread: int, max_abs_coefficient: int) -> float:
    """극값 스켈레톤 수치 → 종합 난이도(1.0~5.0) — 위 공식의 결정론 구현.

    입력은 극값 뼈대가 확정한 수치에서 유도한다(단일 진실 원천 = 뼈대): `root_spread`
    (두 임계점 간격 n−m > 0), `max_abs_coefficient`(삼차함수 전개 계수 절댓값 최대 max(|b|,|c|)).
    """
    score = _EXTREMUM_BASE
    if root_spread > _SPREAD_BIG_BOUND:
        score += _SPREAD_BIG_STEP
    elif root_spread > _SPREAD_MID_BOUND:
        score += _SPREAD_MID_STEP
    if max_abs_coefficient > _EXT_COEF_BIG_BOUND:
        score += _EXT_COEF_BIG_STEP
    elif max_abs_coefficient > _EXT_COEF_MID_BOUND:
        score += _EXT_COEF_MID_STEP
    return min(_MAX, max(_MIN, round(score, 1)))
