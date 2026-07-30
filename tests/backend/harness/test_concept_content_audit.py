"""개념 콘텐츠 코퍼스 감사 — review_status 축·결함 신호·게이트 변별력.

이 감사의 목적은 하나의 불편한 사실을 숫자로 고정하는 것이다: **437행이 전량 'AI 추정·검수필요'인
채로 학생 렌더 경로에 나가고 있다.** 그러므로 여기서는 실 코퍼스의 미검수 비율이 *실제로* 관측되는지
확인하고, 결함 신호가 결함 없는 입력에서 침묵하고 결함 있는 입력에서만 울리는지(변별력) 검사한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.db.models.concept_content import CONTENT_REVIEW_STATUS_AI_ESTIMATED
from whymath_backend.harness.concept_assessment_index import (
    DEFAULT_CONCEPT_PATH,
    ConceptRow,
    load_concepts,
)
from whymath_backend.harness.concept_content_audit import (
    DEFECT_DSL_PROJECTION_REJECTED,
    DEFECT_NO_STANDARD_CODES,
    REVIEW_STATUS_AI_ESTIMATED,
    REVIEW_STATUS_MISSING,
    audit_concepts,
    main,
    render_report,
)


def _row(**overrides: object) -> ConceptRow:
    payload: dict[str, object] = {
        "code": "A1",
        "name": "일차식",
        "subject": "중학수학",
        "unit": "문자와 식",
        "metaphor": "저울의 균형과 같다.",
        "misconception": "차수를 혼동한다.",
        "formal_definition_internal": "미지수의 차수가 1인 식.",
        "accepted_expressions": "2x + 3",
        "standard_codes": ("[9수02-01]",),
        "review_status": REVIEW_STATUS_AI_ESTIMATED,
    }
    payload.update(overrides)
    return ConceptRow(**payload)  # type: ignore[arg-type]


# ── 축 정합(런타임 결합 대신 테스트로 못 박는다) ──────────────────


def test_review_status_literal_matches_persistence_constant() -> None:
    """감사 도구의 리터럴이 영속 계층 상수와 같다 — 관측 도구는 db를 런타임 import하지 않는다.

    `problem_bank_coverage`가 L6 상수를 테스트로만 동결하는 것과 같은 규약이다. 값이 갈라지면
    감사 숫자가 조용히 틀려지므로 여기서 기계로 묶는다.
    """
    assert REVIEW_STATUS_AI_ESTIMATED == CONTENT_REVIEW_STATUS_AI_ESTIMATED


# ── 검수 상태 ────────────────────────────────────────────────────


def test_unreviewed_rate_counts_non_reviewed_rows() -> None:
    """'reviewed'가 아닌 모든 상태가 미검수다(미표기 포함)."""
    report = audit_concepts(
        [
            _row(code="A1"),
            _row(code="A2", review_status="reviewed"),
            _row(code="A3", review_status=None),
        ]
    )
    assert report.review_status_counts == {
        REVIEW_STATUS_AI_ESTIMATED: 1,
        "reviewed": 1,
        REVIEW_STATUS_MISSING: 1,
    }
    assert report.unreviewed == 2
    assert report.unreviewed_rate == pytest.approx(2 / 3)


def test_empty_corpus_reports_unknown_not_zero() -> None:
    """행 0이면 비율은 0%가 아니라 미상(None) — 빈 입력을 완벽으로 위장하지 않는다."""
    report = audit_concepts([])
    assert report.unreviewed_rate is None
    assert report.defect_rate is None
    assert report.defect_rate_upper() is None
    assert "미상" in render_report(report)


# ── 결함 신호(변별력) ────────────────────────────────────────────


def test_clean_row_produces_no_defect_signal() -> None:
    """결함 없는 행에서는 침묵한다 — 항상 울리는 검사는 검사가 아니다."""
    report = audit_concepts([_row()])
    assert report.defective_concepts == 0
    assert report.defect_counts == {}
    # 전수여도 상한은 0이 아니다(관측 0건을 "결함 0"으로 과신하지 않는다).
    upper = report.defect_rate_upper()
    assert upper is not None and upper > 0.0


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"metaphor": None}, "missing:metaphor"),
        ({"misconception": None}, "missing:misconception"),
        ({"standard_codes": ()}, DEFECT_NO_STANDARD_CODES),
        # 교수법 방식 지시어가 본문에 새어 들면 렌더 투영 자체가 거부된다(중립성 위반).
        ({"metaphor": "소크라테스식으로 질문하며 접근한다."}, DEFECT_DSL_PROJECTION_REJECTED),
    ],
)
def test_each_defect_signal_actually_fires(overrides: dict[str, object], expected: str) -> None:
    """각 결함 신호가 해당 결함에서만 실제로 울린다."""
    report = audit_concepts([_row(**overrides)])
    assert report.defect_counts.get(expected) == 1
    assert report.defective_concepts == 1


def test_multiple_defects_on_one_concept_count_once_in_rate() -> None:
    """결함율의 분자는 *개념 수*다 — 같은 개념을 여러 번 세면 비율이 1을 넘는다."""
    report = audit_concepts([_row(metaphor=None, misconception=None, standard_codes=())])
    assert len(report.defects) == 3
    assert report.defective_concepts == 1
    assert report.defect_rate == pytest.approx(1.0)


# ── CLI 게이트 ───────────────────────────────────────────────────


def _write_corpus(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "content.json"
    path.write_text(json.dumps({"content": rows}, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_gates_fire_and_clear(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """임계를 넘으면 exit 1, 완화하면 exit 0 — 게이트가 양방향으로 변별한다."""
    path = _write_corpus(
        tmp_path,
        [
            {
                "code": "A1",
                "name": "일차식",
                "subject": "중학수학",
                "metaphor": "저울의 균형과 같다.",
                "misconception": "차수를 혼동한다.",
                "formal_definition_internal": "미지수의 차수가 1인 식.",
                "accepted_expressions": "2x + 3",
                "standard_codes": ["[9수02-01]"],
                "review_status": "ai_estimated",
            }
        ],
    )
    out = tmp_path / "audit.json"
    assert main(["--concepts", str(path), "--json", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["unreviewed_rate"] == 1.0

    assert main(["--concepts", str(path), "--max-unreviewed-rate", "0.5"]) == 1
    assert main(["--concepts", str(path), "--max-unreviewed-rate", "1.0"]) == 0
    assert main(["--concepts", str(path), "--max-defect-upper", "0.001"]) == 1
    capsys.readouterr()


def test_cli_input_error_is_not_silent_success(tmp_path: Path) -> None:
    """코퍼스 부재를 "결함 0"으로 위장하지 않는다(exit 2)."""
    assert main(["--concepts", str(tmp_path / "nope.json")]) == 2


# ── 실 코퍼스 ────────────────────────────────────────────────────


def test_shipped_corpus_is_fully_ai_estimated_and_structurally_clean() -> None:
    """실 코퍼스 437행 전량이 'ai_estimated' — 검수 승격 없이 학생에게 노출 중임을 동결한다.

    이 값이 바뀌면(검수 승격) 테스트가 빨개져 사람이 의도적으로 갱신하게 된다 — 검수 상태가
    조용히 바뀌는 것을 막는 장치다.
    """
    report = audit_concepts(load_concepts(DEFAULT_CONCEPT_PATH))
    assert report.total == 437
    assert report.review_status_counts == {REVIEW_STATUS_AI_ESTIMATED: 437}
    assert report.unreviewed_rate == 1.0
    assert report.defect_counts == {}, report.defect_counts
