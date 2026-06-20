"""WH-S 자기 진화 — 풀이 트리 → PRM(Process Reward Model) 학습셋(설계 §5·순수).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §5(자기 진화 데이터)·§2.1(풀이 트리)·
§3(verify 3상태). `self_evolution.py`(검증 풀이→SFT)의 *짝* — 풀이 경로 트리의 *단계(step)*
판정을 process-supervision 학습쌍 `(prefix 상태열, step, good/bad 라벨)`로 변환하는 순수 코어다.
PRM은 중간 단계마다 보상을 주는 모델이라, 한 step(부모 상태 → 자식 상태 via `action`)의 검증
결과(`verify_status`)가 곧 그 step의 라벨이 된다 — SFT가 *완성된 풀이*를 통째로 학습신호화하는
것과 달리, PRM은 *단계별* 정/오를 학습신호화한다.

★학습 안전(§3·R-S2 보상 해킹 차단·CLAUDE.md 정확성 #1): **VERIFIED→good·FAILED→bad만** 학습
레코드로 만든다. PENDING(미검증 초기상태)·UNVERIFIED(판정 불가 격리)는 *구조적으로 배제*한다
(uncertain → 학습 누수 0). 배제 수는 *정직하게* 집계한다(조용히 버리지 않음 — `self_evolution`
R-S2 방침과 동형).

7계층(§7.5): WH-S 오프라인 — `solution_nodes`는 *시스템 솔버 내부 탐색 상태*이며 학생 PII가
아니다(redaction·암호화 무관). **구성**(`mastery_tracking` 패턴): `build_prm_dataset`(순수·DB 0)
+ `collect_prm_dataset`(얇은 async DB 시ام — `node_store.get_problem_nodes` 조회 후 순수 빌더 호출).
`self_evolution.py`가 순수→실 DB 조회→ops CLI로 증분 확장한 선례를 답습한다. 범위 밖(후속):
다중 문제 일괄/스트리밍·JSONL ops CLI·confidence(`prm_score` 반영)·(prefix, step) dedup·
Dead-End Log(§2.3) 통합(트리 밖에서 가지친 실패 step의 추가 bad 신호).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode
from whymath_backend.whs.node_store import get_problem_nodes

__all__ = [
    "PrmDataset",
    "PrmRecord",
    "PrmStepLabel",
    "build_prm_dataset",
    "collect_prm_dataset",
    "iter_prm_jsonl",
]

PrmStepLabel = Literal["good", "bad"]

# step 라벨은 노드의 verify_status로 결정 — VERIFIED=good·FAILED=bad. PENDING(미검증)·
# UNVERIFIED(판정 불가)는 매핑에 *없으므로* uncertain으로 배제된다(R-S2 학습 안전).
_LABEL_BY_STATUS: dict[NodeVerifyStatus, PrmStepLabel] = {
    NodeVerifyStatus.VERIFIED: "good",
    NodeVerifyStatus.FAILED: "bad",
}


class PrmRecord(BaseModel):
    """PRM 학습 1건 — 한 step(부모 상태 → 이 상태)의 process-supervision 쌍.

    `prefix_states`는 루트~부모까지의 상태열(이 step 직전까지의 풀이 경로)이고, `step_state`는
    `step_action`을 적용해 도달한 상태다. `label`은 그 step의 검증 결과(good=verified·bad=failed).
    출처 메타(node id·타임스탬프·visits·prm_score)는 학습신호가 아니라 제외한다(SftRecord 동형).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: uuid.UUID = Field(description="step이 속한 문제(느슨참조).")
    prefix_states: tuple[dict[str, Any], ...] = Field(
        description="루트~부모까지 상태열(이 step 직전 경로·루트 직후 step이면 길이 1)."
    )
    step_action: str = Field(description="부모→이 노드 도달 행동(전략 1스텝·엣지).")
    step_state: dict[str, Any] = Field(description="step 적용 후 상태(state_repr).")
    label: PrmStepLabel = Field(description="step 검증 라벨 — good(verified)·bad(failed).")


class PrmDataset(BaseModel):
    """`build_prm_dataset` 결과 — 레코드 + *정직한* 집계(배제·라벨 분포).

    `excluded_uncertain`은 PENDING·UNVERIFIED step을 조용히 버리지 않은 투명 회계다(R-S2 가시화).
    `size`(=len(records))가 실제 학습쌍 수. `good_labels + bad_labels == size`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: tuple[PrmRecord, ...] = Field(description="학습 레코드(good·bad만·입력 순서 보존).")
    total_input: int = Field(ge=0, description="후보 step(action 보유 비루트 노드) 총수(필터 전).")
    excluded_uncertain: int = Field(
        ge=0, description="PENDING·UNVERIFIED로 배제된 step 수(R-S2 학습 배제)."
    )
    good_labels: int = Field(ge=0, description="good(verified) step 수.")
    bad_labels: int = Field(ge=0, description="bad(failed) step 수.")

    @property
    def size(self) -> int:
        """실제 학습쌍 수(=len(records))."""
        return len(self.records)


def _prefix_states(
    node: SolutionNode, by_id: dict[uuid.UUID, SolutionNode]
) -> tuple[dict[str, Any], ...]:
    """루트~부모까지 상태열 — `parent_id` 체인을 `by_id`로 거슬러 모아 역순(root→parent).

    체인이 끊기면(부분 트리·부모 노드 미포함) 거기서 멈춘다(best-effort·날조 0). 순수.
    """
    chain: list[dict[str, Any]] = []
    pid = node.parent_id
    while pid is not None:
        parent = by_id.get(pid)
        if parent is None:
            break  # 부모가 입력에 없음(부분 트리) — 모은 데까지만(끊긴 체인 정직 반영).
        chain.append(parent.state_repr)
        pid = parent.parent_id
    chain.reverse()
    return tuple(chain)


def build_prm_dataset(nodes: Iterable[SolutionNode]) -> PrmDataset:
    """풀이 트리 노드들 → PRM process-supervision 학습셋(good/bad만·정직 집계·순수).

    각 *비루트*(=`parent_id` 있음) 노드는 한 step((부모 상태 → 이 상태) via `action`)이다. 루트
    노드는 들어온 행동이 없어 step이 아니므로 건너뛴다. `action`이 없는 비루트 노드(엣지 결손·데이터
    이상)도 step이 아니므로 제외한다(total_input에 세지 않음 — 후보 step은 *action 보유 비루트*).

    **R-S2 학습 안전(심층 방어)**: step 라벨은 노드 `verify_status`로 — VERIFIED→good·FAILED→bad.
    PENDING(미검증)·UNVERIFIED(판정 불가)는 레코드로 만들지 않고 `excluded_uncertain`으로 집계한다
    (판정 불가 step의 학습 누수 0). 입력 순서를 보존한다(결정론). 트랜잭션·DB 0(순수).
    """
    node_list = list(nodes)
    by_id = {n.id: n for n in node_list}
    records: list[PrmRecord] = []
    total = 0
    excluded = 0
    good = 0
    bad = 0
    for node in node_list:
        if node.parent_id is None or node.action is None:
            continue  # 루트(들어온 행동 없음) 또는 엣지 결손 — step 아님(후보에서 제외).
        total += 1
        label = _LABEL_BY_STATUS.get(node.verify_status)
        if label is None:
            excluded += 1  # PENDING·UNVERIFIED → R-S2 배제(정직 집계).
            continue
        records.append(
            PrmRecord(
                problem_id=node.problem_id,
                prefix_states=_prefix_states(node, by_id),
                step_action=node.action,
                step_state=node.state_repr,
                label=label,
            )
        )
        if label == "good":
            good += 1
        else:
            bad += 1
    return PrmDataset(
        records=tuple(records),
        total_input=total,
        excluded_uncertain=excluded,
        good_labels=good,
        bad_labels=bad,
    )


async def collect_prm_dataset(session: AsyncSession, problem_id: uuid.UUID) -> PrmDataset:
    """한 문제의 풀이 트리를 실 DB에서 로드해 PRM 학습셋을 만든다(얇은 DB 시ام).

    `node_store.get_problem_nodes`로 트리 전체를 *한 번에* 평탄 로드한 뒤 순수 `build_prm_dataset`에
    넘긴다(N+1 쿼리 회피·`mastery_tracking`의 record_attempt_mastery류 얇은 래퍼). 읽기 전용(commit
    0). 다중 문제 일괄/스트리밍·ops CLI는 후속(`self_evolution` 선례).
    """
    nodes = await get_problem_nodes(session, problem_id)
    return build_prm_dataset(nodes)


def iter_prm_jsonl(dataset: PrmDataset) -> Iterator[str]:
    """데이터셋의 레코드를 **JSONL 한 줄/레코드**로 yield한다(순수·결정론·레코드 순서 보존).

    각 줄은 `PrmRecord.model_dump_json()`(UUID→문자열·nested state dict 처리)이다 — 개행 없는 1줄.
    후속 ops CLI가 stdout으로 흘려 `> prm.jsonl`로 받는다(회계는 stderr·`iter_sft_jsonl` 동형).
    """
    for record in dataset.records:
        yield record.model_dump_json()
