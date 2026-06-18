"""WH-S 자기 진화 변환 코어(`whs/self_evolution.py`) — 순수(hermetic·DB 0).

`to_sft_record`(필드 매핑)·`build_sft_dataset`(verified만 R-S2 심층 방어·`(problem_id, 지문)`
재발견 dedup·정직 집계·입력 순서 보존)를 검증한다. DB·세션 없이 `VerifiedSolution`을 직접 구성.
"""

from __future__ import annotations

import uuid

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs.self_evolution import (
    SftRecord,
    build_sft_dataset,
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
