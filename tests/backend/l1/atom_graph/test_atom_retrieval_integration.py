"""원자 의미검색 *조회 좌석* 통합테스트 — S0-4a (WHYMATH_RUN_INTEGRATION 게이트).

`test_concept_retrieval_integration.py`(구 437 좌석 통합)의 *원자 백본* 미러다. 마이그레이션
head가 적용된 **실 pgvector PostgreSQL**(`atom_embedding`·`atom_node` 테이블 + `vector` 확장)에
`populate_atom_embeddings`(Phase 2b 적재) + `AtomNodeStore.upsert`(Phase 2a 메타) →
`search_atoms`(S0-4a 조회) 라운드트립을 건다. 좌석이 적재 임베딩을 실제로 질의해 관련 원자를 상위에
올리고, `atom_node` 조인으로 안전 메타(name_ko·subject_area)를 붙이는지 본다. PG/pgvector 미도달
시 graceful skip. 단위 경로(`test_atom_retrieval.py`)는 PG 없이 hermetic.

검증:
  ① populate→search 라운드트립(질의와 토큰 공유 원자가 상위·atom_code 반환·similarity 범위)
  ② atom_node enrich(name_ko·subject_area가 hit에 붙음·미적재 code는 None graceful)
  ③ top_k 컷·④ memory 모드 graceful(vector_store=memory면 빈 결과 — 좌석 가드)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로
`FakeEmbeddingProvider(dim=settings.embedding_dim)`로 그 차원 결정론 벡터를 만든다(라이브 모델
불요·hermetic하면서 실 pgvector 왕복).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.atom_graph.atom_node_projection import (
    AtomNodeRecord,
    AtomNodeStore,
)
from whymath_backend.l1.atom_graph.embedding import AtomText, populate_atom_embeddings
from whymath_backend.l1.atom_graph.retrieval import search_atoms
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(원자 code 규약·정리 대상). 실 데이터 code와 충돌하지 않도록 IT- 접두.
_CODE_NEAR = "IT-RETR-NEAR"
_CODE_FAR = "IT-RETR-FAR"


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
    """실 PG 도달 + `atom_embedding`·`atom_node` 테이블 존재(마이그레이션 적용) 여부."""
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
    """테스트가 적재한 행을 정리(잔여 방지) — code 키 기준 두 테이블 삭제."""
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


def _pgvector_settings() -> Settings:
    """vector_store=pgvector Settings — 좌석 memory 가드를 통과해 실 search 경로를 타게."""
    return Settings(vector_store="pgvector")


def _meta_record(code: str, *, name_ko: str, subject_area: str) -> AtomNodeRecord:
    """enrich용 최소 원자 메타 레코드(안전 필드만·본문 0)."""
    return AtomNodeRecord(
        code=code,
        name_ko=name_ko,
        level="세부개념",
        parent_code=None,
        school_level="고등",
        subject_area=subject_area,
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


class TestSearchRoundtrip:
    """① populate→search 라운드트립 + ② atom_node enrich."""

    def test_populate_then_search_ranks_and_enriches(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        # Fake는 bag-of-words 해시 — 질의와 토큰을 공유하는 원자가 코사인↑(near가 far보다 상위).
        near = AtomText(code=_CODE_NEAR, text="극한 수렴 다가감 정의")
        far = AtomText(code=_CODE_FAR, text="행렬 벡터 좌표 평면 기울기")
        keys = [_CODE_NEAR, _CODE_FAR]
        try:
            count = populate_atom_embeddings([near, far], provider, settings=settings)
            assert count == 2
            # near에만 메타 적재 — enrich 붙음/미적재(far) None graceful 둘 다 확인.
            store = AtomNodeStore(settings=settings)
            store.upsert(_meta_record(_CODE_NEAR, name_ko="극한", subject_area="해석"))

            hits = search_atoms(
                "극한 수렴 다가감 설명", top_k=2, provider=provider, settings=settings
            )
            assert len(hits) == 2
            # 질의와 토큰 多 공유한 near가 1위·atom_code 키 반환.
            assert hits[0].atom_code == _CODE_NEAR
            assert hits[0].similarity >= hits[1].similarity
            for hit in hits:
                assert -1.0001 <= hit.similarity <= 1.0001
            # near는 메타 enrich(name_ko·subject_area)·far는 미적재라 None graceful.
            assert hits[0].name_ko == "극한"
            assert hits[0].subject_area == "해석"
            assert hits[0].review_status == "ai_estimated"  # 상수 적재
            assert hits[1].atom_code == _CODE_FAR
            assert hits[1].name_ko is None
            assert hits[1].subject_area is None
        finally:
            _cleanup(keys)

    def test_top_k_limits_results(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        atoms = [
            AtomText(code="IT-RETR-A", text="극한 수렴"),
            AtomText(code="IT-RETR-B", text="극한 정의"),
            AtomText(code="IT-RETR-C", text="극한 계산"),
        ]
        keys = [a.code for a in atoms]
        try:
            populate_atom_embeddings(atoms, provider, settings=settings)
            hits = search_atoms("극한", top_k=2, provider=provider, settings=settings)
            assert len(hits) == 2  # top_k 컷
        finally:
            _cleanup(keys)


class TestMemoryModeGraceful:
    """④ memory 모드 — 좌석 가드로 빈 결과(실 PG 무관·조용한 무동작 금지)."""

    def test_memory_mode_returns_empty(self) -> None:
        provider = FakeEmbeddingProvider(dim=Settings().embedding_dim)
        hits = search_atoms("극한", top_k=5, provider=provider, settings=Settings())
        assert hits == []
