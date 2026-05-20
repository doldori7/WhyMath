"""L3 라우터 결정 로직 — 축1(C.1) → 축2(C.2) 순차 결정.

설계 정본: `docs/architecture/03a_l3_router_design.md`
  - §C.1 축1 결정표(6규칙) / §C.2 축2 결정표(7규칙) + §C.4 의사코드
  - §D 에스컬레이션·폴백 체인 / §D.4 guard_cloud
  - §E 비용·예산·구독별 일일 한도 / §F 캐싱 키·Langfuse 필드
  - §A.1 벤치 지연(FAST≈1010ms·MID≈3918ms·QUALITY≈13886ms)

범위 메모 (M1.2): 본 모듈은 *결정 로직*과 *추정·키 생성*만 구현한다(순수 Python).
실제 LLM 호출·Redis·Langfuse·비동기 큐는 `interfaces.py`의 Protocol/스텁으로만
경계를 둔다. `langfuse_fields()`는 *태그 dict만* 만들고 실제 전송은 하지 않는다.
"""

from __future__ import annotations

import hashlib
from typing import Final

from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    RoutingDecision,
    RoutingRequest,
)

# ──────────────────────────────────────────────────────────────────────────
# 그라운딩 상수 — 03a §A.1 벤치(2026-05-19, Phaiakes9 / Radeon 8060S / Ollama 0.24.0)
# 로컬 티어별 p50 지연(ms). 토큰당 비용은 0원(Phaiakes9 로컬).
# ──────────────────────────────────────────────────────────────────────────
LOCAL_LATENCY_MS: Final[dict[LocalModelTier, int]] = {
    LocalModelTier.FAST: 1010,  # qwen2-math:1.5b — p50 1,010ms, SLA PASS
    LocalModelTier.MID: 3918,  # qwen2-math:7b — p50 3,918ms
    LocalModelTier.QUALITY: 13886,  # qwen3.5:27b — p50 13,886ms, 비동기 전용
}
"""로컬 티어별 예상 지연(ms). 출처: 03a §A.1 벤치 p50."""

SLA_GATE_MS: Final[int] = 2000
"""동기 즉답 SLA 게이트(ms). FAST(p50 1,010ms)만 통과 (03a §A.1·C.2 규칙3)."""

# ──────────────────────────────────────────────────────────────────────────
# 구독별 일일 한도(원) — 03a §E.2 표 (확정값). 한도는 *클라우드 호출에만* 차감.
# 로컬은 0원이므로 한도를 소모하지 않는다(budget_krw = 클라우드 잔여 예산).
# ──────────────────────────────────────────────────────────────────────────
DAILY_LIMIT_KRW: Final[dict[str, int]] = {
    "free": 100,  # 사실상 LOCAL 전용. 한도는 클라우드 우발 호출 차단선
    "basic": 500,  # CLOUD_MID 소량, CLOUD_HIGH 불가(guard)
    "premium": 2000,  # CLOUD_MID 일상 + CLOUD_HIGH 제한적
    "gifted": 5000,  # CLOUD_HIGH 포함 폭넓게
}
"""구독별 일일 한도(원). 출처: 03a §E.2."""

# ──────────────────────────────────────────────────────────────────────────
# 클라우드 추정 상수 — 03a는 *경로·가드 설계*만 명세하고 구체 수치는 미제공
# (§H 후속 4 "클라우드 티어 실제 연동·비용 계측·guard_cloud 실측 임계값 보정").
# 아래 값은 *fabricate가 아니라* 실측 전까지의 명시적 placeholder다. 라이브 연동 시
# 실측으로 대체한다. guard_cloud의 "잔여 예산 부족" 판정에 쓰이는 1회 최소 비용.
# ──────────────────────────────────────────────────────────────────────────
CLOUD_MIN_COST_KRW: Final[dict[CostTier, float]] = {
    # 1회 호출 최소 추정 비용(원) — 잔여 예산이 이보다 작으면 LOCAL 강등(§D.4)
    CostTier.CLOUD_MID: 10.0,  # placeholder — §H 후속 4에서 실측 보정
    CostTier.CLOUD_HIGH: 50.0,  # placeholder — §H 후속 4에서 실측 보정
}
"""클라우드 티어 1회 호출 최소 추정 비용(원). placeholder — 03a §H 후속 4 보정 대상."""

CLOUD_LATENCY_MS: Final[dict[CostTier, int]] = {
    # 03a §A.1 표에서 CLOUD는 "가변" — 네트워크·모델 의존. placeholder 예상치.
    CostTier.CLOUD_MID: 3000,  # placeholder — §H 후속 4에서 실측 보정
    CostTier.CLOUD_HIGH: 8000,  # placeholder — §H 후속 4에서 실측 보정
}
"""클라우드 티어 예상 지연(ms). 03a §A.1 "가변" — placeholder, §H 후속 4 보정 대상."""

CACHE_KEY_PREFIX: Final[str] = "llm:cache:"
"""캐시 키 네임스페이스 (llm-architect.md ResponseCache 컨벤션)."""


def _as_cost_tier(value: object) -> CostTier:
    """문자열/enum 어느 쪽이 와도 CostTier로 정규화.

    RoutingDecision은 `use_enum_values=True`라 필드가 문자열일 수 있다(03a §G 스키마).
    """
    if isinstance(value, CostTier):
        return value
    return CostTier(value)


def _as_local_tier(value: object) -> LocalModelTier | None:
    """문자열/enum/None 어느 쪽이 와도 LocalModelTier|None으로 정규화."""
    if value is None:
        return None
    if isinstance(value, LocalModelTier):
        return value
    return LocalModelTier(value)


def _as_call_site(value: object) -> CallSite | None:
    """문자열/enum/None 어느 쪽이 와도 CallSite|None으로 정규화."""
    if value is None:
        return None
    if isinstance(value, CallSite):
        return value
    return CallSite(value)


# ──────────────────────────────────────────────────────────────────────────
# 추정기 (estimators)
# ──────────────────────────────────────────────────────────────────────────
def local_latency(local: LocalModelTier) -> int:
    """로컬 티어 예상 지연(ms) — 03a §A.1 벤치 p50."""
    return LOCAL_LATENCY_MS[local]


def cloud_latency(cost: CostTier) -> int:
    """클라우드 티어 예상 지연(ms) — placeholder(03a §A.1 "가변", §H 후속 4)."""
    return CLOUD_LATENCY_MS[cost]


def cloud_min_cost(desired: CostTier) -> float:
    """클라우드 1회 최소 추정 비용(원) — guard_cloud 예산 판정용(§D.4)."""
    return CLOUD_MIN_COST_KRW[desired]


def cloud_cost(req: RoutingRequest, cost: CostTier) -> float:
    """클라우드 호출 예상 비용(원) — placeholder 추정(03a §E·§H 후속 4).

    03a는 구체 비용 모델을 명세하지 않는다. 실측 연동 전까지 1회 최소 비용을
    예상치로 사용한다(보수적). 라이브 연동 시 토큰 기반 실측으로 대체.
    """
    return CLOUD_MIN_COST_KRW[cost]


# ──────────────────────────────────────────────────────────────────────────
# 구독·예산 가드 (03a §D.4 guard_cloud)
# ──────────────────────────────────────────────────────────────────────────
def guard_cloud(req: RoutingRequest, desired: CostTier) -> CostTier:
    """클라우드 승급 전 구독·예산 가드. 미통과 시 LOCAL/하위 티어로 강등 (03a §D.4).

    규칙(03a §D.4 의사코드 그대로):
      1. free 구독 → 클라우드 금지(LOCAL 강등).
      2. 잔여 예산(budget_krw)이 1회 최소 비용 미만 → LOCAL 강등(+신뢰도 경고).
      3. CLOUD_HIGH 희망인데 basic 구독 → CLOUD_MID로 제한(HIGH 불가).
      그 외 → 희망 티어 그대로.
    """
    if req.student_subscription == "free":
        return CostTier.LOCAL  # 무료는 클라우드 금지
    if req.budget_krw < cloud_min_cost(desired):
        return CostTier.LOCAL  # 잔여 예산 부족 → 강등(+신뢰도 경고)
    if desired == CostTier.CLOUD_HIGH and req.student_subscription == "basic":
        return CostTier.CLOUD_MID  # basic은 HIGH 불가 → MID로 제한
    return desired


# ──────────────────────────────────────────────────────────────────────────
# 캐시 키 (03a §F.1 — 두 축 {cost_tier}:{local_model} 포함)
# ──────────────────────────────────────────────────────────────────────────
def cache_key(
    prompt: str,
    system: str,
    cost_tier: CostTier,
    local_model: LocalModelTier | None,
) -> str:
    """프롬프트+시스템+(두 축 합성 식별자) 기반 캐시 키 (03a §F.1).

    같은 프롬프트라도 *어느 티어가 생성했는지*가 캐시 정체성의 일부다
    (FAST 응답과 QUALITY 응답을 섞지 않는다). 학생 ID는 키에 포함하지 않는다
    (llm-architect.md ResponseCache 규칙 — 개인화는 컨텍스트로).
    """
    cost = _as_cost_tier(cost_tier)
    local = _as_local_tier(local_model)
    model_id = f"{cost.value}:{local.value if local is not None else '-'}"
    content = f"{system}|||{prompt}|||{model_id}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


def cache_key_for(prompt: str, system: str, decision: RoutingDecision) -> str:
    """RoutingDecision으로부터 캐시 키 생성 — cache_key()의 편의 래퍼."""
    return cache_key(prompt, system, decision.cost_tier, decision.local_model)


# ──────────────────────────────────────────────────────────────────────────
# Langfuse 태그 (03a §F.2 — dict만 생성, 실제 전송 X)
# ──────────────────────────────────────────────────────────────────────────
def langfuse_fields(
    decision: RoutingDecision,
    *,
    cache_hit: bool = False,
    escalated_from: CostTier | LocalModelTier | str | None = None,
    call_site: CallSite | str | None = None,
    student_id_hash: str | None = None,
) -> dict[str, object]:
    """Langfuse 기록 필드 dict 생성 (03a §F.2 표).

    범위 메모: *dict만* 반환한다. 실제 Langfuse 전송은 TraceSink 구현의 책임이며
    M1.2 범위 밖이다. `latency_ms`·`cost_krw`는 *실측* 필드라 여기서는 채우지 않고
    (라우터는 추정만 함), 추정치는 est_* 로 별도 노출한다.
    """
    cost = _as_cost_tier(decision.cost_tier)
    local = _as_local_tier(decision.local_model)
    site = _as_call_site(call_site)

    escalated: str | None
    if escalated_from is None:
        escalated = None
    elif isinstance(escalated_from, (CostTier, LocalModelTier)):
        escalated = escalated_from.value
    else:
        escalated = escalated_from

    return {
        "cost_tier": cost.value,  # 80/18/2 분포 모니터링
        "local_model": local.value if local is not None else None,  # 로컬 내부 분포
        "mode": decision.mode,  # SLA 평가 분리(동기만 게이트 대상)
        "est_latency_ms": decision.est_latency_ms,  # 추정 지연(실측은 latency_ms)
        "est_cost_krw": decision.est_cost_krw,  # 추정 비용(실측은 cost_krw)
        "call_site": site.value if site is not None else None,  # 호출지점별 분포
        "cache_hit": cache_hit,  # 캐싱 적중률 KPI
        "escalated_from": escalated,  # 에스컬레이션 빈도 분석
        "student_id_hash": student_id_hash,  # 직접 ID 금지(해시만)
        "reason": decision.reason,  # 결정 근거
    }


# ──────────────────────────────────────────────────────────────────────────
# 에스컬레이션 사슬 (03a §D.1 단방향 승급) — 로직 수준 헬퍼
# ──────────────────────────────────────────────────────────────────────────
ESCALATION_CHAIN: Final[list[tuple[CostTier, LocalModelTier | None]]] = [
    (CostTier.LOCAL, LocalModelTier.FAST),
    (CostTier.LOCAL, LocalModelTier.MID),
    (CostTier.LOCAL, LocalModelTier.QUALITY),
    (CostTier.CLOUD_MID, None),
    (CostTier.CLOUD_HIGH, None),
]
"""단방향 승급 사슬 (03a §D.1): FAST→MID→QUALITY→CLOUD_MID→CLOUD_HIGH.

로컬 3단계를 먼저 올리고(비용 0원), 로컬 천장(QUALITY)에서도 미달일 때만
CLOUD로 넘어간다. CLOUD 승급은 항상 guard_cloud를 통과해야 한다(§D.1).
"""


def next_tier(
    cost_tier: CostTier,
    local_model: LocalModelTier | None,
) -> tuple[CostTier, LocalModelTier | None] | None:
    """현재 (축1, 축2)에서 한 단계 승급한 (축1, 축2) 반환 (03a §D.1·§D.2).

    에스컬레이션 트리거(자기 일관성 불일치·신뢰도 미달 등, §D.2) 발동 시
    "다음 티어 1단계"를 결정하는 로직 수준 헬퍼. 천장(CLOUD_HIGH)이면 None.
    실제 트리거 감지(PRM confidence·다수결 등)는 생성 파이프라인의 책임이며
    M1.2 범위 밖이다 — 본 함수는 *사슬 계산*만 한다.
    """
    cost = _as_cost_tier(cost_tier)
    local = _as_local_tier(local_model)
    current = (cost, local)
    try:
        idx = ESCALATION_CHAIN.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(ESCALATION_CHAIN):
        return None  # 천장
    return ESCALATION_CHAIN[idx + 1]


# ──────────────────────────────────────────────────────────────────────────
# 라우터 본체
# ──────────────────────────────────────────────────────────────────────────
class Router:
    """비용·지연·품질 최적화 라우팅 (03a §C).

    축1(C.1, 80/18/2) → 축2(C.2, FAST/MID/QUALITY)를 *순차* 평가한다.
    `route()`는 *어디서 생성할지*만 정한다. 생성된 응답은 03 문서 환각 방어
    파이프라인을 *반드시* 통과해야 학생에게 노출된다(03a §C.4 메모,
    CLAUDE.md 절대 금기 "LLM 응답을 검증 없이 학생에게 제공 금지").
    """

    def route(self, req: RoutingRequest) -> RoutingDecision:
        """라우팅 결정 — 축1(C.1) → 축2(C.2) (03a §C.4 의사코드)."""
        cost_tier = self._decide_cost_tier(req)

        # CLOUD 경로면 축2(local_model) 없음 — 불변식 2(03a §G)
        if cost_tier != CostTier.LOCAL:
            return RoutingDecision(
                cost_tier=cost_tier,
                local_model=None,
                mode="sync",
                reason="cloud escalation",
                est_latency_ms=cloud_latency(cost_tier),
                est_cost_krw=cloud_cost(req, cost_tier),
            )

        # LOCAL 경로 → 축2 결정
        local_model, mode = self._decide_local_tier(req)
        return RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_model=local_model,
            mode=mode,
            reason=f"local/{local_model.value}",
            est_latency_ms=local_latency(local_model),
            est_cost_krw=0.0,  # 로컬은 0원
        )

    # ── 축1: 비용·위치 (03a §C.1 결정표 6규칙) ──
    def _decide_cost_tier(self, req: RoutingRequest) -> CostTier:
        """축1 결정 — LOCAL / CLOUD_MID / CLOUD_HIGH (03a §C.1).

        평가 순서 = 위에서 아래, 첫 매치 확정. 규칙 5(에스컬레이션 트리거)는
        *생성 결과 신뢰 미달* 시점에 발동하므로 단발 route() 입력만으로는
        평가하지 않는다(트리거 감지는 파이프라인 책임, §D.2). next_tier()로 분리.
        """
        # 규칙 1: 쿼터 소진 → 비용 0원 강제 (03a §E.2 budget_krw<=0 = "오늘은 로컬만")
        if req.budget_krw <= 0:
            return CostTier.LOCAL
        # 규칙 2: 무료 사용자 항상 로컬
        if req.student_subscription == "free":
            return CostTier.LOCAL
        # 규칙 3: 킬러·증명 → CLOUD_HIGH (단 구독·예산 가드 통과 시)
        if req.difficulty == "killer" or req.task_type == "prove":
            return guard_cloud(req, CostTier.CLOUD_HIGH)
        # 규칙 4: 어려운 진단(premium↑) → CLOUD_MID
        if req.requires_reasoning and req.student_subscription in ("premium", "gifted"):
            return guard_cloud(req, CostTier.CLOUD_MID)
        # 규칙 6: 그 외 기본 LOCAL (목표 분포 80%)
        return CostTier.LOCAL

    # ── 축2: 로컬 모델 크기 (03a §C.2 결정표 7규칙) ──
    def _decide_local_tier(self, req: RoutingRequest) -> tuple[LocalModelTier, str]:
        """축2 결정 — FAST / MID / QUALITY + 모드 (03a §C.2).

        축1=LOCAL로 확정된 요청만 평가. 평가 순서 = 위에서 아래, 첫 매치 확정.
        """
        call_site = _as_call_site(req.call_site)

        # 규칙 1: ⑤ 자기검증 → QUALITY 비동기 (검증은 강한 모델·비동기)
        if call_site == CallSite.SELF_VERIFY:
            return LocalModelTier.QUALITY, "async"
        # 규칙 2: 비동기 + (verify/generate or hard/killer) → QUALITY (27b 비동기 전용)
        if (not req.sync) and (
            req.task_type in ("verify", "generate") or req.difficulty in ("hard", "killer")
        ):
            return LocalModelTier.QUALITY, "async"
        # 규칙 3: 동기 + SLA<2s → FAST (FAST만 게이트 통과, p50 1초)
        if req.sync and req.max_latency_ms < SLA_GATE_MS:
            return LocalModelTier.FAST, "sync"
        # 규칙 4: 즉답·경량 호출지점 ①③④ → FAST
        if (
            req.conversation_phase in ("greeting", "followup")
            or req.task_type in ("extract", "match", "translate")
            or (req.difficulty == "easy" and not req.requires_reasoning)
        ):
            return LocalModelTier.FAST, "sync"
        # 규칙 5: 정밀 풀이·메인 대화(추론 필요) → MID (p50 4초 허용)
        if req.task_type in ("explain", "coach", "diagnose") and req.requires_reasoning:
            return LocalModelTier.MID, "sync"
        # 규칙 6: 동기인데 추론 필요(medium/hard) → MID
        if req.difficulty in ("medium", "hard") and req.sync:
            return LocalModelTier.MID, "sync"
        # 규칙 7: 안전 기본값 → FAST (가장 빠르고 SLA 충족)
        return LocalModelTier.FAST, "sync"
