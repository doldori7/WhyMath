"""성장 증거 도달 카운터 — `/health/ready` 노출 + 순수 카운터 동작 (hermetic) (PED-06).

`GrowthEvidenceReachCounters`가 `create_app()`이 만드는 모든 앱에 항상 심어지고(재사용 여부와
무관), `/health/ready`의 `growth_evidence.requests_total`로 정확히 그 스냅샷을 노출하는지
검증한다. `GET /v1/me/harness-metrics` 호출 시 실제로 증가하는지는 실 PG가 필요해
`test_wh1_evaluation_integration.py`에 통합테스트로 추가돼 있다(이 파일은 카운터 자체의
계약만 hermetic하게 고정).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whymath_backend.api._growth_evidence_state import (
    GrowthEvidenceReachCounters,
    get_growth_evidence_counters,
)
from whymath_backend.app import create_app
from whymath_backend.ops.service_health import (
    COMPONENT_DATABASE,
    COMPONENT_LLM_ROUTER,
    COMPONENT_REDIS,
    ComponentCheck,
    ReadinessProbes,
)


def _fake_probes() -> ReadinessProbes:
    """실 DB·Redis·LLM 진입을 막는 가짜 probes(`test_health_endpoints.py` `_probes` 미러).

    `/health/ready`를 호출하는 테스트는 실 엔진에 진입하면 `db.session._engine` 전역이
    남아 CI 순서 의존 오염을 낸다(2026-07-26 사고 선례) — 딥체크를 전부 가짜로 대체한다.
    """

    async def _ok(name: str, *, required: bool) -> ComponentCheck:
        return ComponentCheck(
            name=name, configured=True, reachable=True, required=required, error=None
        )

    async def _db() -> ComponentCheck:
        return await _ok(COMPONENT_DATABASE, required=True)

    async def _redis() -> ComponentCheck:
        return await _ok(COMPONENT_REDIS, required=False)

    async def _llm() -> ComponentCheck:
        return await _ok(COMPONENT_LLM_ROUTER, required=False)

    return ReadinessProbes(database=_db, redis=_redis, llm=_llm)


def test_fresh_app_has_zero_requests() -> None:
    """새 앱은 카운터 0에서 시작 — '측정했더니 0'이 아니라 초기 상태."""
    app = create_app(readiness_probes=_fake_probes())
    counters = get_growth_evidence_counters(app)
    assert counters.snapshot().requests_total == 0


def test_health_ready_exposes_growth_evidence_section() -> None:
    """`GET /health/ready` 응답에 growth_evidence.requests_total이 있다."""
    app = create_app(readiness_probes=_fake_probes())
    resp = TestClient(app).get("/health/ready")
    body = resp.json()
    assert "growth_evidence" in body
    assert body["growth_evidence"]["requests_total"] == 0


def test_health_ready_reflects_recorded_requests() -> None:
    """카운터를 직접 증가시키면 `/health/ready` 응답에 그대로 반영된다(변별력)."""
    app = create_app(readiness_probes=_fake_probes())
    counters = get_growth_evidence_counters(app)
    counters.record_request()
    counters.record_request()
    counters.record_request()

    resp = TestClient(app).get("/health/ready")
    assert resp.json()["growth_evidence"]["requests_total"] == 3


def test_counters_are_independent_per_app_instance() -> None:
    """앱 인스턴스가 다르면 카운터도 독립 — 한쪽 증가가 다른 쪽에 새지 않는다."""
    app_a = create_app(readiness_probes=_fake_probes())
    app_b = create_app(readiness_probes=_fake_probes())
    get_growth_evidence_counters(app_a).record_request()

    assert get_growth_evidence_counters(app_a).snapshot().requests_total == 1
    assert get_growth_evidence_counters(app_b).snapshot().requests_total == 0


class TestGrowthEvidenceReachCountersUnit:
    """`GrowthEvidenceReachCounters` 자체의 계약(app 무관 순수 단위테스트)."""

    def test_starts_at_zero(self) -> None:
        assert GrowthEvidenceReachCounters().snapshot().requests_total == 0

    def test_record_request_increments(self) -> None:
        counters = GrowthEvidenceReachCounters()
        counters.record_request()
        assert counters.snapshot().requests_total == 1
        counters.record_request()
        assert counters.snapshot().requests_total == 2

    def test_snapshot_is_immutable_dataclass(self) -> None:
        """스냅샷은 frozen — 호출자가 실수로 값을 고쳐 카운터를 오염시킬 수 없다."""
        snapshot = GrowthEvidenceReachCounters().snapshot()
        try:
            snapshot.requests_total = 999  # type: ignore[misc]
        except (AttributeError, TypeError):
            pass
        else:
            raise AssertionError("frozen dataclass가 값 변경을 막지 못했다")
