"""자기 진화 SFT export ops CLI(`whs/self_evolution_export_cli.py`) — 단위(hermetic·러너 주입).

DB 없이 CLI *배선*만 검증한다: ① stdout = JSONL 레코드(줄/레코드) ② stderr = 정직 요약 JSON
(total_input·records·excluded_unverified·deduped) ③ `--no-dedup` → dedup=False 전달 ④ 종료 0
(verified 0건도 정상). 실 DB 조회·변환은 solution_bank·self_evolution 테스트가 검증한다(중복 0).
합성 `export_fn`(코루틴, `SftDataset` 반환·dedup 플래그 캡처)을 주입한다.
"""

from __future__ import annotations

import json
import uuid

import pytest

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs import self_evolution_export_cli as cli
from whymath_backend.whs.self_evolution import SftDataset, build_sft_dataset


def _vs(problem_id: uuid.UUID, path: dict, grade: WhsSolutionGrade = WhsSolutionGrade.VERIFIED):  # type: ignore[type-arg]
    return VerifiedSolution(problem_id=problem_id, grade=grade, solution_path=path)


def _runner(dataset: SftDataset, *, seen: dict[str, bool]):  # type: ignore[no-untyped-def]
    async def _export(dedup: bool) -> SftDataset:
        seen["dedup"] = dedup
        return dataset

    return _export


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
