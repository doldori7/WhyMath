"""수식 그래프 정형화 — `formulas.jsonl`(자체작성) → `FormulaNode` 모델 목록.

입력이 자체작성 jsonl이라 별도 extract 단계가 없다(canonical 수식이 우리 자산). 각 raw 레코드를
`FormulaNode`로 구성하며(Pydantic 검증), 실패 행은 조용히 넘기지 않고 `skipped`에 사유를 기록한다
(CLAUDE.md 신뢰 원칙). problem_type_graph transform의 `TransformResult`(모델 목록 + skipped +
provenance 카운트) 패턴을 미러한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from data_pipeline.formula_graph.models import FormulaNode


@dataclass(frozen=True, slots=True)
class TransformResult:
    """정형화 산출 — 수식 노드 목록 + skip 사유 + provenance 카운트."""

    formulas: list[FormulaNode]
    skipped: list[str] = field(default_factory=list)
    provenance: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """한 줄 요약(정형화 카운트)."""
        families = sorted({f.family for f in self.formulas})
        return (
            f"정형화: 수식 {len(self.formulas)}개, family {len(families)}개, "
            f"skip {len(self.skipped)}건"
        )


def transform_formulas(records: list[dict[str, object]]) -> TransformResult:
    """raw 수식 레코드 목록 → `FormulaNode` 정형화(Pydantic 검증·실패 행 skip 기록).

    각 레코드를 `FormulaNode(**record)`로 구성한다 — `extra="forbid"`·형식 검증(formula_id 패턴·
    latex/dsl 비어있지 않음)·필수 누락은 `ValidationError`로 잡아 `skipped`에 사유를 남긴다(조용한
    누락 금지). 중복 formula_id는 여기서 막지 않는다(`validate_formulas` 몫).
    """
    formulas: list[FormulaNode] = []
    skipped: list[str] = []
    families: set[str] = set()
    with_signature = 0
    for i, record in enumerate(records):
        try:
            node = FormulaNode(**record)  # type: ignore[arg-type]
        except ValidationError as exc:
            fid = record.get("formula_id", f"<index {i}>")
            skipped.append(f"{fid}: {exc.error_count()}개 검증 오류")
            continue
        formulas.append(node)
        families.add(node.family)
        if node.canonical_signature is not None:
            with_signature += 1
    provenance = {
        "formulas": len(formulas),
        "families": len(families),
        "with_signature": with_signature,
    }
    return TransformResult(formulas=formulas, skipped=skipped, provenance=provenance)


__all__ = ["TransformResult", "transform_formulas"]
