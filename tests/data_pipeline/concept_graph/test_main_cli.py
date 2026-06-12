"""concept_graph CLI 단위테스트 — seed · validate · load(가드). 라이브 인프라 불요."""

from __future__ import annotations

import csv
import json
from importlib.util import find_spec
from pathlib import Path

import pytest
from typer.testing import CliRunner

from data_pipeline.concept_graph.__main__ import app
from data_pipeline.concept_graph.seed import build_concept_id
from data_pipeline.ncic.load import write_json
from data_pipeline.ncic.models import AchievementStandard

runner = CliRunner()


def _standards_json(tmp_path: Path) -> Path:
    stds = [
        AchievementStandard(
            code="[12미적Ⅰ01-01]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="미적분Ⅰ",
            domain="함수의 극한",
            statement="극한의 뜻을 안다.",
            source_url="https://www.ncic.go.kr/a",
        ),
        AchievementStandard(
            code="[12미적Ⅰ01-02]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="미적분Ⅰ",
            domain="함수의 극한",
            statement="극한값을 계산한다.",
            source_url="https://www.ncic.go.kr/b",
            parent_codes=["[12미적Ⅰ01-01]"],
        ),
    ]
    out = tmp_path / "standards.json"
    write_json(stds, out)
    return out


def _write_filled_concepts(path: Path, ids: list[str]) -> None:
    """전문가가 표기를 채운 concepts.csv 모사(검증 통과용)."""
    fields = [
        "concept_id",
        "name_ko",
        "name_en",
        "name_ja",
        "domain",
        "grade_band_hint",
        "prerequisite_concept_ids",
        "misconception_codes",
        "visualization_card_keys",
        "standard_codes",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, cid in enumerate(ids):
            w.writerow(
                {
                    "concept_id": cid,
                    "name_ko": f"개념{i}",
                    "name_en": f"concept{i}",
                    "name_ja": f"概念{i}",
                    "domain": "미적분",
                    "grade_band_hint": "고등학교",
                    "prerequisite_concept_ids": "",
                    "misconception_codes": "",
                    "visualization_card_keys": "",
                    "standard_codes": "",
                    "notes": "",
                }
            )


def _write_filled_edges(path: Path, pairs: list[tuple[str, str]]) -> None:
    fields = [
        "src_concept_id",
        "dst_concept_id",
        "relation",
        "strength",
        "evidence",
        "evidence_source",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for src, dst in pairs:
            w.writerow(
                {
                    "src_concept_id": src,
                    "dst_concept_id": dst,
                    "relation": "prerequisite",
                    "strength": "0.9",
                    "evidence": "NCIC 인접",
                    "evidence_source": "ncic",
                }
            )


class TestHelp:
    def test_help_lists_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        out = result.stdout.lower()
        assert "seed" in out
        assert "validate" in out
        assert "load" in out
        assert "transform-v1" in out


class TestTransformV1:
    def test_validates_real_corpus(self, corpus_dir: Path) -> None:
        """실데이터 transform-v1(검증만) → PASS 종료코드 0."""
        result = runner.invoke(app, ["transform-v1", "--corpus-dir", str(corpus_dir)])
        assert result.exit_code == 0, result.output
        assert "개념 403개" in result.stdout
        assert "엣지 541개" in result.stdout
        assert "PASS" in result.stdout

    def test_writes_outputs(self, corpus_dir: Path, tmp_path: Path) -> None:
        """--output-dir 주면 graph.json·id_map.csv 저장 + redaction 유지."""
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            ["transform-v1", "--corpus-dir", str(corpus_dir), "--output-dir", str(out)],
        )
        assert result.exit_code == 0, result.output
        graph = out / "graph.json"
        idmap = out / "id_map.csv"
        assert graph.exists()
        assert idmap.exists()
        text = graph.read_text(encoding="utf-8")
        # redaction: 산출 JSON에 본문 키 없음
        assert '"description"' not in text
        assert "formal_definition" not in text
        with idmap.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 403  # src_id → UC 매핑

    def test_missing_corpus_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["transform-v1", "--corpus-dir", str(tmp_path / "nope")])
        assert result.exit_code == 2

    def test_missing_concepts_file_exits_2(self, tmp_path: Path) -> None:
        """디렉토리는 있으나 concepts.jsonl 없음 → 종료코드 2."""
        (tmp_path / "empty").mkdir()
        result = runner.invoke(app, ["transform-v1", "--corpus-dir", str(tmp_path / "empty")])
        assert result.exit_code == 2


class TestSeed:
    def test_seed_writes_csvs(self, tmp_path: Path) -> None:
        ncic = _standards_json(tmp_path)
        out_dir = tmp_path / "seed"
        result = runner.invoke(
            app,
            [
                "seed",
                "--ncic",
                str(ncic),
                "--domain-filter",
                "미적분",
                "--output-dir",
                str(out_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out_dir / "concepts.csv").exists()
        assert (out_dir / "edges.csv").exists()
        with (out_dir / "concepts.csv").open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2  # 미적분Ⅰ 2건
        with (out_dir / "edges.csv").open(encoding="utf-8-sig") as f:
            edges = list(csv.DictReader(f))
        assert len(edges) == 1  # parent_codes 1건 → prerequisite 엣지 1

    def test_seed_missing_input_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["seed", "--ncic", str(tmp_path / "nope.json")])
        assert result.exit_code == 2


class TestValidate:
    def test_validate_filled_graph_succeeds(self, tmp_path: Path) -> None:
        a, b = build_concept_id("[12미적Ⅰ01-01]"), build_concept_id("[12미적Ⅰ01-02]")
        cpath, epath = tmp_path / "c.csv", tmp_path / "e.csv"
        _write_filled_concepts(cpath, [a, b])
        _write_filled_edges(epath, [(a, b)])
        result = runner.invoke(app, ["validate", "--concepts", str(cpath), "--edges", str(epath)])
        assert result.exit_code == 0, result.output
        assert "그래프 검증" in result.stdout

    def test_validate_unfilled_seed_reports_parse_errors(self, tmp_path: Path) -> None:
        """빈칸 표기(name) seed CSV는 파싱 실패 → 종료코드 1."""
        ncic = _standards_json(tmp_path)
        out_dir = tmp_path / "seed"
        runner.invoke(
            app,
            [
                "seed",
                "--ncic",
                str(ncic),
                "--domain-filter",
                "미적분",
                "--output-dir",
                str(out_dir),
            ],
        )
        result = runner.invoke(
            app,
            [
                "validate",
                "--concepts",
                str(out_dir / "concepts.csv"),
                "--edges",
                str(out_dir / "edges.csv"),
            ],
        )
        assert result.exit_code == 1
        assert "파싱 실패" in result.stdout

    def test_validate_detects_cycle_exits_1(self, tmp_path: Path) -> None:
        a, b = "UC.calc.a01.g10n01", "UC.calc.a01.g10n02"
        cpath, epath = tmp_path / "c.csv", tmp_path / "e.csv"
        _write_filled_concepts(cpath, [a, b])
        _write_filled_edges(epath, [(a, b), (b, a)])  # 순환
        result = runner.invoke(app, ["validate", "--concepts", str(cpath), "--edges", str(epath)])
        assert result.exit_code == 1
        assert "prerequisite_cycle" in result.stdout

    def test_validate_missing_csv_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["validate", "--concepts", str(tmp_path / "x.csv"), "--edges", str(tmp_path / "y.csv")],
        )
        assert result.exit_code == 2


class TestLoad:
    """load 명령 — graph.json → Neo4j 멱등 적재. CI(neo4j 미설치)는 드라이버 사전체크에서 안내.

    실 적재 왕복은 test_load_neo4j_integration.py(통합·기본 SKIP)가 검증한다. 여기서는 드라이버
    부재·입력 누락 등 *CLI 표면*만 확인한다(라이브 Neo4j 불요).
    """

    def _graph_json(self, tmp_path: Path) -> Path:
        """transform-v1 산출과 동형의 최소 graph.json(개념 1·엣지 0)."""
        out = tmp_path / "graph.json"
        out.write_text(
            json.dumps(
                {
                    "source_citation": "x",
                    "concepts": [
                        {
                            "concept_id": "UC.calc.limit.epsilon-delta",
                            "name_ko": "극한",
                            "domain": "미적분",
                            "review_status": "reviewed",
                        }
                    ],
                    "edges": [],
                    "flashcards_raw": [],
                    "intl_raw": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return out

    @pytest.mark.skipif(
        find_spec("neo4j") is not None,
        reason="neo4j 드라이버가 설치돼 사전체크 안내 경로가 아님(통합테스트가 적재 검증)",
    )
    def test_load_without_driver_guides_install(self, tmp_path: Path) -> None:
        """neo4j 미설치 → 드라이버 사전체크에서 extra 설치 안내·종료코드 3."""
        graph = self._graph_json(tmp_path)
        result = runner.invoke(app, ["load", "--graph", str(graph)])
        assert result.exit_code == 3
        assert "[neo4j]" in result.output

    def test_load_requires_graph_option(self) -> None:
        """--graph 미지정 → typer 필수 옵션 오류(종료코드 2)."""
        result = runner.invoke(app, ["load"])
        assert result.exit_code == 2
