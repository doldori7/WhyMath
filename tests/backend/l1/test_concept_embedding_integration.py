"""개념 임베딩 pgvector 영속 *통합테스트* — 슬3 (WHYMATH_RUN_INTEGRATION 게이트).

마이그레이션 head가 적용된 **실 pgvector PostgreSQL**(`concept_embedding` 테이블 + `vector`
확장)에 `ConceptEmbeddingIndex` upsert/search를 라운드트립한다. CI `backend — 마이그레이션·통합
(실 PG)` 잡이 `pgvector/pgvector:pg16` 서비스 + `alembic upgrade head` 후
`WHYMATH_RUN_INTEGRATION=1`로 실행한다(신규 CI 잡 불요 — 기존 잡이 `pytest -m integration
--ignore=l3`로 이 파일을 수집한다). PG/pgvector 미도달 시 graceful skip(L4
`test_misconception_pgvector_integration.py`·`test_concepts_integration.py` 미러). 단위 경로
(`test_concept_embedding.py`)는 PG 없이 hermetic.

검증:
  ① upsert→search 라운드트립(코사인 순위·similarity 값·근접 항목 상위·UC 키 반환)
  ② upsert 멱등(같은 UC 키 재적재 → 행 1개·값 갱신)
  ③ provider/model 필터(다른 임베딩 공간 행은 search에 안 잡힘)
  ④ dim 일치(마이그레이션 컬럼 vector(embedding_dim)에 그 차원 벡터만 적재 — 차원 정합)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로 *그 차원* 벡터를
넣어야 한다 — `FakeEmbeddingProvider(dim=settings.embedding_dim)`로 1024차원 결정론 벡터를
만든다(라이브 모델 다운로드 불요·hermetic하면서 실 PG 왕복). 임베딩 *의미* recall(진짜 동의어)은
라이브 모델 통합 몫이고, 여기선 *영속·검색·필터·UC 키 배선*을 실 pgvector로 검증한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import (
    ConceptEmbeddingIndex,
    ConceptText,
    populate_concept_embeddings,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(UC 규약·정리 대상). 실 데이터 UC와 충돌하지 않도록 it- 접두 slug.
_UC_NEAR = "UC.x.it.concept-near"
_UC_FAR = "UC.x.it.concept-far"


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — ConceptEmbeddingIndex와 같은 드라이버/URL.

    `db_disable_pool`(CI가 WHYMATH_DB_DISABLE_POOL=1)면 NullPool로 만든다(다중 연결 충돌 회피).
    정리·도달성 점검용 raw 엔진만 만든다(DELETE/SELECT 1 — 벡터 바인딩 불요).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _pgvector_reachable() -> bool:
    """실 PG 도달 + `concept_embedding` 테이블 존재(마이그레이션 적용) 여부.

    SELECT count + 테이블 존재로 *마이그레이션 head가 적용된* pgvector PG인지 확인한다. 도달
    실패·테이블 부재면 False → graceful skip(로컬·미설정 환경 안전).
    """
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


def _fake_index(
    *, provider_name: str = "fake", model_name: str = "fake-hash"
) -> ConceptEmbeddingIndex:
    """실 PG에 붙는 ConceptEmbeddingIndex(엔진 미주입 → lazy sync 엔진 생성)."""
    return ConceptEmbeddingIndex(provider_name=provider_name, model_name=model_name)


class TestConceptEmbeddingRoundtrip:
    """① upsert→search 라운드트립 — 코사인 순위·similarity·UC 키."""

    def test_upsert_then_search_ranks_by_cosine(self) -> None:
        _skip_if_unreachable()
        dim = Settings().embedding_dim
        provider = FakeEmbeddingProvider(dim=dim)
        # 어휘가 겹치는 질의/항목은 코사인↑(Fake는 bag-of-words 해시). 질의와 토큰을 공유하는
        # 항목이 상위에 오는지(영속 search가 거리순 정렬) 확인.
        query_text = "극한 수렴 다가감 정의"
        near_text = "극한 수렴 다가감 설명"  # 질의와 토큰 다수 공유 → 가까움
        far_text = "행렬 벡터 좌표 평면 기울기"  # 토큰 비공유 → 멂
        keys = [_UC_NEAR, _UC_FAR]
        try:
            index = _fake_index()
            index.upsert(keys[0], provider.embed([near_text])[0], source_text=near_text)
            index.upsert(keys[1], provider.embed([far_text])[0], source_text=far_text)

            hits = index.search(provider.embed([query_text])[0], top_k=2)
            assert len(hits) == 2
            # (concept_id, similarity) 튜플. near가 far보다 상위(질의와 토큰 공유 多).
            assert hits[0][0] == keys[0]
            assert hits[0][1] >= hits[1][1]
            for _cid, sim in hits:
                assert -1.0001 <= sim <= 1.0001
        finally:
            _cleanup(keys)

    def test_top_k_limits_rows(self) -> None:
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        keys = ["UC.x.it.a", "UC.x.it.b", "UC.x.it.c"]
        try:
            index = _fake_index()
            for k in keys:
                index.upsert(k, provider.embed([k])[0], source_text=k)
            hits = index.search(provider.embed(["UC.x.it.a"])[0], top_k=2)
            assert len(hits) == 2  # top_k 컷
        finally:
            _cleanup(keys)


class TestUpsertIdempotency:
    """② upsert 멱등 — 같은 UC 키 재적재 시 행 1개·갱신."""

    def test_readd_same_uc_key_updates_in_place(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key = "UC.x.it.upsert"
        try:
            index = _fake_index()
            index.upsert(key, provider.embed(["첫 표현 토큰"])[0], source_text="첫 표현 토큰")
            index.upsert(
                key, provider.embed(["둘째 표현 다른 토큰"])[0], source_text="둘째 표현 다른 토큰"
            )
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    n = conn.execute(
                        text("SELECT count(*) FROM concept_embedding WHERE concept_id = :k"),
                        {"k": key},
                    ).scalar_one()
                assert n == 1  # PK upsert — 행 1개(멱등)
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup([key])


class TestProviderModelFilter:
    """③ provider/model 필터 — 다른 임베딩 공간 행은 search에 안 잡힘."""

    def test_search_excludes_other_space_rows(self) -> None:
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key_a = "UC.x.it.space-a"
        key_b = "UC.x.it.space-b"
        try:
            vec = provider.embed(["공통 토큰 표현"])[0]
            idx_space1 = ConceptEmbeddingIndex(provider_name="fake", model_name="space-1")
            idx_space2 = ConceptEmbeddingIndex(provider_name="fake", model_name="space-2")
            idx_space1.upsert(key_a, vec, source_text="공통 토큰 표현")
            idx_space2.upsert(key_b, vec, source_text="공통 토큰 표현")

            # space-1로 검색하면 space-2 행(key_b)은 안 보인다(model 필터).
            hits1 = idx_space1.search(vec, top_k=10)
            keys1 = {cid for cid, _sim in hits1}
            assert key_a in keys1
            assert key_b not in keys1
        finally:
            _cleanup([key_a, key_b])


class TestPopulateE2E:
    """④ populate_concept_embeddings e2e — 표현 적재·dim 일치·UC 키."""

    def test_populate_persists_concepts_with_matching_dim(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        concepts = [
            ConceptText(concept_id=_UC_NEAR, text="극한 수렴 다가감"),
            ConceptText(concept_id=_UC_FAR, text="합성함수 결합 순서"),
        ]
        keys = [c.concept_id for c in concepts]
        try:
            count = populate_concept_embeddings(concepts, provider, settings=settings)
            assert count == 2
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT concept_id, dim FROM concept_embedding "
                            "WHERE concept_id = ANY(:keys) ORDER BY concept_id"
                        ),
                        {"keys": keys},
                    ).all()
                # 두 개념 모두 적재되고, dim이 마이그레이션 컬럼 차원(embedding_dim)과 일치.
                assert {r.concept_id for r in rows} == set(keys)
                for r in rows:
                    assert r.dim == settings.embedding_dim
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(keys)
