"""원자 백본 코퍼스 → backend `concept`/`concept_edge` 적재 진입점(원자 Phase 1).

구 개념그래프 `populate.py`와 *별개* 진입점이다(원자 백본 전용·기존 적재 경로 무변경). 순서:
  ① concept 노드 전량 upsert(parent 없이) → ② parent_concept_id 2-pass 해소 → ③ 선수엣지 적재
  (code→UUID 해석·orphan skip). 엣지는 노드가 먼저 적재돼야 양끝 UUID가 잡히므로 ③은 ①②  다음.

멱등: 재실행 시 갱신(노드 UUID·엣지 edge_id 보존). sync 엔진은 슬3 좌석 재사용(신규 seam 0).

CLI: `python -m whymath_backend.l1.atom_graph.populate --graph data/corpus/atom_graph_v1/graph.json`
(접속은 `Settings.sync_database_url` env·자격증명 하드코딩 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.atom_graph.atom_backend_concept import (
    AtomBackendConceptStore,
    load_atom_concepts_from_graph_json,
    populate_atom_concepts,
)
from whymath_backend.l1.atom_graph.atom_backend_edge import (
    AtomBackendEdgeStore,
    load_atom_edges_from_graph_json,
    populate_atom_edges,
)


@dataclass(frozen=True, slots=True)
class AtomBackbonePopulateReport:
    """원자 백본 적재 결과 요약(운영 가시성·테스트 단언용)."""

    concepts_loaded: int
    parents_skipped: int
    edges_loaded: int
    edges_skipped: int


def populate_atom_backbone(
    graph_path: Path,
    *,
    settings: Settings | None = None,
    concept_store: AtomBackendConceptStore | None = None,
    edge_store: AtomBackendEdgeStore | None = None,
) -> AtomBackbonePopulateReport:
    """원자 코퍼스 graph.json을 backend `concept`/`concept_edge`에 멱등 적재(노드→parent→엣지).

    store 미주입 시 슬3 sync 엔진 재사용 store를 만든다(같은 settings 공유). 반환: 적재 리포트.
    """
    resolved = settings if settings is not None else get_settings()
    c_store = (
        concept_store if concept_store is not None else AtomBackendConceptStore(settings=resolved)
    )
    e_store = edge_store if edge_store is not None else AtomBackendEdgeStore(settings=resolved)

    concept_records = load_atom_concepts_from_graph_json(graph_path)
    concepts_loaded, parent_skipped = populate_atom_concepts(
        concept_records, settings=resolved, store=c_store
    )

    edge_records, _load_skipped = load_atom_edges_from_graph_json(graph_path)
    edges_loaded = populate_atom_edges(edge_records, settings=resolved, store=e_store)

    return AtomBackbonePopulateReport(
        concepts_loaded=concepts_loaded,
        parents_skipped=len(parent_skipped),
        edges_loaded=edges_loaded,
        edges_skipped=len(edge_records) - edges_loaded,
    )


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="원자 백본 코퍼스 → backend concept/concept_edge 멱등 적재"
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("data/corpus/atom_graph_v1/graph.json"),
        help="원자 코퍼스 graph.json 경로",
    )
    args = parser.parse_args()
    report = populate_atom_backbone(args.graph)
    print(
        f"[원자 백본 적재] concepts={report.concepts_loaded} "
        f"parent_skip={report.parents_skipped} "
        f"edges={report.edges_loaded} edge_skip={report.edges_skipped}"
    )


if __name__ == "__main__":  # pragma: no cover
    _main()


__all__ = ["AtomBackbonePopulateReport", "populate_atom_backbone"]
