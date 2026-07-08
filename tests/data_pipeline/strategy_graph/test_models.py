"""strategy_graph models 단위테스트 — StrategyNode 검증(형식·family·필수·extra forbid).

hermetic: 모델 생성만(DB·네트워크 불요).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.strategy_graph.models import (
    STRATEGY_FAMILIES,
    STRATEGY_ID_PATTERN,
    STRATEGY_SLUGS,
    StrategyNode,
)


def _valid(**overrides: object) -> StrategyNode:
    base: dict[str, object] = {
        "strategy_id": "strategy.work_backward",
        "name_ko": "역방향 공략",
        "family": "reduction",
        "description": "목표에서 거슬러 올라가며 풀이 경로를 설계한다.",
    }
    base.update(overrides)
    return StrategyNode(**base)  # type: ignore[arg-type]


def test_valid_strategy() -> None:
    """유효 전략 — 필수 필드·기본값(standard_codes=[])."""
    node = _valid()
    assert node.strategy_id == "strategy.work_backward"
    assert node.family == "reduction"
    assert node.standard_codes == []


def test_strategy_id_pattern() -> None:
    """strategy_id는 'strategy.<slug>' 형식(언더스코어·하이픈 허용·대문자/공백 거부)."""
    assert STRATEGY_ID_PATTERN.match("strategy.specialize")
    assert STRATEGY_ID_PATTERN.match("strategy.work_backward")
    assert STRATEGY_ID_PATTERN.match("strategy.case-split")
    for bad in ("Strategy.x", "strategy.", "strategy.X", "ptype.x", "strategy. x", "strategy._x"):
        with pytest.raises(ValidationError):
            _valid(strategy_id=bad)


def test_family_whitelist() -> None:
    """family는 STRATEGY_FAMILIES 4종만 허용(미승인 family 거부)."""
    assert set(STRATEGY_FAMILIES) == {"reduction", "transformation", "exploration", "indirect"}
    for fam in STRATEGY_FAMILIES:
        assert _valid(family=fam).family == fam
    for bad in ("REDUCTION", "heuristic", "", "backward"):
        with pytest.raises(ValidationError):
            _valid(family=bad)


def test_required_fields_nonempty() -> None:
    """name_ko·family·description은 비어있으면 거부."""
    for field in ("name_ko", "description"):
        with pytest.raises(ValidationError):
            _valid(**{field: ""})


def test_extra_forbidden() -> None:
    """extra='forbid' — 미정의 키(엣지 등) 유입 차단."""
    with pytest.raises(ValidationError):
        _valid(edges=["strategy.analogy"])  # 엣지 배열은 노드에 두지 않음


def test_slug_constant_is_eight() -> None:
    """STRATEGY_SLUGS는 정확히 8개(closed 택소노미)."""
    assert len(STRATEGY_SLUGS) == 8
    assert len(set(STRATEGY_SLUGS)) == 8
