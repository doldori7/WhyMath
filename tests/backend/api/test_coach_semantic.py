"""L4 coach 오개념 *의미 매칭 결합* HTTP 결선 단위테스트 — slice 106 (hermetic·매처 주입).

게이트(`misconception_semantic_enabled`)·결합 랭킹·to_thread 경유·graceful 폴백·3 엔드포인트
일관성·잠긴 `_build_response_payload(body)` 불변을 라이브 모델 없이 검증한다.

**게이트 토글**: coach `_compute_matches`는 *실* `get_settings()`(Depends 아님·모듈 직호출)를
읽으므로, dependency_overrides가 아니라 `monkeypatch.setenv` + `get_settings.cache_clear()`로
켠다(기존 `test_step_shadow`·`TestServerTheta` 게이트 토글 패턴 답습).

**매처 주입**: 의미 매처의 *내부 랭킹·임베딩*은 `test_misconception_semantic.py`가 검증하므로,
여기서는 coach *결합 배선*만 본다 — `set_semantic_matcher`로 *결정론 스텁*(고정 의미 매치
반환)을 박아 Fake provider의 어휘 해시 quirk와 분리한다. 매 테스트 끝에 `reset_semantic_matcher`.

전부 *동기* 테스트 함수다 — `TestClient`가 async 엔드포인트(`_compute_matches`의
`asyncio.to_thread` 포함)를 동기 구동하므로 `async def test`가 불필요하고, 플랜 검증 커맨드
(rootdir=repo root·asyncio_mode 미로딩)에서도 skip되지 않는다(기존 coach sync 테스트와 동형).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._misconception_state import (
    reset_semantic_matcher,
    set_semantic_matcher,
)
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import MisconceptionMatch
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()

# 완전 substring 매칭(confidence 1.0·signals 모두 충족) — distribution-over-power.
_SUBSTR_FULL = "내 풀이는 (a+b)² = a² + b²로 전개했어"
# substring이 *전혀* 안 잡는 중립 발화 — 결합 시 semantic-only만 노출되게.
_NEUTRAL = "이 문제 어떻게 접근하면 좋을까"
# 스텁이 의미 매치로 돌려줄 distinct id(substring과 안 겹치게 division-by-zero 사용).
_SEMANTIC_ID = "division-by-zero"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach.py 패턴)."""
    asyncio.run(reset_store())


@pytest.fixture(autouse=True)
def _reset_matcher_singleton() -> Iterator[None]:
    """매 테스트 전후 의미 매처 싱글톤 격리 — 주입 누수 차단."""
    reset_semantic_matcher()
    yield
    reset_semantic_matcher()


def _enable_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """게이트 ON — env+cache_clear(실 get_settings를 읽는 _compute_matches용). 호출자가 finally로
    `get_settings.cache_clear()`를 다시 부르도록 monkeypatch.setenv가 테스트 종료 시 env를 되돌리고
    여기서 한 번 더 명시 클리어를 보장한다(test_step_shadow 패턴)."""
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_SEMANTIC_ENABLED", "true")
    get_settings.cache_clear()


def _settings_no_limits() -> Settings:
    """rate limit 0(비활성)·JWT 시크릿 채움 — 게이트는 env로 따로 켠다(이 Settings는 한도용)."""
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


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        # get_current_theta가 .scalars().first()로 최신 θ를 읽음 — 빈 rows면 None(서버 θ 없음).
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _CapturingSession:
    """/v1/coach/sessions·turns용 — add/commit/refresh/get/execute 캡처(test_coach.py 패턴)."""

    def __init__(self, preload: dict[Any, Any] | None = None) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self._preload = preload or {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: Any) -> None:
        return None

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))

    async def execute(self, stmt: Any) -> _Result:
        return _Result([])


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _session_client(
    preload: dict[Any, Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits
    captured = _CapturingSession(preload=preload)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


# ──────────────────────────────────────────────────────────────────────────
# 결정론 매처 스텁 — coach 결합 배선만 격리 검증(매처 내부는 semantic 테스트가 검증)
# ──────────────────────────────────────────────────────────────────────────
class _StubMatcher:
    """고정 의미 매치(distinct id)를 돌려주는 결정론 매처 — 호출 스레드·횟수 기록.

    `.match`는 입력과 무관히 `_SEMANTIC_ID` 1건을 cos=0.95로 반환한다(coach 결합이 이 결과를
    어떻게 배치하는지만 검증). Fake provider의 어휘 해시 quirk(토큰 경계·해시 충돌)와 분리.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.call_threads: list[str] = []

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]:
        self.calls += 1
        self.call_threads.append(threading.current_thread().name)
        return [
            MisconceptionMatch(
                misconception=CATALOG_BY_ID[_SEMANTIC_ID],
                confidence=0.95,
                semantic_similarity=0.95,
            )
        ]


class _RaisingMatcher:
    """match가 항상 raise — graceful 폴백(substring·200) 검증용."""

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]:
        raise RuntimeError("의미 매칭 강제 실패(폴백 테스트)")


# ──────────────────────────────────────────────────────────────────────────
# ① 게이트 off = 현행 동일(매처 호출 0)
# ──────────────────────────────────────────────────────────────────────────
class TestGateOff:
    def test_gate_off_does_not_call_matcher(self) -> None:
        # env 미설정 → 기본 off. 매처를 박아도 호출되지 않아야 한다.
        stub = _StubMatcher()
        set_semantic_matcher(stub)  # type: ignore[arg-type]
        resp = _client().post("/v1/coach", json={"student_input": _NEUTRAL})
        assert resp.status_code == 200, resp.text
        assert stub.calls == 0  # 게이트 off — 의미 매처 미호출(임베딩 로드 0)

    def test_gate_off_substring_only(self) -> None:
        stub = _StubMatcher()
        set_semantic_matcher(stub)  # type: ignore[arg-type]
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert "distribution-over-power" in ids  # substring 결과
        assert _SEMANTIC_ID not in ids  # 의미 후보는 off라 미노출
        assert all(m["semantic_similarity"] is None for m in body["misconceptions"])


# ──────────────────────────────────────────────────────────────────────────
# ② 게이트 on — semantic-only 후순 등장
# ──────────────────────────────────────────────────────────────────────────
class TestGateOnSemanticSurfaces:
    def test_semantic_only_surfaces_below(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        finally:
            get_settings.cache_clear()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        # substr(distribution-over-power) 위 + semantic-only(division-by-zero) 아래.
        assert ids[0] == "distribution-over-power"
        assert _SEMANTIC_ID in ids
        dz = next(m for m in body["misconceptions"] if m["misconception"]["id"] == _SEMANTIC_ID)
        assert dz["semantic_similarity"] is not None  # 의미 경로 결과(표면 근접도 실림)

    def test_neutral_input_surfaces_semantic_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # substring이 아무것도 안 잡는 중립 발화 → semantic-only만 노출.
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            body = _client().post("/v1/coach", json={"student_input": _NEUTRAL}).json()
        finally:
            get_settings.cache_clear()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert ids == [_SEMANTIC_ID]  # 의미 후보 1건만


# ──────────────────────────────────────────────────────────────────────────
# ③ on이라도 substr 1위·select_intervention 구동
# ──────────────────────────────────────────────────────────────────────────
class TestSubstringStaysFirstWithIntervention:
    def test_substring_first_and_intervention(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        finally:
            get_settings.cache_clear()
        top = body["misconceptions"][0]
        assert top["misconception"]["id"] == "distribution-over-power"
        assert top["semantic_similarity"] is None  # 1위는 substring(의미 아님·재정렬 없음)
        # confidence 1.0(>0.8) → 패턴 1(반례) 개입이 substring 진단 기준으로 구동.
        assert body["intervention"] is not None
        assert body["intervention"]["misconception_id"] == "distribution-over-power"


# ──────────────────────────────────────────────────────────────────────────
# ④ to_thread 경유 — 의미 매칭이 워커 스레드에서 호출됨
# ──────────────────────────────────────────────────────────────────────────
class TestToThreadOffload:
    def test_matcher_called_in_worker_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = _StubMatcher()
        set_semantic_matcher(stub)  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        main_thread = threading.main_thread().name
        try:
            resp = _client().post("/v1/coach", json={"student_input": _NEUTRAL})
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 200, resp.text
        assert stub.calls == 1  # on이면 1회 호출
        assert stub.call_threads[0] != main_thread  # 워커 스레드(to_thread offload)

    def test_to_thread_is_invoked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        seen = {"n": 0}
        real_to_thread = asyncio.to_thread

        async def _spy_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
            seen["n"] += 1
            return await real_to_thread(func, *args, **kwargs)

        monkeypatch.setattr(coach.asyncio, "to_thread", _spy_to_thread)
        try:
            resp = _client().post("/v1/coach", json={"student_input": _NEUTRAL})
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 200, resp.text
        assert seen["n"] == 1  # _compute_matches가 to_thread를 1회 경유


# ──────────────────────────────────────────────────────────────────────────
# ⑤ provider 실패 → substring 폴백·200(500 아님)
# ──────────────────────────────────────────────────────────────────────────
class TestGracefulFallback:
    def test_matcher_raises_falls_back_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_RaisingMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            resp = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 200, resp.text  # 500 아님(가용성 우선)
        body = resp.json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert "distribution-over-power" in ids  # substring 폴백 결과 유지
        assert _SEMANTIC_ID not in ids  # 의미 매칭 실패 → 의미 후보 없음
        assert all(m["semantic_similarity"] is None for m in body["misconceptions"])

    def test_fallback_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        set_semantic_matcher(_RaisingMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            with caplog.at_level(logging.WARNING, logger="whymath_backend.api.coach"):
                resp = _client().post("/v1/coach", json={"student_input": _NEUTRAL})
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 200
        # 조용히 넘기지 않고 warning 로그(CLAUDE.md "장애 조용히 넘어가지 말고 로그").
        assert any("의미 매칭 실패" in rec.message for rec in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# ⑥ sessions·turns도 결합(3 엔드포인트 일관)
# ──────────────────────────────────────────────────────────────────────────
class TestSessionAndTurnsCombine:
    def test_session_create_surfaces_semantic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        client, _ = _session_client()
        try:
            resp = client.post("/v1/coach/sessions", json={"student_input": _NEUTRAL})
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 201, resp.text
        ids = [m["misconception"]["id"] for m in resp.json()["misconceptions"]]
        assert _SEMANTIC_ID in ids  # 세션도 결합 경유(공통 _compute_matches)

    def test_turns_append_surfaces_semantic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                started_at=datetime.now(timezone.utc),
                total_turns=2,
                student_turns=1,
                assistant_turns=1,
            )
        )
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        client, _ = _session_client(preload={(DialogueORM, did): dialogue})
        try:
            resp = client.post(
                f"/v1/coach/sessions/{did}/turns", json={"student_input": _NEUTRAL}
            )
        finally:
            get_settings.cache_clear()
        assert resp.status_code == 201, resp.text
        ids = [m["misconception"]["id"] for m in resp.json()["misconceptions"]]
        assert _SEMANTIC_ID in ids  # 턴 append도 결합 경유


# ──────────────────────────────────────────────────────────────────────────
# ⑦ _build_response_payload(body) 직접호출 불변(잠긴 계약 보강)
# ──────────────────────────────────────────────────────────────────────────
class TestBuildPayloadDirectCallUnchanged:
    def test_direct_sync_call_falls_back_to_diagnose(self) -> None:
        # matches 미주입(잠긴 TestThetaIntoScaffolding 호출 형태) → diagnose 폴백·sync·6튜플.
        body = coach.CoachRequest(student_input=_SUBSTR_FULL)
        result = coach._build_response_payload(body)
        assert isinstance(result, tuple) and len(result) == 6  # 반환 튜플 형태 불변
        _decision, matches, intervention, _lthc, _entry, _sol = result
        assert matches  # distribution-over-power 풀매칭
        assert all(m.semantic_similarity is None for m in matches)  # diagnose만(현행 비트동일)
        assert matches[0].misconception.id == "distribution-over-power"
        assert intervention is not None  # confidence 1.0 → 개입 구동(현행 동작)

    def test_direct_call_does_not_touch_matcher(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 직접 sync 호출은 _compute_matches를 거치지 않으므로 게이트 on이어도 매처 무관.
        stub = _StubMatcher()
        set_semantic_matcher(stub)  # type: ignore[arg-type]
        _enable_gate(monkeypatch)
        try:
            coach._build_response_payload(coach.CoachRequest(student_input=_NEUTRAL))
        finally:
            get_settings.cache_clear()
        assert stub.calls == 0  # 직접 호출 경로는 의미 매처 무관(diagnose 폴백)
