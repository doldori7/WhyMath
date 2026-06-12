"""개념그래프 → backend `Concept` 런타임 적재 *단위테스트* — 브리지 슬1 (hermetic·PG 불요).

CI hermetic 잡엔 PostgreSQL이 없으므로 `BackendConceptStore`/`populate_backend_concepts`의 *실
라운드트립*은 통합테스트(`test_concept_backend_load_integration.py`·실 PG 게이트)로 미룬다. 여기서는
PG 없이 검증 가능한 것만 못 박는다(슬117 `test_concept_node_projection.py` 가짜 엔진 패턴 재사용):

  ① graph.json 로딩 — UC→code 브리지·name_ko·필드 유도·redaction 키 미유입·name_ko 누락 graceful
  ② 필드 유도 — subject 매핑(고4·공통·미대응 None)·difficulty 스케일·misconception 변환·level 고정
  ③ upsert SQL 구성 — ON CONFLICT(code) upsert·**본문 3컬럼(description/formal_definition/
     intuitive_explanation) 0**·PK(concept_id) 미-SET(UUID 보존)
  ④ populate — 전 레코드 upsert(횟수=레코드 수)·멱등(같은 레코드 2회→같은 upsert statement)

가짜 엔진(`_FakeEngine`)은 begin() 컨텍스트 + execute()를 흉내내 실행된 statement를 기록한다 —
psycopg/PG 없이 배선·redaction·멱등 키를 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.backend_concept import (
    BackendConceptRecord,
    BackendConceptStore,
    load_backend_concepts_from_graph_json,
    map_subject,
    populate_backend_concepts,
    scale_difficulty,
)
from whymath_backend.schema.enums import ConceptLevel, Subject

# 슬2 idmap이 발급하는 UC 규약 키 예시(Neo4j·concept_embedding·concept_node와 동일 키 공간).
_UC_A = "UC.calc.alimit.epsilon-delta"
_UC_B = "UC.alg.afunction.composition"


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
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 기록(upsert는 결과 미사용)."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store() -> tuple[BackendConceptStore, _FakeEngine]:
    """가짜 엔진을 주입한 BackendConceptStore + 엔진(검사용) 페어."""
    engine = _FakeEngine()
    store = BackendConceptStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
    return store, engine


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용·슬117 패턴)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


def _record(
    code: str = _UC_A,
    *,
    name_ko: str = "극한",
    subject: Subject | None = Subject.미적분,
    intrinsic_difficulty: float | None = 2.17,
) -> BackendConceptRecord:
    return BackendConceptRecord(
        code=code,
        name_ko=name_ko,
        level=ConceptLevel.세부개념,
        subject=subject,
        intrinsic_difficulty=intrinsic_difficulty,
        common_misconceptions=[{"misconception": "극한을 대입값으로 혼동"}],
    )


# ──────────────────────────────────────────────────────────────────────────
# ① graph.json 로딩 — UC→code 브리지·유도·redaction·graceful
# ──────────────────────────────────────────────────────────────────────────
class TestLoadFromGraphJson:
    def _write_graph(self, tmp_path: Path, concepts: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": concepts, "edges": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_concept_id_becomes_code_bridge(self, tmp_path: Path) -> None:
        # 핵심 브리지: graph concept_id(UC)가 backend Concept.code가 된다.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "domain": "[고]미적분",
                    "difficulty_tier": 7,
                    "misconception_text": "극한을 대입값으로 혼동",
                    "review_status": "reviewed",
                }
            ],
        )
        loaded = load_backend_concepts_from_graph_json(path)
        assert len(loaded) == 1
        rec = loaded[0]
        assert rec.code == _UC_A  # UC = code(브리지 키)
        assert rec.name_ko == "극한"
        assert rec.level == ConceptLevel.세부개념  # 고정 유도(NOT NULL 충족)
        assert rec.subject == Subject.미적분  # domain 매핑
        assert rec.intrinsic_difficulty == scale_difficulty(7)
        assert rec.common_misconceptions == [
            {"misconception": "극한을 대입값으로 혼동"}
        ]

    def test_description_and_formal_definition_never_loaded(
        self, tmp_path: Path
    ) -> None:
        # redaction: graph 부재이나 *오염되어 들어와도* 레코드에 유입되지 않음을 못 박는다.
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "극한",
                    "domain": "[고]미적분",
                    "description": "교과서 본문 근접 서술(절대 적재 금지)",
                    "formal_definition": "∀ε>0 ∃δ>0 ... (절대 적재 금지)",
                    "intuitive_explanation": "검수 책임 직관 설명(절대 적재 금지)",
                }
            ],
        )
        loaded = load_backend_concepts_from_graph_json(path)
        assert len(loaded) == 1
        # BackendConceptRecord에 본문 3슬롯이 *없다*(구조적 차단 — dataclass 필드에 부재).
        fields = set(BackendConceptRecord.__dataclass_fields__)
        assert "description" not in fields
        assert "formal_definition" not in fields
        assert "intuitive_explanation" not in fields

    def test_loads_all_concepts_regardless_of_review_status(
        self, tmp_path: Path
    ) -> None:
        # 전량 적재(review_status 무관·게이팅은 조회 몫·슬2/3/117 동형).
        path = self._write_graph(
            tmp_path,
            [
                {
                    "concept_id": _UC_A,
                    "name_ko": "첫째",
                    "domain": "d",
                    "review_status": "reviewed",
                },
                {
                    "concept_id": _UC_B,
                    "name_ko": "둘째",
                    "domain": "d",
                    "review_status": "pending",
                },
            ],
        )
        loaded = load_backend_concepts_from_graph_json(path)
        assert [c.code for c in loaded] == [_UC_A, _UC_B]

    def test_optional_fields_default_when_absent(self, tmp_path: Path) -> None:
        # difficulty_tier·misconception_text·domain 매핑 불가 → None/빈(날조 0).
        path = self._write_graph(
            tmp_path,
            [{"concept_id": _UC_A, "name_ko": "유효", "domain": "[중]수와 연산"}],
        )
        rec = load_backend_concepts_from_graph_json(path)[0]
        assert rec.subject is None  # 초·중 영역은 backend Subject enum에 없음 → None
        assert rec.intrinsic_difficulty is None  # difficulty_tier 부재
        assert rec.common_misconceptions == []  # misconception_text 부재

    def test_skips_when_name_ko_missing(self, tmp_path: Path) -> None:
        # name_ko 누락(오염) → 건너뜀(NOT NULL 위반 방지·조용한 빈 적재 금지).
        path = self._write_graph(tmp_path, [{"concept_id": _UC_A, "domain": "d"}])
        assert load_backend_concepts_from_graph_json(path) == []

    def test_skips_when_name_ko_blank(self, tmp_path: Path) -> None:
        path = self._write_graph(
            tmp_path, [{"concept_id": _UC_A, "name_ko": "   ", "domain": "d"}]
        )
        assert load_backend_concepts_from_graph_json(path) == []

    def test_missing_concept_id_raises(self, tmp_path: Path) -> None:
        path = self._write_graph(tmp_path, [{"name_ko": "키 없음", "domain": "d"}])
        with pytest.raises(ValueError, match="concept_id"):
            load_backend_concepts_from_graph_json(path)


# ──────────────────────────────────────────────────────────────────────────
# ② 필드 유도 — subject 매핑·difficulty 스케일·misconception·level 고정
# ──────────────────────────────────────────────────────────────────────────
class TestSubjectMapping:
    def test_high_school_four_subjects(self) -> None:
        assert map_subject("[고]미적분") == Subject.미적분
        assert map_subject("[고]기하") == Subject.기하
        assert map_subject("[고]확률·통계") == Subject.확통
        assert map_subject("[고]인공지능 수학") == Subject.인공지능수학

    def test_common_prefix_maps_to_gongtong(self) -> None:
        assert map_subject("[공통]함수") == Subject.공통
        assert map_subject("[공통]집합과 명제") == Subject.공통

    def test_unmapped_domains_are_none(self) -> None:
        # 억지 매핑 0 — enum에 없는 과목·초중 영역은 None(subject nullable).
        assert map_subject("[중]수와 연산") is None
        assert map_subject("[고]대수") is None
        assert map_subject("분수") is None
        assert map_subject(None) is None
        assert map_subject("") is None


class TestDifficultyScale:
    def test_linear_scale_endpoints_and_mid(self) -> None:
        # tier[0,24] → intrinsic[1,5] 선형(schema ge=1 le=5·Numeric(3,2) 정합).
        assert scale_difficulty(0) == 1.0
        assert scale_difficulty(12) == 3.0
        assert scale_difficulty(24) == 5.0

    def test_none_passthrough(self) -> None:
        assert scale_difficulty(None) is None

    def test_out_of_range_clamped(self) -> None:
        # 방어: 범위 밖도 [1,5]로 clamp(schema 제약 위반 방지).
        assert scale_difficulty(-5) == 1.0
        assert scale_difficulty(100) == 5.0


# ──────────────────────────────────────────────────────────────────────────
# ③ upsert SQL 구성 — ON CONFLICT(code)·redaction·PK 미-SET(UUID 보존)
# ──────────────────────────────────────────────────────────────────────────
class TestUpsertStatement:
    def test_upsert_executes_one_statement_with_on_conflict_code(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO concept" in compiled
        assert "ON CONFLICT" in compiled
        # 브리지 키: 충돌 키가 code(UNIQUE)다(UUID PK가 아니라 — UC↔UUID 브리지).
        assert "(code)" in compiled or "concept.code" in compiled

    def test_upsert_omits_redacted_body_columns(self) -> None:
        # redaction: INSERT/SET 컬럼에 본문 3개가 *없다*(검수 책임 필드·NULL 유지).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "description" not in compiled
        assert "formal_definition" not in compiled
        assert "intuitive_explanation" not in compiled

    def test_upsert_does_not_set_pk_or_created_at_on_conflict(self) -> None:
        # UUID 보존: ON CONFLICT DO UPDATE SET이 concept_id(PK)·created_at을 *대입하지 않아야*
        # 한다(재적재가 기존 UUID·생성시각을 덮어쓰지 않음 — L2 mastery·problem_concept FK 안정성).
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "DO UPDATE SET" in compiled
        # SET 절만 분리(뒤따르는 RETURNING concept.concept_id는 PK 대입이 아니라 신규행 PK 회신).
        after_set = compiled.split("DO UPDATE SET", 1)[1]
        set_clause = after_set.split("RETURNING", 1)[0]
        # SET이 PK·created_at을 대입하지 않음(excluded.concept_id/created_at 부재 = 보존).
        assert "concept_id" not in set_clause
        assert "created_at" not in set_clause
        assert (
            "excluded.concept_id" not in compiled
        )  # 어디서도 PK를 excluded로 덮지 않음

    def test_upsert_includes_runtime_identity_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in ("code", "name_ko", "level", "subject", "intrinsic_difficulty"):
            assert col in compiled

    def test_upsert_handles_null_subject_without_error(self) -> None:
        # subject None(미대응 도메인)도 안전 — upsert가 예외 없이 statement를 만든다(억지 매핑 0의
        # 영속 표현). NULL이 실제로 적재됨은 통합테스트 test_unmapped_subject_persists_null이 본다.
        store, engine = _fake_store()
        store.upsert(_record(subject=None))
        assert len(engine.executed) == 1
        compiled = _compile(engine.executed[0])
        assert "subject" in compiled  # subject는 여전히 upsert 컬럼(값만 NULL)


# ──────────────────────────────────────────────────────────────────────────
# ④ populate — 전 레코드 upsert·멱등
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_populate_upserts_each_record(self) -> None:
        store, engine = _fake_store()
        count = populate_backend_concepts([_record(_UC_A), _record(_UC_B)], store=store)
        assert count == 2
        assert len(engine.executed) == 2  # 레코드당 1 upsert

    def test_populate_empty_is_noop(self) -> None:
        store, engine = _fake_store()
        assert populate_backend_concepts([], store=store) == 0
        assert engine.executed == []

    def test_populate_idempotent_same_statements(self) -> None:
        # 같은 레코드 2회 populate → 같은 upsert(ON CONFLICT) statement(멱등 — 실 행 1개는 통합).
        store, engine = _fake_store()
        records = [_record(_UC_A)]
        populate_backend_concepts(records, store=store)
        populate_backend_concepts(records, store=store)
        assert len(engine.executed) == 2
        for stmt in engine.executed:
            assert "ON CONFLICT" in _compile(stmt)


def test_record_has_no_body_slots() -> None:
    # 노출 계약: 적재 레코드는 본문 3슬롯을 갖지 않는다(구조적 redaction).
    fields = set(BackendConceptRecord.__dataclass_fields__)
    assert "description" not in fields
    assert "formal_definition" not in fields
    assert "intuitive_explanation" not in fields
    # 런타임 식별 필드는 보유.
    assert {"code", "name_ko", "level", "subject", "intrinsic_difficulty"} <= fields


def test_store_uses_default_settings_when_unset() -> None:
    # store에 settings·engine 미주입이면 전역 Settings를 지연 해석한다(엔진 생성은 첫 upsert에서).
    store = BackendConceptStore()
    assert isinstance(store._resolved_settings, Settings)
