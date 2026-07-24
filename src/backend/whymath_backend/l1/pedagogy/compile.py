"""소단원 DSL 컴파일 CLI — `whymath_backend.l1.pedagogy.compile`.

`.unit.yaml` 한 편을 받아 참조 검증 후 *발주서*(work order)와 행 수를 출력하고, `--seed`면
`unit_spec`+`learning_objective`에 멱등 적재한다. `l1/pedagogy/populate`(교수법 팩)·`l1/standards/
populate`(성취기준) CLI의 *소단원* 짝이며 같은 골격을 따른다(argparse·`main(argv)->int`·파일 부재
`return 2`·stdout 보고). 컴파일 로직은 `unit_compiler`가 담당하고 본 CLI는 경로 결선·실행·보고만.

종료 코드: 0=성공 · 1=참조 검증 실패(CompileError·미해결 참조 목록 출력) · 2=입력 파일 부재.

사용:
    # 드라이런(검증 + 발주서 출력·적재 없음)
    python -m whymath_backend.l1.pedagogy.compile data/corpus/units_v1/quadratic_maxmin.unit.yaml
    # 적재까지
    python -m whymath_backend.l1.pedagogy.compile <unit.yaml> --seed
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.l1.pedagogy.unit_compiler import (
    CompiledUnit,
    CompileError,
    UnitSpecStore,
    compile_unit,
    load_packs,
    load_statements_by_code,
    load_valid_atom_codes,
)

# 코퍼스 기본 경로 — 레포 루트 기준으로 고정(cwd 무관 해석). 이 파일은
# src/backend/whymath_backend/l1/pedagogy/compile.py라 parents[5]가 레포 루트다. 이렇게 하면
# src/backend에서 실행하든 레포 루트에서 실행하든 기본 코퍼스가 동일하게 잡힌다(다른 populate
# CLI는 cwd=레포 루트 전제라 상대경로를 썼지만, 이 CLI는 검증 실행 cwd=src/backend를 함께 지원).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_ATOM_GRAPH = _REPO_ROOT / "data" / "corpus" / "atom_graph_v1" / "graph.json"
_DEFAULT_STANDARDS = _REPO_ROOT / "data" / "corpus" / "standards_v1" / "standards.json"
_DEFAULT_PACKS_DIR = _REPO_ROOT / "data" / "corpus" / "pedagogy_packs_v1"


def _print_work_order(compiled: CompiledUnit) -> None:
    """발주서(work order)와 행 수를 stdout에 보고 — 콘텐츠 생성 계층이 소비할 슬롯 주문 목록."""
    row = compiled.unit_spec_row
    print(
        f"소단원 컴파일: {row['unit_id']} v{row['unit_version']} "
        f"('{row['title']}'·compiler={row['compiler_ver']}·sha256={row['yaml_sha256'][:12]}…)"
    )
    print(f"  unit_spec 행: 1 · learning_objective 행: {len(compiled.objective_rows)}")
    print(f"  발주서(work order) 항목: {len(compiled.work_order)}줄")
    print("  ── 슬롯 발주 ──")
    total = 0
    for item in compiled.work_order:
        total += item["count"]
        print(f"    {item['objective_id']:<40} {item['slot_type']:<24} × {item['count']}")
    print(f"  ── 총 콘텐츠 수요: {total}점 ──")


def main(argv: list[str] | None = None) -> int:
    """소단원 DSL을 컴파일해 발주서를 출력(드라이런)하거나 `--seed`면 적재까지 한다(CLI 본체).

    반환은 종료 코드(0=성공·1=참조 검증 실패·2=입력 파일 부재). 컴파일 로직은 `compile_unit`이
    담당하며 본 함수는 경로 결선·실행·보고만 한다(조용한 무동작 금지 — 부재·실패 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-unit-compile",
        description=(
            "소단원 DSL(.unit.yaml) → unit_spec/learning_objective 행 + 발주서 컴파일. "
            "기본은 드라이런(검증+발주서 출력), --seed면 멱등 적재까지."
        ),
    )
    parser.add_argument("unit_yaml", type=Path, help="소단원 DSL 파일(.unit.yaml) 경로.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="검증 후 unit_spec·learning_objective에 멱등 적재(생략 시 드라이런).",
    )
    parser.add_argument(
        "--atom-graph",
        type=Path,
        default=_DEFAULT_ATOM_GRAPH,
        help=f"원자 백본 그래프 JSON 경로(기본 {_DEFAULT_ATOM_GRAPH}).",
    )
    parser.add_argument(
        "--standards",
        type=Path,
        default=_DEFAULT_STANDARDS,
        help=f"성취기준 Collection JSON 경로(기본 {_DEFAULT_STANDARDS}).",
    )
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=_DEFAULT_PACKS_DIR,
        help=f"교수법 팩 YAML 디렉터리 경로(기본 {_DEFAULT_PACKS_DIR}).",
    )
    args = parser.parse_args(argv)

    # 입력 파일·코퍼스 부재 → 명확히 보고하고 종료 코드 2(조용한 무동작 금지).
    unit_yaml: Path = args.unit_yaml
    if not unit_yaml.exists():
        print(f"소단원 DSL 파일 없음: {unit_yaml}")
        return 2
    for label, path in (
        ("원자 백본 그래프", args.atom_graph),
        ("성취기준 Collection", args.standards),
    ):
        if not path.exists():
            print(f"{label} 없음: {path} — 코퍼스가 있는지 확인하세요.")
            return 2
    packs_dir: Path = args.packs_dir
    if not packs_dir.exists():
        print(f"교수법 팩 디렉터리 없음: {packs_dir} — 코퍼스가 있는지 확인하세요.")
        return 2

    valid_atom_codes = load_valid_atom_codes(args.atom_graph)
    statements_by_code = load_statements_by_code(args.standards)
    packs = load_packs(packs_dir)

    yaml_text = unit_yaml.read_text(encoding="utf-8")
    try:
        compiled = compile_unit(
            yaml_text,
            packs=packs,
            valid_atom_codes=valid_atom_codes,
            statements_by_code=statements_by_code,
        )
    except CompileError as exc:
        # 참조 검증 실패 — 미해결 참조 목록을 그대로 보고하고 종료 코드 1.
        print(str(exc))
        return 1

    _print_work_order(compiled)

    if args.seed:
        unit_count, obj_count = UnitSpecStore().seed(compiled)
        print(f"적재 완료: unit_spec {unit_count}건·learning_objective {obj_count}건.")
    else:
        print("(드라이런 — 적재하려면 --seed)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
