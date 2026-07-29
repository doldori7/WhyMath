"""L4 step_shadow_harvest 단위테스트 — 구조화 관측 → A/B 라벨링 워크시트(오프라인·비노출).

load_observations·to_draft(프라이버시·candidate 드롭)·format_drafts·CLI
·라운드트립(eval 연결)·미라벨 가드.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.l4 import step_shadow_eval as eval_mod
from whymath_backend.l4.step_shadow import StepBreakObservation
from whymath_backend.l4.step_shadow_harvest import (
    LabelDraft,
    format_drafts,
    harvest,
    load_observations,
    main,
    to_draft,
)


def _obs(
    *,
    verdict: str = "diverged_from_answer",
    candidate: str = "A",
    expected_answer: str | None = "3",
    solset_before: str = "{3}",
    solset_after: str = "{4}",
) -> StepBreakObservation:
    return StepBreakObservation(
        problem_id=None,
        expected_answer=expected_answer,
        verdict=verdict,  # runtime Literal 검증(테스트는 mypy 비대상)
        candidate=candidate,
        var="x",
        step_index=0,
        solset_before=solset_before,
        solset_after=solset_after,
        marker="따라서",
    )


class TestLoadObservations:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# 주석\n\n"
            + _obs().model_dump_json()
            + "\n   \n"
            + _obs(
                verdict="unrelated", candidate="ambiguous", expected_answer="5"
            ).model_dump_json()
            + "\n"
        )
        obs = load_observations(text)
        assert len(obs) == 2
        assert obs[0].verdict == "diverged_from_answer"
        assert obs[1].candidate == "ambiguous"

    def test_invalid_line_raises_with_line_number(self) -> None:
        text = _obs().model_dump_json() + "\n{ not json }\n"
        with pytest.raises(ValueError, match="line 2"):
            load_observations(text)


class TestToDraft:
    def test_maps_fields_and_leaves_label_unset(self) -> None:
        d = to_draft(_obs(expected_answer="3"))
        assert isinstance(d, LabelDraft)
        assert d.human_label is None
        assert d.solset_before == "{3}" and d.solset_after == "{4}"
        assert d.expected_answer == "3"
        assert d.var == "x" and d.marker == "따라서"
        assert d.source == "shadow-log"

    def test_solution_text_empty_for_privacy(self) -> None:
        # 관측에 학생 풀이 원문이 없으므로 draft.solution_text는 빈 문자열.
        assert to_draft(_obs()).solution_text == ""

    def test_candidate_dropped_to_note(self) -> None:
        # candidate는 draft 필드가 아니라 note로만 보존(eval이 라벨에서 재계산).
        d = to_draft(_obs(candidate="A", verdict="diverged_from_answer"))
        assert "candidate=A" in d.note
        assert "verdict=diverged_from_answer" in d.note
        assert "observed_at=" in d.note
        assert "candidate" not in d.model_dump()  # LabelDraft에 candidate 필드 없음


class TestFormatDrafts:
    def test_header_and_one_json_line_per_draft(self) -> None:
        out = format_drafts(
            harvest([_obs(), _obs(verdict="unrelated", candidate="ambiguous", expected_answer="5")])
        )
        lines = out.splitlines()
        assert lines[0].startswith("#") and lines[1].startswith("#")
        data_lines = [ln for ln in lines if not ln.startswith("#")]
        assert len(data_lines) == 2
        first = json.loads(data_lines[0])
        assert first["human_label"] is None and first["source"] == "shadow-log"

    def test_empty_input_only_header(self) -> None:
        out = format_drafts([])
        assert all(ln.startswith("#") for ln in out.splitlines())


class TestRoundTrip:
    def test_harvest_then_label_then_eval(self) -> None:
        # harvest → 사람이 null→A/B 채움 → step_shadow_eval 로드+평가(두 슬라이스 연결 증명).
        obs = [
            _obs(expected_answer="3", verdict="diverged_from_answer", candidate="A"),  # 라벨 A = TP
            _obs(expected_answer="5", verdict="unrelated", candidate="ambiguous"),  # 라벨 B = TN
        ]
        drafts_text = format_drafts(harvest(obs))
        labeled = drafts_text.replace('"human_label":null', '"human_label":"A"', 1).replace(
            '"human_label":null', '"human_label":"B"', 1
        )
        report = eval_mod.evaluate(eval_mod.load_labels(labeled))
        assert report.total == 2
        assert report.true_positive == 1 and report.true_negative == 1
        assert report.precision == 1.0

    def test_unlabeled_draft_rejected_by_eval(self) -> None:
        # 미라벨(null) draft를 eval에 직접 넣으면 line 번호 ValueError(1~2=주석·3=첫 데이터).
        drafts_text = format_drafts(harvest([_obs()]))
        with pytest.raises(ValueError, match="line 3"):
            eval_mod.load_labels(drafts_text)

    def test_labeled_draft_loads_as_steplabel(self) -> None:
        # LabelDraft 필드 = StepBreakLabel 필드(상속)
        # → 라벨 채운 draft가 그대로 StepBreakLabel로 로드.
        labeled_json = (
            to_draft(_obs()).model_dump_json().replace('"human_label":null', '"human_label":"A"')
        )
        label = eval_mod.StepBreakLabel.model_validate_json(labeled_json)
        assert label.human_label == "A" and label.source == "shadow-log"


class TestCli:
    def test_main_reads_obs_and_prints_drafts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        obs_file = tmp_path / "obs.jsonl"
        obs_file.write_text(
            _obs().model_dump_json()
            + "\n"
            + _obs(
                verdict="reached_answer", candidate="not_A", expected_answer="4"
            ).model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        assert main([str(obs_file)]) == 0
        out = capsys.readouterr().out
        assert "# harvest draft" in out
        data_lines = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
        assert len(data_lines) == 2
        assert json.loads(data_lines[0])["source"] == "shadow-log"
