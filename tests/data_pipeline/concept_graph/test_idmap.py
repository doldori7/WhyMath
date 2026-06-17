"""idmap 단위테스트 — src_id → 새 concept_id(`{TRACK}-{AREA}-{NNN}`) 결정론·충돌0·별칭·규약.

정본: docs/data/concept_graph.md §2.4(ID 규약)·§3.5(ID 안정성) +
docs/data/concept_graph_dataset_v1.md §5b.1(매핑) + P2a 결정 로그(MEMORY.md).
"""

from __future__ import annotations

import pytest

from data_pipeline.concept_graph.idmap import (
    _TOPIC_AREA_MAP,
    build_alias_map,
    build_id_map,
    strip_level_prefix,
    to_csv_rows,
    track_for_record,
)
from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN, LEGACY_UC_PATTERN

# 코퍼스 37개 category 전수(접두사 포함 원본) — area_map_total 검증·합성 픽스처 공용.
_ALL_CATEGORIES: tuple[str, ...] = (
    "[고]경제 수학",
    "[고]기하",
    "[고]대수",
    "[고]미적분",
    "[고]수학과 문화",
    "[고]수학과제 탐구",
    "[고]실용 통계",
    "[고]인공지능 수학",
    "[고]직무 수학",
    "[고]확률·통계",
    "[공통]경우의 수",
    "[공통]도형의 방정식",
    "[공통]식·방정식·부등식",
    "[공통]집합과 명제",
    "[공통]함수",
    "[공통]행렬",
    "[중]기하",
    "[중]문자·식·방정식",
    "[중]수와 연산",
    "[중]자료와 가능성",
    "가능성",
    "곱셈",
    "규칙·대응",
    "나눗셈",
    "덧셈·뺄셈",
    "도형(평면·입체)",
    "도형의 요소",
    "둘레·넓이·부피",
    "분수",
    "비와 비율",
    "소수",
    "수의 성질·어림",
    "자료·그래프",
    "자연수·자릿값",
    "측정(단위)",
    "합동·대칭·이동",
)


class TestStripLevelPrefix:
    @pytest.mark.parametrize(
        "category, expected",
        [
            ("[고]미적분", "미적분"),
            ("[중]기하", "기하"),
            ("[공통]함수", "함수"),
            ("분수", "분수"),  # 접두사 없음(초등)
            ("자연수·자릿값", "자연수·자릿값"),
        ],
    )
    def test_strips_known_prefixes(self, category: str, expected: str) -> None:
        assert strip_level_prefix(category) == expected


class TestTopicAreaMap:
    def test_every_category_maps(self) -> None:
        """37개 category 전수가 AREA로 매핑된다(어간 기준·미매핑 0)."""
        stems = {strip_level_prefix(c) for c in _ALL_CATEGORIES}
        unmapped = [s for s in stems if s not in _TOPIC_AREA_MAP]
        assert unmapped == []

    def test_all_area_codes_pass_token_shape(self) -> None:
        """모든 AREA 코드가 2~8 대문자/숫자(concept_id AREA 슬롯 규약)."""
        import re

        token = re.compile(r"^[A-Z0-9]{2,8}$")
        bad = {area for area in _TOPIC_AREA_MAP.values() if not token.match(area)}
        assert bad == set()

    def test_kiki_specified_examples(self) -> None:
        """Kiki가 못박은 대표 매핑 고정(taxonomy 회귀 가드)."""
        assert _TOPIC_AREA_MAP["미적분"] == "CALC"
        assert _TOPIC_AREA_MAP["기하"] == "GEO"
        assert _TOPIC_AREA_MAP["분수"] == "FRAC"
        assert _TOPIC_AREA_MAP["확률·통계"] == "PROB"
        assert _TOPIC_AREA_MAP["함수"] == "FUN"
        assert _TOPIC_AREA_MAP["대수"] == "ALG"
        assert _TOPIC_AREA_MAP["식·방정식·부등식"] == "EQN"
        assert _TOPIC_AREA_MAP["도형의 방정식"] == "COORD"
        assert _TOPIC_AREA_MAP["집합과 명제"] == "LOGIC"
        assert _TOPIC_AREA_MAP["자연수·자릿값"] == "NPLACE"

    def test_shared_stem_shares_area(self) -> None:
        """레벨만 다른 어간([중]기하·[고]기하)은 같은 AREA(TRACK이 구분)."""
        assert strip_level_prefix("[중]기하") == strip_level_prefix("[고]기하")
        assert _TOPIC_AREA_MAP[strip_level_prefix("[중]기하")] == "GEO"


class TestTrackDerivation:
    @pytest.mark.parametrize(
        "code, expected",
        [
            ("[2수01-01]", "ELEM"),
            ("[4수03-20]", "ELEM"),
            ("[6수01-06]", "ELEM"),
            ("[9수01-01]", "MID"),
            ("[10공수1-01-01]", "HIGH"),
            ("[12미적Ⅰ01-01]", "HIGH"),
        ],
    )
    def test_track_from_first_standard_code(self, code: str, expected: str) -> None:
        """첫 standard_code 학년대수 → TRACK(2/4/6=ELEM·9=MID·10/12=HIGH)."""
        assert track_for_record([code], None) == expected

    def test_track_uses_first_parseable_code(self) -> None:
        """파싱 불가 코드는 건너뛰고 첫 파싱 성공 코드로 결정."""
        assert track_for_record(["bad", "[9수01-01]"], None) == "MID"

    def test_track_tier_fallback_when_no_codes(self) -> None:
        """standard_codes 없으면 difficulty_tier 밴드 폴백(0~8 ELEM·9~16 MID·17~24 HIGH)."""
        assert track_for_record([], 3) == "ELEM"
        assert track_for_record([], 12) == "MID"
        assert track_for_record([], 20) == "HIGH"

    def test_track_last_resort_when_no_codes_no_tier(self) -> None:
        """코드도 tier도 없으면 최종 폴백 MID(중립)."""
        assert track_for_record([], None) == "MID"


class TestBuildIdMap:
    def test_real_data_no_collision_403_unique(
        self, concept_records: list[dict[str, object]]
    ) -> None:
        """실데이터 437 개념 → 437 유일 새 ID(충돌 0)."""
        id_map = build_id_map(concept_records)
        assert len(id_map) == 437
        assert len(set(id_map.values())) == 437  # 충돌 0

    def test_real_data_all_pass_pattern(
        self, concept_records: list[dict[str, object]]
    ) -> None:
        """모든 생성 ID가 CONCEPT_ID_PATTERN(`{TRACK}-{AREA}-{NNN}`) 통과."""
        id_map = build_id_map(concept_records)
        bad = [cid for cid in id_map.values() if not CONCEPT_ID_PATTERN.match(cid)]
        assert bad == []

    def test_deterministic_across_runs(
        self, concept_records: list[dict[str, object]]
    ) -> None:
        """두 번 빌드해도 동일 매핑(멱등 — NNN 재현)."""
        assert build_id_map(concept_records) == build_id_map(concept_records)

    def test_nnn_idempotent_and_sorted(self) -> None:
        """(TRACK, AREA) 그룹 안 (tier, src_id) 정렬 → 001·002… 결정론적."""
        records = [
            {
                "src_id": "B",
                "category": "분수",
                "difficulty_tier": "5",
                "standard_codes": ["[6수01-01]"],
            },
            {
                "src_id": "A",
                "category": "분수",
                "difficulty_tier": "5",
                "standard_codes": ["[6수01-02]"],
            },
            {
                "src_id": "C",
                "category": "분수",
                "difficulty_tier": "3",
                "standard_codes": ["[6수01-03]"],
            },
        ]
        id_map = build_id_map(records)
        # tier 3(C) 먼저 → 001, 그 다음 tier 5는 src_id 사전순(A<B) → A=002·B=003
        assert id_map["C"] == "ELEM-FRAC-001"
        assert id_map["A"] == "ELEM-FRAC-002"
        assert id_map["B"] == "ELEM-FRAC-003"
        # 입력 순서를 바꿔도 동일 번호(정렬 키가 tier·src_id라 멱등)
        assert build_id_map(list(reversed(records))) == id_map

    def test_separate_groups_restart_numbering(self) -> None:
        """(TRACK, AREA)가 다르면 NNN이 각자 001부터."""
        records = [
            {
                "src_id": "F1",
                "category": "분수",
                "difficulty_tier": "2",
                "standard_codes": ["[6수01-01]"],
            },
            {
                "src_id": "G1",
                "category": "[중]기하",
                "difficulty_tier": "10",
                "standard_codes": ["[9수04-01]"],
            },
        ]
        id_map = build_id_map(records)
        assert id_map["F1"] == "ELEM-FRAC-001"
        assert id_map["G1"] == "MID-GEO-001"

    def test_shared_standard_code_still_unique(self) -> None:
        """같은 성취기준을 공유하는 개념들(F7·F8·F9 → [6수01-06])도 ID 유일(NNN이 분리)."""
        records = [
            {
                "src_id": "F7",
                "category": "분수",
                "difficulty_tier": "5",
                "standard_codes": ["[6수01-06]"],
            },
            {
                "src_id": "F8",
                "category": "분수",
                "difficulty_tier": "6",
                "standard_codes": ["[6수01-06]"],
            },
            {
                "src_id": "F9",
                "category": "분수",
                "difficulty_tier": "7",
                "standard_codes": ["[6수01-06]"],
            },
        ]
        id_map = build_id_map(records)
        assert set(id_map.values()) == {
            "ELEM-FRAC-001",
            "ELEM-FRAC-002",
            "ELEM-FRAC-003",
        }

    def test_track_disambiguates_shared_area(self) -> None:
        """같은 AREA(기하→GEO)라도 TRACK이 다르면 ID가 충돌하지 않는다."""
        records = [
            {
                "src_id": "MG",
                "category": "[중]기하",
                "difficulty_tier": "10",
                "standard_codes": ["[9수04-01]"],
            },
            {
                "src_id": "HG",
                "category": "[고]기하",
                "difficulty_tier": "20",
                "standard_codes": ["[12기하01-01]"],
            },
        ]
        id_map = build_id_map(records)
        assert id_map["MG"] == "MID-GEO-001"
        assert id_map["HG"] == "HIGH-GEO-001"

    def test_tier_fallback_for_codeless_record(self) -> None:
        """standard_codes 없으면 tier 밴드로 TRACK 결정(폴백 경로)."""
        records = [
            {
                "src_id": "X1",
                "category": "분수",
                "difficulty_tier": "20",
                "standard_codes": [],
            }
        ]
        id_map = build_id_map(records)
        assert id_map["X1"] == "HIGH-FRAC-001"

    def test_unmapped_category_raises_keyerror(self) -> None:
        """미수록 category는 침묵 폴백 없이 KeyError(taxonomy 누수 가드)."""
        records = [
            {
                "src_id": "Z1",
                "category": "외계수학",
                "difficulty_tier": "5",
                "standard_codes": ["[6수01-01]"],
            }
        ]
        with pytest.raises(KeyError):
            build_id_map(records)

    def test_override_applied(self) -> None:
        """override 주입 시 그 src_id는 자동 번호 대신 override concept_id."""
        records = [
            {
                "src_id": "N1",
                "category": "자연수·자릿값",
                "standard_codes": ["[2수01-01]"],
            }
        ]
        id_map = build_id_map(records, overrides={"N1": "ELEM-NPLACE-099"})
        assert id_map["N1"] == "ELEM-NPLACE-099"

    def test_override_must_pass_pattern(self) -> None:
        """override가 새 규약 위반이면 ValueError."""
        records = [
            {"src_id": "N1", "category": "분수", "standard_codes": ["[6수01-01]"]}
        ]
        with pytest.raises(ValueError):
            build_id_map(records, overrides={"N1": "UC.calc.limit.def"})  # 옛 형식 거부

    def test_override_collision_rejected(self) -> None:
        """서로 다른 src_id를 같은 override ID로 매핑하면 ValueError."""
        records = [
            {"src_id": "N1", "category": "분수", "standard_codes": ["[6수01-01]"]},
            {"src_id": "N2", "category": "분수", "standard_codes": ["[6수01-02]"]},
        ]
        with pytest.raises(ValueError):
            build_id_map(
                records, overrides={"N1": "ELEM-FRAC-050", "N2": "ELEM-FRAC-050"}
            )

    def test_duplicate_src_id_rejected(self) -> None:
        """src_id 중복은 ValueError."""
        records = [
            {"src_id": "N1", "category": "분수", "standard_codes": ["[6수01-01]"]},
            {"src_id": "N1", "category": "분수", "standard_codes": ["[6수01-02]"]},
        ]
        with pytest.raises(ValueError):
            build_id_map(records)

    def test_empty_src_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_id_map([{"src_id": "", "category": "분수", "standard_codes": []}])

    def test_preserves_insertion_order(self) -> None:
        records = [
            {"src_id": "N3", "category": "분수", "standard_codes": ["[6수01-03]"]},
            {"src_id": "N1", "category": "분수", "standard_codes": ["[6수01-01]"]},
        ]
        assert list(build_id_map(records).keys()) == ["N3", "N1"]


class TestBuildAliasMap:
    def test_aliases_contain_legacy_uc_and_src_id(self) -> None:
        """별칭 = [옛 UC, src_id]. 옛 UC는 LEGACY_UC_PATTERN 통과·src_id 보존."""
        records = [
            {
                "src_id": "HK01",
                "category": "[공통]식·방정식·부등식",
                "standard_codes": ["[10공수1-01-01]"],
            }
        ]
        alias_map = build_alias_map(records)
        aliases = alias_map["HK01"]
        assert aliases == ["UC.common1.a01.hk01", "HK01"]
        assert LEGACY_UC_PATTERN.match(aliases[0])
        assert "HK01" in aliases

    def test_legacy_fallback_uc_for_codeless(self) -> None:
        """standard_codes 없으면 옛 폴백 UC(UC.x.misc.<slug>) 보존."""
        records = [{"src_id": "Z9", "category": "분수", "standard_codes": []}]
        alias_map = build_alias_map(records)
        assert alias_map["Z9"] == ["UC.x.misc.z9", "Z9"]

    def test_real_data_every_concept_has_aliases(
        self, concept_records: list[dict[str, object]]
    ) -> None:
        """실데이터 437건 모두 별칭에 옛 UC·src_id 보존."""
        alias_map = build_alias_map(concept_records)
        assert len(alias_map) == 437
        for src_id, aliases in alias_map.items():
            assert src_id in aliases
            assert any(LEGACY_UC_PATTERN.match(a) for a in aliases)


class TestToCsvRows:
    def test_csv_rows_shape(self) -> None:
        rows = to_csv_rows({"N1": "ELEM-NPLACE-001", "N2": "ELEM-NPLACE-002"})
        assert rows == [
            {"src_id": "N1", "concept_id": "ELEM-NPLACE-001"},
            {"src_id": "N2", "concept_id": "ELEM-NPLACE-002"},
        ]
