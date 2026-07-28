"""standards_university 테스트 공통 픽스처 — 합성 대학 성취기준 행 + 실 코퍼스 로더.

상위 tests/data_pipeline/conftest.py가 sys.path(소스 우선)를 설정한 뒤 로드된다. 단위테스트는
*작은 합성 행 dict*(실 xlsx 아님)로 transform/validate/models를 검증하고, 실데이터 정합성은
코퍼스 산출(data/corpus/standards_university_v1/) + _provenance로 확인한다(atom_graph 미러).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/data_pipeline/standards_university/conftest.py → parents[3] = 프로젝트 루트.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = _PROJECT_ROOT / "data" / "corpus" / "standards_university_v1"


def _univ_std_row(**over: object) -> dict[str, object]:
    """`성취기준_목록` 대학 한 행(합성 — 업로드 헤더 키). 갈루아 이론 분해체 예."""
    base: dict[str, object] = {
        "키": "대학|[GALOIS-01-01]",
        "교육과정": "대학",
        "학교급": "대학교",
        "구분": "4학년",
        "학년군·과목": "갈루아 이론",
        "영역(단원)": "체확장 복습",
        "소단원(개념)": "분해체",
        "성취기준 코드": "[GALOIS-01-01]",
        "성취기준 내용": "f의 분해체는 f가 일차로 분해되는 최소 확장(ℂ 전체 아님).",
        "성취기준 요약(간결)": "분해체는 근을 다 담는 최소 체",
        "개념ID": "GALOIS-U1-S1",
        "개념명(개념그래프)": "분해체",
        "매칭 CCSS": "-",
        "개정": "대학",
        "과목약칭": "GALOIS",
        "영역": "01",
        "일련": "01",
        "norm_id": "대학_GALOIS_01_01",
    }
    base.update(over)
    return base


@pytest.fixture()
def univ_std_row() -> dict[str, object]:
    """단일 합성 대학 성취기준 행."""
    return _univ_std_row()


@pytest.fixture()
def make_univ_std_row():  # type: ignore[no-untyped-def]
    """오버라이드 가능한 대학 성취기준 행 팩토리."""
    return _univ_std_row


@pytest.fixture(scope="session")
def corpus_standards() -> dict[str, object]:
    """실 대학 성취기준 코퍼스 standards.json(코퍼스 생성 후 존재). 없으면 skip."""
    path = CORPUS_DIR / "standards.json"
    if not path.exists():
        pytest.skip(f"코퍼스 미생성: {path} — `python -m data_pipeline.standards_university` 실행")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="session")
def corpus_links() -> dict[str, object]:
    """실 대학 성취기준 링크 코퍼스. 없으면 skip."""
    path = CORPUS_DIR / "concept_standard_links.json"
    if not path.exists():
        pytest.skip(f"코퍼스 미생성: {path}")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="session")
def corpus_provenance() -> dict[str, object]:
    """실 대학 성취기준 _provenance.json. 없으면 skip."""
    path = CORPUS_DIR / "_provenance.json"
    if not path.exists():
        pytest.skip(f"코퍼스 미생성: {path}")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
