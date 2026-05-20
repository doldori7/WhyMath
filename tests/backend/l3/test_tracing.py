"""LangfuseTraceSink(tracing.py) 단위 테스트 — record()가 가짜 Langfuse에 전송하는지.

설계 정본: docs/architecture/03a_l3_router_design.md §F.2(Langfuse 기록 필드).
범위 메모(M1.2): 라이브 Langfuse 없이, 손으로 짠 가짜 클라이언트를 주입해 *어댑터
계약*(record(fields)→event(name, metadata))만 검증한다. 모킹 라이브러리 미사용.
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.router import Router, langfuse_fields
from whymath_backend.l3.tracing import LangfuseTraceSink


class _FakeLangfuse:
    """손으로 짠 가짜 langfuse 클라이언트 — event 호출(name·metadata)을 기록한다."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def event(self, *, name: str, metadata: dict[str, object]) -> Any:
        self.events.append((name, metadata))
        return None


def _sink(fake: _FakeLangfuse) -> LangfuseTraceSink:
    """가짜 langfuse를 주입한 LangfuseTraceSink."""
    return LangfuseTraceSink(client=fake, settings=Settings())


class TestLangfuseTraceSink:
    def test_record_sends_event(self) -> None:
        """record(fields)는 langfuse.event(name, metadata=fields)를 호출한다."""
        fake = _FakeLangfuse()
        fields: dict[str, object] = {"cost_tier": "local", "cache_hit": False}
        _sink(fake).record(fields)
        assert len(fake.events) == 1
        name, metadata = fake.events[0]
        assert name == "l3_routing_decision"
        assert metadata == fields

    def test_record_passes_router_fields_verbatim(self) -> None:
        """라우터 langfuse_fields() dict를 그대로 metadata로 보낸다(F.2 9필드)."""
        fake = _FakeLangfuse()
        decision = Router().route(
            RoutingRequest(
                task_type="extract",
                difficulty="medium",
                requires_reasoning=False,
                student_subscription="premium",
                budget_krw=0.0,
            )
        )
        fields = langfuse_fields(decision, cache_hit=True, student_id_hash="h1")
        _sink(fake).record(fields)
        _, metadata = fake.events[0]
        assert metadata["cost_tier"] == "local"
        assert metadata["cache_hit"] is True
        assert metadata["student_id_hash"] == "h1"

    def test_multiple_records_accumulate(self) -> None:
        """여러 record 호출이 누적 전송된다."""
        fake = _FakeLangfuse()
        sink = _sink(fake)
        sink.record({"cost_tier": "local"})
        sink.record({"cost_tier": "cloud_mid"})
        assert len(fake.events) == 2

    def test_satisfies_protocol(self) -> None:
        """LangfuseTraceSink는 TraceSink Protocol을 충족한다(runtime_checkable)."""
        assert isinstance(_sink(_FakeLangfuse()), TraceSink)

    def test_lazy_build_uses_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """client 미주입 시 settings로 lazy build한다(빌더를 가짜로 가로챔)."""
        captured: dict[str, object] = {}

        def _fake_build(settings: Settings) -> _FakeLangfuse:
            captured["host"] = settings.langfuse_host
            return _FakeLangfuse()

        # _build_default_langfuse_client를 가짜로 치환 — 라이브 Langfuse 생성 회피.
        monkeypatch.setattr(
            "whymath_backend.l3.tracing._build_default_langfuse_client", _fake_build
        )
        sink = LangfuseTraceSink(client=None, settings=Settings(langfuse_host="https://lf.x"))
        sink.record({"cost_tier": "local"})  # 첫 record에서 lazy build 발동
        assert captured["host"] == "https://lf.x"
