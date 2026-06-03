"""NCIC 크롤러 CLI.

사용:
    python -m data_pipeline.ncic crawl --output-dir data/ncic/
    python -m data_pipeline.ncic crawl --pdf path/to/curriculum.pdf
    python -m data_pipeline.ncic load --json data/ncic/standards.json
    python -m data_pipeline.ncic check-robots

실 크롤링은 Kiki가 직접 실행. 결과는 5% 사람 검수 후 git 커밋.
DB 적재(load)는 `[postgres]` extra + 살아있는 PostgreSQL이 필요(검수 통과분만).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from data_pipeline.ncic.collect import (
    DEFAULT_BASE_URL,
    NcicCrawler,
    NcicSourceConfig,
    check_robots_txt,
)
from data_pipeline.ncic.load import load_to_postgres, write_csv, write_json
from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    AchievementStandard,
    AchievementStandardCollection,
)
from data_pipeline.ncic.validate import validate_standards

app = typer.Typer(
    name="whymath-ncic",
    help="NCIC 성취기준 크롤러 (2022 개정 교육과정). 공공누리 1유형.",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def crawl(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="JSON·CSV 저장 디렉토리.",
        ),
    ] = Path("data/ncic"),
    urls: Annotated[
        list[str] | None,
        typer.Option(
            "--url",
            "-u",
            help="크롤링 대상 HTML URL (반복 지정 가능). 비우면 PDF 폴백.",
        ),
    ] = None,
    pdf: Annotated[
        Path | None,
        typer.Option(
            "--pdf",
            help="로컬 PDF 경로 (대안 경로). 지정 시 HTML 무시.",
        ),
    ] = None,
    pdf_source_url: Annotated[
        str,
        typer.Option(
            "--pdf-source-url",
            help="PDF의 원본 URL (공공누리 출처 표시).",
        ),
    ] = f"{DEFAULT_BASE_URL}/mobile.kri.org4.inventoryList.do",
    pdf_source_document: Annotated[
        str,
        typer.Option(
            "--pdf-source-document",
            help="PDF 문서 식별자 (예: '교육부고시_2022-33호_별책8').",
        ),
    ] = "교육부고시_2022-33호_별책8_수학과교육과정",
    rate_limit: Annotated[
        float,
        typer.Option("--rate-limit", help="요청 간 대기 (초)."),
    ] = 1.0,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="DEBUG 로그."),
    ] = False,
) -> None:
    """NCIC HTML 또는 PDF에서 성취기준을 수집·정제·검증·저장."""
    _setup_logging(verbose)

    print(SOURCE_CITATION)
    print(LICENSE_NOTICE)
    print()

    if pdf is None and not urls:
        typer.echo(
            "[!] --url 또는 --pdf 중 하나는 필수.\n"
            "    실 NCIC 사이트가 봇 차단할 가능성 → PDF 폴백 권장.\n"
            "    예: --pdf docs/교육부고시_2022-33호_별책8.pdf",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        standards = asyncio.run(
            _run_crawl(
                output_dir=output_dir,
                urls=urls or [],
                pdf=pdf,
                pdf_source_url=pdf_source_url,
                pdf_source_document=pdf_source_document,
                rate_limit=rate_limit,
            )
        )
    except FileNotFoundError as exc:
        # PDF 경로 오타·미반입 시 raw traceback 대신 안내
        typer.echo(
            f"[!] {exc}\n"
            "    PDF 경로를 확인하세요. NCIC에서 PDF를 받는 절차는\n"
            "    docs/data/ncic.md 6.2절 '옵션 B'를 참조하세요.",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    # 검증
    report = validate_standards(standards)
    print(f"\n[검증] {report.summary()}")
    if report.issues:
        print("[검증] 처음 10개 이슈:")
        for issue in report.issues[:10]:
            print(f"  - {issue.code} | {issue.rule} | {issue.detail}")

    if not standards:
        typer.echo("[!] 수집된 성취기준 없음. 사이트 접근·구조를 점검하세요.", err=True)
        raise typer.Exit(code=2)

    # 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "standards.json"
    csv_path = output_dir / "standards.csv"
    collection = write_json(standards, json_path)
    rows = write_csv(standards, csv_path)

    print(f"\n[저장] {json_path} — {collection.count}개")
    print(f"[저장] {csv_path}     — {rows}행")
    print(f"[저장] {csv_path.with_suffix('.meta.json')} (출처·라이선스 sidecar)")
    print(
        "\n[다음 단계]\n"
        "  1. 사람 검수: 무작위 5% 샘플링 → 코드·본문·해설 확인\n"
        "  2. git diff → MEMORY.md에 결과 기록\n"
        "  3. 검수 통과분: python -m data_pipeline.ncic load --json <위 standards.json>\n"
        "  4. data-engineer 표준 워크플로우 9단계 완료 표시"
    )


@app.command()
def load(
    json_path: Annotated[
        Path,
        typer.Option(
            "--json",
            "-j",
            help="crawl이 생성한 standards.json 경로 (AchievementStandardCollection).",
        ),
    ],
    dsn: Annotated[
        str | None,
        typer.Option(
            "--dsn",
            help="PostgreSQL DSN. 미지정 시 WHYMATH_DATABASE_URL 환경변수 사용.",
        ),
    ] = None,
    table_name: Annotated[
        str,
        typer.Option("--table-name", help="적재 테이블명."),
    ] = "achievement_standards",
    upsert: Annotated[
        bool,
        typer.Option(
            "--upsert/--no-upsert",
            help="code 충돌 시 UPDATE(기본) vs 무시(DO NOTHING).",
        ),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="DEBUG 로그."),
    ] = False,
) -> None:
    """검수 통과한 standards.json을 PostgreSQL achievement_standards 테이블에 적재.

    DSN은 시크릿이므로 CLI 인자 노출보다 WHYMATH_DATABASE_URL 환경변수를 권장한다.
    `[postgres]` extra(sqlalchemy+asyncpg)가 없으면 load_to_postgres가 RuntimeError로
    안내한다(여기서 종료코드 4로 변환).
    """
    _setup_logging(verbose)

    print(SOURCE_CITATION)
    print(LICENSE_NOTICE)
    print()

    # DSN 해소 — 옵션 > 환경변수. 둘 다 없으면 종료.
    resolved_dsn = dsn or os.environ.get("WHYMATH_DATABASE_URL")
    if not resolved_dsn:
        typer.echo(
            "[!] DSN 미지정 — --dsn 옵션 또는 WHYMATH_DATABASE_URL 환경변수가 필요합니다.",
            err=True,
        )
        raise typer.Exit(code=1)

    # JSON 로드 (crawl 산출물 = AchievementStandardCollection)
    if not json_path.exists():
        typer.echo(f"[!] JSON 파일 없음: {json_path}", err=True)
        raise typer.Exit(code=2)
    collection = AchievementStandardCollection.model_validate_json(
        json_path.read_text(encoding="utf-8")
    )
    print(f"[로드] {json_path} — {collection.count}개 성취기준")
    if not collection.standards:
        typer.echo("[!] 적재할 성취기준 없음.", err=True)
        raise typer.Exit(code=2)

    # 적재 — [postgres] extra 미설치 시 RuntimeError → 종료코드 4
    try:
        affected = asyncio.run(
            load_to_postgres(
                collection.standards,
                dsn=resolved_dsn,
                table_name=table_name,
                upsert=upsert,
            )
        )
    except RuntimeError as exc:
        typer.echo(f"[!] {exc}", err=True)
        raise typer.Exit(code=4) from exc

    mode = "upsert(UPDATE)" if upsert else "DO NOTHING"
    print(f"[적재] {table_name} — {affected}행 영향 (충돌 시 {mode})")


@app.command()
def check_robots(
    base_url: Annotated[str, typer.Option("--base-url", help="확인할 도메인.")] = DEFAULT_BASE_URL,
) -> None:
    """NCIC robots.txt 확인."""
    _setup_logging(False)
    allowed = asyncio.run(check_robots_txt(base_url))
    if allowed:
        typer.echo(f"OK — {base_url}/robots.txt 일반 허용")
    else:
        typer.echo(
            f"WARN — {base_url}/robots.txt 미확인 또는 부분 차단. 보수적으로 크롤링 자제.",
            err=True,
        )
        raise typer.Exit(code=3)


async def _run_crawl(
    *,
    output_dir: Path,
    urls: list[str],
    pdf: Path | None,
    pdf_source_url: str,
    pdf_source_document: str,
    rate_limit: float,
) -> list[AchievementStandard]:
    """HTML/PDF 분기 + 표준화 본체."""
    config = NcicSourceConfig(rate_limit_seconds=rate_limit)
    results: list[AchievementStandard] = []

    if pdf is not None:
        # PDF 경로
        async with NcicCrawler(config) as crawler:
            for std in crawler.crawl_pdf(
                pdf,
                source_url=pdf_source_url,
                source_document=pdf_source_document,
            ):
                results.append(std)
        return results

    # HTML 경로
    async with NcicCrawler(config) as crawler:
        async for std in crawler.crawl_html(urls):
            results.append(std)
    return results


if __name__ == "__main__":  # pragma: no cover
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
