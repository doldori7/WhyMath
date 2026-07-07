"""문제유형 메타 프로젝션 적재 CLI — `whymath_backend.l1.problem_type_graph.populate`.

data-pipeline 산출 `graph.json`(문제유형 노드)의 안전 메타를 backend `problem_type_node` 테이블에
problem_type_id 키로 멱등 upsert한다(검색 enrichment·필터·후속 문제 분류·추천 백킹).
`l1/skill_graph.populate`의 문제유형 그래프 짝 — 임베딩·Neo4j 없이 *메타 프로젝션 1종*만 적재한다.

전제: 마이그레이션 head 적용된 실 PG 도달(`problem_type_node` 테이블) + `graph.json` 존재
(`python -m data_pipeline.problem_type_graph transform-v1 -o ...`로 생성). 자격증명은 env(시크릿 0).

CI hermetic: 이 모듈 import만으로는 PG 연결이 없다(엔진 지연). 실제 적재는 CLI 실행 또는 통합
테스트에서만.

사용:
    python -m whymath_backend.l1.problem_type_graph.populate \
        --graph data/corpus/problem_type_graph_v1/graph.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.config import get_settings
from whymath_backend.l1.problem_type_graph.problem_type_node_projection import (
    load_problem_types_from_graph_json,
    populate_problem_type_nodes,
)

# graph.json 기본 경로(transform-v1 --output-dir 관례). 명시 --graph로 오버라이드.
_DEFAULT_GRAPH_PATH = Path("data/corpus/problem_type_graph_v1/graph.json")


def main(argv: list[str] | None = None) -> int:
    """graph.json 문제유형 노드를 `problem_type_node` 프로젝션에 멱등 적재하고 행 수 출력(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 오류). 적재 건수를 stdout으로 보고한다.
    """
    parser = argparse.ArgumentParser(
        prog="whymath-problem-type-populate",
        description="문제유형 graph.json → problem_type_node 메타 프로젝션 멱등 적재(Phase 3).",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=_DEFAULT_GRAPH_PATH,
        help=f"problem_type_graph transform-v1 산출 graph.json 경로(기본 {_DEFAULT_GRAPH_PATH}).",
    )
    args = parser.parse_args(argv)

    graph_path: Path = args.graph
    if not graph_path.exists():
        print(
            f"graph.json 없음: {graph_path} — transform-v1 산출을 먼저 생성하세요 "
            "(`python -m data_pipeline.problem_type_graph transform-v1 -o ...`)."
        )
        return 2

    settings = get_settings()
    records = load_problem_types_from_graph_json(graph_path)
    count = populate_problem_type_nodes(records, settings=settings)
    print(f"문제유형 메타 프로젝션 적재 완료: {count}건 (graph={graph_path}).")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(통합·운영 실행 전용)
    raise SystemExit(main())
