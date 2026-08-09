"""텍스트 풀이 → 단계 분해 Golden Test (`segment_solution_text`, NLP-03·D3).

`data/segmentation_contract.json`(백엔드·모바일 공유 fixture)을 읽어 `segment_solution_text`가
계약의 모든 케이스에 동의하는지 검증한다. 모바일 `_splitSteps`/`_unwrapDisplaylines`가 *같은
fixture*로 클라 측을 검증해, 두 구현이 같은 입력에 같은 판정을 냄을 교차 보증한다
(`tests/backend/l3/test_notation_contract.py` 선례와 동형 패턴).

계약 파일이 없거나 파싱 불가면 조용히 skip하지 않고 명확히 실패한다(CLAUDE.md 침묵 실패 금지)
— 모듈 임포트 시점에 로드해 수집 단계에서부터 실패가 드러나게 한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l5.ocr.text_segmentation import segment_solution_text

# tests/backend/l5/ocr/ → parents[4] = 레포 루트(tests/backend/l3/test_notation_contract.py의
# parents[3] 기준과 동일 원리 — 이 파일은 한 단계 더 깊은 디렉터리라 parents[4]).
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _PROJECT_ROOT / "data" / "segmentation_contract.json"


def _load_contract() -> dict[str, Any]:
    """계약 JSON을 로드 — 없거나 파싱 불가면 명확히 실패(조용한 skip 금지)."""
    if not _FIXTURE.exists():
        raise FileNotFoundError(
            f"단계 분해 계약 fixture 없음: {_FIXTURE} — data/segmentation_contract.json은 "
            "레포에 이미 존재해야 한다(NLP-03 사전 조건)."
        )
    text = _FIXTURE.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"단계 분해 계약 fixture 파싱 실패: {_FIXTURE} ({exc})") from exc


_CONTRACT = _load_contract()
_CASES = _CONTRACT["cases"]


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_segment_solution_text_matches_contract(case: dict[str, Any]) -> None:
    """계약의 각 케이스에 대해 steps·ambiguous가 정확히 일치(교차 골든)."""
    result = segment_solution_text(case["input"])
    assert result.steps == tuple(
        case["steps"]
    ), f"{case['id']}: steps={result.steps!r} (expected={tuple(case['steps'])!r})"
    assert (
        result.ambiguous == case["ambiguous"]
    ), f"{case['id']}: ambiguous={result.ambiguous} (expected={case['ambiguous']})"


def test_contract_has_at_least_the_known_regression_cases() -> None:
    """계약에 2026-07-20 회귀 케이스(displaylines 언더스플릿)가 실재하는지 확인.

    이 단언은 `segment_solution_text`가 아니라 계약 fixture 자체의 무결성 확인이다.
    """
    ids = {c["id"] for c in _CASES}
    assert "displaylines_two_rows" in ids
    assert "displaylines_undersplit_is_ambiguous" in ids
