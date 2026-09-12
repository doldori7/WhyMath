"""EOS-73 ① — seed 정책과 라우터→provider 스레딩 동결.

이 파일이 지키는 것(좌석 실재 ≠ 값 도달):
  A. **정책**(`l3/generation_seed`) — 범위·경로별 지원 판정·주입 공급자·범위 밖 거부.
  B. **스레딩**(providers) — LOCAL은 ollama `options.seed`로 *실제로 나가고*, 클라우드는
     구조적 불가라 **명확히 거부**하며(조용한 무시 금지) 디스패처가 삼키지 않는다.
  C. **읽기측 분류**(`capability_for_model`) — 모델명으로 지원/불가/미상을 되짚는다.

전부 hermetic — 실 Ollama·실 Anthropic·네트워크 0(가짜 클라이언트 주입).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l3.generation_seed import (
    SEED_MAX,
    SEED_MIN,
    SeedCapability,
    capability_for_model,
    default_seed_source,
    draw_seed,
    seed_for_decision,
    seed_supported,
)
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import FixedModelOllamaProvider, OllamaProvider
from whymath_backend.l3.router import LOCAL_MODEL_MATRIX, QUALITY_MODEL_ID


class FakeOllamaClient:
    """가짜 Ollama 비동기 클라이언트 — `_OllamaClient` Protocol 구조 충족·호출 kwargs 캡처.

    `test_ollama_provider.py`의 동명 대역과 같은 패턴이지만 여기 사본을 둔다 — tests 트리는
    패키지가 아니라(`__init__.py` 없음·importlib 모드) 테스트 간 import가 성립하지 않는다.
    """

    def __init__(self, *, generate_text: str = "원시 출력") -> None:
        self._generate_text = generate_text
        self.generate_calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> Any:
        self.generate_calls.append(kwargs)
        return {"response": self._generate_text}

    async def list(self) -> Any:
        return {"models": []}


def _local_decision() -> RoutingDecision:
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=ModelFamily.GENERAL,
        local_model=LocalModelTier.MID,
        mode="sync",
        reason="테스트",
        est_latency_ms=1200,
    )


def _cloud_decision() -> RoutingDecision:
    return RoutingDecision(
        cost_tier=CostTier.CLOUD_MID, mode="sync", reason="테스트", est_latency_ms=3000
    )


# ──────────────────────────────────────────────────────────────────────
# A. 정책
# ──────────────────────────────────────────────────────────────────────
class TestSeedPolicy:
    def test_drawn_seed_stays_in_uint32_safe_window(self) -> None:
        """추출 범위는 int64 좌석보다 좁다 — llama.cpp 샘플러 시드(uint32) 조용한 접힘 차단."""
        assert SEED_MIN == 0
        assert SEED_MAX == 2**31 - 1
        for _ in range(50):
            assert SEED_MIN <= draw_seed() <= SEED_MAX

    def test_default_source_varies_so_batches_do_not_collapse(self) -> None:
        """기본 공급자는 호출마다 다른 값 — 같은 스펙 n건이 같은 문항 n개가 되면 안 된다."""
        source = default_seed_source()
        drawn = {source() for _ in range(20)}
        # 20회 중복이 전부 같을 확률은 사실상 0 — 상수 공급자로 퇴화하면 여기서 잡힌다.
        assert len(drawn) > 1

    def test_local_supports_seed_and_cloud_does_not(self) -> None:
        """지원 판정은 구조적 사실을 반영한다(클라우드=Messages API에 seed 파라미터 부재)."""
        assert seed_supported(_local_decision()) is True
        assert seed_supported(_cloud_decision()) is False

    def test_cloud_decision_gets_none_not_a_fabricated_number(self) -> None:
        """클라우드는 값을 뽑지 않는다 — 보내지 않은 숫자를 기록하면 거짓 재현 기록이 된다."""
        assert seed_for_decision(_cloud_decision(), source=lambda: 12345) is None

    def test_injected_source_is_used_verbatim(self) -> None:
        """주입 공급자의 값이 그대로 좌표가 된다(재현 프로브가 같은 좌표를 되먹이는 경로)."""
        assert seed_for_decision(_local_decision(), source=lambda: 777) == 777

    def test_out_of_range_source_is_rejected_not_truncated(self) -> None:
        """범위 밖은 조용히 자르지 않고 거부 — 자르면 기록 시드와 전달 시드가 갈라진다."""
        with pytest.raises(ValueError, match="범위"):
            seed_for_decision(_local_decision(), source=lambda: SEED_MAX + 1)


# ──────────────────────────────────────────────────────────────────────
# C. 읽기측 분류 (리포트 분모의 근거)
# ──────────────────────────────────────────────────────────────────────
class TestCapabilityForModel:
    def test_router_matrix_models_are_supported(self) -> None:
        for model_id in {*LOCAL_MODEL_MATRIX.values(), QUALITY_MODEL_ID}:
            assert capability_for_model(model_id) is SeedCapability.SUPPORTED

    def test_configured_cloud_models_are_structurally_unsupported(self) -> None:
        settings = get_settings()
        for model_id in (settings.anthropic_model_mid, settings.anthropic_model_high):
            assert capability_for_model(model_id) is SeedCapability.UNSUPPORTED

    def test_unknown_names_are_not_rounded_either_way(self) -> None:
        """미상을 지원/불가로 반올림하면 분모가 부풀거나 회귀가 숨는다 — 제3의 값으로 둔다."""
        assert capability_for_model("강등전-고정-모델:7b") is SeedCapability.UNKNOWN
        assert capability_for_model(None) is SeedCapability.UNKNOWN


# ──────────────────────────────────────────────────────────────────────
# B. 스레딩 — 값이 *실제로* 나가는가
# ──────────────────────────────────────────────────────────────────────
class TestOllamaSeedThreading:
    async def test_seed_lands_in_ollama_options(self) -> None:
        client = FakeOllamaClient(generate_text="출력")
        provider = OllamaProvider(client=client)
        await provider.generate("프롬프트", "시스템", _local_decision(), seed=4242)
        assert client.generate_calls[0]["options"] == {"seed": 4242}

    async def test_seed_and_temperature_share_one_options_dict(self) -> None:
        """온도와 시드는 같은 options에 함께 실린다(한쪽이 다른 쪽을 덮으면 안 된다)."""
        client = FakeOllamaClient(generate_text="출력")
        await OllamaProvider(client=client).generate(
            "프롬프트", "시스템", _local_decision(), temperature=0.9, seed=7
        )
        assert client.generate_calls[0]["options"] == {"temperature": 0.9, "seed": 7}

    async def test_no_seed_keeps_previous_behaviour(self) -> None:
        """seed 미지정이면 options 키 자체가 없다 — 기존 동작 무변경(대조군)."""
        client = FakeOllamaClient(generate_text="출력")
        await OllamaProvider(client=client).generate("프롬프트", "시스템", _local_decision())
        assert "options" not in client.generate_calls[0]

    async def test_fixed_model_provider_also_threads_seed(self) -> None:
        """측정 전용 고정 provider(재현 프로브가 쓰는 좌석)도 같은 options 규약을 따른다."""
        client = FakeOllamaClient(generate_text="출력")
        provider = FixedModelOllamaProvider("qwen2.5:7b", client=client, num_ctx=2048)
        await provider.generate("프롬프트", "시스템", _local_decision(), seed=99)
        options = client.generate_calls[0]["options"]
        assert options["seed"] == 99 and options["num_ctx"] == 2048


class _FakeCloudProvider:
    """seed를 받으면 거부하는 클라우드 대역 — AnthropicProvider의 계약을 그대로 흉내낸다."""

    def __init__(self) -> None:
        self.seeds: list[int | None] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        self.seeds.append(seed)
        if seed is not None:
            raise RuntimeError("seed 미지원")
        return GenerationResult("클라우드 출력", usage=None)


class TestAnthropicRefusesSeed:
    async def test_real_provider_raises_instead_of_silently_ignoring(self) -> None:
        """조용한 무시는 '전달된 적 없는 숫자'가 기록되는 문이다 — 명확히 거부해야 한다."""
        from whymath_backend.l3.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(client=object())  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="seed"):
            await provider.generate("프롬프트", "시스템", _cloud_decision(), seed=1)

    async def test_composite_forwards_seed_instead_of_swallowing_it(self) -> None:
        """디스패처가 seed를 삼키면 거부가 사라져 조용한 무시로 퇴화한다(변별력 대조)."""
        cloud = _FakeCloudProvider()
        composite = CompositeProvider(local=OllamaProvider(client=FakeOllamaClient()), cloud=cloud)
        with pytest.raises(RuntimeError, match="seed"):
            await composite.generate("프롬프트", "시스템", _cloud_decision(), seed=5)
        assert cloud.seeds == [5]  # 삼키지 않고 그대로 전달됐다

    async def test_composite_without_seed_reaches_cloud_normally(self) -> None:
        cloud = _FakeCloudProvider()
        composite = CompositeProvider(local=OllamaProvider(client=FakeOllamaClient()), cloud=cloud)
        result = await composite.generate("프롬프트", "시스템", _cloud_decision())
        assert result.text == "클라우드 출력" and cloud.seeds == [None]
