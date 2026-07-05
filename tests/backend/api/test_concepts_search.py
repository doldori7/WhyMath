"""의미검색 엔드포인트 단위테스트 — `GET /v1/concepts/search` (hermetic·PG 불요·S0-4a 원자 전환).

(S0-4a) 이 엔드포인트는 이제 *원자* 조회 좌석(`search_atoms`)을 호출한다. 응답 스키마·경로는
클라 계약 안정을 위해 유지하되(`ConceptSearchResponse`), `concept_id` 필드는 *원자 code*를,
`domain` 필드는 원자 `subject_area`를 담는다. `search_atoms`(L1 조회 좌석)는 별 단위테스트
(`tests/backend/l1/atom_graph/test_atom_retrieval.py`)가 실 좌석 흐름을·통합테스트가 실 pgvector
라운드트립을 본다. 여기서는 *HTTP 표면 결선*만 못 박는다(TestClient + dependency_overrides):

  ① 요청 검증 — q 필수·비공백·길이·k 범위 위반 시 422(Query 제약)
  ② 응답 shape — query 에코·results[concept_id(=원자 code),similarity]·vector_store_enabled 신호
  ③ 라우팅 — /search가 /{concept_id}(UUID 경로)에 먹히지 않고 검색으로 매칭
  ④ provider 주입 — dependency_overrides[get_embedding_provider]로 Fake 주입(라이브 0)
  ⑤ memory 모드 신호 — vector_store_enabled=false + 빈 results(조용한 무동작 금지)

검색 *결과*가 있는 경로는 좌석(`search_atoms`)을 가짜로 패치해 HTTP 직렬화만 본다 — 실 코사인·
실 pgvector는 좌석 단위/통합 테스트 몫(여기선 표면이 좌석 결과를 응답 모델로 옳게 싣는지·
특히 atom_code→concept_id·subject_area→domain 매핑).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

import whymath_backend.api.concepts as concepts_api
from whymath_backend.api.concepts import get_embedding_provider
from whymath_backend.app import create_app
from whymath_backend.db.session import get_session
from whymath_backend.l1.atom_graph.retrieval import AtomSearchHit

# 원자 code 규약 예시(atom_embedding/atom_node와 동일 공간·runtime truth source).
_ATOM_A = "2수01-01-2"
_ATOM_B = "2수02-03-1"


class _FakeProvider:
    """라이브 없는 임베딩 제공자 — 단건 결정론 벡터(좌석을 패치하므로 실제로 호출되진 않음)."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class _FakeSession:
    """get_session 오버라이드용 최소 세션 — search 엔드포인트는 DB 세션을 쓰지 않으나,
    같은 앱의 다른 라우트와 일관되게 오버라이드해 둔다(검색 경로는 세션 미사용)."""

    async def get(self, model: Any, pk: Any) -> None:
        return None

    async def execute(self, stmt: Any) -> Any:  # pragma: no cover — 검색 경로 미사용
        raise AssertionError("search 엔드포인트는 DB 세션을 사용하지 않는다")


def _client(*, provider: object | None = None) -> TestClient:
    """get_embedding_provider(+get_session)를 오버라이드한 TestClient."""
    app = create_app()

    def _provider_override() -> object:
        return provider if provider is not None else _FakeProvider()

    async def _session_override() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_embedding_provider] = _provider_override
    app.dependency_overrides[get_session] = _session_override
    return TestClient(app)


# ──────────────────────────────────────────────────────────────────────────
# ① 요청 검증 — q 필수·비공백·k 범위
# ──────────────────────────────────────────────────────────────────────────
class TestRequestValidation:
    def test_missing_q_returns_422(self) -> None:
        resp = _client().get("/v1/concepts/search")
        assert resp.status_code == 422

    def test_empty_q_returns_422(self) -> None:
        # min_length=1 — 빈 문자열 거부.
        resp = _client().get("/v1/concepts/search?q=")
        assert resp.status_code == 422

    def test_k_out_of_range_returns_422(self) -> None:
        assert _client().get("/v1/concepts/search?q=극한&k=0").status_code == 422
        assert _client().get("/v1/concepts/search?q=극한&k=51").status_code == 422
        assert _client().get("/v1/concepts/search?q=극한&k=-1").status_code == 422

    def test_q_too_long_returns_422(self) -> None:
        # max_length=500 — 과대 질의 거부(임베딩 비용·DoS 방어).
        resp = _client().get("/v1/concepts/search", params={"q": "가" * 501})
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────
# ② 응답 shape + ④ provider 주입 (좌석 패치로 결과 직렬화 검증)
# ──────────────────────────────────────────────────────────────────────────
class TestResponseShape:
    def test_returns_ranked_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 좌석(search_atoms)을 가짜로 패치 — HTTP 표면이 좌석 결과(enrich 메타 포함)를 응답 모델로
        # 옳게 싣는지. atom_code→concept_id·subject_area→domain 매핑을 검증한다. _ATOM_A는 메타
        # enrich·_ATOM_B는 메타 없음(None graceful)로 둘 다 확인.
        captured: dict[str, Any] = {}

        def _fake_search(
            query_text: str,
            *,
            top_k: int,
            provider: object,
            reviewed_only: bool = False,
            **_kw: Any,
        ) -> list[AtomSearchHit]:
            captured["query"] = query_text
            captured["top_k"] = top_k
            captured["provider"] = provider
            captured["reviewed_only"] = reviewed_only
            return [
                AtomSearchHit(
                    atom_code=_ATOM_A,
                    similarity=0.91,
                    name_ko="극한",
                    subject_area="해석",
                    review_status="ai_estimated",
                ),
                AtomSearchHit(atom_code=_ATOM_B, similarity=0.42),  # 메타 미적재 → null
            ]

        monkeypatch.setattr(concepts_api, "search_atoms", _fake_search)
        # pgvector 모드 신호를 보려고 vector_store=pgvector로 설정 리로드.
        _force_pgvector(monkeypatch)

        provider = _FakeProvider()
        resp = _client(provider=provider).get("/v1/concepts/search?q=극한 수렴&k=5")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["query"] == "극한 수렴"
        assert body["vector_store_enabled"] is True
        # concept_id 필드에 *원자 code*가, domain 필드에 subject_area가 실린다(계약 안정).
        assert body["results"] == [
            {
                "concept_id": _ATOM_A,
                "similarity": 0.91,
                "name_ko": "극한",
                "domain": "해석",
                "review_status": "ai_estimated",
            },
            {
                "concept_id": _ATOM_B,
                "similarity": 0.42,
                "name_ko": None,
                "domain": None,
                "review_status": None,
            },
        ]
        # 좌석에 질의·top_k·주입 provider가 그대로 전달됐다. reviewed_only 기본 False.
        assert captured["query"] == "극한 수렴"
        assert captured["top_k"] == 5
        assert captured["provider"] is provider
        assert captured["reviewed_only"] is False

    def test_reviewed_only_param_passed_to_seat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ?reviewed_only=true 쿼리가 좌석에 그대로 전달된다(게이팅 필터 위임).
        captured: dict[str, Any] = {}

        def _fake_search(
            query_text: str,
            *,
            top_k: int,
            provider: object,
            reviewed_only: bool = False,
            **_kw: Any,
        ) -> list[AtomSearchHit]:
            captured["reviewed_only"] = reviewed_only
            return []

        monkeypatch.setattr(concepts_api, "search_atoms", _fake_search)
        resp = _client().get("/v1/concepts/search?q=극한&reviewed_only=true")
        assert resp.status_code == 200
        assert captured["reviewed_only"] is True

    def test_default_k_is_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def _fake_search(
            query_text: str, *, top_k: int, provider: object, **_kw: Any
        ) -> list[AtomSearchHit]:
            captured["top_k"] = top_k
            return []

        monkeypatch.setattr(concepts_api, "search_atoms", _fake_search)
        resp = _client().get("/v1/concepts/search?q=함수")
        assert resp.status_code == 200
        assert captured["top_k"] == concepts_api._SEARCH_DEFAULT_K

    def test_empty_results_serialize_as_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            concepts_api,
            "search_atoms",
            lambda *a, **k: [],  # noqa: ARG005 — 빈 결과 패치
        )
        resp = _client().get("/v1/concepts/search?q=없는질의")
        assert resp.status_code == 200
        assert resp.json()["results"] == []


# ──────────────────────────────────────────────────────────────────────────
# ③ 라우팅 — /search가 /{concept_id} UUID 경로에 먹히지 않음
# ──────────────────────────────────────────────────────────────────────────
class TestRouting:
    def test_search_path_not_parsed_as_concept_uuid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # /search가 GET /{concept_id}(UUID)보다 먼저 매칭돼야 한다 — UUID 파싱 422가 아니라 200.
        monkeypatch.setattr(
            concepts_api,
            "search_atoms",
            lambda *a, **k: [],  # noqa: ARG005
        )
        resp = _client().get("/v1/concepts/search?q=극한")
        assert resp.status_code == 200  # 404(미존재 개념)도 422(UUID 파싱)도 아님


# ──────────────────────────────────────────────────────────────────────────
# ⑤ memory 모드 신호 — vector_store_enabled=false + 빈 results
# ──────────────────────────────────────────────────────────────────────────
class TestMemoryModeSignal:
    def test_memory_mode_reports_disabled_and_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 기본(memory) 모드 — 좌석을 패치하지 않아도 실제 search_concepts가 빈 리스트를 돌려준다
        # (memory 가드). vector_store_enabled=false로 명시 신호(조용한 무동작 금지).
        _force_memory(monkeypatch)
        resp = _client().get("/v1/concepts/search?q=극한")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["vector_store_enabled"] is False
        assert body["results"] == []


# ──────────────────────────────────────────────────────────────────────────
# 설정 강제 헬퍼 — get_settings 캐시를 비우고 env로 vector_store를 고정
# ──────────────────────────────────────────────────────────────────────────
def _force_pgvector(monkeypatch: pytest.MonkeyPatch) -> None:
    """vector_store=pgvector로 설정(엔드포인트 enabled 신호용). lru_cache 비움."""
    from whymath_backend.config import get_settings

    monkeypatch.setenv("WHYMATH_VECTOR_STORE", "pgvector")
    get_settings.cache_clear()


def _force_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """vector_store=memory로 설정(기본). lru_cache 비움."""
    from whymath_backend.config import get_settings

    monkeypatch.setenv("WHYMATH_VECTOR_STORE", "memory")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """각 테스트 후 get_settings 캐시 격리(env monkeypatch는 pytest가 자동 복원)."""
    from whymath_backend.config import get_settings

    yield
    get_settings.cache_clear()
