"""개념 의미검색 *조회 좌석* 단위테스트 — 슬라이스 4 (hermetic·PG 불요·Fake provider+index).

이 샌드박스·CI hermetic 잡엔 PostgreSQL·pgvector가 없으므로 `search_concepts`의 *실 라운드트립*
(질의→pgvector search→랭킹)은 통합테스트(`test_concept_retrieval_integration.py`·실 PG 게이트)로
미룬다. 여기서는 PG 없이 검증 가능한 좌석 *배선*만 못 박는다(슬3 `test_concept_embedding.py`의
가짜 엔진 패턴 재사용):

  ① 좌석 흐름 — query 임베딩(1건)→`ConceptEmbeddingIndex.search`→`ConceptSearchHit` 랭킹 반환
  ② top_k 경계 — top_k<=0이면 빈 리스트(search 미실행·임베딩 미실행)
  ③ memory 모드 graceful — vector_store!=pgvector면 빈 리스트(예외·None 아님·조용한 무동작 금지)
  ④ provider 공간 식별 재사용 — index 미주입 시 _provider_model_identity로 같은 공간 인덱스 구성
  ⑤ 반환 타입 — concept_id+similarity만(name_ko 등 enrichment 미포함·노출 계약)

가짜 엔진(`_FakeEngine`)은 search에 canned 행을 돌려주고 실행 statement를 기록한다 — psycopg/PG
없이 좌석이 search 결과를 그대로 랭킹·매핑하는지 검증한다(실 코사인·실 적재는 통합테스트).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import ConceptEmbeddingIndex
from whymath_backend.l1.concept_graph.retrieval import ConceptSearchHit, search_concepts
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

# 슬2 idmap이 발급하는 UC 규약 키 예시(슬2 Neo4j 노드 키와 동일 공간).
_UC_A = "UC.calc.alimit.epsilon-delta"
_UC_B = "UC.alg.afunction.composition"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — connect() 컨텍스트 + execute() (PG 없이 search 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeRow:
    """search 결과 행 흉내 — `.concept_id`·`.distance` 속성 접근(embedding.search가 읽는 형)."""

    def __init__(self, concept_id: str, distance: float | None) -> None:
        self.concept_id = concept_id
        self.distance = distance


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
    """SQLAlchemy sync Engine 최소 흉내 — connect() + 실행 statement 기록 + canned search 행."""

    def __init__(self, search_rows: list[_FakeRow] | None = None) -> None:
        self.executed: list[object] = []
        self.search_rows: list[_FakeRow] = search_rows or []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _pgvector_settings() -> Settings:
    """vector_store=pgvector인 Settings(좌석 memory-가드를 통과해 search 경로를 타게)."""
    return Settings(vector_store="pgvector")


def _index_with_rows(
    rows: list[_FakeRow], *, provider_name: str = "fake", model_name: str = "fake-hash"
) -> tuple[ConceptEmbeddingIndex, _FakeEngine]:
    """canned search 행을 돌려주는 가짜 엔진 주입 ConceptEmbeddingIndex."""
    engine = _FakeEngine(search_rows=rows)
    index = ConceptEmbeddingIndex(
        provider_name=provider_name,
        model_name=model_name,
        engine=engine,  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    )
    return index, engine


# ──────────────────────────────────────────────────────────────────────────
# ① 좌석 흐름 — query 임베딩→search→ConceptSearchHit 랭킹 반환
# ──────────────────────────────────────────────────────────────────────────
class TestSearchFlow:
    def test_returns_ranked_hits_from_search(self) -> None:
        # search가 거리 오름차순(=유사도 내림차순)으로 돌려주는 행을 그대로 ConceptSearchHit로.
        rows = [_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.25)]
        index, engine = _index_with_rows(rows)
        provider = FakeEmbeddingProvider()
        hits = search_concepts(
            "극한 수렴",
            top_k=3,
            provider=provider,
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [
            ConceptSearchHit(concept_id=_UC_A, similarity=1.0),
            ConceptSearchHit(concept_id=_UC_B, similarity=0.75),
        ]
        # search statement가 1회 실행됐다(질의 임베딩→search).
        assert len(engine.executed) == 1

    def test_embeds_query_as_single_item(self) -> None:
        # 질의 1건을 임베딩한다(배치 API에 단건). Scripted provider로 입력·길이를 관찰.
        seen: list[Sequence[str]] = []

        class _Scripted:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                seen.append(list(texts))
                return [[0.1, 0.2] for _ in texts]

        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.1)])
        search_concepts(
            "합성함수",
            top_k=1,
            provider=_Scripted(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert seen == [["합성함수"]]  # 정확히 질의 1건만 임베딩

    def test_empty_search_result_is_empty_list(self) -> None:
        # 적재 행 없음(또는 같은 공간 행 없음)이면 빈 리스트(정직 — 매칭 없음).
        index, _engine = _index_with_rows([])
        hits = search_concepts(
            "없는개념",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == []

    def test_null_distance_is_zero_similarity(self) -> None:
        # 영벡터 등 거리 NULL은 0 유사도로 안전 처리(embedding.search 계약 통과).
        index, _engine = _index_with_rows([_FakeRow(_UC_A, None)])
        hits = search_concepts(
            "x",
            top_k=1,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [ConceptSearchHit(concept_id=_UC_A, similarity=0.0)]


# ──────────────────────────────────────────────────────────────────────────
# ② top_k 경계 — top_k<=0이면 빈 리스트(search·임베딩 미실행)
# ──────────────────────────────────────────────────────────────────────────
class TestTopKBoundary:
    def test_top_k_zero_returns_empty_without_search(self) -> None:
        index, engine = _index_with_rows([_FakeRow(_UC_A, 0.0)])
        assert (
            search_concepts(
                "q",
                top_k=0,
                provider=FakeEmbeddingProvider(),
                index=index,
                settings=_pgvector_settings(),
            )
            == []
        )
        # search statement 미실행(좌석이 top_k<=0에서 조기 반환).
        assert engine.executed == []

    def test_negative_top_k_returns_empty(self) -> None:
        index, engine = _index_with_rows([_FakeRow(_UC_A, 0.0)])
        assert (
            search_concepts(
                "q",
                top_k=-3,
                provider=FakeEmbeddingProvider(),
                index=index,
                settings=_pgvector_settings(),
            )
            == []
        )
        assert engine.executed == []


# ──────────────────────────────────────────────────────────────────────────
# ③ memory 모드 graceful — vector_store!=pgvector면 빈 리스트(조용한 무동작 금지)
# ──────────────────────────────────────────────────────────────────────────
class TestMemoryModeGraceful:
    def test_memory_mode_returns_empty_without_search(self) -> None:
        # 기본 Settings는 vector_store=memory → 영속 store 부재 → 빈 리스트(예외 아님).
        index, engine = _index_with_rows([_FakeRow(_UC_A, 0.0)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=Settings(),  # 기본 memory
        )
        assert hits == []
        # search·임베딩 경로를 아예 안 탄다(memory 가드가 최우선).
        assert engine.executed == []

    def test_memory_mode_does_not_embed(self) -> None:
        # memory면 provider.embed도 호출하지 않는다(불필요한 모델 로드 방지).
        class _ExplodingProvider:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise AssertionError("memory 모드에서 embed가 호출되면 안 된다")

        hits = search_concepts(
            "q", top_k=5, provider=_ExplodingProvider(), settings=Settings()
        )
        assert hits == []


# ──────────────────────────────────────────────────────────────────────────
# ④ provider 공간 식별 재사용 — index 미주입 시 같은 공간 규약(슬3·L4 seam)
# ──────────────────────────────────────────────────────────────────────────
class TestProviderSpaceIdentity:
    def test_index_omitted_builds_with_provider_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # index 미주입이면 좌석이 _provider_model_identity로 ConceptEmbeddingIndex를 만든다.
        # 실 엔진 생성을 막으려 _build_sync_engine을 가짜 엔진으로 패치(PG 불요).
        import whymath_backend.l1.concept_graph.embedding as emb

        fake_engine = _FakeEngine(search_rows=[_FakeRow(_UC_A, 0.0)])
        monkeypatch.setattr(emb, "_build_sync_engine", lambda _settings: fake_engine)

        hits = search_concepts(
            "극한",
            top_k=2,
            provider=FakeEmbeddingProvider(),
            settings=_pgvector_settings(),  # index 미주입
        )
        # 가짜 엔진을 통해 search가 돌고 결과가 랭킹된다(자가 구성 인덱스가 동작).
        assert hits == [ConceptSearchHit(concept_id=_UC_A, similarity=1.0)]
        assert len(fake_engine.executed) == 1


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 반환 타입 — concept_id+similarity만(enrichment 미포함·노출 계약)
# ──────────────────────────────────────────────────────────────────────────
def test_hit_has_only_concept_id_and_similarity() -> None:
    # ConceptSearchHit는 안전 식별자(concept_id)+점수(similarity)만 — name_ko·본문 필드 없음.
    fields = set(ConceptSearchHit.__dataclass_fields__)
    assert fields == {"concept_id", "similarity"}


def test_accepts_any_embedding_provider() -> None:
    # 구조적 타이핑 — 신규 provider 없이 임의 embed 좌석을 받는다(provider seam 재사용).
    class _Scripted:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.3, 0.4] for _ in texts]

    index, engine = _index_with_rows(
        [_FakeRow(_UC_A, 0.1)], provider_name="_Scripted", model_name="_Scripted"
    )
    hits = search_concepts(
        "q", top_k=1, provider=_Scripted(), index=index, settings=_pgvector_settings()
    )
    assert len(hits) == 1
    assert hits[0].concept_id == _UC_A
