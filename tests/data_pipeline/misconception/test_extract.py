"""오개념 추출(`data_pipeline.misconception`) — 순수 추출 + CLI 라운드트립.

순수 `extract_misconceptions`의 평탄화·키 매핑·mis_id dedup·빈값 None을 hermetic 검증하고,
CLI(`__main__.app`)가 Collection JSON·provenance를 쓰는지 CliRunner로 본다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from data_pipeline.misconception.__main__ import app
from data_pipeline.misconception.extract import (
    extract_misconceptions,
    load_json,
)

runner = CliRunner()


def _concepts() -> list[dict[str, Any]]:
    """합성 개념 배열 — 완전/부분 레코드·mis_id 중복·결손·빈 L5_META 포함."""
    return [
        {
            "L5_META": {
                "오개념": [
                    {
                        "mis_id": "M0001",
                        "오개념": "(-)×(-)=(-)",
                        "학생의_잘못된_사고": "부호 규칙을 혼동한다.",
                        "distractor_규칙": "정답 대신 부호를 뒤집은 값을 배치.",
                        "error_type": "부호오류",
                        "난이도": "상",
                        "교정포인트": "음수×음수=양수.",
                        "매칭_CCSS": "7.NS.A.2",
                        "개념ID": "A1",
                        "성취기준코드": "[9수01-03]",
                        "학교급": "중학교",
                        "2022_영역": "수와 연산",
                        "세부단원_개념": "정수의 곱셈",
                        "매핑신뢰도": "높음",
                        "매핑점수": 0.9,
                        "생성·검수": "원본",
                    },
                    {"mis_id": "M0002", "오개념": "y", "매핑점수": "0.5"},  # 부분·str score
                    {"mis_id": "M0001", "오개념": "중복"},  # mis_id 중복 → skip
                    {"오개념": "id 없음"},  # mis_id 결손 → skip
                ]
            }
        },
        {"L5_META": {}},  # 오개념 키 없음
        {},  # L5_META 없음
    ]


class TestExtractMisconceptions:
    def test_normalizes_and_maps_keys(self) -> None:
        records, duplicates = extract_misconceptions(_concepts())
        assert duplicates == 1  # M0001 중복 1건 정직 집계
        assert [r["mis_id"] for r in records] == ["M0001", "M0002"]  # 첫 등장 우선·순서 보존
        full = records[0]
        assert full["canonical_statement"] == "(-)×(-)=(-)"
        assert full["error_type"] == "부호오류"
        assert full["ccss_code"] == "7.NS.A.2"
        assert full["concept_src_id"] == "A1"
        assert full["standard_code"] == "[9수01-03]"
        assert full["mapping_score"] == 0.9
        assert full["provenance_note"] == "원본"

    def test_partial_record_fills_none(self) -> None:
        records, _ = extract_misconceptions(_concepts())
        partial = records[1]  # M0002
        assert partial["canonical_statement"] == "y"
        assert partial["mapping_score"] == 0.5  # 문자열 "0.5" → float
        assert partial["error_type"] is None  # 미존재 필드는 None
        assert partial["ccss_code"] is None

    def test_empty_input(self) -> None:
        records, duplicates = extract_misconceptions([])
        assert records == [] and duplicates == 0


class TestLoadJson:
    def test_rejects_non_array(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text('{"not": "array"}', encoding="utf-8")
        with pytest.raises(ValueError):
            load_json(path)

    def test_loads_array(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.json"
        path.write_text('[{"L5_META": {}}]', encoding="utf-8")
        assert load_json(path) == [{"L5_META": {}}]


class TestExtractCli:
    def test_writes_corpus_and_provenance(self, tmp_path: Path) -> None:
        src = tmp_path / "layers.json"
        src.write_text(json.dumps(_concepts(), ensure_ascii=False), encoding="utf-8")
        out = tmp_path / "corpus"
        result = runner.invoke(app, ["--json", str(src), "--output-dir", str(out)])
        assert result.exit_code == 0, result.output

        collection = json.loads((out / "misconceptions.json").read_text(encoding="utf-8"))
        assert collection["count"] == 2
        assert {m["mis_id"] for m in collection["misconceptions"]} == {"M0001", "M0002"}
        assert "자체 저작" in collection["license_notice"]

        prov = json.loads((out / "_provenance.json").read_text(encoding="utf-8"))
        assert prov["counts"] == {
            "misconceptions": 2,
            "duplicates_skipped": 1,
            "with_ccss": 1,
            "with_error_type": 1,
        }
        assert len(prov["source_sha256"]) == 64
        assert prov["error_types"] == ["부호오류"]

    def test_missing_json_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["--json", str(tmp_path / "nope.json")])
        assert result.exit_code == 2

    def test_no_misconceptions_exits_2(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.json"
        src.write_text('[{"L5_META": {}}]', encoding="utf-8")
        result = runner.invoke(app, ["--json", str(src), "--output-dir", str(tmp_path / "o")])
        assert result.exit_code == 2
