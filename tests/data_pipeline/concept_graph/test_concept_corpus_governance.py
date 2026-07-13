"""개념 그래프 커밋 코퍼스 무결성 거버넌스 — 초인간 검증 S6(hermetic·DB 0).

정본: `docs/standards/superhuman_verification_standard.md` S6(상시성). 커밋된
`data/corpus/concept_graph_v1/`(개념·선수엣지)의 **구조 무결성을 DB 없이 상시(빠른 CI)
재검증**한다. 기존 개념 그래프 순환 검사는 (a) 합성 그래프 단위테스트(`test_validate.py`)
(b) Neo4j 통합 적재에만 있었고, **커밋된 실 코퍼스를 갓 `validate_dataset`으로 재검증**하는
hermetic 경로가 비어 있었다 — 손수 편집된 prerequisite_edges가 순환을 넣어도 상시 게이트가
못 잡던 갭. 이 테스트가 그 갭을 매 PR 닫는다.

*검증은 정본 파이프라인 재사용*(`transform_dataset`→`validate_dataset`) — 재구현 0.
"""

from __future__ import annotations

from data_pipeline.concept_graph.transform import transform_dataset
from data_pipeline.concept_graph.validate import validate_dataset


def test_committed_concept_corpus_validates_clean(
    concept_records: list[dict[str, object]],
    edge_records: list[dict[str, object]],
) -> None:
    """실 코퍼스(concepts.jsonl + prerequisite_edges.jsonl) → validate_dataset error 0.

    error에는 prerequisite_cycle·id 충돌 등 구조 붕괴가 포함된다(§5). 커밋된 코퍼스는
    항상 error 0이어야 한다 — 하나라도 있으면 학습 백본이 깨진 상태로 병합된 것.
    """
    result = transform_dataset(concept_records=concept_records, edge_records=edge_records)
    report = validate_dataset(result)
    assert report.errors == [], f"코퍼스 검증 error {len(report.errors)}건: {report.errors[:5]}"
    assert report.success is True


def test_committed_concept_corpus_has_no_cycle(
    concept_records: list[dict[str, object]],
    edge_records: list[dict[str, object]],
) -> None:
    """선수관계 순환 규칙(prerequisite_cycle)이 이슈에 나타나지 않는다(DAG 불변식)."""
    result = transform_dataset(concept_records=concept_records, edge_records=edge_records)
    report = validate_dataset(result)
    cycle_issues = [i for i in report.issues if i.rule == "prerequisite_cycle"]
    assert cycle_issues == [], f"순환 선수관계: {[i.ref for i in cycle_issues]}"
