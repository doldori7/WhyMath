"""양식↔렌더 좌석 계약 게이트 — 백엔드 측 (VIZ-04).

공유 계약 `data/visual_style_contract.json`의 `styles` 키가 `VisualizationStyle` enum과 *정확히*
일치하는지, `status=="seated"` 집합이 `l4.visualization_policy._SEATED_STYLES`와 *정확히* 일치하는지
(JSON↔Python 이중 진실원 drift 방지), seated 항목의 `render_types`가 `data/render_contract.json`에서
실제 렌더 가능한(`web_adapter != null`) 타입의 부분집합인지 고정한다.

`tests/backend/schema/test_render_contract.py`(두 번째 화살표 — type → 렌더러) 답습 패턴 —
본 게이트는 첫 번째 화살표(양식 → type)를 봉인한다
(`docs/architecture/visualization_module_gap_review.md` §7.1 G1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l4.visualization_policy import _SEATED_STYLES, has_render_seat
from whymath_backend.schema.enums import VisualizationStyle, VisualizationType

# tests/backend/schema/ → parents[3] = 레포 루트(test_render_contract.py와 동일 기준).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_STYLE_FIXTURE = _PROJECT_ROOT / "data" / "visual_style_contract.json"
_RENDER_FIXTURE = _PROJECT_ROOT / "data" / "render_contract.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():  # pragma: no cover - fixture는 레포에 동봉
        pytest.skip(f"계약 fixture 없음: {path}")
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


_STYLE_CONTRACT = _load(_STYLE_FIXTURE)
_STYLES: dict[str, Any] = _STYLE_CONTRACT["styles"]
_RENDER_CONTRACT = _load(_RENDER_FIXTURE)
_RENDERERS: dict[str, Any] = _RENDER_CONTRACT["renderers"]


def test_contract_styles_match_visualization_style_exactly() -> None:
    """계약 styles 키 == VisualizationStyle enum 값(누락·잉여 0) — 완전성."""
    assert set(_STYLES) == {v.value for v in VisualizationStyle}


@pytest.mark.parametrize("style_value", sorted(_STYLES))
def test_each_style_has_required_fields(style_value: str) -> None:
    """각 양식은 render_types(list)·render_mode(str)·status(seated|unseated)·
    seat_owner(str|null)."""
    entry = _STYLES[style_value]
    assert isinstance(entry["render_types"], list)
    assert isinstance(entry["render_mode"], str) and entry["render_mode"]
    assert entry["status"] in {"seated", "unseated"}
    assert entry["seat_owner"] is None or isinstance(entry["seat_owner"], str)


def test_seated_status_matches_render_types_nonempty() -> None:
    """status=="seated"인 항목만 render_types가 비어있지 않다(반대도 성립 — 정합)."""
    for style_value, entry in _STYLES.items():
        if entry["status"] == "seated":
            assert entry["render_types"], f"{style_value}: seated인데 render_types 비어있음"
        else:
            assert not entry["render_types"], f"{style_value}: unseated인데 render_types 있음"


def test_json_seated_set_matches_python_seated_styles_constant() -> None:
    """JSON status=="seated" 집합 == Python `_SEATED_STYLES` — 이중 진실원 drift 방지(VIZ-04).

    이 모듈(`l4/visualization_policy`)은 순수 함수·hermetic 원칙이라 JSON을 직접 읽지 않고
    리터럴 상수로 좌석 집합을 박아둔다 — 그래서 계약 파일이 바뀌어도 상수가 안 바뀌면 이 테스트가
    조용히 놓치지 않고 즉시 red를 낸다(`render_contract.json`이 enum과 cross-check하는 것과 동형
    원리 — 이 저장소에 아직 없던 패턴이라 새로 도입).
    """
    json_seated = {VisualizationStyle(k) for k, v in _STYLES.items() if v["status"] == "seated"}
    assert json_seated == _SEATED_STYLES


@pytest.mark.parametrize(
    "style_value", sorted(k for k, v in _STYLES.items() if v["status"] == "seated")
)
def test_seated_render_types_are_actually_renderable(style_value: str) -> None:
    """seated 항목의 render_types가 render_contract.json에서 web_adapter != null인 타입의 부분집합.

    seated인데 렌더 불가 타입(예: `animation_prerendered` — `web_adapter: null`)을 참조하면
    "좌석은 있다고 선언했는데 실제로는 렌더되지 않는다"는 자기모순이라 red — 계약 두 파일 간
    합류 지점을 봉인한다.
    """
    renderable_types = {t for t, entry in _RENDERERS.items() if entry["web_adapter"] is not None}
    for render_type in _STYLES[style_value]["render_types"]:
        assert (
            render_type in renderable_types
        ), f"{style_value}: render_types에 렌더 불가 타입 '{render_type}' 참조"
        assert render_type in {v.value for v in VisualizationType}


def test_has_render_seat_reuses_json_seated_set() -> None:
    """`has_render_seat`가 JSON이 seated로 선언한 양식에 True를 반환(교차 실측 — 재구현 아님)."""
    for style_value, entry in _STYLES.items():
        style = VisualizationStyle(style_value)
        expected = entry["status"] == "seated"
        assert has_render_seat([style]) is expected


def test_has_render_seat_true_if_any_style_seated() -> None:
    """권장 양식이 여러 개고 그중 하나만 seated면 True(one-of 의미론)."""
    assert has_render_seat([VisualizationStyle.수형도, VisualizationStyle.함수그래프]) is True
    assert has_render_seat([VisualizationStyle.수형도, VisualizationStyle.입체도형]) is False


def test_has_render_seat_empty_sequence_is_false() -> None:
    assert has_render_seat([]) is False
