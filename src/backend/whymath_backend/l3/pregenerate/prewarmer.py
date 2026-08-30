"""캐시 사전적재기 — 런타임 라우터와 *같은* 키로 검증된 시드를 캐시에 채워 넣는다.

런타임(`l3/pipeline.py:125·152`)이 컴퓨트하는 `Router().route(req)` + `cache_key_for(
prompt, system, decision)`을 그대로 재사용 → 사전적재한 키는 런타임이 *반드시* 같은
키로 조회하게 된다(키 정합 보장).

설계 정본: MEMORY.md 2026-05-20 "Max=빌드타임 콘텐츠 생성 → 결과는 캐시/DB 저장 →
학생 런타임은 캐시 히트(0원)". 03a §F.1 캐시 키.

경계 메모: 본 슬라이스는 *시드 품질 위생*까지만 강제한다(BasicSeedValidator). 학생
직접 노출 경계는 L4/L5 환각 방어가 책임진다(CLAUDE.md "LLM 응답을 검증 없이 학생에게
제공 금지" — 사전적재된 응답도 런타임에서 환각 방어를 통과해야 학생에게 닿는다).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider
from whymath_backend.l3.models import RoutingDecision, Usage
from whymath_backend.l3.pregenerate.models import (
    PregenItem,
    PrewarmItemResult,
    PrewarmReport,
)
from whymath_backend.l3.pregenerate.provenance_bridge import (
    actual_cost_usd_or_none,
    generation_log_from_result,
    input_snapshot_for_prewarm,
    model_name_for_decision,
)
from whymath_backend.l3.pregenerate.validator import SeedValidator
from whymath_backend.l3.router import Router, cache_key_for
from whymath_backend.schema.provenance import GenerationLog

logger = logging.getLogger("whymath.l3.pregenerate.prewarmer")

# 생성 로그 싱크 계약 — GenerationLog 1건을 받아 적재한다(JSONL appender·DB 세션 등).
# 예외는 prewarmer가 흡수한다(관측 적재 실패가 사전적재 배치를 깨면 안 됨 — 타입명 로그).
GenerationLogSink = Callable[[GenerationLog], None]


class CachePrewarmer:
    """배치 단위 캐시 사전적재기 — provider·cache·validator 주입.

    `prewarm(items)`은 항목당 (a) 라우팅 → (b) 키 계산 → (c) overwrite=False면 존재 시
    스킵 → (d) 응답 획득(인제스트 우선, 없으면 provider) → (e) 검증 → (f) 통과 시
    `cache.set(key, response, ttl_seconds)`. 각 단계 오류는 *흡수*해 항목 결과로 기록하고
    배치 전체는 계속 진행한다(단일 항목 실패가 배치를 깨면 안 됨).

    `ttl_seconds` 기본 `0` = 무만료(S2 RedisCache는 ttl<=0이면 SET without EX) — 사전
    생성물은 만료되면 의미가 없으므로 기본 무만료. 명시적 회전 정책은 후속.

    `generation_log_sink`(EOS-55 집행 별항): 항목 1건 처리마다 `GenerationLog`(모델·
    prompt_version·seed 좌석·입력 스냅샷 해시+참조)를 조립해 싱크로 흘린다 — 스킵·실패
    항목도 기록한다(성공 경로만 보는 계측 금지·2026-08-22 규칙). None(기본)이면 종전
    동작 그대로(관측 0·기존 호출부 무영향).
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        cache: CacheBackend,
        validator: SeedValidator,
        router: Router | None = None,
        generation_log_sink: GenerationLogSink | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._validator = validator
        self._router = router if router is not None else Router()
        self._generation_log_sink = generation_log_sink

    async def prewarm(
        self,
        items: Iterable[PregenItem],
        *,
        ttl_seconds: int = 0,
        overwrite: bool = False,
    ) -> PrewarmReport:
        """항목 배치를 사전적재 — 결과 리포트 반환(예외 전파 없음)."""
        results: list[PrewarmItemResult] = []
        for item in items:
            results.append(
                await self._prewarm_one(item, ttl_seconds=ttl_seconds, overwrite=overwrite)
            )
        return PrewarmReport(items=tuple(results))

    async def _prewarm_one(
        self,
        item: PregenItem,
        *,
        ttl_seconds: int,
        overwrite: bool,
    ) -> PrewarmItemResult:
        """항목 1건: 라우팅 → 본처리 → 생성 로그 적재(EOS-55) — 결과는 그대로 반환."""
        decision = self._router.route(item.request)
        result = await self._prewarm_with_decision(
            item, decision, ttl_seconds=ttl_seconds, overwrite=overwrite
        )
        self._emit_generation_log(item, decision, result)
        return result

    def _emit_generation_log(
        self,
        item: PregenItem,
        decision: RoutingDecision,
        result: PrewarmItemResult,
    ) -> None:
        """항목 결과 → GenerationLog 조립·싱크 적재 (EOS-55 집행 별항 — never-break).

        기록 원칙(날조 금지):
          - `problem_id=None`·`cu_slug=None` — 사전적재 시드는 problem 레코드도 코퍼스 CU
            정체성도 없다(캐시 키 단위 자산·#912 P1-2 "가진 정체성만 기록"의 이 경로 값).
          - `prompt_version=None`/`seed=None` — 이 경로는 템플릿 체계·seed 스레딩이 없다
            (2026-08-30 실측). 좌석만 두고 실사용 시점에 실제 값을 기록한다.
          - `cost_usd`: 로컬 0원 확정 / 클라우드 토큰 미상 None(`actual_cost_usd_or_none`).
          - 스냅샷: `input_snapshot_for_prewarm` — 프롬프트/시스템 **전문**+sha256 핀 +
            request 원문(#912 P1-1 자기완결).
        싱크 예외는 흡수하되 **타입명을 로그에 남긴다**(침묵 실패 금지 — 관측 적재 실패가
        배치를 깨면 안 됨·`llm_generator._record_trace` 동형).
        """
        if self._generation_log_sink is None:
            return
        try:
            log = generation_log_from_result(
                result,
                problem_id=None,
                model_name=model_name_for_decision(decision),
                cost_usd=actual_cost_usd_or_none(decision, result.usage),
                input_snapshot=input_snapshot_for_prewarm(item),
            )
            self._generation_log_sink(log)
        except Exception as exc:  # noqa: BLE001 — 관측 적재 장애는 배치 비차단(타입명 로그)
            logger.warning("사전적재 생성 로그 적재 실패(%s) — 무시하고 계속", type(exc).__name__)

    async def _prewarm_with_decision(
        self,
        item: PregenItem,
        decision: RoutingDecision,
        *,
        ttl_seconds: int,
        overwrite: bool,
    ) -> PrewarmItemResult:
        """라우팅 결정이 주어진 항목 1건의 본처리 — 종전 `_prewarm_one` 본문 그대로."""

        # QUALITY(async)는 런타임 파이프라인이 async 분기에서 캐시를 *치지 않는다*
        # (pipeline.py:128-149 — async는 enqueue만 하고 cache.get/set 없음). 따라서
        # 사전적재해도 런타임이 영원히 못 읽는다 → 의미 없으므로 명시적 error로 표시.
        if decision.mode == "async":
            return PrewarmItemResult(
                cache_key="",
                status="error",
                error=(
                    "QUALITY async decisions don't hit runtime cache "
                    "(pipeline.generate async branch skips cache, 03a §D.3)"
                ),
            )

        key = cache_key_for(item.prompt, item.system, decision)

        # 중복 적재 회피 — overwrite=False면 존재 시 스킵(불필요한 재생성/덮어쓰기 방지).
        if not overwrite:
            try:
                existing = await self._cache.get(key)
            except Exception as exc:  # noqa: BLE001 — 캐시 조회 오류도 비크래시로 흡수
                return PrewarmItemResult(
                    cache_key=key,
                    status="error",
                    error=f"cache.get failed: {type(exc).__name__}: {exc}",
                )
            if existing is not None:
                return PrewarmItemResult(cache_key=key, status="skipped_exists")

        # 응답 획득 — 인제스트 모드(precomputed) 우선, 없으면 provider 호출.
        # usage(실측 토큰·지연)는 provider 생성 경로에서만 존재한다(인제스트는 None).
        usage: Usage | None = None
        if item.precomputed_response is not None:
            response = item.precomputed_response
        else:
            try:
                generated = await self._provider.generate(item.prompt, item.system, decision)
            except Exception as exc:  # noqa: BLE001 — provider 오류는 항목 단위로 흡수
                return PrewarmItemResult(
                    cache_key=key,
                    status="error",
                    error=f"provider.generate failed: {type(exc).__name__}: {exc}",
                )
            response = generated.text
            usage = generated.usage

        # 검증 게이트 — 통과한 시드만 캐시에 적재(품질 위생).
        failure_reason = self._validator.validate(item, response)
        if failure_reason is not None:
            return PrewarmItemResult(
                cache_key=key,
                status="failed_validation",
                # 신호의 사유 문자열만 담는다(error: str | None 계약 유지·slice 59).
                error=failure_reason.reason,
                usage=usage,
            )

        try:
            await self._cache.set(key, response, ttl_seconds)
        except Exception as exc:  # noqa: BLE001 — 캐시 적재 오류도 항목 단위로 흡수
            return PrewarmItemResult(
                cache_key=key,
                status="error",
                error=f"cache.set failed: {type(exc).__name__}: {exc}",
                usage=usage,
            )

        return PrewarmItemResult(cache_key=key, status="written", usage=usage)
