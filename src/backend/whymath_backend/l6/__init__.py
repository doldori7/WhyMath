"""L6 응용 모드 — 학교진도·수능·사고력·영재·메타인지·재수(N수) 트랙.

CLAUDE.md 7계층의 L6(응용 모드). L1~L4(독립 수학 코어)·L5(상호작용) 위에서 *학생의
학습 트랙·상황에 맞춰 문항을 선별·구성하는* 최상위 응용 계층이다. L6은 아래 계층을
**호출(소비)**할 수 있으나 *구현하지 않으며*(경계 침범 금지), L7(커뮤니티)을 *알지 못한다*
(역방향 의존 금지). L6은 아무도 import하지 않는 **최상위 소비자**다.

입주자(이 슬라이스까지):
  - 재수전용(RT/N수) 트랙 게이팅(`retake/`) — 페르소나 B·C에게 RT 문항 선별 노출. 오버레이
    모델로 기존 L1 `Problem`의 `persona_fit`·`question_format=재수전용형`·`distractor_map`을
    *재사용*한다(L4 미import — distractor_map은 *존재 여부*만 본다).
  - 수능(정시) 모드 게이팅(`suneung/`) — 페르소나 A·B·C에게 정시 문항 선별 노출. RT와 동형
    오버레이 모델로 기존 `exam_type`·`exam_authority_weight`·`signature_patterns`·
    `persona_fit`·`difficulty_overall`·`source_type`을 *재사용*한다. 평가원 기출 *본문*은
    저작권 게이트로 원천 차단하고 자체생성 동등문제만 노출(CLAUDE.md 우선순위 #2).
  - 학교진도 모드 게이팅(`school_progress/`) — 페르소나 A·D(학교 재학생)에게 현재 진도 단원
    정합 문항 선별 노출. RT·수능과 동형 오버레이 모델로 `source_type`·`curriculum_version`·
    `unit_codes`·`persona_fit`·`difficulty_overall`을 *재사용*한다(자동 커리큘럼 정렬 — 진도
    단원 겹침 우선). N수(B·C)·영재(E)는 비재학·홈스쿨이라 제외.

세 모드는 새 concept 노드·Alembic 마이그레이션·새 enum을 *만들지 않고* **게이팅 로직만** 더한다.
얇게 유지 — L4/L2/L3를 import하지 않는다(기존 `Problem` 필드의 존재·값만 본다). 세 모드가
공통으로 쓰는 저작권 게이트·enum 정규화는 L6 공용 모듈 `_shared.py`로 추출했다(Rule of three).

후속(범위 밖): 사고력/영재/메타인지 모드 입주, OLY(영재) 트랙, 학교진도 성취기준 마스터 매칭,
HTTP 노출.
"""

from __future__ import annotations

from whymath_backend.l6.retake import (
    RETAKE_PERSONAS,
    is_retake_eligible,
    retake_priority,
    select_retake_items,
)
from whymath_backend.l6.school_progress import (
    SCHOOL_PROGRESS_PERSONAS,
    is_school_progress_eligible,
    school_progress_priority,
    select_school_progress_items,
)
from whymath_backend.l6.suneung import (
    SUNEUNG_PERSONAS,
    is_suneung_eligible,
    select_suneung_items,
    suneung_priority,
)

__all__ = [
    "RETAKE_PERSONAS",
    "SCHOOL_PROGRESS_PERSONAS",
    "SUNEUNG_PERSONAS",
    "is_retake_eligible",
    "is_school_progress_eligible",
    "is_suneung_eligible",
    "retake_priority",
    "school_progress_priority",
    "select_retake_items",
    "select_school_progress_items",
    "select_suneung_items",
    "suneung_priority",
]
