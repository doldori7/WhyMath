"""문제 유형(problem_type_codes) 백필 CLI(S3-27·PB-07) — 바이트 계약·멱등·계보 분류 단위테스트.

핵심 봉인(`problem_corpus_tag` 패턴 동형): ① 미태깅 레코드에 적용하면 `problem_type_codes` 키만
추가되고 나머지 바이트는 그대로 ② 이미 태깅된 레코드는 재적용해도 바이트 무변경(멱등) ③ dry-run은
파일 미기록·통계만 ④ `problem_bank_rephrased_v0`는 계보(부모 "변형" relations) 승계로 태깅하고,
계보로도 추적 불가한 레코드는 미태깅으로 남겨 리포트가 정직하게 센다(침묵 누락 금지 — PB-07이
구 명시 제외를 해제·`EXCLUDED_CORPORA` 좌석은 현재 빈 상태). LLM·DB 0(순수 결정론).
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


def _variant_relation(parent_slug: str) -> dict[str, object]:
    """계보(변형) relations 픽스처 — S4-18 영속 형태와 동일 구조."""
    return {"parent_slug": parent_slug, "relation_type": "변형", "similarity_score": 1.0}


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

    def test_rephrased_v0_tagged_via_lineage(self, tmp_path: Path) -> None:
        """PB-07 계보 분류 — rephrased 레코드는 "변형" 계보의 부모(직접 분류 코퍼스) 유형을
        승계하고, 부모를 색인에서 못 찾는 레코드는 미태깅으로 남아 리포트가 정직하게 센다."""
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_GENERATED_V0 / "problems.jsonl",
            [_generated_v0_record("QUAD-EQ", problem_id="p1")],
        )
        _write_jsonl(
            root / CORPUS_REPHRASED_V0 / "problems.jsonl",
            [
                {
                    "problem_id": "r1",
                    "slug": "wm-skel-p1-rephrased",
                    "relations": [_variant_relation("wm-skel-p1")],
                },
                {
                    "problem_id": "r2",
                    "slug": "wm-orphan-rephrased",
                    "relations": [_variant_relation("wm-missing-parent")],  # 색인 부재 부모.
                },
            ],
        )

        report = run_backfill(corpus_root=root, write=True)

        by_name = {c.name: c for c in report.corpora}
        reph = by_name[CORPUS_REPHRASED_V0]
        assert reph.total == 2
        assert reph.tagged == 1
        assert reph.untagged == 1  # 침묵 누락 금지 — 추적 불가 건수가 리포트에 드러난다.

        lines = (
            (root / CORPUS_REPHRASED_V0 / "problems.jsonl").read_text(encoding="utf-8").splitlines()
        )
        tagged = [json.loads(line) for line in lines]
        assert tagged[0]["problem_type_codes"] == ["ptype.solve-for-unknown"]  # 부모 유형 승계.
        assert "problem_type_codes" not in tagged[1]  # 미태깅 레코드는 원문 바이트 그대로.

    def test_rephrased_only_gains_problem_type_codes_key(self, tmp_path: Path) -> None:
        """계보 백필도 바이트 계약 준수 — `problem_type_codes` 키 추가 외 타 필드 불변."""
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_GENERATED_V0 / "problems.jsonl",
            [_generated_v0_record("IND-SEQ", problem_id="p1")],
        )
        record = {
            "problem_id": "r1",
            "slug": "wm-skel-p1-rephrased",
            "question_text": "재서술된 발문",
            "answer": "3",
            "relations": [_variant_relation("wm-skel-p1")],
        }
        _write_jsonl(root / CORPUS_REPHRASED_V0 / "problems.jsonl", [record])

        run_backfill(corpus_root=root, write=True)

        result = json.loads(
            (root / CORPUS_REPHRASED_V0 / "problems.jsonl").read_text(encoding="utf-8")
        )
        expected = dict(record)
        expected["problem_type_codes"] = ["ptype.generalize-pattern"]
        assert result == expected

    def test_rephrased_second_run_is_byte_identical(self, tmp_path: Path) -> None:
        """계보 백필 멱등 — 2회 실행 바이트 동일(직접 분류 코퍼스와 동일 계약)."""
        root = tmp_path / "corpus"
        _write_jsonl(
            root / CORPUS_GENERATED_V0 / "problems.jsonl",
            [_generated_v0_record("QUAD-EQ", problem_id="p1")],
        )
        path = root / CORPUS_REPHRASED_V0 / "problems.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "problem_id": "r1",
                    "slug": "wm-skel-p1-rephrased",
                    "relations": [_variant_relation("wm-skel-p1")],
                }
            ],
        )

        run_backfill(corpus_root=root, write=True)
        first_bytes = path.read_bytes()
        second_report = run_backfill(corpus_root=root, write=True)
        second_bytes = path.read_bytes()

        assert first_bytes == second_bytes
        by_name = {c.name: c for c in second_report.corpora}
        assert by_name[CORPUS_REPHRASED_V0].changed == 0  # 무변경(이미 일치).

    def test_excluded_seat_is_empty_after_pb07(self, tmp_path: Path) -> None:
        """PB-07 해제 후 제외 좌석 회계 — `excluded` 절은 유지되되 현재 빈 상태다(항목이
        재등재되면 만료 계약(`ExclusionEntry`·task_id 필수)과 함께만 가능 — mapping 모듈 동결)."""
        root = tmp_path / "corpus"
        _write_jsonl(root / CORPUS_GENERATED_V0 / "problems.jsonl", [])
        report = run_backfill(corpus_root=root, write=True)
        assert report.excluded_corpora == ()
        assert report.excluded_total == 0

    def test_missing_corpus_file_is_zero_not_error(self, tmp_path: Path) -> None:
        root = tmp_path / "corpus"  # 아무 파일도 안 만듦.
        report = run_backfill(corpus_root=root, write=True)
        assert all(c.total == 0 for c in report.corpora)
        assert CORPUS_REPHRASED_V0 in {c.name for c in report.corpora}  # 계보 코퍼스도 회계 대상.
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
