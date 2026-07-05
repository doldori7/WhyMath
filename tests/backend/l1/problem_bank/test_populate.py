"""문제 코퍼스 적재 진입점 `populate_problem_bank` *단위테스트*(hermetic·PG 불요).

가짜 sync 엔진(캡처 커넥션) 기반 store를 주입해 로드→slug upsert→concept 해석→problem_concept
태깅·orphan skip·slug dedup(멱등)·저작권 위생 거부를 PG 없이 검증한다. 실 코퍼스 JSONL 파싱도
함께 본다(스키마 정합). `l1/atom_graph/test_populate.py`의 가짜 엔진 패턴을 미러한다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from whymath_backend.l1.problem_bank.populate import (
    ProblemBankPopulateReport,
    ProblemBankStore,
    ProblemCorpusError,
    load_problem_bank_records,
    populate_problem_bank,
)

# 개념 src_id → concept_id(UUID) 맵의 재료(가짜 concept 테이블).
_HK06 = uuid.uuid4()
_HK10 = uuid.uuid4()
_HK11 = uuid.uuid4()
_HK09 = uuid.uuid4()
_ALL_CONCEPTS = {"HK06": _HK06, "HK10": _HK10, "HK11": _HK11, "HK09": _HK09}


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


class _Row:
    def __init__(self, source_id: str, concept_id: uuid.UUID) -> None:
        self.source_id = source_id
        self.concept_id = concept_id


class _FakeResult:
    def __init__(self, rows: list[object] | None = None, scalar: object | None = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self) -> list[object]:
        return self._rows

    def scalar_one(self) -> object:
        return self._scalar


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
        compiled = str(statement.compile(dialect=_pg_dialect()))  # type: ignore[attr-defined]
        # 개념 해석 SELECT — concept.source_id 조회(INSERT 아님) → 가짜 concept 행 반환.
        if "concept.source_id" in compiled and "INSERT" not in compiled:
            return _FakeResult(rows=self._engine.code_rows)
        # 문제 upsert만 RETURNING problem_id → 결정 uuid 스칼라(problem_concept FK로 재사용).
        if "RETURNING" in compiled:
            return _FakeResult(scalar=uuid.uuid4())
        return _FakeResult()


class _FakeEngine:
    def __init__(self, concepts: dict[str, uuid.UUID]) -> None:
        self.executed: list[object] = []
        self.code_rows: list[object] = [_Row(s, c) for s, c in concepts.items()]

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _corpus_path() -> Path:
    """레포 루트 앵커(parents[4]) — 실 코퍼스 problems.jsonl 경로."""
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "corpus"
        / "problem_bank_v1"
        / "problems.jsonl"
    )


def _base_record(**overrides: Any) -> dict[str, Any]:
    """자체생성 유효 레코드(단답형)의 최소 dict — override로 변형해 위생 거부를 검증."""
    record: dict[str, Any] = {
        "slug": "wm-test-eq",
        "source_type": "자체생성",
        "license": "WHYMATH_GENERATED",
        "generation_type": "FULLY_GENERATED",
        "subject": "공통",
        "curriculum_version": "2022_REVISION",
        "valid_from_year": 2025,
        "unit_codes": ["QUAD-EQ"],
        "question_format": "단답형",
        "answer_format": "자연수",
        "difficulty_overall": 2.0,
        "question_text": "이차방정식 x^2 - 5x + 6 = 0 의 큰 근은?",
        "answer": "3",
        "answer_explanation": "(x-2)(x-3) = 0 이므로 큰 근은 3이다.",
        "achievement_standard_codes": ["[10공수1-02-02]"],
        "concepts": [{"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.9}],
        "verify": {"conditions": "x**2 - 5*x + 6 = 0", "answer_map": {"x": "3"}},
    }
    record.update(overrides)
    return record


def _write(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    path = tmp_path / "problems.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return path


# ──────────────────────────────────────────────────────────────────────────
# 로드·upsert·태깅
# ──────────────────────────────────────────────────────────────────────────
def test_populate_loads_problems_and_concept_tags(tmp_path: Path) -> None:
    path = _write(tmp_path, [_base_record()])
    store = ProblemBankStore(engine=_FakeEngine(_ALL_CONCEPTS))  # type: ignore[arg-type]
    report = populate_problem_bank(None, problems_path=path, store=store)
    assert isinstance(report, ProblemBankPopulateReport)
    assert report.problems_loaded == 1
    assert report.problem_concepts_loaded == 1  # HK06 해석됨
    assert report.concepts_skipped == 0


def test_populate_executes_problem_and_concept_inserts(tmp_path: Path) -> None:
    path = _write(tmp_path, [_base_record()])
    engine = _FakeEngine(_ALL_CONCEPTS)
    store = ProblemBankStore(engine=engine)  # type: ignore[arg-type]
    populate_problem_bank(None, problems_path=path, store=store)
    compiled = [str(s.compile(dialect=_pg_dialect())) for s in engine.executed]  # type: ignore[attr-defined]
    assert any("INSERT INTO problem " in c and "RETURNING" in c for c in compiled)
    assert any("INSERT INTO problem_concept" in c for c in compiled)
    assert any("ON CONFLICT" in c for c in compiled)


# ──────────────────────────────────────────────────────────────────────────
# orphan skip (개념 미해석)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_skips_orphan_concept(tmp_path: Path) -> None:
    # 개념 태깅이 가짜 concept 맵에 없는 src_id면 orphan skip으로 집계된다.
    record = _base_record(concepts=[{"concept_src_id": "NOPE", "role": "PRIMARY"}])
    path = _write(tmp_path, [record])
    store = ProblemBankStore(engine=_FakeEngine(_ALL_CONCEPTS))  # type: ignore[arg-type]
    report = populate_problem_bank(None, problems_path=path, store=store)
    assert report.problems_loaded == 1  # 문제 자체는 적재
    assert report.problem_concepts_loaded == 0  # 태깅은 orphan
    assert report.concepts_skipped == 1
    assert "NOPE" in report.skipped_messages[0]


def test_populate_empty_concept_map_skips_all(tmp_path: Path) -> None:
    # 개념 미적재(빈 맵) → 전건 orphan(l1.concept_graph/atom_graph 선행 안 됨).
    path = _write(tmp_path, [_base_record()])
    store = ProblemBankStore(engine=_FakeEngine({}))  # type: ignore[arg-type]
    report = populate_problem_bank(None, problems_path=path, store=store)
    assert report.problems_loaded == 1
    assert report.problem_concepts_loaded == 0
    assert report.concepts_skipped == 1


# ──────────────────────────────────────────────────────────────────────────
# 멱등 (배치 내 slug 중복 → 마지막 우선 dedup·중복 0)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_dedups_duplicate_slug(tmp_path: Path) -> None:
    # 같은 slug 2회 → dedup(마지막 우선)로 문제 upsert 1건(단일 배치 ON CONFLICT 중복행 방지).
    dup = [_base_record(), _base_record(answer="9")]
    path = _write(tmp_path, dup)
    engine = _FakeEngine(_ALL_CONCEPTS)
    store = ProblemBankStore(engine=engine)  # type: ignore[arg-type]
    report = populate_problem_bank(None, problems_path=path, store=store)
    assert report.problems_loaded == 1  # 중복 0(dedup)
    compiled = [str(s.compile(dialect=_pg_dialect())) for s in engine.executed]  # type: ignore[attr-defined]
    problem_inserts = [c for c in compiled if "INSERT INTO problem " in c and "RETURNING" in c]
    assert len(problem_inserts) == 1


def test_populate_dedups_concept_tag_by_role(tmp_path: Path) -> None:
    # 같은 (concept, role) 태깅 중복 → (concept_id, role)로 dedup(마지막 우선).
    record = _base_record(
        concepts=[
            {"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.5},
            {"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.9},
        ]
    )
    path = _write(tmp_path, [record])
    store = ProblemBankStore(engine=_FakeEngine(_ALL_CONCEPTS))  # type: ignore[arg-type]
    report = populate_problem_bank(None, problems_path=path, store=store)
    assert report.problem_concepts_loaded == 1  # 중복 태깅 접힘


# ──────────────────────────────────────────────────────────────────────────
# 저작권 위생 거부 (source_type/license)
# ──────────────────────────────────────────────────────────────────────────
def test_load_rejects_non_self_generated_source(tmp_path: Path) -> None:
    # source_type이 자체생성이 아니면 로드 거부(본문 보유 불법 출처).
    record = _base_record(source_type="AIHub")
    path = _write(tmp_path, [record])
    with pytest.raises(ProblemCorpusError, match="source_type"):
        load_problem_bank_records(path)


def test_load_rejects_non_whymath_license(tmp_path: Path) -> None:
    # license가 WHYMATH_GENERATED가 아니면 로드 거부.
    record = _base_record(license="PUBLIC_DOMAIN")
    path = _write(tmp_path, [record])
    with pytest.raises(ProblemCorpusError, match="license"):
        load_problem_bank_records(path)


def test_load_rejects_missing_slug(tmp_path: Path) -> None:
    # 안정 키 slug 부재 → 멱등 불가로 거부.
    record = _base_record()
    del record["slug"]
    path = _write(tmp_path, [record])
    with pytest.raises(ProblemCorpusError, match="slug"):
        load_problem_bank_records(path)


def test_load_rejects_invalid_concept_role(tmp_path: Path) -> None:
    record = _base_record(concepts=[{"concept_src_id": "HK06", "role": "MAIN"}])
    path = _write(tmp_path, [record])
    with pytest.raises(ProblemCorpusError, match="role"):
        load_problem_bank_records(path)


# ──────────────────────────────────────────────────────────────────────────
# 실 코퍼스 스키마 정합
# ──────────────────────────────────────────────────────────────────────────
def test_real_corpus_parses() -> None:
    corpus = _corpus_path()
    if not corpus.exists():
        pytest.skip("실 코퍼스 미존재(data/corpus/problem_bank_v1/problems.jsonl)")
    records = load_problem_bank_records(corpus)
    assert len(records) == 4
    slugs = {r.slug for r in records}
    assert "wm-quad-eq-root-count-mc" in slugs
    for record in records:
        # 전건 자체생성 위생 통과(source_type=자체생성·license=WHYMATH_GENERATED).
        assert record.problem.source_type == "자체생성"
        assert record.provenance.license == "WHYMATH_GENERATED"
        assert len(record.problem.unit_codes) >= 1
        assert record.concept_tags  # 개념 태깅 최소 1건
    # 객관식 시드는 distractor_map(오개념 태깅) 보유.
    mc = next(r for r in records if r.slug == "wm-quad-eq-root-count-mc")
    assert mc.problem.distractor_map is not None
    assert mc.problem.distractor_map[0].misconception_id == "root-loss-by-dividing"
