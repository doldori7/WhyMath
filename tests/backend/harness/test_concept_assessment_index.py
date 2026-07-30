"""개념 평가 재료 참조 인덱스 빌더 — 자격 필터·매칭·전후 성공률·산출물.

핵심 회귀는 **측정의 변별력**이다. "주입 후 N%"만 재는 리포트는 주입이 아무 일도 하지 않아도
같은 숫자를 낼 수 있다(2026-07-17 logconfig 사고의 일반형). 그래서 여기서는 주입 *전* 0%를 실제로
재현한 뒤 후를 재고, 두 값이 다르다는 것 자체를 검사한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness import concept_assessment_index as cai
from whymath_backend.harness.concept_assessment_index import (
    AXIS_CONCEPT_SRC_ID,
    AXIS_STANDARD_CODE,
    DROP_EMPTY_ANSWER_MAP,
    DROP_NOT_OWN_LICENSE,
    DROP_REVERIFY_NOT_PASS,
    DROP_TIER1_NOT_PASS,
    ConceptRow,
    build_report,
    discover_problem_files,
    eligible_problem_refs,
    index_payload,
    load_concepts,
    main,
    match_entries,
    render_rates,
    render_report,
)


def _problem(**overrides: object) -> dict[str, object]:
    """상속 자격을 *모두* 갖춘 최소 문항 — 각 테스트는 한 축만 깨서 필터를 검사한다."""
    record: dict[str, object] = {
        "slug": "wm-test-1",
        "source_type": "자체생성",
        "license": "WHYMATH_GENERATED",
        "question_text": "x^2 - 5x + 6 = 0 의 두 근 중 큰 근을 구하시오.",
        "answer": "3",
        "unit_codes": ["QUAD-EQ"],
        "achievement_standard_codes": ["[10공수1-02-02]"],
        "concepts": [{"concept_src_id": "HK06", "role": "PRIMARY"}],
        "difficulty_overall": 2.0,
        "verify": {"conditions": "x**2 - 5*x + 6 = 0", "answer_map": {"x": "3"}},
    }
    record.update(overrides)
    return record


def _write_bank(
    tmp_path: Path, records: list[dict[str, object]], name: str = "problem_bank_t"
) -> Path:
    bank = tmp_path / name
    bank.mkdir(parents=True, exist_ok=True)
    (bank / "problems.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    return tmp_path


def _concept(**overrides: object) -> ConceptRow:
    payload: dict[str, object] = {
        "code": "HK06",
        "name": "이차방정식의 풀이",
        "subject": "공통수학1",
        "unit": "방정식과 부등식",
        "metaphor": "저울의 균형과 같다.",
        "misconception": "판별식을 무시한다.",
        "formal_definition_internal": "최고차항의 차수가 2인 방정식.",
        "accepted_expressions": "인수분해로 두 근을 구한다",
        "standard_codes": ("[10공수1-02-02]",),
    }
    payload.update(overrides)
    return ConceptRow(**payload)  # type: ignore[arg-type]


# ── 자격 필터(4겹) ────────────────────────────────────────────────


def test_all_drop_reasons_are_reported_even_when_zero(tmp_path: Path) -> None:
    """네 겹 전부가 0으로라도 리포트에 나온다 — "0건 걸렀다"와 "필터가 없다"를 구분한다."""
    root = _write_bank(tmp_path, [_problem()])
    refs, drops, scanned = eligible_problem_refs(discover_problem_files(root))
    assert scanned == 1 and len(refs) == 1
    assert set(drops) == {
        DROP_NOT_OWN_LICENSE,
        DROP_REVERIFY_NOT_PASS,
        DROP_EMPTY_ANSWER_MAP,
        DROP_TIER1_NOT_PASS,
    }
    assert all(count == 0 for count in drops.values())


@pytest.mark.parametrize(
    ("overrides", "expected_drop"),
    [
        ({"license": "EXTERNAL"}, DROP_NOT_OWN_LICENSE),
        ({"source_type": "평가원"}, DROP_NOT_OWN_LICENSE),
        (
            # 개념형(실근 *개수*) 문항 — 재검증은 통과하지만 answer_map이 비어 있어
            # `ConceptAssessment`를 만들 수 없다(빈 검증의 통과 위장 금지).
            {
                "verify": {
                    "conditions": "x**2 + 1 = 0",
                    "answer_map": {},
                    "answer_kind": "real_root_count",
                },
                "answer": "0",
            },
            DROP_EMPTY_ANSWER_MAP,
        ),
        (
            # 답이 조건을 만족하지 않는다 → 재검증 자체가 fail로 걸린다(오염 차단).
            {"verify": {"conditions": "x**2 - 5*x + 6 = 0", "answer_map": {"x": "7"}}},
            DROP_REVERIFY_NOT_PASS,
        ),
        (
            # 근 집계(Vieta) 문항 — 답이 근이 아니라 근들의 합이라 Tier1 대입은 실패한다.
            {
                "verify": {
                    "conditions": "x**2 - 5*x + 6 = 0",
                    "answer_map": {"x": "5"},
                    "answer_aggregate": "sum",
                },
                "answer": "5",
            },
            DROP_TIER1_NOT_PASS,
        ),
    ],
)
def test_each_filter_layer_actually_drops(
    tmp_path: Path, overrides: dict[str, object], expected_drop: str
) -> None:
    """각 겹이 *실제로* 탈락시킨다 — 통과만 확인하는 검사는 필터의 존재를 증명하지 못한다."""
    root = _write_bank(tmp_path, [_problem(**overrides)])
    refs, drops, _ = eligible_problem_refs(discover_problem_files(root))
    assert refs == []
    assert drops[expected_drop] == 1


# ── 매칭 ─────────────────────────────────────────────────────────


def test_direct_concept_code_beats_standard_code(tmp_path: Path) -> None:
    """개념 code 직결이 성취기준 다리보다 우선한다(더 강한 신호)."""
    root = _write_bank(
        tmp_path,
        [
            _problem(slug="via-standard", concepts=[], difficulty_overall=1.0),
            _problem(slug="via-code", achievement_standard_codes=[], difficulty_overall=5.0),
        ],
    )
    refs, _, _ = eligible_problem_refs(discover_problem_files(root))
    entries, uncovered = match_entries([_concept()], refs)
    assert uncovered == []
    assert entries[0].match_axis == AXIS_CONCEPT_SRC_ID
    assert entries[0].problem_slug == "via-code"


def test_easiest_candidate_wins_within_same_axis(tmp_path: Path) -> None:
    """같은 축이면 난이도가 낮은 문항을 고른다(문제 우선 제시의 정서 안전)."""
    root = _write_bank(
        tmp_path,
        [
            _problem(slug="hard", concepts=[], difficulty_overall=4.5),
            _problem(slug="easy", concepts=[], difficulty_overall=1.5),
        ],
    )
    refs, _, _ = eligible_problem_refs(discover_problem_files(root))
    entries, _ = match_entries([_concept()], refs)
    assert entries[0].match_axis == AXIS_STANDARD_CODE
    assert entries[0].problem_slug == "easy"


def test_uncovered_concepts_are_recorded_not_dropped(tmp_path: Path) -> None:
    """맞는 문항이 없는 개념은 *기록*된다 — 커버된 것만 세는 침묵 통과 금지."""
    root = _write_bank(tmp_path, [_problem()])
    refs, _, _ = eligible_problem_refs(discover_problem_files(root))
    entries, uncovered = match_entries(
        [_concept(), _concept(code="NO-MATCH", standard_codes=("[9수99-99]",))], refs
    )
    assert [e.concept_code for e in entries] == ["HK06"]
    assert uncovered == ["NO-MATCH"]


# ── 전/후 성공률(변별력) ──────────────────────────────────────────


def test_problem_based_rate_moves_from_zero_after_injection(tmp_path: Path) -> None:
    """주입 전 0% → 후 100%. 두 값이 같으면 측정이 무효라는 것을 이 대조가 드러낸다."""
    root = _write_bank(tmp_path, [_problem()])
    refs, _, _ = eligible_problem_refs(discover_problem_files(root))
    entries, _ = match_entries([_concept()], refs)
    before, after, dsl_invalid = render_rates([_concept()], entries)

    assert dsl_invalid == 0
    assert before["PROBLEM_BASED"].dsl_render_rate == pytest.approx(0.0)
    assert after["PROBLEM_BASED"].dsl_render_rate == pytest.approx(1.0)
    # 다른 어댑터는 원래 렌더되므로 주입이 값을 바꾸지 않는다(부작용 없음).
    assert before["SOCRATIC"].dsl_render_rate == after["SOCRATIC"].dsl_render_rate


def test_render_rates_use_supply_tally_breakdown(tmp_path: Path) -> None:
    """리포트가 `SupplyTally`를 소비한다 — 어댑터별 분해가 리포트 표면에 실제로 실린다."""
    root = _write_bank(tmp_path, [_problem()])
    refs, drops, scanned = eligible_problem_refs(discover_problem_files(root))
    report = build_report([_concept()], refs, drops, scanned)
    payload = report.to_json()
    assert payload["render_rate_after"]["PROBLEM_BASED"]["by_strategy"] == {
        "PROBLEM_BASED": {"dsl_render": 1}
    }
    assert payload["render_rate_before"]["PROBLEM_BASED"]["by_fallback_reason"] == {
        "CANNOT_RENDER": 1
    }
    assert "PROBLEM_BASED" in render_report(report)


# ── 산출물 ───────────────────────────────────────────────────────


def test_index_payload_is_deterministic_and_carries_uncovered(tmp_path: Path) -> None:
    """같은 입력 → 같은 바이트(시각 필드 없음) + 미커버 목록 보존."""
    root = _write_bank(tmp_path, [_problem()])
    refs, drops, scanned = eligible_problem_refs(discover_problem_files(root))
    concepts = [_concept(), _concept(code="NO-MATCH", standard_codes=("[9수99-99]",))]
    first = index_payload(build_report(concepts, refs, drops, scanned), concept_source="c.json")
    second = index_payload(build_report(concepts, refs, drops, scanned), concept_source="c.json")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["uncovered_concept_codes"] == ["NO-MATCH"]
    assert first["counts"]["concepts_uncovered"] == 1


def test_cli_writes_index_and_gate_fires_below_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI가 산출물을 쓰고, 임계 미달이면 exit 1(게이트가 실패 상태에서 실제로 실패한다)."""
    root = _write_bank(tmp_path, [_problem()])
    concepts_path = tmp_path / "content.json"
    concepts_path.write_text(
        json.dumps(
            {
                "content": [
                    {
                        "code": "HK06",
                        "name": "이차방정식의 풀이",
                        "subject": "공통수학1",
                        "metaphor": "저울의 균형과 같다.",
                        "standard_codes": ["[10공수1-02-02]"],
                        "review_status": "ai_estimated",
                    },
                    {
                        "code": "NO-MATCH",
                        "name": "미커버 개념",
                        "subject": "공통수학1",
                        "metaphor": "무엇에 빗댈 수 있다.",
                        "standard_codes": ["[9수99-99]"],
                        "review_status": "ai_estimated",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    argv = [
        "--corpus-root",
        str(root),
        "--concepts",
        str(concepts_path),
        "--out-dir",
        str(out_dir),
        "--write",
    ]
    assert main(argv) == 0
    written = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert [e["concept_code"] for e in written["entries"]] == ["HK06"]
    assert written["uncovered_concept_codes"] == ["NO-MATCH"]

    # 커버율 50%인 상태에서 하한 90%를 요구하면 게이트가 깨져야 한다.
    assert main([*argv, "--min-problem-based-rate", "0.9"]) == 1
    assert main([*argv, "--min-problem-based-rate", "0.4"]) == 0
    capsys.readouterr()


def test_cli_reports_input_error_without_pretending_success(tmp_path: Path) -> None:
    """입력 부재를 0건 통과로 위장하지 않는다(exit 2)."""
    assert main(["--corpus-root", str(tmp_path), "--concepts", str(tmp_path / "nope.json")]) == 2


# ── 실 코퍼스(배선 실재성) ────────────────────────────────────────


def test_shipped_concept_corpus_loads_with_review_status() -> None:
    """실 코퍼스 437행이 로드되고 `review_status` 축이 전 행에 있다."""
    rows = load_concepts(cai.DEFAULT_CONCEPT_PATH)
    assert len(rows) == 437
    assert all(row.review_status for row in rows)
