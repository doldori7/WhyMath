"""L3 시각화 생성기의 **렌더 계약 파생** 로더 단위테스트 (VIZ-02).

정합성 게이트("생성기 제시 타입 ⊆ 렌더 가능 타입")는 `tests/backend/schema/test_render_contract.py`
가 *실제 계약 파일*로 건다. 이 파일은 그 파생의 **기전**을 본다 — 캐시(매 호출 파일 I/O 금지)·계약
부재/파손 시 강등(예외 타입명 로그)·렌더 가능 0건 시 생성 차단·프롬프트가 정말 계약에서 파생되는지
(하드코딩 잔존 여부)를 임시 계약 파일로 주입해 확인한다.

설계 근거: `docs/architecture/visualization_module_gap_review.md` §3 D3.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l3 import visualization as viz


def _contract(adapters: dict[str, str | None]) -> dict[str, Any]:
    """type → web_adapter 매핑으로 최소 계약 문서를 만든다(실제 파일과 같은 최상위 형태)."""
    return {
        "version": "test",
        "renderers": {
            name: {"family": ["X"], "interactive": adapter is not None, "web_adapter": adapter}
            for name, adapter in adapters.items()
        },
    }


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    """계약·프롬프트 캐시를 앞뒤로 비운다 — 전역 캐시가 다른 테스트로 새지 않게(순서 의존 방지)."""
    viz.reset_render_contract_cache()
    yield
    viz.reset_render_contract_cache()


@pytest.fixture
def contract_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """로더가 읽는 계약 경로를 임시 파일로 갈아끼운다(실제 `data/render_contract.json` 무접촉)."""
    path = tmp_path / "render_contract.json"
    monkeypatch.setattr(viz, "RENDER_CONTRACT_PATH", path)
    return path


class TestRenderableTypesDerivation:
    """`web_adapter != null`이 렌더 가능성 술어 — 계약이 바뀌면 결과도 바뀐다(하드코딩 아님)."""

    def test_only_types_with_web_adapter_are_renderable(self, contract_path: Path) -> None:
        contract_path.write_text(
            json.dumps(
                _contract(
                    {
                        "interactive_graph_2d": "graph2dSpecToState",
                        "interactive_surface_3d": None,
                        "animation_prerendered": None,
                    }
                )
            ),
            encoding="utf-8",
        )
        assert viz.renderable_visualization_types() == ("interactive_graph_2d",)

    def test_contract_change_flows_into_production_prompt(self, contract_path: Path) -> None:
        """계약에서 어댑터를 빼면 프롬프트에서도 사라진다 — 프롬프트가 계약 파생임의 양성 대조."""
        contract_path.write_text(
            json.dumps(
                _contract(
                    {
                        "interactive_graph_2d": None,
                        "interactive_surface_3d": "surface3dSpecToState",
                    }
                )
            ),
            encoding="utf-8",
        )
        system_prompt, _ = viz.build_visualization_prompt("구면", "고2")
        assert "interactive_surface_3d" in system_prompt
        assert "interactive_graph_2d" not in system_prompt

    def test_contract_is_read_once_and_cached(self, contract_path: Path) -> None:
        """첫 호출 뒤 계약 파일이 사라져도 같은 값 — 매 LLM 호출마다 파일을 읽지 않는다."""
        contract_path.write_text(
            json.dumps(_contract({"interactive_graph_2d": "graph2dSpecToState"})),
            encoding="utf-8",
        )
        first = viz.renderable_visualization_types()
        contract_path.unlink()
        assert viz.renderable_visualization_types() == first == ("interactive_graph_2d",)


class TestDegradationIsLoudAndSafe:
    """계약을 *읽을 수 없을 때*의 강등 — 조용히 삼키지 않고, 직전 정상 동작을 유지한다."""

    @pytest.mark.parametrize(
        "body, expected_error_type",
        [
            (None, "FileNotFoundError"),  # 파일 자체가 없음
            ("{ 깨진 JSON", "JSONDecodeError"),
            ('{"version": "test"}', "KeyError"),  # renderers 키 부재
            ('{"renderers": []}', "TypeError"),  # renderers 형식 위반
            ('{"renderers": {}}', "TypeError"),  # renderers 공백
        ],
        ids=["missing-file", "broken-json", "no-renderers-key", "renderers-not-dict", "empty"],
    )
    def test_unreadable_contract_falls_back_with_typed_warning(
        self,
        contract_path: Path,
        caplog: pytest.LogCaptureFixture,
        body: str | None,
        expected_error_type: str,
    ) -> None:
        """계약 로드 실패 → 예시 키로 강등 + **예외 타입명을 담은** 경고(침묵 실패 금지)."""
        if body is not None:
            contract_path.write_text(body, encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="whymath.l3.visualization"):
            types = viz.renderable_visualization_types()
        assert types == tuple(sorted(viz._SPEC_EXAMPLES))
        assert f"error_type={expected_error_type}" in caplog.text

    def test_fallback_still_produces_a_usable_prompt(self, contract_path: Path) -> None:
        """강등 상태에서도 프롬프트는 정상 조립된다 — 학생 경로가 계약 파손으로 죽지 않는다."""
        system_prompt, _ = viz.build_visualization_prompt("이차함수", "고1")
        for type_value in viz._SPEC_EXAMPLES:
            assert type_value in system_prompt
        assert "animation_prerendered" not in system_prompt


class TestZeroRenderableBlocksGeneration:
    """계약이 *정상적으로* '렌더 경로 0'을 선언한 경우 — 폴백하지 않고 생성을 막는다."""

    def test_all_null_adapters_yield_empty_set(self, contract_path: Path) -> None:
        """읽기는 성공했으므로 예시 키로 폴백하지 않는다(폴백하면 계약 위반)."""
        contract_path.write_text(
            json.dumps(_contract({"interactive_graph_2d": None, "animation_prerendered": None})),
            encoding="utf-8",
        )
        assert viz.renderable_visualization_types() == ()

    def test_prompt_build_raises_instead_of_wasting_llm_calls(
        self, contract_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """렌더 가능 0건이면 프롬프트 조립 자체를 실패시킨다(생성해도 100% 렌더 불가)."""
        contract_path.write_text(
            json.dumps(_contract({"interactive_graph_2d": None})), encoding="utf-8"
        )
        with caplog.at_level(logging.ERROR, logger="whymath.l3.visualization"):
            with pytest.raises(RuntimeError, match="렌더 가능한 시각화 타입이 없다"):
                viz.build_visualization_prompt("극한", "고2")
        assert "렌더 가능한 시각화 타입이 0건" in caplog.text


class TestSystemPromptAssembly:
    """`_build_system_prompt`는 순수 함수 — 주어진 목록 밖 타입을 절대 부르지 않는다."""

    def test_lists_given_types_only(self) -> None:
        prompt = viz._build_system_prompt(["interactive_graph_2d"])
        assert "interactive_graph_2d" in prompt
        assert "interactive_surface_3d" not in prompt
        assert "위 1종" in prompt

    def test_simulation_only_hint_appears_with_simulation(self) -> None:
        """확률 시뮬 전용 지시는 그 타입이 제시될 때만 붙는다(대상 없는 지시 = 소음)."""
        assert "outcomes" not in viz._build_system_prompt(["interactive_surface_3d"])
        assert "outcomes" in viz._build_system_prompt(["simulation_probabilistic"])
