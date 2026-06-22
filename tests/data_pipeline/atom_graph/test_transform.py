"""transform 단위테스트 — 정규화·계층 승격·redaction 분기·엣지/서술형 분리·결정성.

정본: docs/data/atom_graph_v1.md(§3 redaction) + 마이그레이션 플랜 Phase 1.
실데이터 카운트는 코퍼스 산출(test_corpus.py)이 단언하고, 여기서는 합성 행으로 로직을 검증한다.
"""

from __future__ import annotations

import json

from data_pipeline.atom_graph.models import NodeLevel, SchoolLevel
from data_pipeline.atom_graph.transform import (
    normalize_saisiot,
    normalize_standard_code,
    parse_linked_standards,
    transform_atoms,
    transform_dataset,
    transform_edges,
    unit_code_of,
)


class TestNormalizeSaisiot:
    def test_replaces_exact_tokens(self) -> None:
        assert normalize_saisiot("자리값과 경계값") == "자릿값과 경곗값"

    def test_leaves_gray_zone(self) -> None:
        """회색지대(고유값·진리값·실고유값)는 '자리값'/'경계값' 토큰이 없어 무변경."""
        for token in ["고유값", "고윳값", "진리값", "실고유값", "극값", "최댓값"]:
            assert normalize_saisiot(token) == token

    def test_counts_replacements(self) -> None:
        cnt: dict[str, int] = {}
        normalize_saisiot("자리값 자리값 경계값", cnt)
        assert cnt["자리값"] == 2
        assert cnt["경계값"] == 1


class TestNormalizeStandardCode:
    def test_mijeok_1_gets_hyphen(self) -> None:
        assert normalize_standard_code("[12미적Ⅰ01-01]") == "[12미적Ⅰ-01-01]"

    def test_mijeok_2_gets_hyphen(self) -> None:
        assert normalize_standard_code("[12미적Ⅱ03-05]") == "[12미적Ⅱ-03-05]"

    def test_gongsu_unchanged(self) -> None:
        """공수·기수는 이미 하이픈 → 무변경."""
        assert normalize_standard_code("[10공수1-01-01]") == "[10공수1-01-01]"
        assert (
            normalize_standard_code("[12기하01-01]".replace("기하", "기하"))
            == "[12기하01-01]"
        )

    def test_counts_mijeok(self) -> None:
        cnt: dict[str, int] = {}
        normalize_standard_code("[12미적Ⅰ01-01]", cnt)
        normalize_standard_code("[10공수1-01-01]", cnt)
        assert cnt["미적하이픈"] == 1  # 공수는 무변경

    def test_parse_linked_standards_splits_and_normalizes(self) -> None:
        codes = parse_linked_standards("[12미적Ⅰ01-01]; [10공수1-01-01]")
        assert codes == ["[12미적Ⅰ-01-01]", "[10공수1-01-01]"]

    def test_parse_linked_standards_empty_and_none(self) -> None:
        assert parse_linked_standards("") == []
        assert parse_linked_standards("없음") == []
        assert parse_linked_standards(None) == []


class TestUnitCodeOf:
    def test_strips_subunit_suffix(self) -> None:
        assert unit_code_of("초수연-U1-S1") == "초수연-U1"
        assert unit_code_of("공수1-U1-S2") == "공수1-U1"
        assert unit_code_of("CALC1-U1-S1") == "CALC1-U1"

    def test_no_suffix_returns_original(self) -> None:
        assert unit_code_of("ODE-P07") == "ODE-P07"


class TestTransformAtoms:
    def test_promotes_hierarchy_nodes(self, atom_row: dict[str, object]) -> None:
        """원자 + 소단원 + 단원 노드 승격, parent 체인 정렬."""
        concepts, skipped = transform_atoms([atom_row])
        assert skipped == []
        by_level = {c.level: c for c in concepts}
        atom = by_level[NodeLevel.ATOM.value]
        subunit = by_level[NodeLevel.SUBUNIT.value]
        unit = by_level[NodeLevel.UNIT.value]
        assert atom.parent_code == "초수연-U1-S1"
        assert subunit.code == "초수연-U1-S1"
        assert subunit.parent_code == "초수연-U1"
        assert unit.code == "초수연-U1"
        assert unit.parent_code is None

    def test_dedup_hierarchy(self, make_atom_row) -> None:  # type: ignore[no-untyped-def]
        """같은 소단원코드의 두 원자 → 소단원/단원 노드 각 1개(dedup)."""
        r1 = make_atom_row(원자ID="2수01-01-1")
        r2 = make_atom_row(원자ID="2수01-01-2", 원자명="기수 원리")
        concepts, _ = transform_atoms([r1, r2])
        atoms = [c for c in concepts if c.level == NodeLevel.ATOM.value]
        subunits = [c for c in concepts if c.level == NodeLevel.SUBUNIT.value]
        units = [c for c in concepts if c.level == NodeLevel.UNIT.value]
        assert len(atoms) == 2
        assert len(subunits) == 1
        assert len(units) == 1

    def test_school_level_normalized(self, atom_row: dict[str, object]) -> None:
        c = transform_atoms([atom_row])[0][0]
        assert c.school_level == SchoolLevel.ELEMENTARY.value  # 초등학교 → 초등

    def test_redacts_k12_core_proposition(self, atom_row: dict[str, object]) -> None:
        """K-12 핵심명제(=NCIC 본문)는 산출에 없고 마커만, core_proposition=None."""
        c = transform_atoms([atom_row])[0][0]
        assert c.core_proposition is None
        assert "핵심명제/성취기준내용" in c.redacted_fields

    def test_preserves_university_core_proposition(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        """대학 핵심명제는 자체작성 → core_proposition 보존(redact 아님)."""
        r = make_atom_row(학교급="대학교", 연결성취기준="")
        # '핵심명제/성취기준내용'은 식별자가 아닌 문자열 키라 dict로 직접 갱신.
        r["핵심명제/성취기준내용"] = "자체작성 대학 명제"
        c = transform_atoms([r])[0][0]
        assert c.school_level == SchoolLevel.UNIVERSITY.value
        assert c.core_proposition == "자체작성 대학 명제"
        assert c.redacted_fields == []
        assert c.standard_codes == []  # 대학 연결성취기준 없음

    def test_saisiot_applied_to_text_fields(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        """본문 텍스트 필드(전이 등)에 사이시옷 정규화 적용."""
        r = make_atom_row(**{"④전이": "자리값과 경계값을 이해"})
        c = transform_atoms([r])[0][0]
        assert c.transfer == "자릿값과 경곗값을 이해"

    def test_mijeok_normalized_in_standard_codes(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        r = make_atom_row(학교급="고등학교", 연결성취기준="[12미적Ⅰ01-01]")
        c = transform_atoms([r])[0][0]
        assert c.standard_codes == ["[12미적Ⅰ-01-01]"]

    def test_atomicity_dict(self, atom_row: dict[str, object]) -> None:
        c = transform_atoms([atom_row])[0][0]
        assert c.atomicity == {"a": "예", "b": "예", "c": "예", "d": "예"}

    def test_skips_row_without_atom_id(self) -> None:
        concepts, skipped = transform_atoms([{"원자명": "x"}])
        assert concepts == []
        assert len(skipped) == 1

    def test_skips_unknown_school_level(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        r = make_atom_row(학교급="유치원")
        concepts, skipped = transform_atoms([r])
        assert concepts == []
        assert len(skipped) == 1


class TestTransformEdges:
    def _edge_row(self, **over: object) -> dict[str, object]:
        base: dict[str, object] = {
            "출처": "원본",
            "관계유형": "원본",
            "from(선수)": "2수01-01-1",
            "from_원자명": "일대일 대응으로 세기",
            "from_학교급": "초등학교",
            "from_유형": "원자ID",
            "관계": "선수",
            "to(후행)": "2수01-01-2",
            "to_원자명": "기수 원리",
            "to_학교급": "초등학교",
            "학교급연계": "",
        }
        base.update(over)
        return base

    def test_atom_id_edge_mapped(self) -> None:
        edges, narrative, skipped = transform_edges([self._edge_row()])
        assert skipped == []
        assert narrative == []
        e = edges[0]
        assert e.from_code == "2수01-01-1"
        assert e.to_code == "2수01-01-2"
        assert e.relation_subtype == "원본"
        assert e.school_link is False

    def test_school_link_y(self) -> None:
        edges, _, _ = transform_edges([self._edge_row(학교급연계="Y")])
        assert edges[0].school_link is True

    def test_narrative_passthrough(self) -> None:
        """from_유형=서술형 → 엣지 아님·narrative_edges_raw 보존."""
        row = self._edge_row(**{"from_유형": "서술형", "from(선수)": "좌표평면"})
        edges, narrative, skipped = transform_edges([row])
        assert edges == []
        assert skipped == []
        assert len(narrative) == 1
        assert narrative[0]["from(선수)"] == "좌표평면"

    def test_skips_unknown_from_kind(self) -> None:
        edges, narrative, skipped = transform_edges(
            [self._edge_row(**{"from_유형": "기타"})]
        )
        assert edges == []
        assert narrative == []
        assert len(skipped) == 1


class TestTransformDataset:
    def test_provenance_counts(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        atom = make_atom_row(학교급="고등학교", 연결성취기준="[12미적Ⅰ01-01]")
        atom["④전이"] = "자리값"
        result = transform_dataset(atom_rows=[atom], edge_rows=[])
        assert result.provenance["미적하이픈"] == 1
        assert result.provenance["미적하이픈_distinct"] == 1
        assert result.provenance["자리값"] == 1
        assert result.provenance["redacted_핵심명제"] == 1

    def test_determinism_byte_identical(
        self, make_atom_row
    ) -> None:  # type: ignore[no-untyped-def]
        """동일 입력 2회 transform → dump byte 동일(결정성)."""
        atoms = [
            make_atom_row(원자ID="2수01-01-1"),
            make_atom_row(원자ID="2수01-01-2", 원자명="기수 원리"),
        ]
        edge = {
            "from(선수)": "2수01-01-1",
            "to(후행)": "2수01-01-2",
            "from_유형": "원자ID",
            "관계유형": "소단원내",
        }

        def _dump(r: object) -> str:
            res = r  # type: ignore[assignment]
            return json.dumps(
                {
                    "c": [c.model_dump() for c in res.concepts],  # type: ignore[attr-defined]
                    "e": [e.model_dump() for e in res.edges],  # type: ignore[attr-defined]
                    "n": res.narrative_edges_raw,  # type: ignore[attr-defined]
                    "p": res.provenance,  # type: ignore[attr-defined]
                },
                ensure_ascii=False,
            )

        r1 = transform_dataset(atom_rows=atoms, edge_rows=[edge])
        r2 = transform_dataset(atom_rows=atoms, edge_rows=[edge])
        assert _dump(r1) == _dump(r2)
