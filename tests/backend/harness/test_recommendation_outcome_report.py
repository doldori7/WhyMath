"""추천 폐루프 회계 리포트 테스트 — 결정론·정직 회계(hermetic, REC-03 acceptance③).

`build_report`는 순수 함수라 실 DB 없이 정수 카운트만으로 검증한다. 핵심 관심사는 "0건"이
"효과 없음"으로 읽히지 않도록 결과 미결합 사유가 항상 함께 렌더되는가다.
"""

from __future__ import annotations

import json

from whymath_backend.harness import recommendation_outcome_report as ror


def test_build_report_reflects_treatment_count() -> None:
    report = ror.build_report(7)
    assert report.treatment_count == 7


def test_outcome_linked_count_is_always_zero_with_reason() -> None:
    """결합 배선 자체가 없다는 구조적 사실 — 처치 건수와 무관하게 항상 0 + 사유 병기."""
    report = ror.build_report(100)
    assert report.outcome_linked_count == 0
    assert "session_id" in report.outcome_not_wired_reason
    assert "S3-01" in report.outcome_not_wired_reason


def test_render_report_distinguishes_zero_treatment_from_no_wiring() -> None:
    rendered = ror.render_report(ror.build_report(0))
    assert "처치" in rendered
    assert "결과 결합 건수" in rendered
    assert "효과 없음" in rendered  # 오독 방지 경고 문구가 렌더에 포함돼야 한다


def test_render_report_shows_nonzero_treatment_count() -> None:
    rendered = ror.render_report(ror.build_report(42))
    assert "42" in rendered


def test_report_to_json_roundtrips() -> None:
    report = ror.build_report(3)
    payload = ror.report_to_json(report)
    roundtripped = json.loads(json.dumps(payload, ensure_ascii=False))
    assert roundtripped == payload
    assert roundtripped["treatment_count"] == 3
    assert roundtripped["outcome_linked_count"] == 0


def test_dump_json_produces_valid_json() -> None:
    dumped = ror.dump_json(ror.build_report(1))
    parsed = json.loads(dumped)
    assert parsed["treatment_count"] == 1
