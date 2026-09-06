"""배치 안전장치의 **배선 실재성** 동결 (EOS-95 ④).

`batch_safety` 모듈이 저장소에 존재한다는 것과 배치 루프가 그것을 실제로 부른다는 것은
다르다(CLAUDE.md「정본화를 집행으로 착각한 완료 선언 금지」). 이 파일은 모듈 docstring의
**집행 지점 표가 실물과 일치하는지**를 기계로 대조한다.

특히 "경유하지 않는다"고 적은 두 루프가 나중에 배선되면 이 테스트가 깨진다 — 그때
docstring 표를 갱신하라는 뜻이다. 문서가 실물보다 뒤처지는 것을 막는 장치이며,
**정직한 미배선을 동결하는 것이지 미배선을 정당화하는 것이 아니다.**
"""

from __future__ import annotations

import inspect

from whymath_backend.harness import batch_safety, problem_corpus_accumulate, problem_corpus_batch
from whymath_backend.l3.equivalent import orchestrator


class TestAccumulateIsWired:
    """축적 경로는 실제로 경유한다 — 존재가 아니라 호출을 확인한다."""

    def test_accumulate_imports_the_gate(self) -> None:
        source = inspect.getsource(problem_corpus_accumulate)
        assert "from whymath_backend.harness.batch_safety import" in source

    def test_accumulate_loop_calls_both_guards(self) -> None:
        source = inspect.getsource(problem_corpus_accumulate.run_corpus_accumulate)
        # 카나리 관문과 롤링 감시가 **루프 함수 안에서** 불린다(모듈 어딘가가 아니라).
        assert "evaluate_canary(" in source
        assert "RollingFailureWindow(" in source
        assert "should_abort()" in source

    def test_accumulate_signature_exposes_gate_knobs(self) -> None:
        params = inspect.signature(problem_corpus_accumulate.run_corpus_accumulate).parameters
        for name in (
            "canary_size",
            "canary_threshold",
            "canary_confidence",
            "abort_window",
            "abort_threshold",
        ):
            assert name in params, name

    def test_cli_returns_nonzero_on_gate_trip(self) -> None:
        """CLI가 게이트 판정을 종료 코드로 낸다 — 판정은 exit code로 한다(CLAUDE.md)."""
        source = inspect.getsource(problem_corpus_accumulate.main)
        assert "report.canary_blocked" in source
        assert "report.aborted" in source


class TestDocumentedNonCoverageStaysHonest:
    """docstring이 "경유하지 않는다"고 적은 좌석 — 실제로 그런지 확인한다.

    배선되면 이 테스트가 RED가 되고, 그때 docstring 표를 고치게 된다(있는 척도, 없는
    척도 막는다).
    """

    def test_l3_orchestrator_does_not_import_harness_gate(self) -> None:
        source = inspect.getsource(orchestrator)
        assert "batch_safety" not in source, (
            "L3 orchestrator가 harness.batch_safety를 참조한다 — 계층 역참조이거나, "
            "배선됐다면 batch_safety 모듈 docstring의 집행 지점 표를 갱신해야 한다."
        )

    def test_corpus_batch_does_not_use_the_gate_yet(self) -> None:
        source = inspect.getsource(problem_corpus_batch)
        assert "batch_safety" not in source, (
            "problem_corpus_batch가 배선됐다 — batch_safety 모듈 docstring의 집행 지점 "
            "표에서 '경유하지 않는다'를 고쳐야 한다."
        )


class TestDocstringTableMatchesReality:
    def test_enforcement_table_names_all_three_loops(self) -> None:
        """표가 세 루프를 전부 열거하는지 — 하나라도 빠지면 '있는 척'이 가능해진다."""
        doc = batch_safety.__doc__ or ""
        assert "run_corpus_accumulate" in doc
        assert "orchestrator.py::run_batch" in doc
        assert "problem_corpus_batch.py::run_batch" in doc

    def test_table_states_non_coverage_explicitly(self) -> None:
        doc = batch_safety.__doc__ or ""
        assert "경유하지 않는다" in doc
        assert "아직 보호받지 않는다" in doc
