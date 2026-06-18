"""자기 진화 SFT export ops CLI(`whs/self_evolution_export_cli.py`) — 단위(hermetic·러너 주입).

DB 없이 CLI *배선*만 검증한다: ① stdout = JSONL 레코드(줄/레코드) ② stderr = 정직 요약 JSON
(total_input·records·excluded_unverified·deduped) ③ `--no-dedup` → dedup=False 전달 ④ 종료 0
(verified 0건도 정상) ⑤ `--stream` 옵트인 경로(서버측 커서 흉내 async 이터레이터 주입·출력은
일괄과 동일). 실 DB 조회·변환은 solution_bank·self_evolution 테스트가 검증한다(중복 0). 합성
`export_fn`(코루틴, `SftDataset` 반환)·`stream_fn`(async 이터레이터 팩토리)을 주입한다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import pytest

from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.schema.enums import SourceType
from whymath_backend.whs import self_evolution_export_cli as cli
from whymath_backend.whs.self_evolution import SftDataset, build_sft_dataset


def _vs(problem_id: uuid.UUID, path: dict, grade: WhsSolutionGrade = WhsSolutionGrade.VERIFIED):  # type: ignore[type-arg]
    return VerifiedSolution(problem_id=problem_id, grade=grade, solution_path=path)


def _problem(  # type: ignore[no-untyped-def]
    problem_id: uuid.UUID,
    *,
    question_text: str = "문제 본문",
    source_type: SourceType = SourceType.자체생성,
    conditions_parsed: list | None = None,
):
    return Problem(
        problem_id=problem_id,
        question_text=question_text,
        unit_codes=["M1-A-01"],
        source_type=source_type,
        conditions_parsed=conditions_parsed if conditions_parsed is not None else [],
    )


def _runner(dataset: SftDataset, *, seen: dict[str, bool]):  # type: ignore[no-untyped-def]
    async def _export(dedup: bool, with_problem: bool) -> SftDataset:
        seen["dedup"] = dedup
        seen["with_problem"] = with_problem
        return dataset

    return _export


def _stream_runner(rows: list[VerifiedSolution]):  # type: ignore[no-untyped-def]
    """고정 행을 한 건씩 흘리는 stream_fn 팩토리(실 DB 서버측 커서 흉내·DB 0)."""

    def _factory() -> AsyncIterator[VerifiedSolution]:
        async def _gen() -> AsyncIterator[VerifiedSolution]:
            for row in rows:
                yield row

        return _gen()

    return _factory


def _loader_for(mapping: dict[uuid.UUID, Problem]):  # type: ignore[no-untyped-def]
    """가짜 async problem_loader — mapping에서 조회(없으면 None)."""

    async def _loader(problem_id: uuid.UUID) -> Problem | None:
        return mapping.get(problem_id)

    return _loader


class TestSelfEvolutionExportCli:
    def test_jsonl_to_stdout_summary_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stdout = 레코드/줄 JSONL·stderr = 회계 요약 JSON·종료 0."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(pid, {"steps": ["x=2"]}),
                _vs(pid, {"steps": ["x=2"]}, grade=WhsSolutionGrade.UNVERIFIED),  # 배제
                _vs(pid, {"steps": ["x=3"]}),
            ]
        )
        seen: dict[str, bool] = {}
        code = cli.main([], export_fn=_runner(ds, seen=seen))
        assert code == 0
        assert seen["dedup"] is True  # 기본 dedup ON
        assert seen["with_problem"] is False  # --with-problem 미설정

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == ds.size == 2  # verified 2건만
        assert all(json.loads(ln)["problem_id"] == str(pid) for ln in lines)

        summary = json.loads(captured.err)
        assert summary == {
            "total_input": 3,
            "records": 2,
            "excluded_unverified": 1,  # unverified 1건 배제(정직 집계)
            "deduped": 0,
            "problems_missing": 0,  # 문제 조인 안 함 → 0
            "conditions_gated": 0,
        }

    def test_no_dedup_flag_forwarded(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--no-dedup → export_fn에 dedup=False 전달."""
        seen: dict[str, bool] = {}
        code = cli.main(
            ["--no-dedup"],
            export_fn=_runner(build_sft_dataset([]), seen=seen),
        )
        assert code == 0
        assert seen["dedup"] is False
        capsys.readouterr()

    def test_empty_dataset_no_records_summary_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """verified 0건 → stdout 비고 요약 total=0·종료 0."""
        code = cli.main([], export_fn=_runner(build_sft_dataset([]), seen={}))
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""  # JSONL 0줄
        assert json.loads(captured.err)["total_input"] == 0


class TestSelfEvolutionExportCliStream:
    """`--stream` 옵트인 — 서버측 커서 흉내 async 이터레이터 주입으로 스트리밍 배선 검증."""

    def test_stream_jsonl_to_stdout_summary_to_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--stream: stdout = JSONL/줄·stderr = 회계 요약(verified 필터·dedup 적용)·종료 0."""
        pid = uuid.uuid4()
        rows = [
            _vs(pid, {"steps": ["x=2"]}),
            _vs(pid, {"steps": ["x=2"]}, grade=WhsSolutionGrade.UNVERIFIED),  # 배제
            _vs(pid, {"steps": ["x=2"]}),  # 같은 문제·같은 지문 재발견(dedup)
            _vs(pid, {"steps": ["x=3"]}),
        ]
        code = cli.main(["--stream"], stream_fn=_stream_runner(rows))
        assert code == 0

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert len(lines) == 2  # verified·dedup 통과 2건(x=2 1건 + x=3)
        assert all(json.loads(ln)["problem_id"] == str(pid) for ln in lines)
        assert json.loads(captured.err) == {
            "total_input": 4,
            "records": 2,
            "excluded_unverified": 1,
            "deduped": 1,
            "problems_missing": 0,
            "conditions_gated": 0,
        }

    def test_stream_no_dedup_keeps_duplicates(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--stream --no-dedup: 같은 지문 재발견도 그대로 흘림(deduped=0)."""
        pid = uuid.uuid4()
        rows = [_vs(pid, {"steps": ["x=2"]}), _vs(pid, {"steps": ["x=2"]})]
        code = cli.main(["--stream", "--no-dedup"], stream_fn=_stream_runner(rows))
        assert code == 0
        captured = capsys.readouterr()
        assert len([ln for ln in captured.out.splitlines() if ln]) == 2
        assert json.loads(captured.err) == {
            "total_input": 2,
            "records": 2,
            "excluded_unverified": 0,
            "deduped": 0,
            "problems_missing": 0,
            "conditions_gated": 0,
        }

    def test_stream_empty_summary_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--stream 빈 스트림 → JSONL 0줄·요약 total=0·종료 0."""
        code = cli.main(["--stream"], stream_fn=_stream_runner([]))
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
        assert json.loads(captured.err)["total_input"] == 0


class TestSelfEvolutionExportCliWithProblem:
    """`--with-problem` 옵트인 — 코퍼스 조인 배선(batch=export_fn 플래그·stream=loader 주입)."""

    def test_batch_with_problem_flag_forwarded(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--with-problem → export_fn에 with_problem=True 전달·요약에 problems_missing."""
        pid = uuid.uuid4()
        seen: dict[str, bool] = {}
        ds = build_sft_dataset([_vs(pid, {"s": 1})])
        code = cli.main(["--with-problem"], export_fn=_runner(ds, seen=seen))
        assert code == 0
        assert seen["with_problem"] is True
        capsys.readouterr()

    def test_stream_with_problem_joins_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--stream --with-problem → 주입 loader로 컨텍스트 결합(question_text)."""
        pid = uuid.uuid4()
        rows = [_vs(pid, {"steps": ["x=2"]})]
        code = cli.main(
            ["--stream", "--with-problem"],
            stream_fn=_stream_runner(rows),
            problem_loader=_loader_for({pid: _problem(pid, question_text="조인된 본문")}),
        )
        assert code == 0
        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln]
        assert json.loads(lines[0])["question_text"] == "조인된 본문"
        assert json.loads(captured.err)["problems_missing"] == 0

    def test_stream_with_problem_missing_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--stream --with-problem + 코퍼스 미존재 → 컨텍스트 None·problems_missing 집계."""
        pid = uuid.uuid4()
        rows = [_vs(pid, {"steps": ["x=2"]})]
        code = cli.main(
            ["--stream", "--with-problem"],
            stream_fn=_stream_runner(rows),
            problem_loader=_loader_for({}),  # 항상 None
        )
        assert code == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out.splitlines()[0])["question_text"] is None
        assert json.loads(captured.err)["problems_missing"] == 1

    def test_stream_with_problem_restricted_source_gates_conditions(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--stream --with-problem + 제한 출처 → conditions null·conditions_gated 집계(저작권)."""
        pid = uuid.uuid4()
        rows = [_vs(pid, {"steps": ["x=2"]})]
        restricted = _problem(
            pid,
            source_type=SourceType.평가원,
            conditions_parsed=[{"label": "가", "text": "f(x) 미분가능", "formal": None}],
        )
        code = cli.main(
            ["--stream", "--with-problem"],
            stream_fn=_stream_runner(rows),
            problem_loader=_loader_for({pid: restricted}),
        )
        assert code == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out.splitlines()[0])["conditions"] is None  # 제한 출처 억제
        assert json.loads(captured.err)["conditions_gated"] == 1
