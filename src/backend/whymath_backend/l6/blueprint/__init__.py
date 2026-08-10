"""L6 평가 청사진(blueprint) 모드 — 선언 명세 기반 총괄평가 테스트셋 조립.

설계 정본: `assessment_module_gap_review.md` §3 D4. 다른 L6 모드(재수·수능·학교진도·사고력·
메타인지·영재)가 "이 문항을 이 학생에게 노출해도 되는가"를 판정하는 *게이팅*인 반면, 이
모드는 "이 시험지 명세를 만족하는 문항 집합은 무엇인가"를 조립한다(따라서 파일명이
`gating.py`가 아니라 `assembly.py`다 — 디렉터리-1파일 구조는 동일).

오버레이 모델(다른 L6 모드와 동형): 새 concept 노드·Alembic 마이그레이션·새 PG enum을
*만들지 않는다*. 기존 L1 `Problem` 필드만 재사용한다 —
  - `source_type` (저작권 노출 게이트 — `_shared.is_exposable`),
  - `review_status` (검수 게이트 — `_shared.is_review_cleared`, **저작권 축과 별개 if**),
  - `achievement_standard_codes` (성취기준 축 — 비영속·L5가 원자 축 조인으로 주입),
  - `difficulty_overall` (난이도 밴드 축), `question_format` (문항 유형 축),
  - `points` (배점 — 이 모듈이 **첫 소비처**. 2026-08-10 실측 전량 NULL이라 정직 회계 필요),
  - `review_score` (우선순위 보조 축).

**CAT 대체 아님**(D4-2): 학습 중 노출 정본은 CAT 단건(`GET /v1/me/next-problem`)이고, 이
모듈의 세트는 `BLUEPRINT_USE_CASE`("단원 마감 측정") 예외에만 쓴다. 이 경계는 테스트로 동결.

세트의 좌석: 새 테이블을 만들지 않고 `Assessment` 행(`AssessmentType.실전모의고사`) +
문항 id 배열(`pattern_diagnosis` JSONB)로 표현한다 — 신규 마이그레이션 0.
"""

from __future__ import annotations

from whymath_backend.l6.blueprint.assembly import (
    BLUEPRINT_USE_CASE,
    DIFFICULTY_BAND_BOUNDS,
    AssembledTestSet,
    BlueprintCell,
    CellFill,
    DifficultyBand,
    ExamBlueprint,
    PartialCredit,
    assemble_test_set,
    blueprint_priority,
    difficulty_band_of,
    is_blueprint_eligible,
    matches_cell,
    partial_credit,
)

__all__ = [
    "BLUEPRINT_USE_CASE",
    "DIFFICULTY_BAND_BOUNDS",
    "AssembledTestSet",
    "BlueprintCell",
    "CellFill",
    "DifficultyBand",
    "PartialCredit",
    "ExamBlueprint",
    "assemble_test_set",
    "blueprint_priority",
    "difficulty_band_of",
    "is_blueprint_eligible",
    "matches_cell",
    "partial_credit",
]
