"""L3 관측성 싱크 — `TraceSink` Protocol의 Langfuse 구현.

설계 정본: docs/architecture/03a_l3_router_design.md §F.2(Langfuse 기록 필드).
라우터의 langfuse_fields()가 만든 *태그 dict*를 받아 Langfuse에 기록한다. 필드 dict
구성은 라우터(router.langfuse_fields)의 책임이고, 본 모듈은 *전송*만 담당한다 —
RecordingTraceSink(interfaces.py)의 프로덕션 대체물로 동일 Protocol을 구현한다.

CLAUDE.md 절대 원칙 "모든 LLM 호출 → Langfuse 추적"의 실제 전송 장치다.

테스트 가능성(bench_latency.py·quality_eval.py 패턴 미러링):
  - `langfuse` import는 *함수 안에서만*(lazy) — 모듈은 stdlib만으로 로드 가능해야
    테스트 수집이 라이브 SDK 없이 통과한다.
  - 클라이언트 주입 가능 — 테스트는 손으로 짠 가짜 Langfuse(event 기록)를 주입한다.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from whymath_backend.config import Settings, get_settings

# Langfuse 이벤트 이름 — 라우팅 결정 1건을 한 이벤트로 기록한다(F.2 필드 표가 metadata).
_EVENT_NAME: str = "l3_routing_decision"


class _LangfuseClientProtocol(Protocol):
    """langfuse 클라이언트의 최소 인터페이스 (`event` 1메서드).

    실제 `langfuse.Langfuse`와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    `event(name=..., metadata=...)`로 단일 관측 이벤트를 남긴다 — 라우팅 결정 태그를
    metadata에 담아 보낸다(F.2 표의 9개 필드 dict 그대로).
    """

    def event(  # noqa: D401 — 외부 라이브러리 시그니처 보존
        self,
        *,
        name: str,
        metadata: dict[str, object],
    ) -> Any: ...


def _build_default_langfuse_client(
    settings: Settings,
) -> _LangfuseClientProtocol:  # pragma: no cover
    """기본 langfuse 클라이언트 생성. import 실패 시 명확한 에러.

    라이브 SDK 생성 shim — 라이브 키 없이는 구성·실행 불가하므로 커버리지 제외(테스트는
    monkeypatch로 치환해 lazy build 경로만 검증한다, test_tracing.py).
    `langfuse` import는 *이 함수 안에서만* 한다(lazy). importlib 동적 로드 + cast로
    mypy --strict를 통과한다(quality_eval.py _build_default_client 패턴). 키·호스트는
    settings에서 주입한다(시크릿 하드코딩 금지 — CLAUDE.md 절대 금기).
    """
    import importlib

    try:
        langfuse_mod = importlib.import_module("langfuse")
    except ImportError as exc:
        raise RuntimeError(
            "langfuse 클라이언트가 설치되지 않았습니다. `pip install langfuse` 후 재시도."
        ) from exc
    client = langfuse_mod.Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return cast("_LangfuseClientProtocol", client)


class LangfuseTraceSink:
    """Langfuse 관측성 싱크 — `TraceSink` 충족 (03a §F.2).

    record(fields)로 langfuse_fields()가 만든 태그 dict를 Langfuse 이벤트 metadata에
    실어 전송한다. 클라이언트 주입 가능 — 기본 None이면 첫 record 시 settings로 lazy
    build. record는 *동기* 메서드다(TraceSink Protocol 시그니처) — 관측성 전송 실패가
    학생 응답 경로를 막지 않도록 호출 측(GenerationService)이 결정 경로 마지막에 부른다.
    """

    def __init__(
        self,
        *,
        client: _LangfuseClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings if settings is not None else get_settings()

    def _ensure_client(self) -> _LangfuseClientProtocol:
        """주입된 클라이언트가 없으면 settings로 lazy 생성."""
        if self._client is None:
            self._client = _build_default_langfuse_client(self._settings)
        return self._client

    def record(self, fields: dict[str, object]) -> None:
        """라우팅 결정 태그 dict를 Langfuse 이벤트로 기록한다(F.2 필드 표)."""
        self._ensure_client().event(name=_EVENT_NAME, metadata=fields)
