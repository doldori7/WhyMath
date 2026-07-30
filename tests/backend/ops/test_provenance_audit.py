"""provenance_audit hermetic 테스트 — ARCH-20. 실 data/corpus에 결합하지 않는다(픽스처
디렉터리로 코퍼스 루트를 통째로 대체 — `--corpus-root`).

검증 대상: ① 정상 코퍼스 → exit 0 ② 사이드카 부재(비그랜드파더) → exit 1·SIDECAR_MISSING
③ 그랜드파더 코퍼스는 사이드카 부재라도 위반이 아니라 grandfathered로 분류 ④ pool 누락 →
SCHEMA_INVALID ⑤ problems.jsonl 레코드 license/source_type 결손 → RECORD_FIELDS_MISSING
⑥ 코퍼스 루트 자체가 없으면 CORPUS_ROOT_MISSING ⑦ 그랜드파더 항목은 전부 사유 문자열을
가진다(거버넌스 — 빈 사유 등재 차단).
"""

from __future__ import annotations

import json
from pathlib import Path

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
        grandfathered_name = next(iter(pa._KNOWN_GAPS))
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
    """그랜드파더 목록 자체의 위생 — 빈 사유 등재 차단(HARN-10류 선례 동형)."""

    def test_every_grandfathered_entry_has_a_non_empty_reason(self) -> None:
        assert pa._KNOWN_GAPS, "그랜드파더 목록이 비었다 — 실제로 pending 5종이 있어야 한다."
        for corpus_name, reason in pa._KNOWN_GAPS.items():
            assert reason.strip(), f"{corpus_name}의 그랜드파더 사유가 비어 있다."


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
