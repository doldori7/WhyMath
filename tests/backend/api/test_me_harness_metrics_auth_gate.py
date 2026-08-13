"""`GET /v1/me/harness-metrics` 인가 게이트 회귀 (hermetic) (SEC-24(원 SEC-13)).

`functional_security_audit_2026-08-08.md` H1 — 이 엔드포인트는 도입 당시부터 docstring엔
"내부·집계 전용 원시 계측 표면"이라 적혀 있었으나 실제 게이트는 `ConsentedUser`(학생 포함
인증 사용자 전원)였다. 원시 `SurrogateMetrics`엔 INTERNAL_ONLY 지표(②진단정확도·④턴당토큰)·
⑥보정점수 원 스칼라·⑧`help_reduction_validated.verdict`(=`GAMING_SUSPECT` 낙인 가능)가 그대로
실려 학생 토큰이 이를 직접 조회할 수 있었다. SEC-24(원 SEC-13)이 `RequireContentAdmin`으로 닫았다.

`whymath_backend.api.me.compute_wh1_surrogate_metrics`를 monkeypatch해(`test_me_growth_evidence.py`
패턴 동형) 실 DB 없이 인가 계층만 검증한다 — 결함주입: 이 파일의 `dependency_overrides`에서
`require_content_admin`을 제거하면(=게이트를 되돌리면) `test_student_role_forbidden`이
403 대신 200을 받아 실패한다(변별력 확인 완료 — 아래 각 테스트가 그 상태 전환을 직접 검증).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_current_user, require_content_admin
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    SurrogateMetrics,
)
from whymath_backend.ops.service_health import (
    COMPONENT_DATABASE,
    COMPONENT_LLM_ROUTER,
    COMPONENT_REDIS,
    ComponentCheck,
    ReadinessProbes,
)
from whymath_backend.schema.enums import Persona, Role
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_ENDPOINT = "/v1/me/harness-metrics"


class _FakeAsyncSession:
    """`compute_wh1_surrogate_metrics`를 monkeypatch하므로 세션은 실제로 쿼리되지 않는다."""


def _fake_probes() -> ReadinessProbes:
    """실 DB·Redis·LLM 진입을 막는 가짜 probes(`test_me_growth_evidence.py` 미러)."""

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


def _surrogate_metrics() -> SurrogateMetrics:
    """GAMING_SUSPECT verdict를 포함한 전 필드 MEASURED 고정 응답 — 노출 시 즉시 눈에 띄게."""
    m = Metric(value=0.5, status=MetricStatus.MEASURED, note="테스트 note")
    return SurrogateMetrics(
        verify_pass_rate=m,
        diagnosis_agreement_rate=m,
        session_completion_rate=m,
        tokens_per_turn=m,
        help_reduction_slope=m,
        help_demand_supply_ratio=m,
        calibration_brier=Metric(value=0.42, status=MetricStatus.MEASURED, note="테스트 note"),
        transfer_score=m,
        hint_depth_reached=Metric(value=2.0, status=MetricStatus.MEASURED, note="테스트 note"),
        mastery_gain_rate=m,
        # main 드리프트 수용: `gap_recovery_leadtime_days`는 이식 이후 main에 추가된 필수 필드.
        gap_recovery_leadtime_days=m,
        misconception_resolution_rate=m,
        self_solve_rate=m,
        help_reduction_validated=HelpReductionValidation(
            verdict=R15Verdict.GAMING_SUSPECT,
            help_slope=-1.0,
            accuracy_slope=0.5,
            difficulty_slope=-0.8,
            note="쉬운 문제 회피 테스트 note",
        ),
        sample_sessions=1,
        window_start=None,
        window_end=None,
        user_scoped=True,
    )


def _app_with_session_override(monkeypatch: Any) -> Any:
    async def _fake_compute(*_args: Any, **_kwargs: Any) -> SurrogateMetrics:
        return _surrogate_metrics()

    monkeypatch.setattr("whymath_backend.api.me.compute_wh1_surrogate_metrics", _fake_compute)
    app = create_app(readiness_probes=_fake_probes())

    async def _sess() -> AsyncIterator[_FakeAsyncSession]:
        yield _FakeAsyncSession()

    app.dependency_overrides[get_session] = _sess
    return app


def test_no_token_returns_401(monkeypatch: Any) -> None:
    """무토큰 — 역할 게이트 도달 전에 인증 계층이 먼저 401(기존 계약 불변)."""
    app = _app_with_session_override(monkeypatch)
    client = TestClient(app)
    resp = client.get(_ENDPOINT)
    assert resp.status_code == 401


def test_student_role_forbidden(monkeypatch: Any) -> None:
    """SEC-24(원 SEC-13) 핵심 회귀 — `Role.STUDENT` 인증 사용자는 403(원시 지표 도달 불가).

    이 assert가 이 게이트의 존재 이유다: 되돌리면(= `get_my_harness_metrics`가 다시
    `ConsentedUser`를 쓰면) 200이 나서 이 테스트가 실패한다.
    """
    app = _app_with_session_override(monkeypatch)
    student = UserProfile.from_schema(
        UserProfileSchema(user_id=uuid.uuid4(), persona_primary=Persona.A_일반고고3)
    )
    app.dependency_overrides[get_current_user] = lambda: student
    client = TestClient(app)
    resp = client.get(_ENDPOINT)
    assert resp.status_code == 403
    # GAMING_SUSPECT·INTERNAL_ONLY 지표가 거부 응답 본문에도 없다(방어 심층 — 403 자체가
    # 이미 핸들러 진입을 막지만, 직렬화 우회 재도입 시에도 걸리도록 원문 스캔).
    assert "GAMING_SUSPECT" not in resp.text
    assert "diagnosis_agreement_rate" not in resp.text
    assert "tokens_per_turn" not in resp.text


def test_content_admin_role_allowed(monkeypatch: Any) -> None:
    """CONTENT_ADMIN 인증 사용자는 200 — 원시 표면 자체는 admin에게 여전히 열려 있다.

    `UserProfile.from_schema(...)`가 아니라 직접 생성자를 쓴다(`test_problems.py::_ADMIN_USER`
    동형) — `.from_schema()` 경로는 role을 문자열로 굳혀 `require_role`의 Enum 비교
    (`user.role not in roles`)가 항상 False로 새는 함정이 있다(role은 `str, Enum` 믹스인이
    아니다 — `schema/enums.py` 참조).
    """
    app = _app_with_session_override(monkeypatch)
    admin = UserProfile(user_id=uuid.uuid4(), role=Role.CONTENT_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    resp = client.get(_ENDPOINT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["help_reduction_validated"]["verdict"] == "gaming_suspect"


def test_require_content_admin_is_the_actual_gate(monkeypatch: Any) -> None:
    """라우트가 `require_content_admin`을 실제로 쓴다 — 오버라이드 시 인가가 우회됨을 확인.

    `test_problems.py`/`test_concepts.py`의 `require_content_admin` 오버라이드 패턴과
    동일 대상(`api._auth.require_content_admin` 단일 객체)임을 교차 검증한다.
    """
    app = _app_with_session_override(monkeypatch)
    student = UserProfile.from_schema(
        UserProfileSchema(user_id=uuid.uuid4(), persona_primary=Persona.A_일반고고3)
    )
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[require_content_admin] = lambda: student
    client = TestClient(app)
    resp = client.get(_ENDPOINT)
    assert resp.status_code == 200
