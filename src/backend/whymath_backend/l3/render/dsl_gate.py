"""ConceptDSL 닫힌-DSL 게이트 — pseudo-DSL 거부(03c §1·구성 경계 강제).

`schema/concept_dsl.py::ConceptDSL`은 7계층 최하위(schema)라 SymPy 래퍼(`l3.equivalent`)를
import할 수 없어, 평가 조건의 *닫힌 검증 DSL* 게이트를 자기 안에 걸 수 없다(import-linter 역방향
금지). 그 게이트를 이 계약을 *소비하는* 렌더 계층(l3)에서 건다 — schema(계약)·l3.equivalent
(게이트 함수) 둘 다 정당하게 import하는 유일한 정당 지점이다(관심사 분리·단일 진실 재사용).

`condition_dsl_violation`(`l3/equivalent/canonicalize.py`)이 `largest_root(2,8)==8`·
`solve(...)==[6,4]`류 pseudo-symbolic을 거부한다(닫힌 (부)등식만 허용). 어댑터(worked_example·
problem_based)도 렌더 경로에서 이 검사를 belt-and-suspenders로 재적용한다.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.schema.concept_dsl import ConceptDSL

__all__ = ["assessment_dsl_violation", "validate_concept_dsl"]


def assessment_dsl_violation(dsl: ConceptDSL) -> str | None:
    """DSL의 모든 assessment 조건을 닫힌-DSL 검사 — 첫 위반 사유, 적법하면 None.

    조건 하나라도 pseudo-DSL(미정의 함수·비수식 관계·파싱 불가)이면 위치와 사유를 돌린다.
    """
    for seed_index, seed in enumerate(dsl.assessment):
        for cond_index, condition in enumerate(seed.conditions):
            violation = condition_dsl_violation(condition)
            if violation is not None:
                return f"assessment[{seed_index}].conditions[{cond_index}] — {violation}"
    return None


def validate_concept_dsl(dsl: ConceptDSL) -> None:
    """구성 경계 게이트 — assessment 조건에 pseudo-DSL이 있으면 ValueError(저장/렌더 전 차단).

    적법하면 조용히 통과한다(부작용 없음). 고가치 생성물을 DSL 자산으로 승격(03c §3)하기 전
    이 게이트를 통과시켜 닫힌-DSL 계약을 강제한다.
    """
    violation = assessment_dsl_violation(dsl)
    if violation is not None:
        raise ValueError(f"ConceptDSL 닫힌-DSL 위반 — {violation}")
