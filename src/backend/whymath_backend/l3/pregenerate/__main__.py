"""사전적재 CLI — JSONL 스펙 → CachePrewarmer → 사람읽는 리포트.

사용법:
    python -m whymath_backend.l3.pregenerate <specs.jsonl> \\
        [--overwrite] [--ttl-seconds N] [--min-length N]

스펙 형식(한 줄당 JSON):
    {"prompt": "...", "system": "...",
     "request": {RoutingRequest 필드}, "precomputed_response": "..." | null}

기본 의존성: CompositeProvider(Ollama+Anthropic) + RedisCache + BasicSeedValidator.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from whymath_backend.l3.cache import RedisCache
from whymath_backend.l3.pregenerate.models import PregenItem, PrewarmReport
from whymath_backend.l3.pregenerate.prewarmer import CachePrewarmer
from whymath_backend.l3.pregenerate.validator import BasicSeedValidator
from whymath_backend.l3.providers.anthropic import AnthropicProvider
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import OllamaProvider


def load_items(text: str) -> list[PregenItem]:
    """JSONL 텍스트(한 줄당 PregenItem JSON) → 항목 리스트. 빈 줄·`#` 주석 무시.

    파싱 오류는 line 번호와 함께 ValueError로 던진다(어떤 줄이 잘못됐는지 명시).
    """
    items: list[PregenItem] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            items.append(PregenItem.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return items


def format_report(report: PrewarmReport) -> str:
    """사람읽는 1줄 요약 + 실패/스킵 항목 상세."""
    lines: list[str] = [
        (
            f"total={report.total} written={report.written} "
            f"skipped_exists={report.skipped_exists} "
            f"failed_validation={report.failed_validation} errored={report.errored}"
        ),
    ]
    for item in report.items:
        if item.status == "written":
            continue
        key = item.cache_key or "(no key)"
        reason = item.error or ""
        lines.append(f"  [{item.status}] {key} — {reason}")
    return "\n".join(lines)


async def _run(
    specs_path: Path,
    *,
    overwrite: bool,
    ttl_seconds: int,
    min_length: int,
) -> int:
    text = specs_path.read_text(encoding="utf-8")
    items = load_items(text)
    provider = CompositeProvider(local=OllamaProvider(), cloud=AnthropicProvider())
    cache = RedisCache()
    validator = BasicSeedValidator(min_length=min_length)
    prewarmer = CachePrewarmer(provider=provider, cache=cache, validator=validator)
    report = await prewarmer.prewarm(items, ttl_seconds=ttl_seconds, overwrite=overwrite)
    print(format_report(report))
    return 0 if report.errored == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리. 종료 코드 0(성공) / 1(하나 이상 error 항목 있음)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l3.pregenerate",
        description="L3 캐시 사전적재 — 런타임과 같은 키로 검증된 시드를 캐시에 채워 넣는다.",
    )
    parser.add_argument("specs_path", type=str, help="JSONL 스펙 파일 경로 (한 줄당 PregenItem)")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 캐시 키가 있어도 덮어쓰기(기본은 스킵)",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=0,
        help="캐시 TTL(초). 0(기본)=무만료(사전생성물은 만료되지 않게).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=1,
        help="BasicSeedValidator 최소 응답 길이(strip 후).",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    overwrite: bool = args.overwrite
    ttl_seconds: int = args.ttl_seconds
    min_length: int = args.min_length
    return asyncio.run(
        _run(
            Path(specs_path),
            overwrite=overwrite,
            ttl_seconds=ttl_seconds,
            min_length=min_length,
        )
    )


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())
