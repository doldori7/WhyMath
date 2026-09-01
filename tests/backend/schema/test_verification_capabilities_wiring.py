"""EOS-69 능력 계약의 **배선 실재성** 동결 — 계약이 있다가 아니라 계약이 돌아간다.

이 파일이 막는 것은 세 가지다(전부 이 저장소에서 실제로 일어난 부류):

1. **정본화 ≠ 집행** — 계약 모듈이 존재해도 서빙 코드가 부르지 않으면 아무 일도 안 한다.
   여기서는 합성 루트가 실제로 계약을 만족하는 객체를 준다는 것을 *런타임*으로 확인한다
   (`mypy`는 정적으로만 본다 — 지연 import가 깨져 있으면 mypy는 통과하고 요청이 죽는다).
2. **주입이 무시되는 배선** — 기본값 폴백이 있는 DI는 주입을 조용히 무시해도 테스트가
   초록일 수 있다. 각 호출부에 *구별 가능한* 더블을 넣어 **그 더블이 실제로 불렸는지**
   본다("작동 신호 없는 알고리즘 부착 금지"의 DI 판).
3. **합성 루트의 임무 이탈** — 합성 루트에 판정 로직이 들어오면 라벨만 INFRA인 어댑터가
   된다. 판정 라이브러리를 모듈 상단에서 끌어오지 않는지를 구조로 확인한다.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from whymath_backend import composition
from whymath_backend.schema.verification_capabilities import (
    AssessmentAnswerVerifier,
    ChainVerification,
    ChainVerificationCounts,
    EquivalenceOutcome,
    ExpressionEquivalence,
    ExpressionSeal,
    FinalAnswerVerifier,
    StepOutcome,
    VerificationOutcome,
)

_COMPOSITION_PATH = pathlib.Path(composition.__file__)


# ──────────────────────────────────────────────────────────────────────────
# ① 합성 루트가 실제로 계약을 만족하는 객체를 준다 (런타임 — 지연 import 포함)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("factory_name", "protocol"),
    [
        ("default_expression_equivalence", ExpressionEquivalence),
        ("default_final_answer_verifier", FinalAnswerVerifier),
        ("default_assessment_answer_verifier", AssessmentAnswerVerifier),
        ("default_expression_seal", ExpressionSeal),
    ],
)
def test_composition_factory_returns_a_working_capability(
    factory_name: str, protocol: type
) -> None:
    """팩토리가 계약 메서드를 *가진* 객체를 준다 — 지연 import가 깨지면 여기서 터진다."""
    impl = getattr(composition, factory_name)()
    for method in (name for name in dir(protocol) if not name.startswith("_")):
        assert callable(getattr(impl, method, None)), f"{factory_name} → {method} 미구현"


def test_default_equivalence_actually_judges() -> None:
    """이름만 맞는 껍데기가 아니라 **판정을 한다** — 참/거짓 양쪽에서 다른 값을 낸다."""
    impl = composition.default_expression_equivalence()
    assert impl.identity_status("(x+1)**2", "x**2 + 2*x + 1") is EquivalenceOutcome.identity
    assert impl.identity_status("x + 1", "x + 2") is EquivalenceOutcome.not_identity


# ──────────────────────────────────────────────────────────────────────────
# ② 주입이 실제로 존중된다 (더블이 불렸는지 — 폴백이 조용히 이기지 않는지)
# ──────────────────────────────────────────────────────────────────────────
class _AlwaysNotIdentity:
    """구별 가능한 더블 — 무엇을 넣든 `not_identity`. 진짜 SymPy와 결과가 갈린다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def identity_status(self, lhs: str, rhs: str) -> EquivalenceOutcome:
        self.calls.append((lhs, rhs))
        return EquivalenceOutcome.not_identity


def test_slot_generator_honors_injected_equivalence() -> None:
    """주입한 능력이 **실제로 불린다** — 기본 구현이었다면 True가 나올 입력을 쓴다."""
    from whymath_backend.l3.pedagogy.slot_generator import verify_slot_payload

    payload = {"verification": {"claim_lhs": "(x+1)**2", "claim_rhs": "x**2 + 2*x + 1"}}
    # 기본(수학) 구현이면 identity → True. 더블이 이기면 False.
    assert verify_slot_payload(payload) is True  # 변별력 확인: 기본 경로는 True다.

    double = _AlwaysNotIdentity()
    assert verify_slot_payload(payload, equivalence=double) is False
    assert double.calls == [("(x+1)**2", "x**2 + 2*x + 1")], "주입한 더블이 불리지 않았다"


def test_slot_generator_still_returns_none_without_verification_claim() -> None:
    """주입 여부와 무관하게 `verification` 키가 없으면 None — 개념형 슬롯 정직 표기."""
    from whymath_backend.l3.pedagogy.slot_generator import verify_slot_payload

    double = _AlwaysNotIdentity()
    assert verify_slot_payload({"body": "개념 발문"}, equivalence=double) is None
    assert double.calls == [], "판정 대상이 아닌데 능력을 불렀다"


# ──────────────────────────────────────────────────────────────────────────
# ③ 합성 루트가 배선만 한다 (판정 로직 유입 차단)
# ──────────────────────────────────────────────────────────────────────────
def test_composition_root_has_no_module_level_adapter_import() -> None:
    """어댑터 import는 **함수 안**에서만 — 상단에 두면 모든 경로가 SymPy를 끌고 온다."""
    tree = ast.parse(_COMPOSITION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:  # 모듈 최상위만 본다(함수 안은 대상 아님).
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(
                "whymath_backend.l"
            ), f"합성 루트 최상위에서 계층 모듈을 import한다: {node.module}"
        if isinstance(node, ast.If):  # `if TYPE_CHECKING:` 블록 — 런타임 import 아님.
            continue


def test_composition_root_functions_are_thin() -> None:
    """각 팩토리는 import 1줄 + return 1줄 — 판정·분기가 들어오면 실패한다.

    이 검사가 변별력을 갖는 이유: `if`·`for`·비교 연산이 하나라도 들어오면 본문 노드 수가
    2를 넘는다. 과목 셀렉터가 필요해지는 날 이 테스트가 먼저 실패해 **설계 결정을 강제한다**
    (조용히 어댑터화되지 않는다).
    """
    tree = ast.parse(_COMPOSITION_PATH.read_text(encoding="utf-8"))
    factories = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert factories, "합성 루트에 팩토리가 없다"
    for fn in factories:
        body = [n for n in fn.body if not isinstance(n, ast.Expr)]  # docstring 제외
        assert len(body) == 2, f"{fn.name}: 본문이 배선 2줄을 넘는다({len(body)}) — 판정 유입 의심"
        assert isinstance(body[0], ast.ImportFrom), f"{fn.name}: 첫 줄이 지연 import가 아니다"
        assert isinstance(body[1], ast.Return), f"{fn.name}: 둘째 줄이 return이 아니다"


# ──────────────────────────────────────────────────────────────────────────
# ④ 계약이 상태를 재해석하지 않는다 (어댑터 enum이 중립 enum과 **같은 객체**)
# ──────────────────────────────────────────────────────────────────────────
def test_adapter_states_are_aliases_not_copies() -> None:
    """별칭 공유 — 별도 정의였다면 경계마다 매핑이 필요하고 그 매핑이 붕괴 지점이 된다."""
    from whymath_backend.l3.symbolic_equivalence import IdentityVerdict
    from whymath_backend.l3.verify_final_answer import FinalAnswerState
    from whymath_backend.l3.verify_step import VerifyStepState

    assert VerifyStepState is VerificationOutcome
    assert FinalAnswerState is VerificationOutcome
    assert IdentityVerdict is EquivalenceOutcome


def test_solution_verification_result_satisfies_the_chain_contracts() -> None:
    """실제 어댑터 결과가 **변환 없이** 계약을 만족한다(구조적 Protocol 규칙 1의 런타임 판)."""
    from whymath_backend.l3.verify_solution import verify_solution

    result = verify_solution(["2*x = 4", "x = 2"])
    assert isinstance(result, ChainVerification)
    assert isinstance(result, ChainVerificationCounts)
    assert result.n_correct + result.n_incorrect + result.n_unverifiable == result.n_transitions
    assert sum(result.unverifiable_by_reason.values()) == result.n_unverifiable
    for step in result.steps:
        assert isinstance(step, StepOutcome)
        assert isinstance(step.state, VerificationOutcome)


# ──────────────────────────────────────────────────────────────────────────
# ⑤ EOS-28 — 형태 어휘는 **측정이 허가한 것만** 담는다
# ──────────────────────────────────────────────────────────────────────────
def test_expected_form_vocabulary_is_measurement_gated() -> None:
    """`ExpectedForm`의 각 값이 스캐너 패턴에 실재하고, 코퍼스 적중이 0이 아니어야 한다.

    이 저장소가 반복해서 다친 지점이 "소비처 0 추상"이다 — 쓰이지 않을 어휘를 미리 넣으면
    그것을 지탱하는 분기·테스트·문서가 함께 생기고 아무도 지우지 않는다. 그래서 어휘 추가의
    조건을 **기계가 묻게** 한다: 스캐너가 코퍼스에서 그 형태를 실제로 잡는가?

    이 테스트가 실패하는 두 방향 모두 의미가 있다:
      · 어휘를 추가했는데 적중 0 → 근거 없는 추상. 코퍼스가 먼저 생겨야 한다.
      · 코퍼스에서 형태가 사라짐 → 그 어휘가 죽었다. 지울지 판단해야 한다.
    """
    import importlib.util
    import pathlib

    from whymath_backend.schema.answer_form import ExpectedForm

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    scanner_path = repo_root / "scripts/analysis/answer_form_requirement_scan.py"
    corpus = repo_root / "data/corpus"
    if not scanner_path.exists() or not corpus.exists():
        import pytest

        pytest.skip("스캐너·코퍼스가 없는 체크아웃 — 측정 불가(통과로 위장하지 않는다)")

    spec = importlib.util.spec_from_file_location("_form_scan", scanner_path)
    assert spec and spec.loader
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)

    for form in ExpectedForm:
        assert (
            form.value in scanner.FORM_PATTERNS
        ), f"어휘 '{form.value}'가 스캐너 패턴에 없다 — 측정 경로 없이 추가됐다"

    result = scanner.scan(corpus)
    for form in ExpectedForm:
        hits = result["form_hits"].get(form.value, [])
        assert hits, (
            f"어휘 '{form.value}'의 코퍼스 적중이 0건이다 — 소비처 0 추상. "
            f"코퍼스에 그 형태가 먼저 있어야 한다(측정 없는 도입 없음)."
        )
