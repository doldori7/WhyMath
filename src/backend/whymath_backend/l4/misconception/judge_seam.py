"""L3 백킹 judge seam 어댑터 — judge용 `LLMSeam`을 L3 파이프라인으로 구성(슬108).

judge 코어(`judge.py`)·하니스(`semantic_eval.py`)는 `LLMSeam`(async `generate(prompt, system)`)
*Protocol에만* 의존해 L3 import가 없다(계층 분리). 이 모듈은 그 경계를 L3 파이프라인
(`l3.pipeline.generate`·라우터 경유)으로 *실제 결선*하는 **유일한** 자리다 — L3 의존성을 한 파일에
가둔다. 라이브 judge 측정(integration 테스트)·CLI `--judge`만 이 어댑터를 쓴다(coach 미배선·슬108).

**로컬 우선**(CLAUDE.md "클라우드 LLM 호출 전 항상 로컬 LLM 가능성 검토"): 기본(`fast_math`)은
짧은 3값 분류라 *로컬 FAST*(qwen2-math:1.5b)를 노렸으나, 2026-06-15 라이브 측정에서 1.5b가 한국어
판정 형식을 못 맞춰 전부 UNCERTAIN(FP 감소 0)이었다 — `Settings.misconception_judge_routing`로
프로파일 전환(`general_mid`→qwen2.5:7b·`_judge_routing_request` 참조). 어느 경우든 라우터를
경유하므로 LLM 직접 호출 금지(CLAUDE.md 절대 원칙)도 지킨다.
"""

from __future__ import annotations

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.interfaces import (
    CacheBackend,
    InMemoryCache,
    LLMProvider,
    RecordingTraceSink,
    TraceSink,
)
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.pipeline import generate as l3_generate
from whymath_backend.l3.providers.ollama import OllamaProvider


def _judge_routing_request(settings: Settings | None = None) -> RoutingRequest:
    """judge 라우팅 입력 — `Settings.misconception_judge_routing` 프로파일로 모델 선택(슬108).

    **`fast_math`(기본·현행)**: `max_latency_ms=1500`(<2000)으로 FAST 강제(03a §C.2 규칙5)·
    `sync=True`. family는 MATH(task_type 비-NLP) → 로컬 FAST MATH(qwen2-math:1.5b).

    **`general_mid`**: 2026-06-15 라이브 측정에서 fast_math(1.5b)가 한국어 판정 형식
    (`판정: 예/아니오/불확실`)을 못 맞춰 전부 UNCERTAIN(FP 감소 0) — judge는 *수학*이 아니라
    *한국어 NLP 분류*라 일반 instruct 모델이 적합. 라우팅 레버로 GENERAL MID(qwen2.5:7b) 겨냥:
    `task_type="extract"`(NLP→GENERAL·rule6 FAST는 match/classify만 거니 회피) +
    `difficulty="medium"`+`sync`(rule8 → MID) + `max_latency_ms=5000`(rule5 회피).
    `resolve_model(GENERAL, MID)=qwen2.5:7b`. coach 미배선이라 이 전환은 *측정 경로*만 영향.

    `student_subscription="free"`로 두 경우 모두 로컬 유지(CLOUD 승급 가드 회피·03a §E.2).
    """
    resolved = settings if settings is not None else get_settings()
    if resolved.misconception_judge_routing == "general_mid":
        return RoutingRequest(
            task_type="extract",
            difficulty="medium",
            requires_reasoning=True,
            student_subscription="free",
            max_latency_ms=5000,
            sync=True,
        )
    return RoutingRequest(
        task_type="misconception_judge",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        max_latency_ms=1500,
        sync=True,
    )


class L3JudgeSeam:
    """L3 파이프라인 백킹 judge seam — `LLMSeam`(async `generate(prompt, system)`) 충족.

    `generate()` = judge용 `RoutingRequest` 구성 → `l3.pipeline.generate`(라우터 경유·로컬 FAST·
    캐시·관측) → 생성 텍스트 반환. provider/cache/trace는 주입(기본: `OllamaProvider`·
    `InMemoryCache`·`RecordingTraceSink`) — 라이브 측정은 기본값(로컬 Ollama), 테스트는 Fake
    provider를 넣을 수 있다.

    judge 코어의 never-break(seam 예외→UNCERTAIN)는 `LLMJudge`가 *호출자 쪽*에서 처리하므로, 이
    어댑터는 파이프라인 예외(Ollama 미도달 등)를 *그대로 전파*한다 — `LLMJudge.judge`가 잡아
    UNCERTAIN으로 폴백한다(가용성 보존). 이 seam은 *결선*만 하고 폴백 정책을 중복 두지 않는다.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        cache: CacheBackend | None = None,
        trace: TraceSink | None = None,
    ) -> None:
        self._provider: LLMProvider = provider if provider is not None else OllamaProvider()
        self._cache: CacheBackend = cache if cache is not None else InMemoryCache()
        self._trace: TraceSink = trace if trace is not None else RecordingTraceSink()

    async def generate(self, prompt: str, system: str) -> str:
        """judge 프롬프트를 L3 파이프라인(로컬 FAST·라우터 경유)으로 생성해 텍스트 반환."""
        result = await l3_generate(
            _judge_routing_request(),
            prompt,
            system,
            provider=self._provider,
            cache=self._cache,
            trace=self._trace,
        )
        return result.text


__all__ = ["L3JudgeSeam"]
