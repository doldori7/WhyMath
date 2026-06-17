"""L6 메타인지(metacognition) 모드 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 *메타인지 코칭에 적합한* 기존 문항(오답을 오개념으로 역추적할 자원이 있거나
진단·루브릭 채점으로 자기점검을 유도하는 문항)을 메타인지 모드로 노출할지 결정한다.
**오버레이 모델**(RT 트랙·수능 모드·학교진도·사고력 게이팅과 동형): 새 enum·concept 노드·
Alembic 마이그레이션을 만들지 않고, 기존 L1 `Problem`의 필드(`source_type`·`distractor_map`·
`scoring_type`·`difficulty_overall`·`persona_fit`)만 *재사용*하는 순수 결정 로직이다.
부수효과 없음(I/O·LLM 호출 없음)·결정적(deterministic).

공개 API 3종:
  - `is_metacognition_eligible(problem, persona, *, min_fit)` — 이 문항을 이 페르소나에게
    메타인지 모드로 노출해도 되는가(불리언 게이트).
  - `metacognition_priority(problem)` — 노출 우선순위 가중치(높을수록 먼저). 교수학 근거
    (오답→오개념 역추적 자원이 풍부할수록 메타인지 코칭 가치가 큼) 반영.
  - `select_metacognition_items(problems, persona, *, min_fit, limit)` — 적격 필터 → 우선순위
    내림차순 안정정렬 → limit 적용.

대상 페르소나(중요 — 하드코딩 set으로 좁히지 않는다): 메타인지는 WhyMath의 *공유 코어*
(CLAUDE.md §3 "공유 메타인지 코어 + 첫 노출 A(고3)")라 **전 페르소나 공통**이다. 사고력
(thinking)과 같은 이유로 **닫힌 페르소나 집합(frozenset)으로 게이트하지 않는다** — 재수·학교진도
트랙이 트랙 본질상 비대상 페르소나를 원천 배제한 것과 달리, 메타인지는 페르소나가 아니라
*자기 사고를 돌아보는 코칭*이 본질이라 A(MVP 고3)부터 E(영재)까지 누구에게나 적합하다(첫 노출은
A). 페르소나 적합은 기존 `persona_fit >= min_fit` 메커니즘으로만 판정한다(thinking과 동일 — 기본
persona는 첫 노출 대상 A_일반고고3).

메타인지 *주신호*(게이팅에서 직접 볼 수 있는 것): `distractor_map`(오답 선지→오개념 매핑)의
*존재*다. 오답을 오개념으로 *역추적*하는 것이 메타인지("왜 이 오답을 했는가"의 의식화 —
Polya 4단계 중 검토 단계)의 핵심 자원이기 때문이다(RT 트랙이 같은 신호를 재수생 오개념
재구조화 우선순위로 이미 쓴다). 보조 신호로 `scoring_type ∈ {진단, 루브릭}`(오개념 진단·
자기평가 루브릭 채점)을 OR로 본다 — 진단/루브릭 채점은 *점수보다 자기점검*이 목적인 문항이라
메타인지 코칭에 어울린다. (L4 교수학 엔진의 메타인지 코칭이 쓰는 `socratic_prompt`·
`common_mistakes`는 `ProblemStep` 소속이라 L6 게이팅의 후보(`list[Problem]`)에서 직접 볼 수
없다 — 그래서 게이팅 신호로는 Problem 직속 필드인 distractor_map·scoring_type만 쓴다.)

레이어 규칙(CLAUDE.md): L6→L1만 의존한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — `distractor_map`은 *존재·개수*만 보고(오답→오개념 역추적
*가능성*의 신호일 뿐), 매핑 내용·카탈로그 정합은 L4 검증자 소관이다(역방향 의존 부재).

저작권 게이트(`_shared.is_exposable`)는 RT·수능·학교진도·사고력과 공유한다 — 메타인지 모드도
평가원/EBS/검정교과서 *본문*은 노출 불가(저작권법 §32 단서·MEMORY 2026-05-28), 자체생성
동등문제만 노출한다.

use_enum_values=True 주의: `Problem`은 `ConfigDict(use_enum_values=True)`라 `source_type`·
`scoring_type`이 *문자열 값*일 수 있고 `persona_fit`의 *키*도 문자열일 수 있다. 따라서 enum
비교 시 항상 L6 공용 헬퍼(`_shared.normalize_enum_value`·`_shared.persona_fit`·
`_shared.is_exposable`)로 정규화해 비교한다.
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import Persona, ScoringType
from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
METACOGNITION_SCORING_TYPES: frozenset[ScoringType] = frozenset(
    {ScoringType.진단, ScoringType.루브릭}
)
"""메타인지 모드의 *보조 신호* — 자기점검·오개념 진단에 친화적인 채점 유형 2종.

`ScoringType` 5종(정오답·진단·부분점수·시간·루브릭) 중, *점수보다 자기점검·진단이 목적*인 둘:
  - `진단` — 오답 선지로 오개념을 진단(점수보다 진단 신호가 목적·enum docstring),
  - `루브릭` — 평가 기준표 기반 다차원 채점(수행평가·자기평가 성찰에 어울림).
이 둘에 해당하는 문항은 주신호(`distractor_map`)가 없어도 메타인지 코칭 자원으로 적격이며
(적격 ③의 OR 두 번째 항), 우선순위에서도 가산한다(`metacognition_priority` ② 항). 나머지 3종
(정오답·부분점수·시간)은 메타인지 특화 신호가 아니라 여기 두지 않는다.
"""


def is_metacognition_eligible(
    problem: Problem,
    persona: Persona = Persona.A_일반고고3,
    *,
    min_fit: float = 0.5,
) -> bool:
    """이 문항을 이 페르소나에게 메타인지 모드로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         학생 노출 불가 본문이므로 *메타인지 자원·적합도가 아무리 높아도* 막힌다(CLAUDE.md
         우선순위 #2 — 법적). 자체생성 동등문제만 노출한다.
      ② 페르소나 적합 게이트 — `persona_fit[persona] >= min_fit`. **닫힌 페르소나 집합으로
         좁히지 않는다**(모듈 docstring) — 메타인지는 공유 코어라 A(첫 노출)부터 E까지 누구든
         적합도가 임계 이상이면 통과한다(thinking과 동일 메커니즘). 적합도 미달이면 False.
      ③ 메타인지 주신호(OR) — 다음 중 *하나라도* 참이면 True:
           (a) `distractor_map`이 존재(오답→오개념 역추적 자원), **또는**
           (b) `scoring_type ∈ {진단, 루브릭}`(자기점검·진단 친화 채점).
         둘 다 없으면 메타인지 코칭 자원이 없는 문항이라 부적격(폴백 없음 — thinking이
         bloom None을 막는 것과 동형).

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — 공유 메타인지 코어 첫 노출 대상). 어떤
        페르소나든 `persona_fit` 충족이면 통과할 수 있다(닫힌 집합 게이트 없음).
      min_fit: persona_fit 임계값(기본 0.5 — "절반 이상 적합"). 0~1 척도.

    Returns:
      메타인지 모드 노출 적격이면 True.

    use_enum_values=True 주의: source_type·scoring_type·persona_fit 키가 문자열일 수 있어
    L6 공용 헬퍼(`_shared.is_exposable`·`_shared.normalize_enum_value`·`_shared.persona_fit`)로
    정규화해 비교한다.
    """
    # ① 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(메타인지 자원·적합도가 높아도 차단).
    if not _shared.is_exposable(problem):
        return False

    # ② 페르소나 적합 게이트 — 닫힌 집합으로 좁히지 않고 persona_fit 메커니즘만 쓴다
    #    (공유 메타인지 코어 — A 첫 노출부터 E까지 fit 충족이면 통과·thinking 동형).
    if _shared.persona_fit(problem, persona) < min_fit:
        return False

    # ③ 메타인지 주신호(OR) — 오답→오개념 역추적(distractor_map) 또는 진단/루브릭 채점.
    if problem.distractor_map:  # None·빈 리스트면 거짓(역추적 자원 없음)
        return True
    scoring_values = {s.value for s in METACOGNITION_SCORING_TYPES}
    return _shared.normalize_enum_value(problem.scoring_type) in scoring_values


def metacognition_priority(problem: Problem) -> float:
    """메타인지 모드 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md "메타인지 중심"·우선순위 #3·#4): 메타인지 코칭의 핵심은 *오답을
    오개념으로 역추적해 자기 사고를 의식화*하는 것이다. 오답→오개념 매핑(`distractor_map`)이
    *많을수록* 학생이 점검할 자기 오류의 종류가 풍부해 코칭 가치가 크다. 이를 반영해:

      가중치 = (distractor_map 원소 개수 × 2.0)
               + (scoring_type ∈ {진단,루브릭}이면 +1.0)
               + (difficulty_overall|0.0)

      - **distractor_map 개수**(주신호·가장 큰 가중) × 2.0 — 오답→오개념 매핑이 많을수록 성찰
        자원이 풍부하다(여러 오답 선지가 각각 다른 오개념을 가리킴). *개수*로 단조 가산한다
        (thinking이 사고력 시그니처 *개수*를 세는 선례 답습). 존재만 보지 않고 개수를 쓰는 이유는
        메타인지가 "여러 오답 경로를 비교·성찰"하는 데서 깊어지기 때문이다. None·빈 리스트면 0.0.
      - **scoring_type 진단/루브릭** → +1.0(보조) — 자기점검·진단 채점 문항을 한 단계 앞세운다.
      - **difficulty_overall**(1.0~5.0, None이면 0.0) → 그대로 가산(타이브레이커·다른 모드 동형).

    구체 가중치(개수 ×2.0·진단 +1.0·난이도 그대로)는 *상대 순서*만 의미가 있다 — 주신호
    distractor_map 가중(개수 1개만 있어도 2.0)이 보조 scoring_type(1.0)보다 크게 설계했다
    (RT의 distractor_map +2.0 톤 답습). 합산이라 같은 점수는 동률이며, 동률 처리는
    `select_metacognition_items`의 *안정정렬*(원래 순서 보존)에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항.

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # distractor_map 개수 가중(주신호·최대 가중) — 오답→오개념 매핑 개수 × 2.0(존재 여부가 아닌
    # 개수로 단조 — 여러 오답 경로를 비교·성찰할수록 메타인지 코칭 자원이 풍부). None/빈=0.0.
    if problem.distractor_map:
        weight += len(problem.distractor_map) * 2.0

    # scoring_type 진단/루브릭 보조 — 자기점검·진단 친화 채점을 한 단계 앞세움.
    scoring_values = {s.value for s in METACOGNITION_SCORING_TYPES}
    if _shared.normalize_enum_value(problem.scoring_type) in scoring_values:
        weight += 1.0

    # 종합 난이도 보조 축(None이면 0.0) — 심화를 약하게 앞세움(다른 모드 우선순위와 동형).
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_metacognition_items(
    problems: Iterable[Problem],
    persona: Persona = Persona.A_일반고고3,
    *,
    min_fit: float = 0.5,
    limit: int | None = None,
) -> list[Problem]:
    """메타인지 모드 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_metacognition_eligible(p, persona, min_fit=min_fit)`로 적격 문항만 남긴다(본문
         미보유 출처·페르소나 적합도 미달·메타인지 신호 부재(distractor_map 없음 + 진단/루브릭
         아님)는 탈락).
      2. `metacognition_priority(p)` *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존 —
         `metacognition_priority` docstring의 동률 처리 계약). 따라서 오답→오개념 매핑이 풍부한
         문항이 앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — 공유 코어). `is_metacognition_eligible`에
        전달(닫힌 집합 게이트 없이 persona_fit으로만 판정).
      min_fit: persona_fit 임계값(기본 0.5). `is_metacognition_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [p for p in problems if is_metacognition_eligible(p, persona, min_fit=min_fit)]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(eligible, key=metacognition_priority, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]


__all__ = [
    "METACOGNITION_SCORING_TYPES",
    "is_metacognition_eligible",
    "metacognition_priority",
    "select_metacognition_items",
]
