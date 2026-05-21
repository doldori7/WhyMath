"""L3 생성 파이프라인 — 라우팅 → 캐시 → 생성 → 관측 결선 (M1.2-live S1·S4).

라우터(순수 결정)와 외부 의존(LLMProvider·CacheBackend·TraceSink·AsyncJobQueue)을
*조립*하는 얇은 오케스트레이션 계층이다. 결정 로직은 일절 바꾸지 않고 Router.route()에
위임한다.

흐름 (03a §F.1 캐시 키·§F.2 Langfuse 필드·§D.3 QUALITY 비동기):
  1. Router().route(req) → decision
  2. decision.mode == "async"(QUALITY) → 동기 호출 금지(03a §D.3):
       - queue 미주입 → QualityQueueUnavailableError(미구성 시 안전 폴백, API가 503).
       - queue 주입 → JSON payload enqueue → job_id 반환(GenerationResult.status="queued").
         enqueue 자체 실패(broker 다운)도 QualityQueueUnavailableError로 변환(503).
       - 어느 경우든 provider를 동기 호출하지 않는다. enqueue도 Langfuse에 기록한다.
  3. 그 외(sync) → cache_key_for()로 조회: HIT면 trace+반환, MISS면 provider 생성→cache
     저장→trace+반환

경계 메모 (CLAUDE.md 절대 금기): 반환 텍스트는 *검증 전 원시 모델 출력*이다. 03 문서
환각 방어 파이프라인을 통과하기 전에는 학생에게 직접 노출 금지 ("LLM 응답을 검증
없이 학생에게 제공 금지"). 비동기 경로는 텍스트를 *즉시 돌려주지 않고* job_id만 주며,
폴링으로 받은 결과 역시 동일하게 검증 전 출력이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from whymath_backend.config import get_settings
from whymath_backend.l3.interfaces import (
    AsyncJobQueue,
    CacheBackend,
    LLMProvider,
    TraceSink,
)
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.router import Router, cache_key_for, langfuse_fields


class QualityQueueUnavailableError(RuntimeError):
    """QUALITY(27b) 비동기 큐를 쓸 수 없음 — 미구성 또는 broker 도달 실패 (03a §D.3).

    QUALITY는 p50≈14초·병렬 미작동이라 동기 호출이 *절대* 금지된다(GPU 단일 점유).
    라우터가 mode='async'로 결정한 요청에 대해 (a) 큐가 주입되지 않았거나(미구성)
    (b) enqueue가 broker 도달 실패로 던지면, 동기 폴백 대신 이 예외를 던진다 —
    호출자(엔드포인트)는 이를 명확한 503으로 변환하며 500 스택트레이스를 노출하지
    않는다(가용성 우선: 503 '잠시 후 재시도'가 500 '내부 오류'보다 정직·안전).
    """


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """파이프라인 결과 — 라우팅 메타데이터 + (동기) 생성 텍스트 또는 (비동기) job_id.

    호출자/엔드포인트가 라우팅 결정(어느 티어·패밀리·모드)과 캐시 적중 여부를
    응답에 노출할 수 있도록 decision을 함께 돌려준다.

    두 모드를 하나의 타입으로 표현한다(분기 단순화):
      - 동기(sync) 완료: status="completed", text=생성물, cache_hit=불린, job_id=None.
      - 비동기(async) 큐잉: status="queued", text="", cache_hit=False, job_id=큐 작업 ID.
        텍스트는 *즉시 없다* — 호출자는 job_id로 폴링한다(03a §D.3). 빈 text는 "아직
        없음"을 뜻하며, 학생 노출 대상이 아니다.

    `text`(있을 때)는 *검증 전 원시 출력*이다(모듈 docstring 경계 메모 참조).
    """

    decision: RoutingDecision
    text: str
    cache_hit: bool
    # 비동기(QUALITY) 큐잉 시에만 채워지는 작업 ID. 동기 경로는 None.
    job_id: str | None = None
    # "completed"(동기 완료) / "queued"(비동기 큐 적재). 엔드포인트가 202 vs 200 분기에 사용.
    status: str = "completed"

    @property
    def is_queued(self) -> bool:
        """비동기 큐에 적재돼 job_id 폴링이 필요한 결과인가."""
        return self.status == "queued"


def _build_async_payload(prompt: str, system: str, decision: RoutingDecision) -> dict[str, object]:
    """비동기 큐 payload(JSON-safe dict) 구성 — 워커 태스크 스키마와 일치.

    RoutingDecision은 use_enum_values=True라 model_dump()가 enum을 문자열로 내놓아
    JSON 직렬화·Celery 전송에 안전하다(pickle 미사용). 워커는 이 dict에서
    RoutingDecision을 다시 검증·재구성한다(queue/tasks.py PAYLOAD_* 키와 동일).
    """
    return {
        "prompt": prompt,
        "system": system,
        "decision": decision.model_dump(),
    }


async def generate(
    req: RoutingRequest,
    prompt: str,
    system: str,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    queue: AsyncJobQueue | None = None,
    cache_ttl_s: int | None = None,
    student_id_hash: str | None = None,
) -> GenerationResult:
    """라우팅 → (비동기면 큐잉 / 동기면 캐시·생성) → 관측을 조립한다.

    Args:
        req: 라우팅 입력 신호.
        prompt: 사용자 프롬프트(검증 전 원시 입력).
        system: 시스템 프롬프트.
        provider: LLM 생성 백엔드(LOCAL이면 OllamaProvider).
        cache: 응답 캐시(S1은 인메모리 스텁).
        trace: 관측성 싱크(S1은 RecordingTraceSink).
        queue: QUALITY(27b) 비동기 작업 큐(S4 CeleryJobQueue). None이면 비동기 결정 시
            QualityQueueUnavailableError(미구성 폴백 → API 503).
        cache_ttl_s: 캐시 TTL(초). None이면 Settings.cache_ttl_s.
        student_id_hash: Langfuse 기록용 학생 ID 해시(직접 ID 금지, 03a §F.2).

    Returns:
        GenerationResult — 동기면 텍스트(status="completed"), 비동기면 job_id(status="queued").

    Raises:
        QualityQueueUnavailableError: 큐 미주입(미구성)이거나 enqueue 실패(broker 다운).
    """
    decision = Router().route(req)

    # QUALITY(27b)는 동기 호출 불가(p50≈14초·GPU 단일 점유, 03a §D.3) → 비동기 큐 경로.
    if decision.mode == "async":
        if queue is None:
            # 큐 미구성 → 안전 폴백(동기 호출은 절대 금지). API가 503으로 변환.
            raise QualityQueueUnavailableError(
                "QUALITY(27b) 동기 호출 불가 — 비동기 큐가 구성되지 않았습니다(03a §D.3). "
                f"결정: cost_tier={decision.cost_tier}, local_model={decision.local_model}."
            )
        payload = _build_async_payload(prompt, system, decision)
        try:
            job_id = await queue.enqueue(payload)
        except Exception as exc:  # noqa: BLE001 — broker 다운 등 디스패치 실패를 도메인 예외로
            # broker 도달 실패는 가용성 문제 → 명확한 도메인 예외로 변환(API 503, 500 금지).
            raise QualityQueueUnavailableError(
                "QUALITY(27b) 작업 큐 디스패치 실패 — broker 도달 불가일 수 있습니다(03a §D.3). "
                f"원인: {type(exc).__name__}: {exc}"
            ) from exc
        # enqueue도 관측 기록한다(mode=async — SLA 평가에서 동기와 분리, 03a §F.2).
        # provider는 호출하지 않는다(QUALITY 동기 금지). 캐시도 타지 않는다(결과 미존재).
        trace.record(langfuse_fields(decision, cache_hit=False, student_id_hash=student_id_hash))
        return GenerationResult(
            decision=decision, text="", cache_hit=False, job_id=job_id, status="queued"
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
