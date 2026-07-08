"""문제유형 메타 PG 프로젝션 적재 *단위테스트* — Phase 3 (hermetic·PG 불요).

`ProblemTypeNodeStore`의 실 라운드트립은 통합테스트로 미루고, 여기서는 PG 없이 검증 가능한 것만
못 박는다(`test_skill_node_projection.py` 가짜 엔진 패턴 미러):

  ① graph.json 로딩 — problem_type_id 키 + 안전 메타(behavior_skills/standard 튜플)
  ② 필수 필드 누락/빈 skills graceful — 필수 누락·behavior_skills 빈 배열이면 skip
  ③ upsert SQL 구성 — ON CONFLICT(problem_type_id)·review_status 상수·안전 메타 컬럼(enum 없음)
  ④ populate — 전 레코드 upsert(횟수=레코드 수)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from whymath_backend.config import Settings
from whymath_backend.db.models.problem_type_node import PROBLEM_TYPE_REVIEW_STATUS_DEFAULT
from whymath_backend.l1.problem_type_graph.problem_type_node_projection import (
    ProblemTypeNodeRecord,
    ProblemTypeNodeStore,
    load_problem_types_from_graph_json,
    populate_problem_type_nodes,
)


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


def _fake_store() -> tuple[ProblemTypeNodeStore, _FakeEngine]:
    engine = _FakeEngine()
    store = ProblemTypeNodeStore(engine=engine)  # type: ignore[arg-type]
    return store, engine


def _write_graph(tmp_path: Path, problem_types: list[dict[str, object]]) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps({"problem_types": problem_types}, ensure_ascii=False), encoding="utf-8"
    )
    return path


def _record(problem_type_id: str = "ptype.optimize-extremum") -> ProblemTypeNodeRecord:
    return ProblemTypeNodeRecord(
        problem_type_id=problem_type_id,
        name_ko="최대·최소 구하기",
        family="최적화",
        behavior_skills=("skill.graph-sketching", "skill.completing-square"),
        mastery_estimable=True,
        description="함수의 최댓값·최솟값을 구한다",
        standard_codes=(),
    )


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))  # type: ignore[attr-defined]


class TestLoadFromGraphJson:
    def test_loads_safe_meta(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "problem_type_id": "ptype.optimize-extremum",
                    "name_ko": "최대·최소 구하기",
                    "family": "최적화",
                    "behavior_skills": ["skill.graph-sketching", "skill.completing-square"],
                    "mastery_estimable": True,
                    "description": "함수의 최댓값·최솟값",
                    "standard_codes": ["2수03-01"],
                }
            ],
        )
        rec = load_problem_types_from_graph_json(path)[0]
        assert rec.problem_type_id == "ptype.optimize-extremum"
        assert rec.family == "최적화"
        assert rec.behavior_skills == ("skill.graph-sketching", "skill.completing-square")
        assert rec.standard_codes == ("2수03-01",)

    def test_missing_required_skipped(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "problem_type_id": "ptype.ok",
                    "name_ko": "x",
                    "family": "F",
                    "behavior_skills": ["skill.a"],
                },
                {
                    "problem_type_id": "ptype.no-family",
                    "name_ko": "x",
                    "behavior_skills": ["skill.a"],
                },
            ],
        )
        loaded = load_problem_types_from_graph_json(path)
        assert [r.problem_type_id for r in loaded] == ["ptype.ok"]

    def test_empty_behavior_skills_skipped(self, tmp_path: Path) -> None:
        """behavior_skills 빈 배열 → skip(cognitive-action 표현 부재 행 차단)."""
        path = _write_graph(
            tmp_path,
            [
                {
                    "problem_type_id": "ptype.empty",
                    "name_ko": "x",
                    "family": "F",
                    "behavior_skills": [],
                }
            ],
        )
        assert load_problem_types_from_graph_json(path) == []

    def test_mastery_estimable_defaults_true(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "problem_type_id": "ptype.x",
                    "name_ko": "x",
                    "family": "F",
                    "behavior_skills": ["skill.a"],
                }
            ],
        )
        assert load_problem_types_from_graph_json(path)[0].mastery_estimable is True


class TestUpsertSql:
    def test_upsert_on_conflict_problem_type_id(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO problem_type_node" in compiled
        assert "ON CONFLICT" in compiled
        assert "(problem_type_id)" in compiled or "problem_type_node.problem_type_id" in compiled

    def test_upsert_includes_safe_meta_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in (
            "problem_type_id",
            "name_ko",
            "family",
            "behavior_skills",
            "mastery_estimable",
            "review_status",
        ):
            assert col in compiled

    def test_upsert_review_status_constant(self) -> None:
        assert PROBLEM_TYPE_REVIEW_STATUS_DEFAULT == "ai_estimated"

    def test_upsert_omits_surface_and_body_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for forbidden in ("signature_pattern", "misconception_text", "formal_definition", "prompt"):
            assert forbidden not in compiled


class TestPopulate:
    def test_populate_upserts_each_and_counts(self) -> None:
        store, engine = _fake_store()
        n = populate_problem_type_nodes(
            [_record("ptype.a"), _record("ptype.b")], store=store, settings=Settings()
        )
        assert n == 2
        assert len(engine.executed) == 2

    def test_record_has_no_surface_or_body_slots(self) -> None:
        fields = set(ProblemTypeNodeRecord.__dataclass_fields__)
        for forbidden in ("signature_pattern", "misconception_text", "formal_definition", "prompt"):
            assert forbidden not in fields
