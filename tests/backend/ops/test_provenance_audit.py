"""provenance_audit hermetic 테스트 — ARCH-20/ARCH-25. 실 data/corpus에 결합하지 않는다
(픽스처 디렉터리로 코퍼스 루트를 통째로 대체 — `--corpus-root`). 그랜드파더 만료 계약
테스트(`TestGrandfatherExpiryContract`)만 예외로, 실 `backlog/tasks`를 읽는 테스트 1건과
`tmp_path` 픽스처로 완전 격리한 monkeypatch 테스트 3건으로 나뉜다(각 테스트 docstring 참조).

검증 대상: ① 정상 코퍼스 → exit 0 ② 사이드카 부재(비그랜드파더) → exit 1·SIDECAR_MISSING
③ 그랜드파더 코퍼스는 사이드카 부재라도 위반이 아니라 grandfathered로 분류 ④ pool 누락 →
SCHEMA_INVALID ⑤ problems.jsonl 레코드 license/source_type 결손 → RECORD_FIELDS_MISSING
⑥ 코퍼스 루트 자체가 없으면 CORPUS_ROOT_MISSING ⑦ 그랜드파더 항목은 전부 task_id·사유
non-empty(거버넌스) ⑧ 그랜드파더 만료 계약(ARCH-25) — task_id가 backlog/tasks/*.yaml에
실재하지 않거나, 참조된 태스크가 이미 done인데 항목이 남아 있으면 위반으로 잡는다(자동
해제 아님 — 방치를 구조적으로 드러내는 트립와이어).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

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

    def test_grandfathered_missing_sidecar_is_not_a_violation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """그랜드파더 항목(테스트 전용 더블)이 있으면 사이드카 부재라도 위반이 아니다.

        실 `_KNOWN_GAPS`(2026-08-03 ARCH-25 S3-11 회수로 빈 딕셔너리)에 결합하지 않는다 —
        monkeypatch로 테스트 전용 항목을 주입해 이 테스트를 프로덕션 그랜드파더 상태와
        독립시킨다(그랜드파더가 전부 해소돼도 이 동작 자체는 계속 검증돼야 한다).
        """
        grandfathered_name = "some_pending_corpus"
        monkeypatch.setattr(
            pa,
            "_KNOWN_GAPS",
            {
                grandfathered_name: pa.GrandfatherEntry(
                    task_id="TEST-TASK-ID", reason="테스트용 그랜드파더 사유"
                )
            },
        )
        (tmp_path / grandfathered_name).mkdir()
        report = pa.audit_corpus_root(tmp_path)
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
    """그랜드파더 항목 자체의 위생 — task_id·사유 모두 non-empty(HARN-10류 선례 동형).

    2026-08-03 ARCH-25(S3-11 회수 — `4293da24` 커밋 회수로 문제은행 v0 5종 사이드카가 트렁크에
    실재하게 됨)로 실 `_KNOWN_GAPS`는 빈 딕셔너리다(그랜드파더 전부 해소). 아래 루프는 지금은
    공허하게 참이지만, 향후 새 그랜드파더가 등재될 때의 위생(빈 task_id·빈 사유 등재 차단)을
    계속 동결해 둔다.
    """

    def test_every_grandfathered_entry_has_non_empty_task_id_and_reason(self) -> None:
        for corpus_name, entry in pa._KNOWN_GAPS.items():
            assert entry.task_id.strip(), f"{corpus_name}의 task_id가 비어 있다."
            assert entry.reason.strip(), f"{corpus_name}의 그랜드파더 사유가 비어 있다."


def _write_task_yaml(tasks_dir: Path, task_id: str, status: str) -> None:
    """백로그 태스크 YAML 최소 픽스처(그랜드파더 만료 계약 테스트 전용 — 실 스키마 전 필드가
    아니라 `find_grandfather_expiry_violations`가 실제로 읽는 `id`·`status`만 담는다)."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{task_id}.yaml").write_text(
        yaml.safe_dump({"id": task_id, "status": status}, allow_unicode=True),
        encoding="utf-8",
    )


class TestGrandfatherExpiryContract:
    """그랜드파더 만료 계약(ARCH-25) — task_id 참조 무결성 + done 방치 트립와이어.

    `_KNOWN_GAPS`의 각 항목이 ①실재하는 backlog 태스크를 참조하는지 ②참조된 태스크가 이미
    done인데 항목이 방치되지 않았는지를 상시 대조한다. 자동 해제가 아니다 — 해제는 여전히
    사람 판단이고, 이 계약은 방치를 구조적으로 드러내는 트립와이어일 뿐이다.

    변별력 확인(CLAUDE.md "변별력 없는 검증 스텝 금지"): monkeypatch로 `_KNOWN_GAPS`를 테스트
    전용 딕셔너리로 교체해 ①②가 실제로 위반을 검출하는지(red)와, 정상 상태에서는 검출하지
    않는지(green)를 모두 확인한다 — 성공/성공 또는 실패/실패로 같은 값이 나오면 위장이다.
    """

    def test_real_known_gaps_reference_real_and_non_done_tasks(self) -> None:
        """저장소의 실 `_KNOWN_GAPS`(2026-08-03 기준 빈 딕셔너리 — S3-11 회수로 전부 해소)가
        계약을 위반하지 않는다. `_KNOWN_GAPS`가 비어 있으면 이 테스트는 자명하게 통과한다 —
        지금 뭔가를 잡으려는 게 아니라, 향후 재발 방지 트립와이어로서 상시 배선해 두는 것이
        핵심이다(아래 monkeypatch 테스트가 변별력을 실측한다)."""
        violations = pa.find_grandfather_expiry_violations()
        assert violations == [], f"그랜드파더 만료 계약 위반: {violations}"

    def test_nonexistent_task_id_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """① 실존하지 않는 task_id를 가리키는 그랜드파더 항목은 위반으로 잡혀야 한다(red).

        참조 대상 태스크 파일을 아예 만들지 않는다 — "존재하지 않는 ID" 시나리오를 그대로
        재현(가짜 ID를 실 `_KNOWN_GAPS`에 임시로 넣어 직접 돌려본 뒤 이 단언으로 고정했다)."""
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        monkeypatch.setattr(
            pa,
            "_KNOWN_GAPS",
            {
                "fake_corpus": pa.GrandfatherEntry(
                    task_id="NONEXISTENT-TASK-ID-XYZ", reason="테스트용 사유"
                )
            },
        )
        violations = pa.find_grandfather_expiry_violations(tasks_dir=tasks_dir)
        assert len(violations) == 1
        assert "NONEXISTENT-TASK-ID-XYZ" in violations[0]

    def test_done_task_still_grandfathered_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """② 참조된 태스크가 이미 done인데 그랜드파더 항목이 남아 있으면 위반으로 잡혀야
        한다(red) — "방치" 시나리오(태스크는 끝났는데 면제만 안 지워진 상태)를 재현한다."""
        tasks_dir = tmp_path / "tasks"
        _write_task_yaml(tasks_dir, "FAKE-DONE-TASK", status="done")
        monkeypatch.setattr(
            pa,
            "_KNOWN_GAPS",
            {"fake_corpus": pa.GrandfatherEntry(task_id="FAKE-DONE-TASK", reason="테스트용 사유")},
        )
        violations = pa.find_grandfather_expiry_violations(tasks_dir=tasks_dir)
        assert len(violations) == 1
        assert "FAKE-DONE-TASK" in violations[0]

    def test_todo_task_is_not_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """대조군(green) — 참조된 태스크가 아직 done이 아니면 위반이 아니다. ②가 done 여부로
        실제 갈리는지(같은 코드 경로에서 done만 다르게) 확인해 변별력을 보강한다."""
        tasks_dir = tmp_path / "tasks"
        _write_task_yaml(tasks_dir, "FAKE-TODO-TASK", status="todo")
        monkeypatch.setattr(
            pa,
            "_KNOWN_GAPS",
            {"fake_corpus": pa.GrandfatherEntry(task_id="FAKE-TODO-TASK", reason="테스트용 사유")},
        )
        violations = pa.find_grandfather_expiry_violations(tasks_dir=tasks_dir)
        assert violations == []


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
