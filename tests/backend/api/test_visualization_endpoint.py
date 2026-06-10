"""POST /v1/visualizations/weak-concept 단위테스트 — 인증·진단→시각화·에러매핑. 슬라이스 96.

라이브 DB·LLM 없음: dependency_overrides(get_consented_user·get_session·get_settings) +
compute_concept_diagnoses·visualize_for_concept_diagnosis monkeypatch로 엔드포인트 글루
(인증·404·422·503·200·provider 주입)를 hermetic 검증.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l2.concept_diagnosis import ConceptDiagnosis
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.schema.enums import Persona, VisualizationType
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.schema.visualization import Visualization

_UID = uuid.uuid4()
_PATH = "/v1/visualizations/weak-concept"
_DIAG_FN = "whymath_backend.api.visualization.compute_concept_diagnoses"
_VIZ_FN = "whymath_backend.api.visualization.visualize_for_concept_diagnosis"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — 레이트 리밋 sliding window 카운트 리셋(test_coach 패턴)."""
    import asyncio

    asyncio.run(reset_store())


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출(visualize monkeypatch)."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> str:
        return ""


class _FakeSession:
    """get_session 오버라이드용 — 쿼리 미발생(진단·시각화 monkeypatch)."""


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _settings(viz_limit: int = 0) -> Settings:
    """테스트 설정 — viz_limit>0이면 시각화 *사용자* 한도(분당) 활성(429 검증·IP/device 0)."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        visualization_rate_limit_per_minute=viz_limit,
        visualization_rate_limit_ip_per_minute=0,
        visualization_rate_limit_device_per_minute=0,
    )


def _diagnosis() -> ConceptDiagnosis:
    return ConceptDiagnosis(
        concept_id=uuid.uuid4(),
        response_count=5,
        agreement="insufficient",
        bkt_mastery=0.3,
    )


def _viz() -> Visualization:
    return Visualization(
        type=VisualizationType.interactive_graph_2d,
        spec={"model": "circle"},
        caption="단위원",
    )


def _fake_diagnoses(
    items: list[ConceptDiagnosis],
) -> Callable[[object, object], Awaitable[list[ConceptDiagnosis]]]:
    """compute_concept_diagnoses 대체 — 정해진 진단 목록 반환(약점 먼저 가정)."""

    async def _fake(session: object, user_id: object) -> list[ConceptDiagnosis]:
        return items

    return _fake


class _FakeVisualize:
    """visualize_for_concept_diagnosis 대체 — provider 캡처 + 결과/예외 구성."""

    def __init__(
        self, *, result: Visualization | None = None, raises: Exception | None = None
    ) -> None:
        self.result = result
        self.raises = raises
        self.provider: object = None

    async def __call__(
        self,
        diagnosis: object,
        session: object,
        *,
        provider: object,
        cache: object,
        trace: object,
        student_subscription: str = "free",
    ) -> Visualization | None:
        self.provider = provider
        if self.raises is not None:
            raise self.raises
        return self.result


def _client(
    *, provider: _StubProvider, authed: bool = True, viz_limit: int = 0
) -> TestClient:
    app = create_app(provider=provider)
    if authed:
        app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings(viz_limit)

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_happy_returns_visualization_and_injects_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """약점 진단 → 시각화 200 + provider가 app.state(stub)에서 주입됨."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    fake_viz = _FakeVisualize(result=_viz())
    monkeypatch.setattr(_VIZ_FN, fake_viz)
    stub = _StubProvider()
    resp = _client(provider=stub).post(_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "interactive_graph_2d"
    assert body["caption"] == "단위원"
    # provider DI: 엔드포인트가 app.state의 stub provider를 시각화 함수에 주입했다.
    assert fake_viz.provider is stub


def test_no_diagnoses_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """진단 없음 → 404."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([]))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 404


def test_concept_not_found_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """진단 있으나 Concept 미존재(시각화 None) → 404."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_VIZ_FN, _FakeVisualize(result=None))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 404


def test_invalid_spec_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """L3 검증 실패(InvalidVisualizationSpecError) → 422."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(
        _VIZ_FN, _FakeVisualize(raises=InvalidVisualizationSpecError("bad"))
    )
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 422


def test_quality_queue_unavailable_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 큐 불가(QualityQueueUnavailableError) → 503."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(
        _VIZ_FN, _FakeVisualize(raises=QualityQueueUnavailableError("no queue"))
    )
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 503


def test_unauthenticated_401() -> None:
    """토큰 없음 → 401."""
    assert (
        _client(provider=_StubProvider(), authed=False).post(_PATH).status_code == 401
    )


def test_rate_limit_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """사용자 분당 한도(2) 초과 → 429 (슬97·LLM 비용 보호·전용 버킷)."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_VIZ_FN, _FakeVisualize(result=_viz()))
    client = _client(provider=_StubProvider(), viz_limit=2)
    assert client.post(_PATH).status_code == 200
    assert client.post(_PATH).status_code == 200
    assert client.post(_PATH).status_code == 429
