"""빌드타임 사전생성(pre-warm) — L3 캐시 사전적재 하니스의 값 객체 스키마.

설계 정본: MEMORY.md 2026-05-20 "Claude Max = 빌드타임 콘텐츠 생성" 결정 로그·
03a §F.1 캐시 키. 런타임 `pipeline.generate`와 *같은* `Router`·`cache_key_for`로
응답을 저장해 학생 런타임이 캐시 히트(0원)되도록 한다.

핵심 결합점 (`l3/pipeline.py:125·152`): 런타임은 `decision = Router().route(req)` →
`key = cache_key_for(prompt, system, decision)` → `cache.get(key)`. 사전적재기도
*동일한* (`req`, `prompt`, `system`)으로 같은 키를 만들어 `cache.set`한다.

검증 신호 값 객체(`ValidationSignal`)도 여기 둔다 — 빌드타임 시드뿐 아니라 런타임 shadow
검증·학생 풀이 슬립 검출이 같은 신호를 공유한다(`validator.validate_response` 경로).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.models import RoutingRequest


class PregenItem(BaseModel):
    """사전생성 항목 — 라우팅 신호 + 프롬프트 + 선택적 외부 응답(인제스트 모드).

    `precomputed_response`가 채워져 있으면 *인제스트 모드*: provider 호출 없이 그 응답을
    검증 후 캐시에 적재한다(Max-Claude가 빌드타임에 만든 시드를 받아 넣는 경로).
    None이면 *생성 모드*: provider로 직접 생성한다(로컬 Qwen 대량 사전생성).

    `request`의 라우팅 신호는 *런타임이 보낼 신호와 일치*해야 사전적재 키가 런타임
    캐시 키와 같다(라우터 결정 축에 의존, 03a §F.1). 신호가 어긋나면 사전적재한 항목은
    런타임에서 *영원히 히트하지 않는다*.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(..., description="사용자 프롬프트(런타임과 동일해야 키 일치)")
    system: str = Field(default="", description="시스템 프롬프트")
    request: RoutingRequest = Field(
        ..., description="런타임이 보낼 라우팅 신호 — 키 정합 핵심(03a §F.1)"
    )
    precomputed_response: str | None = Field(
        default=None,
        description=(
            "외부 사전생성 응답(예: Max-Claude 수기 시드). None이면 provider로 생성한다. "
            "있으면 인제스트 모드 — provider 호출 없이 검증 후 캐시 적재."
        ),
    )


# 사전적재 결과 상태 — 가짜 enum 대신 Literal로 mypy 친화적이고 JSON 친화적.
PrewarmStatus = Literal["written", "skipped_exists", "failed_validation", "error"]


@dataclass(slots=True, frozen=True)
class PrewarmItemResult:
    """항목 단위 사전적재 결과 — 키·상태·실패 사유(있으면).

    `cache_key`는 정확한 추적·재시도용. `error`는 status 별 의미가 다르다:
      - "failed_validation" → validator가 돌려준 실패 사유(짧은 라벨/설명).
      - "error" → 예외 타입·메시지(provider/cache 호출 중 던진 것).
      - "written"/"skipped_exists" → None.
    """

    cache_key: str
    status: PrewarmStatus
    error: str | None = None


@dataclass(slots=True, frozen=True)
class PrewarmReport:
    """사전적재 배치 결과 — 항목 리스트 + 집계 카운트(파생).

    CLI는 카운트만 사람이 읽을 수 있게 요약하고, 테스트·자동화는 개별 항목 결과로
    검증한다.
    """

    items: tuple[PrewarmItemResult, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def written(self) -> int:
        return sum(1 for i in self.items if i.status == "written")

    @property
    def skipped_exists(self) -> int:
        return sum(1 for i in self.items if i.status == "skipped_exists")

    @property
    def failed_validation(self) -> int:
        return sum(1 for i in self.items if i.status == "failed_validation")

    @property
    def errored(self) -> int:
        return sum(1 for i in self.items if i.status == "error")


# ──────────────────────────────────────────────────────────────────────
# 검증 신호 — 검증기(validator.py)의 구조화 반환 값 객체 (slice 59).
# str 사유 대신 {kind, span, reason}를 돌려 L4가 산문 접두사 파싱 없이 종류(kind)를
# 읽고, L5가 span으로 오류를 하이라이트할 수 있게 한다. reason 문자열 형식은 불변이라
# 로그·trace·HTTP 등 문자열 경계로 `.reason`을 그대로 흘릴 수 있다(후방호환).
# ──────────────────────────────────────────────────────────────────────
# 검증 신호 종류 — 각 검증기가 자기 종류를 *직접* 선언(접두사 파싱 제거).
# L4 `SlipKind`와 동일 도메인(= 별칭으로 묶임).
ValidationSignalKind = Literal["arithmetic", "inequality", "not_equal", "solution", "other"]


@dataclass(slots=True, frozen=True)
class ValidationSignal:
    """검증 실패 신호 — 종류·사유·(선택) 원문 내 위치. 불변(frozen).

    - `kind`: 슬립/환각 종류. 검증기가 *직접* 선언한다(산문 접두사 파싱 불필요).
    - `reason`: 사람이 읽는 사유 문자열(예: "arithmetic error: '2 + 3 = 6' (sympy: 5 != 6)").
      로그·trace·HTTP 등 문자열 경계로 `.reason`을 그대로 흘린다(`GenerationResult.
      validation_signal`·`SolutionCoaching.validation_signal` 등 — 형식 불변·후방호환).
    - `span`: 원문(response) 내 오류 위치 `[start, end)`(0-based·half-open). 하이라이트용.
      None=위치 미상. slice 59a는 항상 None(span 생산은 후속 slice 59b).
    """

    kind: ValidationSignalKind
    reason: str
    span: tuple[int, int] | None = None
