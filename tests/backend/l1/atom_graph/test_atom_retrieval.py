"""원자 의미검색 *조회 좌석* 단위테스트 — S0-4a (hermetic·PG 불요·Fake provider+index).

`test_concept_retrieval.py`(구 437 개념 조회 좌석 단위)의 *원자 백본* 미러다. 이 샌드박스·CI
hermetic 잡엔 PostgreSQL이 없으므로 `search_atoms`의 *실 라운드트립*(질의→pgvector search→메타
조인→랭킹)은 통합테스트(`test_atom_retrieval_integration.py`·실 PG 게이트)로 미룬다. 여기서는 PG
없이 검증 가능한 좌석 *배선*만 못 박는다(가짜 엔진 + `fetch_atom_node_meta` 패치):

  ① 좌석 흐름 — query 임베딩(1건)→`AtomEmbeddingIndex.search`→메타 enrich→`AtomSearchHit` 랭킹
  ② top_k 경계 — top_k<=0이면 빈 리스트(search·임베딩 미실행)
  ③ memory 모드 graceful — vector_store!=pgvector면 빈 리스트(예외·None 아님·조용한 무동작 금지)
  ④ provider 공간 식별 재사용 — index 미주입 시 provider_model_identity로 같은 공간 인덱스 구성
  ⑤ enrichment — atom_node 메타(name_ko·subject_area·review_status)를 hit에 붙임·미적재 code는 None
  ⑥ 검수 게이팅(reviewed_only) — reviewed만 통과·메타 없음 제외·**'ai_estimated' 전량 제외**
  ⑦ 반환 타입 — atom_code+similarity+안전 메타만(본문 0·노출 계약)
  ⑧ 임계 게이팅(min_similarity)·⑨ 영역 스코프(subject_area) — concept `domain`의 원자 대응
  ⑩ fetch_atom_node_meta — graceful 누락(없는 code는 dict에서 빠짐)·빈 입력 {}

`fetch_atom_node_meta`(PG 조인)는 가짜 엔진에 붙으므로 *패치*해 enrichment 메타를 제어한다 — 실
메타 조인은 통합테스트 몫(여기선 좌석이 메타를 hit에 옳게 합치고 게이팅을 거는지).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any

import pytest
import whymath_backend.l1.atom_graph.retrieval as retrieval_mod
from whymath_backend.config import Settings
from whymath_backend.db.models.atom_node import ATOM_REVIEW_STATUS_AI_ESTIMATED
from whymath_backend.l1.atom_graph.atom_node_projection import (
    AtomNodeMeta,
    fetch_atom_node_meta,
)
from whymath_backend.l1.atom_graph.embedding import AtomEmbeddingIndex
from whymath_backend.l1.atom_graph.retrieval import AtomSearchHit, search_atoms
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

# 원자 code 규약 예시(원자ID·소단원·단원코드 — backend `concept.code`·atom_embedding 공간).
_ATOM_A = "2수01-01-2"
_ATOM_B = "2수02-03-1"
_ATOM_C = "초수연-U1-S1"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — connect() 컨텍스트 + execute() (PG 없이 search/meta 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeRow:
    """행 흉내 — 동적 속성 접근(search는 .code/.distance·meta는 .code/.name_ko/…를 읽는다)."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


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
        return _FakeResult(self._engine.rows)


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — connect() + 실행 statement 기록 + canned 행."""

    def __init__(self, rows: list[_FakeRow] | None = None) -> None:
        self.executed: list[object] = []
        self.rows: list[_FakeRow] = rows or []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _pgvector_settings() -> Settings:
    """vector_store=pgvector인 Settings(좌석 memory-가드를 통과해 search 경로를 타게)."""
    return Settings(vector_store="pgvector")


def _index_with_rows(
    rows: list[_FakeRow], *, provider_name: str = "fake", model_name: str = "fake-hash"
) -> tuple[AtomEmbeddingIndex, _FakeEngine]:
    """canned search 행을 돌려주는 가짜 엔진 주입 AtomEmbeddingIndex."""
    engine = _FakeEngine(rows=rows)
    index = AtomEmbeddingIndex(
        provider_name=provider_name,
        model_name=model_name,
        engine=engine,  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    )
    return index, engine


def _search_row(code: str, distance: float | None) -> _FakeRow:
    """AtomEmbeddingIndex.search가 읽는 행 형(.code·.distance)."""
    return _FakeRow(code=code, distance=distance)


def _patch_meta(
    monkeypatch: pytest.MonkeyPatch, meta: dict[str, AtomNodeMeta] | None = None
) -> dict[str, Any]:
    """`fetch_atom_node_meta`를 패치해 enrichment 메타를 제어(가짜 엔진엔 atom_node 행이 없으므로).

    반환 captured에 호출 인자(codes·engine)를 기록한다 — 좌석이 검색이 잡은 code들·같은 엔진을
    메타 조회에 넘기는지 관찰. meta 미지정이면 빈 dict(enrichment 없음·기존 None 동작).
    """
    captured: dict[str, Any] = {}
    resolved_meta = meta if meta is not None else {}

    def _fake_fetch(
        codes: Sequence[str], *, engine: object = None, settings: object = None
    ) -> dict[str, AtomNodeMeta]:
        captured["codes"] = list(codes)
        captured["engine"] = engine
        return resolved_meta

    monkeypatch.setattr(retrieval_mod, "fetch_atom_node_meta", _fake_fetch)
    return captured


# ──────────────────────────────────────────────────────────────────────────
# ① 좌석 흐름 — query 임베딩→search→메타 enrich→AtomSearchHit 랭킹 반환
# ──────────────────────────────────────────────────────────────────────────
class TestSearchFlow:
    def test_returns_ranked_hits_from_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)  # enrichment 없음 — 메타 None
        rows = [_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.25)]
        index, engine = _index_with_rows(rows)
        hits = search_atoms(
            "극한 수렴",
            top_k=3,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [
            AtomSearchHit(atom_code=_ATOM_A, similarity=1.0),
            AtomSearchHit(atom_code=_ATOM_B, similarity=0.75),
        ]
        # search statement가 1회 실행됐다(질의 임베딩→search). 메타 조회는 패치돼 엔진 미실행.
        assert len(engine.executed) == 1

    def test_embeds_query_as_single_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        seen: list[Sequence[str]] = []

        class _Scripted:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                seen.append(list(texts))
                return [[0.1, 0.2] for _ in texts]

        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.1)])
        search_atoms(
            "합성함수",
            top_k=1,
            provider=_Scripted(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert seen == [["합성함수"]]  # 정확히 질의 1건만 임베딩

    def test_empty_search_result_is_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([])
        hits = search_atoms(
            "없는개념",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == []
        # hits가 비면 메타 조회도 안 한다(early return).
        assert "codes" not in captured

    def test_null_distance_is_zero_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, None)])
        hits = search_atoms(
            "x",
            top_k=1,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [AtomSearchHit(atom_code=_ATOM_A, similarity=0.0)]


# ──────────────────────────────────────────────────────────────────────────
# ② top_k 경계 — top_k<=0이면 빈 리스트(search·임베딩 미실행)
# ──────────────────────────────────────────────────────────────────────────
class TestTopKBoundary:
    def test_top_k_zero_returns_empty_without_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        index, engine = _index_with_rows([_search_row(_ATOM_A, 0.0)])
        assert (
            search_atoms(
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
        index, engine = _index_with_rows([_search_row(_ATOM_A, 0.0)])
        assert (
            search_atoms(
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
        captured = _patch_meta(monkeypatch)
        index, engine = _index_with_rows([_search_row(_ATOM_A, 0.0)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=Settings(),  # 기본 memory
        )
        assert hits == []
        assert engine.executed == []
        assert "codes" not in captured

    def test_memory_mode_does_not_embed(self) -> None:
        class _ExplodingProvider:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise AssertionError("memory 모드에서 embed가 호출되면 안 된다")

        hits = search_atoms("q", top_k=5, provider=_ExplodingProvider(), settings=Settings())
        assert hits == []


# ──────────────────────────────────────────────────────────────────────────
# ④ provider 공간 식별 재사용 — index 미주입 시 같은 공간 규약(Phase 2b seam)
# ──────────────────────────────────────────────────────────────────────────
class TestProviderSpaceIdentity:
    def test_index_omitted_builds_with_provider_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # index 미주입이면 좌석이 provider_model_identity로 AtomEmbeddingIndex를 만든다.
        # 실 엔진 생성을 막으려 _build_sync_engine을 가짜 엔진으로 패치(PG 불요).
        import whymath_backend.l1.atom_graph.embedding as emb

        _patch_meta(monkeypatch)
        fake_engine = _FakeEngine(rows=[_search_row(_ATOM_A, 0.0)])
        monkeypatch.setattr(emb, "_build_sync_engine", lambda _settings: fake_engine)

        hits = search_atoms(
            "극한",
            top_k=2,
            provider=FakeEmbeddingProvider(),
            settings=_pgvector_settings(),  # index 미주입
        )
        assert hits == [AtomSearchHit(atom_code=_ATOM_A, similarity=1.0)]
        assert len(fake_engine.executed) == 1


# ──────────────────────────────────────────────────────────────────────────
# ⑤ enrichment — atom_node 메타를 hit에 붙임·미적재 code는 None graceful
# ──────────────────────────────────────────────────────────────────────────
class TestEnrichment:
    def test_enriches_hits_with_node_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _ATOM_A: AtomNodeMeta(
                name_ko="극한", subject_area="해석", review_status="ai_estimated"
            ),
            _ATOM_B: AtomNodeMeta(
                name_ko="합성함수", subject_area="대수", review_status="ai_estimated"
            ),
        }
        captured = _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == [
            AtomSearchHit(
                atom_code=_ATOM_A,
                similarity=1.0,
                name_ko="극한",
                subject_area="해석",
                review_status="ai_estimated",
            ),
            AtomSearchHit(
                atom_code=_ATOM_B,
                similarity=0.8,
                name_ko="합성함수",
                subject_area="대수",
                review_status="ai_estimated",
            ),
        ]
        # 좌석이 잡은 code들·같은 엔진(index._engine)을 메타 조회에 넘긴다(N+1 없음·엔진 공유).
        assert captured["codes"] == [_ATOM_A, _ATOM_B]
        assert captured["engine"] is index._engine

    def test_missing_meta_is_none_graceful(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="극한", subject_area="해석", review_status="ai_estimated")
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits[0].name_ko == "극한"
        # _ATOM_B는 메타 없음 → 모든 메타 필드 None(but 여전히 결과에 포함·기본 비게이팅).
        assert hits[1].atom_code == _ATOM_B
        assert hits[1].name_ko is None
        assert hits[1].subject_area is None
        assert hits[1].review_status is None

    def test_subject_area_may_be_none_even_with_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # atom_node.subject_area는 nullable — 메타가 있어도 subject_area가 None일 수 있다.
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="단원명", subject_area=None, review_status="ai_estimated")
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0)])
        hits = search_atoms(
            "단원",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits[0].name_ko == "단원명"
        assert hits[0].subject_area is None
        assert hits[0].review_status == "ai_estimated"


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 검수 게이팅(reviewed_only) — reviewed만 통과·메타 없음 제외·'ai_estimated' 전량 제외
# ──────────────────────────────────────────────────────────────────────────
class TestReviewedOnlyGating:
    def test_reviewed_only_filters_non_reviewed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 원자 검수 승격을 가정한 혼재 상태(reviewed vs ai_estimated) — reviewed만 남는다.
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="극한", subject_area="d", review_status="reviewed"),
            _ATOM_B: AtomNodeMeta(name_ko="합성", subject_area="d", review_status="ai_estimated"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            reviewed_only=True,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A]
        assert hits[0].review_status == "reviewed"

    def test_reviewed_only_excludes_all_ai_estimated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 현행 원자는 전 행 'ai_estimated'(상수) — reviewed_only=True면 *전부* 제외(정직·docstring).
        meta = {
            _ATOM_A: AtomNodeMeta(
                name_ko="극한", subject_area="d", review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED
            ),
            _ATOM_B: AtomNodeMeta(
                name_ko="합성", subject_area="d", review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED
            ),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            reviewed_only=True,
            index=index,
            settings=_pgvector_settings(),
        )
        assert hits == []  # 'ai_estimated'는 reviewed가 아니라 전량 제외

    def test_reviewed_only_excludes_missing_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {_ATOM_A: AtomNodeMeta(name_ko="극한", subject_area="d", review_status="reviewed")}
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            reviewed_only=True,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A]  # _ATOM_B(메타 없음) 제외

    def test_default_keeps_all_recall(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _ATOM_A: AtomNodeMeta(
                name_ko="극한", subject_area="d", review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED
            )
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.2)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A, _ATOM_B]  # 둘 다(ai_estimated·메타없음)


# ──────────────────────────────────────────────────────────────────────────
# ⑦ 반환 타입 — atom_code+similarity+안전 메타만(본문 0·노출 계약)
# ──────────────────────────────────────────────────────────────────────────
def test_hit_has_only_safe_fields() -> None:
    fields = set(AtomSearchHit.__dataclass_fields__)
    assert fields == {"atom_code", "similarity", "name_ko", "subject_area", "review_status"}
    assert "description" not in fields
    assert "formal_definition" not in fields
    assert "core_proposition" not in fields


# ──────────────────────────────────────────────────────────────────────────
# ⑧ 임계 게이팅(min_similarity) — 근접도 미만 제외·기본 None 불변·정렬 유지
# ──────────────────────────────────────────────────────────────────────────
class TestMinSimilarityGating:
    def test_filters_below_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.4)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            min_similarity=0.8,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A]
        assert hits[0].similarity == 1.0

    def test_threshold_is_inclusive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.25)])  # sim = 0.75
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            min_similarity=0.75,
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A]

    def test_none_keeps_all_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.9)])
        hits = search_atoms(
            "극한",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A, _ATOM_B]


# ──────────────────────────────────────────────────────────────────────────
# ⑨ 영역 스코프(subject_area) — 일치만 통과·불일치/메타없음 제외·기본 None 불변
# ──────────────────────────────────────────────────────────────────────────
class TestSubjectAreaScoping:
    def test_filters_mismatched_subject_area(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="함수", subject_area="해석", review_status="reviewed"),
            _ATOM_B: AtomNodeMeta(name_ko="함수", subject_area="대수", review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.1)])
        hits = search_atoms(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            subject_area="해석",
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A]
        assert hits[0].subject_area == "해석"

    def test_excludes_missing_or_null_subject_area(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 메타 없거나 subject_area가 None이라 확인 불가면 스코프 모드에서 보수적 제외(정직).
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="함수", subject_area="해석", review_status="reviewed"),
            _ATOM_C: AtomNodeMeta(name_ko="단원", subject_area=None, review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows(
            [_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.1), _search_row(_ATOM_C, 0.15)]
        )
        hits = search_atoms(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            subject_area="해석",
            index=index,
            settings=_pgvector_settings(),
        )
        # _ATOM_B(메타 없음)·_ATOM_C(subject_area None) 모두 제외.
        assert [h.atom_code for h in hits] == [_ATOM_A]

    def test_none_keeps_all_subject_areas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _ATOM_A: AtomNodeMeta(name_ko="함수", subject_area="해석", review_status="reviewed"),
            _ATOM_B: AtomNodeMeta(name_ko="함수", subject_area="대수", review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        index, _engine = _index_with_rows([_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.1)])
        hits = search_atoms(
            "함수",
            top_k=5,
            provider=FakeEmbeddingProvider(),
            index=index,
            settings=_pgvector_settings(),
        )
        assert [h.atom_code for h in hits] == [_ATOM_A, _ATOM_B]


# ──────────────────────────────────────────────────────────────────────────
# ⑩ 게이팅 조합 — reviewed_only·min_similarity·subject_area 동시 적용·정렬 유지
# ──────────────────────────────────────────────────────────────────────────
def test_combined_gating_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    meta = {
        _ATOM_A: AtomNodeMeta(name_ko="극한", subject_area="해석", review_status="reviewed"),
        _ATOM_B: AtomNodeMeta(name_ko="합성", subject_area="해석", review_status="ai_estimated"),
        _ATOM_C: AtomNodeMeta(name_ko="연속", subject_area="해석", review_status="reviewed"),
    }
    _patch_meta(monkeypatch, meta)
    index, _engine = _index_with_rows(
        [_search_row(_ATOM_A, 0.0), _search_row(_ATOM_B, 0.1), _search_row(_ATOM_C, 0.15)]
    )
    hits = search_atoms(
        "극한 연속",
        top_k=5,
        provider=FakeEmbeddingProvider(),
        reviewed_only=True,
        min_similarity=0.5,
        subject_area="해석",
        index=index,
        settings=_pgvector_settings(),
    )
    # _ATOM_B는 ai_estimated로 탈락. _ATOM_A(1.0)·_ATOM_C(0.85) 통과·정렬 유지.
    assert [h.atom_code for h in hits] == [_ATOM_A, _ATOM_C]
    assert [h.similarity for h in hits] == [1.0, 0.85]


def test_accepts_any_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # 구조적 타이핑 — 신규 provider 없이 임의 embed 좌석을 받는다(provider seam 재사용).
    _patch_meta(monkeypatch)

    class _Scripted:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.3, 0.4] for _ in texts]

    index, _engine = _index_with_rows(
        [_search_row(_ATOM_A, 0.1)], provider_name="_Scripted", model_name="_Scripted"
    )
    hits = search_atoms(
        "q", top_k=1, provider=_Scripted(), index=index, settings=_pgvector_settings()
    )
    assert len(hits) == 1
    assert hits[0].atom_code == _ATOM_A


# ──────────────────────────────────────────────────────────────────────────
# ⑪ fetch_atom_node_meta 단위 — graceful 누락·빈 입력·안전 필드 조립
# ──────────────────────────────────────────────────────────────────────────
class TestFetchAtomNodeMeta:
    def test_empty_input_returns_empty_dict_without_query(self) -> None:
        # 빈 입력이면 쿼리 없이 {}(엔진 미접촉).
        engine = _FakeEngine(rows=[_FakeRow(code=_ATOM_A)])
        result = fetch_atom_node_meta([], engine=engine)  # type: ignore[arg-type]
        assert result == {}
        assert engine.executed == []

    def test_maps_rows_to_meta_by_code(self) -> None:
        rows = [
            _FakeRow(
                code=_ATOM_A,
                name_ko="극한",
                subject_area="해석",
                review_status="ai_estimated",
            ),
            _FakeRow(code=_ATOM_C, name_ko="단원", subject_area=None, review_status="ai_estimated"),
        ]
        engine = _FakeEngine(rows=rows)
        result = fetch_atom_node_meta(
            [_ATOM_A, _ATOM_B, _ATOM_C], engine=engine  # type: ignore[arg-type]
        )
        # 조회된 code만 dict에 담기고, 없는 code(_ATOM_B)는 빠진다(graceful 누락).
        assert set(result) == {_ATOM_A, _ATOM_C}
        assert result[_ATOM_A] == AtomNodeMeta(
            name_ko="극한", subject_area="해석", review_status="ai_estimated"
        )
        assert result[_ATOM_C].subject_area is None  # nullable subject_area 보존
        assert len(engine.executed) == 1
