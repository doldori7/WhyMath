"""근의 합/곱(Vieta) 킬러 배치 CLI — 결정론·수율·라운드트립·상시 재검증(hermetic·LLM 0).

핵심 봉인: ① 4 서브밴드 전량 게이트 통과(수율 100%) ② JSONL 산출물이 로더로 되읽히며
`answer_aggregate`가 보존된다(라운드트립) ③ 같은 인자 재실행 = 바이트 동일(결정론) ④ 같은
조건식의 합·곱이 dedup 충돌 없이 공존한다 ⑤ 산출 코퍼스가 S6 전수 재검증을 실패 0으로 통과한다
(콘텐츠 무결성 = 킬러 문항이 검증 스위트로 보호됨).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness import corpus_reverify as cr
from whymath_backend.harness.root_aggregate_batch import main, run_root_aggregate_batch
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records

_BANDS = ("vieta-sum-quad", "vieta-product-quad", "vieta-sum-cubic", "vieta-product-cubic")


class TestRunRootAggregateBatch:
    def test_dry_run_full_yield(self) -> None:
        # 4 서브밴드 dry-run — 전량 저장(수율 100%)·파일 미기록.
        report = run_root_aggregate_batch(
            n_per_band=5, out_path=Path("/nonexistent/never-written.jsonl"), write=False
        )
        assert report.fulfilled
        assert report.written is None
        assert [(b.name, b.requested, b.stored) for b in report.bands] == [
            ("vieta-sum-quad", 5, 5),
            ("vieta-product-quad", 5, 5),
            ("vieta-sum-cubic", 5, 5),
            ("vieta-product-cubic", 5, 5),
        ]
        assert all(b.failure_reasons == [] for b in report.bands)

    def test_written_corpus_roundtrips_preserving_aggregate(self, tmp_path: Path) -> None:
        # JSONL 산출물이 로더로 되읽히고 verify.answer_aggregate가 보존된다(합/곱 태깅 유지).
        out = tmp_path / "problems.jsonl"
        report = run_root_aggregate_batch(n_per_band=6, out_path=out, write=True)
        assert report.fulfilled and report.written == 24

        records = load_problem_bank_records(out)
        assert len(records) == 24
        aggregates = {r.verify.answer_aggregate for r in records}
        assert aggregates == {"sum", "product"}  # 두 집계 종류 모두 보존
        for record in records:
            assert record.verify.answer_aggregate in ("sum", "product")
            assert record.verify.answer_selection is None  # 집계 문항은 근 선택 없음
            assert record.problem.difficulty_overall == 4.0  # 킬러 난이도
            assert record.problem.distractor_map is None  # 단답 집계라 오답 주입 0
            assert [t.concept_src_id for t in record.concept_tags] == ["HK06"]
            # S3-12 성취기준 재태깅 봉인 — 이차=근과 계수의 관계·삼차=삼차·사차방정식(감사 확정
            # 정위치). 구버전 전밴드 [10공수1-02-02](판별식) 하드코딩이면 여기서 실패한다.
            expected_code = (
                "[10공수1-02-07]" if "x^3" in record.problem.question_text else "[10공수1-02-03]"
            )
            assert record.problem.achievement_standard_codes == [expected_code], record.problem.slug

    def test_sum_and_product_coexist_without_dedup_collision(self, tmp_path: Path) -> None:
        # dedup 정합 봉인 — 같은 조건식(예: x^2+4x-2=0)의 합·곱이 별 signature로 공존한다.
        #   (aggregate payload로 signature를 구분하지 않으면 selection=None이라 충돌·유실.)
        out = tmp_path / "problems.jsonl"
        run_root_aggregate_batch(n_per_band=8, out_path=out, write=True)
        records = load_problem_bank_records(out)
        by_conditions: dict[str, set[str | None]] = {}
        for record in records:
            conditions = record.verify.conditions
            assert isinstance(conditions, str)
            by_conditions.setdefault(conditions, set()).add(record.verify.answer_aggregate)
        # 적어도 한 조건식이 합·곱 둘 다를 갖는다(충돌이면 하나가 유실돼 불가능).
        assert any(aggs == {"sum", "product"} for aggs in by_conditions.values())

    def test_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        # 결정론 봉인 — 같은 인자 두 번 실행 = 바이트 동일(타임스탬프·uuid4·난수 오염 0).
        a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
        run_root_aggregate_batch(n_per_band=7, out_path=a, write=True)
        run_root_aggregate_batch(n_per_band=7, out_path=b, write=True)
        assert a.read_bytes() == b.read_bytes()

    def test_written_corpus_passes_s6_reverify(self, tmp_path: Path) -> None:
        # 상시 재검증(S6) — 산출 킬러 코퍼스를 전수 재검산해 실패 0(콘텐츠 무결성 증명).
        out = tmp_path / "problems.jsonl"
        run_root_aggregate_batch(n_per_band=6, out_path=out, write=True)
        records = cr._iter_records(out.read_text(encoding="utf-8"))
        report = cr.reverify_corpus(records, use_fuzz=False)
        assert report.failed == 0
        assert report.passed == 24  # 근 집계 전건 pass(skip 없음)


class TestCliEntry:
    def test_main_exit_0_and_report_json(self, tmp_path: Path, capsys: object) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--n", "4", "--out", str(out)])
        assert code == 0
        assert out.exists()
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert report["fulfilled"] is True
        assert report["total_stored"] == 16
        assert [b["name"] for b in report["bands"]] == list(_BANDS)

    def test_main_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "problems.jsonl"
        code = main(["--n", "3", "--out", str(out), "--dry-run"])
        assert code == 0
        assert not out.exists()
