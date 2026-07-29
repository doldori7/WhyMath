"""L4 wrong_form_shadow_harvest 단위테스트 — SymPy vs substring 분포 집계(오프라인·비노출).

load_observations(빈줄·주석·line 오류)·summarize(히트·순기여·substring 단독·일치·id 빈도 정렬)
·format_summary(사람 리포트 + 마지막 JSON 줄)·CLI. 라이브 PG/HTTP 0(순수 집계).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.l4.misconception.wrong_form_match import WrongFormShadowObservation
from whymath_backend.l4.misconception.wrong_form_shadow_harvest import (
    WrongFormCoverageSummary,
    format_summary,
    load_observations,
    main,
    summarize,
)


def _obs(
    *,
    sympy: list[str] | None = None,
    substring: list[str] | None = None,
) -> WrongFormShadowObservation:
    s = sympy or []
    b = substring or []
    sympy_only = [mid for mid in s if mid not in set(b)]
    return WrongFormShadowObservation(
        sympy_detected_ids=s,
        substring_detected_ids=b,
        sympy_only_ids=sympy_only,
    )


class TestLoadObservations:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# 주석\n\n"
            + _obs(sympy=["M1"], substring=["M1"]).model_dump_json()
            + "\n   \n"
            + _obs(sympy=["M2"], substring=[]).model_dump_json()
            + "\n"
        )
        obs = load_observations(text)
        assert len(obs) == 2
        assert obs[0].sympy_detected_ids == ["M1"]
        assert obs[1].sympy_only_ids == ["M2"]

    def test_invalid_line_raises_with_line_number(self) -> None:
        text = _obs(sympy=["M1"]).model_dump_json() + "\n{ not json }\n"
        with pytest.raises(ValueError, match="line 2"):
            load_observations(text)


class TestSummarize:
    def test_empty_is_all_zero(self) -> None:
        s = summarize([])
        assert s.total == 0 and s.sympy_hits == 0 and s.substring_hits == 0
        assert s.sympy_only_hits == 0 and s.substring_only_hits == 0 and s.agreement == 0
        assert s.sympy_only_id_freq == {} and s.substring_only_id_freq == {}

    def test_hit_counts_and_agreement(self) -> None:
        s = summarize(
            [
                _obs(sympy=["M1"], substring=["M1"]),  # 완전 일치
                _obs(sympy=["M2"], substring=[]),  # sympy 순기여
                _obs(sympy=[], substring=["M3"]),  # substring 단독
                _obs(sympy=[], substring=[]),  # 둘 다 미탐지(일치=빈집합)
            ]
        )
        assert s.total == 4
        assert s.sympy_hits == 2 and s.substring_hits == 2
        assert s.sympy_only_hits == 1 and s.substring_only_hits == 1
        assert s.agreement == 2  # M1 일치 + 빈집합==빈집합

    def test_sympy_only_freq_counts_net_contribution(self) -> None:
        s = summarize(
            [
                _obs(sympy=["M2"], substring=[]),
                _obs(sympy=["M2", "M5"], substring=["M5"]),  # M2만 순기여
            ]
        )
        assert s.sympy_only_id_freq == {"M2": 2}
        assert s.substring_only_id_freq == {}

    def test_substring_only_freq_flags_regression_risk(self) -> None:
        s = summarize(
            [
                _obs(sympy=[], substring=["M3"]),
                _obs(sympy=["M1"], substring=["M1", "M3"]),  # M3은 substring만
            ]
        )
        assert s.substring_only_id_freq == {"M3": 2}
        assert s.sympy_only_id_freq == {}

    def test_freq_dicts_key_sorted(self) -> None:
        s = summarize(
            [
                _obs(sympy=["M-z"], substring=[]),
                _obs(sympy=["M-a"], substring=[]),
            ]
        )
        assert list(s.sympy_only_id_freq.keys()) == ["M-a", "M-z"]  # 정렬


class TestFormatSummary:
    def test_report_header_and_trailing_json(self) -> None:
        out = format_summary(summarize([_obs(sympy=["M2"], substring=[])]))
        lines = out.splitlines()
        assert lines[0].startswith("#")
        parsed = json.loads(lines[-1])
        assert parsed["total"] == 1 and parsed["sympy_only_hits"] == 1
        assert parsed["sympy_only_id_freq"] == {"M2": 1}

    def test_report_roundtrips_to_model(self) -> None:
        summary = summarize([_obs(sympy=["M1"], substring=["M1", "M3"])])
        last_line = format_summary(summary).splitlines()[-1]
        parsed = WrongFormCoverageSummary.model_validate_json(last_line)
        assert parsed == summary


class TestCli:
    def test_main_reads_obs_and_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        obs_file = tmp_path / "obs.jsonl"
        obs_file.write_text(
            _obs(sympy=["M2"], substring=[]).model_dump_json()
            + "\n"
            + _obs(sympy=["M1"], substring=["M1"]).model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        assert main([str(obs_file)]) == 0
        out = capsys.readouterr().out
        assert "wrong_form shadow 분포" in out
        parsed = json.loads(out.splitlines()[-1])
        assert parsed["total"] == 2 and parsed["sympy_only_hits"] == 1
