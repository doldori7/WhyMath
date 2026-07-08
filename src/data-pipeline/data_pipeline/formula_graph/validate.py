"""수식 그래프 검증 — 그래프 레벨 invariant(problem_type_graph/validate.py 패턴 미러).

구조 invariant(formula_id 형식·필수 필드·latex/dsl 비어있지 않음)은 `FormulaNode` 생성 시점
(Pydantic)에서 강제되므로, 여기서는 단일 모델로 알 수 없는 *그래프 레벨* invariant을 본다:

  - **formula_id_unique**(error) — 수식 id 유일(join 붕괴 방지·canonical 중복 금지).
  - **family_singleton**(warning) — family에 수식이 1개뿐이면 그룹핑 의미가 약함(v1 경고·에러 아님).

성공 기준은 **error 0건**(warning은 구축을 막지 않음). **dsl SymPy-parseable** 검증은 여기서 하지
않는다 — data-pipeline은 sympy-free이고, parseable 여부는 backend 거버넌스 테스트(sympy 보유)가
`to_sympy_source`+`condition_dsl_violation`으로 동결한다(계층 무관·의존 최소).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.formula_graph.models import FormulaNode

_ERROR = "error"
_WARNING = "warning"


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(problem_type_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class FormulaValidationReport:
    """수식 그래프 검증 결과(problem_type_graph 리포트 형태 미러)."""

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
            f"수식 그래프 검증[{verdict}]: 노드 {self.node_count}개, "
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


def validate_formulas(formulas: Sequence[FormulaNode]) -> FormulaValidationReport:
    """수식 그래프의 그래프 레벨 invariant 검증(구조 invariant은 모델 생성 시 이미 강제)."""
    report = FormulaValidationReport(node_count=len(formulas))

    # 1. formula_id_unique (error) — canonical 수식 id 유일.
    counts: dict[str, int] = {}
    for node in formulas:
        counts[node.formula_id] = counts.get(node.formula_id, 0) + 1
    for fid, count in sorted(counts.items()):
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=fid,
                    rule="formula_id_unique",
                    detail=f"formula_id 중복 {count}건 — join 붕괴·canonical 중복",
                )
            )

    # 2. family_singleton (warning) — family에 수식이 1개뿐(그룹핑 의미 약함·v1 경고).
    family_counts: dict[str, int] = {}
    for node in formulas:
        family_counts[node.family] = family_counts.get(node.family, 0) + 1
    for family, count in sorted(family_counts.items()):
        if count == 1:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=family,
                    rule="family_singleton",
                    detail=f"family '{family}'에 수식이 1개뿐(그룹핑 의미 약함·v1)",
                )
            )

    return report


__all__ = [
    "FormulaValidationReport",
    "ValidationIssue",
    "validate_formulas",
]
