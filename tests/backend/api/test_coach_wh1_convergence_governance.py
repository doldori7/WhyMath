"""coach↔WH-1 하네스 도구 단일 진실원천 봉인 — S1-11 flip-없는 수렴 거버넌스(hermetic).

"이중 경로" 위험(s1_structure_audit §상환 #3·유지보수 지옥)은 두 오케스트레이터(결정론
coach·WH-1 하네스)가 *같은 순수 도구의 다른 사본*을 소비하게 될 때 현실화된다 — 한쪽만
수정되면 두 경로가 같은 입력에 다른 판정을 낸다. 본 테스트는 공유 도구가 **동일 함수
객체**(is — import 경로가 달라도 원천이 하나)임을 동결해, 사본 분기 유입 시 즉시 red를
낸다. primary flip(오케스트레이션 수렴·Kiki 게이트)과 무관하게 지금 지켜야 하는 불변식.

DB 0·LLM 0·순수 import 검사만(gate3 governance의 AST 검사와 상보 — 이쪽은 identity).
"""

from __future__ import annotations

from whymath_backend.api import coach
from whymath_backend.harness import wh1_loop
from whymath_backend.l4 import solution_coaching
from whymath_backend.l4.misconception import hypothesis_store


def test_diagnose_single_source() -> None:
    # 오개념 진단 — coach(패키지 재수출 경유)와 하네스(모듈 직수입)가 같은 함수 객체.
    assert coach.diagnose is wh1_loop.diagnose


def test_intervention_single_source() -> None:
    # 가설 기반 개입 선택 — 양 경로 동일 원천.
    assert coach.select_intervention_from_hypotheses is wh1_loop.select_intervention_from_hypotheses


def test_curate_single_source() -> None:
    # 가설 큐레이션 — coach는 영속 래퍼(curate_hypothesis) *내부*가, 하네스는 직접이
    # 같은 순수 curate를 소비한다(#191 재사용 계약의 identity 동결).
    assert hypothesis_store.curate is wh1_loop.curate


def test_verify_solution_single_source() -> None:
    # Tier2 단계 검증 — coach 경로의 검산 코칭(solution_coaching)과 하네스가 같은
    # l3.verify_solution을 소비한다(두 경로가 같은 풀이에 다른 판정을 낼 수 없음).
    assert solution_coaching.verify_solution is wh1_loop.verify_solution
