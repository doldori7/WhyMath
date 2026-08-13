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
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.l4.learning_scene import LearningScene, parse_learning_scene
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import CognitiveType, ConceptLevel, Persona
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

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


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


# ── SOL-02 ④ 집행 별항 — 실제 서빙 경로 실바디 변별력 ────────────────────────
# `scene_for_concept_diagnosis`를 monkeypatch하지 않고 *실제* 서비스→생성기를 태운다.
# DB만 가짜 세션(get 디스패치 + execute 큐)으로 대체하고, 응답 *본문*에 step_panel이
# (경로 실재 시) 실리고 (없으면) 안 실리는지 양방향으로 본다 — "생성기 함수가 만들 수
# 있다"는 집행 증거가 아니라 서빙 경로 방출의 실측이다.


class _FakeConceptOrm:
    """가짜 Concept ORM — to_schema()·code만 제공(권장 양식 0 → 시각화 LLM 미호출)."""

    def __init__(self, schema: Concept) -> None:
        self._schema = schema
        self.code = schema.code

    def to_schema(self) -> Concept:
        return self._schema


class _RowResult:
    """execute 결과 범용 모사 — `.all()`(행 목록)·`.scalars().all()/first()` 표면 동시 지원."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def scalars(self) -> "_RowResult":
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None


class _WireSession:
    """서빙 경로 전체 쿼리 순서 모사 — SOL-02 step_panel 실바디 변별력용.

    `scene_for_concept_diagnosis`(+student_id)의 세션 접근 순서:
      get: Concept → ConceptVisualization → ConceptVisualStyle → AtomNode(행동영역·None이면 쿼리 0)
      execute: ① 활성 가설(scalars().all()) ② 증거 순지지도(all()) ③ 앵커 후보(all())
               ④~ 경로 단건(scalars().first() — 후보마다·실재하면 중단)
    """

    def __init__(self, orm: object, queue: list[list[object]]) -> None:
        self._orm = orm
        self._queue = list(queue)

    async def get(self, model: object, key: object) -> object:
        name = getattr(model, "__name__", "")
        if name == "Concept":
            return self._orm
        return None  # ConceptVisualization·ConceptVisualStyle·AtomNode — 미태깅(중립 폴백)

    async def execute(self, _stmt: object) -> _RowResult:
        return _RowResult(self._queue.pop(0))


def _wire_concept_orm() -> _FakeConceptOrm:
    """권장 시각화 양식 0·인지유형 DEFINITION — LLM 없이 소크라테스 골격만 나오는 개념."""
    return _FakeConceptOrm(
        Concept(
            code="ALG-QUAD-DEF",
            name_ko="이차함수의 정의",
            level=ConceptLevel.세부개념,
            cognitive_type=[CognitiveType.DEFINITION],
        )
    )


def _wire_client(session: _WireSession) -> TestClient:
    """실제 서비스를 타는 클라이언트 — compute_concept_diagnoses만 외부에서 주입한다."""
    app = create_app(provider=_StubProvider())
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings()

    async def _sess() -> AsyncIterator[object]:
        yield session

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_step_panel_in_response_body_when_path_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """④ 있음 방향: 시도 문항에 승격 경로 실재 → 응답 실바디 elements에 step_panel이 실린다."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    session = _WireSession(
        _wire_concept_orm(),
        queue=[
            [],  # ① 활성 가설 없음
            [],  # ② 증거 없음
            [(uuid.uuid4(), uuid.uuid4())],  # ③ 앵커 후보 1건
            ["sp-wire-1"],  # ④ 경로 실재
        ],
    )
    resp = _wire_client(session).post(_PATH)
    assert resp.status_code == 200
    body = resp.json()
    panels = [el for el in body["elements"] if el["kind"] == "step_panel"]
    assert len(panels) == 1
    assert panels[0]["solution_path_id"] == "sp-wire-1"
    # 답 미루기 스키마 강제가 응답 본문에서도 불변 — deferred 한 값만.
    assert panels[0]["reveal_policy"] == "deferred"
    # 실바디가 검증 게이트를 그대로 통과하는 유효 명세다(직렬화 라운드트립).
    parse_learning_scene(body)


def test_step_panel_absent_in_response_body_when_no_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """④ 없음 방향(경로 부재): 시도 문항은 있으나 승격 경로 0 → 실바디에 step_panel 미탑재."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    session = _WireSession(
        _wire_concept_orm(),
        queue=[
            [],
            [],
            [(uuid.uuid4(), uuid.uuid4())],  # 앵커 후보 1건
            [],  # 경로 없음(first() → None)
        ],
    )
    resp = _wire_client(session).post(_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert all(el["kind"] != "step_panel" for el in body["elements"])


def test_step_panel_absent_in_response_body_when_no_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """④ 없음 방향(앵커 부재): 시도 이력 0 → 경로 조회 없이 step_panel 미탑재(빈 껍데기 금지)."""
    monkeypatch.setattr(_DIAG_FN, _fake_diagnoses([_diagnosis()]))
    session = _WireSession(
        _wire_concept_orm(),
        queue=[[], [], []],  # 가설·증거·앵커 전부 빈 목록
    )
    resp = _wire_client(session).post(_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert all(el["kind"] != "step_panel" for el in body["elements"])
