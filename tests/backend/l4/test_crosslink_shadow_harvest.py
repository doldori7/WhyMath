"""L4 crosslink_shadow_harvest 단위테스트 — 관측 JSONL → coverage 요약(오프라인·비노출).

load_observations(빈줄·주석·line 오류)·summarize(관측/ distinct 커버리지·1:N·미매핑·invalid)
·format_summary(사람 리포트 + 마지막 JSON 줄)·CLI. 라이브 PG/HTTP 0(순수 집계).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.l4.misconception.crosslink_shadow import (
    MisconceptionCrosslinkShadowObservation,
)
from whymath_backend.l4.misconception.crosslink_shadow_harvest import (
    CrosslinkCoverageSummary,
    format_summary,
    load_observations,
    main,
    summarize,
)


def _obs(
    *,
    kebab_id: str = "k-1",
    kebab_valid: bool = True,
    mis_ids: list[str] | None = None,
) -> MisconceptionCrosslinkShadowObservation:
    ids = mis_ids if mis_ids is not None else []
    return MisconceptionCrosslinkShadowObservation(
        kebab_id=kebab_id,
        kebab_valid=kebab_valid,
        mis_ids=ids,
        mis_id_count=len(ids),
        mapped=len(ids) > 0,
    )


class TestLoadObservations:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# 주석\n\n"
            + _obs(kebab_id="k-1", mis_ids=["M1"]).model_dump_json()
            + "\n   \n"
            + _obs(kebab_id="k-2").model_dump_json()
            + "\n"
        )
        obs = load_observations(text)
        assert len(obs) == 2
        assert obs[0].kebab_id == "k-1" and obs[0].mapped is True
        assert obs[1].kebab_id == "k-2" and obs[1].mapped is False

    def test_invalid_line_raises_with_line_number(self) -> None:
        text = _obs().model_dump_json() + "\n{ not json }\n"
        with pytest.raises(ValueError, match="line 2"):
            load_observations(text)


class TestSummarize:
    def test_empty_is_all_zero(self) -> None:
        s = summarize([])
        assert s.total == 0 and s.mapped == 0 and s.unmapped == 0
        assert s.coverage_ratio == 0.0 and s.distinct_coverage_ratio == 0.0
        assert s.distinct_kebab_ids == 0
        assert s.ambiguous_kebab_ids == [] and s.unmapped_kebab_ids == []

    def test_observation_level_counts(self) -> None:
        s = summarize(
            [
                _obs(kebab_id="k-1", mis_ids=["M1"]),  # single
                _obs(kebab_id="k-2", mis_ids=["M1", "M2"]),  # multi(1:N)
                _obs(kebab_id="k-3"),  # unmapped
            ]
        )
        assert s.total == 3
        assert s.mapped == 2 and s.unmapped == 1
        assert s.single_mapped == 1 and s.multi_mapped == 1
        assert s.coverage_ratio == pytest.approx(2 / 3)

    def test_kebab_invalid_counted(self) -> None:
        s = summarize([_obs(kebab_id="x", kebab_valid=False), _obs(kebab_id="k-1", mis_ids=["M1"])])
        assert s.kebab_invalid == 1

    def test_distinct_coverage_folds_by_kebab_id(self) -> None:
        # 같은 kebab-id가 한 번 미매핑·한 번 매핑이면 distinct로는 "매핑됨"(합집합 OR).
        s = summarize(
            [
                _obs(kebab_id="k-1"),  # unmapped 관측
                _obs(kebab_id="k-1", mis_ids=["M1"]),  # 나중에 매핑됨
                _obs(kebab_id="k-2"),  # 계속 미매핑
            ]
        )
        assert s.distinct_kebab_ids == 2
        assert s.distinct_mapped == 1  # k-1만(합집합)
        assert s.distinct_coverage_ratio == pytest.approx(0.5)
        assert s.unmapped_kebab_ids == ["k-2"]  # k-1은 한 번이라도 매핑돼 제외

    def test_ambiguous_and_unmapped_lists_sorted(self) -> None:
        s = summarize(
            [
                _obs(kebab_id="k-b", mis_ids=["M1", "M2"]),  # 1:N
                _obs(kebab_id="k-a", mis_ids=["M3", "M4", "M5"]),  # 1:N
                _obs(kebab_id="k-z"),  # 미매핑
                _obs(kebab_id="k-m"),  # 미매핑
            ]
        )
        assert s.ambiguous_kebab_ids == ["k-a", "k-b"]  # 정렬
        assert s.unmapped_kebab_ids == ["k-m", "k-z"]  # 정렬


class TestFormatSummary:
    def test_report_header_and_trailing_json(self) -> None:
        out = format_summary(
            summarize([_obs(kebab_id="k-1", mis_ids=["M1"]), _obs(kebab_id="k-2")])
        )
        lines = out.splitlines()
        assert lines[0].startswith("#")
        # 마지막 줄은 파싱 가능한 JSON(요약 재적재·스냅샷용).
        parsed = json.loads(lines[-1])
        assert parsed["total"] == 2 and parsed["distinct_kebab_ids"] == 2
        assert parsed["unmapped_kebab_ids"] == ["k-2"]

    def test_report_roundtrips_to_model(self) -> None:
        summary = summarize([_obs(kebab_id="k-1", mis_ids=["M1", "M2"])])
        last_line = format_summary(summary).splitlines()[-1]
        parsed = CrosslinkCoverageSummary.model_validate_json(last_line)
        assert parsed == summary


class TestCli:
    def test_main_reads_obs_and_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        obs_file = tmp_path / "obs.jsonl"
        obs_file.write_text(
            _obs(kebab_id="k-1", mis_ids=["M1"]).model_dump_json()
            + "\n"
            + _obs(kebab_id="k-2").model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        assert main([str(obs_file)]) == 0
        out = capsys.readouterr().out
        assert "crosslink shadow coverage" in out
        parsed = json.loads(out.splitlines()[-1])
        assert parsed["total"] == 2 and parsed["mapped"] == 1
