"""코퍼스 축적 배치(problem_corpus_accumulate) 단위테스트 — 회차 간 dedup·증분 append(hermetic).

라이브 스모크(2026-07-07)에서 확인된 갭(회차마다 fresh index·전면 교체)이 상환됨을 결정론
스켈레톤 생성기 주입으로 검증한다(LLM 0). 스켈레톤 풀은 고정 시드라 fresh 생성기가 매번 같은
순서로 후보를 내므로, 시드/축적분과의 구조 중복이 재현 가능하게 발생한다 — dedup 검증에 이상적.
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.problem_corpus_accumulate import (
    load_corpus_index,
    main,
    run_corpus_accumulate,
)
from whymath_backend.harness.problem_corpus_batch import run_corpus_batch
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.skeleton_generator import SkeletonEquivalentProblemGenerator

_STANDARD = "[10공수1-02-02]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.5,
        answer_format=None,
    )


def _seed_corpus(tmp_path: Path, short_n: int = 6) -> Path:
    """소형 결정론 시드 코퍼스 — 스켈레톤 배치의 quad 단답형 밴드만."""
    src = tmp_path / "seed.jsonl"
    report = run_corpus_batch(
        out_path=src,
        short_n=short_n,
        mc_n=0,
        sqrt_n=0,
        sqrt_mc_n=0,
        calc_extremum_n=0,
        calc_tangent_n=0,
        calc_value_n=0,
        calc_value_mc_n=0,
        calc_extremum_irr_n=0,
        exp_n=0,
        log_n=0,
        arith_n=0,
        geo_n=0,
        trig_n=0,
        write=True,
    )
    assert report.fulfilled
    return src


class TestLoadCorpusIndex:
    def test_loads_signatures_and_slugs(self, tmp_path: Path) -> None:
        seed = _seed_corpus(tmp_path, short_n=6)
        signatures, slugs, total = load_corpus_index([seed])
        assert total == 6
        assert len(slugs) == 6
        assert len(signatures) == 6  # quad는 다항이라 전건 정규화 가능

    def test_missing_path_skipped(self, tmp_path: Path) -> None:
        signatures, slugs, total = load_corpus_index([tmp_path / "nope.jsonl"])
        assert (signatures, slugs, total) == (set(), set(), 0)


class TestRunCorpusAccumulate:
    def test_seed_structures_are_deduped_and_fresh_appended(self, tmp_path: Path) -> None:
        # 시드 6건과 같은 풀 순서의 fresh 생성기 → 앞 6회는 회차 간 dedup, 뒤 4회만 신규 append.
        seed = _seed_corpus(tmp_path, short_n=6)
        out = tmp_path / "accumulated.jsonl"
        report = run_corpus_accumulate(
            out_path=out,
            seed_paths=[seed],
            generator=SkeletonEquivalentProblemGenerator(),
            spec=_spec(),
            n=10,
        )
        assert report.seed_records == 6
        assert report.existing_out_records == 0
        assert report.outcome_counts.get("rejected_duplicate", 0) == 6  # 시드 구조 전부 차단
        assert report.accepted == 4
        assert report.appended == 4
        assert report.reason_sample  # 미수용 사유 관측(조용한 실패 금지)
        assert len(load_problem_bank_records(out)) == 4

    def test_second_run_appends_incrementally(self, tmp_path: Path) -> None:
        # 회차 2: 시드 6 + 축적 4가 전부 index에 실려 앞 10회 dedup → 신규 2만 증분 append.
        seed = _seed_corpus(tmp_path, short_n=6)
        out = tmp_path / "accumulated.jsonl"
        run_corpus_accumulate(
            out_path=out,
            seed_paths=[seed],
            generator=SkeletonEquivalentProblemGenerator(),
            spec=_spec(),
            n=10,
        )
        report = run_corpus_accumulate(
            out_path=out,
            seed_paths=[seed],
            generator=SkeletonEquivalentProblemGenerator(),
            spec=_spec(),
            n=12,
        )
        assert report.existing_out_records == 4
        assert report.outcome_counts.get("rejected_duplicate", 0) == 10
        assert report.accepted == 2
        assert report.appended == 2
        records = load_problem_bank_records(out)
        assert len(records) == 6  # 4 + 2 증분(전면 교체 아님)
        slugs = [r.slug for r in records]
        assert len(slugs) == len(set(slugs))  # 축적분 내 slug 유일

    def test_appended_records_roundtrip_and_disjoint_from_seed(self, tmp_path: Path) -> None:
        seed = _seed_corpus(tmp_path, short_n=6)
        out = tmp_path / "accumulated.jsonl"
        run_corpus_accumulate(
            out_path=out,
            seed_paths=[seed],
            generator=SkeletonEquivalentProblemGenerator(),
            spec=_spec(),
            n=10,
        )
        seed_slugs = {r.slug for r in load_problem_bank_records(seed)}
        out_slugs = {r.slug for r in load_problem_bank_records(out)}
        assert out_slugs.isdisjoint(seed_slugs)  # 시드와 중복 0(회차 간 dedup 실증)

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        seed = _seed_corpus(tmp_path, short_n=3)
        out = tmp_path / "accumulated.jsonl"
        report = run_corpus_accumulate(
            out_path=out,
            seed_paths=[seed],
            generator=SkeletonEquivalentProblemGenerator(),
            spec=_spec(),
            n=5,
            write=False,
        )
        assert report.appended == 0
        assert not out.exists()


class TestCliEntry:
    def test_main_without_live_llm_exits_1(self, tmp_path: Path, capsys: object) -> None:
        # 라이브 LLM 없음(이 환경) → 생성기 안전 폴백 → 전건 generation_failed → 무진전 exit 1.
        seed = _seed_corpus(tmp_path, short_n=3)
        out = tmp_path / "accumulated.jsonl"
        code = main(["--seed", str(seed), "--out", str(out), "--n", "2"])
        assert code == 1
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert report["appended"] == 0
        assert report["outcome_counts"].get("generation_failed", 0) == 2
