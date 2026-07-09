"""문제 코퍼스 적재 진입점 `populate_problem_bank` *단위테스트*(hermetic·PG 불요).

가짜 sync 엔진(캡처 커넥션) 기반 store를 주입해 로드→slug upsert→**원자 재연결 해석**(S2-03:
src 태그→크로스워크 primary→원자 행 UUID)→problem_concept 태깅·orphan skip·접힘 max-relevance·
reconcile DELETE·저작권 위생 거부를 PG 없이 검증한다. 크로스워크·다리 파일은 *실 코퍼스*를
레포 앵커로 주입한다(파일 해석은 순수·DB 무접촉). 실 코퍼스 JSONL 파싱도 함께 본다(스키마 정합).
`l1/atom_graph/test_populate.py`의 가짜 엔진 패턴을 미러한다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from whymath_backend.l1.concept_atom_crosswalk.transfer import CrosswalkRecord
from whymath_backend.l1.problem_bank.populate import (
    ProblemBankPopulateReport,
    ProblemBankStore,
    ProblemCorpusError,
    derive_src_to_primary_atom,
    load_problem_bank_records,
    populate_problem_bank,
)

# 원자 code → concept_id(UUID) 맵의 재료(가짜 concept 테이블 — S2-03 재연결 후 태깅은 원자 행).
# 크로스워크 primary: HK06→10공수1-02-02-1 · HK09→10공수1-02-04-1 · HK10→10공수1-02-05-1 ·
# HK11→10공수1-02-06-2 (실 코퍼스 crosswalk.jsonl 실측).
_HK06_ATOM = uuid.uuid4()
_HK10_ATOM = uuid.uuid4()
_HK11_ATOM = uuid.uuid4()
_HK09_ATOM = uuid.uuid4()
_ALL_CONCEPTS = {
    "10공수1-02-02-1": _HK06_ATOM,
    "10공수1-02-05-1": _HK10_ATOM,
    "10공수1-02-06-2": _HK11_ATOM,
    "10공수1-02-04-1": _HK09_ATOM,
}


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


class _Row:
    def __init__(self, code: str, concept_id: uuid.UUID) -> None:
        self.code = code
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
        # 원자 해석 SELECT — concept.code 조회(INSERT/DELETE 아님) → 가짜 concept 행 반환.
        if "concept.code" in compiled and "INSERT" not in compiled and "DELETE" not in compiled:
            return _FakeResult(rows=self._engine.code_rows)
        # 문제 upsert만 RETURNING problem_id → 결정 uuid 스칼라(problem_concept FK로 재사용).
        if "RETURNING" in compiled:
            return _FakeResult(scalar=uuid.uuid4())
        return _FakeResult()


class _FakeEngine:
    def __init__(self, concepts: dict[str, uuid.UUID]) -> None:
        self.executed: list[object] = []
        self.code_rows: list[object] = [_Row(c, cid) for c, cid in concepts.items()]

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


# 레포 루트 앵커(parents[4]) — 실 코퍼스 경로(크로스워크 거버넌스 테스트 `_ROOT` 방식).
_ROOT = Path(__file__).resolve().parents[4]
_CROSSWALK = _ROOT / "data" / "corpus" / "concept_atom_crosswalk_v1" / "crosswalk.jsonl"
_CONCEPT_GRAPH = _ROOT / "data" / "corpus" / "concept_graph_v1" / "graph.json"


def _store(engine: _FakeEngine) -> ProblemBankStore:
    """가짜 엔진 + 실 코퍼스 크로스워크/다리 경로를 주입한 store(기본 경로는 CWD 의존이라 앵커)."""
    return ProblemBankStore(
        engine=engine,  # type: ignore[arg-type]
        crosswalk_path=_CROSSWALK,
        concept_graph_path=_CONCEPT_GRAPH,
    )


def _corpus_path() -> Path:
    """레포 루트 앵커(parents[4]) — 실 코퍼스 problems.jsonl 경로."""
    return _ROOT / "data" / "corpus" / "problem_bank_v1" / "problems.jsonl"


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


def _compiled(engine: _FakeEngine) -> list[str]:
    return [str(s.compile(dialect=_pg_dialect())) for s in engine.executed]  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# derive_src_to_primary_atom (순수 유도 단위)
# ──────────────────────────────────────────────────────────────────────────
def test_derive_src_to_primary_atom_normal() -> None:
    # 정상 — 크로스워크 × 다리 조인으로 {src: primary_atom_code}.
    crosswalk = [
        CrosswalkRecord("math.a.x", ("A-1", "A-2"), "A-1"),
        CrosswalkRecord("math.a.y", ("B-1",), "B-1"),
    ]
    bridge = {"math.a.x": "HKX", "math.a.y": "HKY"}
    assert derive_src_to_primary_atom(crosswalk, bridge) == {"HKX": "A-1", "HKY": "B-1"}


def test_derive_src_to_primary_atom_duplicate_src_raises() -> None:
    # 다리 역전 충돌(두 크로스워크 행이 같은 src에 닿음) → ValueError(조용히 덮지 않음).
    crosswalk = [
        CrosswalkRecord("math.a.x", ("A-1",), "A-1"),
        CrosswalkRecord("math.a.y", ("B-1",), "B-1"),
    ]
    bridge = {"math.a.x": "HKX", "math.a.y": "HKX"}  # src 중복
    with pytest.raises(ValueError, match="중복"):
        derive_src_to_primary_atom(crosswalk, bridge)


def test_derive_src_to_primary_atom_unmapped_skipped() -> None:
    # primary_atom_code None(unmapped) 행은 강제 귀속 없이 skip.
    crosswalk = [
        CrosswalkRecord("math.a.x", (), None),  # unmapped
        CrosswalkRecord("math.a.y", ("B-1",), "B-1"),
    ]
    bridge = {"math.a.x": "HKX", "math.a.y": "HKY"}
    assert derive_src_to_primary_atom(crosswalk, bridge) == {"HKY": "B-1"}


def test_derive_src_to_primary_atom_missing_bridge_raises() -> None:
    # 다리에 없는 크로스워크 concept_id → 조인 실패 즉시 오류(transfer.py 동형).
    crosswalk = [CrosswalkRecord("math.a.x", ("A-1",), "A-1")]
    with pytest.raises(ValueError, match="graph.json"):
        derive_src_to_primary_atom(crosswalk, {})


# ──────────────────────────────────────────────────────────────────────────
# 로드·upsert·태깅 (원자 재연결)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_loads_problems_and_concept_tags(tmp_path: Path) -> None:
    path = _write(tmp_path, [_base_record()])
    report = populate_problem_bank(
        None, problems_path=path, store=_store(_FakeEngine(_ALL_CONCEPTS))
    )
    assert isinstance(report, ProblemBankPopulateReport)
    assert report.problems_loaded == 1
    assert report.problem_concepts_loaded == 1  # HK06 → 원자 행(10공수1-02-02-1) 해석됨
    assert report.concepts_skipped == 0


def test_populate_executes_problem_and_concept_inserts(tmp_path: Path) -> None:
    path = _write(tmp_path, [_base_record()])
    engine = _FakeEngine(_ALL_CONCEPTS)
    populate_problem_bank(None, problems_path=path, store=_store(engine))
    compiled = _compiled(engine)
    assert any("INSERT INTO problem " in c and "RETURNING" in c for c in compiled)
    assert any("INSERT INTO problem_concept" in c for c in compiled)
    assert any("ON CONFLICT" in c for c in compiled)


def test_populate_resolves_tag_to_atom_concept_id(tmp_path: Path) -> None:
    # HK06 태그가 *원자 행*(code=10공수1-02-02-1)의 UUID로 해석돼 problem_concept에 실린다.
    path = _write(tmp_path, [_base_record()])
    engine = _FakeEngine(_ALL_CONCEPTS)
    populate_problem_bank(None, problems_path=path, store=_store(engine))
    pc_params = [
        s.compile(dialect=_pg_dialect()).params  # type: ignore[attr-defined]
        for s, c in zip(engine.executed, _compiled(engine), strict=True)
        if "INSERT INTO problem_concept" in c
    ]
    assert len(pc_params) == 1
    assert pc_params[0]["concept_id"] == _HK06_ATOM  # 원자 행 UUID(구 437 legacy 아님)


# ──────────────────────────────────────────────────────────────────────────
# reconcile (구 연결 청소 — DELETE 방출)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_emits_reconcile_delete(tmp_path: Path) -> None:
    # 문제별 upsert 뒤 해석 집합 밖 기존 연결을 지우는 DELETE가 같은 트랜잭션에 방출된다.
    path = _write(tmp_path, [_base_record()])
    engine = _FakeEngine(_ALL_CONCEPTS)
    populate_problem_bank(None, problems_path=path, store=_store(engine))
    deletes = [c for c in _compiled(engine) if "DELETE FROM problem_concept" in c]
    assert len(deletes) == 1
    # 해석이 있으므로 (concept_id, role) NOT IN 절이 붙는다(전체 삭제 아님).
    assert "NOT IN" in deletes[0]


def test_populate_reconcile_full_delete_when_no_resolution(tmp_path: Path) -> None:
    # 해석 0건(빈 concept 테이블) → NOT IN 없는 전체 삭제 DELETE(그 문제의 연결 전부 청소).
    path = _write(tmp_path, [_base_record()])
    engine = _FakeEngine({})
    populate_problem_bank(None, problems_path=path, store=_store(engine))
    deletes = [c for c in _compiled(engine) if "DELETE FROM problem_concept" in c]
    assert len(deletes) == 1
    assert "NOT IN" not in deletes[0]


# ──────────────────────────────────────────────────────────────────────────
# orphan skip (개념 미해석)
# ──────────────────────────────────────────────────────────────────────────
def test_populate_skips_orphan_concept(tmp_path: Path) -> None:
    # 개념 태깅이 크로스워크에 없는 src_id면 orphan skip으로 집계된다(미해석 태그 보존).
    record = _base_record(concepts=[{"concept_src_id": "NOPE", "role": "PRIMARY"}])
    path = _write(tmp_path, [record])
    report = populate_problem_bank(
        None, problems_path=path, store=_store(_FakeEngine(_ALL_CONCEPTS))
    )
    assert report.problems_loaded == 1  # 문제 자체는 적재
    assert report.problem_concepts_loaded == 0  # 태깅은 orphan
    assert report.concepts_skipped == 1
    assert "NOPE" in report.skipped_messages[0]


def test_populate_empty_concept_map_skips_all(tmp_path: Path) -> None:
    # 원자 행 미적재(빈 concept 테이블) → 전건 orphan(l1.atom_graph 선행 안 됨).
    path = _write(tmp_path, [_base_record()])
    report = populate_problem_bank(None, problems_path=path, store=_store(_FakeEngine({})))
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
    report = populate_problem_bank(None, problems_path=path, store=_store(engine))
    assert report.problems_loaded == 1  # 중복 0(dedup)
    compiled = _compiled(engine)
    problem_inserts = [c for c in compiled if "INSERT INTO problem " in c and "RETURNING" in c]
    assert len(problem_inserts) == 1


def test_populate_dedups_concept_tag_by_role_with_max_relevance(tmp_path: Path) -> None:
    # 같은 (concept, role) 태깅 접힘 → 행 1건 + relevance는 max(마지막-우선 아님).
    record = _base_record(
        concepts=[
            {"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.9},
            {"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.5},  # 마지막이 더 낮음
        ]
    )
    path = _write(tmp_path, [record])
    engine = _FakeEngine(_ALL_CONCEPTS)
    report = populate_problem_bank(None, problems_path=path, store=_store(engine))
    assert report.problem_concepts_loaded == 1  # 중복 태깅 접힘
    pc_params = [
        s.compile(dialect=_pg_dialect()).params  # type: ignore[attr-defined]
        for s, c in zip(engine.executed, _compiled(engine), strict=True)
        if "INSERT INTO problem_concept" in c
    ]
    assert pc_params[0]["relevance"] == 0.9  # max — 마지막(0.5)이 덮지 않는다


def test_populate_collapse_treats_none_relevance_as_lowest(tmp_path: Path) -> None:
    # 접힘 시 None은 최저 취급 — 값(0.7)이 있으면 None이 이기지 못한다(순서 무관).
    record = _base_record(
        concepts=[
            {"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.7},
            {"concept_src_id": "HK06", "role": "PRIMARY"},  # relevance 없음(None)
        ]
    )
    path = _write(tmp_path, [record])
    engine = _FakeEngine(_ALL_CONCEPTS)
    populate_problem_bank(None, problems_path=path, store=_store(engine))
    pc_params = [
        s.compile(dialect=_pg_dialect()).params  # type: ignore[attr-defined]
        for s, c in zip(engine.executed, _compiled(engine), strict=True)
        if "INSERT INTO problem_concept" in c
    ]
    assert pc_params[0]["relevance"] == 0.7


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
