"""수식 메타 프로젝션 적재 CLI — `whymath_backend.l1.formula_graph.populate`.

data-pipeline 산출 `graph.json`(canonical 수식 노드)의 안전 메타를 backend `formula_node` 테이블에
formula_id 키로 멱등 upsert한다(검색 enrichment·필터·후속 5b 수식 참조 백킹). `l1/problem_type_
graph.populate`의 수식 짝 — 임베딩·Neo4j 없이 *메타 프로젝션 1종*만 적재한다.

전제: 마이그레이션 head 적용된 실 PG 도달(`formula_node` 테이블) + `graph.json` 존재
(`python -m data_pipeline.formula_graph transform-v1 -o ...`로 생성). 자격증명은 env(시크릿 0).

CI hermetic: 이 모듈 import만으로는 PG 연결이 없다(엔진 지연). 실제 적재는 CLI 실행 또는 통합
테스트에서만.

사용:
    python -m whymath_backend.l1.formula_graph.populate \
        --graph data/corpus/formula_graph_v1/graph.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.config import get_settings
from whymath_backend.l1.formula_graph.formula_node_projection import (
    load_formulas_from_graph_json,
    populate_formula_nodes,
)

# graph.json 기본 경로(transform-v1 --output-dir 관례). 명시 --graph로 오버라이드.
_DEFAULT_GRAPH_PATH = Path("data/corpus/formula_graph_v1/graph.json")


def main(argv: list[str] | None = None) -> int:
    """graph.json 수식 노드를 `formula_node` 프로젝션에 멱등 적재하고 행 수 출력(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 오류). 적재 건수를 stdout으로 보고한다.
    """
    parser = argparse.ArgumentParser(
        prog="whymath-formula-populate",
        description="수식 graph.json → formula_node 메타 프로젝션 멱등 적재(Phase 5a).",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=_DEFAULT_GRAPH_PATH,
        help=f"formula_graph transform-v1 산출 graph.json 경로(기본 {_DEFAULT_GRAPH_PATH}).",
    )
    args = parser.parse_args(argv)

    graph_path: Path = args.graph
    if not graph_path.exists():
        print(
            f"graph.json 없음: {graph_path} — transform-v1 산출을 먼저 생성하세요 "
            "(`python -m data_pipeline.formula_graph transform-v1 -o ...`)."
        )
        return 2

    settings = get_settings()
    records = load_formulas_from_graph_json(graph_path)
    count = populate_formula_nodes(records, settings=settings)
    print(f"수식 메타 프로젝션 적재 완료: {count}건 (graph={graph_path}).")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(통합·운영 실행 전용)
    raise SystemExit(main())
