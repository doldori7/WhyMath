"""오개념 수치평가 MC 배치 CLI — 결정론·수율·라운드트립·상시 재검증(hermetic·LLM 0).

핵심 봉인: ① 14 서브밴드 전량 게이트 통과(수율 100%) ② JSONL 산출물이 로더로 되읽히며 객관식
필드(choices·distractor_map·answer_map)가 보존된다(라운드트립) ③ 같은 인자 재실행 = 바이트 동일
(결정론) ④ 산출 코퍼스가 S6 전수 재검증을 실패 0으로 통과한다 ⑤ 주입 무결성(kebab 역참조 fail-fast).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness import corpus_reverify as cr
from whymath_backend.harness.misconception_mc_batch import (
    build_kebab_distractor_codes,
    build_kebab_distractor_codes_optional,
    main,
    run_misconception_mc_batch,
)
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records

_BANDS = (
    "distribution-over-power",
    "chain-rule-inner-derivative-omitted",
    "sine-distributes-over-sum",
    "exponent-zero",
    "square-root-positivity",
    "log-distribution",
    "composite-function-commutes",
    "period-of-scaled-sine",
    "translation-sign-flip",
    "product-rule-naive",
    "fraction-cancellation",
    "angle-sum-non-triangle",
    "area-perimeter-confusion",
    "circle-radius-squared",
    "gambler-fallacy",
)
_TOTAL = 24 * len(_BANDS)  # 15 밴드 × 24 = 360


class TestRunMisconceptionMcBatch:
    def test_dry_run_full_yield(self) -> None:
        # 전 서브밴드 dry-run — 전량 저장(수율 100%)·파일 미기록.
        report = run_misconception_mc_batch(
            n_per_band=24,
            out_path=Path("/nonexistent/never-written.jsonl"),
            write=False,
        )
        assert report.fulfilled
        assert report.written is None
        assert [(b.name, b.requested, b.stored) for b in report.bands] == [
            (name, 24, 24) for name in _BANDS
        ]
        assert all(b.failure_reasons == [] for b in report.bands)

    def test_written_corpus_roundtrips_mc_fields(self, tmp_path: Path) -> None:
        # JSONL 산출물이 로더로 되읽히고 객관식 필드가 보존된다(선지·오답 주입·검산 재료).
        out = tmp_path / "problems.jsonl"
        report = run_misconception_mc_batch(n_per_band=24, out_path=out, write=True)
        assert report.fulfilled and report.written == _TOTAL

        records = load_problem_bank_records(out)
        assert len(records) == _TOTAL
        kebabs_seen: set[str] = set()
        for record in records:
            problem = record.problem
            assert problem.choices is not None and len(problem.choices) == 4
            assert problem.answer in problem.choices
            assert (
                problem.distractor_map is not None and len(problem.distractor_map) == 1
            )
            entry = problem.distractor_map[0]
            kebabs_seen.add(entry.misconception_id)
            assert record.verify.answer_selection is None
            assert record.verify.answer_aggregate is None
            assert record.verify.answer_map == {"x": problem.answer}
        assert kebabs_seen == set(_BANDS)  # 14 오개념 모두 태깅됨

    def test_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        # 결정론 봉인 — 같은 인자 두 번 실행 = 바이트 동일(타임스탬프·uuid4·난수 오염 0).
        a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
        run_misconception_mc_batch(n_per_band=24, out_path=a, write=True)
        run_misconception_mc_batch(n_per_band=24, out_path=b, write=True)
        assert a.read_bytes() == b.read_bytes()

    def test_written_corpus_passes_s6_reverify(self, tmp_path: Path) -> None:
        # 상시 재검증(S6) — 산출 코퍼스를 전수 재검산해 실패 0(콘텐츠 무결성 증명).
        out = tmp_path / "problems.jsonl"
        run_misconception_mc_batch(n_per_band=24, out_path=out, write=True)
        records = cr._iter_records(out.read_text(encoding="utf-8"))
        report = cr.reverify_corpus(records, use_fuzz=False)
        assert report.failed == 0
        assert report.passed == _TOTAL  # 전건 pass(skip 없음)


class TestInjectionIntegrity:
    def test_build_codes_shape(self) -> None:
        codes = build_kebab_distractor_codes("distribution-over-power")
        assert codes == {
            "distribution-over-power": (
                "distribution-over-power",
                "power-distributed-no-cross-term",
            )
        }

    def test_unknown_kebab_fails_fast(self) -> None:
        with pytest.raises(KeyError):
            build_kebab_distractor_codes("no-such-misconception")

    def test_optional_builder_none_op_code_for_new_kebab(self) -> None:
        # op-code 부재 신규 오개념 — 옵셔널 빌더는 op_code=None을 담고 실패하지 않는다.
        codes = build_kebab_distractor_codes_optional("exponent-zero")
        assert codes == {"exponent-zero": ("exponent-zero", None)}

    def test_optional_builder_keeps_op_code_when_present(self) -> None:
        # op-code 실재 밴드는 옵셔널 빌더도 그대로 담아 strict 빌더와 정합(기존 3밴드 무변경).
        assert build_kebab_distractor_codes_optional(
            "distribution-over-power"
        ) == build_kebab_distractor_codes("distribution-over-power")

    def test_optional_builder_unknown_kebab_fails_fast(self) -> None:
        with pytest.raises(KeyError):
            build_kebab_distractor_codes_optional("no-such-misconception")


class TestCliEntry:
    def test_main_exit_0_and_report_json(self, tmp_path: Path, capsys: object) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--n", "24", "--out", str(out)])
        assert code == 0
        assert out.exists()
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert report["fulfilled"] is True
        assert report["total_stored"] == _TOTAL
        assert [b["name"] for b in report["bands"]] == list(_BANDS)

    def test_main_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--n", "24", "--out", str(out), "--dry-run"])
        assert code == 0
        assert not out.exists()
