"""L2 학습자 모델 — 학생의 *숨은 학습 상태*를 데이터로 추정.

성취기준(개념)별 숙달 확률·문항 난이도·학생 능력·정서 신호·오개념을 추적해 상위 계층
(L3 콘텐츠 생성·L4 교수학 결정·L6 모드 라우팅)에 *학습자 모델 입력*을 제공한다.
`docs/architecture/02_learner_model.md` 참조.

슬라이스 1: BKT(Bayesian Knowledge Tracing) 숙달 확률 추정(`bkt`). 슬라이스 2: BKT ↔
`ConceptMasteryHistory` 시계열 영속 결선(`mastery_tracking`). 범위 밖(후속): IRT 문항/능력
추정·DKT 신경망·파라미터 적합(EM)·정서 신호·오개념 매핑.
"""

from __future__ import annotations

from whymath_backend.l2.bkt import (
    DEFAULT_BKT_PARAMETERS,
    BktModel,
    BktParameters,
    apply_learning,
    posterior_mastery,
    probability_correct,
    update_mastery,
)
from whymath_backend.l2.mastery_tracking import (
    MasteryRecord,
    compute_mastery_record,
    record_attempt_mastery,
    record_problem_attempt_mastery,
)

__all__ = [
    "DEFAULT_BKT_PARAMETERS",
    "BktModel",
    "BktParameters",
    "MasteryRecord",
    "apply_learning",
    "compute_mastery_record",
    "posterior_mastery",
    "probability_correct",
    "record_attempt_mastery",
    "record_problem_attempt_mastery",
    "update_mastery",
]
