"""콘텐츠 공급 경로 — 개념 주소화 DSL 캐시 + render-vs-generate 결정 + 경로 측정.

설계 정본: `docs/architecture/03c_content_strategy_cache.md` §3-4.

REND-01(렌더 어댑터)과 PED-02(교수법 선택·게이트)를 잇는 마지막 조각이다. 대부분의 요청은 이미
가진 교수법-중립 자산을 *선택해서 렌더*하고(0원·결정론), 진짜 새로운 조합만 LLM 생성으로 간다.

────────────────────────────────────────────────────────────────────────────
왜 L3가 아니라 L4인가 (03c §3 의사코드 교정)
────────────────────────────────────────────────────────────────────────────
03c 초판은 `supply()`를 L3에 뒀지만 두 가지 이유로 L4가 맞다:

  1. **계층 계약** — supply는 L4 선택기(`runtime_selector`)를 호출해야 하는데 `l3 → l4`는 역방향이라
     `lint-imports`가 깨진다. L4는 `l3`(`misconception/judge_seam.py` 선례)·`db`(`evidence_store.py`
     선례)를 모두 하향 임포트할 수 있다.
  2. **게이트 우회 불가(더 중요)** — supply가 `decide()`를 *내부에서* 호출하므로, 이 경로를 쓰는 한
     교수학 게이트를 건너뛸 방법이 없다. 전략을 인자로 받는 설계였다면 호출자가 게이트를 빠뜨린 채
     완전예제를 렌더할 수 있다 — PED-02가 세운 냉담 제공 차단이 무력해진다. 교수학 정확성(#3)이
     비용(#6)보다 위라는 원칙은 이런 배치로 지켜진다.

────────────────────────────────────────────────────────────────────────────
이중 회계 — content_source는 *반환값으로도* 나온다
────────────────────────────────────────────────────────────────────────────
경로 판정치(`content_source`)를 Langfuse에만 실으면 관측 인프라가 죽었을 때 "0건 통과"로 위장된다.
`ops/cost_probe`가 존재하는 이유가 정확히 그것이다(placeholder 키 때문에 `cost_report`가 조용히
0건을 보고한 사고). 그래서 `supply()`는 `SupplyResult.content_source`를 **반환**하고, 집계는
`SupplyTally`가 in-process로 낸다. Langfuse 기록은 그 위의 *보조* 축이다.

────────────────────────────────────────────────────────────────────────────
2층 캐시에서 이 모듈의 자리
────────────────────────────────────────────────────────────────────────────
  (1) 개념 주소화 중립 DSL  ← 이 모듈(`dsl:concept:{code}`). 키 축 = 개념.
  (2) 프롬프트-해시 Redis   ← 기존 `l3/pipeline`(`llm:cache:{sha}`). 키 축 = 프롬프트.
  (3) generate             ← 기존 라우터 경유.
(1)은 렌더 시점 조립을 전제하므로 캐시여도 몰개인화되지 않는다 — 개인화는 어댑터·바인딩이 맡는다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.harness.wilson import wilson_lower_bound
from whymath_backend.l1.concept_content import get_concept_content
from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.render.adapter import RenderContext, RenderedUnit
from whymath_backend.l3.render.dsl import ConceptDSL, from_concept_content
from whymath_backend.l3.render.registry import get_adapter
from whymath_backend.l4.pedagogy.prompt_assembler import attach_strategy_card
from whymath_backend.l4.pedagogy.runtime_selector import StudentSignals, decide
from whymath_backend.l4.pedagogy.strategy_registry import get_strategy
from whymath_backend.schema.enums import PedagogyStrategy
from whymath_backend.schema.pedagogy_strategy import PedagogyStrategyCard

logger = logging.getLogger("whymath.l4.content_supply")

# 개념 주소화 캐시 네임스페이스 — 프롬프트-해시(`llm:cache:`)와 **키 축이 다르므로** 분리한다.
DSL_CACHE_PREFIX = "dsl:concept:"

# DSL 캐시 TTL(초) — 콘텐츠는 영구 자산이라 길게 잡되, 코퍼스 재적재가 반영되도록 무한은 아니다.
DSL_CACHE_TTL_S = 24 * 60 * 60

# 공급 경로 — 이 값이 곧 비용 축이다(dsl_render=0원).
ContentSource = Literal["dsl_render", "prompt_cache", "generate"]

# 폴백 사유 — 왜 렌더가 아니라 생성으로 갔는지(조용한 폴백 금지·집계 가능).
REASON_NO_DSL = "NO_DSL"
"""개념 콘텐츠가 아직 없다(캐시·DB 모두 미스)."""

REASON_CANNOT_RENDER = "CANNOT_RENDER"
"""DSL은 있으나 이 전략이 렌더할 재료가 부족하다(`can_render` False)."""

REASON_NO_ADAPTER = "NO_ADAPTER"
"""전략에 등록된 렌더 어댑터가 없다(REND-01 미구현 5종)."""

REASON_RENDER_UNVERIFIED = "RENDER_UNVERIFIED"
"""렌더는 됐으나 검증 신호가 떠서 학생에게 노출할 수 없다."""


@dataclass(frozen=True, slots=True)
class SupplyResult:
    """공급 결과 — 무엇을 어느 경로로 서빙했는가.

    `content_source`가 이중 회계의 in-process 축이다(반환값이므로 관측 인프라와 무관하게 집계된다).
    `fallback_reason`은 렌더가 아닌 경로로 간 이유이며, None이면 렌더 성공이거나 애초에 렌더를
    시도할 상황이 아니었음을 뜻한다.
    """

    content_source: ContentSource
    strategy: PedagogyStrategy
    rendered: RenderedUnit | None = None
    text: str | None = None
    gate_reason_code: str | None = None
    fallback_reason: str | None = None

    @property
    def is_free(self) -> bool:
        """LLM 비용이 0인 경로인가(렌더·프롬프트캐시 히트)."""
        return self.content_source in ("dsl_render", "prompt_cache")


@dataclass(slots=True)
class SupplyTally:
    """공급 경로 in-process 집계 — 판정치는 여기서 낸다(SaaS 비의존).

    `dsl_render_rate`는 점추정과 **Wilson 하한**을 함께 노출한다. 표본이 작을 때 점추정만 보면
    과신하게 되므로, 게이트 판정은 하한으로 한다(`ops/cost_probe`의 로컬 비율 관례 동형).
    """

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, source: ContentSource) -> None:
        self.counts[source] = self.counts.get(source, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def dsl_render_rate(self) -> float | None:
        """렌더 경로 비율(점추정). 표본 0이면 None — "미상"을 0%로 위장하지 않는다."""
        if self.total == 0:
            return None
        return self.counts.get("dsl_render", 0) / self.total

    @property
    def dsl_render_rate_lower(self) -> float | None:
        """렌더 경로 비율의 Wilson 단측 95% 하한. 표본 0이면 None."""
        if self.total == 0:
            return None
        return wilson_lower_bound(self.counts.get("dsl_render", 0), self.total)

    def to_json(self) -> dict[str, object]:
        """사람·자동화가 읽는 요약(미상은 None으로 남긴다)."""
        return {
            "total": self.total,
            "counts": dict(self.counts),
            "dsl_render_rate": self.dsl_render_rate,
            "dsl_render_rate_lower": self.dsl_render_rate_lower,
        }


async def get_concept_dsl(
    code: str,
    *,
    session: AsyncSession,
    cache: CacheBackend,
    ttl_s: int = DSL_CACHE_TTL_S,
) -> ConceptDSL | None:
    """개념 주소화 DSL 조회 — 캐시 → DB read-through. 미적재 개념이면 None.

    캐시(`CacheBackend`)는 **str 전용**이라 pydantic `model_dump_json()`으로 직렬화한다. 역직렬화가
    실패하면(계약 변경·손상) **미스로 취급**해 DB에서 다시 만든다 — 낡은 형태를 억지로 쓰는 조용한
    오작동보다 재적재가 낫다.
    """
    key = f"{DSL_CACHE_PREFIX}{code}"
    cached = await cache.get(key)
    if cached is not None:
        try:
            return ConceptDSL.model_validate_json(cached)
        except ValidationError:
            pass  # 계약 변경 등 — 미스 취급 후 아래에서 재생성.

    row = await get_concept_content(session, code)
    if row is None:
        return None

    dsl = from_concept_content(row)
    await cache.set(key, dsl.model_dump_json(), ttl_s)
    return dsl


def _render_or_reason(
    dsl: ConceptDSL, strategy: PedagogyStrategy, ctx: RenderContext
) -> tuple[RenderedUnit | None, str | None]:
    """렌더 시도 — 성공하면 (unit, None), 불가·미검증이면 (None, 사유).

    어댑터 미등록(`LookupError`)은 REND-01 레지스트리의 명시적 계약이다(조용한 대체 금지). 여기서
    잡아 폴백 사유로 바꾼다 — 상위는 생성 경로로 가면 되지 예외로 죽을 이유가 없다.
    """
    try:
        adapter = get_adapter(strategy)
    except LookupError:
        return None, REASON_NO_ADAPTER

    if not adapter.can_render(dsl):
        return None, REASON_CANNOT_RENDER

    unit = adapter.render(dsl, ctx)
    if unit.validation_signal is not None:
        return None, REASON_RENDER_UNVERIFIED  # 미검증 노출 금지.
    return unit, None


async def supply(
    *,
    code: str,
    signals: StudentSignals,
    session: AsyncSession,
    cache: CacheBackend,
    k_type: str | None = None,
    ctx: RenderContext | None = None,
    generate_request: RoutingRequest | None = None,
    prompt: str = "",
    system: str = "",
    provider: LLMProvider | None = None,
    trace: TraceSink | None = None,
    tally: SupplyTally | None = None,
) -> SupplyResult:
    """콘텐츠 공급 — 교수법 선택·게이트 → 렌더(0원) → 실패 시 생성 폴백.

    흐름:
      ① `decide()` — 전략 선택 + 교수학 게이트(내부 호출이라 우회 불가).
      ② 개념 주소화 DSL 조회(캐시 → DB).
      ③ 렌더 가능·검증 통과면 반환(`dsl_render`·LLM 0원).
      ④ 아니면 `l3.pipeline.generate` 폴백(`prompt_cache` 또는 `generate`).

    생성 폴백에 필요한 인자(`generate_request`·`provider`·`trace`)가 없으면 폴백을 시도하지 않고
    렌더 실패 사유를 담은 결과를 돌려준다 — 호출자가 폴백 없이 쓰는 경우(사전 점검·배치)를 위해서다.
    """
    gate_result = decide(signals, k_type=k_type)
    strategy = gate_result.strategy
    render_ctx = ctx if ctx is not None else RenderContext()

    dsl = await get_concept_dsl(code, session=session, cache=cache)
    if dsl is None:
        reason: str | None = REASON_NO_DSL
        unit: RenderedUnit | None = None
    else:
        unit, reason = _render_or_reason(dsl, strategy, render_ctx)

    if unit is not None:
        result = SupplyResult(
            content_source="dsl_render",
            strategy=strategy,
            rendered=unit,
            gate_reason_code=gate_result.reason_code,
        )
        if trace is not None:
            trace.record(_render_trace_fields(code, strategy))
        if tally is not None:
            tally.record(result.content_source)
        return result

    # ── 생성 폴백 ────────────────────────────────────────────────
    if generate_request is None or provider is None or trace is None:
        result = SupplyResult(
            content_source="generate",
            strategy=strategy,
            gate_reason_code=gate_result.reason_code,
            fallback_reason=reason,
        )
        if tally is not None:
            tally.record(result.content_source)
        return result

    # 전략 카드 계층(PED-06 — 04e §3.2): decide()가 고른(게이트 통과 후) 전략의 카탈로그 카드를
    # system 뒤에 1블록 덧붙인다. 이 지점이 decide 산출 전략이 LLM 프롬프트와 만나는 **유일한
    # 실측 소비 지점**이다(렌더 경로는 프롬프트가 없다). 플래그 OFF(기본)면 카탈로그 미조회·
    # system 무변경 — 프롬프트-해시 캐시 키(`cache_key_for(prompt, system, ...)`)도 불변이라
    # 기존 생성 경로와 비트동일(옵트인 무변경 계약).
    system_for_generate = system
    if get_settings().pedagogy_strategy_card_enabled:
        card: PedagogyStrategyCard | None
        try:
            card = get_strategy(strategy)
        except Exception as exc:
            # best-effort 계층 — 카드 조회 실패(카탈로그 누락 LookupError·코퍼스 손상 등)가
            # 생성 자체를 막으면 안 된다. 단 침묵 실패 금지 — 예외 타입명을 로그에 남긴다.
            logger.warning(
                "교수전략 카드 조회 실패 — 카드 없이 생성 진행 (strategy=%s, error=%s)",
                strategy.value,
                type(exc).__name__,
            )
            card = None
        system_for_generate = attach_strategy_card(system, card)

    generated = await pipeline.generate(
        generate_request,
        prompt,
        system_for_generate,
        provider=provider,
        cache=cache,
        trace=trace,
    )
    # 프롬프트-해시 캐시 히트도 0원이므로 경로를 구분해 집계한다(2층 캐시의 (2)).
    source: ContentSource = "prompt_cache" if generated.cache_hit else "generate"
    result = SupplyResult(
        content_source=source,
        strategy=strategy,
        text=generated.text,
        gate_reason_code=gate_result.reason_code,
        fallback_reason=reason,
    )
    if tally is not None:
        tally.record(source)
    return result


def _render_trace_fields(code: str, strategy: PedagogyStrategy) -> dict[str, object]:
    """렌더 경로 관측 이벤트 — 라우팅 결정이 없는 경로라 `langfuse_fields`를 쓰지 않는다.

    렌더는 LLM을 타지 않으므로 `RoutingDecision`이 존재하지 않는다. 그래서 `cost_tier` 등 라우팅
    필드 없이 경로·비용만 싣는다(집계기는 `.get()`으로 읽으므로 키 부재에 안전하다).
    """
    return {
        "content_source": "dsl_render",
        "cost_krw": 0.0,  # 결정론 렌더 — LLM 호출 0.
        "dsl_code": code,
        "pedagogy_strategy": strategy.value,
    }


__all__ = [
    "DSL_CACHE_PREFIX",
    "DSL_CACHE_TTL_S",
    "REASON_CANNOT_RENDER",
    "REASON_NO_ADAPTER",
    "REASON_NO_DSL",
    "REASON_RENDER_UNVERIFIED",
    "ContentSource",
    "SupplyResult",
    "SupplyTally",
    "get_concept_dsl",
    "supply",
]
