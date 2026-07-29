"""원자 임베딩 pgvector 영속 *통합테스트* — Phase 2b (WHYMATH_RUN_INTEGRATION 게이트).

마이그레이션 head가 적용된 **실 pgvector PostgreSQL**(`atom_embedding` 테이블 + `vector` 확장)에
`AtomEmbeddingIndex` upsert/search를 라운드트립한다. CI `backend — 마이그레이션·통합(실 PG)` 잡이
`pgvector/pgvector:pg16` 서비스 + `alembic upgrade head` 후 `WHYMATH_RUN_INTEGRATION=1`로 실행한다
(기존 잡이 `pytest -m integration`으로 이 파일을 수집한다). PG/pgvector 미도달 시 graceful skip
(`test_concept_embedding_integration.py` 미러). 단위 경로(`test_atom_embedding.py`)는
PG 없이 hermetic.

검증:
  ① upsert→search 라운드트립(코사인 순위·similarity 값·근접 항목 상위·code 키 반환)
  ② upsert 멱등(같은 code 키 재적재 → 행 1개·값 갱신)
  ③ provider/model 필터(다른 임베딩 공간 행은 search에 안 잡힘)
  ④ dim 일치(마이그레이션 컬럼 vector(embedding_dim)에 그 차원 벡터만 적재 — 차원 정합)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로 *그 차원* 벡터를 넣어야
한다 — `FakeEmbeddingProvider(dim=settings.embedding_dim)`로 1024차원 결정론 벡터를 만든다(라이브
모델 다운로드 불요·hermetic하면서 실 PG 왕복). 임베딩 *의미* recall(진짜 동의어)은 라이브 모델
통합 몫이고, 여기선 *영속·검색·필터·code 키 배선*을 실 pgvector로 검증한다.
"""

from __future__ import annotations

import pytest
from whymath_backend.config import Settings
from whymath_backend.l1.atom_graph.embedding import (
    AtomEmbeddingIndex,
    AtomText,
    populate_atom_embeddings,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(원자 code 규약·정리 대상). 실 데이터 code와 충돌하지 않도록 it- 접두.
_CODE_NEAR = "IT-ATOM-NEAR"
_CODE_FAR = "IT-ATOM-FAR"


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — AtomEmbeddingIndex와 같은 드라이버/URL.

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
    """실 PG 도달 + `atom_embedding` 테이블 존재(마이그레이션 적용) 여부.

    SELECT count + 테이블 존재로 *마이그레이션 head가 적용된* pgvector PG인지 확인한다. 도달
    실패·테이블 부재면 False → graceful skip(로컬·미설정 환경 안전).
    """
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM atom_embedding"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[str]) -> None:
    """테스트가 적재한 행을 정리(잔여 방지) — code 키 기준 삭제."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM atom_embedding WHERE code = ANY(:keys)"),
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
) -> AtomEmbeddingIndex:
    """실 PG에 붙는 AtomEmbeddingIndex(엔진 미주입 → lazy sync 엔진 생성)."""
    return AtomEmbeddingIndex(provider_name=provider_name, model_name=model_name)


class TestAtomEmbeddingRoundtrip:
    """① upsert→search 라운드트립 — 코사인 순위·similarity·code 키."""

    def test_upsert_then_search_ranks_by_cosine(self) -> None:
        _skip_if_unreachable()
        dim = Settings().embedding_dim
        provider = FakeEmbeddingProvider(dim=dim)
        # 어휘가 겹치는 질의/항목은 코사인↑(Fake는 bag-of-words 해시). 질의와 토큰을 공유하는
        # 항목이 상위에 오는지(영속 search가 거리순 정렬) 확인.
        query_text = "기수 원리 개수 양 판단"
        near_text = "기수 원리 개수 양 핵심"  # 질의와 토큰 다수 공유 → 가까움
        far_text = "행렬 벡터 좌표 평면 기울기"  # 토큰 비공유 → 멂
        keys = [_CODE_NEAR, _CODE_FAR]
        try:
            index = _fake_index()
            index.upsert(keys[0], provider.embed([near_text])[0], source_text=near_text)
            index.upsert(keys[1], provider.embed([far_text])[0], source_text=far_text)

            hits = index.search(provider.embed([query_text])[0], top_k=2)
            assert len(hits) == 2
            # (code, similarity) 튜플. near가 far보다 상위(질의와 토큰 공유 多).
            assert hits[0][0] == keys[0]
            assert hits[0][1] >= hits[1][1]
            for _code, sim in hits:
                assert -1.0001 <= sim <= 1.0001
        finally:
            _cleanup(keys)

    def test_top_k_limits_rows(self) -> None:
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        keys = ["IT-ATOM-A", "IT-ATOM-B", "IT-ATOM-C"]
        try:
            index = _fake_index()
            for k in keys:
                index.upsert(k, provider.embed([k])[0], source_text=k)
            hits = index.search(provider.embed(["IT-ATOM-A"])[0], top_k=2)
            assert len(hits) == 2  # top_k 컷
        finally:
            _cleanup(keys)


class TestUpsertIdempotency:
    """② upsert 멱등 — 같은 code 키 재적재 시 행 1개·갱신."""

    def test_readd_same_code_key_updates_in_place(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key = "IT-ATOM-UPSERT"
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
                        text("SELECT count(*) FROM atom_embedding WHERE code = :k"),
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
        key_a = "IT-ATOM-SPACE-A"
        key_b = "IT-ATOM-SPACE-B"
        try:
            vec = provider.embed(["공통 토큰 표현"])[0]
            idx_space1 = AtomEmbeddingIndex(provider_name="fake", model_name="space-1")
            idx_space2 = AtomEmbeddingIndex(provider_name="fake", model_name="space-2")
            idx_space1.upsert(key_a, vec, source_text="공통 토큰 표현")
            idx_space2.upsert(key_b, vec, source_text="공통 토큰 표현")

            # space-1로 검색하면 space-2 행(key_b)은 안 보인다(model 필터).
            hits1 = idx_space1.search(vec, top_k=10)
            keys1 = {code for code, _sim in hits1}
            assert key_a in keys1
            assert key_b not in keys1
        finally:
            _cleanup([key_a, key_b])


class TestSubjectAxis:
    """⑤ subject 축(과목 확장 S1) — server_default 백필 + 교과 스코프 경계 실증."""

    def test_insert_without_subject_defaults_to_math(self) -> None:
        # 마이그레이션 후 subject *무지정* raw INSERT가 server_default '수학'으로 충전된다
        # (기존 행 무손상 백필과 같은 메커니즘 — 가산적·BREAKING-free 실증).
        _skip_if_unreachable()
        from sqlalchemy import text

        key = "IT-ATOM-SUBJECT-DEFAULT"
        dim = Settings().embedding_dim
        vec_literal = "[" + ",".join(["0.1"] * dim) + "]"
        try:
            engine = _sync_engine()
            try:
                with engine.begin() as conn:  # type: ignore[attr-defined]
                    conn.execute(
                        text(
                            "INSERT INTO atom_embedding "
                            "(code, embedding, provider, model, dim, text_hash) "
                            "VALUES (:k, CAST(:v AS vector), 'fake', 'fake-hash', :d, 'h')"
                        ),
                        {"k": key, "v": vec_literal, "d": dim},
                    )
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    subject = conn.execute(
                        text("SELECT subject FROM atom_embedding WHERE code = :k"),
                        {"k": key},
                    ).scalar_one()
                assert subject == "수학"
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup([key])

    def test_physics_scope_does_not_see_math_rows(self) -> None:
        # 경계 실증: 기본('수학') 스코프로 적재한 행이 subject='물리' 인스턴스의 search·
        # existing_text_hashes에 *안 잡힌다*(namespace = 테이블 × subject — 교과 혼입 0).
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key = "IT-ATOM-SUBJECT-SCOPE"
        try:
            vec = provider.embed(["교과 경계 공통 표현"])[0]
            math_index = _fake_index()  # 기본 subject='수학'
            math_index.upsert(key, vec, source_text="교과 경계 공통 표현")

            phys_index = AtomEmbeddingIndex(
                provider_name="fake", model_name="fake-hash", subject="물리"
            )
            # search 경계 — 물리 스코프에선 미회수, 수학 스코프(대조군)에선 회수.
            assert key not in {code for code, _sim in phys_index.search(vec, top_k=10)}
            assert key in {code for code, _sim in math_index.search(vec, top_k=10)}
            # skip-if-unchanged 경계 — 물리 스코프 조회엔 안 잡혀 "변경"으로 취급된다.
            assert phys_index.existing_text_hashes([key]) == {}
            assert key in math_index.existing_text_hashes([key])
        finally:
            _cleanup([key])


class TestPopulateE2E:
    """④ populate_atom_embeddings e2e — 표현 적재·dim 일치·code 키."""

    def test_populate_persists_atoms_with_matching_dim(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        atoms = [
            AtomText(code=_CODE_NEAR, text="기수 원리 개수 양"),
            AtomText(code=_CODE_FAR, text="합성함수 결합 순서"),
        ]
        keys = [a.code for a in atoms]
        try:
            count = populate_atom_embeddings(atoms, provider, settings=settings)
            assert count == 2
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT code, dim FROM atom_embedding "
                            "WHERE code = ANY(:keys) ORDER BY code"
                        ),
                        {"keys": keys},
                    ).all()
                # 두 원자 모두 적재되고, dim이 마이그레이션 컬럼 차원(embedding_dim)과 일치.
                assert {r.code for r in rows} == set(keys)
                for r in rows:
                    assert r.dim == settings.embedding_dim
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(keys)
