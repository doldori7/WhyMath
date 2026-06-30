"""POST /v1/scenes/weak-concept 단위테스트 — 인증·진단→장면·에러매핑. S5a.

라이브 DB·LLM 없음: dependency_overrides(get_consented_user·get_session·get_settings) +
compute_concept_diagnoses·scene_for_concept_diagnosis monkeypatch로 엔드포인트 글루
(인증·404·422·503·200·provider 주입·429)를 hermetic 검증(test_visualization_endpoint 미러).
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
from whymath_backend.l4.learning_scene import LearningScene
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_PATH = "/v1/scenes/weak-concept"
_DIAG_FN = "whymath_backend.api.scene.compute_concept_diagnoses"
_SCENE_FN = "whymath_backend.api.scene.scene_for_concept_diagnosis"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — 레이트 리밋 sliding window 카운트 리셋(test_visualization 패턴)."""
    import asyncio

    asyncio.run(reset_store())


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출(scene monkeypatch)."""

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        return ""


class _FakeSession:
    """get_session 오버라이드용 — 쿼리 미발생(진단·장면 monkeypatch)."""


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _settings(viz_limit: int = 0) -> Settings:
    """테스트 설정 — viz_limit>0이면 시각화 *사용자* 한도(분당) 활성(429 검증·scene이 재사용)."""
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


def _scene() -> LearningScene:
    """최소 학습 장면(엔드포인트 글루 검증용·요소 내용은 monkeypatch라 임의)."""
    return LearningScene(
        concept_id="ALG-QUAD-DEF",
        topic_label="이차함수",
        layout="single",
        answer_deferral_max_level=4,
        elements=[],
    )


def _fake_diagnoses(
    items: list[ConceptDiagnosis],
) -> Callable[[object, object], Awaitable[list[ConceptDiagnosis]]]:
    """compute_concept_diagnoses 대체 — 정해진 진단 목록 반환(약점 먼저 가정)."""

    async def _fake(session: object, user_id: object) -> list[ConceptDiagnosis]:
        return items

    return _fake


class _FakeScene:
    """scene_for_concept_diagnosis 대체 — provider 캡처 + 결과/예외 구성."""

    def __init__(
        self, *, result: LearningScene | None = None, raises: Exception | None = None
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
        student_id: object = None,
    ) -> LearningScene | None:
        self.provider = provider
        if self.raises is not None:
            raise self.raises
        return self.result


def _client(*, provider: _StubProvider, authed: bool = True, viz_limit: int = 0) -> TestClient:
    app = create_app(provider=provider)
    if authed:
        app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings(viz_limit)

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_happy_returns_scene_and_injects_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """약점 진단 → 장면 200 + provider가 app.state(stub)에서 주입됨."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    fake_scene = _FakeScene(result=_scene())
    monkeypatch.setattr(_SCENE_FN, fake_scene)
    stub = _StubProvider()
    resp = _client(provider=stub).post(_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["concept_id"] == "ALG-QUAD-DEF"
    assert body["layout"] == "single"
    # provider DI: 엔드포인트가 app.state의 stub provider를 장면 함수에 주입했다.
    assert fake_scene.provider is stub


def test_no_diagnoses_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """진단 없음 → 404."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([]))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 404


def test_concept_not_found_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """진단 있으나 Concept 미존재(장면 None) → 404."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_SCENE_FN, _FakeScene(result=None))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 404


def test_invalid_spec_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """장면 검증 실패(InvalidVisualizationSpecError) → 422."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_SCENE_FN, _FakeScene(raises=InvalidVisualizationSpecError("bad")))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 422


def test_quality_queue_unavailable_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 큐 불가(QualityQueueUnavailableError) → 503."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_SCENE_FN, _FakeScene(raises=QualityQueueUnavailableError("no queue")))
    assert _client(provider=_StubProvider()).post(_PATH).status_code == 503


def test_unauthenticated_401() -> None:
    """토큰 없음 → 401."""
    assert _client(provider=_StubProvider(), authed=False).post(_PATH).status_code == 401


def test_rate_limit_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """사용자 분당 한도(2) 초과 → 429 (visualization 버킷 재사용·LLM 비용 보호)."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    monkeypatch.setattr(_SCENE_FN, _FakeScene(result=_scene()))
    client = _client(provider=_StubProvider(), viz_limit=2)
    assert client.post(_PATH).status_code == 200
    assert client.post(_PATH).status_code == 200
    assert client.post(_PATH).status_code == 429
