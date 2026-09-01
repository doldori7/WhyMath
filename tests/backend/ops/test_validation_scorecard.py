"""12월 검증 결론 판정기 — 동결 기준 준수 + **미측정이 통과로 위장되지 않음** (EOS-61).

이 파일이 지키는 것은 두 가지다.

1. **§5 동결 문언대로 판정하는가** — F-Ⅰ~F-Ⅴ의 임계값과 F-Ⅳ의 "3개 이상 NO_GO /
   2개면 Conditional"은 G0 서명으로 동결됐고 12월 수정 금지다. 코드가 그 문언에서
   미끄러지면 검증이 아니라 확증편향이 된다.
2. **측정하지 않은 것을 통과라 하지 않는가** — 이 저장소가 반복해서 다친 부류다.
   실제로 1차 구현은 **빈 입력에서 GO**를 냈다(Hard Gate가 전부 판정 불가라 triggered가
   없고 KPI가 전부 미측정이라 failed도 없었다). 그 회귀를 여기서 막는다.
"""

from __future__ import annotations

import json

import pytest

from whymath_backend.ops.validation_scorecard import (
    KPI_SOURCES,
    KpiVerdict,
    Verdict,
    evaluate,
    main,
    render,
)


def _anchors(fail: int, total: int = 6) -> dict[str, bool]:
    return {f"A{i + 1}": i >= fail for i in range(total)}


#: 모든 Hard Gate가 '미해당'이고 모든 KPI가 통과하는 완전 입력.
def _clean_payload() -> dict:
    return {
        "hit": {
            "median_minutes": 3.0,
            "p90_minutes": 7.0,
            "sample_size": 200,
            "baseline_anchor_median_minutes": {"A3": 5.0, "A4": 6.0},
        },
        "auto_gate_pass": {"hits": 900, "trials": 1000},
        "rework": {"hits": 60, "trials": 1000},
        "throughput": {"cu_per_hour": 35.0, "sample_size": 200},
        "unit_cost": {"krw_per_cu": 180.0, "sample_size": 200},
        "machine_share": {"hits": 700, "trials": 1000},
        "failure_distribution": {"judgment_share": 0.30},
        "anchors": _anchors(0),
        "content": {
            "reviewed_math_errors": 0,
            "reviewed_cu_total": 2000,
            "hint_leak_hits": 0,
            "hint_leak_sample": 500,
            "EOS-60-golden-benchmark-qa-confusion-matrix": {
                "hits": 990,
                "trials": 1000,
                "floor": 0.95,
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────────
# ① 미측정이 통과가 되지 않는다 — 1차 구현의 실제 결함
# ──────────────────────────────────────────────────────────────────────────
def test_empty_input_never_yields_go() -> None:
    """빈 입력에서 GO가 나오면 '검증했고 통과했다'는 거짓 신호가 된다.

    1차 구현이 실제로 GO를 냈다 — Hard Gate가 전부 판정 불가라 triggered가 없고 KPI가
    전부 미측정이라 failed도 없어서, 두 부정을 통과로 읽었기 때문이다.
    """
    card = evaluate({})
    assert card.verdict is not Verdict.GO
    assert card.measurement_failed is True
    assert card.unmeasured_count > 0 and card.unmeasurable_gate_count == 5


def test_measurement_failure_is_distinct_from_failing_a_gate() -> None:
    """'실패인지 모른다'와 '실패다'는 다른 축 — 같은 필드로 표현하지 않는다."""
    card = evaluate({})
    assert all(not g.triggered for g in card.hard_gates), "판정 불가를 해당으로 접었다"
    assert all(not g.measurable for g in card.hard_gates)


def test_one_missing_kpi_blocks_go() -> None:
    """11종이 통과여도 1종이 미측정이면 GO가 아니다 — 부분 측정은 완결이 아니다."""
    payload = _clean_payload()
    del payload["unit_cost"]
    card = evaluate(payload)
    assert card.verdict is Verdict.CONDITIONAL_GO
    assert card.measurement_failed is True


def test_go_is_currently_unreachable_and_that_is_the_honest_state() -> None:
    """**지금 이 저장소에서는 GO가 나올 수 없다** — 채점기가 아직 없기 때문이다.

    깨끗한 입력을 줘도 내용 KPI 일부는 미측정으로 남는다(`consumer_module=None` +
    골든 축 밖 2종). 그것이 결함이 아니라 **사실**이고, 스코어카드가 그 사실을 GO로
    덮지 않는 것이 이 도구의 존재 이유다.

    이 테스트는 "왜 아직 GO가 안 나오나"를 미래 세션에게 설명하는 자리이기도 하다 —
    답은 '입력이 나빠서'가 아니라 '재는 도구가 아직 없어서'다.
    """
    card = evaluate(_clean_payload())
    assert card.verdict is not Verdict.GO
    assert card.measurement_failed is True
    unmeasured = [k for k in card.kpis if k.verdict is KpiVerdict.unmeasured]
    assert unmeasured, "미측정이 0인데 GO가 아니면 다른 이유가 섞인 것이다"
    for k in unmeasured:
        assert k.note, f"'{k.kpi}'가 왜 미측정인지 말하지 않는다"


def test_go_is_reachable_once_every_scorer_lands(monkeypatch) -> None:
    """변별력 — 전 지표가 측정되면 실제로 GO가 나온다.

    이 케이스가 없으면 위 테스트들이 '항상 GO를 막는' 구현으로도 통과한다. 미착지
    채점기를 착지한 것으로 가정한 입력을 만들어, 막는 것이 *구현*이 아니라 *데이터
    부재*임을 보인다.
    """
    from whymath_backend.ops import validation_scorecard as vs
    from whymath_backend.ops.qa_confusion_matrix import ContentKpiConsumer

    landed = tuple(
        ContentKpiConsumer(
            kpi=c.kpi,
            label_axis=c.label_axis,
            consumer_module=c.consumer_module or "whymath_backend.ops.qa_confusion_matrix",
            seat_task=c.seat_task,
            failure_codes=c.failure_codes,
        )
        for c in vs.CONTENT_KPI_CONSUMERS
    )
    monkeypatch.setattr(vs, "CONTENT_KPI_CONSUMERS", landed)

    payload = _clean_payload()
    for consumer in landed:
        payload["content"][consumer.seat_task] = {"hits": 990, "trials": 1000, "floor": 0.9}
    for kpi, _target, _reason in vs.NON_GOLDEN_CONTENT_KPIS:
        payload["content"][kpi] = {"observed": "ρ=0.62", "passed": True, "sample_size": 120}

    card = vs.evaluate(payload)
    assert card.verdict is Verdict.GO
    assert card.measurement_failed is False


def test_scorecard_reports_all_twelve_kpis() -> None:
    """§6이 동결한 12종(기술 6 · 내용 6)이 전부 표에 오른다.

    결선표(`CONTENT_KPI_CONSUMERS`)는 4종만 담는다 — 골든 라벨 축이 없는 2종(난이도
    타당도·힌트 누설률)이 거기 없는 것이 맞기 때문이다. 그 둘을 스코어카드에서도 빼면
    "12종을 봤다"는 착시가 생기므로 별도 상수로 채운다.
    """
    card = evaluate(_clean_payload())
    assert len(card.kpis) == 12, [k.kpi for k in card.kpis]


# ──────────────────────────────────────────────────────────────────────────
# ② Hard Gate가 점수보다 먼저다 (설계 규칙 1)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda p: p["hit"]["baseline_anchor_median_minutes"].update({"A3": 12.5}), "F-Ⅰ"),
        (lambda p: p["content"].update({"reviewed_math_errors": 200}), "F-Ⅱ"),
        (lambda p: p["failure_distribution"].update({"judgment_share": 0.61}), "F-Ⅲ"),
        (lambda p: p.update({"anchors": _anchors(3)}), "F-Ⅳ"),
        (lambda p: p["content"].update({"hint_leak_hits": 100}), "F-Ⅴ"),
    ],
)
def test_each_hard_gate_forces_no_go(mutate, code: str) -> None:
    """F-Ⅰ~F-Ⅴ **각각**이 단독으로 NO_GO를 만든다 — 하나라도 놓치면 게이트가 아니다."""
    payload = _clean_payload()
    mutate(payload)
    card = evaluate(payload)
    assert card.verdict is Verdict.NO_GO, f"{code}가 NO_GO를 만들지 못했다"
    triggered = [g.code for g in card.hard_gates if g.triggered]
    assert code in triggered, f"{code}가 아니라 {triggered}가 걸렸다"


def test_anchor_threshold_follows_the_frozen_wording() -> None:
    """F-Ⅳ 동결 문언: 3개 이상 미달 = NO_GO · 2개 = Conditional Go.

    임계값이 한 칸 밀리면(2개에서 NO_GO, 또는 3개에서 Conditional) 12월 판정이
    동결 기준과 달라진다 — 경계 양쪽을 모두 고정한다.
    """
    two = _clean_payload()
    two["anchors"] = _anchors(2)
    assert evaluate(two).verdict is Verdict.CONDITIONAL_GO

    three = _clean_payload()
    three["anchors"] = _anchors(3)
    assert evaluate(three).verdict is Verdict.NO_GO


def test_no_single_composite_score_is_produced() -> None:
    """단일 EOS Score 금지 — 치명 오류가 평균에 묻히는 구조를 만들지 않는다.

    Scorecard에 종합 점수 필드가 **없음**을 동결한다. 누군가 편의로 추가하면 그 순간
    "평균 82점이니 괜찮다"가 가능해지고, F-Ⅰ 해당이 그 82점 안으로 사라진다.
    """
    card = evaluate(_clean_payload())
    forbidden = {"score", "total_score", "composite", "eos_score", "overall"}
    assert not (forbidden & set(vars(card).keys() if hasattr(card, "__dict__") else card.__slots__))


# ──────────────────────────────────────────────────────────────────────────
# ③ 결선표·한계·판정 형식
# ──────────────────────────────────────────────────────────────────────────
def test_technical_kpi_sources_are_six_and_name_their_seat() -> None:
    """기술 KPI 6종이 각각 출처 모듈과 좌석 태스크를 말한다(acceptance ⑤)."""
    assert len(KPI_SOURCES) == 6
    for src in KPI_SOURCES:
        assert src.source_module.startswith("whymath_backend."), src.kpi
        assert src.seat_task, src.kpi


def test_content_kpis_reuse_the_existing_crosswalk() -> None:
    """내용 KPI는 `CONTENT_KPI_CONSUMERS`를 재사용한다 — 결선표를 두 곳에 두지 않는다."""
    from whymath_backend.ops.qa_confusion_matrix import CONTENT_KPI_CONSUMERS

    card = evaluate(_clean_payload())
    for consumer in CONTENT_KPI_CONSUMERS:
        assert any(k.kpi == consumer.kpi for k in card.kpis), consumer.kpi


def test_unlanded_scorer_is_reported_as_unmeasured_not_pass() -> None:
    """채점기가 없는 내용 KPI는 '미측정'이며 좌석 태스크를 함께 말한다(추정 금지)."""
    from whymath_backend.ops.qa_confusion_matrix import CONTENT_KPI_CONSUMERS

    unlanded = [c for c in CONTENT_KPI_CONSUMERS if c.consumer_module is None]
    if not unlanded:
        pytest.skip("모든 내용 채점기가 착지했다 — 이 케이스는 더 이상 재현되지 않는다")
    card = evaluate(_clean_payload())
    for consumer in unlanded:
        result = next(k for k in card.kpis if k.kpi == consumer.kpi)
        assert result.verdict is KpiVerdict.unmeasured
        assert consumer.seat_task in result.note


def test_report_always_carries_the_design_limits() -> None:
    """§7 한계가 리포트에 **항상** 실린다 — 빼면 표본 185건 판정이 정밀 추정으로 읽힌다."""
    text = render(evaluate(_clean_payload()))
    assert "§7-3" in text and "185 CU" in text
    assert "§7-4" in text


def test_cli_exit_codes(tmp_path) -> None:
    """exit 0 = GO뿐. CONDITIONAL_GO·NO_GO·측정 실패는 전부 1(진행 금지 신호 공유)."""
    # 현재 저장소 상태에서는 깨끗한 입력도 exit 1이다 — 채점기 미착지로 미측정이 남는다.
    # 그것이 정직한 결과다: "GO를 선언할 수 없다"와 "기준 미달"은 stdout이 구분해 말한다.
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps(_clean_payload()), encoding="utf-8")
    assert main(["--input", str(clean)]) == 1

    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    assert main(["--input", str(empty)]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text("{ 깨진", encoding="utf-8")
    assert main(["--input", str(broken)]) == 1, "입력을 못 읽은 것도 진행 금지다"

    assert main(["--input", str(tmp_path / "없는파일.json")]) == 1


def test_cli_json_output_exposes_measurement_failure(tmp_path) -> None:
    """JSON 소비자도 '측정 불완전'을 볼 수 있어야 한다 — verdict만 읽고 오독하지 않게."""
    src = tmp_path / "in.json"
    src.write_text("{}", encoding="utf-8")
    out = tmp_path / "out.json"
    main(["--input", str(src), "--json", str(out)])
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["measurement_failed"] is True
    assert payload["verdict"] != "GO"
    assert payload["unmeasured_kpis"] > 0
