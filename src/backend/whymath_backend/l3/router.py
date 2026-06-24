"""L3 라우터 결정 로직 — 축1(C.1) → [LOCAL이면] 축3(C.0) → 축2(C.2) 순차 결정.

설계 정본: `docs/architecture/03a_l3_router_design.md`
  - §C.1 축1 결정표(6규칙) / §C.0 축3 패밀리 결정표(5규칙) / §C.2 축2 결정표(7규칙)
    + §C.4 의사코드
  - §A.0 패밀리(축3)×크기(축2) 매트릭스 → 실제 모델 ID lookup
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
    ModelFamily,
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
"""로컬 티어별 예상 지연(ms). 출처: 03a §A.1 벤치 p50.

지연은 *크기 등급별* 대표값이다(2026-05-19 벤치는 qwen2-math 라인업으로 측정).
같은 크기 등급의 GENERAL(qwen2.5:3b/7b) 지연은 동급으로 가정한다(03a §A.1 메모,
패밀리별 지연 재측정은 §H 후속).
"""

# ──────────────────────────────────────────────────────────────────────────
# 축3 그라운딩 — 패밀리(축3)×크기(축2) → 실제 모델 ID 매트릭스 (03a §A.0·§C.4)
# QUALITY(27b)는 패밀리 무관 상위 티어 — 매트릭스에 (패밀리, QUALITY)는 두지 않고
# resolve_model()이 별도 처리한다(27b가 양 패밀리 포괄, 03a §A.0).
# ──────────────────────────────────────────────────────────────────────────
LOCAL_MODEL_MATRIX: Final[dict[tuple[ModelFamily, LocalModelTier], str]] = {
    (ModelFamily.MATH, LocalModelTier.FAST): "qwen2-math:1.5b",
    (ModelFamily.MATH, LocalModelTier.MID): "qwen2-math:7b",
    (ModelFamily.GENERAL, LocalModelTier.FAST): "qwen2.5:3b",
    (ModelFamily.GENERAL, LocalModelTier.MID): "qwen2.5:7b",
    # 멀티모달(VL) — Qwen3-VL 단일 모델. `:latest` 드리프트 회피로 `qwen3-vl:8b` 명시 핀
    # (6.1GB·현 :latest·로컬 풀 가능). 2026-06-23 ollama 태그 확인(4b/8b/235b-cloud).
    # ★ pull_ocr_models.sh VL_MODEL 디폴트·OCR_LIVE_VERIFICATION.md와 *반드시* 일치시킬 것.
    (ModelFamily.VISION, LocalModelTier.FAST): "qwen3-vl:8b",
}
"""로컬 모델 ID = (패밀리 축3 × 크기 축2) lookup. 출처: 03a §A.0 매트릭스.

QUALITY는 패밀리 무관 → 이 매트릭스에 없고 QUALITY_MODEL_ID로 해석한다.
llm-architect.md A.0 매트릭스와 동일해야 한다.
"""

QUALITY_MODEL_ID: Final[str] = "qwen3.5:27b"
"""QUALITY 티어 실제 모델 — 패밀리 무관(27b가 MATH/GENERAL 양쪽 포괄, 03a §A.0)."""

# ──────────────────────────────────────────────────────────────────────────
# 축3 결정 입력 집합 — NLP임이 분명한 호출지점·태스크 (03a §C.0 규칙1·3)
# "NLP임이 분명할 때 GENERAL, 그 외 MATH(안전 기본값)" — 03a §C.0 메모.
# ──────────────────────────────────────────────────────────────────────────
NLP_CALL_SITES: Final[frozenset[CallSite]] = frozenset(
    {
        CallSite.CONCEPT_EXTRACT,  # ① 개념 추출
        CallSite.TRANSLATE_NORMALIZE,  # ③ 번역·정규화
        CallSite.CONCEPT_ID_MATCH,  # ④ 개념 ID 매칭
    }
)
"""NLP 호출지점(축3=GENERAL) — ①③④ (03a §C.0 규칙1). ②(깊이추론)는 MATH."""

NLP_TASK_TYPES: Final[frozenset[str]] = frozenset({"extract", "match", "translate", "classify"})
"""NLP 계열 task_type(축3=GENERAL) — 추출·매칭·정규화·분류 (03a §C.0 규칙3)."""

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
# guard_cloud의 "잔여 예산 부족" 판정·est_cost_krw에 쓰이는 1회 호출 추정 비용.
# 비용(KRW)은 *공개 가격*에서 유도한 sourced 추정이다(fabricate 아님·2026-06-23 확인):
#   - CLOUD_MID  = claude-sonnet-4-6  $3/$15 per 1M(in/out)
#   - CLOUD_HIGH = claude-opus-4-7    $5/$25 per 1M(in/out)
#   - 환율 1 USD ≈ 1,540 KRW(2026-06-23). 기준 호출 = 입력 1K + 출력 1K 토큰(대표 코칭 생성).
#   MID = (1K·$3+1K·$15)/1M × 1540 ≈ ₩28 / HIGH = (1K·$5+1K·$25)/1M × 1540 ≈ ₩46.
# 잔여 불확실(정직): 호출당 실 토큰 수는 워크로드별 가변 → 라이브 토큰 계측으로 최종 보정.
# ──────────────────────────────────────────────────────────────────────────
CLOUD_MIN_COST_KRW: Final[dict[CostTier, float]] = {
    # 1회 호출 추정 비용(원) — 잔여 예산이 이보다 작으면 LOCAL 강등(§D.4). 위 유도 참조.
    CostTier.CLOUD_MID: 28.0,  # sonnet-4-6 1K+1K × ₩1,540 — 라이브 토큰 계측 시 보정
    CostTier.CLOUD_HIGH: 46.0,  # opus-4-7 1K+1K × ₩1,540 — 라이브 토큰 계측 시 보정
}
"""클라우드 티어 1회 호출 추정 비용(원). 공개 가격 유도(2026-06-23)·라이브 토큰 계측 보정 대상."""

CLOUD_LATENCY_MS: Final[dict[CostTier, int]] = {
    # 03a §A.1 표에서 CLOUD는 "가변" — 네트워크·모델 의존. 지연은 *측정값*이라 공개 가격처럼
    # 유도할 수 없다 → placeholder 유지, 라이브 실측 보정(§H 후속 4).
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


def _as_model_family(value: object) -> ModelFamily | None:
    """문자열/enum/None 어느 쪽이 와도 ModelFamily|None으로 정규화."""
    if value is None:
        return None
    if isinstance(value, ModelFamily):
        return value
    return ModelFamily(value)


def resolve_model(
    local_family: ModelFamily | None,
    local_model: LocalModelTier | None,
) -> str:
    """(패밀리 축3 × 크기 축2) → 실제 로컬 모델 ID 해석 (03a §A.0 매트릭스 lookup).

    호출 직전 LLMClient가 수행하는 lookup을 로직 헬퍼로 노출한다.
      - QUALITY → 패밀리 무관 `qwen3.5:27b`(27b가 양 패밀리 포괄, 03a §A.0).
      - FAST/MID → (패밀리, 크기) 매트릭스 lookup. 이때 패밀리가 None이면 오류
        (불변식 4 위반 — LOCAL+FAST/MID는 패밀리가 반드시 있어야 한다).
    클라우드(local_model None)에는 적용하지 않는다 — 호출 전 cost_tier로 분기.
    """
    local = _as_local_tier(local_model)
    family = _as_model_family(local_family)
    if local is None:
        raise ValueError("resolve_model은 로컬 티어에만 적용된다(local_model이 None)")
    if local is LocalModelTier.QUALITY:
        return QUALITY_MODEL_ID  # 패밀리 무관
    if family is None:
        raise ValueError(
            f"불변식 위반: local_model={local.value}(FAST/MID)는 local_family가 "
            "필요하다 (03a §A.0·§G 불변식 4)"
        )
    return LOCAL_MODEL_MATRIX[(family, local)]


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
# 캐시 키 (03a §F.1 — 세 축 {cost_tier}:{local_family}:{local_model} 포함)
# ──────────────────────────────────────────────────────────────────────────
def cache_key(
    prompt: str,
    system: str,
    cost_tier: CostTier,
    local_family: ModelFamily | None,
    local_model: LocalModelTier | None,
    *,
    image_digest: str | None = None,
) -> str:
    """프롬프트+시스템+(세 축 합성 식별자)[+이미지 다이제스트] 기반 캐시 키 (03a §F.1).

    같은 프롬프트라도 *어느 티어·패밀리가 생성했는지*가 캐시 정체성의 일부다 —
    FAST 응답과 QUALITY 응답을, 그리고 MATH(qwen2-math) 응답과 GENERAL(qwen2.5)
    응답을 섞지 않는다(패밀리가 다르면 출력 특성·신뢰도가 다르므로, 03a §F.1).
    예: "local:general:fast"(qwen2.5:3b), "local:math:mid"(qwen2-math:7b),
    "cloud_mid:-:-". 학생 ID는 키에 포함하지 않는다(개인화는 컨텍스트로).

    `image_digest`(멀티모달 입력 이미지의 해시)가 주어지면 키에 합성한다 — 같은
    프롬프트라도 *이미지가 다르면 다른 캐시*(다른 크롭=다른 수식). **None(텍스트
    호출)이면 키가 기존과 100% 동일**(하위호환·텍스트 캐시 무영향).
    """
    cost = _as_cost_tier(cost_tier)
    family = _as_model_family(local_family)
    local = _as_local_tier(local_model)
    family_id = family.value if family is not None else "-"
    local_id = local.value if local is not None else "-"
    model_id = f"{cost.value}:{family_id}:{local_id}"
    content = f"{system}|||{prompt}|||{model_id}"
    if image_digest is not None:
        content = f"{content}|||img:{image_digest}"  # 이미지 있을 때만 부가(텍스트 키 불변)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


def cache_key_for(
    prompt: str, system: str, decision: RoutingDecision, *, image_digest: str | None = None
) -> str:
    """RoutingDecision으로부터 캐시 키 생성 — cache_key()의 편의 래퍼(이미지 다이제스트 통과)."""
    return cache_key(
        prompt,
        system,
        decision.cost_tier,
        decision.local_family,
        decision.local_model,
        image_digest=image_digest,
    )


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
    validation_signal: str | None = None,
) -> dict[str, object]:
    """Langfuse 기록 필드 dict 생성 (03a §F.2 표).

    범위 메모: *dict만* 반환한다. 실제 Langfuse 전송은 TraceSink 구현의 책임이며
    M1.2 범위 밖이다. `latency_ms`·`cost_krw`는 *실측* 필드라 여기서는 채우지 않고
    (라우터는 추정만 함), 추정치는 est_* 로 별도 노출한다.

    `validation_signal`은 런타임 shadow 검증(L3 결정론 도구) 결과다 — None=통과(또는
    미검증), 문자열=거짓 수치 관계 등 *환각 신호 사유*. 비차단 관측 전용이며 반환
    텍스트·캐시 동작에 영향을 주지 않는다(학생 노출 경계는 L4/L5 책임, CLAUDE.md).
    """
    cost = _as_cost_tier(decision.cost_tier)
    family = _as_model_family(decision.local_family)
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
        "local_family": family.value if family is not None else None,  # 패밀리별 분포
        "local_model": local.value if local is not None else None,  # 로컬 내부 분포
        "mode": decision.mode,  # SLA 평가 분리(동기만 게이트 대상)
        "est_latency_ms": decision.est_latency_ms,  # 추정 지연(실측은 latency_ms)
        "est_cost_krw": decision.est_cost_krw,  # 추정 비용(실측은 cost_krw)
        "call_site": site.value if site is not None else None,  # 호출지점별 분포
        "cache_hit": cache_hit,  # 캐싱 적중률 KPI
        "escalated_from": escalated,  # 에스컬레이션 빈도 분석
        "student_id_hash": student_id_hash,  # 직접 ID 금지(해시만)
        "reason": decision.reason,  # 결정 근거
        "validation_signal": validation_signal,  # 런타임 shadow 검증 환각 신호(비차단)
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

    축1(C.1, 80/18/2) → [LOCAL이면] 축3(C.0, MATH/GENERAL) → 축2(C.2, FAST/MID/
    QUALITY)를 *순차* 평가한다. 패밀리(축3)를 크기(축2)보다 먼저 정한다 — 같은
    크기 등급이라도 패밀리가 가리키는 실제 모델이 다르기 때문(03a §0.2·§C).
    `route()`는 *어디서 생성할지*만 정한다. 생성된 응답은 03 문서 환각 방어
    파이프라인을 *반드시* 통과해야 학생에게 노출된다(03a §C.4 메모,
    CLAUDE.md 절대 금기 "LLM 응답을 검증 없이 학생에게 제공 금지").
    """

    def route(self, req: RoutingRequest) -> RoutingDecision:
        """라우팅 결정 — 축1(C.1) → [LOCAL이면] 축3(C.0) → 축2(C.2) (03a §C.4)."""
        # 멀티모달(VL) 단축 경로 — 이미지 인식은 항상 LOCAL Qwen3-VL(VISION 패밀리)·FAST·동기.
        # 수학/일반 텍스트 패밀리·크기 규칙을 건너뛴다(이미지 인식은 직교 축, 03a 확장).
        # 미성년자 프라이버시·로컬-우선(CLAUDE.md 2026-05-28)이라 클라우드 비전 승급은 없다.
        if req.requires_vision:
            return RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_family=ModelFamily.VISION,
                local_model=LocalModelTier.FAST,
                mode="sync",
                reason="local/vision/fast (multimodal)",
                est_latency_ms=local_latency(LocalModelTier.FAST),
                est_cost_krw=0.0,
            )
        cost_tier = self._decide_cost_tier(req)

        # CLOUD 경로면 축3·축2 없음 — 불변식 2·4(03a §G)
        if cost_tier != CostTier.LOCAL:
            return RoutingDecision(
                cost_tier=cost_tier,
                local_family=None,
                local_model=None,
                mode="sync",
                reason="cloud escalation",
                est_latency_ms=cloud_latency(cost_tier),
                est_cost_krw=cloud_cost(req, cost_tier),
            )

        # LOCAL 경로 → 축3(패밀리) 먼저, 그다음 축2(크기)
        family = self._decide_family(req)
        local_model, mode = self._decide_local_tier(req)

        # QUALITY(27b)는 패밀리 무관 → local_family=None (불변식 4, 03a §A.0).
        # 단 reason에는 결정된 패밀리를 남겨 추적성을 유지한다(QUALITY로 합류 전 의도).
        family_applicable = local_model in (LocalModelTier.FAST, LocalModelTier.MID)
        decision_family = family if family_applicable else None
        return RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_family=decision_family,
            local_model=local_model,
            mode=mode,
            reason=f"local/{family.value}/{local_model.value}",
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

    # ── 축3: 로컬 모델 패밀리 (03a §C.0 결정표 — 크기보다 먼저) ──
    def _decide_family(self, req: RoutingRequest) -> ModelFamily:
        """축3 결정 — MATH / GENERAL (03a §C.0).

        축1=LOCAL로 확정된 요청만 평가. 태스크 *유형*(수학 vs NLP)으로 패밀리를
        가른다(크기·SLA가 아니라, §0.2 규칙2). "NLP임이 분명할 때 GENERAL,
        그 외 MATH(안전 기본값)" — WhyMath 호출 다수가 수학 계산이고, NLP를 수학
        모델로 보내면 7b조차 0%였으므로 NLP 식별 규칙을 *넓게* 잡는다(§C.0 메모).

        QUALITY로 합류할 요청도 패밀리를 정해두지만, route()에서 QUALITY면
        local_family는 None으로 비운다(27b가 양 패밀리 포괄, §A.0 불변식 4).
        """
        call_site = _as_call_site(req.call_site)
        # 규칙 1: NLP 호출지점 ①③④ → GENERAL (②=depth는 MATH)
        # 규칙 3: NLP 계열 task_type(추출·매칭·정규화·분류) → GENERAL
        if call_site in NLP_CALL_SITES or req.task_type in NLP_TASK_TYPES:
            return ModelFamily.GENERAL
        # 규칙 2·4·5: 그 외(②깊이추론·계산·풀이·증명·산술·미상) → MATH(안전 기본값)
        return ModelFamily.MATH

    # ── 축2: 로컬 모델 크기 (03a §C.2 결정표 9규칙) ──
    def _decide_local_tier(self, req: RoutingRequest) -> tuple[LocalModelTier, str]:
        """축2 결정 — FAST / MID / QUALITY + 모드 (03a §C.2 9규칙).

        축1=LOCAL·축3(패밀리) 결정 후 평가. 평가 순서 = 위에서 아래, 첫 매치 확정.
        규칙 3·4는 *GENERAL 호출지점 안에서도* 크기를 가른다 — match=FAST(3b=100%),
        extract/translate=MID(3b 하한 미달, 2026-05-20 실측). call_site가 호출지점을
        식별하므로 family 인자 없이 call_site로 분기한다.
        """
        call_site = _as_call_site(req.call_site)

        # 규칙 1: ⑤ 자기검증 → QUALITY 비동기 (패밀리 무관)
        if call_site == CallSite.SELF_VERIFY:
            return LocalModelTier.QUALITY, "async"
        # 규칙 2: 비동기 + (verify/generate or hard/killer) → QUALITY (27b 비동기 전용)
        if (not req.sync) and (
            req.task_type in ("verify", "generate") or req.difficulty in ("hard", "killer")
        ):
            return LocalModelTier.QUALITY, "async"
        # 규칙 3: ④ match → FAST (GENERAL match는 3b=100% → FAST로 충분, 2026-05-20)
        if call_site == CallSite.CONCEPT_ID_MATCH:
            return LocalModelTier.FAST, "sync"
        # 규칙 4: ① extract·③ translate → MID (GENERAL이나 3b 하한 미달 → 7b 필요)
        if call_site in (CallSite.CONCEPT_EXTRACT, CallSite.TRANSLATE_NORMALIZE):
            return LocalModelTier.MID, "sync"
        # 규칙 5: 동기 + SLA<2s → FAST (FAST만 게이트 통과, p50 1초)
        if req.sync and req.max_latency_ms < SLA_GATE_MS:
            return LocalModelTier.FAST, "sync"
        # 규칙 6: 즉답·분류·경량 매칭 → FAST
        if (
            req.conversation_phase in ("greeting", "followup")
            or req.task_type in ("match", "classify")
            or (req.difficulty == "easy" and not req.requires_reasoning)
        ):
            return LocalModelTier.FAST, "sync"
        # 규칙 7: 정밀 풀이·메인 대화(추론 필요) → MID (p50 4초 허용)
        if req.task_type in ("explain", "coach", "diagnose") and req.requires_reasoning:
            return LocalModelTier.MID, "sync"
        # 규칙 8: 동기인데 추론 필요(medium/hard) → MID
        if req.difficulty in ("medium", "hard") and req.sync:
            return LocalModelTier.MID, "sync"
        # 규칙 9: 안전 기본값 → FAST (가장 빠르고 SLA 충족)
        return LocalModelTier.FAST, "sync"
