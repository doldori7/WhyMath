"""대학 성취기준 코퍼스 검증 — `atom_graph/validate.py` 리포트 패턴 미러.

단일 모델 invariant(코드·norm_id·소단원 형식·본문 비공란)은 `UniversityStandard`/링크 생성
시점(Pydantic)에서 강제되므로, 여기서는 *집합 레벨* invariant을 검증한다:

  - **norm_id_unique**(error) — 성취기준 norm_id 유일(PK 충돌 0).
  - **code_unique**(error) — 성취기준 code 유일(대학 내 비중복).
  - **subunit_unique**(error) — 링크 소단원(concept_src_id) 유일 = 소단원↔성취기준 1:1.
  - **link_referential**(error) — 모든 링크 norm_id가 성취기준 집합에 존재(고아 0).
  - **link_count**(error) — 링크 수 = 성취기준 수(1:1 — 누락·잉여 0).
  - **revision_university**(error) — 모든 성취기준 curriculum_revision == '대학'.
  - **subject_count**(warning) — 과목 수(검수보고 기대 32). 불일치는 리포트(에러 아님).

성공 기준은 **error 0건**(atom_graph·concept_graph 미러).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.standards_university.models import (
    UniversityConceptStandardLink,
    UniversityStandard,
)

_ERROR = "error"
_WARNING = "warning"
_EXPECTED_SUBJECT_COUNT = 32


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(atom_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class StandardsValidationReport:
    """대학 성취기준 코퍼스 검증 결과."""

    standard_count: int = 0
    link_count: int = 0
    subject_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == _ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == _WARNING]

    @property
    def is_valid(self) -> bool:
        """성공 = error 0건(warning은 막지 않음)."""
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"대학 성취기준 검증: standards={self.standard_count} links={self.link_count} "
            f"subjects={self.subject_count} "
            f"(error {len(self.errors)} · warning {len(self.warnings)})",
        ]
        for issue in self.issues:
            lines.append(f"  [{issue.severity}] {issue.rule} @ {issue.ref}: {issue.detail}")
        return "\n".join(lines)


def validate_standards(
    standards: Sequence[UniversityStandard],
    links: Sequence[UniversityConceptStandardLink],
) -> StandardsValidationReport:
    """대학 성취기준·링크 집합 검증(집합 레벨 invariant). 반환=리포트(error 0이면 유효)."""
    subjects = {s.subject for s in standards}
    report = StandardsValidationReport(
        standard_count=len(standards),
        link_count=len(links),
        subject_count=len(subjects),
    )
    norm_ids = [s.norm_id for s in standards]
    norm_id_set = set(norm_ids)

    # norm_id 유일.
    for nid, cnt in Counter(norm_ids).items():
        if cnt > 1:
            report.issues.append(
                ValidationIssue(_ERROR, nid, "norm_id_unique", f"norm_id 중복 {cnt}회")
            )
    # code 유일.
    for code, cnt in Counter(s.code for s in standards).items():
        if cnt > 1:
            report.issues.append(ValidationIssue(_ERROR, code, "code_unique", f"code 중복 {cnt}회"))
    # 소단원(링크 소스) 유일 = 1:1.
    for sub, cnt in Counter(link.concept_src_id for link in links).items():
        if cnt > 1:
            report.issues.append(
                ValidationIssue(_ERROR, sub, "subunit_unique", f"소단원 링크 중복 {cnt}회")
            )
    # 링크 referential(norm_id 존재).
    for link in links:
        if link.norm_id not in norm_id_set:
            report.issues.append(
                ValidationIssue(
                    _ERROR,
                    link.concept_src_id,
                    "link_referential",
                    f"링크 norm_id={link.norm_id}가 성취기준 집합에 없음",
                )
            )
    # 링크 수 = 성취기준 수(1:1).
    if len(links) != len(standards):
        report.issues.append(
            ValidationIssue(
                _ERROR,
                "-",
                "link_count",
                f"링크 수({len(links)}) != 성취기준 수({len(standards)}) — 1:1 위반",
            )
        )
    # curriculum_revision == '대학'.
    for s in standards:
        if s.curriculum_revision != "대학":
            report.issues.append(
                ValidationIssue(
                    _ERROR,
                    s.norm_id,
                    "revision_university",
                    f"curriculum_revision={s.curriculum_revision!r} (대학 기대)",
                )
            )
    # 과목 수(기대 32) — warning.
    if subjects and len(subjects) != _EXPECTED_SUBJECT_COUNT:
        report.issues.append(
            ValidationIssue(
                _WARNING,
                "-",
                "subject_count",
                f"과목 수 {len(subjects)} (검수보고 기대 {_EXPECTED_SUBJECT_COUNT})",
            )
        )
    return report


__all__ = ["StandardsValidationReport", "ValidationIssue", "validate_standards"]
