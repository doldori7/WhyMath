"""L2 학습자 모델 — 학생의 *숨은 학습 상태*를 데이터로 추정.

성취기준(개념)별 숙달 확률·문항 난이도·학생 능력·정서 신호·오개념을 추적해 상위 계층
(L3 콘텐츠 생성·L4 교수학 결정·L6 모드 라우팅)에 *학습자 모델 입력*을 제공한다.
`docs/architecture/02_learner_model.md` 참조.

슬라이스 1: BKT(Bayesian Knowledge Tracing) 숙달 확률 추정(`bkt`). 슬라이스 2: BKT ↔
`ConceptMasteryHistory` 시계열 영속 결선(`mastery_tracking`). 슬라이스 6: forgetting(시간
감쇠). 슬라이스 7: IRT(문항 난이도·학생 능력 θ 추정·`irt`). 범위 밖(후속): IRT 난이도
적합·DKT 신경망·파라미터 적합(EM)·정서 신호·오개념 매핑.

이름 충돌 메모: `bkt`·`irt` 모두 `probability_correct`를 정의한다(서로 다른 모델). 패키지
레벨에선 BKT의 것만 재노출하고, IRT 정답확률은 `whymath_backend.l2.irt.probability_correct`로
명시 접근한다(모델 혼동 방지).
"""

from __future__ import annotations

from whymath_backend.l2.bkt import (
    DEFAULT_BKT_PARAMETERS,
    BktModel,
    BktParameters,
    apply_forgetting,
    apply_learning,
    posterior_mastery,
    probability_correct,
    update_mastery,
)
from whymath_backend.l2.irt import IrtItem, estimate_ability, item_information, select_next_item
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
    "IrtItem",
    "MasteryRecord",
    "apply_forgetting",
    "apply_learning",
    "compute_mastery_record",
    "estimate_ability",
    "item_information",
    "posterior_mastery",
    "select_next_item",
    "probability_correct",
    "record_attempt_mastery",
    "record_problem_attempt_mastery",
    "update_mastery",
]
