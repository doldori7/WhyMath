"""GET /v1/solution-paths/{id}/steps 단위테스트 — 서버 측 점층 공개(up_to 슬라이스). SOL-02.

라이브 DB 없음: dependency_overrides(get_consented_user·get_session) + 가짜 세션(execute 큐)으로
store 조회를 hermetic 모사한다(test_scene_endpoint 패턴 답습). 변별력 포인트는 **응답 실바디의
슬라이스** — 기본 1단계만·up_to 슬라이스·total 클램프·미존재 404·무인증 401을 양방향으로 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_PATH_ID = "sp-wire-1"


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출(DB 읽기 전용 엔드포인트)."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


class _FakeStepRow:
    """`problem_step` 행 모사 — 엔드포인트가 읽는 2필드(step_order·expected_answer)만."""

    def __init__(self, step_order: int, content: str) -> None:
        self.step_order = step_order
        self.expected_answer = content


class _QueueResult:
    """execute 결과 모사 — scalars()→first()(헤더 단건)·scalars()→all()(단계 목록) 표면."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _QueueResult:
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[object]:
        return list(self._rows)


class _QueueSession:
    """execute()가 호출 순서대로 큐 결과를 반환 — ① 경로 헤더 조회 ② 단계 목록 조회."""

    def __init__(self, results: list[list[object]]) -> None:
        self._results = list(results)

    async def execute(self, _stmt: object) -> _QueueResult:
        return _QueueResult(self._results.pop(0))


def _steps(n: int) -> list[object]:
    """step_order 1..n의 가짜 단계 행 — 내용은 'N단계 내용'(슬라이스 검증용 식별자)."""
    return [_FakeStepRow(i, f"{i}단계 내용") for i in range(1, n + 1)]


def _client(session: _QueueSession, *, authed: bool = True) -> TestClient:
    app = create_app(provider=_StubProvider())
    if authed:

        def _user() -> UserProfile:
            return UserProfile.from_schema(
                UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
            )

        app.dependency_overrides[get_consented_user] = _user

    async def _sess() -> AsyncIterator[_QueueSession]:
        yield session

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _client_with_steps(step_rows: list[object], *, authed: bool = True) -> TestClient:
    """경로 실재(헤더 1건) + 주어진 단계 행을 반환하는 클라이언트."""
    return _client(_QueueSession([[object()], step_rows]), authed=authed)


def test_default_up_to_returns_first_step_only() -> None:
    """① up_to 생략 → 기본 1 — 첫 단계만 내려간다(점층 공개 기본 자세·답 미루기)."""
    resp = _client_with_steps(_steps(3)).get(f"/v1/solution-paths/{_PATH_ID}/steps")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["up_to"] == 1
    assert body["steps"] == [{"step_order": 1, "content": "1단계 내용"}]


def test_up_to_two_returns_slice() -> None:
    """② up_to=2 → 1·2단계만 — 미펼침 3단계 내용은 응답에 없다(서버 측 슬라이스 실측)."""
    resp = _client_with_steps(_steps(3)).get(f"/v1/solution-paths/{_PATH_ID}/steps?up_to=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["up_to"] == 2
    assert body["steps"] == [
        {"step_order": 1, "content": "1단계 내용"},
        {"step_order": 2, "content": "2단계 내용"},
    ]
    assert "3단계 내용" not in resp.text  # 미펼침 단계는 본문 어디에도 없다


def test_up_to_clamps_at_total() -> None:
    """③ up_to가 총수 초과 → total로 클램프(넘침은 에러가 아니라 전부 공개)."""
    resp = _client_with_steps(_steps(3)).get(f"/v1/solution-paths/{_PATH_ID}/steps?up_to=99")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["up_to"] == 3
    assert [s["step_order"] for s in body["steps"]] == [1, 2, 3]


def test_unknown_path_404() -> None:
    """④ 경로 미존재(헤더 조회 None) → 404 — 댕글링 id에 빈 200을 주지 않는다."""
    client = _client(_QueueSession([[]]))  # 헤더 조회가 first() → None
    resp = client.get(f"/v1/solution-paths/{_PATH_ID}/steps")
    assert resp.status_code == 404


def test_unauthenticated_401() -> None:
    """⑤ 토큰 없음 → 401 — 정답류는 인증된 학생에게만(SEC-24 취지·무인증 공개 아님)."""
    resp = _client_with_steps(_steps(3), authed=False).get(f"/v1/solution-paths/{_PATH_ID}/steps")
    assert resp.status_code == 401


def test_up_to_zero_rejected_422() -> None:
    """up_to=0 → 422(Query ge=1) — 0단계 공개라는 퇴화 요청은 계약 밖."""
    resp = _client_with_steps(_steps(3)).get(f"/v1/solution-paths/{_PATH_ID}/steps?up_to=0")
    assert resp.status_code == 422
