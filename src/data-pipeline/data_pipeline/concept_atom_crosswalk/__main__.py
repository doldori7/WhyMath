"""437↔원자 크로스워크 CLI — derive(코퍼스 생성)·validate(재검증).

사용:
    python -m data_pipeline.concept_atom_crosswalk derive \
        --concept-graph data/corpus/concept_graph_v1/graph.json \
        --concepts-jsonl data/corpus/concept_graph_v1/concepts.jsonl \
        --atom-graph data/corpus/atom_graph_v1/graph.json \
        --output-dir data/corpus/concept_atom_crosswalk_v1

    python -m data_pipeline.concept_atom_crosswalk validate \
        --crosswalk data/corpus/concept_atom_crosswalk_v1/crosswalk.jsonl \
        --concept-graph data/corpus/concept_graph_v1/graph.json \
        --atom-graph data/corpus/atom_graph_v1/graph.json

derive: 양측 코퍼스(읽기 전용)에서 크로스워크를 프로그램적으로 유도→검증→`crosswalk.jsonl`
(437행 전량·concept_id 사전순)과 `_provenance.json`(소스 sha256·유도 방법·커버리지 실측)을
저장한다. validate: 커밋된 크로스워크를 양측 코퍼스에 대고 재검증만 한다(저장 없음).

error 발생 시 비정상 종료(CLAUDE.md 신뢰 원칙 — 조용히 넘기지 않음). skill_graph CLI 미러.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from data_pipeline.concept_atom_crosswalk.derive import (
    derive_crosswalk,
    load_atoms,
    load_concepts,
)
from data_pipeline.concept_atom_crosswalk.models import SOURCE_CITATION, CrosswalkEntry
from data_pipeline.concept_atom_crosswalk.validate import (
    CrosswalkValidationReport,
    validate_crosswalk,
)

app = typer.Typer(
    name="whymath-concept-atom-crosswalk",
    help="437↔원자 크로스워크 — 구 437 개념그래프를 신 원자 백본에 잇는 다리 코퍼스.",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)

# 기본 경로 — 저장소 루트 기준 상대경로(CI·로컬 공용). CLI 옵션으로 오버라이드 가능.
_DEFAULT_CONCEPT_GRAPH = Path("data/corpus/concept_graph_v1/graph.json")
_DEFAULT_CONCEPTS_JSONL = Path("data/corpus/concept_graph_v1/concepts.jsonl")
_DEFAULT_ATOM_GRAPH = Path("data/corpus/atom_graph_v1/graph.json")
_DEFAULT_OUTPUT_DIR = Path("data/corpus/concept_atom_crosswalk_v1")


@app.callback()
def _main() -> None:
    """크로스워크 CLI(서브커맨드: derive·validate).

    Typer가 단일 커맨드를 콜백으로 접지 않도록 명시 콜백을 둔다(skill_graph CLI 미러).
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


def _require_exists(path: Path, label: str) -> None:
    """입력 파일 실재 확인 — 없으면 즉시 종료(exit 2·skill_graph 미러)."""
    if not path.exists():
        typer.echo(f"[!] {label} 없음: {path}", err=True)
        raise typer.Exit(code=2)


def _read_crosswalk_jsonl(path: Path) -> list[CrosswalkEntry]:
    """crosswalk.jsonl → CrosswalkEntry 목록(빈 줄 무시·행 내부 불변식 재검증)."""
    entries: list[CrosswalkEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(CrosswalkEntry.model_validate(json.loads(line)))
    return entries


@app.command(name="derive")
def derive(
    concept_graph: Annotated[
        Path,
        typer.Option("--concept-graph", help="구 437 그래프 graph.json 경로."),
    ] = _DEFAULT_CONCEPT_GRAPH,
    concepts_jsonl: Annotated[
        Path,
        typer.Option("--concepts-jsonl", help="구 437 concepts.jsonl 경로(name_ko 조인)."),
    ] = _DEFAULT_CONCEPTS_JSONL,
    atom_graph: Annotated[
        Path,
        typer.Option("--atom-graph", help="신 원자 백본 graph.json 경로."),
    ] = _DEFAULT_ATOM_GRAPH,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="코퍼스 저장 디렉토리(생략 시 검증만)."),
    ] = _DEFAULT_OUTPUT_DIR,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """양측 코퍼스 → 크로스워크 유도 + 검증 + (선택) 코퍼스 저장."""
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    _require_exists(concept_graph, "concept graph.json")
    _require_exists(concepts_jsonl, "concepts.jsonl")
    _require_exists(atom_graph, "atom graph.json")

    concepts = load_concepts(concept_graph, concepts_jsonl)
    atoms = load_atoms(atom_graph)
    entries = derive_crosswalk(concepts, atoms)
    report = validate_crosswalk(
        entries,
        concept_ids={c.concept_id for c in concepts},
        atom_codes={a.code for a in atoms},
    )

    print(f"[유도] 개념 {len(concepts)}개 × 원자 {len(atoms)}개 → 크로스워크 {len(entries)}행")
    print(f"[검증] {report.report_text()}")

    if output_dir is not None:
        _write_crosswalk_jsonl(entries, output_dir / "crosswalk.jsonl")
        _write_provenance(
            report,
            sources={
                "concept_graph": (concept_graph, _sha256(concept_graph)),
                "concepts_jsonl": (concepts_jsonl, _sha256(concepts_jsonl)),
                "atom_graph": (atom_graph, _sha256(atom_graph)),
            },
            path=output_dir / "_provenance.json",
        )
        print(f"[저장] {output_dir / 'crosswalk.jsonl'} · {output_dir / '_provenance.json'}")

    if not report.success:
        raise typer.Exit(code=1)


@app.command(name="validate")
def validate(
    crosswalk: Annotated[
        Path,
        typer.Option("--crosswalk", "-c", help="crosswalk.jsonl 경로."),
    ] = _DEFAULT_OUTPUT_DIR
    / "crosswalk.jsonl",
    concept_graph: Annotated[
        Path,
        typer.Option("--concept-graph", help="구 437 그래프 graph.json 경로."),
    ] = _DEFAULT_CONCEPT_GRAPH,
    atom_graph: Annotated[
        Path,
        typer.Option("--atom-graph", help="신 원자 백본 graph.json 경로."),
    ] = _DEFAULT_ATOM_GRAPH,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """커밋된 크로스워크를 양측 코퍼스에 대고 재검증(저장 없음)."""
    _setup_logging(verbose)

    _require_exists(crosswalk, "crosswalk.jsonl")
    _require_exists(concept_graph, "concept graph.json")
    _require_exists(atom_graph, "atom graph.json")

    entries = _read_crosswalk_jsonl(crosswalk)
    concept_payload = json.loads(concept_graph.read_text(encoding="utf-8"))
    concept_ids = {str(node["concept_id"]) for node in concept_payload["concepts"]}
    atom_codes = {a.code for a in load_atoms(atom_graph)}

    report = validate_crosswalk(entries, concept_ids=concept_ids, atom_codes=atom_codes)
    print(f"[검증] {report.report_text()}")

    if not report.success:
        raise typer.Exit(code=1)


def _write_crosswalk_jsonl(entries: list[CrosswalkEntry], path: Path) -> None:
    """크로스워크 → crosswalk.jsonl(437행 전량·concept_id 사전순·행당 1 JSON)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(entry.model_dump(), ensure_ascii=False)
        for entry in sorted(entries, key=lambda e: e.concept_id)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_provenance(
    report: CrosswalkValidationReport,
    sources: dict[str, tuple[Path, str]],
    path: Path,
) -> None:
    """provenance 메타 → _provenance.json(소스 경로·sha256·유도 방법·커버리지 실측)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_citation": SOURCE_CITATION,
        "sources": {
            label: {"path": str(src), "sha256": sha} for label, (src, sha) in sources.items()
        },
        "derivation": (
            "프로그램적 유도 — ①양측 standard_codes 교집합으로 원자(level=='세부개념') 후보 "
            "②후보 복수 시 이름 토큰(단어 run+문자 bigram) 자카드 랭킹으로 primary "
            "③후보 0이면 unmapped 정직 표기(강제 매핑 금지). 동률 시 code 사전순."
        ),
        "counts": {
            "entries": report.entry_count,
            "mapped": report.mapped_count,
            "unmapped": report.unmapped_count,
            "method_counts": dict(sorted(report.method_counts.items())),
            "fanout_counts": {str(k): v for k, v in sorted(report.fanout_counts.items())},
        },
        "validation": {
            "success": report.success,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "counts_by_rule": report.counts_by_rule(),
        },
        "review_status": "ai_estimated — 전량 프로그램적 유도·사람 검수 전",
        "determinism": "결정론 — 동일 sha256 입력 2회 derive 시 byte 동일 산출(동률은 code 사전순)",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(운영·통합 실행 전용)
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
