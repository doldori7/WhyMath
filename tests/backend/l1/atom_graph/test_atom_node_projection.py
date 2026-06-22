"""원자 메타 PG 프로젝션 적재 *단위테스트* — 원자 마이그레이션 Phase 2a (hermetic·PG 불요).

이 샌드박스·CI hermetic 잡엔 PostgreSQL이 없으므로 `AtomNodeStore`의 *실 라운드트립*은
통합테스트(`test_atom_node_projection_integration.py`·실 PG 게이트)로 미룬다. 여기서는 PG 없이
검증 가능한 것만 못 박는다(`test_concept_node_projection.py` 가짜 엔진 패턴 미러):

  ① graph.json 로딩 — code 키 + 안전 메타(level 직대응·난이도/None·standard_codes·atomicity)·
     redaction 키 무시·전량(빈 옵션 필드도 적재)
  ② 필수 필드 누락 graceful — name/level 없으면 건너뜀(NOT NULL 위반 방지)
  ③ redaction 단언 — 레코드에 core_proposition/description/formal_definition·4요소 슬롯 없음·
     upsert SQL에 미등장
  ④ upsert SQL 구성 — ON CONFLICT(code) upsert·review_status='ai_estimated'·안전 메타 컬럼 포함
  ⑤ populate — 전 레코드 upsert(횟수=레코드 수)·멱등(같은 레코드 2회→같은 upsert statement)

가짜 엔진(`_FakeEngine`)은 begin() 컨텍스트 + execute()를 흉내내 실행된 statement를 기록한다 —
psycopg/PG 없이 배선·redaction을 검증한다(`test_concept_node_projection.py` 동형).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.db.models.atom_node import ATOM_REVIEW_STATUS_AI_ESTIMATED
from whymath_backend.l1.atom_graph.atom_node_projection import (
    AtomNodeRecord,
    AtomNodeStore,
    load_atom_nodes_from_graph_json,
    populate_atom_nodes,
)

# 원자 code 규약 예시(원자ID·소단원코드·단원코드 — backend `concept.code`와 동일 공간).
_ATOM_A = "2수01-01-2"
_SUBUNIT = "초수연-U1-S1"


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin() 컨텍스트 + execute() (PG 없이 배선 관찰)
# ──────────────────────────────────────────────────────────────────────────
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

    def execute(self, statement: object) -> None:
        self._engine.executed.append(statement)
        return None


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 기록."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store() -> tuple[AtomNodeStore, _FakeEngine]:
    """가짜 엔진을 주입한 AtomNodeStore + 엔진(검사용) 페어."""
    engine = _FakeEngine()
    store = AtomNodeStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    return store, engine


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


def _record(
    code: str = _ATOM_A,
    *,
    name_ko: str = "기수 원리",
    level: str = "세부개념",
) -> AtomNodeRecord:
    return AtomNodeRecord(
        code=code,
        name_ko=name_ko,
        level=level,
        parent_code=_SUBUNIT,
        school_level="초등",
        subject_area="수와 연산",
        subunit_code=_SUBUNIT,
        cognitive_type="개념",
        node_type="구성",
        misconception_type="개념혼동",
        intrinsic_difficulty=1,
        standard_codes=("[2수01-01]",),
        transfer="세기의 마지막 수=모음의 크기",
        transfer_example="사과 3개 세기",
        atomicity={"a": "예", "b": "예"},
    )


# ──────────────────────────────────────────────────────────────────────────
# ① graph.json 로딩 — code 키·안전 메타·level 직대응·난이도/None·standard_codes·atomicity
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_extracts_code_and_safe_meta(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _ATOM_A,
                    "name": "기수 원리",
                    "level": "세부개념",
                    "parent_code": _SUBUNIT,
                    "school_level": "초등",
                    "subject_area": "수와 연산",
                    "subunit_code": _SUBUNIT,
                    "cognitive_type": "개념",
                    "node_type": "구성",
                    "misconception_type": "개념혼동",
                    "intrinsic_difficulty": 1,
                    "standard_codes": ["[2수01-01]"],
                    "transfer": "세기의 마지막 수",
                    "transfer_example": "사과 3개",
                    "atomicity": {"a": "예", "b": "예", "c": "예", "d": "예"},
                }
            ],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert loaded == [
            AtomNodeRecord(
                code=_ATOM_A,
                name_ko="기수 원리",
                level="세부개념",
                parent_code=_SUBUNIT,
                school_level="초등",
                subject_area="수와 연산",
                subunit_code=_SUBUNIT,
                cognitive_type="개념",
                node_type="구성",
                misconception_type="개념혼동",
                intrinsic_difficulty=1,
                standard_codes=("[2수01-01]",),
                transfer="세기의 마지막 수",
                transfer_example="사과 3개",
                atomicity={"a": "예", "b": "예", "c": "예", "d": "예"},
            )
        ]

    def test_level_maps_directly_for_all_three_tiers(self, tmp_path: Path) -> None:
        # level은 직대응(단원/소단원/세부개념) — 고정 아님(Phase 1 적재기 철학 일관).
        path = self._write_graph(
            tmp_path,
            [
                {"code": "초수연-U1", "name": "수와 연산", "level": "단원"},
                {"code": _SUBUNIT, "name": "100까지의 수", "level": "소단원"},
                {"code": _ATOM_A, "name": "기수 원리", "level": "세부개념"},
            ],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert [c.level for c in loaded] == ["단원", "소단원", "세부개념"]

    def test_loads_all_nodes_including_empty_optional_fields(self, tmp_path: Path) -> None:
        # 단원/소단원은 난이도·인지축 등이 None — 전량 적재(검색·필터 recall).
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": "초수연-U1",
                    "name": "수와 연산",
                    "level": "단원",
                    "parent_code": None,
                    "intrinsic_difficulty": None,
                    "cognitive_type": None,
                    "standard_codes": [],
                    "atomicity": {},
                }
            ],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert len(loaded) == 1
        rec = loaded[0]
        assert rec.parent_code is None
        assert rec.intrinsic_difficulty is None  # 단원은 난이도 없음
        assert rec.cognitive_type is None
        assert rec.standard_codes == ()
        assert rec.atomicity is None  # 빈 dict → None 정규화

    def test_standard_codes_non_list_becomes_empty(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "code": _ATOM_A,
                    "name": "x",
                    "level": "세부개념",
                    "standard_codes": "단일문자열은리스트아님",
                }
            ],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert loaded[0].standard_codes == ()

    def test_atomicity_non_dict_becomes_none(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [{"code": _ATOM_A, "name": "x", "level": "세부개념", "atomicity": "비-dict"}],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert loaded[0].atomicity is None

    def test_difficulty_string_coerced_to_int(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [{"code": _ATOM_A, "name": "x", "level": "세부개념", "intrinsic_difficulty": "3"}],
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert loaded[0].intrinsic_difficulty == 3

    def test_missing_code_raises(self, tmp_path: Path) -> None:
        import pytest

        path = self._write_graph(tmp_path, [{"name": "키 없음", "level": "세부개념"}])
        with pytest.raises(ValueError, match="code"):
            load_atom_nodes_from_graph_json(path)


# ──────────────────────────────────────────────────────────────────────────
# ② 필수 필드 누락 graceful — name/level 없으면 건너뜀
# ──────────────────────────────────────────────────────────────────────────
class TestMissingRequiredFields:
    def _write(self, tmp_path: Path, concept: dict[str, object]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(json.dumps({"concepts": [concept]}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_skips_when_name_missing(self, tmp_path: Path) -> None:
        loaded = load_atom_nodes_from_graph_json(
            self._write(tmp_path, {"code": _ATOM_A, "level": "세부개념"})
        )
        assert loaded == []  # name 없음 → 건너뜀(NOT NULL 위반 방지)

    def test_skips_when_name_blank(self, tmp_path: Path) -> None:
        loaded = load_atom_nodes_from_graph_json(
            self._write(tmp_path, {"code": _ATOM_A, "name": "  ", "level": "세부개념"})
        )
        assert loaded == []

    def test_skips_when_level_missing(self, tmp_path: Path) -> None:
        loaded = load_atom_nodes_from_graph_json(
            self._write(tmp_path, {"code": _ATOM_A, "name": "x"})
        )
        assert loaded == []


# ──────────────────────────────────────────────────────────────────────────
# ③ redaction — 레코드 슬롯 부재 + upsert SQL 미등장(우선순위 #2·절대)
# ──────────────────────────────────────────────────────────────────────────
class TestRedaction:
    REDACTED_FIELDS = (
        "core_proposition",
        "description",
        "formal_definition",
        # 4요소(Phase 3 승격 대상) — 메타 프로젝션이 선점·이중 보관하지 않음.
        "misconception",
        "diagnostic_item",
        "diagnostic_answer",
        "diagnostic_signal",
        "socratic",
    )

    def test_record_has_no_redacted_slots(self) -> None:
        # 레코드 dataclass에 본문·4요소 슬롯이 *없다*(구조적 차단).
        fields = set(AtomNodeRecord.__dataclass_fields__)
        for f in self.REDACTED_FIELDS:
            assert f not in fields, f"AtomNodeRecord에 redaction 필드 누출: {f}"

    def test_record_keeps_only_safe_meta(self) -> None:
        # 안전 메타만 — 본문/④요소(misconception/diagnostic/socratic)는 없고,
        # transfer·atomicity는 포함.
        fields = set(AtomNodeRecord.__dataclass_fields__)
        assert fields == {
            "code",
            "name_ko",
            "level",
            "parent_code",
            "school_level",
            "subject_area",
            "subunit_code",
            "cognitive_type",
            "node_type",
            "misconception_type",
            "intrinsic_difficulty",
            "standard_codes",
            "transfer",
            "transfer_example",
            "atomicity",
        }

    def test_load_ignores_redacted_fields_if_present(self, tmp_path: Path) -> None:
        # graph.json엔 본문·4요소가 있으나, *오염되어 들어와도* 레코드에 유입되지 않음을 못 박는다.
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps(
                {
                    "concepts": [
                        {
                            "code": _ATOM_A,
                            "name": "기수 원리",
                            "level": "세부개념",
                            "core_proposition": "핵심명제(절대 적재 금지)",
                            "description": "본문 근접 서술(절대 적재 금지)",
                            "formal_definition": "∀ε>0 ... (절대 적재 금지)",
                            "misconception": "오개념 본문(Phase 3 승격·여기 금지)",
                            "diagnostic_item": "진단문항(Phase 3 승격·여기 금지)",
                            "diagnostic_answer": "정답(여기 금지)",
                            "diagnostic_signal": "오답신호(여기 금지)",
                            "socratic": "소크라테스질문(여기 금지)",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loaded = load_atom_nodes_from_graph_json(path)
        assert len(loaded) == 1
        rec = loaded[0]
        assert rec.name_ko == "기수 원리"  # 안전 필드만 채워짐

    def test_upsert_sql_omits_redacted_columns(self) -> None:
        # redaction: INSERT 컬럼에 본문·4요소가 *없다*(컬럼 자체 부재).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        # 안전 컬럼 `misconception_type`이 `misconception` 부분문자열 검사를 오염시키므로
        # 먼저 제거한다(안전 컬럼 자체는 별도 단언으로 존재 확인 — TestUpsertStatement).
        # 그 뒤 redaction 필드 부재 단언.
        sanitized = compiled.replace("misconception_type", "")
        for f in self.REDACTED_FIELDS:
            assert f not in sanitized, f"upsert SQL에 redaction 필드 누출: {f}"
        # 안전 컬럼은 여전히 SQL에 있다(원본 compiled 기준·sanitize 전).
        assert "misconception_type" in compiled


# ──────────────────────────────────────────────────────────────────────────
# ④ upsert SQL 구성 — ON CONFLICT(code)·review_status='ai_estimated'·안전 메타 컬럼
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO atom_node" in compiled
        assert "ON CONFLICT" in compiled

    def test_upsert_targets_code_pk(self) -> None:
        # 키 일관성: 충돌 키가 code(PK·backend concept.code와 동일 공간·UC 아님).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "atom_node.code" in compiled or "(code)" in compiled

    def test_upsert_includes_safe_meta_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in (
            "name_ko",
            "level",
            "parent_code",
            "school_level",
            "subject_area",
            "subunit_code",
            "cognitive_type",
            "node_type",
            "misconception_type",
            "intrinsic_difficulty",
            "standard_codes",
            "transfer",
            "transfer_example",
            "atomicity",
            "review_status",
        ):
            assert col in compiled, f"upsert SQL에 안전 컬럼 누락: {col}"

    def test_upsert_binds_review_status_ai_estimated(self) -> None:
        # 원자 메타는 AI 추정 — review_status 상수가 'ai_estimated'(정직 표기·게이팅).
        assert ATOM_REVIEW_STATUS_AI_ESTIMATED == "ai_estimated"
        from sqlalchemy.dialects import postgresql

        store, engine = _fake_store()
        store.upsert(_record())
        # 바인드 파라미터에 'ai_estimated'가 실린다(레코드 값이 아닌 코드 상수).
        compiled = engine.executed[0].compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect()
        )
        assert "ai_estimated" in compiled.params.values()


# ──────────────────────────────────────────────────────────────────────────
# ⑤ populate — 전 레코드 upsert·멱등
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_record(self) -> None:
        store, engine = _fake_store()
        records = [_record(_ATOM_A), _record("2수01-01-3")]
        count = populate_atom_nodes(records, store=store)
        assert count == 2
        assert len(engine.executed) == 2  # 레코드당 1 upsert

    def test_populate_empty_is_noop(self) -> None:
        store, engine = _fake_store()
        assert populate_atom_nodes([], store=store) == 0
        assert engine.executed == []

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 레코드 2회 populate → 같은 upsert(ON CONFLICT) statement(멱등 — 실 행 1개는 통합).
        store, engine = _fake_store()
        records = [_record(_ATOM_A)]
        populate_atom_nodes(records, store=store)
        populate_atom_nodes(records, store=store)
        assert len(engine.executed) == 2
        for stmt in engine.executed:
            assert "ON CONFLICT" in _compile(stmt)


def test_store_uses_default_settings_when_unset() -> None:
    # store에 settings·engine 미주입이면 전역 Settings를 지연 해석한다(엔진 생성은 첫 upsert에서).
    store = AtomNodeStore()
    assert isinstance(store._resolved_settings, Settings)
