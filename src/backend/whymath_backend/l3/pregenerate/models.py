"""빌드타임 사전생성(pre-warm) — L3 캐시 사전적재 하니스의 값 객체 스키마.

설계 정본: MEMORY.md 2026-05-20 "Claude Max = 빌드타임 콘텐츠 생성" 결정 로그·
03a §F.1 캐시 키. 런타임 `pipeline.generate`와 *같은* `Router`·`cache_key_for`로
응답을 저장해 학생 런타임이 캐시 히트(0원)되도록 한다.

핵심 결합점 (`l3/pipeline.py:125·152`): 런타임은 `decision = Router().route(req)` →
`key = cache_key_for(prompt, system, decision)` → `cache.get(key)`. 사전적재기도
*동일한* (`req`, `prompt`, `system`)으로 같은 키를 만들어 `cache.set`한다.
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
