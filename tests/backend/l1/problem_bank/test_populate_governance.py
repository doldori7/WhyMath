"""문제 코퍼스 적재 *거버넌스* 테스트 — 저작권 봉인(비-자체생성·본문 보유 메타출처 거부).

CLAUDE.md 우선순위 #2(저작권): 학생에게 노출·저장되는 본문은 `source_type=자체생성`
(WHYMATH_GENERATED)만 합법이다. 이 테스트는 적재 파이프라인이 ① 비-자체생성 출처 ② 본문 보유
메타 전용 출처(평가원/EBS/교과서) ③ 비-WHYMATH license 레코드를 *거부*함을 봉인한다(조용한 통과
금지). PG 불요(로드 단계 위생 검증).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from whymath_backend.l1.problem_bank.populate import (
    ProblemCorpusError,
    load_problem_bank_records,
)


def _valid() -> dict[str, Any]:
    return {
        "slug": "wm-gov-eq",
        "source_type": "자체생성",
        "license": "WHYMATH_GENERATED",
        "generation_type": "FULLY_GENERATED",
        "subject": "공통",
        "curriculum_version": "2022_REVISION",
        "valid_from_year": 2025,
        "unit_codes": ["QUAD-EQ"],
        "question_format": "단답형",
        "answer_format": "자연수",
        "difficulty_overall": 2.0,
        "question_text": "이차방정식 x^2 - 5x + 6 = 0 의 큰 근은?",
        "answer": "3",
        "answer_explanation": "(x-2)(x-3) = 0 이므로 큰 근은 3이다.",
        "concepts": [{"concept_src_id": "HK06", "role": "PRIMARY"}],
        "verify": {"conditions": "x**2 - 5*x + 6 = 0", "answer_map": {"x": "3"}},
    }


def _write(tmp_path: Path, record: dict[str, Any]) -> Path:
    path = tmp_path / "problems.jsonl"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return path


def test_baseline_valid_record_loads(tmp_path: Path) -> None:
    # 통제군 — 유효 자체생성 레코드는 로드된다(거부 규칙이 정당 레코드를 막지 않음).
    path = _write(tmp_path, _valid())
    records = load_problem_bank_records(path)
    assert len(records) == 1


def test_rejects_metadata_only_source_with_body(tmp_path: Path) -> None:
    # 본문 보유 메타출처(평가원 + question_text/answer) — 저작권 위반. source_type 위생이 거부.
    record = _valid()
    record["source_type"] = "평가원"
    path = _write(tmp_path, record)
    with pytest.raises(ProblemCorpusError, match="source_type"):
        load_problem_bank_records(path)


@pytest.mark.parametrize("source", ["EBS", "교과서", "AIHub", "사용자자작", "교육청학평"])
def test_rejects_all_non_self_generated_sources(tmp_path: Path, source: str) -> None:
    record = _valid()
    record["source_type"] = source
    path = _write(tmp_path, record)
    with pytest.raises(ProblemCorpusError):
        load_problem_bank_records(path)


@pytest.mark.parametrize("license_value", ["EBS_LICENSED", "PUBLIC_DOMAIN", "USER_GENERATED"])
def test_rejects_non_whymath_license(tmp_path: Path, license_value: str) -> None:
    record = _valid()
    record["license"] = license_value
    path = _write(tmp_path, record)
    with pytest.raises(ProblemCorpusError, match="license"):
        load_problem_bank_records(path)
