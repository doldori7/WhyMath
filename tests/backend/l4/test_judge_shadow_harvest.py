"""L4 judge_shadow_harvest 단위테스트 — would-remove/keep·verdict 분포(오프라인·비노출).

load_observations(빈줄·주석·line 오류)·summarize(후보·verdict 합·remove/uncertain 율·id 빈도
정렬·라우팅 합집합)·format_summary(사람 리포트 + 마지막 JSON 줄)·CLI. 라이브 PG/HTTP 0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.l4.misconception.judge_shadow_harvest import (
    JudgeShadowSummary,
    format_summary,
    load_observations,
    main,
    summarize,
)
from whymath_backend.l4.misconception.shadow import MisconceptionJudgeShadowObservation


def _obs(
    *,
    keep_expresses: list[str] | None = None,
    keep_uncertain: list[str] | None = None,
    remove: list[str] | None = None,
    routing: str | None = None,
    feed_threshold: float | None = None,
) -> MisconceptionJudgeShadowObservation:
    exp = keep_expresses or []
    unc = keep_uncertain or []
    rem = remove or []
    candidates = exp + unc + rem
    return MisconceptionJudgeShadowObservation(
        semantic_candidate_ids=candidates,
        would_remove_ids=rem,
        would_keep_ids=exp + unc,
        verdict_expresses=len(exp),
        verdict_not_expresses=len(rem),
        verdict_uncertain=len(unc),
        candidate_count=len(candidates),
        feed_threshold=feed_threshold,
        judge_routing=routing,
    )


class TestLoadObservations:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# 주석\n\n"
            + _obs(keep_expresses=["M1"], remove=["M2"]).model_dump_json()
            + "\n   \n"
            + _obs(keep_uncertain=["M3"]).model_dump_json()
            + "\n"
        )
        obs = load_observations(text)
        assert len(obs) == 2
        assert obs[0].would_remove_ids == ["M2"]
        assert obs[1].verdict_uncertain == 1

    def test_invalid_line_raises_with_line_number(self) -> None:
        text = _obs(keep_expresses=["M1"]).model_dump_json() + "\n{ not json }\n"
        with pytest.raises(ValueError, match="line 2"):
            load_observations(text)


class TestSummarize:
    def test_empty_is_all_zero(self) -> None:
        s = summarize([])
        assert s.total == 0 and s.candidates == 0
        assert s.verdict_expresses == 0 and s.verdict_not_expresses == 0
        assert s.verdict_uncertain == 0 and s.would_keep == 0
        assert s.remove_rate == 0.0 and s.uncertain_rate == 0.0
        assert s.would_remove_id_freq == {} and s.routings == []

    def test_verdict_sums_and_would_keep(self) -> None:
        s = summarize(
            [
                _obs(keep_expresses=["M1"], keep_uncertain=["M2"], remove=["M3"]),
                _obs(keep_expresses=["M1"], remove=["M4"]),
            ]
        )
        assert s.total == 2
        assert s.candidates == 5
        assert s.verdict_expresses == 2 and s.verdict_not_expresses == 2
        assert s.verdict_uncertain == 1
        assert s.would_keep == 3  # expresses(2) + uncertain(1)

    def test_rates_over_candidates(self) -> None:
        s = summarize([_obs(keep_expresses=["M1", "M2"], keep_uncertain=["M3"], remove=["M4"])])
        # 후보 4 · 제거 1 · 불확실 1
        assert s.remove_rate == pytest.approx(0.25)
        assert s.uncertain_rate == pytest.approx(0.25)

    def test_would_remove_id_freq_counts_and_sorted(self) -> None:
        s = summarize(
            [
                _obs(remove=["M-z", "M-a"]),
                _obs(remove=["M-a"]),
            ]
        )
        assert s.would_remove_id_freq == {"M-a": 2, "M-z": 1}
        assert list(s.would_remove_id_freq.keys()) == ["M-a", "M-z"]  # 정렬

    def test_routings_union_sorted_and_none_excluded(self) -> None:
        s = summarize(
            [
                _obs(keep_expresses=["M1"], routing="fast_math"),
                _obs(keep_expresses=["M2"], routing="general_mid"),
                _obs(keep_expresses=["M3"], routing="fast_math"),  # 중복
                _obs(keep_expresses=["M4"], routing=None),  # 제외
            ]
        )
        assert s.routings == ["fast_math", "general_mid"]


class TestFormatSummary:
    def test_report_header_and_trailing_json(self) -> None:
        out = format_summary(summarize([_obs(keep_expresses=["M1"], remove=["M2"])]))
        lines = out.splitlines()
        assert lines[0].startswith("#")
        parsed = json.loads(lines[-1])
        assert parsed["candidates"] == 2 and parsed["verdict_not_expresses"] == 1
        assert parsed["would_remove_id_freq"] == {"M2": 1}

    def test_report_roundtrips_to_model(self) -> None:
        summary = summarize([_obs(keep_uncertain=["M1"], remove=["M2"], routing="fast_math")])
        last_line = format_summary(summary).splitlines()[-1]
        parsed = JudgeShadowSummary.model_validate_json(last_line)
        assert parsed == summary


class TestCli:
    def test_main_reads_obs_and_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        obs_file = tmp_path / "obs.jsonl"
        obs_file.write_text(
            _obs(keep_expresses=["M1"], remove=["M2"]).model_dump_json()
            + "\n"
            + _obs(keep_uncertain=["M3"]).model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        assert main([str(obs_file)]) == 0
        out = capsys.readouterr().out
        assert "judge-shadow 분포" in out
        parsed = json.loads(out.splitlines()[-1])
        assert parsed["total"] == 2 and parsed["verdict_not_expresses"] == 1
