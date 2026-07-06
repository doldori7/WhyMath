"""복합 LLM 제공자 — cost_tier로 로컬↔클라우드 디스패치 (M1.2-live S5).

라우터 결정의 축1(CostTier)을 보고 LOCAL→로컬 제공자(Ollama), CLOUD_*→클라우드
제공자(Anthropic)로 *디스패치*한다. interfaces.LLMProvider를 충족하므로 파이프라인·
앱의 `generate(provider=...)` 시그니처를 바꾸지 않고 단일 provider로 두 경로를 모두
태운다(provider-map 방식보다 변경 폭이 작다).

설계 정본: `docs/architecture/03a_l3_router_design.md` §A.0·§C.1·§C.4(클라우드는
mode="sync"). 클라우드 결정은 항상 동기라 비동기 큐(Celery)를 거치지 않는다 → 큐 워커는
로컬(QUALITY) 전용이며 이 디스패처를 알 필요가 없다.

큐 메모 (03a §C.4·§D.3): QUALITY(27b, mode="async")만 큐로 가고, 클라우드는 mode="sync"
라 동기 경로에서 이 디스패처를 탄다. 따라서 비동기 워커는 클라우드를 보지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.providers.anthropic import AnthropicStatus
from whymath_backend.l3.providers.ollama import OllamaStatus
from whymath_backend.l3.router import _as_cost_tier


class CompositeProvider:
    """로컬↔클라우드 디스패처 — interfaces.LLMProvider 충족.

    `generate()`는 decision.cost_tier로 분기한다: LOCAL→local, CLOUD_*→cloud. cloud가
    None(클라우드 미사용 배포)인데 클라우드 결정이 오면 *명확한 오류*를 던진다(조용한
    강등 금지). `check_status()`는 로컬 상태를(/status 로컬 매핑 보존), `check_cloud_status()`
    는 클라우드 상태를 분리 노출한다 — 앱의 기존 /status 로컬 경로를 건드리지 않고
    클라우드 필드만 덧붙이기 위함(저블래스트 반경).
    """

    def __init__(
        self,
        *,
        local: LLMProvider,
        cloud: LLMProvider | None = None,
    ) -> None:
        self._local = local
        self._cloud = cloud

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> str:
        """cost_tier로 로컬↔클라우드 디스패치 (LLMProvider 구현).

        - LOCAL → 로컬 제공자(Ollama)에 위임.
        - CLOUD_MID/CLOUD_HIGH → 클라우드 제공자(Anthropic)에 위임. cloud가 None이면
          명확한 RuntimeError(클라우드 결정이 왔으나 제공자 미구성 — 조용한 강등 금지).
        - `images`(멀티모달)는 위임받는 제공자로 그대로 전달한다(비전은 LOCAL Qwen3-VL이
          처리·클라우드 제공자는 images를 받으면 거부).
        - `temperature`(S2-g 생성 다양성)도 위임받는 제공자로 그대로 전달한다(온도 처리는 각
          하위 제공자 책임 — Ollama options·Anthropic API 인자).
        - `json_schema`(S2-j structured output)도 그대로 전달한다(제약 처리·거부는 각 하위
          제공자 책임 — Ollama format= 제약 디코딩·Anthropic 명확한 거부).

        반환 텍스트는 위임받은 제공자의 *검증 전 원시 출력*이다(각 제공자 docstring 경계 메모).
        """
        cost = _as_cost_tier(decision.cost_tier)
        # 선택 인자(images·temperature·json_schema)는 *있을 때만* 위임 호출에 싣는다 — 해당
        # 인자 미지원 하위 제공자(기존 구현·가짜)는 인자 없이도 동작(하위호환). 전부 None이면
        # 종전과 동일하게 `target.generate(prompt, system, decision)`로 호출된다.
        target = self._local if cost is CostTier.LOCAL else self._cloud
        if cost is not CostTier.LOCAL and target is None:
            raise RuntimeError(
                f"클라우드 결정({cost.value})이 내려졌으나 클라우드 제공자가 미구성입니다 "
                "(CompositeProvider(cloud=None)). 클라우드 라우팅을 쓰려면 cloud= 제공자를 "
                "주입하세요(03a §H 후속 4)."
            )
        assert target is not None  # 위 가드로 보장(LOCAL은 항상 _local·CLOUD는 None 차단)
        forward: dict[str, Any] = {}
        if images is not None:
            forward["images"] = images
        if temperature is not None:
            forward["temperature"] = temperature
        if json_schema is not None:
            forward["json_schema"] = json_schema
        return await target.generate(prompt, system, decision, **forward)

    async def check_status(self) -> OllamaStatus:
        """로컬 제공자의 레디니스 보고 — /status 로컬 매핑 보존.

        로컬 제공자가 check_status를 노출하지 않으면(가짜 등) 도달 불가로 보고한다
        (app.py·ollama check_status와 동일한 기능 탐지 패턴).
        """
        check = getattr(self._local, "check_status", None)
        if check is None:
            return OllamaStatus(
                reachable=False, models=(), error="local provider has no status check"
            )
        status: OllamaStatus = await check()
        return status

    async def check_cloud_status(self) -> AnthropicStatus | None:
        """클라우드 제공자의 구성·도달성 보고 — /status 클라우드 필드용.

        클라우드 제공자가 없거나(cloud=None) 상태 점검을 노출하지 않으면 None을 돌려준다
        (앱은 None이면 클라우드 필드를 채우지 않는다 → 기존 로컬 전용 응답과 호환).
        """
        if self._cloud is None:
            return None
        check = getattr(self._cloud, "check_status", None)
        if check is None:
            return None
        status: AnthropicStatus = await check()
        return status
