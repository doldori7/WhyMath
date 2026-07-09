"""crosswalk 기계 자율 거부 테스트 — 측정 안전 구간의 cross-standard 거부(순수·hermetic).

거부 전용(승인 절대 없음)·증거 하한·pending 한정·봉인 무손상·커밋 큐 e2e를 동결한다.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.l4.misconception.crosslink_machine_reject import (
    machine_reject_candidates,
    run,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_KEBAB_STANDARDS = {
    "opposite-root-selected": frozenset({"[10공수1-02-02]"}),
    "extremum-max-min-confused": frozenset({"[12미적Ⅰ-02-07]"}),
}
_KEBAB_COUNTS = {"opposite-root-selected": 130, "extremum-max-min-confused": 60}
_MID_STANDARDS: dict[str, str | None] = {
    "M0862": "[10공수1-02-02]",  # agree(opposite-root)
    "M0900": "[12미적Ⅰ-02-07]",  # cross for opposite-root
}


def _queue(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"review_queue": rows}


def _row(kebab: str, mis: str, status: str = "pending") -> dict[str, object]:
    return {
        "kebab_id": kebab,
        "mis_id": mis,
        "link_type": "직접매핑",
        "confidence": 0.9,
        "rationale": "테스트",
        "status": status,
    }


class TestMachineRejectCandidates:
    def test_rejects_cross_standard_pending(self) -> None:
        q = _queue(
            [_row("opposite-root-selected", "M0900")]
        )  # cross-standard·well-evidenced
        out = machine_reject_candidates(
            queue=q,
            kebab_standards=_KEBAB_STANDARDS,
            kebab_counts=_KEBAB_COUNTS,
            mid_standards=_MID_STANDARDS,
            evidence_floor=20,
        )
        assert [(r.kebab_id, r.mis_id) for r in out] == [
            ("opposite-root-selected", "M0900")
        ]

    def test_never_rejects_agreeing_mapping(self) -> None:
        # 성취기준 일치(정답 방향)는 거부 목록에 없음 — 승인은 인간 존치(기계 approve 0).
        q = _queue([_row("opposite-root-selected", "M0862")])
        out = machine_reject_candidates(
            queue=q,
            kebab_standards=_KEBAB_STANDARDS,
            kebab_counts=_KEBAB_COUNTS,
            mid_standards=_MID_STANDARDS,
            evidence_floor=20,
        )
        assert out == []

    def test_skips_non_pending_rows(self) -> None:
        # 사람이 이미 판정한 행(approved/rejected)은 불변(기계가 덮지 않음).
        q = _queue([_row("opposite-root-selected", "M0900", status="approved")])
        out = machine_reject_candidates(
            queue=q,
            kebab_standards=_KEBAB_STANDARDS,
            kebab_counts=_KEBAB_COUNTS,
            mid_standards=_MID_STANDARDS,
            evidence_floor=20,
        )
        assert out == []


class TestCommittedQueueEndToEnd:
    def test_exact_machine_rejections_on_real_data(self) -> None:
        # 커밋 큐+코퍼스 e2e — 정확히 4건·thin 제외. distribution MC 코퍼스가 그 kebab을
        # well-evidenced([9수02-19] 곱셈공식)로 승격 → 지수법칙 부분매핑 M0649가 cross-standard로
        # 자동 거부에 추가(직접매핑 M0019/M0572는 [9수02-19] agree라 인간 존치). product-rule MC는
        # 미적Ⅰ 미분·도함수 태깅 → 합성함수 부분매핑 M0424가 cross-standard로 자동 거부(곱미분≠합성·
        # 정당). chain-rule/translation은 다표준 태깅이라 후보 모두 agree → 거부 0(거짓거부 회피).
        rejections = run(
            queue_path=_REPO_ROOT
            / "docs"
            / "data"
            / "misconception_crosslink_review_queue.json",
            corpora=sorted(
                (_REPO_ROOT / "data" / "corpus").glob("problem_bank_*/problems.jsonl")
            ),
            misconceptions=_REPO_ROOT
            / "data"
            / "corpus"
            / "misconceptions_v1"
            / "misconceptions.json",
            evidence_floor=20,
        )
        pairs = {(r.kebab_id, r.mis_id) for r in rejections}
        assert pairs == {
            ("opposite-root-selected", "M0831"),
            ("factor-sign-flip", "M0848"),
            ("distribution-over-power", "M0649"),
            ("product-rule-naive", "M0424"),
        }
        # chain-rule/translation은 다표준 태깅이라 자동 거부 0(거짓거부 회피).
        assert all(
            r.kebab_id != "chain-rule-inner-derivative-omitted" for r in rejections
        )
        assert all(r.kebab_id != "translation-sign-flip" for r in rejections)
        # 개념형 개수/판정 5 kebab도 후보 전부 agree 태깅이라 자동 거부 0(거짓거부 회피).
        for kebab in (
            "invertibility-without-1-1",
            "geometric-series-always-converges",
            "limit-equals-function-value",
            "continuity-implies-differentiability",
            "term-to-zero-implies-convergence",
        ):
            assert all(r.kebab_id != kebab for r in rejections)
        # thin-evidence(root-loss-by-dividing, 1문항)은 제외.
        assert all(r.kebab_id != "root-loss-by-dividing" for r in rejections)
        # 전부 well-evidenced(≥20).
        assert all(r.kebab_problem_count >= 20 for r in rejections)

    def test_committed_queue_template_unchanged(self) -> None:
        # 봉인 준수 — 기계 거부 도구는 커밋 큐를 읽기만 하고 바꾸지 않는다(전행 pending 유지).
        import json

        q = json.loads(
            (
                _REPO_ROOT
                / "docs"
                / "data"
                / "misconception_crosslink_review_queue.json"
            ).read_text(encoding="utf-8")
        )
        assert all(row["status"] == "pending" for row in q["review_queue"])
