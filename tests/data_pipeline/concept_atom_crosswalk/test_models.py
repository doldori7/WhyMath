"""concept_atom_crosswalk 모델 단위테스트 — `CrosswalkEntry`·`MatchMethod` 불변식 동결.

hermetic: 외부 의존·DB·코퍼스 파일 불요(모델 검증만). openpyxl/neo4j 미사용(CI extra 없음).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.concept_atom_crosswalk.models import (
    MATCH_METHODS,
    REVIEW_STATUS_AI_ESTIMATED,
    CrosswalkEntry,
    MatchMethod,
)


def _entry(**overrides: object) -> CrosswalkEntry:
    """기본 유효 CrosswalkEntry(복수 후보·이름 랭킹 케이스·오버라이드 가능)."""
    payload: dict[str, object] = {
        "concept_id": "math.algebra.insubunhae",
        "atom_codes": ["9수02-01-1", "9수02-01-2"],
        "primary_atom_code": "9수02-01-2",
        "match_method": MatchMethod.STANDARD_CODE_NAME,
        "confidence": 0.75,
        "evidence": "성취기준 교집합 ['[9수02-01]'] → 후보 2개; 이름 자카드 최고 0.6250",
    }
    payload.update(overrides)
    return CrosswalkEntry(**payload)  # type: ignore[arg-type]


class TestMatchMethodFrozen:
    """MatchMethod 폐쇄 3종 동결 — 추가/변경은 유도 규칙 변경과 함께만."""

    def test_exactly_three_members(self) -> None:
        """매칭 방법은 정확히 3종(유도 규칙 3단계와 1:1)."""
        assert len(MatchMethod) == 3

    def test_value_set_frozen(self) -> None:
        """3종 값 집합 동결."""
        assert set(MATCH_METHODS) == {"standard_code", "standard_code+name", "unmapped"}


class TestCrosswalkEntryValid:
    """유효 행 생성 — 매핑·미매핑 양쪽."""

    def test_mapped_multi_candidate(self) -> None:
        """복수 후보 + 이름 랭킹 행이 유효하게 생성된다."""
        entry = _entry()
        assert entry.primary_atom_code == "9수02-01-2"
        assert entry.review_status == REVIEW_STATUS_AI_ESTIMATED

    def test_mapped_single_candidate(self) -> None:
        """교집합 유일 후보 행 — match_method='standard_code'·후보 1개."""
        entry = _entry(
            atom_codes=["9수02-01-1"],
            primary_atom_code="9수02-01-1",
            match_method=MatchMethod.STANDARD_CODE,
            confidence=0.9,
        )
        assert entry.atom_codes == ["9수02-01-1"]

    def test_unmapped(self) -> None:
        """미매핑 행 — 후보 0·primary None·사유 필수·confidence 0."""
        entry = _entry(
            atom_codes=[],
            primary_atom_code=None,
            match_method=MatchMethod.UNMAPPED,
            confidence=0.0,
            unmapped_reason="성취기준 교집합 원자 0개",
        )
        assert entry.primary_atom_code is None


class TestCrosswalkEntryInvariants:
    """행 내부 불변식 위반 — 전부 ValidationError."""

    def test_bad_concept_id_rejected(self) -> None:
        """concept_id는 'math.<area>.<slug>' 규약 필수."""
        with pytest.raises(ValidationError, match="concept_id 규약 위반"):
            _entry(concept_id="ELEM-ALG-001")

    def test_primary_must_be_in_atom_codes(self) -> None:
        """primary가 atom_codes 밖이면 거부."""
        with pytest.raises(ValidationError, match="atom_codes에 없음"):
            _entry(primary_atom_code="9수02-99-9")

    def test_mapped_requires_primary(self) -> None:
        """매핑 행에 primary 없음 → 거부(정확히 1개 원칙)."""
        with pytest.raises(ValidationError, match="primary_atom_code 필수"):
            _entry(primary_atom_code=None)

    def test_duplicate_atom_codes_rejected(self) -> None:
        """atom_codes 중복 거부."""
        with pytest.raises(ValidationError, match="중복 금지"):
            _entry(atom_codes=["9수02-01-1", "9수02-01-1"])

    def test_unsorted_atom_codes_rejected(self) -> None:
        """atom_codes는 code 사전순(결정론) — 비정렬 거부."""
        with pytest.raises(ValidationError, match="사전순"):
            _entry(atom_codes=["9수02-01-2", "9수02-01-1"])

    def test_unmapped_requires_reason(self) -> None:
        """unmapped 행에 사유 없음 → 거부."""
        with pytest.raises(ValidationError, match="unmapped_reason 필수"):
            _entry(
                atom_codes=[],
                primary_atom_code=None,
                match_method=MatchMethod.UNMAPPED,
                confidence=0.0,
            )

    def test_unmapped_rejects_atom_codes(self) -> None:
        """unmapped 행에 후보 존재 → 거부(강제 매핑 금지)."""
        with pytest.raises(ValidationError, match="비어야"):
            _entry(
                match_method=MatchMethod.UNMAPPED,
                confidence=0.0,
                unmapped_reason="사유",
            )

    def test_mapped_rejects_unmapped_reason(self) -> None:
        """매핑 행에 unmapped_reason 혼입 → 거부."""
        with pytest.raises(ValidationError, match="unmapped_reason 금지"):
            _entry(unmapped_reason="사유 아님")

    def test_standard_code_requires_single_candidate(self) -> None:
        """standard_code 행은 후보가 정확히 1개(교집합 유일)."""
        with pytest.raises(ValidationError, match="정확히 1개"):
            _entry(match_method=MatchMethod.STANDARD_CODE)

    def test_standard_code_name_requires_multi_candidate(self) -> None:
        """standard_code+name 행은 후보 ≥2(이름 랭킹 개입 케이스만)."""
        with pytest.raises(ValidationError, match="≥2"):
            _entry(
                atom_codes=["9수02-01-1"],
                primary_atom_code="9수02-01-1",
                match_method=MatchMethod.STANDARD_CODE_NAME,
            )

    def test_confidence_range(self) -> None:
        """confidence는 0~1 범위."""
        with pytest.raises(ValidationError):
            _entry(confidence=1.5)

    def test_extra_field_forbidden(self) -> None:
        """extra='forbid' — 미지 필드 거부(스키마 드리프트 방지)."""
        with pytest.raises(ValidationError):
            _entry(renderer="manim")
