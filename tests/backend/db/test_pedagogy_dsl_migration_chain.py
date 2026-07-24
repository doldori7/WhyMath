"""교수법 DSL 마이그레이션 체인 단위테스트 — 리비전 링크 검증(hermetic·PG 0).

검토서 H3: L2(evidence_event)와 L3(pedagogy pack/content)를 *별 리비전 2건*으로 분리·
현재 head(c4d5e6f0a1b2) 위에 순서대로 얹었는지 잠근다. alembic upgrade는 실행하지 않는다(PG 부재).
리비전 모듈을 파일 경로로 로드해 revision/down_revision 상수만 검사한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

def _find_versions_dir() -> Path:
    """저장소 루트를 위로 탐색해 alembic versions 디렉터리를 찾는다(수집 위치 무관·robust)."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "src" / "backend" / "alembic" / "versions"
        if candidate.is_dir():
            return candidate
    raise AssertionError("alembic versions 디렉터리를 찾지 못했다")


_VERSIONS = _find_versions_dir()
_REV_A = _VERSIONS / "20260724_1200_d5e6f0a1b2c3_pedagogy_pack_dsl.py"
_REV_B = _VERSIONS / "20260724_1210_e6f1a2b3c4d5_evidence_event.py"

# 현재 head(검토서 부록 A-1·strategy_node_projection).
_CURRENT_HEAD = "c4d5e6f0a1b2"


def _load(path: Path) -> ModuleType:
    """리비전 파일을 파일 경로로 import(패키지 아님·상수만 읽는다)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_revision_files_exist() -> None:
    """L2·L3 리비전 파일이 각각 존재한다(H3 — 별 리비전 2건)."""
    assert _REV_A.exists()
    assert _REV_B.exists()


def test_rev_a_down_revision_is_current_head() -> None:
    """L3(pedagogy_pack_dsl) down_revision은 현재 head(c4d5e6f0a1b2)다."""
    a = _load(_REV_A)
    assert a.revision == "d5e6f0a1b2c3"
    assert a.down_revision == _CURRENT_HEAD


def test_rev_b_stacks_on_rev_a() -> None:
    """L2(evidence_event) down_revision은 L3 리비전(d5e6f0a1b2c3)이다(순서·계층 분리)."""
    b = _load(_REV_B)
    assert b.revision == "e6f1a2b3c4d5"
    assert b.down_revision == "d5e6f0a1b2c3"


def test_revisions_are_distinct() -> None:
    """두 리비전 해시가 서로 다르다(별 리비전 2건 보장)."""
    a, b = _load(_REV_A), _load(_REV_B)
    assert a.revision != b.revision


def test_knowledge_type_enum_labels_match_across_revisions() -> None:
    """두 리비전이 참조하는 knowledge_type enum 라벨 7종이 동일하다(값 일치)."""
    a, b = _load(_REV_A), _load(_REV_B)
    assert a.knowledge_type_enum.name == "knowledge_type"
    assert b.knowledge_type_enum.name == "knowledge_type"
    assert list(a.knowledge_type_enum.enums) == list(b.knowledge_type_enum.enums)
    assert len(a.knowledge_type_enum.enums) == 7
