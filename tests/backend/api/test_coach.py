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


def _settings_override(
    limit: int = 0,
    write_limit: int | None = None,
    ip_limit: int = 0,
    ip_write_limit: int | None = None,
    device_limit: int = 0,
    device_write_limit: int | None = None,
    device_hmac_secret: str = "",
) -> Settings:
    """기본 모든 한도 0(비활성). `*_limit=None`이면 같은 read 인자와 동일.

    슬라이스 14/17/20/21 — 차등·방어 심층·3차원·디바이스 HMAC 서명. 모든 한도와 서명 검증
    secret을 기본 0/빈으로 두어 기존 테스트가 영향받지 않게 한다.
    """
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=limit,
        coach_rate_limit_write_per_minute=limit if write_limit is None else write_limit,
        coach_rate_limit_ip_read_per_minute=ip_limit,
        coach_rate_limit_ip_write_per_minute=(
            ip_limit if ip_write_limit is None else ip_write_limit
        ),
        coach_rate_limit_device_read_per_minute=device_limit,
        coach_rate_limit_device_write_per_minute=(
            device_limit if device_write_limit is None else device_write_limit
        ),
        coach_device_hmac_secret=SecretStr(device_hmac_secret),
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


class TestCoachingFocusSeed:
    """slice 23: coaching_focus → entry_socratic_category 시드(L2 진단→coach 결선)."""

    def test_none_focus_no_entry_category(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        assert resp.json()["entry_socratic_category"] is None

    def test_focus_seeds_entry_category(self) -> None:
        """consolidate → evidence(slice 22 매핑)."""
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "음", "coaching_focus": "consolidate"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["entry_socratic_category"] == "evidence"

    def test_all_focus_mappings(self) -> None:
        cases = {
            "consolidate": "evidence",
            "retrieval": "meta",
            "foundation": "clarification",
            "advance": "perspective",
            "diagnose": "clarification",
        }
        client = _client()
        for focus, expected in cases.items():
            resp = client.post(
                "/v1/coach", json={"student_input": "음", "coaching_focus": focus}
            )
            assert resp.json()["entry_socratic_category"] == expected, focus

    def test_invalid_focus_rejected_422(self) -> None:
        resp = _client().post(
            "/v1/coach", json={"student_input": "음", "coaching_focus": "bogus"}
        )
        assert resp.status_code == 422

    def test_session_create_includes_entry_category(self) -> None:
        """세션 생성 응답에도 진입 카테고리 시드 노출."""
        client, _ = _session_client()
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "음", "coaching_focus": "advance"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["entry_socratic_category"] == "perspective"


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
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.0)).allowed
            is True
        )
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.5)).allowed
            is False
        )
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=61.0)).allowed
            is True
        )


class _FakeRedisClient:
    """Lua evalsha/script_load seam — `_LUA_HIT` 스크립트의 *의미*를 in-memory ZSET으로 재현.

    실제 Redis 없이도 RedisBackend의 결선·키 네이밍·TTL 호출·EVALSHA 캐시 의미를 검증할 수
    있게 한다(Lua 스크립트 자체의 정확성은 통합 테스트에서 실 Redis로 검증).

    스크립트 캐시 모델: `script_load(script)`로 적재된 SHA만 evalsha가 인정. 적재 전 evalsha
    호출은 `NoScriptError`(redis-py 정본 예외)로 거절.
    """

    def __init__(self) -> None:
        self.zsets: dict[str, list[tuple[float, str]]] = {}
        self.expires: dict[str, int] = {}
        self.evalsha_calls: list[tuple[str, int, tuple[Any, ...]]] = []
        self.script_loads: list[str] = []
        self._loaded_shas: set[str] = set()

    def _apply_hit_script(self, args: tuple[Any, ...]) -> list[int]:
        """Lua 스크립트 의미 재현 — `[allowed, count_after, oldest_micros]` 반환."""
        key = args[0]
        now = float(args[1])
        limit = int(args[2])
        member = args[3]
        cutoff = now - 60
        bucket = self.zsets.setdefault(key, [])
        bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
        allowed = 1 if len(bucket) < limit else 0
        if allowed:
            bucket.append((now, member))
            self.expires[key] = 60
        oldest_micros = -1
        if bucket:
            oldest_micros = int(bucket[0][0] * 1_000_000)
        return [allowed, len(bucket), oldest_micros]

    def _apply_hit_both_script(self, args: tuple[Any, ...]) -> list[int]:
        """Lua _LUA_HIT_BOTH 의미 재현 — 원자 user+IP 검사. 5-튜플 반환."""
        user_key = args[0]
        ip_key = args[1]
        now = float(args[2])
        user_limit = int(args[3])
        ip_limit = int(args[4])
        member = args[5]
        cutoff = now - 60
        user_count = -1
        ip_count = -1
        user_ok = True
        ip_ok = True
        if user_limit > 0:
            bucket = self.zsets.setdefault(user_key, [])
            bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
            user_count = len(bucket)
            if user_count >= user_limit:
                user_ok = False
        if ip_limit > 0:
            bucket = self.zsets.setdefault(ip_key, [])
            bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
            ip_count = len(bucket)
            if ip_count >= ip_limit:
                ip_ok = False
        allowed = 1 if (user_ok and ip_ok) else 0
        if allowed:
            if user_limit > 0:
                self.zsets[user_key].append((now, member))
                self.expires[user_key] = 60
                user_count += 1
            if ip_limit > 0:
                self.zsets[ip_key].append((now, member))
                self.expires[ip_key] = 60
                ip_count += 1
        user_oldest = -1
        ip_oldest = -1
        if user_limit > 0 and self.zsets.get(user_key):
            user_oldest = int(self.zsets[user_key][0][0] * 1_000_000)
        if ip_limit > 0 and self.zsets.get(ip_key):
            ip_oldest = int(self.zsets[ip_key][0][0] * 1_000_000)
        return [allowed, user_count, user_oldest, ip_count, ip_oldest]

    def _apply_hit_many_script(self, numkeys: int, args: tuple[Any, ...]) -> list[int]:
        """Lua _LUA_HIT_MANY 의미 재현 — KEYS 가변·ARGV [now, member, limit1..limitN]."""
        keys = list(args[:numkeys])
        now = float(args[numkeys])
        member = args[numkeys + 1]
        limits = [int(x) for x in args[numkeys + 2 : numkeys + 2 + numkeys]]
        cutoff = now - 60
        for k in keys:
            bucket = self.zsets.setdefault(k, [])
            bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
        counts = [len(self.zsets[k]) for k in keys]
        all_ok = all(c < lim for c, lim in zip(counts, limits))
        if all_ok:
            for i, k in enumerate(keys):
                self.zsets[k].append((now, member))
                self.expires[k] = 60
                counts[i] += 1
        response: list[int] = [1 if all_ok else 0]
        for i, k in enumerate(keys):
            response.append(counts[i])
            oldest = -1
            if self.zsets[k]:
                oldest = int(self.zsets[k][0][0] * 1_000_000)
            response.append(oldest)
        return response

    async def evalsha(self, sha: str, numkeys: int, *args: Any) -> Any:
        self.evalsha_calls.append((sha, numkeys, args))
        if sha not in self._loaded_shas:
            from redis.exceptions import NoScriptError

            raise NoScriptError("NOSCRIPT No matching script. Use SCRIPT LOAD.")
        # SHA로 분기 — _LUA_HIT_MANY / _LUA_HIT_BOTH / _LUA_HIT
        from whymath_backend.api._rate_limit import (
            _LUA_HIT_BOTH_SHA1,
            _LUA_HIT_MANY_SHA1,
        )

        if sha == _LUA_HIT_MANY_SHA1:
            return self._apply_hit_many_script(numkeys, args)
        if sha == _LUA_HIT_BOTH_SHA1:
            return self._apply_hit_both_script(args)
        return self._apply_hit_script(args)

    async def script_load(self, script: str) -> Any:
        self.script_loads.append(script)
        import hashlib

        sha = hashlib.sha1(script.encode("utf-8")).hexdigest()
        self._loaded_shas.add(sha)
        return sha

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
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=2, now=0.0)).allowed
            is True
        )
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=2, now=0.1)).allowed
            is True
        )
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=2, now=0.2)).allowed
            is False
        )

    def test_hit_uses_canonical_key_prefix(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        asyncio.run(backend.hit(uid, category="read", limit=1, now=0.0))
        assert f"rate:coach:read:user:{uid}" in fake.zsets

    def test_reset_clears_all_keys(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        asyncio.run(backend.hit(uuid.uuid4(), category="read", limit=10, now=0.0))
        asyncio.run(backend.hit(uuid.uuid4(), category="read", limit=10, now=0.0))
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
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.0)).allowed
            is True
        )
        # 같은 윈도우 — 초과
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.5)).allowed
            is False
        )
        # 60초+ — prune되어 통과
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=61.0)).allowed
            is True
        )


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
        # 첫 hit — lazy build 발화 + EVALSHA NOSCRIPT → script_load + 재시도
        assert (
            asyncio.run(
                backend.hit(uuid.uuid4(), category="read", limit=2, now=0.0)
            ).allowed
            is True
        )
        # 첫 hit: evalsha 2회(NOSCRIPT + 재시도), script_load 1회
        assert len(fake.evalsha_calls) == 2
        assert len(fake.script_loads) == 1
        # 두번째 hit — script 이미 캐시됨, evalsha 1회만(NOSCRIPT 없음)
        assert (
            asyncio.run(
                backend.hit(uuid.uuid4(), category="read", limit=2, now=0.1)
            ).allowed
            is True
        )
        assert len(fake.evalsha_calls) == 3
        assert len(fake.script_loads) == 1  # 추가 load 없음


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


class TestEvalshaOptimization:
    """슬라이스 13 — EVALSHA + NOSCRIPT 폴백 최적화 정합 검증."""

    def test_sha1_matches_redis_canonical(self) -> None:
        # `_LUA_HIT_SHA1`이 Redis SCRIPT LOAD가 반환할 정본 SHA와 같아야 EVALSHA 캐시 적중
        import hashlib

        from whymath_backend.api._rate_limit import _LUA_HIT, _LUA_HIT_SHA1

        expected = hashlib.sha1(_LUA_HIT.encode("utf-8")).hexdigest()
        assert _LUA_HIT_SHA1 == expected
        assert len(_LUA_HIT_SHA1) == 40  # SHA1 hex

    def test_first_hit_triggers_script_load_then_evalsha(self) -> None:
        # 빈 스크립트 캐시 → 첫 evalsha NOSCRIPT → script_load → 재시도 → 성공
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        assert (
            asyncio.run(
                backend.hit(uuid.uuid4(), category="read", limit=2, now=0.0)
            ).allowed
            is True
        )
        assert fake.script_loads == [
            __import__(
                "whymath_backend.api._rate_limit", fromlist=["_LUA_HIT"]
            )._LUA_HIT
        ]
        assert len(fake.evalsha_calls) == 2  # 1회 NOSCRIPT + 1회 재시도

    def test_subsequent_hits_use_cached_script(self) -> None:
        # 두번째 호출부터는 evalsha 1회만(NOSCRIPT 없음·script_load 추가 호출 없음)
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        asyncio.run(backend.hit(uuid.uuid4(), category="read", limit=10, now=0.0))
        evalsha_after_first = len(fake.evalsha_calls)
        loads_after_first = len(fake.script_loads)

        # 추가 5회 — 전부 evalsha 1회씩만
        for i in range(5):
            asyncio.run(
                backend.hit(uuid.uuid4(), category="read", limit=10, now=0.1 + i * 0.01)
            )
        assert len(fake.evalsha_calls) == evalsha_after_first + 5
        assert len(fake.script_loads) == loads_after_first  # 변동 없음

    def test_recovers_from_script_flush(self) -> None:
        # Redis가 SCRIPT FLUSH/재시작된 경우 시뮬레이션 — 캐시 비우면 다음 evalsha NOSCRIPT
        # → 자동으로 script_load + 재시도
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        asyncio.run(backend.hit(uuid.uuid4(), category="read", limit=10, now=0.0))
        assert len(fake.script_loads) == 1  # 첫 적재

        # Redis SCRIPT FLUSH 시뮬레이션
        fake._loaded_shas.clear()
        asyncio.run(backend.hit(uuid.uuid4(), category="read", limit=10, now=0.1))
        assert len(fake.script_loads) == 2  # 재적재 발화


class TestReadWriteSeparation:
    """슬라이스 14 — POST/GET 차등 한도. 두 카테고리 *별도 버킷*."""

    def test_write_limit_does_not_block_reads(self) -> None:
        # write_limit=1 소진 + read_limit=10 → read는 여전히 통과
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID)
        )

        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=10, write_limit=1
        )
        captured = _CapturingSession(
            preload={(DialogueORM, did): dialogue}, execute_rows=[]
        )

        async def _sess() -> AsyncIterator[_CapturingSession]:
            yield captured

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)

        # POST 1회 — write_limit=1 소진
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        # POST 2회 — 429(write 한도 초과)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 429
        # GET 여러 번 — read 한도(10)는 별도 버킷이라 영향 없음
        for _ in range(5):
            assert client.get(f"/v1/coach/sessions/{did}").status_code == 200

    def test_read_limit_does_not_block_writes(self) -> None:
        # read_limit=1 소진 + write_limit=10 → write는 여전히 통과
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        did = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(dialogue_id=did, user_id=_UID)
        )

        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=1, write_limit=10
        )
        captured = _CapturingSession(
            preload={(DialogueORM, did): dialogue}, execute_rows=[]
        )

        async def _sess() -> AsyncIterator[_CapturingSession]:
            yield captured

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)

        # GET 1회 — read_limit=1 소진
        assert client.get(f"/v1/coach/sessions/{did}").status_code == 200
        # GET 2회 — 429(read 한도 초과)
        assert client.get(f"/v1/coach/sessions/{did}").status_code == 429
        # POST 여러 번 — write 한도(10)는 별도 버킷이라 영향 없음
        for _ in range(5):
            assert (
                client.post("/v1/coach", json={"student_input": "음"}).status_code
                == 200
            )


class TestRateCategoryBackend:
    """`InMemoryBackend`·`RedisBackend`가 `category`별 *별도 버킷* 유지."""

    def test_inmemory_categories_isolated(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        # write 1/1 한도 도달
        assert (
            asyncio.run(backend.hit(uid, category="write", limit=1, now=0.0)).allowed
            is True
        )
        assert (
            asyncio.run(backend.hit(uid, category="write", limit=1, now=0.1)).allowed
            is False
        )
        # 같은 사용자의 read 버킷은 독립 — 영향 없음
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.2)).allowed
            is True
        )

    def test_redis_key_prefix_includes_category(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        asyncio.run(backend.hit(uid, category="read", limit=10, now=0.0))
        asyncio.run(backend.hit(uid, category="write", limit=10, now=0.0))
        assert f"rate:coach:read:user:{uid}" in fake.zsets
        assert f"rate:coach:write:user:{uid}" in fake.zsets


class TestRateLimitHeaders:
    """슬라이스 15 — X-RateLimit-* 응답 헤더(클라이언트 자체 throttle 입력)."""

    def test_200_includes_rate_limit_headers(self) -> None:
        client = _client(rate_limit=5)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "5"
        # 1회 사용 → 4 남음
        assert resp.headers["X-RateLimit-Remaining"] == "4"
        # 즉시 1슬롯 비기까지의 시간 ≤ 60(같은 초에 발급된 1개 → ~60초 후 비어짐)
        reset = int(resp.headers["X-RateLimit-Reset"])
        assert 0 <= reset <= 60

    def test_429_includes_rate_limit_headers_and_retry_after(self) -> None:
        client = _client(rate_limit=1)
        # 첫 호출 200
        first = client.post("/v1/coach", json={"student_input": "음"})
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Remaining"] == "0"
        # 두번째 호출 — 429
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "1"
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        # Retry-After = reset_seconds(>= 0). 0이면 사양상 "즉시" 의미라 본 실패서 1+ 권장.
        retry_after = int(resp.headers["Retry-After"])
        assert retry_after >= 1
        # X-RateLimit-Reset도 동봉
        assert int(resp.headers["X-RateLimit-Reset"]) >= 0

    def test_remaining_decrements_across_requests(self) -> None:
        client = _client(rate_limit=3)
        r1 = client.post("/v1/coach", json={"student_input": "음"})
        r2 = client.post("/v1/coach", json={"student_input": "음"})
        r3 = client.post("/v1/coach", json={"student_input": "음"})
        assert r1.headers["X-RateLimit-Remaining"] == "2"
        assert r2.headers["X-RateLimit-Remaining"] == "1"
        assert r3.headers["X-RateLimit-Remaining"] == "0"

    def test_zero_limit_no_headers_no_429(self) -> None:
        # limit=0이면 dep는 짧게 반환·헤더 미세팅
        client = _client(rate_limit=0)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers
        assert "X-RateLimit-Remaining" not in resp.headers


class TestRateLimitResultStruct:
    """`RateLimitResult` 결과 구조 — InMemoryBackend 직접 호출."""

    def test_first_hit_allowed_remaining_and_reset(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend, RateLimitResult

        backend = InMemoryBackend()
        result = asyncio.run(
            backend.hit(uuid.uuid4(), category="read", limit=5, now=100.0)
        )
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining == 4  # limit - 1
        # 60초 윈도우에 방금 추가 → reset ≈ 60
        assert result.reset_seconds == 60

    def test_denied_when_at_limit(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        asyncio.run(backend.hit(uid, category="read", limit=1, now=100.0))
        result = asyncio.run(backend.hit(uid, category="read", limit=1, now=100.5))
        assert result.allowed is False
        assert result.remaining == 0
        # 옛 항목이 100.0에 추가됨 → 100.5 시점엔 ~60초 후 만료
        assert result.reset_seconds == 60


class TestIpRateLimit:
    """슬라이스 16 — IP 단위 한도(미인증 표면). 사용자 키와 *네임스페이스 분리*."""

    def test_inmemory_ip_isolated_from_user(self) -> None:
        # 같은 prefix("read") 카테고리지만 user key와 ip key는 완전 분리
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        # 사용자 한도 1 소진
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.0)).allowed
            is True
        )
        assert (
            asyncio.run(backend.hit(uid, category="read", limit=1, now=0.1)).allowed
            is False
        )
        # 같은 사용자 *as IP*가 별도 키 — IP 한도는 별개
        assert (
            asyncio.run(
                backend.hit_by_ip(str(uid), category="read", limit=1, now=0.2)
            ).allowed
            is True
        )

    def test_redis_ip_key_prefix_explicit(self) -> None:
        # IP 키는 `rate:coach:{cat}:ip:{addr}` — 사용자 키와 충돌 X
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        ip = "203.0.113.42"
        uid = uuid.uuid4()
        asyncio.run(backend.hit_by_ip(ip, category="read", limit=10, now=0.0))
        asyncio.run(backend.hit(uid, category="read", limit=10, now=0.0))
        assert f"rate:coach:read:ip:{ip}" in fake.zsets
        assert f"rate:coach:read:user:{uid}" in fake.zsets

    def test_two_ips_independent_buckets(self) -> None:
        # 다른 IP는 같은 한도를 독립적으로 쓴다
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        assert (
            asyncio.run(
                backend.hit_by_ip("1.1.1.1", category="write", limit=1, now=0.0)
            ).allowed
            is True
        )
        # 다른 IP는 별도 버킷
        assert (
            asyncio.run(
                backend.hit_by_ip("2.2.2.2", category="write", limit=1, now=0.1)
            ).allowed
            is True
        )

    def test_x_forwarded_for_extraction(self) -> None:
        # `_client_ip`가 X-Forwarded-For 첫 항목을 우선 사용
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "198.51.100.1, 10.0.0.5"}
        request.client = MagicMock()
        request.client.host = "10.0.0.99"
        assert _client_ip(request) == "198.51.100.1"

    def test_direct_client_host_fallback(self) -> None:
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_ip

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.0.2.99"
        assert _client_ip(request) == "192.0.2.99"

    def test_no_client_returns_none(self) -> None:
        # request.client None → 알 수 없는 IP라 한도 미적용 신호
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_ip

        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _client_ip(request) is None

    def test_empty_xff_header_falls_back(self) -> None:
        # X-Forwarded-For: "  " (공백) → 빈 head → request.client.host로 폴백
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "   "}
        request.client = MagicMock()
        request.client.host = "192.0.2.50"
        assert _client_ip(request) == "192.0.2.50"

    def test_ip_dep_enforces_limit_via_test_endpoint(self) -> None:
        # 임시 미인증 엔드포인트로 IP dep 결선 검증
        from fastapi import APIRouter

        from whymath_backend.api._rate_limit import RateLimitedIpRead

        router = APIRouter()

        @router.get("/_test/ip-limited", dependencies=[RateLimitedIpRead])
        async def _hit() -> dict[str, bool]:
            return {"ok": True}

        app = create_app()
        app.include_router(router)
        # IP read 한도 1, write 0(영향 없음)
        app.dependency_overrides[get_settings] = lambda: Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_read_per_minute=0,
            coach_rate_limit_write_per_minute=0,
            coach_rate_limit_ip_read_per_minute=1,
        )
        client = TestClient(app)
        # 1회 통과
        r1 = client.get("/_test/ip-limited")
        assert r1.status_code == 200
        # 2회 429 + 헤더
        r2 = client.get("/_test/ip-limited")
        assert r2.status_code == 429
        assert r2.headers["X-RateLimit-Limit"] == "1"
        assert r2.headers["X-RateLimit-Remaining"] == "0"


class TestIpRateLimitEdgeCases:
    """슬라이스 16 잔여 결선 — write IP·limit=0·IP None 폴백."""

    def test_ip_write_dep_enforces_via_test_endpoint(self) -> None:
        from fastapi import APIRouter

        from whymath_backend.api._rate_limit import RateLimitedIpWrite

        router = APIRouter()

        @router.post("/_test/ip-write-limited", dependencies=[RateLimitedIpWrite])
        async def _hit() -> dict[str, bool]:
            return {"ok": True}

        app = create_app()
        app.include_router(router)
        app.dependency_overrides[get_settings] = lambda: Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_read_per_minute=0,
            coach_rate_limit_write_per_minute=0,
            coach_rate_limit_ip_write_per_minute=1,
        )
        client = TestClient(app)
        assert client.post("/_test/ip-write-limited").status_code == 200
        resp = client.post("/_test/ip-write-limited")
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "1"

    def test_ip_limit_zero_disables_enforcement(self) -> None:
        # IP limit=0 → 의존성이 짧게 반환, 응답 헤더 미세팅
        from fastapi import APIRouter

        from whymath_backend.api._rate_limit import RateLimitedIpRead

        router = APIRouter()

        @router.get("/_test/ip-disabled", dependencies=[RateLimitedIpRead])
        async def _hit() -> dict[str, bool]:
            return {"ok": True}

        app = create_app()
        app.include_router(router)
        app.dependency_overrides[get_settings] = lambda: Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_ip_read_per_minute=0,  # 비활성
        )
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/_test/ip-disabled")
            assert resp.status_code == 200
            assert "X-RateLimit-Limit" not in resp.headers

    def test_dep_skips_when_ip_unknown(self) -> None:
        # request.client=None → IP 알 수 없음 → dep 짧게 반환(헤더 0건·예외 0건)
        import asyncio
        from unittest.mock import MagicMock

        from fastapi import Response

        from whymath_backend.api._rate_limit import (
            rate_limit_ip_read,
            rate_limit_ip_write,
        )

        request = MagicMock()
        request.headers = {}
        request.client = None
        settings = Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_ip_read_per_minute=1,
            coach_rate_limit_ip_write_per_minute=1,
        )
        response = Response()
        asyncio.run(rate_limit_ip_read(request, settings, response))
        asyncio.run(rate_limit_ip_write(request, settings, response))
        assert "X-RateLimit-Limit" not in response.headers


class TestDefenseInDepth:
    """슬라이스 17 — 사용자 + IP 동시 적용. 둘 다 통과해야 200·뜨거운 쪽 헤더."""

    def test_user_limit_fires_before_ip(self) -> None:
        # user_limit=1, ip_limit=10 → 2번째 요청은 사용자 한도에서 429
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=1, ip_limit=0, ip_write_limit=10
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        # 사용자 한도가 발화 → 헤더는 user 기준(Limit=1)
        assert resp.headers["X-RateLimit-Limit"] == "1"

    def test_ip_limit_fires_when_user_loose(self) -> None:
        # user_limit=100, ip_limit=1 → 두번째 요청은 IP 한도에서 429
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=100, ip_limit=0, ip_write_limit=1
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        # IP 한도가 발화 → 헤더는 IP 기준(Limit=1)
        assert resp.headers["X-RateLimit-Limit"] == "1"

    def test_tighter_remaining_shown_on_200(self) -> None:
        # user_limit=10, ip_limit=2 → IP가 더 엄격 → 헤더에 IP의 remaining 노출
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=10, ip_limit=0, ip_write_limit=2
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        # IP는 remaining=1(2-1), user는 9(10-1). 더 엄격한 IP 노출.
        assert resp.headers["X-RateLimit-Limit"] == "2"
        assert resp.headers["X-RateLimit-Remaining"] == "1"

    def test_user_only_when_ip_unknown(self) -> None:
        # request.client = None인 상황은 hermetic으론 어렵지만, ip_limit=0이면 IP 검사
        # 비활성. user 한도만 적용되어야 한다.
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=1, ip_limit=0, ip_write_limit=0
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "1"

    def test_both_zero_no_enforcement(self) -> None:
        # 둘 다 0 → 무한 통과·헤더 없음
        client = _client(rate_limit=0)  # 이미 ip_limit=0 기본
        for _ in range(20):
            resp = client.post("/v1/coach", json={"student_input": "음"})
            assert resp.status_code == 200
            assert "X-RateLimit-Limit" not in resp.headers


class TestHitBothAtomic:
    """슬라이스 18 — `hit_both` 원자 동시 검사. 한쪽 거부 시 양쪽 미증가."""

    def test_inmemory_both_pass_increments_both(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        result = asyncio.run(
            backend.hit_both(
                uid,
                "1.2.3.4",
                category="read",
                user_limit=5,
                ip_limit=10,
                now=100.0,
            )
        )
        assert result.allowed is True
        assert result.user_result is not None
        assert result.ip_result is not None
        assert result.user_result.remaining == 4  # 5-1
        assert result.ip_result.remaining == 9  # 10-1

    def test_inmemory_user_blocks_ip_not_incremented(self) -> None:
        # user 한도 1 소진 후, 같은 user+다른 IP 시도 → 둘 다 증가 X
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        # user에 1 추가(한도 도달)
        asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=1, ip_limit=10, now=0.0
            )
        )
        # 같은 user, *다른* IP — user 한도 도달이라 atomic deny
        result = asyncio.run(
            backend.hit_both(
                uid, "2.2.2.2", category="read", user_limit=1, ip_limit=10, now=0.1
            )
        )
        assert result.allowed is False
        # IP 2.2.2.2 버킷은 *미증가*(0개) → remaining = 10
        assert result.ip_result is not None
        assert result.ip_result.remaining == 10

    def test_inmemory_prunes_expired_entries(self) -> None:
        # 60초 후의 hit_both — 옛 항목 prune되어 카운트 0부터 다시(분기 커버)
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=1, ip_limit=1, now=0.0
            )
        )
        denied = asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=1, ip_limit=1, now=0.5
            )
        )
        assert denied.allowed is False
        # 60초+ 후 — 옛 항목 prune되어 통과
        passed = asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=1, ip_limit=1, now=61.0
            )
        )
        assert passed.allowed is True

    def test_inmemory_atomic_no_waste_counter(self) -> None:
        # 핵심 invariant — IP가 거부면 user counter 낭비 안 함
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        uid = uuid.uuid4()
        # IP에 1 추가(한도 도달)
        asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=10, ip_limit=1, now=0.0
            )
        )
        # 같은 uid+같은 ip → IP 한도 도달이라 atomic deny
        result = asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=10, ip_limit=1, now=0.1
            )
        )
        assert result.allowed is False
        # user counter는 *미증가* — 다음 다른 IP에서 user_limit 그대로
        followup = asyncio.run(
            backend.hit_both(
                uid, "2.2.2.2", category="read", user_limit=10, ip_limit=10, now=0.2
            )
        )
        # user_count가 누적 1(첫 호출만) — IP 거부된 두번째는 user 미증가
        assert followup.allowed is True
        assert followup.user_result is not None
        assert followup.user_result.remaining == 8  # 10 - 2(첫+세번째)

    def test_inmemory_user_only_when_ip_none(self) -> None:
        # ip=None이면 user만 검사 — ip_result=None
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        result = asyncio.run(
            backend.hit_both(
                uuid.uuid4(),
                None,
                category="read",
                user_limit=5,
                ip_limit=10,
                now=0.0,
            )
        )
        assert result.allowed is True
        assert result.user_result is not None
        assert result.ip_result is None

    def test_inmemory_ip_only_when_user_limit_zero(self) -> None:
        # user_limit=0이면 IP만 검사
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        result = asyncio.run(
            backend.hit_both(
                uuid.uuid4(),
                "1.1.1.1",
                category="read",
                user_limit=0,
                ip_limit=5,
                now=0.0,
            )
        )
        assert result.allowed is True
        assert result.user_result is None
        assert result.ip_result is not None

    def test_redis_hit_both_atomic_lua(self) -> None:
        # Lua _LUA_HIT_BOTH가 원자성 보장 — fake로 의미 재현 확인
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = uuid.uuid4()
        # IP에 1 추가(한도 도달)
        r1 = asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=10, ip_limit=1, now=0.0
            )
        )
        assert r1.allowed is True
        # 같은 ip → IP 거부 → atomic 거부 → user counter 낭비 X
        r2 = asyncio.run(
            backend.hit_both(
                uid, "1.1.1.1", category="read", user_limit=10, ip_limit=1, now=0.1
            )
        )
        assert r2.allowed is False
        # user 키엔 1개만 있어야 함(낭비 0)
        from whymath_backend.api._rate_limit import RedisBackend as RB

        user_key = f"{RB._KEY_PREFIX}read:user:{uid}"
        assert len(fake.zsets[user_key]) == 1

    def test_redis_noscript_fallback_for_hit_both(self) -> None:
        # _LUA_HIT_BOTH도 NOSCRIPT 폴백 자동 적재
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        # 새 backend — _LUA_HIT_BOTH 캐시 비어있음
        backend = RedisBackend(client=fake)
        result = asyncio.run(
            backend.hit_both(
                uuid.uuid4(),
                "1.1.1.1",
                category="read",
                user_limit=5,
                ip_limit=5,
                now=0.0,
            )
        )
        assert result.allowed is True
        # script_load 발화·재시도
        assert len(fake.script_loads) >= 1


class TestDefenseAtomicInRouter:
    """슬라이스 18 결선 — _enforce_defense가 hit_both 사용해 낭비 0."""

    def test_ip_block_does_not_consume_user_quota(self) -> None:
        # user=10, ip=1로 첫 요청 → 통과. 두번째 → IP 거부.
        # 세번째 *다른 IP*로 → user 한도 그대로(낭비 0이라 9 남아야 함, 8 아님)
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user

        # 매 요청 시 settings를 새로 — 이상적이지만 여기선 동일 limit 고정.
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=10, ip_limit=0, ip_write_limit=1
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        # IP=testclient라 둘 다 같은 ip — 한 client는 같은 IP. 1회만 IP 통과.
        r1 = client.post("/v1/coach", json={"student_input": "음"})
        assert r1.status_code == 200
        # X-RateLimit-Remaining(user 입장)이 9, ip 입장이 0
        # 더 엄격한 ip가 노출 (Remaining=0)
        assert r1.headers["X-RateLimit-Remaining"] == "0"
        # 두번째 — IP 한도 도달, atomic 거부 → user counter 낭비 X
        r2 = client.post("/v1/coach", json={"student_input": "음"})
        assert r2.status_code == 429
        # blocker는 IP — Limit=1
        assert r2.headers["X-RateLimit-Limit"] == "1"


class TestPairHeaders:
    """슬라이스 19 — `X-RateLimit-User-*`/`-Ip-*` 두 쌍 헤더 동시 노출."""

    def test_defense_200_emits_both_pairs_and_rollup(self) -> None:
        # user=10, ip=2 → 200 응답에 User-*, Ip-*, rollup 모두 동봉
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=10, ip_limit=0, ip_write_limit=2
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        # rollup (더 엄격한 = IP)
        assert resp.headers["X-RateLimit-Limit"] == "2"
        assert resp.headers["X-RateLimit-Remaining"] == "1"
        # 두 쌍 동시
        assert resp.headers["X-RateLimit-User-Limit"] == "10"
        assert resp.headers["X-RateLimit-User-Remaining"] == "9"
        assert resp.headers["X-RateLimit-Ip-Limit"] == "2"
        assert resp.headers["X-RateLimit-Ip-Remaining"] == "1"

    def test_defense_429_emits_pairs_on_blocker(self) -> None:
        # ip 한도 1 소진 후 429 — User-* 와 Ip-* 둘 다 동봉
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=10, ip_limit=0, ip_write_limit=1
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        assert client.post("/v1/coach", json={"student_input": "음"}).status_code == 200
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 429
        # blocker(IP)의 rollup
        assert resp.headers["X-RateLimit-Limit"] == "1"
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        # 두 쌍 동시 — 첫 호출에서 user count=1, 두번째 atomic deny → user 그대로 1.
        # User-Remaining = 10 - 1 = 9. Ip-Remaining = 0(blocker).
        assert resp.headers["X-RateLimit-User-Limit"] == "10"
        assert resp.headers["X-RateLimit-User-Remaining"] == "9"
        assert resp.headers["X-RateLimit-Ip-Limit"] == "1"
        assert resp.headers["X-RateLimit-Ip-Remaining"] == "0"

    def test_user_only_active_emits_only_user_pair(self) -> None:
        # ip_limit=0이면 User-*만 노출, Ip-*는 미세팅
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=5, ip_limit=0, ip_write_limit=0
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-User-Limit"] == "5"
        assert "X-RateLimit-Ip-Limit" not in resp.headers

    def test_ip_only_endpoint_emits_ip_pair(self) -> None:
        # 미인증 IP-only dep도 X-RateLimit-Ip-* 동시 노출
        from fastapi import APIRouter

        from whymath_backend.api._rate_limit import RateLimitedIpRead

        router = APIRouter()

        @router.get("/_test/ip-headers", dependencies=[RateLimitedIpRead])
        async def _hit() -> dict[str, bool]:
            return {"ok": True}

        app = create_app()
        app.include_router(router)
        app.dependency_overrides[get_settings] = lambda: Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            coach_rate_limit_ip_read_per_minute=3,
        )
        client = TestClient(app)
        resp = client.get("/_test/ip-headers")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Ip-Limit"] == "3"
        assert resp.headers["X-RateLimit-Ip-Remaining"] == "2"
        # rollup도 동일
        assert resp.headers["X-RateLimit-Limit"] == "3"
        # User-* 차원은 IP-only라 미세팅
        assert "X-RateLimit-User-Limit" not in resp.headers


class TestPairHelperUnit:
    """`_pair_headers` 헬퍼 — 프리픽스 조립 검증."""

    def test_canonical_prefix_keys(self) -> None:
        from whymath_backend.api._rate_limit import RateLimitResult, _pair_headers

        result = RateLimitResult(allowed=True, remaining=5, reset_seconds=30)
        headers = _pair_headers("User", 10, result)
        assert set(headers.keys()) == {
            "X-RateLimit-User-Limit",
            "X-RateLimit-User-Remaining",
            "X-RateLimit-User-Reset",
        }
        assert headers["X-RateLimit-User-Limit"] == "10"
        assert headers["X-RateLimit-User-Remaining"] == "5"
        assert headers["X-RateLimit-User-Reset"] == "30"

    def test_different_prefix(self) -> None:
        from whymath_backend.api._rate_limit import RateLimitResult, _pair_headers

        result = RateLimitResult(allowed=True, remaining=2, reset_seconds=15)
        headers = _pair_headers("Ip", 5, result)
        assert "X-RateLimit-Ip-Limit" in headers
        assert "X-RateLimit-User-Limit" not in headers

    def test_defense_with_user_limit_zero_skips_user_pair(self) -> None:
        # user_limit=0, ip_limit>0이면 Defense는 IP만 검사 — User-* 미세팅
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0, write_limit=0, ip_limit=0, ip_write_limit=5
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        resp = client.post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200
        # IP만 활성 — User-* 미세팅
        assert "X-RateLimit-User-Limit" not in resp.headers
        assert resp.headers["X-RateLimit-Ip-Limit"] == "5"


class TestTripleDimension:
    """슬라이스 20 — 3차원 한도(user+IP+device). hit_many 원자성·X-Device-Id 추출."""

    def test_hit_many_all_pass(self) -> None:
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend, Subject

        backend = InMemoryBackend()
        results = asyncio.run(
            backend.hit_many(
                [
                    Subject(kind="user", id=str(uuid.uuid4()), limit=10),
                    Subject(kind="ip", id="1.1.1.1", limit=20),
                    Subject(kind="device", id="dev-abc", limit=5),
                ],
                category="read",
                now=0.0,
            )
        )
        assert results["user"].allowed is True
        assert results["ip"].allowed is True
        assert results["device"].allowed is True
        assert results["user"].remaining == 9
        assert results["device"].remaining == 4

    def test_hit_many_atomic_device_blocks_others(self) -> None:
        # device 한도 1 도달 시, 같은 호출의 user/ip는 미증가
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend, Subject

        backend = InMemoryBackend()
        uid = str(uuid.uuid4())
        asyncio.run(
            backend.hit_many(
                [
                    Subject(kind="user", id=uid, limit=10),
                    Subject(kind="ip", id="1.1.1.1", limit=10),
                    Subject(kind="device", id="dev-abc", limit=1),
                ],
                category="read",
                now=0.0,
            )
        )
        # 두번째 호출 — device 한도 도달이라 atomic deny
        result = asyncio.run(
            backend.hit_many(
                [
                    Subject(kind="user", id=uid, limit=10),
                    Subject(kind="ip", id="1.1.1.1", limit=10),
                    Subject(kind="device", id="dev-abc", limit=1),
                ],
                category="read",
                now=0.1,
            )
        )
        assert result["device"].allowed is False
        # user/ip counter는 *미증가* — 다음 다른 device로 통과 시 user remaining=8(누적 2)
        followup = asyncio.run(
            backend.hit_many(
                [
                    Subject(kind="user", id=uid, limit=10),
                    Subject(kind="ip", id="1.1.1.1", limit=10),
                    Subject(kind="device", id="dev-xyz", limit=1),  # 다른 device
                ],
                category="read",
                now=0.2,
            )
        )
        assert followup["user"].allowed is True
        assert followup["user"].remaining == 8  # 10 - 2(첫 + 세번째 통과)

    def test_hit_many_empty_subjects(self) -> None:
        # 빈 리스트 → 빈 dict no-op
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend

        backend = InMemoryBackend()
        results = asyncio.run(backend.hit_many([], category="read", now=0.0))
        assert results == {}

    def test_redis_hit_many_atomic(self) -> None:
        # _LUA_HIT_MANY가 N개 키 원자 처리
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend, Subject

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        uid = str(uuid.uuid4())
        results = asyncio.run(
            backend.hit_many(
                [
                    Subject(kind="user", id=uid, limit=5),
                    Subject(kind="ip", id="1.1.1.1", limit=5),
                    Subject(kind="device", id="dev-1", limit=5),
                ],
                category="read",
                now=0.0,
            )
        )
        assert results["user"].allowed is True
        # 세 키 모두 ZSET에 생성됨
        from whymath_backend.api._rate_limit import RedisBackend as RB

        assert f"{RB._KEY_PREFIX}read:user:{uid}" in fake.zsets
        assert f"{RB._KEY_PREFIX}read:ip:1.1.1.1" in fake.zsets
        assert f"{RB._KEY_PREFIX}read:device:dev-1" in fake.zsets

    async def test_device_id_header_extraction(self) -> None:
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        request = MagicMock()
        request.headers = {"x-device-id": "dev-abc-123"}
        # secret 미설정 — slice 20 동작 그대로(서명 검증 생략)
        settings = _settings_override(0)
        assert await _client_device_id(request, settings) == "dev-abc-123"

    async def test_device_id_missing_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        request = MagicMock()
        request.headers = {}
        assert await _client_device_id(request, _settings_override(0)) is None

    async def test_device_id_empty_returns_none(self) -> None:
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        request = MagicMock()
        request.headers = {"x-device-id": "  "}
        assert await _client_device_id(request, _settings_override(0)) is None

    def test_coach_endpoint_uses_device_limit(self) -> None:
        # coach POST가 RateLimitedTripleWrite 부착 — device 한도 1 시 X-Device-Id로 2번째 429
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0,
            write_limit=10,
            ip_limit=0,
            ip_write_limit=10,
            device_limit=0,
            device_write_limit=1,
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        # X-Device-Id 헤더 동봉
        headers = {"x-device-id": "dev-test"}
        r1 = client.post("/v1/coach", json={"student_input": "음"}, headers=headers)
        assert r1.status_code == 200
        # Device pair-header 노출
        assert r1.headers["X-RateLimit-Device-Limit"] == "1"
        assert r1.headers["X-RateLimit-Device-Remaining"] == "0"
        # 두번째 — device 한도 도달
        r2 = client.post("/v1/coach", json={"student_input": "음"}, headers=headers)
        assert r2.status_code == 429
        assert r2.headers["X-RateLimit-Limit"] == "1"  # blocker=device

    def test_coach_endpoint_skips_device_when_header_absent(self) -> None:
        # X-Device-Id 헤더 없으면 device 차원 검사 비활성 — user+IP만
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0,
            write_limit=10,
            ip_limit=0,
            ip_write_limit=10,
            device_limit=0,
            device_write_limit=1,
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        # device 한도 1이지만 헤더 없음 → 5번 모두 통과(device 검사 안 함)
        for _ in range(5):
            resp = client.post("/v1/coach", json={"student_input": "음"})
            assert resp.status_code == 200
            assert "X-RateLimit-Device-Limit" not in resp.headers


class TestHitManyEdgeCases:
    """잔여 분기 커버 — hit_many prune·Redis 빈 subjects."""

    def test_inmemory_hit_many_prunes_expired(self) -> None:
        # 60초+ 후 hit_many — 옛 항목 prune(while bucket[0]<cutoff: popleft)
        import asyncio

        from whymath_backend.api._rate_limit import InMemoryBackend, Subject

        backend = InMemoryBackend()
        uid = str(uuid.uuid4())
        asyncio.run(
            backend.hit_many(
                [Subject(kind="user", id=uid, limit=1)], category="read", now=0.0
            )
        )
        # 같은 윈도우 — 거부
        denied = asyncio.run(
            backend.hit_many(
                [Subject(kind="user", id=uid, limit=1)], category="read", now=0.5
            )
        )
        assert denied["user"].allowed is False
        # 60초+ — prune 분기 발화
        passed = asyncio.run(
            backend.hit_many(
                [Subject(kind="user", id=uid, limit=1)], category="read", now=61.0
            )
        )
        assert passed["user"].allowed is True

    def test_redis_hit_many_empty_subjects_noop(self) -> None:
        # Redis backend도 빈 subjects 시 no-op 반환(early return)
        import asyncio

        from whymath_backend.api._rate_limit import RedisBackend

        fake = _FakeRedisClient()
        backend = RedisBackend(client=fake)
        results = asyncio.run(backend.hit_many([], category="read", now=0.0))
        assert results == {}
        assert fake.evalsha_calls == []  # Redis 호출 자체가 없음


class TestDeviceHmacSignature:
    """슬라이스 21 — HMAC X-Device-Sig 검증."""

    def _sig(self, secret: str, device_id: str) -> str:
        from whymath_backend.api._rate_limit import _expected_device_signature

        return _expected_device_signature(secret, device_id)

    async def test_valid_signature_accepts_device_id(self) -> None:
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        secret = "test-device-secret-123"
        device_id = "dev-abc-123"
        valid_sig = self._sig(secret, device_id)
        request = MagicMock()
        request.headers = {"x-device-id": device_id, "x-device-sig": valid_sig}
        settings = _settings_override(0, device_hmac_secret=secret)
        assert await _client_device_id(request, settings) == device_id

    async def test_invalid_signature_returns_none(self) -> None:
        # 서명 불일치 → fail-safe(device 차원 검사 비활성)
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        secret = "test-device-secret-123"
        request = MagicMock()
        request.headers = {
            "x-device-id": "dev-abc-123",
            "x-device-sig": "0" * 64,  # 형식 맞으나 잘못된 서명
        }
        settings = _settings_override(0, device_hmac_secret=secret)
        assert await _client_device_id(request, settings) is None

    async def test_missing_signature_when_secret_set_returns_none(self) -> None:
        # secret 설정·X-Device-Sig 헤더 누락 → None(fail-safe)
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        request = MagicMock()
        request.headers = {"x-device-id": "dev-abc-123"}
        settings = _settings_override(0, device_hmac_secret="some-secret")
        assert await _client_device_id(request, settings) is None

    async def test_empty_secret_skips_verification(self) -> None:
        # secret 비어있으면 서명 검증 생략(slice 20 backward compat)
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        request = MagicMock()
        request.headers = {"x-device-id": "dev-abc-123"}  # X-Device-Sig 없음
        settings = _settings_override(0, device_hmac_secret="")
        assert await _client_device_id(request, settings) == "dev-abc-123"

    async def test_case_insensitive_signature(self) -> None:
        # 클라이언트가 대문자 hex로 보내도 일치 검증(.lower() 정규화)
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        secret = "test-device-secret-123"
        device_id = "dev-abc"
        valid_sig = self._sig(secret, device_id).upper()  # 대문자
        request = MagicMock()
        request.headers = {"x-device-id": device_id, "x-device-sig": valid_sig}
        settings = _settings_override(0, device_hmac_secret=secret)
        assert await _client_device_id(request, settings) == device_id

    async def test_signature_for_different_device_id_rejected(self) -> None:
        # 다른 device_id의 서명을 보내면 거부(서명·ID 페어 무결성)
        from unittest.mock import MagicMock

        from whymath_backend.api._rate_limit import _client_device_id

        secret = "test-secret"
        sig_for_other = self._sig(secret, "other-device")
        request = MagicMock()
        request.headers = {"x-device-id": "this-device", "x-device-sig": sig_for_other}
        settings = _settings_override(0, device_hmac_secret=secret)
        assert await _client_device_id(request, settings) is None

    def test_expected_signature_deterministic_and_64char(self) -> None:
        from whymath_backend.api._rate_limit import _expected_device_signature

        s1 = _expected_device_signature("secret", "device-1")
        s2 = _expected_device_signature("secret", "device-1")
        assert s1 == s2
        assert len(s1) == 64  # SHA-256 hex
        # 다른 입력 → 다른 서명
        assert s1 != _expected_device_signature("secret", "device-2")
        assert s1 != _expected_device_signature("other-secret", "device-1")

    def test_coach_endpoint_with_valid_sig_enforces_device_limit(self) -> None:
        # secret 설정 + 유효 서명 → device 한도 정상 발화
        from whymath_backend.api._rate_limit import _expected_device_signature

        secret = "endpoint-test-secret"
        device_id = "dev-1"
        valid_sig = _expected_device_signature(secret, device_id)

        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0,
            write_limit=10,
            ip_limit=0,
            ip_write_limit=10,
            device_limit=0,
            device_write_limit=1,
            device_hmac_secret=secret,
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        headers = {"x-device-id": device_id, "x-device-sig": valid_sig}
        r1 = client.post("/v1/coach", json={"student_input": "음"}, headers=headers)
        assert r1.status_code == 200
        assert r1.headers["X-RateLimit-Device-Limit"] == "1"
        r2 = client.post("/v1/coach", json={"student_input": "음"}, headers=headers)
        assert r2.status_code == 429

    def test_coach_endpoint_with_invalid_sig_skips_device(self) -> None:
        # 잘못된 서명 → device 차원 비활성·user+IP만 적용
        secret = "endpoint-test-secret"
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            limit=0,
            write_limit=10,
            ip_limit=0,
            ip_write_limit=10,
            device_limit=0,
            device_write_limit=1,
            device_hmac_secret=secret,
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        # 잘못된 서명을 매 호출 다른 device_id로 (spoofing 시도)
        for i in range(5):
            headers = {"x-device-id": f"dev-{i}", "x-device-sig": "0" * 64}
            resp = client.post(
                "/v1/coach", json={"student_input": "음"}, headers=headers
            )
            assert resp.status_code == 200
            # device 차원 미활성 → Device-* 헤더 없음
            assert "X-RateLimit-Device-Limit" not in resp.headers
