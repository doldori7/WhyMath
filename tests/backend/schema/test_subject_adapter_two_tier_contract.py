"""과목 계약 **2층 구조**의 동결 — 필수층은 늘지 않고, 선택층은 늘어도 된다 (Kiki 판단 2026-08-31).

────────────────────────────────────────────────────────────────────────────
왜 산문이 아니라 테스트인가
────────────────────────────────────────────────────────────────────────────
"모든 과목에 강제되는 기본 계약"과 "선택적 검증 capability"를 나눈다는 판단은, 문서에만
적으면 **다음 세션이 모른 채로 어긴다**. 필수 Protocol에 메서드를 하나 더 다는 것은 5초면
되고 리뷰에서도 자연스러워 보이지만, 그 순간 역사·국어 어댑터는 `NotImplementedError`나 빈
구현을 강요당한다 — 그리고 빈 구현은 곧 "판정했다"는 거짓 신호가 된다.

그래서 필수층의 메서드 집합 자체를 상수로 동결한다. 늘리면 CI가 적색이 되고, 통과시키려면
아래 목록을 고치면서 **"왜 선택층으로 갈 수 없는가"를 적어야 한다**. 조용한 확장이 불가능해지는
것이 이 파일의 유일한 목적이다.

이 저장소에서 같은 부류의 실패가 반복됐다("검증 장치를 만들고 배선 확인 없이 완료 선언 금지"·
"정본화를 집행으로 착각한 완료 선언 금지"). 이 테스트는 그 계열의 *계약 확장* 축이다.
"""

from __future__ import annotations

from whymath_backend.schema import subject_adapter, verification_capabilities
from whymath_backend.schema.subject_adapter import SubjectAdapter

# ──────────────────────────────────────────────────────────────────────────
# 필수층 — 이 목록을 바꾸는 것은 "모든 과목이 반드시 제공한다"는 선언을 바꾸는 것이다.
# 추가 게이트: "Physics·Chemistry·History에도 **반드시** 존재하는가?" 예일 때만.
# 아니오면 `schema/verification_capabilities.py`(선택층)로 간다.
# ──────────────────────────────────────────────────────────────────────────
REQUIRED_METHODS: frozenset[str] = frozenset(
    {
        "evaluate_answer",  # 답 평가 — 채점 없는 과목은 없다
        "detect_misconception",  # 오개념 탐지 — 오답 원인 분석은 과목 무관
        "validate_problem",  # 문항 타당성 — 낼 수 있는 문제인지의 판정
    }
)


def _public_methods(protocol: type) -> frozenset[str]:
    """Protocol이 요구하는 공개 멤버 이름 — dunder·클래스 속성 제외."""
    inherited = set()
    for base in protocol.__mro__[1:]:
        inherited |= set(vars(base))
    own = {name for name in vars(protocol) if not name.startswith("_")}
    return frozenset(own - inherited)


def test_required_contract_has_not_silently_grown() -> None:
    """필수층이 3종 그대로인가 — 늘었으면 선택층으로 갈 수 없는 이유를 적어야 한다."""
    actual = _public_methods(SubjectAdapter) - {"subject_id"}
    assert actual == REQUIRED_METHODS, (
        f"SubjectAdapter 필수 메서드가 바뀌었다: {sorted(actual)} (기대 {sorted(REQUIRED_METHODS)}).\n"
        "늘렸다면 먼저 물어라 — 이 능력이 Physics·Chemistry·History에도 **반드시** 존재하는가?\n"
        "아니오면 schema/verification_capabilities.py(선택층)로 옮기고, 예면 이 목록과\n"
        "subject_adapter.py 모듈 docstring의 2층 표를 함께 고쳐라."
    )


def test_optional_capabilities_are_not_required_of_every_subject() -> None:
    """선택층 능력이 필수층으로 새어 들어오지 않았는가 — 두 목록이 겹치면 분리가 무너진 것이다."""
    optional_methods = set()
    for name in verification_capabilities.__all__:
        member = getattr(verification_capabilities, name)
        if isinstance(member, type):
            optional_methods |= _public_methods(member)
    overlap = optional_methods & REQUIRED_METHODS
    assert (
        not overlap
    ), f"선택 능력이 필수 계약과 겹친다: {sorted(overlap)} — 과목이 두 번 강요받는다"


def test_optional_tier_is_discoverable_from_the_required_tier() -> None:
    """필수층 문서가 선택층을 **가리키는가**.

    가리키지 않으면 필수 계약만 읽은 사람이 선택층의 존재를 모르고 여기에 메서드를 추가한다
    — 이 2층 구조가 깨지는 가장 흔한 경로가 '몰라서'다. 링크는 장식이 아니라 방어다.
    """
    doc = subject_adapter.__doc__ or ""
    assert "verification_capabilities" in doc, "필수 계약 docstring이 선택층을 가리키지 않는다"


def test_math_adapter_provides_required_and_may_provide_optional() -> None:
    """수학 어댑터는 필수 3종을 **전부** 제공하고, 선택 능력은 별도 객체로 제공한다.

    선택 능력이 `MathSubjectAdapter`의 메서드로 들어가 있지 않은지도 함께 본다 — 들어가 있으면
    "필수 계약을 만족하는 객체"와 "선택 능력을 가진 객체"가 같아져, 다음 과목이 그 모양을
    따라 하다가 선택 능력을 필수처럼 구현하게 된다.
    """
    from whymath_backend.l4.subject_adapter_math import MathSubjectAdapter

    adapter = MathSubjectAdapter()
    for method in REQUIRED_METHODS:
        assert callable(getattr(adapter, method, None)), f"수학 어댑터가 필수 {method} 미제공"
    for optional in ("identity_status", "verify_chain", "extract_sealed"):
        assert not hasattr(
            adapter, optional
        ), f"선택 능력 {optional}이 필수 어댑터 객체에 달려 있다 — 2층 분리가 흐려진다"
