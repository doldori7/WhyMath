"""문제유형 그래프 정형화 — `problem_types.jsonl`(자체작성) → `ProblemTypeNode` 모델 목록.

입력이 자체작성 jsonl이라 별도 extract 단계가 없다(택소노미가 우리 자산). 각 raw 레코드를
`ProblemTypeNode`로 구성하며(Pydantic 검증), 실패 행은 조용히 넘기지 않고 `skipped`에 사유를
기록한다(CLAUDE.md 신뢰 원칙). skill_graph transform의 `TransformResult`(모델 목록 + skipped +
provenance 카운트) 패턴을 미러한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from data_pipeline.problem_type_graph.models import ProblemTypeNode


@dataclass(frozen=True, slots=True)
class TransformResult:
    """정형화 산출 — 문제유형 노드 목록 + skip 사유 + provenance 카운트."""

    problem_types: list[ProblemTypeNode]
    skipped: list[str] = field(default_factory=list)
    provenance: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """한 줄 요약(정형화 카운트)."""
        families = sorted({p.family for p in self.problem_types})
        return (
            f"정형화: 문제유형 {len(self.problem_types)}개, family {len(families)}개, "
            f"skip {len(self.skipped)}건"
        )


def transform_problem_types(records: list[dict[str, object]]) -> TransformResult:
    """raw 문제유형 레코드 목록 → `ProblemTypeNode` 정형화(Pydantic 검증·실패 행 skip 기록).

    각 레코드를 `ProblemTypeNode(**record)`로 구성한다 — `extra="forbid"`·형식 검증(problem_type_id·
    behavior_skills 패턴·≥1 스킬)·필수 누락은 `ValidationError`로 잡아 `skipped`에 사유를 남긴다
    (조용한 누락 금지). 중복 problem_type_id는 여기서 막지 않는다(`validate_problem_types` 몫).
    """
    problem_types: list[ProblemTypeNode] = []
    skipped: list[str] = []
    families: set[str] = set()
    skills: set[str] = set()
    for i, record in enumerate(records):
        try:
            node = ProblemTypeNode(**record)  # type: ignore[arg-type]
        except ValidationError as exc:
            pid = record.get("problem_type_id", f"<index {i}>")
            skipped.append(f"{pid}: {exc.error_count()}개 검증 오류")
            continue
        problem_types.append(node)
        families.add(node.family)
        skills.update(node.behavior_skills)
    provenance = {
        "problem_types": len(problem_types),
        "families": len(families),
        "referenced_skills": len(skills),
    }
    return TransformResult(problem_types=problem_types, skipped=skipped, provenance=provenance)


__all__ = ["TransformResult", "transform_problem_types"]
