"""거버넌스 동결 — MisconceptionNode enrichment (리치 Part 2 Phase 4a·2026-07-07).

오개념 카탈로그 enrichment(`severity`·`behavior_skills`)가 CLAUDE.md 금기 안에서 사는지 동결한다.
Misconception은 *이미 완성된 독립 DB*(4테이블·거버넌스 5노드에 부재)이므로 노드 승격·거버넌스 반전은
없다 — enrichment는 정본 카탈로그(`misconception_catalog`)의 additive 필드다:

  ① **신규 엣지 타입 0**: enrichment가 EdgeType/Relation을 늘리지 않는다 — behavior_skills는
     참조 키 배열(별도 엣지 배열·junction 없음·anti-explosion).
  ② **cross-corpus 링크(dangling 0)**: 정본 코퍼스의 전 오개념 `behavior_skills`가 skill_graph_v1
     skill_id에 실재(dangling 0). arises-in 방향(진단)·오개념→skill.
  ③ **severity 축 분리**: severity 어휘(blocking/local/cosmetic)가 SEVERITY_VALUES와 일치하고
     difficulty 어휘('상/중/하')와 **disjoint**(문항 난이도 vs 손상도 — 별개 축·혼입 금지).
  ④ **독립 DB 유지**: enrichment가 오개념→개념 FK를 만들지 않는다(behavior_skills는 loose-ref 배열).

hermetic: DB 불요(모델 import + 코퍼스 JSON 스캔). 상세 7레벨 분리는
`test_misconception_seven_stage_manifest.py` 몫(중복 단언 안 함).
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.concept_graph.models import RELATION_TYPES
from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog as OrmCatalog
from whymath_backend.schema.enums import EdgeType
from whymath_backend.schema.misconception_catalog import SEVERITY_VALUES

# 리포지토리 루트(tests/backend/l1/ 기준 3단 상위) → 코퍼스 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_GRAPH = _REPO_ROOT / "data" / "corpus" / "skill_graph_v1" / "graph.json"
_MIS_CORPUS = _REPO_ROOT / "data" / "corpus" / "misconceptions_v1" / "misconceptions.json"

# difficulty 닫힌 어휘(문항 난이도) — severity(손상도)와 disjoint여야 한다.
_DIFFICULTY_VALUES = frozenset({"상", "중", "하"})


def _load_misconceptions() -> list[dict[str, object]]:
    return list(json.loads(_MIS_CORPUS.read_text(encoding="utf-8"))["misconceptions"])


# ── ① 신규 엣지 타입 0 ──────────────────────────────────────────────────────
def test_enrichment_adds_no_edge_type() -> None:
    """enrichment가 EdgeType/Relation을 늘리지 않는다 — behavior_skills는 참조 키(엣지 없음)."""
    assert 5 <= len(EdgeType) <= 8
    assert 5 <= len(RELATION_TYPES) <= 8
    # 오개념/스킬 관련 엣지 타입 토큰이 EdgeType/Relation에 유입되지 않았다(참조 키로만 연결).
    edge_tokens = {e.value.lower() for e in EdgeType} | {r.lower() for r in RELATION_TYPES}
    assert not any("misconception" in tok or "behavior_skill" in tok for tok in edge_tokens)


def test_corpus_has_no_edge_array() -> None:
    """코퍼스에 별도 엣지 배열이 없다 — 연결은 오개념 노드 내장 참조 키(behavior_skills)뿐."""
    doc = json.loads(_MIS_CORPUS.read_text(encoding="utf-8"))
    assert "edges" not in doc  # junction/엣지 배열 없음(anti-explosion)


# ── ② cross-corpus 링크(dangling 0) ────────────────────────────────────────
def test_behavior_skills_reference_existing_skills() -> None:
    """전 오개념의 behavior_skills가 skill_graph_v1 skill_id에 실재(dangling 0)."""
    skill_ids = {
        s["skill_id"] for s in json.loads(_SKILL_GRAPH.read_text(encoding="utf-8"))["skills"]
    }
    misconceptions = _load_misconceptions()
    assert misconceptions, "misconception 코퍼스가 비어있지 않아야 한다(스캔 무력화 방지)"
    dangling: dict[str, list[str]] = {}
    covered = 0
    for node in misconceptions:
        refs = list(node.get("behavior_skills") or [])  # type: ignore[arg-type]
        if refs:
            covered += 1
        missing = [r for r in refs if r not in skill_ids]
        if missing:
            dangling[str(node["mis_id"])] = missing
    assert not dangling, f"cross-corpus dangling — skill_graph_v1에 없는 참조: {dangling}"
    # 최소 커버리지 존재(전량 빈 배열이면 필드가 무의미 — 승계 시드가 실제로 채워짐).
    assert covered > 0, "behavior_skills가 전부 비어있음(승계 시드 실패)"


# ── ③ severity 축 분리(difficulty와 disjoint) ──────────────────────────────
def test_severity_values_in_closed_vocabulary() -> None:
    """전 오개념 severity가 SEVERITY_VALUES(blocking/local/cosmetic) 또는 None(신호 없음)이다."""
    allowed = set(SEVERITY_VALUES)
    offenders = {
        str(m["mis_id"]): m.get("severity")
        for m in _load_misconceptions()
        if m.get("severity") is not None and m.get("severity") not in allowed
    }
    assert not offenders, f"severity 어휘 위반(닫힌 집합 밖): {offenders}"


def test_severity_vocabulary_disjoint_from_difficulty() -> None:
    """severity 어휘가 difficulty('상/중/하')와 disjoint(문항 난이도 vs 손상도 — 축 혼입 금지)."""
    assert set(SEVERITY_VALUES).isdisjoint(_DIFFICULTY_VALUES)
    # 코퍼스 실측 severity 값도 difficulty 값과 겹치지 않는다.
    corpus_sev = {m.get("severity") for m in _load_misconceptions() if m.get("severity")}
    assert corpus_sev.isdisjoint(_DIFFICULTY_VALUES)


# ── ④ 독립 DB 유지(오개념→개념 FK 0) ───────────────────────────────────────
def test_enrichment_adds_no_foreign_key() -> None:
    """enrichment가 오개념 카탈로그에 FK를 만들지 않는다(behavior_skills·severity는 loose-ref)."""
    assert len(OrmCatalog.__table__.foreign_keys) == 0
    assert len(OrmCatalog.__table__.c.behavior_skills.foreign_keys) == 0
    assert len(OrmCatalog.__table__.c.severity.foreign_keys) == 0
