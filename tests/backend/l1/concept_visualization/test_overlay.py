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


def test_seed_corpus_covers_all_four_classes() -> None:
    """대표 시드 코퍼스가 4분류(직접/동적/부분/추상)를 전부 실증한다(end-to-end 판별 존재)."""
    records = load_concept_visualization_from_json(_SEED)
    covered = {r.visualizability for r in records}
    assert covered == set(Visualizability)
    # 모든 시드 code는 concept_graph_v1 형식({TRACK}-{AREA}-{NNN}).
    assert all("-" in r.code for r in records)
