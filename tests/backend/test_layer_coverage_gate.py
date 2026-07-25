"""계층별 커버리지 게이트(`scripts/coverage/check_layer_coverage.py`) hermetic 테스트.

합성 coverage.xml로 게이트의 **변별력**을 동결한다("변별력 없는 검증 스텝 금지"):
바닥선 이상이면 PASS(exit 0)·미달이면 FAIL(exit 1)·무측정(라인 0)이면 성공 위장 대신
명시 실패. coverage.xml 파싱(서브패키지 집계)도 함께 검증한다. DB·네트워크 0.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "coverage" / "check_layer_coverage.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("check_layer_coverage", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_xml(path: Path, per_layer: dict[str, tuple[int, int]], prefix: str = "") -> None:
    """per_layer: {계층: (covered, total)} → 최소 coverage.xml 생성.

    filename은 실제 coverage.xml처럼 <source>(=whymath_backend) 기준 *상대경로*(`l4/mod.py`)가
    기본이다 — CI 실측 포맷 재현(2026-07-25 파서 버그 회귀 방지). prefix로 `whymath_backend/`·
    절대경로 변형도 검증한다.
    """
    classes = []
    for layer, (covered, total) in per_layer.items():
        lines = "".join(
            f'<line number="{i + 1}" hits="{1 if i < covered else 0}"/>' for i in range(total)
        )
        classes.append(f'<class filename="{prefix}{layer}/mod.py"><lines>{lines}</lines></class>')
    path.write_text(
        '<?xml version="1.0" ?><coverage><packages><package><classes>'
        + "".join(classes)
        + "</classes></package></packages></coverage>",
        encoding="utf-8",
    )


def test_layer_coverage_parses_relative_filenames(tmp_path: Path) -> None:
    # 실제 CI coverage.xml 포맷: <source>=whymath_backend 기준 상대경로(`l4/mod.py`).
    mod = _load()
    xml = tmp_path / "coverage.xml"
    _write_xml(xml, {"l4": (90, 100), "l1": (7, 10)})  # prefix="" (상대)
    cov = mod.layer_coverage(str(xml))
    assert cov["l4"] == (90, 100)
    assert cov["l1"] == (7, 10)


def test_layer_coverage_parses_prefixed_filenames(tmp_path: Path) -> None:
    # 절대경로/whymath_backend 접두 변형도 동일하게 집계(파서 견고성).
    mod = _load()
    xml = tmp_path / "coverage.xml"
    _write_xml(xml, {"l4": (80, 100)}, prefix="/home/runner/work/whymath_backend/")
    cov = mod.layer_coverage(str(xml))
    assert cov["l4"] == (80, 100)


def test_gate_passes_when_all_layers_meet_floor(tmp_path: Path) -> None:
    mod = _load()
    xml = tmp_path / "coverage.xml"
    # 모든 게이트 계층을 바닥선 이상으로.
    _write_xml(xml, {layer: (95, 100) for layer in mod.LAYER_FLOORS})
    assert mod.main([str(xml)]) == 0


def test_gate_fails_when_one_layer_below_floor(tmp_path: Path) -> None:
    mod = _load()
    # 바닥선을 인위로 올려 미달을 강제(실측 무관 결정론).
    mod.LAYER_FLOORS = {"l4": 90.0, "l1": 80.0}
    xml = tmp_path / "coverage.xml"
    _write_xml(xml, {"l4": (95, 100), "l1": (50, 100)})  # l1 50% < 80%
    failed, unmeasured = mod.evaluate(mod.layer_coverage(str(xml)), mod.LAYER_FLOORS)
    assert failed == ["l1"]
    assert unmeasured == []
    assert mod.main([str(xml)]) == 1


def test_gate_fails_on_unmeasured_layer(tmp_path: Path) -> None:
    mod = _load()
    mod.LAYER_FLOORS = {"l4": 50.0, "api": 50.0}
    xml = tmp_path / "coverage.xml"
    _write_xml(xml, {"l4": (60, 100)})  # api 미측정(라인 0)
    failed, unmeasured = mod.evaluate(mod.layer_coverage(str(xml)), mod.LAYER_FLOORS)
    assert "api" in unmeasured
    assert "api" in failed
    assert mod.main([str(xml)]) == 1  # 성공 위장 대신 명시 실패


def test_boundary_exactly_at_floor_passes(tmp_path: Path) -> None:
    mod = _load()
    mod.LAYER_FLOORS = {"l4": 60.0}
    xml = tmp_path / "coverage.xml"
    _write_xml(xml, {"l4": (60, 100)})  # 정확히 60% == 바닥선
    assert mod.main([str(xml)]) == 0
