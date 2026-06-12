"""개념 임베딩 적재 *단위테스트* — 슬라이스 3 (hermetic·PG 불요·Fake provider).

이 샌드박스·CI hermetic 잡엔 PostgreSQL·pgvector가 없으므로 `ConceptEmbeddingIndex`
upsert/search의 *실 라운드트립*은 통합테스트(`test_concept_embedding_integration.py`·실 PG
게이트)로 미룬다. 여기서는 PG 없이 검증 가능한 것만 못 박는다(L4 `test_misconception_pgvector.py`
패턴 미러):

  ① 임베딩 텍스트 구성 — name_ko+metaphor+accepted만, **description·formal_definition 미포함**(redaction)
  ② graph.json 로딩 — UC concept_id 추출·안전 필드 표현·redaction 키 무시·빈 표현 제외
  ③ upsert SQL 구성(가짜 엔진 주입 — ON CONFLICT(concept_id) upsert·바인딩 관찰)
  ④ search SQL 구성 — provider/model 필터·<=> 코사인·LIMIT + similarity=1-distance 변환·top_k 경계
  ⑤ populate — Fake provider + 가짜 엔진으로 전 개념 upsert(횟수=개념 수)·dim 일치
  ⑥ UC 키 일관성 — upsert가 concept_id(UC)를 PK로 쓴다(슬2 Neo4j 키와 동일 키 공간)

가짜 엔진(`_FakeEngine`)은 `begin()`/`connect()` 컨텍스트 + `execute()`를 흉내내 실행된
statement를 기록하고 search엔 canned 행을 돌려준다 — psycopg/PG 없이 배선·변환·필터를 검증한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import (
    ConceptEmbeddingIndex,
    ConceptText,
    concept_embedding_text,
    load_concepts_from_graph_json,
    populate_concept_embeddings,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

# 슬2 idmap이 발급하는 UC 규약 키 예시(슬2 Neo4j 노드 키와 동일 공간).
_UC_A = "UC.calc.alimit.epsilon-delta"
_UC_B = "UC.alg.afunction.composition"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin()/connect() 컨텍스트 + execute() (PG 없이 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeRow:
    """search 결과 행 흉내 — `.concept_id`·`.distance` 속성 접근."""

    def __init__(self, concept_id: str, distance: float | None) -> None:
        self.concept_id = concept_id
        self.distance = distance


class _FakeResult:
    """execute() 반환 흉내 — `.all()`로 canned 행 리스트."""

    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeRow]:
        return self._rows


class _FakeConnection:
    """begin()/connect()가 yield하는 연결 흉내 — execute 기록 + canned search 결과."""

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
) -> tuple[ConceptEmbeddingIndex, _FakeEngine]:
    """가짜 엔진을 주입한 ConceptEmbeddingIndex + 엔진(검사용) 페어."""
    engine = _FakeEngine(search_rows=search_rows)
    index = ConceptEmbeddingIndex(
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
# ① 임베딩 텍스트 구성 — 안전 필드만(redaction)
# ──────────────────────────────────────────────────────────────────────────
class TestConceptEmbeddingText:
    def test_joins_safe_fields_in_order(self) -> None:
        text = concept_embedding_text(
            name_ko="극한",
            metaphor="가까이 다가가지만 닿지 않는 거리",
            accepted_expressions="ε-δ 논법으로 수렴을 설명함",
        )
        assert text == "극한. 가까이 다가가지만 닿지 않는 거리. ε-δ 논법으로 수렴을 설명함"

    def test_skips_empty_and_none_fields(self) -> None:
        # metaphor 없음·accepted 공백 → name_ko만. None/공백 조각은 건너뛴다.
        assert concept_embedding_text(name_ko="함수", metaphor=None, accepted_expressions="  ") == (
            "함수"
        )

    def test_name_ko_missing_uses_remaining(self) -> None:
        # name_ko가 비어도 나머지 안전 필드로 표현 합성(빈 표현 방지는 로더가 처리).
        assert concept_embedding_text(name_ko=None, metaphor="은유만 있음") == "은유만 있음"

    def test_all_empty_gives_empty_string(self) -> None:
        assert concept_embedding_text(name_ko=None, metaphor=None, accepted_expressions=None) == ""

    def test_signature_has_no_description_or_formal_definition(self) -> None:
        # redaction 구조적 차단: 함수 시그니처에 description·formal_definition 인자가 *없다*.
        import inspect

        params = set(inspect.signature(concept_embedding_text).parameters)
        assert "description" not in params
        assert "formal_definition" not in params
        # 허용 인자는 안전 필드 3종 + (keyword-only) 뿐.
        assert params == {"name_ko", "metaphor", "accepted_expressions"}


# ──────────────────────────────────────────────────────────────────────────
# ② graph.json 로딩 — UC 키·안전 필드·redaction 키 무시·빈 표현 제외
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_extracts_uc_and_safe_text(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "metaphor": "다가감",
                    "accepted_expressions": "수렴 설명",
                }
            ],
        )
        loaded = load_concepts_from_graph_json(path)
        assert loaded == [ConceptText(concept_id=_UC_A, text="극한. 다가감. 수렴 설명")]

    def test_ignores_description_and_formal_definition_if_present(self, tmp_path: Path) -> None:
        # graph.json엔 본디 없지만, *오염되어 들어와도* 임베딩 표현에 유입되지 않음을 못 박는다.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "metaphor": "다가감",
                    "accepted_expressions": "수렴",
                    "description": "교과서 본문 근접 서술(절대 임베딩 금지)",
                    "formal_definition": "∀ε>0 ∃δ>0 ... (절대 임베딩 금지)",
                }
            ],
        )
        loaded = load_concepts_from_graph_json(path)
        assert len(loaded) == 1
        text = loaded[0].text
        assert text == "극한. 다가감. 수렴"
        # 본문 토큰이 표현에 *전혀* 없다.
        assert "본문" not in text
        assert "∀ε" not in text
        assert "formal" not in text.lower()

    def test_skips_concepts_with_empty_safe_text(self, tmp_path: Path) -> None:
        # 안전 필드가 전부 빈 개념은 제외(빈 벡터 적재 방지).
        path = self._write_graph(
            tmp_path,
            [
                {"concept_id": _UC_A, "name_ko": "유효", "metaphor": "은유"},
                {"concept_id": _UC_B, "name_ko": "", "metaphor": None, "accepted_expressions": ""},
            ],
        )
        loaded = load_concepts_from_graph_json(path)
        assert [c.concept_id for c in loaded] == [_UC_A]

    def test_missing_concept_id_raises(self, tmp_path: Path) -> None:
        import pytest

        path = self._write_graph(tmp_path, [{"name_ko": "키 없음"}])
        with pytest.raises(ValueError, match="concept_id"):
            load_concepts_from_graph_json(path)

    def test_does_not_read_flashcards_or_intl(self, tmp_path: Path) -> None:
        # 그래프 외 자산(flashcards_raw·intl_raw)은 임베딩 대상이 아니다(읽지 않음).
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps(
                {
                    "concepts": [{"concept_id": _UC_A, "name_ko": "개념"}],
                    "flashcards_raw": [{"front": "무시"}],
                    "intl_raw": [{"ccss": "무시"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loaded = load_concepts_from_graph_json(path)
        assert [c.concept_id for c in loaded] == [_UC_A]


# ──────────────────────────────────────────────────────────────────────────
# ③ upsert SQL 구성 (가짜 엔진으로 실행 statement 관찰·컴파일)
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict(self) -> None:
        index, engine = _fake_index()
        index.upsert(_UC_A, [0.1, 0.2, 0.3], source_text="극한. 다가감")
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO concept_embedding" in compiled
        assert "ON CONFLICT" in compiled

    def test_upsert_targets_concept_id_pk(self) -> None:
        # UC 키 일관성: 충돌 키가 concept_id(PK)다(슬2 Neo4j 노드 키와 동일 공간).
        index, engine = _fake_index()
        index.upsert(_UC_A, [0.5], source_text="표현")
        compiled = _compile(engine.executed[0])
        assert "concept_embedding.concept_id" in compiled or "(concept_id)" in compiled


# ──────────────────────────────────────────────────────────────────────────
# ④ search SQL 구성 + similarity 변환 + top_k 경계
# ──────────────────────────────────────────────────────────────────────────
class TestSearch:
    def test_search_filters_provider_and_model_with_cosine_and_limit(self) -> None:
        index, engine = _fake_index(
            search_rows=[_FakeRow(_UC_A, 0.1)], provider_name="local", model_name="bge-m3"
        )
        index.search([1.0, 2.0], top_k=3)
        compiled = _compile(engine.executed[0])
        assert "concept_embedding.provider" in compiled
        assert "concept_embedding.model" in compiled
        assert "<=>" in compiled
        assert "LIMIT" in compiled

    def test_similarity_is_one_minus_distance(self) -> None:
        rows = [_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.25)]
        index, _engine = _fake_index(search_rows=rows)
        hits = index.search([1.0, 0.0], top_k=2)
        assert hits == [(_UC_A, 1.0), (_UC_B, 0.75)]

    def test_null_distance_is_zero_similarity(self) -> None:
        index, _engine = _fake_index(search_rows=[_FakeRow(_UC_A, None)])
        assert index.search([0.0], top_k=1) == [(_UC_A, 0.0)]

    def test_top_k_zero_returns_empty_without_engine_call(self) -> None:
        index, engine = _fake_index(search_rows=[_FakeRow(_UC_A, 0.0)])
        assert index.search([1.0], top_k=0) == []
        assert index.search([1.0], top_k=-2) == []
        assert engine.executed == []  # 질의 statement 미실행


# ──────────────────────────────────────────────────────────────────────────
# ⑤ populate — Fake provider + 가짜 엔진으로 전 개념 upsert
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_concept(self) -> None:
        concepts = [
            ConceptText(concept_id=_UC_A, text="극한. 다가감"),
            ConceptText(concept_id=_UC_B, text="합성함수. f∘g"),
        ]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index(provider_name="fake", model_name="fake-hash")
        count = populate_concept_embeddings(concepts, provider, index=index)
        assert count == 2
        assert len(engine.executed) == 2  # 개념당 1 upsert

    def test_populate_dim_matches_provider(self) -> None:
        # upsert에 박히는 dim이 provider 벡터 차원과 일치(컬럼 차원 정합 점검 신호).
        concepts = [ConceptText(concept_id=_UC_A, text="개념 표현")]
        provider = FakeEmbeddingProvider(dim=64)
        index, engine = _fake_index(provider_name="fake", model_name="fake-hash")
        populate_concept_embeddings(concepts, provider, index=index)
        compiled = _compile(engine.executed[0])
        # dim 컬럼이 INSERT에 포함된다(값은 바인딩이라 직접 못 보지만, provider가 64차원이므로
        # 같은 벡터로 search/upsert가 정합 — 통합테스트가 실 차원을 검증).
        assert "dim" in compiled

    def test_populate_uses_uc_key(self) -> None:
        # UC 키 일관성: populate가 concept_id(UC)로 upsert한다(슬2와 동일 키).
        concepts = [ConceptText(concept_id=_UC_A, text="표현")]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        populate_concept_embeddings(concepts, provider, index=index)
        compiled = _compile(engine.executed[0])
        assert "concept_id" in compiled

    def test_populate_empty_concepts_is_noop(self) -> None:
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        assert populate_concept_embeddings([], provider, index=index) == 0
        assert engine.executed == []


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 멱등·provider 공간 식별 재사용 (L4 _provider_model_identity 공유)
# ──────────────────────────────────────────────────────────────────────────
class TestProviderModelIdentityReuse:
    def test_fake_provider_space_identity(self) -> None:
        # L4 seam을 재사용하므로 식별 규약이 동일하다(fake→fake-hash).
        from whymath_backend.l4.misconception.semantic.pgvector_index import (
            _provider_model_identity,
        )

        name, model = _provider_model_identity(FakeEmbeddingProvider(), Settings())
        assert (name, model) == ("fake", "fake-hash")

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 개념 2회 populate → 같은 upsert statement 수(멱등 — PK 충돌 upsert).
        concepts = [ConceptText(concept_id=_UC_A, text="표현")]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        populate_concept_embeddings(concepts, provider, index=index)
        populate_concept_embeddings(concepts, provider, index=index)
        # 가짜 엔진은 실 PK 충돌을 모사하지 않으나, 호출이 매번 upsert(ON CONFLICT) statement임을
        # 확인 — 실 멱등(행 1개)은 통합테스트.
        assert len(engine.executed) == 2
        for stmt in engine.executed:
            assert "ON CONFLICT" in _compile(stmt)


# ──────────────────────────────────────────────────────────────────────────
# 표현 비저장(원문 미저장) — upsert에 source_text 컬럼이 없다
# ──────────────────────────────────────────────────────────────────────────
def test_upsert_does_not_persist_source_text() -> None:
    """원문 비저장: INSERT에 source_text/원문 컬럼이 없고 text_hash만 적재(redaction·중복)."""
    index, engine = _fake_index()
    index.upsert(_UC_A, [0.1, 0.2], source_text="비밀 표현 원문")
    compiled = _compile(engine.executed[0])
    assert "text_hash" in compiled
    # 원문 컬럼명(source_text)이 INSERT 컬럼 목록에 없다.
    assert "source_text" not in compiled


# ──────────────────────────────────────────────────────────────────────────
# 적재기가 임의 provider seam을 받는다(구조적 타이핑 — 신규 provider 없이 재사용)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_accepts_any_embedding_provider() -> None:
    class _Scripted:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    concepts = [ConceptText(concept_id=_UC_A, text="표현")]
    index, engine = _fake_index(provider_name="_Scripted", model_name="_Scripted")
    count = populate_concept_embeddings(concepts, _Scripted(), index=index)
    assert count == 1
    assert len(engine.executed) == 1
