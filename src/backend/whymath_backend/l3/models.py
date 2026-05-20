"""L3 라우터 스키마 — 두 라우팅 축의 enum + 입력/출력 모델 (Pydantic).

설계 정본: `docs/architecture/03a_l3_router_design.md` §G(스키마)·§0.1(명칭 충돌 해소).

두 라우팅 축 (03a §0):
  - 축1 `CostTier` (비용·위치): LOCAL / CLOUD_MID / CLOUD_HIGH — 목표 분포 80/18/2
  - 축2 `LocalModelTier` (로컬 모델 크기): FAST(1.5b) / MID(7b) / QUALITY(27b)
    — CostTier.LOCAL일 때만 의미를 가진다.

명칭 충돌 해소: 기존 단일 enum `LLMTier{LOCAL,MID,HIGH}`를 (a) 축1 `CostTier`와
(b) 축2 `LocalModelTier`로 분해한다. `LLMTier.MID → CostTier.CLOUD_MID`,
`LLMTier.HIGH → CostTier.CLOUD_HIGH`로 1:1 의미 보존(03a §0.1).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ──────────────────────────────────────────────────────────────────────────
# 축1: 비용·위치 (기존 LLMTier.MID/HIGH → CLOUD_ 접두사로 개명, 03a §0.1)
# ──────────────────────────────────────────────────────────────────────────
class CostTier(str, Enum):
    """비용·위치 축 — 클라우드로 *올라갈* 것인가? (03a §0 표·§A.1)"""

    LOCAL = "local"
    """Phaiakes9 로컬 (0원) — 축2(LocalModelTier)로 세분."""

    CLOUD_MID = "cloud_mid"
    """Claude Sonnet 4.6 등 (구 LLMTier.MID). ~$0.003/$0.015."""

    CLOUD_HIGH = "cloud_high"
    """Claude Opus 4.7 / GPT-5 등 (구 LLMTier.HIGH). ~$0.015/$0.075."""


# ──────────────────────────────────────────────────────────────────────────
# 축2: 로컬 모델 크기 (2026-05-19 벤치 라인업, CostTier.LOCAL일 때만 적용)
# 그라운딩 데이터: 03a §A.1 (Phaiakes9 / Radeon 8060S / Ollama 0.24.0).
# ──────────────────────────────────────────────────────────────────────────
class LocalModelTier(str, Enum):
    """로컬 모델 크기 축 — 로컬에서 *어느 크기* 모델인가? (03a §A.1)"""

    FAST = "fast"
    """qwen2-math:1.5b — p50 1,010ms, SLA 게이트(p50<2s) PASS, 동기 즉답."""

    MID = "mid"
    """qwen2-math:7b — p50 3,918ms, 동기 가능(즉답엔 길다). 정밀 풀이·메인 대화."""

    QUALITY = "quality"
    """qwen3.5:27b — p50 13,886ms, 병렬 미작동(GPU 단일 점유) → 비동기 전용."""


# ──────────────────────────────────────────────────────────────────────────
# 5개 핵심 호출지점 (03a §B.2 — PRD가 식별한 LLM 필수 호출지점 ①~⑤)
# ──────────────────────────────────────────────────────────────────────────
class CallSite(str, Enum):
    """LLM 핵심 호출지점 식별자 (03a §B.2, 03 문서 "LLM 핵심 호출지점")."""

    CONCEPT_EXTRACT = "extract"
    """① 개념 추출 — 기본 FAST. 반복성 높음·캐싱 적중률 큼."""

    DEEP_REASON = "depth"
    """② 깊이 추론 — 기본 MID(난이도 hard↑면 QUALITY/CLOUD). 다단계."""

    TRANSLATE_NORMALIZE = "translate"
    """③ 번역·정규화 — 기본 FAST. 표기 통일·동의어 정규화는 경량."""

    CONCEPT_ID_MATCH = "match"
    """④ 개념 ID 매칭 — 기본 FAST(모호하면 MID). 매칭 실패 → 사람 검수."""

    SELF_VERIFY = "self_verify"
    """⑤ 자기검증 — QUALITY 비동기 전용. 환각 방어 ③. 추가 비용 → 샘플링."""


# ──────────────────────────────────────────────────────────────────────────
# 입력: RoutingRequest (기존 llm-architect.md 모델 확장, 03a §B.1·§G)
# ──────────────────────────────────────────────────────────────────────────
class RoutingRequest(BaseModel):
    """라우팅 결정의 입력 신호 (03a §B.1 입력 신호 표)."""

    model_config = ConfigDict(
        # 추가 필드 금지 — 모델이 스키마의 단일 진실 (data-pipeline 컨벤션)
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    task_type: str = Field(
        ...,
        description=(
            "작업 유형 — explain/diagnose/coach/generate/verify/prove/"
            "extract/match/translate/self_verify (03a §B.1)"
        ),
    )
    difficulty: str = Field(
        ...,
        description="난이도 — easy/medium/hard/killer. 축1·축2 동시 영향 (03a §B.1)",
    )
    requires_reasoning: bool = Field(
        ...,
        description="다단계 추론 필요 여부 — MID/QUALITY·CLOUD 승급 신호",
    )
    student_subscription: str = Field(
        ...,
        description="구독 — free/basic/premium/gifted. CLOUD 승급 가드 (03a §E.2)",
    )
    max_latency_ms: int = Field(
        default=30000,
        description="SLA 한도(ms). <2000이면 사실상 FAST 강제 (03a §B.1·C.2 규칙3)",
        ge=0,
    )
    budget_krw: float = Field(
        default=0.0,
        description=(
            "이 호출의 클라우드 잔여 예산(원). 0 이하면 LOCAL 강제 "
            "(구 budget_cents 개명, 03a §B.1·§E.2)"
        ),
    )
    # ── 신규 신호 (03a §B.1·§G) ──
    sync: bool = Field(
        default=True,
        description="True=동기 즉답 요구, False=비동기 허용. QUALITY 게이팅의 핵심",
    )
    conversation_phase: str | None = Field(
        default=None,
        description=(
            "L4 대화 상태 — greeting/probing/hint/solution_reveal/followup. "
            "즉답성 판단 (03a §B.1)"
        ),
    )
    call_site: CallSite | None = Field(
        default=None,
        description="5개 핵심 호출지점 식별 ①~⑤ (없으면 일반 호출, 03a §B.2)",
    )


# ──────────────────────────────────────────────────────────────────────────
# 출력: RoutingDecision — 두 축을 합성한 결정 객체 (03a §G)
# ──────────────────────────────────────────────────────────────────────────
class RoutingDecision(BaseModel):
    """라우팅 결정 — (축1, 축2) 쌍 + 모드·근거·추정치 (03a §G).

    불변식 (03a §G·§0.1, after-validator로 강제):
      1. cost_tier == LOCAL  ⟺  local_model is not None
      2. cost_tier in {CLOUD_MID, CLOUD_HIGH}  ⟺  local_model is None
      3. local_model == QUALITY  ⟹  mode == "async" (27b 동기 불가, 03a §A.1)
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    cost_tier: CostTier = Field(..., description="축1 — 비용·위치 결정")
    local_model: LocalModelTier | None = Field(
        default=None,
        description="축2 — 로컬 모델 크기 (cost_tier=LOCAL일 때만, 아니면 None)",
    )
    mode: str = Field(
        default="sync",
        description="sync/async — QUALITY는 async 강제 (03a §A.1·C.2)",
    )
    reason: str = Field(
        default="",
        description="결정 근거 (디버깅·Langfuse 태그용, 03a §F.2)",
    )
    est_latency_ms: int = Field(
        ...,
        description=("예상 지연(ms) — FAST≈1010/MID≈3918/QUALITY≈13886/CLOUD≈가변 " "(03a §A.1)"),
        ge=0,
    )
    est_cost_krw: float = Field(
        default=0.0,
        description="예상 비용(원) — 로컬=0, 클라우드 추정 (03a §E)",
        ge=0.0,
    )

    @model_validator(mode="after")
    def _validate_axis_invariants(self) -> RoutingDecision:
        """두 축 불변식 강제 (03a §G·§0.1).

        use_enum_values=True 환경에서도 동작하도록 enum/문자열 양쪽을 비교한다.
        """
        # use_enum_values=True면 필드가 문자열 값일 수 있으므로 정규화
        cost_value = (
            self.cost_tier.value if isinstance(self.cost_tier, CostTier) else self.cost_tier
        )
        local_value = (
            self.local_model.value
            if isinstance(self.local_model, LocalModelTier)
            else self.local_model
        )

        is_local = cost_value == CostTier.LOCAL.value

        # 불변식 1·2: LOCAL ⟺ local_model 존재
        if is_local and local_value is None:
            raise ValueError(
                "불변식 위반: cost_tier=LOCAL이면 local_model이 반드시 있어야 한다 "
                "(03a §G 불변식 1)"
            )
        if (not is_local) and local_value is not None:
            raise ValueError(
                f"불변식 위반: cost_tier={cost_value}(CLOUD_*)이면 local_model은 "
                f"None이어야 한다(현재 {local_value!r}, 03a §G 불변식 2)"
            )

        # 불변식 3: QUALITY ⟹ async
        if local_value == LocalModelTier.QUALITY.value and self.mode != "async":
            raise ValueError(
                f"불변식 위반: local_model=QUALITY(27b)는 mode='async'여야 한다 "
                f"(현재 {self.mode!r}, 동기 불가 03a §A.1·§G 불변식 3)"
            )

        # 모드 값 자체 검증
        if self.mode not in ("sync", "async"):
            raise ValueError(f"mode는 'sync' 또는 'async'여야 한다(현재 {self.mode!r})")

        return self
