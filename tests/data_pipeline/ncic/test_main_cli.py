"""CLI(__main__) smoke test."""

from __future__ import annotations

from typer.testing import CliRunner

from data_pipeline.ncic.__main__ import app

runner = CliRunner()


def test_help_works() -> None:
    """`python -m data_pipeline.ncic --help` 가 정상 동작."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "crawl" in result.stdout.lower() or "ncic" in result.stdout.lower()


def test_crawl_requires_url_or_pdf() -> None:
    """url·pdf 모두 없으면 에러 종료."""
    result = runner.invoke(app, ["crawl"])
    # exit code != 0
    assert result.exit_code != 0
