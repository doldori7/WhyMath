"""교수법 팩 YAML → backend 적재 *단위테스트* — PED-01 후속 시더 (hermetic·PG 불요).

CI hermetic 잡엔 PostgreSQL이 없으므로 `PedagogyPackStore`의 *실 라운드트립*은 통합테스트(실 PG
게이트)로 미룬다. 여기서는 PG 없이 검증 가능한 것만 못 박는다(`test_standard_loader.py` 가짜 엔진
패턴 재사용):

  ① 실 코퍼스 파싱·검증 — `data/corpus/pedagogy_packs_v1/*.yaml` 7팩·k_type 전종·stub 분포
  ② 멱등 upsert SQL — ON CONFLICT(k_type) DO UPDATE·k_type은 SET에서 제외(PK 보존)
  ③ 입력 dedup(마지막 우선) + 멱등(2회 populate → 동일 statement)
  ④ schema-lint 음성 — {domain_example} 누락·주제 명사·미정의 forbidden_mode·빈 required_slots 거부
  ⑤ model_dump JSON-native — required_slots=list[{type,count}]·k_type=문자열

가짜 엔진(`_FakeEngine`)은 begin() 컨텍스트 + execute()를 흉내내 실행 statement를 수집한다 —
psycopg/PG 없이 배선·멱등 키·dedup를 검증한다(성취기준 로더와 달리 해석 SELECT가 없어 더 단순).
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
from pydantic import ValidationError

from whymath_backend.config import Settings
from whymath_backend.l1.pedagogy.pack_loader import (
    PedagogyPackStore,
    _as_collection,
    load_packs,
)
from whymath_backend.schema.enums import KnowledgeType
from whymath_backend.schema.pedagogy_pack import PedagogyPack

# 7 지식유형 전종(schema/enums.py KnowledgeType). full 3 + stub 4의 정본 기대치.
_ALL_K_TYPES = {
    "CONCEPT",
    "PROCEDURE",
    "REPRESENT",
    "PROOF",
    "MODELING",
    "SPATIAL",
    "STOCHASTIC",
}
_FULL_K_TYPES = {"CONCEPT", "PROCEDURE", "REPRESENT"}  # is_stub=false
_STUB_K_TYPES = {"PROOF", "MODELING", "SPATIAL", "STOCHASTIC"}  # is_stub=true

# 유효 발문 — {domain_example} 자리표시자 포함·주제 명사 없음(양성 케이스).
_VALID_PROMPT = "학생이 {domain_example}의 정의를 스스로 구성하도록 이끈다."


# ──────────────────────────────────────────────────────────────────────────
# raw 팩 dict 픽스처 (인라인 합성 — 유효 팩 1건)
# ──────────────────────────────────────────────────────────────────────────
def _pack_dict(
    k_type: str = "CONCEPT",
    *,
    socratic_prompt: str = _VALID_PROMPT,
    is_stub: bool = False,
    forbidden_modes: tuple[str, ...] = ("WORKED_EXAMPLE_FIRST",),
    required_slots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """유효 raw 팩 dict — schema.PedagogyPack이 검증하는 형태(테스트 오버라이드 가능)."""
    slots = (
        required_slots
        if required_slots is not None
        else [{"type": "example_pair", "count": 4}, {"type": "diag_item", "count": 2}]
    )
    return {
        "k_type": k_type,
        "pack_version": 1,
        "api_version": "1.0",
        "is_stub": is_stub,
        "socratic_prompt": socratic_prompt,
        "fading_schedule": None,
        "forbidden_modes": list(forbidden_modes),
        "required_slots": slots,
        "default_evidence": {"kind": "COUNTEREXAMPLE_GEN", "judge": "claude", "rubric_axes": 3},
    }


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


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 수집(해석 SELECT 없음)."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


def _compile(statement: object) -> str:
    return str(statement.compile(dialect=_pg_dialect()))  # type: ignore[attr-defined]


def _params(statement: object) -> dict[str, Any]:
    return dict(statement.compile(dialect=_pg_dialect()).params)  # type: ignore[attr-defined]


def _pack_store() -> tuple[PedagogyPackStore, _FakeEngine]:
    engine = _FakeEngine()
    store = PedagogyPackStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    return store, engine


def _real_corpus_dir() -> Path:
    """실 코퍼스 디렉터리 — 이 슬라이스가 시딩하는 `data/corpus/pedagogy_packs_v1/`."""
    return Path(__file__).resolve().parents[3] / "data" / "corpus" / "pedagogy_packs_v1"


# ──────────────────────────────────────────────────────────────────────────
# ① 실 코퍼스 파싱·검증 — 7팩·k_type 전종·stub 분포
# ──────────────────────────────────────────────────────────────────────────
class TestShippedCorpus:
    def test_seven_packs_parse_and_validate(self) -> None:
        # 이 슬라이스가 시딩하는 7 YAML을 실 디렉터리에서 로드해 전부 검증한다.
        corpus_dir = _real_corpus_dir()
        assert corpus_dir.is_dir(), f"시딩 코퍼스 부재: {corpus_dir}(이 슬라이스 산출물)"
        raw_packs = _as_collection(corpus_dir)
        packs = [PedagogyPack.model_validate(raw) for raw in raw_packs]
        assert len(packs) == 7  # 7 지식유형 팩

    def test_all_seven_k_types_present(self) -> None:
        packs = [PedagogyPack.model_validate(raw) for raw in _as_collection(_real_corpus_dir())]
        # use_enum_values=True라 p.k_type은 문자열 값이다.
        assert {p.k_type for p in packs} == _ALL_K_TYPES
        # KnowledgeType enum 전종과도 일치(누락·오타 방지).
        assert {p.k_type for p in packs} == {m.value for m in KnowledgeType}

    def test_stub_distribution_three_full_four_stub(self) -> None:
        packs = [PedagogyPack.model_validate(raw) for raw in _as_collection(_real_corpus_dir())]
        full = {p.k_type for p in packs if not p.is_stub}
        stub = {p.k_type for p in packs if p.is_stub}
        assert full == _FULL_K_TYPES  # 3 full
        assert stub == _STUB_K_TYPES  # 4 stub
        assert len(full) == 3 and len(stub) == 4

    def test_provenance_file_not_globbed_as_pack(self) -> None:
        # `_provenance.json`은 .yaml이 아니라 glob에서 제외 — 정확히 7 팩만 잡힌다.
        raw_packs = _as_collection(_real_corpus_dir())
        assert len(raw_packs) == 7


# ──────────────────────────────────────────────────────────────────────────
# ② 멱등 upsert SQL — ON CONFLICT(k_type)·k_type SET 제외
# ──────────────────────────────────────────────────────────────────────────
class TestPackUpsert:
    def test_on_conflict_k_type_pk(self) -> None:
        store, engine = _pack_store()
        count = load_packs(None, [_pack_dict()], store=store)
        assert count == 1
        assert len(engine.executed) == 1  # 팩당 1 upsert
        sql = _compile(engine.executed[0])
        assert "INSERT INTO pedagogy_pack" in sql
        assert "ON CONFLICT" in sql
        # 충돌 키는 k_type(PK).
        assert "k_type" in sql

    def test_does_not_set_k_type_on_conflict(self) -> None:
        # 멱등 보존: ON CONFLICT DO UPDATE SET이 k_type(PK)를 *대입하지 않는다*.
        store, engine = _pack_store()
        load_packs(None, [_pack_dict()], store=store)
        sql = _compile(engine.executed[0])
        assert "DO UPDATE SET" in sql
        after_set = sql.split("DO UPDATE SET", 1)[1]
        set_clause = after_set.split("RETURNING", 1)[0]
        assert "k_type" not in set_clause
        # SET은 나머지 컬럼(socratic_prompt·required_slots 등)을 갱신한다.
        assert "socratic_prompt" in set_clause
        assert "required_slots" in set_clause

    def test_k_type_bound_as_string_value(self) -> None:
        # use_enum_values=True라 k_type 바인딩 값은 문자열("CONCEPT")이다(enum 멤버 아님).
        store, engine = _pack_store()
        load_packs(None, [_pack_dict(k_type="PROCEDURE")], store=store)
        params = _params(engine.executed[0])
        assert params["k_type"] == "PROCEDURE"
        assert type(params["k_type"]) is str


# ──────────────────────────────────────────────────────────────────────────
# ③ 입력 dedup(마지막 우선) + 멱등(2회 populate → 동일 statement)
# ──────────────────────────────────────────────────────────────────────────
class TestDedupAndIdempotency:
    def test_input_dedup_last_wins_on_k_type(self) -> None:
        # 입력 내 같은 k_type 중복 → 마지막 우선 dedup(단일 배치 ON CONFLICT 중복행 오류 방지).
        store, engine = _pack_store()
        count = load_packs(
            None,
            [
                _pack_dict(socratic_prompt="{domain_example} 정의 A"),
                _pack_dict(socratic_prompt="{domain_example} 정의 B"),
            ],
            store=store,
        )
        assert count == 1  # dedup → 1행
        assert len(engine.executed) == 1
        params = _params(engine.executed[0])
        assert params["socratic_prompt"] == "{domain_example} 정의 B"  # 마지막 우선

    def test_idempotent_same_statements(self) -> None:
        # 같은 팩 2회 load → 동일 upsert(ON CONFLICT) statement(멱등 — 실 행 1개로 통합).
        store, engine = _pack_store()
        packs = [_pack_dict()]
        load_packs(None, packs, store=store)
        load_packs(None, packs, store=store)
        inserts = [s for s in engine.executed if "INSERT INTO pedagogy_pack" in _compile(s)]
        assert len(inserts) == 2
        assert _compile(inserts[0]) == _compile(inserts[1])  # 동일 statement
        for stmt in inserts:
            assert "ON CONFLICT" in _compile(stmt)

    def test_empty_input_is_noop(self) -> None:
        store, engine = _pack_store()
        assert load_packs(None, [], store=store) == 0
        assert engine.executed == []


# ──────────────────────────────────────────────────────────────────────────
# ④ schema-lint 음성 — 오염 팩을 검증 단계에서 거부
# ──────────────────────────────────────────────────────────────────────────
class TestSchemaLintNegatives:
    def test_missing_domain_example_placeholder_raises(self) -> None:
        # (a) {domain_example} 자리표시자 누락 → 거부.
        with pytest.raises(ValidationError, match="자리표시자"):
            PedagogyPack.model_validate(_pack_dict(socratic_prompt="자리표시자 없는 발문이다."))

    def test_subject_noun_in_prompt_raises(self) -> None:
        # (b) 발문에 주제 명사(이차함수)가 새어 들면 거부(유형 불변 위배).
        with pytest.raises(ValidationError, match="주제 명사"):
            PedagogyPack.model_validate(
                _pack_dict(socratic_prompt="학생이 {domain_example} 이차함수를 살펴본다.")
            )

    def test_forbidden_mode_outside_vocab_raises(self) -> None:
        # (c) FORBIDDEN_MODE_VOCAB에 없는 forbidden_modes 항목 → 거부.
        with pytest.raises(ValidationError, match="미정의 모드"):
            PedagogyPack.model_validate(_pack_dict(forbidden_modes=("NOT_A_REAL_MODE",)))

    def test_empty_required_slots_raises(self) -> None:
        # (d) required_slots 비어 있으면 거부.
        with pytest.raises(ValidationError, match="required_slots가 비었"):
            PedagogyPack.model_validate(_pack_dict(required_slots=[]))

    def test_extra_field_forbidden(self) -> None:
        # extra=forbid — YAML 오타 키 차단.
        bad = _pack_dict()
        bad["oops_typo_key"] = 1
        with pytest.raises(ValidationError):
            PedagogyPack.model_validate(bad)


# ──────────────────────────────────────────────────────────────────────────
# ⑤ model_dump JSON-native — required_slots=list[{type,count}]·k_type=문자열
# ──────────────────────────────────────────────────────────────────────────
class TestModelDumpJsonNative:
    def test_k_type_dumps_as_plain_string(self) -> None:
        dumped = PedagogyPack.model_validate(_pack_dict()).model_dump()
        assert dumped["k_type"] == "CONCEPT"
        assert type(dumped["k_type"]) is str  # 문자열 값(enum 멤버 아님·JSONB 정합)

    def test_required_slots_dumps_as_dict_list(self) -> None:
        dumped = PedagogyPack.model_validate(_pack_dict()).model_dump()
        slots = dumped["required_slots"]
        assert isinstance(slots, list)
        assert all(isinstance(s, dict) and set(s) == {"type", "count"} for s in slots)
        assert slots[0] == {"type": "example_pair", "count": 4}

    def test_default_evidence_and_fading_are_json_native(self) -> None:
        dumped = PedagogyPack.model_validate(_pack_dict()).model_dump()
        assert isinstance(dumped["default_evidence"], dict)
        assert dumped["fading_schedule"] is None  # nullable
        assert isinstance(dumped["forbidden_modes"], list)


# ──────────────────────────────────────────────────────────────────────────
# 입력 정규화 + store 기본 설정 (standard_loader 미러)
# ──────────────────────────────────────────────────────────────────────────
class TestAsCollection:
    def test_single_dict_becomes_one_element_list(self) -> None:
        assert _as_collection(_pack_dict()) == [_pack_dict()]

    def test_list_passthrough(self) -> None:
        packs = [_pack_dict(), _pack_dict(k_type="PROCEDURE")]
        assert _as_collection(packs) == packs

    def test_single_file_path(self, tmp_path: Path) -> None:
        import yaml

        path = tmp_path / "concept.yaml"
        path.write_text(yaml.safe_dump(_pack_dict(), allow_unicode=True), encoding="utf-8")
        raw = _as_collection(path)
        assert len(raw) == 1
        assert raw[0]["k_type"] == "CONCEPT"

    def test_invalid_input_type_raises(self) -> None:
        with pytest.raises(TypeError):
            _as_collection(42)  # type: ignore[arg-type]


def test_pack_store_uses_default_settings_when_unset() -> None:
    store = PedagogyPackStore()
    assert isinstance(store._resolved_settings, Settings)
