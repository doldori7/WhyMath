"""개념 의미검색 *조회 좌석* 단위테스트 — 슬4 + 소비 슬1 (hermetic·PG 불요·Fake provider+index).

이 샌드박스·CI hermetic 잡엔 PostgreSQL이 없으므로 `search_concepts`의 *실 라운드트립*(질의→
pgvector search→메타 조인→랭킹)은 통합테스트(`test_concept_retrieval_integration.py`·실 PG 게이트)로
미룬다. 여기서는 PG 없이 검증 가능한 좌석 *배선*만 못 박는다(슬3 가짜 엔진 패턴 + `fetch_node_meta`
패치):

  ① 좌석 흐름 — query 임베딩(1건)→`ConceptEmbeddingIndex.search`→메타 enrich→`ConceptSearchHit` 랭킹
  ② top_k 경계 — top_k<=0이면 빈 리스트(search·임베딩 미실행)
  ③ memory 모드 graceful — vector_store!=pgvector면 빈 리스트(예외·None 아님·조용한 무동작 금지)
  ④ provider 공간 식별 재사용 — index 미주입 시 _provider_model_identity로 같은 공간 인덱스 구성
  ⑤ enrichment — concept_node 메타(name_ko·domain·review_status)를 hit에 붙임·미적재 UC는 None
  ⑥ 검수 게이팅(reviewed_only) — True면 reviewed 아닌(또는 메타 없는) hit 필터·정렬 유지
  ⑦ 반환 타입 — concept_id+similarity+안전 메타만(본문 0·노출 계약)

`fetch_node_meta`(PG 조인)는 가짜 엔진에 붙으므로 *패치*해 enrichment 메타를 제어한다 — 실 메타
조인은 통합테스트 몫(여기선 좌석이 메타를 hit에 옳게 합치고 게이팅을 거는지).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any

import pytest

import whymath_backend.l1.concept_graph.retrieval as retrieval_mod
from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.embedding import ConceptEmbeddingIndex
from whymath_backend.l1.concept_graph.node_projection import ConceptNodeMeta
from whymath_backend.l1.concept_graph.retrieval import ConceptSearchHit, search_concepts
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

# 슬2 idmap이 발급하는 UC 규약 키 예시(슬2 Neo4j 노드 키·슬3 concept_embedding과 동일 공간).
_UC_A = "UC.calc.alimit.epsilon-delta"
_UC_B = "UC.alg.afunction.composition"
_UC_C = "UC.calc.acont.continuity"


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


def _patch_meta(
    monkeypatch: pytest.MonkeyPatch, meta: dict[str, ConceptNodeMeta] | None = None
) -> dict[str, Any]:
    """`fetch_node_meta`를 패치해 enrichment 메타를 제어(가짜 엔진엔 concept_node 행이 없으므로).

    반환 captured에 호출 인자(concept_ids·engine)를 기록한다 — 좌석이 검색이 잡은 UC들·같은
    엔진을 메타 조회에 넘기는지 관찰. meta 미지정이면 빈 dict(enrichment 없음·기존 None 동작).
    """
    captured: dict[str, Any] = {}
    resolved_meta = meta if meta is not None else {}

    def _fake_fetch(
        concept_ids: Sequence[str], *, engine: object = None, settings: object = None
    ) -> dict[str, ConceptNodeMeta]:
        captured["concept_ids"] = list(concept_ids)
        captured["engine"] = engine
        return resolved_meta

    monkeypatch.setattr(retrieval_mod, "fetch_node_meta", _fake_fetch)
    return captured


# ──────────────────────────────────────────────────────────────────────────
# ① 좌석 흐름 — query 임베딩→search→메타 enrich→ConceptSearchHit 랭킹 반환
# ──────────────────────────────────────────────────────────────────────────
class TestSearchFlow:
    def test_returns_ranked_hits_from_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # search가 거리 오름차순(=유사도 내림차순)으로 돌려주는 행을 그대로 ConceptSearchHit로.
        _patch_meta(monkeypatch)  # enrichment 없음 — 메타 None
        rows = [_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.25)]
        index, engine = _index_with_rows(rows)
        hits = search_concepts(
            "극한 수렴",
            top_k=3,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [
            ConceptSearchHit(concept_id=_UC_A, similarity=1.0),
            ConceptSearchHit(concept_id=_UC_B, similarity=0.75),
        ]
        # search statement가 1회 실행됐다(질의 임베딩→search). 메타 조회는 패치돼 엔진 미실행.
        assert len(engine.executed) == 1

    def test_embeds_query_as_single_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 질의 1건을 임베딩한다(배치 API에 단건). Scripted provider로 입력·길이를 관찰.
        _patch_meta(monkeypatch)
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

    def test_empty_search_result_is_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 적재 행 없음(또는 같은 공간 행 없음)이면 빈 리스트(정직 — 매칭 없음). 메타 조회 생략.
        captured = _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([])
        hits = search_concepts(
            "없는개념",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == []
        # hits가 비면 메타 조회도 안 한다(early return).
        assert "concept_ids" not in captured

    def test_null_distance_is_zero_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
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
    def test_top_k_zero_returns_empty_without_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
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
        assert engine.executed == []

    def test_negative_top_k_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
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
    def test_memory_mode_returns_empty_without_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 기본 Settings는 vector_store=memory → 영속 store 부재 → 빈 리스트(예외 아님).
        captured = _patch_meta(monkeypatch)
        index, engine = _index_with_rows([_FakeRow(_UC_A, 0.0)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=Settings(),  # 기본 memory
        )
        assert hits == []
        # search·임베딩·메타 경로를 아예 안 탄다(memory 가드가 최우선).
        assert engine.executed == []
        assert "concept_ids" not in captured

    def test_memory_mode_does_not_embed(self) -> None:
        # memory면 provider.embed도 호출하지 않는다(불필요한 모델 로드 방지).
        class _ExplodingProvider:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise AssertionError("memory 모드에서 embed가 호출되면 안 된다")

        hits = search_concepts("q", top_k=5, provider=_ExplodingProvider(), settings=Settings())
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

        _patch_meta(monkeypatch)
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
# ⑤ enrichment — concept_node 메타를 hit에 붙임·미적재 UC는 None graceful
# ──────────────────────────────────────────────────────────────────────────
class TestEnrichment:
    def test_enriches_hits_with_node_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="극한", domain="[고]미적분", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="합성함수", domain="[고]대수", review_status="pending"),
        }
        captured = _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.2)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [
            ConceptSearchHit(
                concept_id=_UC_A,
                similarity=1.0,
                name_ko="극한",
                domain="[고]미적분",
                review_status="reviewed",
            ),
            ConceptSearchHit(
                concept_id=_UC_B,
                similarity=0.8,
                name_ko="합성함수",
                domain="[고]대수",
                review_status="pending",
            ),
        ]
        # 좌석이 검색이 잡은 UC들·같은 엔진(index._engine)을 메타 조회에 넘긴다(N+1 없음·엔진 공유).
        assert captured["concept_ids"] == [_UC_A, _UC_B]
        assert captured["engine"] is index._engine

    def test_missing_meta_is_none_graceful(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # concept_node에 _UC_B 메타가 없으면(적재 누락) None으로 채운다(검색 계속·graceful).
        meta = {_UC_A: ConceptNodeMeta(name_ko="극한", domain="d", review_status="reviewed")}
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.2)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits[0].name_ko == "극한"
        # _UC_B는 메타 없음 → 모든 메타 필드 None(but 여전히 결과에 포함·기본 비게이팅).
        assert hits[1].concept_id == _UC_B
        assert hits[1].name_ko is None
        assert hits[1].domain is None
        assert hits[1].review_status is None


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 검수 게이팅(reviewed_only) — reviewed만 통과·메타 없음 제외·정렬 유지
# ──────────────────────────────────────────────────────────────────────────
class TestReviewedOnlyGating:
    def test_reviewed_only_filters_pending(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="극한", domain="d", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="합성함수", domain="d", review_status="pending"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.2)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            reviewed_only=True,
            index=index,
            settings=_pgvector_settings(),
        )
        # pending(_UC_B)은 필터·reviewed(_UC_A)만 남음. 정렬(유사도 내림차순)은 유지.
        assert [h.concept_id for h in hits] == [_UC_A]
        assert hits[0].review_status == "reviewed"

    def test_reviewed_only_excludes_missing_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 메타가 없어 reviewed 확인 불가인 UC는 gated 모드에서 보수적으로 제외(정직).
        meta = {_UC_A: ConceptNodeMeta(name_ko="극한", domain="d", review_status="reviewed")}
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.2)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            reviewed_only=True,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A]  # _UC_B(메타 없음) 제외

    def test_default_keeps_all_recall(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 기본 reviewed_only=False면 pending·메타 없음도 모두 노출(recall 보존).
        meta = {_UC_A: ConceptNodeMeta(name_ko="극한", domain="d", review_status="pending")}
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.2)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [
            _UC_A,
            _UC_B,
        ]  # 둘 다(pending·메타없음 포함)


# ──────────────────────────────────────────────────────────────────────────
# ⑦ 반환 타입 — concept_id+similarity+안전 메타만(본문 0·노출 계약)
# ──────────────────────────────────────────────────────────────────────────
def test_hit_has_only_safe_fields() -> None:
    # ConceptSearchHit는 안전 식별자(concept_id)+점수(similarity)+안전 메타만 — 본문 필드 없음.
    fields = set(ConceptSearchHit.__dataclass_fields__)
    assert fields == {"concept_id", "similarity", "name_ko", "domain", "review_status"}
    assert "description" not in fields
    assert "formal_definition" not in fields


# ──────────────────────────────────────────────────────────────────────────
# ⑧ 임계 게이팅(min_similarity) — 근접도 미만 제외·기본 None 불변·정렬 유지
# ──────────────────────────────────────────────────────────────────────────
class TestMinSimilarityGating:
    def test_filters_below_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # sim(_UC_A)=1.0, sim(_UC_B)=0.6. 임계 0.8 → _UC_B 제외(semantic 실패 침묵 차단).
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.4)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            min_similarity=0.8,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A]
        assert hits[0].similarity == 1.0

    def test_threshold_is_inclusive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 경계값(similarity == min_similarity)은 포함(< 만 제외).
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.25)])  # sim = 0.75
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            min_similarity=0.75,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A]

    def test_none_keeps_all_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 기본 None이면 임계 없음(기존 동작 불변 — 낮은 유사도도 유지).
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.9)])
        hits = search_concepts(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A, _UC_B]


# ──────────────────────────────────────────────────────────────────────────
# ⑨ 도메인 스코프(domain) — 일치만 통과·불일치/메타없음 제외·기본 None 불변
# ──────────────────────────────────────────────────────────────────────────
class TestDomainScoping:
    def test_filters_mismatched_domain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 동명 개념 collision 방어 — 지정 도메인과 다른 히트 제외.
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="함수", domain="[고]미적분", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="함수", domain="[중]함수", review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.1)])
        hits = search_concepts(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            domain="[고]미적분",
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A]
        assert hits[0].domain == "[고]미적분"

    def test_excludes_missing_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 메타 없어 도메인 확인 불가인 UC는 스코프 모드에서 보수적 제외(정직).
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="함수", domain="[고]미적분", review_status="reviewed")
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.1)])
        hits = search_concepts(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            domain="[고]미적분",
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A]  # _UC_B(메타 없음) 제외

    def test_none_keeps_all_domains(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 기본 None이면 전 도메인 유지(기존 동작 불변).
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="함수", domain="[고]미적분", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="함수", domain="[중]함수", review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.1)])
        hits = search_concepts(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.concept_id for h in hits] == [_UC_A, _UC_B]


# ──────────────────────────────────────────────────────────────────────────
# ⑩ 게이팅 조합 — reviewed_only·min_similarity·domain 동시 적용·정렬 유지
# ──────────────────────────────────────────────────────────────────────────
def test_combined_gating_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # _UC_A: reviewed·sim1.0·미적분(통과). _UC_B: pending(reviewed_only 탈락).
    # 세 게이팅이 함께 걸려도 남은 히트의 유사도 내림차순 정렬은 유지.
    meta = {
        _UC_A: ConceptNodeMeta(name_ko="극한", domain="[고]미적분", review_status="reviewed"),
        _UC_B: ConceptNodeMeta(name_ko="합성", domain="[고]미적분", review_status="pending"),
        _UC_C: ConceptNodeMeta(name_ko="연속", domain="[고]미적분", review_status="reviewed"),
    }
    _patch_meta(monkeypatch, meta)
    index, _engine = _index_with_rows(
        [_FakeRow(_UC_A, 0.0), _FakeRow(_UC_B, 0.1), _FakeRow(_UC_C, 0.15)]
    )
    hits = search_concepts(
        "극한 연속",
        top_k=5,
        provider=FakeEmbeddingProvider(),
        reviewed_only=True,
        min_similarity=0.5,
        domain="[고]미적분",
        index=index,
        settings=_pgvector_settings(),
    )
    # _UC_B는 pending으로 탈락. _UC_A(1.0)·_UC_C(0.85) 통과·정렬 유지.
    assert [h.concept_id for h in hits] == [_UC_A, _UC_C]
    assert [h.similarity for h in hits] == [1.0, 0.85]


def test_accepts_any_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # 구조적 타이핑 — 신규 provider 없이 임의 embed 좌석을 받는다(provider seam 재사용).
    _patch_meta(monkeypatch)

    class _Scripted:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.3, 0.4] for _ in texts]

    index, _engine = _index_with_rows(
        [_FakeRow(_UC_A, 0.1)], provider_name="_Scripted", model_name="_Scripted"
    )
    hits = search_concepts(
        "q", top_k=1, provider=_Scripted(), index=index, settings=_pgvector_settings()
    )
    assert len(hits) == 1
    assert hits[0].concept_id == _UC_A
