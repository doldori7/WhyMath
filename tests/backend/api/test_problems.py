"""problem API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic).

concept 라우터 테스트(test_concepts.py)와 동형. 실제 SQL·필터는 통합테스트와 메인 PG 검증
담당(여기서는 상태코드·직렬화·404/409/422·commit/rollback 결선만).

인가(SEC-07 D1): POST/PATCH/DELETE는 `RequireContentAdmin` 게이트가 있다. `_client()`가
`require_content_admin`을 CONTENT_ADMIN 고정 사용자로 오버라이드해 이 파일의 결선 테스트를
유지하고(test_concepts.py 패턴 동형), `TestAuthGate`가 오버라이드 없는 실제 인증·인가 회귀
(401/403)와 GET 무인증 유지를 검증한다.

노출 계약(PB-08): GET 4개는 노출 2축(저작권 `is_exposable`·검수 `is_review_cleared`)을 경유하고
정답 축 4필드를 리댁션한다. 그래서 이 파일의 표본 `_sample_problem()`은 **approved·자체생성**
(=노출 적격)이다 — 계약 도입 전에는 `review_status`가 None이라 지금 기준으로는 전부 404가 된다.
`TestPublicCatalogExposure`가 차단·리댁션을 검증하고, `TestAuthGate`의 GET 3건은 *무인증 유지*
회귀를 그대로 지킨다(이 태스크는 "누가 보는가"가 아니라 "무엇이 보이는가"만 바꾼다).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from whymath_backend.api._auth import require_content_admin
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.problem import Problem, ProblemRelation, ProblemStep
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import (
    Curriculum,
    RelationType,
    ReviewStatus,
    Role,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.problem import ProblemRelation as ProblemRelationSchema
from whymath_backend.schema.problem import ProblemStep as ProblemStepSchema
from whymath_backend.security import create_access_token

_ADMIN_USER = UserProfile(user_id=uuid.uuid4(), role=Role.CONTENT_ADMIN)


def _valid_schema() -> ProblemSchema:
    """최소 유효 schema.Problem(자체생성 — 본문 보유 허용).

    PB-08 공개 노출 계약을 통과하도록 `review_status=approved`(검수 축)를 명시한다. 출처는
    `자체생성`이라 저작권 축도 통과한다. 이 값이 없으면(=계약 도입 전 상태) `is_review_cleared`가
    fail-closed로 막아 GET이 전부 404가 된다.
    """
    return ProblemSchema(
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2015,
        valid_from_year=2014,
        subject=Subject.미적분,
        unit_codes=["CAL-INT-DEF"],
        review_status=ReviewStatus.approved,
    )


def _valid_body() -> dict[str, Any]:
    return _valid_schema().model_dump(mode="json")


class _FakeScalars:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def all(self) -> list[Problem]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeSession:
    """AsyncSession 표면 일부 모사 — 라우터가 부르는 메서드만(test_concepts.py와 동일 패턴)."""

    def __init__(
        self,
        *,
        get_map: dict[uuid.UUID, Problem] | None = None,
        list_rows: list[Problem] | None = None,
        commit_error: Exception | None = None,
    ) -> None:
        self._get_map = dict(get_map or {})
        self._list_rows = list(list_rows or [])
        self._commit_error = commit_error
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = False
        self.rolled_back = False
        # PB-08: 목록 라우트가 실행에 넘긴 실제 Select 객체(노출 게이트 SQL 화이트박스 검사용).
        self.executed_stmts: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        return None

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def merge(self, obj: Any) -> Any:
        return obj

    async def get(self, model: Any, pk: uuid.UUID) -> Problem | None:
        return self._get_map.get(pk)

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed_stmts.append(stmt)
        return _FakeResult(self._list_rows)


def _client(fake: FakeSession) -> TestClient:
    """get_session을 가짜로, require_content_admin을 고정 관리자로 오버라이드(결선 테스트용)."""
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[require_content_admin] = lambda: _ADMIN_USER
    return TestClient(app)


def _sample_problem() -> Problem:
    """노출 적격 표본(자체생성·approved) — PB-08 두 축 모두 통과."""
    return Problem.from_schema(_valid_schema())


def _pending_problem() -> Problem:
    """검수 축 위반 표본 — `review_status=pending`.

    실측 코퍼스의 pending 158건(killer_v0 120·probability_finite_v0 34·v1 4)과 동형이다.
    저작권 축(자체생성)은 통과하므로 *검수 축만* 단독으로 변별한다.
    """
    schema = _valid_schema().model_copy(update={"review_status": ReviewStatus.pending})
    return Problem.from_schema(schema)


def _metadata_only_problem() -> Problem:
    """저작권 축 위반 표본 — 평가원 출처(본문 미보유·구조 메타 전용).

    `review_status=approved`로 두어 *저작권 축만* 단독으로 변별한다(검수 축은 통과).
    """
    return Problem.from_schema(
        ProblemSchema(
            source_type=SourceType.평가원,
            curriculum_version=Curriculum.REVISION_2015,
            valid_from_year=2014,
            subject=Subject.미적분,
            unit_codes=["CAL-INT-DEF"],
            review_status=ReviewStatus.approved,
        )
    )


def _answer_bearing_problem() -> Problem:
    """정답 축 4필드를 모두 채운 노출 적격 표본 — 리댁션 검증용."""
    schema = _valid_schema().model_copy(
        update={
            "answer": "42",
            "answer_explanation": "적분 구간을 나눠 계산하면 42가 나온다.",
            "multiple_answers": {"has_multiple": True, "candidates": ["42", "-42"]},
            "distractor_map": [
                DistractorEntry(choice_index=1, misconception_id="M-CAL-001", op_code=None)
            ],
        }
    )
    return Problem.from_schema(schema)


def _sample_step(problem_id: uuid.UUID, order: int) -> ProblemStep:
    return ProblemStep.from_schema(
        ProblemStepSchema(problem_id=problem_id, step_order=order, step_title=f"단계{order}")
    )


def _sample_relation(parent: uuid.UUID, related: uuid.UUID) -> ProblemRelation:
    return ProblemRelation.from_schema(
        ProblemRelationSchema(
            parent_problem_id=parent,
            related_problem_id=related,
            relation_type=RelationType.유사,
        )
    )


class TestCreate:
    def test_create_returns_201_and_commits(self) -> None:
        fake = FakeSession()
        resp = _client(fake).post("/v1/problems", json=_valid_body())
        assert resp.status_code == 201, resp.text
        assert resp.json()["subject"] == "미적분"
        assert fake.committed is True
        assert len(fake.added) == 1

    def test_create_duplicate_returns_409(self) -> None:
        """external_id/slug UNIQUE 충돌(IntegrityError) → 롤백 후 409."""
        err = IntegrityError("INSERT", {}, Exception("duplicate key value violates unique"))
        fake = FakeSession(commit_error=err)
        resp = _client(fake).post("/v1/problems", json=_valid_body())
        assert resp.status_code == 409
        assert fake.rolled_back is True
        assert fake.committed is False

    def test_create_invalid_body_returns_422(self) -> None:
        """필수 필드(subject 등) 누락 → 422."""
        fake = FakeSession()
        resp = _client(fake).post("/v1/problems", json={"source_type": "자체생성"})
        assert resp.status_code == 422
        assert fake.committed is False


class TestRead:
    def test_read_existing_returns_200(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 200
        assert resp.json()["problem_id"] == str(problem.problem_id)

    def test_read_missing_returns_404(self) -> None:
        fake = FakeSession()
        resp = _client(fake).get(f"/v1/problems/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_read_invalid_uuid_returns_422(self) -> None:
        fake = FakeSession()
        resp = _client(fake).get("/v1/problems/not-a-uuid")
        assert resp.status_code == 422


class TestList:
    def test_list_returns_rows(self) -> None:
        fake = FakeSession(list_rows=[_sample_problem(), _sample_problem()])
        resp = _client(fake).get("/v1/problems")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_empty_returns_empty_array(self) -> None:
        resp = _client(FakeSession()).get("/v1/problems")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_accepts_valid_subject_filter(self) -> None:
        resp = _client(FakeSession()).get("/v1/problems?subject=미적분")
        assert resp.status_code == 200

    def test_list_rejects_unknown_subject(self) -> None:
        """enum 밖 subject → 422."""
        resp = _client(FakeSession()).get("/v1/problems?subject=없는과목")
        assert resp.status_code == 422

    def test_list_rejects_out_of_range_pagination(self) -> None:
        client = _client(FakeSession())
        assert client.get("/v1/problems?limit=0").status_code == 422
        assert client.get("/v1/problems?limit=999").status_code == 422
        assert client.get("/v1/problems?offset=-1").status_code == 422


class TestSteps:
    def test_lists_steps_for_existing_problem(self) -> None:
        problem = _sample_problem()
        steps = [
            _sample_step(problem.problem_id, 1),
            _sample_step(problem.problem_id, 2),
        ]
        fake = FakeSession(get_map={problem.problem_id: problem}, list_rows=steps)
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_steps_404_when_problem_missing(self) -> None:
        resp = _client(FakeSession()).get(f"/v1/problems/{uuid.uuid4()}/steps")
        assert resp.status_code == 404

    def test_steps_empty_when_no_steps(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_steps_invalid_uuid_returns_422(self) -> None:
        resp = _client(FakeSession()).get("/v1/problems/not-a-uuid/steps")
        assert resp.status_code == 422

    def test_promoted_step_serves_additive_fields(self) -> None:
        """S4-09(D1) reader ① 계약: 승격 어댑터가 적재한 실데이터(additive 필드 포함)가
        기존 응답 스키마로 서빙된다 — 기존 필드 제거·의미 변경 0."""
        problem = _sample_problem()
        promoted = ProblemStep.from_schema(
            ProblemStepSchema(
                problem_id=problem.problem_id,
                step_order=1,
                expected_answer="2*x = 6",  # SolutionStep.content 영속 좌석
                solution_path_id="sp-11111111-1111-1111-1111-111111111111",
                concept_node_id=None,  # 매칭 검수 대기(사람 검수 큐)
                sympy_verified=False,  # 첫 스텝은 전이 검증 대상 아님(정직 승계)
            )
        )
        fake = FakeSession(get_map={problem.problem_id: problem}, list_rows=[promoted])
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        step = body[0]
        # additive 필드 노출(승격 실데이터).
        assert step["solution_path_id"] == "sp-11111111-1111-1111-1111-111111111111"
        assert step["expected_answer"] == "2*x = 6"
        assert step["concept_node_id"] is None
        assert step["sympy_verified"] is False
        assert step["reasoning_type"] is None
        # 기존 필드 유지(제거·의미 변경 0 — 하위호환 계약).
        assert step["step_order"] == 1
        assert "socratic_prompt" in step and "common_mistakes" in step

    def test_legacy_step_still_serves_with_none_additive_fields(self) -> None:
        """레거시 단계(additive 미지정)도 그대로 서빙 — additive 필드는 전부 None(비파괴)."""
        problem = _sample_problem()
        legacy = _sample_step(problem.problem_id, 1)
        fake = FakeSession(get_map={problem.problem_id: problem}, list_rows=[legacy])
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 200
        step = resp.json()[0]
        assert step["step_title"] == "단계1"
        assert step["solution_path_id"] is None
        assert step["concept_node_id"] is None
        assert step["justification"] is None
        assert step["common_errors"] is None
        assert step["sympy_verified"] is None


class TestRelations:
    def test_lists_relations_for_existing_problem(self) -> None:
        parent = _sample_problem()
        rel = _sample_relation(parent.problem_id, uuid.uuid4())
        fake = FakeSession(get_map={parent.problem_id: parent}, list_rows=[rel])
        resp = _client(fake).get(f"/v1/problems/{parent.problem_id}/relations")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["relation_type"] == "유사"

    def test_relations_404_when_problem_missing(self) -> None:
        resp = _client(FakeSession()).get(f"/v1/problems/{uuid.uuid4()}/relations")
        assert resp.status_code == 404


class TestPatch:
    def test_patch_updates_field(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).patch(f"/v1/problems/{problem.problem_id}", json={"answer": "42"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["answer"] == "42"
        assert fake.committed is True

    def test_patch_404_when_missing(self) -> None:
        resp = _client(FakeSession()).patch(f"/v1/problems/{uuid.uuid4()}", json={"answer": "x"})
        assert resp.status_code == 404

    def test_patch_invalid_enum_returns_422(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).patch(
            f"/v1/problems/{problem.problem_id}", json={"subject": "없는과목"}
        )
        assert resp.status_code == 422
        assert fake.committed is False

    def test_patch_violating_legal_invariant_returns_422(self) -> None:
        """본문 보유 문제를 평가원 출처로 변경 → 본문 보유 금지 불변식 재검증 → 422."""
        with_text = Problem.from_schema(
            ProblemSchema(
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2015,
                valid_from_year=2014,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
                question_text="f(x)를 구하시오",
            )
        )
        fake = FakeSession(get_map={with_text.problem_id: with_text})
        resp = _client(fake).patch(
            f"/v1/problems/{with_text.problem_id}", json={"source_type": "평가원"}
        )
        assert resp.status_code == 422
        assert fake.committed is False

    def test_patch_duplicate_returns_409(self) -> None:
        problem = _sample_problem()
        err = IntegrityError("UPDATE", {}, Exception("duplicate key"))
        fake = FakeSession(get_map={problem.problem_id: problem}, commit_error=err)
        resp = _client(fake).patch(
            f"/v1/problems/{problem.problem_id}", json={"external_id": "X-1"}
        )
        assert resp.status_code == 409
        assert fake.rolled_back is True


class TestDelete:
    def test_delete_returns_204(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).delete(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 204
        assert fake.committed is True
        assert len(fake.deleted) == 1

    def test_delete_404_when_missing(self) -> None:
        resp = _client(FakeSession()).delete(f"/v1/problems/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_409_when_referenced(self) -> None:
        problem = _sample_problem()
        err = IntegrityError("DELETE", {}, Exception("FK violation"))
        fake = FakeSession(get_map={problem.problem_id: problem}, commit_error=err)
        resp = _client(fake).delete(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 409
        assert fake.rolled_back is True


class TestConcurrency:
    """낙관적 동시성 — ETag 노출 + If-Match 조건부 변경."""

    def test_get_and_post_expose_etag(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        get_resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert get_resp.headers.get("ETag", "").startswith('"')
        post_resp = _client(FakeSession()).post("/v1/problems", json=_valid_body())
        assert post_resp.headers.get("ETag", "").startswith('"')

    def test_patch_with_matching_if_match_succeeds(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        client = _client(fake)
        etag = client.get(f"/v1/problems/{problem.problem_id}").headers["ETag"]
        resp = client.patch(
            f"/v1/problems/{problem.problem_id}",
            json={"answer": "42"},
            headers={"If-Match": etag},
        )
        assert resp.status_code == 200, resp.text

    def test_patch_with_stale_if_match_returns_412(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).patch(
            f"/v1/problems/{problem.problem_id}",
            json={"answer": "42"},
            headers={"If-Match": '"deadbeefdeadbeef"'},
        )
        assert resp.status_code == 412
        assert fake.committed is False

    def test_patch_without_if_match_proceeds(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).patch(f"/v1/problems/{problem.problem_id}", json={"answer": "42"})
        assert resp.status_code == 200

    def test_delete_with_stale_if_match_returns_412(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).delete(
            f"/v1/problems/{problem.problem_id}",
            headers={"If-Match": '"deadbeefdeadbeef"'},
        )
        assert resp.status_code == 412
        assert len(fake.deleted) == 0


class TestConditionalGet:
    """If-None-Match → 304 조건부 GET(캐싱)."""

    def test_matching_if_none_match_returns_304(self) -> None:
        problem = _sample_problem()
        client = _client(FakeSession(get_map={problem.problem_id: problem}))
        etag = client.get(f"/v1/problems/{problem.problem_id}").headers["ETag"]
        resp = client.get(f"/v1/problems/{problem.problem_id}", headers={"If-None-Match": etag})
        assert resp.status_code == 304
        assert resp.headers.get("ETag") == etag
        assert resp.content == b""

    def test_wildcard_if_none_match_returns_304(self) -> None:
        problem = _sample_problem()
        client = _client(FakeSession(get_map={problem.problem_id: problem}))
        resp = client.get(f"/v1/problems/{problem.problem_id}", headers={"If-None-Match": "*"})
        assert resp.status_code == 304

    def test_stale_if_none_match_returns_200(self) -> None:
        problem = _sample_problem()
        client = _client(FakeSession(get_map={problem.problem_id: problem}))
        resp = client.get(
            f"/v1/problems/{problem.problem_id}",
            headers={"If-None-Match": '"deadbeefdeadbeef"'},
        )
        assert resp.status_code == 200

    def test_no_if_none_match_returns_200(self) -> None:
        problem = _sample_problem()
        client = _client(FakeSession(get_map={problem.problem_id: problem}))
        resp = client.get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 200


_TEST_JWT_SETTINGS = Settings(jwt_secret_key=SecretStr("test-secret-key-0123456789abcdef"))


class TestAuthGate:
    """SEC-07 D1 — CUD 인가 회귀(오버라이드 없는 *실제* 의존성) + GET 무인증 유지 동결.

    test_concepts.py `TestAuthGate`와 동형(설계 근거는 그쪽 docstring 참조).
    """

    def _client_real_auth(self, fake: FakeSession) -> TestClient:
        app = create_app()

        async def _override() -> AsyncIterator[FakeSession]:
            yield fake

        app.dependency_overrides[get_session] = _override
        app.dependency_overrides[get_settings] = lambda: _TEST_JWT_SETTINGS
        return TestClient(app)

    def _token_for(self, user: UserProfile) -> str:
        return create_access_token(user.user_id, settings=_TEST_JWT_SETTINGS)

    # ── 무인증 → CUD 401 ──
    def test_unauthenticated_post_returns_401(self) -> None:
        resp = self._client_real_auth(FakeSession()).post("/v1/problems", json=_valid_body())
        assert resp.status_code == 401

    def test_unauthenticated_patch_returns_401(self) -> None:
        resp = self._client_real_auth(FakeSession()).patch(
            f"/v1/problems/{uuid.uuid4()}", json={"answer": "x"}
        )
        assert resp.status_code == 401

    def test_unauthenticated_delete_returns_401(self) -> None:
        resp = self._client_real_auth(FakeSession()).delete(f"/v1/problems/{uuid.uuid4()}")
        assert resp.status_code == 401

    # ── 인증됐으나 역할 불일치(STUDENT) → CUD 403 ──
    def test_student_role_post_returns_403(self) -> None:
        student = UserProfile(user_id=uuid.uuid4(), role=Role.STUDENT)
        fake = FakeSession(get_map={student.user_id: student})
        resp = self._client_real_auth(fake).post(
            "/v1/problems",
            json=_valid_body(),
            headers={"Authorization": f"Bearer {self._token_for(student)}"},
        )
        assert resp.status_code == 403

    # ── CONTENT_ADMIN 실 토큰 → 정상 통과(엔드투엔드 결선 확인) ──
    def test_content_admin_role_post_returns_201(self) -> None:
        admin = UserProfile(user_id=uuid.uuid4(), role=Role.CONTENT_ADMIN)
        fake = FakeSession(get_map={admin.user_id: admin})
        resp = self._client_real_auth(fake).post(
            "/v1/problems",
            json=_valid_body(),
            headers={"Authorization": f"Bearer {self._token_for(admin)}"},
        )
        assert resp.status_code == 201, resp.text

    # ── GET은 봉인 범위 밖 — 무인증 유지 회귀(과확대 방지) ──
    def test_unauthenticated_get_single_still_public(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = self._client_real_auth(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 200

    def test_unauthenticated_get_list_still_public(self) -> None:
        resp = self._client_real_auth(FakeSession()).get("/v1/problems")
        assert resp.status_code == 200

    def test_unauthenticated_get_steps_still_public(self) -> None:
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = self._client_real_auth(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 200


class TestPublicCatalogExposure:
    """PB-08 — 공개 카탈로그 노출 계약(무엇이 보이는가).

    두 축을 *따로* 변별한다: `_pending_problem()`은 검수 축만, `_metadata_only_problem()`은
    저작권 축만 위반하므로, 한쪽 게이트만 무력화해도 대응하는 테스트가 red가 된다(두 축을
    하나로 합치는 회귀도 잡힌다).

    목록 경로의 *실제 SQL 필터링*은 살아있는 Postgres가 필요해 이 sandbox에서는 검증하지
    못한다(`test_me_review_status_gate.py`가 인정한 것과 같은 한계). 그래서 목록은 두 겹으로
    본다 — ① 라우터가 실행에 넘긴 Select에 두 조건이 실려 나가는지(컴파일 SQL 화이트박스)
    ② FakeSession이 where를 무시하고 부적격 행을 그대로 돌려줘도 라우터의 행 단위 재확인
    (`_public_catalog_row`)이 응답에서 그 행을 실제로 뺐는지(행동 검증).
    """

    # ── 단건: 두 축 각각 404 ──
    def test_single_pending_problem_returns_404(self) -> None:
        """검수 축 — pending은 존재해도 404(존재 여부를 흘리지 않는다)."""
        problem = _pending_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 404, resp.text

    def test_single_metadata_only_source_returns_404(self) -> None:
        """저작권 축 — 평가원(본문 미보유)은 approved여도 404."""
        problem = _metadata_only_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 404, resp.text

    def test_single_approved_own_source_returns_200(self) -> None:
        """대조군 — 두 축 통과 문항은 그대로 200(게이트가 전부를 막지 않는다)."""
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 200, resp.text

    # ── 목록 ①: 두 조건이 SQL에 실려 나가는가 ──
    def test_list_sql_carries_both_gates(self) -> None:
        fake = FakeSession()
        assert _client(fake).get("/v1/problems").status_code == 200
        assert len(fake.executed_stmts) == 1
        compiled = str(
            fake.executed_stmts[0].compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        # 축① 저작권 — 본문 미보유 출처 3종이 NOT IN에 실려야 한다.
        assert "NOT IN" in compiled
        for blocked in ("평가원", "EBS", "교과서"):
            assert blocked in compiled, compiled
        # 축② 검수 — approved 등호 조건이 *별도로* 있어야 한다(두 축을 합치지 않는다).
        assert "review_status" in compiled and "approved" in compiled, compiled

    # ── 목록 ②: 부적격 행이 응답에서 실제로 빠지는가 ──
    def test_list_drops_pending_and_metadata_only_rows(self) -> None:
        approved = _sample_problem()
        fake = FakeSession(
            list_rows=[_pending_problem(), approved, _metadata_only_problem()],
        )
        resp = _client(fake).get("/v1/problems")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [row["problem_id"] for row in body] == [str(approved.problem_id)]

    # ── 하위 리소스: 부모가 부적격이면 함께 404 ──
    def test_steps_404_when_parent_pending(self) -> None:
        problem = _pending_problem()
        fake = FakeSession(
            get_map={problem.problem_id: problem},
            list_rows=[_sample_step(problem.problem_id, 1)],
        )
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 404, resp.text

    def test_steps_404_when_parent_metadata_only(self) -> None:
        problem = _metadata_only_problem()
        fake = FakeSession(
            get_map={problem.problem_id: problem},
            list_rows=[_sample_step(problem.problem_id, 1)],
        )
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/steps")
        assert resp.status_code == 404, resp.text

    def test_relations_404_when_parent_pending(self) -> None:
        problem = _pending_problem()
        fake = FakeSession(
            get_map={problem.problem_id: problem},
            list_rows=[_sample_relation(problem.problem_id, uuid.uuid4())],
        )
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}/relations")
        assert resp.status_code == 404, resp.text

    # ── 정답 축 리댁션(결정 동결) ──
    def test_single_get_redacts_answer_fields(self) -> None:
        """무인증 공개 GET은 정답 축 4필드를 서버가 None으로 비운다."""
        problem = _answer_bearing_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).get(f"/v1/problems/{problem.problem_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for field in ("answer", "answer_explanation", "multiple_answers", "distractor_map"):
            assert body[field] is None, f"{field}가 공개 GET 응답에 남아 있다: {body[field]!r}"
        # 리댁션이 응답 전체를 비우지는 않는다(비정답 필드는 그대로).
        assert body["subject"] == "미적분"

    def test_list_get_redacts_answer_fields(self) -> None:
        problem = _answer_bearing_problem()
        resp = _client(FakeSession(list_rows=[problem])).get("/v1/problems")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        for field in ("answer", "answer_explanation", "multiple_answers", "distractor_map"):
            assert body[0][field] is None, f"{field}가 공개 목록 응답에 남아 있다"

    def test_admin_write_path_is_not_redacted(self) -> None:
        """PATCH(=RequireContentAdmin) 응답은 리댁션 대상이 아니다 — 관리자는 정답을 봐야 한다."""
        problem = _sample_problem()
        fake = FakeSession(get_map={problem.problem_id: problem})
        resp = _client(fake).patch(
            f"/v1/problems/{problem.problem_id}",
            json={"answer": "42", "answer_explanation": "해설"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["answer"] == "42"
        assert resp.json()["answer_explanation"] == "해설"
