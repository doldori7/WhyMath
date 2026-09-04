"""EOS Core 경계 계측 2종 — "수학을 제거했을 때 무엇이 남는가" + 금지 규칙

(EOS-84 · 계획서 100 §3.7)


EOS-65가 배정(BOUNDARY_MAP)을, EOS-67이 **직접 import** 계약을, EOS-69가 위반 상환을 했다. 남은
사각 둘을 이 계측기가 잰다:

1. **전이 도달** — CORE 모듈이 CORE/INFRA/MIXED를 *경유해* ADAPTER에 닿는가. import-linter는
   `allow_indirect_imports=true`라 경유 의존을 보지 않는다(경계 문서 §4 "정직한 공백"). "수학을
   제거하면 함께 깨지는 Core"가 바로 이 집합이다. 합성 루트 `composition`은 **설계된 유일 교체점**
   (EOS-69 — 과목이 바뀌면 *고쳐야 하는* 파일)이므로 그 경유는 정상이고, 그것을 막아도 남는 경로가
   **잔여 누수**다.
2. **금지 규칙** — 계획서 100 §3.7 *"`if subject == "math":` · `if problem.type == "quadratic":`가
   Core에 보이면 위반"*. CORE 모듈 AST의 비교문(`Compare`)·`match` 패턴에서 과목·수학 유형 문자열
   리터럴을 찾는다. 함께 **수학 어휘 문자열 상수**(비교문이 아니라 데이터·프롬프트에 박힌 "이차함수"
   등·docstring 제외)를 모듈별로 세어 "Core가 데이터로 수학을 아는" 자리를 드러낸다.

둘 다 **계측기**다 — 위반 수로 exit 1을 내지 않는다(측정 실패만 exit 1). 게이트는 EOS-67 계약과
`tests/infra/test_eos_core_boundary_probe.py`(리터럴 비교 0 ratchet · 잔여 누수 집합 동결)가 세운다.

사용법:
    python3 scripts/analysis/eos_core_boundary_probe.py            # 마크다운 리포트(stdout)
    python3 scripts/analysis/eos_core_boundary_probe.py --json out.json
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import pathlib
import re
import sys
from collections import deque
from dataclasses import dataclass
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
INVENTORY_SCRIPT = pathlib.Path(__file__).with_name("eos_feature_inventory_v2.py")

# 설계된 교체점 — 이 노드를 지나는 도달은 "과목을 바꿀 때 이 파일만 고친다"의 증거이지 누수가 아니다
DESIGNED_SEAMS: frozenset[str] = frozenset({"composition"})

# 금지 규칙 어휘 — 비교문의 *문자열 리터럴*만 본다(변수명·docstring은 대상 아님)
SUBJECT_LITERALS: frozenset[str] = frozenset({"math", "mathematics", "수학", "physics", "물리"})
MATH_TYPE_RX = re.compile(
    r"^(quadratic|linear|polynomial|trig\w*|calculus|geometry|probability|sequence|exponential|"
    r"logarithm|vector|matrix|integral|derivative|equation|inequality|fraction|algebra|statistics|"
    r"combinatorics|number_theory)(_[a-z_]+)?$",
    re.I,
)
# 어휘 상수 스캔 — 일반어와 겹치는 낱말(함수·로그·실수·소수·분수·확률)은 뺐다:
# 거짓 양성이 신호를 덮는다
VOCAB_KO = re.compile(
    r"이차방정식|일차방정식|이차함수|일차함수|삼각함수|미적분|정적분|부정적분|다항식|인수분해|"
    r"근의 공식|피타고라스|등차|등비|순열|조합|행렬|벡터|도함수|제곱근|무리수|복소수|"
    r"이차부등식|연립방정식|수직선|좌표평면"
)
VOCAB_EN = re.compile(
    r"\b(quadratic|polynomial|trigonometr\w*|derivative|integral|logarithm|factoring|pythagor\w*|"
    r"sympy|latex)\b",
    re.I,
)


def _load_inventory() -> Any:
    spec = importlib.util.spec_from_file_location("_eos_inventory_v2_for_probe", INVENTORY_SCRIPT)
    assert spec is not None and spec.loader is not None, f"로드 불가: {INVENTORY_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


# ──────────────────────────────────────────────────────────────────────
# ① 전이 도달
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Reach:
    source: str  # CORE 모듈
    path: tuple[str, ...]  # source 다음부터 ADAPTER까지
    via_designed_seam: bool  # 경로가 DESIGNED_SEAMS를 지나는가


def first_adapter_path(
    src: str,
    graph: dict[str, set[str]],
    verdict: dict[str, str],
    blocked: frozenset[str] = frozenset(),
) -> tuple[str, ...] | None:
    """src에서 import 간선을 따라 처음 만나는 ADAPTER까지의 최단 경로(BFS). 없으면 None.

    이웃은 **정렬해서** 순회한다 — 간선 집합(`set`)을 그대로 돌면 문자열 해시 시드에 따라 같은
    깊이의 동률 경로가 실행마다 달라져, 잔여 누수 동결 테스트가 해시 시드 복권이 된다(2026-09-04
    실측: 같은 출발점이 `wrong_form_match`·`verify_solution` 중 하나로 번갈아 끝났다).
    """
    prev: dict[str, str | None] = {src: None}
    dq: deque[str] = deque([src])
    while dq:
        m = dq.popleft()
        for n in sorted(graph.get(m, ())):
            if n in prev or n in blocked:
                continue
            prev[n] = m
            if verdict.get(n) == "ADAPTER":
                path = [n]
                while path[-1] != src:
                    nxt = prev[path[-1]]
                    assert nxt is not None
                    path.append(nxt)
                return tuple(reversed(path))[1:]
            dq.append(n)
    return None


def transitive_reach(
    core: list[str], graph: dict[str, set[str]], verdict: dict[str, str]
) -> tuple[list[Reach], list[Reach]]:
    """(전체 도달, 설계 교체점을 막아도 남는 잔여 누수)."""
    all_hits: list[Reach] = []
    residual: list[Reach] = []
    for m in core:
        p = first_adapter_path(m, graph, verdict)
        if p is None:
            continue
        all_hits.append(Reach(m, p, any(x in DESIGNED_SEAMS for x in p)))
        q = first_adapter_path(m, graph, verdict, blocked=DESIGNED_SEAMS)
        if q is not None:
            residual.append(Reach(m, q, False))
    return all_hits, residual


# ──────────────────────────────────────────────────────────────────────
# ② 금지 규칙 — 순수 함수(소스 문자열 → 히트) · 테스트가 결함을 주입하기 쉽게
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LiteralHit:
    lineno: int
    kind: str  # "subject" | "math_type"
    snippet: str


def _classify_literal(value: str) -> str | None:
    if value.lower() in SUBJECT_LITERALS:
        return "subject"
    if MATH_TYPE_RX.match(value):
        return "math_type"
    return None


def scan_literal_compares(source: str) -> list[LiteralHit]:
    """`x == "math"` · `t in ("quadratic", …)` · `case "trig":` — 비교·매치의 문자열 리터럴."""
    tree = ast.parse(source)
    hits: list[LiteralHit] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands: list[ast.expr] = [node.left, *node.comparators]
            for operand in operands:
                consts: list[ast.Constant] = []
                if isinstance(operand, ast.Constant):
                    consts = [operand]
                elif isinstance(operand, (ast.Tuple, ast.List, ast.Set)):
                    consts = [e for e in operand.elts if isinstance(e, ast.Constant)]
                for c in consts:
                    if isinstance(c.value, str) and (kind := _classify_literal(c.value)):
                        hits.append(LiteralHit(node.lineno, kind, ast.unparse(node)[:100]))
                        break
        elif isinstance(node, ast.match_case) and isinstance(node.pattern, ast.MatchValue):
            v = node.pattern.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                if kind := _classify_literal(v.value):
                    hits.append(LiteralHit(v.lineno, kind, f"case {v.value!r}"))
    return hits


def scan_math_vocabulary(source: str) -> list[tuple[int, str]]:
    """docstring이 아닌 문자열 상수 중 수학 어휘를 담은 것 — 데이터·프롬프트 누수 신호."""
    tree = ast.parse(source)
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, ast.Constant):
                    doc_ids.add(id(node.body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in doc_ids
        ):
            if VOCAB_KO.search(node.value) or VOCAB_EN.search(node.value):
                out.append((node.lineno, node.value.replace("\n", " ")[:80]))
    return out


# ──────────────────────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────────────────────
def run_probe(log: Any) -> dict[str, Any]:
    inv = _load_inventory()
    scan = inv._load_script(inv.SCAN_SCRIPT, "_eos_boundary_scan_for_probe")
    v1 = inv._load_script(inv.V1_SCRIPT, "_eos_inventory_v1_for_probe")
    universe: list[str] = inv._backend_modules()
    graph: dict[str, set[str]] = inv._effective_import_graph(universe, v1)
    verdict = {m: scan.classify(m)[0] for m in universe}
    core = [m for m in universe if verdict[m] == "CORE"]
    if not core:
        raise RuntimeError("CORE 모듈 0 — 배정 정본 로드 실패(빈 결과를 성공으로 위장 금지)")
    log(f"[probe] 모듈 {len(universe)} · CORE {len(core)} · ADAPTER "
        f"{sum(1 for v in verdict.values() if v == 'ADAPTER')}")  # fmt: skip

    all_hits, residual = transitive_reach(core, graph, verdict)
    survivors = len(core) - len(all_hits)
    compares: dict[str, list[LiteralHit]] = {}
    vocab: dict[str, list[tuple[int, str]]] = {}
    for m in core:
        path = inv._module_path(m)
        assert path is not None
        src = path.read_text(encoding="utf-8")
        if hits := scan_literal_compares(src):
            compares[m] = hits
        if words := scan_math_vocabulary(src):
            vocab[m] = words
    n_cmp = sum(len(v) for v in compares.values())
    n_vocab = sum(len(v) for v in vocab.values())
    log(
        f"[probe] 전이 도달 {len(all_hits)} (잔여 {len(residual)})"
        f" · 리터럴 비교 {n_cmp} · 어휘 상수 {n_vocab}"
    )
    return {
        "modules": len(universe),
        "core": len(core),
        "adapter": sum(1 for v in verdict.values() if v == "ADAPTER"),
        "mixed": sum(1 for v in verdict.values() if v == "MIXED"),
        "reach_all": [
            {"source": r.source, "path": list(r.path), "via_designed_seam": r.via_designed_seam}
            for r in all_hits
        ],
        "reach_residual": [{"source": r.source, "path": list(r.path)} for r in residual],
        "survivors_after_math_removal": survivors,
        "literal_compares": {
            m: [{"lineno": h.lineno, "kind": h.kind, "snippet": h.snippet} for h in hits]
            for m, hits in compares.items()
        },
        "math_vocabulary_constants": {
            m: [{"lineno": ln, "text": t} for ln, t in words] for m, words in vocab.items()
        },
    }


def to_markdown(r: dict[str, Any]) -> str:
    lines = [
        "# EOS Core 경계 계측 — 수학을 제거했을 때 남는 것 / 금지 규칙",
        "",
        f"모듈 {r['modules']} · CORE {r['core']} · ADAPTER {r['adapter']} · MIXED {r['mixed']}",
        "",
        "## ① 전이 도달 (CORE →…→ ADAPTER)",
        f"- 도달 {len(r['reach_all'])} / CORE {r['core']} → 수학 제거 후 온전히 남는 CORE "
        f"**{r['survivors_after_math_removal']}**",
        "- 설계 교체점(composition) 경유: "
        f"{sum(1 for x in r['reach_all'] if x['via_designed_seam'])}",
        "",
        f"- **잔여 누수(교체점을 막아도 닿음): {len(r['reach_residual'])}**",
        "",
        "| CORE 출발 | 경로 | 교체점 경유 |",
        "|---|---|---|",
    ]
    for x in r["reach_all"]:
        lines.append(
            f"| `{x['source']}` | {' → '.join(x['path'])} | "
            f"{'예' if x['via_designed_seam'] else '**아니오**'} |"
        )
    total_cmp = sum(len(v) for v in r["literal_compares"].values())
    lines += ["", "## ② 금지 규칙 — 과목·수학 유형 리터럴 비교", f"- 히트 **{total_cmp}**"]
    for m, hits in r["literal_compares"].items():
        for h in hits:
            lines.append(f"- `{m}` L{h['lineno']} ({h['kind']}): `{h['snippet']}`")
    total_vocab = sum(len(v) for v in r["math_vocabulary_constants"].values())
    lines += [
        "",
        "## ③ 수학 어휘 문자열 상수 (데이터·프롬프트 누수 신호 · docstring 제외)",
        f"- {total_vocab}건 / {len(r['math_vocabulary_constants'])}모듈",
        "",
        "| CORE 모듈 | 건수 | 예 |",
        "|---|---:|---|",
    ]
    ranked = sorted(r["math_vocabulary_constants"].items(), key=lambda kv: -len(kv[1]))
    for m, words in ranked:
        lines.append(f"| `{m}` | {len(words)} | L{words[0]['lineno']} `{words[0]['text'][:50]}` |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    def log(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)

    try:
        result = run_probe(log)
    except Exception as exc:  # noqa: BLE001 — 계측기 최상위: 원인 타입을 남기고 실패
        log(f"[fatal] 측정 실패 {type(exc).__name__}: {exc}")
        return 1
    print(to_markdown(result))
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[out] {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
