"""동등문제 코퍼스 배치 CLI(S2-p) — 조성 루트·JSONL 라운드트립·결정론 단위테스트(hermetic).

핵심 봉인: ① 주입 매핑이 L4 정본과 정합(fail-fast) ② JSONL이 로더(`load_problem_bank_records`)
로 정확히 되읽힌다(라운드트립) ③ 같은 인자 재실행이 *바이트까지* 동일(결정론) ④ 수율 미달이면
종료 코드 1(조용한 실패 금지).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.problem_corpus_batch import (
    build_distractor_codes,
    main,
    run_corpus_batch,
)
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import DISTRACTOR_BY_ID


class TestBuildDistractorCodes:
    def test_injection_targets_exist_in_l4_canon(self) -> None:
        # 조성 루트의 참조 무결성 — 주입 id 전부 L4 정본 실재 + op-code↔오개념 정합.
        codes = build_distractor_codes()
        assert set(codes) == {"opposite_root", "sign_flip"}
        for misconception_id, op_code in codes.values():
            assert misconception_id in CATALOG_BY_ID
            assert DISTRACTOR_BY_ID[op_code].misconception_id == misconception_id


class TestRunCorpusBatch:
    def test_dry_run_full_yield(self) -> None:
        # 소형 3밴드 dry-run — 전량 저장(수율 100%)·파일 미기록.
        report = run_corpus_batch(
            out_path=Path("/nonexistent/never-written.jsonl"),
            short_n=5,
            mc_n=3,
            sqrt_n=2,
            write=False,
        )
        assert report.fulfilled
        assert report.written is None
        assert [(b.name, b.requested, b.stored) for b in report.bands] == [
            ("short", 5, 5),
            ("mc", 3, 3),
            ("sqrt", 2, 2),
        ]
        assert all(b.failure_reasons == [] for b in report.bands)

    def test_written_corpus_roundtrips_through_loader(self, tmp_path: Path) -> None:
        # JSONL 산출물이 코퍼스 로더로 정확히 되읽힌다 — 형식·위생·Problem 검증 통과.
        out = tmp_path / "problems.jsonl"
        report = run_corpus_batch(out_path=out, short_n=6, mc_n=4, sqrt_n=3, write=True)
        assert report.fulfilled and report.written == 13

        records = load_problem_bank_records(out)
        assert len(records) == 13
        # 결정론 메타 — 전건 HK06 태깅·난이도 분산(2.5 균일 회귀 차단).
        for record in records:
            assert [t.concept_src_id for t in record.concept_tags] == ["HK06"]
            assert record.problem.difficulty_overall is not None
        assert len({r.problem.difficulty_overall for r in records}) >= 2
        # 객관식 밴드 — 실 L4 id로 distractor 태깅·answer∈choices.
        mc = [r for r in records if r.problem.question_format == "객관식"]
        assert len(mc) == 4
        for record in mc:
            problem = record.problem
            assert problem.choices is not None and problem.answer in problem.choices
            assert problem.distractor_map is not None and len(problem.distractor_map) == 3
            for entry in problem.distractor_map:
                assert entry.misconception_id in CATALOG_BY_ID
        # 무리근 밴드 — SymPy 정확값 answer.
        sqrt_records = [r for r in records if "sqrt(" in (r.problem.answer or "")]
        assert len(sqrt_records) == 3

    def test_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        # 결정론 봉인 — 같은 인자 두 번 실행 = 바이트 동일(타임스탬프·uuid4·난수 오염 0).
        a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
        run_corpus_batch(out_path=a, short_n=5, mc_n=3, sqrt_n=2, write=True)
        run_corpus_batch(out_path=b, short_n=5, mc_n=3, sqrt_n=2, write=True)
        assert a.read_bytes() == b.read_bytes()

    def test_cross_band_signatures_unique(self, tmp_path: Path) -> None:
        # 공유 signature_index — 밴드 간·내 구조 판박이 0(slug도 전건 상이).
        out = tmp_path / "problems.jsonl"
        run_corpus_batch(out_path=out, short_n=8, mc_n=4, sqrt_n=3, write=True)
        slugs = [r.slug for r in load_problem_bank_records(out)]
        assert len(slugs) == len(set(slugs))


class TestCliEntry:
    def test_main_exit_0_and_report_json(self, tmp_path: Path, capsys: object) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--out", str(out), "--short", "4", "--mc", "3", "--sqrt", "2"])
        assert code == 0
        assert out.exists()
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert report["fulfilled"] is True
        assert report["total_stored"] == 9

    def test_main_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--out", str(out), "--short", "2", "--mc", "2", "--sqrt", "2", "--dry-run"])
        assert code == 0
        assert not out.exists()

    def test_main_exit_1_on_pool_exhaustion(self, tmp_path: Path, capsys: object) -> None:
        # 무리근 풀(180)보다 많이 요청 → generation_failed 발생 → 수율 미달 종료 코드 1 + 사유.
        out = tmp_path / "problems.jsonl"
        code = main(["--out", str(out), "--short", "0", "--mc", "0", "--sqrt", "185"])
        assert code == 1
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert report["fulfilled"] is False
        assert report["total_stored"] == 180  # 풀 전수 소진분은 저장(정직 기록)
        sqrt_band = next(b for b in report["bands"] if b["name"] == "sqrt")
        assert sqrt_band["failure_reasons"]  # 조용한 실패 금지 — 사유 존재
