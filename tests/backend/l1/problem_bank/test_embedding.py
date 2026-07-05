"""문제 발문 임베딩 dedup *단위테스트* — S2-c (hermetic·PG 불요·Fake provider).

이 샌드박스·CI hermetic 잡엔 PostgreSQL·pgvector가 없으므로 `ProblemEmbeddingIndex` upsert/search의
*실 라운드트립*은 통합테스트(`test_embedding_integration.py`·실 PG 게이트)로 미룬다. 여기서는 PG
없이 검증 가능한 것만 못 박는다(`atom_graph/test_atom_embedding.py` 미러):

  ① 임베딩 텍스트 구성 — 발문(question_text)만·None/공백 안전 처리·NFKC 결합
  ② upsert SQL 구성(가짜 엔진 주입 — ON CONFLICT(problem_id) upsert·created_at 보존·원문 미저장)
  ③ search SQL 구성 — provider/model 필터·<=> 코사인·LIMIT + similarity=1-distance·top_k 경계
  ④ populate — Fake provider + 가짜 엔진으로 발문 있는 문제만 upsert·skip-if-unchanged·빈 발문 제외
  ⑤ 과유사 dedup 게이트 — threshold(0.97) 경계·자기 제외·is_near_duplicate 판정

가짜 엔진(`_FakeEngine`)은 `begin()`/`connect()` 컨텍스트 + `execute()`를 흉내내 실행된 statement를
기록하고 search엔 canned 행을 돌려준다 — psycopg/PG 없이 배선·변환·필터·게이트를 검증한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.l1.embedding_primitives import text_hash
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

# 고정 problem_id(UUID PK 공간·결정론). 실 데이터와 충돌 무관(hermetic).
_PID_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_PID_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
_PID_C = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _make_problem(question_text: str | None, *, problem_id: uuid.UUID = _PID_A) -> Problem:
    """최소 자체생성 Problem — 발문만 바꿔 임베딩/게이트 대상으로 쓴다(본문 불변식 통과)."""
    return Problem(
        problem_id=problem_id,
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2027,
        subject=Subject.미적분,
        unit_codes=["CAL-DIFF"],
        question_text=question_text,
    )


class _SpyProvider:
    """embed 호출 횟수를 세는 provider — skip-if-unchanged 검증용(불변분 미임베딩 확인)."""

    def __init__(self, dim: int = 64) -> None:
        self.embed_calls = 0
        self._dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [[0.1] * self._dim for _ in texts]


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin()/connect() 컨텍스트 + execute() (PG 없이 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeRow:
    """행 흉내 — search는 `.problem_id`·`.distance`, existing_text_hashes는 `.text_hash` 접근."""

    def __init__(
        self,
        problem_id: uuid.UUID,
        distance: float | None = None,
        text_hash: str | None = None,
    ) -> None:
        self.problem_id = problem_id
        self.distance = distance
        self.text_hash = text_hash


class _FakeResult:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeRow]:
        return self._rows


class _FakeConnection:
    def __init__(self, engine: _FakeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, statement: object) -> _FakeResult:
        self._engine.executed.append(statement)
        return _FakeResult(self._engine.search_rows)


class _FakeEngine:
    """SQLAlchemy sync Engine의 최소 흉내 — begin()/connect() + 실행 statement 기록."""

    def __init__(self, search_rows: list[_FakeRow] | None = None) -> None:
        self.executed: list[object] = []
        self.search_rows: list[_FakeRow] = search_rows or []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_index(
    *,
    search_rows: list[_FakeRow] | None = None,
    provider_name: str = "fake",
    model_name: str = "fake-hash",
) -> tuple[ProblemEmbeddingIndex, _FakeEngine]:
    """가짜 엔진을 주입한 ProblemEmbeddingIndex + 엔진(검사용) 페어."""
    engine = _FakeEngine(search_rows=search_rows)
    index = ProblemEmbeddingIndex(
        provider_name=provider_name,
        model_name=model_name,
        engine=engine,  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    )
    return index, engine


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# ① 임베딩 텍스트 구성 — 발문(question_text)만
# ──────────────────────────────────────────────────────────────────────────
class TestProblemEmbeddingText:
    def test_uses_question_text(self) -> None:
        problem = _make_problem("함수 f(x)의 극한값을 구하시오.")
        assert problem_embedding_text(problem) == "함수 f(x)의 극한값을 구하시오."

    def test_none_question_text_gives_empty(self) -> None:
        # 발문 None(메타 전용 레코드 등) → 빈 표현(호출자가 거른다·빈 벡터 방지).
        assert problem_embedding_text(_make_problem(None)) == ""

    def test_blank_question_text_gives_empty(self) -> None:
        # str_strip_whitespace로 공백 발문은 ""가 되고, join_embedding_text도 빈값 skip.
        assert problem_embedding_text(_make_problem("   ")) == ""

    def test_nfkc_normalizes_representation(self) -> None:
        # 합성/전각 문자를 NFKC로 접어 원자·개념 표현과 같은 포맷 계약을 공유한다.
        # 전각 숫자 '２'(U+FF12) → '2'로 정규화.
        assert problem_embedding_text(_make_problem("x ＝ ２")) == "x = 2"


# ──────────────────────────────────────────────────────────────────────────
# ② upsert SQL 구성 — ON CONFLICT(problem_id)·created_at 보존·원문 미저장
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict(self) -> None:
        index, engine = _fake_index()
        index.upsert(_PID_A, [0.1, 0.2, 0.3], source_text="발문 표현")
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO problem_embedding" in compiled
        assert "ON CONFLICT" in compiled

    def test_upsert_targets_problem_id_pk(self) -> None:
        index, engine = _fake_index()
        index.upsert(_PID_A, [0.5], source_text="표현")
        compiled = _compile(engine.executed[0])
        assert "problem_embedding.problem_id" in compiled or "(problem_id)" in compiled

    def test_upsert_preserves_created_at(self) -> None:
        # created_at은 ON CONFLICT SET에서 제외 — 최초 생성 시각 보존(atom updated_at과 대비).
        index, engine = _fake_index()
        index.upsert(_PID_A, [0.5], source_text="표현")
        compiled = _compile(engine.executed[0])
        assert "ON CONFLICT" in compiled
        assert "created_at = excluded.created_at" not in compiled
        # 갱신 대상엔 embedding·text_hash가 포함된다.
        assert "text_hash = excluded.text_hash" in compiled

    def test_upsert_does_not_persist_source_text(self) -> None:
        # 원문 비저장: INSERT에 source_text 컬럼이 없고 text_hash만 적재(redaction·중복).
        index, engine = _fake_index()
        index.upsert(_PID_A, [0.1, 0.2], source_text="비밀 발문 원문")
        compiled = _compile(engine.executed[0])
        assert "text_hash" in compiled
        assert "source_text" not in compiled

    def test_upsert_hashes_source_text(self) -> None:
        from sqlalchemy.dialects import postgresql

        index, engine = _fake_index()
        index.upsert(_PID_A, [0.5], source_text="발문 표현")
        params = dict(
            engine.executed[0].compile(dialect=postgresql.dialect()).params  # type: ignore[attr-defined]
        )
        assert params["text_hash"] == text_hash("발문 표현")


# ──────────────────────────────────────────────────────────────────────────
# ③ search SQL 구성 + similarity 변환 + top_k 경계
# ──────────────────────────────────────────────────────────────────────────
class TestSearch:
    def test_search_filters_provider_and_model_with_cosine_and_limit(self) -> None:
        index, engine = _fake_index(
            search_rows=[_FakeRow(_PID_A, 0.1)], provider_name="local", model_name="bge-m3"
        )
        index.search([1.0, 2.0], top_k=3)
        compiled = _compile(engine.executed[0])
        assert "problem_embedding.provider" in compiled
        assert "problem_embedding.model" in compiled
        assert "<=>" in compiled
        assert "LIMIT" in compiled

    def test_search_has_no_subject_predicate(self) -> None:
        # problem_embedding엔 subject 축이 없다(atom과 달리·ORM docstring) — WHERE에 subject 없음.
        index, engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.1)])
        index.search([1.0], top_k=1)
        compiled = _compile(engine.executed[0])
        assert "subject" not in compiled

    def test_similarity_is_one_minus_distance(self) -> None:
        rows = [_FakeRow(_PID_A, 0.0), _FakeRow(_PID_B, 0.25)]
        index, _engine = _fake_index(search_rows=rows)
        hits = index.search([1.0, 0.0], top_k=2)
        assert hits == [(_PID_A, 1.0), (_PID_B, 0.75)]

    def test_null_distance_is_zero_similarity(self) -> None:
        index, _engine = _fake_index(search_rows=[_FakeRow(_PID_A, None)])
        assert index.search([0.0], top_k=1) == [(_PID_A, 0.0)]

    def test_top_k_zero_returns_empty_without_engine_call(self) -> None:
        index, engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.0)])
        assert index.search([1.0], top_k=0) == []
        assert index.search([1.0], top_k=-2) == []
        assert engine.executed == []

    def test_existing_text_hashes_filters_provider_model(self) -> None:
        rows = [_FakeRow(_PID_A, text_hash="deadbeef")]
        index, engine = _fake_index(search_rows=rows)
        found = index.existing_text_hashes([_PID_A])
        assert found == {_PID_A: "deadbeef"}
        compiled = _compile(engine.executed[0])
        assert "problem_embedding.provider" in compiled
        assert "problem_embedding.model" in compiled

    def test_existing_text_hashes_empty_input_no_query(self) -> None:
        index, engine = _fake_index()
        assert index.existing_text_hashes([]) == {}
        assert engine.executed == []


# ──────────────────────────────────────────────────────────────────────────
# ④ populate — Fake provider + 가짜 엔진으로 발문 있는 문제만 upsert
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_problem(self) -> None:
        problems = [
            _make_problem("극한값을 구하시오.", problem_id=_PID_A),
            _make_problem("도함수를 구하시오.", problem_id=_PID_B),
        ]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        count = populate_problem_embeddings(problems, provider, index=index)
        assert count == 2
        assert len(engine.executed) == 3  # 1 read(existing·비어) + 2 upsert

    def test_populate_excludes_empty_question_text(self) -> None:
        # 발문 빈 문제는 임베딩 대상에서 제외(빈 벡터 방지).
        problems = [
            _make_problem("유효 발문", problem_id=_PID_A),
            _make_problem(None, problem_id=_PID_B),
        ]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        count = populate_problem_embeddings(problems, provider, index=index)
        assert count == 1
        # read 1 + upsert 1 (빈 발문 문제는 items에 안 들어가 embed도 안 됨).
        assert len(engine.executed) == 2

    def test_populate_dim_uses_problem_id_key(self) -> None:
        problems = [_make_problem("표현", problem_id=_PID_A)]
        provider = FakeEmbeddingProvider(dim=64)
        index, engine = _fake_index()
        populate_problem_embeddings(problems, provider, index=index)
        compiled = _compile(engine.executed[1])  # [0]=read, [1]=upsert
        assert "problem_id" in compiled
        assert "dim" in compiled

    def test_populate_skips_unchanged(self) -> None:
        # 현행 text_hash 일치 → provider 미호출·upsert 0·count 0(읽기 1회만).
        problems = [_make_problem("변함없는 발문", problem_id=_PID_A)]
        rows = [_FakeRow(_PID_A, text_hash=text_hash("변함없는 발문"))]
        provider = _SpyProvider()
        index, engine = _fake_index(search_rows=rows)
        count = populate_problem_embeddings(problems, provider, index=index)
        assert count == 0
        assert provider.embed_calls == 0
        assert len(engine.executed) == 1  # read만

    def test_populate_empty_problems_is_noop(self) -> None:
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        assert populate_problem_embeddings([], provider, index=index) == 0
        assert engine.executed == []

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 문제 2회 populate → 매 회 ON CONFLICT upsert(가짜 엔진은 기존 미반영·실 멱등은 통합).
        problems = [_make_problem("표현", problem_id=_PID_A)]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        populate_problem_embeddings(problems, provider, index=index)
        populate_problem_embeddings(problems, provider, index=index)
        upserts = [s for s in engine.executed if "ON CONFLICT" in _compile(s)]
        assert len(upserts) == 2


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 과유사 dedup 게이트 — threshold(0.97) 경계·자기 제외·판정
# ──────────────────────────────────────────────────────────────────────────
class TestNearDuplicateGate:
    def test_near_duplicate_above_threshold_is_flagged(self) -> None:
        # similarity = 1 - distance. distance 0.02 → sim 0.98(≥0.97) → 과유사.
        index, _engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.02)])
        hits = find_near_duplicates(index, [1.0, 0.0])
        assert hits == [(_PID_A, 0.98)]
        assert is_near_duplicate(index, [1.0, 0.0]) is True

    def test_threshold_boundary_is_inclusive(self) -> None:
        # 정확히 0.97(distance 0.03)은 threshold 이상(>=)이라 과유사로 잡힌다.
        index, _engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.03)])
        hits = find_near_duplicates(index, [1.0, 0.0])
        assert len(hits) == 1
        assert abs(hits[0][1] - 0.97) < 1e-9

    def test_below_threshold_is_not_flagged(self) -> None:
        # sim 0.95(distance 0.05) < 0.97 → 정당한 유사 문제로 통과(과잉 억제 회피).
        index, _engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.05)])
        assert find_near_duplicates(index, [1.0, 0.0]) == []
        assert is_near_duplicate(index, [1.0, 0.0]) is False

    def test_mixed_hits_keeps_only_near(self) -> None:
        # 여러 후보 중 과유사(≥0.97)만 남는다 — 상위 판박이는 잡고 유사 문제는 흘린다.
        rows = [_FakeRow(_PID_A, 0.01), _FakeRow(_PID_B, 0.10)]  # sim 0.99, 0.90
        index, _engine = _fake_index(search_rows=rows)
        hits = find_near_duplicates(index, [1.0, 0.0], top_k=5)
        assert [pid for pid, _ in hits] == [_PID_A]

    def test_exclude_self_id(self) -> None:
        # 기존 문제 갱신 시 자기 자신이 최상위 과유사로 잡히는 것을 배제한다.
        rows = [_FakeRow(_PID_A, 0.0), _FakeRow(_PID_B, 0.02)]  # sim 1.0(자기), 0.98
        index, _engine = _fake_index(search_rows=rows)
        hits = find_near_duplicates(index, [1.0, 0.0], exclude_problem_id=_PID_A)
        assert [pid for pid, _ in hits] == [_PID_B]
        # 자기밖에 없으면 과유사 아님(빈 결과).
        rows_self_only = [_FakeRow(_PID_A, 0.0)]
        index2, _e2 = _fake_index(search_rows=rows_self_only)
        assert is_near_duplicate(index2, [1.0, 0.0], exclude_problem_id=_PID_A) is False

    def test_custom_threshold_overrides_default(self) -> None:
        # 호출자가 threshold를 낮추면 더 많은 후보가 과유사로 잡힌다(파라미터 실효성).
        index, _engine = _fake_index(search_rows=[_FakeRow(_PID_A, 0.10)])  # sim 0.90
        assert find_near_duplicates(index, [1.0], threshold=0.85) == [(_PID_A, 0.90)]
        assert find_near_duplicates(index, [1.0], threshold=0.97) == []


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 임의 provider seam 재사용(구조적 타이핑)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_accepts_any_embedding_provider() -> None:
    class _Scripted:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    problems = [_make_problem("표현", problem_id=_PID_A)]
    index, engine = _fake_index(provider_name="_Scripted", model_name="_Scripted")
    count = populate_problem_embeddings(problems, _Scripted(), index=index)
    assert count == 1
    assert len(engine.executed) == 2  # read(existing) 1 + upsert 1


def test_fake_provider_space_identity() -> None:
    # 프리미티브 seam 재사용 — 식별 규약 동일(fake→fake-hash·atom_embedding 동일).
    from whymath_backend.l1.embedding_primitives import provider_model_identity

    name, model = provider_model_identity(FakeEmbeddingProvider(), Settings())
    assert (name, model) == ("fake", "fake-hash")
