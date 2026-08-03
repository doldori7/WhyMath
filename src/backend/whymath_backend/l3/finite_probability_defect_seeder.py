"""결함 주입기 — 잔여 축(발문↔형식모델) 강등전 시험지 제조(순수·결정론·LLM 0).

`l3/equivalent/defect_seeder.py`의 확률 도메인 형제. 설계 정본은 없음(S4-16 신설)이나
구조·주석 스타일·`Literal` 어휘·`__all__` 구성을 그 파일과 동형으로 맞춘다.

핵심 아이디어(mutation testing)는 `defect_seeder.py`와 같다 — 결함을 우리가 의도적으로
주입하므로 어디에 무슨 결함이 있는지 100% 안다. 다만 겨냥하는 축이 다르다: 그쪽 6종은
"계산이 틀림"(정답·조건식·태그 변조)을 겨냥하고, 여기 4종은 **"발문↔형식모델(DSL)
불일치"**만 겨냥한다. `conditions`(DSL)·`answer`·`answer_explanation`은 변조하지 않고
원본 그대로 둔다 — 그래야 기계 축(`l3/finite_probability` 전수 열거)은 항상 pass하고,
오직 잔여 축(`l3/cross_verify.CrossVerifier` 독립 다관점 LLM 교차검증)만 이 결함을
잡아야 하는 구도가 성립한다. 두 축을 한 문항에 섞지 않는 것이 이 시더의 존재 이유다
(`harness/defect_detection_eval.py` = 계산 축, `harness/residue_gate_demotion_battle.py`
= 서술 축 — 서로 다른 강등전).

무결함 후보는 기존 결정론 스켈레톤 생성기(`FiniteProbabilitySkeletonGenerator`)가
만든다(재구현 금지) — 밴드 A(dice-sum-prob)·밴드 B(coin-heads-prob)만 쓴다. 두 밴드
모두 발문에 "두 개의"/"N번" 같은 명시적 개수 표현과 "가능성이 모두 같을 때" 등확률
절을 갖고 있어 변조 앵커가 명확하다(밴드 C·D는 이번 스코프 밖).

결함 4종:
  ① `condition_missing`           표본공간 크기(개수) 명시를 발문에서 제거.
  ② `ambiguous_statement`         정확한 사건 표현을 모호한 어림 표현으로 흐림.
  ③ `equal_probability_unstated`  "가능성이 같다" 절 제거(등확률 미명시).
  ④ `multiple_answers`            사건에 암묵적 or-분기 추가(정답은 단일값 그대로 두어
                                   발문과 정답 사이에 복수 정답 결함이 생기게 함).

변조 앵커가 실제 발문 문자열과 맞지 않으면(치환 후 텍스트가 원문과 동일하면) 조용히
넘기지 않고 `ValueError`로 즉시 실패한다(침묵 실패 금지) — 앵커 불일치는 "그 스켈레톤은
이 결함류의 시드 후보가 아니다"라는 신호이므로 시더가 걸러야 한다.

7계층: L3 지역. `l3/equivalent`(스켈레톤 생성기·CandidateProblem)만 import. DB 0·
네트워크 0·LLM 0.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.finite_probability_skeleton_generator import (
    FiniteBand,
    FiniteProbabilitySkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem

__all__ = [
    "DEFECT_CLASSES",
    "DefectClass",
    "SeededResidueItem",
    "build_defect_seeded_residue_set",
]

# 결함 4종 — 잔여 축(발문↔형식모델) 전용. 순서는 순환 배정 순서(defect_seeder.py 관례 미러).
DefectClass = Literal[
    "condition_missing",
    "ambiguous_statement",
    "equal_probability_unstated",
    "multiple_answers",
]
DEFECT_CLASSES: tuple[DefectClass, ...] = (
    "condition_missing",
    "ambiguous_statement",
    "equal_probability_unstated",
    "multiple_answers",
)

# 변조 앵커가 확보된 밴드만 — 밴드 C(주머니)·D(경우의 수)는 발문 형태가 달라 이번 스코프 밖.
_ANCHORED_BANDS: tuple[FiniteBand, ...] = ("dice-sum-prob", "coin-heads-prob")

# 강등전 시험지의 생성자 서명 — `CrossVerifier.signature`(실 provider 모델 id)와 절대 같을
# 수 없는 고정 문자열이면 된다(생성자≠검증자 강제·`IndependenceError` 방지).
_AUTHORED_BY = "harness:residue_demotion_battle"

# 밴드 A+B 후보 조립용 형식적 최소 스펙 — 결함류와 무관(난이도만 필수 필드).
_GEN_SPEC = EquivalenceSpec(difficulty_overall=2.5)


@dataclass(frozen=True, slots=True)
class SeededResidueItem:
    """강등전 시험지 1문 — 발문 변조(가능) + 원본 DSL·정답·해설(불변) + 정답지(defect_class).

    `defect_class=None`이면 무결함(정상) 문항이다. `conditions`·`answer`·`answer_explanation`
    은 결함류와 무관하게 항상 무결함 스켈레톤의 원본 값이다 — 변조 대상은 `question_text`뿐.
    """

    slug: str
    defect_class: DefectClass | None
    question_text: str
    answer: str
    answer_explanation: str
    conditions: str
    answer_kind: Literal["finite_probability", "finite_count"]
    authored_by: str = _AUTHORED_BY


# ──────────────────────────────────────────────────────────────────────────
# 변조 함수 4개 — 정규식/문자열 치환. 결정론·LLM 0. 앵커 불일치는 무변조(원문 그대로) 반환하고
# 판정은 `_mutate_or_raise`가 한다(개별 함수가 예외를 던지지 않음 — 조합 단순화).
# ──────────────────────────────────────────────────────────────────────────


def _mutate_condition_missing(question: str) -> str:
    """① 표본공간 개수 명시를 제거 — 밴드 A "두 개의 주사위를" → "주사위를",
    밴드 B "동전을 {N}번 던진다" → "동전을 던진다"(숫자+"번" 통째 제거)."""
    q = question.replace("두 개의 주사위를", "주사위를")
    q = re.sub(r"동전을\s*\d+번\s*던진다", "동전을 던진다", q)
    return q


def _mutate_ambiguous_statement(question: str) -> str:
    """② 정확한 사건 표현을 어림 표현으로 흐림 — "합이 {N}일 확률" → "합이 {N} 근처일 확률",
    "정확히 {N}번 나올 확률" → "{N}번 정도 나올 확률"(정확히 삭제 + 정도 삽입)."""
    q = re.sub(r"합이\s*(\d+)일\s*확률", r"합이 \1 근처일 확률", question)
    q = re.sub(r"정확히\s*(\d+)번\s*나올\s*확률", r"\1번 정도 나올 확률", q)
    return q


def _mutate_equal_probability_unstated(question: str) -> str:
    """③ 등확률 절 제거 — 밴드 A "각 주사위의 여섯 눈이 나올 가능성이 모두 같을 때, " 삭제,
    밴드 B "매번 앞면과 뒷면이 나올 가능성이 같을 때, " 삭제."""
    q = question.replace("각 주사위의 여섯 눈이 나올 가능성이 모두 같을 때, ", "")
    q = q.replace("매번 앞면과 뒷면이 나올 가능성이 같을 때, ", "")
    return q


def _mutate_multiple_answers(question: str) -> str:
    """④ 사건에 암묵적 or-분기 추가(발문은 두 값 중 하나를 묻지만 conditions/answer는 원
    target 1개만 계산 — "복수 정답"류 결함). 경계값은 인접 값으로 교체(범위 이탈 방지)."""
    m = re.search(r"합이\s*(\d+)일\s*확률", question)
    if m:
        target = int(m.group(1))
        other = target - 1 if target >= 12 else target + 1
        return question.replace(f"합이 {target}일 확률", f"합이 {target}이거나 {other}일 확률")
    m = re.search(r"정확히\s*(\d+)번\s*나올\s*확률", question)
    if m:
        heads = int(m.group(1))
        # trials 상한을 모르니(heads만 텍스트에 있음) heads>=1이면 heads-1, 아니면 heads+1로
        # 안전하게 둔다 — 실제 trials 초과 여부는 이 변조가 검증할 사항이 아니다(발문 표현의
        # 문제이지 정합성 검산이 아님).
        other = heads - 1 if heads >= 1 else heads + 1
        return question.replace(
            f"정확히 {heads}번 나올 확률", f"{heads}번 또는 {other}번 나올 확률"
        )
    return question  # 앵커 없으면 무변조(호출자 _mutate_or_raise가 ValueError로 걸러낸다)


_MUTATORS: dict[DefectClass, Callable[[str], str]] = {
    "condition_missing": _mutate_condition_missing,
    "ambiguous_statement": _mutate_ambiguous_statement,
    "equal_probability_unstated": _mutate_equal_probability_unstated,
    "multiple_answers": _mutate_multiple_answers,
}


def _mutate_or_raise(defect: DefectClass, question: str) -> str:
    """변조 적용 + 앵커 불일치 검출. 치환 후 원문과 동일하면 침묵하지 않고 즉시 실패한다."""
    mutated = _MUTATORS[defect](question)
    if mutated == question:
        raise ValueError(f"{defect} 변조 앵커 불일치 — 발문에 기대 표현이 없음: {question!r}")
    return mutated


# ──────────────────────────────────────────────────────────────────────────
# 무결함 후보 풀 — 밴드 A+B, 결정론 순서(재구현 금지·기존 생성기 그대로 소비).
# ──────────────────────────────────────────────────────────────────────────


def _collect_pool() -> tuple[CandidateProblem, ...]:
    """밴드 A(dice-sum-prob)+B(coin-heads-prob) 무결함 후보 풀 — 생성기 소진까지 전량 수집."""
    pool: list[CandidateProblem] = []
    for band in _ANCHORED_BANDS:
        generator = FiniteProbabilitySkeletonGenerator(band=band, slug_prefix=f"wm-residue-{band}")
        while True:
            candidate = generator.generate(_GEN_SPEC)
            if candidate is None:
                break
            pool.append(candidate)
    return tuple(pool)


def _select_indices(pool_size: int, n: int, *, seed: str, tag: str) -> list[int]:
    """결정론 표본 선택 — `sha256(seed:tag:index)` 정렬로 앞 n개(풀 초과는 ValueError).

    태그(결함류 이름 또는 "clean")별로 *독립* 선택이다 — 다른 태그의 선택과 풀을 공유하지
    않고 매번 전체 풀에서 새로 뽑는다(순환 재사용이 아니라 "각각 뽑는다"). 풀 크기 초과
    요청은 조용한 부분 셋으로 축소하지 않고 명확히 거부한다.
    """
    if n > pool_size:
        raise ValueError(f"{tag}: 요청 {n}건이 스켈레톤 풀 크기 {pool_size}건을 초과함")
    order = sorted(
        range(pool_size),
        key=lambda index: hashlib.sha256(f"{seed}:{tag}:{index}".encode()).hexdigest(),
    )
    return order[:n]


def build_defect_seeded_residue_set(
    *,
    n_per_class: int = 10,
    n_clean: int = 10,
    seed: str = "S4-16",
) -> list[SeededResidueItem]:
    """강등전 시험지 셋 — 결함류 4종 × n_per_class + 무결함 n_clean, seed 고정 결정론.

    밴드 A+B 스켈레톤 풀(20건)에서 결함류별로 독립 표본을 뽑아 발문만 변조한다.
    `conditions`·`answer`·`answer_explanation`은 항상 원본(무결함) 값 그대로다 — 계산 축은
    이 강등전의 대상이 아니다(`harness/defect_detection_eval.py`가 그 축을 이미 다룬다).

    풀 소진(요청 건수가 풀 크기를 초과) 시 정직하게 `ValueError`(조용한 부분 셋 반환 금지).
    """
    pool = _collect_pool()
    if not pool:  # pragma: no cover — 스켈레톤 생성기가 항상 채움(방어)
        raise ValueError("유한 확률 스켈레톤 풀이 비어 있음 — 밴드 A/B 생성 실패")

    items: list[SeededResidueItem] = []

    for defect in DEFECT_CLASSES:
        indices = _select_indices(len(pool), n_per_class, seed=seed, tag=defect)
        for order, pool_index in enumerate(indices):
            candidate = pool[pool_index]
            problem = candidate.problem
            question = problem.question_text or ""
            conditions = candidate.conditions
            if not isinstance(conditions, str):  # pragma: no cover — 이 생성기는 항상 str
                raise ValueError(f"{problem.slug}: conditions가 단일 문자열이 아님")
            items.append(
                SeededResidueItem(
                    slug=f"residue-battle-{defect}-{order}",
                    defect_class=defect,
                    question_text=_mutate_or_raise(defect, question),
                    answer=problem.answer or "",
                    answer_explanation=problem.answer_explanation or "",
                    conditions=conditions,
                    answer_kind="finite_probability",
                )
            )

    clean_indices = _select_indices(len(pool), n_clean, seed=seed, tag="clean")
    for order, pool_index in enumerate(clean_indices):
        candidate = pool[pool_index]
        problem = candidate.problem
        conditions = candidate.conditions
        if not isinstance(conditions, str):  # pragma: no cover — 이 생성기는 항상 str
            raise ValueError(f"{problem.slug}: conditions가 단일 문자열이 아님")
        items.append(
            SeededResidueItem(
                slug=f"residue-battle-clean-{order}",
                defect_class=None,
                question_text=problem.question_text or "",
                answer=problem.answer or "",
                answer_explanation=problem.answer_explanation or "",
                conditions=conditions,
                answer_kind="finite_probability",
            )
        )

    return items
