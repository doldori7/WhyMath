"""bench_latency.py 단위 테스트.

- 실제 ollama 호출은 *반드시* 모킹 (테스트 표준 docs/standards/testing.md).
- run_benchmark 의 `client` 인자로 모의 클라이언트를 주입.
- 게이트 통과/실패 분기, 동시도 처리, 표본 로딩, percentile 정확성 검증.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---- bench_latency 모듈 로드 (sys.path 의존 없이) ---------------------------
_BENCH_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "phaiakes9" / "benchmark" / "bench_latency.py"
)
_SAMPLES_PATH = _BENCH_PATH.parent / "sample_prompts.json"


def _import_bench_module() -> Any:
    """bench_latency.py 를 동적 import. 테스트 격리 보장."""
    spec = importlib.util.spec_from_file_location("bench_latency_under_test", _BENCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench() -> Any:
    """bench_latency 모듈 한 번만 로드해 모듈 전체에 공유."""
    return _import_bench_module()


# ---- 모의 클라이언트 -------------------------------------------------------
class MockOllamaClient:
    """ollama.AsyncClient 의 generate 1메서드를 모방하는 모의 객체.

    Args:
        latency_seq: 호출 순서별로 반환할 지연(초). 부족하면 마지막 값 반복.
        eval_count: 모든 호출에 동일 적용할 생성 토큰 수.
        fail_indices: 이 인덱스의 호출은 RuntimeError 발생.
    """

    def __init__(
        self,
        latency_seq: list[float] | None = None,
        eval_count: int = 100,
        fail_indices: set[int] | None = None,
    ) -> None:
        self._latency_seq = latency_seq or [0.05]
        self._eval_count = eval_count
        self._fail_indices = fail_indices or set()
        self.calls: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 호출 인덱스 결정 (락으로 직렬화)
        async with self._lock:
            idx = len(self.calls)
            self.calls.append(
                {"model": model, "prompt": prompt, "stream": stream, "options": options}
            )

        if idx in self._fail_indices:
            raise RuntimeError(f"mock 실패: idx={idx}")

        latency = self._latency_seq[idx] if idx < len(self._latency_seq) else self._latency_seq[-1]
        await asyncio.sleep(latency)
        return {
            "response": f"mock response for prompt[:20]={prompt[:20]}",
            "eval_count": self._eval_count,
            "done": True,
        }


# ---- percentile 유틸 ------------------------------------------------------
def test_percentile_basic(bench: Any) -> None:
    """선형 보간 percentile이 알려진 값과 일치."""
    assert bench.percentile([], 0.5) == 0.0
    assert bench.percentile([10.0], 0.5) == 10.0
    # 1..10 의 p50 ≈ 5.5 (선형 보간)
    vals = [float(i) for i in range(1, 11)]
    assert bench.percentile(vals, 0.50) == pytest.approx(5.5, rel=0, abs=0.01)
    assert bench.percentile(vals, 0.90) == pytest.approx(9.1, rel=0, abs=0.01)
    assert bench.percentile(vals, 0.99) == pytest.approx(9.91, rel=0, abs=0.01)


def test_percentile_monotonic(bench: Any) -> None:
    """p50 <= p90 <= p99 보장."""
    vals = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    p50 = bench.percentile(vals, 0.50)
    p90 = bench.percentile(vals, 0.90)
    p99 = bench.percentile(vals, 0.99)
    assert p50 <= p90 <= p99


# ---- load_samples ---------------------------------------------------------
def test_load_samples_real_file(bench: Any) -> None:
    """프로젝트의 실제 sample_prompts.json 이 정상 파싱되는지."""
    samples = bench.load_samples(_SAMPLES_PATH)
    assert len(samples) >= 5, "M1.1 게이트 요구사항: 5~10개 표본"
    assert len(samples) <= 10
    for s in samples:
        assert s.id, "id 필수"
        assert s.prompt, "prompt 필수"
        assert s.unit, "unit 필수"


def test_load_samples_no_copyright_violation(bench: Any) -> None:
    """검정교과서 인용 방지를 위한 메타데이터 확인.

    sample_prompts.json 은 자체 원작 명시(license, author)가 있어야 함.
    """
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert "license" in raw, "라이선스 명시 필수 (CLAUDE.md 절대 금기)"
    assert "author" in raw, "저자 명시 필수"
    # CC0 또는 자체 원작 표기
    assert "CC0" in raw["license"] or "원작" in raw["license"]


def test_load_samples_missing_file(bench: Any, tmp_path: Path) -> None:
    """없는 파일은 FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        bench.load_samples(tmp_path / "missing.json")


# ---- 단일 호출 ------------------------------------------------------------
@pytest.mark.asyncio
async def test_call_once_success(bench: Any) -> None:
    """성공 시 latency_ms > 0, output_tokens 반영."""
    client = MockOllamaClient(latency_seq=[0.02], eval_count=42)
    sample = bench.Sample(id="T01", unit="test", difficulty="easy", prompt="x+1=?")
    result = await bench._call_once(client, "mock-model", sample, num_predict=64)
    assert result.success is True
    assert result.sample_id == "T01"
    assert result.output_tokens == 42
    assert result.latency_ms >= 20.0  # 최소 20ms (asyncio.sleep 정밀도 고려)
    assert result.error is None
    assert client.calls[0]["model"] == "mock-model"
    assert client.calls[0]["options"] == {"num_predict": 64}


@pytest.mark.asyncio
async def test_call_once_failure(bench: Any) -> None:
    """예외는 CallResult.error 로 흡수, success=False."""
    client = MockOllamaClient(fail_indices={0})
    sample = bench.Sample(id="T02", unit="test", difficulty="easy", prompt="x")
    result = await bench._call_once(client, "mock-model", sample, num_predict=16)
    assert result.success is False
    assert "RuntimeError" in (result.error or "")


# ---- 전체 벤치마크 흐름 ---------------------------------------------------
def _make_samples(bench: Any, n: int = 4) -> list[Any]:
    return [
        bench.Sample(id=f"S{i:02d}", unit="단위", difficulty="easy", prompt=f"문제 {i}")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_run_benchmark_gate_pass(bench: Any) -> None:
    """모든 호출이 1초 이내면 게이트 통과(True)."""
    client = MockOllamaClient(latency_seq=[0.01] * 100, eval_count=50)
    samples = _make_samples(bench, n=6)
    report = await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1, 2],
        warmup_calls=0,
        gate_p50_ms=2000,
        client=client,
    )
    assert report.gate_p50_under_2s is True
    assert len(report.concurrency_runs) == 2
    assert report.concurrency_runs[0].concurrent == 1
    assert report.concurrency_runs[0].success_count == 6
    assert report.concurrency_runs[0].fail_count == 0
    # 동시도 1에서 p50 < 1000ms
    assert report.concurrency_runs[0].p50_ms < 1000


@pytest.mark.asyncio
async def test_run_benchmark_gate_fail(bench: Any) -> None:
    """동시도 1의 p50이 한도 초과면 게이트 실패."""
    # 4초 지연을 6개 표본에 적용 → p50 ≈ 4000ms
    client = MockOllamaClient(latency_seq=[4.0] * 100, eval_count=10)
    samples = _make_samples(bench, n=6)
    report = await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1],
        warmup_calls=0,
        gate_p50_ms=2000,
        client=client,
    )
    assert report.gate_p50_under_2s is False
    assert report.concurrency_runs[0].p50_ms >= 2000


@pytest.mark.asyncio
async def test_run_benchmark_partial_failure(bench: Any) -> None:
    """일부 호출 실패가 있어도 보고서가 생성되고 fail_count 반영."""
    client = MockOllamaClient(latency_seq=[0.01] * 100, fail_indices={1, 3}, eval_count=20)
    samples = _make_samples(bench, n=6)
    report = await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1],
        warmup_calls=0,
        client=client,
    )
    run = report.concurrency_runs[0]
    # 동시도 1이므로 호출 순서 결정적: idx 1, 3 실패 → 2건 실패
    assert run.fail_count == 2
    assert run.success_count == 4
    assert len(run.errors) == 2


@pytest.mark.asyncio
async def test_run_benchmark_warmup_called(bench: Any) -> None:
    """워밍업 호출이 카운트에 반영되는지."""
    client = MockOllamaClient(latency_seq=[0.001] * 100, eval_count=5)
    samples = _make_samples(bench, n=3)
    await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1],
        warmup_calls=2,
        client=client,
    )
    # 워밍업 2회 + 본 측정 3회 = 5회
    assert len(client.calls) == 5
    # 워밍업 호출은 num_predict=16
    assert client.calls[0]["options"]["num_predict"] == 16
    assert client.calls[1]["options"]["num_predict"] == 16
    # 본 측정은 디폴트 num_predict (테스트에서는 미지정 → DEFAULT_NUM_PREDICT)
    assert client.calls[2]["options"]["num_predict"] == bench.DEFAULT_NUM_PREDICT


@pytest.mark.asyncio
async def test_run_benchmark_empty_samples_raises(bench: Any) -> None:
    """빈 표본은 ValueError."""
    client = MockOllamaClient()
    with pytest.raises(ValueError, match="표본"):
        await bench.run_benchmark(model="mock", samples=[], concurrencies=[1], client=client)


@pytest.mark.asyncio
async def test_run_benchmark_empty_concurrencies_raises(bench: Any) -> None:
    """빈 동시도는 ValueError."""
    client = MockOllamaClient()
    samples = _make_samples(bench, n=2)
    with pytest.raises(ValueError, match="concurrencies"):
        await bench.run_benchmark(model="mock", samples=samples, concurrencies=[], client=client)


# ---- report 직렬화 --------------------------------------------------------
@pytest.mark.asyncio
async def test_report_to_dict_is_json_serializable(bench: Any) -> None:
    """report_to_dict 출력이 json.dumps 가능해야 함."""
    client = MockOllamaClient(latency_seq=[0.005] * 100, eval_count=10)
    samples = _make_samples(bench, n=3)
    report = await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1],
        warmup_calls=0,
        client=client,
    )
    d = bench.report_to_dict(report)
    # JSON 왕복
    s = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(s)
    assert parsed["model"] == "mock"
    assert parsed["gate_p50_under_2s"] is True
    assert isinstance(parsed["concurrency_runs"], list)
    assert parsed["concurrency_runs"][0]["concurrent"] == 1


@pytest.mark.asyncio
async def test_report_machine_detection(bench: Any) -> None:
    """machine 필드에 platform 정보가 채워지는지."""
    client = MockOllamaClient(latency_seq=[0.001])
    samples = _make_samples(bench, n=2)
    report = await bench.run_benchmark(
        model="mock",
        samples=samples,
        concurrencies=[1],
        warmup_calls=0,
        client=client,
    )
    assert "platform" in report.machine
    assert "python_version" in report.machine


# ---- CLI parser -----------------------------------------------------------
def test_parse_concurrency_sorted_unique(bench: Any) -> None:
    """중복·순서 무관, 정렬된 결과."""
    assert bench._parse_concurrency("4,1,2,4") == [1, 2, 4]
    assert bench._parse_concurrency("8") == [8]


def test_parse_concurrency_rejects_empty(bench: Any) -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        bench._parse_concurrency(",,, ")


def test_parse_concurrency_rejects_zero(bench: Any) -> None:
    """0/음수 제외 후 빈 결과면 에러."""
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        bench._parse_concurrency("0")


# ---- main() 엔트리 (출력 파일 생성까지) ------------------------------------
# main() 내부에서 asyncio.run() 을 호출하므로, 이 그룹의 테스트는 *동기* 함수.
# asyncio_mode=auto 환경에서 비동기 함수로 작성하면 이미 실행 중인 루프와 충돌.
def test_main_writes_output_file(
    bench: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """main() 이 결과 JSON 파일을 작성하는지 (CLI 표면 검증).

    실제 ollama 클라이언트 생성을 가로채기 위해 _build_default_client 를 모킹.
    """
    monkeypatch.setattr(
        bench,
        "_build_default_client",
        lambda host: MockOllamaClient(latency_seq=[0.001] * 100, eval_count=10),
    )

    output_file = tmp_path / "out.json"
    rc = bench.main(
        [
            "--model",
            "mock",
            "--samples",
            str(_SAMPLES_PATH),
            "--output",
            str(output_file),
            "--concurrency",
            "1",
            "--warmup",
            "0",
            "--gate-ms",
            "10000",  # 모의 응답은 매우 빨라 통과 보장
        ]
    )
    assert rc == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["model"] == "mock"
    assert data["gate_p50_under_2s"] is True


def test_main_returns_failure_when_gate_missed(
    bench: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """게이트 미달 시 종료 코드 1."""
    monkeypatch.setattr(
        bench,
        "_build_default_client",
        lambda host: MockOllamaClient(latency_seq=[0.5] * 100, eval_count=10),
    )
    output_file = tmp_path / "out_fail.json"
    rc = bench.main(
        [
            "--model",
            "mock",
            "--samples",
            str(_SAMPLES_PATH),
            "--output",
            str(output_file),
            "--concurrency",
            "1",
            "--warmup",
            "0",
            "--gate-ms",
            "100",  # 모의 500ms → 미달
        ]
    )
    assert rc == 1
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["gate_p50_under_2s"] is False


def test_main_missing_samples_returns_error(bench: Any, tmp_path: Path) -> None:
    """없는 표본 경로 → 종료 코드 2."""
    rc = bench.main(
        [
            "--model",
            "mock",
            "--samples",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "x.json"),
            "--concurrency",
            "1",
        ]
    )
    assert rc == 2


# ---- 정적 자산 검증 (보너스) ----------------------------------------------
def test_shell_scripts_have_shebang_and_strict_mode() -> None:
    """모든 .sh 가 #!/usr/bin/env bash 와 set -euo pipefail 포함."""
    infra = Path(__file__).resolve().parents[2] / "infra" / "phaiakes9"
    shells = list(infra.rglob("*.sh"))
    assert shells, "최소 1개 이상의 .sh가 있어야 함"
    for sh in shells:
        first_lines = sh.read_text(encoding="utf-8").splitlines()[:30]
        joined = "\n".join(first_lines)
        assert first_lines[0].startswith("#!"), f"{sh} 첫 줄 shebang 누락"
        assert "set -euo pipefail" in joined, f"{sh} set -euo pipefail 누락"


def test_systemd_unit_binds_all_interfaces() -> None:
    """ollama.service 가 0.0.0.0:11434 바인딩."""
    unit = (
        Path(__file__).resolve().parents[2] / "infra" / "phaiakes9" / "systemd" / "ollama.service"
    )
    text = unit.read_text(encoding="utf-8")
    assert "OLLAMA_HOST=0.0.0.0:11434" in text


def test_gitignore_excludes_results() -> None:
    """results/ 가 git ignore 되어야 (개인정보 보호)."""
    gi = Path(__file__).resolve().parents[2] / "infra" / "phaiakes9" / ".gitignore"
    text = gi.read_text(encoding="utf-8")
    assert "results/" in text
