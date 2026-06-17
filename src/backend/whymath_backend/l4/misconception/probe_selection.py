"""진단 프로브 선택 `select_probe` — 정보이득 근사 + ε-탐색(순수 결정 로직).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §3 도구6(`select_probe`)·§3.2
(정보이득 근사)·§2.2 규칙2(ε-탐색 강제). WH-1 하네스가 *활성 가설을 판별*할 진단 문항 1개를
고르는 도구다. 이미 만들어진 가설 세트(`hypothesis.py`)와 L2 IRT 정보함수(`l2.irt`)를
**조합**할 뿐, 매칭·IRT *알고리즘*은 전혀 건드리지 않는다(재구현 0).

핵심 원칙(§3.2 — "전용 판별 문항이 항상 존재" 가정은 조합 폭발로 비현실적):
  - **정보이득 근사**: 문항은 오개념 *태그*(다중)를 갖는다. "가설 A 태그는 *있고* 경쟁
    가설 태그는 *없는*" 문항이 A를 깔끔히 판별한다(`discriminates`). 그 중 학생 능력 θ
    대비 *정보량 최대*(난이도가 θ에 가까울수록 변별력↑)인 문항을 IRT `item_information`
    으로 고른다. 완전 판별이 아닌 *근사*다 — 하네스가 진단 신뢰도 상한(가설 confidence
    ≤0.9)을 거는 근거(시스템이 "확신"을 출력하지 않게·§3.2).
  - **ε-탐색 강제(§2.2 규칙2)**: `period`턴마다 1회, 프로브는 활성 가설 세트 *밖*의 차순위
    오개념을 의무로 겨냥한다(`is_exploration_turn`). 1위 고착(확증편향·R4)을 깨 진단
    다양성을 유지한다. 카운터(턴 인덱스)·외부 후보 산출은 하네스 몫이라 *주입*받는다.

**순수·결정론**: DB·provider·LLM·전역 상태·무작위를 *모른다*(입력 후보/가설/θ/턴 인덱스
스칼라만으로 결정). 입력을 변형하지 않고 frozen 모델·새 객체만 반환한다. 동률은 problem_id
오름차순으로 안정 tiebreak(입력 순서 무관 재현). `select_focus`의 *확률적 ε-greedy*(개입
대상 선택)와 본 모듈의 *주기적 ε-탐색*(프로브 타깃)은 **다른 ε**임에 유의(둘 다 R4 대응).

**정직 스코프(후속)**: 본 슬라이스는 *순수 선택 로직만*이다. 다음은 후속 —
  · 문제은행 적재·문항-오개념 *태그* 스키마(현 레포 부재 — 하네스가 후보를 공급).
  · ε 턴 카운터 per-session 영속(Redis/PG 스냅샷)·위반 시 probe 거부 집행(하네스 런타임).
  · IRT 난이도 b 실적합·노출 통제·a-층화(L2 후속)·진단 신뢰도 상한 0.9 집행(하네스).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l2.irt import IrtItem, item_information
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis

# 설계 §2.2 규칙2 — "5턴마다 1회" ε-탐색 주기(파라미터화·기본은 설계값).
_EXPLORE_PERIOD = 5
"""ε-탐색 강제 주기(턴). 이 주기마다 1회 프로브는 활성 가설 세트 *밖*의 오개념을 의무로
겨냥한다(§2.2 규칙2). 1위 고착(확증편향)을 깨 진단 다양성을 유지(R4 대응)."""


class ProbeCandidate(BaseModel):
    """진단 프로브 후보 문항 1개 — IRT 파라미터 + 오개념 태그(다중). 불변(frozen).

    `misconception_tags`는 이 문항이 *드러낼 수 있는* 오개념 id 집합이다(다중 태그·§3.2).
    난이도/변별도로 학생 θ에서의 정보량을 계산한다(`item_information` 재사용).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: str = Field(description="문항 식별자(구조 참조·동률 tiebreak 키).")
    difficulty: float = Field(description="IRT b — 난이도(θ=b에서 정답확률 0.5). logit 척도.")
    discrimination: float = Field(
        default=1.0, gt=0.0, description="IRT a — 변별도(곡선 기울기·양수). 기본 1.0=Rasch."
    )
    misconception_tags: frozenset[str] = Field(
        default_factory=frozenset,
        description="이 문항이 드러낼 수 있는 오개념 id 집합(다중 태그·§3.2 정보이득).",
    )

    def as_irt_item(self) -> IrtItem:
        """L2 `IrtItem`으로 변환 — `item_information`에 넘겨 정보량 계산(재구현 0)."""
        return IrtItem(difficulty=self.difficulty, discrimination=self.discrimination)


class ProbeTarget(BaseModel):
    """프로브가 *겨냥*할 오개념 1개 + 판별에서 *배제*할 경쟁 오개념들. 불변(frozen).

    `resolve_probe_target`이 활성 가설 세트·ε 주기에서 산출한다. `select_probe`는 이 타깃에
    맞춰 "target 태그 있고 competing 태그 없는" 문항만 후보로 본다(정보이득 근사·§3.2).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_misconception_id: str = Field(description="판별 대상 오개념 id(이 태그가 *있어야* 함).")
    competing_mids: frozenset[str] = Field(
        default_factory=frozenset,
        description="판별 시 *배제*할 경쟁 오개념 id들(이 태그가 *없어야* 함·교란 제거).",
    )
    is_exploration: bool = Field(
        default=False,
        description="ε-탐색(활성 세트 밖 겨냥) 여부 — 진단 신뢰도·로깅 표식(§2.2 규칙2).",
    )


class ProbeSelection(BaseModel):
    """`select_probe` 결과 — 고른 문항 + 겨냥 오개념 + 정보량. 불변(frozen).

    `information`은 학생 θ에서 이 문항의 IRT 정보량(Fisher)이다 — 클수록 변별력↑. 하네스가
    이를 *진단 신뢰도*(가설 confidence ≤0.9 상한)로 환산한다(완전 판별 아닌 근사·§3.2).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: str = Field(description="선택된 진단 문항 id.")
    target_misconception_id: str = Field(description="이 프로브가 판별하려는 오개념 id.")
    is_exploration: bool = Field(description="ε-탐색(활성 세트 밖)으로 고른 타깃 여부.")
    information: float = Field(
        ge=0.0,
        description="학생 θ에서의 IRT 정보량(Fisher) — 진단 신뢰도 환산 근거(상한은 하네스).",
    )


def is_exploration_turn(turn_index: int, *, period: int = _EXPLORE_PERIOD) -> bool:
    """이번 턴이 ε-탐색 강제 턴인가 — `period`턴마다 1회 True(§2.2 규칙2·순수·결정론).

    `turn_index`(1-기반)가 `period`의 양의 배수면 True. `turn_index<1`이면 False(미시작).
    `period<=0`이면 ValueError(주기는 양수). 무작위 없이 *주기적*으로 탐색을 강제해 1위
    고착을 깬다(`select_focus`의 확률적 ε와 달리 결정론 — 하네스 카운터로 재현·집행 가능).
    """
    if period <= 0:
        raise ValueError("period는 양의 정수여야 합니다")
    return turn_index >= 1 and turn_index % period == 0


def discriminates(
    tags: frozenset[str], target_mid: str, *, competing_mids: frozenset[str] = frozenset()
) -> bool:
    """이 문항 태그가 target을 *판별*하는가 — target 있고 competing 전부 없음(§3.2·순수).

    정보이득 근사: "가설 A 태그는 *있고* 경쟁 가설 B 태그는 *없는*" 문항이라야 A를 교란 없이
    판별한다. `target_mid ∈ tags` AND `tags ∩ competing_mids == ∅`. target 자신이 competing에
    들어도(모순 입력) 교집합 검사가 우선해 False(안전).
    """
    return target_mid in tags and tags.isdisjoint(competing_mids)


def resolve_probe_target(
    active: Sequence[MisconceptionHypothesis],
    outside_mids: Sequence[str],
    *,
    turn_index: int,
    period: int = _EXPLORE_PERIOD,
) -> ProbeTarget | None:
    """겨냥 타깃 결정 — ε-탐색 턴이면 활성 세트 *밖*, 아니면 최상위 가설(순수·결정론·§2.2).

    절차:
      - **탐색 턴**(`is_exploration_turn`)이고 `outside_mids`가 있으면 → 첫 외부 오개념을 겨냥
        (`is_exploration=True`)하고 *활성 세트 전체*를 competing으로 배제(외부를 활성과 구별).
      - 그 외 활성 가설이 있으면 → **활용**: 최상위 가설을 겨냥(`is_exploration=False`)하고
        *나머지 활성 가설*을 competing으로 배제(최상위를 경쟁 가설들과 판별·§3.2 "A있고 B없음").
      - 활성 가설이 없으면 → 외부 후보가 있으면 그것을 그대로 겨냥(탐색/활용 구분 무의미·
        `is_exploration`은 주기만 반영)·없으면 None(겨냥 대상 없음).

    `active`는 confidence 내림차순 정렬을 가정한다(`get_active_hypotheses`/`curate` 결과). 입력
    비변형. 무엇을 외부 후보로 줄지(해당 노드 차순위 오개념)는 하네스 몫이라 주입받는다.
    """
    explore = is_exploration_turn(turn_index, period=period)
    active_mids = [h.misconception_id for h in active]

    if explore and outside_mids:
        return ProbeTarget(
            target_misconception_id=outside_mids[0],
            competing_mids=frozenset(active_mids),
            is_exploration=True,
        )
    if active_mids:
        return ProbeTarget(
            target_misconception_id=active_mids[0],
            competing_mids=frozenset(active_mids[1:]),
            is_exploration=False,
        )
    if outside_mids:
        return ProbeTarget(
            target_misconception_id=outside_mids[0],
            competing_mids=frozenset(),
            is_exploration=explore,
        )
    return None


def select_probe(
    candidates: Sequence[ProbeCandidate],
    target: ProbeTarget,
    *,
    theta: float,
    administered: frozenset[str] = frozenset(),
) -> ProbeSelection | None:
    """타깃을 판별하는 후보 중 학생 θ에서 *정보량 최대* 문항 1개 선택(순수·결정론·§3.2).

    절차:
      1. `discriminates`(target 있고 competing 없음) AND `problem_id ∉ administered` 후보만 추림.
      2. 남은 후보 중 `item_information(θ, ·)`(IRT Fisher 정보)이 최대인 문항 선택 — 난이도가
         θ에 가까울수록 변별력↑(맞힐지 틀릴지 불확실한 문항·재구현 0). 동률은 problem_id
         오름차순(결정론·입력 순서 무관).
      3. 판별 후보가 없으면 None(억지 매칭 금지·§3.3 정신).

    반환 `ProbeSelection`은 `target.is_exploration`을 그대로 전파한다(로깅·신뢰도 표식).
    """
    best: ProbeSelection | None = None
    best_info = -math.inf
    for cand in candidates:
        if cand.problem_id in administered:
            continue
        if not discriminates(
            cand.misconception_tags,
            target.target_misconception_id,
            competing_mids=target.competing_mids,
        ):
            continue
        info = item_information(theta, cand.as_irt_item())
        # 동률 tiebreak: 더 큰 정보량 우선, 같으면 problem_id 사전식 더 작은 쪽(결정론).
        if info > best_info or (
            best is not None and info == best_info and cand.problem_id < best.problem_id
        ):
            best_info = info
            best = ProbeSelection(
                problem_id=cand.problem_id,
                target_misconception_id=target.target_misconception_id,
                is_exploration=target.is_exploration,
                information=info,
            )
    return best


def plan_probe(
    candidates: Sequence[ProbeCandidate],
    active: Sequence[MisconceptionHypothesis],
    outside_mids: Sequence[str],
    *,
    theta: float,
    turn_index: int,
    administered: frozenset[str] = frozenset(),
    period: int = _EXPLORE_PERIOD,
) -> ProbeSelection | None:
    """프로브 1개 계획 — 타깃 결정(ε-탐색/활용) → 정보량 최대 판별 문항 선택(순수 조합).

    `resolve_probe_target`(§2.2 ε-탐색·활용 분기) → `select_probe`(§3.2 정보이득 근사)를 잇는
    하네스용 단일 진입점이다(재구현 0·조합). 겨냥 대상이 없거나(`resolve_probe_target` None)
    판별 문항이 없으면(`select_probe` None) None을 반환한다. 후보·외부 오개념·턴 카운터는
    하네스가 DB/세션에서 공급한다(본 함수는 순수).
    """
    target = resolve_probe_target(active, outside_mids, turn_index=turn_index, period=period)
    if target is None:
        return None
    return select_probe(candidates, target, theta=theta, administered=administered)


__all__ = [
    "ProbeCandidate",
    "ProbeSelection",
    "ProbeTarget",
    "discriminates",
    "is_exploration_turn",
    "plan_probe",
    "resolve_probe_target",
    "select_probe",
]
