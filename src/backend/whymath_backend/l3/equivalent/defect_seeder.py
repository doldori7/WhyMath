"""결함 주입기 — 초인간 검증 기준 §3 *강등전*의 시험지 제조 (순수·결정론·LLM 0).

설계 정본: `docs/standards/superhuman_verification_standard.md` §3 "결함 주입 강등전".
핵심 아이디어(mutation testing): 기계 검증 스택을 채점할 정답지(GT)를 인간 라벨에
의존하면 순환이다. 대신 **결함을 우리가 의도적으로 주입**한다 — 어디에 무슨 결함이
있는지 우리가 100% 알므로, 인간 라벨 0건으로 완전한 정답지가 성립한다.

무결함 후보는 기존 결정론 스켈레톤 생성기(`SkeletonEquivalentProblemGenerator`)가
만든다 — 근을 코드가 고르고 방정식을 역산하므로 **구성상 참**이며 수용 게이트를
통과한다(테스트가 전수 확인). 결함 후보는 그 무결함 후보에 아래 6종을 결정론
변조(seed 고정)해 만든다:

  ① `answer_error`            정답+1 — 진답(선택된 근)보다 크므로 근이 될 수 없음이
                              증명됨(이차방정식 근은 2개뿐). Tier1 검출 예상.
  ② `explanation_slip`        해설에 거짓 수치 등식 삽입("3 * 4 = 11"). 위생 게이트
                              검출 예상(`default_seed_validator` 실측 확인).
  ③ `condition_mismatch`      조건식 좌변에 "+1" — f(답)=0+1=1≠0 이라 답이 더는 해가
                              아님이 증명됨. Tier1 검출 예상.
  ④ `standard_tag_error`      성취기준 코드 끝자리 변조 — 동등성 성취기준 성분 0
                              → 점수 0.60(검수필요) → 차단 예상.
  ⑤ `distractor_misattribution` 객관식 오답 선지의 오개념 id 전량 교체 — Jaccard 0
                              → 점수 0.70(검수필요) → 차단 예상.
  ⑥ `statement_mismatch`      발문 표시 수식의 숫자 변조(검산 조건은 원본 유지) —
                              **현 스택 미검출이 예상되는 정직한 공백**. 발문-수식
                              교차 검사(`retag.StatementConsistencyAuditor`)의 존재
                              이유이며, 강등전 baseline에 눈가림 없이 공개한다.

평가 스펙(`EquivalenceSpec`)은 *변조 전* 후보에서 역구성한다 — 스펙이 곧 "원 의도"
이고, 태그류 변조(④⑤)는 그 의도와의 불일치로 검출된다. 무결함 후보는 스펙과 완전
일치라 동등성 점수 1.0이 보장된다.

7계층: L3 지역(생성·게이트와 동일 층). 같은 패키지(skeleton_generator·acceptance·
generator)와 schema만 import한다. DB 0·네트워크 0·LLM 0.
"""

from __future__ import annotations

import random
import re
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.skeleton_generator import (
    GeneratorVariant,
    SkeletonEquivalentProblemGenerator,
)
from whymath_backend.schema.problem import Problem

__all__ = [
    "DEFECT_CLASSES",
    "DefectClass",
    "SeededItem",
    "build_defect_seeded_set",
]

# 결함 6종 — superhuman_verification_standard.md §3.1과 1:1. 순서는 순환 배정 순서.
DefectClass = Literal[
    "answer_error",
    "explanation_slip",
    "condition_mismatch",
    "standard_tag_error",
    "distractor_misattribution",
    "statement_mismatch",
]
DEFECT_CLASSES: tuple[DefectClass, ...] = (
    "answer_error",
    "explanation_slip",
    "condition_mismatch",
    "standard_tag_error",
    "distractor_misattribution",
    "statement_mismatch",
)

# 객관식 결함(⑤)만 객관식 후보가 필요 — 나머지는 단답형 후보에 주입한다.
_MC_ONLY_CLASSES: frozenset[str] = frozenset({"distractor_misattribution"})

# 강등전 셋 생성용 성취기준 코드 — 스켈레톤 풀(이차방정식 근)의 실제 단원 코드.
_GEN_STANDARD_CODE = "[10공수1-02-02]"

# 객관식 생성기에 주입하는 합성 오개념 코드(op키→(misconception_id, op_code)) —
# 강등전 셋은 L4 카탈로그와 무관한 자족 시험지라 실제 id를 오염시키지 않는다.
_SYNTH_DISTRACTOR_CODES: dict[str, tuple[str, str]] = {
    "opposite_root": ("wm-test-opposite-root", "opposite_root"),
    "sign_flip": ("wm-test-sign-flip", "sign_flip"),
}

# ⑤가 바꿔치는 무관 오개념 id — 스펙(원 의도)과 교집합 0이 되도록 합성 id 사용.
_UNRELATED_MISCONCEPTION_ID = "wm-test-unrelated-misconception"

# ②가 삽입하는 거짓 수치 등식 — default_seed_validator가 arithmetic 신호로 검출함을
# 실측 확인한 형식(sympy: 12 != 11).
_FALSE_EQUALITY_SLIP = " 검산하면 3 * 4 = 11 이다."


class SeededItem(BaseModel):
    """강등전 시험지 1문 — 후보 + 평가 스펙 + 정답지(defect_class·변조 기록).

    `defect_class=None`이면 무결함(정상) 문항이다. `mutation_note`는 무엇을 어떻게
    변조했는지의 사람 가독 기록(정답지·감사용) — 블라인드 셋에는 싣지 않는다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: CandidateProblem = Field(description="시험 문항 번들(변조 후).")
    spec: EquivalenceSpec = Field(description="평가 스펙 — 변조 *전* 후보에서 역구성한 원 의도.")
    defect_class: DefectClass | None = Field(
        default=None, description="주입된 결함 유형(None=무결함)."
    )
    mutation_note: str = Field(default="", description="변조 내용 기록(정답지 전용·블라인드 제외).")


def _spec_from(candidate: CandidateProblem) -> EquivalenceSpec:
    """변조 전 후보에서 평가 스펙(원 의도)을 역구성 — 무결함이면 점수 1.0이 보장된다."""
    problem = candidate.problem
    return EquivalenceSpec(
        achievement_standard_codes=frozenset(problem.achievement_standard_codes),
        target_misconception_ids=frozenset(
            entry.misconception_id for entry in (problem.distractor_map or [])
        ),
        difficulty_overall=(
            problem.difficulty_overall if problem.difficulty_overall is not None else 2.5
        ),
        answer_format=problem.answer_format,
    )


def _rebuild(
    candidate: CandidateProblem,
    *,
    problem_updates: dict[str, object] | None = None,
    conditions: str | list[str] | None = None,
    answer_map: dict[str, str] | None = None,
) -> CandidateProblem:
    """frozen 후보를 변조해 재구성 — dump→수정→re-validate(스키마 불변식 유지 확인)."""
    data = candidate.model_dump()
    if problem_updates:
        problem_data = candidate.problem.model_dump()
        problem_data.update(problem_updates)
        data["problem"] = Problem.model_validate(problem_data).model_dump()
    if conditions is not None:
        data["conditions"] = conditions
    if answer_map is not None:
        data["answer_map"] = answer_map
    return CandidateProblem.model_validate(data)


def _shift_answer(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """① answer_error — 정답+1(유리수 정확값). 진답보다 크므로 근일 수 없음이 증명됨."""
    old = candidate.problem.answer or "0"
    shifted = Fraction(old) + 1
    new = (
        str(shifted.numerator)
        if shifted.denominator == 1
        else f"{shifted.numerator}/{shifted.denominator}"
    )
    new_map = {key: new for key in candidate.answer_map}
    rebuilt = _rebuild(candidate, problem_updates={"answer": new}, answer_map=new_map)
    return rebuilt, f"answer {old!r} → {new!r} (+1)"


def _slip_explanation(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """② explanation_slip — 해설 끝에 거짓 수치 등식을 삽입."""
    old = candidate.problem.answer_explanation or ""
    rebuilt = _rebuild(
        candidate, problem_updates={"answer_explanation": old + _FALSE_EQUALITY_SLIP}
    )
    return rebuilt, f"해설에 거짓 등식 삽입: {_FALSE_EQUALITY_SLIP.strip()!r}"


def _mismatch_condition(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """③ condition_mismatch — 조건식 좌변 +1. f(답)=1≠0 이라 답이 더는 해가 아님."""
    cond = candidate.conditions
    if not isinstance(cond, str) or " = " not in cond:  # pragma: no cover — 스켈레톤 형식 방어
        raise ValueError(f"condition_mismatch 주입 불가 형식: {cond!r}")
    mutated = cond.replace(" = ", " + 1 = ", 1)
    rebuilt = _rebuild(candidate, conditions=mutated)
    return rebuilt, f"conditions {cond!r} → {mutated!r}"


def _corrupt_standard_code(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """④ standard_tag_error — 성취기준 코드의 마지막 숫자를 변조(형식 보존)."""
    codes = list(candidate.problem.achievement_standard_codes)
    if not codes:  # pragma: no cover — 생성 스펙이 코드를 항상 실음(방어)
        raise ValueError("standard_tag_error 주입 불가 — 성취기준 코드 없음")
    original = codes[0]
    digits = list(re.finditer(r"\d", original))
    if not digits:  # pragma: no cover — 코드 형식 방어
        raise ValueError(f"standard_tag_error 주입 불가 형식: {original!r}")
    last = digits[-1]
    new_digit = str((int(last.group()) + 1) % 10)
    corrupted = original[: last.start()] + new_digit + original[last.end() :]
    codes[0] = corrupted
    rebuilt = _rebuild(candidate, problem_updates={"achievement_standard_codes": codes})
    return rebuilt, f"성취기준 {original!r} → {corrupted!r}"


def _misattribute_distractors(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """⑤ distractor_misattribution — 오답 선지의 오개념 id를 전량 무관 id로 교체."""
    entries = candidate.problem.distractor_map or []
    if not entries:  # pragma: no cover — MC 전용 배정이 보장(방어)
        raise ValueError("distractor_misattribution 주입 불가 — distractor_map 없음")
    mutated = [
        entry.model_dump() | {"misconception_id": _UNRELATED_MISCONCEPTION_ID} for entry in entries
    ]
    rebuilt = _rebuild(candidate, problem_updates={"distractor_map": mutated})
    return rebuilt, f"오답 선지 오개념 {len(entries)}건 전량 → {_UNRELATED_MISCONCEPTION_ID!r}"


def _mismatch_statement(candidate: CandidateProblem) -> tuple[CandidateProblem, str]:
    """⑥ statement_mismatch — 발문 표시 수식의 마지막 숫자 변조(검산 조건은 원본 유지).

    학생이 읽는 방정식과 검증기가 검산하는 방정식이 달라지는 결함 — 현 스택에는 이를
    교차 검사하는 컴포넌트가 없어 미검출이 예상된다(정직한 공백·retag 감사기의 대상).
    """
    text = candidate.problem.question_text or ""
    anchor = text.rfind("= 0")
    if anchor < 0:  # pragma: no cover — 단답형 발문은 항상 "= 0" 포함(방어)
        raise ValueError(f"statement_mismatch 주입 불가 발문: {text!r}")
    digits = list(re.finditer(r"\d", text[:anchor]))
    if not digits:  # pragma: no cover — 계수 숫자 항상 존재(방어)
        raise ValueError(f"statement_mismatch 주입 불가 발문: {text!r}")
    last = digits[-1]
    new_digit = str((int(last.group()) + 1) % 10)
    mutated = text[: last.start()] + new_digit + text[last.end() :]
    rebuilt = _rebuild(candidate, problem_updates={"question_text": mutated})
    return rebuilt, f"발문 수식 숫자 변조: …{text[max(0, last.start() - 8) : anchor + 3]!r}"


# 결함별 주입 함수 디스패치 — 전부 (변조 후보, 기록) 반환.
_MUTATORS = {
    "answer_error": _shift_answer,
    "explanation_slip": _slip_explanation,
    "condition_mismatch": _mismatch_condition,
    "standard_tag_error": _corrupt_standard_code,
    "distractor_misattribution": _misattribute_distractors,
    "statement_mismatch": _mismatch_statement,
}


def build_defect_seeded_set(
    *,
    n_defective: int = 100,
    n_clean: int = 100,
    seed: int = 20260708,
) -> list[SeededItem]:
    """강등전 시험지 셋 — 결함 n_defective + 무결함 n_clean, seed 고정 결정론.

    결함은 6종을 순환 배정한다(클래스별 균형). ⑤(객관식 전용)는 객관식 생성기에서,
    나머지는 단답형 생성기에서 후보를 뽑는다. 무결함도 두 형식을 섞는다(형식만으로
    결함 여부를 추측할 수 없게 — 객관식 무결함이 존재해야 블라인드가 성립).
    최종 순서는 seed 셔플(블라인드 제출 순서) — 같은 seed면 바이트 동일 셋이다.

    풀 소진 시 정직하게 ValueError(조용한 부분 셋 반환 금지).
    """
    rng = random.Random(seed)
    generation_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_GEN_STANDARD_CODE}),
        difficulty_overall=2.5,
    )

    def _make_generator(variant: GeneratorVariant) -> SkeletonEquivalentProblemGenerator:
        if variant == "multiple_choice":
            return SkeletonEquivalentProblemGenerator(
                variant="multiple_choice",
                distractor_codes=_SYNTH_DISTRACTOR_CODES,
                slug_prefix="wm-demote-mc",
            )
        return SkeletonEquivalentProblemGenerator(
            variant="short_answer", slug_prefix="wm-demote-sa"
        )

    sa_gen = _make_generator("short_answer")
    mc_gen = _make_generator("multiple_choice")

    def _next_clean(variant: GeneratorVariant) -> CandidateProblem:
        generator = mc_gen if variant == "multiple_choice" else sa_gen
        candidate = generator.generate(generation_spec)
        if candidate is None:
            raise ValueError(
                f"스켈레톤 풀 소진({variant}) — n_defective/n_clean을 줄이거나 풀을 확장하라."
            )
        return candidate

    items: list[SeededItem] = []

    # ① 결함 문항 — 6종 순환 배정(클래스별 균형·결정론).
    for index in range(n_defective):
        defect: DefectClass = DEFECT_CLASSES[index % len(DEFECT_CLASSES)]
        variant: GeneratorVariant = (
            "multiple_choice" if defect in _MC_ONLY_CLASSES else "short_answer"
        )
        clean = _next_clean(variant)
        spec = _spec_from(clean)  # 스펙 = 변조 *전* 원 의도
        mutated, note = _MUTATORS[defect](clean)
        items.append(
            SeededItem(candidate=mutated, spec=spec, defect_class=defect, mutation_note=note)
        )

    # ② 무결함 문항 — 단답형·객관식 교대(형식으로 결함 여부 추측 불가).
    for index in range(n_clean):
        variant = "multiple_choice" if index % 2 else "short_answer"
        clean = _next_clean(variant)
        items.append(SeededItem(candidate=clean, spec=_spec_from(clean)))

    rng.shuffle(items)  # 블라인드 제출 순서(seed 고정 결정론)
    return items
