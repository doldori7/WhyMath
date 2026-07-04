"""개념 메타 PG 프로젝션 + 검색 enrichment·게이팅 *통합테스트* — 소비 슬1 (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**(`concept_node` 테이블 + 슬3 `concept_embedding`)에
메타 적재 → 검색 enrich/게이팅 라운드트립을 건다. 슬3/4 통합테스트가 임베딩 적재·검색을 봤다면,
여기선 *메타 브리지(PG 프로젝션)*가 검색 결과에 안전 메타(name_ko·domain·review_status)를 실제로
붙이고 검수 게이팅을 거는지 본다(backend↔Neo4j 런타임 연결 0·PG 조인). CI `backend — 마이그레이션·
통합 (실 PG)` 잡이 `pgvector/pgvector:pg16` 서비스 + `alembic upgrade head` 후
`WHYMATH_RUN_INTEGRATION=1`로 수집·실행한다(신규 CI 잡 불요 — 기존 잡이 `pytest -m integration
--ignore=l3`로 `tests/backend/l1/`를 수집). PG 미도달 시 graceful skip(슬3/4 미러).

검증:
  ① populate_concept_nodes → fetch_node_meta 라운드트립(UC 키·안전 메타 채워짐·멱등)
  ② populate→search enrich(name_ko·domain·review_status가 hit에 붙음)
  ③ reviewed_only 게이팅(pending 개념 필터·reviewed만)
  ④ 메타 누락 graceful(concept_node에 없는 UC는 None — 검색 계속)

차원 정합(임베딩): 슬3 `concept_embedding`은 `vector(embedding_dim)`이므로 검색 적재엔
`FakeEmbeddingProvider(dim=settings.embedding_dim)`로 그 차원 결정론 벡터를 쓴다. 메타 적재는
임베딩 무관(순수 메타 upsert). 여기선 *메타 브리지 배선*(PG 조인 enrich·게이팅 필터)을 실 PG로
검증한다(Fake는 bag-of-words 해시라 토큰 겹침이 코사인 신호).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import (
    ConceptText,
    populate_concept_embeddings,
)
from whymath_backend.l1.concept_graph.node_projection import (
    ConceptNodeRecord,
    fetch_node_meta,
    populate_concept_nodes,
)
from whymath_backend.l1.concept_graph.retrieval import search_concepts
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(UC 규약·정리 대상). 실 데이터 UC와 충돌하지 않도록 it- 접두 slug.
_UC_REVIEWED = "UC.x.it.node-reviewed"
_UC_PENDING = "UC.x.it.node-pending"
_UC_NOMETA = "UC.x.it.node-nometa"


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·도달성 점검용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + `concept_node`·`concept_embedding` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM concept_node"))
            conn.execute(text("SELECT count(*) FROM concept_embedding"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup_nodes(keys: list[str]) -> None:
    """concept_node 적재 행 정리(UC 키 기준)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM concept_node WHERE concept_id = ANY(:keys)"),
                {"keys": keys},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup_embeddings(keys: list[str]) -> None:
    """concept_embedding 적재 행 정리(UC 키 기준)."""
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
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _pgvector_settings() -> Settings:
    """vector_store=pgvector Settings — 검색 좌석 memory 가드를 통과해 실 경로를 타게."""
    return Settings(vector_store="pgvector")


def _node(concept_id: str, *, name_ko: str, review_status: str) -> ConceptNodeRecord:
    return ConceptNodeRecord(
        concept_id=concept_id,
        name_ko=name_ko,
        domain="[고]미적분",
        review_status=review_status,
        standard_codes=("10공수1-01-01",),
        ccss_code=None,
        difficulty_tier=3,
        behavior_skills=("skill.factorization",),
    )


class TestNodeRoundtrip:
    """① populate → fetch_node_meta 라운드트립 — UC 키·안전 메타·멱등."""

    def test_populate_then_fetch_meta(self) -> None:
        _skip_if_unreachable()
        keys = [_UC_REVIEWED, _UC_PENDING]
        try:
            records = [
                _node(_UC_REVIEWED, name_ko="극한", review_status="reviewed"),
                _node(_UC_PENDING, name_ko="연속", review_status="pending"),
            ]
            count = populate_concept_nodes(records, settings=Settings())
            assert count == 2

            meta = fetch_node_meta(keys, settings=Settings())
            assert set(meta) == set(keys)
            assert meta[_UC_REVIEWED].name_ko == "극한"
            assert meta[_UC_REVIEWED].review_status == "reviewed"
            assert meta[_UC_REVIEWED].domain == "[고]미적분"
            assert meta[_UC_PENDING].review_status == "pending"
        finally:
            _cleanup_nodes(keys)

    def test_upsert_idempotent_updates_in_place(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        key = "UC.x.it.node-upsert"
        try:
            populate_concept_nodes(
                [_node(key, name_ko="첫 이름", review_status="pending")],
                settings=Settings(),
            )
            populate_concept_nodes(
                [_node(key, name_ko="둘째 이름", review_status="reviewed")],
                settings=Settings(),
            )
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT name_ko, review_status, behavior_skills FROM concept_node "
                            "WHERE concept_id = :k"
                        ),
                        {"k": key},
                    ).all()
                # PK upsert — 행 1개·값 갱신(멱등).
                assert len(rows) == 1
                assert rows[0].name_ko == "둘째 이름"
                assert rows[0].review_status == "reviewed"
                # behavior_skills 참조 배열 왕복(Phase 2b-1·TEXT[]).
                assert rows[0].behavior_skills == ["skill.factorization"]
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup_nodes([key])


class TestSearchEnrichment:
    """② populate→search enrich — name_ko·domain·review_status가 hit에 붙음."""

    def test_search_enriches_with_node_meta(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        emb_keys = [_UC_REVIEWED]
        node_keys = [_UC_REVIEWED]
        try:
            # 임베딩 적재(검색 대상) + 메타 적재(enrich 대상) — 같은 UC 키.
            populate_concept_embeddings(
                [ConceptText(concept_id=_UC_REVIEWED, text="극한 수렴 다가감 정의")],
                provider,
                settings=settings,
            )
            populate_concept_nodes(
                [_node(_UC_REVIEWED, name_ko="극한", review_status="reviewed")],
                settings=settings,
            )

            hits = search_concepts(
                "극한 수렴 다가감 설명", top_k=5, provider=provider, settings=settings
            )
            # 검색이 _UC_REVIEWED를 잡고, 메타가 붙는다(name_ko·domain·review_status).
            match = next((h for h in hits if h.concept_id == _UC_REVIEWED), None)
            assert match is not None
            assert match.name_ko == "극한"
            assert match.domain == "[고]미적분"
            assert match.review_status == "reviewed"
        finally:
            _cleanup_embeddings(emb_keys)
            _cleanup_nodes(node_keys)


class TestReviewedOnlyGating:
    """③ reviewed_only 게이팅 — pending 필터·reviewed만(실 PG 조인 필터)."""

    def test_reviewed_only_filters_pending(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        emb_keys = [_UC_REVIEWED, _UC_PENDING]
        node_keys = [_UC_REVIEWED, _UC_PENDING]
        try:
            # 토큰을 공유해 둘 다 검색에 잡히게 한다(reviewed·pending 한 쌍).
            populate_concept_embeddings(
                [
                    ConceptText(concept_id=_UC_REVIEWED, text="극한 수렴 정의 검수완료"),
                    ConceptText(concept_id=_UC_PENDING, text="극한 수렴 정의 검수대기"),
                ],
                provider,
                settings=settings,
            )
            populate_concept_nodes(
                [
                    _node(_UC_REVIEWED, name_ko="극한검수", review_status="reviewed"),
                    _node(_UC_PENDING, name_ko="극한대기", review_status="pending"),
                ],
                settings=settings,
            )

            # 게이팅 OFF(기본): 둘 다 노출 가능(recall).
            all_hits = search_concepts(
                "극한 수렴 정의", top_k=10, provider=provider, settings=settings
            )
            all_keys = {h.concept_id for h in all_hits}
            assert _UC_REVIEWED in all_keys
            assert _UC_PENDING in all_keys

            # 게이팅 ON: pending 제외·reviewed만.
            gated = search_concepts(
                "극한 수렴 정의",
                top_k=10,
                provider=provider,
                reviewed_only=True,
                settings=settings,
            )
            gated_keys = {h.concept_id for h in gated}
            assert _UC_REVIEWED in gated_keys
            assert _UC_PENDING not in gated_keys
        finally:
            _cleanup_embeddings(emb_keys)
            _cleanup_nodes(node_keys)


class TestMissingMetaGraceful:
    """④ 메타 누락 graceful — concept_node에 없는 UC는 None(검색 계속)."""

    def test_search_hit_without_node_meta_has_none(self) -> None:
        _skip_if_unreachable()
        settings = _pgvector_settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        emb_keys = [_UC_NOMETA]
        try:
            # 임베딩만 적재하고 concept_node 메타는 *적재하지 않는다*(누락 상황).
            populate_concept_embeddings(
                [ConceptText(concept_id=_UC_NOMETA, text="행렬 벡터 좌표 고유값")],
                provider,
                settings=settings,
            )
            # concept_node에 이 UC가 없도록 보장(잔여 제거).
            _cleanup_nodes([_UC_NOMETA])

            hits = search_concepts(
                "행렬 벡터 좌표 고유값", top_k=5, provider=provider, settings=settings
            )
            match = next((h for h in hits if h.concept_id == _UC_NOMETA), None)
            assert match is not None  # 검색은 계속(임베딩으로 잡힘)
            # 메타 없음 → None graceful(예외 아님·검색 결과에 포함).
            assert match.name_ko is None
            assert match.domain is None
            assert match.review_status is None
        finally:
            _cleanup_embeddings(emb_keys)
            _cleanup_nodes([_UC_NOMETA])
