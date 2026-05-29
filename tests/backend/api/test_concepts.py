"""concept API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic).

get_session 의존성을 가짜 세션으로 오버라이드해 *엔드포인트 결선*(상태코드·직렬화·404/409/
422 분기·commit/rollback 호출)을 검증한다. 실제 SQL 정확성은 메인의 실 PG 검증과 통합
테스트(test_concepts_integration.py)가 담당한다 — db 모델 테스트가 from_schema/to_schema
왕복만 보는 것과 같은 분담(라이브 PG는 단위테스트 범위 밖).

app.py L3 테스트가 provider/cache/queue 가짜를 주입하는 것과 동형으로, 여기서는 DB 세션을
FastAPI dependency_overrides로 가짜화한다(create_app의 L3 기본 의존성은 모두 지연이라 구성만
으로 네트워크를 타지 않는다 — app.py docstring).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from whymath_backend.app import create_app
from whymath_backend.db.models.concept import Concept, ConceptEdge
from whymath_backend.db.session import get_session
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ConceptEdge as ConceptEdgeSchema
from whymath_backend.schema.enums import EdgeType

_VALID_BODY = {"code": "CAL-INT-FTC", "name_ko": "미적분학의 기본정리", "level": "단원"}


class _FakeScalars:
    def __init__(self, rows: list[Concept]) -> None:
        self._rows = rows

    def all(self) -> list[Concept]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Concept]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeSession:
    """AsyncSession 표면 일부를 모사 — 라우터가 부르는 메서드만 구현.

    get/execute는 미리 넣어둔 행을 돌려주고, add/commit/rollback/refresh는 호출 사실만
    기록한다(commit_error를 주면 commit이 그 예외를 던져 409 경로를 모사).
    """

    def __init__(
        self,
        *,
        get_map: dict[uuid.UUID, Concept] | None = None,
        list_rows: list[Concept] | None = None,
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

    async def get(self, model: Any, pk: uuid.UUID) -> Concept | None:
        return self._get_map.get(pk)

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self._list_rows)


def _client(fake: FakeSession) -> TestClient:
    """get_session을 가짜로 오버라이드한 TestClient."""
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _sample_concept(
    code: str = "CAL-INT-FTC", name: str = "미적분학의 기본정리"
) -> Concept:
    """from_schema로 만든 transient ORM(라이브 PG 불필요) — get/list 행 모사용."""
    return Concept.from_schema(ConceptSchema(code=code, name_ko=name, level="단원"))


def _sample_edge(from_id: uuid.UUID, to_id: uuid.UUID) -> ConceptEdge:
    return ConceptEdge.from_schema(
        ConceptEdgeSchema(
            from_concept_id=from_id,
            to_concept_id=to_id,
            edge_type=EdgeType.PREREQUISITE,
        )
    )


class TestCreate:
    def test_create_returns_201_and_commits(self) -> None:
        """정상 생성 → 201 + code 에코 + commit 호출."""
        fake = FakeSession()
        resp = _client(fake).post("/v1/concepts", json=_VALID_BODY)
        assert resp.status_code == 201, resp.text
        assert resp.json()["code"] == "CAL-INT-FTC"
        assert fake.committed is True
        assert len(fake.added) == 1

    def test_create_duplicate_code_returns_409(self) -> None:
        """code UNIQUE 충돌(IntegrityError) → 롤백 후 409(스택트레이스 없이)."""
        err = IntegrityError(
            "INSERT", {}, Exception("duplicate key value violates unique")
        )
        fake = FakeSession(commit_error=err)
        resp = _client(fake).post("/v1/concepts", json=_VALID_BODY)
        assert resp.status_code == 409
        assert fake.rolled_back is True
        assert fake.committed is False

    def test_create_invalid_body_returns_422(self) -> None:
        """필수 필드(name_ko·level) 누락 → 핸들러 전 422(검증은 시스템 경계)."""
        fake = FakeSession()
        resp = _client(fake).post("/v1/concepts", json={"code": "X"})
        assert resp.status_code == 422
        assert fake.committed is False


class TestRead:
    def test_read_existing_returns_200(self) -> None:
        """존재하는 UUID → 200 + to_schema 직렬화."""
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).get(f"/v1/concepts/{concept.concept_id}")
        assert resp.status_code == 200
        assert resp.json()["code"] == concept.code

    def test_read_missing_returns_404(self) -> None:
        """없는 UUID → 404."""
        fake = FakeSession()
        resp = _client(fake).get(f"/v1/concepts/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_read_invalid_uuid_returns_422(self) -> None:
        """경로 파라미터가 UUID가 아니면 422."""
        fake = FakeSession()
        resp = _client(fake).get("/v1/concepts/not-a-uuid")
        assert resp.status_code == 422


class TestList:
    def test_list_returns_rows(self) -> None:
        """행이 있으면 200 + 전부 직렬화."""
        rows = [_sample_concept("C-A", "가"), _sample_concept("C-B", "나")]
        fake = FakeSession(list_rows=rows)
        resp = _client(fake).get("/v1/concepts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {item["code"] for item in body} == {"C-A", "C-B"}

    def test_list_empty_returns_empty_array(self) -> None:
        """행이 없으면 200 + 빈 배열."""
        fake = FakeSession()
        resp = _client(fake).get("/v1/concepts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_rejects_out_of_range_pagination(self) -> None:
        """limit/offset 범위 위반 → 422(Query 제약)."""
        client = _client(FakeSession())
        assert client.get("/v1/concepts?limit=0").status_code == 422
        assert client.get("/v1/concepts?limit=999").status_code == 422
        assert client.get("/v1/concepts?offset=-1").status_code == 422


class TestEdges:
    def test_lists_edges_for_existing_concept(self) -> None:
        concept = _sample_concept()
        edge = _sample_edge(concept.concept_id, uuid.uuid4())
        fake = FakeSession(get_map={concept.concept_id: concept}, list_rows=[edge])
        resp = _client(fake).get(f"/v1/concepts/{concept.concept_id}/edges")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["edge_type"] == "PREREQUISITE"

    def test_edges_404_when_concept_missing(self) -> None:
        resp = _client(FakeSession()).get(f"/v1/concepts/{uuid.uuid4()}/edges")
        assert resp.status_code == 404

    def test_edges_empty_when_no_edges(self) -> None:
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).get(f"/v1/concepts/{concept.concept_id}/edges")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPatch:
    def test_patch_updates_field(self) -> None:
        """제공된 필드만 갱신 → 200 + 병합 결과."""
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).patch(
            f"/v1/concepts/{concept.concept_id}", json={"name_en": "Updated FTC"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name_en"] == "Updated FTC"
        assert fake.committed is True

    def test_patch_404_when_missing(self) -> None:
        resp = _client(FakeSession()).patch(
            f"/v1/concepts/{uuid.uuid4()}", json={"name_en": "x"}
        )
        assert resp.status_code == 404

    def test_patch_invalid_value_returns_422(self) -> None:
        """병합 결과가 스키마 위반(잘못된 enum) → 422."""
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).patch(
            f"/v1/concepts/{concept.concept_id}", json={"level": "없는레벨"}
        )
        assert resp.status_code == 422
        assert fake.committed is False

    def test_patch_unknown_field_returns_422(self) -> None:
        """미정의 필드(extra=forbid) → 422."""
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).patch(
            f"/v1/concepts/{concept.concept_id}", json={"nonexistent": 1}
        )
        assert resp.status_code == 422

    def test_patch_duplicate_code_returns_409(self) -> None:
        """code 변경이 UNIQUE 충돌 → 롤백 후 409."""
        concept = _sample_concept()
        err = IntegrityError("UPDATE", {}, Exception("duplicate key"))
        fake = FakeSession(get_map={concept.concept_id: concept}, commit_error=err)
        resp = _client(fake).patch(
            f"/v1/concepts/{concept.concept_id}", json={"code": "DUP-CODE"}
        )
        assert resp.status_code == 409
        assert fake.rolled_back is True


class TestDelete:
    def test_delete_returns_204(self) -> None:
        concept = _sample_concept()
        fake = FakeSession(get_map={concept.concept_id: concept})
        resp = _client(fake).delete(f"/v1/concepts/{concept.concept_id}")
        assert resp.status_code == 204
        assert fake.committed is True
        assert len(fake.deleted) == 1

    def test_delete_404_when_missing(self) -> None:
        resp = _client(FakeSession()).delete(f"/v1/concepts/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_409_when_referenced(self) -> None:
        """참조(FK)로 IntegrityError → 롤백 후 409."""
        concept = _sample_concept()
        err = IntegrityError("DELETE", {}, Exception("FK violation"))
        fake = FakeSession(get_map={concept.concept_id: concept}, commit_error=err)
        resp = _client(fake).delete(f"/v1/concepts/{concept.concept_id}")
        assert resp.status_code == 409
        assert fake.rolled_back is True
