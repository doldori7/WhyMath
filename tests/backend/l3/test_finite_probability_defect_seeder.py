"""유한 확률 잔여 축 결함 시더 hermetic 테스트(S4-16, LLM 0).

`l3/finite_probability_defect_seeder.py`가 밴드 A(dice-sum-prob)·B(coin-heads-prob)
스켈레톤의 발문만 결정론 변조하고, `conditions`·`answer`·`answer_explanation`은 항상
원본(무결함) 값 그대로 둠을 동결한다. 앵커 불일치·풀 초과 요청이 조용히 넘어가지 않고
`ValueError`로 즉시 드러남을 확인한다(침묵 실패 금지).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.finite_probability import (
    enumerate_model,
    parse_finite_model,
    verify_finite_probability,
)
from whymath_backend.l3.finite_probability_defect_seeder import (
    DEFECT_CLASSES,
    SeededResidueItem,
    _mutate_ambiguous_statement,
    _mutate_condition_missing,
    _mutate_equal_probability_unstated,
    _mutate_multiple_answers,
    build_defect_seeded_residue_set,
)

# ──────────────────────────────────────────────────────────────────────────
# 결정론·구성
# ──────────────────────────────────────────────────────────────────────────


def test_deterministic_same_seed() -> None:
    a = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s1")
    b = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s1")
    assert [i.slug for i in a] == [j.slug for j in b]
    assert [i.question_text for i in a] == [j.question_text for j in b]


def test_different_seed_can_change_selection() -> None:
    a = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s1")
    b = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s2")
    # 같은 slug 명명 규칙이라 slug 자체는 동일 나열이지만, 실제 뽑힌 발문 내용은 달라질 수
    # 있다(선택 순서가 시드에 좌우됨) — 적어도 하나는 달라야 한다(퇴화 테스트 방지).
    a_texts = [i.question_text for i in a]
    b_texts = [i.question_text for i in b]
    assert a_texts != b_texts


def test_composition_counts() -> None:
    items = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s2")
    assert len(items) == 4 * 5 + 5
    assert sum(1 for i in items if i.defect_class is None) == 5
    from collections import Counter

    counts = Counter(i.defect_class for i in items if i.defect_class is not None)
    assert all(counts[k] == 5 for k in DEFECT_CLASSES)


def test_slugs_are_unique() -> None:
    items = build_defect_seeded_residue_set(n_per_class=5, n_clean=5, seed="s3")
    slugs = [i.slug for i in items]
    assert len(slugs) == len(set(slugs))


def test_pool_exhaustion_is_explicit_valueerror() -> None:
    # 밴드 A+B 풀은 20건뿐 — 결함류당 21건 요청은 조용한 축소가 아니라 ValueError.
    with pytest.raises(ValueError, match="초과"):
        build_defect_seeded_residue_set(n_per_class=21, n_clean=1, seed="s4")
    with pytest.raises(ValueError, match="초과"):
        build_defect_seeded_residue_set(n_per_class=1, n_clean=21, seed="s4")


# ──────────────────────────────────────────────────────────────────────────
# 발문만 변조 — DSL·정답·해설은 불변(계산 축은 항상 참이어야 한다)
# ──────────────────────────────────────────────────────────────────────────


def test_defective_items_mutate_question_only() -> None:
    items = build_defect_seeded_residue_set(n_per_class=5, n_clean=0, seed="s5")
    for item in items:
        assert item.defect_class is not None
        # 계산 축(conditions·answer)은 항상 참으로 남는다 — 전수 열거가 그대로 통과해야 한다.
        verdict = verify_finite_probability(item.conditions, item.answer)
        assert verdict.state == "pass", f"{item.slug}: {verdict.reason}"


def test_clean_items_are_unmutated_and_pass_gate() -> None:
    items = build_defect_seeded_residue_set(n_per_class=0, n_clean=10, seed="s6")
    assert len(items) == 10
    for item in items:
        assert item.defect_class is None
        verdict = verify_finite_probability(item.conditions, item.answer)
        assert verdict.state == "pass"


def test_defective_items_keep_parseable_original_conditions() -> None:
    """결함 문항의 `conditions`는 변조되지 않으므로 항상 파싱·전수 열거가 가능하다."""
    items = build_defect_seeded_residue_set(n_per_class=5, n_clean=0, seed="s7")
    for item in items:
        model = parse_finite_model(item.conditions)
        result = enumerate_model(model)
        assert result.total > 0


# ──────────────────────────────────────────────────────────────────────────
# 변조 함수 단위 — 앵커가 실제로 발문을 바꾸는지
# ──────────────────────────────────────────────────────────────────────────

_DICE_QUESTION = (
    "서로 구별되는 두 개의 주사위를 동시에 던진다. 각 주사위의 여섯 눈이 나올 "
    "가능성이 모두 같을 때, 나온 두 눈의 수의 합이 7일 확률을 기약분수로 나타내시오."
)
_COIN_QUESTION = (
    "한 개의 동전을 4번 던진다. 매번 앞면과 뒷면이 나올 가능성이 같을 때, "
    "앞면이 정확히 2번 나올 확률을 기약분수로 나타내시오."
)


@pytest.mark.parametrize("question", [_DICE_QUESTION, _COIN_QUESTION])
def test_condition_missing_mutation_changes_text(question: str) -> None:
    mutated = _mutate_condition_missing(question)
    assert mutated != question


@pytest.mark.parametrize("question", [_DICE_QUESTION, _COIN_QUESTION])
def test_ambiguous_statement_mutation_changes_text(question: str) -> None:
    mutated = _mutate_ambiguous_statement(question)
    assert mutated != question


@pytest.mark.parametrize("question", [_DICE_QUESTION, _COIN_QUESTION])
def test_equal_probability_unstated_mutation_changes_text(question: str) -> None:
    mutated = _mutate_equal_probability_unstated(question)
    assert mutated != question


@pytest.mark.parametrize("question", [_DICE_QUESTION, _COIN_QUESTION])
def test_multiple_answers_mutation_changes_text(question: str) -> None:
    mutated = _mutate_multiple_answers(question)
    assert mutated != question


def test_condition_missing_removes_count_phrase() -> None:
    assert "두 개의 주사위를" not in _mutate_condition_missing(_DICE_QUESTION)
    assert "4번 던진다" not in _mutate_condition_missing(_COIN_QUESTION)


def test_equal_probability_unstated_removes_clause() -> None:
    assert "가능성이 모두 같을 때" not in _mutate_equal_probability_unstated(_DICE_QUESTION)
    assert "가능성이 같을 때" not in _mutate_equal_probability_unstated(_COIN_QUESTION)


def test_multiple_answers_adds_or_branch_without_changing_answer_field() -> None:
    mutated_dice = _mutate_multiple_answers(_DICE_QUESTION)
    assert "이거나" in mutated_dice
    mutated_coin = _mutate_multiple_answers(_COIN_QUESTION)
    assert "또는" in mutated_coin


def test_mutation_anchor_mismatch_raises_valueerror() -> None:
    # 앵커가 전혀 없는 문장은 4종 결함 시더 함수 모두 무변조(원문 반환) — 시더는 이를
    # ValueError로 승격한다는 계약을 build_defect_seeded_residue_set 경로에서 확인한다.
    with pytest.raises(ValueError):
        from whymath_backend.l3.finite_probability_defect_seeder import _mutate_or_raise

        _mutate_or_raise("multiple_answers", "이 문장에는 확률 관련 앵커가 없다.")


def test_seeded_item_is_frozen_dataclass() -> None:
    items = build_defect_seeded_residue_set(n_per_class=0, n_clean=1, seed="s8")
    item = items[0]
    assert isinstance(item, SeededResidueItem)
    with pytest.raises(AttributeError):
        item.slug = "other"  # type: ignore[misc]
