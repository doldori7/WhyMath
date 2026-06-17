"""L6 학교진도 모드 게이팅 — 페르소나 A·D(학교 재학생) 대상 진도 정합 문항 선별 노출.

오버레이 모델(RT 트랙 `l6/retake`·수능 모드 `l6/suneung`와 동형): 새 concept 노드·Alembic
마이그레이션·새 enum을 *만들지 않는다*. 기존 L1 `Problem` 필드만 재사용한다 —
  - `Problem.source_type` (저작권 노출 게이트 — 평가원/EBS/교과서 본문 미보유 차단),
  - `Problem.curriculum_version` (교육과정 버전 정합 — 진도는 교육과정 버전이 맞아야 함),
  - `Problem.unit_codes` (현재 진도 단원과의 겹침 — 자동 커리큘럼 정렬의 핵심 신호),
  - `Problem.persona_fit: dict[Persona, float]` (진도 단원 정보가 없을 때 폴백 적합도),
  - `Problem.difficulty_overall` (진도 정합 안에서 심화를 약하게 앞세우는 보조 축).

대상: 학교 재학생 페르소나 A(일반고 고3)·D(학종 고2)만. N수(B·C — 비재학)·영재(E — 홈스쿨)는
이 모드 범위 밖(B·C는 수능 모드, E는 후속 영재 모드).

레이어 규칙(CLAUDE.md): L6→L1 의존만 한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — 기존 `Problem` 필드의 *존재·값*만 보므로 하위 카탈로그·검증자가
불필요하다. 성취기준 마스터(AchievementStandard)도 이번 범위에서 참조하지 않는다(진도 정합은
unit_codes·curriculum_version 매칭). L6은 아무도 import하지 않는 최상위 소비자다.

저작권(CLAUDE.md 우선순위 #2): 평가원·EBS·검정교과서의 *본문* 복제는 절대 금지(저작권법 §32
단서·MEMORY 2026-05-28) — 이 세 출처는 L6 공용 게이트(`_shared.is_exposable`)로 원천 차단하고,
학생에게는 *자체생성 동등문제*(WHYMATH_GENERATED)만 노출한다(RT·수능과 동일한 공용 게이트).
"""

from __future__ import annotations

from whymath_backend.l6.school_progress.gating import (
    SCHOOL_PROGRESS_PERSONAS,
    is_school_progress_eligible,
    school_progress_priority,
    select_school_progress_items,
)

__all__ = [
    "SCHOOL_PROGRESS_PERSONAS",
    "is_school_progress_eligible",
    "school_progress_priority",
    "select_school_progress_items",
]
