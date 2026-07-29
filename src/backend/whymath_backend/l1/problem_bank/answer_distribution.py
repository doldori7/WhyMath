"""⑧ 정답 위치 분포 편향 — 코퍼스 수준 결정론 분포 검정 (품질 15축 ⑧, ARCH-19).

객관식 문항의 정답 위치(0-기반 `choices` 인덱스)가 균등분포에서 벗어나는지 카이제곱
적합도 검정(scipy)으로 판정한다. `defect_seeder`(문항 *개별* 결함 모델)와 달리 이 축은
**배치**(코퍼스 전체 또는 표본) 수준 통계 검정이다 — 단일 문항은 "쏠렸다"고 말할 수 없고
집단만 말할 수 있다.

정본: `docs/architecture/problem_bank_gap_review.md` §3 D5. 결함 주입 강등전은
`harness/answer_distribution_battle.py`가 담당(합성 쏠림 배치 vs 균형 배치로 검정력 실측).

7계층: L1(문제은행 코퍼스 축). scipy(수치 계산)만 의존 — DB·LLM·네트워크 0.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scipy.stats import chisquare

__all__ = [
    "AnswerDistributionResult",
    "answer_position",
    "chi_square_uniform_test",
    "tally_positions",
]


@dataclass(slots=True, frozen=True)
class AnswerDistributionResult:
    """카이제곱 적합도 검정 결과 — 균등분포(각 위치 1/n_positions 기대) 대비 관측 위치 분포."""

    position_counts: Mapping[int, int]
    n_positions: int
    n_items: int
    statistic: float
    p_value: float
    malformed: int

    def is_skewed(self, alpha: float = 0.05) -> bool:
        """p < alpha면 균등분포 기각(쏠림 있음). n_items==0(대상 부재)이면 판정 불가 → False.

        대상 부재를 "균등하다"(쏠림 없음)로 확정하지 않되, 게이트가 True/False 이분을
        요구하므로 미판정은 통과 쪽(False)에 둔다 — n_items는 리포트에 항상 병기되므로
        "0건이라 판정 불가"가 숨겨지지 않는다(조용한 실패 금지).
        """
        if self.n_items == 0:
            return False
        return self.p_value < alpha


def answer_position(choices: Sequence[str], answer: str | None) -> int | None:
    """정답의 `choices` 내 0-기반 인덱스 — `answer`가 None이거나 `choices`에 없으면 None."""
    if answer is None:
        return None
    try:
        return list(choices).index(answer)
    except ValueError:
        return None


def tally_positions(
    pairs: Sequence[tuple[Sequence[str], str | None]], *, n_positions: int
) -> tuple[Counter[int], int]:
    """(choices, answer) 쌍 배치 → 위치별 카운트 + malformed 수(정직 회계).

    `choices` 길이가 `n_positions`와 다른 항목은 malformed로 센다(다른 선택지 수는 균등분포
    가정의 카테고리 수 자체가 달라 같은 검정에 섞을 수 없다 — 조용히 버리지 않고 카운트).
    """
    counts: Counter[int] = Counter()
    malformed = 0
    for choices, answer in pairs:
        if len(choices) != n_positions:
            malformed += 1
            continue
        pos = answer_position(choices, answer)
        if pos is None:
            malformed += 1
            continue
        counts[pos] += 1
    return counts, malformed


def chi_square_uniform_test(
    position_counts: Mapping[int, int], *, n_positions: int, malformed: int = 0
) -> AnswerDistributionResult:
    """위치별 카운트 → 균등분포 대비 카이제곱 적합도 검정.

    `n_items == 0`(대상 부재)이면 검정을 실행하지 않고 nan을 낸다 — 표본 0을 "균등"으로
    위장하지 않는다.
    """
    observed = [position_counts.get(i, 0) for i in range(n_positions)]
    n_items = sum(observed)
    if n_items == 0:
        return AnswerDistributionResult(
            position_counts=dict(position_counts),
            n_positions=n_positions,
            n_items=0,
            statistic=float("nan"),
            p_value=float("nan"),
            malformed=malformed,
        )
    result = chisquare(observed)
    return AnswerDistributionResult(
        position_counts=dict(position_counts),
        n_positions=n_positions,
        n_items=n_items,
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
        malformed=malformed,
    )
