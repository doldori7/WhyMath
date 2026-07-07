"""문제유형 그래프 검증 — 그래프 레벨 invariant(skill_graph/validate.py 패턴 미러).

구조 invariant(problem_type_id 형식·필수 필드·behavior_skills 형식/≥1개)은 `ProblemTypeNode`
생성 시점(Pydantic)에서 강제되므로, 여기서는 단일 모델로 알 수 없는 *그래프 레벨* invariant을 본다:

  - **problem_type_id_unique**(error) — 유형 id 유일(join 붕괴 방지).
  - **behavior_skills_nonempty**(error) — 각 유형이 ≥1 스킬 참조(cognitive-action 표현 보장·방어적
    이중화; 모델 `min_length=1`이 1차 보장이나 그래프 레벨 계약을 명문화).
  - **family_singleton**(warning) — family에 유형이 1개뿐이면 그룹핑 의미가 약함(v1 경고·에러 아님).

성공 기준은 **error 0건**(warning은 구축을 막지 않음). **cross-corpus dangling**(behavior_skills가
skill_graph_v1 skill_id에 실재)은 여기서 검증하지 않는다 — 단일 코퍼스 검증 범위를 넘어(backend
거버넌스 테스트가 skill_graph_v1을 로드해 dangling 0을 동결). ProblemType≠SignaturePattern 구별
불변식도 두 심볼을 모두 import할 수 있는 backend 거버넌스 테스트가 authoritative(형식은 id 패턴이
구조적으로 보장).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.problem_type_graph.models import ProblemTypeNode

_ERROR = "error"
_WARNING = "warning"


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(skill_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class ProblemTypeValidationReport:
    """문제유형 그래프 검증 결과(skill_graph 리포트 형태 미러)."""

    node_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """error 심각도 이슈."""
        return [i for i in self.issues if i.severity == _ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """warning 심각도 이슈."""
        return [i for i in self.issues if i.severity == _WARNING]

    @property
    def success(self) -> bool:
        """error가 없으면 성공(warning 허용)."""
        return len(self.errors) == 0

    def counts_by_rule(self) -> dict[str, int]:
        """rule별 이슈 건수(결정론적·rule 이름 정렬)."""
        tally: dict[str, int] = {}
        for issue in self.issues:
            tally[issue.rule] = tally.get(issue.rule, 0) + 1
        return dict(sorted(tally.items()))

    def summary(self) -> str:
        """사람 가독 요약(PASS/FAIL = error 없음/있음)."""
        verdict = "PASS" if self.success else "FAIL"
        return (
            f"문제유형 그래프 검증[{verdict}]: 노드 {self.node_count}개, "
            f"error {len(self.errors)}개, warning {len(self.warnings)}개"
        )

    def report_text(self, *, max_examples: int = 10) -> str:
        """rule별 집계 + 구체 위반 예시."""
        lines = [self.summary()]
        tally = self.counts_by_rule()
        if tally:
            lines.append("  [rule별 집계]")
            for rule, count in tally.items():
                lines.append(f"    - {rule}: {count}건")
        for severity, label in ((_ERROR, "error"), (_WARNING, "warning")):
            picked = [i for i in self.issues if i.severity == severity]
            if not picked:
                continue
            lines.append(f"  [{label} 예시 (최대 {max_examples})]")
            for issue in picked[:max_examples]:
                lines.append(f"    [{label}] {issue.rule} | {issue.ref} | {issue.detail}")
        return "\n".join(lines)


def validate_problem_types(
    problem_types: Sequence[ProblemTypeNode],
) -> ProblemTypeValidationReport:
    """문제유형 그래프의 그래프 레벨 invariant 검증(구조 invariant은 모델 생성 시 이미 강제)."""
    report = ProblemTypeValidationReport(node_count=len(problem_types))

    # 1. problem_type_id_unique (error)
    counts: dict[str, int] = {}
    for node in problem_types:
        counts[node.problem_type_id] = counts.get(node.problem_type_id, 0) + 1
    for pid, count in sorted(counts.items()):
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=pid,
                    rule="problem_type_id_unique",
                    detail=f"problem_type_id 중복 {count}건 — join 붕괴",
                )
            )

    # 2. behavior_skills_nonempty (error) — 각 유형 ≥1 스킬(모델도 보장·그래프 계약 명문화).
    for node in problem_types:
        if not node.behavior_skills:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=node.problem_type_id,
                    rule="behavior_skills_nonempty",
                    detail="behavior_skills가 비어 cognitive-action 표현 부재",
                )
            )

    # 3. family_singleton (warning) — family에 유형이 1개뿐(그룹핑 의미 약함·v1 경고).
    family_counts: dict[str, int] = {}
    for node in problem_types:
        family_counts[node.family] = family_counts.get(node.family, 0) + 1
    for family, count in sorted(family_counts.items()):
        if count == 1:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=family,
                    rule="family_singleton",
                    detail=f"family '{family}'에 유형이 1개뿐(그룹핑 의미 약함·v1)",
                )
            )

    return report


__all__ = [
    "ProblemTypeValidationReport",
    "ValidationIssue",
    "validate_problem_types",
]
