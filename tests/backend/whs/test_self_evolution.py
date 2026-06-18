"""WH-S 자기 진화 변환 코어(`whs/self_evolution.py`) — 순수(hermetic·DB 0).

`to_sft_record`(필드 매핑)·`build_sft_dataset`(verified만 R-S2 심층 방어·`(problem_id, 지문)`
재발견 dedup·정직 집계·입력 순서 보존)를 검증한다. DB·세션 없이 `VerifiedSolution`을 직접 구성.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs.self_evolution import (
    SftRecord,
    SftStreamAccounting,
    build_sft_dataset,
    iter_sft_jsonl,
    stream_sft_jsonl,
    to_sft_record,
)


def _vs(
    *,
    problem_id: uuid.UUID,
    grade: WhsSolutionGrade = WhsSolutionGrade.VERIFIED,
    solution_path: dict | None = None,
    strategy_tag: str | None = None,
    answer: str | None = None,
) -> VerifiedSolution:
    return VerifiedSolution(
        problem_id=problem_id,
        grade=grade,
        solution_path=solution_path if solution_path is not None else {"steps": ["x=2"]},
        strategy_tag=strategy_tag,
        answer=answer,
    )


class TestToSftRecord:
    def test_maps_learning_signal_fields(self) -> None:
        """학습신호 필드(problem_id·solution_path·strategy_tag·answer)만 그대로 매핑."""
        pid = uuid.uuid4()
        rec = to_sft_record(
            _vs(
                problem_id=pid,
                solution_path={"conditions": ["x**2=4"], "answer": {"x": "2"}, "steps": ["x=2"]},
                strategy_tag="대수적",
                answer="2",
            )
        )
        assert isinstance(rec, SftRecord)
        assert rec.problem_id == pid
        assert rec.solution_path == {
            "conditions": ["x**2=4"],
            "answer": {"x": "2"},
            "steps": ["x=2"],
        }
        assert rec.strategy_tag == "대수적"
        assert rec.answer == "2"

    def test_optional_fields_default_none(self) -> None:
        rec = to_sft_record(_vs(problem_id=uuid.uuid4()))
        assert rec.strategy_tag is None and rec.answer is None

    def test_record_is_frozen(self) -> None:
        """SftRecord는 frozen — 적재 후 변경 불가(데이터셋 불변성)."""
        rec = to_sft_record(_vs(problem_id=uuid.uuid4()))
        try:
            rec.answer = "바꿈"  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "immutable" in str(exc).lower()
        else:
            raise AssertionError("frozen 모델이 변경을 허용했다")


class TestBuildSftDataset:
    def test_verified_only_excludes_unverified(self) -> None:
        """verified만 레코드화 — unverified는 배제하고 excluded_unverified로 정직 집계(R-S2)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"s": 1}),
                _vs(problem_id=pid, grade=WhsSolutionGrade.UNVERIFIED, solution_path={"s": 2}),
                _vs(problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"s": 3}),
            ]
        )
        assert ds.size == 2
        assert ds.total_input == 3
        assert ds.excluded_unverified == 1
        assert ds.deduped == 0
        assert all(isinstance(r, SftRecord) for r in ds.records)

    def test_dedup_same_problem_same_path_collapses(self) -> None:
        """같은 문제·같은 지문(키 순서 무관) 재발견은 1건만 — deduped로 집계."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"], "k": 1}),
                _vs(
                    problem_id=pid, solution_path={"k": 1, "steps": ["x=2"]}
                ),  # 같은 내용·순서만 다름
            ]
        )
        assert ds.size == 1
        assert ds.deduped == 1
        assert ds.total_input == 2

    def test_dedup_same_path_different_problem_kept(self) -> None:
        """*다른 문제*의 우연히 같은 경로는 보존(키=(problem_id, 지문))."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=p1, solution_path={"steps": ["x=2"]}),
                _vs(problem_id=p2, solution_path={"steps": ["x=2"]}),
            ]
        )
        assert ds.size == 2 and ds.deduped == 0

    def test_dedup_different_path_kept(self) -> None:
        """같은 문제라도 경로가 다르면 둘 다 보존(다중 전략)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}, strategy_tag="대수적"),
                _vs(problem_id=pid, solution_path={"steps": ["기하"]}, strategy_tag="기하적"),
            ]
        )
        assert ds.size == 2 and ds.deduped == 0

    def test_dedup_disabled_keeps_duplicates(self) -> None:
        """dedup=False → 동일 경로라도 모두 보존(deduped=0·조회 안 함)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}),
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}),
            ],
            dedup=False,
        )
        assert ds.size == 2 and ds.deduped == 0

    def test_preserves_input_order(self) -> None:
        """결정론 — 입력 순서를 보존한다(verified·dedup 통과분)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=pid, solution_path={"n": 1}),
                _vs(problem_id=pid, solution_path={"n": 2}),
                _vs(problem_id=pid, solution_path={"n": 3}),
            ]
        )
        assert [r.solution_path["n"] for r in ds.records] == [1, 2, 3]

    def test_empty_input(self) -> None:
        ds = build_sft_dataset([])
        assert ds.size == 0
        assert ds.total_input == 0
        assert ds.excluded_unverified == 0
        assert ds.deduped == 0


class TestIterSftJsonl:
    def test_one_line_per_record_each_parses(self) -> None:
        """레코드/줄 JSONL — 줄 수 == size·각 줄 JSON 파싱 가능·필드 보존."""
        pid = uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(
                    problem_id=pid,
                    solution_path={"steps": ["x=2"]},
                    strategy_tag="대수적",
                    answer="2",
                ),
                _vs(problem_id=pid, solution_path={"steps": ["기하"]}, strategy_tag="기하적"),
            ]
        )
        lines = list(iter_sft_jsonl(ds))
        assert len(lines) == ds.size == 2
        first = json.loads(lines[0])
        assert first["problem_id"] == str(pid)  # UUID → 문자열
        assert first["solution_path"] == {"steps": ["x=2"]}
        assert first["strategy_tag"] == "대수적" and first["answer"] == "2"

    def test_preserves_record_order(self) -> None:
        """JSONL 줄 순서 = 레코드 순서(결정론)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset([_vs(problem_id=pid, solution_path={"n": i}) for i in range(3)])
        ns = [json.loads(line)["solution_path"]["n"] for line in iter_sft_jsonl(ds)]
        assert ns == [0, 1, 2]

    def test_empty_dataset_no_lines(self) -> None:
        assert list(iter_sft_jsonl(build_sft_dataset([]))) == []


async def _aiter(items: list[VerifiedSolution]) -> AsyncIterator[VerifiedSolution]:
    """리스트를 한 건씩 흘리는 async 이터레이터(stream_all_verified 흉내·DB 없음)."""
    for item in items:
        yield item


def _run_stream(
    items: list[VerifiedSolution], *, dedup: bool = True
) -> tuple[list[str], SftStreamAccounting]:
    """stream_sft_jsonl을 구동해 (JSONL 줄 목록, 소진 후 회계)를 돌려준다."""
    accounting = SftStreamAccounting()

    async def _go() -> list[str]:
        return [line async for line in stream_sft_jsonl(_aiter(items), accounting, dedup=dedup)]

    lines = asyncio.run(_go())
    return lines, accounting


class TestStreamSftJsonl:
    """스트리밍 export — `build_sft_dataset`+`iter_sft_jsonl`와 *동일 불변식*(verified만·dedup·
    순서·정직 회계)을 전량 적재 없이 보존하는지 검증한다."""

    def test_verified_only_excludes_unverified(self) -> None:
        """verified만 JSONL로 흘리고 unverified는 배제·excluded_unverified로 정직 집계(R-S2)."""
        pid = uuid.uuid4()
        lines, acc = _run_stream(
            [
                _vs(problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"s": 1}),
                _vs(problem_id=pid, grade=WhsSolutionGrade.UNVERIFIED, solution_path={"s": 2}),
                _vs(problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"s": 3}),
            ]
        )
        assert len(lines) == 2  # verified 2건만
        assert acc.records == 2
        assert acc.total_input == 3
        assert acc.excluded_unverified == 1
        assert acc.deduped == 0
        assert [json.loads(ln)["solution_path"]["s"] for ln in lines] == [1, 3]

    def test_dedup_same_problem_same_path_collapses(self) -> None:
        """같은 문제·같은 지문(키 순서 무관) 재발견은 1줄만 — deduped로 집계."""
        pid = uuid.uuid4()
        lines, acc = _run_stream(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"], "k": 1}),
                _vs(problem_id=pid, solution_path={"k": 1, "steps": ["x=2"]}),  # 내용 동일
            ]
        )
        assert len(lines) == 1 and acc.records == 1
        assert acc.deduped == 1 and acc.total_input == 2

    def test_dedup_same_path_different_problem_kept(self) -> None:
        """*다른 문제*의 우연히 같은 경로는 보존(키=(problem_id, 지문))."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        lines, acc = _run_stream(
            [
                _vs(problem_id=p1, solution_path={"steps": ["x=2"]}),
                _vs(problem_id=p2, solution_path={"steps": ["x=2"]}),
            ]
        )
        assert len(lines) == 2 and acc.records == 2 and acc.deduped == 0

    def test_dedup_different_path_kept(self) -> None:
        """같은 문제라도 경로가 다르면 둘 다 보존(다중 전략)."""
        pid = uuid.uuid4()
        lines, acc = _run_stream(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}),
                _vs(problem_id=pid, solution_path={"steps": ["기하"]}),
            ]
        )
        assert len(lines) == 2 and acc.deduped == 0

    def test_dedup_disabled_keeps_duplicates(self) -> None:
        """dedup=False → 동일 경로라도 모두 흘림(deduped=0)."""
        pid = uuid.uuid4()
        lines, acc = _run_stream(
            [
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}),
                _vs(problem_id=pid, solution_path={"steps": ["x=2"]}),
            ],
            dedup=False,
        )
        assert len(lines) == 2 and acc.records == 2 and acc.deduped == 0

    def test_preserves_input_order(self) -> None:
        """결정론 — 입력 순서를 보존한다(verified·dedup 통과분)."""
        pid = uuid.uuid4()
        lines, _ = _run_stream([_vs(problem_id=pid, solution_path={"n": i}) for i in range(3)])
        assert [json.loads(ln)["solution_path"]["n"] for ln in lines] == [0, 1, 2]

    def test_jsonl_matches_batch_path(self) -> None:
        """스트리밍 JSONL은 일괄 경로(build_sft_dataset+iter_sft_jsonl)와 바이트 동일."""
        pid = uuid.uuid4()
        items = [
            _vs(
                problem_id=pid, solution_path={"steps": ["x=2"]}, strategy_tag="대수적", answer="2"
            ),
            _vs(problem_id=pid, solution_path={"steps": ["기하"]}, strategy_tag="기하적"),
        ]
        lines, _ = _run_stream(items)
        batch = list(iter_sft_jsonl(build_sft_dataset(items)))
        assert lines == batch  # 동일 직렬화(일괄/스트리밍 등가)

    def test_empty_stream(self) -> None:
        """빈 스트림 → 0줄·회계 전부 0."""
        lines, acc = _run_stream([])
        assert lines == []
        assert acc.summary() == {
            "total_input": 0,
            "records": 0,
            "excluded_unverified": 0,
            "deduped": 0,
        }

    def test_summary_shape_matches_cli_keys(self) -> None:
        """summary()는 일괄 CLI stderr 요약과 동일 키·값을 낸다."""
        pid = uuid.uuid4()
        _, acc = _run_stream(
            [
                _vs(problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"s": 1}),
                _vs(problem_id=pid, grade=WhsSolutionGrade.UNVERIFIED, solution_path={"s": 2}),
                _vs(problem_id=pid, solution_path={"s": 1}),  # 같은 문제·같은 지문 재발견(dedup)
            ]
        )
        assert acc.summary() == {
            "total_input": 3,
            "records": 1,
            "excluded_unverified": 1,
            "deduped": 1,
        }
