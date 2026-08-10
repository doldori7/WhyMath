"""backlog._next_free_number — 100 이상에서 형식 위반 ID를 제안하던 결함 (HARN-21 결함②).

`{index:02d}`는 **최소** 2자리이지 **정확히** 2자리가 아니다 — `index=100`이면 `"100"`
(3자리)을 낸다. 그런데 `models.TASK_ID_RE`는 `\\d{2}` — 정확히 2자리만 허용한다. 즉
어떤 프리픽스가 99개를 다 쓰면 다음 제안이 형식 위반 ID(`E1-100`)가 됐다.

수정: index가 99를 넘어서면 `_next_free_number`가 `None`을 반환하고, `cmd_add`가 이를
"프리픽스 소진 — 사람의 결정 필요" 명시적 오류로 승격한다(날조된 3자리 제안 금지).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _taken_full(prefix: str, numbers: range) -> dict[str, tuple[str, str]]:
    """`{prefix}-01`..`{prefix}-NN`이 전부 점유된 taken 딕셔너리를 만든다."""
    return {f"{prefix}-{i:02d}": (f"{prefix}-{i:02d}-task", "로컬 백로그") for i in numbers}


class TestNextFreeNumberFormatGuard:
    """단위 레벨 — 함수 자체의 경계값 동작."""

    def test_normal_range_still_returns_two_digit_string(self):
        """정상_범위는_여전히_2자리_문자열을_낸다 — 회귀 방지"""
        taken = _taken_full("E1", range(1, 5))  # E1-01..E1-04 점유
        assert cli._next_free_number("E1", taken) == "E1-05"

    def test_single_digit_index_is_zero_padded(self):
        """1자리_index도_0패딩된다"""
        assert cli._next_free_number("ZZ", {}) == "ZZ-01"

    def test_exactly_99_used_returns_none_not_three_digits(self):
        """99개_전부_소진되면_None을_반환한다 — 3자리(E1-100) 날조 금지"""
        taken = _taken_full("E1", range(1, 100))  # E1-01..E1-99 전부 점유
        assert cli._next_free_number("E1", taken) is None

    def test_boundary_98_used_still_suggests_99(self):
        """98개_소진_시엔_아직_99번을_제안할_수_있다 — 경계값 반대쪽"""
        taken = _taken_full("E1", range(1, 99))  # E1-01..E1-98 점유
        assert cli._next_free_number("E1", taken) == "E1-99"

    def test_taken_value_shape_matches_taken_id_numbers_return_type(self):
        """taken의_값_형태가_실제_taken_id_numbers_반환형(tuple[str,str])과_일치한다

        시그니처 애노테이션 정정(HARN-21) 검증 — 함수가 실제로 이 형태의 dict를
        받아 동작함을 실증한다(키만 순회하므로 값 타입이 달라도 런타임 버그는
        없었지만, 애노테이션이 이 형태를 정확히 반영해야 한다).
        """
        taken: dict[str, tuple[str, str]] = {"ZQ-01": ("ZQ-01-existing", "로컬 백로그")}
        assert cli._next_free_number("ZQ", taken) == "ZQ-02"


class TestCmdAddSurfacesExhaustionAsExplicitError:
    """CLI 종단 — 프리픽스 소진 시 cmd_add가 날조 대신 명시적 오류를 낸다."""

    def _add(self, task_id: str) -> int:
        return cli.main(
            [
                "add",
                "--id",
                task_id,
                "--title",
                "프리픽스 소진 테스트",
                "--track",
                "math-completion",
                "--stage",
                "S2",
            ]
        )

    def test_exhausted_prefix_collision_fails_with_explicit_message_not_three_digit_suggestion(
        self, seeded_repo, monkeypatch, capsys
    ):
        """소진된_프리픽스_충돌은_3자리_제안_대신_명시적_오류를_낸다"""
        fake_taken = _taken_full("ZQ", range(1, 100))  # ZQ-01..ZQ-99 전부 로컬 점유로 가장

        def _fake_taken_id_numbers(root, backlog, policy):
            return dict(fake_taken)

        monkeypatch.setattr(cli, "_taken_id_numbers", _fake_taken_id_numbers)

        capsys.readouterr()
        assert self._add("ZQ-01-my-new-slug") == 1, "번호 충돌은 여전히 거부돼야 한다"
        captured = capsys.readouterr()
        assert "ZQ-100" not in captured.err, "3자리 형식 위반 ID를 제안하면 안 된다"
        assert "소진" in captured.err, "프리픽스 소진 사실이 명시돼야 한다"
        assert "사람의 결정" in captured.err, "사람의 결정이 필요함을 알려야 한다"
