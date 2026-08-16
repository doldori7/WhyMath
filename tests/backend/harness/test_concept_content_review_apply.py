"""concept_content_review_apply 단위테스트 — 코퍼스 JSON + DB 갱신(실 DB 없이)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.db.models.concept_content import (
    CONTENT_REVIEW_STATUS_AI_ESTIMATED,
    CONTENT_SCOPE_K12,
    CONTENT_SCOPE_UNIVERSITY,
)
from whymath_backend.harness.concept_content_review_apply import (
    LabelRow,
    apply_labels,
    load_labels,
    main,
)


class _FakeStore:
    """ConceptContentStore 표면 모사 — mark_review_status 호출 기록."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str]] = []

    def mark_review_status(self, codes: tuple[str, ...], status: str) -> int:
        self.calls.append((codes, status))
        return len(codes)


def _write_corpus(tmp_path: Path, *, scope: str, codes: list[str]) -> Path:
    path = tmp_path / f"{scope}.json"
    path.write_text(
        json.dumps(
            {
                "scope": scope,
                "content": [
                    {
                        "code": code,
                        "name": f"name-{code}",
                        "subject": "s",
                        "review_status": CONTENT_REVIEW_STATUS_AI_ESTIMATED,
                    }
                    for code in codes
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


class TestLoadLabels:
    def test_loads_reviewed_and_others(self, tmp_path: Path) -> None:
        path = tmp_path / "labels.jsonl"
        path.write_text(
            '{"code":"N1","review_status":"reviewed"}\n'
            '{"code":"N2","review_status":"rejected"}\n',
            encoding="utf-8",
        )
        rows = load_labels(path)
        assert [row.review_status for row in rows] == ["reviewed", "rejected"]

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "labels.jsonl"
        path.write_text('\n{"code":"N1","review_status":"reviewed"}\n\n', encoding="utf-8")
        assert len(load_labels(path)) == 1

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "labels.jsonl"
        path.write_text("not-json\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_labels(path)


class TestApplyLabels:
    def test_reviewed_updates_corpus_and_db(self, tmp_path: Path) -> None:
        k12 = _write_corpus(tmp_path, scope=CONTENT_SCOPE_K12, codes=["N1", "N2"])
        univ = _write_corpus(tmp_path, scope=CONTENT_SCOPE_UNIVERSITY, codes=["G1"])
        fake_store = _FakeStore()

        labels = [
            LabelRow("N1", "reviewed", "kiki", "2026-08-16T00:00:00Z"),
            LabelRow("N2", "ai_estimated", "kiki", "2026-08-16T00:00:00Z"),
        ]
        report = apply_labels(
            labels, k12_path=k12, university_path=univ, store=fake_store, dry_run=False
        )

        assert report.k12_updated == 1
        assert report.university_updated == 0
        assert report.db_updated == 1
        assert fake_store.calls == [(("N1",), "reviewed")]

        # K-12 JSON에만 반영되었는지 확인
        k12_data = json.loads(k12.read_text(encoding="utf-8"))
        statuses = {r["code"]: r["review_status"] for r in k12_data["content"]}
        assert statuses["N1"] == "reviewed"
        assert statuses["N2"] == CONTENT_REVIEW_STATUS_AI_ESTIMATED

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        k12 = _write_corpus(tmp_path, scope=CONTENT_SCOPE_K12, codes=["N1"])
        univ = _write_corpus(tmp_path, scope=CONTENT_SCOPE_UNIVERSITY, codes=["G1"])
        fake_store = _FakeStore()

        labels = [LabelRow("N1", "reviewed", "kiki", None)]
        report = apply_labels(
            labels, k12_path=k12, university_path=univ, store=fake_store, dry_run=True
        )

        assert report.k12_updated == 0
        assert report.university_updated == 0
        assert report.db_updated == 0
        assert fake_store.calls == []

        k12_data = json.loads(k12.read_text(encoding="utf-8"))
        assert k12_data["content"][0]["review_status"] == CONTENT_REVIEW_STATUS_AI_ESTIMATED

    def test_missing_code_in_corpus_is_reported(self, tmp_path: Path) -> None:
        k12 = _write_corpus(tmp_path, scope=CONTENT_SCOPE_K12, codes=["N1"])
        univ = _write_corpus(tmp_path, scope=CONTENT_SCOPE_UNIVERSITY, codes=[])
        labels = [LabelRow("MISSING", "reviewed", "kiki", None)]
        report = apply_labels(labels, k12_path=k12, university_path=univ, dry_run=True)
        assert report.missing_in_corpus == ["MISSING"]


class TestApplyCLI:
    def test_main_dry_run(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.jsonl"
        labels.write_text('{"code":"N1","review_status":"reviewed"}\n', encoding="utf-8")
        k12 = _write_corpus(tmp_path, scope=CONTENT_SCOPE_K12, codes=["N1"])
        univ = _write_corpus(tmp_path, scope=CONTENT_SCOPE_UNIVERSITY, codes=[])
        out = tmp_path / "report.json"

        rc = main(
            [
                "--labels",
                str(labels),
                "--k12",
                str(k12),
                "--university",
                str(univ),
                "--dry-run",
                "--json",
                str(out),
            ]
        )
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["approved_count"] == 1
        assert report["k12_updated"] == 0

    def test_main_missing_labels_returns_2(self, tmp_path: Path) -> None:
        rc = main(["--labels", str(tmp_path / "nope.jsonl")])
        assert rc == 2

    def test_main_missing_corpus_code_returns_1(self, tmp_path: Path) -> None:
        labels = tmp_path / "labels.jsonl"
        labels.write_text('{"code":"MISSING","review_status":"reviewed"}\n', encoding="utf-8")
        k12 = _write_corpus(tmp_path, scope=CONTENT_SCOPE_K12, codes=["N1"])
        univ = _write_corpus(tmp_path, scope=CONTENT_SCOPE_UNIVERSITY, codes=[])

        rc = main(
            [
                "--labels",
                str(labels),
                "--k12",
                str(k12),
                "--university",
                str(univ),
            ]
        )
        assert rc == 1
