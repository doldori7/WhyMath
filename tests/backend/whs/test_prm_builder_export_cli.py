"""WH-S PRM export ops CLI(`whs/prm_builder_export_cli.py`) — 단위(hermetic·러너 주입).

DB 없이 CLI *배선*만 검증한다: ① stdout = JSONL 레코드(줄/레코드) ② stderr = 정직 요약 JSON
(total_input·records·excluded_uncertain·good_labels·bad_labels) ③ 종료 0(노드 0건도 정상)
④ `--stream` 옵트인 경로(distinct problem_id 흉내 async 이터레이터 + 문제별 node_loader 주입·
출력은 일괄과 동일·회계 누적). 실 DB 조회·트리 의미는 node_store·prm_builder 통합테스트가
검증한다(중복 0). 합성 `export_fn`(코루틴, `PrmDataset` 반환)·`stream_fn`(problem_id async
이터레이터 팩토리)·`node_loader`(problem_id→노드 list)를 주입한다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import pytest

from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode
from whymath_backend.whs import prm_builder_export_cli as cli
from whymath_backend.whs.prm_builder import PrmDataset, build_prm_dataset


def _node(
    *,
    problem_id: uuid.UUID,
    state: dict[str, object],
    status: NodeVerifyStatus,
    parent_id: uuid.UUID | None = None,
    action: str | None = None,
    node_id: uuid.UUID | None = None,
) -> SolutionNode:
    """in-memory SolutionNode 1개(DB 없음·id 명시 발급·`test_prm_builder._node` 복제)."""
    return SolutionNode(
        id=node_id or uuid.uuid4(),
        problem_id=problem_id,
        parent_id=parent_id,
        state_repr=state,
        action=action,
        verify_status=status,
    )


def _tree(problem_id: uuid.UUID, *, with_pending: bool = False) -> list[SolutionNode]:
    """root + good + bad(+ 옵션 pending) 1트리 — 한 문제 트리 픽스처."""
    root = _node(problem_id=problem_id, state={"s": "root"}, status=NodeVerifyStatus.PENDING)
    nodes = [
        root,
        _node(
            problem_id=problem_id,
            state={"s": "ok"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="good-step",
        ),
        _node(
            problem_id=problem_id,
            state={"s": "wrong"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="bad-step",
        ),
    ]
    if with_pending:
        nodes.append(
            _node(
                problem_id=problem_id,
                state={"s": "todo"},
                status=NodeVerifyStatus.PENDING,
                parent_id=root.id,
                action="pending-step",
            )
        )
    return nodes


def _runner(dataset: PrmDataset):  # type: ignore[no-untyped-def]
    """고정 `PrmDataset`을 반환하는 export_fn(배치 경로용·실 DB 조회 흉내·DB 0)."""

    async def _export() -> PrmDataset:
        return dataset

    return _export


def _stream_runner(problem_ids: list[uuid.UUID]):  # type: ignore[no-untyped-def]
    """고정 problem_id를 한 건씩 흘리는 stream_fn 팩토리(실 DB 서버측 커서 흉내·DB 0)."""

    def _factory() -> AsyncIterator[uuid.UUID]:
        async def _gen() -> AsyncIterator[uuid.UUID]:
            for pid in problem_ids:
                yield pid

        return _gen()

    return _factory


def _loader_for(mapping: dict[uuid.UUID, list[SolutionNode]]):  # type: ignore[no-untyped-def]
    """가짜 async node_loader — mapping에서 문제 트리 조회(없으면 빈 list)."""

    async def _loader(problem_id: uuid.UUID) -> list[SolutionNode]:
        return mapping.get(problem_id, [])

    return _loader


class TestPrmBuilderExportCli:
    def test_jsonl_to_stdout_summary_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """배치: stdout = 레코드/줄 JSONL·stderr = 회계 요약 JSON·종료 0."""
        pid = uuid.uuid4()
        ds = build_prm_dataset(_tree(pid))
        code = cli.main([], export_fn=_runner(ds))
        assert code == 0

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == ds.size == 2  # good 1·bad 1
        assert all(json.loads(ln)["problem_id"] == str(pid) for ln in lines)

        summary = json.loads(captured.err)
        assert summary == {
            "total_input": 2,
            "records": 2,
            "excluded_uncertain": 0,
            "good_labels": 1,
            "bad_labels": 1,
        }

    def test_excluded_uncertain_in_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        """배치 + PENDING 포함 → 정직 배제 집계·stdout은 good/bad만."""
        pid = uuid.uuid4()
        ds = build_prm_dataset(_tree(pid, with_pending=True))
        code = cli.main([], export_fn=_runner(ds))
        assert code == 0

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == 2  # good·bad만(pending 배제)
        assert all(json.loads(ln)["label"] in ("good", "bad") for ln in lines)
        summary = json.loads(captured.err)
        assert summary == {
            "total_input": 3,  # 비루트 step 3
            "records": 2,
            "excluded_uncertain": 1,  # PENDING 배제(R-S2)
            "good_labels": 1,
            "bad_labels": 1,
        }

    def test_empty_dataset_summary_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        """배치 빈 데이터셋 → stdout 0줄·요약 total=0·종료 0."""
        code = cli.main([], export_fn=_runner(build_prm_dataset([])))
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
        assert json.loads(captured.err) == {
            "total_input": 0,
            "records": 0,
            "excluded_uncertain": 0,
            "good_labels": 0,
            "bad_labels": 0,
        }


class TestPrmBuilderExportCliStream:
    """`--stream` 옵트인 — distinct problem_id 흉내 + 문제별 node_loader 주입으로 배선 검증."""

    def test_stream_jsonl_to_stdout_summary_to_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--stream 2문제: stdout = 합산 JSONL·stderr = 누적 회계 요약·종료 0."""
        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()
        code = cli.main(
            ["--stream"],
            stream_fn=_stream_runner([pid_a, pid_b]),
            node_loader=_loader_for({pid_a: _tree(pid_a), pid_b: _tree(pid_b)}),
        )
        assert code == 0

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == 4  # 문제당 good 1·bad 1 × 2문제
        pids = {json.loads(ln)["problem_id"] for ln in lines}
        assert pids == {str(pid_a), str(pid_b)}
        assert json.loads(captured.err) == {
            "total_input": 4,
            "records": 4,
            "excluded_uncertain": 0,
            "good_labels": 2,
            "bad_labels": 2,
        }

    def test_stream_multiple_problems_accounting_accumulates(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--stream: 문제마다 배제 step이 다른 경우에도 merge 누적이 정확하다."""
        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()
        code = cli.main(
            ["--stream"],
            stream_fn=_stream_runner([pid_a, pid_b]),
            node_loader=_loader_for(
                {
                    pid_a: _tree(pid_a, with_pending=True),  # good1·bad1·excluded1
                    pid_b: _tree(pid_b),  # good1·bad1
                }
            ),
        )
        assert code == 0
        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == 4  # good/bad만(pending 2개 배제 안 흘림)
        assert json.loads(captured.err) == {
            "total_input": 5,  # (3) + (2)
            "records": 4,
            "excluded_uncertain": 1,  # pid_a의 PENDING 1
            "good_labels": 2,
            "bad_labels": 2,
        }

    def test_stream_empty_summary_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--stream 빈 problem_id 스트림 → JSONL 0줄·요약 total=0·종료 0."""
        code = cli.main(
            ["--stream"],
            stream_fn=_stream_runner([]),
            node_loader=_loader_for({}),
        )
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
        assert json.loads(captured.err) == {
            "total_input": 0,
            "records": 0,
            "excluded_uncertain": 0,
            "good_labels": 0,
            "bad_labels": 0,
        }
