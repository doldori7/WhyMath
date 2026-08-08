"""`problem_corpus_review_status_backfill.verdict_from_audit_labels` 결정 로직 단위 테스트(PB-03).

`corpus_audit_eval`(단일 권위)의 판정 규칙 4갈래(라벨 없음/min-n 미달/결함율 상한 이하/초과)가
review_status 매핑으로 정확히 이어지는지 확인한다 — 학생 노출 여부를 가르는 핵심 로직이라
hermetic이어도 반드시 직접 검증한다(문서에만 서술하고 테스트가 없는 상태를 남기지 않는다).
"""

from __future__ import annotations

import json

from whymath_backend.harness.problem_corpus_review_status_backfill import (
    verdict_from_audit_labels,
)
from whymath_backend.schema.enums import ReviewStatus


def _labels_jsonl(n_ok: int, n_defect: int) -> str:
    lines = [json.dumps({"problem_id": f"p{i}", "verdict": "ok"}) for i in range(n_ok)]
    lines += [json.dumps({"problem_id": f"d{i}", "verdict": "defect"}) for i in range(n_defect)]
    return "\n".join(lines)


class TestVerdictFromAuditLabels:
    def test_no_label_file_is_pending(self) -> None:
        """감사 라벨 파일 자체가 없으면(probability_finite_v0·v1) 평가 시도 없이 pending."""
        verdict = verdict_from_audit_labels(None, label_path=None)
        assert verdict.review_status == ReviewStatus.pending
        assert verdict.n is None
        assert "없음" in verdict.reason

    def test_below_min_n_is_pending_even_with_zero_defects(self) -> None:
        """표본 n < 200이면 결함 0건이어도 pending(killer_v0류 — 증거 부족, FAIL 아님)."""
        text = _labels_jsonl(n_ok=120, n_defect=0)
        verdict = verdict_from_audit_labels(text, label_path="fake.jsonl")
        assert verdict.review_status == ReviewStatus.pending
        assert verdict.n == 120
        assert "min_n" in verdict.reason

    def test_at_min_n_with_low_defect_rate_is_approved(self) -> None:
        """n>=200이고 Wilson 95% 상한 <= 0.02면 approved."""
        text = _labels_jsonl(n_ok=240, n_defect=0)
        verdict = verdict_from_audit_labels(text, label_path="fake.jsonl")
        assert verdict.review_status == ReviewStatus.approved
        assert verdict.n == 240
        assert verdict.upper_bound is not None
        assert verdict.upper_bound <= 0.02

    def test_high_defect_rate_is_rejected(self) -> None:
        """n>=200이고 Wilson 95% 상한 > 0.02면 rejected(전수 검수 복귀)."""
        text = _labels_jsonl(n_ok=176, n_defect=24)  # 12% 점추정 — 상한이 2%를 크게 초과
        verdict = verdict_from_audit_labels(text, label_path="fake.jsonl")
        assert verdict.review_status == ReviewStatus.rejected
        assert verdict.n == 200
        assert verdict.upper_bound is not None
        assert verdict.upper_bound > 0.02

    def test_verdict_always_carries_reason_and_label_path(self) -> None:
        """조용한 판정 금지 — 4갈래 전부 reason이 비어있지 않고 label_path가 그대로 보존된다."""
        for verdict in (
            verdict_from_audit_labels(None, label_path=None),
            verdict_from_audit_labels(_labels_jsonl(120, 0), label_path="a.jsonl"),
            verdict_from_audit_labels(_labels_jsonl(240, 0), label_path="b.jsonl"),
            verdict_from_audit_labels(_labels_jsonl(176, 24), label_path="c.jsonl"),
        ):
            assert verdict.reason
        assert (
            verdict_from_audit_labels(_labels_jsonl(240, 0), label_path="b.jsonl").label_path
            == "b.jsonl"
        )
