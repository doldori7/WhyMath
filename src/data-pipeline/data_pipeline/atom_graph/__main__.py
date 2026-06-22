"""원자 백본 CLI — transform-v1(xlsx → graph.json) · load(graph.json → Neo4j 멱등 적재).

사용:
    python -m data_pipeline.atom_graph transform-v1 \
        --source <원자_xlsx> \
        --output-dir data/corpus/atom_graph_v1 \
        --standards data/corpus/standards_v1/standards.json
    python -m data_pipeline.atom_graph load \
        --graph data/corpus/atom_graph_v1/graph.json   # Neo4j 멱등 적재(env 접속)

transform-v1: xlsx 2시트(원자_통합마스터·선수엣지_통합)를 추출→정형화→검증한 뒤 `graph.json`
(원자+단원+소단원 노드·원자ID 엣지·서술형 패스스루·redaction 마커)과 `_provenance.json`
(source sha256·정규화 카운트·결정성)을 저장한다. concept_graph transform-v1 출력을 미러한다.

load: transform-v1이 만든 graph.json을 Neo4j에 멱등 MERGE 적재한다(Phase 2c·접속 env 전용).
구 437 개념 그래프와 별개 라벨(`:Atom`·`:ATOM_PREREQUISITE`)로 additive 적재한다.

무저장소(--output-dir 생략) 시 검증만 수행한다. warning은 통과 처리(§3), error 또는 정형화
skip 발생 시 비정상 종료(CLAUDE.md 신뢰 원칙 — 조용히 넘기지 않음).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Annotated

import typer

from data_pipeline.atom_graph.extract import ExtractError, extract_workbook
from data_pipeline.atom_graph.models import SOURCE_CITATION, AtomConcept, AtomEdge
from data_pipeline.atom_graph.transform import TransformResult, transform_dataset
from data_pipeline.atom_graph.validate import GraphValidationReport, validate_dataset

app = typer.Typer(
    name="whymath-atom-graph",
    help="원자 백본 — 원자_통합마스터·선수엣지_통합 xlsx 정형화·검증(자체 구축 자산).",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """원자 백본 파이프라인 CLI(서브커맨드: transform-v1).

    Typer가 단일 커맨드를 콜백으로 접지 않도록 명시 콜백을 둔다 — concept_graph CLI처럼
    `python -m data_pipeline.atom_graph transform-v1 ...` 형태를 보장(시그니처 미러).
    """


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _sha256(path: Path) -> str:
    """파일 sha256(provenance 기록·재현성). 청크 읽기(대용량 xlsx 대비)."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_standard_codes(standards: Path | None) -> set[str] | None:
    """standards.json → code 집합(standard_exists 검증용). 미지정/부재 시 None(검증 skip)."""
    if standards is None or not standards.exists():
        return None
    payload = json.loads(standards.read_text(encoding="utf-8"))
    return {str(s["code"]) for s in payload.get("standards", [])}


@app.command(name="transform-v1")
def transform_v1(
    source: Annotated[
        Path,
        typer.Option("--source", "-s", help="원자 백본 xlsx 경로(원자_통합마스터·선수엣지_통합)."),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="graph.json·_provenance.json 저장 디렉토리(생략 시 검증만).",
        ),
    ] = None,
    standards: Annotated[
        Path | None,
        typer.Option(
            "--standards",
            help="standards.json 경로(standard_exists 검증용·생략 시 해당 검증 skip).",
        ),
    ] = Path("data/corpus/standards_v1/standards.json"),
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """원자 백본 xlsx → 정형화 + 검증 + (선택) 코퍼스 저장."""
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    if not source.exists():
        typer.echo(f"[!] 원자 xlsx 없음: {source}", err=True)
        raise typer.Exit(code=2)

    try:
        atom_rows, edge_rows = extract_workbook(source)
    except ExtractError as exc:
        typer.echo(f"[!] 추출 실패: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    result = transform_dataset(atom_rows=atom_rows, edge_rows=edge_rows)
    known_codes = _load_standard_codes(standards)
    report = validate_dataset(result, known_standard_codes=known_codes)

    print(f"[정형화] {result.summary()}")
    if result.provenance:
        print(f"[정규화] {result.provenance}")
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
    """정형화 산출 → graph.json(개념·엣지·서술형 패스스루·redaction 마커 유지).

    redaction 불변: AtomConcept 모델에 K-12 핵심명제 본문 슬롯이 없어 dump에 미포함. 각 K-12
    원자는 redacted_fields=['핵심명제/성취기준내용'] 마커를 보존한다(누수 감사).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_citation": SOURCE_CITATION,
        "concepts": [c.model_dump() for c in result.concepts],
        "edges": [e.model_dump() for e in result.edges],
        "narrative_edges_raw": result.narrative_edges_raw,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_provenance(
    result: TransformResult,
    report: GraphValidationReport,
    source: Path,
    source_sha: str,
    path: Path,
) -> None:
    """provenance 메타 → _provenance.json(sha256·정규화 카운트·노드/엣지 통계·검증 결과)."""
    from data_pipeline.atom_graph.models import NodeLevel, SchoolLevel

    atoms = [c for c in result.concepts if c.level == NodeLevel.ATOM.value]
    units = [c for c in result.concepts if c.level == NodeLevel.UNIT.value]
    subunits = [c for c in result.concepts if c.level == NodeLevel.SUBUNIT.value]
    univ = sum(1 for c in atoms if c.school_level == SchoolLevel.UNIVERSITY.value)

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_file": source.name,
        "source_sha256": source_sha,
        "source_citation": SOURCE_CITATION,
        "normalization_counts": result.provenance,
        "node_counts": {
            "atoms": len(atoms),
            "units": len(units),
            "subunits": len(subunits),
            "total": len(result.concepts),
        },
        "edge_counts": {
            "atom_id_edges": len(result.edges),
            "narrative_edges_raw": len(result.narrative_edges_raw),
        },
        "school_level_university_atoms": univ,
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


def _graph_json_to_result(path: Path) -> TransformResult:
    """graph.json(transform-v1 산출) → TransformResult(원자·엣지 모델 복원).

    dump는 `use_enum_values=True`라 enum이 문자열이지만 Pydantic이 enum 값으로 재구성한다.
    narrative_edges_raw는 그래프 적재 대상이 아니나 라운드트립 보존을 위해 복원한다(load는 미적재).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    concepts = [AtomConcept(**record) for record in payload.get("concepts", [])]
    edges = [AtomEdge(**record) for record in payload.get("edges", [])]
    return TransformResult(
        concepts=concepts,
        edges=edges,
        narrative_edges_raw=list(payload.get("narrative_edges_raw", [])),
    )


@app.command()
def load(
    graph: Annotated[
        Path,
        typer.Option("--graph", "-g", help="transform-v1이 만든 graph.json 경로."),
    ],
    database: Annotated[
        str | None,
        typer.Option("--database", help="대상 Neo4j DB명(멀티-DB 환경). 생략 시 기본 DB."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """graph.json → Neo4j 멱등 적재(Phase 2c). 접속은 env 전용(시크릿 하드코딩 금지).

    적재는 멱등(MERGE)이라 재실행해도 노드·엣지 수가 불변이다. 구 437 개념 그래프와 별개 라벨
    (`:Atom`·`:ATOM_PREREQUISITE`)로 additive 적재한다. 접속 자격은 NEO4J_URI·NEO4J_USER·
    NEO4J_PASSWORD env에서만 읽는다(CLAUDE.md 보안).
    """
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    # neo4j 드라이버 사전체크(미설치 시 친절 안내 — find_spec은 import 부작용 없음).
    if find_spec("neo4j") is None:
        typer.echo(
            "[!] neo4j 드라이버가 없습니다 — `pip install -e '.[neo4j]'` 후 재시도하세요.",
            err=True,
        )
        raise typer.Exit(code=3)

    if not graph.exists():
        typer.echo(f"[!] graph.json 없음: {graph}", err=True)
        raise typer.Exit(code=2)

    # 지연 import(드라이버 사전체크 통과 후) — extra 미설치 환경에서 모듈 import 막지 않기 위함.
    from data_pipeline.atom_graph.load import connect_driver, load_graph

    try:
        driver = connect_driver()
    except ValueError as exc:
        # 접속 env 누락 — 시크릿 안내(절대 하드코딩 금지).
        typer.echo(f"[!] {exc}", err=True)
        raise typer.Exit(code=2) from exc

    result = _graph_json_to_result(graph)
    try:
        report = load_graph(result, driver=driver, database=database)
    finally:
        driver.close()

    print(f"[적재] {report.summary()}")
    print(
        "[멱등] MERGE 기반 — 재실행해도 노드·엣지 수 불변. "
        f"노드 {report.nodes_merged}개·엣지 {report.edges_merged}개."
    )


if __name__ == "__main__":  # pragma: no cover
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
