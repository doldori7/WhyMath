"""strategy_graph transform 단위테스트 — 정형화·skip 기록.

hermetic: dict 입력 → 모델 정형화(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.strategy_graph.transform import transform_strategies


def _rec(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "strategy_id": "strategy.specialize",
        "name_ko": "특수화",
        "family": "reduction",
        "description": "특수값으로 좁혀 실마리를 얻고 원 문제로 되돌린다.",
    }
    base.update(overrides)
    return base


def test_transforms_valid_records() -> None:
    """유효 레코드 정형화·provenance 카운트."""
    result = transform_strategies(
        [_rec(), _rec(strategy_id="strategy.reformulate", family="transformation")]
    )
    assert len(result.strategies) == 2
    assert result.skipped == []
    assert result.provenance["strategies"] == 2
    assert result.provenance["families"] == 2


def test_invalid_record_skipped_not_dropped() -> None:
    """검증 실패 행은 조용히 누락되지 않고 skip 사유 기록(형식 위반·미승인 family·빈 설명)."""
    result = transform_strategies(
        [
            _rec(),
            _rec(strategy_id="BADID"),  # 형식 위반
            _rec(strategy_id="strategy.x", family="heuristic"),  # 미승인 family
            _rec(strategy_id="strategy.y", description=""),  # 빈 description
        ]
    )
    assert len(result.strategies) == 1
    assert len(result.skipped) == 3
