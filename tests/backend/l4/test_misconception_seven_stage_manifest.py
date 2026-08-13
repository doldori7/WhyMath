"""정본 7레벨 분리 manifest 동결 — 명세(`docs/architecture/04c…`)↔코드 드리프트 차단.

`04c_misconception_seven_stage_separation.md`가 열거한 **정본 7레벨**(Storage · Relation ·
Embedding · Retrieval · Runtime Context · Repair Strategy · Renderer)의 각 앵커(모듈·테이블·약한
관계 금지 상수·게이트 기본값·기존 동결 테스트·문서)가 *실제로 존재*함을 확인한다. 이 테스트는
기존 governance 테스트(namespace·purity·runtime·edge-relation)의 단언을 **중복하지 않는다** — 그
방어들이 저장소에 *실재*한다는 연결 무결성과, 명세가 이름 댄 앵커가 *import/존재 가능*하다는 것만
동결한다.

명세를 바꾸면(레벨 추가·앵커 이동·레벨명 변경) 이 테스트가 red가 되어 문서와 코드가 함께 움직이도록
강제한다.

hermetic: 외부 의존·DB 불요(모듈 import·ORM 메타데이터·소스 텍스트 스캔·파일 존재·Field 기본값만).
"""

from __future__ import annotations

import importlib
from pathlib import Path

from whymath_backend.config import Settings
from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog
from whymath_backend.db.models.misconception_crosslink import MisconceptionCrosslink
from whymath_backend.db.models.misconception_embedding import MisconceptionEmbedding
from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.db.models.misconception_relation import MisconceptionRelation

# 저장소 루트 — 이 파일: tests/backend/l4/…  →  parents[3] = repo root(tests·docs·src 보유).
_REPO_ROOT = Path(__file__).resolve().parents[3]


# ──────────────────────────────────────────────────────────────────────────
# 정본 7레벨 — 플레이북 Part 6 §6-2 표. 레벨명·순서를 코드로 동결(초판 파생 7단계 교정).
# ──────────────────────────────────────────────────────────────────────────
_LEVEL_NAMES: dict[int, str] = {
    1: "Storage",
    2: "Relation",
    3: "Embedding",
    4: "Retrieval",
    5: "Runtime Context",
    6: "Repair Strategy",
    7: "Renderer",
}

# 각 레벨의 구현 앵커(dotted path·04c §2 표). 전부 import 가능해야 한다 — 좌석이 사라지면 명세가
# 거짓말이 된다. (data-pipeline 크로스패키지 import는 피하고, Level 2 약한관계 금지 상수는 아래
# 별도 소스 스캔으로 동결한다 — mypy/경로 취약성 회피.)
_LEVEL_ANCHOR_MODULES: dict[int, tuple[str, ...]] = {
    1: (  # Storage
        "whymath_backend.db.models.misconception_catalog",
        "whymath_backend.db.models.misconception_hypothesis",
        "whymath_backend.db.models.misconception_crosslink",
        "whymath_backend.db.models.misconception_embedding",
    ),
    2: (  # Relation — 오개념이 개념 traversal에 진입 불가(선수 전용 필터·적재기)
        "whymath_backend.l1.concept_graph.backend_edge",
        "whymath_backend.l2.prerequisite_recommendation",
    ),
    3: (  # Embedding
        "whymath_backend.l4.misconception.semantic.pgvector_index",
        "whymath_backend.l1.concept_graph.embedding",
        "whymath_backend.l1.atom_graph.embedding",
    ),
    4: (  # Retrieval — reactive + classifier-first
        "whymath_backend.l4.misconception.diagnose",
        "whymath_backend.l4.misconception.combined",
        "whymath_backend.l4.misconception.match_gate",
    ),
    5: (  # Runtime Context — 2-stage·게이트 off 기본
        "whymath_backend.api.coach",
        "whymath_backend.api._misconception_state",
    ),
    6: (  # Repair Strategy — intervene(교정)은 카탈로그와 별도 모듈
        "whymath_backend.l4.misconception.intervene",
        "whymath_backend.l4.misconception.distractor",
    ),
    7: (  # Renderer — Visualization Intent → L3 spec → L5 렌더(구현체 비내장)
        "whymath_backend.l4.misconception.visualize",
        "whymath_backend.schema.visualization",
    ),
}

# 오개념 5 ORM 테이블(Level 1·2) — 개념 테이블과 disjoint·개념에 FK 결합 안 됨을 확인할 대상.
# MisconceptionRelation(MISC-04·caused_by/variant_of)은 개념상 Level 2(오개념 간 관계)이지만,
# "개념에 FK 결합 안 됨" 검사는 Level 1·2 공통 불변식이라 이 튜플에 함께 실어 동일 검사를
# 무료로(신규 테스트 코드 0) 확장한다(04e_misconception_remediation_design.md §2-3).
_MISCONCEPTION_MODELS = (
    MisconceptionCatalog,
    MisconceptionHypothesisRecord,
    MisconceptionCrosslink,
    MisconceptionEmbedding,
    MisconceptionRelation,
)

# 개념 측 테이블명(오개념이 여기에 FK로 묶이면 loose-ref 분리가 깨진다).
_CONCEPT_TABLE_NAMES = frozenset(
    {
        "concept",
        "concept_edge",
        "concept_node",
        "concept_embedding",
        "concept_content",
        "concept_fusion",
        "concept_standard_link",
        "problem_concept",
    }
)

# Level 2 약한 관계 금지 상수의 단일 진실(data-pipeline). 소스 텍스트로 실재만 확인(크로스패키지
# import·mypy 취약성 회피). 상세 거버넌스는 test_edge_relation_governance.py 몫(중복 단언 안 함).
_CONCEPT_GRAPH_SRC_DIR = "src/data-pipeline/data_pipeline/concept_graph"
_RELATION_CROSSWALK_SRC = f"{_CONCEPT_GRAPH_SRC_DIR}/relation_crosswalk.py"

# MISC-04 — concept_edge를 실제로 순회·join하는 backend 소스(재귀 CTE·집합 내부 엣지 조회). 이
# 목록이 `misconception_relation`을 join하면(현재는 하지 않는다 — 04e §2-3 traversal 진입 차단
# 불변식) 오개념이 개념 traversal의 사실상 노드가 되는 뒷문이 열린 것 — 회귀 트립와이어(§2-3).
# `whymath_backend.l2.prerequisite_recommendation` — 재귀 CTE(`build_prerequisite_stmt`,
#   `.cte(recursive=True)`)로 concept_edge를 순회하는 정본 traversal 엔진(Level 2 앵커 모듈).
# `whymath_backend.l2.learning_path` — 막힌 선수 집합 *내부* concept_edge를 조회해 위상정렬하는
#   보조 traversal 소비처(`fetch_internal_prerequisite_edges`).
_CONCEPT_EDGE_TRAVERSAL_SRC_FILES: tuple[str, ...] = (
    "src/backend/whymath_backend/l2/prerequisite_recommendation.py",
    "src/backend/whymath_backend/l2/learning_path.py",
)

# 항목 ①③·preload·관계 동결을 담당하는 *기존* 방어 — 명세가 근거로 든 테스트들의 실재 확인
# (repo 상대경로). 이들이 사라지면 04c 감사·갭 장부가 근거를 잃는다.
_REFERENCED_GUARD_TESTS = (
    "tests/data_pipeline/concept_graph/test_concept_node_purity.py",
    # test_concept_misconception_runtime.py는 Phase 1b(2026-07-03)로 제거됐다 — 동결 대상
    # 런타임 `common_misconceptions` 컬럼 자체가 삭제돼(schema/db 슬롯 부재) 정적 가드가 moot.
    "tests/backend/l1/test_embedding_namespace_governance.py",
    "tests/backend/l1/test_edge_relation_governance.py",
    "tests/backend/l4/test_misconception_namespace_gate.py",
)

# 명세 문서 자체.
_SPEC_DOC = "docs/architecture/04c_misconception_seven_stage_separation.md"


# ──────────────────────────────────────────────────────────────────────────
# 정본 7레벨 — 열거·레벨명·앵커 import
# ──────────────────────────────────────────────────────────────────────────
def test_seven_levels_are_enumerated() -> None:
    """명세는 정확히 7레벨이고 앵커·레벨명 키가 일치한다(1..7)."""
    assert set(_LEVEL_ANCHOR_MODULES) == set(range(1, 8))
    assert set(_LEVEL_NAMES) == set(range(1, 8))


def test_level_names_are_canonical() -> None:
    """레벨명·순서가 정본 표와 정확히 일치(초판 파생 7단계로의 재드리프트 차단)."""
    ordered = tuple(_LEVEL_NAMES[i] for i in range(1, 8))
    assert ordered == (
        "Storage",
        "Relation",
        "Embedding",
        "Retrieval",
        "Runtime Context",
        "Repair Strategy",
        "Renderer",
    )


def test_every_level_anchor_module_importable() -> None:
    """7레벨 각 앵커 모듈이 import 가능 — 명세가 이름 댄 좌석이 실재한다.

    소실 시 `importlib.import_module`이 ImportError로 즉시 red(해당 레벨 앵커 소실).
    """
    for modules in _LEVEL_ANCHOR_MODULES.values():
        for dotted in modules:
            importlib.import_module(dotted)


# ──────────────────────────────────────────────────────────────────────────
# Level 1·2 — 오개념 테이블 분리(개념과 disjoint·FK 비결합)
# ──────────────────────────────────────────────────────────────────────────
def test_misconception_tables_disjoint_from_concept_tables() -> None:
    """오개념 5테이블명이 개념 측 테이블명과 겹치지 않는다(별도 store·Level 1·2)."""
    mis_tables = {m.__tablename__ for m in _MISCONCEPTION_MODELS}
    assert mis_tables == {
        "misconception_catalog",
        "misconception_hypothesis",
        "misconception_crosslink",
        "misconception_embedding",
        "misconception_relation",
    }
    assert mis_tables.isdisjoint(_CONCEPT_TABLE_NAMES)


def test_misconception_tables_have_no_foreign_key_into_concept() -> None:
    """오개념 테이블의 어떤 FK도 개념 측 테이블을 가리키지 않는다(loose ref — Level 2).

    오개념→개념 참조는 `concept_src_id`(원천 문자열)·kebab-id 같은 *느슨참조*로만 존재하고 DB
    FK로 개념 identity에 결합되지 않는다(개념↔오개념 결합 폭발·순환 차단). 허용 FK 타깃은
    오개념 도메인 내부(`misconception_catalog`)·학생(`user_profile`)뿐이다.
    """
    for model in _MISCONCEPTION_MODELS:
        referenced = {fk.column.table.name for fk in model.__table__.foreign_keys}
        offenders = referenced & _CONCEPT_TABLE_NAMES
        assert offenders == set(), (
            f"{model.__tablename__}가 개념 테이블에 FK 결합됨 — {sorted(offenders)}. 오개념은 "
            "개념에 느슨참조(원천 문자열)로만 이어야 한다(04c Level 2·Concept Purity)."
        )


# ──────────────────────────────────────────────────────────────────────────
# Level 2 — 약한 관계 금지 상수 실재(traversal dense화 방어)
# ──────────────────────────────────────────────────────────────────────────
def test_weak_relation_ban_constants_present() -> None:
    """`FORBIDDEN_RELATION_TOKENS`에 similar_to·related_to가, 배제 집합 상수가 소스에 실재한다.

    상세 거버넌스(로더가 PREREQUISITE만 적재 등)는 `test_edge_relation_governance.py` 몫 — 여기선
    Level 2 traversal 배제의 단일 진실 상수가 *존재*함만 동결한다(중복 단언 회피·소스 텍스트 스캔).
    """
    src = (_REPO_ROOT / _RELATION_CROSSWALK_SRC).read_text(encoding="utf-8")
    assert "FORBIDDEN_RELATION_TOKENS" in src
    assert '"similar_to"' in src
    assert '"related_to"' in src
    assert "TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES" in src


def test_concept_edge_traversal_never_joins_misconception_relation() -> None:
    """`concept_edge` 순회·CTE 함수가 `misconception_relation`을 join하지 않는다(MISC-04 acc③).

    04e_misconception_remediation_design.md §2-3 "traversal 진입 차단"의 (b) 소스 스캔 절반 —
    (a) 스키마 레벨 FK 부재는 `test_misconception_tables_have_no_foreign_key_into_concept`가
    이미 확인한다. `misconception_relation`은 이 태스크(MISC-04)에서 저장소만 세우고 순회 코드를
    전혀 쓰지 않으므로 이 테스트는 *지금* 자명하게 통과한다 — 값어치는 현재 증명이 아니라 향후
    누군가 `prerequisite_recommendation`/`learning_path`의 concept_edge traversal에
    `misconception_relation`을 얹으면(개념 traversal의 사실상 뒷문) 즉시 red가 되는 회귀
    트립와이어라는 데 있다(hermetic — 소스 텍스트 스캔만, DB 불요).
    """
    for rel in _CONCEPT_EDGE_TRAVERSAL_SRC_FILES:
        path = _REPO_ROOT / rel
        assert path.is_file(), f"concept_edge traversal 소스 부재(스캔 대상 확인 필요): {rel}"
        src = path.read_text(encoding="utf-8")
        assert "misconception_relation" not in src, (
            f"{rel}가 misconception_relation을 참조 — 오개념 관계셋이 개념 traversal에 "
            "진입했다(04e §2-3 불변식 위반). misconception_relation은 reactive 조회 전용이며 "
            "concept_edge 순회 엔진과 join되면 안 된다."
        )


# ──────────────────────────────────────────────────────────────────────────
# Level 5 — 런타임 게이트 기본값이 reactive(off·opt-in)
# ──────────────────────────────────────────────────────────────────────────
def test_runtime_gate_defaults_are_reactive() -> None:
    """의미 매칭·judge 노출 게이트 기본값 동결 — off·False(substring 우선·reactive·Level 5).

    env 무관하게 *Field 기본값*을 읽는다(런타임 Settings 인스턴스가 아니라 선언 기본).
    """
    fields = Settings.model_fields
    assert fields["misconception_semantic_mode"].default == "off"
    assert fields["misconception_judge_enabled"].default is False


# ──────────────────────────────────────────────────────────────────────────
# 연결 무결성 — 명세가 근거로 든 기존 방어·문서가 실재
# ──────────────────────────────────────────────────────────────────────────
def test_referenced_guard_tests_exist() -> None:
    """04c 감사·갭 장부가 인용한 기존 동결 테스트들이 저장소에 실재한다(근거 무결성)."""
    for rel in _REFERENCED_GUARD_TESTS:
        assert (_REPO_ROOT / rel).is_file(), f"명세가 인용한 방어 테스트 부재: {rel}"


def test_spec_document_exists() -> None:
    """정본 7레벨 명세 문서 자체가 실재한다(이 manifest의 대응 문서)."""
    assert (_REPO_ROOT / _SPEC_DOC).is_file(), f"7레벨 정본 명세 부재: {_SPEC_DOC}"
