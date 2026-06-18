"""WH-S 자기 진화 변환 코어(`whs/self_evolution.py`) — 순수(hermetic·DB 0).

`to_sft_record`(필드 매핑)·`build_sft_dataset`(verified만 R-S2 심층 방어·`(problem_id, 지문)`
재발견 dedup·정직 집계·입력 순서 보존)를 검증한다. DB·세션 없이 `VerifiedSolution`을 직접 구성.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from whymath_backend.db.models.problem import Problem
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


def _problem(
    problem_id: uuid.UUID,
    *,
    question_text: str | None = "다음 방정식을 풀어라.",
    unit_codes: tuple[str, ...] = ("M1-A-01",),
) -> Problem:
    """transient Problem(세션 미부착) — to_sft_record가 읽는 question_text·unit_codes만 채운다."""
    return Problem(problem_id=problem_id, question_text=question_text, unit_codes=list(unit_codes))


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
    items: list[VerifiedSolution],
    *,
    dedup: bool = True,
    problem_loader: Any = None,
) -> tuple[list[str], SftStreamAccounting]:
    """stream_sft_jsonl을 구동해 (JSONL 줄 목록, 소진 후 회계)를 돌려준다."""
    accounting = SftStreamAccounting()

    async def _go() -> list[str]:
        return [
            line
            async for line in stream_sft_jsonl(
                _aiter(items), accounting, dedup=dedup, problem_loader=problem_loader
            )
        ]

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
            "problems_missing": 0,
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
            "problems_missing": 0,  # 문제 조인 안 함 → 0
        }


def _make_loader(mapping: dict[uuid.UUID, Problem], *, calls: list[uuid.UUID]) -> Any:
    """가짜 async problem_loader — 호출 인자를 calls에 기록(단일 캐시 호출수 검증용)."""

    async def _loader(problem_id: uuid.UUID) -> Problem | None:
        calls.append(problem_id)
        return mapping.get(problem_id)

    return _loader


class TestProblemContextJoin:
    """문제 본문 조인(opt-in) — to_sft_record·build_sft_dataset(map)·stream(loader)."""

    def test_to_sft_record_embeds_problem(self) -> None:
        """problem 주면 question_text·unit_codes 임베드(tuple)."""
        pid = uuid.uuid4()
        rec = to_sft_record(
            _vs(problem_id=pid),
            _problem(pid, question_text="x를 구하라.", unit_codes=("M1-A-01", "M1-A-02")),
        )
        assert rec.question_text == "x를 구하라."
        assert rec.unit_codes == ("M1-A-01", "M1-A-02")

    def test_to_sft_record_without_problem_is_none(self) -> None:
        """problem 미제공 → 두 컨텍스트 필드 None(하위호환)."""
        rec = to_sft_record(_vs(problem_id=uuid.uuid4()))
        assert rec.question_text is None and rec.unit_codes is None

    def test_to_sft_record_honest_null_body(self) -> None:
        """본문 미보유 출처(question_text=None)는 None 그대로 임베드(날조 0)·unit_codes는 채움."""
        pid = uuid.uuid4()
        rec = to_sft_record(_vs(problem_id=pid), _problem(pid, question_text=None))
        assert rec.question_text is None
        assert rec.unit_codes == ("M1-A-01",)

    def test_build_with_problem_map_joins(self) -> None:
        """problem_map 결합 — verified 레코드에 컨텍스트 채움·problems_missing=0."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=p1, solution_path={"s": 1}),
                _vs(problem_id=p2, solution_path={"s": 2}),
            ],
            problem_map={
                p1: _problem(p1, question_text="첫째"),
                p2: _problem(p2, question_text="둘째"),
            },
        )
        assert ds.size == 2 and ds.problems_missing == 0
        assert {r.question_text for r in ds.records} == {"첫째", "둘째"}

    def test_build_with_problem_map_missing_counts(self) -> None:
        """map에 없는 problem_id → 컨텍스트 None·problems_missing 집계·레코드는 보존(NO_DATA)."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        ds = build_sft_dataset(
            [
                _vs(problem_id=p1, solution_path={"s": 1}),
                _vs(problem_id=p2, solution_path={"s": 2}),  # map에 없음
            ],
            problem_map={p1: _problem(p1)},
        )
        assert ds.size == 2  # 둘 다 보존(verified는 안 버림)
        assert ds.problems_missing == 1
        missing = [r for r in ds.records if r.problem_id == p2][0]
        assert missing.question_text is None and missing.unit_codes is None

    def test_build_no_problem_map_missing_zero(self) -> None:
        """problem_map 미제공 → 컨텍스트 None·problems_missing 0(조인 안 함)."""
        pid = uuid.uuid4()
        ds = build_sft_dataset([_vs(problem_id=pid)])
        assert ds.problems_missing == 0
        assert ds.records[0].question_text is None

    def test_stream_loader_single_cache_one_call_per_problem(self) -> None:
        """그룹 정렬 스트림 — problem_id가 바뀔 때만 loader 1회(단일 캐시·O(distinct))."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        items = [
            _vs(problem_id=p1, solution_path={"s": 1}),
            _vs(problem_id=p1, solution_path={"s": 2}),  # 같은 문제 연속 — 재조회 안 함
            _vs(problem_id=p2, solution_path={"s": 3}),
        ]
        calls: list[uuid.UUID] = []
        loader = _make_loader(
            {p1: _problem(p1, question_text="P1"), p2: _problem(p2, question_text="P2")},
            calls=calls,
        )
        lines, acc = _run_stream(items, problem_loader=loader)
        assert [json.loads(ln)["question_text"] for ln in lines] == ["P1", "P1", "P2"]
        assert calls == [p1, p2]  # 문제당 1회(연속 같은 문제는 캐시)
        assert acc.problems_missing == 0

    def test_stream_loader_missing_counts(self) -> None:
        """loader가 None(코퍼스 미존재) → 컨텍스트 None·problems_missing 집계(NO_DATA)."""
        p1 = uuid.uuid4()
        calls: list[uuid.UUID] = []
        loader = _make_loader({}, calls=calls)  # 항상 None
        lines, acc = _run_stream(
            [_vs(problem_id=p1, solution_path={"s": 1})], problem_loader=loader
        )
        assert json.loads(lines[0])["question_text"] is None
        assert acc.problems_missing == 1 and calls == [p1]
