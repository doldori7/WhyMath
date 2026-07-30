"""S4-14 소급 백필(`rephrase_lineage_backfill`) 단위테스트(hermetic·PG 불요·라이브 LLM 0).

`problem_corpus_rephrase.rephrased_slug`/`_rephrased_problem_id`와 동일 공식을 재사용해 변형
레코드에 신규 identity를 소급 발급하고, 발문 불변 레코드는 그대로 두되 관계만 소스에서 복사하는
동작을 검증한다. 미매칭·signature 불일치는 fail-closed(예외)로 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.harness.problem_corpus_rephrase import (
    _rephrased_problem_id,
    rephrased_slug,
)
from whymath_backend.harness.rephrase_lineage_backfill import backfill_rephrase_lineage


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "slug": "wm-skel-src1",
        "problem_id": "00000000-0000-0000-0000-000000000001",
        "unit_codes": ["QUAD-EQ"],
        "question_text": "이차방정식 x^2 - 5x + 6 = 0 의 큰 근은?",
        "answer": "3",
        "verify": {"conditions": "x**2 - 5*x + 6 = 0", "answer_selection": "max"},
        "relations": [],
    }
    record.update(overrides)
    return record


def _write(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


def _read(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class TestBackfillNewIdentity:
    def test_changed_question_gets_new_slug_and_relation(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        source = _record()
        _write(generated, [source])
        # rephrase 산출물(구 코드 산출 흉내) — 같은 slug/problem_id 보존, 발문만 다름.
        changed_text = "이차방정식 x^2 - 5x + 6 = 0 의 큰 근을 구하시오."
        _write(rephrased, [_record(question_text=changed_text)])

        report = backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
        assert report.rephrased_new_identity == 1
        assert report.unchanged_kept_identity == 0
        assert not report.unmatched
        assert not report.signature_mismatches

        (after,) = _read(rephrased)
        expected_slug = rephrased_slug("wm-skel-src1", after["question_text"])
        assert after["slug"] == expected_slug
        assert after["slug"] != "wm-skel-src1"
        assert after["problem_id"] == str(_rephrased_problem_id(expected_slug))
        assert after["relations"] == [
            {"parent_slug": "wm-skel-src1", "relation_type": "변형", "similarity_score": 0.95}
        ]

    def test_deterministic_rerun(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        _write(generated, [_record()])
        _write(rephrased, [_record(question_text="변형된 발문입니다.")])

        backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
        (first_pass,) = _read(rephrased)

        # 재실행 — slug이 이미 바뀌었으니 math_key 폴백으로 재매치되어 같은 결과 재도출.
        backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
        (second_pass,) = _read(rephrased)
        assert first_pass == second_pass


class TestBackfillKeepsIdentity:
    def test_unchanged_question_keeps_slug_and_copies_relations(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        source = _record(relations=[{"parent_slug": "sib", "relation_type": "유사"}])
        _write(generated, [source])
        _write(rephrased, [_record(relations=[])])  # 발문 동일(fail-closed 원문 유지 흉내)

        report = backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
        assert report.rephrased_new_identity == 0
        assert report.unchanged_kept_identity == 1

        (after,) = _read(rephrased)
        assert after["slug"] == "wm-skel-src1"
        assert after["problem_id"] == "00000000-0000-0000-0000-000000000001"
        assert after["relations"] == [{"parent_slug": "sib", "relation_type": "유사"}]

    def test_check_mode_does_not_write(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        _write(generated, [_record()])
        _write(rephrased, [_record(question_text="변형된 발문입니다.")])
        before = rephrased.read_text(encoding="utf-8")

        report = backfill_rephrase_lineage(
            generated_path=generated, rephrased_path=rephrased, check=True
        )
        assert report.rephrased_new_identity == 1
        assert rephrased.read_text(encoding="utf-8") == before  # 미기록(드라이런)


class TestBackfillMatching:
    def test_falls_back_to_math_key_when_slug_diverged(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        _write(generated, [_record(slug="wm-skel-src1-v2")])  # 소스 재슬러그(조사 수정 등)
        _write(
            rephrased,
            [_record(slug="wm-skel-src1", question_text="변형된 발문입니다.")],  # 구 slug 잔존
        )

        report = backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
        assert report.rephrased_new_identity == 1
        (after,) = _read(rephrased)
        assert after["relations"][0]["parent_slug"] == "wm-skel-src1-v2"  # 소스 최신 slug 참조

    def test_unmatched_record_raises(self, tmp_path: Path) -> None:
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        _write(generated, [_record()])
        _write(
            rephrased,
            [_record(slug="wm-nope", unit_codes=["OTHER"], answer="999")],  # 조인 불가
        )
        with pytest.raises(ValueError, match="미매칭"):
            backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)

    def test_signature_mismatch_raises(self, tmp_path: Path) -> None:
        # slug 조인은 성공하지만(우연 동일 slug) verify 내용이 실제로 다른 적대적 케이스
        # (정상 파이프라인에서는 불가능하나 조인 오류 방어를 하드 실패로 검증).
        generated = tmp_path / "generated.jsonl"
        rephrased = tmp_path / "rephrased.jsonl"
        _write(generated, [_record()])  # conditions: x**2 - 5*x + 6 = 0
        _write(
            rephrased,
            [
                _record(
                    verify={"conditions": "x**2 - 7*x + 12 = 0", "answer_selection": "max"},
                )
            ],
        )
        with pytest.raises(ValueError, match="signature 불일치"):
            backfill_rephrase_lineage(generated_path=generated, rephrased_path=rephrased)
