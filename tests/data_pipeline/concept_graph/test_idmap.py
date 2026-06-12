"""idmap 단위테스트 — src_id → UC 결정론·충돌0·override·규약 통과.

정본: docs/data/concept_graph.md §2.4(UC 규약)·§3.5(ID 안정성).
"""

from __future__ import annotations

import pytest

from data_pipeline.concept_graph.idmap import (
    build_concept_uc,
    build_id_map,
    slugify_src_id,
    to_csv_rows,
)
from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN


class TestSlugify:
    @pytest.mark.parametrize(
        "src_id, expected",
        [
            ("N1", "n1"),
            ("HK01", "hk01"),
            ("H:12대수01-01", "h-12-01-01"),  # 콜론→하이픈, 한글 제거
            ("J0105", "j0105"),
            ("AD1", "ad1"),
        ],
    )
    def test_slugify_known_shapes(self, src_id: str, expected: str) -> None:
        assert slugify_src_id(src_id) == expected

    def test_slugify_collapses_and_trims_dashes(self) -> None:
        """연속·양끝 하이픈 정리."""
        assert slugify_src_id("--A__B--") == "a-b"

    def test_slugify_raises_on_no_alnum(self) -> None:
        """영숫자가 하나도 없으면 slug 불가 → ValueError."""
        with pytest.raises(ValueError):
            slugify_src_id("한글:::")


class TestBuildConceptUc:
    def test_uc_from_standard_code(self) -> None:
        """standard_code 기반 도메인/토픽 + src_id slug."""
        uc = build_concept_uc("HK01", ["[10공수1-01-01]"])
        assert uc == "UC.common1.a01.hk01"
        assert CONCEPT_ID_PATTERN.match(uc)

    def test_uc_fallback_without_codes(self) -> None:
        """standard_codes 비면 폴백 도메인/토픽(UC.x.misc.<slug>)."""
        uc = build_concept_uc("Z9", [])
        assert uc == "UC.x.misc.z9"
        assert CONCEPT_ID_PATTERN.match(uc)

    def test_uc_fallback_on_unparseable_code(self) -> None:
        """파싱 불가 코드만 있으면 폴백."""
        uc = build_concept_uc("Z9", ["not-a-code"])
        assert uc == "UC.x.misc.z9"

    def test_uc_uses_first_parseable_code(self) -> None:
        """다중 코드 중 첫 파싱 성공 코드로 도메인/토픽 결정(결정론적)."""
        uc = build_concept_uc("W1", ["bad", "[4수03-20]", "[6수01-01]"])
        # [4수03-20] → math / a03
        assert uc == "UC.math.a03.w1"

    @pytest.mark.parametrize("src_id", ["N1", "HK01", "H:12대수01-01", "J0201"])
    def test_uc_is_deterministic(self, src_id: str) -> None:
        """같은 입력 → 같은 UC(재실행 멱등)."""
        assert build_concept_uc(src_id, ["[9수01-01]"]) == build_concept_uc(src_id, ["[9수01-01]"])


class TestBuildIdMap:
    def test_real_data_no_collision_403_unique(
        self, concept_records: list[dict[str, object]]
    ) -> None:
        """실데이터 403 개념 → 403 유일 UC(충돌 0)."""
        id_map = build_id_map(concept_records)
        assert len(id_map) == 403
        assert len(set(id_map.values())) == 403  # 충돌 0

    def test_real_data_all_pass_pattern(self, concept_records: list[dict[str, object]]) -> None:
        """모든 생성 UC가 CONCEPT_ID_PATTERN 통과."""
        id_map = build_id_map(concept_records)
        bad = [uc for uc in id_map.values() if not CONCEPT_ID_PATTERN.match(uc)]
        assert bad == []

    def test_deterministic_across_runs(self, concept_records: list[dict[str, object]]) -> None:
        """두 번 빌드해도 동일 매핑."""
        assert build_id_map(concept_records) == build_id_map(concept_records)

    def test_shared_standard_code_still_unique(self) -> None:
        """같은 성취기준을 공유하는 개념들(F7·F8·F9 → [6수01-06])도 UC 유일."""
        records = [
            {"src_id": "F7", "standard_codes": ["[6수01-06]"]},
            {"src_id": "F8", "standard_codes": ["[6수01-06]"]},
            {"src_id": "F9", "standard_codes": ["[6수01-06]"]},
        ]
        id_map = build_id_map(records)
        assert len(set(id_map.values())) == 3  # 충돌 없음(slug=src_id)

    def test_override_applied(self) -> None:
        """override 주입 시 그 src_id는 결정론 규칙 대신 override UC."""
        records = [{"src_id": "N1", "standard_codes": ["[2수01-01]"]}]
        id_map = build_id_map(records, overrides={"N1": "UC.calc.limit.epsilon-delta"})
        assert id_map["N1"] == "UC.calc.limit.epsilon-delta"

    def test_override_must_pass_pattern(self) -> None:
        """override UC가 규약 위반이면 ValueError."""
        records = [{"src_id": "N1", "standard_codes": ["[2수01-01]"]}]
        with pytest.raises(ValueError):
            build_id_map(records, overrides={"N1": "not-a-uc"})

    def test_override_collision_rejected(self) -> None:
        """서로 다른 src_id를 같은 override UC로 매핑하면 ValueError."""
        records = [
            {"src_id": "N1", "standard_codes": ["[2수01-01]"]},
            {"src_id": "N2", "standard_codes": ["[2수01-02]"]},
        ]
        with pytest.raises(ValueError):
            build_id_map(
                records,
                overrides={"N1": "UC.x.misc.dup", "N2": "UC.x.misc.dup"},
            )

    def test_duplicate_src_id_rejected(self) -> None:
        """src_id 중복은 ValueError."""
        records = [
            {"src_id": "N1", "standard_codes": ["[2수01-01]"]},
            {"src_id": "N1", "standard_codes": ["[2수01-02]"]},
        ]
        with pytest.raises(ValueError):
            build_id_map(records)

    def test_empty_src_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_id_map([{"src_id": "", "standard_codes": []}])

    def test_preserves_insertion_order(self) -> None:
        records = [
            {"src_id": "N3", "standard_codes": ["[2수01-03]"]},
            {"src_id": "N1", "standard_codes": ["[2수01-01]"]},
        ]
        assert list(build_id_map(records).keys()) == ["N3", "N1"]


class TestToCsvRows:
    def test_csv_rows_shape(self) -> None:
        rows = to_csv_rows({"N1": "UC.math.a01.n1", "N2": "UC.math.a01.n2"})
        assert rows == [
            {"src_id": "N1", "concept_id": "UC.math.a01.n1"},
            {"src_id": "N2", "concept_id": "UC.math.a01.n2"},
        ]
