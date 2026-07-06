"""OllamaProvider 단위테스트 — 가짜 Ollama 클라이언트 주입 (라이브 서비스 없음).

bench_latency.py 패턴(Protocol 경유 가짜 주입)을 미러링한다. 실제 Ollama 데몬·
ollama 라이브러리에 의존하지 않는다.

설계 정본: docs/architecture/03a_l3_router_design.md §A.0(모델 매트릭스)·§A.1.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.providers.ollama import (
    OllamaProvider,
    OllamaStatus,
    _extract_model_names,
    _extract_text,
)
from whymath_backend.l3.router import LOCAL_MODEL_MATRIX, QUALITY_MODEL_ID


class FakeOllamaClient:
    """가짜 Ollama 비동기 클라이언트 — 호출 기록 + 정해진 응답 반환.

    `_OllamaClient` Protocol을 구조적으로 충족한다. generate/list 응답 형태는
    인자로 주입해 dict·객체 양쪽 정규화 경로를 테스트할 수 있다.
    """

    def __init__(
        self,
        *,
        generate_text: str = "원시 출력",
        installed_models: list[str] | None = None,
        list_raises: Exception | None = None,
        generate_response: Any = None,
        list_response: Any = None,
    ) -> None:
        self._generate_text = generate_text
        self._installed = installed_models if installed_models is not None else []
        self._list_raises = list_raises
        self._generate_response_override = generate_response
        self._list_response_override = list_response
        # 호출 기록
        self.generate_calls: list[dict[str, Any]] = []
        self.list_calls: int = 0

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str,
        images: Sequence[str] | None = None,
        options: dict[str, Any] | None = None,
        format: Any = None,  # noqa: A002 — ollama API 인자명 그대로(S2-j)
        stream: bool = False,
    ) -> Any:
        self.generate_calls.append(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "images": images,
                "options": options,
                "format": format,
                "stream": stream,
            }
        )
        if self._generate_response_override is not None:
            return self._generate_response_override
        return {"response": self._generate_text}

    async def list(self) -> Any:
        self.list_calls += 1
        if self._list_raises is not None:
            raise self._list_raises
        if self._list_response_override is not None:
            return self._list_response_override
        return {"models": [{"model": m} for m in self._installed]}


def _local_decision(
    family: ModelFamily | None,
    model: LocalModelTier,
    mode: str = "sync",
) -> RoutingDecision:
    """테스트용 로컬 RoutingDecision 생성."""
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=family,
        local_model=model,
        mode=mode,
        reason="test",
        est_latency_ms=1010,
        est_cost_krw=0.0,
    )


class TestGenerate:
    async def test_local_fast_math_resolves_model_and_returns_text(self) -> None:
        """LOCAL+MATH+FAST → qwen2-math:1.5b로 호출하고 원시 텍스트 반환."""
        client = FakeOllamaClient(generate_text="42")
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.MATH, LocalModelTier.FAST)

        out = await provider.generate("2+2?", "system", decision)

        assert out == "42"
        assert len(client.generate_calls) == 1
        assert client.generate_calls[0]["model"] == "qwen2-math:1.5b"
        assert client.generate_calls[0]["prompt"] == "2+2?"
        assert client.generate_calls[0]["system"] == "system"
        assert client.generate_calls[0]["stream"] is False

    async def test_local_general_mid_resolves_qwen25_7b(self) -> None:
        """LOCAL+GENERAL+MID → qwen2.5:7b."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.MID)

        await provider.generate("p", "s", decision)

        assert client.generate_calls[0]["model"] == "qwen2.5:7b"

    async def test_quality_resolves_27b_family_agnostic(self) -> None:
        """QUALITY(패밀리 None) → qwen3.5:27b. 제공자는 동기 차단을 하지 않는다.

        QUALITY 동기 차단은 파이프라인 책임이다(03a §D.3). 제공자는 비동기 워커가
        같은 코드로 호출할 수 있도록 모델 해석·호출만 한다.
        """
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(None, LocalModelTier.QUALITY, mode="async")

        await provider.generate("p", "s", decision)

        assert client.generate_calls[0]["model"] == QUALITY_MODEL_ID

    async def test_cloud_decision_rejected(self) -> None:
        """CLOUD_* 결정은 거부(S5 범위 밖)."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = RoutingDecision(
            cost_tier=CostTier.CLOUD_MID,
            local_family=None,
            local_model=None,
            mode="sync",
            reason="cloud",
            est_latency_ms=3000,
            est_cost_krw=10.0,
        )

        with pytest.raises(ValueError, match="로컬 결정만"):
            await provider.generate("p", "s", decision)
        assert client.generate_calls == []  # 호출 자체가 없어야 함

    async def test_temperature_none_omits_options(self) -> None:
        """온도 미지정(None) → options에 온도를 싣지 않는다(기존 동작·Ollama 기본 온도)."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.MATH, LocalModelTier.FAST)

        await provider.generate("p", "s", decision)

        assert client.generate_calls[0]["options"] is None

    async def test_temperature_set_injects_options(self) -> None:
        """온도 지정(S2-g 생성 다양성) → options={"temperature": ...}로 실린다."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.MID)

        await provider.generate("p", "s", decision, temperature=0.9)

        assert client.generate_calls[0]["options"] == {"temperature": 0.9}

    async def test_temperature_with_images_both_passed(self) -> None:
        """온도+이미지 동시 지정 → options·images 모두 전달(상호 배타 아님)."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.MATH, LocalModelTier.FAST)

        await provider.generate("p", "s", decision, images=["b64"], temperature=0.7)

        assert client.generate_calls[0]["options"] == {"temperature": 0.7}
        assert client.generate_calls[0]["images"] == ["b64"]

    async def test_json_schema_none_omits_format(self) -> None:
        """스키마 미지정(None) → format을 싣지 않는다(기존 동작·자유 텍스트 생성)."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.MID)

        await provider.generate("p", "s", decision)

        assert client.generate_calls[0]["format"] is None

    async def test_json_schema_set_injects_format(self) -> None:
        """스키마 지정(S2-j structured output) → format=스키마 dict로 실린다(제약 디코딩)."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.MID)
        schema = {"type": "object", "required": ["answer"]}

        await provider.generate("p", "s", decision, json_schema=schema)

        assert client.generate_calls[0]["format"] == schema

    async def test_json_schema_with_temperature_both_passed(self) -> None:
        """스키마+온도 동시 지정(동등문제 저작 실제 조합) → format·options 모두 전달."""
        client = FakeOllamaClient()
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.MID)
        schema = {"type": "object"}

        await provider.generate("p", "s", decision, temperature=0.9, json_schema=schema)

        assert client.generate_calls[0]["format"] == schema
        assert client.generate_calls[0]["options"] == {"temperature": 0.9}

    async def test_extract_text_from_object_response(self) -> None:
        """generate 응답이 pydantic 유사 객체(.response)여도 텍스트 추출."""

        class _Resp:
            response = "객체응답"

        client = FakeOllamaClient(generate_response=_Resp())
        provider = OllamaProvider(client=client)
        decision = _local_decision(ModelFamily.MATH, LocalModelTier.FAST)

        out = await provider.generate("p", "s", decision)
        assert out == "객체응답"


class TestCheckStatus:
    async def test_reachable_all_models_present(self) -> None:
        """모든 라우팅 모델 설치 시 reachable + all_present."""
        all_models = [*LOCAL_MODEL_MATRIX.values(), QUALITY_MODEL_ID]
        client = FakeOllamaClient(installed_models=all_models)
        provider = OllamaProvider(client=client)

        st = await provider.check_status()

        assert st.reachable is True
        assert st.all_present is True
        assert st.missing == ()
        assert client.list_calls == 1

    async def test_reachable_some_models_missing(self) -> None:
        """일부 모델 누락 시 reachable=True지만 all_present=False, missing 채워짐."""
        client = FakeOllamaClient(installed_models=["qwen2-math:1.5b"])
        provider = OllamaProvider(client=client)

        st = await provider.check_status()

        assert st.reachable is True
        assert st.all_present is False
        assert QUALITY_MODEL_ID in st.missing
        assert "qwen2.5:7b" in st.missing

    async def test_unreachable_returns_handled_status(self) -> None:
        """데몬 도달 실패는 예외가 아니라 reachable=False로 흡수."""
        client = FakeOllamaClient(list_raises=ConnectionError("refused"))
        provider = OllamaProvider(client=client)

        st = await provider.check_status()

        assert st.reachable is False
        assert st.all_present is False
        assert st.error is not None
        assert "ConnectionError" in st.error
        # 도달 실패여도 모델 항목은 채워지되 전부 present=False
        assert all(not m.present for m in st.models)

    async def test_list_response_as_object_with_model_attr(self) -> None:
        """list 응답이 객체(.models[*].model)여도 정규화."""

        class _Item:
            def __init__(self, name: str) -> None:
                self.model = name

        class _ListResp:
            models = [_Item("qwen2-math:1.5b")]

        client = FakeOllamaClient(list_response=_ListResp())
        provider = OllamaProvider(client=client)

        st = await provider.check_status()
        assert st.reachable is True
        present = {m.model_id for m in st.models if m.present}
        assert present == {"qwen2-math:1.5b"}


class TestNormalizers:
    def test_extract_model_names_handles_name_key(self) -> None:
        """list 항목이 'name' 키만 가질 때도 추출."""
        resp = {"models": [{"name": "qwen2.5:3b"}]}
        assert _extract_model_names(resp) == {"qwen2.5:3b"}

    def test_extract_model_names_unknown_shape_returns_empty(self) -> None:
        """알 수 없는 형태는 빈 집합."""
        assert _extract_model_names(12345) == set()

    def test_extract_model_names_skips_unnamed_items(self) -> None:
        """이름을 못 찾는 항목(빈 dict·정수)은 건너뛰고 유효한 것만 모은다."""
        resp = {"models": [{}, 7, {"model": ""}, {"name": "qwen2.5:3b"}]}
        assert _extract_model_names(resp) == {"qwen2.5:3b"}

    def test_extract_text_unknown_shape_returns_empty(self) -> None:
        """알 수 없는 generate 응답 형태는 빈 문자열."""
        assert _extract_text(12345) == ""


class TestLazyDefaults:
    def test_default_client_built_from_settings(self) -> None:
        """클라이언트 미주입 시 Settings로 실제 ollama AsyncClient를 지연 생성한다.

        생성자(AsyncClient(...)) 호출은 네트워크를 타지 않으므로 라이브 데몬 없이도
        안전하다. _build_default_client·_get_client·_resolved_settings의 기본 경로를
        모두 통과시킨다.
        """
        from whymath_backend.config import Settings
        from whymath_backend.l3.providers.ollama import _OllamaClient

        provider = OllamaProvider(settings=Settings(ollama_host="http://127.0.0.1:11434"))
        client = provider._get_client()
        assert isinstance(client, _OllamaClient)  # runtime_checkable Protocol 충족
        # 두 번째 호출은 캐시된 같은 인스턴스를 돌려준다(지연 1회 생성).
        assert provider._get_client() is client

    def test_resolved_settings_falls_back_to_global(self) -> None:
        """settings 미주입 시 전역 get_settings()로 폴백한다."""
        from whymath_backend.config import Settings, get_settings

        get_settings.cache_clear()
        provider = OllamaProvider()
        assert isinstance(provider._resolved_settings, Settings)


def test_ollama_status_value_object() -> None:
    """OllamaStatus 파생 속성 동작."""
    st = OllamaStatus(
        reachable=True,
        models=(),
    )
    assert st.all_present is True  # 빈 모델 목록 + reachable → all() True
    assert st.missing == ()
