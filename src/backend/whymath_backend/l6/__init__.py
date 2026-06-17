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
  - 사고력 모드 게이팅(`thinking/`) — 고차 사고(Bloom 상위 3단계 ANALYZE/EVALUATE/CREATE)
    문항 선별 노출. RT·수능·학교진도와 동형 오버레이 모델로 `source_type`·`bloom_level`(주신호)·
    `signature_patterns`·`diff_case_analysis`·`diff_integration`·`difficulty_overall`·
    `persona_fit`을 *재사용*한다. 주 대상은 D(학종)·E(영재)이나 **닫힌 페르소나 집합으로 좁히지
    않는다** — 사고력은 페르소나가 아니라 문항의 사고 수준이 본질이라 A(MVP 고3)도 적합도가
    충족되면 노출된다(persona_fit 메커니즘만 사용·MVP 페르소나 배제 금지).
  - 메타인지 모드 게이팅(`metacognition/`) — 메타인지 코칭에 적합한 문항 선별 노출. RT·수능·
    학교진도·사고력과 동형 오버레이 모델로 `source_type`·`distractor_map`(주신호 — 오답→오개념
    역추적)·`scoring_type`(보조 — 진단/루브릭)·`difficulty_overall`·`persona_fit`을 *재사용*한다.
    WhyMath의 *공유 메타인지 코어*(CLAUDE.md §3)라 사고력처럼 **닫힌 페르소나 집합으로 좁히지
    않는다** — A(첫 노출)부터 E까지 적합도가 충족되면 노출된다(자기 사고를 돌아보는 코칭이 본질).
  - 영재 트랙 게이팅(`gifted/`) — 심화·창안 문항 선별 노출. RT·수능·학교진도·사고력과 동형
    오버레이 모델로 `source_type`·`persona_fit`(높은 임계 0.7)·`difficulty_overall`(심화 하한 4.0)·
    `bloom_level`(창안 CREATE)·`is_cross_unit`·`diff_integration`을 *재사용*한다. 페르소나 **E
    (홈스쿨링 영재) 전용 닫힌 집합**(RT가 재수 B·C를 닫은 것과 동형 — 학습 환경이 본질). 영재
    콘텐츠(KMO·올림피아드)는 코퍼스 미존재라 데이터가 차면 자동 활성(데이터0 안전).

여섯 모드는 새 concept 노드·Alembic 마이그레이션·새 enum을 *만들지 않고* **게이팅 로직만** 더한다.
얇게 유지 — L4/L2/L3를 import하지 않는다(기존 `Problem` 필드의 존재·값만 본다). 여섯 모드가
공통으로 쓰는 저작권 게이트·enum 정규화는 L6 공용 모듈 `_shared.py`로 추출했다(Rule of three).

후속(범위 밖): 영재·메타인지 *콘텐츠 코퍼스·태깅*(L1 데이터 — KMO/올림피아드 문항·distractor_map
적재), 학교진도 성취기준 문항 태깅(problem_concept 적재).
"""

from __future__ import annotations

from whymath_backend.l6.gifted import (
    GIFTED_MIN_DIFFICULTY,
    GIFTED_PERSONAS,
    gifted_priority,
    is_gifted_eligible,
    select_gifted_items,
)
from whymath_backend.l6.metacognition import (
    METACOGNITION_SCORING_TYPES,
    is_metacognition_eligible,
    metacognition_priority,
    select_metacognition_items,
)
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
from whymath_backend.l6.thinking import (
    THINKING_BLOOM_LEVELS,
    is_thinking_eligible,
    select_thinking_items,
    thinking_priority,
)

__all__ = [
    "GIFTED_MIN_DIFFICULTY",
    "GIFTED_PERSONAS",
    "METACOGNITION_SCORING_TYPES",
    "RETAKE_PERSONAS",
    "SCHOOL_PROGRESS_PERSONAS",
    "SUNEUNG_PERSONAS",
    "THINKING_BLOOM_LEVELS",
    "gifted_priority",
    "is_gifted_eligible",
    "is_metacognition_eligible",
    "is_retake_eligible",
    "is_school_progress_eligible",
    "is_suneung_eligible",
    "is_thinking_eligible",
    "metacognition_priority",
    "retake_priority",
    "school_progress_priority",
    "select_gifted_items",
    "select_metacognition_items",
    "select_retake_items",
    "select_school_progress_items",
    "select_suneung_items",
    "select_thinking_items",
    "suneung_priority",
    "thinking_priority",
]
