"""L6 메타인지(metacognition) 모드 게이팅 — 메타인지 코칭 적합 문항 선별 노출.

오버레이 모델(RT·수능·학교진도·사고력 게이팅과 동형): 새 concept 노드·Alembic 마이그레이션·
새 enum을 *만들지 않는다*. 기존 L1 `Problem` 필드만 재사용한다 —
  - `Problem.source_type` (저작권 노출 게이트 — 평가원/EBS/교과서 본문 미보유 차단),
  - `Problem.distractor_map` (메타인지 *주신호* — 오답→오개념 역추적 자원·존재/개수),
  - `Problem.scoring_type` (보조 신호 — 진단/루브릭 채점은 자기점검 친화),
  - `Problem.difficulty_overall` (심화를 약하게 앞세우는 보조 축),
  - `Problem.persona_fit: dict[Persona, float]` (페르소나 적합도 — 닫힌 집합 게이트 없이 이것만).

대상: 메타인지는 WhyMath의 *공유 코어*(CLAUDE.md §3 "공유 메타인지 코어 + 첫 노출 A(고3)")라
**전 페르소나 공통**이다 — 사고력(thinking)과 같이 **닫힌 페르소나 집합으로 좁히지 않고**
`persona_fit >= min_fit`로만 판정한다(기본 persona는 첫 노출 대상 A_일반고고3). 메타인지는
페르소나가 아니라 *자기 사고를 돌아보는 코칭*이 본질이다(상세: `gating.py` 모듈 docstring).

레이어 규칙(CLAUDE.md): L6→L1 의존만 한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — `distractor_map`은 존재·개수만 보고(역추적 *가능성* 신호),
매핑 내용·카탈로그 정합은 L4 소관이다. L6은 아무도 import하지 않는 최상위 소비자다.

저작권(CLAUDE.md 우선순위 #2): 평가원·EBS·검정교과서의 *본문*은 L6 공용 게이트
(`_shared.is_exposable`)로 원천 차단하고, 학생에게는 자체생성 동등문제만 노출한다
(RT·수능·학교진도·사고력과 동일 공용 게이트).
"""

from __future__ import annotations

from whymath_backend.l6.metacognition.gating import (
    METACOGNITION_SCORING_TYPES,
    is_metacognition_eligible,
    metacognition_priority,
    select_metacognition_items,
)

__all__ = [
    "METACOGNITION_SCORING_TYPES",
    "is_metacognition_eligible",
    "metacognition_priority",
    "select_metacognition_items",
]
