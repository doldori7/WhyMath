"""`GET /v1/concepts/search` HTTP 표면 통합테스트 — S0-4a 원자 전환 실증(실 PG 게이트).

`test_concepts_search.py`(hermetic·좌석 패치)가 결선을, 이 통합테스트가 *실 pgvector 왕복 +
런타임 원자 전환*을 못 박는다. 마이그레이션 head가 적용된 실 PG(`atom_embedding`·`atom_node`)에
원자 임베딩·메타를 적재한 뒤 엔드포인트를 TestClient로 호출해 **응답 `concept_id`가 원자 code를,
`domain`이 원자 subject_area를 담는지**(runtime truth source=원자) 실증한다. 구 437 기대는 없다.

PG/pgvector 미도달 시 graceful skip. provider는 `FakeEmbeddingProvider`(적재와 같은 fake/fake-hash
공간)를 dependency_override로 주입 — 라이브 모델 없이 실 pgvector를 왕복한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api.concepts import get_embedding_provider
from whymath_backend.app import create_app
from whymath_backend.config import Settings
from whymath_backend.db.session import get_session
from whymath_backend.l1.atom_graph.atom_node_projection import (
    AtomNodeRecord,
    AtomNodeStore,
)
from whymath_backend.l1.atom_graph.embedding import AtomText, populate_atom_embeddings
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

_CODE = "IT-API-ATOM-1"


def _sync_engine() -> object:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _pgvector_reachable() -> bool:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM atom_embedding"))
            conn.execute(text("SELECT count(*) FROM atom_node"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[str]) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(text("DELETE FROM atom_embedding WHERE code = ANY(:keys)"), {"keys": keys})
            conn.execute(text("DELETE FROM atom_node WHERE code = ANY(:keys)"), {"keys": keys})
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _pgvector_reachable():
        pytest.skip(
            "pgvector PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


class _FakeSession:
    """검색 경로는 DB 세션을 쓰지 않는다(get_session 오버라이드용 최소 세션)."""

    async def get(self, model: Any, pk: Any) -> None:
        return None

    async def execute(self, stmt: Any) -> Any:  # pragma: no cover — 검색 경로 미사용
        raise AssertionError("search 엔드포인트는 DB 세션을 사용하지 않는다")


def _client(provider: object) -> TestClient:
    app = create_app()

    def _provider_override() -> object:
        return provider

    async def _session_override() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_embedding_provider] = _provider_override
    app.dependency_overrides[get_session] = _session_override
    return TestClient(app)


@pytest.fixture
def _pgvector_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """엔드포인트가 pgvector 모드로 좌석·enabled 신호를 타게 env 고정 + 캐시 격리."""
    from whymath_backend.config import get_settings

    monkeypatch.setenv("WHYMATH_VECTOR_STORE", "pgvector")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_search_endpoint_returns_atom_code(_pgvector_env: None) -> None:
    _skip_if_unreachable()
    settings = Settings()  # env로 pgvector 반영됨
    provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
    keys = [_CODE]
    try:
        populate_atom_embeddings(
            [AtomText(code=_CODE, text="극한 수렴 다가감 정의")], provider, settings=settings
        )
        AtomNodeStore(settings=settings).upsert(
            AtomNodeRecord(
                code=_CODE,
                name_ko="극한",
                level="세부개념",
                parent_code=None,
                school_level="고등",
                subject_area="해석",
                subunit_code=None,
                cognitive_type=None,
                node_type=None,
                misconception_type=None,
                intrinsic_difficulty=None,
                standard_codes=(),
                transfer=None,
                transfer_example=None,
                atomicity=None,
            )
        )

        resp = _client(provider).get("/v1/concepts/search?q=극한 수렴 다가감&k=5")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["vector_store_enabled"] is True
        codes = [item["concept_id"] for item in body["results"]]
        # runtime truth source=원자 — concept_id 필드에 원자 code가 실린다(구 437 UC 아님).
        assert _CODE in codes
        item = next(i for i in body["results"] if i["concept_id"] == _CODE)
        assert item["name_ko"] == "극한"
        assert item["domain"] == "해석"  # subject_area가 domain 필드에 매핑
        assert item["review_status"] == "ai_estimated"
    finally:
        _cleanup(keys)
