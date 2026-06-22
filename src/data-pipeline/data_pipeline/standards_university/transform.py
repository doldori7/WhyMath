"""대학 성취기준 행 dict → `UniversityStandard` + 소단원 링크 (정형화·openpyxl 불요).

`ncic/transform.py` 선례 미러(순수 함수·드라이버 의존 0). `성취기준_목록` 대학 행의 컬럼을
backend 스키마 정합 키로 매핑한다. 소단원↔성취기준은 1:1이라 각 성취기준이 정확히 한 링크를 낸다
(`개념ID`=소단원 코드 → `norm_id`).

컬럼 매핑(업로드 헤더 → 모델 필드):
  성취기준 코드→code · norm_id→norm_id · 학년군·과목→subject · 영역(단원)→domain ·
  소단원(개념)→sub_domain · 성취기준 내용→statement · 성취기준 요약(간결)→commentary ·
  학교급→school_type · 개념ID→링크 concept_src_id. curriculum_revision·grade_band는 대학 상수.
"""

from __future__ import annotations

from collections.abc import Sequence

from data_pipeline.standards_university.models import (
    UniversityConceptStandardLink,
    UniversityStandard,
)


class TransformError(ValueError):
    """대학 성취기준 정형화 실패(필수 컬럼 누락 등)."""


def _req(row: dict[str, object], key: str) -> str:
    """필수 문자열 컬럼 추출 — None/공란이면 명확한 오류(조용한 누락 금지)."""
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    if not text:
        raise TransformError(f"대학 성취기준 행에 필수 컬럼 누락/공란: {key!r} (행: {row!r})")
    return text


def _opt(row: dict[str, object], key: str) -> str | None:
    """선택 문자열 컬럼 — None/공란/'-'는 None(매칭 CCSS 등 미해당 표기 흡수)."""
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    if not text or text == "-":
        return None
    return text


def transform_rows(
    rows: Sequence[dict[str, object]],
) -> tuple[list[UniversityStandard], list[UniversityConceptStandardLink]]:
    """대학 성취기준 행들 → (성취기준 목록, 소단원 링크 목록). 검증은 Pydantic 모델이 수행.

    각 행이 정확히 하나의 성취기준과 하나의 링크(소단원↔성취기준 1:1)를 낸다. 형식 위반(코드·
    norm_id·소단원 코드)은 모델 validator가 `ValueError`로 막는다(미적 하이픈 사태 방지).
    """
    standards: list[UniversityStandard] = []
    links: list[UniversityConceptStandardLink] = []
    for row in rows:
        norm_id = _req(row, "norm_id")
        standards.append(
            UniversityStandard(
                norm_id=norm_id,
                code=_req(row, "성취기준 코드"),
                curriculum_revision="대학",
                grade_band="대학교",
                school_type=_req(row, "학교급"),
                subject=_req(row, "학년군·과목"),
                domain=_req(row, "영역(단원)"),
                sub_domain=_opt(row, "소단원(개념)"),
                statement=_req(row, "성취기준 내용"),
                commentary=_opt(row, "성취기준 요약(간결)"),
            )
        )
        links.append(
            UniversityConceptStandardLink(
                concept_src_id=_req(row, "개념ID"),
                norm_id=norm_id,
                link_type="직접",
            )
        )
    return standards, links


__all__ = ["TransformError", "transform_rows"]
