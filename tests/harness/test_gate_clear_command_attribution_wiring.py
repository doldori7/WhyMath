"""사람이 **복사해 실행하는** clear 명령이 주체 플래그를 달고 있는가 (HARN-60 배선).

**왜 이 파일이 있는가 — 기록이 없는 것보다 나쁜 상태**

`HARN-60`이 `--as`를 만들어도, Kiki가 실제로 복사하는 명령(보드의 '해소 명령', 런북·도시에의
복붙 블록)이 그 플래그를 빼먹으면 **사람이 실행한 clear가 대장에 `cleared_by: claude`로 남는다.**
그건 미기록보다 나쁘다 — 대장이 "에이전트가 닫았다"고 *적극적으로 거짓을* 말하고, 준수 감사는
그 거짓을 근거로 판정한다. 즉 계약(`--as`)만 만들고 **집행 지점(복붙 경로)을 안 고치면 HARN-60은
목적을 정확히 거꾸로 달성한다**(CLAUDE.md "정본화를 집행으로 착각한 완료 선언 금지").

지적: PR #978 codex P2.

**설계 원칙 3가지**

1. **문자열 금지 목록이 아니라 산출물을 본다** — 보드는 소스의 템플릿 문자열이 아니라
   `build_board`가 실제로 낸 HTML을 검사한다. 소스를 어떻게 고쳐 쓰든 *나오는 명령*이 옳아야 한다.
2. **스캔 0건은 실패다** — 대상을 하나도 못 찾은 전수 가드는 공허하게 통과한다. 파일별로
   "최소 1건은 찾았다"를 함께 못박는다.
3. **면제는 이유와 함께 열거한다** — 자리표시자(`<id>`)만 있는 일반 usage와 날짜가 박힌 과거
   스냅샷은 복붙 대상이 아니므로 제외하되, 그 목록을 여기 적어 다음 사람이 판단을 되짚을 수 있게 한다.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import board
import store

_REPO = Path(__file__).resolve().parents[2]

# 사람이 그대로 복사해 실행하는 clear 명령이 사는 파일 — 여기 있는 구체 게이트 ID 명령은
# 전부 `--as`를 달아야 한다.
_HUMAN_COPY_PASTE_FILES = [
    "scripts/demo/README.md",
    "docs/ops/eos_relevance_triage_gate_runbook.md",
    "docs/standards/crosswalk_gate_contract.md",
    "docs/standards/eos_verification_design_v1.md",
    "docs/data/misconception_crosslink_review_dossier.md",
]

# `gates clear` 뒤에 **구체 게이트 ID**(G-로 시작)가 오는 형태만 잡는다.
# `<id>`·`<G-id>` 자리표시자는 실행 대상이 아니라 문법 설명이므로 애초에 매치되지 않는다.
_CONCRETE_CLEAR = re.compile(r"gates clear\s+(G-[A-Za-z0-9-]+)((?:\s+\S+)*)")

# 면제 — 복붙 대상이 아닌 곳. 이유를 함께 남긴다(만료 없는 예외 금지의 정신).
_EXEMPT = {
    # 날짜가 박힌 과거 스냅샷 — 고치면 그때의 기록을 사후 수정하는 것이 된다.
    "docs/strategy/human_bottleneck_status_2026-07-26.md": "2026-07-26 시점 스냅샷(역사 보존)",
    # 결정 로그 — 당시 실행된 명령을 그대로 인용한 것이라 수정 대상이 아니다.
    "MEMORY.md": "결정 로그(당시 인용)",
}
# CLAUDE.md는 여기 없다: 구체 게이트 ID 명령이 0건이라(자리표시자 서술뿐) 면제할 대상 자체가
# 없다. 처음엔 넣었다가 `test_exemptions_are_real_and_named`가 유령 면제로 잡아냈다 —
# 가드가 자기 목록의 거짓을 잡은 사례라 기록으로 남긴다.


def _lines_with_concrete_clear(text: str) -> list[tuple[str, str]]:
    """(게이트 ID, 명령 꼬리) — 구체 ID를 가진 clear 명령만."""
    return [(m.group(1), m.group(2)) for m in _CONCRETE_CLEAR.finditer(text)]


class TestHumanCopyPasteCommandsCarryTheFlag:
    """복붙 경로의 구체 clear 명령은 전부 `--as`를 단다."""

    def test_every_human_facing_command_has_as_flag(self):
        """사람용_복붙명령_전건에_주체플래그"""
        offenders: list[str] = []
        found_total = 0
        for rel in _HUMAN_COPY_PASTE_FILES:
            path = _REPO / rel
            assert path.exists(), f"대상 파일이 사라졌다 — 목록을 갱신하라: {rel}"
            hits = _lines_with_concrete_clear(path.read_text(encoding="utf-8"))
            # 파일별 0건도 실패다 — 파일이 개편돼 명령이 사라졌다면 이 목록이 낡은 것이고,
            # 그 상태로 통과시키면 가드가 아무것도 지키지 않으면서 초록을 낸다.
            assert hits, f"{rel}: 구체 clear 명령 0건 — 목록이 낡았거나 정규식이 깨졌다"
            found_total += len(hits)
            for gate_id, tail in hits:
                if "--as" not in tail:
                    offenders.append(f"{rel} :: gates clear {gate_id}")
        assert found_total >= len(_HUMAN_COPY_PASTE_FILES), "스캔 대상이 비정상적으로 적다"
        assert not offenders, (
            "사람이 복사해 실행하는 clear 명령에 --as 가 없다 — 실행하면 대장에 "
            "cleared_by: claude(거짓 주체)가 남는다:\n  " + "\n  ".join(offenders)
        )

    def test_syntax_reference_shows_the_flag(self):
        """규약 정본(build_harness.md)의 *문법* 참조도 플래그를 노출한다.

        이 파일은 구체 게이트 ID가 아니라 `<id>` 자리표시자를 쓰므로 위 전수 스캔의 대상이
        아니다. 그러나 여기가 사람이 문법을 배우는 곳이라, 플래그가 안 보이면 복붙 명령을
        직접 쓸 때 빠뜨린다. 그래서 별도로 못박는다.
        """
        text = (_REPO / "docs" / "standards" / "build_harness.md").read_text(encoding="utf-8")
        assert "gates clear" in text, "정본에서 gates clear 서술이 사라졌다 — 목록을 갱신하라"
        clear_lines = [ln for ln in text.splitlines() if "gates clear" in ln]
        assert clear_lines
        assert any(
            "--as" in ln for ln in clear_lines
        ), "규약 정본의 gates clear 서술 어디에도 --as 가 없다"

    def test_exemptions_are_real_and_named(self):
        """면제는 *실재하는* 대상에만 붙고 사유가 적혀 있다(유령 면제·조용한 예외 금지)."""
        assert _EXEMPT, "면제가 없다면 목록 자체를 지워라 — 빈 dict는 의도를 감춘다"
        for rel, reason in _EXEMPT.items():
            assert reason.strip(), f"{rel}: 면제 사유가 비어 있다"
            assert rel not in _HUMAN_COPY_PASTE_FILES, f"{rel}: 스캔 대상이면서 면제일 수 없다"
            path = _REPO / rel
            assert path.exists(), f"{rel}: 면제 대상이 존재하지 않는다(유령 면제)"
            # 면제가 의미를 가지려면 그 파일에 실제로 구체 clear 명령이 있어야 한다.
            assert _lines_with_concrete_clear(
                path.read_text(encoding="utf-8")
            ), f"{rel}: 구체 clear 명령이 없다 — 면제할 것이 없으므로 목록에서 빼라"


class TestBoardEmitsAttributedCommand:
    """보드는 **생성된 산출물**로 검사한다 — 소스 문자열이 아니라 실제로 나오는 명령."""

    def test_generated_board_command_includes_assignee(self, git_repo: Path, monkeypatch):
        """보드가_낸_해소명령에_담당자플래그 — 대기 게이트가 있어야 의미가 있다."""
        monkeypatch.chdir(git_repo)
        import backlog as cli

        assert cli.main(["seed"]) == 0
        backlog_data, errors = store.load_backlog(git_repo)
        assert not errors, errors
        pending = [g for g in backlog_data.gates.values() if g.status == "pending"]
        assert pending, "seed에 대기 게이트가 없으면 이 검사는 아무것도 재현하지 못한다"
        assert any(g.assignee == "kiki" for g in pending), "kiki 담당 대기 게이트가 필요하다"

        payload = board.build_board(backlog_data, errors, date.today())
        html = board.render_html(payload)

        # 산출물에 담당자 인지형 플래그 조립이 들어 있어야 한다. 상수 문자열로 박아 두면
        # 담당자가 partner인 게이트에서 틀린 명령이 나오므로, 조립식인지를 본다.
        assert "--as ${g.assignee}" in html, "보드 명령이 담당자를 싣지 않는다"
        # 그리고 담당자 데이터가 실제로 payload에 실려 있어야 조립이 성립한다.
        assert '"assignee": "kiki"' in html or '"assignee":"kiki"' in html

    def test_agent_owned_gate_gets_no_flag(self):
        """담당자가 claude면 플래그를 붙이지 않는다 — `--as claude`는 선택지 자체가 아니다.

        이 방향이 없으면 "항상 --as를 붙이는" 구현도 통과한다(그 구현은 에이전트 소유 게이트에서
        argparse exit 2를 낸다).
        """
        source = (_REPO / "scripts" / "harness" / "board.py").read_text(encoding="utf-8")
        assert "g.assignee !== 'claude'" in source, "claude 담당 게이트의 예외 처리가 없다"
