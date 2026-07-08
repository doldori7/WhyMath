"""전략 그래프 검증 — 그래프 레벨 invariant(formula_graph/validate.py 패턴 미러).

구조 invariant(strategy_id 형식·필수 필드·family 화이트리스트·description 비어있지 않음)은
`StrategyNode` 생성 시점(Pydantic)에서 강제되므로, 여기서는 단일 모델로 알 수 없는 *그래프 레벨*
invariant을 본다. 전략은 **closed 8노드 택소노미**라 개수·slug 집합 자체가 계약이다:

  - **strategy_count**(error) — 정확히 8개(closed 택소노미·누락/증식 방지).
  - **strategy_slug_unique**(error) — slug(=strategy_id) 중복 없음(join 붕괴 방지).
  - **strategy_slug_set**(error) — slug 집합이 `STRATEGY_SLUGS`와 정확히 일치(누락·미승인 차단).
  - **strategy_family_known**(error) — family ∈ `STRATEGY_FAMILIES`(모델도 보장·그래프 계약 명문화).

성공 기준은 **error 0건**이다. 별도 **엣지 배열은 존재하지 않는다** — 전략 노드는 순수 canonical
단위이고(extra="forbid"·엣지 필드 없음) 연결은 소비처 참조 키가 담당한다(신규 엣지 타입 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.strategy_graph.models import (
    STRATEGY_FAMILIES,
    STRATEGY_SLUGS,
    StrategyNode,
)

_ERROR = "error"
_WARNING = "warning"

_STRATEGY_PREFIX = "strategy."
_EXPECTED_COUNT = len(STRATEGY_SLUGS)


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(formula_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class StrategyValidationReport:
    """전략 그래프 검증 결과(formula_graph 리포트 형태 미러)."""

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
            f"전략 그래프 검증[{verdict}]: 노드 {self.node_count}개, "
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


def _slug_of(strategy_id: str) -> str:
    """strategy_id에서 'strategy.' 접두를 제거한 slug(형식은 모델이 이미 보장)."""
    return strategy_id.removeprefix(_STRATEGY_PREFIX)


def validate_strategies(strategies: Sequence[StrategyNode]) -> StrategyValidationReport:
    """전략 그래프의 그래프 레벨 invariant 검증(구조 invariant은 모델 생성 시 이미 강제)."""
    report = StrategyValidationReport(node_count=len(strategies))

    # 1. strategy_count (error) — 정확히 8개(closed 택소노미).
    if len(strategies) != _EXPECTED_COUNT:
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref="<graph>",
                rule="strategy_count",
                detail=f"전략 {len(strategies)}개 — closed 택소노미는 정확히 {_EXPECTED_COUNT}개",
            )
        )

    # 2. strategy_slug_unique (error) — slug(=strategy_id) 중복 없음.
    counts: dict[str, int] = {}
    for node in strategies:
        counts[node.strategy_id] = counts.get(node.strategy_id, 0) + 1
    for sid, count in sorted(counts.items()):
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=sid,
                    rule="strategy_slug_unique",
                    detail=f"strategy_id 중복 {count}건 — join 붕괴",
                )
            )

    # 3. strategy_slug_set (error) — slug 집합이 STRATEGY_SLUGS와 정확히 일치.
    observed = {_slug_of(node.strategy_id) for node in strategies}
    expected = set(STRATEGY_SLUGS)
    for missing in sorted(expected - observed):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=missing,
                rule="strategy_slug_set",
                detail=f"필수 slug '{missing}' 누락(STRATEGY_SLUGS 불일치)",
            )
        )
    for extra in sorted(observed - expected):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=extra,
                rule="strategy_slug_set",
                detail=f"미승인 slug '{extra}'(STRATEGY_SLUGS에 없음)",
            )
        )

    # 4. strategy_family_known (error) — family ∈ STRATEGY_FAMILIES(모델도 보장·계약 명문화).
    for node in strategies:
        if node.family not in STRATEGY_FAMILIES:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=node.strategy_id,
                    rule="strategy_family_known",
                    detail=f"미승인 family '{node.family}'(STRATEGY_FAMILIES 밖)",
                )
            )

    return report


__all__ = [
    "StrategyValidationReport",
    "ValidationIssue",
    "validate_strategies",
]
