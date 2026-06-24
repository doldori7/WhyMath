"""viz_eval 채점기·집계 단위 테스트 — 모델 0(canned 텍스트)·CI 단위잡 수집.

라이브 평가(`test_visualization_live`)는 실 모델이 필요해 CI에서 빠지지만, *채점·집계
로직*은 순수 함수라 여기서 모델 없이 전부 검증한다 — quality_eval 채점기 단위 테스트와 동형.
"""

from __future__ import annotations

import json
from typing import Any

from whymath_backend.l3.viz_eval import (
    VIZ_MIN_VALID,
    CellAggregate,
    VizEvalItem,
    VizItemScore,
    VizRunRecord,
    aggregate,
    build_verdicts,
    complete_graph2d,
    complete_simulation,
    complete_surface3d,
    grade_spec,
)
from whymath_backend.schema.enums import VisualizationType

T_SIM = VisualizationType.simulation_probabilistic
T_3D = VisualizationType.interactive_surface_3d
T_2D = VisualizationType.interactive_graph_2d


def _raw(viz: dict[str, Any]) -> str:
    """Visualization dict → LLM 원시 출력 흉내(산문·코드펜스로 감싸 게이트 견고성도 확인)."""
    return "다음은 명세입니다:\n```json\n" + json.dumps(viz, ensure_ascii=False) + "\n```"


def _sim(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "simulation_probabilistic",
        "spec": {"experiment": "임의 실험", "trials": 200, "outcomes": outcomes},
        "caption": "확률 시뮬",
        "interactive": True,
    }


# ── grade_spec: simulation ──────────────────────────────────────────────────
def test_grade_valid_simulation_with_outcomes() -> None:
    raw = _raw(_sim([{"label": "가위", "weight": 1}, {"label": "바위", "weight": 1}]))
    score = grade_spec(raw, T_SIM, item_id="s1")
    assert score.item_id == "s1"
    assert score.parsed_ok and score.type_ok and score.complete
    assert score.valid is True
    assert score.error is None


def test_grade_simulation_missing_outcomes_incomplete() -> None:
    raw = _raw(
        {
            "type": "simulation_probabilistic",
            "spec": {"experiment": "동전", "trials": 100},  # outcomes 없음
            "interactive": True,
        }
    )
    score = grade_spec(raw, T_SIM)
    assert score.parsed_ok and score.type_ok
    assert score.complete is False
    assert score.valid is False


def test_grade_simulation_single_outcome_incomplete() -> None:
    raw = _raw(_sim([{"label": "앞", "weight": 1}]))  # outcomes 1개 → 이산 분포 아님
    score = grade_spec(raw, T_SIM)
    assert score.complete is False
    assert score.valid is False


def test_grade_simulation_negative_weight_rejected_by_gate() -> None:
    # SimOutcome.weight는 ge=0 → 음수는 *파스 게이트*에서 거부(parsed_ok False).
    raw = _raw(_sim([{"label": "앞", "weight": 1}, {"label": "뒤", "weight": -1}]))
    score = grade_spec(raw, T_SIM)
    assert score.parsed_ok is False
    assert score.valid is False
    assert score.error is not None


# ── grade_spec: 3d / 2d ─────────────────────────────────────────────────────
def test_grade_valid_surface3d() -> None:
    raw = _raw(
        {
            "type": "interactive_surface_3d",
            "spec": {"surface": "z = x**2 - y**2", "rotatable": True},
            "interactive": True,
        }
    )
    score = grade_spec(raw, T_3D)
    assert score.valid is True


def test_grade_valid_graph2d() -> None:
    raw = _raw(
        {
            "type": "interactive_graph_2d",
            "spec": {"function": "a*x**2+b*x+c", "domain": [-3, 3]},
            "interactive": True,
        }
    )
    score = grade_spec(raw, T_2D)
    assert score.valid is True


def test_grade_type_mismatch() -> None:
    # 기대는 sim이지만 모델이 (유효한) 2d를 반환 → type_ok False·valid False.
    raw = _raw(
        {
            "type": "interactive_graph_2d",
            "spec": {"function": "x**2", "domain": [-1, 1]},
            "interactive": True,
        }
    )
    score = grade_spec(raw, T_SIM)
    assert score.parsed_ok is True
    assert score.type_ok is False
    assert score.valid is False


def test_grade_broken_json_parse_fails() -> None:
    score = grade_spec("이건 JSON이 아닙니다 {그냥 텍스트", T_SIM, item_id="bad")
    assert score.parsed_ok is False
    assert score.valid is False
    assert score.error is not None
    assert score.item_id == "bad"


# ── 완성도 순수 함수(파스 게이트가 가리는 방어 분기 포함) ───────────────────
def test_complete_simulation_branches() -> None:
    assert complete_simulation(
        {"outcomes": [{"label": "a", "weight": 1}, {"label": "b", "weight": 0}]}
    )
    assert not complete_simulation({"outcomes": []})
    assert not complete_simulation({"outcomes": [{"label": "a", "weight": 1}]})
    assert not complete_simulation(
        {"outcomes": [{"label": "", "weight": 1}, {"label": "b", "weight": 1}]}
    )
    assert not complete_simulation(
        {"outcomes": [{"label": "a", "weight": -1}, {"label": "b", "weight": 1}]}
    )
    assert not complete_simulation(
        {"outcomes": [{"label": "a", "weight": True}, {"label": "b", "weight": 1}]}
    )
    assert not complete_simulation({"outcomes": ["가위", "바위"]})  # 비-dict 항목
    assert not complete_simulation({})


def test_complete_graph2d_branches() -> None:
    assert complete_graph2d({"function": "x**2", "domain": [-3, 3]})
    assert not complete_graph2d({"function": "", "domain": [-3, 3]})
    assert not complete_graph2d({"function": "x**2", "domain": [-3, 3, 5]})  # 2원소 아님
    assert not complete_graph2d({"function": "x**2"})  # domain 없음
    assert not complete_graph2d({"function": "x**2", "domain": ["a", "b"]})  # 비-숫자


def test_complete_surface3d_branches() -> None:
    assert complete_surface3d({"surface": "z = x**2 + y**2"})
    assert not complete_surface3d({"surface": "   "})
    assert not complete_surface3d({})


# ── 집계 ────────────────────────────────────────────────────────────────────
def _item(item_id: str, vtype: VisualizationType) -> VizEvalItem:
    return VizEvalItem(id=item_id, concept="개념", level="고1", expected_type=vtype)


def _rec(family: str, vtype: VisualizationType, valid: bool, idx: int) -> VizRunRecord:
    score = VizItemScore(
        item_id=f"{family}-{idx}",
        expected_type=vtype.value,
        parsed_ok=True,
        type_ok=valid,
        complete=valid,
        valid=valid,
    )
    return VizRunRecord(
        model_id=f"model-{family}", family=family, item=_item(f"{idx}", vtype), score=score
    )


def test_aggregate_valid_rate_per_cell() -> None:
    records = [
        _rec("math", T_SIM, True, 0),
        _rec("math", T_SIM, False, 1),  # math/sim: 1/2 = 0.5
        _rec("general", T_SIM, True, 2),
        _rec("general", T_SIM, True, 3),  # general/sim: 2/2 = 1.0
    ]
    cells = aggregate(records)
    by = {(c.family, c.viz_type): c for c in cells}
    assert by[("math", T_SIM.value)].valid_rate == 0.5
    assert by[("math", T_SIM.value)].n_valid == 1
    assert by[("general", T_SIM.value)].valid_rate == 1.0


# ── 판정 ────────────────────────────────────────────────────────────────────
def _cell(family: str, vtype: VisualizationType, rate: float) -> CellAggregate:
    n = 10
    return CellAggregate(
        family=family,
        model_id=f"model-{family}",
        viz_type=vtype.value,
        n_items=n,
        n_valid=round(rate * n),
        valid_rate=rate,
    )


def test_verdict_production_below_threshold_flags_best_family() -> None:
    cells = [
        _cell("math", T_SIM, 0.4),  # 프로덕션 < 하한
        _cell("general", T_SIM, 0.9),  # 최적
        _cell("vision", T_SIM, 0.7),
    ]
    verdicts = build_verdicts(cells)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.meets_threshold is False
    assert v.production_family == "math"
    assert v.production_rate == 0.4
    assert v.best_family == "general"
    assert v.best_rate == 0.9


def test_verdict_production_meets_threshold() -> None:
    cells = [_cell("math", T_2D, 0.8), _cell("general", T_2D, 0.6)]
    verdicts = build_verdicts(cells)
    assert verdicts[0].meets_threshold is True


def test_verdict_threshold_boundary() -> None:
    # 정확히 VIZ_MIN_VALID(0.6)면 충족(>= 하한, _EPS 허용).
    cells = [_cell("math", T_3D, VIZ_MIN_VALID)]
    verdicts = build_verdicts(cells)
    assert verdicts[0].meets_threshold is True

    cells_below = [_cell("math", T_3D, 0.59)]
    assert build_verdicts(cells_below)[0].meets_threshold is False
