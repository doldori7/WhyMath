"""coach 세션 엔드포인트 WH-1 하네스 shadow 결선 통합테스트 — S1-b (기본 SKIP·실 PG).

`POST /v1/coach/sessions`가 `wh1_harness_shadow_enabled`에 따라 하네스 shadow를 *비차단*으로
spawn하되 학생 응답(결정론 경로)은 *절대* 바꾸지 않는지 검증한다. `/v1/coach/sessions`는 DB에
dialogue+turn을 영속하므로 실 PG가 필요하다(`test_coach_integration` 패턴 답습·미도달 시 skip).

검증 항목:
- 플래그 OFF(기본) → shadow spawn 0회·응답 201(shadow 없이와 동일 동작·완전 되돌리기).
- 플래그 ON → shadow가 비차단 spawn 1회·응답 201 불변·(캡처 코루틴 구동 시) 레코드 관측.
- shadow 구성 실패라도 응답 201(never-break·가용성 우선·shadow는 학생 경로를 안 깬다).

**비차단 결정론**: `coach._spawn`을 monkeypatch해 코루틴을 *캡처*(즉시 실행 안 함)하고, 응답 후
동기 구동(`test_coach_judge_shadow._CapturedSpawn` 미러). **라이브 0**: 하네스가 표준 provider를
구성하지 않게 `coach.observe_wh1_harness_shadow`를 감싸 스텁 provider를 주입한다.
**게이트 토글**: `create_session`은 실 `get_settings()`(모듈 직호출)를 읽으므로 env+cache_clear.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Coroutine, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api import coach
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.harness import wh1_shadow
from whymath_backend.harness.wh1_shadow import Wh1HarnessShadowObservation
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"
_STUDENT_INPUT = "내 풀이는 (a+b)² = a² + b² 이렇게 했어"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _add_user(uid: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                UserProfile.from_schema(
                    UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID, dialogue_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    dids = [str(d) for d in dialogue_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: 자식(dialogue_turn·attempt_event·hypothesis) → 부모(dialogue) → user_profile.
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM attempt_event WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
    finally:
        await engine.dispose()


def _enable_wh1_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    """WH-1 하네스 shadow 토글 ON — env+cache_clear."""
    monkeypatch.setenv("WHYMATH_WH1_HARNESS_SHADOW_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _restore_settings_cache() -> Iterator[None]:
    """env 토글 누수 차단 — 테스트 후 전역 Settings 캐시를 무조건 클리어."""
    yield
    get_settings.cache_clear()


class _CapturedSpawn:
    """`coach._spawn` 대체 — 코루틴을 캡처(즉시 실행 안 함)해 비차단을 결정론으로 만든다."""

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


class _StubProvider:
    """스크립트된 JSON만 돌려주는 L3 provider 대역 — 하네스가 라이브 LLM을 안 부르게(네트워크 0)."""

    async def generate(self, prompt: str, system: str, decision: object, **_kw: object) -> str:
        return '{"kind": "end_turn", "action_type": "격려"}'


def _patch_shadow_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """observe를 감싸 표준 provider 구성 대신 스텁을 강제 주입(hermetic·라이브 0)."""
    original = wh1_shadow.observe_wh1_harness_shadow

    async def _wrapped(**kwargs: Any) -> None:
        kwargs.setdefault("provider", _StubProvider())
        await original(**kwargs)

    monkeypatch.setattr(coach, "observe_wh1_harness_shadow", _wrapped)


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def _auth(uid: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(uid, settings=_settings())}"}


def _decision_fields(body: dict[str, Any]) -> dict[str, Any]:
    """학생-대면 결정론 필드만(매 요청 새로 생성되는 id 제외)."""
    return {
        k: body.get(k)
        for k in ("decision", "misconceptions", "intervention", "lthc", "solution_coaching")
    }


# ──────────────────────────────────────────────────────────────────────────
# ① 플래그 OFF(기본) → spawn 0회·응답 201
# ──────────────────────────────────────────────────────────────────────────
def test_flag_off_no_spawn_response_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")
    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        captured = _CapturedSpawn()
        monkeypatch.setattr(coach, "_spawn", captured)
        # 플래그 미설정(기본 OFF).
        get_settings.cache_clear()
        with _client() as client:
            resp = client.post(
                "/v1/coach/sessions", headers=_auth(uid), json={"student_input": _STUDENT_INPUT}
            )
            assert resp.status_code == 201, resp.text
            dialogue_ids.append(uuid.UUID(resp.json()["dialogue_id"]))
        assert captured.calls == 0  # OFF → shadow spawn 0(완전 되돌리기)
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


# ──────────────────────────────────────────────────────────────────────────
# ② 플래그 ON → spawn 1회·응답 불변·레코드 관측
# ──────────────────────────────────────────────────────────────────────────
def test_flag_on_spawns_records_response_unchanged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")
    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        captured = _CapturedSpawn()
        monkeypatch.setattr(coach, "_spawn", captured)
        _patch_shadow_provider(monkeypatch)

        # OFF 기준 응답(결정론 필드) 확보.
        get_settings.cache_clear()
        with _client() as client:
            off = client.post(
                "/v1/coach/sessions", headers=_auth(uid), json={"student_input": _STUDENT_INPUT}
            )
            assert off.status_code == 201, off.text
            dialogue_ids.append(uuid.UUID(off.json()["dialogue_id"]))
        assert captured.calls == 0  # OFF 경로에선 spawn 0

        # ON 응답 — 학생-대면 필드는 OFF와 동일해야(shadow는 노출 불변).
        _enable_wh1_shadow(monkeypatch)
        with _client() as client:
            on = client.post(
                "/v1/coach/sessions", headers=_auth(uid), json={"student_input": _STUDENT_INPUT}
            )
            assert on.status_code == 201, on.text
            dialogue_ids.append(uuid.UUID(on.json()["dialogue_id"]))
        assert captured.calls == 1  # ON → 비차단 spawn 1회(응답은 이미 반환됨)
        assert _decision_fields(off.json()) == _decision_fields(on.json())  # 노출 비트동일

        # 응답 후 캡처 코루틴을 구동 — 부수효과(레코드) 결정론 관측.
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            captured.drive()
        records = [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]
        assert len(records) == 1
        obs = Wh1HarnessShadowObservation.model_validate_json(records[0])
        assert obs.status == "ended"
        assert obs.action_type == "격려"
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


# ──────────────────────────────────────────────────────────────────────────
# ③ never-break — shadow 구성 실패라도 학생 응답 201(가용성 우선)
# ──────────────────────────────────────────────────────────────────────────
def test_shadow_failure_does_not_break_response(monkeypatch: pytest.MonkeyPatch) -> None:
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")
    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        captured = _CapturedSpawn()
        monkeypatch.setattr(coach, "_spawn", captured)

        async def _boom(**_kwargs: object) -> None:
            raise RuntimeError("shadow 구성 실패(never-break 테스트)")

        monkeypatch.setattr(coach, "observe_wh1_harness_shadow", _boom)
        _enable_wh1_shadow(monkeypatch)
        with _client() as client:
            resp = client.post(
                "/v1/coach/sessions", headers=_auth(uid), json={"student_input": _STUDENT_INPUT}
            )
            # shadow가 예외를 낼 코루틴을 spawn해도 응답은 이미 반환됨(비차단·학생 경로 무관).
            assert resp.status_code == 201, resp.text
            dialogue_ids.append(uuid.UUID(resp.json()["dialogue_id"]))
        assert captured.calls == 1
        captured.close()  # 캡처 코루틴 정리(구동 안 함 — 응답 무관 확인이 목적)
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))
