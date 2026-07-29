"""store.py — 직렬화 왕복·무결성 검증 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import store
from models import Gate, Task, Track


def _write_minimal_backlog(
    root: Path,
    tasks: list[Task],
    gates: list[Gate] | None = None,
    stage_order: list[str] | None = None,
) -> None:
    store.save_tracks(
        root,
        stage_order or ["S1", "S2"],
        [
            Track(id="math-completion", title="수학 완성"),
            Track(id="locked-track", title="잠긴 트랙", entry_gate="G-lock"),
        ],
    )
    store.save_gates(
        root,
        (
            gates
            if gates is not None
            else [
                Gate(id="G-lock", title="잠금 게이트", requested="2026-07-01"),
            ]
        ),
    )
    for task in tasks:
        store.save_task(root, task)


def _task(**overrides) -> Task:
    base = dict(
        id="S1-01-alpha", title="알파", track="math-completion", stage="S1", updated="2026-07-08"
    )
    base.update(overrides)
    return Task(**base)


class TestRoundtrip:
    def test_task_save_then_load_roundtrips(self, tmp_path: Path):
        """태스크 저장 후 로드 동일."""
        original = _task(
            title='제목: 콜론·"인용"·한글 포함',
            depends_on=["S1-02-beta"],
            acceptance=["항목 1: 콜론 포함", "항목 2"],
            notes="비고",
            priority=2,
        )
        _write_minimal_backlog(tmp_path, [original, _task(id="S1-02-beta", title="베타")])
        backlog, errors = store.load_backlog(tmp_path)
        assert errors == []
        loaded = backlog.tasks["S1-01-alpha"]
        assert loaded == original

    def test_gate_save_then_load_roundtrips(self, tmp_path: Path):
        """게이트 저장 후 로드 동일."""
        gate = Gate(
            id="G-sample",
            title="샘플 게이트",
            requested="2026-07-05",
            remind_after_days=7,
            notes="비고",
        )
        _write_minimal_backlog(
            tmp_path,
            [_task()],
            gates=[
                Gate(id="G-lock", title="잠금"),
                gate,
            ],
        )
        backlog, _ = store.load_backlog(tmp_path)
        assert backlog.gates["G-sample"] == gate

    def test_serialization_output_is_deterministic(self, tmp_path: Path):
        """직렬화 출력은 결정적."""
        # 같은 태스크를 두 번 저장하면 바이트 단위로 동일해야 한다 (diff 안정)
        task = _task()
        first = store.dump_task(task)
        second = store.dump_task(task)
        assert first == second


class TestLoadErrors:
    def test_detects_id_filename_mismatch(self, tmp_path: Path):
        """id와 파일명 불일치 검출."""
        _write_minimal_backlog(tmp_path, [])
        path = tmp_path / "backlog" / "tasks" / "S1-99-wrong-name.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(store.dump_task(_task(id="S1-01-alpha")), encoding="utf-8")
        _, errors = store.load_backlog(tmp_path)
        assert any("파일명" in e for e in errors)

    def test_detects_unknown_field(self, tmp_path: Path):
        """미지 필드 검출."""
        _write_minimal_backlog(tmp_path, [])
        path = tmp_path / "backlog" / "tasks" / "S1-01-alpha.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(store.dump_task(_task()) + "renderer: manim\n", encoding="utf-8")
        _, errors = store.load_backlog(tmp_path)
        assert any("미지 필드" in e for e in errors)


class TestValidateBacklog:
    def test_valid_backlog_is_green(self, tmp_path: Path):
        """정상 백로그는 green."""
        _write_minimal_backlog(tmp_path, [_task()])
        backlog, schema_errors = store.load_backlog(tmp_path)
        assert store.validate_backlog(backlog, schema_errors) == []

    def test_detects_missing_dependency(self, tmp_path: Path):
        """미존재 의존성 검출."""
        _write_minimal_backlog(tmp_path, [_task(depends_on=["S1-99-ghost"])])
        backlog, schema_errors = store.load_backlog(tmp_path)
        errors = store.validate_backlog(backlog, schema_errors)
        assert any("미존재" in e for e in errors)

    def test_detects_missing_gate(self, tmp_path: Path):
        """미존재 게이트 검출."""
        _write_minimal_backlog(tmp_path, [_task(requires_gates=["G-ghost"])])
        backlog, schema_errors = store.load_backlog(tmp_path)
        assert any("G-ghost" in e for e in store.validate_backlog(backlog, schema_errors))

    def test_detects_undefined_track(self, tmp_path: Path):
        """미정의 track 검출."""
        _write_minimal_backlog(tmp_path, [_task(track="ghost-track")])
        backlog, schema_errors = store.load_backlog(tmp_path)
        assert any("track" in e for e in store.validate_backlog(backlog, schema_errors))

    def test_detects_stage_outside_stage_order(self, tmp_path: Path):
        """stage order 밖 stage 검출."""
        _write_minimal_backlog(tmp_path, [_task(stage="S9")])
        backlog, schema_errors = store.load_backlog(tmp_path)
        assert any("stage_order" in e for e in store.validate_backlog(backlog, schema_errors))

    def test_detects_roadmap_order_violation(self, tmp_path: Path):
        """로드맵 순서 위반 검출."""
        # S1 태스크가 S2(후행) 태스크에 의존하면 로드맵 순서 위반
        _write_minimal_backlog(
            tmp_path,
            [
                _task(id="S1-01-alpha", depends_on=["S2-01-later"]),
                _task(id="S2-01-later", stage="S2"),
            ],
        )
        backlog, schema_errors = store.load_backlog(tmp_path)
        assert any("순서 위반" in e for e in store.validate_backlog(backlog, schema_errors))

    def test_detects_circular_dependency(self, tmp_path: Path):
        """순환 참조 검출."""
        _write_minimal_backlog(
            tmp_path,
            [
                _task(id="S1-01-alpha", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", depends_on=["S1-01-alpha"], title="베타"),
            ],
        )
        backlog, schema_errors = store.load_backlog(tmp_path)
        errors = store.validate_backlog(backlog, schema_errors)
        assert any("순환" in e for e in errors)

    def test_detects_multiple_claims_per_session(self, tmp_path: Path):
        """1세션 다중 claim 검출."""
        _write_minimal_backlog(
            tmp_path,
            [
                _task(id="S1-01-alpha", status="in_progress", session="branch-x"),
                _task(id="S1-02-beta", title="베타", status="in_progress", session="branch-x"),
            ],
        )
        backlog, schema_errors = store.load_backlog(tmp_path)
        errors = store.validate_backlog(backlog, schema_errors)
        assert any("동시 claim" in e for e in errors)


class TestEvents:
    def test_events_are_appended_as_ndjson(self, tmp_path: Path, git_repo: Path):
        """이벤트는 ndjson으로 append."""
        store.append_event(git_repo, "start", "S1-01-alpha", session="b1")
        store.append_event(git_repo, "done", "S1-01-alpha", artifacts=["PR#1"])
        lines = (git_repo / "backlog" / "events.ndjson").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["action"] == "start"
        assert first["id"] == "S1-01-alpha"
        assert "ts" in first and "actor" in first
