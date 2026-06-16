"""L6 응용 모드 — 학교진도·수능·사고력·영재·메타인지·재수(N수) 트랙.

CLAUDE.md 7계층의 L6(응용 모드). L1~L4(독립 수학 코어)·L5(상호작용) 위에서 *학생의
학습 트랙·상황에 맞춰 문항을 선별·구성하는* 최상위 응용 계층이다. L6은 아래 계층을
**호출(소비)**할 수 있으나 *구현하지 않으며*(경계 침범 금지), L7(커뮤니티)을 *알지 못한다*
(역방향 의존 금지). L6은 아무도 import하지 않는 **최상위 소비자**다.

첫 입주자(이 슬라이스): 재수전용(RT/N수) 트랙 게이팅(`retake/`). HIGH 오버레이 모델 —
새 concept 노드·Alembic 마이그레이션·새 enum을 *만들지 않고*, 기존 L1 `Problem`의
`persona_fit`·`question_format=재수전용형`·`distractor_map`을 *재사용*해 페르소나 B·C에게
RT 문항을 선별 노출하는 **게이팅 로직만** 더한다. 얇게 유지 — L4를 import하지 않는다
(distractor_map은 *존재 여부*만 본다).

후속(범위 밖): 수능/학교진도/사고력/영재/메타인지 모드 입주, OLY(영재) 트랙, HTTP 노출.
"""

from __future__ import annotations

from whymath_backend.l6.retake import (
    RETAKE_PERSONAS,
    is_retake_eligible,
    retake_priority,
    select_retake_items,
)

__all__ = [
    "RETAKE_PERSONAS",
    "is_retake_eligible",
    "retake_priority",
    "select_retake_items",
]
