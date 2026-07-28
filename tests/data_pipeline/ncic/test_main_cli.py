"""CLI(__main__) smoke test — crawl·load·check-robots.

load 커맨드는 hermetic하게 검증한다(라이브 PG 불요): DSN 해소·JSON 파싱·인자 전달은
`load_to_postgres`를 monkeypatch로 가짜화해 확인하고, 실제 PG 적재는 함수 단위 통합
테스트(test_load_postgres_integration.py)가 담당한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from data_pipeline.ncic.__main__ import app
from data_pipeline.ncic.load import write_json
from data_pipeline.ncic.models import AchievementStandard

runner = CliRunner()


def _write_min_file_a(path: Path) -> None:
    """extract 테스트용 합성 File A xlsx(실 컬럼명·괄호 link_type 포함)."""
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    sheets: dict[str, list[list[str]]] = {
        "성취기준_목록": [
            ["성취기준 코드", "교육과정", "과목약칭", "영역(단원)", "성취기준 내용"],
            ["[9수01-01]", "2022개정", "수학", "수와 연산", "소인수분해를 이해한다."],
            ["[2수03-08]", "2022개정", "수학", "도형과 측정", "도형 A."],
        ],
        "개념-성취기준-CCSS": [
            ["개념ID", "한국 성취기준(2022)", "연결구분"],
            ["N1", "[9수01-01]", "직접(기본수학)"],  # 괄호→베어 토큰·note
            ["N5", "[2수03-08]", "직접"],
        ],
    }
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            worksheet.append(row)
    workbook.remove(default_sheet)
    workbook.save(str(path))


class TestExtractCommand:
    def test_extract_writes_corpus(self, tmp_path: Path) -> None:
        """extract → standards.json·links.json·_provenance.json 생성·카운트·정규화 검증."""
        xlsx = tmp_path / "file_a.xlsx"
        _write_min_file_a(xlsx)
        out = tmp_path / "corpus"
        result = runner.invoke(app, ["extract", "--xlsx", str(xlsx), "--output-dir", str(out)])
        assert result.exit_code == 0, result.output

        std = json.loads((out / "standards.json").read_text(encoding="utf-8"))
        links = json.loads((out / "concept_standard_links.json").read_text(encoding="utf-8"))
        prov = json.loads((out / "_provenance.json").read_text(encoding="utf-8"))

        assert len(std["standards"]) == 2
        assert len(links["links"]) == 2
        # 괄호 link_type 정규화(직접(기본수학)→직접·note 기본수학)
        n1 = next(link for link in links["links"] if link["concept_src_id"] == "N1")
        assert n1["link_type"] == "직접" and n1["note"] == "기본수학"
        # provenance: sha256·카운트
        assert len(prov["source_sha256"]) == 64
        assert prov["counts"] == {"standards": 2, "links": 2, "2022 개정": 2}
        assert "공공누리" in prov["license_notice"]

    def test_extract_missing_xlsx_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["extract", "--xlsx", str(tmp_path / "nope.xlsx")])
        assert result.exit_code == 2

    def test_extract_validation_failure_exits_2(self, tmp_path: Path) -> None:
        """링크가 미존재 성취기준을 가리키면(norm_id 미해소) 검증 실패→Exit 2."""
        openpyxl = pytest.importorskip("openpyxl")
        xlsx = tmp_path / "bad.xlsx"
        workbook = openpyxl.Workbook()
        default_sheet = workbook.active
        sheets: dict[str, list[list[str]]] = {
            "성취기준_목록": [
                ["성취기준 코드", "교육과정", "과목약칭", "영역(단원)", "성취기준 내용"],
                ["[9수01-01]", "2022개정", "수학", "수와 연산", "x."],
            ],
            "개념-성취기준-CCSS": [
                ["개념ID", "한국 성취기준(2022)", "연결구분"],
                ["N9", "[9수99-99]", "직접"],  # 성취기준 목록에 없는 코드 → 고아
            ],
        }
        for name, rows in sheets.items():
            worksheet = workbook.create_sheet(title=name)
            for row in rows:
                worksheet.append(row)
        workbook.remove(default_sheet)
        workbook.save(str(xlsx))
        out = tmp_path / "corpus"
        result = runner.invoke(app, ["extract", "--xlsx", str(xlsx), "--output-dir", str(out)])
        assert result.exit_code == 2
        assert not (out / "standards.json").exists()  # 검증 실패 시 미저장


def _samples() -> list[AchievementStandard]:
    return [
        AchievementStandard(
            norm_id="2022_9수_01_01",
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="소인수분해의 뜻을 알고 자연수를 소인수분해할 수 있다.",
            source_url="https://www.ncic.go.kr/a",
        ),
        AchievementStandard(
            norm_id="2022_10공수1_01_01",
            code="[10공수1-01-01]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="공통수학1",
            domain="다항식",
            statement="다항식의 덧셈과 뺄셈을 이해한다.",
            source_url="https://www.ncic.go.kr/b",
        ),
    ]


def test_help_works() -> None:
    """`python -m data_pipeline.ncic --help` 가 정상 동작하고 load 커맨드를 노출."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "crawl" in result.stdout.lower() or "ncic" in result.stdout.lower()
    assert "load" in result.stdout.lower()


def test_crawl_requires_url_or_pdf() -> None:
    """url·pdf 모두 없으면 에러 종료."""
    result = runner.invoke(app, ["crawl"])
    assert result.exit_code != 0


def test_load_help_works() -> None:
    """`load --help`가 정상 동작."""
    result = runner.invoke(app, ["load", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.stdout
    assert "--dsn" in result.stdout


def test_load_without_dsn_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--dsn 도 WHYMATH_DATABASE_URL 도 없으면 종료코드 1."""
    monkeypatch.delenv("WHYMATH_DATABASE_URL", raising=False)
    out = tmp_path / "standards.json"
    write_json(_samples(), out)
    result = runner.invoke(app, ["load", "--json", str(out)])
    assert result.exit_code == 1


def test_load_missing_json_exits_2() -> None:
    """JSON 파일이 없으면 종료코드 2(DSN은 --dsn으로 통과)."""
    result = runner.invoke(
        app,
        [
            "load",
            "--json",
            "/nonexistent/standards.json",
            "--dsn",
            "postgresql://fake/db",
        ],
    )
    assert result.exit_code == 2


def test_load_empty_collection_exits_2(tmp_path: Path) -> None:
    """성취기준이 0개면 종료코드 2."""
    out = tmp_path / "empty.json"
    write_json([], out)
    result = runner.invoke(app, ["load", "--json", str(out), "--dsn", "postgresql://fake/db"])
    assert result.exit_code == 2


def test_load_success_passes_parsed_standards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON을 파싱해 load_to_postgres에 표준·DSN·테이블·upsert를 전달(가짜 로더)."""
    out = tmp_path / "standards.json"
    write_json(_samples(), out)

    calls: list[tuple[int, str, str, bool]] = []

    async def _fake_load(
        standards: Sequence[AchievementStandard],
        *,
        dsn: str,
        table_name: str,
        upsert: bool,
    ) -> int:
        calls.append((len(standards), dsn, table_name, upsert))
        return len(standards)

    monkeypatch.setattr("data_pipeline.ncic.__main__.load_to_postgres", _fake_load)
    result = runner.invoke(app, ["load", "--json", str(out), "--dsn", "postgresql://fake/db"])
    assert result.exit_code == 0, result.output
    assert calls == [(2, "postgresql://fake/db", "achievement_standards", True)]
    assert "2행 영향" in result.stdout


def test_load_uses_env_var_when_dsn_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--dsn 생략 시 WHYMATH_DATABASE_URL 환경변수를 사용."""
    out = tmp_path / "standards.json"
    write_json(_samples(), out)
    monkeypatch.setenv("WHYMATH_DATABASE_URL", "postgresql://envhost/db")

    seen: list[str] = []

    async def _fake_load(
        standards: Sequence[AchievementStandard],
        *,
        dsn: str,
        table_name: str,
        upsert: bool,
    ) -> int:
        seen.append(dsn)
        return len(standards)

    monkeypatch.setattr("data_pipeline.ncic.__main__.load_to_postgres", _fake_load)
    result = runner.invoke(app, ["load", "--json", str(out)])
    assert result.exit_code == 0, result.output
    assert seen == ["postgresql://envhost/db"]


def test_load_missing_postgres_extra_exits_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_to_postgres가 RuntimeError([postgres] 미설치)면 종료코드 4로 변환."""
    out = tmp_path / "standards.json"
    write_json(_samples(), out)

    async def _fake_load(
        standards: Sequence[AchievementStandard],
        *,
        dsn: str,
        table_name: str,
        upsert: bool,
    ) -> int:
        raise RuntimeError("load_to_postgres에는 [postgres] extra가 필요합니다")

    monkeypatch.setattr("data_pipeline.ncic.__main__.load_to_postgres", _fake_load)
    result = runner.invoke(app, ["load", "--json", str(out), "--dsn", "postgresql://fake/db"])
    assert result.exit_code == 4


def test_load_no_upsert_flag_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--no-upsert가 load_to_postgres(upsert=False)로 전달."""
    out = tmp_path / "standards.json"
    write_json(_samples(), out)

    captured: dict[str, bool] = {}

    async def _fake_load(
        standards: Sequence[AchievementStandard],
        *,
        dsn: str,
        table_name: str,
        upsert: bool,
    ) -> int:
        captured["upsert"] = upsert
        return len(standards)

    monkeypatch.setattr("data_pipeline.ncic.__main__.load_to_postgres", _fake_load)
    result = runner.invoke(
        app,
        ["load", "--json", str(out), "--dsn", "postgresql://fake/db", "--no-upsert"],
    )
    assert result.exit_code == 0, result.output
    assert captured["upsert"] is False
