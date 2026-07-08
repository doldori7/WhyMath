"""strategy_graph validate 단위테스트 — 그래프 레벨 invariant.

hermetic: 모델 목록 → 검증(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.strategy_graph.models import STRATEGY_SLUGS, StrategyNode
from data_pipeline.strategy_graph.validate import validate_strategies

# slug → family(코퍼스와 동일 매핑·검증 픽스처용).
_FAMILY_OF = {
    "specialize": "reduction",
    "work_backward": "reduction",
    "analogy": "reduction",
    "reformulate": "transformation",
    "auxiliary_construction": "transformation",
    "pattern_seeking": "exploration",
    "case_exhaustion": "exploration",
    "contradiction": "indirect",
}


def _node(slug: str, family: str | None = None) -> StrategyNode:
    return StrategyNode(
        strategy_id=f"strategy.{slug}",
        name_ko="전략",
        family=family or _FAMILY_OF[slug],
        description="인지행동 기준 자체작성 설명.",
    )


def _full_eight() -> list[StrategyNode]:
    return [_node(slug) for slug in STRATEGY_SLUGS]


def test_valid_graph_passes() -> None:
    """정확히 8·slug 집합 일치·family 유효 → error 0(PASS)."""
    report = validate_strategies(_full_eight())
    assert report.success, report.report_text()
    assert report.errors == []
    assert report.node_count == 8


def test_wrong_count_errors() -> None:
    """8개가 아니면 strategy_count error(누락·closed 택소노미 위반)."""
    report = validate_strategies(_full_eight()[:7])
    rules = {i.rule for i in report.errors}
    assert "strategy_count" in rules
    assert "strategy_slug_set" in rules  # 누락 slug도 감지
    assert not report.success


def test_slug_set_mismatch_errors() -> None:
    """미승인 slug가 섞이면 strategy_slug_set error(STRATEGY_SLUGS 불일치)."""
    nodes = _full_eight()[:-1] + [_node("contradiction", "indirect")]  # contradiction 대체 유지
    nodes[-1] = StrategyNode(
        strategy_id="strategy.bogus",
        name_ko="가짜",
        family="reduction",
        description="STRATEGY_SLUGS 밖의 미승인 slug.",
    )
    report = validate_strategies(nodes)
    rules = {i.rule for i in report.errors}
    assert "strategy_slug_set" in rules
    assert not report.success


def test_duplicate_slug_errors() -> None:
    """slug 중복 → strategy_slug_unique error(join 붕괴)."""
    nodes = _full_eight()
    nodes[1] = _node("specialize")  # specialize 중복(work_backward 자리)
    report = validate_strategies(nodes)
    rules = {i.rule for i in report.errors}
    assert "strategy_slug_unique" in rules
    assert not report.success


def test_no_edge_array_on_nodes() -> None:
    """전략 노드 model_dump에 엣지 배열 키 부재(canonical-only·신규 엣지 타입 0)."""
    for node in _full_eight():
        dumped = node.model_dump()
        for forbidden in ("edges", "prerequisites", "related", "prompt"):
            assert forbidden not in dumped
