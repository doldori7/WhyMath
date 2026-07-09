"""수능 시그니처 결정론 태거(S2-06) 단위테스트 — 규칙 3종·비날조·멱등·실코퍼스 통계 봉인.

핵심 봉인: ① T1/T2/T3 양성·음성 ② 규칙 미해당 → 빈 배열(비날조 — 시그니처를 채우려고 문항을
각색하지 않는다) ③ 멱등(2회 적용 동일·무변경 시 원본 객체 그대로) ④ 정렬 결정성(enum 값 사전순)
⑤ 시그니처 외 타 필드 무변경 ⑥ **실코퍼스 통계**: generated_v0는 `wm-indseq` 접두 외 전건 태깅
0 + wm-indseq 전건 2종 태깅, rephrased_v0는 전건 0(기존 1,073문 비날조 유지). LLM·DB 0(순수).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whymath_backend.l1.problem_bank.populate import (
    ProblemBankRecord,
    load_problem_bank_records,
)
from whymath_backend.l1.problem_bank.signature_tagger import (
    apply_signatures,
    derive_signatures,
)
from whymath_backend.schema.enums import SignaturePattern
from whymath_backend.schema.problem import Problem


def _problem(**overrides: object) -> Problem:
    """최소 유효 Problem 픽스처 — 자체생성·필수 필드만 채우고 overrides로 케이스 구성."""
    base: dict[str, object] = {
        "source_type": "자체생성",
        "curriculum_version": "2022_REVISION",
        "valid_from_year": 2022,
        "subject": "공통",
        "unit_codes": ["IND-SEQ"],
        "question_format": "단답형",
        "question_text": "첫째항이 3, 공차가 2인 등차수열의 제7항을 구하시오.",
        "answer": "15",
    }
    base.update(overrides)
    return Problem.model_validate(base)


# 귀납 밴드 발문 고정 표기(생성기 방출 형식) — T1+T2 동시 양성.
_INDUCTIVE_QUESTION = (
    "수열 {aₙ}이 다음 조건을 만족시킨다.\n"
    "(가) a₁ = 3\n"
    "(나) aₙ₊₁ = aₙ + 2 (n ≥ 1)\n"
    "a₇의 값을 구하시오."
)


class TestConditionList:
    def test_positive(self) -> None:
        # T1 양성 — 플래그 + (가)(나) 동시 존재.
        problem = _problem(
            has_condition_list=True,
            question_text="다음 조건을 만족시킨다.\n(가) 첫째 조건\n(나) 둘째 조건\n값을 구하시오.",
        )
        assert derive_signatures(problem) == [SignaturePattern.CONDITION_LIST]

    def test_negative_flag_off(self) -> None:
        # 발문에 (가)(나)가 있어도 has_condition_list=False면 미태깅(플래그·표기 동시 요구).
        problem = _problem(
            has_condition_list=False,
            question_text="(가) 조건과 (나) 조건이 있는 발문.",
        )
        assert derive_signatures(problem) == []

    def test_negative_single_marker(self) -> None:
        # (가)만 있으면 조건 *나열*이 아니다 — 미태깅.
        problem = _problem(has_condition_list=True, question_text="(가) 조건 하나만 있는 발문.")
        assert derive_signatures(problem) == []


class TestInductiveSequence:
    def test_positive_arith_recurrence(self) -> None:
        # T2 양성 — 등차 점화 고정 표기.
        problem = _problem(has_condition_list=False, question_text="aₙ₊₁ = aₙ + 3 (n ≥ 1)")
        assert derive_signatures(problem) == [SignaturePattern.INDUCTIVE_SEQUENCE]

    def test_positive_geo_recurrence(self) -> None:
        # T2 양성 — 등비 점화 고정 표기.
        problem = _problem(has_condition_list=False, question_text="aₙ₊₁ = 2·aₙ (n ≥ 1)")
        assert derive_signatures(problem) == [SignaturePattern.INDUCTIVE_SEQUENCE]

    def test_negative_general_term(self) -> None:
        # 일반항 발문(점화식 아님)은 미태깅 — 기존 수열 밴드가 여기 해당(비날조).
        problem = _problem(question_text="첫째항이 3, 공차가 2인 등차수열의 제7항을 구하시오.")
        assert derive_signatures(problem) == []

    def test_both_t1_t2_sorted(self) -> None:
        # 귀납 밴드 발문 — T1+T2 동시·enum 값 사전순 정렬(결정성).
        problem = _problem(has_condition_list=True, question_text=_INDUCTIVE_QUESTION)
        assert derive_signatures(problem) == [
            SignaturePattern.CONDITION_LIST,
            SignaturePattern.INDUCTIVE_SEQUENCE,
        ]


class TestCompoundChoices:
    def test_positive(self) -> None:
        # T3 양성 — 객관식 + 선지 전원 ㄱㄴㄷ 조합. 현 코퍼스 0건(후속 밴드용 선치).
        problem = _problem(
            question_format="객관식",
            question_text="옳은 것만을 있는 대로 고른 것은?",
            choices=["ㄱ", "ㄴ", "ㄱ, ㄴ", "ㄱ, ㄴ, ㄷ"],
            answer="ㄱ, ㄴ",
        )
        assert derive_signatures(problem) == [SignaturePattern.COMPOUND_CHOICES]

    def test_negative_numeric_choices(self) -> None:
        # 숫자 선지 객관식은 합답형이 아니다 — 미태깅.
        problem = _problem(
            question_format="객관식",
            choices=["1", "2", "3", "4"],
            answer="2",
        )
        assert derive_signatures(problem) == []

    def test_negative_partial_compound(self) -> None:
        # 선지 일부만 ㄱㄴㄷ면 미태깅(전원 요구).
        problem = _problem(
            question_format="객관식",
            choices=["ㄱ", "ㄴ", "3", "ㄱ, ㄴ"],
            answer="ㄱ",
        )
        assert derive_signatures(problem) == []

    def test_negative_short_answer_format(self) -> None:
        # 단답형이면 선지가 ㄱㄴㄷ 꼴이어도 미태깅(객관식 요구).
        problem = _problem(question_format="단답형", choices=None)
        assert derive_signatures(problem) == []


class TestApplySignatures:
    def test_no_match_returns_same_object(self) -> None:
        # 비날조 + 바이트 불변의 구조 보장 — 규칙 미해당·빈 배열 유지면 **원본 객체 그대로**.
        problem = _problem()
        assert apply_signatures(problem) is problem

    def test_idempotent(self) -> None:
        # 멱등 — 1회 적용 후 재적용은 동일 객체(2회 결과 동일).
        problem = _problem(has_condition_list=True, question_text=_INDUCTIVE_QUESTION)
        once = apply_signatures(problem)
        assert once is not problem
        assert apply_signatures(once) is once

    def test_only_signature_field_changes(self) -> None:
        # 시그니처 외 타 필드 무변경 — model_dump 비교(persona_fit·exam_type 미조작 포함).
        problem = _problem(has_condition_list=True, question_text=_INDUCTIVE_QUESTION)
        tagged = apply_signatures(problem)
        before = problem.model_dump(mode="json")
        after = tagged.model_dump(mode="json")
        assert before.pop("signature_patterns") == []
        assert after.pop("signature_patterns") == ["CONDITION_LIST", "INDUCTIVE_SEQUENCE"]
        assert before == after


# ──────────────────────────────────────────────────────────────────────
# 실코퍼스 통계 봉인 — 기존 문항 전건 태깅 0(비날조) + 귀납 밴드 전건 2종 태깅.
# ──────────────────────────────────────────────────────────────────────
def _corpus_records(dirname: str) -> list[ProblemBankRecord]:
    corpus = Path(__file__).resolve().parents[4] / "data" / "corpus" / dirname / "problems.jsonl"
    if not corpus.exists():
        pytest.skip(f"코퍼스 미존재(data/corpus/{dirname}/problems.jsonl)")
    return load_problem_bank_records(corpus)


def test_generated_corpus_signature_stats() -> None:
    # generated_v0 — wm-indseq 접두 외 전건 유도 0(기존 문항 비날조 유지) + wm-indseq 밴드는
    # 전건 [CONDITION_LIST, INDUCTIVE_SEQUENCE] 유도·저장 필드와 일치(태거=저장 정합).
    records = _corpus_records("problem_bank_generated_v0")
    indseq = [r for r in records if r.slug.startswith("wm-indseq-")]
    others = [r for r in records if not r.slug.startswith("wm-indseq-")]
    assert len(indseq) == 30  # S2-06 신설 밴드 볼륨
    for record in others:
        assert derive_signatures(record.problem) == [], f"{record.slug} 기존 문항 오태깅"
        assert record.problem.signature_patterns == []
    for record in indseq:
        assert derive_signatures(record.problem) == [
            SignaturePattern.CONDITION_LIST,
            SignaturePattern.INDUCTIVE_SEQUENCE,
        ], f"{record.slug} 귀납 밴드 태깅 누락"
        assert record.problem.signature_patterns == ["CONDITION_LIST", "INDUCTIVE_SEQUENCE"]


def test_rephrased_corpus_signature_stats() -> None:
    # rephrased_v0(불변 코퍼스) — 전건 유도 0·저장 필드도 빈 배열(비날조·무변경).
    for record in _corpus_records("problem_bank_rephrased_v0"):
        assert derive_signatures(record.problem) == [], f"{record.slug} rephrase 문항 오태깅"
        assert record.problem.signature_patterns == []
