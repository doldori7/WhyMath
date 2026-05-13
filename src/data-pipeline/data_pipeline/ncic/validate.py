"""성취기준 검증.

great_expectations 미사용(대형 의존성). 자체 validator로 동일 invariant 검증.
Phase 2에 PostgreSQL·great_expectations 도입 시 이 모듈만 어댑터로 전환.

검증 invariants (`.claude/agents/data-engineer.md` 검증 패턴 기준):
  1. 모든 행 `code` 비공백
  2. `code` 정규식 일치
  3. `grade_band` enum 집합
  4. `school_type` ↔ `grade_band` 정합성 (모델에서 일차 검증, 여기서 재확인)
  5. `statement` 비공백
  6. `code` 중복 없음 (PK 가정)
  7. `source_url` 비공백 (공공누리 출처 표시 의무)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.ncic.models import (
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    GradeBand,
)

# typing.get_args(GradeBand)와 등가 — 명시적 리스트가 가독성 우월
_VALID_GRADE_BANDS: frozenset[GradeBand] = frozenset(
    [
        "초등학교 1~2학년군",
        "초등학교 3~4학년군",
        "초등학교 5~6학년군",
        "중학교 1~3학년군",
        "고등학교",
    ]
)


@dataclass(slots=True)
class ValidationIssue:
    """검증 실패 항목 1건."""

    code: str
    rule: str
    detail: str


@dataclass(slots=True)
class ValidationReport:
    """검증 결과 묶음."""

    total: int = 0
    passed: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """실패 건수."""
        return self.total - self.passed

    @property
    def success(self) -> bool:
        """전건 통과 여부."""
        return self.failed == 0 and self.total > 0

    def summary(self) -> str:
        """사람 가독 요약."""
        return (
            f"검증 결과: 총 {self.total}건, 통과 {self.passed}건, "
            f"실패 {self.failed}건, 이슈 {len(self.issues)}개"
        )


def validate_standards(standards: Sequence[AchievementStandard]) -> ValidationReport:
    """성취기준 컬렉션을 검증.

    Args:
        standards: 검증 대상.

    Returns:
        ValidationReport. `issues`에 실패 항목들이 누적.

    설계:
      - Pydantic 모델은 *생성 시점* 검증 → 여기서는 *컬렉션 invariants* 추가.
        예: 중복 코드는 단일 모델로는 알 수 없음.
    """
    report = ValidationReport(total=len(standards))

    seen_codes: set[str] = set()

    for std in standards:
        code = std.code
        ok = True

        # 규칙 1: code 비공백 + 정규식 (Pydantic이 이미 검증했으나 재확인)
        if not code or not STANDARD_CODE_PATTERN.match(code):
            report.issues.append(
                ValidationIssue(code=code, rule="code_format", detail="코드 정규식 미일치")
            )
            ok = False

        # 규칙 2: grade_band enum
        if std.grade_band not in _VALID_GRADE_BANDS:
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="grade_band_enum",
                    detail=f"비표준 학년군: {std.grade_band!r}",
                )
            )
            ok = False

        # 규칙 3: statement 비공백
        if not std.statement.strip():
            report.issues.append(
                ValidationIssue(code=code, rule="statement_nonblank", detail="본문 빈 문자열")
            )
            ok = False

        # 규칙 4: source_url 비공백 (공공누리 1유형 의무)
        if not std.source_url.strip():
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="source_url_required",
                    detail="공공누리 1유형: source_url 누락 — 출처 표시 의무 위반",
                )
            )
            ok = False

        # 규칙 5: 중복 코드
        if code in seen_codes:
            report.issues.append(
                ValidationIssue(code=code, rule="duplicate_code", detail="코드 중복")
            )
            ok = False
        else:
            seen_codes.add(code)

        # 규칙 6: 학교급-학년군 정합성 (모델 model_validator로 검증되나 재확인)
        if std.school_type == "초등학교" and not std.grade_band.startswith("초등학교"):
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="school_band_consistency",
                    detail=f"초등학교 + {std.grade_band}",
                )
            )
            ok = False
        elif std.school_type == "중학교" and std.grade_band != "중학교 1~3학년군":
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="school_band_consistency",
                    detail=f"중학교 + {std.grade_band}",
                )
            )
            ok = False
        elif std.school_type == "고등학교" and std.grade_band != "고등학교":
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="school_band_consistency",
                    detail=f"고등학교 + {std.grade_band}",
                )
            )
            ok = False

        if ok:
            report.passed += 1

    return report


__all__ = ["ValidationIssue", "ValidationReport", "validate_standards"]
