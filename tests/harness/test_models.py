"""models.py — 스키마 검증 규칙 테스트."""

from __future__ import annotations

from models import Gate, Task, Track


def _valid_task(**overrides) -> Task:
    base = dict(
        id="S1-01-sample-task",
        title="샘플 태스크",
        track="math-completion",
        stage="S1",
        updated="2026-07-08",
    )
    base.update(overrides)
    return Task(**base)


class TestTaskValidation:
    def test_valid_task_has_no_errors(self):
        """정상 태스크는 오류 없음."""
        assert _valid_task().validate() == []

    def test_invalid_id_format_is_rejected(self):
        """잘못된 ID 형식 거부."""
        assert any("ID 형식" in e for e in _valid_task(id="s1_bad_id").validate())

    def test_unregistered_layer_is_rejected(self):
        """미등록 layer 거부."""
        # worktree 화이트리스트 7종 밖의 layer는 거부 (7계층 경계 강제)
        assert any("layer" in e for e in _valid_task(layer="frontend").validate())

    def test_unregistered_subject_is_rejected(self):
        """미등록 subject 거부."""
        assert any("subject" in e for e in _valid_task(subject="astrology").validate())

    def test_all_registered_subjects_pass(self):
        """등록된 전과목은 통과."""
        # 다과목 확장: 물리~세계사까지 전부 스키마가 수용해야 한다
        for subject in (
            "physics",
            "chemistry",
            "biology",
            "earth-science",
            "economics",
            "history",
            "world-history",
            "korean",
            "english",
        ):
            assert _valid_task(subject=subject).validate() == []

    def test_priority_out_of_range_is_rejected(self):
        """priority 범위 밖 거부."""
        assert any("priority" in e for e in _valid_task(priority=0).validate())
        assert any("priority" in e for e in _valid_task(priority=6).validate())

    def test_done_without_artifact_is_rejected(self):
        """done인데 증적 없으면 거부."""
        errors = _valid_task(status="done", artifacts=[]).validate()
        assert any("artifacts" in e for e in errors)

    def test_done_with_artifact_passes(self):
        """done이고 증적 있으면 통과."""
        assert _valid_task(status="done", artifacts=["PR #500"]).validate() == []

    def test_in_progress_without_session_is_rejected(self):
        """in progress인데 session 없으면 거부."""
        errors = _valid_task(status="in_progress", session=None).validate()
        assert any("session" in e for e in errors)

    def test_invalid_updated_format_is_rejected(self):
        """잘못된 updated 형식 거부."""
        assert any("updated" in e for e in _valid_task(updated="07/08/2026").validate())

    def test_gate_id_format_violation_is_rejected(self):
        """게이트 ID 형식 위반 거부."""
        errors = _valid_task(requires_gates=["phaiakes9"]).validate()
        assert any("게이트 ID" in e for e in errors)


class TestGateValidation:
    def test_valid_gate(self):
        """정상 게이트."""
        gate = Gate(id="G-sample-gate", title="샘플", requested="2026-07-08")
        assert gate.validate() == []

    def test_cleared_without_evidence_is_rejected(self):
        """cleared인데 evidence 없으면 거부."""
        gate = Gate(id="G-sample-gate", title="샘플", status="cleared")
        assert any("evidence" in e for e in gate.validate())

    def test_passed_decision(self):
        """passed 판정."""
        assert not Gate(id="G-a", title="t").passed
        assert Gate(id="G-a", title="t", status="cleared", evidence="PR").passed
        assert Gate(id="G-a", title="t", status="waived").passed


class TestTrackValidation:
    def test_valid_track(self):
        """정상 트랙."""
        assert Track(id="math-completion", title="수학 완성").validate() == []

    def test_entry_gate_format_violation_is_rejected(self):
        """entry gate 형식 위반 거부."""
        track = Track(id="t", title="제목", entry_gate="not-a-gate")
        assert any("entry_gate" in e for e in track.validate())


class TestTaskPaths:
    """paths 필드 — 파일 범위 선언 검증 (harness v1.1)."""

    def test_paths_defaults_to_empty_list_for_backward_compatibility(self):
        """paths 기본값은 빈 리스트 기존 태스크 하위호환."""
        task = _valid_task()
        assert task.paths == []
        assert task.validate() == []

    def test_valid_paths_pass(self):
        """정상 paths 통과."""
        task = _valid_task(paths=["src/backend/**", "docs/data/*.md"])
        assert task.validate() == []

    def test_absolute_path_is_rejected(self):
        """절대경로 거부."""
        errors = _valid_task(paths=["/etc/passwd"]).validate()
        assert any("절대경로" in e for e in errors)

    def test_parent_reference_is_rejected(self):
        """상위참조 거부."""
        errors = _valid_task(paths=["../outside/**"]).validate()
        assert any("상위 참조" in e for e in errors)

    def test_backslash_is_rejected(self):
        """백슬래시 거부."""
        errors = _valid_task(paths=["src\\backend\\**"]).validate()
        assert any("백슬래시" in e for e in errors)

    def test_paths_outside_layer_domain_only_warn(self):
        """layer 도메인 밖 paths는 경고만."""
        # backend 태스크가 mobile 폴더를 선언 — error가 아닌 warning (횡단 태스크 허용)
        task = _valid_task(layer="backend", paths=["src/mobile/**"])
        assert task.validate() == []
        assert any("도메인" in w for w in task.layer_drift_warnings())

    def test_paths_inside_layer_domain_do_not_warn(self):
        """layer 도메인 안 paths는 경고 없음."""
        task = _valid_task(layer="backend", paths=["src/backend/api/**"])
        assert task.layer_drift_warnings() == []
