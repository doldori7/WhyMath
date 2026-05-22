"""Celery 태스크 단위테스트 — 플레인 함수 직접 호출 (broker·워커 없음).

QUALITY 생성 태스크의 *핵심 로직*(run_quality_generation_payload)을 broker 없이 직접
호출해 검증한다 — 가짜 provider를 주입해 ollama·GPU·Celery 라이브가 필요 없다(CI
hermetic). 등록된 Celery 태스크는 이 플레인 함수 위의 얇은 래퍼이므로(register_quality_task),
함수만 검증하면 태스크 본체가 검증된 셈이다.

설계 정본: docs/architecture/03a_l3_router_design.md §D.3(QUALITY 비동기)·§A.0(27b 해석).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    RoutingDecision,
)
from whymath_backend.l3.queue.tasks import (
    PAYLOAD_DECISION,
    PAYLOAD_PROMPT,
    PAYLOAD_SYSTEM,
    QUALITY_TASK_NAME,
    run_quality_generation_payload,
)
from whymath_backend.l3.router import QUALITY_MODEL_ID, resolve_model


class FakeProvider:
    """가짜 LLMProvider — generate 인자를 기록하고 정해진 텍스트 반환(async)."""

    def __init__(self, text: str = "27b 원시 출력") -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


def _quality_decision() -> RoutingDecision:
    """QUALITY(async) 결정 — 27b, 패밀리 무관(불변식 4)."""
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=None,
        local_model=LocalModelTier.QUALITY,
        mode="async",
        reason="self_verify",
        est_latency_ms=13886,
        est_cost_krw=0.0,
    )


def _quality_payload(prompt: str = "검증할 풀이", system: str = "시스템") -> dict[str, object]:
    """파이프라인이 만드는 형태의 payload(decision은 model_dump dict)."""
    return {
        PAYLOAD_PROMPT: prompt,
        PAYLOAD_SYSTEM: system,
        PAYLOAD_DECISION: _quality_decision().model_dump(),
    }


class TestRunQualityGenerationPayload:
    # 이 메서드들은 *동기* 테스트다 — run_quality_generation_payload가 내부에서
    # asyncio.run()을 호출하므로, pytest-asyncio의 실행 중 이벤트 루프 안에서 부르면
    # "asyncio.run() cannot be called from a running event loop"로 실패한다. async def가
    # 아니라 plain def로 두어 루프 밖에서 호출한다(태스크는 본디 워커의 동기 컨텍스트).
    def test_runs_provider_and_returns_text(self) -> None:
        """payload → provider.generate 실행 → 생성 텍스트 반환."""
        provider = FakeProvider(text="생성된 27b 결과")
        text = run_quality_generation_payload(_quality_payload(), provider=provider)
        assert text == "생성된 27b 결과"
        assert len(provider.calls) == 1

    def test_reconstructs_decision_and_passes_to_provider(self) -> None:
        """payload의 decision dict → RoutingDecision 재구성 → provider에 전달."""
        provider = FakeProvider()
        run_quality_generation_payload(
            _quality_payload(prompt="P본문", system="S본문"), provider=provider
        )
        prompt, system, decision = provider.calls[0]
        assert prompt == "P본문"
        assert system == "S본문"
        # 재구성된 결정은 QUALITY(async) — 불변식 통과.
        assert decision.cost_tier == CostTier.LOCAL.value
        assert decision.local_model == LocalModelTier.QUALITY.value
        assert decision.mode == "async"

    def test_quality_resolves_to_27b_model_id(self) -> None:
        """재구성된 QUALITY 결정은 resolve_model로 qwen3.5:27b가 된다(03a §A.0).

        태스크가 provider에 넘기는 결정으로 실제 모델 ID가 27b인지 확인한다 — 워커가
        OllamaProvider를 통해 호출할 모델이 QUALITY 전용 모델임을 보장.
        """
        provider = FakeProvider()
        run_quality_generation_payload(_quality_payload(), provider=provider)
        _, _, decision = provider.calls[0]
        model_id = resolve_model(decision.local_family, decision.local_model)
        assert model_id == QUALITY_MODEL_ID == "qwen3.5:27b"

    def test_missing_payload_key_raises(self) -> None:
        """payload 스키마가 깨지면(키 누락) KeyError — 워커가 실패로 기록."""
        provider = FakeProvider()
        with pytest.raises(KeyError):
            run_quality_generation_payload(
                {PAYLOAD_PROMPT: "p", PAYLOAD_SYSTEM: "s"},  # decision 누락
                provider=provider,
            )

    def test_invalid_decision_raises(self) -> None:
        """decision dict가 불변식 위반이면 검증 오류(워커 실패로 기록)."""
        provider = FakeProvider()
        # QUALITY인데 mode=sync → 불변식 3 위반.
        bad = {
            PAYLOAD_PROMPT: "p",
            PAYLOAD_SYSTEM: "s",
            PAYLOAD_DECISION: {
                "cost_tier": "local",
                "local_family": None,
                "local_model": "quality",
                "mode": "sync",  # 위반
                "reason": "",
                "est_latency_ms": 13886,
                "est_cost_krw": 0.0,
            },
        }
        with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError 계열
            run_quality_generation_payload(bad, provider=provider)
        assert provider.calls == []  # 검증 실패 → provider 미호출


def test_task_name_is_stable_contract() -> None:
    """태스크 이름은 enqueue(send_task)와 공유하는 안정적 문자열 계약이다."""
    assert QUALITY_TASK_NAME == "whymath.l3.quality.generate"


def test_quality_task_registered_on_default_app() -> None:
    """모듈 import 시 기본 Celery 앱에 QUALITY 태스크가 등록된다(워커 include 경로).

    앱 생성은 broker에 연결하지 않으므로(지연 연결) 이 단정은 hermetic하다 —
    등록 여부만 본다(디스패치·실행 없음).
    """
    from whymath_backend.l3.queue.tasks import quality_celery_app

    assert QUALITY_TASK_NAME in quality_celery_app.tasks


def test_resolve_provider_defaults_to_ollama_provider() -> None:
    """provider 미주입 시 기본 OllamaProvider를 지연 생성한다(생성만 — 연결 없음).

    OllamaProvider() 생성자는 클라이언트를 지연 생성하므로(첫 호출 때 연결) 라이브
    ollama·GPU 없이도 이 단정은 hermetic하다. _resolve_provider의 기본 분기를 덮는다.
    """
    from whymath_backend.l3.providers.ollama import OllamaProvider
    from whymath_backend.l3.queue.tasks import _resolve_provider

    resolved = _resolve_provider(None)
    assert isinstance(resolved, OllamaProvider)


def test_resolve_provider_returns_injected() -> None:
    """provider 주입 시 그대로 돌려준다(지연 생성 안 함)."""
    from whymath_backend.l3.queue.tasks import _resolve_provider

    fake = FakeProvider()
    assert _resolve_provider(fake) is fake


def test_register_quality_task_body_delegates_to_plain_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """register_quality_task가 만든 태스크 본체는 플레인 함수에 위임한다(라인 커버).

    신선한 Celery 앱에 태스크를 등록하고, 모듈의 run_quality_generation_payload를 가짜로
    바꿔치기한 뒤 태스크 본체(.run)를 직접 호출한다 — broker·워커·실제 생성 없이 위임
    경로(워커가 기본 provider로 실행하는 줄)를 검증한다. 등록 자체도 broker에 연결하지
    않는다(지연 연결).
    """
    import whymath_backend.l3.queue.tasks as tasks_mod
    from whymath_backend.config import Settings
    from whymath_backend.l3.queue.celery_app import build_celery_app
    from whymath_backend.l3.queue.tasks import register_quality_task

    seen: list[dict[str, Any]] = []

    def _fake_payload_runner(payload: dict[str, Any]) -> str:
        seen.append(payload)
        return "위임됨"

    # 태스크 본체가 부르는 모듈 레벨 함수를 가짜로 교체(실제 ollama 호출 회피).
    monkeypatch.setattr(tasks_mod, "run_quality_generation_payload", _fake_payload_runner)

    app = build_celery_app(Settings())
    task = register_quality_task(app)
    # 태스크 본체를 직접 호출(.run은 데코레이트 전 원함수) — broker 우회.
    out = task.run({"prompt": "p", "system": "s", "decision": {}})
    assert out == "위임됨"
    assert seen == [{"prompt": "p", "system": "s", "decision": {}}]
