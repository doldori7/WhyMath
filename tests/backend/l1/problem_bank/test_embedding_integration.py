"""문제 발문 임베딩 dedup pgvector 영속 *통합테스트* — S2-c (integration 마커·실 PG).

마이그레이션 head가 적용된 **실 pgvector PostgreSQL**(`problem_embedding` 테이블 + `vector` 확장)에
`ProblemEmbeddingIndex` upsert/search·과유사 게이트를 라운드트립한다. CI `backend — 마이그레이션·
통합(실 PG)` 잡이 `pgvector/pgvector:pg16` 서비스 + `alembic upgrade head` 후 실행한다
(`pytest -m integration`). PG/pgvector 미도달 시 graceful skip(`atom_graph/test_atom_embedding_
integration.py` 미러). 단위 경로(`test_embedding.py`)는 PG 없이 hermetic.

검증:
  ① 실 코퍼스 4문제 임베딩 적재(populate)·dim 일치·problem_id 키 반환
  ② 멱등(2회 populate → count 안정·행 수 안정)
  ③ 과유사 판정 실증 — 같은 발문 문자열 후보는 near_duplicate=True·다른 단원 문제는 False
  ④ search 코사인 정합(같은 발문 상위·다른 발문 하위·similarity 범위)

차원 정합: 마이그레이션 컬럼은 `vector(embedding_dim)`(기본 1024)이므로 `FakeEmbeddingProvider
(dim=settings.embedding_dim)`로 그 차원 결정론 벡터를 만든다(라이브 모델 불요·hermetic하면서 실
pgvector 왕복). Fake는 *어휘 해시*(bag-of-words)라 **같은 발문 문자열은 동일 벡터→코사인 1.0**,
어휘가 완전히 다르면 직교에 가깝다 — 과유사 게이트의 identical/disjoint 경계를 실 PG로 못 박는다
(진짜 패러프레이즈 recall은 라이브 모델 통합 몫). problem_embedding은 느슨참조(하드 FK 없음)라
`problem` 행을 먼저 넣지 않고 임베딩만 적재한다(atom_embedding 동형·적재 분리).
"""

from __future__ import annotations

import uuid

import pytest
from whymath_backend.config import Settings
from whymath_backend.l1.problem_bank.embedding import (
    ProblemEmbeddingIndex,
    find_near_duplicates,
    is_near_duplicate,
    populate_problem_embeddings,
    problem_embedding_text,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider
from whymath_backend.schema.enums import Curriculum, SourceType, Subject
from whymath_backend.schema.problem import Problem

pytestmark = pytest.mark.integration

# 통합테스트 적재 problem_id(정리 대상·결정론 UUID). 실 데이터와 충돌 무관(전용 네임스페이스).
_PID_LIMIT = uuid.UUID("aaaa0000-0000-0000-0000-000000000001")
_PID_DERIV = uuid.UUID("aaaa0000-0000-0000-0000-000000000002")
_PID_MATRIX = uuid.UUID("aaaa0000-0000-0000-0000-000000000003")
_PID_PROB = uuid.UUID("aaaa0000-0000-0000-0000-000000000004")
_ALL_PIDS = [_PID_LIMIT, _PID_DERIV, _PID_MATRIX, _PID_PROB]


def _make_problem(problem_id: uuid.UUID, question_text: str) -> Problem:
    """최소 자체생성 Problem — 발문만 지정(본문 불변식 통과)."""
    return Problem(
        problem_id=problem_id,
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2027,
        subject=Subject.미적분,
        unit_codes=["CAL-DIFF"],
        question_text=question_text,
    )


# 실 코퍼스 4문제 — 어휘가 단원별로 갈리게 짜 Fake bag-of-words 코사인을 결정론적으로 만든다.
_CORPUS = [
    _make_problem(_PID_LIMIT, "극한 값 을 구하 는 문제"),
    _make_problem(_PID_DERIV, "도함수 를 구하 는 문제"),
    _make_problem(_PID_MATRIX, "행렬 곱셈 계산"),
    _make_problem(_PID_PROB, "확률 분포 기댓값 계산"),
]


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — ProblemEmbeddingIndex와 같은 드라이버/URL."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _pgvector_reachable() -> bool:
    """실 PG 도달 + `problem_embedding` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM problem_embedding"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[uuid.UUID]) -> None:
    """테스트가 적재한 행을 정리(잔여 방지) — problem_id 키 기준 삭제."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM problem_embedding WHERE problem_id = ANY(:keys)"),
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


def _count(keys: list[uuid.UUID]) -> int:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            return int(
                conn.execute(
                    text("SELECT count(*) FROM problem_embedding WHERE problem_id = ANY(:keys)"),
                    {"keys": keys},
                ).scalar_one()
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestPopulateE2E:
    """① populate 4문제 적재·dim 일치·problem_id 키."""

    def test_populate_persists_four_problems_with_matching_dim(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            count = populate_problem_embeddings(_CORPUS, provider, settings=settings)
            assert count == 4
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT problem_id, dim FROM problem_embedding "
                            "WHERE problem_id = ANY(:keys)"
                        ),
                        {"keys": _ALL_PIDS},
                    ).all()
                assert {r.problem_id for r in rows} == set(_ALL_PIDS)
                for r in rows:
                    assert r.dim == settings.embedding_dim
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(_ALL_PIDS)


class TestIdempotency:
    """② 멱등 — 2회 populate 후 행 수 안정·재적재 count 0(skip-if-unchanged)."""

    def test_second_populate_is_noop_and_row_count_stable(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            first = populate_problem_embeddings(_CORPUS, provider, settings=settings)
            assert first == 4
            assert _count(_ALL_PIDS) == 4
            # 2회차 — 발문 불변이라 text_hash 일치 → 재임베딩 0·행 수 그대로(멱등).
            second = populate_problem_embeddings(_CORPUS, provider, settings=settings)
            assert second == 0
            assert _count(_ALL_PIDS) == 4
        finally:
            _cleanup(_ALL_PIDS)


class TestNearDuplicateGate:
    """③ 과유사 판정 실증 — 같은 발문 후보=True·다른 단원 문제=False."""

    def test_identical_question_is_near_duplicate(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            populate_problem_embeddings(_CORPUS, provider, settings=settings)
            index = ProblemEmbeddingIndex(
                provider_name="fake", model_name="fake-hash", settings=settings
            )
            # S2-d 게이트 실증: 기존 문제와 *같은 발문*을 가진 신규 후보(problem_id 다름)는
            # 코퍼스에 이미 있는 판박이라 과유사(코사인 1.0 ≥ 0.97)로 잡혀 저장이 막힌다.
            candidate_text = problem_embedding_text(_CORPUS[0])  # "극한 값 을 구하 는 문제"
            cand_vec = provider.embed([candidate_text])[0]
            hits = find_near_duplicates(index, cand_vec)
            assert _PID_LIMIT in {pid for pid, _ in hits}
            assert is_near_duplicate(index, cand_vec) is True
        finally:
            _cleanup(_ALL_PIDS)

    def test_different_unit_problem_is_not_near_duplicate(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            populate_problem_embeddings(_CORPUS, provider, settings=settings)
            index = ProblemEmbeddingIndex(
                provider_name="fake", model_name="fake-hash", settings=settings
            )
            # 어휘가 완전히 다른 신규 후보(다른 단원)는 기존 코퍼스와 직교에 가까워 과유사 아님
            # (정당한 신규 문제 통과 — 과잉 억제 회피).
            novel_vec = provider.embed(["벡터 내적 사이 각"])[0]
            assert find_near_duplicates(index, novel_vec) == []
            assert is_near_duplicate(index, novel_vec) is False
        finally:
            _cleanup(_ALL_PIDS)

    def test_exclude_self_on_reembed(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            populate_problem_embeddings(_CORPUS, provider, settings=settings)
            index = ProblemEmbeddingIndex(
                provider_name="fake", model_name="fake-hash", settings=settings
            )
            # 기존 문제 자신을 재평가할 때 자기 행(코사인 1.0)을 exclude하면 다른 판박이가 없는 한
            # 과유사 아님(자기 자신을 중복으로 오판하지 않음).
            own_vec = provider.embed([problem_embedding_text(_CORPUS[2])])[0]  # 행렬 곱셈 계산
            assert is_near_duplicate(index, own_vec, exclude_problem_id=_PID_MATRIX) is False
        finally:
            _cleanup(_ALL_PIDS)


class TestSearchCosine:
    """④ search 코사인 정합 — 같은 발문 상위·다른 발문 하위·similarity 범위."""

    def test_search_ranks_same_question_top(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            populate_problem_embeddings(_CORPUS, provider, settings=settings)
            index = ProblemEmbeddingIndex(
                provider_name="fake", model_name="fake-hash", settings=settings
            )
            query_vec = provider.embed([problem_embedding_text(_CORPUS[0])])[0]
            hits = index.search(query_vec, top_k=4)
            assert hits[0][0] == _PID_LIMIT  # 같은 발문이 최상위
            # 유사도 내림차순·범위.
            sims = [sim for _, sim in hits]
            assert sims == sorted(sims, reverse=True)
            for _pid, sim in hits:
                assert -1.0001 <= sim <= 1.0001
        finally:
            _cleanup(_ALL_PIDS)

    def test_search_excludes_other_space(self) -> None:
        _skip_if_unreachable()
        settings = Settings()
        provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
        try:
            populate_problem_embeddings(_CORPUS, provider, settings=settings)
            # 다른 임베딩 공간(model 다름)으로 검색하면 fake-hash 행이 안 잡힌다.
            other = ProblemEmbeddingIndex(
                provider_name="fake", model_name="other-model", settings=settings
            )
            vec = provider.embed([problem_embedding_text(_CORPUS[0])])[0]
            assert other.search(vec, top_k=10) == []
        finally:
            _cleanup(_ALL_PIDS)
