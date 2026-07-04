"""개념 메타 PG 프로젝션 적재 *단위테스트* — 개념그래프 소비 슬1 (hermetic·PG 불요).

이 샌드박스·CI hermetic 잡엔 PostgreSQL이 없으므로 `ConceptNodeStore`/`fetch_node_meta`의 *실
라운드트립*은 통합테스트(`test_concept_node_projection_integration.py`·실 PG 게이트)로 미룬다.
여기서는 PG 없이 검증 가능한 것만 못 박는다(슬3 `test_concept_embedding.py` 가짜 엔진 패턴 재사용):

  ① graph.json 로딩 — UC concept_id + 안전 메타 추출·redaction 키 무시·전량(빈 표현도 적재)
  ② 필수 필드 누락 graceful — name_ko/domain/review_status 없으면 건너뜀(NOT NULL 위반 방지)
  ③ upsert SQL 구성 — ON CONFLICT(concept_id) upsert·**본문 컬럼(description/formal_definition) 0**
  ④ populate — 전 레코드 upsert(횟수=레코드 수)·멱등(같은 레코드 2회→같은 upsert statement)
  ⑤ fetch_node_meta SQL — IN(concept_id) 조회·안전 필드만 SELECT·빈 입력 graceful

가짜 엔진(`_FakeEngine`)은 begin()/connect() 컨텍스트 + execute()를 흉내내 실행된 statement를
기록하고, fetch엔 canned 행을 돌려준다 — psycopg/PG 없이 배선·redaction을 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.node_projection import (
    ConceptNodeMeta,
    ConceptNodeRecord,
    ConceptNodeStore,
    fetch_node_meta,
    load_concept_nodes_from_graph_json,
    populate_concept_nodes,
)

# 슬2 idmap이 발급하는 UC 규약 키 예시(슬2 Neo4j 노드 키·슬3 concept_embedding과 동일 공간).
_UC_A = "UC.calc.alimit.epsilon-delta"
_UC_B = "UC.alg.afunction.composition"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin()/connect() 컨텍스트 + execute() (PG 없이 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
class _FakeMetaRow:
    """fetch_node_meta 결과 행 흉내 — concept_id·name_ko·domain·review_status 속성 접근."""

    def __init__(self, concept_id: str, name_ko: str, domain: str, review_status: str) -> None:
        self.concept_id = concept_id
        self.name_ko = name_ko
        self.domain = domain
        self.review_status = review_status


class _FakeResult:
    def __init__(self, rows: list[_FakeMetaRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeMetaRow]:
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
        return _FakeResult(self._engine.fetch_rows)


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin()/connect() + 실행 statement 기록 + canned fetch."""

    def __init__(self, fetch_rows: list[_FakeMetaRow] | None = None) -> None:
        self.executed: list[object] = []
        self.fetch_rows: list[_FakeMetaRow] = fetch_rows or []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store() -> tuple[ConceptNodeStore, _FakeEngine]:
    """가짜 엔진을 주입한 ConceptNodeStore + 엔진(검사용) 페어."""
    engine = _FakeEngine()
    store = ConceptNodeStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    return store, engine


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


def _record(
    concept_id: str = _UC_A,
    *,
    name_ko: str = "극한",
    domain: str = "[고]미적분",
    review_status: str = "reviewed",
) -> ConceptNodeRecord:
    return ConceptNodeRecord(
        concept_id=concept_id,
        name_ko=name_ko,
        domain=domain,
        review_status=review_status,
        standard_codes=("10공수1-01-01",),
        ccss_code=None,
        difficulty_tier=3,
        behavior_skills=("skill.factorization",),
    )


# ──────────────────────────────────────────────────────────────────────────
# ① graph.json 로딩 — UC 키·안전 메타·redaction 키 무시·전량
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_extracts_uc_and_safe_meta(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "domain": "[고]미적분",
                    "review_status": "reviewed",
                    "standard_codes": ["10공수1-01-01", "10공수1-01-02"],
                    "ccss_code": "HSF.IF.B.4",
                    "difficulty_tier": 7,
                    "behavior_skills": ["skill.factorization", "skill.quadratic-equation-solving"],
                    # metaphor·accepted는 Stage B로 프로젝션에서 제거됨 — 입력에 있어도 *무시*된다.
                    "metaphor": "무시돼야 함",
                    "accepted_expressions": "무시돼야 함",
                }
            ],
        )
        loaded = load_concept_nodes_from_graph_json(path)
        assert loaded == [
            ConceptNodeRecord(
                concept_id=_UC_A,
                name_ko="극한",
                domain="[고]미적분",
                review_status="reviewed",
                standard_codes=("10공수1-01-01", "10공수1-01-02"),
                ccss_code="HSF.IF.B.4",
                difficulty_tier=7,
                behavior_skills=("skill.factorization", "skill.quadratic-equation-solving"),
            )
        ]

    def test_ignores_description_and_formal_definition_if_present(self, tmp_path: Path) -> None:
        # graph.json엔 본디 없지만, *오염되어 들어와도* 메타 레코드에 유입되지 않음을 못 박는다.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "domain": "[고]미적분",
                    "review_status": "pending",
                    "description": "교과서 본문 근접 서술(절대 적재 금지)",
                    "formal_definition": "∀ε>0 ∃δ>0 ... (절대 적재 금지)",
                }
            ],
        )
        loaded = load_concept_nodes_from_graph_json(path)
        assert len(loaded) == 1
        rec = loaded[0]
        # ConceptNodeRecord에 본문 슬롯이 없다(구조적 차단) — dataclass 필드에 부재.
        fields = set(ConceptNodeRecord.__dataclass_fields__)
        assert "description" not in fields
        assert "formal_definition" not in fields
        # 안전 필드만 채워졌다.
        assert rec.name_ko == "극한"
        assert rec.review_status == "pending"

    def test_loads_all_concepts_including_empty_optional_fields(self, tmp_path: Path) -> None:
        # 슬3 임베딩 로더와 달리 빈 표현 제외 없음 — 메타는 전량 적재(enrichment·게이팅 recall).
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "유효",
                    "domain": "대수",
                    "review_status": "reviewed",
                },
                {
                    "concept_id": _UC_B,
                    "name_ko": "둘째",
                    "domain": "기하",
                    "review_status": "pending",
                },
            ],
        )
        loaded = load_concept_nodes_from_graph_json(path)
        assert [c.concept_id for c in loaded] == [_UC_A, _UC_B]
        # 옵션 필드는 None·빈 standard_codes로 정규화.
        assert loaded[0].ccss_code is None
        assert loaded[0].standard_codes == ()
        assert loaded[0].difficulty_tier is None

    def test_standard_codes_non_list_becomes_empty(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "x",
                    "domain": "d",
                    "review_status": "reviewed",
                    "standard_codes": "단일문자열은리스트아님",
                }
            ],
        )
        loaded = load_concept_nodes_from_graph_json(path)
        assert loaded[0].standard_codes == ()

    def test_missing_concept_id_raises(self, tmp_path: Path) -> None:
        import pytest

        path = self._write_graph(
            tmp_path, [{"name_ko": "키 없음", "domain": "d", "review_status": "x"}]
        )
        with pytest.raises(ValueError, match="concept_id"):
            load_concept_nodes_from_graph_json(path)


# ──────────────────────────────────────────────────────────────────────────
# ② 필수 필드 누락 graceful — name_ko/domain/review_status 없으면 건너뜀
# ──────────────────────────────────────────────────────────────────────────
class TestMissingRequiredFields:
    def _write(self, tmp_path: Path, concept: dict[str, object]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(json.dumps({"concepts": [concept]}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_skips_when_name_ko_missing(self, tmp_path: Path) -> None:
        loaded = load_concept_nodes_from_graph_json(
            self._write(
                tmp_path,
                {"concept_id": _UC_A, "domain": "d", "review_status": "reviewed"},
            )
        )
        assert loaded == []  # name_ko 없음 → 건너뜀(NOT NULL 위반 방지)

    def test_skips_when_domain_blank(self, tmp_path: Path) -> None:
        loaded = load_concept_nodes_from_graph_json(
            self._write(
                tmp_path,
                {
                    "concept_id": _UC_A,
                    "name_ko": "x",
                    "domain": "  ",
                    "review_status": "reviewed",
                },
            )
        )
        assert loaded == []

    def test_skips_when_review_status_missing(self, tmp_path: Path) -> None:
        loaded = load_concept_nodes_from_graph_json(
            self._write(tmp_path, {"concept_id": _UC_A, "name_ko": "x", "domain": "d"})
        )
        assert loaded == []


# ──────────────────────────────────────────────────────────────────────────
# ③ upsert SQL 구성 — ON CONFLICT + redaction(description/formal_definition 미포함)
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO concept_node" in compiled
        assert "ON CONFLICT" in compiled

    def test_upsert_targets_concept_id_pk(self) -> None:
        # UC 키 일관성: 충돌 키가 concept_id(PK)다(슬2 Neo4j·슬3 concept_embedding과 동일 공간).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "concept_node.concept_id" in compiled or "(concept_id)" in compiled

    def test_upsert_omits_redacted_columns(self) -> None:
        # redaction: INSERT 컬럼에 description/formal_definition이 *없다*(컬럼 자체 부재).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "description" not in compiled
        assert "formal_definition" not in compiled
        # 안전 표시·게이팅 컬럼은 포함.
        assert "name_ko" in compiled
        assert "review_status" in compiled

    def test_upsert_includes_safe_meta_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in (
            "domain",
            "standard_codes",
            "ccss_code",
            "difficulty_tier",
            "behavior_skills",
        ):
            assert col in compiled

    def test_upsert_omits_pedagogy_columns(self) -> None:
        # Stage B: metaphor·accepted_expressions는 프로젝션에서 제거(pedagogy=concept_content).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "metaphor" not in compiled
        assert "accepted_expressions" not in compiled


# ──────────────────────────────────────────────────────────────────────────
# ④ populate — 전 레코드 upsert·멱등
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_record(self) -> None:
        store, engine = _fake_store()
        records = [_record(_UC_A), _record(_UC_B)]
        count = populate_concept_nodes(records, store=store)
        assert count == 2
        assert len(engine.executed) == 2  # 레코드당 1 upsert

    def test_populate_empty_is_noop(self) -> None:
        store, engine = _fake_store()
        assert populate_concept_nodes([], store=store) == 0
        assert engine.executed == []

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 레코드 2회 populate → 같은 upsert(ON CONFLICT) statement(멱등 — 실 행 1개는 통합).
        store, engine = _fake_store()
        records = [_record(_UC_A)]
        populate_concept_nodes(records, store=store)
        populate_concept_nodes(records, store=store)
        assert len(engine.executed) == 2
        for stmt in engine.executed:
            assert "ON CONFLICT" in _compile(stmt)


# ──────────────────────────────────────────────────────────────────────────
# ⑤ fetch_node_meta SQL — IN 조회·안전 필드만·빈 입력 graceful
# ──────────────────────────────────────────────────────────────────────────
class TestFetchNodeMeta:
    def test_empty_input_returns_empty_without_query(self) -> None:
        engine = _FakeEngine()
        result = fetch_node_meta([], engine=engine)  # type: ignore[arg-type]
        assert result == {}
        assert engine.executed == []  # 빈 입력 → 쿼리 생략

    def test_fetch_builds_in_query_with_safe_fields(self) -> None:
        engine = _FakeEngine(fetch_rows=[_FakeMetaRow(_UC_A, "극한", "[고]미적분", "reviewed")])
        result = fetch_node_meta([_UC_A, _UC_B], engine=engine)  # type: ignore[arg-type]
        compiled = _compile(engine.executed[0])
        # IN 조회·안전 필드 SELECT·본문 미조회.
        assert "concept_node.name_ko" in compiled
        assert "concept_node.review_status" in compiled
        assert "IN (" in compiled
        assert "description" not in compiled
        assert "formal_definition" not in compiled
        # 결과 dict는 UC 키 → ConceptNodeMeta.
        assert result == {
            _UC_A: ConceptNodeMeta(name_ko="극한", domain="[고]미적분", review_status="reviewed")
        }

    def test_missing_uc_absent_from_result(self) -> None:
        # canned 행에 없는 UC는 결과 dict에서 빠진다(graceful — 호출자가 None 처리).
        engine = _FakeEngine(fetch_rows=[_FakeMetaRow(_UC_A, "극한", "d", "reviewed")])
        result = fetch_node_meta([_UC_A, _UC_B], engine=engine)  # type: ignore[arg-type]
        assert _UC_A in result
        assert _UC_B not in result


# ──────────────────────────────────────────────────────────────────────────
# ConceptNodeMeta — 안전 필드만(본문 0·노출 계약)
# ──────────────────────────────────────────────────────────────────────────
def test_node_meta_has_only_safe_fields() -> None:
    fields = set(ConceptNodeMeta.__dataclass_fields__)
    assert fields == {"name_ko", "domain", "review_status"}
    assert "description" not in fields
    assert "formal_definition" not in fields


def test_store_uses_default_settings_when_unset() -> None:
    # store에 settings·engine 미주입이면 전역 Settings를 지연 해석한다(엔진 생성은 첫 upsert에서).
    store = ConceptNodeStore()
    assert isinstance(store._resolved_settings, Settings)
