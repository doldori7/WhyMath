"""교육과정 깊이 resolver 단위테스트 — concept_id → required_depth (hermetic·fake 엔진).

`CurriculumDepthResolver`의 read 배선·행→dict 매핑·enum 복원을 PG 없이 검증한다(crosslink_resolve
fake-엔진 패턴 재사용). is_present·country·required_depth NOT NULL·min_confidence *SQL 필터*는
실 PG 통합테스트(`test_curriculum_resolve_integration.py`) 몫이다 — fake 엔진은 WHERE를 실행하지
않고 주어진 행을 그대로 돌려주므로, 여기서는 매핑·enum 변환·빈 입력만 못 박는다.
"""

from __future__ import annotations

from types import TracebackType

from whymath_backend.l1.curriculum.curriculum_resolve import CurriculumDepthResolver
from whymath_backend.schema.enums import RequiredDepth


# ──────────────────────────────────────────────────────────────────────────
# fake sync 엔진 (resolver 주입) — crosslink_resolve 테스트 패턴 미러
# ──────────────────────────────────────────────────────────────────────────
class _Row:
    def __init__(self, concept_id: str, required_depth: object) -> None:
        self.concept_id = concept_id
        self.required_depth = required_depth


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
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

    def execute(self, statement: object, parameters: object = None) -> _FakeResult:
        self._engine.executed.append(statement)
        return _FakeResult(self._engine.rows)


class _FakeEngine:
    def __init__(self, rows: list[object] | None = None) -> None:
        self.executed: list[object] = []
        self.rows: list[object] = rows or []

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


class TestResolveDepth:
    def test_resolve_returns_enum(self) -> None:
        # PG enum이 문자열로 와도 RequiredDepth로 복원된다.
        engine = _FakeEngine(rows=[_Row("C1", "conceptual")])
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve("C1") == RequiredDepth.conceptual

    def test_resolve_accepts_enum_value_directly(self) -> None:
        # 이미 RequiredDepth 멤버로 와도 그대로 반환(이중 변환 안전).
        engine = _FakeEngine(rows=[_Row("C1", RequiredDepth.mastery)])
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve("C1") == RequiredDepth.mastery

    def test_resolve_missing_returns_none(self) -> None:
        engine = _FakeEngine(rows=[])
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve("nope") is None

    def test_resolve_many_maps_each(self) -> None:
        engine = _FakeEngine(
            rows=[_Row("A", "awareness"), _Row("B", "procedural"), _Row("C", "mastery")]
        )
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        out = resolver.resolve_many(["A", "B", "C"])
        assert out == {
            "A": RequiredDepth.awareness,
            "B": RequiredDepth.procedural,
            "C": RequiredDepth.mastery,
        }

    def test_resolve_many_empty_input(self) -> None:
        engine = _FakeEngine()
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve_many([]) == {}
        assert engine.executed == []  # 빈 입력은 쿼리 생략

    def test_resolve_many_dedups_input(self) -> None:
        # 입력 중복은 방어적으로 dedup(쿼리 IN 절·결과는 같음).
        engine = _FakeEngine(rows=[_Row("A", "conceptual")])
        resolver = CurriculumDepthResolver(engine=engine)  # type: ignore[arg-type]
        out = resolver.resolve_many(["A", "A"])
        assert out == {"A": RequiredDepth.conceptual}
