"""오개념 crosswalk 승인의 *독립 구조 신호* — kebab 성취기준 역유도 + M-id 대조(순수·결정론).

crosswalk(kebab↔M-id) 매핑 정답성은 *의미 일치* 판단이고, 유일한 의미 신호(임베딩 코사인)는
이미 후보를 *제안*하므로(`crosslink_candidates.py`) 같은 코사인으로 *승인*하면 순환(독립 검증
아님)이다. 이 모듈은 코사인과 **독립**인 구조 신호를 만든다: kebab이 문항 `distractor_map`에
오답 귀인으로 쓰일 때 그 문항의 `achievement_standard_codes`로부터 **kebab의 성취기준을
역유도**하고, 이를 M-id의 `standard_code`와 대조한다. 임베딩·LLM 0·완전 결정론(집합 교집합).

**정직한 경계(핵심)**: 이 신호는 kebab이 문항에 등장할 때만 유도된다(현 34 중 5). 미등장 kebab은
`no_signal`(기계 판정 불가 → 인간 폴백). 또한 *같은 성취기준을 공유하는 다른 오개념*으로의 잘못된
매핑은 `agree`로 통과한다(구조축이 못 잡는 의미 구간 — 인간 검수 존치). 즉 이 게이트는 성취기준을
가로지르는 오매핑을 *거부*할 수 있으나, 같은 성취기준 내 형제 오개념 혼동은 못 잡는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

from whymath_backend.l1.misconception.crosslink_gate import MACHINE_REJECT_EVIDENCE_FLOOR
from whymath_backend.l1.problem_bank.populate import ProblemBankRecord

__all__ = [
    "StandardAgreement",
    "derive_kebab_problem_counts",
    "derive_kebab_standards",
    "machine_rejectable",
    "standard_agreement",
]

# 구조 신호 3판정 — agree(성취기준 겹침)·disagree(겹침 없음)·no_signal(kebab 문항 미등장·판정 불가).
StandardAgreement = Literal["agree", "disagree", "no_signal"]


def derive_kebab_standards(
    records: Sequence[ProblemBankRecord],
) -> dict[str, frozenset[str]]:
    """문항 코퍼스 → {kebab_id: 그 kebab을 오답 귀인으로 쓰는 문항들의 성취기준 합집합}(순수).

    각 문항의 `distractor_map` 오개념 id(kebab)마다 그 문항 `achievement_standard_codes`를 모은다.
    kebab의 성취기준을 *문항 사용*에서 역유도하므로 kebab 카탈로그(성취기준 필드 없음)와 독립이고,
    후보를 제안한 임베딩 코사인과도 독립이다. 결정론(입력 순서 무관·집합).
    """
    out: dict[str, set[str]] = {}
    for record in records:
        problem = record.problem
        stds = [str(s) for s in (problem.achievement_standard_codes or [])]
        if not stds:
            continue
        for entry in problem.distractor_map or []:
            kebab = entry.misconception_id
            if kebab:
                out.setdefault(kebab, set()).update(stds)
    return {k: frozenset(v) for k, v in out.items()}


def standard_agreement(
    kebab_standards: Iterable[str],
    mid_standard: str | None,
) -> StandardAgreement:
    """kebab 역유도 성취기준 집합 vs M-id `standard_code` → 3판정(순수).

    - `no_signal`: kebab 성취기준 신호가 없거나(문항 미등장) M-id에 `standard_code`가 없음 —
      기계 판정 불가(인간 폴백). 절대 disagree로 위장하지 않는다(정직·모르면 모른다).
    - `agree`: M-id 성취기준이 kebab 역유도 집합에 포함.
    - `disagree`: 신호는 있으나 성취기준이 겹치지 않음(성취기준 가로지르는 오매핑 후보).
    """
    kebab_set = {s for s in kebab_standards if s}
    if not kebab_set or not mid_standard:
        return "no_signal"
    return "agree" if mid_standard in kebab_set else "disagree"


def derive_kebab_problem_counts(
    records: Sequence[ProblemBankRecord],
) -> dict[str, int]:
    """문항 코퍼스 → {kebab_id: 그 kebab을 오답 귀인으로 쓰는 문항 수}(증거량·순수).

    역유도 성취기준의 *신뢰도*는 kebab이 등장한 문항 수에 달렸다(1문항 기반 유도는 얇음). 기계
    자동 거부는 이 증거량이 하한 이상인 kebab에만 적용한다(`machine_rejectable`).
    """
    counts: dict[str, int] = {}
    for record in records:
        for entry in record.problem.distractor_map or []:
            kebab = entry.misconception_id
            if kebab:
                counts[kebab] = counts.get(kebab, 0) + 1
    return counts


def machine_rejectable(
    kebab_standards: Iterable[str],
    kebab_problem_count: int,
    mid_standard: str | None,
    *,
    evidence_floor: int = MACHINE_REJECT_EVIDENCE_FLOOR,
) -> bool:
    """기계가 이 (kebab, M-id) 매핑을 *자율 거부*해도 되는가 — 측정된 안전 구간만(순수).

    True 조건: ① kebab 증거량 ≥ `evidence_floor`(역유도 성취기준 신뢰) **그리고** ② 성취기준이
    가로지름(`disagree`). agree·no_signal·증거 미달은 전부 False(인간 폴백). 이 함수는 *거부*만
    판정한다 — 승인(True로 통과)은 절대 반환하지 않는다(승인은 인간 존치·초인간 검증 §3.3).
    거부 실패 모드는 보수적(놓쳐도 오매핑 적재가 아니라 누락).
    """
    if kebab_problem_count < evidence_floor:
        return False
    return standard_agreement(kebab_standards, mid_standard) == "disagree"
