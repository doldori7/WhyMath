"""[OPS-24] 코퍼스 후처리 백필 CLI 2종의 `--check` 드리프트 가드 모드 단위테스트(hermetic).

왜 이 테스트가 있는가
--------------------
`review_status`·`persona_fit` 백필 CLI는 OPS-22 감사기가 "CI 어디에도 도달하지 않는다"고 잡아낸
2종이다. 배선 판정은 "수동 실행 의도"가 아니라 **CI 배선이 맞다**였다 — `review_status`가 빈
레코드는 `l6/_shared.is_review_cleared`가 fail-closed로 노출을 전건 차단하므로 백필 누락은 서빙
영향을 갖는 회귀다. 다만 CI가 레포 데이터를 재작성하면 안 되므로 *변이형*이 아니라 `--check`
(미기록 · 미백필 1건이라도 있으면 exit 1)를 신설해 걸었다.

기존 `--dry-run`은 **채울 게 있든 없든 항상 exit 0**이라 게이트로 쓸 수 없다(CLAUDE.md "변별력
없는 검증 스텝 금지" — 성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장이다). 이
테스트는 그 변별력 자체를 동결한다.

봉인 계약
--------
① 미백필 레코드가 1건이라도 있으면 `--check` exit 1(변별력).
② 전건 백필돼 있으면 exit 0.
③ `--check`는 **write 경로에 진입하지 않는다** — `Path.write_text`/`Path.mkdir`를 폭발물로
   바꿔 놓아도 통과한다(파일·감사로그 미기록의 기계적 동결. "산출물이 없더라"보다 강한 계약).
④ 같은 입력에서 `--dry-run`은 exit 0 — 두 모드의 차이가 *종료 코드뿐*임을 명시적으로 대조한다.
⑤ `--dry-run --check` 동시 지정은 argparse가 거부(exit 2) — 모드 혼선 방지.
⑥ exit 1일 때 stderr에 무엇이 얼마나 남았는지 적힌다(침묵 실패 금지).

LLM·DB·네트워크 0(순수 결정론). `--corpus`는 감사 라벨 파일이 없는 키(`v1`)만 쓴다 — 레포
상대경로 파일을 읽지 않아 실행 cwd에 의존하지 않는다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.harness import problem_corpus_persona_fit_backfill as persona_cli
from whymath_backend.harness import problem_corpus_review_status_backfill as review_cli


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )


def _problem_record(
    *,
    slug: str,
    persona_fit: dict[str, float] | None = None,
    review_status: str | None = None,
) -> dict[str, Any]:
    """최소 유효 코퍼스 레코드(populate 로더 authoring 키 포함).

    `persona_fit`/`review_status`를 `None`으로 두면 그 키를 아예 넣지 않는다(= 미백필 상태 —
    두 CLI 모두 "키 부재"와 "빈 값"을 같게 다룬다).
    """
    rec: dict[str, Any] = {
        "slug": slug,
        "problem_id": str(uuid.uuid5(uuid.NAMESPACE_URL, slug)),
        "source_type": "자체생성",
        "license": "WHYMATH_GENERATED",
        "generation_type": "FULLY_GENERATED",
        "curriculum_version": "2022_REVISION",
        "valid_from_year": 2022,
        "subject": "공통",
        "unit_codes": ["QUAD-EQ"],
        "question_format": "단답형",
        "question_text": "이차방정식 x^2 + 4x - 2 = 0 의 서로 다른 두 근의 합의 값을 구하시오.",
        "answer": "-4",
        "difficulty_overall": 2.0,
        "concepts": [],
        "verify": {"conditions": "x**2 + 4*x - 2 = 0", "answer_map": {}, "answer_aggregate": "sum"},
    }
    if persona_fit is not None:
        rec["persona_fit"] = persona_fit
    if review_status is not None:
        rec["review_status"] = review_status
    return rec


def _review_argv(src: Path, tmp_path: Path) -> list[str]:
    """review_status CLI 공통 인자 — `--corpus v1`은 감사 라벨 파일이 없는 키(cwd 비의존).

    `--audit-out`을 tmp_path로 못 박는다: 생략하면 기본값이 레포 상대경로
    (`docs/data/review_status_backfill_audit/<입력 디렉터리명>.jsonl`)라, 회귀로 write 경로가
    열리는 순간 테스트가 **레포에 파일을 싼다**(실측: 이 테스트를 뮤테이션 검증할 때 실제로
    3개가 유출됐다). 테스트는 구조적으로 레포 밖만 만지게 한다.
    """
    return ["--in", str(src), "--corpus", "v1", "--audit-out", str(tmp_path / "audit.jsonl")]


def _persona_argv(src: Path, tmp_path: Path) -> list[str]:
    """persona_fit CLI 공통 인자 — `--audit-out` 못 박기 이유는 `_review_argv` 참조."""
    return ["--in", str(src), "--audit-out", str(tmp_path / "audit.jsonl")]


def _arm_write_explosives(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Path.write_text`·`Path.mkdir`를 폭발물로 바꾼다 — write 경로 진입 시 즉시 실패."""

    def _boom_write(self: Path, *args: Any, **kwargs: Any) -> int:
        raise AssertionError(f"--check가 파일에 썼다(금지): {self}")

    def _boom_mkdir(self: Path, *args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"--check가 디렉터리를 만들었다(금지): {self}")

    monkeypatch.setattr(Path, "write_text", _boom_write)
    monkeypatch.setattr(Path, "mkdir", _boom_mkdir)


# ──────────────────────────────────────────────────────────────────────────
# review_status 백필(PB-03)
# ──────────────────────────────────────────────────────────────────────────


class TestReviewStatusCheckMode:
    def test_check_exits_1_when_records_are_unfilled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """① 변별력 — 미백필 1건이면 exit 1이고, stderr가 무엇이 남았는지 말한다(⑥)."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        exit_code = review_cli.main([*_review_argv(src, tmp_path), "--check"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "미백필 1건" in captured.err
        assert str(src) in captured.err

    def test_check_exits_0_when_all_records_filled(self, tmp_path: Path) -> None:
        """② 전건 백필돼 있으면 통과 — 성공/실패가 서로 다른 값을 낸다."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="filled", review_status="pending")])

        assert review_cli.main([*_review_argv(src, tmp_path), "--check"]) == 0

    def test_check_never_enters_write_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """③ 파일·감사로그 미기록을 기계로 동결 — write 경로에 들어가면 AssertionError로 폭발."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])
        before = src.read_bytes()

        _arm_write_explosives(monkeypatch)
        exit_code = review_cli.main([*_review_argv(src, tmp_path), "--check"])

        assert exit_code == 1  # 폭발 없이 판정만 났다
        monkeypatch.undo()
        assert src.read_bytes() == before  # 입력도 바이트 무변경

    def test_dry_run_stays_exit_0_on_the_same_input(self, tmp_path: Path) -> None:
        """④ 대조 — 같은 미백필 입력에서 `--dry-run`은 exit 0이다(그래서 게이트가 못 된다)."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        assert review_cli.main([*_review_argv(src, tmp_path), "--dry-run"]) == 0
        assert review_cli.main([*_review_argv(src, tmp_path), "--check"]) == 1

    def test_dry_run_and_check_together_are_rejected(self, tmp_path: Path) -> None:
        """⑤ 모드 혼선 방지 — argparse 상호배타 그룹이 exit 2로 거부한다."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        with pytest.raises(SystemExit) as exc:
            review_cli.main([*_review_argv(src, tmp_path), "--dry-run", "--check"])
        assert exc.value.code == 2

    def test_check_still_emits_report_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """관측 유지 — exit 1이어도 stdout 리포트는 그대로 난다(조용한 실패 금지)."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        review_cli.main([*_review_argv(src, tmp_path), "--check"])

        payload = json.loads(capsys.readouterr().out)
        assert payload["total"] == 1 and payload["filled"] == 1
        assert payload["written"] is None and payload["audit_written"] is None


# ──────────────────────────────────────────────────────────────────────────
# persona_fit 백필(S3-10/PB-01)
# ──────────────────────────────────────────────────────────────────────────


class TestPersonaFitCheckMode:
    def test_check_exits_1_when_records_are_unfilled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        exit_code = persona_cli.main([*_persona_argv(src, tmp_path), "--check"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "미백필 1건" in captured.err
        assert str(src) in captured.err

    def test_check_exits_0_when_all_records_filled(self, tmp_path: Path) -> None:
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="filled", persona_fit={"A_일반고고3": 0.42})])

        assert persona_cli.main([*_persona_argv(src, tmp_path), "--check"]) == 0

    def test_empty_dict_counts_as_unfilled(self, tmp_path: Path) -> None:
        """`persona_fit: {}`은 "채워짐"이 아니다 — 백필 대상이므로 게이트가 잡아야 한다."""
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="empty", persona_fit={})])

        assert persona_cli.main([*_persona_argv(src, tmp_path), "--check"]) == 1

    def test_check_never_enters_write_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])
        before = src.read_bytes()

        _arm_write_explosives(monkeypatch)
        exit_code = persona_cli.main([*_persona_argv(src, tmp_path), "--check"])

        assert exit_code == 1
        monkeypatch.undo()
        assert src.read_bytes() == before

    def test_dry_run_stays_exit_0_on_the_same_input(self, tmp_path: Path) -> None:
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        assert persona_cli.main([*_persona_argv(src, tmp_path), "--dry-run"]) == 0
        assert persona_cli.main([*_persona_argv(src, tmp_path), "--check"]) == 1

    def test_dry_run_and_check_together_are_rejected(self, tmp_path: Path) -> None:
        src = tmp_path / "problems.jsonl"
        _write_jsonl(src, [_problem_record(slug="unfilled")])

        with pytest.raises(SystemExit) as exc:
            persona_cli.main([*_persona_argv(src, tmp_path), "--dry-run", "--check"])
        assert exc.value.code == 2
