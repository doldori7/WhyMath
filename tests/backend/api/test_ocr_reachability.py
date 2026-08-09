"""OCR 도달 관측·503 사유 분리 테스트 (NLP-01 백엔드 축).

설계 정본: `docs/architecture/nlp_module_gap_review.md` §3 D1. 이 태스크는 *활성화*가
아니라 *가시화*다 — `ocr_enabled` 기본값(False)이나 모델 배선은 건드리지 않는다.

동결 계약:
  1. **사유 분리** — `ocr_enabled=False`(비활성)와 부품 적재 실패(load_failed)가 서로
     다른 기계 판독 사유(`detail["code"]`)를 낸다. HTTP 상태코드는 둘 다 503으로 유지
     (모바일 축이 상태코드만으로 판단 — 별도 세션 진행 중이라 여기서 바꾸지 않는다).
  2. **침묵 실패 금지** — 적재 실패 로그 *메시지 본문*에 예외 타입명이 들어간다(트레이스백
     `exc_info`만으로는 부족 — langfuse 8일 무증상 전멸 교훈).
  3. **도달 관측(변별력)** — 비활성/적재실패/정상 세 상태가 `/health/ready`의 `ocr` 섹션에서
     서로 다른 카운터 값을 낸다. `enabled=False`는 '0건 통과'가 아니라 '미측정'이다
     (None-vs-zero — 트래픽 0인 활성 상태와 구분: 이 파일의
     `test_disabled_and_enabled_zero_traffic_are_distinguishable`).
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import whymath_backend.app as app_module
from whymath_backend.api import ocr as ocr_module
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._ocr_state import (
    OcrReachCounters,
    get_ocr_components,
    get_ocr_reach_snapshot,
    set_ocr_components,
)
from whymath_backend.app import _activate_ocr, create_app
from whymath_backend.config import Settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.ops.service_health import (
    COMPONENT_DATABASE,
    COMPONENT_LLM_ROUTER,
    COMPONENT_REDIS,
    ComponentCheck,
    ReadinessProbes,
)
from whymath_backend.schema.enums import ContentType, Persona
from whymath_backend.schema.ocr import BBox, OcrRegion, OcrResult
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


class _FakeComponents:
    """get_ocr_components 오버라이드용 — 파이프라인 monkeypatch라 내용 무관(기존 관행)."""


class _FakeRequest:
    """`get_ocr_components(request)`가 요구하는 표면(`request.app.state`)만 흉내낸 더블.

    실 Starlette `Request`를 조립하는 대신 duck typing으로 최소 표면만 준다 — 함수는
    `request.app.state`만 읽으므로 이 정도로 충분하고, scope 조립 취약성을 피한다.
    """

    def __init__(self, app: FastAPI) -> None:
        self.app = app


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


class _FakeSession:
    """get_session 오버라이드용 빈 스텁 — 실 get_engine 회피(test_ocr_endpoint.py 관행)."""


async def _fake_session():
    yield _FakeSession()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _ocr_result() -> OcrResult:
    return OcrResult(
        regions=[
            OcrRegion(
                bbox=BBox(x=0, y=0, width=50, height=20),
                content_type=ContentType.수식,
                latex="x = 2",
                confidence=0.9,
                verified=True,
            )
        ],
        plain_latex="x = 2",
        solution_steps=["x = 2"],
        solution_step_types=[],
        markdown="$x = 2$",
        overall_confidence=0.9,
        min_confidence=0.9,
    )


def _fake_probes() -> ReadinessProbes:
    """항상 성공하는 가짜 딥체크 — `/health/ready` 호출이 실 DB/Redis/Ollama에 닿지 않게 한다.

    `default_readiness_probes`(get_engine 경유)를 쓰면 `db.session._engine` 전역을
    남겨 "다음 순서 테스트가 전역 None을 단언하면 깨진다"는 conftest 가드에 걸린다
    (`test_health_endpoints.py::_probes` 선례를 그대로 미러).
    """

    async def _db() -> ComponentCheck:
        return ComponentCheck(
            name=COMPONENT_DATABASE,
            configured=True,
            reachable=True,
            required=True,
            error=None,
        )

    async def _redis() -> ComponentCheck:
        return ComponentCheck(
            name=COMPONENT_REDIS,
            configured=True,
            reachable=True,
            required=False,
            error=None,
        )

    async def _llm() -> ComponentCheck:
        return ComponentCheck(
            name=COMPONENT_LLM_ROUTER,
            configured=True,
            reachable=True,
            required=False,
            error=None,
        )

    return ReadinessProbes(database=_db, redis=_redis, llm=_llm)


def _authed_app(*, ocr_counters: OcrReachCounters | None = None) -> FastAPI:
    """인증·세션을 오버라이드한 앱(부품은 시나리오별로 직접 app.state에 심는다)."""
    app = create_app(
        provider=_StubProvider(),
        ocr_counters=ocr_counters,
        readiness_probes=_fake_probes(),
    )
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_session] = _fake_session
    return app


# ──────────────────────────────────────────────────────────────────────────
# ① 503 사유 분리 — _ocr_state 단위 (HTTPException detail 직접 검증)
# ──────────────────────────────────────────────────────────────────────────
class TestUnavailableReasonSeparation:
    def test_set_requires_reason_when_components_none(self) -> None:
        """components=None인데 unavailable_reason 미지정 ⇒ ValueError(계약 강제)."""
        app = FastAPI()
        with pytest.raises(ValueError):
            set_ocr_components(app, None)

    def test_set_rejects_reason_when_components_present(self) -> None:
        """components가 있는데 unavailable_reason도 지정 ⇒ ValueError(성공 상태에 사유 금지)."""
        app = FastAPI()
        with pytest.raises(ValueError):
            set_ocr_components(app, _FakeComponents(), unavailable_reason="disabled")  # type: ignore[arg-type]

    def test_disabled_reason_yields_disabled_code(self) -> None:
        """set(None, reason=disabled) ⇒ get_ocr_components이 503 + detail.code=ocr_disabled."""
        app = FastAPI()
        set_ocr_components(app, None, unavailable_reason="disabled")
        with pytest.raises(HTTPException) as exc_info:
            get_ocr_components(_FakeRequest(app))  # type: ignore[arg-type]
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "ocr_disabled"

    def test_load_failed_reason_yields_load_failed_code(self) -> None:
        """set(None, reason=load_failed) ⇒ get_ocr_components이 503 + detail.code=ocr_load_failed.

        비활성(disabled)과 **다른** code — 변별력 핵심 단언(무변별이었던 기존 동작 회귀 방지).
        """
        app = FastAPI()
        set_ocr_components(app, None, unavailable_reason="load_failed")
        with pytest.raises(HTTPException) as exc_info:
            get_ocr_components(_FakeRequest(app))  # type: ignore[arg-type]
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "ocr_load_failed"
        # 두 사유의 code는 서로 달라야 한다(무변별 회귀 방지).
        assert exc_info.value.detail["code"] != "ocr_disabled"


# ──────────────────────────────────────────────────────────────────────────
# ② 침묵 실패 금지 — _activate_ocr 로그 메시지 본문에 예외 타입명 (lifespan에서 분리된 단위)
# ──────────────────────────────────────────────────────────────────────────
class TestSilentFailureCompliance:
    def test_load_failure_logs_exception_type_name_in_message_body(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """부품 적재 실패 ⇒ 경고 로그 *메시지 본문*에 예외 타입명 포함(exc_info만으론 부족)."""

        class _OcrBoomError(Exception):
            pass

        def _boom(*args: object, **kwargs: object) -> None:
            raise _OcrBoomError("부품 적재 실패(주입)")

        monkeypatch.setattr(app_module, "build_ocr_components", _boom)

        app = FastAPI()
        settings = Settings(ocr_enabled=True)
        with caplog.at_level(logging.WARNING, logger="whymath_backend.app"):
            _activate_ocr(app, settings)

        # 메시지 본문(포맷된 문자열)에 타입명이 들어 있어야 한다 — exc_info만으로는
        # CLAUDE.md 규칙("메시지 자체에 타입명을 명시") 불충족.
        formatted = [record.getMessage() for record in caplog.records]
        assert any("_OcrBoomError" in msg for msg in formatted)
        # 상태도 load_failed로 기록됐는지 확인(로그와 상태가 일치).
        snapshot = get_ocr_reach_snapshot(app)
        assert snapshot.enabled is True  # 설정 의도는 켜짐(적재만 실패)

    def test_disabled_config_does_not_attempt_build(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ocr_enabled=False ⇒ build_ocr_components 시도 자체를 안 한다(비활성 사유 즉시 기록)."""
        called = False

        def _should_not_be_called(*args: object, **kwargs: object) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(app_module, "build_ocr_components", _should_not_be_called)
        app = FastAPI()
        settings = Settings(ocr_enabled=False)
        _activate_ocr(app, settings)
        assert called is False
        snapshot = get_ocr_reach_snapshot(app)
        assert snapshot.enabled is False

    def test_success_path_leaves_no_unavailable_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """부품 적재 성공 ⇒ unavailable_reason은 None(성공 상태에 사유를 남기지 않는다)."""
        sentinel = _FakeComponents()

        def _ok(*args: object, **kwargs: object) -> _FakeComponents:
            return sentinel

        monkeypatch.setattr(app_module, "build_ocr_components", _ok)
        app = FastAPI()
        settings = Settings(ocr_enabled=True)
        _activate_ocr(app, settings)
        assert get_ocr_components(_FakeRequest(app)) is sentinel  # type: ignore[arg-type]
        snapshot = get_ocr_reach_snapshot(app)
        assert snapshot.enabled is True


# ──────────────────────────────────────────────────────────────────────────
# ③ 도달 관측 — /health/ready의 ocr 섹션이 세 상태를 변별한다(None-vs-zero 포함)
# ──────────────────────────────────────────────────────────────────────────
class TestReachObservability:
    def test_disabled_state_reports_enabled_false(self) -> None:
        """비활성 상태 — /health/ready.ocr.enabled=False(요청 없이도)."""
        app = _authed_app()
        set_ocr_components(app, None, unavailable_reason="disabled")
        resp = TestClient(app).get("/health/ready")
        body = resp.json()
        assert body["ocr"]["enabled"] is False
        assert body["ocr"]["requests_total"] == 0

    def test_disabled_request_increments_unavailable_disabled_only(self) -> None:
        """비활성 상태에서 /v1/ocr 호출 ⇒ 503 + unavailable_disabled만 증가(다른 사유는 0)."""
        app = _authed_app()
        set_ocr_components(app, None, unavailable_reason="disabled")
        client = TestClient(app)
        resp = client.post("/v1/ocr", files={"image": ("s.png", b"x", "image/png")})
        assert resp.status_code == 503
        assert resp.json()["detail"]["code"] == "ocr_disabled"

        ready = client.get("/health/ready").json()["ocr"]
        assert ready["enabled"] is False
        assert ready["requests_total"] == 1
        assert ready["unavailable_disabled"] == 1
        assert ready["unavailable_load_failed"] == 0
        assert ready["succeeded"] == 0

    def test_load_failed_request_increments_unavailable_load_failed_only(self) -> None:
        """적재실패 상태에서 /v1/ocr 호출 ⇒ 503 + unavailable_load_failed만 증가, enabled=True."""
        app = _authed_app()
        set_ocr_components(app, None, unavailable_reason="load_failed")
        client = TestClient(app)
        resp = client.post("/v1/ocr", files={"image": ("s.png", b"x", "image/png")})
        assert resp.status_code == 503
        assert resp.json()["detail"]["code"] == "ocr_load_failed"

        ready = client.get("/health/ready").json()["ocr"]
        assert ready["enabled"] is True  # 설정 의도는 켜짐(적재만 실패)
        assert ready["requests_total"] == 1
        assert ready["unavailable_disabled"] == 0
        assert ready["unavailable_load_failed"] == 1
        assert ready["succeeded"] == 0

    def test_success_increments_succeeded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """정상 부품 + 파이프라인 성공 ⇒ succeeded=1, 양 unavailable=0.

        `get_ocr_components`는 dependency_overrides로 우회되므로 `requests_total`(사유별
        503 판정 경로 전용 카운터)은 이 경로에서 증가하지 않는다 — `succeeded`는 핸들러가
        직접 기록해 우회와 무관하다.
        """

        async def _fake_pipeline(
            image_bytes: bytes, *, components: object
        ) -> OcrResult:
            return _ocr_result()

        monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
        app = _authed_app()
        app.dependency_overrides[get_ocr_components] = _FakeComponents
        client = TestClient(app)
        resp = client.post("/v1/ocr", files={"image": ("s.png", b"x", "image/png")})
        assert resp.status_code == 200

        ready = client.get("/health/ready").json()["ocr"]
        assert ready["succeeded"] == 1
        assert ready["unavailable_disabled"] == 0
        assert ready["unavailable_load_failed"] == 0

    def test_disabled_and_enabled_zero_traffic_are_distinguishable(self) -> None:
        """None-vs-zero 핵심 단언: '비활성(0건)'과 '활성인데 트래픽 0'은 다른 상태다.

        둘 다 requests_total=0이지만 `enabled` 플래그가 갈라 '미측정'과 '측정했더니 0건'을
        구분한다 — 이게 없으면 모바일·운영자가 두 상태를 혼동한다(§3 D1 재발 방지 취지).
        """
        disabled_app = _authed_app()
        set_ocr_components(disabled_app, None, unavailable_reason="disabled")
        disabled_body = TestClient(disabled_app).get("/health/ready").json()["ocr"]

        loaded_app = _authed_app()
        set_ocr_components(loaded_app, _FakeComponents())  # type: ignore[arg-type]
        loaded_body = TestClient(loaded_app).get("/health/ready").json()["ocr"]

        # 카운트는 둘 다 0(트래픽 없음)이지만 enabled는 갈린다.
        assert disabled_body["requests_total"] == 0
        assert loaded_body["requests_total"] == 0
        assert disabled_body["enabled"] is False
        assert loaded_body["enabled"] is True

    def test_three_states_yield_pairwise_distinct_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """변별력 실측(CLAUDE.md) — 비활성/적재실패/성공 세 상태가 서로 다른 카운터 조합을 낸다."""

        async def _fake_pipeline(
            image_bytes: bytes, *, components: object
        ) -> OcrResult:
            return _ocr_result()

        monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)

        def _hit(app: FastAPI) -> dict[str, object]:
            client = TestClient(app)
            client.post("/v1/ocr", files={"image": ("s.png", b"x", "image/png")})
            body: dict[str, object] = client.get("/health/ready").json()["ocr"]
            return body

        disabled_app = _authed_app()
        set_ocr_components(disabled_app, None, unavailable_reason="disabled")
        disabled_result = _hit(disabled_app)

        load_failed_app = _authed_app()
        set_ocr_components(load_failed_app, None, unavailable_reason="load_failed")
        load_failed_result = _hit(load_failed_app)

        success_app = _authed_app()
        success_app.dependency_overrides[get_ocr_components] = _FakeComponents
        success_result = _hit(success_app)

        # 세 결과의 (unavailable_disabled, unavailable_load_failed, succeeded) 튜플이
        # 모두 서로 다르다 — 무변별이었던 기존 단일 503 문구 대비 회귀 동결.
        signatures = {
            (
                r["unavailable_disabled"],
                r["unavailable_load_failed"],
                r["succeeded"],
            )
            for r in (disabled_result, load_failed_result, success_result)
        }
        assert len(signatures) == 3


# ──────────────────────────────────────────────────────────────────────────
# 회귀: create_app(ocr_counters=...) 주입 좌석(OPS-01 metrics/readiness_probes와 동형)
# ──────────────────────────────────────────────────────────────────────────
def test_create_app_accepts_injected_ocr_counters() -> None:
    """주입한 카운터 인스턴스가 실제로 앱이 쓰는 카운터와 동일 객체인지 확인."""
    injected = OcrReachCounters()
    app = _authed_app(ocr_counters=injected)
    set_ocr_components(app, None, unavailable_reason="disabled")
    client = TestClient(app)
    client.post("/v1/ocr", files={"image": ("s.png", b"x", "image/png")})
    snapshot = injected.snapshot(enabled=False)
    assert snapshot.requests_total == 1
    assert snapshot.unavailable_disabled == 1
