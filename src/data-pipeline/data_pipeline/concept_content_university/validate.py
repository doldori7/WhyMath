"""대학 소단원 콘텐츠 코퍼스 검증 — `standards_university/validate.py` 리포트 패턴 미러.

집합 invariant:
  - **code_unique**(error) — 소단원 코드 유일.
  - **name_present**(error) — 소단원명 비공란.
  - **content_present**(warning) — 핵심 콘텐츠(은유·오개념·정식정의·허용표현) 누락 보고(검수 큐).
  - **subject_count**(warning) — 과목 수(기대 32).

성공 = error 0(콘텐츠 누락은 warning — 검수 대상이지 적재 차단 아님).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.concept_content_university.models import UniversityConceptContent

_ERROR = "error"
_WARNING = "warning"
_EXPECTED_SUBJECTS = 32


@dataclass(slots=True)
class ContentValidationReport:
    """대학 콘텐츠 코퍼스 검증 결과."""

    content_count: int = 0
    flashcard_count: int = 0
    subject_count: int = 0
    issues: list[tuple[str, str, str]] = field(default_factory=list)  # (severity, rule, detail)

    @property
    def errors(self) -> list[tuple[str, str, str]]:
        return [i for i in self.issues if i[0] == _ERROR]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        warns = [i for i in self.issues if i[0] == _WARNING]
        lines = [
            f"대학 콘텐츠 검증: content={self.content_count} flashcards={self.flashcard_count} "
            f"subjects={self.subject_count} (error {len(self.errors)} · warning {len(warns)})"
        ]
        for sev, rule, detail in self.issues[:20]:
            lines.append(f"  [{sev}] {rule}: {detail}")
        return "\n".join(lines)


def validate_content(
    items: Sequence[UniversityConceptContent],
) -> ContentValidationReport:
    """대학 소단원 콘텐츠 집합 검증. 반환=리포트(error 0이면 유효)."""
    report = ContentValidationReport(
        content_count=len(items),
        flashcard_count=sum(len(c.flashcards) for c in items),
        subject_count=len({c.subject for c in items}),
    )
    for code, cnt in Counter(c.code for c in items).items():
        if cnt > 1:
            report.issues.append((_ERROR, "code_unique", f"소단원 코드 중복 {cnt}회: {code}"))
    for c in items:
        if not c.name:
            report.issues.append((_ERROR, "name_present", f"소단원명 공란: {c.code}"))
        missing = [
            label
            for label, val in (
                ("은유", c.metaphor),
                ("오개념", c.misconception),
                ("정식정의", c.formal_definition_internal),
                ("허용표현", c.accepted_expressions),
            )
            if not val
        ]
        if missing:
            report.issues.append(
                (
                    _WARNING,
                    "content_present",
                    f"{c.code} 콘텐츠 누락: {','.join(missing)}",
                )
            )
    if items and report.subject_count != _EXPECTED_SUBJECTS:
        report.issues.append(
            (
                _WARNING,
                "subject_count",
                f"과목 수 {report.subject_count} (기대 {_EXPECTED_SUBJECTS})",
            )
        )
    return report


__all__ = ["ContentValidationReport", "validate_content"]
