"""concept_graph 테스트 공통 픽스처 — 데이터셋 v1 실데이터 로더.

상위 tests/data_pipeline/conftest.py가 sys.path(소스 우선)·통합 게이트를 설정한 뒤 이 파일이
로드된다. 여기서는 실데이터(data/corpus/concept_graph_v1/*.jsonl) 경로·레코드 픽스처만 제공한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/data_pipeline/concept_graph/conftest.py → parents[3] = 프로젝트 루트.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = _PROJECT_ROOT / "data" / "corpus" / "concept_graph_v1"


def _load_jsonl(name: str) -> list[dict[str, object]]:
    """corpus 디렉토리의 jsonl → dict 목록(빈 줄 무시)."""
    path = CORPUS_DIR / name
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    """데이터셋 v1 디렉토리 경로(CLI 테스트용)."""
    return CORPUS_DIR


@pytest.fixture(scope="session")
def concept_records() -> list[dict[str, object]]:
    """concepts.jsonl 전체(403행)."""
    return _load_jsonl("concepts.jsonl")


@pytest.fixture(scope="session")
def edge_records() -> list[dict[str, object]]:
    """prerequisite_edges.jsonl 전체(541행)."""
    return _load_jsonl("prerequisite_edges.jsonl")


@pytest.fixture(scope="session")
def flashcard_records() -> list[dict[str, object]]:
    """flashcards.jsonl 전체(113행)."""
    return _load_jsonl("flashcards.jsonl")


@pytest.fixture(scope="session")
def intl_records() -> list[dict[str, object]]:
    """ccss_only_intl.jsonl 전체(13행)."""
    return _load_jsonl("ccss_only_intl.jsonl")
