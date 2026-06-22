"""Ollama 로컬 LLM 제공자 — interfaces.LLMProvider 구현 (M1.2-live S1).

라우터 결정(RoutingDecision)을 받아 Phaiakes9 로컬 Ollama 데몬으로 실제 생성을
수행한다. 로컬(CostTier.LOCAL) 결정만 처리하며, 클라우드는 범위 밖(S5)이다.

설계 정본: `docs/architecture/03a_l3_router_design.md` §A.0(모델 매트릭스)·§D.3(QUALITY
비동기 전용)·§A.1(벤치 지연). 테스트 주입 패턴은 infra/phaiakes9/benchmark/
bench_latency.py(`_OllamaClientProtocol` 경유 가짜 클라이언트 주입)를 미러링한다.

경계 메모 (CLAUDE.md 절대 금기): 이 제공자가 반환하는 텍스트는 *검증 전 원시 모델
출력*이다. 03 문서 환각 방어 파이프라인(스키마→SymPy/Lean→PRM→자기검증→사람검수)을
통과하기 전에는 *학생에게 직접 노출 금지* ("LLM 응답을 검증 없이 학생에게 제공 금지").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.router import (
    LOCAL_MODEL_MATRIX,
    QUALITY_MODEL_ID,
    _as_cost_tier,
    resolve_model,
)


# ──────────────────────────────────────────────────────────────────────────
# Ollama 클라이언트 추상화 (테스트 주입용) — bench_latency.py 패턴 미러링.
# 실제 `ollama.AsyncClient`와 동형이지만 테스트는 가짜 객체로 대체한다.
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _OllamaClient(Protocol):
    """ollama 비동기 클라이언트의 최소 인터페이스 (구조적 타이핑).

    `ollama.AsyncClient`의 부분집합. `generate`는 단일 프롬프트 생성, `list`는
    설치된 모델 목록 조회. 반환 타입은 라이브러리 버전별로 dict 또는 pydantic
    객체일 수 있어 `Any`로 두고, 제공자 쪽에서 방어적으로 정규화한다.
    """

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str,
        images: Sequence[str] | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        """단일 프롬프트 생성 (ollama generate API). `images`=멀티모달(VL) base64 목록."""
        ...

    async def list(self) -> Any:
        """설치된 모델 목록 조회 (ollama list API)."""
        ...


# ──────────────────────────────────────────────────────────────────────────
# /status 보고용 값 객체
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ModelAvailability:
    """라우팅에 필요한 단일 로컬 모델의 설치 여부."""

    model_id: str
    present: bool


@dataclass(slots=True, frozen=True)
class OllamaStatus:
    """Ollama 준비 상태 보고 (/status 엔드포인트용).

    `reachable=False`면 데몬에 닿지 못한 것이며, 이는 *처리된 비크래시 상태*다
    (호출자는 503/ready=false로 보고하되 500을 던지지 않는다).
    """

    reachable: bool
    models: tuple[ModelAvailability, ...]
    error: str | None = None

    @property
    def all_present(self) -> bool:
        """라우팅 매트릭스의 모든 모델이 설치돼 있는가."""
        return self.reachable and all(m.present for m in self.models)

    @property
    def missing(self) -> tuple[str, ...]:
        """미설치 모델 ID 목록."""
        return tuple(m.model_id for m in self.models if not m.present)


# 라우팅이 실제로 요구하는 로컬 모델 ID 전체 = 매트릭스(FAST/MID) + QUALITY(27b).
# 03a §A.0. /status가 이 집합의 설치 여부를 점검한다.
_REQUIRED_MODEL_IDS: tuple[str, ...] = (
    *sorted(set(LOCAL_MODEL_MATRIX.values())),
    QUALITY_MODEL_ID,
)


def _extract_model_names(list_response: Any) -> set[str]:
    """ollama list 응답에서 모델 이름 집합을 방어적으로 추출.

    ollama 버전에 따라 응답이 (a) pydantic `ListResponse`(`.models[*].model`),
    (b) dict(`{"models": [{"model"|"name": ...}]}`) 등으로 달라질 수 있어 양쪽을
    모두 흡수한다. 정규화 실패 시 빈 집합(닿았으나 비어 있음과 동일하게 취급).
    """
    raw_models: Any
    if hasattr(list_response, "models"):
        raw_models = list_response.models
    elif isinstance(list_response, dict):
        raw_models = list_response.get("models", [])
    else:
        return set()

    names: set[str] = set()
    for item in raw_models or []:
        name: Any = None
        if hasattr(item, "model"):
            name = item.model
        elif isinstance(item, dict):
            name = item.get("model") or item.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _extract_text(generate_response: Any) -> str:
    """ollama generate 응답에서 생성 텍스트를 방어적으로 추출.

    pydantic `GenerateResponse`(`.response`) 또는 dict(`{"response": ...}`)
    양쪽을 흡수한다. 둘 다 아니면 빈 문자열.
    """
    if hasattr(generate_response, "response"):
        text = generate_response.response
        return text if isinstance(text, str) else ""
    if isinstance(generate_response, dict):
        text = generate_response.get("response", "")
        return text if isinstance(text, str) else ""
    return ""


def _build_default_client(settings: Settings) -> _OllamaClient:
    """기본 ollama AsyncClient 생성 (지연 import).

    `ollama` 라이브러리/데몬이 없는 환경(CI 단위테스트)에서도 모듈 import가 깨지지
    않도록 *호출 시점에만* import한다 (bench_latency.py 패턴). 라이브러리 미설치는
    명확한 RuntimeError로 보고한다.
    """
    try:
        from ollama import AsyncClient
    except ImportError as exc:  # pragma: no cover — 환경 의존(라이브러리 미설치)
        raise RuntimeError(
            "ollama Python 클라이언트가 설치되지 않았습니다. "
            "`pip install ollama` 후 다시 시도하세요."
        ) from exc
    # ollama AsyncClient는 timeout을 httpx로 전달한다(초 단위).
    #
    # cast 사유: ollama가 제공하는 정밀 overload 스텁(stream=Literal[False/True]별
    # 반환 타입)은 우리의 좁은 구조적 시임 `_OllamaClient`와 형태가 어긋난다. 우리가
    # 실제로 쓰는 호출 규약(generate(model=,prompt=,system=,stream=False)·list())은
    # AsyncClient가 런타임에 충족하므로, 스텁 정밀도 차이만 cast로 좁힌다(타입 무시 X).
    client = AsyncClient(
        host=settings.ollama_host,
        timeout=settings.ollama_request_timeout_s,
    )
    return cast(_OllamaClient, client)


class OllamaProvider:
    """로컬 Ollama 생성 제공자 — interfaces.LLMProvider 충족.

    라우터 결정의 (패밀리 축3 × 크기 축2)를 resolve_model()로 실제 모델 ID로 바꾼 뒤
    Ollama로 호출한다. 클라우드(CLOUD_*) 결정은 명시적으로 거부한다(S5 범위).

    클라이언트는 지연 생성(lazy)·주입 가능(injectable)하다 — 테스트는 가짜 클라이언트를
    `client=` 로 넣고, 프로덕션은 기본 AsyncClient를 첫 호출 때 생성한다.
    """

    def __init__(
        self,
        *,
        client: _OllamaClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        # 주입된 클라이언트가 있으면 그것을 쓰고, 없으면 첫 사용 시 기본 생성(지연).
        self._client = client
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self) -> _OllamaClient:
        """클라이언트 지연 해석 — 주입 우선, 없으면 기본 AsyncClient 생성."""
        if self._client is None:
            self._client = _build_default_client(self._resolved_settings)
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> str:
        """라우터 결정에 따라 로컬 Ollama로 생성 (LLMProvider 구현).

        - CostTier.LOCAL이 아니면 즉시 거부(클라우드는 S5 범위 밖).
        - LOCAL FAST/MID/QUALITY는 resolve_model()로 실제 모델 ID를 얻어 호출한다
          (QUALITY→qwen3.5:27b, 패밀리 무관; FAST/MID→매트릭스 lookup, 03a §A.0;
          VISION/FAST→qwen3-vl 멀티모달).
        - `images`(base64 목록)가 주어지면 ollama generate의 `images=`로 전달한다 —
          VL 모델(qwen3-vl)이 이미지를 받는다. None이면 기존 텍스트 호출과 동일.

        주의: QUALITY(27b)의 *동기 디스패치 차단*은 파이프라인(pipeline.generate)의
        책임이다(03a §D.3). 제공자 자체는 모델 ID 해석·호출만 담당한다 —
        비동기 워커가 같은 제공자로 QUALITY를 호출할 수 있어야 하기 때문.

        반환 텍스트는 *검증 전 원시 출력*이다(모듈 docstring 경계 메모 참조).
        """
        cost = _as_cost_tier(decision.cost_tier)
        if cost is not CostTier.LOCAL:
            raise ValueError(
                f"OllamaProvider는 로컬 결정만 처리한다(받은 cost_tier={cost.value}). "
                "클라우드 티어는 S5 범위 밖이다(03a §H 후속 4)."
            )

        # (패밀리 × 크기) → 실제 Ollama 모델 ID. local_model이 None이면 resolve_model이
        # 명확히 오류를 던진다(불변식 1 위반은 RoutingDecision 검증에서 이미 차단됨).
        # VISION/FAST는 매트릭스에서 qwen3-vl로 해석된다(텍스트 패밀리와 동일 경로).
        model_id = resolve_model(decision.local_family, decision.local_model)

        # images는 *있을 때만* 전달한다 — 텍스트 전용 클라이언트(기존 가짜 시임)는 images
        # 인자 없이도 동작(하위호환). 멀티모달(VL)일 때만 ollama generate의 images=로 싣는다.
        client = self._get_client()
        if images is not None:
            response = await client.generate(
                model=model_id, prompt=prompt, system=system, images=images, stream=False
            )
        else:
            response = await client.generate(
                model=model_id, prompt=prompt, system=system, stream=False
            )
        return _extract_text(response)

    async def check_status(self) -> OllamaStatus:
        """Ollama 도달성 + 라우팅 모델 매트릭스 설치 여부 점검 (/status용).

        데몬에 닿지 못하면 예외를 *흡수*하고 `reachable=False`로 보고한다 —
        /status는 Ollama가 죽어 있어도 500을 던지지 않고 상태를 *보고*해야 한다.
        """
        try:
            list_response = await self._get_client().list()
        except Exception as exc:  # noqa: BLE001 — 도달 불가를 비크래시 상태로 흡수
            return OllamaStatus(
                reachable=False,
                models=tuple(
                    ModelAvailability(model_id=mid, present=False) for mid in _REQUIRED_MODEL_IDS
                ),
                error=f"{type(exc).__name__}: {exc}",
            )

        installed = _extract_model_names(list_response)
        return OllamaStatus(
            reachable=True,
            models=tuple(
                ModelAvailability(model_id=mid, present=mid in installed)
                for mid in _REQUIRED_MODEL_IDS
            ),
            error=None,
        )
