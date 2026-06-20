"""오개념 느슨참조 해소 *단위테스트* — 해소 슬라이스 (hermetic·PG 불요).

순수 코어(`_split_standard_codes`·`_assemble_links`)·결과 모델(frozen)·집계(`summarize`)를
DB 없이 못 박는다. ORM `MisconceptionCatalog` 인스턴스를 직접 만들어 *페이크 맵*을
`_assemble_links`에 넘긴다(DB I/O 0). 실 라운드트립(`resolve_many`·2 IN쿼리)은 통합테스트
(`test_misconception_resolve_integration.py`)로 미룬다.

  ① `_split_standard_codes` — 단일·다중`;`·None·공백·후행`;`
  ② `_assemble_links` — concept 매칭/orphan/None 구분·standard 단일/다중revision 정렬/부분 다중코드
  ③ StandardRef 정렬 결정성 — 셔플 입력 → norm_id 정렬 출력
  ④ frozen 불변 — 결과 모델 mutate 차단(ValidationError)
  ⑤ `summarize` — 집계(total·해소·orphan)
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog
from whymath_backend.l1.misconception.resolve import (
    ConceptRef,
    ResolvedMisconceptionLinks,
    StandardRef,
    _assemble_links,
    _split_standard_codes,
    summarize,
)


def _mis(
    mis_id: str,
    *,
    concept_src_id: str | None = None,
    standard_code: str | None = None,
) -> MisconceptionCatalog:
    """페이크 맵 단위테스트용 ORM 인스턴스(DB 미부착 — 컬럼 속성만 사용)."""
    return MisconceptionCatalog(
        mis_id=mis_id,
        concept_src_id=concept_src_id,
        standard_code=standard_code,
    )


def _concept_ref(source_id: str) -> ConceptRef:
    return ConceptRef(concept_id=uuid.uuid4(), code=f"CODE-{source_id}")


def _std_ref(norm_id: str, code: str, revision: str) -> StandardRef:
    return StandardRef(norm_id=norm_id, official_code=code, curriculum_revision=revision)


# ──────────────────────────────────────────────────────────────────────────
# ① _split_standard_codes — 단일·다중·None·공백·후행;
# ──────────────────────────────────────────────────────────────────────────
class TestSplitStandardCodes:
    def test_single_code(self) -> None:
        assert _split_standard_codes("[2수01-01]") == ["[2수01-01]"]

    def test_multi_code_semicolon(self) -> None:
        raw = "[2수03-08]; [2수03-09]; [4수03-13]"
        assert _split_standard_codes(raw) == ["[2수03-08]", "[2수03-09]", "[4수03-13]"]

    def test_none_is_empty(self) -> None:
        assert _split_standard_codes(None) == []

    def test_blank_and_whitespace(self) -> None:
        assert _split_standard_codes("   ") == []
        assert _split_standard_codes("") == []

    def test_trailing_semicolon(self) -> None:
        assert _split_standard_codes("[2수01-01];") == ["[2수01-01]"]
        assert _split_standard_codes("[2수01-01]; ; [2수01-02]") == [
            "[2수01-01]",
            "[2수01-02]",
        ]


# ──────────────────────────────────────────────────────────────────────────
# ② _assemble_links — concept 매칭/orphan/None·standard 단일/다중revision/부분
# ──────────────────────────────────────────────────────────────────────────
class TestAssembleConcept:
    def test_concept_matched(self) -> None:
        ref = _concept_ref("N1")
        links = _assemble_links(_mis("M1", concept_src_id="N1"), {"N1": ref}, {})
        assert links.concept == ref
        assert links.concept_resolved is True
        assert links.concept_orphan is False

    def test_concept_orphan_present_but_missing(self) -> None:
        # concept_src_id가 있는데 map miss → orphan(조용한 누락 아님).
        links = _assemble_links(_mis("M1", concept_src_id="ZZ9"), {}, {})
        assert links.concept is None
        assert links.concept_resolved is False
        assert links.concept_orphan is True

    def test_concept_none_is_not_orphan(self) -> None:
        # concept_src_id None → "참조 없음" ≠ "미해소 참조"(orphan 아님).
        links = _assemble_links(_mis("M1", concept_src_id=None), {}, {})
        assert links.concept is None
        assert links.concept_resolved is False
        assert links.concept_orphan is False


class TestAssembleStandard:
    def test_single_code_resolved(self) -> None:
        std = _std_ref("2022_n_01", "[2수01-01]", "2022 개정")
        links = _assemble_links(
            _mis("M1", standard_code="[2수01-01]"),
            {},
            {"[2수01-01]": [std]},
        )
        assert len(links.standard_codes) == 1
        assert links.standard_codes[0].code == "[2수01-01]"
        assert links.standard_codes[0].standards == (std,)
        assert links.standard_resolved is True
        assert links.standard_orphan_codes == ()

    def test_multi_revision_both_returned(self) -> None:
        # 같은 official_code가 2015·2022 → 둘 다 반환(revision 강제 선택 안 함)·orphan 아님.
        a = _std_ref("2015_n_01", "[2수01-01]", "2015 개정")
        b = _std_ref("2022_n_01", "[2수01-01]", "2022 개정")
        links = _assemble_links(
            _mis("M1", standard_code="[2수01-01]"),
            {},
            {"[2수01-01]": [a, b]},
        )
        assert len(links.standard_codes[0].standards) == 2
        assert links.standard_resolved is True
        assert links.standard_orphan_codes == ()

    def test_partial_multi_code_orphan(self) -> None:
        # 다중코드 행 — 한 코드만 해소·나머지는 orphan(코드별 정직 집계).
        std = _std_ref("2022_n_08", "[2수03-08]", "2022 개정")
        links = _assemble_links(
            _mis("M1", standard_code="[2수03-08]; [2수03-09]"),
            {},
            {"[2수03-08]": [std]},
        )
        assert len(links.standard_codes) == 2
        assert links.standard_orphan_codes == ("[2수03-09]",)
        # 부분 해소 → 전체 standard_resolved는 False(orphan 코드 존재).
        assert links.standard_resolved is False

    def test_no_standard_code_not_resolved(self) -> None:
        links = _assemble_links(_mis("M1", standard_code=None), {}, {})
        assert links.standard_codes == ()
        assert links.standard_resolved is False
        assert links.standard_orphan_codes == ()


# ──────────────────────────────────────────────────────────────────────────
# ③ StandardRef 정렬 결정성 — 셔플 입력 → norm_id 정렬(직접 _fetch는 통합테스트)
# ──────────────────────────────────────────────────────────────────────────
class TestSortDeterminism:
    def test_standards_sorted_by_norm_id(self) -> None:
        # _fetch_standard_map이 norm_id 정렬을 보장하므로, 정렬된 맵을 _assemble에 넣으면
        # 출력도 정렬 순서를 보존한다(셔플 입력은 맵 빌더가 정렬). 여기선 정렬 후 동일성 단언.
        refs = [
            _std_ref("2022_n_01", "[c]", "2022 개정"),
            _std_ref("2015_n_01", "[c]", "2015 개정"),
        ]
        ordered = sorted(refs, key=lambda r: r.norm_id)
        links = _assemble_links(_mis("M1", standard_code="[c]"), {}, {"[c]": ordered})
        norm_ids = [s.norm_id for s in links.standard_codes[0].standards]
        assert norm_ids == sorted(norm_ids)
        assert norm_ids == ["2015_n_01", "2022_n_01"]


# ──────────────────────────────────────────────────────────────────────────
# ④ frozen 불변 — 결과 모델 mutate 차단
# ──────────────────────────────────────────────────────────────────────────
class TestFrozen:
    def test_resolved_links_is_frozen(self) -> None:
        links = _assemble_links(_mis("M1"), {}, {})
        with pytest.raises(ValidationError):
            links.mis_id = "M2"  # type: ignore[misc]

    def test_concept_ref_is_frozen(self) -> None:
        ref = _concept_ref("N1")
        with pytest.raises(ValidationError):
            ref.code = "X"  # type: ignore[misc]

    def test_standard_ref_is_frozen(self) -> None:
        ref = _std_ref("2022_n_01", "[c]", "2022 개정")
        with pytest.raises(ValidationError):
            ref.norm_id = "Y"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────
# ⑤ summarize — 집계(total·해소·orphan)
# ──────────────────────────────────────────────────────────────────────────
class TestSummarize:
    def test_aggregates_counts(self) -> None:
        std = _std_ref("2022_n_01", "[a]", "2022 개정")
        results: list[ResolvedMisconceptionLinks] = [
            # 둘 다 해소.
            _assemble_links(
                _mis("M1", concept_src_id="N1", standard_code="[a]"),
                {"N1": _concept_ref("N1")},
                {"[a]": [std]},
            ),
            # concept orphan·standard orphan(코드 1).
            _assemble_links(
                _mis("M2", concept_src_id="ZZ", standard_code="[b]"),
                {},
                {},
            ),
            # 참조 없음(orphan 아님).
            _assemble_links(_mis("M3"), {}, {}),
        ]
        summary = summarize(results)
        assert summary["total"] == 3
        assert summary["concept_resolved_n"] == 1
        assert summary["standard_resolved_n"] == 1
        assert summary["concept_orphan_n"] == 1
        assert summary["standard_orphan_code_n"] == 1

    def test_empty_results(self) -> None:
        summary = summarize([])
        assert summary == {
            "total": 0,
            "concept_resolved_n": 0,
            "standard_resolved_n": 0,
            "concept_orphan_n": 0,
            "standard_orphan_code_n": 0,
        }
