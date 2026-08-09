"""L4 coach 오개념 교정 시각화 shadow→on 롤아웃 HTTP 결선 단위테스트 — MISC-01(hermetic·provider
주입·라이브 LLM 0).

`test_coach_judge_shadow.py`(judge would-be shadow HTTP 결선) 구조를 답습한다 — `coach._spawn`
캡처기로 비차단 스폰을 결정론화하고, `coach._get_judge_seam_deps`(app.state DI 좌석)를
override해 `visualize_misconception`이 실제로 소비하는 L3 provider를 가짜로 교체한다
(`test_misconception_visualize.py`의 `_FakeProvider` 패턴 — `l3.pipeline.generate`가
`provider.generate(prompt, system, decision)`를 직접 호출하므로 라우터 전체를 hermetic하게 통과).

검증 항목(acceptance):
- **off(기본)**: 확정 진단이어도 `visualize_misconception` 호출 0·응답 `visualization` 항상 None
  (현행 비트동일).
- **shadow**: 응답 `visualization`은 *항상* None(비노출 — 노출 payload가 off와 비트동일)이고,
  spawn이 비차단으로 캡처된다(judge shadow 패턴 답습). 구동하면 shadow 레코드가 로깅되고,
  진단 보류(intervention None)면 spawn 자체가 0회(불필요한 LLM 호출 회피).
- **on**: 확정 진단 + 유효 L3 출력 → 응답 `visualization`에 검증된 명세가 실린다. L3 검증 실패
  (`InvalidVisualizationSpecError`)면 `visualization=None`으로 그레이스풀 폴백하되 `decision`/
  `intervention`(소크라테스 발화)은 절대 안 바뀐다. 진단 보류면 L3 미호출·None.

전부 *동기* 테스트 함수다(`TestClient`가 async 엔드포인트를 동기 구동) — 기존 coach shadow
테스트들과 동형.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.shadow import MisconceptionVisualizationShadowObservation
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_VIZ_RECORD_LOGGER = "whymath.l4.misconception.visualization_shadow.record"

_UID = uuid.uuid4()

# 완전 substring 매칭(confidence 1.0) — distribution-over-power. select_intervention이
# COUNTEREXAMPLE로 확정(임계 일관 — intervene.py와 동일).
_SUBSTR_FULL = "내 풀이는 (a+b)² = a² + b²로 전개했어"
# substring·의미 매칭 둘 다 안 잡는 중립 발화 — intervention이 None(진단 보류)이 되게.
_NEUTRAL = "이 문제 어떻게 접근하면 좋을까"

_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"model": "area"}, '
    '"caption": "(a+b)² 넓이 모델", "interactive": true}'
)
_INVALID_TEXT = "죄송합니다, 만들 수 없습니다."


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach.py 패턴)."""
    asyncio.run(reset_store())


@pytest.fixture(autouse=True)
def _restore_settings_cache() -> Iterator[None]:
    """env 토글 누수 차단 — 테스트 후 전역 Settings 캐시를 무조건 클리어."""
    yield
    get_settings.cache_clear()


def _set_viz_mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_VISUALIZATION_MODE", mode)
    get_settings.cache_clear()


def _settings_no_limits() -> Settings:
    """rate limit 0(비활성)·JWT 시크릿 채움 — 게이트는 env로 따로 켠다(judge_shadow 테스트 동형)."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """stateless /v1/coach용 — execute 호출 시 AssertionError(DB 무접근)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


class _FakeProvider:
    """가짜 LLMProvider — 정해진 텍스트 반환 + 호출 횟수 기록(`test_misconception_visualize.py`
    동형). `_get_judge_seam_deps`(app.state DI) override로 주입해 `l3.pipeline.generate`가
    이 인스턴스를 *직접* 호출하게 한다(라우터·캐시·관측은 실물 InMemoryCache/RecordingTraceSink).
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(self._text)


def _client(provider: _FakeProvider) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    # MISC-01 결선 좌석 — judge seam과 동일 DI 경로(app.state 공유 provider/cache/trace)를
    # `_get_judge_seam_deps` override로 가로채 `visualize_misconception`이 소비할 provider를 교체.
    app.dependency_overrides[coach._get_judge_seam_deps] = lambda: coach._JudgeSeamDeps(
        provider=provider, cache=InMemoryCache(), trace=RecordingTraceSink()
    )
    return TestClient(app)


class _CapturedSpawn:
    """`coach._spawn`을 대체해 코루틴을 캡처(즉시 실행 안 함) — `test_coach_judge_shadow.py` 동형."""

    def __init__(self) -> None:
        self.coros: list[Coroutine[Any, Any, None]] = []

    def __call__(self, coro: Coroutine[Any, Any, None]) -> None:
        self.coros.append(coro)

    @property
    def calls(self) -> int:
        return len(self.coros)

    def drive(self) -> None:
        for coro in self.coros:
            asyncio.run(coro)
        self.coros.clear()

    def close(self) -> None:
        for coro in self.coros:
            coro.close()
        self.coros.clear()


def _patch_spawn(monkeypatch: pytest.MonkeyPatch) -> _CapturedSpawn:
    captured = _CapturedSpawn()
    monkeypatch.setattr(coach, "_spawn", captured)
    return captured


def _viz_records(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _VIZ_RECORD_LOGGER]


# ──────────────────────────────────────────────────────────────────────────
# ① off(기본) — 확정 진단이어도 호출 0·응답 항상 None(현행 비트동일)
# ──────────────────────────────────────────────────────────────────────────
class TestOffMode:
    def test_confirmed_diagnosis_no_call_no_exposure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _FakeProvider(_VALID_JSON)
        captured = _patch_spawn(monkeypatch)
        # off는 기본값이라 env 미설정으로도 충분하지만, 명시적으로 켜 회귀를 방지한다.
        _set_viz_mode(monkeypatch, "off")
        body = (
            _client(provider)
            .post("/v1/coach", json={"student_input": _SUBSTR_FULL, "mastery_level": "초보"})
            .json()
        )
        assert body["intervention"] is not None  # 진단은 확정됐다(off가 개입 자체를 안 건드림)
        assert body["visualization"] is None  # 그런데도 시각화는 호출 0·비노출
        assert provider.calls == 0
        assert captured.calls == 0


# ──────────────────────────────────────────────────────────────────────────
# ② shadow — 응답 불변(비노출) + 비차단 스폰, 진단 보류면 스폰도 0
# ──────────────────────────────────────────────────────────────────────────
class TestShadowMode:
    def test_confirmed_diagnosis_spawns_but_stays_unexposed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = _FakeProvider(_VALID_JSON)
        captured = _patch_spawn(monkeypatch)
        _set_viz_mode(monkeypatch, "shadow")
        resp = _client(provider).post(
            "/v1/coach", json={"student_input": _SUBSTR_FULL, "mastery_level": "초보"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["intervention"] is not None
        assert body["visualization"] is None  # shadow는 노출 0(응답이 off와 비트동일)
        assert provider.calls == 0  # 응답 시점까지는 L3 미호출(비차단 — 아직 안 돎)
        assert captured.calls == 1  # 비차단 스폰 1회
        with caplog.at_level(logging.INFO, logger=_VIZ_RECORD_LOGGER):
            captured.drive()  # 응답 후 동기 구동 — 부수효과(레코드) 결정론 관측
        assert provider.calls == 1  # 구동 뒤에야 L3 호출
        records = _viz_records(caplog)
        assert len(records) == 1
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(records[0])
        assert obs.misconception_id == "distribution-over-power"
        assert obs.pattern == "counterexample"
        assert obs.success is True

    def test_generation_failure_still_records_but_never_exposes(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = _FakeProvider(_INVALID_TEXT)  # L3 검증 실패 유도
        captured = _patch_spawn(monkeypatch)
        _set_viz_mode(monkeypatch, "shadow")
        body = (
            _client(provider)
            .post("/v1/coach", json={"student_input": _SUBSTR_FULL, "mastery_level": "초보"})
            .json()
        )
        assert body["visualization"] is None
        with caplog.at_level(logging.INFO, logger=_VIZ_RECORD_LOGGER):
            captured.drive()  # 검증 실패해도 never-break — drive()가 안 터진다
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(
            _viz_records(caplog)[0]
        )
        assert obs.success is False
        assert obs.error_type == "InvalidVisualizationSpecError"

    def test_pending_diagnosis_no_spawn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _FakeProvider(_VALID_JSON)
        captured = _patch_spawn(monkeypatch)
        _set_viz_mode(monkeypatch, "shadow")
        body = _client(provider).post("/v1/coach", json={"student_input": _NEUTRAL}).json()
        assert body["intervention"] is None  # 진단 보류
        assert body["visualization"] is None
        assert captured.calls == 0  # 불필요한 스폰 회피(진단 보류)
        assert provider.calls == 0


# ──────────────────────────────────────────────────────────────────────────
# ③ on — 성공 시 노출, 실패 시 그레이스풀 폴백(소크라테스 발화 불변), 보류 시 미호출
# ──────────────────────────────────────────────────────────────────────────
class TestOnMode:
    def test_confirmed_diagnosis_exposes_visualization(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = _FakeProvider(_VALID_JSON)
        _set_viz_mode(monkeypatch, "on")
        body = (
            _client(provider)
            .post("/v1/coach", json={"student_input": _SUBSTR_FULL, "mastery_level": "초보"})
            .json()
        )
        assert body["intervention"] is not None
        assert body["visualization"] is not None
        assert body["visualization"]["type"] == "interactive_graph_2d"
        assert provider.calls == 1  # await — 응답 시점에 이미 L3 왕복 완료

    def test_generation_failure_falls_back_to_none_without_blocking_decision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = _FakeProvider(_INVALID_TEXT)
        _set_viz_mode(monkeypatch, "on")
        resp = _client(provider).post(
            "/v1/coach", json={"student_input": _SUBSTR_FULL, "mastery_level": "초보"}
        )
        assert resp.status_code == 200, resp.text  # 500 아님(가용성 우선)
        body = resp.json()
        assert body["visualization"] is None  # 그레이스풀 폴백
        assert body["intervention"] is not None  # 소크라테스 개입 발화는 절대 안 막힘
        assert body["decision"] is not None

    def test_pending_diagnosis_skips_llm_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _FakeProvider(_VALID_JSON)
        _set_viz_mode(monkeypatch, "on")
        body = _client(provider).post("/v1/coach", json={"student_input": _NEUTRAL}).json()
        assert body["intervention"] is None
        assert body["visualization"] is None
        assert provider.calls == 0  # 불필요한 LLM 호출 회피(진단 보류)
