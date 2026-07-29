"""유한 표본공간 전수 열거 검산기(S4-13 ①) — 순수·결정론·LLM 0.

검증 축:
  ① 알려진 확률·경우의 수를 정확 유리수로 맞힌다(주사위 합·동전·주머니·조건부).
  ② **중복 라벨 등확률**: 같은 색 공이 여러 개일 때 '색 조합'이 아니라 *물체 인덱스*를
     열거해야 답이 맞는다(이 도메인 정확성의 핵심).
  ③ **변별력**: 틀린 답은 fail, 근삿값은 통과하지 않는다.
  ④ **정직한 회피**: 파싱 불가·등확률 깨짐(중복조합)·열거 한도 초과·and/or 혼용은
     pass 위장 없이 unverifiable/예외.
  ⑤ 수용 게이트(`_CONCEPTUAL_VERIFIERS`) 결선 — answer_kind로 실제 분기된다.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from whymath_backend.l3.equivalent.acceptance import _CONCEPTUAL_VERIFIERS
from whymath_backend.l3.finite_probability import (
    FiniteProbabilityError,
    describe_model_ko,
    enumerate_model,
    parse_finite_model,
    verify_finite_count,
    verify_finite_probability,
)

_DICE = "space=dice(n=2,faces=6); event=sum==7"
_MARBLE = "space=draw(items=[R,R,R,B,B],k=2,ordered=false,replace=false); event=count(R)==2"


# ── ① 알려진 값 ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("conditions", "answer"),
    [
        (_DICE, "1/6"),
        ("space=dice(n=2,faces=6); event=sum==2", "1/36"),
        ("space=coin(n=3); event=count(H)==2", "3/8"),
        ("space=coin(n=4); event=count(H)>=3", "5/16"),
        (_MARBLE, "3/10"),
        ("space=dice(n=1,faces=6); event=sum>=5", "1/3"),
    ],
)
def test_known_probabilities_pass(conditions: str, answer: str) -> None:
    """교과서 값과 일치 — 전수 열거가 정확 유리수를 낸다."""
    verdict = verify_finite_probability(conditions, answer)
    assert verdict.state == "pass", verdict.reason


def test_conditional_probability_uses_given_clause() -> None:
    """조건부확률 — P(합≥10 | 최댓값≥5). 조건 사건 안에서만 센다."""
    conditions = "space=dice(n=2,faces=6); event=sum>=10; given=max>=5"
    result = enumerate_model(parse_finite_model(conditions))
    # 최댓값≥5인 경우 20가지, 그중 합≥10은 6가지(직접 셈: (4,6),(6,4),(5,5),(5,6),(6,5),(6,6)).
    assert (result.conditioned, result.favorable) == (20, 6)
    assert verify_finite_probability(conditions, "3/10").state == "pass"


def test_finite_count_counts_favorable_outcomes() -> None:
    """경우의 수형 — 답이 확률이 아니라 유리한 경우의 수."""
    conditions = "space=dice(n=2,faces=6); event=sum>=10"
    assert verify_finite_count(conditions, "6").state == "pass"
    assert verify_finite_count(conditions, "5").state == "fail"


# ── ② 중복 라벨 등확률(물체 인덱스 열거) ────────────────────────────────
def test_duplicate_labels_enumerate_objects_not_label_combinations() -> None:
    """빨강3·파랑2에서 2개를 꺼내 모두 빨강 = C(3,2)/C(5,2) = 3/10.

    '색 조합'({RR},{RB},{BB})을 세면 1/3이 나온다 — 등확률이 아니기 때문이다. 전수 열거가
    물체 인덱스를 도는지 이 값이 판별한다.
    """
    result = enumerate_model(parse_finite_model(_MARBLE))
    assert result.total == math.comb(5, 2) == 10
    assert result.favorable == math.comb(3, 2) == 3
    assert result.probability == Fraction(3, 10)
    assert verify_finite_probability(_MARBLE, "1/3").state == "fail"


# ── ③ 변별력 ──────────────────────────────────────────────────────────
def test_wrong_answer_fails_with_exact_reason() -> None:
    verdict = verify_finite_probability(_DICE, "1/9")
    assert verdict.state == "fail"
    assert verdict.reason is not None and "6/36" in verdict.reason


def test_rounded_decimal_is_not_accepted_as_exact_probability() -> None:
    """근삿값(0.1667)은 1/6이 아니다 — 정확값 계약을 기계가 강제한다."""
    assert verify_finite_probability(_DICE, "0.1667").state == "fail"
    # 정확한 유한소수는 통과한다(0.5 == 1/2).
    assert verify_finite_probability("space=coin(n=1); event=count(H)==1", "0.5").state == "pass"


def test_samples_checked_reports_full_space_size() -> None:
    """`samples_checked`가 표본공간 크기 = '전수'임이 수치로 드러난다(난수 표본과 구별)."""
    assert verify_finite_probability(_DICE, "1/6").samples_checked == 36


# ── ④ 정직한 회피 ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "conditions",
    [
        "space=dice(n=2,faces=6)",  # event 절 없음
        "space=roulette(n=2); event=sum==7",  # 미지 표본공간
        "space=dice(n=2,faces=6); event=sum ~ 7",  # 술어 문법 밖
        "space=coin(n=3); event=sum==2",  # 라벨 공간에 수치 술어
        "space=dice(n=2,faces=6); event=sum==7 and max>=5 or min==1",  # and/or 혼용
        "space=draw(items=[R,B],k=2,ordered=false,replace=true); event=count(R)==2",  # 중복조합
        "space=dice(n=12,faces=20); event=sum==30",  # 열거 한도 초과
    ],
)
def test_unparseable_or_unsafe_models_are_unverifiable(conditions: str) -> None:
    """pass 위장 없이 unverifiable — 사유에 예외 타입명이 실린다(침묵 실패 금지)."""
    verdict = verify_finite_probability(conditions, "1/6")
    assert verdict.state == "unverifiable"
    assert verdict.reason is not None and "FiniteProbabilityError" in verdict.reason


def test_unreadable_claim_is_unverifiable_not_fail() -> None:
    """주장값을 못 읽으면 '틀렸다'가 아니라 '모른다'(보수적 회피)."""
    assert verify_finite_probability(_DICE, "약 17%").state == "unverifiable"
    assert verify_finite_count(_DICE, "여섯").state == "unverifiable"


def test_zero_probability_condition_is_unverifiable() -> None:
    """조건 사건이 공집합이면 조건부확률이 미정의 — 0으로 단정하지 않는다."""
    conditions = "space=dice(n=2,faces=6); event=sum==7; given=sum==13"
    assert verify_finite_probability(conditions, "0").state == "unverifiable"


def test_parse_rejects_unknown_clause() -> None:
    with pytest.raises(FiniteProbabilityError):
        parse_finite_model("space=dice(n=2,faces=6); event=sum==7; wager=high")


# ── ⑤ 수용 게이트 결선 + 형식모델 산문 ───────────────────────────────
def test_conceptual_verifier_table_wires_both_kinds() -> None:
    """게이트의 answer_kind 분기표에 실제로 꽂혀 있어야 코퍼스 경로가 산다(dead code 방지)."""
    assert _CONCEPTUAL_VERIFIERS["finite_probability"] is verify_finite_probability
    assert _CONCEPTUAL_VERIFIERS["finite_count"] is verify_finite_count


def test_korean_model_description_states_what_machine_actually_checked() -> None:
    """교차검증 ③ 관점이 발문과 대조할 산문 — 발문을 참조하지 않고 모델만 서술한다."""
    model = parse_finite_model(_MARBLE)
    prose = describe_model_ko(model, enumerate_model(model))
    assert "순서를 구별하지 않고" in prose
    assert "다시 넣지 않고" in prose
    assert "10가지" in prose
    assert "3/10" in prose
