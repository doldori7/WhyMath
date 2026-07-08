"""전략 그래프 정형화 — `strategies.jsonl`(자체작성) → `StrategyNode` 모델 목록.

입력이 자체작성 jsonl이라 별도 extract 단계가 없다(전략 택소노미가 우리 자산). 각 raw 레코드를
`StrategyNode`로 구성하며(Pydantic 검증), 실패 행은 조용히 넘기지 않고 `skipped`에 사유를 기록한다
(CLAUDE.md 신뢰 원칙). formula_graph transform의 `TransformResult`(모델 목록 + skipped +
provenance 카운트) 패턴을 미러한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from data_pipeline.strategy_graph.models import StrategyNode


@dataclass(frozen=True, slots=True)
class TransformResult:
    """정형화 산출 — 전략 노드 목록 + skip 사유 + provenance 카운트."""

    strategies: list[StrategyNode]
    skipped: list[str] = field(default_factory=list)
    provenance: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """한 줄 요약(정형화 카운트)."""
        families = sorted({s.family for s in self.strategies})
        return (
            f"정형화: 전략 {len(self.strategies)}개, family {len(families)}개, "
            f"skip {len(self.skipped)}건"
        )


def transform_strategies(records: list[dict[str, object]]) -> TransformResult:
    """raw 전략 레코드 목록 → `StrategyNode` 정형화(Pydantic 검증·실패 행 skip 기록).

    각 레코드를 `StrategyNode(**record)`로 구성한다 — `extra="forbid"`·형식 검증(strategy_id 패턴·
    family 화이트리스트·description 비어있지 않음)·필수 누락은 `ValidationError`로 잡아 `skipped`에
    사유를 남긴다(조용한 누락 금지). 중복 strategy_id·전략 수 불변식은 `validate_strategies` 몫이다.
    """
    strategies: list[StrategyNode] = []
    skipped: list[str] = []
    families: set[str] = set()
    for i, record in enumerate(records):
        try:
            node = StrategyNode(**record)  # type: ignore[arg-type]
        except ValidationError as exc:
            sid = record.get("strategy_id", f"<index {i}>")
            skipped.append(f"{sid}: {exc.error_count()}개 검증 오류")
            continue
        strategies.append(node)
        families.add(node.family)
    provenance = {
        "strategies": len(strategies),
        "families": len(families),
    }
    return TransformResult(strategies=strategies, skipped=skipped, provenance=provenance)


__all__ = ["TransformResult", "transform_strategies"]
