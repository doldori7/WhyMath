"""bench_latency.py 환경 기록·프리필 분리 계약 동결 (OPS-45 · OPS-46).

**이 테스트가 지키는 것**:
  · OPS-45 — ollama 응답의 prompt_eval_*/eval_* 를 읽어 프리필/생성 tok/s를 분리한다.
  · OPS-46 — 측정 조건(백엔드·CMOS·전력·냉각·VRAM 비율·OLLAMA_* env)을 결과에 남기고,
             조건이 빠진 결과는 **기계로 "비교 불가"** 판정된다.

**왜 이 계약이 필요한가**: 2026-05-16(9.22 tok/s)·2026-08-14(0.5~1 tok/s) 두 측정이
조건 미기록이라 "회귀냐 냉각이냐"를 사후에 가릴 수 없었고, 그래서 회귀 판정을 회수해야 했다.

실 ollama 호출·실 HTTP는 **전부 금지** — client와 probe를 모두 주입한다.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_BENCH_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "phaiakes9" / "benchmark" / "bench_latency.py"
)


def _import_bench_module() -> Any:
    spec = importlib.util.spec_from_file_location("bench_env_under_test", _BENCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench() -> Any:
    return _import_bench_module()


# ---- 모의 클라이언트: 타이밍 필드를 붙이거나 뺄 수 있다 --------------------
class TimingClient:
    """generate 응답에 ollama의 duration 계열을 실을지 말지 선택하는 모의 클라이언트.

    Args:
        with_timings: False면 구 버전 ollama처럼 prompt_eval_*/eval_* 를 **빼고** 응답한다.
        prompt_eval_ms / eval_ms: 응답에 실을 프리필·생성 소요(ms).
    """

    def __init__(
        self,
        with_timings: bool = True,
        eval_count: int = 100,
        prompt_tokens: int = 40,
        prompt_eval_ms: float = 200.0,
        eval_ms: float = 800.0,
    ) -> None:
        self.with_timings = with_timings
        self.eval_count = eval_count
        self.prompt_tokens = prompt_tokens
        self.prompt_eval_ms = prompt_eval_ms
        self.eval_ms = eval_ms
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"model": model, "options": options})
        await asyncio.sleep(0.001)
        payload: dict[str, Any] = {"response": "ok", "eval_count": self.eval_count}
        if self.with_timings:
            payload["prompt_eval_count"] = self.prompt_tokens
            payload["prompt_eval_duration"] = int(self.prompt_eval_ms * 1_000_000)
            payload["eval_duration"] = int(self.eval_ms * 1_000_000)
            payload["load_duration"] = 5_000_000
        return payload


def _make_probe(bench: Any, vram_fraction: float | None, version: str | None = "0.24.0") -> Any:
    """bench 모듈의 Observed 를 써서 프로브를 만든다(모듈 동적 로드라 클래스 재사용 불가)."""

    class _P:
        def ollama_version(self) -> Any:
            if version is None:
                return bench.Observed.absent(bench.ObsStatus.NO_DATA, "테스트: 버전 없음")
            return bench.Observed.measured(version)

        def loaded_model(self, model: str) -> tuple[Any, Any]:
            if vram_fraction is None:
                absent = bench.Observed.absent(bench.ObsStatus.NO_DATA, "테스트: 미적재")
                return absent, absent
            summary = bench.Observed.measured({"name": model, "size": 100, "size_vram": 100})
            return summary, bench.Observed.measured(vram_fraction)

        def gpu_temp_c(self) -> Any:
            return bench.Observed.absent(bench.ObsStatus.UNSUPPORTED, "테스트: 센서 없음")

    return _P()


def _samples(bench: Any, n: int = 4) -> list[Any]:
    return [
        bench.Sample(id=f"s{i}", unit="test", difficulty="easy", prompt=f"p{i}") for i in range(n)
    ]


async def _run(bench: Any, client: Any, probe: Any, **kwargs: Any) -> Any:
    return await bench.run_benchmark(
        model="mock",
        samples=_samples(bench),
        concurrencies=[1],
        warmup_calls=0,
        client=client,
        probe=probe,
        **kwargs,
    )


# ---- OPS-45: 프리필/생성 분리 ----------------------------------------------
@pytest.mark.asyncio
async def test_prefill_and_decode_are_separated(bench: Any) -> None:
    """프리필 tok/s와 생성 tok/s가 **서로 다른 값**으로 산출된다."""
    client = TimingClient(prompt_tokens=40, prompt_eval_ms=200.0, eval_count=100, eval_ms=800.0)
    report = await _run(bench, client, _make_probe(bench, 1.0))
    run = report.concurrency_runs[0]

    assert run.timing_status == "MEASURED"
    # 프리필: 4호출 × 40토큰 = 160토큰 / (4 × 0.2초 = 0.8초) = 200 tok/s
    assert run.prefill_tokens_per_sec == pytest.approx(200.0, rel=0.01)
    # 생성: 4호출 × 100토큰 = 400토큰 / (4 × 0.8초 = 3.2초) = 125 tok/s
    assert run.decode_tokens_per_sec == pytest.approx(125.0, rel=0.01)
    assert run.prompt_tokens_total == 160
    # 두 값이 실제로 갈라져야 분리에 의미가 있다
    assert run.prefill_tokens_per_sec != run.decode_tokens_per_sec


@pytest.mark.asyncio
async def test_missing_timings_report_none_not_zero(bench: Any) -> None:
    """타이밍 필드가 없으면 **0이 아니라 None** + NO_DATA (날조 0 금지)."""
    client = TimingClient(with_timings=False)
    report = await _run(bench, client, _make_probe(bench, 1.0))
    run = report.concurrency_runs[0]

    assert run.prefill_tokens_per_sec is None
    assert run.decode_tokens_per_sec is None
    assert run.prompt_tokens_total is None
    assert run.timing_status == "NO_DATA"
    assert "prompt_eval_duration" in run.timing_note
    # 기존 지표는 계속 나온다 — 분리만 못 할 뿐
    assert run.tokens_per_sec > 0


@pytest.mark.asyncio
async def test_thermal_and_offload_signatures_are_distinguishable(bench: Any) -> None:
    """써멀(프리필 급락)과 오프로드(생성 급락)가 **다른 지표에** 나타난다.

    이 테스트가 OPS-45의 존재 이유를 직접 고정한다 — 합산 wall-clock만 보면
    두 시나리오가 구분되지 않지만, 분리 지표에서는 갈린다.
    """
    thermal = TimingClient(prompt_eval_ms=2000.0, eval_ms=800.0)  # 프리필만 10배 느림
    offload = TimingClient(prompt_eval_ms=200.0, eval_ms=8000.0)  # 생성만 10배 느림

    r_thermal = (await _run(bench, thermal, _make_probe(bench, 1.0))).concurrency_runs[0]
    r_offload = (await _run(bench, offload, _make_probe(bench, 1.0))).concurrency_runs[0]

    # 써멀 시나리오: 프리필이 죽고 생성은 멀쩡
    assert r_thermal.prefill_tokens_per_sec < r_offload.prefill_tokens_per_sec
    # 오프로드 시나리오: 생성이 죽고 프리필은 멀쩡
    assert r_offload.decode_tokens_per_sec < r_thermal.decode_tokens_per_sec


# ---- OPS-46: 환경 기록 · 비교가능성 ----------------------------------------
@pytest.mark.asyncio
async def test_environment_recorded_with_manual_conditions(bench: Any) -> None:
    """사람이 입력한 측정 조건이 결과에 그대로 남는다."""
    report = await _run(
        bench,
        TimingClient(),
        _make_probe(bench, 1.0),
        gpu_backend="ROCm",
        cmos_profile="auto",
        power_profile="기본",
        cooling="평균",
    )
    env = report.environment
    assert env.schema_version == bench.ENV_SCHEMA_VERSION
    assert env.gpu_backend.value == "ROCm"
    assert env.cmos_profile.value == "auto"
    assert env.power_profile.value == "기본"
    assert env.cooling.value == "평균"
    assert env.vram_fraction.value == 1.0
    assert env.ollama_version.value == "0.24.0"


@pytest.mark.asyncio
async def test_missing_conditions_marked_not_provided(bench: Any) -> None:
    """조건 미입력은 빈 문자열이 아니라 NOT_PROVIDED + 사유."""
    report = await _run(bench, TimingClient(), _make_probe(bench, 1.0))
    env = report.environment
    for obs in (env.gpu_backend, env.cmos_profile, env.power_profile, env.cooling):
        assert obs.value is None
        assert obs.status == "NOT_PROVIDED"
        assert obs.note  # 사유가 비어 있으면 안 된다


@pytest.mark.asyncio
async def test_result_without_conditions_is_not_comparable(bench: Any) -> None:
    """조건이 빠진 결과는 **기계로** 비교 불가 판정된다."""
    report = await _run(bench, TimingClient(), _make_probe(bench, 1.0))
    d = bench.report_to_dict(report)
    assert d["environment_comparable"] is False
    assert "gpu_backend" in d["environment_comparable_reason"]


@pytest.mark.asyncio
async def test_result_with_all_conditions_is_comparable(bench: Any) -> None:
    """조건이 다 있으면 비교 가능 판정 — 위 테스트의 변별력 대조군."""
    report = await _run(
        bench,
        TimingClient(),
        _make_probe(bench, 1.0),
        gpu_backend="Vulkan",
        cmos_profile="UMA Fixed 64GB",
        power_profile="성능",
        cooling="증설 완료",
    )
    d = bench.report_to_dict(report)
    assert d["environment_comparable"] is True


def test_v1_legacy_result_is_flagged_incomparable(bench: Any) -> None:
    """`environment` 필드가 아예 없던 과거 결과(v1)가 비교 불가로 드러난다.

    2026-05·2026-08 결과가 정확히 이 모양이다 — 미래 세션이 이를 유효한
    기준선으로 오인하지 않게 하는 것이 이 계약의 목적이다.
    """
    legacy = {"model": "qwen3.5:27b", "concurrency_runs": [{"concurrent": 1}]}
    comparable, reason = bench.environment_comparable(legacy)
    assert comparable is False
    assert "v1" in reason


def test_schema_version_mismatch_is_flagged(bench: Any) -> None:
    """스키마 버전이 다르면 비교 불가."""
    stale = {"environment": {"schema_version": bench.ENV_SCHEMA_VERSION - 1}}
    comparable, reason = bench.environment_comparable(stale)
    assert comparable is False
    assert "버전" in reason


@pytest.mark.asyncio
async def test_partial_gpu_residency_is_visible(bench: Any) -> None:
    """부분 오프로드(vram_fraction < 1.0)가 결과에 그대로 보인다.

    이 값은 **냉각과 독립**으로 오프로드 가설을 판정하는 신호다
    Windows 측 동일 산식 구현은 scripts/ops/bench_ollama.ps1의 gpu_fraction.
    """
    report = await _run(bench, TimingClient(), _make_probe(bench, 0.42))
    assert report.environment.vram_fraction.value == 0.42
    assert report.environment.vram_fraction.status == "MEASURED"


@pytest.mark.asyncio
async def test_probe_failure_records_reason_not_silence(bench: Any) -> None:
    """프로브가 실패해도 벤치는 진행하되 **사유가 남는다**(침묵 실패 금지)."""
    report = await _run(bench, TimingClient(), _make_probe(bench, None, version=None))
    assert report.environment.vram_fraction.value is None
    assert report.environment.vram_fraction.note  # 사유 필수
    assert report.environment.ollama_version.value is None
    # 프로브 실패가 측정 자체를 막지는 않는다
    assert report.concurrency_runs[0].success_count == 4


@pytest.mark.asyncio
async def test_ollama_env_snapshot_only_includes_set_keys(
    bench: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """설정된 OLLAMA_* 만 담는다 — 미설정 키를 빈 문자열로 날조하지 않는다."""
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "8192")
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    report = await _run(bench, TimingClient(), _make_probe(bench, 1.0))
    env_snapshot = report.environment.ollama_env
    assert env_snapshot["OLLAMA_CONTEXT_LENGTH"] == "8192"
    assert "OLLAMA_NUM_PARALLEL" not in env_snapshot


@pytest.mark.asyncio
async def test_thermal_drift_probe_off_by_default(bench: Any) -> None:
    """드리프트 프로브 미지정이면 NOT_PROVIDED — 조용히 0으로 두지 않는다."""
    report = await _run(bench, TimingClient(), _make_probe(bench, 1.0))
    assert report.thermal_drift.value is None
    assert report.thermal_drift.status == "NOT_PROVIDED"


@pytest.mark.asyncio
async def test_thermal_drift_probe_measures_drop(bench: Any) -> None:
    """드리프트 프로브를 켜면 앞뒤 tok/s 하락률이 기록된다."""
    client = TimingClient()
    report = await _run(bench, client, _make_probe(bench, 1.0), thermal_drift_probe=True)
    drift = report.thermal_drift
    assert drift.status == "MEASURED"
    assert set(drift.value) == {
        "concurrent",
        "first_tokens_per_sec",
        "last_tokens_per_sec",
        "drop_pct",
    }
    # 재실행분만큼 호출이 늘어야 프로브가 실제로 돈 것이다
    assert len(client.calls) == 8


@pytest.mark.asyncio
async def test_report_with_environment_is_json_serializable(bench: Any) -> None:
    """환경·타이밍 필드가 붙어도 JSON 왕복이 된다(Enum 누수 금지)."""
    report = await _run(bench, TimingClient(), _make_probe(bench, 1.0), gpu_backend="ROCm")
    parsed = json.loads(json.dumps(bench.report_to_dict(report), ensure_ascii=False))
    assert parsed["environment"]["gpu_backend"]["value"] == "ROCm"
    assert parsed["environment"]["schema_version"] == bench.ENV_SCHEMA_VERSION
    assert parsed["concurrency_runs"][0]["prefill_tokens_per_sec"] is not None
