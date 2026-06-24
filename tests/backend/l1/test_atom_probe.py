"""원자 ②진단문항·③소크라테스 → atom_probe 승격 *단위테스트* — Slice 3 (hermetic·PG 불요).

CI hermetic 잡엔 PostgreSQL이 없으므로 실 라운드트립은 통합테스트
(`test_atom_probe_integration.py`·실 PG)로 미룬다. 여기서는 PG 없이 검증 가능한 것만 못 박는다
(`test_atom_misconception_catalog.py` 가짜 엔진 패턴 재사용):

  ① `load_atom_probes_from_json` — graph.json → AtomProbeRecord 투영(②3필드·③ rename·난이도·코드)
  ② 필터 — 비-원자(단원/소단원) skip·code/name 없는 항목 skip·②③ 전부 빈 값 skip·빈 concepts
  ③ store.upsert 배선 — code ON CONFLICT(가짜 엔진으로 SQL 관찰·review_status 상수)
  ④ `populate_atom_probes` — 레코드별 upsert 위임·반환 행수·멱등 재적재
  ⑤ CLI populate — load/populate monkeypatch·파일 부재 Exit 2·정상 stdout 행수
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.db.models.atom_probe import ATOM_PROBE_REVIEW_STATUS_AI_ESTIMATED
from whymath_backend.l1.atom_probe import populate
from whymath_backend.l1.atom_probe import projection as projection_mod
from whymath_backend.l1.atom_probe.projection import (
    AtomProbeRecord,
    AtomProbeStore,
    load_atom_probes_from_json,
    populate_atom_probes,
)


# ──────────────────────────────────────────────────────────────────────────
# graph.json 픽스처 — 실 코퍼스 원자 항목 모양을 본뜬 concept dict
# ──────────────────────────────────────────────────────────────────────────
def _atom(
    code: str = "2수01-01-2",
    *,
    name: str | None = "기수 원리(마지막 수=전체 개수)",
    diagnostic_item: str | None = "'하나, 둘, 셋, 넷, 다섯'까지 세었어요. 사탕은 모두 몇 개일까요?",
    diagnostic_answer: str | None = "정답: 5개 / 통과기준: 다시 세지 않고 '5개'",
    diagnostic_signal: str | None = "다시 셈; '다섯째'와 '다섯 개' 혼동",
    socratic: str | None = "마지막에 말한 수가 '다섯'이었지? 다 합치면 몇 개일까?",
    intrinsic_difficulty: object = 1,
    school_level: str | None = "초등",
    subject_area: str | None = "수와 연산",
    subunit: str | None = "100까지의 수와 세기",
    standard_codes: list[str] | None = None,
    level: str = "세부개념",
) -> dict[str, Any]:
    """graph.json `concepts` 원자 항목 dict(실 코퍼스 row 미러)."""
    record: dict[str, Any] = {
        "code": code,
        "name": name,
        "level": level,
        "school_level": school_level,
        "subject_area": subject_area,
        "subunit": subunit,
        "diagnostic_item": diagnostic_item,
        "diagnostic_answer": diagnostic_answer,
        "diagnostic_signal": diagnostic_signal,
        "socratic": socratic,
        "intrinsic_difficulty": intrinsic_difficulty,
        "standard_codes": ["[2수01-01]"] if standard_codes is None else standard_codes,
    }
    return record


def _graph(concepts: list[dict[str, Any]]) -> dict[str, Any]:
    """graph.json Collection 객체(concepts 배열) — Phase 1 산출 형태."""
    return {"version": "atom_graph_v1", "concepts": concepts}


def _write_graph(tmp_path: Path, concepts: list[dict[str, Any]]) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_graph(concepts), ensure_ascii=False), encoding="utf-8")
    return path


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin() 컨텍스트 + execute() (test_atom_misconception_catalog 미러)
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
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 수집."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


def _compile(statement: object) -> str:
    return str(statement.compile(dialect=_pg_dialect()))  # type: ignore[attr-defined]


def _compile_params(statement: object) -> dict[str, Any]:
    return dict(statement.compile(dialect=_pg_dialect()).params)  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# ① load_atom_probes_from_json — 투영·필드 매핑
# ──────────────────────────────────────────────────────────────────────────
class TestLoadAtomProbes:
    def test_maps_atom_fields(self, tmp_path: Path) -> None:
        path = _write_graph(tmp_path, [_atom()])
        records = load_atom_probes_from_json(path)
        assert len(records) == 1
        rec = records[0]
        assert rec.code == "2수01-01-2"
        assert rec.name == "기수 원리(마지막 수=전체 개수)"
        assert rec.school_level == "초등"
        assert rec.subject_area == "수와 연산"
        assert rec.subunit == "100까지의 수와 세기"
        # ②진단문항 3필드.
        assert rec.diagnostic_item is not None and rec.diagnostic_item.startswith("'하나")
        assert rec.diagnostic_answer is not None and rec.diagnostic_answer.startswith("정답: 5개")
        assert rec.diagnostic_signal == "다시 셈; '다섯째'와 '다섯 개' 혼동"
        # ③소크라테스 — `socratic` → `socratic_question` rename.
        assert rec.socratic_question is not None and rec.socratic_question.startswith("마지막에")
        assert rec.intrinsic_difficulty == 1
        assert rec.standard_codes == ("[2수01-01]",)

    def test_socratic_renamed_only(self, tmp_path: Path) -> None:
        # `socratic` 키만 `socratic_question`으로 옮긴다(다른 rename 없음).
        rec = load_atom_probes_from_json(_write_graph(tmp_path, [_atom(socratic="질문?")]))[0]
        assert rec.socratic_question == "질문?"

    def test_standard_codes_empty_tuple(self, tmp_path: Path) -> None:
        rec = load_atom_probes_from_json(_write_graph(tmp_path, [_atom(standard_codes=[])]))[0]
        assert rec.standard_codes == ()

    def test_standard_codes_non_list_tuple(self, tmp_path: Path) -> None:
        # standard_codes가 리스트/튜플이 아니면 빈 튜플(방어).
        atom = _atom()
        atom["standard_codes"] = "단일문자열"
        rec = load_atom_probes_from_json(_write_graph(tmp_path, [atom]))[0]
        assert rec.standard_codes == ()

    def test_difficulty_string_parsed(self, tmp_path: Path) -> None:
        rec = load_atom_probes_from_json(_write_graph(tmp_path, [_atom(intrinsic_difficulty="3")]))[
            0
        ]
        assert rec.intrinsic_difficulty == 3

    def test_difficulty_none_and_nonint(self, tmp_path: Path) -> None:
        none_rec = load_atom_probes_from_json(
            _write_graph(tmp_path, [_atom(intrinsic_difficulty=None)])
        )[0]
        assert none_rec.intrinsic_difficulty is None
        bad_rec = load_atom_probes_from_json(
            _write_graph(tmp_path, [_atom(intrinsic_difficulty="상")])
        )[0]
        assert bad_rec.intrinsic_difficulty is None

    def test_difficulty_bool_and_empty(self, tmp_path: Path) -> None:
        # bool은 int 하위형이지만 난이도가 아니므로 None(명시 제외).
        bool_rec = load_atom_probes_from_json(
            _write_graph(tmp_path, [_atom(intrinsic_difficulty=True)])
        )[0]
        assert bool_rec.intrinsic_difficulty is None
        # 빈 문자열 → None(strip 후 빈 값).
        empty_rec = load_atom_probes_from_json(
            _write_graph(tmp_path, [_atom(intrinsic_difficulty="")])
        )[0]
        assert empty_rec.intrinsic_difficulty is None

    def test_partial_diagnostic_kept(self, tmp_path: Path) -> None:
        # ②③ 일부만 있어도(예: 소크라테스만) 적재 대상(전부 빈 값일 때만 skip).
        rec = load_atom_probes_from_json(
            _write_graph(
                tmp_path,
                [
                    _atom(
                        diagnostic_item=None,
                        diagnostic_answer=None,
                        diagnostic_signal=None,
                        socratic="소크라테스만",
                    )
                ],
            )
        )[0]
        assert rec.diagnostic_item is None
        assert rec.socratic_question == "소크라테스만"

    def test_university_atom(self, tmp_path: Path) -> None:
        uni = _atom(
            code="CALC1-C01",
            name="함수는 입력 하나에 출력 하나",
            school_level="대학",
            subject_area="미적분학 I",
            subunit="함수의 종류",
            standard_codes=["[CALC1-01-01]"],
            intrinsic_difficulty=4,
        )
        rec = load_atom_probes_from_json(_write_graph(tmp_path, [uni]))[0]
        assert rec.code == "CALC1-C01"
        assert rec.subject_area == "미적분학 I"
        assert rec.intrinsic_difficulty == 4
        assert rec.standard_codes == ("[CALC1-01-01]",)


# ──────────────────────────────────────────────────────────────────────────
# ② 필터 — 비-원자·code/name 없는 항목·②③ 전부 빈 값 skip·빈 concepts
# ──────────────────────────────────────────────────────────────────────────
class TestFilter:
    def test_non_atom_levels_skipped(self, tmp_path: Path) -> None:
        unit = _atom(code="초수연-U1", level="단원")
        subunit = _atom(code="초수연-U1-S1", level="소단원")
        path = _write_graph(tmp_path, [unit, subunit, _atom()])
        records = load_atom_probes_from_json(path)
        assert [r.code for r in records] == ["2수01-01-2"]  # 원자만.

    def test_missing_code_skipped(self, tmp_path: Path) -> None:
        bad = _atom()
        del bad["code"]
        path = _write_graph(tmp_path, [bad, _atom()])
        assert len(load_atom_probes_from_json(path)) == 1

    def test_missing_name_skipped(self, tmp_path: Path) -> None:
        path = _write_graph(tmp_path, [_atom(code="A1", name=None), _atom()])
        assert [r.code for r in load_atom_probes_from_json(path)] == ["2수01-01-2"]

    def test_all_probes_empty_skipped(self, tmp_path: Path) -> None:
        empty_probe = _atom(
            code="A1",
            diagnostic_item=None,
            diagnostic_answer=" ",
            diagnostic_signal="",
            socratic=None,
        )
        path = _write_graph(tmp_path, [empty_probe, _atom()])
        assert [r.code for r in load_atom_probes_from_json(path)] == ["2수01-01-2"]

    def test_empty_or_missing_concepts(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text(json.dumps({"version": "x"}), encoding="utf-8")
        assert load_atom_probes_from_json(empty) == []


# ──────────────────────────────────────────────────────────────────────────
# ③ store.upsert 배선 — code ON CONFLICT(가짜 엔진·review_status 상수)
# ──────────────────────────────────────────────────────────────────────────
class TestStoreWiring:
    def test_on_conflict_code_and_constant_review_status(self, tmp_path: Path) -> None:
        engine = _FakeEngine()
        store = AtomProbeStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진
        records = load_atom_probes_from_json(_write_graph(tmp_path, [_atom()]))
        count = populate_atom_probes(records, store=store)
        assert count == 1
        sql = _compile(engine.executed[0])
        assert "INSERT INTO atom_probe" in sql
        assert "ON CONFLICT" in sql
        assert "code" in sql
        # PK(code)는 SET하지 않는다(보존·멱등) — 나머지 컬럼만 갱신.
        set_clause = sql.split("DO UPDATE SET", 1)[1]
        assert "code = " not in set_clause  # code 자체는 갱신 대상 아님.
        assert "socratic_question" in set_clause
        assert "diagnostic_item" in set_clause
        assert "review_status" in set_clause
        assert "updated_at" in set_clause
        # review_status는 코퍼스에서 읽지 않고 상수 'ai_estimated'로 박힌다(정직 표기).
        params = _compile_params(engine.executed[0])
        assert ATOM_PROBE_REVIEW_STATUS_AI_ESTIMATED in params.values()


# ──────────────────────────────────────────────────────────────────────────
# ④ populate_atom_probes — 레코드별 upsert 위임·반환 행수·멱등
# ──────────────────────────────────────────────────────────────────────────
class _RecordingStore:
    """upsert 인자를 기록하는 fake store(populate 위임 배선 검증)."""

    def __init__(self) -> None:
        self.received: list[AtomProbeRecord] = []

    def upsert(self, record: AtomProbeRecord) -> None:
        self.received.append(record)


def test_store_uses_default_settings_when_unset() -> None:
    # settings 미주입 시 전역 Settings로 지연 해석(concept_content 선례).
    store = AtomProbeStore()
    assert isinstance(store._resolved_settings, Settings)


def test_get_engine_builds_via_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    # engine 미주입 시 슬3 `_build_sync_engine` seam으로 지연 생성·캐시(신규 seam 0).
    sentinel = object()
    monkeypatch.setattr(projection_mod, "_build_sync_engine", lambda _s: sentinel)
    store = AtomProbeStore(settings=Settings())
    assert store._get_engine() is sentinel
    assert store._get_engine() is sentinel  # 캐시 — 재빌드하지 않는다.


class TestPopulateAtomProbes:
    def test_delegates_per_record(self, tmp_path: Path) -> None:
        store = _RecordingStore()
        records = load_atom_probes_from_json(
            _write_graph(tmp_path, [_atom(code="A1"), _atom(code="A2")])
        )
        count = populate_atom_probes(records, store=store)  # type: ignore[arg-type]
        assert count == 2
        assert [r.code for r in store.received] == ["A1", "A2"]

    def test_idempotent_reload_same_count(self, tmp_path: Path) -> None:
        store = _RecordingStore()
        records = load_atom_probes_from_json(_write_graph(tmp_path, [_atom(code="A1")]))
        assert populate_atom_probes(records, store=store) == 1  # type: ignore[arg-type]
        assert populate_atom_probes(records, store=store) == 1  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# ⑤ CLI populate — load/populate monkeypatch·파일 부재 Exit 2·stdout 행수
# ──────────────────────────────────────────────────────────────────────────
class TestPopulateMain:
    def test_loads_and_reports_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        src = tmp_path / "graph.json"
        src.write_text("{}", encoding="utf-8")  # 존재 검사용(load/populate는 monkeypatch).
        calls: dict[str, object] = {}

        def _fake_load(path: Path) -> list[AtomProbeRecord]:
            calls["path"] = path
            return ["sentinel"]  # type: ignore[list-item]  # populate에 그대로 전달만.

        def _fake_populate(records: object) -> int:
            calls["records"] = records
            return 1837

        monkeypatch.setattr(populate, "load_atom_probes_from_json", _fake_load)
        monkeypatch.setattr(populate, "populate_atom_probes", _fake_populate)
        rc = populate.main(["--graph", str(src)])
        assert rc == 0
        assert calls["path"] == src
        assert calls["records"] == ["sentinel"]
        assert "1837" in capsys.readouterr().out

    def test_missing_file_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(populate, "load_atom_probes_from_json", lambda _p: [])
        monkeypatch.setattr(populate, "populate_atom_probes", lambda _r: 0)
        rc = populate.main(["--graph", str(tmp_path / "nope.json")])
        assert rc == 2

    def test_verbose_flag_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        src = tmp_path / "graph.json"
        src.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(populate, "load_atom_probes_from_json", lambda _p: [])
        monkeypatch.setattr(populate, "populate_atom_probes", lambda _r: 0)
        rc = populate.main(["--graph", str(src), "--verbose"])
        assert rc == 0
