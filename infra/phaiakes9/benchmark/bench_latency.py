"""Phaiakes9 — Ollama LLM 응답 속도 벤치마크 (Linux/CI 경로).

M1.1 게이트: p50 < 2s 측정.

**역할 경계 (2026-08-21 확정)**: 이 도구는 *CI에서 상시 도는 계측 계약* 담당이다.
Kiki 머신(Windows)의 성능 측정·튜닝 정본은 `docs/ops/amd395_local_llm_performance.md`와
`scripts/ops/{collect_gpu_evidence,bench_ollama}.ps1`이며, 전용 VRAM 실바이트·전원 계획·
드라이버·서버 로그 등 Python으로 못 읽는 증거는 그쪽이 수집한다. 설정 권고가 충돌하면
그 문서가 이긴다. 여기서는 *권고하지 않고 기록·판정만* 한다.

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

측정 조건 인자 (OPS-46 — 미지정 시 결과가 "비교 불가"로 표시된다):
    --gpu-backend ROCm|DirectML|Vulkan|CPU
    --cmos "auto" | "UMA Fixed 64GB"
    --power-profile "기본" | "성능 140W"
    --cooling "쿨링 부족" | "평균" | "증설 완료"
    --thermal-drift-probe   첫 동시도를 마지막에 재실행해 tok/s 하락률 기록

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
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final, Protocol

# ---- 상수 -------------------------------------------------------------------
DEFAULT_HOST: Final[str] = "http://localhost:11434"
DEFAULT_MODEL: Final[str] = "qwen2-math:7b"
DEFAULT_CONCURRENCY: Final[tuple[int, ...]] = (1, 2, 4, 8)
DEFAULT_NUM_PREDICT: Final[int] = 512
DEFAULT_GATE_MS: Final[int] = 2000
DEFAULT_WARMUP: Final[int] = 1

ENV_SCHEMA_VERSION: Final[int] = 2
"""결과 JSON의 환경 기록 스키마 버전 (OPS-46).

v1 = 이 필드가 **아예 없던** 결과 = 측정 조건(냉각·CMOS·백엔드·VRAM) 미기록 =
     **다른 시점 결과와 비교 불가**. `environment_comparable()`이 이를 기계로 판정한다.

왜 버전을 박는가: 2026-05-16(9.22 tok/s)과 2026-08-14(0.5~1 tok/s) 두 측정이
같은 조건에서 잰 것인지 알 방법이 없어 둘 다 폐기해야 했다(경위:
`infra/phaiakes9/LLM_STACK_TUNING.md` §1). 버전 필드가 없으면 미래 세션이
v1 결과를 또 유효한 기준선으로 오인한다.
"""

OLLAMA_ENV_KEYS: Final[tuple[str, ...]] = (
    "OLLAMA_HOST",
    "OLLAMA_CONTEXT_LENGTH",
    "OLLAMA_NUM_PARALLEL",
    "OLLAMA_MAX_LOADED_MODELS",
    "OLLAMA_FLASH_ATTENTION",
    "OLLAMA_KV_CACHE_TYPE",
    "OLLAMA_KEEP_ALIVE",
    "OLLAMA_GPU_OVERHEAD",
    "OLLAMA_SCHED_SPREAD",
    "OLLAMA_NUM_GPU",
    "OLLAMA_MODELS",
    "OLLAMA_DEBUG",
    "HSA_OVERRIDE_GFX_VERSION",
)
"""성능에 직접 영향을 주는 Ollama 환경변수 — 결과에 그대로 스냅샷한다.

CONTEXT_LENGTH·NUM_PARALLEL은 KV 캐시 크기를 곱으로 키워 부분 오프로드를 유발할 수
있으므로, 이 값을 모르면 tok/s를 해석할 수 없다.
권장값의 정본은 `docs/ops/amd395_local_llm_performance.md` L6·L7 — 여기서는 *기록*만 한다.
"""

_PROBE_TIMEOUT_S: Final[float] = 3.0
"""환경 프로브 HTTP 타임아웃. 프로브 실패가 벤치 자체를 막으면 안 되므로 짧게."""


# ---- 관측 상태 (날조 0 원칙) -------------------------------------------------
class ObsStatus(str, Enum):
    """관측값의 획득 상태. `whymath_backend/harness/wh1_evaluation.py`의 MetricStatus 선례.

    **가짜 0/빈문자를 쓰지 않는 이유**: 온도 0℃와 "온도를 못 읽었음"은 완전히 다른데,
    0으로 적어 두면 미래 세션이 이를 실측으로 오인한다. 값이 없으면 value=None이고,
    *왜* 없는지가 status와 note에 남는다.
    """

    MEASURED = "MEASURED"  # 실제로 읽었다
    NO_DATA = "NO_DATA"  # 읽으려 했으나 응답/파일에 값이 없었다
    UNSUPPORTED = "UNSUPPORTED"  # 이 플랫폼/환경에서 획득 경로가 없다
    NOT_PROVIDED = "NOT_PROVIDED"  # 사람이 입력해야 하는데 미입력


@dataclass(slots=True, frozen=True)
class Observed:
    """단일 관측값 = (값, 획득 상태, 사유). 값이 없으면 value is None."""

    value: Any
    status: str
    note: str = ""

    @classmethod
    def measured(cls, value: Any, note: str = "") -> Observed:
        return cls(value=value, status=ObsStatus.MEASURED.value, note=note)

    @classmethod
    def absent(cls, status: ObsStatus, note: str) -> Observed:
        """획득 실패. note에 **사유**를 반드시 적는다(CLAUDE.md 침묵 실패 금지)."""
        return cls(value=None, status=status.value, note=note)

    @property
    def is_measured(self) -> bool:
        return self.status == ObsStatus.MEASURED.value


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
    """단일 호출 결과.

    **프리필/생성 분리(OPS-45)**: `prompt_eval_*`(프리필=연산 바운드)과
    `eval_*`(생성=대역폭 바운드)는 느려지는 원인이 다르다 —
    써멀·전원은 프리필을 크게 때리고, 부분 오프로드/KV 폭발은 생성을 파국적으로 때린다.
    둘을 합산한 wall-clock만 보면 두 원인이 구분되지 않는다.
    (성능 해석의 정본: `docs/ops/amd395_local_llm_performance.md` §2·L2)

    ollama 응답의 duration 계열은 **나노초**다 → ms로 환산해 저장한다.
    필드가 없으면 0이 아니라 **None**이다(날조 0 금지).
    """

    sample_id: str
    latency_ms: float
    output_tokens: int
    success: bool
    error: str | None = None
    prompt_tokens: int | None = None
    prompt_eval_ms: float | None = None
    eval_ms: float | None = None
    load_ms: float | None = None


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
    # ── OPS-45: 프리필/생성 분리 지표 (획득 불가 시 None) ──
    prompt_tokens_total: int | None = None
    prefill_tokens_per_sec: float | None = None
    decode_tokens_per_sec: float | None = None
    timing_status: str = ObsStatus.NO_DATA.value
    timing_note: str = ""


@dataclass(slots=True)
class EnvironmentCapture:
    """측정 시점의 환경 조건 (OPS-46).

    **왜 필요한가**: 이게 없으면 서로 다른 시점의 tok/s를 비교할 수 없다.
    2026-05·2026-08 두 측정이 정확히 이 상태였고, 그래서 회귀 판정을 회수해야 했다.

    항목별 획득 경로:
      · ollama_version / loaded_model / vram_fraction → ollama HTTP API (자동)
      · ollama_env                                    → 프로세스 환경변수 (자동)
      · gpu_temp_c                                    → Linux sysfs (Windows는 UNSUPPORTED)
      · gpu_backend / cmos_profile / power_profile / cooling
                                                      → **사람이 CLI로 입력** (자동 획득 경로 없음)
    """

    schema_version: int
    ollama_version: Observed
    loaded_model: Observed
    vram_fraction: Observed
    ollama_env: dict[str, str]
    gpu_temp_c_before: Observed
    gpu_temp_c_after: Observed
    gpu_backend: Observed
    cmos_profile: Observed
    power_profile: Observed
    cooling: Observed


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
    environment: EnvironmentCapture | None = None
    thermal_drift: Observed | None = None


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


# ---- 환경 프로브 (OPS-46) ---------------------------------------------------
class _EnvProbeProtocol(Protocol):
    """측정 환경을 읽는 최소 인터페이스. 테스트는 가짜 프로브를 주입한다."""

    def ollama_version(self) -> Observed: ...

    def loaded_model(self, model: str) -> tuple[Observed, Observed]: ...

    def gpu_temp_c(self) -> Observed: ...


class HttpEnvProbe:
    """Ollama HTTP API + OS sysfs로 환경을 읽는 기본 프로브.

    **프로브 실패는 벤치를 막지 않는다** — 모든 실패는 `Observed.absent(...)`로 흡수하되
    **예외 타입명을 note에 반드시 남긴다**(CLAUDE.md 침묵 실패 금지: 무타입 경고 금지).
    """

    def __init__(self, host: str, timeout_s: float = _PROBE_TIMEOUT_S) -> None:
        self._host = host.rstrip("/")
        self._timeout_s = timeout_s

    def _get_json(self, path: str) -> tuple[dict[str, Any] | None, str]:
        """GET {host}{path} → (dict, "") 또는 (None, 실패사유). 예외 타입명 포함."""
        url = f"{self._host}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout_s) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return None, f"{path} 응답이 dict가 아님: {type(payload).__name__}"
            return payload, ""
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def ollama_version(self) -> Observed:
        payload, why = self._get_json("/api/version")
        if payload is None:
            return Observed.absent(ObsStatus.NO_DATA, f"/api/version 조회 실패 — {why}")
        version = payload.get("version")
        if not version:
            return Observed.absent(ObsStatus.NO_DATA, "/api/version 응답에 version 키 없음")
        return Observed.measured(str(version))

    def loaded_model(self, model: str) -> tuple[Observed, Observed]:
        """`ollama ps` 상당. → (적재 모델 요약, GPU 상주 비율).

        **vram_fraction이 이 프로브의 존재 이유다.** 적재 위치(GPU 전량이냐 CPU 분할이냐)는
        온도가 아니라 VRAM 예산이 정하므로, 이 값은 **냉각 상태와 완전히 독립**으로
        부분 오프로드를 확정/기각한다. 1.0 = 100% GPU, 미만이면 그만큼 CPU로 흘렀다.
        Windows 측 정본 구현은 `scripts/ops/bench_ollama.ps1`의 `gpu_fraction`(동일 산식).
        """
        payload, why = self._get_json("/api/ps")
        if payload is None:
            fail = Observed.absent(ObsStatus.NO_DATA, f"/api/ps 조회 실패 — {why}")
            return fail, fail
        models = payload.get("models") or []
        entry = next((m for m in models if str(m.get("name", "")).startswith(model)), None)
        if entry is None:
            names = ", ".join(str(m.get("name", "?")) for m in models) or "(적재 0건)"
            miss = Observed.absent(
                ObsStatus.NO_DATA,
                f"/api/ps에 모델 {model!r} 미적재 — 적재 목록: {names}",
            )
            return miss, miss
        size = int(entry.get("size", 0) or 0)
        size_vram = int(entry.get("size_vram", 0) or 0)
        summary = Observed.measured(
            {"name": entry.get("name"), "size": size, "size_vram": size_vram}
        )
        if size <= 0:
            return summary, Observed.absent(
                ObsStatus.NO_DATA, "/api/ps size가 0 이하라 GPU 비율 계산 불가"
            )
        return summary, Observed.measured(round(size_vram / size, 4))

    def gpu_temp_c(self) -> Observed:
        """Linux sysfs hwmon에서 GPU 온도(℃). Windows는 획득 경로가 없다."""
        if not sys.platform.startswith("linux"):
            return Observed.absent(
                ObsStatus.UNSUPPORTED,
                f"stdlib로 GPU 온도를 읽을 경로 없음 (platform={sys.platform}) — "
                "--cooling 으로 수기 기록하거나 외부 툴(HWiNFO 등) 값을 병기할 것",
            )
        try:
            for hwmon in sorted(Path("/sys/class/drm").glob("card*/device/hwmon/hwmon*")):
                temp_file = hwmon / "temp1_input"
                if temp_file.exists():
                    milli = int(temp_file.read_text(encoding="utf-8").strip())
                    return Observed.measured(round(milli / 1000.0, 1))
        except (OSError, ValueError) as exc:
            return Observed.absent(
                ObsStatus.NO_DATA, f"sysfs hwmon 읽기 실패 — {type(exc).__name__}: {exc}"
            )
        return Observed.absent(ObsStatus.NO_DATA, "sysfs에서 drm hwmon temp1_input을 찾지 못함")


class NullEnvProbe:
    """아무것도 조회하지 않는 프로브 — **테스트 hermetic 보장용**.

    HttpEnvProbe는 `{host}/api/version`·`/api/ps`를 실제로 두드린다. 테스트가 이걸
    그대로 쓰면 **Ollama가 떠 있는 머신과 아닌 머신에서 다르게 동작한다** —
    OPS-44에서 실제로 겪은 결함 유형이다(로컬 Ollama 도달로 'provider 없음' 전제 붕괴 5건).
    그래서 단위 테스트는 반드시 이 프로브를 주입한다.
    """

    _WHY = "NullEnvProbe — 테스트/오프라인용 프로브라 환경을 조회하지 않는다"

    def ollama_version(self) -> Observed:
        return Observed.absent(ObsStatus.UNSUPPORTED, self._WHY)

    def loaded_model(self, model: str) -> tuple[Observed, Observed]:
        absent = Observed.absent(ObsStatus.UNSUPPORTED, self._WHY)
        return absent, absent

    def gpu_temp_c(self) -> Observed:
        return Observed.absent(ObsStatus.UNSUPPORTED, self._WHY)


def collect_ollama_env() -> dict[str, str]:
    """성능에 영향을 주는 OLLAMA_* 환경변수 스냅샷 — **설정된 것만** 담는다.

    미설정 키를 빈 문자열로 채우지 않는다: "설정 안 함"과 "빈 값으로 설정함"은 다르고,
    Ollama는 그 둘을 다르게 해석한다.
    """
    return {k: os.environ[k] for k in OLLAMA_ENV_KEYS if k in os.environ}


def environment_comparable(report: dict[str, Any]) -> tuple[bool, str]:
    """결과 dict가 **다른 시점 결과와 비교 가능한지** 기계 판정 (OPS-46 acceptance ③).

    Returns:
        (비교가능 여부, 사유). 비교 불가면 사유에 무엇이 빠졌는지 적는다.
    """
    env = report.get("environment")
    if not isinstance(env, dict):
        return False, "environment 필드 없음 (v1) — 측정 조건 미기록이라 다른 시점과 비교 불가"
    version = env.get("schema_version")
    if version != ENV_SCHEMA_VERSION:
        return False, f"환경 스키마 버전 불일치 (기록={version}, 현재={ENV_SCHEMA_VERSION})"
    missing = [
        key
        for key in ("gpu_backend", "cmos_profile", "power_profile", "cooling")
        if not isinstance(env.get(key), dict) or env[key].get("status") != ObsStatus.MEASURED.value
    ]
    if missing:
        return False, (
            f"사람이 입력해야 하는 조건 미기록: {', '.join(missing)} — "
            "--gpu-backend/--cmos/--power-profile/--cooling 로 지정할 것"
        )
    return True, "측정 조건 전부 기록됨"


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


def _opt_int(raw: Any) -> int | None:
    """정수 변환. 값이 없으면 **0이 아니라 None**(날조 0 금지)."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _ns_to_ms(raw: Any) -> float | None:
    """ollama duration(나노초) → ms. 값이 없으면 None."""
    value = _opt_int(raw)
    if value is None:
        return None
    return round(value / 1_000_000.0, 2)


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
            prompt_tokens=_opt_int(response.get("prompt_eval_count")),
            prompt_eval_ms=_ns_to_ms(response.get("prompt_eval_duration")),
            eval_ms=_ns_to_ms(response.get("eval_duration")),
            load_ms=_ns_to_ms(response.get("load_duration")),
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

    prefill_tps, decode_tps, prompt_total, timing_status, timing_note = _split_timings(success)

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
        prompt_tokens_total=prompt_total,
        prefill_tokens_per_sec=prefill_tps,
        decode_tokens_per_sec=decode_tps,
        timing_status=timing_status,
        timing_note=timing_note,
    )


def _split_timings(
    success: list[CallResult],
) -> tuple[float | None, float | None, int | None, str, str]:
    """성공 호출들에서 **프리필 tok/s**와 **생성 tok/s**를 분리 집계 (OPS-45).

    합산 wall-clock 기반 `tokens_per_sec`과 달리, 이 둘은 ollama가 보고한
    `prompt_eval_duration`/`eval_duration`만 쓴다 — 큐 대기·네트워크가 섞이지 않는다.

    두 지표의 지문이 반대라서 원인이 갈린다:
      · 써멀 스로틀        → 프리필(연산)이 크게 떨어지고 생성은 상대적으로 덜 떨어진다
      · 부분 오프로드/KV   → 생성(대역폭)이 파국적으로 떨어진다

    Returns:
        (프리필 tok/s, 생성 tok/s, 프롬프트 토큰 합, 상태, 사유).
        하나라도 못 구하면 해당 값은 **None**이고 상태가 NO_DATA다(가짜 0 금지).
    """
    if not success:
        return None, None, None, ObsStatus.NO_DATA.value, "성공한 호출이 0건"

    timed = [r for r in success if r.prompt_eval_ms is not None and r.eval_ms is not None]
    if not timed:
        return (
            None,
            None,
            None,
            ObsStatus.NO_DATA.value,
            "ollama 응답에 prompt_eval_duration/eval_duration 없음 — "
            "구 버전 서버이거나 응답 스키마가 다르다. 프리필/생성 분리 불가",
        )

    prompt_total = sum(r.prompt_tokens or 0 for r in timed)
    output_total = sum(r.output_tokens for r in timed)
    prefill_ms = sum(r.prompt_eval_ms or 0.0 for r in timed)
    decode_ms = sum(r.eval_ms or 0.0 for r in timed)

    prefill_tps = round(prompt_total / (prefill_ms / 1000.0), 2) if prefill_ms > 0 else None
    decode_tps = round(output_total / (decode_ms / 1000.0), 2) if decode_ms > 0 else None

    note = ""
    if len(timed) < len(success):
        note = f"타이밍 보유 {len(timed)}/{len(success)}건만 집계 (나머지는 필드 없음)"
    return prefill_tps, decode_tps, prompt_total, ObsStatus.MEASURED.value, note


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


def _manual(value: str | None, flag: str) -> Observed:
    """사람이 입력하는 환경 항목. 미입력이면 **빈 문자열이 아니라** NOT_PROVIDED."""
    if value:
        return Observed.measured(value)
    return Observed.absent(
        ObsStatus.NOT_PROVIDED,
        f"자동 획득 경로 없음 — {flag} 로 지정해야 다른 시점 결과와 비교 가능해진다",
    )


def _print_environment(env: EnvironmentCapture) -> None:
    """환경 캡처 요약 출력 + **비교 불가 상태를 큰 소리로 경고**한다.

    갭을 조용히 넘기면 미래 세션이 이 결과를 유효한 기준선으로 오인한다 —
    2026-05·2026-08 측정이 정확히 그렇게 오인됐다.
    """
    print("[bench] ── 측정 환경 ──", flush=True)
    print(f"[bench]   ollama 버전     : {_fmt_obs(env.ollama_version)}", flush=True)
    print(f"[bench]   GPU 상주 비율   : {_fmt_obs(env.vram_fraction)}", flush=True)
    if env.vram_fraction.is_measured and float(env.vram_fraction.value) < 1.0:
        pct = float(env.vram_fraction.value) * 100
        print(
            f"[bench]   ⚠️ 모델이 100% GPU가 아니다 ({pct:.1f}%) — 부분 오프로드 상태다. "
            "이 상태의 tok/s는 스택 성능이 아니라 오프로드 페널티를 재는 것이다.",
            flush=True,
        )
    print(f"[bench]   GPU 백엔드      : {_fmt_obs(env.gpu_backend)}", flush=True)
    print(f"[bench]   CMOS            : {_fmt_obs(env.cmos_profile)}", flush=True)
    print(f"[bench]   전력 프로파일   : {_fmt_obs(env.power_profile)}", flush=True)
    print(f"[bench]   냉각            : {_fmt_obs(env.cooling)}", flush=True)
    print(f"[bench]   OLLAMA_* 환경변수: {env.ollama_env or '(설정된 것 없음)'}", flush=True)

    missing = [
        flag
        for obs, flag in (
            (env.gpu_backend, "--gpu-backend"),
            (env.cmos_profile, "--cmos"),
            (env.power_profile, "--power-profile"),
            (env.cooling, "--cooling"),
        )
        if not obs.is_measured
    ]
    if missing:
        print(
            f"[bench]   ⚠️ 측정 조건 미기록: {', '.join(missing)} — "
            "이 결과는 **다른 시점 결과와 비교할 수 없다**.",
            flush=True,
        )
    print(flush=True)


def _fmt_obs(obs: Observed) -> str:
    """Observed 를 사람이 읽는 한 줄로. 미획득이면 사유를 그대로 보여준다."""
    if obs.is_measured:
        return f"{obs.value}"
    return f"({obs.status}) {obs.note}"


async def _thermal_drift(
    client: _OllamaClientProtocol,
    model: str,
    samples: list[Sample],
    concurrencies: list[int],
    num_predict: int,
    runs: list[ConcurrencyRun],
    enabled: bool,
) -> Observed:
    """첫 동시도 단계를 마지막에 재실행해 tok/s 하락률(%)을 잰다.

    온도 센서를 못 읽는 환경(Windows)에서 **써멀 스로틀의 행동 기반 프록시**다:
    같은 부하를 앞뒤로 두 번 돌렸는데 뒤가 느리면 열을 의심할 근거가 된다.
    양수 = 뒤가 느려짐(스로틀 의심), 음수 = 뒤가 빨라짐(초기 워밍업 잔여).
    """
    if not enabled:
        return Observed.absent(
            ObsStatus.NOT_PROVIDED, "--thermal-drift-probe 미지정 (기본 off — 측정 시간 2배)"
        )
    first = runs[0] if runs else None
    if first is None or first.tokens_per_sec <= 0:
        return Observed.absent(ObsStatus.NO_DATA, "기준 동시도 결과가 없거나 tok/s가 0")

    print(f"[bench] 써멀 드리프트 프로브: 동시도={concurrencies[0]} 재실행...", flush=True)
    again = await _run_concurrency(client, model, samples, concurrencies[0], num_predict)
    if again.tokens_per_sec <= 0:
        return Observed.absent(ObsStatus.NO_DATA, "재실행 tok/s가 0 — 드리프트 계산 불가")

    drop_pct = round((first.tokens_per_sec - again.tokens_per_sec) / first.tokens_per_sec * 100, 2)
    return Observed.measured(
        {
            "concurrent": concurrencies[0],
            "first_tokens_per_sec": first.tokens_per_sec,
            "last_tokens_per_sec": again.tokens_per_sec,
            "drop_pct": drop_pct,
        },
        note="양수 = 뒤가 느려짐(써멀 스로틀 의심). 센서 대체 프록시이지 온도 측정이 아니다.",
    )


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
    probe: _EnvProbeProtocol | None = None,
    gpu_backend: str | None = None,
    cmos_profile: str | None = None,
    power_profile: str | None = None,
    cooling: str | None = None,
    thermal_drift_probe: bool = False,
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
        probe: 환경 프로브. None이면 HttpEnvProbe(host). 테스트는 가짜를 주입.
        gpu_backend: GPU 백엔드(ROCm/DirectML/Vulkan/CPU) — 자동 획득 경로가 없어 사람이 입력.
        cmos_profile: BIOS/CMOS 설정 상태(예: "auto", "UMA Fixed 64GB").
        power_profile: 전력·TDP 프로파일.
        cooling: 냉각 상태 메모(예: "쿨링 부족", "평균", "증설 완료").
        thermal_drift_probe: True면 **첫 동시도 단계를 마지막에 한 번 더** 재실행해
            앞뒤 tok/s 차이를 기록한다. 온도 센서가 없는 환경(Windows)에서 써멀
            스로틀을 잡는 **행동 기반 프록시** — 뒤가 유의미하게 느리면 열을 의심한다.

    Returns:
        BenchmarkReport (JSON 직렬화 가능).
    """
    if not samples:
        raise ValueError("표본이 비어 있습니다. sample_prompts.json 확인.")
    if not concurrencies:
        raise ValueError("concurrencies 가 비어 있습니다.")

    real_client = client if client is not None else _build_default_client(host)
    real_probe = probe if probe is not None else HttpEnvProbe(host)

    await _warmup(real_client, model, samples, warmup_calls)

    # 환경 캡처는 **워밍업 직후**다 — /api/ps는 모델이 적재된 뒤에야 의미가 있다.
    loaded, vram_fraction = real_probe.loaded_model(model)
    temp_before = real_probe.gpu_temp_c()
    environment = EnvironmentCapture(
        schema_version=ENV_SCHEMA_VERSION,
        ollama_version=real_probe.ollama_version(),
        loaded_model=loaded,
        vram_fraction=vram_fraction,
        ollama_env=collect_ollama_env(),
        gpu_temp_c_before=temp_before,
        gpu_temp_c_after=Observed.absent(ObsStatus.NO_DATA, "측정 종료 전"),
        gpu_backend=_manual(gpu_backend, "--gpu-backend"),
        cmos_profile=_manual(cmos_profile, "--cmos"),
        power_profile=_manual(power_profile, "--power-profile"),
        cooling=_manual(cooling, "--cooling"),
    )
    _print_environment(environment)

    runs: list[ConcurrencyRun] = []
    for c in concurrencies:
        print(f"[bench] 동시도={c} 시작 ({len(samples)}개 호출)...", flush=True)
        run = await _run_concurrency(real_client, model, samples, c, num_predict)
        runs.append(run)
        status = "✅" if run.fail_count == 0 else f"⚠️ 실패 {run.fail_count}건"
        print(
            f"[bench] 동시도={c} 완료: p50={run.p50_ms}ms / p90={run.p90_ms}ms / "
            f"p99={run.p99_ms}ms / tok/s={run.tokens_per_sec} "
            f"(프리필 {run.prefill_tokens_per_sec} / 생성 {run.decode_tokens_per_sec}) {status}",
            flush=True,
        )

    environment.gpu_temp_c_after = real_probe.gpu_temp_c()

    drift = await _thermal_drift(
        real_client, model, samples, concurrencies, num_predict, runs, thermal_drift_probe
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
        environment=environment,
        thermal_drift=drift,
    )


def report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    """BenchmarkReport → JSON 직렬화 가능 dict.

    `environment_comparable`의 판정을 **결과 안에 박아 둔다** — 파일만 열어도
    이 결과를 다른 시점과 비교해도 되는지가 드러나야 한다(OPS-46 acceptance ③).
    """
    d = asdict(report)
    comparable, reason = environment_comparable(d)
    d["environment_comparable"] = comparable
    d["environment_comparable_reason"] = reason
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
    # ── 측정 조건 (OPS-46) — 자동 획득 경로가 없어 사람이 입력한다 ──
    p.add_argument(
        "--gpu-backend",
        default=os.environ.get("WHYMATH_BENCH_GPU_BACKEND"),
        help="GPU 백엔드: ROCm / DirectML / Vulkan / CPU (미지정 시 결과가 비교 불가로 표시)",
    )
    p.add_argument(
        "--cmos",
        default=os.environ.get("WHYMATH_BENCH_CMOS"),
        help='BIOS/CMOS 상태 (예: "auto", "UMA Fixed 64GB")',
    )
    p.add_argument(
        "--power-profile",
        default=os.environ.get("WHYMATH_BENCH_POWER_PROFILE"),
        help='전력·TDP 프로파일 (예: "기본", "성능 140W")',
    )
    p.add_argument(
        "--cooling",
        default=os.environ.get("WHYMATH_BENCH_COOLING"),
        help='냉각 상태 (예: "쿨링 부족", "평균", "증설 완료")',
    )
    p.add_argument(
        "--thermal-drift-probe",
        action="store_true",
        help="첫 동시도 단계를 마지막에 재실행해 tok/s 하락률 기록 (측정 시간 증가)",
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
                gpu_backend=args.gpu_backend,
                cmos_profile=args.cmos,
                power_profile=args.power_profile,
                cooling=args.cooling,
                thermal_drift_probe=args.thermal_drift_probe,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bench] ❌ 벤치마크 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    out_path = args.output or _default_output_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report_to_dict(report)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("[bench] ─────────────────────────────────────")
    print(f"[bench] 결과 저장: {out_path}")
    if report.thermal_drift is not None and report.thermal_drift.is_measured:
        print(f"[bench] 써멀 드리프트: {report.thermal_drift.value}")
    # 비교가능 여부는 게이트와 **별개**로 보고한다 — 게이트 PASS라도 조건이
    # 미기록이면 그 수치는 다른 시점과 나란히 놓을 수 없다.
    if payload["environment_comparable"]:
        print("[bench] 환경 기록: ✅ 비교 가능")
    else:
        print(f"[bench] 환경 기록: ⚠️ 비교 불가 — {payload['environment_comparable_reason']}")
    print(
        f"[bench] 게이트 (p50 < {args.gate_ms}ms): "
        f"{'✅ PASS' if report.gate_p50_under_2s else '❌ FAIL'}"
    )

    return 0 if report.gate_p50_under_2s else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
