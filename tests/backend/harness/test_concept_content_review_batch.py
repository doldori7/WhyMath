"""concept_content_review_batch 단위테스트 — LLM 없이 결정론·표본·rubric 변별력 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.db.models.concept_content import (
    CONTENT_REVIEW_STATUS_AI_ESTIMATED,
    CONTENT_SCOPE_K12,
)
from whymath_backend.harness.concept_content_review_batch import (
    _injected_defects,
    main,
    min_n_for_zero_defects,
    stratified_sample,
)
from whymath_backend.l1.concept_content.projection import ConceptContentRecord


class TestMinN:
    def test_min_n_is_positive(self) -> None:
        n = min_n_for_zero_defects(0.05)
        assert n > 0

    def test_min_n_decreases_with_looser_threshold(self) -> None:
        strict = min_n_for_zero_defects(0.02)
        loose = min_n_for_zero_defects(0.05)
        assert strict > loose

    def test_min_n_higher_confidence_needs_more(self) -> None:
        n95 = min_n_for_zero_defects(0.05, confidence=0.95)
        n99 = min_n_for_zero_defects(0.05, confidence=0.99)
        assert n99 > n95

    def test_min_n_invalid_threshold_raises(self) -> None:
        with pytest.raises(ValueError):
            min_n_for_zero_defects(0.0)
        with pytest.raises(ValueError):
            min_n_for_zero_defects(1.0)


class TestStratifiedSample:
    def test_deterministic_by_seed(self) -> None:
        records = [
            ConceptContentRecord(
                code=f"N{i}",
                scope=CONTENT_SCOPE_K12,
                name="x",
                subject="s",
                unit=None,
                metaphor=None,
                misconception=None,
                formal_definition_internal=None,
                accepted_expressions=None,
                explanation=None,
                standard_codes=(),
                flashcards=(),
                review_status=CONTENT_REVIEW_STATUS_AI_ESTIMATED,
            )
            for i in range(100)
        ]
        s1 = stratified_sample(records, 10, seed=7)
        s2 = stratified_sample(records, 10, seed=7)
        assert [r.code for r in s1] == [r.code for r in s2]

    def test_respects_sample_size(self) -> None:
        records = [
            ConceptContentRecord(
                code=f"N{i}",
                scope=CONTENT_SCOPE_K12,
                name="x",
                subject="s",
                unit=None,
                metaphor=None,
                misconception=None,
                formal_definition_internal=None,
                accepted_expressions=None,
                explanation=None,
                standard_codes=(),
                flashcards=(),
                review_status=CONTENT_REVIEW_STATUS_AI_ESTIMATED,
            )
            for i in range(50)
        ]
        assert len(stratified_sample(records, 20, seed=1)) == 20

    def test_capped_at_total(self) -> None:
        records = [
            ConceptContentRecord(
                code="N1",
                scope=CONTENT_SCOPE_K12,
                name="x",
                subject="s",
                unit=None,
                metaphor=None,
                misconception=None,
                formal_definition_internal=None,
                accepted_expressions=None,
                explanation=None,
                standard_codes=(),
                flashcards=(),
                review_status=CONTENT_REVIEW_STATUS_AI_ESTIMATED,
            )
        ]
        assert len(stratified_sample(records, 100, seed=1)) == 1


class TestBatchReviewFakeLLM:
    def test_fake_llm_produces_jsonl_and_passes_gate(self, tmp_path: Path) -> None:
        out = tmp_path / "audit.jsonl"
        rc = main(
            [
                "--fake-llm",
                "--out",
                str(out),
                "--seed",
                "123",
                "--threshold",
                "0.10",
            ]
        )
        assert rc == 0
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) > 0
        # fake provider는 주입 결함을 항상 잡는다.
        assert any(json.loads(line).get("injected") for line in lines)
        assert any(json.loads(line).get("passed") for line in lines)

    def test_fake_llm_gate_fails_when_threshold_too_low(self, tmp_path: Path) -> None:
        out = tmp_path / "audit.jsonl"
        # threshold 0.0001 → 모든 결함을 초과로 판정, exit 1
        rc = main(
            [
                "--fake-llm",
                "--out",
                str(out),
                "--seed",
                "123",
                "--threshold",
                "0.0001",
            ]
        )
        assert rc == 1

    def test_dry_run_does_not_call_llm(self, tmp_path: Path) -> None:
        out = tmp_path / "audit.jsonl"
        rc = main(["--dry-run", "--out", str(out), "--seed", "123"])
        assert rc == 0
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert all(json.loads(line)["reason"] == "dry-run: 평가 생략" for line in lines)

    def test_injected_defects_count(self) -> None:
        assert len(_injected_defects()) >= 2


class TestBatchReviewWithTinyCorpus:
    def test_small_corpus_caps_sample_at_total(self, tmp_path: Path) -> None:
        k12 = tmp_path / "k12.json"
        k12.write_text(
            json.dumps(
                {
                    "scope": CONTENT_SCOPE_K12,
                    "content": [
                        {
                            "code": "N1",
                            "name": "자연수",
                            "subject": "초등수학",
                            "metaphor": "개수",
                            "misconception": "0 포함",
                            "formal_definition_internal": "1,2,3...",
                            "accepted_expressions": "자연수",
                            "explanation": "기초",
                            "standard_codes": ["[2수01-01]"],
                            "flashcards": [],
                            "review_status": "ai_estimated",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        out = tmp_path / "audit.jsonl"
        rc = main(
            [
                "--k12",
                str(k12),
                "--university",
                str(k12),
                "--fake-llm",
                "--out",
                str(out),
                "--threshold",
                "0.60",
            ]
        )
        assert rc == 0
