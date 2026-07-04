"""concept_atom_crosswalk 검증 규칙 단위테스트 — dangling·전량 존재·유일성·커버리지 집계.

hermetic: 인메모리 CrosswalkEntry fixture만 사용(코퍼스 파일·DB 불요).
"""

from __future__ import annotations

from data_pipeline.concept_atom_crosswalk.models import CrosswalkEntry, MatchMethod
from data_pipeline.concept_atom_crosswalk.validate import validate_crosswalk


def _mapped(concept_id: str, atom_code: str) -> CrosswalkEntry:
    """유일 후보 매핑 행."""
    return CrosswalkEntry(
        concept_id=concept_id,
        atom_codes=[atom_code],
        primary_atom_code=atom_code,
        match_method=MatchMethod.STANDARD_CODE,
        confidence=0.9,
        evidence="fixture",
    )


def _unmapped(concept_id: str) -> CrosswalkEntry:
    """미매핑 행."""
    return CrosswalkEntry(
        concept_id=concept_id,
        atom_codes=[],
        primary_atom_code=None,
        match_method=MatchMethod.UNMAPPED,
        confidence=0.0,
        evidence="fixture",
        unmapped_reason="교집합 0",
    )


class TestValidateRules:
    """그래프 레벨 규칙 — error rule별 검출."""

    def test_all_green(self) -> None:
        """정합 코퍼스 — error 0·커버리지 실측 집계."""
        entries = [_mapped("math.algebra.a", "A-1"), _unmapped("math.algebra.b")]
        report = validate_crosswalk(
            entries,
            concept_ids={"math.algebra.a", "math.algebra.b"},
            atom_codes={"A-1"},
        )
        assert report.success
        assert report.mapped_count == 1
        assert report.unmapped_count == 1
        assert report.method_counts == {"standard_code": 1, "unmapped": 1}
        assert report.fanout_counts == {0: 1, 1: 1}

    def test_concept_dangling(self) -> None:
        """구 그래프에 없는 concept_id → concept_dangling error."""
        report = validate_crosswalk(
            [_mapped("math.algebra.ghost", "A-1")],
            concept_ids={"math.algebra.a"},
            atom_codes={"A-1"},
        )
        assert not report.success
        assert "concept_dangling" in report.counts_by_rule()

    def test_atom_dangling(self) -> None:
        """원자 백본에 없는 atom code → atom_dangling error."""
        report = validate_crosswalk(
            [_mapped("math.algebra.a", "GHOST-1")],
            concept_ids={"math.algebra.a"},
            atom_codes={"A-1"},
        )
        assert not report.success
        assert "atom_dangling" in report.counts_by_rule()

    def test_concept_missing(self) -> None:
        """구 그래프 개념이 크로스워크에 없음 → concept_missing error(전량 원칙)."""
        report = validate_crosswalk(
            [_mapped("math.algebra.a", "A-1")],
            concept_ids={"math.algebra.a", "math.algebra.b"},
            atom_codes={"A-1"},
        )
        assert not report.success
        assert "concept_missing" in report.counts_by_rule()

    def test_concept_duplicate(self) -> None:
        """concept_id 중복 → concept_duplicate error."""
        report = validate_crosswalk(
            [_mapped("math.algebra.a", "A-1"), _mapped("math.algebra.a", "A-1")],
            concept_ids={"math.algebra.a"},
            atom_codes={"A-1"},
        )
        assert not report.success
        assert report.counts_by_rule().get("concept_duplicate") == 1

    def test_primary_invariant_recheck(self) -> None:
        """primary가 atom_codes 밖(모델 우회 유입 가정) → primary_invariant error.

        Pydantic이 정상 경로에선 막지만, validate는 파일 재독 경로 방어로 재확인한다.
        model_construct로 검증을 우회해 주입한다.
        """
        broken = CrosswalkEntry.model_construct(
            concept_id="math.algebra.a",
            atom_codes=["A-1"],
            primary_atom_code="A-9",
            match_method="standard_code",
            confidence=0.9,
            evidence="fixture",
            review_status="ai_estimated",
            unmapped_reason=None,
        )
        report = validate_crosswalk([broken], concept_ids={"math.algebra.a"}, atom_codes={"A-1"})
        assert not report.success
        assert "primary_invariant" in report.counts_by_rule()

    def test_report_text_mentions_coverage(self) -> None:
        """report_text에 커버리지 실측(매핑/미매핑)이 드러난다."""
        report = validate_crosswalk(
            [_mapped("math.algebra.a", "A-1")],
            concept_ids={"math.algebra.a"},
            atom_codes={"A-1"},
        )
        text = report.report_text()
        assert "매핑 1" in text
        assert "미매핑 0" in text
