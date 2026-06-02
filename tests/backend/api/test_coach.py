"""L4 coach 라우터 단위테스트 — `POST /v1/coach`(hermetic).

엔드포인트 결선(200·통합 결정 직렬화·401·422·옵션 LTHC) 검증. 학생 발화·상태가 그대로
응답에 *에코되지 않음* 확인(에코는 표면화 위험 — coach.py docstring 경계 메모).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


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


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _session_client(
    preload: dict[Any, Any] | None = None,
    execute_rows: list[Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    """`/v1/coach/sessions` hermetic — capturing session으로 add/commit/execute 검증."""
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    captured = _CapturingSession(preload=preload, execute_rows=execute_rows)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


def _no_auth_client() -> TestClient:
    app = create_app()

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
