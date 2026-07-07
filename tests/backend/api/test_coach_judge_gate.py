"""L4 coach 오개념 *방향 판별 judge 게이트* HTTP 결선 단위테스트 — 슬108 배선(hermetic·judge 주입).

검증 항목:
- 게이트(`misconception_judge_enabled`) off(기본) = judge 좌석 미구성·현행 비트동일.
- on = `NOT_EXPRESSES`(아니오)만 제거·`EXPRESSES`(예)·`UNCERTAIN`(불확실)은 유지(recall 보존).
- judge는 *품질 게이트 이전*에 적용 → 강한 top-1(1.0)도 아니오면 비워지고 `no_confident_match=True`.
- never-break: judge seam 예외 → `UNCERTAIN` 폴백 → 후보 유지·200(가용성 우선).
- 후보 0(중립)이면 judge 미호출(좌석 구성 0·효율).
- 3 엔드포인트(stateless·sessions·turns) 공통 `_compute_matches`라 게이트 일관.
- 직접 sync `_build_response_payload(body)` 경로는 게이트 *미적용*(diagnose 폴백·잠긴 계약 불변).

**게이트 토글**: `_compute_matches`는 실 `get_settings()`(Depends 아님·모듈 직호출)를 읽으므로
`monkeypatch.setenv` + `get_settings.cache_clear()`로 켠다(test_coach_semantic 패턴).
**judge 주입**: `coach._judge_for_gate`를 monkeypatch해 `FakeJudge`(결정론·라이브 0)·
never-break용 Boom seam을 박는다(좌석 주입점·hermetic — 라이브 Ollama 0).

전부 *동기* 테스트 함수다(`TestClient`가 async 엔드포인트를 동기 구동) — test_coach_semantic과 동형.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._l3_state import CACHE_KEY, PROVIDER_KEY, TRACE_KEY
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.judge import (
    FakeJudge,
    JudgeProtocol,
    JudgeVerdict,
    LLMJudge,
)
from whymath_backend.l4.misconception.judge_seam import L3JudgeSeam
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()

# 완전 substring 매칭(confidence 1.0)·distribution-over-power.
# judge가 *제거*하면 강한 top-1도 비워진다.
_SUBSTR_FULL = "내 풀이는 (a+b)² = a² + b²로 전개했어"
# substring이 전혀 안 잡는 중립 발화 — 후보 0이라 judge 미호출 검증용.
_NEUTRAL = "이 문제 어떻게 접근하면 좋을까"
_DOP = "distribution-over-power"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach 패턴)."""
    asyncio.run(reset_store())


@pytest.fixture(autouse=True)
def _restore_settings_cache() -> Iterator[None]:
    """env 토글 누수 차단 — 테스트 후 전역 Settings 캐시를 무조건 클리어(setenv 되돌림 재반영)."""
    yield
    get_settings.cache_clear()


def _enable_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    """judge 게이트 ON — env+cache_clear(실 get_settings를 읽는 _compute_matches용)."""
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_JUDGE_ENABLED", "true")
    get_settings.cache_clear()


def _patch_judge(monkeypatch: pytest.MonkeyPatch, judge: JudgeProtocol) -> dict[str, int]:
    """`_judge_for_gate` 좌석을 주입 judge로 교체 + 호출 횟수 스파이 반환(off면 0이어야)."""
    calls = {"n": 0}

    # 좌석은 이제 app.state 공유 provider/cache/trace를 kwargs로 받는다 — 대체 팩토리도
    # `**_`로 받아 무시한다(FakeJudge라 주입값 미소비·실 좌석 시그니처와 호환).
    def _factory(**_: object) -> JudgeProtocol:
        calls["n"] += 1
        return judge

    monkeypatch.setattr(coach, "_judge_for_gate", _factory)
    return calls


def _settings_no_limits() -> Settings:
    """rate limit 0(비활성)·JWT 시크릿 채움 — judge 게이트는 env로 따로 켠다."""
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


class _Result:
    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Any]:
        return []

    def first(self) -> Any:
        return None


class _CapturingSession:
    """/v1/coach/sessions·turns용 — add/commit/refresh/get/execute 캡처(test_coach 패턴)."""

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

    async def flush(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        return None

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))

    async def execute(self, stmt: Any) -> _Result:
        return _Result()


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


class _BoomSeam:
    """generate가 항상 raise — `LLMJudge` never-break(예외→UNCERTAIN→유지) 검증용."""

    async def generate(self, prompt: str, system: str) -> str:
        raise RuntimeError("judge seam 강제 실패(never-break 테스트)")


# ──────────────────────────────────────────────────────────────────────────
# ① 게이트 off(기본) = judge 좌석 미구성·현행 비트동일
# ──────────────────────────────────────────────────────────────────────────
class TestGateOffDefault:
    def test_off_does_not_construct_judge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 플래그 미설정(기본 off) → judge 팩토리가 호출되지 않아야 한다(좌석 구성 0).
        calls = _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        assert calls["n"] == 0  # off — judge 미구성(LLM 0)
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert _DOP in ids  # 현행 비트동일(아니오 judge를 박아도 off라 미적용)

    def test_off_unit_bit_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # _compute_matches 단위: off면 NOT_EXPRESSES judge를 박아도 매칭 유지(judge 미호출).
        calls = _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        outcome = asyncio.run(coach._compute_matches(_SUBSTR_FULL))
        assert calls["n"] == 0
        assert outcome.matches and outcome.matches[0].misconception.id == _DOP
        assert outcome.no_confident_match is False


# ──────────────────────────────────────────────────────────────────────────
# ② 게이트 on — NOT_EXPRESSES만 제거(품질 게이트 *이전*·강한 top-1도 비워짐)
# ──────────────────────────────────────────────────────────────────────────
class TestGateOnRemovesNotExpresses:
    def test_not_expresses_removes_and_sets_no_confident(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 강한 top-1(distribution-over-power·1.0)을 judge가 '아니오'로 제거 → 후보 비고
        # no_confident_match=True. (품질 게이트 단독이면 1.0은 안 비워짐 →
        # judge가 *먼저* 적용됨 입증.)
        calls = _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        _enable_judge(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        assert calls["n"] == 1  # on + 후보 있음 → judge 1회 구성
        assert body["misconceptions"] == []  # 아니오 → 제거
        assert body["no_confident_match"] is True  # judge 후 top-1 없음 → 품질 게이트가 플래그
        assert body["intervention"] is None  # 후보 0 → 개입 없음

    def test_expresses_keeps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.EXPRESSES}))
        _enable_judge(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert _DOP in ids  # 예 → 유지
        assert body["no_confident_match"] is False

    def test_uncertain_keeps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # default=UNCERTAIN(불확실) — 명시 안 된 후보는 보수적으로 유지.
        _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.UNCERTAIN))
        _enable_judge(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert _DOP in ids  # 불확실 → 유지(recall 보존)

    def test_unit_not_expresses_empties(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        _enable_judge(monkeypatch)
        outcome = asyncio.run(coach._compute_matches(_SUBSTR_FULL))
        assert outcome.matches == []
        assert outcome.no_confident_match is True


# ──────────────────────────────────────────────────────────────────────────
# ③ never-break — judge seam 예외 → UNCERTAIN 폴백 → 후보 유지·200
# ──────────────────────────────────────────────────────────────────────────
class TestNeverBreak:
    def test_seam_exception_keeps_candidate_200(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 실 LLMJudge + 항상 raise하는 seam → LLMJudge가 UNCERTAIN으로 폴백 → 후보 유지.
        _patch_judge(monkeypatch, LLMJudge(_BoomSeam()))  # type: ignore[arg-type]
        _enable_judge(monkeypatch)
        with caplog.at_level(logging.WARNING):
            resp = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 200, resp.text  # 500 아님(가용성 우선)
        ids = [m["misconception"]["id"] for m in resp.json()["misconceptions"]]
        assert _DOP in ids  # UNCERTAIN 폴백 → 유지
        # 조용히 넘기지 않고 로그(CLAUDE.md "장애 조용히 넘어가지 말고 로그").
        assert any("judge seam 호출 실패" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# ④ 후보 0(중립) → judge 미호출(효율·좌석 구성 0)
# ──────────────────────────────────────────────────────────────────────────
class TestNoCandidatesSkipsJudge:
    def test_neutral_input_does_not_call_judge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.NOT_EXPRESSES))
        _enable_judge(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _NEUTRAL}).json()
        assert calls["n"] == 0  # 후보 0 → short-circuit(judge 좌석 미구성)
        assert body["misconceptions"] == []


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 3 엔드포인트(sessions·turns) 공통 게이트
# ──────────────────────────────────────────────────────────────────────────
class TestThreeEndpointsConsistent:
    def test_session_create_gates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        _enable_judge(monkeypatch)
        client, _ = _session_client()
        resp = client.post("/v1/coach/sessions", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["misconceptions"] == []  # 세션도 공통 _compute_matches 게이트
        # 가설 영속도 같은 게이트된 matches를 받으므로 judge가 거른 가설은 적재 0.
        assert body["active_hypotheses"] == []

    def test_turns_append_gates(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        _enable_judge(monkeypatch)
        client, _ = _session_client(preload={(DialogueORM, did): dialogue})
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 201, resp.text
        assert resp.json()["misconceptions"] == []  # 턴 append도 게이트


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 직접 sync _build_response_payload(body) 경로는 게이트 미적용(잠긴 계약 불변)
# ──────────────────────────────────────────────────────────────────────────
class TestDirectPayloadCallUngated:
    def test_direct_sync_call_skips_judge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 직접 호출은 _compute_matches(게이트 거처)를 거치지 않으므로, 게이트 on·아니오 judge여도
        # diagnose 폴백이라 후보 유지(잠긴 _build_response_payload(body) 계약 불변).
        calls = _patch_judge(monkeypatch, FakeJudge({_DOP: JudgeVerdict.NOT_EXPRESSES}))
        _enable_judge(monkeypatch)
        result = coach._build_response_payload(coach.CoachRequest(student_input=_SUBSTR_FULL))
        assert calls["n"] == 0  # 직접 경로는 judge 무관
        _decision, matches, _intervention, _lthc, _entry, _sol = result
        assert matches and matches[0].misconception.id == _DOP  # diagnose 폴백·유지


# ──────────────────────────────────────────────────────────────────────────
# ⑦ 프로덕션 배선 — judge seam이 app.state 공유 LangfuseSink/provider/cache를 주입받는다
#    (judge usage/cost가 throwaway로 버려지지 않고 실제 관측으로 흐름을 증명)
# ──────────────────────────────────────────────────────────────────────────
class _RecordingProvider:
    """`LLMProvider` 가짜 — 유효 verdict 텍스트를 돌리고 호출을 캡처(라이브 Ollama 0).

    judge seam→l3.pipeline이 이 provider를 부르면 pipeline이 `trace.record`를 호출하므로,
    주입 trace로 레코드가 흐르는지로 배선을 증명한다.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        **_: object,
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(text="판정: 예\n근거: 테스트 결선")


class TestJudgeSeamSharedDepsWiring:
    def test_judge_for_gate_injects_shared_instances_into_seam(self) -> None:
        # 단위: `_judge_for_gate`가 주입 provider/cache/trace로 `L3JudgeSeam`을 만드는지 단언.
        provider = _RecordingProvider()
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        judge = coach._judge_for_gate(provider=provider, cache=cache, trace=trace)
        assert isinstance(judge, LLMJudge)
        seam = judge._seam
        assert isinstance(seam, L3JudgeSeam)
        # seam이 *바로 그* 공유 인스턴스를 물었는지(throwaway 기본값이 아니라).
        assert seam._provider is provider
        assert seam._cache is cache
        assert seam._trace is trace

    def test_get_judge_seam_deps_reads_app_state(self) -> None:
        # 의존성 헬퍼: app.state의 공유 provider/cache/trace를 그대로 묶어 반환.
        provider = _RecordingProvider()
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        app = create_app(provider=provider, cache=cache, trace=trace)
        # `request.app.state`만 참조하는 얇은 헬퍼라 app을 문 최소 Request 스텁으로 구동.
        request = SimpleNamespace(app=app)
        deps = coach._get_judge_seam_deps(cast(Any, request))
        assert deps.provider is provider
        assert deps.cache is cache
        assert deps.trace is trace
        # 확인: 기본이 아니라 실제 app.state 인스턴스(state 키 단일 출처).
        assert getattr(app.state, PROVIDER_KEY) is provider
        assert getattr(app.state, CACHE_KEY) is cache
        assert getattr(app.state, TRACE_KEY) is trace

    def test_endpoint_flows_judge_record_to_shared_trace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 관통: judge 게이트 ON에서 /v1/coach 경로가 app.state 공유 trace로 judge usage/cost를
        # 기록하는지. `_judge_for_gate`는 monkeypatch하지 *않는다* — 실 좌석이 주입 인스턴스로
        # L3JudgeSeam을 구성해야 함을 증명(throwaway RecordingTraceSink로 새면 이 단언이 깨진다).
        provider = _RecordingProvider()
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        app = create_app(provider=provider, cache=cache, trace=trace)
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = _settings_no_limits

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        _enable_judge(monkeypatch)  # env로 게이트 ON(_compute_matches는 실 get_settings 직독)
        resp = TestClient(app).post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 200, resp.text
        # judge seam이 *공유* provider를 탔고(호출 발생), *공유* trace에 레코드가 흘렀다
        # (throwaway였다면 provider.calls>0라도 trace.records는 비었을 것).
        assert provider.calls >= 1
        assert trace.records, "judge 호출 usage/cost가 공유 trace로 흐르지 않음(배선 실패)"
