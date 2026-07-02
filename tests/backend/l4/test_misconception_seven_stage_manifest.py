"""정본 7단계 분리 manifest 동결 — 명세(`docs/architecture/04c…`)↔코드 드리프트 차단.

`04c_misconception_seven_stage_separation.md`가 "개념 ↔ 오개념이 7단계에서 분리된다"고 열거한
각 앵커(모듈·테이블·기존 동결 테스트·게이트 기본값)가 *실제로 존재*함을 확인한다. 이 테스트는
기존 governance 테스트(namespace·purity·runtime)의 단언을 **중복하지 않는다** — 그 방어들이
저장소에 *실재*한다는 연결 무결성과, 명세가 이름 댄 앵커가 *import/존재 가능*하다는 것만 동결한다.

명세를 바꾸면(단계 추가·앵커 이동) 이 테스트가 red가 되어 문서와 코드가 함께 움직이도록 강제한다.

hermetic: 외부 의존·DB 불요(모듈 import·ORM 메타데이터·파일 존재·Field 기본값만).
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

# 저장소 루트 — 이 파일: tests/backend/l4/…  →  parents[3] = repo root(tests·docs 보유).
_REPO_ROOT = Path(__file__).resolve().parents[3]


# ──────────────────────────────────────────────────────────────────────────
# 단계 1~7 앵커 모듈 — 04c §2 표의 "구현 앵커"(dotted path). 전부 import 가능해야 한다.
# (명세가 이름 댄 좌석이 실재하는지 — 좌석이 사라지면 명세가 거짓말이 된다.)
# ──────────────────────────────────────────────────────────────────────────
_STAGE_ANCHOR_MODULES: dict[int, tuple[str, ...]] = {
    1: (  # Storage / DB
        "whymath_backend.db.models.misconception_catalog",
        "whymath_backend.db.models.misconception_hypothesis",
        "whymath_backend.db.models.misconception_crosslink",
        "whymath_backend.db.models.misconception_embedding",
    ),
    2: (  # Retrieval
        "whymath_backend.l4.misconception.diagnose",
        "whymath_backend.l4.misconception.combined",
    ),
    3: (  # Embedding index
        "whymath_backend.l4.misconception.semantic.pgvector_index",
        "whymath_backend.l1.concept_graph.embedding",
        "whymath_backend.l1.atom_graph.embedding",
    ),
    4: (  # Context (LLM)
        "whymath_backend.api.coach",
        "whymath_backend.harness.wh1_loop",
    ),
    5: (  # Runtime / detection gate
        "whymath_backend.l4.misconception.match_gate",
        "whymath_backend.api._misconception_state",
    ),
    6: (  # Judge / Validation
        "whymath_backend.l4.misconception.judge",
        "whymath_backend.l4.misconception.judge_seam",
    ),
    7: (  # Identity / Canonical
        "whymath_backend.l4.misconception.catalog",
        "whymath_backend.l1.misconception.crosslink_resolve",
    ),
}

# 오개념 4 ORM 테이블(단계 1) — 개념 테이블과 disjoint·개념에 FK 결합 안 됨을 확인할 대상.
_MISCONCEPTION_MODELS = (
    MisconceptionCatalog,
    MisconceptionHypothesisRecord,
    MisconceptionCrosslink,
    MisconceptionEmbedding,
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

# 항목 ①③·preload 동결을 담당하는 *기존* 방어 — 명세가 "존재한다"고 주장한 테스트들의 실재 확인
# (repo 상대경로). 이들이 사라지면 04c 감사 결과표가 근거를 잃는다.
_REFERENCED_GUARD_TESTS = (
    "tests/data_pipeline/concept_graph/test_concept_node_purity.py",
    "tests/backend/schema/test_concept_misconception_runtime.py",
    "tests/backend/l1/test_embedding_namespace_governance.py",
    "tests/backend/l4/test_misconception_namespace_gate.py",
)

# 명세 문서 자체.
_SPEC_DOC = "docs/architecture/04c_misconception_seven_stage_separation.md"


# ──────────────────────────────────────────────────────────────────────────
# 단계 1~7 — 앵커 모듈 전수 import
# ──────────────────────────────────────────────────────────────────────────
def test_all_seven_stages_are_enumerated() -> None:
    """명세는 정확히 7단계다(체크리스트 5 + 구현 2층 = 7·04c §0)."""
    assert set(_STAGE_ANCHOR_MODULES) == set(range(1, 8))


def test_every_stage_anchor_module_importable() -> None:
    """7단계 각 앵커 모듈이 import 가능 — 명세가 이름 댄 좌석이 실재한다.

    소실 시 `importlib.import_module`이 ImportError로 즉시 red(해당 단계 앵커 소실).
    """
    for modules in _STAGE_ANCHOR_MODULES.values():
        for dotted in modules:
            importlib.import_module(dotted)


# ──────────────────────────────────────────────────────────────────────────
# 단계 1 — 오개념 테이블 분리(개념과 disjoint·FK 비결합)
# ──────────────────────────────────────────────────────────────────────────
def test_misconception_tables_disjoint_from_concept_tables() -> None:
    """오개념 4테이블명이 개념 측 테이블명과 겹치지 않는다(별도 store)."""
    mis_tables = {m.__tablename__ for m in _MISCONCEPTION_MODELS}
    assert mis_tables == {
        "misconception_catalog",
        "misconception_hypothesis",
        "misconception_crosslink",
        "misconception_embedding",
    }
    assert mis_tables.isdisjoint(_CONCEPT_TABLE_NAMES)


def test_misconception_tables_have_no_foreign_key_into_concept() -> None:
    """오개념 테이블의 어떤 FK도 개념 측 테이블을 가리키지 않는다(loose ref — 04c §2 단계 1).

    오개념→개념 참조는 `concept_src_id`(원천 문자열)·kebab-id 같은 *느슨참조*로만 존재하고 DB
    FK로 개념 identity에 결합되지 않는다(개념↔오개념 결합 폭발·순환 차단). 허용 FK 타깃은
    오개념 도메인 내부(`misconception_catalog`)·학생(`user_profile`)뿐이다.
    """
    for model in _MISCONCEPTION_MODELS:
        referenced = {fk.column.table.name for fk in model.__table__.foreign_keys}
        offenders = referenced & _CONCEPT_TABLE_NAMES
        assert offenders == set(), (
            f"{model.__tablename__}가 개념 테이블에 FK 결합됨 — {sorted(offenders)}. 오개념은 "
            "개념에 느슨참조(원천 문자열)로만 이어야 한다(04c 단계 1·Concept Purity)."
        )


# ──────────────────────────────────────────────────────────────────────────
# 단계 5 — 런타임 게이트 기본값이 reactive(off·opt-in)
# ──────────────────────────────────────────────────────────────────────────
def test_runtime_gate_defaults_are_reactive() -> None:
    """의미 매칭·judge 노출 게이트 기본값 동결 — off·False(substring 우선·reactive·04c 단계 5).

    env 무관하게 *Field 기본값*을 읽는다(런타임 Settings 인스턴스가 아니라 선언 기본).
    """
    fields = Settings.model_fields
    assert fields["misconception_semantic_mode"].default == "off"
    assert fields["misconception_judge_enabled"].default is False


# ──────────────────────────────────────────────────────────────────────────
# 연결 무결성 — 명세가 근거로 든 기존 방어·문서가 실재
# ──────────────────────────────────────────────────────────────────────────
def test_referenced_guard_tests_exist() -> None:
    """04c 감사 결과표가 인용한 기존 동결 테스트들이 저장소에 실재한다(근거 무결성)."""
    for rel in _REFERENCED_GUARD_TESTS:
        assert (_REPO_ROOT / rel).is_file(), f"명세가 인용한 방어 테스트 부재: {rel}"


def test_spec_document_exists() -> None:
    """정본 7단계 명세 문서 자체가 실재한다(이 manifest의 대응 문서)."""
    assert (_REPO_ROOT / _SPEC_DOC).is_file(), f"7단계 정본 명세 부재: {_SPEC_DOC}"
