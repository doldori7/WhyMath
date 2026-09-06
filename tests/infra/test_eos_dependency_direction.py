"""EOS Core 허용 의존 방향 — 계획서 100 §3.8 (EOS-88).

§3.8은 두 그림을 준다. 권장 방향은 ``Application → EOS Core → Subject Contract → Math Adapter``
이고, 실행 시 어댑터가 Core에 *등록*되는 형태라면 실제 의존 역전은
``EOS Core → Subject Interface ← Math Adapter`` 가 더 정확하다 — **Core는 Math Adapter 구현체를
몰라야 한다**. 이 파일은 그 문장을 네 화살표로 나눠 AST로 잰다:

1. **Interface → Adapter 금지** — `schema.subject_adapter`·`schema.verification_capabilities`는
   `schema` 밖을 import하지 않는다(함수 안 지연 import도 본다).
2. **Adapter → Interface 필수** — `l4.subject_adapter_math`는 인터페이스를 import하고 적합성 증명
   (`: SubjectAdapter = MathSubjectAdapter()`)을 갖는다. 화살표가 *위로* 향한다는 증거다.
3. **Core는 구현체를 모른다** — CORE 코드(docstring 제외)에 어댑터 클래스 이름·모듈명이 0.
4. **Core → Application 금지** — `l*`·`schema`·`lang`·`composition`이 `api`·`app`·`main`을 모른다.

그리고 §3.8이 "덜 정확하다"고 한 형태 — Core가 합성 루트에서 기본 구현을 **끌어오는(pull)**
자리 — 를 집합으로 동결한다. 늘면 RED, 줄면 ratchet. 등록(push) 형태로 바꾸는 일은 별도
태스크(EOS-89)이며, 이 파일은 그 전환이 *진행되는지*를 그 집합의 크기로 본다.

정본화 ≠ 집행: 1·3의 *직접 import*는 EOS-67 import-linter 계약이 이미 강제한다(schema가 source).
이 파일이 더 보는 것은 지연 import·이름·문자열·pull 지점이다.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKG = _REPO_ROOT / "src" / "backend" / "whymath_backend"
_PYPROJECT = _REPO_ROOT / "src" / "backend" / "pyproject.toml"
_PROBE = _REPO_ROOT / "scripts" / "analysis" / "eos_core_boundary_probe.py"
_BOUNDARY_DOC = _REPO_ROOT / "docs" / "architecture" / "eos_core_adapter_boundary.md"

INTERFACE_MODULES = ("schema.subject_adapter", "schema.verification_capabilities")
ADAPTER_MODULE = "l4.subject_adapter_math"
COMPOSITION_MODULE = "composition"
APPLICATION_PREFIXES = ("whymath_backend.api", "whymath_backend.app", "whymath_backend.main")

# 어댑터 구현체의 이름 — Core 코드에 하나라도 나타나면 "Core가 구현체를 안다".
ADAPTER_IMPL_NAMES: frozenset[str] = frozenset(
    {
        "MathSubjectAdapter",
        "MathExpressionEquivalence",
        "MathFinalAnswerVerifier",
        "MathAssessmentAnswerVerifier",
        "MathExpressionSeal",
        "MathAnswerFormVerifier",
    }
)
ADAPTER_IMPL_MODULE_TOKEN = "subject_adapter_math"

# 합성 루트에서 기본 구현을 *끌어오는* Core 모듈 — §3.8의 "덜 정확한" 형태. 줄이는 방향으로만.
CORE_PULL_BASELINE: frozenset[str] = frozenset(
    {"api.coach", "l3.pedagogy.slot_generator", "l3.render.adapters"}
)


# ──────────────────────────────────────────────────────────────────────
# 스캐너 (순수 함수 — 결함 주입 테스트가 직접 부른다)
# ──────────────────────────────────────────────────────────────────────


def absolute_imports(source: str) -> set[str]:
    """모듈·클래스·함수 본문 어디에 있든 절대 import 대상 모듈 이름 전부(지연 import 포함)."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
    return out


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    ids.add(id(body[0].value))
    return ids


def code_mentions(source: str, names: frozenset[str], module_token: str) -> list[str]:
    """docstring을 제외한 코드에서 이름(Name/Attribute)·문자열 상수·import가 구현체를 가리키는 곳."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in names:
            hits.append(f"L{node.lineno} name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in names:
            hits.append(f"L{node.lineno} attr {node.attr}")
        elif (
            isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
        ):
            if module_token in node.value or any(n in node.value for n in names):
                hits.append(f"L{node.lineno} str {node.value[:60]!r}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""] + [a.name for a in node.names]
            )
            if any(module_token in m or m in names for m in mods):
                hits.append(f"L{node.lineno} import {mods}")
    return hits


def conformance_proofs(source: str) -> list[tuple[str, str]]:
    """`_X: SubjectAdapter = MathSubjectAdapter()` 꼴 — (프로토콜, 구현체) 쌍."""
    out: list[tuple[str, str]] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.annotation, ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
        ):
            out.append((node.annotation.id, node.value.func.id))
    return out


# ──────────────────────────────────────────────────────────────────────
# 모집단
# ──────────────────────────────────────────────────────────────────────


def _module_path(mod: str) -> Path:
    p = _PKG / (mod.replace(".", "/") + ".py")
    return p if p.exists() else _PKG / mod.replace(".", "/") / "__init__.py"


def _all_modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in _PKG.rglob("*.py"):
        rel = p.relative_to(_PKG).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            out[".".join(parts)] = p
    return out


def _load_probe() -> Any:
    spec = importlib.util.spec_from_file_location("_eos_core_boundary_probe_for_direction", _PROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture(scope="module")
def core_modules() -> list[str]:
    probe = _load_probe()
    inv = probe._load_inventory()
    scan = inv._load_script(inv.SCAN_SCRIPT, "_eos_boundary_scan_for_direction")
    core = [m for m in inv._backend_modules() if scan.classify(m)[0] == "CORE"]
    if len(core) < 200:  # 스캔 0건은 실패 — 공허한 통과 금지(CLAUDE.md 2026-09-01 ④)
        raise RuntimeError(f"CORE 모집단이 비정상적으로 작다: {len(core)}")
    return core


# ──────────────────────────────────────────────────────────────────────
# ① 네 화살표
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mod", INTERFACE_MODULES)
def test_subject_interface_imports_nothing_below_schema(mod: str) -> None:
    """Interface → Adapter(또는 어느 계층이든) 금지 — 인터페이스는 schema 안에서만 닫힌다."""
    imports = absolute_imports(_module_path(mod).read_text(encoding="utf-8"))
    ours = {m for m in imports if m.startswith("whymath_backend")}
    leaks = {m for m in ours if not m.startswith("whymath_backend.schema")}
    assert not leaks, f"{mod}가 schema 밖을 import: {sorted(leaks)}"


def test_math_adapter_points_up_at_the_interface() -> None:
    """Adapter → Interface: 두 인터페이스 모듈을 import하고 필수층 적합성 증명을 갖는다."""
    src = _module_path(ADAPTER_MODULE).read_text(encoding="utf-8")
    imports = absolute_imports(src)
    for iface in INTERFACE_MODULES:
        assert f"whymath_backend.{iface}" in imports, f"어댑터가 {iface}를 import하지 않는다"
    proofs = conformance_proofs(src)
    assert ("SubjectAdapter", "MathSubjectAdapter") in proofs, proofs


def test_core_code_never_names_an_adapter_implementation(core_modules: list[str]) -> None:
    """Core는 Math Adapter 구현체를 몰라야 한다 — 이름·속성·문자열·import 어디에도(docstring 제외)."""
    offenders: dict[str, list[str]] = {}
    for mod in core_modules:
        if mod == COMPOSITION_MODULE:
            continue  # 합성 루트는 정의상 구현체를 아는 유일한 자리(INFRA)
        path = _module_path(mod)
        if not path.exists():
            continue
        hits = code_mentions(
            path.read_text(encoding="utf-8"), ADAPTER_IMPL_NAMES, ADAPTER_IMPL_MODULE_TOKEN
        )
        if hits:
            offenders[mod] = hits
    assert offenders == {}, f"CORE 코드가 어댑터 구현체를 안다: {offenders}"


def test_core_never_imports_the_application(core_modules: list[str]) -> None:
    """Core → Application 금지 — CORE 배정 모듈이 api/app/main을 모른다.

    INFRA 배정의 운영 CLI(`ops.*`·`harness.*`·`privacy.*`)는 이 검사 대상이 아니다 — 그들은
    Application 쪽에 서서 api 헬퍼를 쓰는 도구다(실측 8모듈 · 경계 문서 §9.2에 기록).
    """
    offenders: dict[str, set[str]] = {}
    for mod in core_modules:
        if mod.split(".")[0] in {"api", "app", "main"}:
            continue
        path = _module_path(mod)
        if not path.exists():
            continue
        imports = absolute_imports(path.read_text(encoding="utf-8"))
        bad = {m for m in imports if m.startswith(APPLICATION_PREFIXES)}
        if bad:
            offenders[mod] = bad
    assert offenders == {}, offenders


# ──────────────────────────────────────────────────────────────────────
# ② 등록(push) vs 풀(pull)
# ──────────────────────────────────────────────────────────────────────


def _pull_points() -> set[str]:
    out: set[str] = set()
    for mod, path in _all_modules().items():
        if mod in {COMPOSITION_MODULE, ADAPTER_MODULE}:
            continue
        imports = absolute_imports(path.read_text(encoding="utf-8"))
        if f"whymath_backend.{COMPOSITION_MODULE}" in imports:
            out.add(mod)
    return out


def test_core_pull_points_from_composition_are_frozen_and_only_shrink() -> None:
    observed = _pull_points()
    new = observed - CORE_PULL_BASELINE
    assert (
        not new
    ), f"새 pull 지점(Core가 합성 루트에서 구현을 끌어옴 — §3.8 위반 방향): {sorted(new)}"
    if observed < CORE_PULL_BASELINE:
        pytest.fail(f"pull 지점이 줄었다 — CORE_PULL_BASELINE을 {sorted(observed)}로 ratchet")


def test_every_layer_pull_point_is_enumerated_in_the_layers_contract() -> None:
    """합성 루트가 세탁 통로가 되지 않게 — l* 풀 간선은 pyproject에 한 줄씩 적혀 있어야 한다."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    layers = next(c for c in data["tool"]["importlinter"]["contracts"] if c.get("type") == "layers")
    ignores = set(layers.get("ignore_imports", []))
    for mod in sorted(_pull_points()):
        if mod.startswith("api."):
            continue  # api는 layers 최상단 — 합성 루트 import가 역방향이 아니다
        edge = f"whymath_backend.{mod} -> whymath_backend.{COMPOSITION_MODULE}"
        assert edge in ignores, f"열거되지 않은 pull 간선: {edge}"


def test_app_factory_registers_no_subject_capability_yet() -> None:
    """현행 실측을 그대로 동결한다: app.py는 합성 루트를 import하지 않는다(등록 형태 부재).

    EOS-89가 등록 형태로 바꾸면 이 테스트는 **의도적으로** 실패해야 하고, 그때 pull 기준선과
    함께 갱신한다 — 두 형태가 소리 없이 공존하는 상태를 막는 잠금이다.
    """
    src = (_PKG / "app.py").read_text(encoding="utf-8")
    assert f"whymath_backend.{COMPOSITION_MODULE}" not in absolute_imports(src)


# ──────────────────────────────────────────────────────────────────────
# ③ 변별력 — 결함 주입
# ──────────────────────────────────────────────────────────────────────


def test_scanner_catches_lazy_import_inside_a_function() -> None:
    src = "def f():\n    from whymath_backend.l4.subject_adapter_math import MathSubjectAdapter\n"
    assert "whymath_backend.l4.subject_adapter_math" in absolute_imports(src)
    assert code_mentions(src, ADAPTER_IMPL_NAMES, ADAPTER_IMPL_MODULE_TOKEN)


@pytest.mark.parametrize(
    "src",
    [
        "x = MathSubjectAdapter()\n",
        "y = mod.MathExpressionSeal\n",
        'p = "whymath_backend.l4.subject_adapter_math"\n',
        "import whymath_backend.l4.subject_adapter_math as m\n",
    ],
)
def test_scanner_detects_injected_implementation_knowledge(src: str) -> None:
    assert len(code_mentions(src, ADAPTER_IMPL_NAMES, ADAPTER_IMPL_MODULE_TOKEN)) == 1


@pytest.mark.parametrize(
    "src",
    [
        '"""MathSubjectAdapter가 구현한다 — docstring."""\nx = 1\n',
        'def f():\n    """subject_adapter_math를 본다."""\n    return 1\n',
        "from whymath_backend.schema.subject_adapter import SubjectAdapter\n",
        'kind = "quadratic"\n',
    ],
)
def test_scanner_ignores_docstrings_and_interface_imports(src: str) -> None:
    assert code_mentions(src, ADAPTER_IMPL_NAMES, ADAPTER_IMPL_MODULE_TOKEN) == []


def test_conformance_scanner_reads_the_proof_shape() -> None:
    src = "_P: SubjectAdapter = MathSubjectAdapter()\n_Q = MathSubjectAdapter()\n"
    assert conformance_proofs(src) == [("SubjectAdapter", "MathSubjectAdapter")]


# ──────────────────────────────────────────────────────────────────────
# ④ 정본 문서 배선
# ──────────────────────────────────────────────────────────────────────


def test_boundary_doc_records_the_direction_measurement() -> None:
    doc = _BOUNDARY_DOC.read_text(encoding="utf-8")
    assert "§9" in doc and "허용 의존 방향" in doc and "test_eos_dependency_direction.py" in doc
