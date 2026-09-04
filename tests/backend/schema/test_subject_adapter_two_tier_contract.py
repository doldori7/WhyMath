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


# ──────────────────────────────────────────────────────────────────────────
# 후보 9종 전수 판정 (EOS-90 · 계획서 100 §3.9 Kiki 제시 목록)
#
# "과목마다 반드시 존재하는 능력만 계약에 넣는다"를 9후보에 기계 적용한 결과다. 판정 근거는
# `docs/reviews/subject_contract_v1_candidate_verdicts_2026-09-04.md`.
#
# 행선지는 넷뿐이다:
#   REQUIRED  — 필수층(SubjectAdapter). 모든 과목이 반드시 제공한다.
#   OPTIONAL  — 선택층(verification_capabilities). 있는 과목만. Core는 없을 때 경로를 갖는다.
#   DATA      — 계약 아님. 이미 과목 중립 스키마에 **데이터**로 존재한다 → Physics는 행만 채운다.
#   CORE_OWNED— 계약 아님. Core가 **이미 스스로** 하는 일이라 과목에 되물을 것이 없다.
#   ADAPTER_INTERNAL — 계약 아님. 어댑터 안에 있어도 되지만 Core가 위임할 진입점이 없다.
#
# 이 표를 기계가 기억하는 이유: 다음 세션이 "getConcept이 없네?"라며 필수층에 넣는 것을 막는다.
# 넣으면 아래 테스트가 판정 기록과 함께 RED가 된다.
# ──────────────────────────────────────────────────────────────────────────
CANDIDATE_VERDICTS: dict[str, str] = {
    # Kiki 후보명(camelCase) → 판정. 저장소 명명은 snake_case다.
    "evaluateAnswer": "REQUIRED",
    "detectMisconception": "REQUIRED",
    "validateProblem": "REQUIRED",
    # 조회(read)지 계산(compute)이 아니다 — 계약에 넣으면 어댑터가 ORM 위임층이 되고
    # schema가 db를 알게 되는 계층 역방향이 된다. 개념·엣지·성취기준 스키마는 이미 과목 중립.
    "getConcept": "DATA",
    "getPrerequisites": "DATA",
    "getLearningObjectives": "DATA",
    # l2.irt가 응답 통계만으로 난이도 b를 추정한다 — 문항 내용을 한 글자도 보지 않는다.
    "estimateDifficulty": "CORE_OWNED",
    # 위임할 공개 진입점 0건(설명 생성기는 전부 생성기 내부 비공개 함수).
    "generateExplanation": "ADAPTER_INTERNAL",
    # 유일한 선택층 후보. 단 현행 VisualizationStyle 16종이 전량 수학 어휘라
    # **중립 반환 타입 재설계가 전제**다. 그 전에는 계약이 될 수 없다.
    "getRepresentations": "OPTIONAL",
}

# camelCase 후보명 → 저장소의 snake_case 이름(필수층 판정 대조용).
_SNAKE = {
    "evaluateAnswer": "evaluate_answer",
    "detectMisconception": "detect_misconception",
    "validateProblem": "validate_problem",
    "getConcept": "get_concept",
    "getPrerequisites": "get_prerequisites",
    "getLearningObjectives": "get_learning_objectives",
    "estimateDifficulty": "estimate_difficulty",
    "generateExplanation": "generate_explanation",
    "getRepresentations": "get_representations",
}


def test_every_candidate_has_a_recorded_verdict() -> None:
    """Kiki 후보 9종이 빠짐없이 판정돼 있는가 — 판정하지 않은 채 넘어간 후보가 없어야 한다."""
    assert len(CANDIDATE_VERDICTS) == 9, sorted(CANDIDATE_VERDICTS)
    assert set(CANDIDATE_VERDICTS) == set(_SNAKE), "후보 목록과 이름 매핑이 어긋났다"
    allowed = {"REQUIRED", "OPTIONAL", "DATA", "CORE_OWNED", "ADAPTER_INTERNAL"}
    unknown = {k: v for k, v in CANDIDATE_VERDICTS.items() if v not in allowed}
    assert not unknown, f"정의되지 않은 행선지: {unknown}"


def test_only_required_verdicts_appear_in_the_required_tier() -> None:
    """판정과 실제 계약이 일치하는가 — REQUIRED만 프로토콜에 있고 나머지는 없어야 한다.

    누가 `get_concept`을 필수층에 추가하면 여기서 RED가 나고, 판정 기록(DATA)이 함께 보인다.
    판정을 바꾸려면 표를 고쳐야 하므로 조용한 확장이 불가능하다.
    """
    actual = _public_methods(SubjectAdapter) - {"subject_id"}
    for candidate, verdict in CANDIDATE_VERDICTS.items():
        name = _SNAKE[candidate]
        if verdict == "REQUIRED":
            assert name in actual, f"{candidate}는 REQUIRED 판정인데 필수층에 없다"
        else:
            assert name not in actual, (
                f"{candidate}가 필수층에 들어왔다 — 판정은 {verdict}였다.\n"
                "필수층으로 올리려면 CANDIDATE_VERDICTS를 고치고 판정 문서의 근거를 갱신하라."
            )


def test_required_tier_holds_exactly_the_required_verdicts() -> None:
    """역방향 — 필수층에 판정표 밖의 메서드가 몰래 들어오지 않았는가."""
    expected = {_SNAKE[c] for c, v in CANDIDATE_VERDICTS.items() if v == "REQUIRED"}
    actual = _public_methods(SubjectAdapter) - {"subject_id"}
    assert actual == expected == REQUIRED_METHODS, (actual, expected, REQUIRED_METHODS)


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
