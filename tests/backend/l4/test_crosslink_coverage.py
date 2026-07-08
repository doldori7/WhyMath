"""crosslink_coverage 단위테스트 — 커버리지 분류·요약(read-only·판정 없음).

hermetic: 합성 검수 큐 행 + 주입 카탈로그 → 분류(DB·네트워크·파일 불요).
"""

from __future__ import annotations

import json

from whymath_backend.l4.misconception.crosslink_coverage import (
    build_coverage,
    format_coverage,
    summarize_coverage,
)
from whymath_backend.l4.misconception.crosslink_review import CrosslinkReviewItem

# 값은 안 쓰이고 멤버십(키)만 쓰인다 — build_coverage는 kebab_id ∈ 카탈로그만 본다.
_CATALOG: dict[str, object] = {
    "k_cover": None,
    "k_below": None,
    "k_tie": None,
    "k_nodirect": None,
    "k_none": None,
}


def _item(**overrides: object) -> CrosslinkReviewItem:
    base: dict[str, object] = {
        "kebab_id": "k_cover",
        "mis_id": "M1",
        "link_type": "직접매핑",
        "confidence": 0.9,
        "rationale": "r",
        "status": "pending",
    }
    base.update(overrides)
    return CrosslinkReviewItem.model_validate(base)


def _cov() -> list:
    items = [
        _item(kebab_id="k_cover", mis_id="M1", link_type="직접매핑", confidence=0.9),
        _item(kebab_id="k_below", mis_id="M2", link_type="직접매핑", confidence=0.5),
        _item(kebab_id="k_tie", mis_id="M3", link_type="직접매핑", confidence=0.8),
        _item(kebab_id="k_tie", mis_id="M4", link_type="직접매핑", confidence=0.8),
        _item(kebab_id="k_nodirect", mis_id="M5", link_type="부분매핑", confidence=0.9),
        # k_none: 큐 행 없음 → no_candidate(카탈로그엔 있음)
    ]
    return build_coverage(items, catalog=_CATALOG, statuses=("pending",))


def test_classification_by_kebab() -> None:
    """각 시나리오가 의도한 분류로 떨어진다(coverable/below/tie/no_direct/no_candidate)."""
    by_id = {c.kebab_id: c for c in _cov()}
    assert by_id["k_cover"].classification == "coverable"
    assert by_id["k_cover"].canonical_mis_id == "M1"
    assert by_id["k_below"].classification == "below_threshold"  # reason ok이나 conf<0.6
    assert by_id["k_below"].promotable_direct_count == 0
    assert by_id["k_tie"].classification == "ambiguous_tie"
    assert by_id["k_tie"].ambiguous is True
    assert by_id["k_nodirect"].classification == "no_direct"
    assert by_id["k_none"].classification == "no_candidate"
    assert by_id["k_none"].candidate_count == 0


def test_summary_counts_and_signals() -> None:
    """요약이 분류별 카운트·검수 신호 목록을 집계한다."""
    summary = summarize_coverage(_cov(), statuses=("pending",))
    assert summary.counts["coverable"] == 1
    assert summary.counts["below_threshold"] == 1
    assert summary.counts["ambiguous_tie"] == 1
    assert summary.counts["no_direct"] == 1
    assert summary.counts["no_candidate"] == 1
    assert summary.no_candidate == ["k_none"]
    assert summary.ambiguous_tie == ["k_tie"]
    assert summary.below_threshold == ["k_below"]
    assert summary.not_in_catalog == []


def test_kebab_not_in_catalog_flagged() -> None:
    """큐에만 있고 카탈로그 밖인 kebab은 not_in_catalog로 드러난다(전사 왜곡 신호)."""
    items = [_item(kebab_id="ghost", mis_id="M9", link_type="직접매핑", confidence=0.9)]
    cov = build_coverage(items, catalog=_CATALOG, statuses=("pending",))
    ghost = next(c for c in cov if c.kebab_id == "ghost")
    assert ghost.in_catalog is False
    assert summarize_coverage(cov, statuses=("pending",)).not_in_catalog == ["ghost"]


def test_format_last_line_is_json_summary() -> None:
    """리포트 마지막 줄은 파싱 가능한 요약 JSON(harvest 규약·회귀 스냅샷)."""
    report = format_coverage(_cov(), statuses=("pending",))
    last = report.splitlines()[-1]
    parsed = json.loads(last)
    assert parsed["counts"]["coverable"] == 1
    assert "no_candidate" in parsed
