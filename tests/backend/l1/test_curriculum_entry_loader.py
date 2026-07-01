"""교육과정 Overlay 적재 *단위테스트* — graph.json → curriculum_entry KR 셀 (hermetic·PG 불요).

CI hermetic 잡엔 PostgreSQL이 없으므로 `CurriculumEntryStore`/`populate_kr_curriculum_entries`의
*실 라운드트립*은 통합테스트(`test_curriculum_entry_loader_integration.py`·실 PG 게이트)로 미룬다.
여기서는 PG 없이 검증 가능한 것만 못 박는다(backend_concept `test_concept_backend_load.py` 가짜
엔진 패턴 재사용):

  ① graph.json 로딩 — concept_id→KR 셀 매핑(domain→domain_label·grade_band_hint→grade_band/
     introduced_grade·standard_codes→national_standard_codes·review_status→confidence)·KR 상수·
     entry_id 형식·concept_id 누락 graceful skip
  ② upsert SQL 구성 — ON CONFLICT(entry_id) upsert·created_at는 SET에서 제외(보존)·updated_at은
     SET에 포함(갱신)
  ③ populate — 전 셀 upsert(횟수=dedup 후 수)·입력 내 entry_id 중복 dedup
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

from whymath_backend.l1.curriculum.curriculum_loader import (
    CurriculumEntryStore,
    load_kr_curriculum_entries_from_graph_json,
    populate_kr_curriculum_entries,
)

# 결정적 created_at/updated_at(테스트 주입 — schema required datetime).
_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin() 컨텍스트 + execute() (PG 없이 배선 관찰·backend_concept 미러)
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


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 기록(upsert는 결과 미사용)."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store() -> tuple[CurriculumEntryStore, _FakeEngine]:
    """가짜 엔진을 주입한 CurriculumEntryStore + 엔진(검사용) 페어."""
    engine = _FakeEngine()
    store = CurriculumEntryStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    return store, engine


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# ① graph.json 로딩 — concept_id→KR 셀 매핑·KR 상수·graceful skip
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_maps_kr_fields_and_constants(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": "HIGH-CALC-001",
                    "name_ko": "극한",
                    "domain": "극한과 연속",
                    "grade_band_hint": "고등학교",
                    "standard_codes": ["[12미적01-01]"],
                    "prerequisite_concept_ids": ["HIGH-CALC-000"],
                    "review_status": "reviewed",
                }
            ],
        )
        entries = load_kr_curriculum_entries_from_graph_json(path, now=_NOW)
        assert len(entries) == 1
        e = entries[0]
        # 식별 — 복합키 + 결정적 entry_id
        assert e.concept_id == "HIGH-CALC-001"
        assert e.country_code == "KR"
        assert e.entry_id == "HIGH-CALC-001:KR"
        # 매핑
        assert e.domain_label == "극한과 연속"
        assert e.grade_band == "고등학교"
        assert e.introduced_grade == 10  # 고등학교 = KR 1~12 번호 하한 10
        assert e.national_standard_codes == ["[12미적01-01]"]
        assert e.prerequisite_concept_ids == ["HIGH-CALC-000"]
        assert e.confidence == 0.9  # reviewed
        # KR 상수
        assert e.license_id == "KR-NCIC"  # use_enum_values → 하이픈 값
        assert e.curriculum_revision == "2022 개정"
        assert e.is_present is True
        assert e.source_url and e.source_url.startswith("https://www.ncic.go.kr")
        assert e.created_at == _NOW
        assert e.updated_at == _NOW
        # 깊이 — grade_band 학년진행 휴리스틱(고등학교 → mastery·use_enum_values 문자열)
        assert e.required_depth == "mastery"
        # 미매핑(소스에 신호 없음 → 기본/None)
        assert e.is_assessed is None

    def test_introduced_grade_band_lower_bounds(self, tmp_path: Path) -> None:
        bands = {
            "초등학교 1~2학년군": 1,
            "초등학교 3~4학년군": 3,
            "초등학교 5~6학년군": 5,
            "중학교 1~3학년군": 7,
            "고등학교": 10,
        }
        concepts = [
            {
                "concept_id": f"C-{i}",
                "name_ko": "x",
                "domain": "d",
                "grade_band_hint": band,
                "standard_codes": [],
                "review_status": "pending",
            }
            for i, band in enumerate(bands)
        ]
        # grade_band 학년진행 → required_depth 휴리스틱(use_enum_values 문자열).
        expected_depth = {
            "초등학교 1~2학년군": "awareness",
            "초등학교 3~4학년군": "procedural",
            "초등학교 5~6학년군": "procedural",
            "중학교 1~3학년군": "conceptual",
            "고등학교": "mastery",
        }
        path = self._write_graph(tmp_path, concepts)  # type: ignore[arg-type]
        loaded = load_kr_curriculum_entries_from_graph_json(path, now=_NOW)
        by_code = {e.concept_id: e for e in loaded}
        for i, (band, grade) in enumerate(bands.items()):
            assert by_code[f"C-{i}"].introduced_grade == grade
            assert by_code[f"C-{i}"].grade_band == band
            assert by_code[f"C-{i}"].required_depth == expected_depth[band]

    def test_unknown_grade_band_introduced_grade_none(self, tmp_path: Path) -> None:
        # 매핑에 없는 밴드 → introduced_grade None(추정 안 함·정직). grade_band는 원문 보존.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": "C1",
                    "name_ko": "x",
                    "domain": "d",
                    "grade_band_hint": "대학교",
                    "standard_codes": [],
                    "review_status": "reviewed",
                }
            ],
        )
        e = load_kr_curriculum_entries_from_graph_json(path, now=_NOW)[0]
        assert e.grade_band == "대학교"
        assert e.introduced_grade is None
        assert e.required_depth is None  # 미지 밴드 → 깊이 휴리스틱도 None(정직 폴백)

    def test_pending_review_lower_confidence(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": "C1",
                    "name_ko": "x",
                    "domain": "d",
                    "grade_band_hint": "고등학교",
                    "standard_codes": [],
                    "review_status": "pending",
                }
            ],
        )
        e = load_kr_curriculum_entries_from_graph_json(path, now=_NOW)[0]
        assert e.confidence == 0.6  # 비-reviewed → 보수적

    def test_skips_when_concept_id_missing(self, tmp_path: Path) -> None:
        # concept_id 누락 → 건너뜀(복합키 구성 불가·조용한 빈 적재 금지).
        path = self._write_graph(
            tmp_path,
            [{"name_ko": "키 없음", "domain": "d", "grade_band_hint": "고등학교"}],
        )
        assert load_kr_curriculum_entries_from_graph_json(path, now=_NOW) == []


# ──────────────────────────────────────────────────────────────────────────
# ② upsert SQL 구성 — ON CONFLICT(entry_id)·created_at 보존·updated_at 갱신
# ──────────────────────────────────────────────────────────────────────────
def _entry(tmp_path: Path, concept_id: str = "C1") -> object:
    path = tmp_path / "g.json"
    path.write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": concept_id,
                        "name_ko": "x",
                        "domain": "d",
                        "grade_band_hint": "고등학교",
                        "standard_codes": ["[x]"],
                        "review_status": "reviewed",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return load_kr_curriculum_entries_from_graph_json(path, now=_NOW)[0]


class TestUpsertSql:
    def test_on_conflict_entry_id(self, tmp_path: Path) -> None:
        store, engine = _fake_store()
        store.populate([_entry(tmp_path)])  # type: ignore[list-item]
        compiled = _compile(engine.executed[0])
        assert "ON CONFLICT" in compiled
        assert "entry_id" in compiled

    def test_created_at_preserved_updated_at_set(self, tmp_path: Path) -> None:
        store, engine = _fake_store()
        store.populate([_entry(tmp_path)])  # type: ignore[list-item]
        compiled = _compile(engine.executed[0])
        set_clause = compiled.split("DO UPDATE SET", 1)[1]
        # created_at은 SET 절에 없어야(보존), updated_at은 있어야(갱신).
        assert "created_at" not in set_clause
        assert "updated_at" in set_clause


# ──────────────────────────────────────────────────────────────────────────
# ③ populate — 전 셀 upsert·dedup
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each(self, tmp_path: Path) -> None:
        store, engine = _fake_store()
        entries = [_entry(tmp_path, "C1"), _entry(tmp_path, "C2")]
        count = populate_kr_curriculum_entries(entries, store=store)  # type: ignore[arg-type]
        assert count == 2
        assert len(engine.executed) == 2

    def test_populate_empty_is_noop(self, tmp_path: Path) -> None:
        store, engine = _fake_store()
        assert populate_kr_curriculum_entries([], store=store) == 0
        assert engine.executed == []

    def test_dedups_duplicate_entry_id_last_wins(self, tmp_path: Path) -> None:
        # 같은 concept_id → 같은 entry_id → 단일 배치 dedup(마지막 우선·중복행 오류 방지).
        store, engine = _fake_store()
        entries = [_entry(tmp_path, "C1"), _entry(tmp_path, "C1")]
        count = populate_kr_curriculum_entries(entries, store=store)  # type: ignore[arg-type]
        assert count == 1
        assert len(engine.executed) == 1
