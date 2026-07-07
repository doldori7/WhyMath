"""라이브 프리플라이트 — 라이브 키 투입 *직후 1회* 실행하는 계측 흐름 즉석 검증.

배경
----
Kiki가 Phaiakes9(또는 프로덕션)에 라이브 키(Anthropic·Langfuse)를 수동 주입한 **직후
1회** 실행해, 방금 넣은 키로 실제 계측이 흐르는지 즉석에서 확인하는 도구다. 서버(uvicorn)
를 띄우지 않고 provider를 직접 호출하므로, 배포 파이프라인에 태우기 전 손끝 검증에 쓴다.
LIVE_LLM_ACTIVATION.md §10 "활성 확인/스모크"를 이 단일 명령으로 턴키화한다(§11 판독 연결).

판정 항목
--------
① cloud_configured   — `Settings().anthropic_configured`(config.py). Anthropic 키가 채워졌는가.
② langfuse_configured — `Settings().langfuse_configured`(config.py). 공개키·시크릿키가 둘 다인가.
   도달성      — Anthropic·Ollama `check_status()`(reachable/error)를 /status 없이 직접 점검.
③ 클라우드 스모크    — (스모크 on·anthropic 설정 시) 실 클라우드 CLOUD_MID(Sonnet) 1콜 →
   실측 usage(토큰·지연) → `actual_cost_krw`로 실측 비용(원) 산출. anthropic 미설정이면
   "키 없음"을 명시하고 조용한 실패 없이 graceful skip 한다.

실행
----
    python -m whymath_backend.ops.live_preflight            # 스모크 on(기본) — 실 1콜
    python -m whymath_backend.ops.live_preflight --no-smoke # 판정·도달성만(실 호출 없음)
    python -m whymath_backend.ops.live_preflight --json report.json  # JSON 리포트도 저장

시크릿 안전
----------
키 *값*은 절대 출력하지 않는다 — 설정 여부(bool)·실측 비용(원)·토큰 수만 보고한다.

None-vs-0 원칙(CLAUDE.md "모르면 모른다고")
--------------------------------------------
usage 자체가 없거나(미계측 provider) 클라우드인데 토큰이 미상(None)이면 비용을 **None**으로
남긴다 — '산정 불가(미상)'와 '0원 확정'을 구분한다(값을 지어내지 않음). 로컬만 0.0 확정이며,
이 스모크는 항상 CLOUD_MID라 토큰 미상 시 cost=None이다(pipeline.py 로직과 동형).

종료 코드
--------
- 0  : 정상. *미설정*(키 없음·스모크 skip)은 오류가 아니라 정보이므로 0.
- 2  : 실질 오류 — 클라우드가 *설정됐는데* 도달 불가, 또는 스모크 1콜이 예외로 실패.
  (Ollama 도달성은 정보로만 보고하고 종료 코드를 좌우하지 않는다 — 이 도구가 검증하는
   대상은 방금 주입한 클라우드·관측성 키의 흐름이지 로컬 스택 기동 여부가 아니다.)
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from whymath_backend.config import Settings
from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision
from whymath_backend.l3.providers.anthropic import AnthropicProvider, AnthropicStatus
from whymath_backend.l3.providers.ollama import OllamaProvider, OllamaStatus
from whymath_backend.l3.router import actual_cost_krw

# 스모크 프롬프트 — 가장 짧고 결정적인 산술 1콜(토큰·비용을 실측하려는 것이지 정답 채점이 아님).
_SMOKE_PROMPT = "1 + 1은 얼마인가? 숫자만 답하라."
_SMOKE_SYSTEM = "너는 간결한 수학 조수다. 요청받은 것만 최소로 답한다."

# 종료 코드 — 미설정은 정보(0), 설정됐는데 실패는 오류(2).
_EXIT_OK = 0
_EXIT_ERROR = 2


class _CloudProvider(Protocol):
    """스모크·도달성에 필요한 클라우드 provider 경계 (AnthropicProvider 충족).

    테스트가 라이브 없이 태울 수 있도록 Protocol로 최소 표면만 요구한다.
    """

    @property
    def configured(self) -> bool: ...

    async def check_status(self) -> AnthropicStatus: ...

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult: ...


class _LocalProvider(Protocol):
    """도달성 점검에 필요한 로컬 provider 경계 (OllamaProvider 충족)."""

    async def check_status(self) -> OllamaStatus: ...


# provider 주입 지점 — 기본은 실 provider, 테스트는 가짜를 주입한다(라이브 0).
CloudProviderFactory = Callable[[Settings], _CloudProvider]
LocalProviderFactory = Callable[[Settings], _LocalProvider]


def _default_cloud_provider(settings: Settings) -> _CloudProvider:
    """기본 클라우드 provider — 주입된 Settings로 AnthropicProvider 구성."""
    return AnthropicProvider(settings=settings)


def _default_local_provider(settings: Settings) -> _LocalProvider:
    """기본 로컬 provider — 주입된 Settings로 OllamaProvider 구성."""
    return OllamaProvider(settings=settings)


@dataclass(slots=True, frozen=True)
class SmokeResult:
    """③ 클라우드 스모크 1콜 결과 — 실측 비용·토큰·지연(또는 skip/실패 사유)."""

    ran: bool
    """실제로 1콜을 실행했는가. False면 skipped_reason이 이유를 담는다."""

    skipped_reason: str | None = None
    """스모크를 건너뛴 사유(스모크 off·anthropic 미설정 등). ran=True면 None."""

    cost_krw: float | None = None
    """실측 비용(원) — None이면 '산정 불가(미상)'이지 0원이 아니다(None-vs-0)."""

    input_tokens: int | None = None
    """입력 토큰 수(provider usage 포착). 미상이면 None."""

    output_tokens: int | None = None
    """출력 토큰 수(provider usage 포착). 미상이면 None."""

    latency_ms: float | None = None
    """호출 실측 지연(ms). 미측정이면 None."""

    text_chars: int | None = None
    """생성 텍스트 *길이*만 기록(내용은 로그에 남기지 않음). 실패 시 None."""

    error: str | None = None
    """1콜이 예외로 실패한 경우의 오류 요약. 정상이면 None."""


@dataclass(slots=True, frozen=True)
class Report:
    """프리플라이트 종합 리포트 — 사람용 출력·JSON 직렬화의 단일 진실."""

    cloud_configured: bool
    """① Anthropic 키 설정 여부(Settings 기준·정본)."""

    langfuse_configured: bool
    """② Langfuse 공개키·시크릿키 둘 다 설정 여부(Settings 기준)."""

    cloud_reachable: bool | None
    """클라우드 도달·인증(설정된 경우만 점검, 미설정이면 None=미점검)."""

    cloud_error: str | None
    """클라우드 도달 실패 사유(설정+실패 시). 정상·미설정이면 None."""

    ollama_reachable: bool
    """로컬 Ollama 데몬 도달 여부(정보용 — 종료 코드에 영향 없음)."""

    ollama_error: str | None
    """Ollama 도달 실패 사유. 정상이면 None."""

    smoke: SmokeResult
    """③ 클라우드 스모크 결과."""

    exit_code: int
    """종료 코드 — 0(정상·미설정) / 2(설정됐는데 도달 불가·스모크 실패)."""


def _cloud_mid_decision() -> RoutingDecision:
    """스모크용 CLOUD_MID(Sonnet) 강제 결정 — Opus(HIGH) 아님.

    test_anthropic_integration.py의 클라우드 결정 패턴과 동형(불변식 충족:
    CLOUD_*는 local_family/local_model=None·sync).
    """
    return RoutingDecision(
        cost_tier=CostTier.CLOUD_MID,
        local_family=None,
        local_model=None,
        mode="sync",
        reason="preflight",
        est_latency_ms=3000,
        est_cost_krw=0.0,
    )


async def _run_smoke(cloud: _CloudProvider) -> SmokeResult:
    """실 클라우드 CLOUD_MID 1콜 → 실측 usage·비용(None-vs-0)."""
    decision = _cloud_mid_decision()
    try:
        generated = await cloud.generate(_SMOKE_PROMPT, _SMOKE_SYSTEM, decision)
    except Exception as exc:  # noqa: BLE001 — 스모크 실패를 리포트로 흡수(종료 코드로 표면화)
        return SmokeResult(ran=True, error=f"{type(exc).__name__}: {exc}")

    usage = generated.usage
    # None-vs-0 구분(pipeline.py:234-241 동형): usage 없음 → None; 클라우드인데 토큰 미상 →
    # None; 그 외에만 실측 비용을 산정한다. CLOUD_MID는 항상 클라우드라 토큰 미상 시 None.
    is_cloud = decision.cost_tier is not CostTier.LOCAL
    cost_krw: float | None
    if usage is None:
        cost_krw = None
    elif is_cloud and (usage.input_tokens is None or usage.output_tokens is None):
        cost_krw = None
    else:
        cost_krw = actual_cost_krw(decision, usage)

    return SmokeResult(
        ran=True,
        cost_krw=cost_krw,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        latency_ms=usage.latency_ms if usage is not None else None,
        text_chars=len(generated.text),
    )


async def run_preflight(
    settings: Settings,
    *,
    smoke: bool,
    cloud_provider_factory: CloudProviderFactory = _default_cloud_provider,
    local_provider_factory: LocalProviderFactory = _default_local_provider,
) -> Report:
    """프리플라이트 순수 코어 — 라이브 없이도 provider 주입으로 태울 수 있다.

    순서: ①② 판정(Settings) → 도달성(check_status) → ③ 스모크(설정+on일 때만).
    라이브 호출 여부는 전적으로 주입된 provider·`smoke`·설정 상태가 결정한다.
    """
    # ①② 판정 — Settings가 정본(키 값은 읽지 않고 '채워졌는지'만 본다).
    cloud_configured = settings.anthropic_configured
    langfuse_configured = settings.langfuse_configured

    # 클라우드 도달성 — 설정된 경우만 의미가 있다(미설정이면 None=미점검).
    cloud = cloud_provider_factory(settings)
    cloud_status = await cloud.check_status()
    cloud_reachable = cloud_status.reachable if cloud_configured else None
    cloud_error = cloud_status.error if cloud_configured else None

    # 로컬 Ollama 도달성 — 정보용(종료 코드 무관).
    local = local_provider_factory(settings)
    local_status = await local.check_status()

    # ③ 스모크 — off거나 anthropic 미설정이면 graceful skip(조용한 실패 없음).
    if not smoke:
        smoke_result = SmokeResult(ran=False, skipped_reason="스모크 비활성(--no-smoke)")
    elif not cloud_configured:
        smoke_result = SmokeResult(
            ran=False, skipped_reason="anthropic 미설정(키 없음) — 스모크 skip"
        )
    else:
        smoke_result = await _run_smoke(cloud)

    # 종료 코드 — 설정됐는데 도달 불가, 또는 스모크 예외 실패면 오류(2). 미설정은 0(정보).
    exit_code = _EXIT_OK
    if cloud_configured and cloud_reachable is False:
        exit_code = _EXIT_ERROR
    if smoke_result.error is not None:
        exit_code = _EXIT_ERROR

    return Report(
        cloud_configured=cloud_configured,
        langfuse_configured=langfuse_configured,
        cloud_reachable=cloud_reachable,
        cloud_error=cloud_error,
        ollama_reachable=local_status.reachable,
        ollama_error=local_status.error,
        smoke=smoke_result,
        exit_code=exit_code,
    )


def _fmt_bool(value: bool | None) -> str:
    """bool/None을 사람용 표기로(값이 아니라 상태만)."""
    if value is None:
        return "미점검"
    return "예" if value else "아니오"


def _fmt_cost(cost: float | None) -> str:
    """비용(원) 표기 — None은 '미상'(0원과 구분)."""
    if cost is None:
        return "미상(산정 불가)"
    return f"{cost:.4f}원"


def _render_stdout(report: Report) -> str:
    """사람용 stdout 렌더 — 시크릿 값 없이 판정·도달성·스모크만."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("WhyMath 라이브 프리플라이트 — 키 투입 직후 계측 흐름 검증")
    lines.append("=" * 60)
    lines.append("[판정]")
    lines.append(f"  ① cloud_configured (Anthropic 키)      : {_fmt_bool(report.cloud_configured)}")
    lines.append(
        f"  ② langfuse_configured (공개·시크릿키)  : {_fmt_bool(report.langfuse_configured)}"
    )
    lines.append("[도달성]")
    cloud_line = f"  · Anthropic reachable                  : {_fmt_bool(report.cloud_reachable)}"
    if report.cloud_error:
        cloud_line += f"  ({report.cloud_error})"
    lines.append(cloud_line)
    ollama_line = f"  · Ollama reachable (정보용)            : {_fmt_bool(report.ollama_reachable)}"
    if report.ollama_error:
        ollama_line += f"  ({report.ollama_error})"
    lines.append(ollama_line)
    lines.append("[③ 클라우드 스모크 — CLOUD_MID(Sonnet) 1콜]")
    smoke = report.smoke
    if not smoke.ran:
        lines.append(f"  · skip: {smoke.skipped_reason}")
    elif smoke.error is not None:
        lines.append(f"  · 실패: {smoke.error}")
    else:
        lines.append(f"  · 실측 비용     : {_fmt_cost(smoke.cost_krw)}")
        lines.append(f"  · 입력 토큰     : {smoke.input_tokens}")
        lines.append(f"  · 출력 토큰     : {smoke.output_tokens}")
        lines.append(f"  · 지연(ms)      : {smoke.latency_ms}")
        lines.append(f"  · 응답 길이(자) : {smoke.text_chars}")
    lines.append("-" * 60)
    verdict = "정상(exit 0)" if report.exit_code == _EXIT_OK else f"오류(exit {report.exit_code})"
    lines.append(f"결과: {verdict}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _write_json(report: Report, path: Path) -> None:
    """리포트를 JSON으로 저장 — 시크릿 없이 bool·비용·토큰만(dataclass 직렬화)."""
    path.write_text(
        json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """얇은 CLI — 인자 파싱 → Settings() 직접 생성 → run_preflight → 출력/종료 코드.

    Settings()는 lru_cache(get_settings)를 우회해 *지금* 주입된 키를 읽는다(투입 직후 1회).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.live_preflight",
        description="라이브 키 투입 직후 계측 흐름 1회 검증(cloud/langfuse 설정·도달성·실 1콜).",
    )
    parser.add_argument(
        "--no-smoke",
        dest="smoke",
        action="store_false",
        help="실 클라우드 1콜을 건너뛰고 판정·도달성만 확인(기본은 스모크 on).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="JSON 리포트 저장 경로(선택). 지정 시 사람용 stdout과 함께 저장한다.",
    )
    args = parser.parse_args(argv)

    settings = Settings()  # lru_cache 우회 — 방금 주입한 키를 읽는다
    report = asyncio.run(run_preflight(settings, smoke=args.smoke))

    print(_render_stdout(report))
    if args.json_path is not None:
        json_path = Path(args.json_path)
        _write_json(report, json_path)
        print(f"JSON 리포트 저장: {json_path}")

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
