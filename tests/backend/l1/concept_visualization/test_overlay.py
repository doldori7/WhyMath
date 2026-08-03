"""시각화 가능성 Overlay 조회·로더 단위테스트 (플레이북 Part 5).

`get_visualizability`(async·fake 세션)·`load_concept_visualization_from_json`(시드 파싱)·시드 코퍼스
4분류 커버리지. hermetic(DB 없이 fake 세션·파일 파싱만).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.l1.concept_visualization import (
    ConceptVisualizabilityRecord,
    get_visualizability,
    load_concept_visualization_from_json,
)
from whymath_backend.schema.enums import Visualizability

_SEED = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "corpus"
    / "concept_visualization_v1"
    / "visualizability.json"
)


class _FakeRow:
    def __init__(self, v: Visualizability) -> None:
        self.visualizability = v


class _FakeSession:
    """`session.get(ConceptVisualization, code)`만 모사 — code→4분류 맵."""

    def __init__(self, viz: dict[str, Visualizability]) -> None:
        self._viz = viz

    async def get(self, model: object, key: object) -> object:
        v = self._viz.get(str(key))
        return _FakeRow(v) if v is not None else None


@pytest.mark.asyncio
async def test_get_visualizability_hit_and_miss() -> None:
    """태깅된 code는 4분류 반환, 미태깅 code는 None(하위호환)."""
    session = _FakeSession({"MID-FUN-010": Visualizability.직접})
    hit = await get_visualizability(session, "MID-FUN-010")  # type: ignore[arg-type]
    miss = await get_visualizability(session, "UNKNOWN")  # type: ignore[arg-type]
    assert hit is Visualizability.직접
    assert miss is None


def test_loader_parses_records_and_skips_bad() -> None:
    """로더는 code+4분류 항목을 레코드로, 어휘 밖·code 누락 항목은 건너뛴다."""
    payload = {
        "entries": [
            {"code": "A", "visualizability": "직접"},
            {"code": "B", "visualizability": "잘못된값"},  # 어휘 밖 → skip
            {"visualizability": "추상"},  # code 없음 → skip
            {"code": "C", "visualizability": "추상"},
        ]
    }
    tmp = Path(__file__).with_name("_tmp_viz.json")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    try:
        records = load_concept_visualization_from_json(tmp)
    finally:
        tmp.unlink()
    assert records == [
        ConceptVisualizabilityRecord(code="A", visualizability=Visualizability.직접),
        ConceptVisualizabilityRecord(code="C", visualizability=Visualizability.추상),
    ]


def test_seed_corpus_is_atom_backbone_aligned_abstract_only() -> None:
    """VIZ-05 재정렬 후 시드 코퍼스 — 추상 축 1건만, code는 원자 백본(atom_graph_v1) 형식.

    v1.1(7건 전부 레거시 concept_graph_v1 code)은 런타임 code 공간과 orphan 7/7이었다
    (docs/architecture/visualization_module_gap_review.md §7.2). 직접·동적·부분은 인지행동
    판정이라 억지 재태깅하지 않고 미태깅 존치했으므로(VIZ-01 acceptance③ 답습), 4분류 전부
    실증은 더 이상 이 코퍼스의 불변식이 아니다 — orphan 게이트(신설
    `tests/backend/l1/test_concept_visualization_orphan_gate.py`)가 대신 code 정합을 지킨다.
    """
    records = load_concept_visualization_from_json(_SEED)
    assert [r.visualizability for r in records] == [Visualizability.추상]
    # 원자 백본 code 형식({학년군}{과목}-{단원}-{소단원}-{세부}) — concept_graph_v1의
    # {TRACK}-{AREA}-{NNN} 형식과 다르다(둘 다 "-" 포함이라 그 자체는 구분자가 아님).
    assert records[0].code == "10공수2-02-07-1"
