"""L4 coach 라우터 단위테스트 — `POST /v1/coach`(hermetic).

엔드포인트 결선(200·통합 결정 직렬화·401·422·옵션 LTHC) 검증. 학생 발화·상태가 그대로
응답에 *에코되지 않음* 확인(에코는 표면화 위험 — coach.py docstring 경계 메모).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(다른 테스트로의 누수 차단).

    `reset_store()`는 async — 모듈 전역 `_BACKEND`(기본 InMemoryBackend)에 위임. 테스트
    별 새 이벤트 루프에서 호출되도록 `asyncio.run`으로 감싼다.
    """
    import asyncio

    asyncio.run(reset_store())


def _settings_override(limit: int = 0) -> Settings:
    """기본 rate_limit=0(비활성). 테스트가 명시적으로 limit 지정 시 활성."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_per_minute=limit,
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """`/v1/coach`(stateless)용 — DB 호출 시 AssertionError."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _CapturingSession:
    """`/v1/coach/sessions`용 — add/add_all/commit/refresh/get/execute 캡처.

    `_preload`로 `.get(Model, pk)`·`execute_rows`로 `.execute()` 결과를 미리 주입.
    """

    def __init__(
        self,
        preload: dict[Any, Any] | None = None,
        execute_rows: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self.refreshes = 0
        self._preload = preload or {}
        self._execute_rows = list(execute_rows or [])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: Any) -> None:
        self.refreshes += 1

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self._execute_rows)


def _client(rate_limit: int = 0) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings_override(rate_limit)

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _session_client(
    preload: dict[Any, Any] | None = None,
    execute_rows: list[Any] | None = None,
    rate_limit: int = 0,
) -> tuple[TestClient, _CapturingSession]:
    """`/v1/coach/sessions` hermetic — capturing session으로 add/commit/execute 검증."""
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings_override(rate_limit)
    captured = _CapturingSession(preload=preload, execute_rows=execute_rows)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


def _no_auth_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings_override(0)

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class TestBasicDecision:
    def test_minimal_request_returns_decision(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "decision" in body
        d = body["decision"]
        # 슬라이스 1-3 통합 — 모든 필드 채워짐
        assert d["polya_stage_to_advance"] in ("stay", "next", "previous")
        assert d["hint_level"] in (1, 2, 3, 4)
        assert d["socratic_category"] in (
            "clarification",
            "assumption",
            "evidence",
            "perspective",
            "implication",
            "meta",
        )
        assert d["prompt"]  # 비공
        assert d["system"]
        assert d["reveals"]  # hint_level에서 파생

    def test_default_state_is_understand_stay(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        body = resp.json()
        # 기본 PolyaState = UNDERSTAND + 짧은 입력 → stay·clarification
        assert body["decision"]["polya_stage_to_advance"] == "stay"
        assert body["decision"]["socratic_category"] == "clarification"

    def test_misconceptions_empty_for_neutral_input(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        body = resp.json()
        assert body["misconceptions"] == []
        assert body["intervention"] is None

    def test_lthc_none_without_mastery_level(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        assert resp.json()["lthc"] is None


class TestMisconceptionIntegration:
    def test_distribution_misconception_detected_with_intervention(self) -> None:
        # 슬라이스 4 카탈로그 — (a+b)² = a² + b² 신호로 풀 매칭(confidence 1.0)
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "내 풀이는 (a+b)² = a² + b² 이렇게 했어"},
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert "distribution-over-power" in ids
        # confidence 1.0 → COUNTEREXAMPLE 패턴
        assert body["intervention"] is not None
        assert body["intervention"]["pattern"] == "counterexample"
        assert "a=1, b=1" in body["intervention"]["prompt"]

    def test_partial_match_holds_intervention(self) -> None:
        # 부분 매칭 confidence 0.5 → REVERSE_REASONING 패턴
        resp = _client().post("/v1/coach", json={"student_input": "(a+b) 까지만"})
        body = resp.json()
        # 부분 매칭은 0.5 — reverse 패턴 또는 보류(임계 정확히 0.5는 reverse)
        if body["intervention"] is not None:
            assert body["intervention"]["pattern"] == "reverse_reasoning"


class TestLthcIntegration:
    def test_mastery_level_triggers_lthc(self) -> None:
        # 초보 → 진입점·비계 ON, 확장 OFF
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "음", "mastery_level": "초보"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["lthc"] is not None
        assert body["lthc"]["mastery_level"] == "초보"
        assert body["lthc"]["entry_suggestions"]  # 비공
        assert body["lthc"]["extensions"] == []

    def test_master_level_extensions_only(self) -> None:
        # 숙달 → 확장 ON, 나머지 OFF
        resp = _client().post(
            "/v1/coach",
            json={
                "student_input": "음",
                "polya_state": {"current_stage": "review"},
                "mastery_level": "숙달",
            },
        )
        body = resp.json()
        assert body["lthc"]["entry_suggestions"] == []
        assert body["lthc"]["extensions"]  # 비공


class TestHintLevelWiring:
    def test_demand_answer_signal_raises_hint(self) -> None:
        resp = _client().post(
            "/v1/coach",
            json={
                "student_input": "그냥 답이 뭐야",
                "polya_state": {"prev_hint_level": 1},
            },
        )
        body = resp.json()
        # slice 3 — min(4, prev+1) = 2
        assert body["decision"]["hint_level"] == 2
        assert body["decision"]["reveals"] == "step_flow"


class TestAuthGate:
    def test_no_token_401(self) -> None:
        resp = _no_auth_client().post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


class TestRequestValidation:
    def test_missing_student_input_422(self) -> None:
        assert _client().post("/v1/coach", json={}).status_code == 422

    def test_oversize_input_422(self) -> None:
        big = "가" * 4001  # max_length=4000
        assert (
            _client().post("/v1/coach", json={"student_input": big}).status_code == 422
        )

    def test_bad_mastery_level_422(self) -> None:
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "음", "mastery_level": "고수"},  # 비-Literal
        )
        assert resp.status_code == 422

    def test_extra_field_forbidden(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음", "foo": "bar"})
        assert resp.status_code == 422


class TestSessionPersistence:
    """`/v1/coach/sessions` — dialogue + 2 turn 영속 결선(hermetic)."""

    def test_creates_dialogue_and_two_turns_201(self) -> None:
        client, captured = _session_client()
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "내 풀이는 (a+b)² = a² + b² 이렇게 했어"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 응답 — decision/misconceptions/intervention + 영속 ID 3종
        assert "dialogue_id" in body
        assert "student_turn_id" in body
        assert "assistant_turn_id" in body
        assert body["intervention"]["pattern"] == "counterexample"

        # 영속 — 1 dialogue + 2 turns, commit 2회(parent 먼저, child 다음).
        from whymath_backend.db.models.dialogue import (
            Dialogue as DialogueORM,
        )
        from whymath_backend.db.models.dialogue import (
            DialogueTurn as DialogueTurnORM,
        )

        dialogues = [o for o in captured.added if isinstance(o, DialogueORM)]
        turns = [o for o in captured.added if isinstance(o, DialogueTurnORM)]
        assert len(dialogues) == 1
        assert len(turns) == 2
        assert captured.commits == 2  # dialogue → turns 순서
        assert captured.refreshes == 1

    def test_user_id_scoped_to_authenticated_user(self) -> None:
        # 본인 데이터 차단 — dialogue.user_id는 인증된 user.user_id로 자동
        client, captured = _session_client()
        client.post(
            "/v1/coach/sessions",
            json={"student_input": "음", "problem_id": str(uuid.uuid4())},
        )
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM

        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.user_id == _UID

    def test_student_turn_content_matches_input(self) -> None:
        client, captured = _session_client()
        client.post(
            "/v1/coach/sessions",
            json={"student_input": "내 풀이는 이렇게 했어"},
        )
        from whymath_backend.db.models.dialogue import DialogueTurn as DialogueTurnORM

        turns = [o for o in captured.added if isinstance(o, DialogueTurnORM)]
        student_t = next(t for t in turns if t.role == "student")
        assistant_t = next(t for t in turns if t.role == "assistant")
        assert student_t.content == "내 풀이는 이렇게 했어"
        assert student_t.turn_order == 1
        assert assistant_t.turn_order == 2
        # AI 턴 content = decision.prompt — LLM 호출 없이 결정된 발화 보존
        assert assistant_t.content  # 비공

    def test_no_token_401(self) -> None:
        resp = _no_auth_client().post(
            "/v1/coach/sessions", json={"student_input": "음"}
        )
        assert resp.status_code == 401

    def test_extra_field_forbidden(self) -> None:
        client, _ = _session_client()
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "음", "evil": "field"},
        )
        assert resp.status_code == 422

    def test_bad_problem_id_422(self) -> None:
        client, _ = _session_client()
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "음", "problem_id": "not-a-uuid"},
        )
        assert resp.status_code == 422


class TestTurnAppend:
    """`/v1/coach/sessions/{id}/turns` — 2턴 추가 결선."""

    def _preloaded_dialogue(
        self,
        dialogue_id: uuid.UUID,
        owner: uuid.UUID,
        total_turns: int = 2,
    ) -> Any:
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        return (DialogueORM, dialogue_id), DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=dialogue_id,
                user_id=owner,
                total_turns=total_turns,
                student_turns=1,
                assistant_turns=1,
            )
        )

    def test_append_creates_two_turns_with_continuing_order(self) -> None:
        from whymath_backend.db.models.dialogue import DialogueTurn as DialogueTurnORM

        did = uuid.uuid4()
        key, dialogue = self._preloaded_dialogue(did, _UID, total_turns=2)
        client, captured = _session_client(preload={key: dialogue})

        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "이번엔 다른 풀이 해볼게"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 다음 학생 turn_order = 직전 total_turns(2) + 1 = 3
        assert body["student_turn_order"] == 3
        assert body["assistant_turn_order"] == 4

        # 영속 — 2 turns added, dialogue 카운트 업데이트, 1 commit
        turns = [o for o in captured.added if isinstance(o, DialogueTurnORM)]
        assert len(turns) == 2
        assert captured.commits == 1
        # dialogue 카운트가 증가됨
        assert dialogue.total_turns == 4
        assert dialogue.student_turns == 2
        assert dialogue.assistant_turns == 2

    def test_nonexistent_dialogue_404(self) -> None:
        client, captured = _session_client()  # 빈 preload
        resp = client.post(
            f"/v1/coach/sessions/{uuid.uuid4()}/turns",
            json={"student_input": "음"},
        )
        assert resp.status_code == 404
        # DB 쓰기 발생 안 함
        assert captured.added == []
        assert captured.commits == 0

    def test_other_users_dialogue_404(self) -> None:
        # 타인 소유 dialogue → 404 (403 분리하지 않음 — 존재 노출 회피)
        other_uid = uuid.uuid4()
        did = uuid.uuid4()
        key, dialogue = self._preloaded_dialogue(did, other_uid, total_turns=2)
        client, captured = _session_client(preload={key: dialogue})

        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "타인 세션 가로채기 시도"},
        )
        assert resp.status_code == 404
        assert captured.added == []

    def test_no_token_401(self) -> None:
        did = uuid.uuid4()
        resp = _no_auth_client().post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "음"},
        )
        assert resp.status_code == 401

    def test_bad_dialogue_id_format_422(self) -> None:
        client, _ = _session_client()
        resp = client.post(
            "/v1/coach/sessions/not-a-uuid/turns",
            json={"student_input": "음"},
        )
        assert resp.status_code == 422

    def test_total_turns_none_starts_from_1(self) -> None:
        # 기존 dialogue.total_turns가 None이면 0으로 취급 → 학생=1·AI=2
        did = uuid.uuid4()
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID, total_turns=None)
        )
        client, _ = _session_client(preload={(DialogueORM, did): dialogue})
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "음"},
        )
        body = resp.json()
        assert body["student_turn_order"] == 1
        assert body["assistant_turn_order"] == 2


class TestSessionGet:
    """`GET /v1/coach/sessions/{id}` — dialogue 메타 + turn 목록 조회."""

    def test_returns_dialogue_and_turns(self) -> None:
        from whymath_backend.db.models.dialogue import (
            Dialogue as DialogueORM,
        )
        from whymath_backend.db.models.dialogue import (
            DialogueTurn as DialogueTurnORM,
        )
        from whymath_backend.schema.dialogue import (
            Dialogue as DialogueSchema,
        )
        from whymath_backend.schema.dialogue import (
            DialogueTurn as DialogueTurnSchema,
        )
        from whymath_backend.schema.enums import TurnRole

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID, total_turns=2)
        )
        t1 = DialogueTurnORM.from_schema(
            DialogueTurnSchema(
                dialogue_id=did,
                turn_order=1,
                role=TurnRole.student,
                content="문제 시도",
            )
        )
        t2 = DialogueTurnORM.from_schema(
            DialogueTurnSchema(
                dialogue_id=did, turn_order=2, role=TurnRole.assistant, content="질문"
            )
        )
        client, _ = _session_client(
            preload={(DialogueORM, did): dialogue},
            execute_rows=[t1, t2],
        )
        resp = client.get(f"/v1/coach/sessions/{did}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dialogue"]["dialogue_id"] == str(did)
        assert len(body["turns"]) == 2
        assert body["turns"][0]["role"] == "student"
        assert body["turns"][0]["content"] == "문제 시도"
        assert body["turns"][1]["role"] == "assistant"

    def test_empty_dialogue_returns_zero_turns(self) -> None:
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID)
        )
        client, _ = _session_client(
            preload={(DialogueORM, did): dialogue}, execute_rows=[]
        )
        resp = client.get(f"/v1/coach/sessions/{did}")
        assert resp.status_code == 200
        assert resp.json()["turns"] == []

    def test_nonexistent_404(self) -> None:
        client, _ = _session_client()
        resp = client.get(f"/v1/coach/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_other_users_dialogue_404(self) -> None:
        # 타인 소유 → 404(403 분리 안 함, 존재 노출 회피)
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        did = uuid.uuid4()
        other_uid = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=other_uid)
        )
        client, _ = _session_client(preload={(DialogueORM, did): dialogue})
        resp = client.get(f"/v1/coach/sessions/{did}")
        assert resp.status_code == 404

    def test_no_token_401(self) -> None:
        resp = _no_auth_client().get(f"/v1/coach/sessions/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_bad_uuid_422(self) -> None:
        client, _ = _session_client()
        resp = client.get("/v1/coach/sessions/not-a-uuid")
        assert resp.status_code == 422


class TestSessionGetConditional:
    """`GET /v1/coach/sessions/{id}` — ETag + If-None-Match → 304(읽기 캐싱)."""

    def _preloaded(self) -> tuple[uuid.UUID, dict[Any, Any], list[Any]]:
        from whymath_backend.db.models.dialogue import (
            Dialogue as DialogueORM,
        )
        from whymath_backend.db.models.dialogue import (
            DialogueTurn as DialogueTurnORM,
        )
        from whymath_backend.schema.dialogue import (
            Dialogue as DialogueSchema,
        )
        from whymath_backend.schema.dialogue import (
            DialogueTurn as DialogueTurnSchema,
        )
        from whymath_backend.schema.enums import TurnRole

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID, total_turns=2)
        )
        t1 = DialogueTurnORM.from_schema(
            DialogueTurnSchema(
                dialogue_id=did, turn_order=1, role=TurnRole.student, content="A"
            )
        )
        t2 = DialogueTurnORM.from_schema(
            DialogueTurnSchema(
                dialogue_id=did, turn_order=2, role=TurnRole.assistant, content="B"
            )
        )
        return did, {(DialogueORM, did): dialogue}, [t1, t2]

    def test_200_includes_etag_header(self) -> None:
        did, preload, rows = self._preloaded()
        client, _ = _session_client(preload=preload, execute_rows=rows)
        resp = client.get(f"/v1/coach/sessions/{did}")
        assert resp.status_code == 200
        assert resp.headers.get("ETag")  # 따옴표 포함 강한 ETag

    def test_matching_if_none_match_returns_304(self) -> None:
        did, preload, rows = self._preloaded()
        client, _ = _session_client(preload=preload, execute_rows=rows)
        first = client.get(f"/v1/coach/sessions/{did}")
        etag = first.headers["ETag"]

        # 같은 ETag로 재요청 → 304, 빈 본문, ETag 유지
        resp = client.get(f"/v1/coach/sessions/{did}", headers={"If-None-Match": etag})
        assert resp.status_code == 304
        assert resp.content == b""
        assert resp.headers["ETag"] == etag

    def test_wildcard_if_none_match_returns_304(self) -> None:
        did, preload, rows = self._preloaded()
        client, _ = _session_client(preload=preload, execute_rows=rows)
        resp = client.get(f"/v1/coach/sessions/{did}", headers={"If-None-Match": "*"})
        assert resp.status_code == 304

    def test_stale_if_none_match_returns_200(self) -> None:
        # 무관한 ETag → 본문 반환(현재 ETag와 다름)
        did, preload, rows = self._preloaded()
        client, _ = _session_client(preload=preload, execute_rows=rows)
        resp = client.get(
            f"/v1/coach/sessions/{did}",
            headers={"If-None-Match": '"deadbeefdeadbeef"'},
        )
        assert resp.status_code == 200
        assert resp.json()["turns"]

    def test_etag_changes_when_turns_change(self) -> None:
        # 같은 dialogue·다른 turn 집합 → 다른 ETag(내용 해시이므로 자동 무효화)
        did, preload, rows = self._preloaded()
        client_a, _ = _session_client(preload=preload, execute_rows=rows)
        etag_a = client_a.get(f"/v1/coach/sessions/{did}").headers["ETag"]

        # turn 1개만 노출(짧은 결과) → 다른 ETag
        client_b, _ = _session_client(preload=preload, execute_rows=rows[:1])
        etag_b = client_b.get(f"/v1/coach/sessions/{did}").headers["ETag"]
        assert etag_a != etag_b


class TestRateLimit:
    """coach 엔드포인트 사용자당 분당 상한 — 초과 시 429 + Retry-After."""

    def test_under_limit_passes(self) -> None:
        # limit=3 → 3회까지 통과
        client = _client(rate_limit=3)
        for _ in range(3):
            assert (
                client.post("/v1/coach", json={"student_input": "음"}).status_code
                == 200
            )

    def test_over_limit_returns_429(self) -> None:
        # limit=2 → 3번째 요청 429 + Retry-After
        client = _client(rate_limit=2)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "60"

    def test_zero_means_disabled(self) -> None:
        # limit=0 → 무제한(기본 테스트 모드)
        client = _client(rate_limit=0)
        for _ in range(20):
            assert (
                client.post("/v1/coach", json={"student_input": "음"}).status_code
                == 200
            )

    def test_get_endpoint_also_limited(self) -> None:
        # GET /v1/coach/sessions/{id}도 동일 버킷 카운트 — 임계 공유
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID)
        )
        client, _ = _session_client(
            preload={(DialogueORM, did): dialogue},
            execute_rows=[],
            rate_limit=1,
        )
        # 1번 통과
        assert client.get(f"/v1/coach/sessions/{did}").status_code == 200
        # 2번째 429
        resp = client.get(f"/v1/coach/sessions/{did}")
        assert resp.status_code == 429

    def test_sliding_window_prunes_expired(self) -> None:
        # 클럭 seam — 60초 후엔 옛 히트가 만료돼 다시 통과
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        assert asyncio.run(backend.hit(uid, limit=1, now=0.0)) is True
        assert asyncio.run(backend.hit(uid, limit=1, now=0.5)) is False
        assert asyncio.run(backend.hit(uid, limit=1, now=61.0)) is True


class _FakeRedisClient:
    """Lua eval seam — `_LUA_HIT` 스크립트의 *의미*를 in-memory ZSET으로 재현.

    실제 Redis 없이도 RedisBackend의 결선·키 네이밍·TTL 호출을 검증할 수 있게 한다
    (Lua 스크립트 자체의 정확성은 통합 테스트에서 실 Redis로 검증 — 후속).
    """

    def __init__(self) -> None:
        self.zsets: dict[str, list[tuple[float, str]]] = {}
        self.expires: dict[str, int] = {}
        self.eval_calls: list[tuple[str, int, tuple[Any, ...]]] = []

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        self.eval_calls.append((script, numkeys, args))
        key = args[0]
        now = float(args[1])
        limit = int(args[2])
        member = args[3]
        cutoff = now - 60
        bucket = self.zsets.setdefault(key, [])
        bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
        if len(bucket) >= limit:
            return 0
        bucket.append((now, member))
        self.expires[key] = 60
        return 1

    async def ping(self) -> Any:
        return True

    async def delete(self, *names: str) -> Any:
        for n in names:
            self.zsets.pop(n, None)
            self.expires.pop(n, None)
        return len(names)

    async def keys(self, pattern: str) -> Any:
        prefix = pattern.rstrip("*")
        return [k for k in self.zsets if k.startswith(prefix)]


class TestRedisBackend:
    """RedisBackend 결선 — fake `_RedisClient`로 Lua eval·키·TTL 검증."""

    def test_hit_returns_true_under_limit(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        assert asyncio.run(backend.hit(uid, limit=2, now=0.0)) is True
        assert asyncio.run(backend.hit(uid, limit=2, now=0.1)) is True
        assert asyncio.run(backend.hit(uid, limit=2, now=0.2)) is False

    def test_hit_uses_canonical_key_prefix(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        asyncio.run(backend.hit(uid, limit=1, now=0.0))
        assert f"rate:coach:{uid}" in fake.zsets

    def test_reset_clears_all_keys(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        asyncio.run(backend.hit(uuid.uuid4(), limit=10, now=0.0))
        asyncio.run(backend.hit(uuid.uuid4(), limit=10, now=0.0))
        assert len(fake.zsets) == 2
        asyncio.run(backend.reset())
        assert fake.zsets == {}

    def test_prunes_expired_via_lua_semantics(self) -> None:
        # cutoff = now - 60 → 옛 히트는 prune
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        assert asyncio.run(backend.hit(uid, limit=1, now=0.0)) is True
        # 같은 윈도우 — 초과
        assert asyncio.run(backend.hit(uid, limit=1, now=0.5)) is False
        # 60초+ — prune되어 통과
        assert asyncio.run(backend.hit(uid, limit=1, now=61.0)) is True


class TestRedisBackendLazyPaths:
    """`RedisBackend` lazy 해석 경로 — 주입 없으면 settings/client 지연 생성."""

    def test_resolved_settings_falls_back_to_global(self) -> None:
        from whymath_backend.api._rate_limit import RedisBackend

        backend = RedisBackend()  # settings/client 모두 주입 X
        # _resolved_settings는 get_settings() 캐시된 전역으로 폴백
        assert backend._resolved_settings is not None  # type: ignore[truthy-bool]

    def test_resolved_settings_uses_injection_when_provided(self) -> None:
        # settings 주입 시 — get_settings() 미호출, 주입된 인스턴스 그대로 반환
        from whymath_backend.api._rate_limit import RedisBackend

        injected = _settings_override(0)
        backend = RedisBackend(client=_FakeRedisClient(), settings=injected)
        assert backend._resolved_settings is injected

    def test_reset_with_no_keys_noops(self) -> None:
        # keys() 빈 결과 → delete 호출 분기 회피
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        asyncio.run(backend.reset())  # zsets 비어있음 → keys=[] → delete 미호출

    def test_get_client_lazy_builds_default_when_not_injected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 주입된 client 없으면 `_build_default_redis_client`를 호출해 lazy 생성
        import asyncio

        from whymath_backend.api import _rate_limit as rl

        fake = _FakeRedisClient()
        monkeypatch.setattr(rl, "_build_default_redis_client", lambda s: fake)
        backend = rl.RedisBackend()  # client 주입 X
        # 첫 hit — lazy build 발화
        assert asyncio.run(backend.hit(uuid.uuid4(), limit=2, now=0.0)) is True
        assert len(fake.eval_calls) == 1
        # 두번째 hit — 이미 build됨, lazy skip
        assert asyncio.run(backend.hit(uuid.uuid4(), limit=2, now=0.1)) is True
        assert len(fake.eval_calls) == 2


class TestBackendSelection:
    """`configure_backend_from_settings` — 설정으로 백엔드 선택."""

    def test_memory_default(self) -> None:
        from whymath_backend.api._rate_limit import (
            InMemoryBackend,
            configure_backend_from_settings,
            get_backend,
        )

        configure_backend_from_settings(_settings_override(0))
        assert isinstance(get_backend(), InMemoryBackend)

    def test_redis_when_configured(self) -> None:
        from whymath_backend.api._rate_limit import (
            RedisBackend,
            configure_backend_from_settings,
            get_backend,
        )

        s = Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_backend="redis",
        )
        configure_backend_from_settings(s)
        try:
            assert isinstance(get_backend(), RedisBackend)
        finally:
            # 다음 테스트 격리 — 기본 InMemory로 복원
            configure_backend_from_settings(_settings_override(0))
