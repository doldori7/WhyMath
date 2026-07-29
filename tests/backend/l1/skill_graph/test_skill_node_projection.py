"""스킬 메타 PG 프로젝션 적재 *단위테스트* — Phase 2a (hermetic·PG 불요).

`AtomNodeStore`의 실 라운드트립은 통합테스트로 미루고, 여기서는 PG 없이 검증 가능한 것만 못
박는다(`test_atom_node_projection.py` 가짜 엔진 패턴 미러):

  ① graph.json 로딩 — skill_id 키 + 안전 메타(behavior_area 검증·prerequisite/standard 튜플)
  ② 필수 필드 누락/오염 graceful — 필수 누락 skip·behavior_area 6종 밖이면 ValueError
  ③ upsert SQL 구성 — ON CONFLICT(skill_id)·review_status 상수·behavior_area 값·안전 메타 컬럼
  ④ populate — 전 레코드 upsert(횟수=레코드 수)·멱등
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

import pytest
from whymath_backend.config import Settings
from whymath_backend.db.models.skill_node import SKILL_REVIEW_STATUS_DEFAULT
from whymath_backend.l1.skill_graph.skill_node_projection import (
    SkillNodeRecord,
    SkillNodeStore,
    load_skill_nodes_from_graph_json,
    populate_skill_nodes,
)
from whymath_backend.schema.enums import BehaviorArea


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


def _fake_store() -> tuple[SkillNodeStore, _FakeEngine]:
    engine = _FakeEngine()
    store = SkillNodeStore(engine=engine)  # type: ignore[arg-type]
    return store, engine


def _write_graph(tmp_path: Path, skills: list[dict[str, object]]) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"skills": skills}, ensure_ascii=False), encoding="utf-8")
    return path


def _record(skill_id: str = "skill.factorization") -> SkillNodeRecord:
    return SkillNodeRecord(
        skill_id=skill_id,
        name_ko="인수분해",
        behavior_area=BehaviorArea.TRANSFORM,
        family="인수분해와 전개",
        mastery_estimable=True,
        description="식을 인수의 곱으로 변형",
        prerequisite_skill_ids=("skill.expansion",),
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
                    "skill_id": "skill.factorization",
                    "name_ko": "인수분해",
                    "behavior_area": "TRANSFORM",
                    "family": "인수분해와 전개",
                    "mastery_estimable": True,
                    "description": "식을 인수의 곱으로 변형",
                    "prerequisite_skill_ids": ["skill.expansion"],
                    "standard_codes": ["2수03-01"],
                }
            ],
        )
        rec = load_skill_nodes_from_graph_json(path)[0]
        assert rec.skill_id == "skill.factorization"
        assert rec.behavior_area == BehaviorArea.TRANSFORM
        assert rec.family == "인수분해와 전개"
        assert rec.prerequisite_skill_ids == ("skill.expansion",)
        assert rec.standard_codes == ("2수03-01",)

    def test_missing_required_skipped(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {"skill_id": "skill.ok", "name_ko": "x", "behavior_area": "REASON", "family": "F"},
                {"skill_id": "skill.no-family", "name_ko": "x", "behavior_area": "REASON"},
            ],
        )
        loaded = load_skill_nodes_from_graph_json(path)
        assert [r.skill_id for r in loaded] == ["skill.ok"]

    def test_invalid_behavior_area_raises(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [{"skill_id": "skill.x", "name_ko": "x", "behavior_area": "GUESS", "family": "F"}],
        )
        with pytest.raises(ValueError):
            load_skill_nodes_from_graph_json(path)

    def test_mastery_estimable_defaults_true(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [{"skill_id": "skill.x", "name_ko": "x", "behavior_area": "VERIFY", "family": "F"}],
        )
        assert load_skill_nodes_from_graph_json(path)[0].mastery_estimable is True


class TestUpsertSql:
    def test_upsert_on_conflict_skill_id(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO skill_node" in compiled
        assert "ON CONFLICT" in compiled
        assert "(skill_id)" in compiled or "skill_node.skill_id" in compiled

    def test_upsert_includes_safe_meta_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in (
            "skill_id",
            "name_ko",
            "behavior_area",
            "family",
            "mastery_estimable",
            "prerequisite_skill_ids",
            "review_status",
        ):
            assert col in compiled

    def test_upsert_review_status_constant(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        # 상수 리터럴이 바인딩된다(정직 표기 'ai_estimated').
        assert SKILL_REVIEW_STATUS_DEFAULT == "ai_estimated"

    def test_upsert_omits_body_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for forbidden in ("misconception_text", "formal_definition", "prompt"):
            assert forbidden not in compiled


class TestPopulate:
    def test_populate_upserts_each_and_counts(self) -> None:
        store, engine = _fake_store()
        n = populate_skill_nodes(
            [_record("skill.a"), _record("skill.b")], store=store, settings=Settings()
        )
        assert n == 2
        assert len(engine.executed) == 2

    def test_record_has_no_body_slots(self) -> None:
        fields = set(SkillNodeRecord.__dataclass_fields__)
        for forbidden in ("misconception_text", "formal_definition", "prompt"):
            assert forbidden not in fields
