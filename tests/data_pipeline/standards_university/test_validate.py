"""대학 성취기준 검증 단위테스트 — 집합 invariant(유일성·1:1·referential·revision·과목 수)."""

from __future__ import annotations

from data_pipeline.standards_university.models import (
    UniversityConceptStandardLink,
    UniversityStandard,
)
from data_pipeline.standards_university.validate import validate_standards


def _std(norm: str, code: str, subject: str = "미적분학 I") -> UniversityStandard:
    return UniversityStandard(
        norm_id=norm,
        code=code,
        subject=subject,
        domain="극한",
        statement="...",
    )


def _link(sub: str, norm: str) -> UniversityConceptStandardLink:
    return UniversityConceptStandardLink(concept_src_id=sub, norm_id=norm)


def test_valid_set_has_no_errors() -> None:
    standards = [_std("대학_CALC1_01_01", "[CALC1-01-01]")]
    links = [_link("CALC1-U1-S1", "대학_CALC1_01_01")]
    report = validate_standards(standards, links)
    assert report.is_valid
    assert report.standard_count == 1 and report.link_count == 1


def test_duplicate_norm_id_is_error() -> None:
    standards = [
        _std("대학_CALC1_01_01", "[CALC1-01-01]"),
        _std("대학_CALC1_01_01", "[CALC1-01-02]"),
    ]
    links = [
        _link("CALC1-U1-S1", "대학_CALC1_01_01"),
        _link("CALC1-U1-S2", "대학_CALC1_01_01"),
    ]
    report = validate_standards(standards, links)
    assert not report.is_valid
    assert any(i.rule == "norm_id_unique" for i in report.errors)


def test_duplicate_code_is_error() -> None:
    standards = [
        _std("대학_CALC1_01_01", "[CALC1-01-01]"),
        _std("대학_CALC1_01_02", "[CALC1-01-01]"),
    ]
    links = [
        _link("CALC1-U1-S1", "대학_CALC1_01_01"),
        _link("CALC1-U1-S2", "대학_CALC1_01_02"),
    ]
    report = validate_standards(standards, links)
    assert any(i.rule == "code_unique" for i in report.errors)


def test_duplicate_subunit_link_is_error() -> None:
    standards = [
        _std("대학_CALC1_01_01", "[CALC1-01-01]"),
        _std("대학_CALC1_01_02", "[CALC1-01-02]"),
    ]
    links = [
        _link("CALC1-U1-S1", "대학_CALC1_01_01"),
        _link("CALC1-U1-S1", "대학_CALC1_01_02"),
    ]
    report = validate_standards(standards, links)
    assert any(i.rule == "subunit_unique" for i in report.errors)


def test_dangling_link_norm_id_is_error() -> None:
    standards = [_std("대학_CALC1_01_01", "[CALC1-01-01]")]
    links = [_link("CALC1-U1-S1", "대학_CALC1_99_99")]  # 성취기준 집합에 없음
    report = validate_standards(standards, links)
    assert any(i.rule == "link_referential" for i in report.errors)


def test_link_count_mismatch_is_error() -> None:
    standards = [
        _std("대학_CALC1_01_01", "[CALC1-01-01]"),
        _std("대학_CALC1_01_02", "[CALC1-01-02]"),
    ]
    links = [_link("CALC1-U1-S1", "대학_CALC1_01_01")]  # 2 != 1
    report = validate_standards(standards, links)
    assert any(i.rule == "link_count" for i in report.errors)


def test_subject_count_warning_only() -> None:
    # 과목 수 32 미만 → warning(에러 아님·그래프 구축 막지 않음).
    standards = [_std("대학_CALC1_01_01", "[CALC1-01-01]")]
    links = [_link("CALC1-U1-S1", "대학_CALC1_01_01")]
    report = validate_standards(standards, links)
    assert report.is_valid  # warning만
    assert any(i.rule == "subject_count" and i.severity == "warning" for i in report.warnings)
