"""L6 수능 적응 추천 — L6 게이팅(적격·우선순위) × L2 IRT CAT(정보량 최대)의 결합점.

`GET /v1/me/next-problem?mode=suneung`(api/me)의 *추천 결정* 로직을 소유한다 — api는
θ 추정·후보 SQL 축소·응답 조립(배선)만 하고, "이 후보 중 무엇을 낼 것인가"는 이 모듈이
결정한다. 순수 함수·부수효과 없음(I/O·LLM 호출 없음)·결정적(deterministic).

결합 구조(수능 적응 추천 루프):
  ① **L6 게이팅 = 진실 게이트** — `is_suneung_eligible`(저작권 노출 게이트·대상 페르소나·
     수능 적합 신호)를 후보마다 *재수행*한다. api의 SQL 사전필터는 성능용 *축소 전용*이고,
     최종 적격 판정의 단일 진실은 항상 이 게이트다(사전필터가 느슨해도 부적격이 새지 않는다).
  ② **L2 IRT CAT = 문항 선택** — 적격 후보를 `IrtItem`(난이도 b)으로 바꿔
     `select_weighted_item(θ, items, weights)`로 *가중 정보량 최대* 문항을 고른다.
     b는 보정값 우선·전문가 난이도 폴백(`resolve_item_difficulty_b` — L2 단일 지점).
  ③ **가중치 = 수능 우선순위 × 약점 가중** — `suneung_item_weight`(1+`suneung_priority`,
     항상 양수)에 호출자가 준 `extra_weights`(약점 개념 가중 등)를 *곱*으로 결합한다.

레이어 규칙(CLAUDE.md·import-linter `api > l6 > … > l2 > l1 > schema`): 이 모듈은
L6→L2(`l2.irt`·`l2.ability_estimation`)·L6→schema *하향* import만 한다 — L6이 하위 계층을
*호출(소비)*하는 정상 방향이다(게이팅 모듈들이 L2를 안 쓰는 것은 "불필요해서"였고, 추천은
IRT CAT이 본질이라 L2 호출이 필요하다). 역방향(l2→l6) 의존은 없다.

부적격 처리 원칙(중요): 부적격 후보는 *가중 0*이 아니라 **목록에서 제외**한다 —
`select_weighted_item`은 "최대 점수 선택"이라 전원 0점이어도 인덱스를 반환하므로, 가중 0
방식은 부적격 문항이 추천되는 사고로 이어진다. 제외 후 원 인덱스를 보존해 역매핑한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from whymath_backend.l2.ability_estimation import resolve_item_difficulty_b
from whymath_backend.l2.irt import IrtItem, select_weighted_item
from whymath_backend.l6.suneung.gating import is_suneung_eligible, suneung_priority
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.problem import Problem

__all__ = [
    "recommend_suneung_index",
    "suneung_item_weight",
]


def suneung_item_weight(problem: Problem) -> float:
    """수능 CAT 가중치 = `1.0 + suneung_priority(problem)` — 양수 보장·priority 단조 보존.

    `suneung_priority`(권위×2.0 + 시그니처+1.0 + 난이도, 항상 비음수)를 그대로 쓰면 신호가
    전무한 적격 문항(priority 0.0)의 가중 정보량이 0이 되어, 그런 문항만 남은 풀에서 전원
    0점 동률이 된다(전-0 퇴화). +1.0 바닥을 깔아 *항상 양수*로 만들고, priority가 큰 문항이
    가중도 큰 *단조성*은 그대로 보존한다(1+x는 단조증가). 결정적·순수.
    """
    return 1.0 + suneung_priority(problem)


def recommend_suneung_index(
    theta: float,
    candidates: Sequence[Problem],
    persona: Persona = Persona.A_일반고고3,
    *,
    min_fit: float = 0.5,
    extra_weights: Sequence[float] | None = None,
) -> int | None:
    """수능 모드 다음 문항 추천 — 적격 축소 후 가중 정보량 최대 후보의 *원 인덱스*.

    알고리즘(모듈 docstring의 결합 구조):
      1. `extra_weights`가 있으면 길이가 `candidates`와 같아야 한다(불일치 → ValueError —
         `l2.irt.select_weighted_item`의 길이 계약 미러).
      2. 적격 축소 — 각 후보에 대해 다음 *둘 다* 만족해야 남긴다(부적격은 가중 0이 아니라
         **제외** — 모듈 docstring의 사고 방지 원칙):
           (a) `is_suneung_eligible(p, persona, min_fit=min_fit)` — L6 진실 게이트
               (저작권·페르소나·수능 신호 재검증. api SQL 사전필터와 무관하게 항상 수행),
           (b) `resolve_item_difficulty_b(p.irt_difficulty_b, p.difficulty_overall)`가
               None이 아님 — IRT 정보량 계산에 난이도 b가 필수(둘 다 없으면 배제).
         제외하면서 *원 인덱스*를 보존한다.
      3. 적격 후보를 `IrtItem(difficulty=b)`로, 가중치를
         `suneung_item_weight(p) × (extra_weights[원i] if 있으면 else 1.0)`으로 구성한다
         (곱 결합 — 수능 우선순위와 약점 가중이 서로를 스케일).
      4. `select_weighted_item(theta, items, weights=…)` → 축소 리스트 인덱스를 *원 인덱스*로
         역매핑해 반환. 동률은 낮은 인덱스(l2의 결정론 계승 — 축소가 순서를 보존하므로
         "낮은 축소 인덱스" = "낮은 원 인덱스").

    Args:
      theta: 현재 학생 능력 θ(logit — api가 채점 이력으로 추정).
      candidates: 후보 문항들(api가 SQL로 θ 근방 축소·`to_schema()`한 L1 `Problem`들).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — MVP 정시 정면 대상).
      min_fit: `is_suneung_eligible`의 persona_fit 임계값(기본 0.5).
      extra_weights: 후보별 추가 가중(약점 개념 가중 등). `candidates`와 동일 길이·곱 결합.
        None이면 전부 1.0(수능 우선순위만).

    Returns:
      추천 문항의 `candidates` 내 *원 인덱스*. 적격 후보가 0이면 None(추천 불가).

    Raises:
      ValueError: `extra_weights` 길이가 `candidates`와 다를 때.
    """
    # 1. 길이 계약 — l2.select_weighted_item과 동일한 조기 검증(부분 적용 사고 방지).
    if extra_weights is not None and len(extra_weights) != len(candidates):
        raise ValueError("extra_weights 길이는 candidates와 같아야 합니다")

    # 2. 적격 축소 — 진실 게이트(a) + b 존재(b). 원 인덱스를 함께 보존한다.
    original_indices: list[int] = []
    items: list[IrtItem] = []
    weights: list[float] = []
    for index, problem in enumerate(candidates):
        # (a) L6 진실 게이트 — 저작권·페르소나·수능 신호를 *여기서* 최종 재검증.
        if not is_suneung_eligible(problem, persona, min_fit=min_fit):
            continue
        # (b) 난이도 b — 보정값 우선·전문가 난이도 폴백(둘 다 없으면 정보량 계산 불가 → 제외).
        b = resolve_item_difficulty_b(problem.irt_difficulty_b, problem.difficulty_overall)
        if b is None:
            continue
        original_indices.append(index)
        items.append(IrtItem(difficulty=b))
        # 3. 가중치 — 수능 우선순위(항상 양수) × 약점 가중(있으면 곱 결합).
        weight = suneung_item_weight(problem)
        if extra_weights is not None:
            weight *= extra_weights[index]
        weights.append(weight)

    if not items:
        return None  # 적격 후보 0 — 추천 불가(호출자가 problem_id=null 응답).

    # 4. L2 IRT CAT — 가중 정보량 최대(동률은 낮은 인덱스 = 낮은 원 인덱스) → 원 인덱스 역매핑.
    best = select_weighted_item(theta, items, weights=weights)
    if best is None:  # pragma: no cover — items 비어있지 않으면 l2가 항상 인덱스 반환
        return None
    return original_indices[best]
