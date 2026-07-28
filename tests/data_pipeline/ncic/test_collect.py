"""수집기 단위 테스트.

원칙:
  - 실 NCIC HTTP 호출 *절대 안 함*. respx로 모킹.
  - 합성 HTML 픽스처 → 추출·변환 e2e.
  - PDF 파싱은 pdfplumber 모킹 (한국어 폰트 임베딩 부담 회피).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from data_pipeline.ncic.collect import (
    DEFAULT_BASE_URL,
    NcicCrawler,
    NcicSourceConfig,
    check_robots_txt,
)


# ──────────────────────────────────────────────────────────────────────
# HTML 추출 e2e
# ──────────────────────────────────────────────────────────────────────
class TestHtmlExtractionE2E:
    async def test_extracts_middle_school_standards(self, html_middle_school_unit: str) -> None:
        """합성 중학교 HTML → 3개 성취기준 추출."""
        url = "https://www.ncic.go.kr/middle/math/01"
        with respx.mock(base_url="https://www.ncic.go.kr") as mock:
            mock.get("/middle/math/01").respond(
                status_code=200,
                text=html_middle_school_unit,
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
            config = NcicSourceConfig(rate_limit_seconds=0.0)
            async with NcicCrawler(config) as crawler:
                results = [s async for s in crawler.crawl_html([url])]

        assert len(results) == 3
        codes = {r.code for r in results}
        assert codes == {"[9수01-01]", "[9수01-02]", "[9수01-03]"}
        # 모든 레코드가 중학교
        assert all(r.school_type == "중학교" for r in results)
        assert all(r.grade_band == "중학교 1~3학년군" for r in results)
        # 공공누리 출처 추적
        assert all(r.source_url == url for r in results)
        # 본문 한국어 보존
        std1 = next(r for r in results if r.code == "[9수01-01]")
        assert "소인수분해" in std1.statement

    async def test_extracts_high_school_standards(self, html_high_school_unit: str) -> None:
        """합성 고1 HTML → 공통수학1 성취기준 추출."""
        url = "https://www.ncic.go.kr/high/math/공통수학1"
        with respx.mock(base_url="https://www.ncic.go.kr") as mock:
            mock.get(path__regex=r"/high/math/.+").respond(
                status_code=200,
                text=html_high_school_unit,
            )
            async with NcicCrawler(NcicSourceConfig(rate_limit_seconds=0.0)) as crawler:
                results = [s async for s in crawler.crawl_html([url])]

        assert len(results) == 2
        codes = {r.code for r in results}
        assert codes == {"[10공수1-01-01]", "[10공수1-01-02]"}
        for r in results:
            assert r.school_type == "고등학교"
            assert r.subject == "공통수학1"


# ──────────────────────────────────────────────────────────────────────
# 정중한 크롤링·재시도 정책
# ──────────────────────────────────────────────────────────────────────
class TestPoliteCrawling:
    async def test_user_agent_includes_contact(self) -> None:
        """UA에 연락처 포함 — 정중한 크롤링 표준."""
        config = NcicSourceConfig()
        assert "contact" in config.user_agent.lower()
        assert "whymath" in config.user_agent.lower()

    async def test_default_rate_limit_is_one_second(self) -> None:
        config = NcicSourceConfig()
        assert config.rate_limit_seconds == pytest.approx(1.0)

    async def test_retry_on_503(self) -> None:
        """503 응답 → 재시도 후 200."""
        url = "https://www.ncic.go.kr/retry-test"
        call_count = {"n": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(503)
            return httpx.Response(200, text="<html><body>[9수01-01] 본문</body></html>")

        with respx.mock(base_url="https://www.ncic.go.kr") as mock:
            mock.get("/retry-test").mock(side_effect=_handler)
            config = NcicSourceConfig(rate_limit_seconds=0.0, backoff_base=1.0)
            async with NcicCrawler(config) as crawler:
                results = [s async for s in crawler.crawl_html([url])]

        assert call_count["n"] >= 2
        assert len(results) == 1

    async def test_max_retries_exhausted_skips_url(self) -> None:
        """반복 실패 시 해당 URL 건너뜀, 다른 URL은 계속."""
        url_bad = "https://www.ncic.go.kr/always-fails"
        url_good = "https://www.ncic.go.kr/works"
        with respx.mock(base_url="https://www.ncic.go.kr") as mock:
            mock.get("/always-fails").respond(500)
            mock.get("/works").respond(200, text="<html><body>[9수01-05] 본문</body></html>")
            config = NcicSourceConfig(rate_limit_seconds=0.0, max_retries=2, backoff_base=1.0)
            async with NcicCrawler(config) as crawler:
                results = [s async for s in crawler.crawl_html([url_bad, url_good])]

        # bad URL은 건너뛰고 good URL의 1개만 수집
        assert len(results) == 1
        assert results[0].code == "[9수01-05]"


# ──────────────────────────────────────────────────────────────────────
# PDF 파싱 (pdfplumber 모킹)
# ──────────────────────────────────────────────────────────────────────
class TestPdfExtraction:
    def test_pdf_parsing_with_mocked_pdfplumber(
        self,
        tmp_path: Path,
        synthetic_pdf_bytes: bytes,
        synthetic_pdf_text: str,
    ) -> None:
        """pdfplumber.open 모킹 → 한국어 텍스트 반환 → 3개 추출."""
        pdf_path = tmp_path / "curriculum.pdf"
        pdf_path.write_bytes(synthetic_pdf_bytes)

        # pdfplumber 모킹: open() → context manager → pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = synthetic_pdf_text
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = False

        with patch("pdfplumber.open", return_value=mock_pdf):
            crawler = NcicCrawler(NcicSourceConfig(rate_limit_seconds=0.0))
            results = list(
                crawler.crawl_pdf(
                    pdf_path,
                    source_url="https://www.ncic.go.kr/pdf/x",
                    source_document="교육부고시_2022-33호_별책8",
                )
            )

        assert len(results) == 3
        codes = {r.code for r in results}
        assert "[9수01-01]" in codes
        assert "[9수01-02]" in codes
        assert "[10공수1-01-01]" in codes
        # 출처 추적
        first = results[0]
        assert first.source_document == "교육부고시_2022-33호_별책8"
        assert "ncic.go.kr" in first.source_url

    def test_pdf_missing_file_raises(self, tmp_path: Path) -> None:
        crawler = NcicCrawler(NcicSourceConfig(rate_limit_seconds=0.0))
        with pytest.raises(FileNotFoundError):
            list(
                crawler.crawl_pdf(
                    tmp_path / "missing.pdf",
                    source_url="https://x.com",
                )
            )


# ──────────────────────────────────────────────────────────────────────
# robots.txt 헬퍼
# ──────────────────────────────────────────────────────────────────────
class TestRobotsTxt:
    async def test_robots_allowed(self) -> None:
        with respx.mock(base_url=DEFAULT_BASE_URL) as mock:
            mock.get("/robots.txt").respond(
                200,
                text="User-agent: *\nAllow: /\n",
            )
            assert await check_robots_txt(DEFAULT_BASE_URL) is True

    async def test_robots_full_disallow(self) -> None:
        with respx.mock(base_url=DEFAULT_BASE_URL) as mock:
            mock.get("/robots.txt").respond(
                200,
                text="User-agent: *\nDisallow: /\n",
            )
            assert await check_robots_txt(DEFAULT_BASE_URL) is False

    async def test_robots_missing_treated_as_disallow(self) -> None:
        with respx.mock(base_url=DEFAULT_BASE_URL) as mock:
            mock.get("/robots.txt").respond(404)
            assert await check_robots_txt(DEFAULT_BASE_URL) is False


# ──────────────────────────────────────────────────────────────────────
# 컨텍스트 매니저 안전성
# ──────────────────────────────────────────────────────────────────────
class TestCrawlerLifecycle:
    async def test_requires_async_context(self) -> None:
        """`async with` 컨텍스트 밖에서 사용 → 에러."""
        from data_pipeline.ncic.collect import NcicCrawlError

        crawler = NcicCrawler()
        with pytest.raises(NcicCrawlError):
            await crawler._fetch("https://www.ncic.go.kr/x")
