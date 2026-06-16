"""L6 재수전용(RT/N수) 트랙 게이팅 — 페르소나 B·C 대상 문항 선별 노출.

HIGH 오버레이 모델(기계장치+synthetic·얇게): 새 concept 노드·Alembic 마이그레이션·새
enum을 *만들지 않는다*. 기존 L1 자산만 재사용한다 —
  - `Problem.persona_fit: dict[Persona, float]` (페르소나별 적합도 0~1),
  - `Problem.question_format == QuestionFormat.재수전용형` (RT 유형 라벨),
  - `Problem.distractor_map` (오답→오개념 역추적 — *존재 여부*만 본다).

대상: RT(재수전용)만. OLY(영재)는 이 슬라이스 범위 밖.

레이어 규칙(CLAUDE.md): L6→L1 의존만 한다(`schema.problem`·`schema.enums`). L4를
import하지 않는다 — `distractor_map`은 *존재 여부*만 보므로 L4 카탈로그·검증자가 불필요하다
(역방향 아님이라 호출은 허용되나 이번엔 얇게 유지하려고 하지 않는다). L6은 아무도
import하지 않는 최상위 소비자다.
"""

from __future__ import annotations

from whymath_backend.l6.retake.gating import (
    METADATA_ONLY_SOURCES,
    RETAKE_PERSONAS,
    is_retake_eligible,
    retake_priority,
    select_retake_items,
)

__all__ = [
    "METADATA_ONLY_SOURCES",
    "RETAKE_PERSONAS",
    "is_retake_eligible",
    "retake_priority",
    "select_retake_items",
]
