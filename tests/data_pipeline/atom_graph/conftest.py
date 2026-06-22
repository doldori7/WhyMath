"""atom_graph 테스트 공통 픽스처 — 작은 합성 행 + 실 코퍼스 로더.

상위 tests/data_pipeline/conftest.py가 sys.path(소스 우선)를 설정한 뒤 이 파일이 로드된다.
단위테스트는 *작은 합성 행 dict*(실 xlsx 아님)로 transform/validate/models를 검증한다 — 실데이터
정합성은 코퍼스 산출(data/corpus/atom_graph_v1/graph.json) + _provenance로 확인한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/data_pipeline/atom_graph/conftest.py → parents[3] = 프로젝트 루트.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = _PROJECT_ROOT / "data" / "corpus" / "atom_graph_v1"
STANDARDS_PATH = _PROJECT_ROOT / "data" / "corpus" / "standards_v1" / "standards.json"
UNIV_STANDARDS_PATH = (
    _PROJECT_ROOT / "data" / "corpus" / "standards_university_v1" / "standards.json"
)


def _atom_row(**over: object) -> dict[str, object]:
    """원자_통합마스터 한 행(합성 — 헤더 키). K-12 초등 원자(핵심명제=NCIC 본문 redact 대상)."""
    base: dict[str, object] = {
        "순번": "1",
        "출처": "초중고",
        "교육과정": "2022개정",
        "학교급": "초등학교",
        "학년/학년군": "1~2학년군",
        "영역/과목": "수와 연산",
        "단원": "수와 연산",
        "소단원": "100까지의 수와 세기",
        "소단원코드": "초수연-U1-S1",
        "원자ID": "2수01-01-1",
        "원자명": "일대일 대응으로 세기",
        "원자명_표시": "일대일 대응으로 세기",
        "인지축": "절차",
        "노드유형": "선행",
        "오개념유형": "절차오류",
        "난이도": "1",
        "연결성취기준": "[2수01-01]",
        "핵심명제/성취기준내용": "수의 필요성을 인식하면서 0과 100까지의 수 개념을 이해한다.",
        "①오개념": "셀 때 빠뜨림",
        "②진단문항": "별 7개를 세어 보세요.",
        "②정답·통과기준": "정답: 7개",
        "②미통과·오답신호": "6/8 누락",
        "③소크라테스질문": "다시 세도 또 7일까?",
        "④전이": "대응시키는 세기",
        "④전이예시": "연필 세기",
        "선수원자": "없음",
        "원자성a": "예",
        "원자성b": "예",
        "원자성c": "예",
        "원자성d": "예",
        "비고": "",
    }
    base.update(over)
    return base


@pytest.fixture()
def atom_row() -> dict[str, object]:
    """단일 합성 원자 행(K-12 초등)."""
    return _atom_row()


@pytest.fixture()
def make_atom_row():  # type: ignore[no-untyped-def]
    """오버라이드 가능한 원자 행 팩토리."""
    return _atom_row


@pytest.fixture(scope="session")
def corpus_graph() -> dict[str, object]:
    """실 코퍼스 graph.json(코퍼스 생성 후 존재). 없으면 skip."""
    path = CORPUS_DIR / "graph.json"
    if not path.exists():
        pytest.skip(f"코퍼스 미생성: {path} — transform-v1 --output-dir로 생성 후 실행")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="session")
def corpus_provenance() -> dict[str, object]:
    """실 코퍼스 _provenance.json. 없으면 skip."""
    path = CORPUS_DIR / "_provenance.json"
    if not path.exists():
        pytest.skip(f"코퍼스 미생성: {path}")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="session")
def standards_codes() -> set[str]:
    """유효 성취기준 code 집합 — K-12(standards_v1) ∪ 대학(standards_university_v1·U1 이후).

    원자 standard_codes는 K-12 NCIC 코드(`[2수01-01]`)와 대학 자체작성 코드(`[CALC1-01-01]`·U2에서
    대학 원자에 채움)를 모두 포함하므로, 두 코퍼스의 code 합집합으로 검증한다(대학 코퍼스 미생성
    시 K-12만)."""
    if not STANDARDS_PATH.exists():
        pytest.skip(f"standards.json 없음: {STANDARDS_PATH}")
    payload = json.loads(STANDARDS_PATH.read_text(encoding="utf-8"))
    codes = {str(s["code"]) for s in payload.get("standards", [])}
    if UNIV_STANDARDS_PATH.exists():
        univ = json.loads(UNIV_STANDARDS_PATH.read_text(encoding="utf-8"))
        codes |= {str(s["code"]) for s in univ.get("standards", [])}
    return codes
