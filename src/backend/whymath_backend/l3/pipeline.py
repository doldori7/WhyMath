"""L3 생성 파이프라인 — 라우팅 → 캐시 → 생성 → 관측 결선 (M1.2-live S1).

라우터(순수 결정)와 외부 의존(LLMProvider·CacheBackend·TraceSink)을 *조립*하는
얇은 오케스트레이션 계층이다. 결정 로직은 일절 바꾸지 않고 Router.route()에 위임한다.

흐름 (03a §F.1 캐시 키·§F.2 Langfuse 필드·§D.3 QUALITY 비동기):
  1. Router().route(req) → decision
  2. decision.mode == "async"(QUALITY) → 동기 호출 금지 → 명시적 예외(S4에서 큐 연동)
  3. 그 외 → cache_key_for() 로 조회: HIT면 trace+반환, MISS면 provider 생성→cache 저장
     →trace+반환

경계 메모 (CLAUDE.md 절대 금기): 반환 텍스트는 *검증 전 원시 모델 출력*이다. 03 문서
환각 방어 파이프라인을 통과하기 전에는 학생에게 직접 노출 금지 ("LLM 응답을 검증
없이 학생에게 제공 금지").
"""

from __future__ import annotations

from dataclasses import dataclass

from whymath_backend.config import get_settings
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.router import Router, cache_key_for, langfuse_fields


class QualityQueueUnavailableError(RuntimeError):
    """QUALITY(27b) 동기 디스패치 시도 — 비동기 큐는 슬라이스 S4 (03a §D.3).

    QUALITY는 p50≈14초·병렬 미작동이라 동기 호출이 금지된다. 라우터가 mode='async'로
    결정한 요청을 동기 파이프라인이 받으면 이 예외를 던진다. 호출자(엔드포인트)는
    이를 명확한 4xx로 변환해야 하며 500 스택트레이스를 노출하지 않는다.
    """


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """파이프라인 결과 — 라우팅 메타데이터 + 생성 텍스트.

    호출자/엔드포인트가 라우팅 결정(어느 티어·패밀리·모드)과 캐시 적중 여부를
    응답에 노출할 수 있도록 decision을 함께 돌려준다.

    `text`는 *검증 전 원시 출력*이다(모듈 docstring 경계 메모 참조).
    """

    decision: RoutingDecision
    text: str
    cache_hit: bool


async def generate(
    req: RoutingRequest,
    prompt: str,
    system: str,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    cache_ttl_s: int | None = None,
    student_id_hash: str | None = None,
) -> GenerationResult:
    """라우팅 → 캐시 → 생성 → 관측을 조립해 한 번의 생성을 수행한다.

    Args:
        req: 라우팅 입력 신호.
        prompt: 사용자 프롬프트(검증 전 원시 입력).
        system: 시스템 프롬프트.
        provider: LLM 생성 백엔드(LOCAL이면 OllamaProvider).
        cache: 응답 캐시(S1은 인메모리 스텁).
        trace: 관측성 싱크(S1은 RecordingTraceSink).
        cache_ttl_s: 캐시 TTL(초). None이면 Settings.cache_ttl_s.
        student_id_hash: Langfuse 기록용 학생 ID 해시(직접 ID 금지, 03a §F.2).

    Returns:
        GenerationResult — 결정·텍스트·캐시 적중 여부.

    Raises:
        QualityQueueUnavailableError: 라우터가 QUALITY(mode='async')로 결정한 경우.
    """
    decision = Router().route(req)

    # QUALITY(27b)는 동기 호출 불가 — 비동기 큐 경로는 S4 (03a §D.3).
    if decision.mode == "async":
        raise QualityQueueUnavailableError(
            "QUALITY(27b) 동기 호출 불가 — 비동기 큐는 슬라이스 S4 범위다(03a §D.3). "
            f"결정: cost_tier={decision.cost_tier}, local_model={decision.local_model}."
        )

    ttl = cache_ttl_s if cache_ttl_s is not None else get_settings().cache_ttl_s
    key = cache_key_for(prompt, system, decision)

    cached = await cache.get(key)
    if cached is not None:
        # 캐시 적중도 반드시 기록(분포·KPI 왜곡 방지, 03a §F.1).
        trace.record(langfuse_fields(decision, cache_hit=True, student_id_hash=student_id_hash))
        return GenerationResult(decision=decision, text=cached, cache_hit=True)

    # 캐시 미스 → 실제 생성(검증 전 원시 출력) → 캐시 저장 → 기록.
    output = await provider.generate(prompt, system, decision)
    await cache.set(key, output, ttl)
    trace.record(langfuse_fields(decision, cache_hit=False, student_id_hash=student_id_hash))
    return GenerationResult(decision=decision, text=output, cache_hit=False)
