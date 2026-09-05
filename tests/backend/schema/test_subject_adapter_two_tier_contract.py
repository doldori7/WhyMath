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

from pydantic import BaseModel

from whymath_backend.schema import subject_adapter, verification_capabilities
from whymath_backend.schema.subject_adapter import (
    AnswerEvaluation,
    MisconceptionSignal,
    ProblemStatement,
    ProblemValidation,
    SubjectAdapter,
)

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


# ══════════════════════════════════════════════════════════════════════════
# EOS-91 — Provisional 상태의 단조 축소 래칫 (Kiki 지시 2026-09-05)
#
# 위 REQUIRED_METHODS는 *메서드*만 본다. 계약의 과목 중립성이 실제로 깨지는 자리는
# **필드**인데(예: `conditions`가 물리 관계식을 담을 수 있는가), 실측 결과 필드 축은
# 동결이 **0건**이었다 — 필드를 늘려도 줄여도 CI가 조용했다.
#
# 규칙 2조를 기계로 옮기면 비대칭 래칫이 된다:
#   · 확장(신규 필드) → **무조건 RED**. 예외 경로 없음(규칙 2조 나 "Core 확장 금지").
#   · 축소(필드 제거) → 강등 대장 DEMOTED_FIELDS 경유로만 통과(규칙 2조 가).
#     조용한 삭제와 *기록된 강등*을 구분하기 위한 것이다 — 대장이 곧 강등의 증적이다.
# ══════════════════════════════════════════════════════════════════════════

CORE_CONTRACT_FIELDS: dict[str, frozenset[str]] = {
    "ProblemStatement": frozenset(
        {"problem_ref", "question_text", "answer", "answer_kind", "conditions"}
    ),
    "AnswerEvaluation": frozenset({"state", "reason", "checked_axes"}),
    "ProblemValidation": frozenset({"state", "reason", "machine_axes", "residual_axes"}),
    "MisconceptionSignal": frozenset({"code", "confidence", "matched_signals"}),
}
"""프로브 전 Core 계약의 필드 전수 — 이 집합은 **늘어날 수 없고**, 줄어들면 강등 대장을 요구한다."""

DEMOTED_FIELDS: dict[str, str] = {}
"""프로브에서 깨져 Core→Adapter 강등된 필드 → 이관처.

키는 `"<DTO>.<필드>"`, 값은 이관처(예: "verification_capabilities.SymbolicIdentity" ·
"l4.subject_adapter_math 내부"). **프로브(EOS-92) 전에는 비어 있는 것이 정상이다** —
여기에 항목이 생겼다는 것은 어떤 필드가 과목 중립이 아님이 증명됐다는 뜻이다.
"""

_DTO_TYPES: dict[str, type[BaseModel]] = {
    "ProblemStatement": ProblemStatement,
    "AnswerEvaluation": AnswerEvaluation,
    "ProblemValidation": ProblemValidation,
    "MisconceptionSignal": MisconceptionSignal,
}


def test_core_contract_fields_never_grow() -> None:
    """규칙 2조 (나) — Core 확장 금지. 필드가 하나라도 늘면 예외 없이 RED."""
    grown: dict[str, list[str]] = {}
    for name, frozen in CORE_CONTRACT_FIELDS.items():
        actual = frozenset(_DTO_TYPES[name].model_fields)
        if extra := actual - frozen:
            grown[name] = sorted(extra)
    assert not grown, (
        f"Core 계약 필드가 늘었다: {grown}\n"
        "규칙 2조 (나) Core 확장 금지 — 이 계약은 프로브를 거치며 **줄어들 수만 있다**.\n"
        "새 능력은 schema/verification_capabilities.py(선택층) 또는 어댑터 내부로 보내라.\n"
        "필수층에 넣어야만 하는 근거가 있다면 Kiki 판단을 받고 이 상수와 계약 docstring의\n"
        "상태 절을 함께 고쳐라(조용한 확장 불가)."
    )


def test_core_contract_shrink_requires_demotion_ledger() -> None:
    """규칙 2조 (가) — 강등은 대장 경유. 대장 없는 필드 제거는 조용한 삭제이므로 RED."""
    for name, frozen in CORE_CONTRACT_FIELDS.items():
        actual = frozenset(_DTO_TYPES[name].model_fields)
        for missing in sorted(frozen - actual):
            key = f"{name}.{missing}"
            assert key in DEMOTED_FIELDS, (
                f"Core 계약에서 필드가 사라졌는데 강등 대장에 없다: {key}\n"
                "규칙 2조 (가)는 강등을 *요구*하지만, 강등은 **기록되어야** 강등이다.\n"
                f'DEMOTED_FIELDS["{key}"] = "<이관처>" 를 적고 프로브 근거(EOS-92)를 남겨라.'
            )
            assert DEMOTED_FIELDS[key].strip(), f"{key} 강등 대장에 이관처가 비어 있다"


def test_demotion_ledger_only_names_real_contract_fields() -> None:
    """강등 대장이 실재하지 않는 필드를 가리키지 않는가 — 대장 자체의 오타·유령 항목 차단."""
    for key in DEMOTED_FIELDS:
        dto, _, field = key.partition(".")
        assert dto in CORE_CONTRACT_FIELDS, f"강등 대장의 알 수 없는 DTO: {key}"
        assert field in CORE_CONTRACT_FIELDS[dto], (
            f"강등 대장이 계약에 없던 필드를 가리킨다: {key}\n"
            "강등은 *있던 것*을 내보내는 일이다 — 없던 필드는 강등 대상이 아니다."
        )


def test_contract_status_is_provisional_until_probe() -> None:
    """상태 라벨 동결 — 프로브(EOS-92) 없이 Provisional을 되돌리면 RED.

    이 검사가 없으면 상태 절은 산문일 뿐이라 다음 세션이 무심코 'Frozen'으로 되돌린다.
    문구 자체를 계약으로 고정해, 되돌리려면 이 테스트를 함께 고치는 **의도적 행위**를 요구한다.
    """
    doc = subject_adapter.__doc__ or ""
    assert "Provisional" in doc, (
        "계약 상태가 Provisional로 표기돼 있지 않다 — 교차 과목 프로브(EOS-92) 통과 전까지\n"
        "이 계약은 Math 단일 과목에서 도출된 가설이다."
    )
    assert "cross-subject probe" in doc, "해제 조건(교차 과목 프로브)이 상태 절에 없다"
    assert "9/27" in doc, "프로브 기한(9/27 · G1 게이트일)이 상태 절에 없다"
    for clause in ("강등", "Core 확장 금지", "ADR", "중복 구현", "3건을 초과"):
        assert clause in doc, f"프로브 결과 처리 규칙 3조가 상태 절에 없다: {clause!r}"
    # (다) 출구가 없으면 (가)·(나)는 위반을 숨기는 금지가 된다 — 출구 조항의 존재를 동결한다.
    assert "(다)" in doc, "규칙 (다) 출구 조항이 없다 — 출구 없는 금지는 편법을 부른다"
    # 래칫이 못 잡는 축을 문서가 스스로 밝히는가 — 이 한계 표기가 사라지면 9/27에
    # 'CI 초록 = 계약 준수'로 오판한다.
    assert "필드 개수" in doc, "래칫의 한계('기계는 필드 개수만 본다')가 상태 절에서 사라졌다"
    # 기계가 못 보는 축에 소유자가 지목돼 있는가 — "기계 집행 없음"에서 끝나면 알려진 갭에
    # 소유자가 없는 상태다. 보상 통제(EOS-92)의 지목 자체를 동결한다.
    assert "검증 책임은 `EOS-92`" in doc, (
        "의미적 확장 축의 검증 책임자(EOS-92)가 한계 절에서 사라졌다 — 기계 집행이 없는 갭은\n"
        "보상 통제를 지목해야 소유자가 있는 갭이 된다."
    )
