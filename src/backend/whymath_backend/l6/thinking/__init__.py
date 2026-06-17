"""L6 사고력(thinking) 모드 게이팅 — 고차 사고 문항 선별 노출(Bloom 상위 3단계 주신호).

오버레이 모델(RT 트랙 `l6/retake`·수능 모드 `l6/suneung`·학교진도 `l6/school_progress`와
동형): 새 concept 노드·Alembic 마이그레이션·새 enum을 *만들지 않는다*. 기존 L1 `Problem`
필드만 재사용한다 —
  - `Problem.source_type` (저작권 노출 게이트 — 평가원/EBS/교과서 본문 미보유 차단),
  - `Problem.bloom_level` (사고력 *주신호* — 상위 3단계 ANALYZE/EVALUATE/CREATE만 적격),
  - `Problem.signature_patterns` (사고력 시그니처 3종 보유 *개수* — 우선순위 가산),
  - `Problem.diff_case_analysis` (케이스 분류 깊이 — 사고력 특화 난이도 축),
  - `Problem.diff_integration` (단원 융합도 — 사고력 특화 난이도 축),
  - `Problem.difficulty_overall` (심화·변별을 약하게 앞세우는 보조 축),
  - `Problem.persona_fit: dict[Persona, float]` (페르소나 적합도 — 닫힌 집합 게이트 없이 이것만).

대상: 사고력 주 대상은 D(학종 고2)·E(홈스쿨링 영재)이나 **닫힌 페르소나 집합으로 좁히지
않는다** — 사고력은 페르소나가 아니라 문항의 사고 수준이 본질이라, A(일반고 고3·MVP)도
적합도가 임계 이상이면 노출된다(MVP 페르소나 배제 금지). 페르소나 적합은 기존
`persona_fit >= min_fit` 메커니즘으로만 판정한다(상세: `gating.py` 모듈 docstring).

레이어 규칙(CLAUDE.md): L6→L1 의존만 한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — 기존 `Problem` 필드의 *존재·값*만 보므로 하위 카탈로그·검증자가
불필요하다. L6은 아무도 import하지 않는 최상위 소비자다.

저작권(CLAUDE.md 우선순위 #2): 평가원·EBS·검정교과서의 *본문* 복제는 절대 금지(저작권법 §32
단서·MEMORY 2026-05-28) — 이 세 출처는 L6 공용 게이트(`_shared.is_exposable`)로 원천 차단하고,
학생에게는 *자체생성 동등문제*(WHYMATH_GENERATED)만 노출한다(RT·수능·학교진도와 동일 공용 게이트).
"""

from __future__ import annotations

from whymath_backend.l6.thinking.gating import (
    THINKING_BLOOM_LEVELS,
    is_thinking_eligible,
    select_thinking_items,
    thinking_priority,
)

__all__ = [
    "THINKING_BLOOM_LEVELS",
    "is_thinking_eligible",
    "select_thinking_items",
    "thinking_priority",
]
