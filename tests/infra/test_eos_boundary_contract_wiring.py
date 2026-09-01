"""EOS Core↔Adapter 경계 계약의 **정합성 + 배선 실재** 동결 (EOS-67 acceptance ③).

이 저장소는 "만들었는데 안 도는 것"에 반복해서 뚫렸다(`tests/infra` 199건 미실행·브랜치
보호 required check 미강제·`tests/infra` lint 잡 부재). 그래서 계약을 하나 세울 때마다
**그것이 CI에서 실제로 실행되는지**를 기계가 대조한다(OPS-10 선례).

여기서 막는 것은 두 가지다.

1. **드리프트** — `pyproject.toml`의 forbidden 목록과 배정 정본(`BOUNDARY_MAP`)이 어긋나는 것.
   pyproject를 손으로 고치고 정본을 안 고치면(또는 반대) 이중 진실 원천이 된다.
2. **미배선** — 계약이 파일에는 있는데 CI 잡이 `lint-imports`를 부르지 않는 것.
   "pyproject에 존재함"과 "잡이 돌아감"은 다르다.

`lint-imports`의 *판정 자체*는 여기서 재현하지 않는다(그건 CI lint 스텝이 한다). 이 파일은
계약이 **올바른 대상을 가리키고 실제로 호출되는지**만 본다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "src" / "backend" / "pyproject.toml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_SCAN_SCRIPT = _REPO_ROOT / "scripts" / "analysis" / "eos_core_adapter_boundary_scan.py"
_BOUNDARY_DOC = _REPO_ROOT / "docs" / "architecture" / "eos_core_adapter_boundary.md"

_ROOT_PACKAGE = "whymath_backend"
_CONTRACT_NAME_PREFIX = "EOS Core → Math Adapter 금지"


def _load_boundary_map() -> dict[str, tuple[str, str]]:
    """배정 정본을 스크립트에서 직접 읽는다 — 목록을 여기 복사하면 진실이 셋이 된다."""
    name = "_eos_boundary_scan"
    spec = importlib.util.spec_from_file_location(name, _SCAN_SCRIPT)
    assert spec is not None and spec.loader is not None, f"스캔 스크립트 로드 불가: {_SCAN_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    # `@dataclass`가 어노테이션을 풀 때 sys.modules에서 자기 모듈을 찾는다 — 등록 없이
    # exec_module하면 AttributeError로 죽는다(실측 2026-08-31).
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    boundary_map: dict[str, tuple[str, str]] = module.BOUNDARY_MAP
    return boundary_map


def _contracts() -> list[dict[str, Any]]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    all_contracts: list[dict[str, Any]] = data["tool"]["importlinter"]["contracts"]
    return [c for c in all_contracts if str(c.get("name", "")).startswith(_CONTRACT_NAME_PREFIX)]


# ──────────────────────────────────────────────────────────────────────
# ① 드리프트 — 계약 목록 ↔ 배정 정본
# ──────────────────────────────────────────────────────────────────────


def test_eos_boundary_contracts_exist() -> None:
    contracts = _contracts()
    assert (
        len(contracts) == 2
    ), f"EOS 경계 계약이 2건이어야 한다(깨끗한 구역 / baseline 있음). 실측 {len(contracts)}건"
    assert {c["type"] for c in contracts} == {"forbidden"}


def test_forbidden_modules_match_the_adapter_assignment_exactly() -> None:
    """forbidden 목록 == BOUNDARY_MAP의 ADAPTER 키 전체. 어느 쪽이 빠져도 실패한다.

    빠지면 그 어댑터는 아무도 안 막고(위험), 남으면 존재하지 않는 모듈을 가리킨다(거짓 안심).
    """
    expected = {
        f"{_ROOT_PACKAGE}.{key}"
        for key, (verdict, _) in _load_boundary_map().items()
        if verdict == "ADAPTER"
    }
    assert expected, "정본에 ADAPTER 배정이 하나도 없다 — 스캔 스크립트 로드가 잘못됐다"

    for contract in _contracts():
        actual = set(contract["forbidden_modules"])
        missing = expected - actual
        extra = actual - expected
        assert (
            not missing
        ), f"[{contract['name']}] 정본에 있으나 계약에 없는 ADAPTER: {sorted(missing)}"
        assert not extra, f"[{contract['name']}] 계약에 있으나 정본에 없는 모듈: {sorted(extra)}"


def test_source_modules_are_never_adapter_assigned() -> None:
    """source에 ADAPTER 배정 모듈이 들어가면 안 된다 — 어댑터끼리의 의존을 위반으로 오판한다."""
    boundary = _load_boundary_map()
    adapters = {
        f"{_ROOT_PACKAGE}.{key}" for key, (verdict, _) in boundary.items() if verdict == "ADAPTER"
    }
    for contract in _contracts():
        offending = [src for src in contract["source_modules"] if src in adapters]
        assert not offending, f"[{contract['name']}] ADAPTER를 source로 잡았다: {offending}"


def test_clean_region_contract_carries_no_baseline() -> None:
    """'깨끗한 구역' 계약은 유예를 가지면 안 된다 — 유예가 붙는 순간 이름이 거짓이 된다."""
    clean = [c for c in _contracts() if "baseline 0" in c["name"]]
    assert len(clean) == 1, "baseline 0 계약이 정확히 1건이어야 한다"
    assert not clean[0].get(
        "ignore_imports"
    ), "깨끗한 구역 계약에 ignore_imports가 생겼다 — 깨끗하지 않다면 baseline 계약으로 옮겨라"


def test_baseline_entries_are_documented_as_debt_with_an_owner() -> None:
    """baseline 계약의 유예에는 해소 소유자(EOS-69)와 재확인 지점이 주석으로 붙어 있어야 한다.

    "만료 없는 유예 금지" — 만료의 1차 집행은 import-linter의
    `unmatched_ignore_imports_alerting`(기본 ERROR)이지만, *누가 언제* 갚는지는 사람이 읽는다.
    """
    raw = _PYPROJECT.read_text(encoding="utf-8")
    baseline_section = raw.split("그룹 ②", 1)
    assert len(baseline_section) == 2, "baseline 유예 그룹(② 주석)이 없다"
    body = baseline_section[1]
    assert "EOS-69" in body, "baseline 유예에 해소 소유자 태스크가 적혀 있지 않다"
    assert re.search(r"G1|2026-09-27", body), "baseline 유예에 재확인 지점이 적혀 있지 않다"


def test_baseline_ignores_do_not_silently_outlive_the_debt() -> None:
    """유예 만료가 *기계*로 걸려 있는지 — 기본 ERROR 정책을 끄지 않았는지 확인한다.

    `unmatched_ignore_imports_alerting = "none"`(또는 warn)으로 낮추면, 빚을 갚아도 유예 줄이
    조용히 남는다. 그 순간 이 계약의 만료 장치가 사라진다.
    """
    for contract in _contracts():
        level = contract.get("unmatched_ignore_imports_alerting", "error")
        assert str(level).lower() == "error", (
            f"[{contract['name']}] unmatched_ignore_imports_alerting={level!r} — "
            "ERROR가 아니면 갚은 빚의 유예 줄이 조용히 남는다"
        )


# ──────────────────────────────────────────────────────────────────────
# ② 배선 실재 — CI가 실제로 부르는가
# ──────────────────────────────────────────────────────────────────────


def test_ci_actually_runs_lint_imports() -> None:
    """'pyproject에 존재함'과 '잡이 돌아감'은 다르다 — CI가 lint-imports를 부르는지 대조."""
    ci = _CI_WORKFLOW.read_text(encoding="utf-8")
    assert re.search(
        r"(?m)^\s*run:\s*lint-imports\s*$", ci
    ), "ci.yml에 `run: lint-imports` 스텝이 없다 — 계약이 파일에만 있고 돌지 않는다"


def test_boundary_doc_and_scan_script_exist_as_the_referenced_sources() -> None:
    """계약 주석이 가리키는 정본·해설 파일이 실재하는지 — 링크가 썩으면 계약을 못 고친다."""
    assert _SCAN_SCRIPT.is_file(), f"배정 정본 스크립트 부재: {_SCAN_SCRIPT}"
    assert _BOUNDARY_DOC.is_file(), f"경계 해설 문서 부재: {_BOUNDARY_DOC}"
    pyproject = _PYPROJECT.read_text(encoding="utf-8")
    assert "eos_core_adapter_boundary_scan.py" in pyproject
    assert "eos_core_adapter_boundary.md" in pyproject


# ──────────────────────────────────────────────────────────────────────
# ③ 이 테스트 자체의 변별력 — 검사기가 고장나면 조용히 통과하지 않는가
# ──────────────────────────────────────────────────────────────────────


def test_boundary_map_loader_actually_returns_the_real_assignment() -> None:
    """로더가 빈 dict를 조용히 돌려주면 드리프트 검사는 '비교 대상 0건'으로 항상 통과한다.

    그 위장을 막기 위해, 로더가 실제 정본을 읽었다는 증거(알려진 키·4배정 전부)를 요구한다.
    """
    boundary = _load_boundary_map()
    assert len(boundary) > 30, f"정본 키가 너무 적다({len(boundary)}) — 로더가 실물을 못 읽었다"
    verdicts = {verdict for verdict, _ in boundary.values()}
    assert verdicts == {"CORE", "ADAPTER", "INFRA", "MIXED"}
    # 경계 문서가 근거로 드는 대표 배정 — 바뀌면 문서와 함께 고쳐야 한다
    assert boundary["l2"][0] == "CORE"
    assert boundary["l3.equivalent"][0] == "ADAPTER"
    assert boundary["l5.ocr"][0] == "ADAPTER"


# ──────────────────────────────────────────────────────────────────────
# ④ 조립 지점 예외 — 7계층 계약의 유일한 유예가 자라지 않는가 (EOS-69)
# ──────────────────────────────────────────────────────────────────────


def _layers_contract() -> dict[str, Any]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    contracts: list[dict[str, Any]] = data["tool"]["importlinter"]["contracts"]
    layered = [c for c in contracts if c.get("type") == "layers"]
    assert len(layered) == 1, f"layers 계약이 정확히 1건이어야 한다. 실측 {len(layered)}건"
    return layered[0]


def test_layers_contract_has_exactly_one_composition_root_exception() -> None:
    """7계층 계약의 유예는 **조립 지점 1건**뿐이어야 한다 — 예외가 조용히 자라지 못하게.

    EOS-69가 과목 어댑터 DI 좌석(`subject_registry`)을 세우면서, 좌석이 기본 구현체를
    만들어야 하는 탓에 `subject_registry -> l4.subject_adapter_math`라는 정적 간선 하나가
    남았다(논리적 방향은 이미 역전돼 있고, 남은 것은 그 그림자다). `layers` 계약은 간접
    체인까지 보므로 이것이 `l3 → l4`로 비친다.

    유예가 정당한 이유는 *하나*(의존성 역전의 조립 지점)뿐이므로, 유예도 하나여야 한다.
    두 번째 줄이 붙는 순간 그건 다른 사유이고, 다른 사유는 별도 판정을 받아야 한다.
    """
    ignores = _layers_contract().get("ignore_imports", [])
    assert ignores == [
        "whymath_backend.subject_registry -> whymath_backend.l4.subject_adapter_math"
    ], f"7계층 계약의 유예는 조립 지점 1건이어야 한다 — 실측 {ignores}"


def test_layers_exception_starts_at_the_composition_root_not_at_a_layer() -> None:
    """유예의 *출발점*이 계층이 아니라 조립 지점인지 — 계층에서 출발하면 그냥 역방향 의존이다.

    `l3.foo -> l4.bar` 같은 줄이 여기 들어오면 그것은 7계층 위반을 유예하는 것이지 의존성
    역전을 표기하는 것이 아니다. 출발점이 `layers` 목록 밖의 모듈이어야만 "조립 지점"이다.
    """
    contract = _layers_contract()
    layer_prefixes = tuple(str(layer) for layer in contract["layers"])
    for line in contract.get("ignore_imports", []):
        source = str(line).split("->", 1)[0].strip()
        assert not any(
            source == prefix or source.startswith(prefix + ".") for prefix in layer_prefixes
        ), f"유예의 출발점이 계층 안에 있다(= 그냥 역방향 의존): {line}"


def test_layers_exception_expiry_is_machine_enforced() -> None:
    """유예 만료가 기계로 걸려 있는지 — 기본 ERROR 정책을 끄지 않았는지 확인한다.

    EOS 계약과 같은 장치다(위 `test_baseline_ignores_do_not_silently_outlive_the_debt`).
    좌석이 구현체를 그만 알게 되면 이 줄이 매치되지 않아 CI가 삭제를 요구해야 한다.
    """
    level = _layers_contract().get("unmatched_ignore_imports_alerting", "error")
    assert str(level).lower() == "error", (
        f"layers 계약 unmatched_ignore_imports_alerting={level!r} — "
        "ERROR가 아니면 갚은 유예가 조용히 남는다"
    )
