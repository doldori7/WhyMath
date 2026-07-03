"""스킬 그래프 검증 — 그래프 레벨 invariant(atom_graph/validate.py 패턴 미러).

구조 invariant(skill_id 형식·필수 필드·behavior_area 값)은 `SkillNode` 생성 시점(Pydantic)에서
강제되므로, 여기서는 단일 모델로 알 수 없는 *그래프 레벨* invariant을 본다:

  - **skill_id_unique**(error) — 스킬 code 유일(join 붕괴 방지).
  - **prerequisite_dangling**(error) — `prerequisite_skill_ids`가 스킬 집합에 존재(자기완결 코퍼스).
  - **prerequisite_cycle**(error) — 선수 참조가 DAG(순환 = 학습 경로 불능).
  - **behavior_area_coverage**(warning) — 6종 행동영역 각각 ≥1개 스킬(v1 커버리지·에러 아님).

성공 기준은 **error 0건**(warning은 구축을 막지 않음 — atom_graph §3 미러).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.skill_graph.models import BEHAVIOR_AREAS, SkillNode

_ERROR = "error"
_WARNING = "warning"


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(atom_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class SkillValidationReport:
    """스킬 그래프 검증 결과(atom_graph 리포트 형태 미러)."""

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
            f"스킬 그래프 검증[{verdict}]: 노드 {self.node_count}개, "
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


def _find_prerequisite_cycle(skills: Sequence[SkillNode]) -> list[str] | None:
    """선수 참조 그래프(skill → prerequisite)에서 사이클 1건 탐지(반복 스택 DFS).

    `atom_graph.validate._find_prerequisite_cycle` 미러(재귀 대신 명시 스택). Returns: 사이클
    노드 경로 또는 None. dangling 참조는 사이클 탐지 대상이 아니다(별도 rule).
    """
    adj: dict[str, list[str]] = {}
    ids = {s.skill_id for s in skills}
    for skill in skills:
        # 존재하는 선수만 그래프에 넣는다(dangling은 prerequisite_dangling이 별도로 잡음).
        adj.setdefault(skill.skill_id, [])
        for pre in skill.prerequisite_skill_ids:
            if pre in ids:
                adj[skill.skill_id].append(pre)

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {}
    for start in list(adj):
        if color.get(start, white) != white:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = [start]
        color[start] = gray
        while stack:
            node, child_idx = stack[-1]
            children = adj.get(node, [])
            if child_idx < len(children):
                stack[-1] = (node, child_idx + 1)
                nxt = children[child_idx]
                state = color.get(nxt, white)
                if state == gray:  # back-edge → 사이클
                    return path[path.index(nxt) :] + [nxt]
                if state == white:
                    color[nxt] = gray
                    path.append(nxt)
                    stack.append((nxt, 0))
            else:
                color[node] = black
                path.pop()
                stack.pop()
    return None


def validate_skills(skills: Sequence[SkillNode]) -> SkillValidationReport:
    """스킬 그래프의 그래프 레벨 invariant 검증(구조 invariant은 모델 생성 시 이미 강제)."""
    report = SkillValidationReport(node_count=len(skills))
    ids = {s.skill_id for s in skills}

    # 1. skill_id_unique (error)
    counts: dict[str, int] = {}
    for skill in skills:
        counts[skill.skill_id] = counts.get(skill.skill_id, 0) + 1
    for skill_id, count in sorted(counts.items()):
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=skill_id,
                    rule="skill_id_unique",
                    detail=f"skill_id 중복 {count}건 — join 붕괴",
                )
            )

    # 2. prerequisite_dangling (error) — 선수 참조가 스킬 집합에 존재(자기완결 코퍼스).
    for skill in skills:
        for pre in skill.prerequisite_skill_ids:
            if pre not in ids:
                report.issues.append(
                    ValidationIssue(
                        severity=_ERROR,
                        ref=skill.skill_id,
                        rule="prerequisite_dangling",
                        detail=f"선수 스킬이 코퍼스에 없음: {pre}",
                    )
                )

    # 3. prerequisite_cycle (error) — 선수 참조 DAG.
    cycle = _find_prerequisite_cycle(skills)
    if cycle is not None:
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=" → ".join(cycle),
                rule="prerequisite_cycle",
                detail="순환 선수관계 — 학습 경로 구성 불가",
            )
        )

    # 4. behavior_area_coverage (warning) — 6종 각각 ≥1개(v1 커버리지·에러 아님).
    present = {s.behavior_area for s in skills}
    for area in BEHAVIOR_AREAS:
        if area not in present:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=area,
                    rule="behavior_area_coverage",
                    detail=f"행동영역 {area}에 스킬이 없음(v1 커버리지 권장)",
                )
            )

    return report


__all__ = [
    "SkillValidationReport",
    "ValidationIssue",
    "validate_skills",
]
