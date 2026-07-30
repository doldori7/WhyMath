"""문제 유형(problem_type_codes) 백필 CLI(S3-27) — 바이트 계약·멱등·제외 코퍼스 단위테스트.

핵심 봉인(`problem_corpus_tag` 패턴 동형): ① 미태깅 레코드에 적용하면 `problem_type_codes` 키만
추가되고 나머지 바이트는 그대로 ② 이미 태깅된 레코드는 재적용해도 바이트 무변경(멱등) ③ dry-run은
파일 미기록·통계만 ④ `problem_bank_rephrased_v0`는 열지도 쓰지도 않되 행 수는 정직하게 센다.
LLM·DB 0(순수 결정론).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.problem_type_backfill import main, run_backfill
from whymath_backend.harness.problem_type_mapping import (
    CORPUS_GENERATED_V0,
    CORPUS_REPHRASED_V0,
    CORPUS_V1,
)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )


def _generated_v0_record(unit_code: str, *, problem_id: str) -> dict[str, object]:
    return {"problem_id": problem_id, "unit_codes": [unit_code], "slug": f"wm-skel-{problem_id}"}


class TestRunBackfill:
    def test_tags_generated_v0_by_unit_codes(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_GENERATED_V0 / "problems.jsonl",
            [
                _generated_v0_record("QUAD-EQ", problem_id="a"),
                _generated_v0_record("IND-SEQ", problem_id="b"),
            ],
        )
        report = run_backfill(corpus_root=root, write=True)

        by_name = {c.name: c for c in report.corpora}
        gen = by_name[CORPUS_GENERATED_V0]
        assert gen.total == 2
        assert gen.tagged == 2
        assert gen.changed == 2  # 신규 키 추가 — 첫 실행은 전건 변경.

        lines = (
            (root / CORPUS_GENERATED_V0 / "problems.jsonl").read_text(encoding="utf-8").splitlines()
        )
        tagged = [json.loads(line) for line in lines]
        assert tagged[0]["problem_type_codes"] == ["ptype.solve-for-unknown"]
        assert tagged[1]["problem_type_codes"] == ["ptype.generalize-pattern"]

    def test_second_run_is_byte_identical(self, tmp_path: Path) -> None:
        # 2회 실행 바이트 동일(멱등) — 문제_corpus_tag와 동일 계약.
        root = tmp_path / "corpus"
        path = root / CORPUS_GENERATED_V0 / "problems.jsonl"
        _write_jsonl(path, [_generated_v0_record("QUAD-EQ", problem_id="a")])

        run_backfill(corpus_root=root, write=True)
        first_bytes = path.read_bytes()
        second_report = run_backfill(corpus_root=root, write=True)
        second_bytes = path.read_bytes()

        assert first_bytes == second_bytes
        by_name = {c.name: c for c in second_report.corpora}
        assert by_name[CORPUS_GENERATED_V0].changed == 0  # 무변경(이미 일치).

    def test_only_problem_type_codes_key_changes(self, tmp_path: Path) -> None:
        """바이트 계약 — 다른 필드는 절대 건드리지 않는다."""
        root = tmp_path / "corpus"
        record = {
            "problem_id": "a",
            "unit_codes": ["QUAD-EQ"],
            "question_text": "이차방정식 문제",
            "answer": "3",
        }
        _write_jsonl(root / CORPUS_GENERATED_V0 / "problems.jsonl", [record])
        run_backfill(corpus_root=root, write=True)
        result = json.loads(
            (root / CORPUS_GENERATED_V0 / "problems.jsonl").read_text(encoding="utf-8")
        )
        expected = dict(record)
        expected["problem_type_codes"] = ["ptype.solve-for-unknown"]
        assert result == expected

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"
        path = root / CORPUS_GENERATED_V0 / "problems.jsonl"
        _write_jsonl(path, [_generated_v0_record("QUAD-EQ", problem_id="a")])
        original = path.read_bytes()

        report = run_backfill(corpus_root=root, write=False)

        assert path.read_bytes() == original  # 파일 미기록.
        by_name = {c.name: c for c in report.corpora}
        assert by_name[CORPUS_GENERATED_V0].tagged == 1
        assert by_name[CORPUS_GENERATED_V0].written is None

    def test_v1_slug_based_classification(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_V1 / "problems.jsonl",
            [
                {"slug": "wm-quad-eq-larger-root", "unit_codes": ["QUAD-EQ"]},
                {"slug": "wm-quad-fn-axis", "unit_codes": ["QUAD-FN"]},
                {"slug": "wm-unknown-slug", "unit_codes": ["QUAD-EQ"]},  # 매핑표 밖 — 미태깅.
            ],
        )
        report = run_backfill(corpus_root=root, write=True)
        by_name = {c.name: c for c in report.corpora}
        v1 = by_name[CORPUS_V1]
        assert v1.total == 3
        assert v1.tagged == 2
        assert v1.untagged == 1

    def test_rephrased_v0_excluded_not_opened_but_counted(self, tmp_path: Path) -> None:
        """제외 코퍼스는 대상 목록에 없고, 파일도 열리지 않되(수정 없음) 행 수는 정직히 센다."""
        root = tmp_path / "corpus"
        rephrased_path = root / CORPUS_REPHRASED_V0 / "problems.jsonl"
        original_content = '{"problem_id": "r1", "slug": "wm-rephrase-x"}\n'
        _write_jsonl(root / CORPUS_GENERATED_V0 / "problems.jsonl", [])  # 대상 코퍼스 최소 존재.
        rephrased_path.parent.mkdir(parents=True, exist_ok=True)
        rephrased_path.write_text(original_content, encoding="utf-8")

        report = run_backfill(corpus_root=root, write=True)

        assert rephrased_path.read_text(encoding="utf-8") == original_content  # 완전 무변경.
        assert report.excluded_corpora == (CORPUS_REPHRASED_V0,)
        assert report.excluded_total == 1
        assert CORPUS_REPHRASED_V0 not in {c.name for c in report.corpora}

    def test_missing_corpus_file_is_zero_not_error(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"  # 아무 파일도 안 만듦.
        report = run_backfill(corpus_root=root, write=True)
        assert all(c.total == 0 for c in report.corpora)
        assert report.excluded_total == 0
        assert report.grand_total == 0


class TestMainCli:
    def test_cli_reports_json_and_exit_zero(self, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_GENERATED_V0 / "problems.jsonl",
            [_generated_v0_record("QUAD-EQ", problem_id="a")],
        )
        rc = main(["--corpus-root", str(root)])
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert rc == 0
        assert payload["total_tagged"] == 1

    def test_cli_dry_run_flag(self, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
        root = tmp_path / "corpus"
        path = root / CORPUS_GENERATED_V0 / "problems.jsonl"
        _write_jsonl(path, [_generated_v0_record("QUAD-EQ", problem_id="a")])
        original = path.read_bytes()

        rc = main(["--corpus-root", str(root), "--dry-run"])

        assert rc == 0
        assert path.read_bytes() == original
