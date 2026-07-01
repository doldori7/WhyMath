"""L4 semantic_shadow_harvest 단위테스트 — semantic 순기여 + 유사도 버킷(오프라인·비노출).

load_observations(빈줄·주석·line 오류)·summarize(히트·순기여 id 빈도·유사도 누적 버킷·unknown)
·format_summary(사람 리포트 + 마지막 JSON 줄)·CLI. 라이브 PG/HTTP 0(순수 집계).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.l4.misconception.semantic_shadow_harvest import (
    SemanticShadowCoverageSummary,
    format_summary,
    load_observations,
    main,
    summarize,
)
from whymath_backend.l4.misconception.shadow import MisconceptionShadowObservation


def _obs(
    *,
    substr: list[str] | None = None,
    semantic_only: list[tuple[str, float]] | None = None,
) -> MisconceptionShadowObservation:
    substr_ids = substr or []
    pairs = semantic_only or []
    return MisconceptionShadowObservation(
        substr_ids=substr_ids,
        semantic_only_ids=[mid for mid, _ in pairs],
        semantic_only_similarities=[sim for _, sim in pairs],
        substr_count=len(substr_ids),
        semantic_count=len(substr_ids) + len(pairs),
    )


class TestLoadObservations:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# 주석\n\n"
            + _obs(substr=["M1"], semantic_only=[("M2", 0.85)]).model_dump_json()
            + "\n   \n"
            + _obs(substr=["M1"]).model_dump_json()
            + "\n"
        )
        obs = load_observations(text)
        assert len(obs) == 2
        assert obs[0].semantic_only_ids == ["M2"]
        assert obs[1].semantic_only_ids == []

    def test_invalid_line_raises_with_line_number(self) -> None:
        text = _obs(substr=["M1"]).model_dump_json() + "\n{ not json }\n"
        with pytest.raises(ValueError, match="line 2"):
            load_observations(text)


class TestSummarize:
    def test_empty_is_all_zero(self) -> None:
        s = summarize([])
        assert s.total == 0 and s.substr_hits == 0 and s.semantic_only_hits == 0
        assert s.semantic_only_detections == 0 and s.semantic_only_id_freq == {}
        assert s.sim_ge_090 == 0 and s.sim_ge_080 == 0 and s.sim_ge_070 == 0
        assert s.sim_unknown == 0

    def test_hit_counts(self) -> None:
        s = summarize(
            [
                _obs(substr=["M1"], semantic_only=[("M2", 0.85)]),  # substr + 순기여
                _obs(substr=["M1"]),  # substr만
                _obs(semantic_only=[("M3", 0.75)]),  # 순기여만
            ]
        )
        assert s.total == 3
        assert s.substr_hits == 2
        assert s.semantic_only_hits == 2
        assert s.semantic_only_detections == 2

    def test_id_freq_counts_and_sorted(self) -> None:
        s = summarize(
            [
                _obs(semantic_only=[("M-z", 0.9), ("M-a", 0.8)]),
                _obs(semantic_only=[("M-a", 0.72)]),
            ]
        )
        assert s.semantic_only_id_freq == {"M-a": 2, "M-z": 1}
        assert list(s.semantic_only_id_freq.keys()) == ["M-a", "M-z"]  # 정렬

    def test_similarity_buckets_cumulative(self) -> None:
        s = summarize(
            [
                _obs(
                    semantic_only=[
                        ("M1", 0.95),  # ge90, ge80, ge70
                        ("M2", 0.85),  # ge80, ge70
                        ("M3", 0.72),  # ge70
                        ("M4", 0.50),  # 아무 버킷 아님
                    ]
                ),
            ]
        )
        assert s.semantic_only_detections == 4
        assert s.sim_ge_090 == 1
        assert s.sim_ge_080 == 2  # 0.95 + 0.85
        assert s.sim_ge_070 == 3  # + 0.72
        assert s.sim_unknown == 0

    def test_unknown_similarity_excluded_from_buckets(self) -> None:
        # -1.0(미설정)은 unknown으로만 세고 임계 버킷엔 안 들어간다(음수라 자연 제외).
        s = summarize([_obs(semantic_only=[("M1", -1.0), ("M2", 0.9)])])
        assert s.sim_unknown == 1
        assert s.sim_ge_090 == 1 and s.sim_ge_070 == 1  # M2만
        assert s.semantic_only_detections == 2


class TestFormatSummary:
    def test_report_header_and_trailing_json(self) -> None:
        out = format_summary(summarize([_obs(substr=["M1"], semantic_only=[("M2", 0.85)])]))
        lines = out.splitlines()
        assert lines[0].startswith("#")
        parsed = json.loads(lines[-1])
        assert parsed["total"] == 1 and parsed["semantic_only_detections"] == 1
        assert parsed["sim_ge_080"] == 1

    def test_report_roundtrips_to_model(self) -> None:
        summary = summarize([_obs(semantic_only=[("M1", 0.95)])])
        last_line = format_summary(summary).splitlines()[-1]
        parsed = SemanticShadowCoverageSummary.model_validate_json(last_line)
        assert parsed == summary


class TestCli:
    def test_main_reads_obs_and_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        obs_file = tmp_path / "obs.jsonl"
        obs_file.write_text(
            _obs(substr=["M1"], semantic_only=[("M2", 0.85)]).model_dump_json()
            + "\n"
            + _obs(substr=["M1"]).model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        assert main([str(obs_file)]) == 0
        out = capsys.readouterr().out
        assert "의미매칭 shadow 분포" in out
        parsed = json.loads(out.splitlines()[-1])
        assert parsed["total"] == 2 and parsed["semantic_only_hits"] == 1
