"""렌더 선택 단일 진실원(invariant ⑩) 계약 게이트 — 백엔드 측.

공유 계약 `data/render_contract.json`의 `renderers` 키가 코어 `VisualizationType` enum과 *정확히*
일치하는지 고정한다(웹 측 `test/render_contract.test.js`는 각 type이 web_adapter로 dispatch되는지
검증 — 둘이 합쳐 "코어 type ↔ 웹 렌더러" drift를 막는다·notation_contract 선례).

이 게이트가 있으면 `VisualizationType`에 새 렌더 타입이 추가될 때 계약 파일도 함께 갱신하지 않으면
즉시 red → capability matrix가 코드(enum)와 계약(파일)에 이중으로 흩어져 drift하는 것을 차단한다.
`_SPEC_MODEL_BY_TYPE` 완전성 테스트(test_visualization.py)와 동형 패턴.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from whymath_backend.schema.enums import VisualizationType

# tests/backend/schema/ → parents[3] = 레포 루트(test_notation_contract.py와 동일 기준).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _PROJECT_ROOT / "data" / "render_contract.json"


def _load_contract() -> dict[str, Any]:
    if not _FIXTURE.exists():  # pragma: no cover - fixture는 레포에 동봉
        pytest.skip(f"렌더 계약 fixture 없음: {_FIXTURE}")
    loaded: dict[str, Any] = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return loaded


_CONTRACT = _load_contract()
_RENDERERS: dict[str, Any] = _CONTRACT["renderers"]


def test_contract_renderers_match_visualization_type_exactly() -> None:
    """계약 renderers 키 == VisualizationType enum 값(누락·잉여 0) — 단일 진실원 완전성."""
    assert set(_RENDERERS) == {v.value for v in VisualizationType}


@pytest.mark.parametrize("type_value", sorted(_RENDERERS))
def test_each_renderer_has_family_and_interactive(type_value: str) -> None:
    """각 type은 family(렌더러 계열·비어있지 않음)·interactive(bool)·web_adapter(str|null)."""
    entry = _RENDERERS[type_value]
    assert isinstance(entry["family"], list) and entry["family"], "family는 비어있지 않은 목록"
    assert isinstance(entry["interactive"], bool)
    assert entry["web_adapter"] is None or isinstance(entry["web_adapter"], str)


def test_animation_prerendered_is_non_interactive_and_unrendered_on_web() -> None:
    """animation_prerendered는 interactive=False(05 §5.2 '조작 불가')·웹 미렌더(web_adapter=null).

    코어 `Visualization._prerendered_not_interactive` 불변식과 정합 — 계약이 그 규약을 미러한다.
    """
    entry = _RENDERERS[VisualizationType.animation_prerendered.value]
    assert entry["interactive"] is False
    assert entry["web_adapter"] is None


def test_interactive_types_have_web_adapter() -> None:
    """interactive 3종(graph_2d·surface_3d·simulation)은 웹 렌더 어댑터를 가진다(미렌더 방지)."""
    for type_value, entry in _RENDERERS.items():
        if entry["interactive"]:
            assert entry["web_adapter"], f"{type_value}: interactive인데 web_adapter 없음"
