"""atom_graph CLI load 명령 단위테스트 — graph.json → Neo4j 적재(가드·헬퍼). 라이브 Neo4j 불요.

별도 파일인 이유: 형제 test_main_cli.py는 모듈 상단 `importorskip("openpyxl")`로 xlsx 미설치
CI(data-pipeline 기본 잡)에서 *전체* skip된다. load 명령은 openpyxl 불요라, 이 파일은 importorskip
없이 두어 기본 잡에서도 돌게 한다(load 명령 커버리지 확보). 실 적재 왕복은
test_load_neo4j_integration.py(통합·기본 SKIP)가 검증한다.
"""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path

import pytest
from typer.testing import CliRunner

from data_pipeline.atom_graph.__main__ import _graph_json_to_result, app

runner = CliRunner()


def _graph_json(path: Path, *, with_edge: bool = False) -> Path:
    """transform-v1 산출과 동형의 최소 graph.json."""
    concepts = [
        {
            "code": "2수01-01-1",
            "name": "일대일 대응으로 세기",
            "level": "세부개념",
            "school_level": "초등",
            "standard_codes": ["[2수01-01]"],
        },
        {
            "code": "2수01-01-2",
            "name": "기수 원리",
            "level": "세부개념",
            "school_level": "초등",
            "standard_codes": ["[2수01-01]"],
        },
    ]
    edges = (
        [
            {
                "from_code": "2수01-01-1",
                "to_code": "2수01-01-2",
                "relation": "prerequisite",
                "relation_subtype": "원본",
                "school_link": False,
                "strength": 0.8,
                "evidence": "원자 백본 v1",
            }
        ]
        if with_edge
        else []
    )
    path.write_text(
        json.dumps(
            {
                "source_citation": "x",
                "concepts": concepts,
                "edges": edges,
                "narrative_edges_raw": [{"from": "좌표평면", "to": "기수 원리"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


class TestHelp:
    def test_help_lists_load_and_transform(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        out = result.stdout.lower()
        assert "load" in out
        assert "transform-v1" in out


class TestGraphJsonRoundtrip:
    def test_graph_json_to_result_restores_models(self, tmp_path: Path) -> None:
        """graph.json → TransformResult: 원자·엣지·서술형 패스스루 복원."""
        graph = _graph_json(tmp_path / "graph.json", with_edge=True)
        result = _graph_json_to_result(graph)
        assert len(result.concepts) == 2
        assert len(result.edges) == 1
        assert result.edges[0].from_code == "2수01-01-1"
        assert result.edges[0].relation == "prerequisite"  # use_enum_values → 문자열
        assert len(result.narrative_edges_raw) == 1


class TestLoadGuards:
    """load 명령 표면 — 드라이버 부재·입력 누락·env 누락(라이브 Neo4j 불요)."""

    @pytest.mark.skipif(
        find_spec("neo4j") is not None,
        reason="neo4j 드라이버가 설치돼 사전체크 안내 경로가 아님(통합테스트가 적재 검증)",
    )
    def test_load_without_driver_guides_install(self, tmp_path: Path) -> None:
        """neo4j 미설치 → 드라이버 사전체크에서 extra 설치 안내·종료코드 3."""
        graph = _graph_json(tmp_path / "graph.json")
        result = runner.invoke(app, ["load", "--graph", str(graph)])
        assert result.exit_code == 3
        assert "[neo4j]" in result.output

    def test_load_requires_graph_option(self) -> None:
        """--graph 미지정 → typer 필수 옵션 오류(종료코드 2)."""
        result = runner.invoke(app, ["load"])
        assert result.exit_code == 2

    def test_load_missing_graph_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """드라이버 설치 가정(find_spec 패치) + graph.json 부재 → 종료코드 2."""
        monkeypatch.setattr("data_pipeline.atom_graph.__main__.find_spec", lambda name: object())
        result = runner.invoke(app, ["load", "--graph", str(tmp_path / "nope.json")])
        assert result.exit_code == 2

    def test_load_missing_env_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """드라이버 설치 가정 + 접속 env 누락 → connect_driver ValueError → 종료코드 2."""
        monkeypatch.setattr("data_pipeline.atom_graph.__main__.find_spec", lambda name: object())
        for key in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
            monkeypatch.delenv(key, raising=False)
        graph = _graph_json(tmp_path / "graph.json")
        result = runner.invoke(app, ["load", "--graph", str(graph)])
        assert result.exit_code == 2
        assert "Neo4j 접속 정보 누락" in result.output
