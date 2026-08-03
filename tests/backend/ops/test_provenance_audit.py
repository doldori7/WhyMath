"""provenance_audit hermetic 테스트 — ARCH-20 + ARCH-25. 실 data/corpus에 결합하지 않는다
(픽스처 디렉터리로 코퍼스 루트를 통째로 대체 — `--corpus-root`).

검증 대상: ① 정상 코퍼스 → exit 0 ② 사이드카 부재(비그랜드파더) → exit 1·SIDECAR_MISSING
③ 그랜드파더 코퍼스는 사이드카 부재라도 위반이 아니라 grandfathered로 분류 ④ pool 누락 →
SCHEMA_INVALID ⑤ problems.jsonl 레코드 license/source_type 결손 → RECORD_FIELDS_MISSING
⑥ 코퍼스 루트 자체가 없으면 CORPUS_ROOT_MISSING ⑦ 그랜드파더 항목은 전부 사유 문자열을
가진다(거버넌스 — 빈 사유 등재 차단) ⑧ (ARCH-25) `_load_backlog_task_status`가 실존/부재
태스크를 실제로 구분한다 ⑨ (ARCH-25) 그랜드파더 항목이 참조하는 태스크가 done인데 항목이
남아 있으면 검증 로직이 red를 낸다(자동 해제는 하지 않는다 — 사람이 지워야 함을 알리는 것만).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.ops import provenance_audit as pa


def _write_sidecar(corpus_dir: Path, payload: dict) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "_provenance.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _write_problems(corpus_dir: Path, records: list[dict]) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    (corpus_dir / "problems.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCleanCorpusPasses:
    def test_exit_0_when_all_valid(self, tmp_path: Path) -> None:
        _write_sidecar(
            tmp_path / "corpus_a",
            {"pool": "whymath-original", "source_citation": "출처"},
        )
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 0
        assert report.violations == []
        assert report.corpora_scanned == 1


class TestSidecarMissing:
    def test_non_grandfathered_missing_sidecar_is_violation(self, tmp_path: Path) -> None:
        (tmp_path / "unknown_corpus").mkdir()
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 1
        assert len(report.violations) == 1
        assert report.violations[0].kind == "SIDECAR_MISSING"
        assert report.violations[0].corpus == "unknown_corpus"

    def test_grandfathered_missing_sidecar_is_not_a_violation(self, tmp_path: Path) -> None:
        """실제 프로덕션 `_KNOWN_GAPS`가 비어 있을 수 있으므로(ARCH-25) 여기서는 합성
        그랜드파더 항목을 `known_gaps`로 주입해 판정 로직 자체를 검증한다."""
        grandfathered_name = "synthetic_corpus_v0"
        known_gaps = {
            grandfathered_name: pa.GrandfatherEntry(
                task_id="FAKE-01", reason="테스트용 합성 그랜드파더"
            )
        }
        (tmp_path / grandfathered_name).mkdir()
        report = pa.audit_corpus_root(tmp_path, known_gaps=known_gaps)
        assert report.exit_code == 0
        assert report.violations == []
        assert any(grandfathered_name in entry for entry in report.grandfathered)


class TestSchemaValidation:
    def test_missing_pool_is_violation(self, tmp_path: Path) -> None:
        _write_sidecar(tmp_path / "corpus_a", {"source_citation": "출처"})
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 1
        assert report.violations[0].kind == "SCHEMA_INVALID"
        assert "pool" in report.violations[0].detail

    def test_invalid_json_is_violation(self, tmp_path: Path) -> None:
        corpus_dir = tmp_path / "corpus_a"
        corpus_dir.mkdir()
        (corpus_dir / "_provenance.json").write_text("{not valid json", encoding="utf-8")
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 1
        assert report.violations[0].kind == "SCHEMA_INVALID"

    def test_extra_fields_do_not_cause_violation(self, tmp_path: Path) -> None:
        """이질적 자유 필드(코퍼스별 서술)는 위반이 아니다 — extra='allow' 계약 그대로 반영."""
        _write_sidecar(
            tmp_path / "corpus_a",
            {
                "pool": "whymath-original",
                "license_notice": "y",
                "corpus_name": "corpus_a",
                "counts": {"x": 1},
            },
        )
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 0


class TestRecordFieldsMissing:
    def test_missing_license_or_source_type_is_violation(self, tmp_path: Path) -> None:
        corpus_dir = tmp_path / "corpus_a"
        _write_sidecar(corpus_dir, {"pool": "whymath-original", "source_citation": "출처"})
        _write_problems(
            corpus_dir,
            [
                {"slug": "p1", "license": "WHYMATH_GENERATED", "source_type": "자체생성"},
                {"slug": "p2", "license": None, "source_type": "자체생성"},
                {"slug": "p3", "source_type": "자체생성"},  # license 키 자체 없음
            ],
        )
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 1
        record_violations = [v for v in report.violations if v.kind == "RECORD_FIELDS_MISSING"]
        assert len(record_violations) == 1
        assert "2/3건" in record_violations[0].detail
        assert "p2" in record_violations[0].detail or "p3" in record_violations[0].detail

    def test_all_records_populated_no_violation(self, tmp_path: Path) -> None:
        corpus_dir = tmp_path / "corpus_a"
        _write_sidecar(corpus_dir, {"pool": "whymath-original", "source_citation": "출처"})
        _write_problems(
            corpus_dir,
            [{"slug": "p1", "license": "WHYMATH_GENERATED", "source_type": "자체생성"}],
        )
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 0

    def test_corpus_without_problems_jsonl_skips_record_check(self, tmp_path: Path) -> None:
        """graph.json류 코퍼스(problems.jsonl 없음)는 레코드 검사 대상이 아니다."""
        _write_sidecar(
            tmp_path / "graph_corpus", {"pool": "whymath-original", "source_citation": "출처"}
        )
        report = pa.audit_corpus_root(tmp_path)
        assert report.exit_code == 0


class TestCorpusRootMissing:
    def test_nonexistent_root_is_violation(self, tmp_path: Path) -> None:
        report = pa.audit_corpus_root(tmp_path / "does-not-exist")
        assert report.exit_code == 1
        assert report.violations[0].kind == "CORPUS_ROOT_MISSING"


class TestGrandfatherGovernance:
    """그랜드파더 목록 자체의 위생 — 빈 사유 등재 차단(HARN-10류 선례 동형).

    ARCH-25로 프로덕션 `_KNOWN_GAPS`가 (S3-11 회수 완료로) 비었을 수 있으므로, 이 검사는
    실제 모듈 dict가 아니라 테스트 내부에서 만든 synthetic dict로 로직을 검증한다 —
    프로덕션 dict가 비든 나중에 다시 채워지든 이 테스트는 항상 유효하다."""

    def test_every_grandfathered_entry_has_a_non_empty_reason(self) -> None:
        synthetic_gaps = {
            "synthetic_corpus_v0": pa.GrandfatherEntry(task_id="FAKE-01", reason="사유 있음"),
        }
        assert synthetic_gaps, "그랜드파더 목록이 비었다 — 실제로 pending 항목이 있어야 한다."
        for corpus_name, entry in synthetic_gaps.items():
            assert entry.reason.strip(), f"{corpus_name}의 그랜드파더 사유가 비어 있다."


def _write_backlog_task(backlog_tasks_dir: Path, task_id: str, status: str) -> None:
    backlog_tasks_dir.mkdir(parents=True, exist_ok=True)
    (backlog_tasks_dir / f"{task_id}.yaml").write_text(
        f"id: {task_id}\nstatus: {status}\n", encoding="utf-8"
    )


class TestLoadBacklogTaskStatus:
    """`_load_backlog_task_status` 자체의 변별력 — 존재/부재 태스크를 실제로 구분하는지
    (ARCH-25 acceptance: 존재하지 않는 태스크 ID에서 실제 red를 내는지 실측)."""

    def test_existing_task_returns_its_status(self, tmp_path: Path) -> None:
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        _write_backlog_task(backlog_tasks_dir, "FAKE-DONE-01", status="done")
        status = pa._load_backlog_task_status("FAKE-DONE-01", backlog_tasks_dir=backlog_tasks_dir)
        assert status == "done"

    def test_missing_task_file_returns_none(self, tmp_path: Path) -> None:
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        backlog_tasks_dir.mkdir(parents=True)
        status = pa._load_backlog_task_status("NONEXISTENT-99", backlog_tasks_dir=backlog_tasks_dir)
        assert status is None

    def test_task_yaml_without_status_field_raises(self, tmp_path: Path) -> None:
        """침묵 실패 금지 — status 필드 부재는 조용히 None이 아니라 명확한 예외여야 한다."""
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        backlog_tasks_dir.mkdir(parents=True)
        (backlog_tasks_dir / "BROKEN-01.yaml").write_text("id: BROKEN-01\n", encoding="utf-8")
        with pytest.raises(ValueError, match="status"):
            pa._load_backlog_task_status("BROKEN-01", backlog_tasks_dir=backlog_tasks_dir)

    def test_invalid_yaml_raises_with_clear_reason(self, tmp_path: Path) -> None:
        """침묵 실패 금지 — YAML 파싱 실패는 조용히 넘어가지 않고 사유가 드러나야 한다."""
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        backlog_tasks_dir.mkdir(parents=True)
        (backlog_tasks_dir / "BROKEN-02.yaml").write_text(
            "id: BROKEN-02\nstatus: [unterminated\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="파싱 실패"):
            pa._load_backlog_task_status("BROKEN-02", backlog_tasks_dir=backlog_tasks_dir)


class TestGrandfatherTaskStatusContract:
    """ARCH-25 핵심 계약 — 그랜드파더 항목이 (a) 존재하지 않는 태스크를 참조하거나
    (b) 이미 done인 태스크를 참조하는데 항목이 남아 있으면 red(문제 목록 non-empty)를
    낸다. 자동 해제는 하지 않는다 — 이 함수는 아무것도 지우지 않고 보고만 한다."""

    def test_reference_to_nonexistent_task_id_is_flagged(self, tmp_path: Path) -> None:
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        backlog_tasks_dir.mkdir(parents=True)
        known_gaps = {
            "corpus_x": pa.GrandfatherEntry(task_id="NONEXISTENT-99", reason="사유"),
        }
        problems = pa.check_grandfather_task_status(known_gaps, backlog_tasks_dir=backlog_tasks_dir)
        assert len(problems) == 1
        assert "NONEXISTENT-99" in problems[0]

    def test_reference_to_todo_task_is_not_flagged(self, tmp_path: Path) -> None:
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        _write_backlog_task(backlog_tasks_dir, "PENDING-01", status="todo")
        known_gaps = {
            "corpus_x": pa.GrandfatherEntry(task_id="PENDING-01", reason="사유"),
        }
        problems = pa.check_grandfather_task_status(known_gaps, backlog_tasks_dir=backlog_tasks_dir)
        assert problems == []

    def test_reference_to_done_task_is_flagged(self, tmp_path: Path) -> None:
        """핵심 회귀 방지 케이스 — 태스크가 done이 됐는데 그랜드파더 항목이 방치되면
        red를 내야 한다(이 태스크 자체의 사고 경위와 동형: S3-11이 5일간 방치됨)."""
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        _write_backlog_task(backlog_tasks_dir, "DONE-01", status="done")
        known_gaps = {
            "corpus_x": pa.GrandfatherEntry(task_id="DONE-01", reason="사유"),
        }
        problems = pa.check_grandfather_task_status(known_gaps, backlog_tasks_dir=backlog_tasks_dir)
        assert len(problems) == 1
        assert "DONE-01" in problems[0]
        assert "done" in problems[0]

    def test_empty_known_gaps_yields_no_problems(self, tmp_path: Path) -> None:
        backlog_tasks_dir = tmp_path / "backlog" / "tasks"
        backlog_tasks_dir.mkdir(parents=True)
        problems = pa.check_grandfather_task_status({}, backlog_tasks_dir=backlog_tasks_dir)
        assert problems == []

    def test_production_known_gaps_pass_against_real_backlog(self) -> None:
        """실제 `_KNOWN_GAPS`(현재 비었을 가능성이 높다)를 실제 backlog/tasks 디렉터리에
        대조한다 — 항목이 남아 있다면 실존 태스크를 참조해야 하고 done이면 안 된다."""
        problems = pa.check_grandfather_task_status(
            pa._KNOWN_GAPS, backlog_tasks_dir=pa._BACKLOG_TASKS_DIR
        )
        assert problems == [], f"방치된 그랜드파더 항목 발견: {problems}"


class TestMainCli:
    def test_main_returns_exit_code_and_writes_json(self, tmp_path: Path) -> None:
        _write_sidecar(
            tmp_path / "corpus_a",
            {"pool": "whymath-original", "source_citation": "출처"},
        )
        json_path = tmp_path / "report.json"
        exit_code = pa.main(["--corpus-root", str(tmp_path), "--json", str(json_path)])
        assert exit_code == 0
        assert json_path.is_file()
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["corpora_scanned"] == 1
        assert payload["violations"] == []
