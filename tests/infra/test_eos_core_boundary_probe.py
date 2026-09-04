"""EOS Core 경계 계측 2종 동결 — 전이 도달 잔여 누수 · 리터럴 금지 규칙 (EOS-84 acceptance ③).

계측기(`eos_core_boundary_probe.py`)는 위반 수로 exit 1을 내지 않는다. **게이트는 여기다**:

1. **리터럴 비교 기준선 동결** — CORE 모듈의 `== "math"`·`in ("quadratic", …)`류는 현재 **1건**
   (`l1.problem_bank.populate._verify_meta_from_raw`가 answer_kind 16종을 튜플로 열거 — EOS-66의
   "answer_kind는 Core가 해석하지 않는 불투명 문자열" 계약과 충돌하는 진성 경계 냄새). 새 위치가
   생기면 RED, 그 1건이 어댑터/데이터로 빠지면 기준선을 비워 ratchet한다. 계획서 100 §3.7의
   금지 규칙을 글자 그대로 집행하되, 이미 있던 위반을 0으로 위장하지 않는다.
2. **잔여 누수 집합 동결** — 합성 루트를 막아도 ADAPTER에 닿는 CORE 출발점은 현재 2건(둘 다
   `l4.solution_coaching`(MIXED) 경유)이다. 늘면 RED, 줄면 이 집합을 줄여 ratchet한다. 키는
   (출발점, 누수 지점)이다 — 끝 ADAPTER는 동률이 있어 열쇠로 쓰면 BFS 순서에 따라 흔들린다.
3. **변별력** — 스캐너에 결함을 실제로 주입해(가짜 소스·가짜 그래프) 검출되는지 확인한다. 정상
   입력에서 초록인 것은 보호의 증거가 아니다(CLAUDE.md 2026-09-01).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "analysis" / "eos_core_boundary_probe.py"
_BOUNDARY_DOC = _REPO_ROOT / "docs" / "architecture" / "eos_core_adapter_boundary.md"

# 리터럴 비교 기준선 — (CORE 모듈, 위반 종류) → 허용 건수. 줄이는 방향으로만 고친다.
LITERAL_COMPARE_BASELINE: dict[tuple[str, str], int] = {
    ("l1.problem_bank.populate", "math_type"): 1,
}

# 잔여 누수 동결 — (CORE 출발점, ADAPTER 직전의 누수 지점). 줄이는 방향으로만 고친다.
# 끝점(ADAPTER)이 아니라 *누수 지점*을 고정한다: `l4.solution_coaching`은 `verify_solution`과
# `wrong_form_match`를 둘 다 import하므로 끝점은 동률이고, 고쳐야 할 자리는 그 앞 모듈이다.
RESIDUAL_LEAK_BASELINE: frozenset[tuple[str, str]] = frozenset(
    {
        ("api.coach", "l4.solution_coaching"),
        ("api.ocr_handoff", "l4.solution_coaching"),
    }
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("_eos_core_boundary_probe_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture(scope="module")
def probe() -> Any:
    return _load()


@pytest.fixture(scope="module")
def result(probe: Any) -> dict[str, Any]:
    return probe.run_probe(lambda _msg: None)


# ──────────────────────────────────────────────────────────────────────
# ① 게이트 — 실측이 동결값을 넘지 않는가
# ──────────────────────────────────────────────────────────────────────


def test_population_is_real(result: dict[str, Any]) -> None:
    assert result["core"] > 200 and result["adapter"] > 50, result


def test_core_literal_compares_do_not_exceed_baseline(result: dict[str, Any]) -> None:
    """계획서 100 §3.7 — `if subject == "math"` · `if problem.type == "quadratic"`는 Core 위반.

    기준선 밖의 (모듈, 종류)가 하나라도 생기거나 같은 자리의 건수가 늘면 RED. 기준선보다 줄면
    기준선을 갱신하라고 실패시킨다(ratchet) — 고쳐 놓고 게이트가 느슨한 채 남는 것을 막는다.
    """
    observed: dict[tuple[str, str], int] = {}
    for module, hits in result["literal_compares"].items():
        for h in hits:
            observed[(module, h["kind"])] = observed.get((module, h["kind"]), 0) + 1
    new_or_grown = {k: n for k, n in observed.items() if n > LITERAL_COMPARE_BASELINE.get(k, 0)}
    assert not new_or_grown, f"CORE 리터럴 비교 위반(기준선 초과): {new_or_grown}"
    if observed != LITERAL_COMPARE_BASELINE:
        pytest.fail(f"리터럴 비교가 줄었다 — LITERAL_COMPARE_BASELINE을 {observed}로 ratchet")


def test_subject_literal_compares_are_absent_from_core(result: dict[str, Any]) -> None:
    """과목명 분기(`== "math"`)는 기준선조차 두지 않는다 — 0이 아니면 즉시 RED."""
    subject_hits = {
        m: [h for h in hits if h["kind"] == "subject"]
        for m, hits in result["literal_compares"].items()
    }
    subject_hits = {m: v for m, v in subject_hits.items() if v}
    assert subject_hits == {}, f"CORE 과목명 리터럴 비교: {subject_hits}"


def test_residual_transitive_leaks_are_frozen_and_only_shrink(result: dict[str, Any]) -> None:
    observed = {(x["source"], x["path"][-2]) for x in result["reach_residual"]}
    for x in result["reach_residual"]:
        assert len(x["path"]) >= 2, f"ADAPTER 직접 import는 EOS-67이 막는다 — 잔여 경로가 1홉: {x}"
    assert (
        observed <= RESIDUAL_LEAK_BASELINE
    ), f"신규 잔여 누수: {observed - RESIDUAL_LEAK_BASELINE}"
    if observed < RESIDUAL_LEAK_BASELINE:
        pytest.fail(f"잔여 누수가 줄었다 — RESIDUAL_LEAK_BASELINE을 {sorted(observed)}로 ratchet")


def test_every_non_residual_reach_passes_the_designed_seam(result: dict[str, Any]) -> None:
    """교체점(composition)을 지나지 않는 도달은 전부 잔여 누수 목록에 있어야 한다 — 누수가 '정상'으로
    분류되는 세 번째 범주가 생기면 안 된다."""
    residual_sources = {x["source"] for x in result["reach_residual"]}
    for x in result["reach_all"]:
        assert x["via_designed_seam"] or x["source"] in residual_sources, x


def test_math_removal_leaves_most_of_core_standing(result: dict[str, Any]) -> None:
    """'수학을 제거했을 때 무엇이 남는가' — CORE의 90% 이상이 ADAPTER 없이도 import 가능해야 한다."""
    assert result["survivors_after_math_removal"] / result["core"] >= 0.90, result["core"]


# ──────────────────────────────────────────────────────────────────────
# ② 변별력 — 결함 주입
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ('if subject == "math":\n    pass\n', "subject"),
        ('if problem.type == "quadratic":\n    pass\n', "math_type"),
        ('ok = kind in ("linear", "other")\n', "math_type"),
        (
            'match kind:\n    case "trig_identity":\n        pass\n    case _:\n        pass\n',
            "math_type",
        ),
        ('if "수학" == subject_id:\n    pass\n', "subject"),
    ],
)
def test_literal_scanner_detects_injected_violation(probe: Any, source: str, kind: str) -> None:
    hits = probe.scan_literal_compares(source)
    assert len(hits) == 1 and hits[0].kind == kind, hits


@pytest.mark.parametrize(
    "source",
    [
        "if subject == other_subject:\n    pass\n",  # 변수 대 변수 — 리터럴 아님
        'x = "math"\n',  # 대입은 비교가 아니다(③ 어휘 스캔의 영역)
        '"""quadratic in a docstring"""\nif a == "apple":\n    pass\n',
        'if status == "pending":\n    pass\n',
    ],
)
def test_literal_scanner_ignores_non_violations(probe: Any, source: str) -> None:
    assert probe.scan_literal_compares(source) == []


def test_vocabulary_scanner_skips_docstrings_but_catches_data(probe: Any) -> None:
    src = '"""이차방정식을 다루는 모듈 — docstring은 제외."""\nLABEL = "이차함수"\n\n\ndef f():\n    """삼각함수 docstring"""\n    return "LaTeX 본문"\n'
    words = probe.scan_math_vocabulary(src)
    assert [t for _, t in words] == ["이차함수", "LaTeX 본문"], words


def test_reach_detects_an_injected_indirect_edge(probe: Any) -> None:
    """CORE→INFRA→ADAPTER 경유 간선을 가짜 그래프에 넣으면 잡히고, 교체점 경유는 잔여에서 빠진다."""
    graph = {
        "l2.bkt": {"ops.helper"},
        "ops.helper": {"l3.symbolic_equivalence"},
        "l4.polya.engine": {"composition"},
        "composition": {"l4.subject_adapter_math"},
        "l2.irt": {"schema.enums"},
    }
    verdict = {
        "l2.bkt": "CORE",
        "ops.helper": "INFRA",
        "l3.symbolic_equivalence": "ADAPTER",
        "l4.polya.engine": "CORE",
        "composition": "INFRA",
        "l4.subject_adapter_math": "ADAPTER",
        "l2.irt": "CORE",
        "schema.enums": "MIXED",
    }
    all_hits, residual = probe.transitive_reach(
        ["l2.bkt", "l4.polya.engine", "l2.irt"], graph, verdict
    )
    assert {r.source for r in all_hits} == {"l2.bkt", "l4.polya.engine"}
    assert {r.source for r in residual} == {"l2.bkt"}, residual
    assert next(r for r in all_hits if r.source == "l4.polya.engine").via_designed_seam


def test_bfs_tie_break_is_deterministic_across_hash_seeds(probe: Any) -> None:
    """같은 깊이의 ADAPTER가 둘이면 항상 사전순 첫 것으로 끝나야 한다 — set 순회 비결정성 회귀 방어.

    이웃 집합을 여러 삽입 순서로 만들어도 결과가 같아야 한다(set 순서는 삽입·해시에 따라 바뀐다).
    """
    verdict = {"a": "CORE", "m": "MIXED", "z_adapter": "ADAPTER", "b_adapter": "ADAPTER"}
    for order in (["z_adapter", "b_adapter"], ["b_adapter", "z_adapter"]):
        graph = {"a": {"m"}, "m": set(order)}
        assert probe.first_adapter_path("a", graph, verdict) == ("m", "b_adapter"), order


def test_probe_fails_loudly_when_core_population_is_empty(probe: Any, monkeypatch: Any) -> None:
    inv = probe._load_inventory()
    monkeypatch.setattr(inv, "_backend_modules", lambda: [])
    monkeypatch.setattr(probe, "_load_inventory", lambda: inv)
    with pytest.raises(RuntimeError, match="CORE 모듈 0"):
        probe.run_probe(lambda _msg: None)


# ──────────────────────────────────────────────────────────────────────
# ③ 정본 문서 배선
# ──────────────────────────────────────────────────────────────────────


def test_boundary_doc_records_the_measurement_and_points_at_the_probe() -> None:
    doc = _BOUNDARY_DOC.read_text(encoding="utf-8")
    assert "eos_core_boundary_probe.py" in doc
    assert "수학을 제거했을 때" in doc and "잔여 누수" in doc
