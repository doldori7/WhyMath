"""렌더 선택 단일 진실원(invariant ⑩) 계약 게이트 — 백엔드 측.

공유 계약 `data/render_contract.json`의 `renderers` 키가 코어 `VisualizationType` enum과 *정확히*
일치하는지 고정한다(웹 측 `test/render_contract.test.js`는 각 type이 web_adapter로 dispatch되는지
검증 — 둘이 합쳐 "코어 type ↔ 웹 렌더러" drift를 막는다·notation_contract 선례).

이 게이트가 있으면 `VisualizationType`에 새 렌더 타입이 추가될 때 계약 파일도 함께 갱신하지 않으면
즉시 red → capability matrix가 코드(enum)와 계약(파일)에 이중으로 흩어져 drift하는 것을 차단한다.
`_SPEC_MODEL_BY_TYPE` 완전성 테스트(test_visualization.py)와 동형 패턴.

VIZ-02 추가 축 — **생성기 ↔ 렌더 가능성**(`TestGeneratorOffersOnlyRenderableTypes`).
위 완전성 게이트(계약↔enum)도, 웹 vitest(dispatch)도 *"L3 생성기가 LLM에게 무엇을 제시하는가"*는
보지 않았다. 그 사각에서 `_SYSTEM_PROMPT`가 `animation_prerendered`(계약상 `web_adapter: null`·
Manim 구현 0건)를 유효 선택지로 제시했고, 생성된 명세는 어디서도 렌더되지 않았다(웹 조용한 미렌더·
LLM 비용 낭비·caption이 예고한 시각화 불이행 — `visualization_module_gap_review.md` §3 D3).
이 클래스가 그 축을 닫는다: **생성기가 제시하는 타입 집합 ⊆ 렌더 가능 타입 집합**(그리고 누락·
dead 예시가 없도록 양방향 등식).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l3.visualization import (
    _SPEC_EXAMPLES,
    build_visualization_prompt,
    renderable_visualization_types,
    reset_render_contract_cache,
)
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


# ──────────────────────────────────────────────────────────────────────────
# VIZ-02 — 생성기가 제시하는 타입 ⊆ 렌더 가능 타입
# ──────────────────────────────────────────────────────────────────────────
# 계약에서 직접(로더를 거치지 않고) 계산한 렌더 가능 집합 — 로더의 *독립 대조군*이다.
# 로더가 같은 파일을 읽으므로 로더 버그가 이 기준까지 오염시키지는 못한다.
_RENDERABLE_BY_CONTRACT = frozenset(t for t, e in _RENDERERS.items() if e["web_adapter"])
_UNRENDERABLE_BY_CONTRACT = frozenset(_RENDERERS) - _RENDERABLE_BY_CONTRACT


def _offered_types(system_prompt: str) -> set[str]:
    """프로덕션 시스템 프롬프트가 *실제로 이름을 부른* 타입 집합.

    코드 상수가 아니라 LLM에게 나가는 문자열 자체를 본다 — "로더는 파생했는데 프롬프트는
    여전히 하드코딩"이라는 상태를 잡아내려면 최종 산출물을 재료로 삼아야 한다.
    """
    return {v.value for v in VisualizationType if v.value in system_prompt}


class TestGeneratorOffersOnlyRenderableTypes:
    """L3 생성기가 제시하는 타입 집합 == 계약상 렌더 경로가 있는 타입 집합.

    ⊆(렌더 불가 제시 금지)와 ⊇(렌더 가능한데 미제시 금지)를 모두 건다. 전자가 이 태스크의
    본체이고, 후자는 계약에 렌더러가 늘었는데(예: `S4-03` 기하) 생성기가 따라오지 않는 반대
    방향 drift를 막는다.
    """

    @pytest.fixture(autouse=True)
    def _fresh_contract_cache(self) -> Any:
        """계약 캐시를 앞뒤로 비운다 — 이 클래스는 *디스크의 계약*을 판정 대상으로 삼는다.

        다른 테스트가 남긴 캐시(또는 이 클래스가 남기는 캐시)가 판정에 새지 않게 한다
        (전역 오염으로 순서 의존이 생기는 것이 이 저장소의 실측 실패 유형이다).
        """
        reset_render_contract_cache()
        yield
        reset_render_contract_cache()

    def test_loader_derives_renderable_set_from_contract(self) -> None:
        """로더가 `web_adapter != null`을 렌더 가능성 술어로 쓰는지 — 파생 규칙 동결."""
        assert set(renderable_visualization_types()) == set(_RENDERABLE_BY_CONTRACT)

    def test_renderable_set_is_not_empty(self) -> None:
        """렌더 가능 0건이면 생성 자체가 무의미하다 — 하한을 명시적으로 둔다(측정 실패 ≠ 통과)."""
        assert _RENDERABLE_BY_CONTRACT, "계약에 web_adapter를 가진 type이 하나도 없다"

    def test_prompt_offers_exactly_the_renderable_types(self) -> None:
        """프로덕션 프롬프트가 부르는 타입 == 렌더 가능 타입(누락 0·잉여 0)."""
        system_prompt, _ = build_visualization_prompt("이차함수의 그래프", "고1")
        assert _offered_types(system_prompt) == set(_RENDERABLE_BY_CONTRACT)

    @pytest.mark.parametrize("type_value", sorted(_UNRENDERABLE_BY_CONTRACT))
    def test_prompt_never_names_an_unrenderable_type(self, type_value: str) -> None:
        """렌더 경로가 없는 타입(현재 `animation_prerendered`)은 프롬프트에 등장하지 않는다.

        스키마·enum·계약의 좌석은 그대로 존치한다 — 죽이는 것은 *생성 경로*뿐이다.
        """
        system_prompt, _ = build_visualization_prompt("극한의 개념", "고2")
        assert type_value not in system_prompt, (
            f"{type_value}는 계약상 web_adapter=null(렌더 경로 없음)인데 생성기가 LLM에 "
            "제시하고 있다 — 생성해도 렌더될 수 없다(LLM 비용 낭비·caption 불이행)."
        )

    def test_spec_examples_cover_exactly_the_renderable_types(self) -> None:
        """프롬프트의 type별 spec 예시 키 == 렌더 가능 타입(dead 예시 0·누락 0).

        렌더 불가 타입의 예시가 남아 있으면 dead code이고, 렌더 가능한데 예시가 없으면 LLM이
        그 type의 spec을 못 채운다. 계약 로드 실패 시의 강등값이 이 키 집합이므로, 이 등식이
        곧 "강등해도 계약과 같은 답"의 근거다.
        """
        assert set(_SPEC_EXAMPLES) == set(_RENDERABLE_BY_CONTRACT)

    def test_renderable_types_are_all_interactive(self) -> None:
        """렌더 가능 타입은 전부 조작형 — 프롬프트의 'interactive=true' 지시와 계약의 정합."""
        non_interactive = sorted(
            t for t in _RENDERABLE_BY_CONTRACT if not _RENDERERS[t]["interactive"]
        )
        assert not non_interactive, (
            f"{non_interactive}: 렌더 가능한데 계약상 비조작형 — 프롬프트가 interactive=true를 "
            "일괄 지시하므로 프롬프트 문구를 함께 갱신해야 한다."
        )
