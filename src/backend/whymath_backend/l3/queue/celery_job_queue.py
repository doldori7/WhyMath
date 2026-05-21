"""CeleryJobQueue — interfaces.AsyncJobQueue 구현 (M1.2-live S4).

QUALITY(27b)로 라우팅된 요청을 Celery 큐로 보내고(enqueue→job_id), job_id로 결과를
폴링한다(result). broker·result backend는 Redis(config.effective_celery_*)이며 워커
동시성은 1(GPU 단일 점유, 03a §D.3·§A.1)이다.

설계 정본: `docs/architecture/03a_l3_router_design.md` §D.3(QUALITY 비동기 큐 경로)·
§H 후속 6(큐 SLA). 시임·지연·주입·never-break 패턴은 providers/ollama.py(`_OllamaClient`)·
cache/redis_cache.py(`_RedisClient`)·trace/langfuse_sink.py(`_LangfuseClient`)를 미러링한다.

────────────────────────────────────────────────────────────────────────────
가용성 우선 — 큐/백엔드 장애가 학생 경로를 500으로 깨뜨리지 않는다 (#1 ≫ #6)
────────────────────────────────────────────────────────────────────────────
  - `enqueue` 실패(broker 다운)는 호출자(파이프라인)가 QualityQueueUnavailableError로
    변환해 API가 503을 내게 한다 — 여기서는 *예외를 그대로 전파*한다(파이프라인이 의미
    있는 도메인 예외로 감싸기 때문). 단, 디스패치 자체의 raw 예외는 파이프라인 경계에서
    흡수된다.
  - `result` 조회 실패(result backend 다운·미설정)는 *흡수*하고 JobStatus(state=...,
    error=...)로 보고한다 — 폴링이 500 스택트레이스를 내지 않는다(관측성 싱크가
    오류를 삼킨 것과 같은 방침). 결과 텍스트는 *검증 전 원시 출력*이다(CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.queue.tasks import QUALITY_TASK_NAME


# ──────────────────────────────────────────────────────────────────────────
# 폴링 응답 값 객체 (/v1/jobs/{job_id} 표면) — ollama.OllamaStatus와 같은 결의 DTO.
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class JobStatus:
    """비동기 작업 폴링 결과 — 상태 + (완료 시) 텍스트 / (실패 시) 사유.

    `state`는 정규화된 4값 중 하나다:
      - "pending" — 대기/실행 중(아직 결과 없음).
      - "success" — 완료. `text`에 *검증 전 원시 출력*(CLAUDE.md 경계 메모).
      - "failure" — 워커에서 실패. `error`에 사유(스택트레이스 아님).
      - "unknown" — result backend 미도달·미설정 등으로 상태 판정 불가(비크래시).

    `text`는 success일 때만 채워지고, `error`는 failure/unknown일 때 채워진다.
    """

    job_id: str
    state: str
    text: str | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        """결과가 확정됐는가(success 또는 failure). pending/unknown은 미확정."""
        return self.state in ("success", "failure")


# Celery AsyncResult.state → JobStatus.state 정규화 표. Celery 상태 문자열(03a 무관,
# celery 표준): PENDING/STARTED/RETRY/RECEIVED는 '진행 중', SUCCESS는 완료, FAILURE/
# REVOKED는 실패. 표에 없는 상태는 보수적으로 'pending'(미확정)으로 본다.
_CELERY_STATE_MAP: dict[str, str] = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "pending",
    "RETRY": "pending",
    "SUCCESS": "success",
    "FAILURE": "failure",
    "REVOKED": "failure",
}


# ──────────────────────────────────────────────────────────────────────────
# Celery 추상화 (테스트 주입용) — ollama/redis/langfuse 시임 패턴 미러링.
# 우리가 *실제로 쓰는* 것만 좁게 선언한다: 디스패치(send_task)와 결과 조회(AsyncResult).
# 단위테스트는 가짜 app을 주입해 broker·워커 없이 검증한다(CI hermetic).
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _CeleryResult(Protocol):
    """celery.result.AsyncResult의 최소 인터페이스 (구조적 타이핑).

    우리는 상태(state)와 결과(result)만 읽는다. `result`는 success면 반환값(여기선
    생성 텍스트 str), failure면 예외 객체일 수 있어 `Any`로 두고 방어적으로 정규화한다.
    """

    @property
    def id(self) -> str:
        """작업 ID."""
        ...

    @property
    def state(self) -> str:
        """celery 상태 문자열(PENDING/STARTED/SUCCESS/FAILURE 등)."""
        ...

    @property
    def result(self) -> Any:
        """성공 시 반환값, 실패 시 예외(또는 None). 상태에 따라 의미가 다름."""
        ...


@runtime_checkable
class _CeleryApp(Protocol):
    """celery.Celery의 최소 인터페이스 (구조적 타이핑).

    `celery.Celery`의 부분집합 — 우리는 (a) 이름으로 태스크 디스패치(send_task)와
    (b) job_id로 결과 핸들 조회(AsyncResult)만 한다. 반환 타입은 celery 버전별로
    풍부한 객체라 `Any`/좁은 `_CeleryResult`로 두고 방어적으로 다룬다.
    """

    def send_task(self, name: str, args: Any = ..., kwargs: Any = ...) -> Any:
        """태스크를 이름으로 디스패치하고 결과 핸들을 반환(.id가 job_id)."""
        ...

    def AsyncResult(self, task_id: str) -> Any:  # noqa: N802 — celery API 이름 보존
        """job_id로 결과 핸들 조회(폴링용). celery 메서드명을 그대로 따른다."""
        ...


def _build_default_app(settings: Settings) -> _CeleryApp:
    """기본 Celery 앱 생성 (지연 import — celery_app.build_celery_app 위임).

    `celery` 라이브러리·broker가 없는 환경(CI 단위테스트)에서도 모듈 import가 깨지지
    않도록 *호출 시점에만* 앱을 만든다(다른 시임들의 _build_default_client 패턴). 앱
    생성은 broker에 연결하지 않으므로(첫 디스패치 때 연결) 라이브 Redis 없이도 안전하다.
    """
    from whymath_backend.l3.queue.celery_app import build_celery_app

    # cast 사유: build_celery_app은 정밀 Celery 타입을 돌려주지만(celery는 py.typed
    # 미제공이라 사실상 Any), 우리의 좁은 구조적 시임 `_CeleryApp`으로 좁힌다 —
    # ollama/redis/langfuse가 각자 시임으로 좁힌 것과 동일한 방침(타입 무시 X).
    return cast(_CeleryApp, build_celery_app(settings))


def _coerce_text(value: Any) -> str | None:
    """AsyncResult.result(성공값)를 str|None으로 방어적 정규화.

    태스크 반환은 생성 텍스트(str)다. JSON 직렬화 왕복에서도 str로 보존되지만, 비정상
    타입이 오면(스키마 깨짐) None으로 본다(폴링이 깨지지 않게 — 안전 처리).
    """
    if isinstance(value, str):
        return value
    return None


class CeleryJobQueue:
    """Celery 기반 비동기 작업 큐 — interfaces.AsyncJobQueue 충족.

    파이프라인은 `enqueue(payload)`만 호출하고(03a §D.3) job_id를 받는다. 폴링은
    `result(job_id)`로 한다(AsyncJobQueue Protocol에는 없는 추가 메서드 — ollama의
    check_status처럼 *기능 탐지*로 쓴다). 워커 동시성 1은 celery_app 설정·기동 명령에서
    강제한다(celery_app.py 모듈 docstring).

    app은 지연 생성(lazy)·주입 가능(injectable)하다 — 테스트는 가짜 app을 `app=`으로
    넣고, 프로덕션은 첫 사용 시 기본 Celery 앱을 생성한다(앱 구성만으로는 broker가
    필요 없도록 — RedisCache·LangfuseSink와 동일한 지연 연결).
    """

    def __init__(
        self,
        *,
        app: _CeleryApp | None = None,
        settings: Settings | None = None,
    ) -> None:
        # 주입된 app이 있으면 그것을 쓰고, 없으면 첫 사용 시 기본 생성(지연).
        self._app = app
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_app(self) -> _CeleryApp:
        """Celery 앱 지연 해석 — 주입 우선, 없으면 기본 앱 생성."""
        if self._app is None:
            self._app = _build_default_app(self._resolved_settings)
        return self._app

    async def enqueue(self, payload: dict[str, object]) -> str:
        """QUALITY 작업을 큐에 넣고 job_id를 반환 (AsyncJobQueue 구현).

        payload는 JSON-safe dict여야 한다(tasks.py 스키마: prompt·system·decision).
        디스패치는 태스크 *이름*(QUALITY_TASK_NAME)으로 한다 — 보내는 앱에 태스크가
        등록돼 있지 않아도 워커(include로 tasks 로드)가 이름으로 받는다.

        broker 다운 시 send_task가 예외를 던지면 *그대로 전파*한다 — 호출 파이프라인이
        이를 QualityQueueUnavailableError로 감싸 API가 503을 내게 한다(가용성 우선,
        모듈 docstring). 여기서 흡수하면 job_id 계약(항상 str 반환)을 어기게 된다.

        Celery 디스패치는 동기 호출이지만 빠르다(broker에 메시지 1건 publish). async
        시그니처(Protocol 계약)를 지키되 내부는 동기 send_task를 그대로 호출한다 —
        파이프라인의 await 흐름과 정합한다.
        """
        # send_task는 동기다(브로커에 publish 후 즉시 반환). args에 payload 1개 전달.
        async_result = self._get_app().send_task(QUALITY_TASK_NAME, args=[payload])
        # 반환 핸들의 .id가 job_id. celery는 항상 .id를 채운다(클라이언트가 UUID 생성).
        job_id = async_result.id
        return str(job_id)

    def result(self, job_id: str) -> JobStatus:
        """job_id로 작업 상태·결과를 조회 (폴링용 — Protocol 외 추가 메서드).

        AsyncJobQueue Protocol에는 없는 메서드다(ollama의 check_status처럼 기능 탐지로
        호출처가 getattr로 확인). result backend 도달 실패·미설정 등은 *흡수*하고
        state='unknown'으로 보고한다 — 폴링이 500을 내지 않는다(가용성 우선).

        반환 텍스트(success)는 *검증 전 원시 출력*이다(모듈/클래스 docstring 경계 메모).
        """
        try:
            handle = self._get_app().AsyncResult(job_id)
            celery_state = handle.state
        except Exception as exc:  # noqa: BLE001 — backend 미도달을 비크래시로 흡수
            # result backend 다운·미설정 → 상태 판정 불가. 폴링은 깨지지 않는다.
            return JobStatus(
                job_id=job_id,
                state="unknown",
                error=f"{type(exc).__name__}: {exc}",
            )

        state = _CELERY_STATE_MAP.get(str(celery_state), "pending")

        if state == "success":
            # 성공값(결과 텍스트) 추출 — 조회 자체도 backend를 탈 수 있어 방어.
            try:
                raw = handle.result
            except Exception as exc:  # noqa: BLE001 — 결과 역직렬화/도달 실패 흡수
                return JobStatus(
                    job_id=job_id,
                    state="unknown",
                    error=f"{type(exc).__name__}: {exc}",
                )
            return JobStatus(job_id=job_id, state="success", text=_coerce_text(raw))

        if state == "failure":
            # 실패 사유 — celery는 result에 예외 객체를 담는다. 스택트레이스 대신
            # 짧은 사유 문자열만 노출한다(500 노출 금지, 학생 경로 보호).
            error_text: str | None
            try:
                raw_err = handle.result
                error_text = str(raw_err) if raw_err is not None else None
            except Exception:  # noqa: BLE001 — 실패 메타 역직렬화 실패도 흡수
                error_text = None
            return JobStatus(job_id=job_id, state="failure", error=error_text)

        # pending/진행 중 — 아직 결과 없음.
        return JobStatus(job_id=job_id, state=state)
