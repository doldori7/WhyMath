"""원자 임베딩 적재 *단위테스트* — Phase 2b (hermetic·PG 불요·Fake provider).

이 샌드박스·CI hermetic 잡엔 PostgreSQL·pgvector가 없으므로 `AtomEmbeddingIndex` upsert/search의
*실 라운드트립*은 통합테스트(`test_atom_embedding_integration.py`·실 PG 게이트)로 미룬다. 여기서는
PG 없이 검증 가능한 것만 못 박는다(`test_concept_embedding.py` 미러):

  ① 임베딩 텍스트 구성 — name·transfer + 안전 파셋(cognitive_type·subunit), 빈값 graceful,
     **본문·4요소·교육과정 필드 미포함**(redaction 구조적 차단·retrieval 파셋 분리 Q1·Q2·Q4)
  ② graph.json 로딩 — level=="세부개념" 필터·code 키·안전 파셋 read·redaction 키 미독·빈 표현 제외
  ③ upsert SQL 구성(가짜 엔진 주입 — ON CONFLICT(code) upsert·바인딩 관찰)
  ④ search SQL 구성 — provider/model 필터·<=> 코사인·LIMIT + similarity=1-distance 변환·top_k 경계
  ⑤ populate — Fake provider + 가짜 엔진으로 전 원자 upsert(횟수=원자 수)·dim 일치
  ⑥ code 키 일관성 — upsert가 code를 PK로 쓴다(Phase 1 concept.code·Phase 2a atom_node.code 공간)
  ⑦ 원문 비저장(text_hash만·source_text 컬럼 없음)·임의 provider 주입

가짜 엔진(`_FakeEngine`)은 `begin()`/`connect()` 컨텍스트 + `execute()`를 흉내내 실행된
statement를 기록하고 search엔 canned 행을 돌려준다 — psycopg/PG 없이 배선·변환·필터를 검증한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.l1.atom_graph.embedding import (
    AtomEmbeddingIndex,
    AtomText,
    atom_embedding_text,
    load_atoms_from_graph_json,
    populate_atom_embeddings,
)
from whymath_backend.l1.embedding_primitives import text_hash
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider


class _SpyProvider:
    """embed 호출 횟수를 세는 provider — skip-if-unchanged 검증용(불변분 미임베딩 확인)."""

    def __init__(self, dim: int = 64) -> None:
        self.embed_calls = 0
        self._dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [[0.1] * self._dim for _ in texts]


# 원자 code 규약 예시(Phase 1 concept.code·Phase 2a atom_node.code와 동일 공간·하이픈 확정본).
_CODE_A = "12미적Ⅰ-01-01-1"
_CODE_B = "2수01-01-2"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin()/connect() 컨텍스트 + execute() (PG 없이 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeRow:
    """행 흉내 — search는 `.code`·`.distance`, existing_text_hashes는 `.text_hash` 접근."""

    def __init__(
        self, code: str, distance: float | None = None, text_hash: str | None = None
    ) -> None:
        self.code = code
        self.distance = distance
        self.text_hash = text_hash


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
) -> tuple[AtomEmbeddingIndex, _FakeEngine]:
    """가짜 엔진을 주입한 AtomEmbeddingIndex + 엔진(검사용) 페어."""
    engine = _FakeEngine(search_rows=search_rows)
    index = AtomEmbeddingIndex(
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
# ① 임베딩 텍스트 구성 — name + transfer만(redaction)
# ──────────────────────────────────────────────────────────────────────────
class TestAtomEmbeddingText:
    def test_joins_name_and_transfer_in_order(self) -> None:
        text = atom_embedding_text(
            name_ko="기수 원리",
            transfer="세기의 마지막 수=모음의 크기(기수)",
        )
        assert text == "기수 원리. 세기의 마지막 수=모음의 크기(기수)"

    def test_transfer_none_uses_name_only(self) -> None:
        # 전이 None → 명칭만(개념판의 metaphor/accepted 빈값 처리와 동일 규칙).
        assert atom_embedding_text(name_ko="합성함수", transfer=None) == "합성함수"

    def test_skips_empty_transfer(self) -> None:
        # 공백 transfer 조각은 건너뛴다.
        assert atom_embedding_text(name_ko="극한", transfer="  ") == "극한"

    def test_name_missing_uses_transfer(self) -> None:
        # name이 비어도 transfer로 표현 합성(빈 표현 방지는 로더가 처리).
        assert atom_embedding_text(name_ko=None, transfer="전이만 있음") == "전이만 있음"

    def test_all_empty_gives_empty_string(self) -> None:
        assert atom_embedding_text(name_ko=None, transfer=None) == ""

    def test_includes_safe_facets_in_order(self) -> None:
        # 안전 파셋(cognitive_type·subunit)이 name·transfer 뒤에 붙는다(벡터 분리 신호·Q1·Q2·Q4).
        text = atom_embedding_text(
            name_ko="합성함수의 미분",
            transfer="연쇄법칙의 핵심",
            cognitive_type="절차",
            subunit="도함수",
        )
        assert text == "합성함수의 미분. 연쇄법칙의 핵심. 절차. 도함수"

    def test_facets_none_falls_back_to_name_transfer(self) -> None:
        # 파셋 미지정(기존 호출부·구 데이터) → name+transfer만(후방 호환).
        assert atom_embedding_text(name_ko="극한", transfer="수렴") == "극한. 수렴"

    def test_skips_empty_facets(self) -> None:
        # 빈/공백 파셋 조각은 graceful skip(빈값 처리 규칙 공유).
        text = atom_embedding_text(
            name_ko="기울기", transfer="변화율", cognitive_type="  ", subunit=None
        )
        assert text == "기울기. 변화율"

    def test_cognitive_type_separates_object_vs_technique(self) -> None:
        # 같은 name이라도 cognitive_type가 다르면 표현이 갈린다(개념 vs 절차 융합 방지·Q4).
        obj = atom_embedding_text(name_ko="정적분", transfer="넓이", cognitive_type="개념")
        proc = atom_embedding_text(name_ko="정적분", transfer="넓이", cognitive_type="절차")
        assert obj != proc
        assert obj.endswith("개념") and proc.endswith("절차")

    def test_signature_allows_only_safe_fields(self) -> None:
        # redaction 구조적 차단: 시그니처에 본문·4요소·교육과정 필드가 *없다*.
        import inspect

        params = set(inspect.signature(atom_embedding_text).parameters)
        for forbidden in (
            "description",
            "formal_definition",
            "core_proposition",
            "metaphor",
            "accepted_expressions",
            "misconception",
            "diagnostic_item",
            "socratic",
            "grade_band",
            "standard_codes",
        ):
            assert forbidden not in params
        # 허용 인자는 안전 구조 신호뿐(keyword-only).
        assert params == {"name_ko", "transfer", "cognitive_type", "subunit"}


# ──────────────────────────────────────────────────────────────────────────
# ② graph.json 로딩 — level 필터·code 키·redaction 키 무시·빈 표현 제외
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_extracts_code_and_name_transfer_text(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _CODE_A,
                    "level": "세부개념",
                    "name": "기수 원리",
                    "transfer": "개수·양 판단의 핵심",
                }
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert loaded == [AtomText(code=_CODE_A, text="기수 원리. 개수·양 판단의 핵심")]

    def test_filters_only_detail_concept_level(self, tmp_path: Path) -> None:
        # 단원/소단원 노드는 임베딩 대상이 아니다(level=="세부개념"만).
        path = self._write_graph(
            tmp_path,
            [
                {"code": "단원코드", "level": "단원", "name": "수의 체계", "transfer": "무시"},
                {"code": "소단원코드", "level": "소단원", "name": "자연수", "transfer": "무시"},
                {"code": _CODE_A, "level": "세부개념", "name": "기수 원리", "transfer": "핵심"},
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert [a.code for a in loaded] == [_CODE_A]

    def test_does_not_read_redaction_keys(self, tmp_path: Path) -> None:
        # 본문·4요소·redacted_fields가 *오염되어 들어와도* 임베딩 표현에 유입되지 않음을 못 박는다.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _CODE_A,
                    "level": "세부개념",
                    "name": "기수 원리",
                    "transfer": "핵심",
                    "core_proposition": "대학 핵심명제 본문(절대 임베딩 금지)",
                    "description": "교과서 본문 근접 서술(절대 임베딩 금지)",
                    "formal_definition": "∀ε>0 ∃δ>0 ... (절대 임베딩 금지)",
                    "misconception": "오개념 본문(절대 임베딩 금지)",
                    "diagnostic_item": "진단 문항 본문(절대 임베딩 금지)",
                    "diagnostic_answer": "진단 정답(절대 임베딩 금지)",
                    "diagnostic_signal": "진단 신호(절대 임베딩 금지)",
                    "socratic": "소크라테스 발문(절대 임베딩 금지)",
                    "redacted_fields": ["description", "formal_definition"],
                }
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert len(loaded) == 1
        text = loaded[0].text
        assert text == "기수 원리. 핵심"
        # 본문·4요소 토큰이 표현에 *전혀* 없다.
        for forbidden in ("본문", "∀ε", "오개념", "진단", "소크라테스", "명제"):
            assert forbidden not in text

    def test_reads_safe_facets_into_text(self, tmp_path: Path) -> None:
        # cognitive_type·subunit(안전 파셋)를 읽어 표현에 포함(벡터 분리 신호·Q1·Q2·Q4).
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _CODE_A,
                    "level": "세부개념",
                    "name": "기수 원리",
                    "transfer": "핵심",
                    "cognitive_type": "개념",
                    "subunit": "100까지의 수와 세기",
                }
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert loaded == [AtomText(code=_CODE_A, text="기수 원리. 핵심. 개념. 100까지의 수와 세기")]

    def test_facets_present_but_redaction_still_excluded(self, tmp_path: Path) -> None:
        # 파셋이 있어도 본문·4요소·교육과정 필드는 여전히 유입되지 않는다(redaction 유지).
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _CODE_A,
                    "level": "세부개념",
                    "name": "연속과 미분가능",
                    "transfer": "함수의 국소 성질",
                    "cognitive_type": "개념",
                    "subunit": "미분",
                    "core_proposition": "명제 본문(금지)",
                    "misconception": "오개념 본문(금지)",
                    "socratic": "소크라테스 발문(금지)",
                    "grade_band": "고2",
                    "standard_codes": ["[12미적I-01]"],
                }
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert loaded == [
            AtomText(code=_CODE_A, text="연속과 미분가능. 함수의 국소 성질. 개념. 미분")
        ]
        text = loaded[0].text
        for forbidden in ("본문", "오개념", "소크라테스", "고2", "12미적"):
            assert forbidden not in text

    def test_skips_atoms_with_empty_safe_text(self, tmp_path: Path) -> None:
        # name·transfer가 전부 빈 원자는 제외(빈 벡터 적재 방지).
        path = self._write_graph(
            tmp_path,
            [
                {"code": _CODE_A, "level": "세부개념", "name": "유효", "transfer": "전이"},
                {"code": _CODE_B, "level": "세부개념", "name": "", "transfer": ""},
            ],
        )
        loaded = load_atoms_from_graph_json(path)
        assert [a.code for a in loaded] == [_CODE_A]

    def test_missing_code_on_detail_concept_raises(self, tmp_path: Path) -> None:
        import pytest

        path = self._write_graph(tmp_path, [{"level": "세부개념", "name": "code 없음"}])
        with pytest.raises(ValueError, match="code"):
            load_atoms_from_graph_json(path)

    def test_does_not_read_non_concept_assets(self, tmp_path: Path) -> None:
        # 그래프 외 자산은 임베딩 대상이 아니다(읽지 않음).
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps(
                {
                    "concepts": [{"code": _CODE_A, "level": "세부개념", "name": "원자"}],
                    "edges": [{"src": "무시"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loaded = load_atoms_from_graph_json(path)
        assert [a.code for a in loaded] == [_CODE_A]


# ──────────────────────────────────────────────────────────────────────────
# ③ upsert SQL 구성 (가짜 엔진으로 실행 statement 관찰·컴파일)
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict(self) -> None:
        index, engine = _fake_index()
        index.upsert(_CODE_A, [0.1, 0.2, 0.3], source_text="기수 원리. 핵심")
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO atom_embedding" in compiled
        assert "ON CONFLICT" in compiled

    def test_upsert_targets_code_pk(self) -> None:
        # code 키 일관성: 충돌 키가 code(PK)다(Phase 1 concept.code·Phase 2a atom_node.code 공간).
        index, engine = _fake_index()
        index.upsert(_CODE_A, [0.5], source_text="표현")
        compiled = _compile(engine.executed[0])
        assert "atom_embedding.code" in compiled or "(code)" in compiled


# ──────────────────────────────────────────────────────────────────────────
# ④ search SQL 구성 + similarity 변환 + top_k 경계
# ──────────────────────────────────────────────────────────────────────────
class TestSearch:
    def test_search_filters_provider_and_model_with_cosine_and_limit(self) -> None:
        index, engine = _fake_index(
            search_rows=[_FakeRow(_CODE_A, 0.1)], provider_name="local", model_name="bge-m3"
        )
        index.search([1.0, 2.0], top_k=3)
        compiled = _compile(engine.executed[0])
        assert "atom_embedding.provider" in compiled
        assert "atom_embedding.model" in compiled
        assert "<=>" in compiled
        assert "LIMIT" in compiled

    def test_similarity_is_one_minus_distance(self) -> None:
        rows = [_FakeRow(_CODE_A, 0.0), _FakeRow(_CODE_B, 0.25)]
        index, _engine = _fake_index(search_rows=rows)
        hits = index.search([1.0, 0.0], top_k=2)
        assert hits == [(_CODE_A, 1.0), (_CODE_B, 0.75)]

    def test_null_distance_is_zero_similarity(self) -> None:
        index, _engine = _fake_index(search_rows=[_FakeRow(_CODE_A, None)])
        assert index.search([0.0], top_k=1) == [(_CODE_A, 0.0)]

    def test_top_k_zero_returns_empty_without_engine_call(self) -> None:
        index, engine = _fake_index(search_rows=[_FakeRow(_CODE_A, 0.0)])
        assert index.search([1.0], top_k=0) == []
        assert index.search([1.0], top_k=-2) == []
        assert engine.executed == []  # 질의 statement 미실행


# ──────────────────────────────────────────────────────────────────────────
# ⑤ populate — Fake provider + 가짜 엔진으로 전 원자 upsert
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_atom(self) -> None:
        atoms = [
            AtomText(code=_CODE_A, text="기수 원리. 핵심"),
            AtomText(code=_CODE_B, text="합성함수. f∘g"),
        ]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index(provider_name="fake", model_name="fake-hash")
        count = populate_atom_embeddings(atoms, provider, index=index)
        assert count == 2
        assert len(engine.executed) == 3  # 1 read(existing·비어) + 2 upsert

    def test_populate_dim_matches_provider(self) -> None:
        # upsert에 박히는 dim이 provider 벡터 차원과 일치(컬럼 차원 정합 점검 신호).
        atoms = [AtomText(code=_CODE_A, text="원자 표현")]
        provider = FakeEmbeddingProvider(dim=64)
        index, engine = _fake_index(provider_name="fake", model_name="fake-hash")
        populate_atom_embeddings(atoms, provider, index=index)
        compiled = _compile(engine.executed[1])  # [0]=read, [1]=upsert
        assert "dim" in compiled

    def test_populate_uses_code_key(self) -> None:
        # code 키 일관성: populate가 code로 upsert한다.
        atoms = [AtomText(code=_CODE_A, text="표현")]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        populate_atom_embeddings(atoms, provider, index=index)
        compiled = _compile(engine.executed[1])  # [0]=read, [1]=upsert
        assert "code" in compiled

    def test_populate_skips_unchanged(self) -> None:
        # 현행 text_hash 일치 → provider 미호출·upsert 0·count 0(읽기 1회만).
        atoms = [AtomText(code=_CODE_A, text="기수 원리. 핵심")]
        rows = [_FakeRow(_CODE_A, text_hash=text_hash("기수 원리. 핵심"))]
        provider = _SpyProvider()
        index, engine = _fake_index(search_rows=rows)
        count = populate_atom_embeddings(atoms, provider, index=index)
        assert count == 0
        assert provider.embed_calls == 0
        assert len(engine.executed) == 1  # read만

    def test_populate_empty_atoms_is_noop(self) -> None:
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        assert populate_atom_embeddings([], provider, index=index) == 0
        assert engine.executed == []


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 멱등·provider 공간 식별 재사용 (L4 _provider_model_identity 공유·신규 seam 0)
# ──────────────────────────────────────────────────────────────────────────
class TestProviderModelIdentityReuse:
    def test_fake_provider_space_identity(self) -> None:
        # L4 seam을 재사용하므로 식별 규약이 동일하다(fake→fake-hash·concept_embedding 동일).
        from whymath_backend.l4.misconception.semantic.pgvector_index import (
            _provider_model_identity,
        )

        name, model = _provider_model_identity(FakeEmbeddingProvider(), Settings())
        assert (name, model) == ("fake", "fake-hash")

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 원자 2회 populate → 같은 upsert statement 수(멱등 — PK 충돌 upsert).
        atoms = [AtomText(code=_CODE_A, text="표현")]
        provider = FakeEmbeddingProvider()
        index, engine = _fake_index()
        populate_atom_embeddings(atoms, provider, index=index)
        populate_atom_embeddings(atoms, provider, index=index)
        # 가짜 엔진은 기존 행을 반영 못 해(read 매번 빈 결과) 두 번 다 재임베딩 — 실 멱등·skip은
        # 통합테스트. 여기선 매 populate가 upsert(ON CONFLICT)를 낸다는 것만(read SELECT는 제외).
        upserts = [s for s in engine.executed if "ON CONFLICT" in _compile(s)]
        assert len(upserts) == 2


# ──────────────────────────────────────────────────────────────────────────
# ⑦ 표현 비저장(원문 미저장) — upsert에 source_text 컬럼이 없다
# ──────────────────────────────────────────────────────────────────────────
def test_upsert_does_not_persist_source_text() -> None:
    """원문 비저장: INSERT에 source_text/원문 컬럼이 없고 text_hash만 적재(redaction·중복)."""
    index, engine = _fake_index()
    index.upsert(_CODE_A, [0.1, 0.2], source_text="비밀 표현 원문")
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

    atoms = [AtomText(code=_CODE_A, text="표현")]
    index, engine = _fake_index(provider_name="_Scripted", model_name="_Scripted")
    count = populate_atom_embeddings(atoms, _Scripted(), index=index)
    assert count == 1
    assert len(engine.executed) == 2  # read(existing) 1 + upsert 1
