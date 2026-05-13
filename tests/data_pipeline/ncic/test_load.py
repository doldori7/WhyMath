"""load 모듈 (JSON·CSV·PostgreSQL) 단위 테스트."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from data_pipeline.ncic.load import load_to_postgres, write_csv, write_json
from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    AchievementStandard,
)


def _samples() -> list[AchievementStandard]:
    return [
        AchievementStandard(
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            sub_domain="소인수분해",
            statement="소인수분해의 뜻을 알고 자연수를 소인수분해할 수 있다.",
            commentary="유한 번의 시행으로 가능.",
            source_url="https://www.ncic.go.kr/a",
        ),
        AchievementStandard(
            code="[10공수1-01-01]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="공통수학1",
            domain="다항식",
            statement="다항식의 덧셈과 뺄셈을 이해한다.",
            source_url="https://www.ncic.go.kr/b",
            parent_codes=["[9수02-01]"],
        ),
    ]


class TestWriteJson:
    def test_writes_file_with_metadata(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        coll = write_json(_samples(), out)
        assert out.exists()
        assert coll.count == 2

    def test_json_includes_license_notice(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        write_json(_samples(), out)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        # 공공누리 출처·라이선스 표지가 포함되어야 함
        assert loaded["source_citation"] == SOURCE_CITATION
        assert loaded["license_notice"] == LICENSE_NOTICE
        assert "2022 개정" in loaded["curriculum_revision"]
        assert "collected_at" in loaded
        assert len(loaded["standards"]) == 2

    def test_korean_text_not_escaped(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        write_json(_samples(), out)
        raw = out.read_text(encoding="utf-8")
        assert "소인수분해" in raw  # ensure_ascii=False
        assert "\\u" not in raw or "소인수분해" in raw

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "path" / "out.json"
        write_json(_samples(), nested)
        assert nested.exists()


class TestWriteCsv:
    def test_writes_csv_with_header(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        rows = write_csv(_samples(), out)
        assert rows == 2
        assert out.exists()
        # UTF-8 BOM (Excel 친화)
        content = out.read_bytes()
        assert content.startswith(b"\xef\xbb\xbf")

    def test_csv_has_expected_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        write_csv(_samples(), out)
        with out.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            assert "code" in reader.fieldnames
            assert "statement" in reader.fieldnames
            assert "source_url" in reader.fieldnames
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["code"] == "[9수01-01]"

    def test_csv_parent_codes_serialized(self, tmp_path: Path) -> None:
        """리스트 필드는 ';' 구분."""
        out = tmp_path / "out.csv"
        write_csv(_samples(), out)
        with out.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # 두 번째 샘플의 parent_codes
        second = next(r for r in rows if r["code"] == "[10공수1-01-01]")
        assert second["parent_codes"] == "[9수02-01]"

    def test_csv_sidecar_metadata_created(self, tmp_path: Path) -> None:
        """CSV는 sidecar `.meta.json`을 함께 생성."""
        out = tmp_path / "out.csv"
        write_csv(_samples(), out)
        sidecar = out.with_suffix(".meta.json")
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        assert meta["source_citation"] == SOURCE_CITATION
        assert meta["license_notice"] == LICENSE_NOTICE
        assert meta["rows"] == 2

    def test_none_fields_become_blank(self, tmp_path: Path) -> None:
        """None 필드는 CSV에서 빈 문자열."""
        out = tmp_path / "out.csv"
        write_csv(_samples(), out)
        with out.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        first = next(r for r in rows if r["code"] == "[9수01-01]")
        # sub_domain 있음, big_idea 없음
        assert first["big_idea"] == ""
        assert first["sub_domain"] == "소인수분해"


class TestPostgresLoadStub:
    async def test_postgres_load_not_yet_implemented(self) -> None:
        """Phase 1에서는 시그니처만 — 호출 시 NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            await load_to_postgres(_samples(), dsn="postgresql://localhost/test")
        assert "Phase 2" in str(exc_info.value)
