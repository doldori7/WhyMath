"""중립 검증 뷰 계약 — 구조 만족 + **3상태 보존** 동결 (EOS-69).

`l6.blueprint.assembly`·`api.coach`는 수학 검증기를 부르지 않고 그 *결과*를 읽는다. EOS-69는
그 의존을 Protocol 메서드가 아니라 **중립 뷰**(`SolutionVerificationView`)로 끊었다. 뷰는
변환이 아니라 "덜 보기"라서 값이 바뀔 자리가 없어야 하는데, 그 "없어야 함"을 여기서 기계가
확인한다.

특히 지키는 것은 하나다 — **`unverifiable`이 `incorrect`로 접히지 않는 것**. 접히면 "기계가
판정 못 함"이 "학생이 틀림"이 되고, 그건 이 저장소의 검증 권위 서열 위반이다. 뷰·부분점수·
사유 분포 세 지점에서 각각 확인한다(한 곳만 보면 다른 곳에서 접혀도 초록이 된다).
"""

from __future__ import annotations

from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.l6.blueprint.assembly import partial_credit
from whymath_backend.schema.enums import StepType
from whymath_backend.schema.subject_adapter import (
    STEP_STATE_CORRECT,
    STEP_STATE_INCORRECT,
    STEP_STATE_UNVERIFIABLE,
    SolutionVerificationView,
    StepVerificationView,
)


def _view(steps: list[str], step_types: list[StepType | None] | None = None) -> object:
    """실제 검증기를 돌려 결과를 얻는다 — 스텁이 아니라 진짜 산출물로 뷰를 검증한다."""
    return verify_solution(steps, step_types)


def test_real_verifier_result_satisfies_the_neutral_view() -> None:
    """구조적 만족을 *런타임*으로 확인한다 — mypy만 믿지 않는다(이중 회계).

    `isinstance`는 시그니처를 보지 않으므로 이 단언만으로 충분하지는 않다. 그래서 아래
    테스트들이 실제 값 읽기까지 확인한다.
    """
    result = _view(["2*x + 1 = 7", "2*x = 6", "x = 3"])
    assert isinstance(result, SolutionVerificationView)
    for step in result.steps:
        assert isinstance(step, StepVerificationView)


def test_view_vocabulary_matches_the_real_states() -> None:
    """중립 상수가 실제 검증기 어휘와 같은 값인지 — 다르면 비교가 항상 False가 된다.

    변별력 있는 검사여야 하므로 *실제로 관측된* 상태와 대조한다. 상수만 서로 비교하면
    성공/실패 양쪽에서 같은 값을 내는 위장 검사가 된다.
    """
    correct = _view(["2*x = 6", "x = 3"])
    assert correct.steps[0].state == STEP_STATE_CORRECT
    assert correct.n_correct == 1

    incorrect = _view(["2*x = 6", "x = 4"])
    assert incorrect.steps[0].state == STEP_STATE_INCORRECT
    assert incorrect.n_incorrect == 1

    # 비대수 단계 — 판정 자체가 불가(틀린 것이 아니다).
    unverifiable = _view(["조건을 해석한다", "그래프를 그린다"], [StepType.조건해석])
    assert unverifiable.steps[0].state == STEP_STATE_UNVERIFIABLE
    assert unverifiable.n_unverifiable == 1


def test_unverifiable_is_never_counted_as_incorrect() -> None:
    """뷰 축 — 검증 불가 전이가 incorrect 카운트로 새지 않는다."""
    result = _view(["조건을 해석한다", "그래프를 그린다"], [StepType.조건해석])
    assert result.n_unverifiable == 1
    assert result.n_incorrect == 0, "판정 불가를 오답으로 세면 측정 실패가 오답으로 위장된다"
    assert result.first_incorrect_index is None
    assert result.n_correct + result.n_incorrect + result.n_unverifiable == result.n_transitions


def test_partial_credit_refuses_to_score_an_unverifiable_prefix() -> None:
    """부분점수 축 — 중립 뷰를 거쳐도 '확언 불가'가 '0점'이나 '만점'으로 접히지 않는다."""
    result = _view(["조건을 해석한다", "그래프를 그린다"], [StepType.조건해석])
    credit = partial_credit(4, result)
    assert credit.awarded_points is None, "판정 불가 구간에 점수를 만들면 허위 확언이다"
    assert credit.reason == "unverifiable_prefix"


def test_partial_credit_still_scores_a_verified_prefix() -> None:
    """대조군 — 검증된 구간은 그대로 점수가 난다(위 테스트가 '항상 None'이 아님을 증명)."""
    credit = partial_credit(4, _view(["2*x = 6", "x = 3"]))
    assert credit.awarded_points == 4
    assert credit.reason == "credited_full"


def test_reason_counts_are_plain_strings_and_sum_to_the_unverifiable_count() -> None:
    """사유 분포 축 — Core가 enum을 풀지 않아도 되도록 문자열 키로 나오고, 합이 보존된다.

    값 합이 `n_unverifiable`과 다르면 어딘가에서 사유가 유실됐거나 이중 계상된 것이다.
    """
    result = _view(["조건을 해석한다", "그래프를 그린다", "$$$"], [StepType.조건해석, None])
    counts = result.unverifiable_reason_counts
    assert counts, "검증 불가가 있는데 사유 분포가 비었다"
    assert all(isinstance(key, str) and not hasattr(key, "value") for key in counts)
    assert sum(counts.values()) == result.n_unverifiable
