"""전략 그래프 CLI — transform-v1(strategies.jsonl → graph.json).

사용:
    python -m data_pipeline.strategy_graph transform-v1 \
        --source data/corpus/strategy_graph_v1/strategies.jsonl \
        --output-dir data/corpus/strategy_graph_v1

transform-v1: 자체작성 `strategies.jsonl`을 정형화→검증한 뒤 `graph.json`(전략 노드)과
`_provenance.json`(source sha256·카운트·결정성)을 저장한다. formula_graph transform-v1 출력 미러
(전략은 PG 프로젝션만·엣지 없음 — closed 8노드 canonical·연결은 소비처 참조 키[Phase 6b]).

무저장소(--output-dir 생략) 시 검증만 수행한다. warning은 통과 처리, error 또는 정형화 skip 발생
시 비정상 종료(CLAUDE.md 신뢰 원칙 — 조용히 넘기지 않음).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from data_pipeline.strategy_graph.models import SOURCE_CITATION
from data_pipeline.strategy_graph.transform import (
    TransformResult,
    transform_strategies,
)
from data_pipeline.strategy_graph.validate import (
    StrategyValidationReport,
    validate_strategies,
)

app = typer.Typer(
    name="whymath-strategy-graph",
    help="전략 그래프 — strategies.jsonl(자체작성 공략 heuristic) 정형화·검증.",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """전략 그래프 파이프라인 CLI(서브커맨드: transform-v1).

    Typer가 단일 커맨드를 콜백으로 접지 않도록 명시 콜백을 둔다(formula_graph CLI 미러).
    """


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _sha256(path: Path) -> str:
    """파일 sha256(provenance 기록·재현성)."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """jsonl → dict 목록(빈 줄 무시). 각 줄은 한 전략 레코드."""
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


@app.command(name="transform-v1")
def transform_v1(
    source: Annotated[
        Path,
        typer.Option("--source", "-s", help="자체작성 strategies.jsonl 경로."),
    ] = Path("data/corpus/strategy_graph_v1/strategies.jsonl"),
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="graph.json·_provenance.json 저장 디렉토리(생략 시 검증만).",
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """strategies.jsonl → 정형화 + 검증 + (선택) 코퍼스 저장."""
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    if not source.exists():
        typer.echo(f"[!] strategies.jsonl 없음: {source}", err=True)
        raise typer.Exit(code=2)

    records = _read_jsonl(source)
    result = transform_strategies(records)
    report = validate_strategies(result.strategies)

    print(f"[정형화] {result.summary()}")
    if result.skipped:
        print(f"[정형화] skip {len(result.skipped)}건:")
        for msg in result.skipped[:10]:
            print(f"  - {msg}")
    print(f"[검증] {report.report_text()}")

    if output_dir is not None:
        source_sha = _sha256(source)
        _write_graph_json(result, output_dir / "graph.json")
        _write_provenance(result, report, source, source_sha, output_dir / "_provenance.json")
        print(f"[저장] {output_dir / 'graph.json'} · {output_dir / '_provenance.json'}")

    if result.skipped or not report.success:
        raise typer.Exit(code=1)


def _write_graph_json(result: TransformResult, path: Path) -> None:
    """정형화 산출 → graph.json(전략 노드 배열·엣지 없음 — closed canonical·연결은 참조 키[6b])."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_citation": SOURCE_CITATION,
        "strategies": [s.model_dump() for s in result.strategies],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_provenance(
    result: TransformResult,
    report: StrategyValidationReport,
    source: Path,
    source_sha: str,
    path: Path,
) -> None:
    """provenance 메타 → _provenance.json(sha256·카운트·검증 결과·결정성)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_file": source.name,
        "source_sha256": source_sha,
        "source_citation": SOURCE_CITATION,
        "counts": result.provenance,
        "validation": {
            "success": report.success,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "counts_by_rule": report.counts_by_rule(),
        },
        "skipped": result.skipped,
        "determinism": "결정론 — 동일 sha256 입력 2회 transform 시 byte 동일 산출",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(운영·통합 실행 전용)
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
