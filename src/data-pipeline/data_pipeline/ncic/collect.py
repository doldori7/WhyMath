"""NCIC 성취기준 수집기.

NCIC 사이트 구조에 대한 *현실적 가정* (실 크롤링 전 검증 필요):

  1. NCIC 메인은 `https://www.ncic.go.kr` (`ncic.re.kr`은 리다이렉트 가능).
  2. 한국 정부 사이트는 *자동화 봇 UA를 차단*하는 경향 — 정중한 UA(연락처 포함) 사용.
  3. 교육과정 원문은 *HWP/PDF 첨부*가 표준 (HTML은 메타정보·목차만).
  4. ASP/JSP·세션 기반 — 일부 페이지가 POST 전용일 수 있음.
  5. JavaScript로 목록 렌더링 → playwright 폴백 경로 필요(이 모듈은 *기본 비활성*).

이 모듈이 제공하는 두 경로:
  (A) HTML 크롤링 — 가벼움, 메타정보·목차에 적합. `crawl_html()`
  (B) PDF 파싱   — 본문 추출에 적합, 정확. `crawl_pdf()` (로컬 파일 또는 URL).

실제 크롤링은 Kiki가 `python -m data_pipeline.ncic` 실행하여 시도.
사이트 차단·구조 변경 시 명확한 에러 + 폴백 안내.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import httpx
from bs4 import BeautifulSoup, Tag

from data_pipeline.ncic.clean import clean_text, normalize_code
from data_pipeline.ncic.models import AchievementStandard
from data_pipeline.ncic.transform import (
    RawStandardRecord,
    TransformError,
    transform_raw_to_standard,
)

logger = logging.getLogger("data_pipeline.ncic.collect")

# ──────────────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────────────
DEFAULT_BASE_URL: Final[str] = "https://www.ncic.go.kr"
"""NCIC 메인 도메인. 사이트 정책 변경 시 갱신."""

DEFAULT_USER_AGENT: Final[str] = (
    "WhyMath/0.1 (research; contact: data-engineer@whymath.example) " "httpx/0.27"
)
"""정중한 크롤링 UA. 연락처 포함이 표준."""

DEFAULT_RATE_LIMIT_SECONDS: Final[float] = 1.0
"""요청 간 최소 대기 (초). 정부 사이트 부담 최소화."""

DEFAULT_TIMEOUT: Final[float] = 30.0
"""HTTP 타임아웃 (초)."""

DEFAULT_MAX_RETRIES: Final[int] = 3
"""실패 시 재시도 횟수. Exponential backoff."""

DEFAULT_BACKOFF_BASE: Final[float] = 2.0
"""백오프 베이스. 대기 = base^(시도-1)."""

# robots.txt 확인은 별도 함수에서 — 호출자 책임


# ──────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class NcicSourceConfig:
    """수집기 설정 (불변)."""

    base_url: str = DEFAULT_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE
    # 추가 HTTP 헤더 (CSRF·세션 토큰 등 필요 시)
    extra_headers: dict[str, str] = field(default_factory=dict)


class NcicCrawlError(RuntimeError):
    """수집기 운영 예외."""


# ──────────────────────────────────────────────────────────────────────
# HTML 추출기
# ──────────────────────────────────────────────────────────────────────
class _HtmlStandardExtractor:
    """HTML 페이지에서 성취기준을 추출.

    가정:
      - 각 성취기준은 어떤 형태든 `[코드] 본문` 형식의 텍스트 노드로 등장.
      - 영역명·과목명은 상위 헤더(`<h1>`~`<h4>`)에 있을 가능성.

    NCIC 실제 구조가 다르면 *이 클래스만 교체*. 인터페이스(`extract_from_html`)는 안정.
    """

    # 인라인 코드 패턴 (텍스트 노드 안에 [9수01-01] 또는 [10공수1-01-01] 등장)
    # 형식 A: <학년><과목한글><영역2><-><순번2>
    # 형식 B: <학년><과목한글><과목숫자><-><영역2><-><순번2>
    _INLINE_CODE: Final[re.Pattern[str]] = re.compile(
        r"\[(\d{1,2}[ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6}\d?-?\d{2}-\d{2})\]"
    )

    def extract_from_html(self, html: str, source_url: str) -> Iterable[RawStandardRecord]:
        """HTML 한 페이지에서 모든 성취기준 raw 레코드를 yield.

        Args:
            html: HTML 본문.
            source_url: 원자료 URL (출처 표시용).

        Yields:
            RawStandardRecord. 변환 책임은 호출자.
        """
        soup = BeautifulSoup(html, "lxml")

        # 페이지 헤더 → 과목·영역 단서
        subject_hint, domain_hint = self._infer_subject_and_domain(soup)

        # 본문 전체 텍스트 (코드 단위로 분할)
        body_text = clean_text(soup.get_text(separator="\n"))

        # 코드 위치 추출 → 각 코드 다음 텍스트를 statement로
        matches = list(self._INLINE_CODE.finditer(body_text))
        for idx, match in enumerate(matches):
            code = f"[{match.group(1)}]"
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body_text)
            statement_raw = body_text[start:end].strip()

            # 다음 코드 직전까지를 statement로 보고, 첫 줄만 본문으로 채택
            #  나머지 줄(예: 해설)은 commentary 후보
            lines = [ln.strip() for ln in statement_raw.split("\n") if ln.strip()]
            if not lines:
                logger.debug("코드 %s 직후 본문 비어있음 — 건너뜀", code)
                continue

            statement = lines[0]
            commentary = "\n".join(lines[1:]) if len(lines) > 1 else None

            record: RawStandardRecord = {
                "code": normalize_code(code),
                "statement": statement,
                "source_url": source_url,
            }
            if commentary:
                record["commentary"] = commentary
            if subject_hint:
                record["subject"] = subject_hint
            if domain_hint:
                record["domain"] = domain_hint
            yield record

    @staticmethod
    def _infer_subject_and_domain(soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """페이지 헤더에서 과목·영역 단서를 뽑는다.

        보수적 추론 — 못 찾으면 None 반환(상위에서 fallback).
        """
        subject: str | None = None
        domain: str | None = None

        # h1·h2·h3 순으로 탐색
        for tag_name in ("h1", "h2", "h3", "h4"):
            tag = soup.find(tag_name)
            if isinstance(tag, Tag):
                text = clean_text(tag.get_text())
                # "수학", "공통수학1", "대수" 등이 포함되면 과목으로
                for token in (
                    "공통수학1",
                    "공통수학2",
                    "미적분Ⅰ",
                    "미적분Ⅱ",
                    "확률과 통계",
                    "기하",
                    "대수",
                    "수학",
                ):
                    if token in text:
                        subject = subject or token
                        break
                if subject and not domain:
                    # 영역 단서: "수와 연산", "변화와 관계" 등
                    for dom in (
                        "수와 연산",
                        "변화와 관계",
                        "도형과 측정",
                        "자료와 가능성",
                        "다항식",
                        "방정식과 부등식",
                        "도형의 방정식",
                        "집합과 명제",
                        "함수와 그래프",
                    ):
                        if dom in text:
                            domain = dom
                            break

        return subject, domain


# ──────────────────────────────────────────────────────────────────────
# PDF 추출기 (폴백 경로)
# ──────────────────────────────────────────────────────────────────────
class _PdfStandardExtractor:
    """PDF 파일에서 성취기준을 추출.

    NCIC 교육과정 PDF는 일반적으로:
      - 각 영역의 도입부에 영역명·핵심 아이디어
      - 표 형태로 [코드] | 성취기준 본문 | 해설
      - 페이지 footer에 출처·고시 번호

    pdfplumber로 페이지별 텍스트 추출 → 인라인 패턴 매칭.
    """

    # HTML 추출기와 동일 — 두 형식 모두 지원
    _INLINE_CODE: Final[re.Pattern[str]] = re.compile(
        r"\[(\d{1,2}[ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6}\d?-?\d{2}-\d{2})\]"
    )

    def extract_from_pdf(
        self,
        pdf_path: Path,
        source_url: str,
        source_document: str | None = None,
    ) -> Iterable[RawStandardRecord]:
        """PDF 파일에서 raw 레코드를 yield.

        Args:
            pdf_path: 로컬 PDF 경로.
            source_url: 원자료 URL.
            source_document: 문서 식별자 (예: '교육부고시_2022-33호_별책8').

        Yields:
            RawStandardRecord.

        Raises:
            FileNotFoundError: PDF 파일 없음.
            NcicCrawlError: pdfplumber 미설치 또는 파싱 실패.
        """
        try:
            import pdfplumber
        except ImportError as exc:
            raise NcicCrawlError("pdfplumber 미설치. `pip install pdfplumber`로 설치.") from exc

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

        logger.info("PDF 파싱 시작: %s", pdf_path)
        # 페이지를 전체 합쳐 텍스트화 후 코드 단위로 분할
        full_text_parts: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                if page_text:
                    full_text_parts.append(page_text)
                logger.debug("페이지 %d 텍스트 길이=%d", page_idx + 1, len(page_text))

        full_text = clean_text("\n".join(full_text_parts))
        matches = list(self._INLINE_CODE.finditer(full_text))

        if not matches:
            logger.warning("PDF에서 성취기준 코드를 찾지 못함: %s", pdf_path)
            return

        for idx, match in enumerate(matches):
            code = f"[{match.group(1)}]"
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
            statement_block = full_text[start:end].strip()
            lines = [ln.strip() for ln in statement_block.split("\n") if ln.strip()]
            if not lines:
                continue

            statement = lines[0]
            commentary = "\n".join(lines[1:]) if len(lines) > 1 else None

            record: RawStandardRecord = {
                "code": normalize_code(code),
                "statement": statement,
                "source_url": source_url,
            }
            if commentary:
                record["commentary"] = commentary
            if source_document:
                record["source_document"] = source_document
            yield record


# ──────────────────────────────────────────────────────────────────────
# 메인 크롤러 (비동기)
# ──────────────────────────────────────────────────────────────────────
class NcicCrawler:
    """NCIC 성취기준 수집기.

    사용 패턴:
        config = NcicSourceConfig()
        async with NcicCrawler(config) as crawler:
            async for std in crawler.crawl_html(["https://..../math_unit1"]):
                print(std)
    """

    def __init__(
        self,
        config: NcicSourceConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or NcicSourceConfig()
        self._client = client
        self._own_client = client is None
        self._html_extractor = _HtmlStandardExtractor()
        self._pdf_extractor = _PdfStandardExtractor()
        self._last_request_time: float = 0.0
        self._loop_lock = asyncio.Lock()

    # ── 컨텍스트 매니저 ──────────────────────────────────────────
    async def __aenter__(self) -> NcicCrawler:
        if self._client is None:
            headers = {
                "User-Agent": self.config.user_agent,
                # 한국 사이트는 Accept-Language 검증을 하기도 함
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
                **self.config.extra_headers,
            }
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.config.timeout,
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        if self._own_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── 정중한 fetch ────────────────────────────────────────────
    async def _fetch(self, url: str) -> httpx.Response:
        """rate-limit + retry 적용된 GET.

        Raises:
            NcicCrawlError: max_retries 초과.
        """
        if self._client is None:
            raise NcicCrawlError("AsyncClient 미초기화 — `async with` 컨텍스트에서 사용.")

        async with self._loop_lock:
            # rate limit 대기
            loop = asyncio.get_event_loop()
            now = loop.time()
            wait = self.config.rate_limit_seconds - (now - self._last_request_time)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = loop.time()

        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.debug("GET %s (시도 %d/%d)", url, attempt, self.config.max_retries)
                response = await self._client.get(url)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                wait = self.config.backoff_base ** (attempt - 1)
                logger.warning(
                    "GET %s 실패 (시도 %d/%d): %s — %.1fs 후 재시도",
                    url,
                    attempt,
                    self.config.max_retries,
                    exc,
                    wait,
                )
                if attempt < self.config.max_retries:
                    await asyncio.sleep(wait)

        raise NcicCrawlError(
            f"GET {url} {self.config.max_retries}회 실패. 마지막 에러: {last_error}"
        )

    # ── 공개 메서드: HTML 크롤링 ──────────────────────────────
    async def crawl_html(
        self,
        urls: Iterable[str],
    ) -> AsyncIterator[AchievementStandard]:
        """주어진 URL 목록을 순차 크롤링.

        각 URL마다 (1) fetch (2) 추출 (3) 변환 → AchievementStandard yield.
        실패한 레코드는 로깅 후 *건너뜀* (전체 중단 X).

        Args:
            urls: NCIC HTML 페이지 URL 리스트.

        Yields:
            검증된 AchievementStandard.
        """
        for url in urls:
            try:
                response = await self._fetch(url)
            except NcicCrawlError as exc:
                logger.error("페이지 fetch 실패: %s — %s", url, exc)
                continue

            html = response.text
            logger.info("페이지 %s 본문 길이=%d", url, len(html))

            for raw in self._html_extractor.extract_from_html(html, source_url=url):
                try:
                    yield transform_raw_to_standard(raw)
                except (TransformError, ValueError) as exc:
                    logger.warning(
                        "레코드 변환 실패 (code=%s): %s",
                        raw.get("code"),
                        exc,
                    )

    # ── 공개 메서드: PDF 파싱 (로컬 파일) ──────────────────────
    def crawl_pdf(
        self,
        pdf_path: Path,
        source_url: str,
        source_document: str | None = None,
    ) -> Iterable[AchievementStandard]:
        """로컬 PDF 파일에서 성취기준을 yield.

        비동기 아님 — pdfplumber가 동기 라이브러리.
        Args:
            pdf_path: PDF 경로.
            source_url: 원자료 URL (출처 표시).
            source_document: 문서 식별자.
        """
        for raw in self._pdf_extractor.extract_from_pdf(
            pdf_path, source_url=source_url, source_document=source_document
        ):
            try:
                yield transform_raw_to_standard(raw)
            except (TransformError, ValueError) as exc:
                logger.warning(
                    "PDF 레코드 변환 실패 (code=%s): %s",
                    raw.get("code"),
                    exc,
                )

    # ── 공개 메서드: 원격 PDF 다운로드 후 파싱 ────────────────
    async def download_and_parse_pdf(
        self,
        pdf_url: str,
        save_path: Path,
        source_document: str | None = None,
    ) -> Iterable[AchievementStandard]:
        """PDF를 다운로드하여 로컬 저장 후 파싱.

        Args:
            pdf_url: PDF URL.
            save_path: 저장 경로.
            source_document: 식별자.
        """
        response = await self._fetch(pdf_url)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(response.content)
        logger.info("PDF 저장: %s (%d bytes)", save_path, len(response.content))
        return self.crawl_pdf(save_path, source_url=pdf_url, source_document=source_document)


# ──────────────────────────────────────────────────────────────────────
# robots.txt 확인 헬퍼 (정중한 크롤링 의무)
# ──────────────────────────────────────────────────────────────────────
async def check_robots_txt(base_url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """robots.txt의 사용자 에이전트에 대한 일반 허용 여부 (대략 확인).

    True를 반환해도 *세부 경로별 disallow*는 별도 확인 필요.
    실패 시 보수적으로 False.
    """
    robots_url = base_url.rstrip("/") + "/robots.txt"
    headers = {"User-Agent": user_agent}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(robots_url)
            if response.status_code != 200:
                logger.warning("robots.txt 응답 비정상: %d", response.status_code)
                return False
            content = response.text.lower()
            # 매우 단순한 휴리스틱 — 전체 disallow 검사
            if "disallow: /\n" in content or "disallow: /\r" in content:
                # 단, User-agent: * 블록에 한해서만 적용 가정
                return False
            return True
    except httpx.HTTPError as exc:
        logger.warning("robots.txt 조회 실패: %s — 보수적으로 차단", exc)
        return False


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_USER_AGENT",
    "NcicCrawlError",
    "NcicCrawler",
    "NcicSourceConfig",
    "check_robots_txt",
]
