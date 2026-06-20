"""WH-S PRM 학습셋 빌더(`whs/prm_builder.py`) — 순수 단위(hermetic·in-memory 트리).

`build_prm_dataset`의 *추출·라벨·회계* 로직만 검증한다: 비루트 step 추출·verify_status→good/bad
라벨·PENDING/UNVERIFIED 배제(R-S2)·prefix 상태열·정직 집계·JSONL 직렬화. DB 무관(SolutionNode
in-memory 구성). 실 DB 트리 조회는 후속 슬라이스(self_evolution 순수→DB 선례).
"""

from __future__ import annotations

import json
import uuid

from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode
from whymath_backend.whs.prm_builder import (
    PrmDataset,
    build_prm_dataset,
    iter_prm_jsonl,
)

_PID = uuid.uuid4()


def _node(
    *,
    state: dict[str, object],
    status: NodeVerifyStatus,
    parent_id: uuid.UUID | None = None,
    action: str | None = None,
    node_id: uuid.UUID | None = None,
) -> SolutionNode:
    """in-memory SolutionNode 1개(DB 없음·id 명시 발급)."""
    return SolutionNode(
        id=node_id or uuid.uuid4(),
        problem_id=_PID,
        parent_id=parent_id,
        state_repr=state,
        action=action,
        verify_status=status,
    )


class TestBuildPrmDataset:
    def test_extracts_good_and_bad_from_verify_status(self) -> None:
        """root + verified child + failed child → good 1·bad 1·배제 0."""
        root = _node(state={"expr": "2x+1=7"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"expr": "2x=6"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="양변에서 1 빼기",
        )
        bad = _node(
            state={"expr": "x^2=9"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="잘못된 제곱",
        )
        ds = build_prm_dataset([root, good, bad])
        assert isinstance(ds, PrmDataset)
        assert ds.total_input == 2  # 비루트 step 2(root는 step 아님)
        assert ds.good_labels == 1 and ds.bad_labels == 1
        assert ds.excluded_uncertain == 0
        assert ds.size == 2
        by_label = {r.label: r for r in ds.records}
        assert by_label["good"].step_action == "양변에서 1 빼기"
        assert by_label["good"].step_state == {"expr": "2x=6"}
        assert by_label["good"].prefix_states == ({"expr": "2x+1=7"},)  # root만
        assert by_label["bad"].label == "bad"

    def test_excludes_pending_and_unverified_r_s2(self) -> None:
        """PENDING·UNVERIFIED step은 학습 배제(uncertain)·정직 집계·verified만 레코드."""
        root = _node(state={"s": 0}, status=NodeVerifyStatus.PENDING)
        pending = _node(
            state={"s": 1}, status=NodeVerifyStatus.PENDING, parent_id=root.id, action="a"
        )
        unverified = _node(
            state={"s": 2}, status=NodeVerifyStatus.UNVERIFIED, parent_id=root.id, action="b"
        )
        verified = _node(
            state={"s": 3}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="c"
        )
        ds = build_prm_dataset([root, pending, unverified, verified])
        assert ds.total_input == 3  # 비루트 step 3
        assert ds.excluded_uncertain == 2  # PENDING·UNVERIFIED 배제
        assert ds.size == 1 and ds.good_labels == 1
        assert all(r.label in ("good", "bad") for r in ds.records)
        assert ds.records[0].step_action == "c"

    def test_prefix_states_multi_level(self) -> None:
        """깊은 트리 — step의 prefix는 루트~부모 상태열(순서 보존)."""
        root = _node(state={"d": 0}, status=NodeVerifyStatus.PENDING)
        a = _node(state={"d": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="a1")
        b = _node(state={"d": 2}, status=NodeVerifyStatus.VERIFIED, parent_id=a.id, action="a2")
        ds = build_prm_dataset([root, a, b])
        by_state = {tuple(sorted(r.step_state.items())): r for r in ds.records}
        rec_a = by_state[(("d", 1),)]
        rec_b = by_state[(("d", 2),)]
        assert rec_a.prefix_states == ({"d": 0},)  # root
        assert rec_b.prefix_states == ({"d": 0}, {"d": 1})  # root → a

    def test_root_only_yields_no_records(self) -> None:
        """루트만 있으면 step 0(들어온 행동 없음)."""
        root = _node(state={"x": 1}, status=NodeVerifyStatus.PENDING)
        ds = build_prm_dataset([root])
        assert ds.total_input == 0 and ds.size == 0

    def test_empty_input(self) -> None:
        """빈 입력 → 빈 데이터셋(전부 0)."""
        ds = build_prm_dataset([])
        assert ds.size == 0
        assert ds.total_input == 0 and ds.excluded_uncertain == 0

    def test_non_root_without_action_is_not_a_step(self) -> None:
        """비루트인데 action 결손(엣지 미상) → 후보 step 아님(total_input 미포함)."""
        root = _node(state={"x": 0}, status=NodeVerifyStatus.PENDING)
        orphan_action = _node(
            state={"x": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action=None
        )
        ds = build_prm_dataset([root, orphan_action])
        assert ds.total_input == 0 and ds.size == 0

    def test_input_order_preserved(self) -> None:
        """레코드는 입력 순서 보존(결정론)."""
        root = _node(state={"n": 0}, status=NodeVerifyStatus.PENDING)
        c1 = _node(state={"n": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="1")
        c2 = _node(state={"n": 2}, status=NodeVerifyStatus.FAILED, parent_id=root.id, action="2")
        c3 = _node(state={"n": 3}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="3")
        ds = build_prm_dataset([root, c1, c2, c3])
        assert [r.step_action for r in ds.records] == ["1", "2", "3"]


class TestIterPrmJsonl:
    def test_yields_one_json_line_per_record(self) -> None:
        """레코드당 JSONL 1줄 — UUID·nested state dict 직렬화·round-trip."""
        root = _node(state={"expr": "a"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"expr": "b"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="step"
        )
        ds = build_prm_dataset([root, good])
        lines = list(iter_prm_jsonl(ds))
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["problem_id"] == str(_PID)
        assert obj["label"] == "good"
        assert obj["step_action"] == "step"
        assert obj["step_state"] == {"expr": "b"}
        assert obj["prefix_states"] == [{"expr": "a"}]

    def test_empty_dataset_yields_no_lines(self) -> None:
        """빈 데이터셋 → 0줄."""
        assert list(iter_prm_jsonl(build_prm_dataset([]))) == []
