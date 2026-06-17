"""problem API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic).

concept 라우터 테스트(test_concepts.py)와 동형. 실제 SQL·필터는 통합테스트와 메인 PG 검증
담당(여기서는 상태코드·직렬화·404/409/422·commit/rollback 결선만).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from whymath_backend.app import create_app
from whymath_backend.db.models.problem import Problem, ProblemRelation, ProblemStep
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Curriculum, RelationType, SourceType, Subject
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.problem import ProblemRelation as ProblemRelationSchema
from whymath_backend.schema.problem import ProblemStep as ProblemStepSchema


def _valid_schema() -> ProblemSchema:
    """최소 유효 schema.Problem(자체생성 — 본문 보유 허용)."""
    return ProblemSchema(
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2015,
        valid_from_year=2014,
        subject=Subject.미적분,
        unit_codes=["CAL-INT-DEF"],
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
        return _FakeResult(self._list_rows)


def _client(fake: FakeSession) -> TestClient:
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _sample_problem() -> Problem:
    return Problem.from_schema(_valid_schema())


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
