"""시각화 도달률 관측 리포트 CLI 테스트 — 결정론·정직 회계·게이트 재사용 동결(hermetic).

대상: `whymath_backend.harness.visualization_reach_report`(VIZ-01 acceptance⑤). 실 DB·LLM·
네트워크 0 — 픽스처(dict payload)로 검증한다. 실 코퍼스 대상 스모크 테스트 1건만 실제
`data/corpus/*` 파일을 읽는다(회귀 감시용·상수 임계 없음).

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"):
  - 게이트 판정을 재구현하지 않고 `l4.visualization_policy.is_visualizable`를 그대로 재사용하는지
    — 그 함수를 monkeypatch해서 리포트 값이 바뀌는지로 실측한다(재구현이었다면 안 바뀐다).
  - 코퍼스 code가 카탈로그 code 공간과 어긋나면(orphan) 매치 0건이 되고 orphan 목록에 실린다.
  - 4분류 통제 어휘 밖 값은 조용히 버려지지 않고 `invalid_values`로 집계된다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness import visualization_reach_report as vrr


def _catalog_payload(entries: list[dict[str, object]]) -> dict[str, object]:
    return {"concepts": entries}


def _concept(code: str, *, name: str = "개념", level: str = "세부개념") -> dict[str, object]:
    return {"code": code, "name": name, "level": level}


def _style_payload(entries: list[dict[str, object]]) -> dict[str, object]:
    return {"version": "1.0", "entries": entries}


def _style_entry(code: str, styles: list[str]) -> dict[str, object]:
    return {"code": code, "recommended_styles": styles}


def _viz_payload(entries: list[dict[str, object]]) -> dict[str, object]:
    return {"version": "1.0", "entries": entries}


def _viz_entry(code: str, value: str) -> dict[str, object]:
    return {"code": code, "visualizability": value}


# ──────────────────────────────────────────────────────────────────────────
# 1. 로더 — 정상·정직 실패
# ──────────────────────────────────────────────────────────────────────────
def test_load_catalog_filters_to_leaf_level_only() -> None:
    """단원·소단원은 진단 대상이 아니므로 카탈로그에서 제외된다(세부개념만)."""
    catalog = vrr.load_catalog(
        _catalog_payload(
            [
                {"code": "U1", "name": "단원", "level": "단원"},
                {"code": "U1-S1", "name": "소단원", "level": "소단원"},
                _concept("A1"),
                _concept("A2"),
            ]
        )
    )
    assert {c.code for c in catalog} == {"A1", "A2"}


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"items": []},
        {"concepts": [{"name": "code 없음", "level": "세부개념"}]},
    ],
)
def test_load_catalog_rejects_malformed_payload(payload: object) -> None:
    with pytest.raises(ValueError):
        vrr.load_catalog(payload)


def test_load_style_corpus_preserves_raw_values() -> None:
    """어휘 검증 없이 원시 문자열 그대로 보존(오염값도 드러내기 위함)."""
    corpus = vrr.load_style_corpus(_style_payload([_style_entry("A1", ["함수그래프", "오염값"])]))
    assert corpus.entries == {"A1": ("함수그래프", "오염값")}


def test_load_visualization_corpus_preserves_raw_values() -> None:
    corpus = vrr.load_visualization_corpus(_viz_payload([_viz_entry("A1", "오염값")]))
    assert corpus.entries == {"A1": "오염값"}


def test_loaders_reject_malformed_payload() -> None:
    with pytest.raises(ValueError):
        vrr.load_style_corpus({"entries": [{"recommended_styles": ["x"]}]})  # code 없음
    with pytest.raises(ValueError):
        vrr.load_visualization_corpus({"entries": [{"code": "A1"}]})  # visualizability 없음


# ──────────────────────────────────────────────────────────────────────────
# 2. 집계 — 매치·orphan·정직 회계
# ──────────────────────────────────────────────────────────────────────────
def test_build_report_matches_and_orphans_separately() -> None:
    """카탈로그 code 공간과 어긋나는 코퍼스 항목은 orphan으로 분리되고 매치엔 안 잡힌다."""
    catalog = vrr.load_catalog(_catalog_payload([_concept("A1"), _concept("A2"), _concept("A3")]))
    style = vrr.load_style_corpus(
        _style_payload(
            [
                _style_entry("A1", ["함수그래프"]),
                _style_entry("LEGACY-CODE", ["단위원"]),  # 카탈로그에 없음 → orphan
            ]
        )
    )
    viz = vrr.load_visualization_corpus(_viz_payload([_viz_entry("A2", "직접")]))

    report = vrr.build_report(catalog, style, viz)
    assert report.catalog_total == 3
    assert report.style_matched_count == 1
    assert report.style_orphaned_codes == ("LEGACY-CODE",)
    assert report.style_untagged_codes == ("A2", "A3")
    assert report.visualization_matched_count == 1
    assert report.visualization_orphaned_codes == ()
    assert report.unclassified_both_codes == ("A3",)  # A1=style만·A2=viz만·A3=완전 미관측


def test_visualization_corpus_fully_orphaned_matches_viz01_d1_finding() -> None:
    """실제 D1 실측(레거시 437 code vs 원자 백본 code 불일치)을 소형 픽스처로 재현.

    코퍼스 전 항목이 카탈로그와 하나도 안 겹치면 매치 0·orphan 100%.
    """
    catalog = vrr.load_catalog(_catalog_payload([_concept("2수01-01-1")]))
    viz = vrr.load_visualization_corpus(_viz_payload([_viz_entry("MID-FUN-010", "직접")]))
    style = vrr.load_style_corpus(_style_payload([]))

    report = vrr.build_report(catalog, style, viz)
    assert report.visualization_matched_count == 0
    assert report.visualization_orphaned_codes == ("MID-FUN-010",)
    assert report.visualization_tagged_rate == 0.0


def test_invalid_visualizability_values_counted_not_dropped_silently() -> None:
    """4분류 통제 어휘 밖 값은 조용히 사라지지 않고 invalid_values로 집계된다."""
    catalog = vrr.load_catalog(_catalog_payload([_concept("A1")]))
    viz = vrr.load_visualization_corpus(_viz_payload([_viz_entry("A1", "존재하지않는분류")]))
    style = vrr.load_style_corpus(_style_payload([]))

    report = vrr.build_report(catalog, style, viz)
    assert report.visualization_matched_count == 0  # 오염값은 매치에 안 들어감
    assert report.visualization_invalid_values == {"존재하지않는분류": 1}


# ──────────────────────────────────────────────────────────────────────────
# 3. 게이트 통과율 — 실 게이트 재사용(재구현 아님)을 변별력 있게 실측
# ──────────────────────────────────────────────────────────────────────────
def test_gate_pass_requires_both_style_and_visualizable() -> None:
    """스타일만 있고 분류가 없으면(None) fail-open으로 통과·'추상'이면 보류."""
    catalog = vrr.load_catalog(
        _catalog_payload([_concept("A1"), _concept("A2"), _concept("A3"), _concept("A4")])
    )
    style = vrr.load_style_corpus(
        _style_payload(
            [
                _style_entry("A1", ["함수그래프"]),  # 분류 없음(None) → fail-open 통과
                _style_entry("A2", ["함수그래프"]),  # 분류=직접 → 통과
                _style_entry("A3", ["함수그래프"]),  # 분류=추상 → 보류
                # A4는 스타일 자체가 없음 → 게이트 미통과(AND 조건 좌변 거짓)
            ]
        )
    )
    viz = vrr.load_visualization_corpus(
        _viz_payload([_viz_entry("A2", "직접"), _viz_entry("A3", "추상")])
    )

    report = vrr.build_report(catalog, style, viz)
    assert report.gate_pass_count == 2  # A1(fail-open)·A2(직접)
    assert report.gate_withheld_abstain_count == 1  # A3
    assert report.gate_pass_rate == pytest.approx(2 / 4)


def test_gate_reuses_real_is_visualizable_not_a_reimplementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """변별력 핵심 — is_visualizable 몽키패치 시 리포트 값이 실제로 바뀐다(재구현이면 안 바뀜)."""
    catalog = vrr.load_catalog(_catalog_payload([_concept("A1")]))
    style = vrr.load_style_corpus(_style_payload([_style_entry("A1", ["함수그래프"])]))
    viz = vrr.load_visualization_corpus(_viz_payload([]))  # A1 미분류(None) → 기본 fail-open 통과

    baseline = vrr.build_report(catalog, style, viz)
    assert baseline.gate_pass_count == 1  # fail-open 통과(대조군)

    # is_visualizable을 "항상 False"로 몽키패치 — 리포트가 실제 함수를 호출한다면 0으로 바뀐다.
    # vrr은 `from ... import is_visualizable`로 이름을 자기 네임스페이스에 바인딩했으므로
    # build_report가 실제로 참조하는 건 vrr.is_visualizable이다(원본 모듈 패치는 무영향).
    monkeypatch.setattr(vrr, "is_visualizable", lambda v: False)
    mutated = vrr.build_report(catalog, style, viz)
    assert mutated.gate_pass_count == 0
    assert mutated.gate_pass_count != baseline.gate_pass_count

    monkeypatch.undo()
    restored = vrr.build_report(catalog, style, viz)
    assert restored.gate_pass_count == baseline.gate_pass_count == 1


# ──────────────────────────────────────────────────────────────────────────
# 4. 렌더·JSON — 결정론·정직 절단 표기
# ──────────────────────────────────────────────────────────────────────────
def test_render_report_is_deterministic_across_dict_insertion_order() -> None:
    catalog = vrr.load_catalog(_catalog_payload([_concept("A1"), _concept("A2")]))
    style_fwd = vrr.load_style_corpus(
        _style_payload([_style_entry("A1", ["함수그래프"]), _style_entry("A2", ["수직선"])])
    )
    style_rev = vrr.load_style_corpus(
        _style_payload([_style_entry("A2", ["수직선"]), _style_entry("A1", ["함수그래프"])])
    )
    viz = vrr.load_visualization_corpus(_viz_payload([]))

    r1 = vrr.render_report(vrr.build_report(catalog, style_fwd, viz))
    r2 = vrr.render_report(vrr.build_report(catalog, style_rev, viz))
    assert r1 == r2


def test_render_report_truncates_and_notes_remainder() -> None:
    entries = [_concept(f"A{i}") for i in range(10)]
    catalog = vrr.load_catalog(_catalog_payload(entries))
    style = vrr.load_style_corpus(_style_payload([]))
    viz = vrr.load_visualization_corpus(_viz_payload([]))

    report = vrr.build_report(catalog, style, viz)
    rendered = vrr.render_report(report, max_listed=3)
    assert "…외 **7**건" in rendered


def test_report_to_json_round_trips_key_fields() -> None:
    catalog = vrr.load_catalog(_catalog_payload([_concept("A1")]))
    style = vrr.load_style_corpus(_style_payload([_style_entry("A1", ["함수그래프"])]))
    viz = vrr.load_visualization_corpus(_viz_payload([]))
    report = vrr.build_report(catalog, style, viz)

    payload = vrr.report_to_json(report)
    assert payload["catalog_total"] == 1
    assert payload["gate"]["pass_count"] == 1
    assert payload["style"]["matched_count"] == 1

    dumped = vrr.dump_json(report)
    assert json.loads(dumped) == payload


# ──────────────────────────────────────────────────────────────────────────
# 5. CLI — exit 코드 규율(게이트 아님·입력 오류만 2)
# ──────────────────────────────────────────────────────────────────────────
def test_main_exit_0_even_when_reach_rate_is_zero(tmp_path: Path) -> None:
    """도달률 0%여도 exit 0 — 관측 리포트지 게이트가 아니다."""
    catalog_path = tmp_path / "graph.json"
    catalog_path.write_text(json.dumps(_catalog_payload([_concept("A1")])), encoding="utf-8")
    style_path = tmp_path / "style.json"
    style_path.write_text(json.dumps(_style_payload([])), encoding="utf-8")
    viz_path = tmp_path / "viz.json"
    viz_path.write_text(json.dumps(_viz_payload([])), encoding="utf-8")

    exit_code = vrr.main(
        [
            "--catalog",
            str(catalog_path),
            "--style-corpus",
            str(style_path),
            "--visualization-corpus",
            str(viz_path),
        ]
    )
    assert exit_code == 0


def test_main_exit_2_on_missing_catalog_file(tmp_path: Path) -> None:
    exit_code = vrr.main(["--catalog", str(tmp_path / "없음.json")])
    assert exit_code == 2


def test_main_writes_json_artifact(tmp_path: Path) -> None:
    catalog_path = tmp_path / "graph.json"
    catalog_path.write_text(json.dumps(_catalog_payload([_concept("A1")])), encoding="utf-8")
    style_path = tmp_path / "style.json"
    style_path.write_text(json.dumps(_style_payload([])), encoding="utf-8")
    viz_path = tmp_path / "viz.json"
    viz_path.write_text(json.dumps(_viz_payload([])), encoding="utf-8")
    out_path = tmp_path / "out" / "report.json"

    exit_code = vrr.main(
        [
            "--catalog",
            str(catalog_path),
            "--style-corpus",
            str(style_path),
            "--visualization-corpus",
            str(viz_path),
            "--json",
            str(out_path),
        ]
    )
    assert exit_code == 0
    assert out_path.is_file()
    assert json.loads(out_path.read_text(encoding="utf-8"))["catalog_total"] == 1


# ──────────────────────────────────────────────────────────────────────────
# 6. 실 코퍼스 스모크(회귀 감시 — 임계 단언 없음)
# ──────────────────────────────────────────────────────────────────────────
def test_real_corpora_smoke() -> None:
    """실제 data/corpus 3파일을 읽어 리포트가 구성되는지만 확인(임계값 assert 없음·회귀 감시용)."""
    if not vrr.DEFAULT_CATALOG_PATH.is_file():
        pytest.skip("data/corpus/atom_graph_v1/graph.json 미존재")
    catalog = vrr.load_catalog(json.loads(vrr.DEFAULT_CATALOG_PATH.read_text(encoding="utf-8")))
    style = vrr.load_style_corpus(
        json.loads(vrr.DEFAULT_STYLE_CORPUS_PATH.read_text(encoding="utf-8"))
    )
    viz = vrr.load_visualization_corpus(
        json.loads(vrr.DEFAULT_VISUALIZATION_CORPUS_PATH.read_text(encoding="utf-8"))
    )
    report = vrr.build_report(catalog, style, viz)
    assert report.catalog_total > 0
    assert report.style_matched_count > 0  # VIZ-01 신설 코퍼스가 실제로 매치됨(회귀 감시)
    assert isinstance(vrr.render_report(report), str)
    assert isinstance(vrr.dump_json(report), str)
