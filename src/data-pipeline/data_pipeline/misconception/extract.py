"""7계층 본문 JSON → 정규화 오개념 레코드(순수·openpyxl 불요).

각 개념의 `L5_META.오개념` 리스트를 평탄화해 한글 소스 키를 안정 영문 키로 매핑한다(데이터카드 §2).
`mis_id`는 유일 PK이므로 중복은 *마지막 우선*이 아니라 *첫 등장 우선*으로 dedup하고 누락/중복을
정직하게 셀 수 있도록 순수 함수로 둔다(조용한 누락 금지 — CLAUDE.md 신뢰 원칙).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class MisconceptionRecord(TypedDict):
    """정규화 오개념 1건 — 한글 소스 키 → 안정 영문 키(데이터카드 §2).

    `mis_id`만 필수(PK). 나머지는 소스 채우율이 52~100%라 빈 값이면 None으로 둔다(자유텍스트 잔차
    방지). 개념·성취기준 해소(`concept_src_id`→concept.code·`standard_code`→norm_id)는 백엔드 로더
    책임이므로 여기서는 원천 코드를 *그대로 보존*한다(ncic concept_src_id 선례).
    """

    mis_id: str
    canonical_statement: str | None
    student_wrong_thinking: str | None
    distractor_rule: str | None
    error_type: str | None
    difficulty: str | None
    correction_point: str | None
    ccss_code: str | None
    concept_src_id: str | None
    standard_code: str | None
    school_level: str | None
    domain: str | None
    subunit: str | None
    mapping_confidence: str | None
    mapping_score: float | None
    provenance_note: str | None


# 한글 소스 키 → 영문 키 매핑(문자열 필드만 — mapping_score는 별도 수치 처리).
_STR_FIELDS: dict[str, str] = {
    "오개념": "canonical_statement",
    "학생의_잘못된_사고": "student_wrong_thinking",
    "distractor_규칙": "distractor_rule",
    "error_type": "error_type",
    "난이도": "difficulty",
    "교정포인트": "correction_point",
    "매칭_CCSS": "ccss_code",
    "개념ID": "concept_src_id",
    "성취기준코드": "standard_code",
    "학교급": "school_level",
    "2022_영역": "domain",
    "세부단원_개념": "subunit",
    "매핑신뢰도": "mapping_confidence",
    "생성·검수": "provenance_note",
}


def _clean_str(value: object) -> str | None:
    """문자열 정제 — 정제 후 빈 값이면 None(미존재로 취급)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_float(value: object) -> float | None:
    """수치 정제 — float 변환 실패/빈 값이면 None."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def load_json(path: str | Path) -> list[dict[str, Any]]:
    """7계층 본문 JSON 로드 — 최상위 개념 배열을 반환(형식 위반은 명확히 오류)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(
            f"7계층 JSON 최상위는 개념 배열이어야 합니다(got {type(payload).__name__})."
        )
    return payload


def extract_misconceptions(
    concepts: list[dict[str, Any]],
) -> tuple[list[MisconceptionRecord], int]:
    """개념 배열 → (정규화 오개념 레코드 목록, mis_id 중복 skip 수).

    각 개념의 `L5_META.오개념` 리스트를 평탄화한다. `mis_id` 없는 레코드는 건너뛰고(PK 결손),
    이미 본 `mis_id`는 *첫 등장 우선*으로 dedup하며 중복 수를 *정직하게* 집계해 반환한다.
    """
    records: list[MisconceptionRecord] = []
    seen: set[str] = set()
    duplicates = 0
    for concept in concepts:
        meta = concept.get("L5_META") or {}
        rows = meta.get("오개념") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mis_id = _clean_str(row.get("mis_id"))
            if mis_id is None:
                continue  # PK 결손 — 카탈로그 레코드로 부적격(건너뜀).
            if mis_id in seen:
                duplicates += 1
                continue
            seen.add(mis_id)
            record: MisconceptionRecord = {
                "mis_id": mis_id,
                "canonical_statement": None,
                "student_wrong_thinking": None,
                "distractor_rule": None,
                "error_type": None,
                "difficulty": None,
                "correction_point": None,
                "ccss_code": None,
                "concept_src_id": None,
                "standard_code": None,
                "school_level": None,
                "domain": None,
                "subunit": None,
                "mapping_confidence": None,
                "mapping_score": _clean_float(row.get("매핑점수")),
                "provenance_note": None,
            }
            for src_key, dst_key in _STR_FIELDS.items():
                record[dst_key] = _clean_str(row.get(src_key))  # type: ignore[literal-required]
            records.append(record)
    return records, duplicates
