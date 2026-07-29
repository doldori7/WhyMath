"""권장 시각화 양식 Overlay 조회·로더 단위테스트 (슬88·ARCH-14 ③).

`get_recommended_visual_styles`(async·fake 세션)·`load_concept_visual_style_from_json`(시드 파싱).
hermetic(DB 없이 fake 세션·파일 파싱만·`concept_visualization` overlay 테스트 미러).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.l1.concept_visual_style import (
    ConceptVisualStyleRecord,
    get_recommended_visual_styles,
    load_concept_visual_style_from_json,
)
from whymath_backend.schema.enums import VisualizationStyle


class _FakeRow:
    def __init__(self, styles: list[VisualizationStyle]) -> None:
        self.recommended_styles = styles


class _FakeSession:
    """`session.get(ConceptVisualStyle, code)`만 모사 — code→양식 배열 맵."""

    def __init__(self, styles: dict[str, list[VisualizationStyle]]) -> None:
        self._styles = styles

    async def get(self, model: object, key: object) -> object:
        v = self._styles.get(str(key))
        return _FakeRow(v) if v is not None else None


@pytest.mark.asyncio
async def test_get_recommended_visual_styles_hit_and_miss() -> None:
    """태깅된 code는 양식 배열 반환, 미태깅 code는 빈 배열(하위호환)."""
    session = _FakeSession(
        {"TRIG-PERIOD": [VisualizationStyle.단위원, VisualizationStyle.함수그래프]}
    )
    hit = await get_recommended_visual_styles(session, "TRIG-PERIOD")  # type: ignore[arg-type]
    miss = await get_recommended_visual_styles(session, "UNKNOWN")  # type: ignore[arg-type]
    assert hit == [VisualizationStyle.단위원, VisualizationStyle.함수그래프]
    assert miss == []


@pytest.mark.asyncio
async def test_get_recommended_visual_styles_normalizes_str_values() -> None:
    """행이 한글 문자열 값을 담고 있어도 VisualizationStyle enum으로 정규화한다(방어적 복원)."""
    session = _FakeSession({"ALG-QUAD": ["함수그래프"]})  # type: ignore[dict-item]
    styles = await get_recommended_visual_styles(session, "ALG-QUAD")  # type: ignore[arg-type]
    assert styles == [VisualizationStyle.함수그래프]
    assert all(isinstance(s, VisualizationStyle) for s in styles)


def test_loader_parses_records_and_skips_bad() -> None:
    """로더는 code+양식 배열 항목을 레코드로, 어휘 밖 원소·code 누락·빈 유효 배열을 건너뛴다."""
    payload = {
        "entries": [
            {"code": "A", "recommended_styles": ["단위원", "함수그래프"]},
            {"code": "B", "recommended_styles": ["잘못된값"]},  # 유효 원소 0 → skip
            {"recommended_styles": ["수직선"]},  # code 없음 → skip
            {"code": "C", "recommended_styles": ["수형도", "없는양식"]},  # 어휘 밖 원소만 제거
            {"code": "D", "recommended_styles": "수직선"},  # 배열 아님 → skip
        ]
    }
    tmp = Path(__file__).with_name("_tmp_style.json")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    try:
        records = load_concept_visual_style_from_json(tmp)
    finally:
        tmp.unlink()
    assert records == [
        ConceptVisualStyleRecord(
            code="A",
            recommended_styles=(VisualizationStyle.단위원, VisualizationStyle.함수그래프),
        ),
        ConceptVisualStyleRecord(code="C", recommended_styles=(VisualizationStyle.수형도,)),
    ]
