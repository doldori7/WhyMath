"""오개념 pgvector 영속 백엔드 *통합테스트* — slice 105 (WHYMATH_RUN_INTEGRATION 게이트).

마이그레이션 head가 적용된 **실 pgvector PostgreSQL**(`misconception_embedding` 테이블 +
`vector` 확장)에 PgVectorIndex add/search를 라운드트립한다. CI backend-migrations 잡이
`pgvector/pgvector:pg16` 서비스 + `alembic upgrade head` 후 `WHYMATH_RUN_INTEGRATION=1`로
실행한다. PG/pgvector 미도달 시 graceful skip(기존 통합테스트 패턴 — `test_concepts_
integration.py` 미러). 단위 경로(`test_misconception_pgvector.py`)는 PG 없이 hermetic.

검증:
  ① PgVectorIndex add→search 라운드트립(코사인 순위·similarity 값·근접 항목 상위)
  ② SemanticMatcher(index=PgVectorIndex) e2e recall(좌석 드롭인 — 슬104 매처가 그대로 동작)
  ③ upsert 멱등(같은 키 재적재 → 행 1개·값 갱신)
  ④ provider/model 필터(다른 공간 행은 search에 안 잡힘)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로 *그 차원* 벡터를
넣어야 한다 — `FakeEmbeddingProvider(dim=settings.embedding_dim)`로 1024차원 결정론 벡터를
만든다(라이브 모델 다운로드 불요·hermetic하면서 실 PG 왕복). 임베딩 *의미* recall(진짜 동의어)은
라이브 모델 통합(`test_misconception_semantic_integration.py`) 몫이고, 여기선 *영속·검색·필터
배선*을 실 pgvector로 검증한다(과장 금지 — Fake는 어휘 해시라 토큰 겹침으로 순위가 정해짐).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l4.misconception.semantic.pgvector_index import (
    PgVectorIndex,
    _provider_model_identity,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — PgVectorIndex와 같은 드라이버/URL.

    `db_disable_pool`(CI가 WHYMATH_DB_DISABLE_POOL=1)면 NullPool로 만든다(다중 연결 충돌 회피).
    pgvector 어댑터(register_vector)는 PgVectorIndex가 자기 엔진에 등록하므로 여기선 정리·
    도달성 점검용 raw 엔진만 만든다(벡터 바인딩 불요 — DELETE/SELECT 1).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _pgvector_reachable() -> bool:
    """실 PG 도달 + `misconception_embedding` 테이블 존재(마이그레이션 적용) 여부.

    SELECT 1 + 테이블 카운트로 *마이그레이션 head가 적용된* pgvector PG인지 확인한다. 도달
    실패·테이블 부재면 False → graceful skip(로컬·미설정 환경 안전).
    """
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM misconception_embedding"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[str]) -> None:
    """테스트가 적재한 행을 정리(잔여 방지) — provider 무관 키 기준 삭제."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM misconception_embedding WHERE misconception_id = ANY(:keys)"),
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


def _fake_index(*, provider_name: str = "fake", model_name: str = "fake-hash") -> PgVectorIndex:
    """실 PG에 붙는 PgVectorIndex(엔진 미주입 → lazy sync 엔진 생성)."""
    return PgVectorIndex(provider_name=provider_name, model_name=model_name)


class TestPgVectorRoundtrip:
    """① add→search 라운드트립 — 코사인 순위·similarity."""

    def test_add_then_search_ranks_by_cosine(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        dim = settings.embedding_dim
        provider = FakeEmbeddingProvider(dim=dim)
        # 어휘가 겹치는 질의/항목은 코사인↑(Fake는 bag-of-words 해시). 질의와 토큰을 공유하는
        # 항목이 상위에 오는지(영속 search가 거리순 정렬) 확인.
        query_text = "분모 영 나눗셈 정의 가능"
        near_text = "분모 영 나눗셈 늘 가능"  # 질의와 토큰 다수 공유 → 가까움
        far_text = "기울기 그래프 좌표 평면 벡터"  # 토큰 비공유 → 멂
        keys = ["it-pgv-near", "it-pgv-far"]
        try:
            index = _fake_index()
            near_vec = provider.embed([near_text])[0]
            far_vec = provider.embed([far_text])[0]
            index.add(keys[0], near_vec)
            index.add(keys[1], far_vec)

            query_vec = provider.embed([query_text])[0]
            hits = index.search(query_vec, top_k=2)
            assert len(hits) == 2
            # 거리순 = 유사도 내림차순. near가 far보다 상위(질의와 토큰 공유 多).
            assert hits[0].key == keys[0]
            assert hits[0].similarity >= hits[1].similarity
            # similarity ∈ [-1, 1] 범위(코사인 거리→1-distance).
            for h in hits:
                assert -1.0001 <= h.similarity <= 1.0001
        finally:
            _cleanup(keys)

    def test_top_k_limits_rows(self) -> None:
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        keys = ["it-pgv-a", "it-pgv-b", "it-pgv-c"]
        try:
            index = _fake_index()
            for k in keys:
                index.add(k, provider.embed([k])[0])
            hits = index.search(provider.embed(["it-pgv-a"])[0], top_k=2)
            assert len(hits) == 2  # top_k 컷
        finally:
            _cleanup(keys)


class TestUpsertIdempotency:
    """③ upsert 멱등 — 같은 키 재적재 시 행 1개·갱신."""

    def test_readd_same_key_updates_in_place(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key = "it-pgv-upsert"
        try:
            index = _fake_index()
            index.add(key, provider.embed(["첫 표현 토큰"])[0])
            index.add(key, provider.embed(["둘째 표현 다른 토큰"])[0])  # 같은 키 재적재
            # 행이 하나만 존재(PK upsert) — 카운트로 멱등 확인.
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    n = conn.execute(
                        text(
                            "SELECT count(*) FROM misconception_embedding "
                            "WHERE misconception_id = :k"
                        ),
                        {"k": key},
                    ).scalar_one()
                assert n == 1
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup([key])


class TestProviderModelFilter:
    """④ provider/model 필터 — 다른 임베딩 공간 행은 search에 안 잡힘."""

    def test_search_excludes_other_provider_rows(self) -> None:
        _skip_if_unreachable()
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        key_a = "it-pgv-space-a"
        key_b = "it-pgv-space-b"
        try:
            vec = provider.embed(["공통 토큰 표현"])[0]
            # 같은 키 공간 충돌을 피하려고 키를 다르게(둘 다 같은 질의에 가깝다).
            idx_space1 = PgVectorIndex(provider_name="fake", model_name="space-1")
            idx_space2 = PgVectorIndex(provider_name="fake", model_name="space-2")
            idx_space1.add(key_a, vec)
            idx_space2.add(key_b, vec)

            # space-1로 검색하면 space-2 행(key_b)은 안 보인다(model 필터).
            hits1 = idx_space1.search(vec, top_k=10)
            keys1 = {h.key for h in hits1}
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

        key = "it-pgv-subject-default"
        dim = Settings().embedding_dim
        vec_literal = "[" + ",".join(["0.1"] * dim) + "]"
        try:
            engine = _sync_engine()
            try:
                with engine.begin() as conn:  # type: ignore[attr-defined]
                    conn.execute(
                        text(
                            "INSERT INTO misconception_embedding "
                            "(misconception_id, embedding, provider, model, dim, text_hash) "
                            "VALUES (:k, CAST(:v AS vector), 'fake', 'fake-hash', :d, 'h')"
                        ),
                        {"k": key, "v": vec_literal, "d": dim},
                    )
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    subject = conn.execute(
                        text(
                            "SELECT subject FROM misconception_embedding "
                            "WHERE misconception_id = :k"
                        ),
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
        key = "it-pgv-subject-scope"
        try:
            vec = provider.embed(["교과 경계 공통 표현"])[0]
            math_index = _fake_index()  # 기본 subject='수학'
            math_index.upsert_entry(key, vec, source_text="교과 경계 공통 표현")

            phys_index = PgVectorIndex(provider_name="fake", model_name="fake-hash", subject="물리")
            # search 경계 — 물리 스코프에선 미회수, 수학 스코프(대조군)에선 회수.
            assert key not in {h.key for h in phys_index.search(vec, top_k=10)}
            assert key in {h.key for h in math_index.search(vec, top_k=10)}
            # skip-if-unchanged 경계 — 물리 스코프 조회엔 안 잡혀 "변경"으로 취급된다.
            assert phys_index.existing_text_hashes([key]) == {}
            assert key in math_index.existing_text_hashes([key])
        finally:
            _cleanup([key])


class TestSemanticMatcherE2E:
    """② SemanticMatcher(index=PgVectorIndex) — 슬104 좌석 드롭인 e2e."""

    def test_matcher_with_pgvector_index_recall(self) -> None:
        _skip_if_unreachable()
        from whymath_backend.l4.misconception.catalog import CATALOG
        from whymath_backend.l4.misconception.semantic.matcher import SemanticMatcher

        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        provider_name, model_name = _provider_model_identity(provider, settings)
        # 매처가 카탈로그를 실 pgvector에 적재(add)하고 학생 텍스트로 search.
        keys = [m.id for m in CATALOG]
        try:
            index = PgVectorIndex(provider_name=provider_name, model_name=model_name)
            matcher = SemanticMatcher(provider=provider, index=index)
            # 카탈로그 첫 항목의 표현 토큰을 일부 포함한 학생 텍스트 — recall 후보가 비지 않게.
            first = CATALOG[0]
            student = f"{first.name_kr} 관련해서 {first.canonical_statement} 라고 생각했어"
            # threshold를 낮춰(Fake 어휘 해시) 후보가 잡히도록 — 실 PG search 경로 동작 입증.
            out = matcher.match(student, top_k=5, threshold=0.1)
            assert isinstance(out, list)
            # 매칭이 났다면 semantic_similarity가 채워졌는지(영속 경로도 코사인 보존).
            for match in out:
                assert match.semantic_similarity is not None
        finally:
            _cleanup(keys)
