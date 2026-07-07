"""rephrase 온도 스윕 CLI 단위테스트(hermetic) — 온도 가변 FakeProvider로 라이브 0.

핵심: 같은 코퍼스 샘플을 여러 온도로 돌려 온도별 변형률을 집계하고, ① 샘플 상한(`limit`)이
온도 간 동일 시도 수를 만들고 ② 변형률이 온도에 대해 단조(높은 온도 ≥ 낮은 온도)이며 ③
write=False라 코퍼스를 쓰지 않고 ④ provider 미주입 main이 fail-closed(변형 0·exit 0)임을 봉인한다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whymath_backend.harness.problem_corpus_batch import run_corpus_batch
from whymath_backend.harness.problem_corpus_rephrase_sweep import (
    main,
    run_rephrase_sweep,
)
from whymath_backend.l3.equivalent.rephrase import QuestionRephraser
from whymath_backend.l3.models import GenerationResult, RoutingDecision


class _TempVaryingProvider:
    """온도가 높을수록 더 많은 발문을 '다양화'하는 결정론 FakeProvider(hermetic).

    각 발문의 sha256 해시(0~99)가 `round(temperature*100)` 미만이면 접미사를 붙여 다양화를
    흉내내고(방정식 보존 → 검증 통과), 아니면 원문 그대로 돌려준다(→ '원문과 동일'로 미변형).
    임계가 온도에 비례하므로 낮은 온도에서 변형된 발문은 높은 온도에서도 반드시 변형된다
    (변형률 단조 — 실 LLM의 '온도↑ → 다양성↑' 경향을 결정론으로 모델).
    """

    @staticmethod
    def _base(prompt: str) -> str:
        for line in prompt.splitlines():
            if line.startswith("원 발문: "):
                return line[len("원 발문: ") :]
        return "무효"  # pragma: no cover — 프롬프트 형식 보증

    @staticmethod
    def _diversifies(question: str, temperature: float) -> bool:
        bucket = int(hashlib.sha256(question.encode("utf-8")).hexdigest(), 16) % 100
        return bucket < round(temperature * 100)

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
        base = self._base(prompt)
        temp = temperature if temperature is not None else 0.9
        text = base + " (다양화)" if self._diversifies(base, temp) else base
        return GenerationResult(text)


class _AlternatingProvider:
    """호출 순번이 짝수면 다양화·홀수면 원문 — 반복 간 변형률이 흔들리게(min≠max 검증용).

    provider 인스턴스를 반복 간 재사용하므로 전역 호출 카운터가 회차 경계를 넘어 이어진다.
    limit=5(홀수)에 repeats=3이면 회차마다 짝수 호출 수가 3·2·3으로 갈려 변형률이 흔들린다 —
    라이브 LLM의 회차 변동을 결정론으로 모사해 `--repeats` 집계(합산·min~max)를 검증한다.
    """

    def __init__(self) -> None:
        self.calls = 0

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
        base = _TempVaryingProvider._base(prompt)
        diversify = self.calls % 2 == 0
        self.calls += 1
        text = base + " (다양화)" if diversify else base  # 원문 그대로면 '동일'로 미변형.
        return GenerationResult(text)


def _seed_corpus(tmp_path: Path) -> Path:
    """소형 결정론 코퍼스 생성(quad 밴드만 — 방정식 추출 대상)."""
    src = tmp_path / "src.jsonl"
    report = run_corpus_batch(
        out_path=src,
        short_n=8,
        mc_n=4,
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


def _factory(provider: object):
    return lambda temp: QuestionRephraser(provider, temperature=temp)  # type: ignore[arg-type]


class TestRunRephraseSweep:
    def test_yield_is_monotonic_in_temperature(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7, 0.9),
            limit=None,
            rephraser_factory=_factory(_TempVaryingProvider()),
        )
        assert [row.temperature for row in report.rows] == [0.7, 0.9]
        low, high = report.rows
        # 시도 수는 온도 무관 동일(같은 입력·전건).
        assert low.attempted == high.attempted == report.total == 12
        # 변형률 단조 — 높은 온도가 낮은 온도 이상으로 다양화(임계 비례·결정론).
        assert high.rephrased >= low.rephrased
        assert high.rate >= low.rate
        # 유지 = 시도 − 변형(샘플 밖 미시도는 제외).
        for row in report.rows:
            assert row.unchanged == row.attempted - row.rephrased
            assert 0.0 <= row.rate <= 1.0

    def test_limit_caps_attempts_equally_across_temperatures(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7, 0.9),
            limit=5,
            rephraser_factory=_factory(_TempVaryingProvider()),
        )
        assert report.total == 12
        assert report.limit == 5
        for row in report.rows:
            assert row.attempted == 5  # 상한이 온도 간 동일 시도 → 공정 비교.
            assert row.rephrased <= 5

    def test_repeats_default_one_reports_zero_spread(self, tmp_path: Path) -> None:
        # repeats 기본 1 — 합산=단발·min=max=rate(결정론 provider라 변동 0).
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7,),
            limit=6,
            rephraser_factory=_factory(_TempVaryingProvider()),
        )
        row = report.rows[0]
        assert row.repeats == 1
        assert row.attempted == 6
        assert row.rate_min == row.rate == row.rate_max

    def test_repeats_aggregates_and_reports_spread(self, tmp_path: Path) -> None:
        # 반복 간 변형률이 흔들리는 provider — 합산·min~max 폭을 정확히 집계.
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7,),
            limit=5,
            repeats=3,
            rephraser_factory=_factory(_AlternatingProvider()),
        )
        row = report.rows[0]
        assert row.repeats == 3
        assert row.attempted == 15  # 5건 × 3회 반복 합산.
        assert row.rephrased == 8  # 짝수 호출만 다양화: 회차별 3·2·3.
        assert (row.rate_min, row.rate_max) == (0.4, 0.6)  # 회차 변동폭 관측.
        assert row.rate_min <= row.rate <= row.rate_max  # 평균은 폭 안.
        assert row.unchanged == row.attempted - row.rephrased

    def test_repeats_below_one_rejected(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        with pytest.raises(ValueError):
            run_rephrase_sweep(
                in_path=src,
                temperatures=(0.7,),
                limit=5,
                repeats=0,
                rephraser_factory=_factory(_TempVaryingProvider()),
            )

    def test_sweep_writes_no_corpus(self, tmp_path: Path) -> None:
        # 측정 전용 — write=False라 어떤 산출 파일도 생기지 않는다.
        src = _seed_corpus(tmp_path)
        before = {p.name for p in tmp_path.iterdir()}
        run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7, 0.9),
            limit=3,
            rephraser_factory=_factory(_TempVaryingProvider()),
        )
        assert {p.name for p in tmp_path.iterdir()} == before  # 새 파일 0

    def test_render_table_lists_each_temperature(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7, 0.9),
            limit=6,
            rephraser_factory=_factory(_TempVaryingProvider()),
        )
        table = report.render_table()
        assert "0.70" in table and "0.90" in table
        assert "변형률" in table

    def test_render_table_shows_repeat_count_and_range(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        report = run_rephrase_sweep(
            in_path=src,
            temperatures=(0.7,),
            limit=5,
            repeats=3,
            rephraser_factory=_factory(_AlternatingProvider()),
        )
        table = report.render_table()
        assert "반복 3" in table  # 반복 횟수 표기.
        assert "범위(min~max)" in table  # 회차 변동폭 열.
        assert "40.0~60.0%" in table  # 실제 min~max 렌더.


class TestCliEntry:
    def test_main_without_live_provider_fails_closed(self, tmp_path: Path, capsys: object) -> None:
        # provider 미주입(이 환경 LLM 0) → 전건 provider 예외 → 변형 0, exit 0(fail-closed).
        src = _seed_corpus(tmp_path)
        code = main(["--in", str(src), "--temperatures", "0.7,0.9", "--limit", "4", "--json"])
        assert code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        assert [row["temperature"] for row in report["rows"]] == [0.7, 0.9]
        for row in report["rows"]:
            assert row["attempted"] == 4
            assert row["rephrased"] == 0  # 라이브 provider 부재 → 전건 미변형(정직 관측)
            assert row["rate"] == 0.0

    def test_main_table_output(self, tmp_path: Path, capsys: object) -> None:
        src = _seed_corpus(tmp_path)
        code = main(["--in", str(src), "--limit", "3"])
        assert code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "0.70" in captured.out and "0.90" in captured.out  # 기본 온도 표

    def test_main_repeats_aggregates_attempts(self, tmp_path: Path, capsys: object) -> None:
        # --repeats N → 시도 수 = limit × N(provider 부재라 변형 0·표에 반복 N 표기).
        src = _seed_corpus(tmp_path)
        code = main(
            ["--in", str(src), "--temperatures", "0.7", "--limit", "4", "--repeats", "2", "--json"]
        )
        assert code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        report = json.loads(captured.out)
        row = report["rows"][0]
        assert row["repeats"] == 2
        assert row["attempted"] == 8  # 4 × 2 반복
        assert row["rephrased"] == 0

    def test_main_rejects_repeats_below_one(self, tmp_path: Path) -> None:
        src = _seed_corpus(tmp_path)
        with pytest.raises(SystemExit):
            main(["--in", str(src), "--limit", "3", "--repeats", "0"])
