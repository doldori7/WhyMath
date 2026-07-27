"""그래프 분석 CLI — report(허브·영향도·오개념 전파 — 빌드타임 오프라인).

사용:
    python -m data_pipeline.graph_analytics report [--top-n 20] [--json out.json]

코퍼스 4파일(원자 그래프·구 개념 그래프[source_id 다리]·오개념·crosswalk)을 읽어 저작·검수
우선순위 리포트를 낸다. **오프라인 산출 전용** — LLM 컨텍스트·튜터링 preload로 배선 금지
(`__init__.py` 경계 명문). 사이클(DAG 위반) 발견 시 비정상 종료(조용히 넘기지 않음).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from data_pipeline.graph_analytics.analytics import AnalyticsReport, build_report

app = typer.Typer(
    name="whymath-graph-analytics",
    help="그래프 분석 — 허브·영향도·blocking 오개념 전파(빌드타임 오프라인 리포트).",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)

_NOTICE = (
    "빌드타임 오프라인 리포트 — LLM 컨텍스트·튜터링 preload 투입 금지"
    "(Minimal Reasoning Subgraph·오개념 preload 금지 불변)"
)


@app.callback()
def _main() -> None:
    """그래프 분석 CLI(서브커맨드: report). formula_graph CLI 미러(단일 커맨드 접힘 방지)."""


@app.command(name="report")
def report(
    atom_graph: Annotated[Path, typer.Option("--atom-graph", help="원자 백본 graph.json.")] = Path(
        "data/corpus/atom_graph_v1/graph.json"
    ),
    concept_graph: Annotated[
        Path, typer.Option("--concept-graph", help="구 개념 그래프 graph.json(source_id 다리).")
    ] = Path("data/corpus/concept_graph_v1/graph.json"),
    misconceptions: Annotated[
        Path, typer.Option("--misconceptions", help="오개념 코퍼스 JSON.")
    ] = Path("data/corpus/misconceptions_v1/misconceptions.json"),
    crosswalk: Annotated[
        Path, typer.Option("--crosswalk", help="개념↔원자 crosswalk.jsonl.")
    ] = Path("data/corpus/concept_atom_crosswalk_v1/crosswalk.jsonl"),
    top_n: Annotated[int, typer.Option("--top-n", help="stdout 랭킹 표시 수.")] = 20,
    json_out: Annotated[
        Path | None, typer.Option("--json", help="전체 리포트 JSON 저장 경로(선택).")
    ] = None,
) -> None:
    """코퍼스 → 허브·영향도·오개념 전파 리포트(stdout + 선택 JSON)."""
    for path in (atom_graph, concept_graph, misconceptions, crosswalk):
        if not path.is_file():
            typer.echo(f"[!] 코퍼스 파일 없음: {path}", err=True)
            raise typer.Exit(code=2)

    result = build_report(
        atom_graph=atom_graph,
        concept_graph=concept_graph,
        misconceptions=misconceptions,
        crosswalk=crosswalk,
    )
    print(f"[경계] {_NOTICE}")
    print(result.report_text(top_n=top_n))

    if json_out is not None:
        _write_json(result, json_out)
        print(f"[저장] {json_out}")

    if not result.success:
        raise typer.Exit(code=1)


def _write_json(result: AnalyticsReport, path: Path) -> None:
    """전체 리포트(허브·전파 전량·skip) → JSON — 소비처는 저작·검수 ops."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "notice": _NOTICE,
        "atom_count": result.atom_count,
        "edge_count": result.edge_count,
        "blocking_total": result.blocking_total,
        "cycle": result.cycle,
        "hubs": [asdict(m) for m in result.hubs],
        "misconception_impacts": [asdict(i) for i in result.impacts],
        "skipped": result.skipped,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(운영·통합 실행 전용)
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
