"""Phaiakes9 — Ollama LLM 응답 속도 벤치마크.

M1.1 게이트: p50 < 2s 측정.

사용:
    python bench_latency.py [--model qwen2.5-math:7b-instruct] [--concurrency 1,2,4,8]

환경변수:
    WHYMATH_OLLAMA_HOST       ollama 호스트 (디폴트: http://localhost:11434)
    WHYMATH_BENCH_MODEL       모델 ID (디폴트: qwen2.5-math:7b-instruct)
    WHYMATH_BENCH_CONCURRENCY 콤마 구분 동시도 (디폴트: 1,2,4,8)
    WHYMATH_BENCH_SAMPLES     샘플 JSON 경로 (디폴트: ./sample_prompts.json)
    WHYMATH_BENCH_OUTPUT      결과 JSON 출력 경로 (디폴트: results/<ts>.json)
    WHYMATH_BENCH_NUM_PREDICT 모델당 생성 토큰 한도 (디폴트: 512)
    WHYMATH_BENCH_GATE_MS     게이트 p50 한도 ms (디폴트: 2000)
    WHYMATH_BENCH_WARMUP      워밍업 호출 수 (디폴트: 1)

출력 JSON 스키마는 README.md "측정 지표" 절 참조.

테스트 가능성:
    - `ollama` Python 클라이언트 호출은 `_OllamaClientProtocol` 추상 인터페이스 경유
    - 단위 테스트에서 `run_benchmark(client=MockClient(...))` 로 주입 가능
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Protocol

# ---- 상수 -------------------------------------------------------------------
DEFAULT_HOST: Final[str] = "http://localhost:11434"
DEFAULT_MODEL: Final[str] = "qwen2-math:7b"
DEFAULT_CONCURRENCY: Final[tuple[int, ...]] = (1, 2, 4, 8)
DEFAULT_NUM_PREDICT: Final[int] = 512
DEFAULT_GATE_MS: Final[int] = 2000
DEFAULT_WARMUP: Final[int] = 1


# ---- 도메인 타입 ------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class Sample:
    """벤치마크 표본 1건."""

    id: str
    unit: str
    difficulty: str
    prompt: str


@dataclass(slots=True, frozen=True)
class CallResult:
    """단일 호출 결과."""

    sample_id: str
    latency_ms: float
    output_tokens: int
    success: bool
    error: str | None = None


@dataclass(slots=True)
class ConcurrencyRun:
    """동시도 1단계 (예: concurrent=4) 결과."""

    concurrent: int
    samples: int
    success_count: int
    fail_count: int
    p50_ms: float
    p90_ms: float
    p99_ms: float
    avg_ms: float
    tokens_per_sec: float
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BenchmarkReport:
    """최종 벤치마크 보고서. JSON 직렬화 대상."""

    timestamp: str
    model: str
    host: str
    machine: dict[str, Any]
    samples: int
    num_predict: int
    warmup_calls: int
    gate_p50_ms: int
    concurrency_runs: list[ConcurrencyRun]
    gate_p50_under_2s: bool


# ---- Ollama 클라이언트 추상화 (테스트 주입용) -------------------------------
class _OllamaClientProtocol(Protocol):
    """ollama 비동기 클라이언트의 최소 인터페이스.

    실제 `ollama.AsyncClient` 와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    """

    async def generate(  # noqa: D401 — 외부 라이브러리 시그니처 보존
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def _build_default_client(host: str) -> _OllamaClientProtocol:
    """기본 ollama AsyncClient 생성. import 실패 시 명확한 에러."""
    try:
        from ollama import AsyncClient  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — 환경 의존
        raise RuntimeError(
            "ollama Python 클라이언트가 설치되지 않았습니다. "
            "`pip install ollama` 후 다시 실행하세요."
        ) from exc
    return AsyncClient(host=host)  # type: ignore[no-any-return]


# ---- 유틸 -------------------------------------------------------------------
def load_samples(path: Path) -> list[Sample]:
    """sample_prompts.json 에서 표본 로드."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    samples = raw.get("samples", [])
    return [
        Sample(
            id=str(s["id"]),
            unit=str(s.get("unit", "")),
            difficulty=str(s.get("difficulty", "")),
            prompt=str(s["prompt"]),
        )
        for s in samples
    ]


def detect_machine() -> dict[str, Any]:
    """현재 머신의 기본 사양을 best-effort로 수집."""
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }
    # /proc/cpuinfo 에서 모델명 추출 (Linux만)
    try:
        cpu_path = Path("/proc/cpuinfo")
        if cpu_path.exists():
            for line in cpu_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("model name"):
                    info["cpu"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    # /proc/meminfo 에서 메모리 (GB) 추출
    try:
        mem_path = Path("/proc/meminfo")
        if mem_path.exists():
            for line in mem_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    info["ram_gb"] = round(kb / 1024 / 1024, 1)
                    break
    except (OSError, ValueError, IndexError):
        pass
    return info


def percentile(values: list[float], q: float) -> float:
    """단순 percentile (선형 보간). statistics 의존 최소화."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * q
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


# ---- 호출 실행 --------------------------------------------------------------
async def _call_once(
    client: _OllamaClientProtocol,
    model: str,
    sample: Sample,
    num_predict: int,
) -> CallResult:
    """단일 generate 호출. 예외는 CallResult.error 로 흡수."""
    start = time.perf_counter()
    try:
        response = await client.generate(
            model=model,
            prompt=sample.prompt,
            stream=False,
            options={"num_predict": num_predict},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        # eval_count 는 ollama 응답의 생성 토큰 수
        output_tokens = int(response.get("eval_count", 0) or 0)
        return CallResult(
            sample_id=sample.id,
            latency_ms=elapsed_ms,
            output_tokens=output_tokens,
            success=True,
        )
    except Exception as exc:  # noqa: BLE001 — 모든 오류를 결과로 흡수
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return CallResult(
            sample_id=sample.id,
            latency_ms=elapsed_ms,
            output_tokens=0,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )


async def _run_concurrency(
    client: _OllamaClientProtocol,
    model: str,
    samples: list[Sample],
    concurrent: int,
    num_predict: int,
) -> ConcurrencyRun:
    """동시도 N으로 표본 전체를 1회 처리."""
    sem = asyncio.Semaphore(concurrent)

    async def bounded(s: Sample) -> CallResult:
        async with sem:
            return await _call_once(client, model, s, num_predict)

    wall_start = time.perf_counter()
    results = await asyncio.gather(*(bounded(s) for s in samples))
    wall_elapsed_s = max(time.perf_counter() - wall_start, 1e-6)

    success = [r for r in results if r.success]
    fail = [r for r in results if not r.success]
    latencies = [r.latency_ms for r in success]
    total_tokens = sum(r.output_tokens for r in success)
    tokens_per_sec = total_tokens / wall_elapsed_s if wall_elapsed_s > 0 else 0.0

    return ConcurrencyRun(
        concurrent=concurrent,
        samples=len(samples),
        success_count=len(success),
        fail_count=len(fail),
        p50_ms=round(percentile(latencies, 0.50), 2),
        p90_ms=round(percentile(latencies, 0.90), 2),
        p99_ms=round(percentile(latencies, 0.99), 2),
        avg_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
        tokens_per_sec=round(tokens_per_sec, 2),
        errors=[r.error for r in fail if r.error],
    )


async def _warmup(
    client: _OllamaClientProtocol,
    model: str,
    samples: list[Sample],
    warmup_calls: int,
) -> None:
    """모델 콜드 로드 회피."""
    if warmup_calls <= 0 or not samples:
        return
    print(f"[bench] 워밍업 {warmup_calls}회 (모델 콜드 로드 회피)...", flush=True)
    for i in range(warmup_calls):
        await _call_once(client, model, samples[i % len(samples)], num_predict=16)
    print("[bench] 워밍업 완료", flush=True)


# ---- 공개 API ---------------------------------------------------------------
async def run_benchmark(
    *,
    model: str,
    samples: list[Sample],
    concurrencies: list[int],
    host: str = DEFAULT_HOST,
    num_predict: int = DEFAULT_NUM_PREDICT,
    warmup_calls: int = DEFAULT_WARMUP,
    gate_p50_ms: int = DEFAULT_GATE_MS,
    client: _OllamaClientProtocol | None = None,
) -> BenchmarkReport:
    """벤치마크 1회 수행. 단위 테스트는 client 인자로 모킹.

    Args:
        model: ollama 모델 ID.
        samples: 표본 리스트.
        concurrencies: 측정할 동시도 단계.
        host: ollama 호스트 (client 미주입 시 사용).
        num_predict: 호출당 생성 토큰 한도.
        warmup_calls: 워밍업 횟수.
        gate_p50_ms: 게이트 통과 p50 한도.
        client: 테스트에서 주입하는 모의 클라이언트. None이면 기본 생성.

    Returns:
        BenchmarkReport (JSON 직렬화 가능).
    """
    if not samples:
        raise ValueError("표본이 비어 있습니다. sample_prompts.json 확인.")
    if not concurrencies:
        raise ValueError("concurrencies 가 비어 있습니다.")

    real_client = client if client is not None else _build_default_client(host)

    await _warmup(real_client, model, samples, warmup_calls)

    runs: list[ConcurrencyRun] = []
    for c in concurrencies:
        print(f"[bench] 동시도={c} 시작 ({len(samples)}개 호출)...", flush=True)
        run = await _run_concurrency(real_client, model, samples, c, num_predict)
        runs.append(run)
        status = "✅" if run.fail_count == 0 else f"⚠️ 실패 {run.fail_count}건"
        print(
            f"[bench] 동시도={c} 완료: p50={run.p50_ms}ms / p90={run.p90_ms}ms / "
            f"p99={run.p99_ms}ms / tok/s={run.tokens_per_sec} {status}",
            flush=True,
        )

    # 게이트: 동시도 1의 p50이 한도 이내인지
    baseline = next((r for r in runs if r.concurrent == 1), runs[0])
    gate_passed = baseline.p50_ms > 0 and baseline.p50_ms < gate_p50_ms

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        model=model,
        host=host,
        machine=detect_machine(),
        samples=len(samples),
        num_predict=num_predict,
        warmup_calls=warmup_calls,
        gate_p50_ms=gate_p50_ms,
        concurrency_runs=runs,
        gate_p50_under_2s=gate_passed,
    )


def report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    """BenchmarkReport → JSON 직렬화 가능 dict."""
    d = asdict(report)
    # concurrency_runs 가 dict 리스트로 변환되며 errors 필드 보존
    return d


# ---- CLI --------------------------------------------------------------------
def _parse_concurrency(value: str) -> list[int]:
    """'1,2,4,8' → [1, 2, 4, 8] (중복·0 제거, 정렬)."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    nums = sorted({int(p) for p in parts if int(p) > 0})
    if not nums:
        raise argparse.ArgumentTypeError("동시도 1개 이상 필요 (예: 1,2,4,8)")
    return nums


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phaiakes9 Ollama 응답 속도 벤치마크 (WhyMath M1.1)",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("WHYMATH_BENCH_MODEL", DEFAULT_MODEL),
        help=f"ollama 모델 ID (디폴트: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("WHYMATH_OLLAMA_HOST", DEFAULT_HOST),
        help=f"ollama 호스트 (디폴트: {DEFAULT_HOST})",
    )
    p.add_argument(
        "--concurrency",
        type=_parse_concurrency,
        default=_parse_concurrency(
            os.environ.get(
                "WHYMATH_BENCH_CONCURRENCY",
                ",".join(str(c) for c in DEFAULT_CONCURRENCY),
            )
        ),
        help="콤마 구분 동시도 단계 (디폴트: 1,2,4,8)",
    )
    p.add_argument(
        "--samples",
        type=Path,
        default=Path(
            os.environ.get(
                "WHYMATH_BENCH_SAMPLES",
                str(Path(__file__).parent / "sample_prompts.json"),
            )
        ),
        help="표본 JSON 경로",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("WHYMATH_BENCH_OUTPUT", "")) or None,
        help="결과 JSON 경로 (미지정 시 ./results/<ts>.json)",
    )
    p.add_argument(
        "--num-predict",
        type=int,
        default=int(os.environ.get("WHYMATH_BENCH_NUM_PREDICT", DEFAULT_NUM_PREDICT)),
        help=f"호출당 생성 토큰 한도 (디폴트: {DEFAULT_NUM_PREDICT})",
    )
    p.add_argument(
        "--gate-ms",
        type=int,
        default=int(os.environ.get("WHYMATH_BENCH_GATE_MS", DEFAULT_GATE_MS)),
        help=f"게이트 p50 한도 ms (디폴트: {DEFAULT_GATE_MS})",
    )
    p.add_argument(
        "--warmup",
        type=int,
        default=int(os.environ.get("WHYMATH_BENCH_WARMUP", DEFAULT_WARMUP)),
        help=f"워밍업 호출 수 (디폴트: {DEFAULT_WARMUP})",
    )
    return p


def _default_output_path() -> Path:
    """results/YYYY-MM-DD_HHMMSS.json"""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = Path(__file__).parent.parent / "results"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{ts}.json"


def main(argv: list[str] | None = None) -> int:
    """엔트리포인트. 종료 코드: 0=게이트 통과, 1=실패, 2=에러."""
    args = _build_arg_parser().parse_args(argv)

    if not args.samples.exists():
        print(f"[bench] ❌ 표본 파일 없음: {args.samples}", file=sys.stderr)
        return 2

    samples = load_samples(args.samples)
    if not samples:
        print(f"[bench] ❌ 표본이 비어 있음: {args.samples}", file=sys.stderr)
        return 2

    print(f"[bench] 모델: {args.model}")
    print(f"[bench] 호스트: {args.host}")
    print(f"[bench] 동시도: {args.concurrency}")
    print(f"[bench] 표본 수: {len(samples)}")
    print(f"[bench] num_predict: {args.num_predict}")
    print(f"[bench] 게이트: p50 < {args.gate_ms}ms")
    print()

    try:
        report = asyncio.run(
            run_benchmark(
                model=args.model,
                samples=samples,
                concurrencies=args.concurrency,
                host=args.host,
                num_predict=args.num_predict,
                warmup_calls=args.warmup,
                gate_p50_ms=args.gate_ms,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bench] ❌ 벤치마크 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    out_path = args.output or _default_output_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report_to_dict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("[bench] ─────────────────────────────────────")
    print(f"[bench] 결과 저장: {out_path}")
    print(
        f"[bench] 게이트 (p50 < {args.gate_ms}ms): "
        f"{'✅ PASS' if report.gate_p50_under_2s else '❌ FAIL'}"
    )

    return 0 if report.gate_p50_under_2s else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
