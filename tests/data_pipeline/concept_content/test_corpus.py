"""실 K-12 콘텐츠 코퍼스 검증 — 산출(concept_content_v1) 정합성(ground truth)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_CORPUS = (
    Path(__file__).resolve().parents[3] / "data" / "corpus" / "concept_content_v1" / "content.json"
)
_EXPECTED = 437
_EXPECTED_SUBJECTS = 17


def _load() -> dict:
    if not _CORPUS.exists():
        pytest.skip("K-12 콘텐츠 코퍼스 미생성")
    return json.loads(_CORPUS.read_text(encoding="utf-8"))


def test_corpus_counts_and_codes() -> None:
    data = _load()
    content = data["content"]
    assert data["scope"] == "K-12"
    assert len(content) == _EXPECTED
    assert len({c["code"] for c in content}) == _EXPECTED  # 개념ID 유일
    for c in content:
        assert c["code"].strip()  # 비공란(U4 SUBUNIT_PATTERN 미적용)
        assert c["name"].strip()


def test_corpus_self_authored_and_internal_definition() -> None:
    data = _load()
    # 자체작성·정식정의 학생비노출 표기(검수필요·NCIC 본문 미수록).
    assert "자체" in data["source_citation"]
    assert "학생 비노출" in data["license_notice"]
    assert "미수록" in data["license_notice"]
    # 콘텐츠 4종 전수 채움(검수보고: K-12 437칸 채움).
    for fld in (
        "metaphor",
        "misconception",
        "formal_definition_internal",
        "accepted_expressions",
    ):
        assert all(c[fld] for c in data["content"]), fld


def test_corpus_no_ncic_body_keys() -> None:
    data = _load()
    # 모든 항목 키에 NCIC 본문 키가 없어야 한다(코드만 보존).
    all_keys: set[str] = set()
    for c in data["content"]:
        all_keys.update(c.keys())
    for forbidden in ("성취기준 문장", "성취기준 요약(간결)", "성취기준 요약", "핵심명제"):
        assert forbidden not in all_keys
    # 원문 JSON에도 NCIC 본문 키가 없어야 한다.
    raw = _CORPUS.read_text(encoding="utf-8")
    for forbidden in ("성취기준 문장", "성취기준 요약", "핵심명제", "성취기준 본문"):
        assert f'"{forbidden}"' not in raw
    # 연결 성취기준 코드 다리는 보존(전수 ≥1).
    assert all(c["standard_codes"] for c in data["content"])


def test_corpus_flashcards_present() -> None:
    data = _load()
    total = sum(len(c["flashcards"]) for c in data["content"])
    assert total > 0  # K-12는 1:1 아님(일부 개념만 카드 보유)
    cards = [fc for c in data["content"] for fc in c["flashcards"]]
    sample = cards[0]
    assert sample["front"] and sample["back"]


def test_corpus_subjects() -> None:
    data = _load()
    assert len({c["subject"] for c in data["content"]}) == _EXPECTED_SUBJECTS
