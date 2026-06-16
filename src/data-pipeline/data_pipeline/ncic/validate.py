"""성취기준 검증.

great_expectations 미사용(대형 의존성). 자체 validator로 동일 invariant 검증.
Phase 2에 PostgreSQL·great_expectations 도입 시 이 모듈만 어댑터로 전환.

성취기준 검증 invariants (`.claude/agents/data-engineer.md` 검증 패턴 기준):
  1. 모든 행 `code` 비공백
  2. `code` 정규식 일치
  3. `grade_band` enum 집합
  4. `school_type` ↔ `grade_band` 정합성 (모델에서 일차 검증, 여기서 재확인)
  5. `statement` 비공백
  6. `source_url` 비공백 (공공누리 출처 표시 의무)
  7. `norm_id` 중복 없음 (PK 가정 — P1-1 신규)
  8. `(curriculum_revision, code)` 중복 없음 — *같은 code의 교육과정 간 공존은 허용* (P1-1)
  9. `curriculum_split` — 개정별 건수 집계 (INFO, 오류 아님; P1-1)

링크 검증 invariants (`validate_links`):
  - link_type_enum      — link_type ∈ {직접, 재매핑, 준용}
  - link_norm_id_resolves — link.norm_id ∈ 성취기준 norm_id 집합
  - link_concept_resolves — link.concept_src_id ∈ 알려진 개념 id 집합
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from data_pipeline.ncic.models import (
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    ConceptStandardLink,
    GradeBand,
)

# link_type 허용 집합 — ConceptLinkType Literal과 동기화.
_VALID_LINK_TYPES: frozenset[str] = frozenset({"직접", "재매핑", "준용"})

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
    """검증 실패 항목 1건.

    `code`: 행 식별자 슬롯 — 성취기준 규칙은 official_code, 링크 규칙은 norm_id를 담는다.
    `severity`: 'error'(기본) | 'info'. INFO는 *집계·안내*용으로 pass/fail에 영향을 주지 않는다.
    """

    code: str
    rule: str
    detail: str
    severity: str = "error"


@dataclass(slots=True)
class ValidationReport:
    """검증 결과 묶음.

    `passed`/`failed`/`success`는 *오류(severity='error')* 기준이다 — INFO 이슈는 `issues`에
    누적되지만 통과 판정에는 영향을 주지 않는다.
    """

    total: int = 0
    passed: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """실패 건수 (오류 기준)."""
        return self.total - self.passed

    @property
    def success(self) -> bool:
        """전건 통과 여부 (오류 0건 + 검증 대상 존재)."""
        return self.failed == 0 and self.total > 0

    @property
    def errors(self) -> list[ValidationIssue]:
        """오류(severity='error') 이슈만."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def infos(self) -> list[ValidationIssue]:
        """INFO 이슈만 (집계·안내)."""
        return [i for i in self.issues if i.severity == "info"]

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
        ValidationReport. `issues`에 실패 항목(+ INFO 집계)이 누적.

    설계:
      - Pydantic 모델은 *생성 시점* 검증 → 여기서는 *컬렉션 invariants* 추가.
        예: 중복은 단일 모델로는 알 수 없음.
      - PK는 norm_id이므로 유일성은 norm_id로 본다. official_code는 교육과정 간 *비유일*이라
        `(curriculum_revision, code)` 조합만 유일하게 본다.
    """
    report = ValidationReport(total=len(standards))

    seen_norm_ids: set[str] = set()
    seen_code_revision: set[tuple[str, str]] = set()
    revision_counts: dict[str, int] = {}

    for std in standards:
        code = std.code
        norm_id = std.norm_id
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

        # 규칙 5: norm_id 유일성 (PK) — P1-1 신규
        if norm_id in seen_norm_ids:
            report.issues.append(
                ValidationIssue(code=norm_id, rule="norm_id_unique", detail="norm_id 중복")
            )
            ok = False
        else:
            seen_norm_ids.add(norm_id)

        # 규칙 6: (curriculum_revision, code) 유일성 — P1-1 신규.
        #   *같은 code의 교육과정 간 공존은 허용*(2022·2015에 동일 code 가능).
        #   같은 교육과정 안에서 같은 code가 두 번 나오면 위반.
        cr_key = (std.curriculum_revision, code)
        if cr_key in seen_code_revision:
            report.issues.append(
                ValidationIssue(
                    code=code,
                    rule="official_code_curriculum_unique",
                    detail=f"동일 교육과정 내 code 중복: {std.curriculum_revision!r} / {code}",
                )
            )
            ok = False
        else:
            seen_code_revision.add(cr_key)

        # 규칙 7: 학교급-학년군 정합성 (모델 model_validator로 검증되나 재확인)
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

        # 개정별 집계 (규칙 8: curriculum_split — INFO)
        revision_counts[std.curriculum_revision] = (
            revision_counts.get(std.curriculum_revision, 0) + 1
        )

        if ok:
            report.passed += 1

    # 규칙 8: curriculum_split — 개정별 건수 INFO (오류 아님)
    for revision in sorted(revision_counts):
        report.issues.append(
            ValidationIssue(
                code=revision,
                rule="curriculum_split",
                detail=f"{revision}: {revision_counts[revision]}건",
                severity="info",
            )
        )

    return report


def validate_links(
    links: Sequence[ConceptStandardLink],
    standards: Sequence[AchievementStandard],
    known_concept_ids: Iterable[str],
) -> ValidationReport:
    """개념↔성취기준 연결을 검증.

    참조 무결성: 링크가 가리키는 norm_id·concept_src_id가 실재하는지 본다.

    Args:
        links: 검증 대상 연결.
        standards: 연결 대상 후보 성취기준 (norm_id 해소용).
        known_concept_ids: 알려진 개념 소스 id 집합 (concept_src_id 해소용).

    Returns:
        ValidationReport. 규칙: link_type_enum / link_norm_id_resolves / link_concept_resolves.
    """
    report = ValidationReport(total=len(links))

    valid_norm_ids: set[str] = {std.norm_id for std in standards}
    concept_ids: set[str] = set(known_concept_ids)

    for link in links:
        # 식별자 슬롯: norm_id 사용 (링크의 자연 키)
        ident = link.norm_id
        ok = True

        # 규칙 1: link_type enum (모델 Literal이 일차 검증, 여기서 재확인)
        if link.link_type not in _VALID_LINK_TYPES:
            report.issues.append(
                ValidationIssue(
                    code=ident,
                    rule="link_type_enum",
                    detail=f"비허용 link_type: {link.link_type!r}",
                )
            )
            ok = False

        # 규칙 2: norm_id 참조 해소
        if link.norm_id not in valid_norm_ids:
            report.issues.append(
                ValidationIssue(
                    code=ident,
                    rule="link_norm_id_resolves",
                    detail=f"미해소 norm_id: {link.norm_id!r} (성취기준 집합에 없음)",
                )
            )
            ok = False

        # 규칙 3: concept_src_id 참조 해소
        if link.concept_src_id not in concept_ids:
            report.issues.append(
                ValidationIssue(
                    code=ident,
                    rule="link_concept_resolves",
                    detail=f"미해소 concept_src_id: {link.concept_src_id!r} (개념 집합에 없음)",
                )
            )
            ok = False

        if ok:
            report.passed += 1

    return report


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "validate_links",
    "validate_standards",
]
