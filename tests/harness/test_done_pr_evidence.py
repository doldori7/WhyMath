"""done의 PR 증적 게이트 (HARN-23) — 요청 없이도 PR을 여는 기본값의 *집행 지점*.

규칙 정본은 CLAUDE.md "✅ 절대 원칙 → 완료·병합"이고, 이 파일은 그 규칙이 산문이 아니라
CLI exit code로 집행되는지를 동결한다. 규칙만 있고 집행이 없으면 세션 기억에 의존하게 되고,
이 저장소는 그 실패를 이미 4회 겪었다(미병합 고립 — MEMORY 2026-08-11).

양방향으로 본다: 거부 경로가 실제로 exit 1을 내는가(변별력), 허용 경로가 exit 0을 내는가(오탐).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import store

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    """seed까지 끝난 저장소 (cwd 고정)."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _claimed_task(capsys) -> str:
    """게이트 없는 착수 가능 태스크 하나를 claim하고 id를 돌려준다."""
    assert cli.main(["next", "--n", "1", "--json"]) == 0
    task_id = json.loads(capsys.readouterr().out)[0]["id"]
    assert cli.main(["start", task_id, "--session", "test-branch"]) == 0
    return task_id


class TestPrReferenceAccepted:
    """PR 참조가 있는 증적은 그대로 통과한다 (오탐 없음)."""

    @pytest.mark.parametrize(
        "artifact",
        [
            "PR #12",
            "https://github.com/doldori7/whymath/pull/12",
            # 스쿼시 머지 커밋 메시지 관례 — 기존 증적 표기를 손대지 않아도 통과해야 한다
            "e02ba48c docs/harness: 하네스·헌법 통합점검 (#758)",
        ],
    )
    def test_artifact_with_pr_reference_passes(self, seeded_repo: Path, capsys, artifact: str):
        """PR참조_있는_증적_통과"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", artifact]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "done"

    def test_any_one_artifact_with_pr_reference_suffices(self, seeded_repo: Path, capsys):
        """증적_여러건_중_하나만_PR참조여도_통과"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", "abc123", "--artifact", "PR #7"]) == 0


class TestBarePrEvidenceRejected:
    """PR 참조가 없으면 거부 — 이 게이트의 변별력 자체."""

    def test_bare_commit_hash_rejected(self, seeded_repo: Path, capsys):
        """맨_커밋해시_증적_거부"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", "abc123"]) == 1
        # 거부됐으면 상태는 그대로여야 한다 (반쪽 적용 금지)
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "in_progress"

    def test_rejection_message_names_the_escape_hatch(self, seeded_repo: Path, capsys):
        """거부_메시지가_예외4종_탈출구를_안내"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", "커밋만 있음"]) == 1
        err = capsys.readouterr().err
        assert "--no-pr" in err
        for reason in cli.NO_PR_REASONS:
            assert reason in err

    def test_missing_artifact_still_rejected_first(self, seeded_repo: Path, capsys):
        """증적_자체가_없으면_기존_거부가_먼저"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id]) == 1
        assert "증적 없는 done 금지" in capsys.readouterr().err


class TestNoPrEscapeHatch:
    """예외 4종은 통과시키되 흔적을 남긴다 — 조용한 예외는 예외가 아니라 구멍이다."""

    def test_no_pr_reason_allows_done(self, seeded_repo: Path, capsys):
        """예외사유_명시하면_PR없이_완료_가능"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", "abc123", "--no-pr", "kiki-hold"]) == 0
        assert "PR 없이 완료" in capsys.readouterr().out

    def test_no_pr_reason_recorded_in_notes_and_event(self, seeded_repo: Path, capsys):
        """예외사유가_notes와_이벤트_대장에_남는다"""
        task_id = _claimed_task(capsys)
        backlog, _ = store.load_backlog(seeded_repo)
        original_notes = backlog.tasks[task_id].notes

        assert cli.main(["done", task_id, "--artifact", "abc123", "--no-pr", "ci-red"]) == 0

        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks[task_id].notes
        assert "ci-red" in notes
        assert "PR 보류" in notes
        # 원 notes를 덮어쓰지 않는다 (HARN-20 데이터 파괴 재발 방지)
        if original_notes.strip():
            assert original_notes in notes

        events = (seeded_repo / "backlog" / "events.ndjson").read_text(encoding="utf-8")
        records = [json.loads(line) for line in events.splitlines() if line.strip()]
        done_events = [r for r in records if r.get("id") == task_id and r.get("action") == "done"]
        assert done_events and done_events[-1].get("no_pr_reason") == "ci-red"

    def test_unknown_reason_rejected_by_argparse(self, seeded_repo: Path, capsys):
        """미등록_사유는_argparse가_거부 — 자유 서술 우회 차단"""
        task_id = _claimed_task(capsys)
        with pytest.raises(SystemExit) as exc:
            cli.main(["done", task_id, "--artifact", "abc123", "--no-pr", "그냥요"])
        assert exc.value.code == 2

    def test_normal_done_leaves_no_no_pr_trace(self, seeded_repo: Path, capsys):
        """정상_PR_완료에는_보류_흔적이_남지_않는다"""
        task_id = _claimed_task(capsys)
        assert cli.main(["done", task_id, "--artifact", "PR #5"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert "PR 보류" not in backlog.tasks[task_id].notes
        assert "PR 없이 완료" not in capsys.readouterr().out
