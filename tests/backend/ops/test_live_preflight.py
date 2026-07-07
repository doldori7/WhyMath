"""live_preflight 프리플라이트 hermetic 테스트 — 라이브 호출 0.

가짜 Settings(키 유/무)로 ①② 판정 분기를, 가짜 provider(generate가 GenerationResult를
반환)로 ③ 실측 비용·None-vs-0·graceful skip·JSON 형식을 단언한다. 실 네트워크·실 키 없음.
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision, Usage
from whymath_backend.l3.providers.anthropic import AnthropicStatus
from whymath_backend.l3.providers.ollama import ModelAvailability, OllamaStatus
from whymath_backend.l3.router import actual_cost_krw
from whymath_backend.ops import live_preflight as lp


# ──────────────────────────────────────────────────────────────────────────
# 가짜 Settings·provider — 라이브 없이 코어를 태운다.
# ──────────────────────────────────────────────────────────────────────────
class _FakeSettings:
    """Settings의 최소 표면만 흉내 — 두 판정 프로퍼티만 필요하다."""

    def __init__(self, *, anthropic: bool, langfuse: bool) -> None:
        self.anthropic_configured = anthropic
        self.langfuse_configured = langfuse


class _FakeCloud:
    """가짜 클라우드 provider — configured/check_status/generate 표면만."""

    def __init__(
        self,
        *,
        configured: bool,
        reachable: bool,
        result: GenerationResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._configured = configured
        self._reachable = reachable
        self._result = result
        self._raise = raise_exc
        self.generate_calls: list[RoutingDecision] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def check_status(self) -> AnthropicStatus:
        return AnthropicStatus(
            configured=self._configured,
            reachable=self._reachable,
            error=None if self._reachable else "AuthError: bad key",
        )

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.generate_calls.append(decision)
        if self._raise is not None:
            raise self._raise
        assert self._result is not None
        return self._result


class _FakeOllama:
    """가짜 로컬 provider — check_status만."""

    def __init__(self, *, reachable: bool) -> None:
        self._reachable = reachable

    async def check_status(self) -> OllamaStatus:
        return OllamaStatus(
            reachable=self._reachable,
            models=(ModelAvailability(model_id="qwen2-math:7b", present=self._reachable),),
            error=None if self._reachable else "ConnectionError: down",
        )


def _cloud_factory(fake: _FakeCloud) -> lp.CloudProviderFactory:
    return lambda _settings: fake  # type: ignore[arg-type,return-value]


def _local_factory(fake: _FakeOllama) -> lp.LocalProviderFactory:
    return lambda _settings: fake  # type: ignore[arg-type,return-value]


def _settings(*, anthropic: bool, langfuse: bool) -> lp.Settings:
    # _FakeSettings는 Settings의 두 프로퍼티만 노출 — run_preflight는 그 둘만 읽는다.
    return _FakeSettings(anthropic=anthropic, langfuse=langfuse)  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────
# ①② 판정 분기
# ──────────────────────────────────────────────────────────────────────────
async def test_configured_flags_reflect_settings() -> None:
    """①② 판정은 Settings의 두 프로퍼티를 그대로 반영한다."""
    cloud = _FakeCloud(configured=True, reachable=True, result=GenerationResult(text="2"))
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=False),
        smoke=False,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.cloud_configured is True
    assert report.langfuse_configured is False


# ──────────────────────────────────────────────────────────────────────────
# ③ 스모크 — 실측 비용 산정
# ──────────────────────────────────────────────────────────────────────────
async def test_smoke_computes_actual_cost_krw() -> None:
    """토큰이 있으면 actual_cost_krw로 실측 비용을 산정하고 CLOUD_MID로 호출한다."""
    usage = Usage(input_tokens=100, output_tokens=50, latency_ms=1234.5)
    cloud = _FakeCloud(
        configured=True, reachable=True, result=GenerationResult(text="2", usage=usage)
    )
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    # CLOUD_MID(Sonnet) 강제 — Opus(HIGH) 아님.
    assert cloud.generate_calls[0].cost_tier == CostTier.CLOUD_MID.value
    smoke = report.smoke
    assert smoke.ran is True
    expected = actual_cost_krw(lp._cloud_mid_decision(), usage)
    assert smoke.cost_krw == expected
    assert smoke.cost_krw is not None and smoke.cost_krw > 0.0
    assert smoke.input_tokens == 100
    assert smoke.output_tokens == 50
    assert smoke.latency_ms == 1234.5
    assert smoke.text_chars == 1
    assert report.exit_code == 0


# ──────────────────────────────────────────────────────────────────────────
# None-vs-0: 토큰 미상 → cost None (0원 아님)
# ──────────────────────────────────────────────────────────────────────────
async def test_smoke_none_tokens_yields_none_cost() -> None:
    """클라우드인데 토큰이 미상(None)이면 비용은 None — '0원 확정'과 구분."""
    usage = Usage(input_tokens=None, output_tokens=None, latency_ms=900.0)
    cloud = _FakeCloud(
        configured=True, reachable=True, result=GenerationResult(text="2", usage=usage)
    )
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.smoke.ran is True
    assert report.smoke.cost_krw is None  # 미상 ≠ 0원


async def test_smoke_no_usage_yields_none_cost() -> None:
    """usage 자체가 없으면(미계측 provider) 비용은 None."""
    cloud = _FakeCloud(
        configured=True, reachable=True, result=GenerationResult(text="2", usage=None)
    )
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.smoke.cost_krw is None
    assert report.smoke.input_tokens is None


# ──────────────────────────────────────────────────────────────────────────
# graceful skip — 키 없음
# ──────────────────────────────────────────────────────────────────────────
async def test_smoke_skipped_when_anthropic_unconfigured() -> None:
    """anthropic 미설정이면 스모크는 graceful skip 하고 사유에 '키 없음'을 명시한다."""
    cloud = _FakeCloud(configured=False, reachable=False)
    report = await lp.run_preflight(
        _settings(anthropic=False, langfuse=False),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=False)),
    )
    assert report.smoke.ran is False
    assert report.smoke.skipped_reason is not None
    assert "키 없음" in report.smoke.skipped_reason
    # 미설정은 정보 — Ollama도 down이지만 종료 코드는 0.
    assert report.exit_code == 0
    assert cloud.generate_calls == []  # 실 호출 없음


async def test_smoke_skipped_when_no_smoke_flag() -> None:
    """--no-smoke(smoke=False)면 설정돼 있어도 실 호출을 하지 않는다."""
    cloud = _FakeCloud(configured=True, reachable=True, result=GenerationResult(text="2"))
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=False,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.smoke.ran is False
    assert cloud.generate_calls == []


# ──────────────────────────────────────────────────────────────────────────
# 종료 코드 — 설정됐는데 도달 불가 / 스모크 실패
# ──────────────────────────────────────────────────────────────────────────
async def test_exit_error_when_configured_but_unreachable() -> None:
    """클라우드가 설정됐는데 도달 불가면 종료 코드 2."""
    cloud = _FakeCloud(configured=True, reachable=False)
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=False,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.cloud_reachable is False
    assert report.cloud_error is not None
    assert report.exit_code == 2


async def test_exit_error_when_smoke_raises() -> None:
    """스모크 1콜이 예외로 실패하면 종료 코드 2, 오류는 리포트에 흡수된다."""
    cloud = _FakeCloud(configured=True, reachable=True, raise_exc=RuntimeError("boom"))
    report = await lp.run_preflight(
        _settings(anthropic=True, langfuse=True),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.smoke.error is not None
    assert "boom" in report.smoke.error
    assert report.exit_code == 2


async def test_ollama_down_does_not_fail_exit() -> None:
    """Ollama 도달 불가는 정보용 — 종료 코드를 좌우하지 않는다."""
    cloud = _FakeCloud(configured=False, reachable=False)
    report = await lp.run_preflight(
        _settings(anthropic=False, langfuse=False),
        smoke=True,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=False)),
    )
    assert report.ollama_reachable is False
    assert report.ollama_error is not None
    assert report.exit_code == 0


# ──────────────────────────────────────────────────────────────────────────
# 미설정 시 클라우드 도달성은 미점검(None)
# ──────────────────────────────────────────────────────────────────────────
async def test_cloud_reachable_none_when_unconfigured() -> None:
    """anthropic 미설정이면 도달성은 점검 대상이 아니므로 None."""
    cloud = _FakeCloud(configured=False, reachable=False)
    report = await lp.run_preflight(
        _settings(anthropic=False, langfuse=True),
        smoke=False,
        cloud_provider_factory=_cloud_factory(cloud),
        local_provider_factory=_local_factory(_FakeOllama(reachable=True)),
    )
    assert report.cloud_reachable is None
    assert report.cloud_error is None


# ──────────────────────────────────────────────────────────────────────────
# 리포트 렌더·JSON 형식 + 시크릿 미출력
# ──────────────────────────────────────────────────────────────────────────
def _sample_report() -> lp.Report:
    return lp.Report(
        cloud_configured=True,
        langfuse_configured=True,
        cloud_reachable=True,
        cloud_error=None,
        ollama_reachable=False,
        ollama_error="ConnectionError: down",
        smoke=lp.SmokeResult(
            ran=True,
            cost_krw=1.155,
            input_tokens=100,
            output_tokens=50,
            latency_ms=1234.5,
            text_chars=1,
        ),
        exit_code=0,
    )


def test_stdout_render_has_sections_and_no_secrets() -> None:
    """사람용 stdout은 판정·도달성·스모크 섹션을 담고 bool·비용·토큰만 노출한다."""
    text = lp._render_stdout(_sample_report())
    assert "cloud_configured" in text
    assert "langfuse_configured" in text
    assert "CLOUD_MID" in text
    assert "1.1550원" in text  # 비용 표기
    # 시크릿 값(sk-ant-/pk-lf-)은 어디에도 없어야 한다.
    assert "sk-ant" not in text
    assert "pk-lf" not in text


def test_none_cost_renders_as_unknown() -> None:
    """비용 None은 '미상'으로 렌더(0원과 구분)."""
    assert "미상" in lp._fmt_cost(None)
    assert lp._fmt_cost(None) != "0원"


def test_json_report_roundtrip(tmp_path: Path) -> None:
    """JSON 리포트는 dataclass 구조를 그대로 담고 다시 로드된다."""
    report = _sample_report()
    out = tmp_path / "preflight.json"
    lp._write_json(report, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["cloud_configured"] is True
    assert loaded["smoke"]["cost_krw"] == 1.155
    assert loaded["smoke"]["input_tokens"] == 100
    assert loaded["exit_code"] == 0


def test_main_dry_run_unconfigured_returns_zero(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    """main: 키 없는 환경에서 스모크 skip·exit 0(드라이런 계약)."""

    def _fake_run(
        settings: object,
        *,
        smoke: bool,
        cloud_provider_factory: object = None,
        local_provider_factory: object = None,
    ) -> lp.Report:
        # run_preflight을 가짜로 대체 — main의 파싱·출력·종료 코드 경로만 검증.
        return lp.Report(
            cloud_configured=False,
            langfuse_configured=False,
            cloud_reachable=None,
            cloud_error=None,
            ollama_reachable=False,
            ollama_error="down",
            smoke=lp.SmokeResult(
                ran=False, skipped_reason="anthropic 미설정(키 없음) — 스모크 skip"
            ),
            exit_code=0,
        )

    async def _fake_coro(*args: object, **kwargs: object) -> lp.Report:
        return _fake_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(lp, "run_preflight", _fake_coro)
    monkeypatch.setattr(lp, "Settings", lambda: object())
    code = lp.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "스모크 skip" in captured.out
