"""rephrase 실패 진단 CLI 단위테스트(hermetic) — 실패 유형별 FakeProvider로 라이브 0.

핵심: 각 실패 유형(EQUATION_ALTERED·EXTRA_EQUATION·EMPTY·NO_CHANGE·성공)을 흉내내는 provider로
① reason-code taxonomy 집계 ② 원 LLM 출력이 실패 케이스에 dump되는지 ③ skeleton 유형별 수율
그룹핑 ④ --dump JSONL 기록 ⑤ provider 미주입 main이 PROVIDER_ERROR로 정직 관측됨을 봉인한다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whymath_backend.harness.problem_corpus_batch import run_corpus_batch
from whymath_backend.harness.problem_corpus_rephrase_diagnose import (
    main,
    run_rephrase_diagnose,
)
from whymath_backend.l3.equivalent.rephrase import (
    REASON_EMPTY,
    REASON_EQUATION_ALTERED,
    REASON_EXTRA_EQUATION,
    REASON_NO_CHANGE,
    REASON_PROVIDER_ERROR,
    QuestionRephraser,
)
from whymath_backend.l3.models import GenerationResult, RoutingDecision


def _base(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("원 발문: "):
            return line[len("원 발문: ") :]
    return "무효"  # pragma: no cover — 프롬프트 형식 보증


class _ScriptedProvider:
    """발문을 고정 규칙으로 변형해 특정 실패 유형을 결정론으로 유발(hermetic 좌석)."""

    def __init__(self, transform: str) -> None:
        self._transform = transform

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        base = _base(prompt)
        if self._transform == "success":
            return GenerationResult(base + " (다양화)")
        if self._transform == "altered":
            # 방정식 substring 소실 → EQUATION_ALTERED.
            return GenerationResult("이차방정식의 근을 구하시오")
        if self._transform == "extra_eq":
            # 방정식 외 추가 등식 → EXTRA_EQUATION.
            return GenerationResult(base + " 참고 2+2=5")
        if self._transform == "empty":
            return GenerationResult("")  # → EMPTY.
        return GenerationResult(base)  # echo → NO_CHANGE.


def _seed_corpus(tmp_path: Path, *, short_n: int = 8, mc_n: int = 4) -> Path:
    src = tmp_path / "src.jsonl"
    report = run_corpus_batch(
        out_path=src,
        short_n=short_n,
        mc_n=mc_n,
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
        arith_sum_n=0,
        geo_sum_n=0,
        trig_eq_n=0,
        seq_inductive_n=0,
        write=True,
    )
    assert report.fulfilled
    return src


def _diagnose(src: Path, transform: str, *, limit: int | None = None, offset: int = 0):
    provider = _ScriptedProvider(transform)
    return run_rephrase_diagnose(
        in_path=src,
        rephraser=QuestionRephraser(provider, temperature=0.7),  # type: ignore[arg-type]
        temperature=0.7,
        limit=limit,
        offset=offset,
    )


class TestRunRephraseDiagnose:
    def test_success_provider_has_no_failures(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "success")
        assert report.attempted == report.rephrased == 12
        assert report.reason_histogram == {}
        assert report.failures == []
        for stat in report.skeleton_stats:
            assert stat.rate == 1.0

    def test_altered_provider_classifies_and_keeps_raw_output(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "altered")
        assert report.rephrased == 0
        assert report.reason_histogram == {REASON_EQUATION_ALTERED: 12}
        assert len(report.failures) == 12
        for case in report.failures:
            assert case.reason_code == REASON_EQUATION_ALTERED
            assert case.rephrased_raw == "이차방정식의 근을 구하시오"  # 원 LLM 출력 보존.
            assert case.original  # 원문도 함께 기록.

    def test_extra_equation_classified(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "extra_eq")
        assert report.reason_histogram == {REASON_EXTRA_EQUATION: 12}

    def test_empty_output_classified(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "empty")
        assert report.reason_histogram == {REASON_EMPTY: 12}
        assert all(case.rephrased_raw == "" for case in report.failures)

    def test_echo_output_is_no_change(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "echo")
        assert report.reason_histogram == {REASON_NO_CHANGE: 12}

    def test_skeleton_stats_group_by_type(self, tmp_path: Path) -> None:
        # short(단답형)·mc(객관식)는 발문형식이 달라 skeleton 키가 갈린다.
        report = _diagnose(_seed_corpus(tmp_path, short_n=8, mc_n=4), "success")
        keys = {stat.skeleton_key for stat in report.skeleton_stats}
        assert len(keys) >= 2  # 최소 단답형·객관식 2유형.
        assert sum(stat.attempted for stat in report.skeleton_stats) == report.attempted

    def test_limit_caps_attempts(self, tmp_path: Path) -> None:
        report = _diagnose(_seed_corpus(tmp_path), "altered", limit=5)
        assert report.attempted == 5
        assert report.limit == 5
        assert len(report.failures) == 5

    def test_offset_skips_leading_records(self, tmp_path: Path) -> None:
        # 앞 offset건 건너뛰기 — 뒤쪽 밴드(지수·로그) 저비용 타게팅(quad 재실행 회피).
        src = _seed_corpus(tmp_path)  # 12건
        full = _diagnose(src, "success")
        tail = _diagnose(src, "success", offset=8)
        assert full.attempted == 12
        assert tail.attempted == 4  # 앞 8건 건너뜀 → 남은 4건만 시도.
        assert tail.total == 4  # 처리 창 크기.


class TestCliEntry:
    def test_dump_writes_failures_jsonl(
        self, tmp_path: Path, capsys: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # provider 차단 main → 전건 PROVIDER_ERROR(환경 무관)·그 실패가 dump된다.
        # [OPS-44 사고 경위] "라이브 부재" 전제였으나 Kiki 머신은 Ollama가 상시 기동이라 실제
        # 변형이 일어나 깨졌다 — provider 해소를 예외로 강제 차단해 전제를 코드로 봉인.
        def _blocked(self: QuestionRephraser) -> None:
            raise RuntimeError("테스트 강제 차단 — 라이브 provider 해소 금지")

        monkeypatch.setattr(QuestionRephraser, "_resolve_provider", _blocked)
        src = _seed_corpus(tmp_path)
        dump = tmp_path / "failures.jsonl"
        # provider 미주입 main → 전건 PROVIDER_ERROR(라이브 부재)·그 실패가 dump된다.
        code = main(["--in", str(src), "--limit", "4", "--dump", str(dump), "--json"])
        assert code == 0
        assert dump.exists()
        rows = [json.loads(line) for line in dump.read_text(encoding="utf-8").splitlines() if line]
        assert len(rows) == 4
        for row in rows:
            assert row["reason_code"] == REASON_PROVIDER_ERROR
            assert set(row) == {
                "slug",
                "temperature",
                "reason_code",
                "skeleton_key",
                "original",
                "rephrased_raw",
            }
        report = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
        assert report["reason_histogram"] == {REASON_PROVIDER_ERROR: 4}

    def test_main_summary_output(self, tmp_path: Path, capsys: object) -> None:
        src = _seed_corpus(tmp_path)
        code = main(["--in", str(src), "--limit", "3"])
        assert code == 0
        out = capsys.readouterr().out  # type: ignore[attr-defined]
        assert "reason-code" in out and "skeleton 유형별 수율" in out

    def test_main_offset_reaches_tail(self, tmp_path: Path, capsys: object) -> None:
        src = _seed_corpus(tmp_path)  # 12건
        code = main(["--in", str(src), "--offset", "10", "--json"])
        assert code == 0
        report = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
        assert report["total"] == 2  # 앞 10건 건너뜀 → 처리 창 2건.
        assert report["attempted"] == 2

    def test_main_rejects_negative_offset(self, tmp_path: Path) -> None:
        import pytest

        src = _seed_corpus(tmp_path)
        with pytest.raises(SystemExit):
            main(["--in", str(src), "--offset", "-1"])
