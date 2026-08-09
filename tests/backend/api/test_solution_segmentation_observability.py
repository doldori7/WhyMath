"""단계 분해 0-전이 제출 관측 테스트 (NLP-03 acceptance ③ 백엔드 축).

설계 정본: `docs/architecture/nlp_module_gap_review.md` §3 D3. 백엔드가 원문을 직접 분해하는
라이브 경로는 없다 — 관측 대상은 클라이언트가 `/v1/coach`류 요청에 실어 보낸
`solution_steps`의 길이 분포(0-전이 의심 신호)다.

동결 계약:
  1. **변별력(단위)** — 1스텝/2+스텝/무관측 요청이 `SolutionSegmentationCounters`에서
     서로 다른 값을 낸다(CLAUDE.md 변별력 실측).
  2. **핸들러 결선** — `/v1/coach` 요청이 실제로 카운터를 갱신한다(`create_app`
     주입 좌석 경유).
  3. **`/health/ready` 노출** — `solution_segmentation` 섹션이 total·single_or_zero_step을
     정확히 보고한다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.api._segmentation_state import SolutionSegmentationCounters
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.ops.service_health import (
    COMPONENT_DATABASE,
    COMPONENT_LLM_ROUTER,
    COMPONENT_REDIS,
    ComponentCheck,
    ReadinessProbes,
)
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


# ──────────────────────────────────────────────────────────────────────────
# ① 변별력(단위) — 카운터 자체가 서로 다른 입력에 서로 다른 값을 낸다.
# ──────────────────────────────────────────────────────────────────────────
class TestSolutionSegmentationCountersUnit:
    def test_none_and_empty_do_not_count(self) -> None:
        """solution_steps가 None이거나 빈 리스트면 관측 대상이 아니다(분모 불변)."""
        counters = SolutionSegmentationCounters()
        counters.record(None)
        counters.record([])
        snapshot = counters.snapshot()
        assert snapshot.total == 0
        assert snapshot.single_or_zero_step == 0

    def test_single_step_counts_as_zero_transition_suspect(self) -> None:
        """1스텝 요청은 total·single_or_zero_step 둘 다 증가(2026-07-20류 재발 의심 신호)."""
        counters = SolutionSegmentationCounters()
        counters.record(["x = 1"])
        snapshot = counters.snapshot()
        assert snapshot.total == 1
        assert snapshot.single_or_zero_step == 1

    def test_multi_step_counts_total_only(self) -> None:
        """2+스텝 요청은 total만 증가·single_or_zero_step은 불변(정상 분해)."""
        counters = SolutionSegmentationCounters()
        counters.record(["x + 1 = 2", "x = 1"])
        snapshot = counters.snapshot()
        assert snapshot.total == 1
        assert snapshot.single_or_zero_step == 0

    def test_three_input_kinds_yield_pairwise_distinct_counters(self) -> None:
        """무관측(None)·1스텝·2+스텝 세 입력이 서로 다른 (total, single_or_zero_step) 신호를 낸다.

        None-vs-1스텝-vs-2+스텝 세 상태의 변별력 실측(CLAUDE.md).
        """
        no_obs = SolutionSegmentationCounters()
        no_obs.record(None)

        one_step = SolutionSegmentationCounters()
        one_step.record(["x = 1"])

        multi_step = SolutionSegmentationCounters()
        multi_step.record(["x + 1 = 2", "x = 1"])

        signatures = {
            (s.total, s.single_or_zero_step)
            for s in (no_obs.snapshot(), one_step.snapshot(), multi_step.snapshot())
        }
        assert len(signatures) == 3

    def test_mixed_sequence_accumulates_correctly(self) -> None:
        """여러 건 누적 — total은 관측 대상 요청 수, single_or_zero_step은 그중 1스텝 이하 건수."""
        counters = SolutionSegmentationCounters()
        counters.record(["a=1", "b=2"])  # 2스텝 — total만
        counters.record(["a=1"])  # 1스텝 — 둘 다
        counters.record(None)  # 관측 대상 아님
        counters.record([])  # 관측 대상 아님
        counters.record(["c=3"])  # 1스텝 — 둘 다
        snapshot = counters.snapshot()
        assert snapshot.total == 3
        assert snapshot.single_or_zero_step == 2


# ──────────────────────────────────────────────────────────────────────────
# ② 핸들러 결선 — `/v1/coach` 요청이 실제로 주입된 카운터를 갱신한다.
# ──────────────────────────────────────────────────────────────────────────
def _settings_override() -> Settings:
    """coach rate limit 전부 비활성(0) — test_coach.py 관행과 동일."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
        coach_device_hmac_secret=SecretStr(""),
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeStatelessSession:
    """`/v1/coach`(stateless)용 — DB 호출 시 AssertionError(test_coach.py 관행 미러)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


def _fake_probes() -> ReadinessProbes:
    """항상 성공하는 가짜 딥체크 — `/health/ready` 호출이 실 DB/Redis/Ollama에 닿지 않게 한다
    (`test_ocr_reachability.py::_fake_probes` 미러)."""

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


def _client(*, segmentation_counters: SolutionSegmentationCounters | None = None) -> TestClient:
    app: FastAPI = create_app(
        segmentation_counters=segmentation_counters, readiness_probes=_fake_probes()
    )
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_override

    async def _sess() -> AsyncIterator[_FakeStatelessSession]:
        yield _FakeStatelessSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach.py 관행 미러)."""
    import asyncio

    asyncio.run(reset_store())


class TestCoachHandlerWiring:
    def test_multi_step_request_does_not_flag_single_or_zero(self) -> None:
        """2+스텝 solution_steps ⇒ total만 증가·single_or_zero_step은 0(정상 분해)."""
        injected = SolutionSegmentationCounters()
        client = _client(segmentation_counters=injected)
        resp = client.post(
            "/v1/coach",
            json={"student_input": "음", "solution_steps": ["x + 1 = 2", "x = 1"]},
        )
        assert resp.status_code == 200
        snapshot = injected.snapshot()
        assert snapshot.total == 1
        assert snapshot.single_or_zero_step == 0

    def test_single_step_request_flags_single_or_zero(self) -> None:
        """1스텝 solution_steps ⇒ total·single_or_zero_step 둘 다 증가(의심 신호)."""
        injected = SolutionSegmentationCounters()
        client = _client(segmentation_counters=injected)
        resp = client.post(
            "/v1/coach",
            json={"student_input": "음", "solution_steps": ["x = 1"]},
        )
        assert resp.status_code == 200
        snapshot = injected.snapshot()
        assert snapshot.total == 1
        assert snapshot.single_or_zero_step == 1

    def test_request_without_solution_steps_is_not_observed(self) -> None:
        """solution_steps 미제공(None) ⇒ 관측 대상 아님(total 불변) — 기존 동작 완전 불변 경로."""
        injected = SolutionSegmentationCounters()
        client = _client(segmentation_counters=injected)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        snapshot = injected.snapshot()
        assert snapshot.total == 0
        assert snapshot.single_or_zero_step == 0


# ──────────────────────────────────────────────────────────────────────────
# ③ `/health/ready` 노출 — solution_segmentation 섹션이 total·single_or_zero_step 보고.
# ──────────────────────────────────────────────────────────────────────────
class TestHealthReadyExposure:
    def test_no_traffic_reports_zero(self) -> None:
        """요청 없이도 /health/ready.solution_segmentation은 0/0(에러 없이 노출)."""
        client = _client()
        body = client.get("/health/ready").json()
        assert body["solution_segmentation"]["total"] == 0
        assert body["solution_segmentation"]["single_or_zero_step"] == 0

    def test_mixed_traffic_surfaces_in_ready_body(self) -> None:
        """1스텝 1건 + 2스텝 1건 + None 1건 ⇒ ready body가 total=2·single_or_zero_step=1."""
        client = _client()
        client.post("/v1/coach", json={"student_input": "음", "solution_steps": ["x = 1"]})
        client.post(
            "/v1/coach",
            json={"student_input": "음", "solution_steps": ["x + 1 = 2", "x = 1"]},
        )
        client.post("/v1/coach", json={"student_input": "음"})

        body = client.get("/health/ready").json()
        assert body["solution_segmentation"]["total"] == 2
        assert body["solution_segmentation"]["single_or_zero_step"] == 1

    def test_ready_gate_is_unaffected_by_segmentation_observation(self) -> None:
        """solution_segmentation은 ready 판정(200/503)에 관여하지 않는다 — DB 도달성만 게이트."""
        client = _client()
        client.post("/v1/coach", json={"student_input": "음", "solution_steps": ["x = 1"]})
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True
