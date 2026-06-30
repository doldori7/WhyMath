"""오개념 crosswalk(kebab-id ↔ M-id) 골격 단위테스트 — hermetic(PG 불요).

스키마 검증·로더 멱등 upsert·read-time resolver를 fake sync 엔진 주입으로 PG 없이 검증한다
(test_populate.py·test_misconception_loader.py 패턴). 실 PG 왕복은 후속 통합테스트 몫.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import pytest
from pydantic import ValidationError

from whymath_backend.l1.misconception.crosslink_loader import (
    MisconceptionCrosslinkStore,
    load_crosslinks,
)
from whymath_backend.l1.misconception.crosslink_resolve import MisconceptionCrosslinkResolver
from whymath_backend.schema.misconception_crosslink import MisconceptionCrosslink


# ──────────────────────────────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────────────────────────────
class TestSchema:
    def test_full_roundtrip(self) -> None:
        cl = MisconceptionCrosslink(
            kebab_id="distribution-over-power",
            mis_id="M0425",
            link_type="직접매핑",
            confidence=0.82,
            method="manual",
            note="검수: 동일 오개념",
        )
        assert cl.kebab_id == "distribution-over-power"
        assert cl.mis_id == "M0425"
        assert cl.model_dump()["link_type"] == "직접매핑"

    def test_defaults(self) -> None:
        cl = MisconceptionCrosslink(kebab_id="k", mis_id="M1", link_type="부분매핑")
        assert cl.confidence is None
        assert cl.method == "manual"
        assert cl.note is None

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MisconceptionCrosslink(  # type: ignore[call-arg]
                kebab_id="k", mis_id="M1", link_type="직접매핑", bogus="x"
            )

    def test_bad_link_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MisconceptionCrosslink(kebab_id="k", mis_id="M1", link_type="없는유형")  # type: ignore[arg-type]

    def test_confidence_range(self) -> None:
        with pytest.raises(ValidationError):
            MisconceptionCrosslink(kebab_id="k", mis_id="M1", link_type="직접매핑", confidence=1.5)


# ──────────────────────────────────────────────────────────────────────
# fake sync 엔진 (store/resolver 주입)
# ──────────────────────────────────────────────────────────────────────
class _Row:
    def __init__(self, kebab_id: str, mis_id: str, confidence: float | None) -> None:
        self.kebab_id = kebab_id
        self.mis_id = mis_id
        self.confidence = confidence


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

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


# ──────────────────────────────────────────────────────────────────────
# 로더
# ──────────────────────────────────────────────────────────────────────
class TestLoader:
    def test_empty_returns_zero(self) -> None:
        assert load_crosslinks(None, {"crosslinks": []}) == 0

    def test_populate_upserts_each(self) -> None:
        engine = _FakeEngine()
        store = MisconceptionCrosslinkStore(engine=engine)  # type: ignore[arg-type]
        n = load_crosslinks(
            None,
            {
                "crosslinks": [
                    {"kebab_id": "k1", "mis_id": "M1", "link_type": "직접매핑", "confidence": 0.9},
                    {"kebab_id": "k2", "mis_id": "M2", "link_type": "부분매핑"},
                ]
            },
            store=store,
        )
        assert n == 2
        assert len(engine.executed) == 2  # 행마다 upsert 1회

    def test_dedup_last_wins_on_unique_key(self) -> None:
        engine = _FakeEngine()
        store = MisconceptionCrosslinkStore(engine=engine)  # type: ignore[arg-type]
        # 같은 (kebab, mis, link_type) 트리플 2건 → 1건으로 dedup(마지막 우선).
        n = load_crosslinks(
            None,
            {
                "crosslinks": [
                    {"kebab_id": "k", "mis_id": "M1", "link_type": "직접매핑", "confidence": 0.5},
                    {"kebab_id": "k", "mis_id": "M1", "link_type": "직접매핑", "confidence": 0.9},
                ]
            },
            store=store,
        )
        assert n == 1
        assert len(engine.executed) == 1

    def test_path_missing_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_crosslinks(None, Path("/nonexistent/crosslink.json"))

    def test_bad_input_type_raises(self) -> None:
        with pytest.raises(TypeError):
            load_crosslinks(None, 123)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# read-time resolver
# ──────────────────────────────────────────────────────────────────────
class TestResolver:
    def test_resolve_returns_mids(self) -> None:
        engine = _FakeEngine(rows=[_Row("k", "M2", 0.7), _Row("k", "M1", 0.9)])
        resolver = MisconceptionCrosslinkResolver(engine=engine)  # type: ignore[arg-type]
        # confidence 내림차순 → M1(0.9) 먼저, M2(0.7).
        assert resolver.resolve("k") == ["M1", "M2"]

    def test_resolve_missing_returns_empty(self) -> None:
        engine = _FakeEngine(rows=[])
        resolver = MisconceptionCrosslinkResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve("nope") == []

    def test_resolve_many_groups_by_kebab(self) -> None:
        engine = _FakeEngine(
            rows=[_Row("a", "M1", 0.9), _Row("b", "M2", 0.8), _Row("a", "M3", 0.5)]
        )
        resolver = MisconceptionCrosslinkResolver(engine=engine)  # type: ignore[arg-type]
        out = resolver.resolve_many(["a", "b"])
        assert out["a"] == ["M1", "M3"]  # confidence 내림차순
        assert out["b"] == ["M2"]

    def test_resolve_many_empty_input(self) -> None:
        engine = _FakeEngine()
        resolver = MisconceptionCrosslinkResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve_many([]) == {}

    def test_null_confidence_sorts_last(self) -> None:
        engine = _FakeEngine(rows=[_Row("k", "M_null", None), _Row("k", "M_hi", 0.6)])
        resolver = MisconceptionCrosslinkResolver(engine=engine)  # type: ignore[arg-type]
        assert resolver.resolve("k") == ["M_hi", "M_null"]  # 값 있는 것 먼저, NULL 마지막
