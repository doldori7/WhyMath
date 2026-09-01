"""HARN-52 — 의존 선언↔집행 게이트의 계약 동결.

이 테스트가 지키는 것은 "탐지기가 존재한다"가 아니라 **"위반 상태에서 실제로 실패 신호를
낸다"** 이다(CLAUDE.md: 변별력 없는 검증 스텝 금지 — 성공/실패 양쪽에서 같은 값을 내는
검사는 검증이 아니라 위장이다). 그래서 각 축마다 *위반을 주입한 케이스*와 *정상 케이스*를
쌍으로 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import dep_declaration as dd


@dataclass
class FakeTask:
    """탐지기가 읽는 4필드만 가진 최소 대역 — harness models.Task와 구조 호환."""

    id: str
    status: str = "todo"
    notes: str = ""
    acceptance: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


def _tasks(*tasks: FakeTask) -> dict[str, FakeTask]:
    return {t.id: t for t in tasks}


# ── ① 핵심 변별력: 선언은 있고 집행이 없으면 잡고, 집행이 있으면 안 잡는다 ──────────


def test_undeclared_dependency_is_detected() -> None:
    """notes가 '선행'으로 지목했는데 depends_on이 비면 위반 — EOS-62 실사례의 재현."""
    tasks = _tasks(
        FakeTask(id="EOS-62-review-verdict", notes="선행: EOS-54-hit-timer 착지 후 착수"),
        FakeTask(id="EOS-54-hit-timer"),
    )
    findings = dd.find_undeclared_dependencies(tasks)
    assert len(findings) == 1
    assert findings[0].task_id == "EOS-62-review-verdict"
    assert findings[0].referenced == "EOS-54"


def test_declared_dependency_is_clean() -> None:
    """같은 notes라도 depends_on에 있으면 위반이 아니다 — 이 대비가 변별력의 증거다."""
    tasks = _tasks(
        FakeTask(
            id="EOS-62-review-verdict",
            notes="선행: EOS-54-hit-timer 착지 후 착수",
            depends_on=["EOS-54-hit-timer"],
        ),
        FakeTask(id="EOS-54-hit-timer"),
    )
    assert dd.find_undeclared_dependencies(tasks) == []


# ── ② 오탐 억제: 잡지 *않아야* 하는 것들 ─────────────────────────────────────


def test_plain_mention_without_ordering_phrase_is_not_a_dependency() -> None:
    """단순 언급은 의존 선언이 아니다 — 어구 없이 ID만 있으면 통과."""
    tasks = _tasks(
        FakeTask(id="A-1-x", notes="EOS-54-hit-timer 가 만든 계측기를 재사용한다"),
        FakeTask(id="EOS-54-hit-timer"),
    )
    assert dd.find_undeclared_dependencies(tasks) == []


def test_reference_to_done_task_is_not_a_violation() -> None:
    """참조 대상이 done이면 순서 제약이 실효 없다 — 과거형 서술까지 잡으면 소음이 된다."""
    tasks = _tasks(
        FakeTask(id="A-1-x", notes="선행: EOS-54-hit-timer 착지 후"),
        FakeTask(id="EOS-54-hit-timer", status="done"),
    )
    assert dd.find_undeclared_dependencies(tasks) == []


def test_acceptance_prose_is_not_scanned() -> None:
    """acceptance는 사양 산문이라 오탐원 — notes만 본다(실측 근거는 모듈 docstring)."""
    tasks = _tasks(
        FakeTask(
            id="A-1-x",
            acceptance=["ⓐ진짜 선행 → 부착 / ⓑ소프트 권고(EOS-54-hit-timer 사례)"],
        ),
        FakeTask(id="EOS-54-hit-timer"),
    )
    assert dd.find_undeclared_dependencies(tasks) == []


def test_done_task_is_not_scanned() -> None:
    """완료된 태스크는 착수 대상이 아니므로 순서 강제가 무의미하다."""
    tasks = _tasks(
        FakeTask(id="A-1-x", status="done", notes="선행: EOS-54-hit-timer"),
        FakeTask(id="EOS-54-hit-timer"),
    )
    assert dd.find_undeclared_dependencies(tasks) == []


def test_unknown_reference_is_ignored() -> None:
    """저장소에 없는 ID 참조는 이 게이트의 책임 밖(오타·외부 표기)."""
    tasks = _tasks(FakeTask(id="A-1-x", notes="선행: NOPE-99-ghost 착지 후"))
    assert dd.find_undeclared_dependencies(tasks) == []


# ── ③ 그랜드파더와 만료 계약 (ARCH-25 패턴) ──────────────────────────────────


def test_exemption_suppresses_and_can_be_bypassed(monkeypatch) -> None:
    """면제는 판정에서 빼되, --all(감사 모드)에서는 그대로 보인다."""
    tasks = _tasks(
        FakeTask(id="A-1-x", notes="선행: EOS-54-hit-timer 착지 후"),
        FakeTask(id="EOS-54-hit-timer"),
        FakeTask(id="T-1-triage"),
    )
    monkeypatch.setattr(dd, "LEGACY_EXEMPT", {"A-1-x": "T-1-triage"})
    assert dd.find_undeclared_dependencies(tasks) == []
    assert len(dd.find_undeclared_dependencies(tasks, apply_exemptions=False)) == 1


def test_expiry_fires_when_triage_task_is_done(monkeypatch) -> None:
    """해소 태스크가 done인데 면제가 남으면 만료 위반 — 만료 없는 유예 금지의 집행."""
    tasks = _tasks(FakeTask(id="A-1-x"), FakeTask(id="T-1-triage", status="done"))
    monkeypatch.setattr(dd, "LEGACY_EXEMPT", {"A-1-x": "T-1-triage"})
    violations = dd.find_expiry_violations(tasks)
    assert len(violations) == 1
    assert "만료" in violations[0]


def test_expiry_silent_while_triage_open(monkeypatch) -> None:
    """해소 태스크가 살아 있으면 만료가 아니다 — 위 테스트의 대조군."""
    tasks = _tasks(FakeTask(id="A-1-x"), FakeTask(id="T-1-triage", status="todo"))
    monkeypatch.setattr(dd, "LEGACY_EXEMPT", {"A-1-x": "T-1-triage"})
    assert dd.find_expiry_violations(tasks) == []


def test_expiry_catches_dangling_exemption(monkeypatch) -> None:
    """추적 불가능한 면제(대상·해소 태스크가 백로그에 없음)도 위반이다."""
    monkeypatch.setattr(dd, "LEGACY_EXEMPT", {"GONE-1-x": "ALSO-GONE-1-y"})
    assert len(dd.find_expiry_violations({})) == 2


# ── ④ 실제 저장소 대장이 green인가 (게이트가 오늘부터 유효한지) ────────────────


def test_repository_backlog_is_green() -> None:
    """실 대장에서 위반 0·만료 0 — 게이트가 red로 출발하면 사람이 게이트를 끈다."""
    from pathlib import Path

    import store

    root = Path(__file__).resolve().parents[2]
    backlog, _ = store.load_backlog(root)
    assert dd.find_expiry_violations(backlog.tasks) == []
    findings = dd.find_undeclared_dependencies(backlog.tasks)
    assert findings == [], "\n".join(f.render() for f in findings)
