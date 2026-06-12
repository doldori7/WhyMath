"""개념 의미검색 *조회 좌석* 통합테스트 — 슬4 (WHYMATH_RUN_INTEGRATION 게이트).

마이그레이션 head가 적용된 **실 pgvector PostgreSQL**(`concept_embedding` 테이블 + `vector`
확장)에 `populate_concept_embeddings`(슬3 적재) → `search_concepts`(슬4 조회) 라운드트립을 건다.
슬3 통합테스트가 `ConceptEmbeddingIndex.upsert/search`를 직접 검증했다면, 여기선 *조회 좌석*
(`search_concepts`: query 임베딩→search→랭킹)이 적재 임베딩을 실제로 질의해 관련 개념을 상위에
올리는지 본다. CI `backend — 마이그레이션·통합 (실 PG)` 잡이 `pgvector/pgvector:pg16` 서비스 +
`alembic upgrade head` 후 `WHYMATH_RUN_INTEGRATION=1`로 수집·실행한다(신규 CI 잡 불요 — 기존
잡이 `pytest -m integration --ignore=l3`로 `tests/backend/l1/`를 수집한다). PG/pgvector 미도달 시
graceful skip(슬3 `test_concept_embedding_integration.py` 미러). 단위 경로
(`test_concept_retrieval.py`)는 PG 없이 hermetic.

검증:
  ① populate→search 라운드트립(질의와 토큰 공유 개념이 상위·UC 키 반환·similarity 범위)
  ② top_k 컷(적재 N개 중 상위 k만)
  ③ memory 모드 graceful(vector_store=memory면 빈 결과 — 좌석 가드)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로 `FakeEmbeddingProvider
(dim=settings.embedding_dim)`로 그 차원 결정론 벡터를 만든다(라이브 모델 다운로드 불요·hermetic
하면서 실 pgvector 왕복). 임베딩 *의미* recall(진짜 동의어)은 라이브 모델 몫이고, 여기선 좌석이
*적재 임베딩을 질의해 거리순 랭킹을 돌려주는 배선*을 실 pgvector로 검증한다(Fake는 bag-of-words
해시라 토큰 겹침이 코사인 신호).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import (
    ConceptText,
    populate_concept_embeddings,
)
from whymath_backend.l1.concept_graph.retrieval import search_concepts
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(UC 규약·정리 대상). 실 데이터 UC와 충돌하지 않도록 it- 접두 slug.
_UC_NEAR = "UC.x.it.retrieval-near"
_UC_FAR = "UC.x.it.retrieval-far"


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·도달성 점검용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _pgvector_reachable() -> bool:
    """실 PG 도달 + `concept_embedding` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM concept_embedding"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[str]) -> None:
    """테스트가 적재한 행을 정리(잔여 방지) — UC 키 기준 삭제."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM concept_embedding WHERE concept_id = ANY(:keys)"),
                {"keys": keys},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _pgvector_reachable():
        pytest.skip(
            "pgvector PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _pgvector_settings() -> Settings:
    """vector_store=pgvector Settings — 좌석 memory 가드를 통과해 실 search 경로를 타게."""
    return Settings(vector_store="pgvector")


class TestSearchRoundtrip:
    """① populate→search 라운드트립 — 토큰 공유 개념 상위·UC 키·similarity 범위."""

    def test_populate_then_search_ranks_related_concept_top(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        # Fake는 bag-of-words 해시 — 질의와 토큰을 공유하는 개념이 코사인↑(near가 far보다 상위).
        near = ConceptText(concept_id=_UC_NEAR, text="극한 수렴 다가감 정의")
        far = ConceptText(concept_id=_UC_FAR, text="행렬 벡터 좌표 평면 기울기")
        keys = [_UC_NEAR, _UC_FAR]
        try:
            count = populate_concept_embeddings(
                [near, far], provider, settings=settings
            )
            assert count == 2

            hits = search_concepts(
                "극한 수렴 다가감 설명", top_k=2, provider=provider, settings=settings
            )
            assert len(hits) == 2
            # 질의와 토큰 多 공유한 near가 1위.
            assert hits[0].concept_id == _UC_NEAR
            assert hits[0].similarity >= hits[1].similarity
            for hit in hits:
                assert -1.0001 <= hit.similarity <= 1.0001
        finally:
            _cleanup(keys)

    def test_top_k_limits_results(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        concepts = [
            ConceptText(concept_id="UC.x.it.r-a", text="극한 수렴"),
            ConceptText(concept_id="UC.x.it.r-b", text="극한 정의"),
            ConceptText(concept_id="UC.x.it.r-c", text="극한 계산"),
        ]
        keys = [c.concept_id for c in concepts]
        try:
            populate_concept_embeddings(concepts, provider, settings=settings)
            hits = search_concepts(
                "극한", top_k=2, provider=provider, settings=settings
            )
            assert len(hits) == 2  # top_k 컷
        finally:
            _cleanup(keys)


class TestMemoryModeGraceful:
    """③ memory 모드 — 좌석 가드로 빈 결과(실 PG 무관·조용한 무동작 금지)."""

    def test_memory_mode_returns_empty(self) -> None:
        # vector_store=memory면 search_concepts가 search 전에 빈 리스트를 돌려준다(영속 store 부재).
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        hits = search_concepts("극한", top_k=5, provider=provider, settings=Settings())
        assert hits == []
