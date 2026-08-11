"""거버넌스 동결 — FormulaNode (리치 Part 2 Phase 5a·2026-07-08 + NS-04·2026-08-10).

FormulaNode 1급 승격(위험문서 정식 개정)이 CLAUDE.md 금기·위험문서 canonical-only 경계 안에서 사는지
동결한다. FormulaNode는 두 위험문서(`math_dsl_evolution`·`risk_register`)가 유일하게 anti-goal로
판정했던 노드라, 경계가 코드로 강제돼야 한다:

  ① **신규 엣지 타입 0**: FormulaNode 도입이 EdgeType/Relation을 늘리지 않는다 — 수식 연결은
     참조 키(formula_refs·Phase 5b)만(anti-explosion).
  ② **canonical-only 불변식**: 노드에 변형/동치 열거 필드(`equivalence_class`·`sympy_repr`·
     `variant*`)가 없다 — canonical 1개만 노드화(조합폭발 방지). id 공간 `formula.<slug>`.
  ③ **SymPy 재구현 금지 경계**: FormulaNode 노드 모듈(pipeline 모델·backend 프로젝션·ORM)이 sympy를
     import하지 않는다 — 이 노드는 정체성·참조만 담고 동치 계산(CAS·재작성 규칙)은 l3 SymPy 단일
     권위가 한다(`math_dsl_evolution.md` §2.1 "SymPy 재구현 금지").
  ④ **dsl SymPy-parseable**: 정본 코퍼스의 전 수식 `dsl`이 `to_sympy_source`+`condition_dsl_
     violation`을 통과한다(검증가능·동치는 SymPy에 위임). data-pipeline은 sympy-free라 backend 몫.
  ⑤ **latex↔dsl 의미 정합(NS-04)**: ①~④는 각각 latex·dsl *내부* 형식만 봤지 둘 *사이*의 의미
     일치는 검사한 적이 없었다(`dsl_integration_gap_review.md` §2-⑧) — `formula.quadratic.roots`의
     latex는 `±`(두 근)인데 dsl은 +근 하나뿐인 실결함이 무봉인 상태였다. latex를 SymPy가 읽을 수
     있는 소스로 표기 변환(LaTeX 커맨드 토큰만·판정 아님)한 뒤 `identity_status`(l3 단일 권위)로
     dsl과 대조한다 — 값-공식 축(±)·구조 축(나머지)으로 나눈다(하단 섹션 주석 참고).

hermetic: DB 불요(모델·enum import + 코퍼스 JSON 스캔·소스 AST 스캔 + l3 SymPy primitive).
정정 이력: `formula.quadratic.roots`의 dsl은 2026-08-10 ±-중립 음함수형으로 정정됐다(NS-04) — 이
파일의 ⑤ 섹션이 그 정정을 봉인하는 게이트이자 원 결함의 회귀 방지 테스트다.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from data_pipeline.concept_graph.models import RELATION_TYPES
from data_pipeline.formula_graph.models import FORMULA_ID_PATTERN
from data_pipeline.formula_graph.models import FormulaNode as PipelineFormulaNode

from whymath_backend.db.models.formula_node import FormulaNode as OrmFormulaNode
from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.l3.symbolic_equivalence import (
    IdentityVerdict,
    identity_status,
    to_sympy_source,
)
from whymath_backend.schema.enums import EdgeType

# 리포지토리 루트(tests/backend/l1/ 기준 3단 상위) → 코퍼스·소스 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORMULA_GRAPH = _REPO_ROOT / "data" / "corpus" / "formula_graph_v1" / "graph.json"

# FormulaNode 노드 모듈(③ sympy 미import 스캔 대상 — 정체성·참조 전용·동치는 l3).
_NODE_SOURCES = (
    _REPO_ROOT / "src" / "data-pipeline" / "data_pipeline" / "formula_graph" / "models.py",
    _REPO_ROOT / "src" / "backend" / "whymath_backend" / "db" / "models" / "formula_node.py",
    _REPO_ROOT
    / "src"
    / "backend"
    / "whymath_backend"
    / "l1"
    / "formula_graph"
    / "formula_node_projection.py",
)

# canonical-only 위반 — 변형/동치 열거 저장 필드(있으면 조합폭발·SymPy 위임 원칙 위반).
_FORBIDDEN_NODE_FIELDS = ("equivalence_class", "sympy_repr", "variant", "variants", "equivalents")


def _load_formulas() -> list[dict[str, object]]:
    return list(json.loads(_FORMULA_GRAPH.read_text(encoding="utf-8"))["formulas"])


# ── ① 신규 엣지 타입 0 ──────────────────────────────────────────────────────
def test_formula_adds_no_edge_type() -> None:
    """FormulaNode 도입이 EdgeType/Relation을 늘리지 않는다 — 수식 연결은 참조 키(5b)만.

    EdgeType(backend)·RELATION_TYPES(pipeline)는 Formula 승격과 무관하게 예산(5~8) 안에 머문다.
    """
    assert 5 <= len(EdgeType) <= 8
    assert 5 <= len(RELATION_TYPES) <= 8
    edge_tokens = {e.value.lower() for e in EdgeType} | {r.lower() for r in RELATION_TYPES}
    assert not any("formula" in tok for tok in edge_tokens)


def test_corpus_has_no_edge_array() -> None:
    """코퍼스에 별도 엣지 배열이 없다 — canonical 노드만(연결은 참조 키·Phase 5b)."""
    graph = json.loads(_FORMULA_GRAPH.read_text(encoding="utf-8"))
    assert "edges" not in graph


# ── ② canonical-only 불변식 ─────────────────────────────────────────────────
def test_node_has_no_variant_or_equivalence_field() -> None:
    """노드(파이프라인 모델·ORM)에 변형/동치 열거 필드가 없다 — canonical 1개만·동치는 SymPy."""
    pipeline_fields = set(PipelineFormulaNode.model_fields)
    orm_columns = {c.key for c in OrmFormulaNode.__table__.columns}
    for forbidden in _FORBIDDEN_NODE_FIELDS:
        assert forbidden not in pipeline_fields, forbidden
        assert forbidden not in orm_columns, forbidden


def test_formula_ids_follow_slug_space() -> None:
    """전 수식 formula_id가 `formula.<slug>` 공간(사람 관리 code·SymPy 계산값 아님)·유일."""
    formulas = _load_formulas()
    assert formulas, "formula 코퍼스가 비어있지 않아야 한다(스캔 무력화 방지)"
    ids = [str(f["formula_id"]) for f in formulas]
    assert len(ids) == len(set(ids)), "formula_id 중복(canonical 중복)"
    for fid in ids:
        assert FORMULA_ID_PATTERN.match(fid), fid


# ── ③ SymPy 재구현 금지 경계 (노드 모듈 sympy 미import) ─────────────────────
def _imports_sympy(tree: ast.Module) -> bool:
    """AST에서 `import sympy`/`from sympy ...`(하위 포함) 실제 import를 탐지."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "sympy" or a.name.startswith("sympy.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "sympy" or mod.startswith("sympy."):
                return True
    return False


def test_node_modules_do_not_import_sympy() -> None:
    """FormulaNode 노드 모듈이 sympy를 import하지 않는다 — 동치 권위는 l3 SymPy 단일(재구현 금지).

    노드는 수식의 정체성·참조만 담는다. CAS·재작성 규칙을 내장하면 위험문서 §2.1 "SymPy 재구현=즉사"
    경계를 넘는다. 이 스캔이 경계를 코드로 동결한다(동치 계산은 `l3/symbolic_equivalence`가 담당).
    """
    offenders: list[str] = []
    for path in _NODE_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_sympy(tree):
            offenders.append(path.name)
    assert (
        not offenders
    ), f"FormulaNode 노드 모듈이 sympy import(동치 권위 l3 단일 위반): {offenders}"


# ── ④ dsl SymPy-parseable (검증가능·동치는 SymPy 위임) ──────────────────────
def test_all_dsl_are_sympy_parseable() -> None:
    """전 수식 dsl이 `to_sympy_source`+`condition_dsl_violation`을 통과(닫힌 검증 DSL).

    dsl이 SymPy로 파싱돼야 런타임 동치 판정(변형↔canonical)이 가능하다 — canonical-only 실효성 보증.
    """
    bad: dict[str, str] = {}
    for node in _load_formulas():
        dsl = str(node["dsl"])
        violation = condition_dsl_violation(to_sympy_source(dsl))
        if violation is not None:
            bad[str(node["formula_id"])] = violation
    assert not bad, f"dsl SymPy-parseable 위반(동치 위임 불가): {bad}"


# ── ⑤ latex↔dsl 의미 정합 (NS-04·2026-08-10) ─────────────────────────────────
#
# latex(표시용)·dsl(SymPy 검증용)은 같은 canonical 수식의 *병렬* 표현이다 — 문자열은 다르지만
# *같은 수학적 관계*를 표현해야 한다. ①~④는 각각 latex·dsl *내부* 형식만 봤지 둘 *사이*의 의미
# 일치는 검사한 적이 없다(`dsl_integration_gap_review.md` §2-⑧). 실결함 1건 확정: `formula.
# quadratic.roots`의 latex는 `\pm`(두 근)인데 dsl은 +근 하나뿐(± 소실). dsl은 현재 write-only
# (Phase 5b 미착수)라 학생 피해 0 — 소비 시작 전인 지금이 봉인 적기.
#
# 두 축으로 나눈다(성격이 달라 한 축으로 뭉치면 ± 분기와 단순 기호 불일치를 구분 못 한다):
#   (A) 값-공식 축 — latex에 `\pm`/`\mp`가 있는 레코드(코퍼스 실측 1건). 단일 대입식은 두 근을
#       동시에 표현할 수 없으므로, dsl 관계식의 잔차(lhs−rhs)에 두 근(+/−)을 각각 대입해 *둘 다*
#       항등(0)이어야 통과한다 — explicit `x==...`형은 구조상 항상 실패한다(원 결함의 증상).
#   (B) 구조 축 — 나머지 24건. latex·dsl 좌/우변을 *개별* 대조한다(전체 잔차 아님 — 스케일이
#       다른데 해가 같은 착시를 배제). 기호명이 의도적으로 다른 레코드(vieta류 — α/β↔r_1/r_2,
#       β는 SymPy Beta 함수 충돌 회피)는 명시적 별칭 테이블로만 흡수하고, 테이블에 없는 불일치는
#       조용히 넘기지 않는다(CLAUDE.md 침묵 실패 금지).
#
# 최종 판정은 항상 `identity_status`(l3 단일 권위)에 위임한다 — 아래 전처리는 *판정*이 아니라
# *표기 변환*(LaTeX 커맨드 토큰을 SymPy가 읽는 문자열로)이라 SymPy 재구현이 아니다. `to_sympy_
# source`가 못 건드리는(유니코드 아닌 백슬래시 커맨드) 토큰만 다루고, 코퍼스 25건에 실제 등장하는
# 토큰만 커버한다(범용 LaTeX 파서 아님 — 과공학 방지. 실측: alpha·beta·cdot·cos·frac·int·log·pi·
# pm·sin·sqrt·theta).

# LaTeX 커맨드 토큰 → SymPy 소스 리터럴 치환(코퍼스 실측 전수 — 확장 시 grep 재실측 필수).
# `to_sympy_source`의 유니코드 그리스 매핑과는 별도 경로(거긴 유니코드 문자 `α`, 여긴 백슬래시
# 커맨드 `\alpha`).
_LATEX_TOKEN_MAP: tuple[tuple[str, str], ...] = (
    (r"\cdot", "*"),
    (r"\pi", "pi"),
    (r"\alpha", "alpha"),
    (r"\beta", "beta"),
    (r"\theta", "theta"),
    (r"\sin", "sin"),
    (r"\cos", "cos"),
    (r"\log", "log"),
)

# 함수/상수명(이 파일이 만들거나 위 맵이 치환한 다중 문자 토큰) — 문자 병치 분리가 이들을 낱자로
# 찢지 않도록 보호한다.
_PROTECTED_MULTI_LETTER_TOKENS = frozenset(
    {"sin", "cos", "log", "sqrt", "pi", "alpha", "beta", "theta", "Derivative", "Integral"}
)

_LETTER_RUN_RE = re.compile(r"[A-Za-z]+")


def _find_matching_brace(text: str, open_index: int) -> int:
    """`text[open_index] == '{'` 전제 — 중첩 고려해 대응하는 `}`의 인덱스를 찾는다."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"짝이 맞지 않는 '{{': {text!r}")


def _consume_group(text: str, index: int) -> tuple[str, int]:
    """`\\frac`/`\\sqrt` 뒤 인자 그룹 하나를 소비 — `{...}`(중첩 허용) 우선, 없으면 단일 문자.

    코퍼스 25건은 항상 `{...}` 형태만 쓰지만(단일 문자 관례 `\\frac12`는 미등장), 방어적으로 단일
    문자 폴백을 둔다.
    """
    if index < len(text) and text[index] == "{":
        end = _find_matching_brace(text, index)
        return text[index + 1 : end], end + 1
    if index < len(text):
        return text[index], index + 1
    return "", index


def _expand_frac_sqrt(text: str) -> str:
    """`\\frac{a}{b}` → `((a)/(b))`, `\\sqrt{a}` → `sqrt((a))` — 중첩 인자까지 재귀 전개.

    코퍼스의 `formula.quadratic.roots`(`\\frac{-b\\pm\\sqrt{...}}{2a}`)는 분수 분자에 `\\sqrt`가
    중첩된다 — 비-중첩 정규식(예: l5/ocr 폴백의 `[^()]*` 패턴)으로는 괄호 안에 괄호가 생기는 이
    형태를 못 잡는다. 이 함수는 중괄호 짝을 직접 추적해 임의 중첩을 처리한다(범용 LaTeX 파서가
    아니라 `\\frac`/`\\sqrt` 두 커맨드 전용).
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("\\frac", i):
            i += len("\\frac")
            numerator, i = _consume_group(text, i)
            denominator, i = _consume_group(text, i)
            num_src = _expand_frac_sqrt(numerator)
            den_src = _expand_frac_sqrt(denominator)
            out.append(f"(({num_src})/({den_src}))")
        elif text.startswith("\\sqrt", i):
            i += len("\\sqrt")
            arg, i = _consume_group(text, i)
            out.append(f"sqrt(({_expand_frac_sqrt(arg)}))")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


# 라이프니츠 표기(프리픽스 연산자) — `\frac{a}{b}`류 일반 분수 치환과 다른 처리가 필요하다. 매치
# 대상은 *등식 분리 후 한쪽 변 전체*라 `.+`가 "나머지 전부"를 피연산자로 삼는다(코퍼스 2건 —
# power-rule-derivative·power-rule-integral — 전용 최소 패턴, 범용 미적분 파서가 아니다).
_LEIBNIZ_DERIVATIVE_RE = re.compile(r"^\\frac\{d\}\{d([a-zA-Z]+)\}\s*(.+)$")
_LEIBNIZ_INTEGRAL_RE = re.compile(r"^\\int\s+(.+?)\s*\\,\s*d([a-zA-Z]+)\s*$")


def _rewrite_leibniz_operators(text: str) -> str:
    """`\\frac{d}{dx} E` → `Derivative((E), x)`, `\\int E \\, dx` → `Integral((E), x)`.

    dsl이 이미 SymPy `Derivative`/`Integral`(미평가 연산자) 문법을 쓰므로(코퍼스 확인), latex의
    라이프니츠 표기를 *같은* 미평가 연산자 문법으로 바꿔야 좌우 대조가 가능하다 — 직접 미적분을
    계산해 값을 맞추는 게 아니다(그건 "공식이 참인가"이지, 이 게이트의 질문 "latex와 dsl이 같은
    관계를 말하는가"가 아니다. 실제로 `Derivative(x**n,x)`는 `n*x**(n-1)`과 미평가 상태로는
    `undecidable`이다 — 실측 확인).
    """
    match = _LEIBNIZ_DERIVATIVE_RE.match(text)
    if match:
        var, operand = match.group(1), match.group(2)
        return f"Derivative(({operand}), {var})"
    match = _LEIBNIZ_INTEGRAL_RE.match(text)
    if match:
        operand, var = match.group(1), match.group(2)
        return f"Integral(({operand}), {var})"
    return text


# 함수명 뒤 지수가 먼저 오는 관용 표기 — `\sin^2\theta`=`(\sin(\theta))^2`(코퍼스: trig.pythagorean).
_FUNC_POWER_ARG_RE = re.compile(
    r"\\(sin|cos)\^(\{[^{}]*\}|[0-9]+)\s*(\\[a-zA-Z]+|[A-Za-z][0-9A-Za-z_]*)"
)
# 함수명 뒤 괄호 없는 단일 인자 병치 — `\log x`·`\sin a`(코퍼스: log.power·trig.*-addition).
_FUNC_BARE_ARG_RE = re.compile(r"\\(sin|cos|log)\s+(\\[a-zA-Z]+|[A-Za-z][0-9A-Za-z_]*)")


def _rewrite_function_application(text: str) -> str:
    """함수명 병치(괄호 생략)를 명시적 호출로 — SymPy는 `sin x`류 함수적용 병치를 못 읽는다.

    `l3.symbolic_equivalence`가 쓰는 파싱 변환(`implicit_multiplication`)은 *함수 적용* 병치
    (`sin x`→`sin(x)`)를 의도적으로 제외한다(학생 입력처럼 못 믿을 소스엔 "sin이 함수"라고 가정
    않는 게 안전 — 확실하지 않으면 모른다). 그러나 이 코퍼스는 자체작성 canonical LaTeX라
    `\\sin`이 *항상* sine 함수임을 안다 — 이 가정이 안전한 유일한 자리다. 지수 선행형을 먼저
    처리해야 뒤 단계가 `^2`를 인자로 오인하지 않는다.
    """

    def _pow_repl(match: re.Match[str]) -> str:
        func, exponent, arg = match.group(1), match.group(2), match.group(3)
        if exponent.startswith("{"):
            exponent = exponent[1:-1]
        return f"(\\{func}({arg}))^{exponent}"

    def _bare_repl(match: re.Match[str]) -> str:
        func, arg = match.group(1), match.group(2)
        return f"\\{func}({arg})"

    text = _FUNC_POWER_ARG_RE.sub(_pow_repl, text)
    return _FUNC_BARE_ARG_RE.sub(_bare_repl, text)


def _split_letter_juxtaposition(text: str) -> str:
    """보호되지 않은 2자+ 알파벳 런을 낱자*낱자로 분리 — LaTeX 암묵곱 관례(`ab`→`a*b`).

    `to_sympy_source`/`identity_status`의 파싱 관용구는 순수 문자 병치를 *추정하지 않는다*(학생
    입력 보수 처리 — `symbolic_equivalence.py` 상단 주석). 그러나 인쇄 수학 표기에서 `2ab`·`mn`
    같은 낱자 병치는 명백히 곱셈이다(canonical 자체작성 코퍼스 — 모호성 없음). 함수/상수명
    (`_PROTECTED_MULTI_LETTER_TOKENS`)은 낱자로 찢지 않는다.
    """

    def _repl(match: re.Match[str]) -> str:
        run = match.group(0)
        if len(run) == 1 or run in _PROTECTED_MULTI_LETTER_TOKENS:
            return run
        return "*".join(run)

    return _LETTER_RUN_RE.sub(_repl, text)


def _latex_side_to_sympy_text(side: str) -> str:
    """등식 한쪽 변의 raw LaTeX → SymPy가 읽을 수 있는 소스 문자열(표기 변환·판정 아님).

    순서가 중요하다: ①라이프니츠 연산자(변 전체 매치) ②함수 병치(지수선행→단일인자 순으로 좁은
    패턴 먼저) ③`\\frac`/`\\sqrt` 중첩 전개 ④잔여 중괄호(단독 지수 그룹 등)→소괄호 ⑤커맨드 토큰
    맵(이 시점엔 남은 `\\sin`/`\\cos`/`\\log`가 전부 괄호 인자를 가져 함수적용 안전) ⑥낱자 병치
    분리 ⑦`to_sympy_source`(l3 단일 권위 최종 정규화 — 위첨자·NFKC 등). ⑦은 ①~⑥ 출력에 멱등이라
    (이미 ASCII) 마지막에 얹어도 안전하다(입력 정규화 이원화 방지 — 단일 최종 관문).
    """
    text = side.strip()
    text = _rewrite_leibniz_operators(text)
    text = _rewrite_function_application(text)
    text = _expand_frac_sqrt(text)
    text = text.replace("{", "(").replace("}", ")")
    for token, repl in _LATEX_TOKEN_MAP:
        text = text.replace(token, repl)
    text = _split_letter_juxtaposition(text)
    return to_sympy_source(text)


# (B) 구조 축 별칭 테이블 — latex·dsl이 *의도적으로* 다른 기호를 쓰는 레코드만(코퍼스 스캔 실측:
# vieta-sum·vieta-product 2건 — dsl notes: "β는 SymPy Beta 함수와 충돌 회피"). 여기 없는 기호
# 불일치는 게이트가 조용히 넘기지 않고 명시 실패한다(침묵 실패 금지).
_SYMBOL_ALIASES: dict[str, str] = {"alpha": "r_1", "beta": "r_2"}


def _apply_symbol_aliases(text: str) -> str:
    """선언된 별칭만 단어 경계로 치환(코퍼스 스캔 기반 — 하드코딩 formula_id 분기가 아니다)."""
    for source, target in _SYMBOL_ALIASES.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    return text


def _structure_axis_violation(latex: str, dsl: str) -> str | None:
    """(B) 구조 축 — `\\pm` 없는 레코드. latex·dsl 좌/우변을 *개별* 대조(전체 잔차 아님).

    좌/우를 따로 보는 이유: 전체 잔차(lhs−rhs) 비교는 스케일이 달라도 해집합이 같은 경우(예:
    `2x=2y` vs `x=y`)를 오탐 없이 통과시켜 버릴 위험이 있다 — canonical 표기인 이 코퍼스엔 그런
    스케일 차가 있어선 안 되므로, 좌/우 개별 항등 요구가 더 엄격하고 정확하다.
    """
    if "=" not in latex:
        return f"latex에 '='가 없음(등식 아님): {latex!r}"
    if "==" not in dsl:
        return f"dsl에 '=='가 없음(등식 아님): {dsl!r}"
    latex_lhs, latex_rhs = latex.split("=", 1)
    dsl_lhs_raw, dsl_rhs_raw = dsl.split("==", 1)
    dsl_lhs, dsl_rhs = dsl_lhs_raw.strip(), dsl_rhs_raw.strip()
    translated_lhs = _apply_symbol_aliases(_latex_side_to_sympy_text(latex_lhs))
    translated_rhs = _apply_symbol_aliases(_latex_side_to_sympy_text(latex_rhs))
    lhs_verdict = identity_status(translated_lhs, dsl_lhs)
    rhs_verdict = identity_status(translated_rhs, dsl_rhs)
    if lhs_verdict is IdentityVerdict.identity and rhs_verdict is IdentityVerdict.identity:
        return None
    return (
        "latex↔dsl 구조 불일치(별칭 적용 후에도) — "
        f"lhs: {translated_lhs!r} vs {dsl_lhs!r} = {lhs_verdict.value}; "
        f"rhs: {translated_rhs!r} vs {dsl_rhs!r} = {rhs_verdict.value}"
    )


def _expand_plus_minus(text: str, *, prefer_plus: bool) -> str:
    """`\\pm`/`\\mp`를 지정 부호로 치환 — 둘은 항상 반대 부호로 함께 움직인다(수학 관례).

    코퍼스엔 `\\mp`가 등장하지 않지만(실측 grep — 등장 토큰은 `\\pm`뿐), 등장 시에도 안전하도록
    대칭 처리한다(`test_expand_plus_minus_moves_mp_opposite_to_pm`가 직접 검증).
    """
    plus_token, minus_token = ("+", "-") if prefer_plus else ("-", "+")
    return text.replace("\\pm", plus_token).replace("\\mp", minus_token)


def _substitute_symbol(text: str, symbol: str, replacement: str) -> str:
    """단어 경계 기준 심볼 치환(문자열 수준) — `x` 토큰만 바꾸고 부분 문자열은 건드리지 않는다.

    값 치환(`.subs()`류 대입)이지 동치 재판정이 아니다 — 최종 항등 판정은 여전히 `identity_status`
    (l3 단일 권위)가 한다(축③ 정신 유지·SymPy 재구현 아님).
    """
    return re.sub(rf"\b{re.escape(symbol)}\b", f"({replacement})", text)


_BARE_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _pm_axis_violation(latex: str, dsl: str) -> str | None:
    """(A) 값-공식 축 — latex에 `\\pm`/`\\mp`가 있는 레코드(해가 2개인 공식).

    단일 대입식(`x==expr(a,b,c)`)은 구조상 두 근을 동시에 표현할 수 없다 — 그래서 이 축은 "dsl
    관계식(lhs−rhs)에 두 근을 각각 대입했을 때 *둘 다* 항등적으로 0이 되는가"를 묻는다. dsl이
    `x==+근`류(explicit) 형이면 대입해도 절대 둘 다 통과 못 한다(원 결함의 증상 그 자체) — ±-중립
    음함수(예: `(2ax+b)^2==b^2-4ac`)로 바꿔야 통과한다. 하드코딩된 formula_id 분기가 없다 — latex
    좌변(=대상 변수)·dsl의 대상 변수 등장 위치만으로 일반적으로 동작해, 코퍼스가 늘어도 자동으로
    커버된다.
    """
    if "=" not in latex:
        return f"latex에 '='가 없음(등식 아님): {latex!r}"
    if "==" not in dsl:
        return f"dsl에 '=='가 없음(등식 아님): {dsl!r}"
    latex_lhs, latex_rhs = latex.split("=", 1)
    target_var = _latex_side_to_sympy_text(latex_lhs)
    if not _BARE_IDENTIFIER_RE.fullmatch(target_var):
        return f"± 레코드의 latex 좌변이 단일 변수가 아님(± 게이트 적용 불가): {target_var!r}"

    dsl_lhs_raw, dsl_rhs_raw = dsl.split("==", 1)
    dsl_lhs, dsl_rhs = dsl_lhs_raw.strip(), dsl_rhs_raw.strip()
    var_pattern = rf"\b{re.escape(target_var)}\b"
    if not re.search(var_pattern, dsl_lhs) and not re.search(var_pattern, dsl_rhs):
        return f"dsl에 대상 변수 {target_var!r}가 전혀 등장하지 않음(± 대입 불가)"

    residual = f"({dsl_lhs}) - ({dsl_rhs})"
    verdicts: dict[str, IdentityVerdict] = {}
    for label, prefer_plus in (("root_plus", True), ("root_minus", False)):
        root_text = _expand_plus_minus(latex_rhs, prefer_plus=prefer_plus)
        root_expr = _latex_side_to_sympy_text(root_text)
        substituted = _substitute_symbol(residual, target_var, root_expr)
        verdicts[label] = identity_status(substituted, "0")
    if all(verdict is IdentityVerdict.identity for verdict in verdicts.values()):
        return None
    rendered = {label: verdict.value for label, verdict in verdicts.items()}
    return f"± 소실/해집합 불일치 — dsl이 두 근 모두에서 항등이어야 하는데: {rendered}"


def _formula_latex_dsl_violation(latex: str, dsl: str) -> str | None:
    """latex↔dsl 의미 정합 위반 사유(정합이면 None) — `\\pm`/`\\mp` 유무로 axis A/B를 분기.

    `condition_dsl_violation`(축④)과 같은 "위반 시 사유 문자열, 정합이면 None" 관례를 따른다.
    코퍼스 레코드뿐 아니라 합성(결함 주입) latex·dsl 문자열에도 직접 적용 가능한 순수 함수라,
    변별력 테스트가 실 코퍼스 파일을 건드리지 않고도 이 판정 로직을 그대로 재사용할 수 있다.
    """
    if "\\pm" in latex or "\\mp" in latex:
        return _pm_axis_violation(latex, dsl)
    return _structure_axis_violation(latex, dsl)


def test_formula_latex_dsl_semantically_consistent() -> None:
    """전 수식 25건의 latex↔dsl이 의미 정합(axis A·B 자동 분기) — 정상 코퍼스는 green.

    `formula.quadratic.roots`의 dsl이 ±-중립형으로 정정된 뒤(NS-04 acceptance②)에만 green이다 —
    이 테스트 자체가 그 정정의 회귀 방지 게이트다.
    """
    bad: dict[str, str] = {}
    for node in _load_formulas():
        violation = _formula_latex_dsl_violation(str(node["latex"]), str(node["dsl"]))
        if violation is not None:
            bad[str(node["formula_id"])] = violation
    assert not bad, f"latex↔dsl 의미 불일치: {bad}"


def test_pm_axis_gate_catches_lost_root_defect() -> None:
    """변별력 실증 — 같은 게이트 로직이 결함 dsl엔 red, 정정 dsl엔 green(같은 latex 대상).

    원 결함(2026-08-10 확정, `dsl_integration_gap_review.md` §2-⑧): quadratic.roots dsl이 +근
    하나만 표현(± 소실). 정정 dsl은 실 코퍼스에서 읽어(하드코딩 이중화 방지), 결함 dsl은 사고의
    실제 원본 문자열을 그대로 재현한다 — "성공/실패가 같은 값을 내면 검증이 아니다"(CLAUDE.md)의
    실증. 실 코퍼스 파일은 건드리지 않는다(게이트 핵심 로직을 순수 함수로 뽑아 직접 호출).
    """
    formulas_by_id = {str(f["formula_id"]): f for f in _load_formulas()}
    record = formulas_by_id["formula.quadratic.roots"]
    latex = str(record["latex"])
    fixed_dsl = str(record["dsl"])  # 코퍼스 현재값 — NS-04 acceptance②의 ±-중립 정정형
    defective_dsl = "x == (-b + sqrt(b**2 - 4*a*c))/(2*a)"  # 실사고 원본(+근 하나만·± 소실)

    assert (
        _formula_latex_dsl_violation(latex, fixed_dsl) is None
    ), "정정된 dsl은 게이트를 통과해야 한다"
    violation = _formula_latex_dsl_violation(latex, defective_dsl)
    assert violation is not None, "± 소실 결함 dsl은 게이트가 반드시 잡아야 한다(변별력)"
    assert "±" in violation, f"진단 메시지가 원인(± 소실)을 드러내야 한다: {violation!r}"


def test_pm_axis_flags_non_bare_target_variable() -> None:
    """± 레코드의 latex 좌변이 단일 변수가 아니면 명시 실패 — 조용한 오판 금지(합성 입력)."""
    violation = _formula_latex_dsl_violation(
        "x + 1 = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
        "x == (-b + sqrt(b**2 - 4*a*c))/(2*a)",
    )
    assert violation is not None
    assert "단일 변수" in violation


def test_pm_axis_flags_target_variable_missing_from_dsl() -> None:
    """± 레코드인데 dsl이 대상 변수를 아예 언급 안 하면 명시 실패(조용한 통과 금지·합성 입력)."""
    latex = "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"
    violation = _formula_latex_dsl_violation(latex, "y == 5")
    assert violation is not None
    assert "전혀 등장하지" in violation


def test_symbol_alias_table_covers_vieta_root_symbols() -> None:
    """구조 축 별칭 테이블 최종본 — vieta류 α/β↔r_1/r_2만(코퍼스 실측 기반·그 외 확장 없음)."""
    assert _SYMBOL_ALIASES == {"alpha": "r_1", "beta": "r_2"}


def test_structure_axis_flags_unresolved_symbol_mismatch() -> None:
    """별칭 테이블에 없는 기호 불일치는 조용히 통과하지 않고 명시 실패한다(합성 입력)."""
    violation = _formula_latex_dsl_violation("p + q = 1", "r_5 + r_6 == 1")
    assert violation is not None
    assert "구조 불일치" in violation


def test_expand_plus_minus_moves_mp_opposite_to_pm() -> None:
    """`\\mp`는 `\\pm`과 항상 반대 부호로 움직인다(코퍼스 미등장 — 직접 단위 검증으로 보강)."""
    assert _expand_plus_minus("a \\pm b \\mp c", prefer_plus=True) == "a + b - c"
    assert _expand_plus_minus("a \\pm b \\mp c", prefer_plus=False) == "a - b + c"


def test_latex_side_to_sympy_text_handles_nested_frac_and_sqrt() -> None:
    """분수 분자에 중첩된 `\\sqrt`(quadratic.roots 실 패턴)까지 재귀 전개되는지 직접 검증."""
    text = _latex_side_to_sympy_text("\\frac{-b + \\sqrt{b^2 - 4ac}}{2a}")
    assert text == "((-b + sqrt((b^2 - 4a*c)))/(2a))"
