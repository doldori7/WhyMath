"""EOS 기능 인벤토리 v2 — 장부 동결·전수성·결함 주입 (EOS-83 acceptance ④).

여기서 막는 것은 셋이다.

1. **드리프트** — `backlog/inventory/feature_inventory_v2.{yaml,csv}`가 생성기 출력과 다르다.
   장부만 손으로 고치거나 카탈로그만 고치고 `--write`를 안 돌리면 이중 진실 원천이 된다.
2. **전수성 붕괴** — 백엔드 모듈·엔드포인트·Flutter feature 중 어느 행에도 귀속되지 않은 것이
   생겼는데 생성기가 조용히 통과한다. 모듈이 하나 추가되면 이 테스트가 RED가 되어야 한다.
3. **위장 가드** — 전수성 검사가 *모든* 입력에서 초록인 것(CLAUDE.md 2026-09-01 "실패 주입 없이
   보호 있음 선언 금지"). 그래서 카탈로그를 실제로 깨뜨려(모듈 중복 귀속·엔드포인트 미귀속·
   플래그 오타) 각각이 exit 1을 내는지 확인한다.

생성기의 *판정 자체*(6축 점수)는 여기서 재현하지 않는다 — 임계는 v1에서 import되고 v1의 규칙은
`eos_feature_inventory_migration_map.md`가 소유한다. 이 파일은 v2가 **올바른 모집단을 전부
보고 실제로 실패할 수 있는지**만 본다.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "analysis" / "eos_feature_inventory_v2.py"
_V1_SCRIPT = _REPO_ROOT / "scripts" / "analysis" / "eos_feature_inventory.py"
_LEDGER_YAML = _REPO_ROOT / "backlog" / "inventory" / "feature_inventory_v2.yaml"
_LEDGER_CSV = _REPO_ROOT / "backlog" / "inventory" / "feature_inventory_v2.csv"
_DOC = _REPO_ROOT / "docs" / "reviews" / "eos_feature_inventory_v2_2026-09-03.md"
_V1_DOC = _REPO_ROOT / "docs" / "reviews" / "eos_feature_inventory_migration_map.md"

REQUIRED_FIELDS = (
    "feature_id",
    "name",
    "location",
    "user",
    "domain",
    "eos_ownership",
    "eos_target",
    "status",
    "coupling",
    "tests",
    "migration_action",
    "matrix_action",
    "release_priority_proposed",
    "migration_risk",
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `@dataclass`가 어노테이션을 풀 때 sys.modules에서 자기 모듈을 찾는다(실측 2026-08-31).
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@pytest.fixture(scope="module")
def gen() -> Any:
    return _load(_SCRIPT, "_eos_inventory_v2_under_test")


@pytest.fixture(scope="module")
def measured(gen: Any) -> tuple[list[Any], dict[str, Any]]:
    logs: list[str] = []
    rows, info = gen.measure(logs.append)
    assert not info["errors"], "\n".join(info["errors"])
    return rows, info


# ──────────────────────────────────────────────────────────────────────
# ① 드리프트 — 장부 == 생성기 출력
# ──────────────────────────────────────────────────────────────────────


def test_yaml_ledger_matches_generator_output(gen: Any, measured: Any) -> None:
    rows, info = measured
    expected = gen.to_yaml(rows, gen.dashboard(rows, info))
    assert _LEDGER_YAML.read_text(encoding="utf-8") == expected, (
        "feature_inventory_v2.yaml이 생성기 출력과 다르다 — "
        "`python3 scripts/analysis/eos_feature_inventory_v2.py --write`로 재생성"
    )


def test_csv_ledger_matches_generator_output_and_has_bom(gen: Any, measured: Any) -> None:
    rows, _ = measured
    raw = _LEDGER_CSV.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "CSV는 utf-8-sig(BOM) — 한국어 Windows Excel 호환"
    assert raw.decode("utf-8-sig") == gen.to_csv(rows)


def test_csv_has_every_required_field_as_a_column(gen: Any) -> None:
    header = next(csv.reader(io.StringIO(_LEDGER_CSV.read_text(encoding="utf-8-sig"))))
    for col in ("Feature ID", "기능명", "현재 위치", "사용자", "Domain", "EOS Ownership",
                "EOS 대상", "상태", "결합도", "테스트", "Migration Action", "출시 우선도(제안)",
                "Migration Risk"):  # fmt: skip
        assert col in header, f"CSV 헤더에 {col!r} 없음"
    assert header == gen.CSV_HEADER


# ──────────────────────────────────────────────────────────────────────
# ② 전수성 — 모집단이 실제로 전부 덮였는가
# ──────────────────────────────────────────────────────────────────────


def test_population_is_feature_grained_not_router_grained(measured: Any) -> None:
    rows, _ = measured
    v1_population = 23  # v1 = 라우터 22 + app-core 1
    assert len(rows) >= 100, f"기능 단위 모집단이 {len(rows)}행 — 카탈로그 붕괴"
    assert len(rows) > v1_population * 4


def test_every_backend_module_is_owned_exactly_once(gen: Any, measured: Any) -> None:
    rows, info = measured
    universe = set(gen._backend_modules())
    assert info["backend_modules"] == len(universe) > 500
    owned: dict[str, str] = {}
    for r in rows:
        for m in r.own_modules:
            assert m not in owned or r.spec.plane == "S", f"{m}: {owned[m]}와 {r.spec.fid} 중복"
            owned[m] = r.spec.fid
    assert universe <= set(owned), sorted(universe - set(owned))


def test_every_included_router_has_serving_rows_and_all_endpoints_are_owned(
    gen: Any, measured: Any
) -> None:
    rows, info = measured
    app_src = (gen.BACKEND / "app.py").read_text(encoding="utf-8")
    included = {a.removesuffix("_router") for a in
                __import__("re").findall(r"app\.include_router\((\w+)\)", app_src)}  # fmt: skip
    routers_with_rows = {r.spec.router for r in rows if r.spec.plane == "S"}
    assert included <= routers_with_rows, sorted(included - routers_with_rows)
    total_eps = sum(len(gen._endpoints(r)) for r in routers_with_rows)
    assert info["endpoints"] == total_eps == sum(r.endpoints for r in rows if r.spec.plane == "S")


def test_every_flutter_feature_directory_is_claimed(gen: Any) -> None:
    features = {p.name for p in (gen.MOBILE / "lib" / "features").iterdir() if p.is_dir()}
    claimed = {
        r.split("/")[3]
        for s in gen.CATALOG
        if s.plane == "C"
        for r in s.client
        if r.startswith("mobile/lib/features/")
    }
    assert features <= claimed, sorted(features - claimed)


def test_rows_carry_every_plan_100_field_with_closed_vocabulary(gen: Any, measured: Any) -> None:
    rows, info = measured
    text = gen.to_yaml(rows, gen.dashboard(rows, info))
    for f in REQUIRED_FIELDS:
        # 첫 필드는 리스트 항목 머리("  - feature_id:"), 나머지는 4칸 들여쓰기
        marker = f"  - {f}: " if f == "feature_id" else f"    {f}: "
        assert text.count(marker) == len(rows), f"{f} 필드가 전 행에 없다"
    for r in rows:
        assert r.ownership in gen.OWNERSHIP_VOCAB
        assert r.spec.priority in gen.PRIORITIES
        assert r.migration_action in {*(v for _, v in _load(_V1_SCRIPT, "_v1").BANDS), "POSTPONE"}
        assert r.migration_risk in {"High", "Med", "Low"}
        assert r.coupling in {"High", "Med", "Low"}
        assert r.tests in {"Full", "Partial", "None"}


def test_ownership_is_derived_from_boundary_map_not_declared(gen: Any, measured: Any) -> None:
    """카탈로그에 ownership 필드가 *없다* — 배정 정본(EOS-65)에서만 나온다."""
    rows, _ = measured
    assert not hasattr(gen.Spec, "ownership")
    by_fid = {r.spec.fid: r for r in rows}
    assert by_fid["WM-E-353"].ownership == "ADAPTER"  # symbolic_equivalence — 어댑터 정본 그대로
    assert by_fid["WM-E-201"].ownership == "CORE"  # l2 — 수학 신호 0 실측 구역
    assert by_fid["WM-E-801"].ownership == "MIXED"  # schema.problem 등 MIXED 포함
    assert by_fid["WM-S-029"].ownership == "CORE+ADAPTER_DEP"  # verify 표면 → l3.verify_*
    assert all(r.ownership == "CLIENT" for r in rows if r.spec.plane == "C")


def test_postpone_overrides_only_p2_p3_and_preserves_matrix_verdict(measured: Any) -> None:
    rows, _ = measured
    for r in rows:
        if r.release_priority in ("P2", "P3"):
            assert r.migration_action == "POSTPONE" and r.matrix_action != "POSTPONE"
        else:
            assert r.migration_action != "POSTPONE"


# ──────────────────────────────────────────────────────────────────────
# ②-c P0~P3 — "이 기능이 없으면 12/31 폐쇄루프가 깨지는가"를 기계가 답하는가
# ──────────────────────────────────────────────────────────────────────


def test_every_loop_seed_route_and_module_actually_exists(gen: Any, measured: Any) -> None:
    """씨앗이 사라진 엔드포인트·모듈을 가리키면 도달성 전체가 조용히 비어 P0가 0이 된다 — 그래서 실재를 검사."""
    _, info = measured
    assert not [e for e in info["errors"] if "씨앗" in e]
    assert info["student_loop_reach"] > 50 and info["production_loop_reach"] > 50


def test_release_priority_is_derived_and_every_p0_carries_loop_evidence(
    gen: Any, measured: Any
) -> None:
    rows, _ = measured
    for r in rows:
        assert r.release_priority in gen.PRIORITIES and r.priority_basis, r.spec.fid
        if r.release_priority == "P0":
            assert any(r.loop_hits.values()), f"{r.spec.fid}: P0인데 폐쇄루프 근거가 없다"
        if r.release_priority == "P3":
            assert r.spec.horizon == "P3", f"{r.spec.fid}: P3는 horizon 선언으로만 생긴다"
    assert sum(1 for r in rows if r.release_priority == "P0") >= 60


def test_flag_off_modules_reached_only_statically_are_not_p0(measured: Any) -> None:
    """정적 import로 닿았지만 플래그가 꺼진 기능은 없어도 루프가 안 깨진다 — P1(우회 가능)."""
    rows, _ = measured
    for r in rows:
        only_reach = set(k for k, v in r.loop_hits.items() if v) <= {
            "student_loop",
            "production_loop",
        }
        if r.status in ("Flag-off", "Shadow") and only_reach and any(r.loop_hits.values()):
            assert r.release_priority == "P1", r.spec.fid


def test_invariant_contracts_are_p0_regardless_of_reach(measured: Any) -> None:
    by_fid = {r.spec.fid: r for r in rows} if (rows := measured[0]) else {}
    for fid in ("WM-S-007", "WM-S-009", "WM-S-023", "WM-O-901", "WM-E-305", "WM-E-803"):
        assert by_fid[fid].release_priority == "P0" and by_fid[fid].loop_hits["invariant"], fid


def test_client_rows_are_p0_only_via_seed_route_literal_or_declared_seed(measured: Any) -> None:
    rows, _ = measured
    for r in rows:
        if r.spec.plane == "C" and r.release_priority == "P0":
            assert r.client_seed_routes > 0 or r.spec.loop_seed, r.spec.fid
        if r.spec.plane == "C" and r.client_seed_routes == 0 and not r.spec.loop_seed:
            assert r.release_priority != "P0", r.spec.fid


def test_prior_manual_priority_is_kept_for_the_diff_not_used_for_p0(
    gen: Any, measured: Any
) -> None:
    rows, info = measured
    text = gen.to_yaml(rows, gen.dashboard(rows, info))
    assert text.count("    release_priority_prior_manual: ") == len(rows)
    demoted = [r for r in rows if r.spec.priority == "P0" and r.release_priority == "P1"]
    assert demoted, "선행 P0 중 기계가 강등한 행이 0 — 도달성 규칙이 선행 제안을 그대로 베낀 것"
    for r in demoted:
        assert "강등" in r.priority_basis or "우회 가능" in r.priority_basis, r.spec.fid


# ──────────────────────────────────────────────────────────────────────
# ②-b §3.4 KEEP/REFACTOR/REPLACE/POSTPONE 기준 — 서술형 기준이 실제로 판정을 결정하는가
# ──────────────────────────────────────────────────────────────────────


def test_every_row_carries_the_measurable_34_criteria(gen: Any, measured: Any) -> None:
    rows, _ = measured
    keep_keys = {f"k{i}" for i in range(1, 7)}
    replace_keys = {f"r{i}" for i in range(1, 7)}
    for r in rows:
        assert {k[:2] for k in r.criteria} == keep_keys | replace_keys, r.spec.fid
        assert r.keep_met == sum(v for k, v in r.criteria.items() if k.startswith("k"))
        assert r.replace_signals == sum(v for k, v in r.criteria.items() if k.startswith("r"))
        assert r.criteria_action in {"KEEP", "REFACTOR", "REPLACE_CANDIDATE", "POSTPONE"}
        assert r.action_basis, f"{r.spec.fid}: 판정 근거 문자열이 비었다"
    assert gen.KEEP_MIN_CRITERIA == 5 and gen.REPLACE_MIN_SIGNALS == 3


def test_final_action_follows_the_combined_rule_row_by_row(gen: Any, measured: Any) -> None:
    """POSTPONE=P2 · REPLACE=매트릭스 14+ 또는 신호≥3 · HEAVY=매트릭스 10~13 · KEEP=§3.4 ≥5/6 · 나머지 REFACTOR."""
    rows, _ = measured
    for r in rows:
        if r.release_priority in ("P2", "P3"):
            expected = "POSTPONE"
        elif r.matrix_action == "REPLACE_CANDIDATE" or r.replace_signals >= gen.REPLACE_MIN_SIGNALS:
            expected = "REPLACE_CANDIDATE"
        elif r.matrix_action == "HEAVY_REFACTOR":
            expected = "HEAVY_REFACTOR"
        elif r.keep_met >= gen.KEEP_MIN_CRITERIA:
            expected = "KEEP"
        else:
            expected = "REFACTOR"
        assert r.migration_action == expected, (r.spec.fid, r.migration_action, expected)


def test_keep_is_never_granted_below_five_of_six_criteria(measured: Any) -> None:
    """§3.4 '대부분 만족' — 5/6 미만인데 KEEP인 행이 하나라도 있으면 기준이 판정을 결정하지 않는다."""
    rows, _ = measured
    offenders = [r.spec.fid for r in rows if r.migration_action == "KEEP" and r.keep_met < 5]
    assert not offenders, offenders
    assert any(
        r.migration_action == "REFACTOR" and r.matrix_action == "KEEP" for r in rows
    ), "매트릭스 KEEP인데 §3.4 기준 미달로 REFACTOR가 된 행이 0 — 기준이 변별력을 내지 않는다"


def test_replace_needs_multiple_signals_not_a_single_one(measured: Any) -> None:
    """단독 신호(예: 테스트 0건)로 REPLACE를 선고하지 않는다 — 계획서 100 '경계 복구 불가일 때만'."""
    rows, _ = measured
    for r in rows:
        if r.replace_signals <= 2 and r.matrix_action != "REPLACE_CANDIDATE":
            assert r.migration_action != "REPLACE_CANDIDATE", r.spec.fid


def test_duplicate_of_points_at_an_existing_row(gen: Any) -> None:
    fids = {s.fid for s in gen.CATALOG}
    for s in gen.CATALOG:
        if s.duplicate_of:
            assert s.duplicate_of in fids and s.duplicate_of != s.fid, s.fid


def test_criteria_react_to_injected_defects(gen: Any) -> None:
    """가드 변별력 — 테스트가 없다고 위장한 행은 k3·k6이 꺼지고 r3이 켜져야 한다."""
    rows, _ = gen.measure(lambda _msg: None)
    row = next(r for r in rows if r.spec.fid == "WM-E-201")
    assert row.criteria["k3_tests_exist"] and not row.criteria["r3_untestable"]
    row.test_functions = 0
    gen._score(row, gen._load_script(gen.V1_SCRIPT, "_v1_for_mutation"))
    assert not row.criteria["k3_tests_exist"] and not row.criteria["k6_verified"]
    assert row.criteria["r3_untestable"] and row.migration_action != "KEEP"


def test_status_follows_measured_flag_default(gen: Any, measured: Any) -> None:
    rows, _ = measured
    defaults = gen._config_defaults()
    assert defaults["ocr_enabled"] == "False"  # 실측 전제 — 바뀌면 이 단언과 장부가 함께 바뀐다
    by_fid = {r.spec.fid: r for r in rows}
    assert (
        by_fid["WM-S-046"].status == "Flag-off" and "ocr_enabled" in by_fid["WM-S-046"].flag_default
    )
    assert by_fid["WM-E-704"].status == "Production"  # wh1_primary_enabled=True


def test_matrix_thresholds_are_imported_from_v1_not_redefined(gen: Any) -> None:
    src = _SCRIPT.read_text(encoding="utf-8")
    for const in ("B_DBMODEL", "C_IMPORTS", "D_TESTFN", "E_WRITES", "F_TABLES", "BANDS"):
        assert (
            f"{const} =" not in src and f"{const}=" not in src
        ), f"v2가 {const}를 재정의 — 이중 정본"
    assert "V1_SCRIPT" in src


# ──────────────────────────────────────────────────────────────────────
# ③ 결함 주입 — 가드가 실제로 RED를 내는가
# ──────────────────────────────────────────────────────────────────────


def _run_with_catalog(gen: Any, catalog: tuple[Any, ...]) -> list[str]:
    original = gen.CATALOG
    gen.CATALOG = catalog
    try:
        _, info = gen.measure(lambda _msg: None)
    finally:
        gen.CATALOG = original
    errors: list[str] = info["errors"]
    return errors


def test_duplicate_module_ownership_is_detected(gen: Any) -> None:
    dup = replace(gen.CATALOG[-1], fid="WM-X-DUP", plane="E", modules=("l2.bkt",), client=())
    errors = _run_with_catalog(gen, (*gen.CATALOG, dup))
    assert any("l2.bkt" in e and "이미 귀속" in e for e in errors), errors


def test_unowned_endpoint_is_detected(gen: Any) -> None:
    trimmed = tuple(
        (
            replace(s, routes=tuple(r for r in s.routes if r != "GET /next-problem"))
            if s.fid == "WM-S-021"
            else s
        )
        for s in gen.CATALOG
    )
    errors = _run_with_catalog(gen, trimmed)
    assert any("미귀속 엔드포인트" in e and "/next-problem" in e for e in errors), errors


def test_unowned_module_is_detected(gen: Any) -> None:
    trimmed = tuple(
        (
            replace(s, modules=tuple(m for m in s.modules if m != "l2.bkt"))
            if s.fid == "WM-E-201"
            else s
        )
        for s in gen.CATALOG
    )
    errors = _run_with_catalog(gen, trimmed)
    assert any("미귀속 모듈: l2.bkt" in e for e in errors), errors


def test_unknown_flag_name_fails_loudly(gen: Any) -> None:
    broken = tuple(
        replace(s, flag="ocr_enabeld_typo") if s.fid == "WM-S-046" else s for s in gen.CATALOG
    )
    original = gen.CATALOG
    gen.CATALOG = broken
    try:
        with pytest.raises(KeyError, match="ocr_enabeld_typo"):
            gen.measure(lambda _msg: None)
    finally:
        gen.CATALOG = original


def test_main_refuses_to_write_when_population_is_incomplete(gen: Any, tmp_path: Path) -> None:
    original_catalog, original_yaml, original_csv = gen.CATALOG, gen.LEDGER_YAML, gen.LEDGER_CSV
    gen.CATALOG = original_catalog[:10]
    gen.LEDGER_YAML, gen.LEDGER_CSV = tmp_path / "v2.yaml", tmp_path / "v2.csv"
    try:
        assert gen.main(["--write"]) == 1
        assert not (tmp_path / "v2.yaml").exists(), "전수성 위반인데 장부를 썼다"
    finally:
        gen.CATALOG, gen.LEDGER_YAML, gen.LEDGER_CSV = original_catalog, original_yaml, original_csv


# ──────────────────────────────────────────────────────────────────────
# ④ 문서 배선 — 해설 문서가 장부·v1을 서로 가리킨다
# ──────────────────────────────────────────────────────────────────────


def test_docs_reference_each_other_and_the_ledger() -> None:
    doc = _DOC.read_text(encoding="utf-8")
    assert "feature_inventory_v2.yaml" in doc and "eos_feature_inventory_v2.py" in doc
    assert "eos_feature_inventory_migration_map.md" in doc, "v1 관계 미명기"
    assert "eos_feature_inventory_v2_2026-09-03.md" in _V1_DOC.read_text(
        encoding="utf-8"
    ), "v1 문서가 v2를 가리키지 않는다 — 두 장부의 관계는 양쪽에 적는다"
