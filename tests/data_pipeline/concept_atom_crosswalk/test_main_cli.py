"""concept_atom_crosswalk CLI 스모크 — derive→validate 파일 왕복(atom_graph test_main_cli 미러).

hermetic: tmp_path에 소형 fixture 코퍼스를 만들어 CLI를 구동한다(실코퍼스·DB·네트워크 불요).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from data_pipeline.concept_atom_crosswalk.__main__ import app

runner = CliRunner()


def _write_fixture_corpora(base: Path) -> tuple[Path, Path, Path]:
    """소형 양측 코퍼스 fixture — (concept graph.json, concepts.jsonl, atom graph.json)."""
    concept_graph = base / "concept_graph.json"
    concept_graph.write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": "math.algebra.insubunhae",
                        "source_id": "N1",
                        "standard_codes": ["[9수02-01]"],
                    },
                    {
                        "concept_id": "math.probability.hwakryul",
                        "source_id": "N2",
                        "standard_codes": ["[9수04-99]"],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    concepts_jsonl = base / "concepts.jsonl"
    concepts_jsonl.write_text(
        json.dumps({"src_id": "N1", "name_ko": "인수분해"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"src_id": "N2", "name_ko": "확률"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    atom_graph = base / "atom_graph.json"
    atom_graph.write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "code": "9수02-01-1",
                        "name": "인수분해 기본",
                        "level": "세부개념",
                        "standard_codes": ["[9수02-01]"],
                    },
                    {
                        "code": "중수연-U1",
                        "name": "수와 연산",
                        "level": "단원",
                        "standard_codes": ["[9수02-01]"],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return concept_graph, concepts_jsonl, atom_graph


def test_derive_then_validate_roundtrip(tmp_path: Path) -> None:
    """derive가 코퍼스 2파일을 쓰고, validate가 그 산출을 green으로 재검증한다."""
    concept_graph, concepts_jsonl, atom_graph = _write_fixture_corpora(tmp_path)
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "derive",
            "--concept-graph",
            str(concept_graph),
            "--concepts-jsonl",
            str(concepts_jsonl),
            "--atom-graph",
            str(atom_graph),
            "-o",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "crosswalk.jsonl").exists()
    assert (out_dir / "_provenance.json").exists()

    # 산출 내용 — 매핑 1(유일 후보) + 미매핑 1(교집합 0·단원 노드는 후보 아님).
    rows = [
        json.loads(line)
        for line in (out_dir / "crosswalk.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r["concept_id"] for r in rows] == sorted(r["concept_id"] for r in rows)
    by_id = {r["concept_id"]: r for r in rows}
    assert by_id["math.algebra.insubunhae"]["match_method"] == "standard_code"
    assert by_id["math.probability.hwakryul"]["match_method"] == "unmapped"

    provenance = json.loads((out_dir / "_provenance.json").read_text(encoding="utf-8"))
    assert provenance["counts"] == {
        "entries": 2,
        "mapped": 1,
        "unmapped": 1,
        "method_counts": {"standard_code": 1, "unmapped": 1},
        "fanout_counts": {"0": 1, "1": 1},
    }

    result = runner.invoke(
        app,
        [
            "validate",
            "-c",
            str(out_dir / "crosswalk.jsonl"),
            "--concept-graph",
            str(concept_graph),
            "--atom-graph",
            str(atom_graph),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_validate_fails_on_dangling(tmp_path: Path) -> None:
    """dangling atom code가 섞인 크로스워크 → validate exit 1(조용히 넘기지 않음)."""
    concept_graph, _, atom_graph = _write_fixture_corpora(tmp_path)
    crosswalk = tmp_path / "crosswalk.jsonl"
    crosswalk.write_text(
        json.dumps(
            {
                "concept_id": "math.algebra.insubunhae",
                "atom_codes": ["GHOST-1"],
                "primary_atom_code": "GHOST-1",
                "match_method": "standard_code",
                "confidence": 0.9,
                "evidence": "fixture",
                "review_status": "ai_estimated",
                "unmapped_reason": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "validate",
            "-c",
            str(crosswalk),
            "--concept-graph",
            str(concept_graph),
            "--atom-graph",
            str(atom_graph),
        ],
    )
    assert result.exit_code == 1
    assert "atom_dangling" in result.output


def test_derive_missing_input_exits_2(tmp_path: Path) -> None:
    """입력 파일 부재 → exit 2(skill_graph CLI 미러)."""
    result = runner.invoke(
        app,
        ["derive", "--concept-graph", str(tmp_path / "없는파일.json")],
    )
    assert result.exit_code == 2
