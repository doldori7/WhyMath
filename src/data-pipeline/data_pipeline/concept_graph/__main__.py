"""개념 그래프 CLI — seed(단계 3) · validate(단계 6) · load(Neo4j, 후속 Phase 가드).

사용:
    python -m data_pipeline.concept_graph seed \
        --ncic data/ncic/standards.json --domain-filter 미적분 \
        --output-dir data/concept_graph/seed/
    python -m data_pipeline.concept_graph validate \
        --concepts data/concept_graph/seed/concepts.csv \
        --edges data/concept_graph/seed/edges.csv
    python -m data_pipeline.concept_graph load ...   # Neo4j — 후속 Phase(가드)

seed는 NCIC 산출물에서 *후보* 노드·엣지 CSV를 만든다(전문가가 표기·관계·근거 채움).
validate는 *채워진* CSV를 strict 모델로 파싱해 §5 그래프 invariant를 점검한다.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from data_pipeline.concept_graph.idmap import build_id_map, to_csv_rows
from data_pipeline.concept_graph.models import SOURCE_CITATION, Concept, ConceptEdge
from data_pipeline.concept_graph.seed import (
    seed_concepts,
    seed_edges,
    write_concepts_csv,
    write_edges_csv,
)
from data_pipeline.concept_graph.transform import TransformResult, transform_dataset
from data_pipeline.concept_graph.validate import validate_dataset, validate_graph
from data_pipeline.ncic.models import AchievementStandardCollection

app = typer.Typer(
    name="whymath-concept-graph",
    help="개념 연결 그래프 — NCIC 성취기준 시드 생성·검증(자체 구축 자산).",
    rich_markup_mode=None,
    no_args_is_help=False,
    add_completion=False,
)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _split_list(cell: str) -> list[str]:
    """';'-구분 CSV 셀 → 리스트(빈 셀 → [])."""
    return [item for item in cell.split(";") if item]


@app.command()
def seed(
    ncic: Annotated[
        Path,
        typer.Option("--ncic", "-n", help="crawl이 만든 standards.json 경로."),
    ],
    domain_filter: Annotated[
        str | None,
        typer.Option("--domain-filter", "-d", help="과목/영역 부분문자열 필터(예 '미적분')."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="concepts.csv·edges.csv 저장 디렉토리."),
    ] = Path("data/concept_graph/seed"),
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """NCIC 성취기준 → 후보 개념·prerequisite 엣지 CSV(전문가 작성용 빈칸 포함)."""
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    if not ncic.exists():
        typer.echo(f"[!] standards.json 없음: {ncic}", err=True)
        raise typer.Exit(code=2)

    collection = AchievementStandardCollection.model_validate_json(ncic.read_text(encoding="utf-8"))
    concept_rows = seed_concepts(collection.standards, domain_filter=domain_filter)
    edge_rows = seed_edges(collection.standards, domain_filter=domain_filter)
    if not concept_rows:
        typer.echo("[!] 후보 개념 0개 — domain-filter 또는 입력을 확인하세요.", err=True)
        raise typer.Exit(code=2)

    n_concepts = write_concepts_csv(concept_rows, output_dir / "concepts.csv")
    n_edges = write_edges_csv(edge_rows, output_dir / "edges.csv")
    print(f"[시드] 후보 개념 {n_concepts}개 → {output_dir / 'concepts.csv'}")
    print(f"[시드] 후보 prerequisite 엣지 {n_edges}개 → {output_dir / 'edges.csv'}")
    print(
        "\n[다음 단계] 단계 4 — 전문가가 표기(한·영·일)·6종 관계·strength·evidence를 채운 뒤\n"
        "  python -m data_pipeline.concept_graph validate --concepts ... --edges ..."
    )


def _read_concepts_csv(path: Path) -> tuple[list[Concept], list[str]]:
    """채워진 concepts.csv → Concept 목록 + 파싱 실패 메시지(행별 ValidationError 흡수)."""
    concepts: list[Concept] = []
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                concepts.append(
                    Concept(
                        concept_id=row["concept_id"],
                        name_ko=row["name_ko"],
                        name_en=row["name_en"],
                        name_ja=row["name_ja"],
                        domain=row["domain"],
                        grade_band_hint=row.get("grade_band_hint") or None,
                        prerequisite_concept_ids=_split_list(
                            row.get("prerequisite_concept_ids", "")
                        ),
                        misconception_codes=_split_list(row.get("misconception_codes", "")),
                        visualization_card_keys=_split_list(row.get("visualization_card_keys", "")),
                        standard_codes=_split_list(row.get("standard_codes", "")),
                        notes=row.get("notes") or None,
                    )
                )
            except ValidationError as exc:
                errors.append(
                    f"concept {row.get('concept_id', '?')}: {exc.error_count()}개 검증 오류"
                )
    return concepts, errors


def _read_edges_csv(path: Path) -> tuple[list[ConceptEdge], list[str]]:
    """채워진 edges.csv → ConceptEdge 목록 + 파싱 실패 메시지."""
    edges: list[ConceptEdge] = []
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ref = f"{row.get('src_concept_id', '?')}→{row.get('dst_concept_id', '?')}"
            try:
                edges.append(
                    ConceptEdge(
                        src_concept_id=row["src_concept_id"],
                        dst_concept_id=row["dst_concept_id"],
                        relation=row["relation"],  # type: ignore[arg-type]
                        strength=float(row["strength"]),
                        evidence=row["evidence"],
                        evidence_source=row["evidence_source"],  # type: ignore[arg-type]
                    )
                )
            except (ValidationError, ValueError) as exc:
                errors.append(f"edge {ref}: {type(exc).__name__}")
    return edges, errors


@app.command()
def validate(
    concepts: Annotated[
        Path,
        typer.Option("--concepts", "-c", help="채워진 concepts.csv 경로."),
    ],
    edges: Annotated[
        Path,
        typer.Option("--edges", "-e", help="채워진 edges.csv 경로."),
    ],
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """채워진 CSV를 strict 모델로 파싱해 §5 그래프 invariant 검증."""
    _setup_logging(verbose)
    for label, p in (("concepts", concepts), ("edges", edges)):
        if not p.exists():
            typer.echo(f"[!] {label} CSV 없음: {p}", err=True)
            raise typer.Exit(code=2)

    parsed_concepts, c_errors = _read_concepts_csv(concepts)
    parsed_edges, e_errors = _read_edges_csv(edges)
    parse_errors = c_errors + e_errors

    report = validate_graph(parsed_concepts, parsed_edges)
    print(f"[검증] {report.summary()}")
    if parse_errors:
        print(f"[검증] 파싱 실패 {len(parse_errors)}건 (전문가 미작성·형식 오류):")
        for msg in parse_errors[:10]:
            print(f"  - {msg}")
    for issue in report.issues[:20]:
        print(f"  [{issue.severity}] {issue.rule} | {issue.ref} | {issue.detail}")

    if parse_errors or not report.success:
        raise typer.Exit(code=1)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """jsonl 파일 → dict 목록(빈 줄 무시)."""
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


@app.command(name="transform-v1")
def transform_v1(
    corpus_dir: Annotated[
        Path,
        typer.Option(
            "--corpus-dir",
            "-i",
            help="데이터셋 v1 디렉토리(concepts.jsonl·prerequisite_edges.jsonl 등 5종).",
        ),
    ] = Path("data/corpus/concept_graph_v1"),
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="graph.json·id_map.csv 저장 디렉토리(생략 시 저장 안 함, 검증만).",
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="DEBUG 로그.")] = False,
) -> None:
    """데이터셋 v1(5종 jsonl) → 확장 Concept/ConceptEdge 정형화 + §5 그래프 검증.

    무저장소 슬라이스 1: Neo4j/PG 적재는 하지 않는다(--output-dir 주면 graph.json 백업만).
    flashcards·intl은 raw 패스스루로 보존한다(L6/국제트랙은 후속). warning은 통과 처리(§3),
    error 또는 정형화 skip 발생 시 비정상 종료.
    """
    _setup_logging(verbose)
    print(SOURCE_CITATION)
    print()

    if not corpus_dir.is_dir():
        typer.echo(f"[!] 데이터셋 디렉토리 없음: {corpus_dir}", err=True)
        raise typer.Exit(code=2)
    concepts_path = corpus_dir / "concepts.jsonl"
    edges_path = corpus_dir / "prerequisite_edges.jsonl"
    for label, p in (("concepts.jsonl", concepts_path), ("prerequisite_edges.jsonl", edges_path)):
        if not p.exists():
            typer.echo(f"[!] {label} 없음: {p}", err=True)
            raise typer.Exit(code=2)

    flashcards_path = corpus_dir / "flashcards.jsonl"
    intl_path = corpus_dir / "ccss_only_intl.jsonl"

    result = transform_dataset(
        concept_records=_read_jsonl(concepts_path),
        edge_records=_read_jsonl(edges_path),
        flashcard_records=_read_jsonl(flashcards_path) if flashcards_path.exists() else None,
        intl_records=_read_jsonl(intl_path) if intl_path.exists() else None,
    )
    report = validate_dataset(result)

    print(f"[정형화] {result.summary()}")
    if result.skipped:
        print(f"[정형화] skip {len(result.skipped)}건:")
        for msg in result.skipped[:10]:
            print(f"  - {msg}")
    print(f"[검증] {report.report_text()}")

    if output_dir is not None:
        _write_graph_json(result, output_dir / "graph.json")
        _write_id_map_csv(_read_jsonl(concepts_path), output_dir / "id_map.csv")
        print(f"[저장] {output_dir / 'graph.json'} · {output_dir / 'id_map.csv'}")

    if result.skipped or not report.success:
        raise typer.Exit(code=1)


def _write_graph_json(result: TransformResult, path: Path) -> None:
    """정형화 산출(개념·엣지 + raw 패스스루) → graph.json 백업(검증·인계용).

    redaction 불변: Concept 모델에 description/formal_definition 슬롯이 없어 dump에 미포함.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_citation": SOURCE_CITATION,
        "concepts": [c.model_dump() for c in result.concepts],
        "edges": [e.model_dump() for e in result.edges],
        "flashcards_raw": result.passthrough_flashcards,
        "intl_raw": result.passthrough_intl,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_id_map_csv(concept_records: list[dict[str, object]], path: Path) -> None:
    """src_id → UC 매핑 테이블 → id_map.csv(검토·슬라이스 2 적재 입력)."""
    id_map = build_id_map(concept_records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["src_id", "concept_id"])
        writer.writeheader()
        writer.writerows(to_csv_rows(id_map))


@app.command()
def load(
    concepts: Annotated[
        Path | None, typer.Option("--concepts", "-c", help="검증 통과 concepts.csv.")
    ] = None,
    edges: Annotated[
        Path | None, typer.Option("--edges", "-e", help="검증 통과 edges.csv.")
    ] = None,
    neo4j_uri: Annotated[
        str, typer.Option("--neo4j-uri", help="Neo4j bolt URI.")
    ] = "bolt://localhost:7687",
) -> None:
    """Neo4j 적재 — 후속 Phase(가드).

    Neo4j 드라이버는 아직 의존성이 아니고, 적재는 *검증 통과한 전문가 작성 CSV*(단계 4~6)를
    선행 요구한다. 따라서 현재는 명령 표면만 두고 가드로 종료한다(load_to_postgres 스텁과 동일
    철학 — 실행 불가 DB 코드 대신 명확한 안내).
    """
    typer.echo(
        "[!] Neo4j 적재는 후속 Phase입니다 — neo4j 드라이버 의존성 추가 + 전문가 작성·검증\n"
        "    통과한 CSV(단계 4~6) 선행이 필요합니다. 현재는 seed/validate까지 지원합니다.",
        err=True,
    )
    raise typer.Exit(code=3)


if __name__ == "__main__":  # pragma: no cover
    try:
        app()
    except KeyboardInterrupt:
        print("\n[!] 사용자 중단", file=sys.stderr)
        sys.exit(130)
