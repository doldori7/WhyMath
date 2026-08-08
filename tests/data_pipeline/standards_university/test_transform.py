"""대학 성취기준 정형화 단위테스트 — 행 dict → 모델 매핑·1:1 링크·필수 컬럼."""

from __future__ import annotations

import pytest
from data_pipeline.standards_university.transform import TransformError, transform_rows


def test_maps_columns_to_fields(univ_std_row: dict[str, object]) -> None:
    standards, links = transform_rows([univ_std_row])
    assert len(standards) == 1 and len(links) == 1
    s = standards[0]
    assert s.norm_id == "대학_GALOIS_01_01"
    assert s.code == "[GALOIS-01-01]"
    assert s.subject == "갈루아 이론"  # 학년군·과목 → subject
    assert s.domain == "체확장 복습"  # 영역(단원) → domain
    assert s.sub_domain == "분해체"  # 소단원(개념) → sub_domain
    assert s.statement.startswith("f의 분해체")  # 성취기준 내용 → statement
    assert s.commentary == "분해체는 근을 다 담는 최소 체"  # 요약 → commentary
    assert s.school_type == "대학교"
    # 링크: 소단원(개념ID) → concept_src_id, 1:1.
    assert links[0].concept_src_id == "GALOIS-U1-S1"
    assert links[0].norm_id == "대학_GALOIS_01_01"
    assert links[0].link_type == "직접"


def test_one_link_per_standard(make_univ_std_row) -> None:  # type: ignore[no-untyped-def]
    rows = [
        make_univ_std_row(),
        make_univ_std_row(
            **{
                "성취기준 코드": "[GALOIS-01-02]",
                "norm_id": "대학_GALOIS_01_02",
                "개념ID": "GALOIS-U1-S2",
                "소단원(개념)": "정규확장",
            }
        ),
    ]
    standards, links = transform_rows(rows)
    assert len(standards) == 2 and len(links) == 2  # 소단원↔성취기준 1:1


def test_dash_commentary_becomes_none(make_univ_std_row) -> None:  # type: ignore[no-untyped-def]
    rows = [make_univ_std_row(**{"성취기준 요약(간결)": "-", "매칭 CCSS": "-"})]
    standards, _ = transform_rows(rows)
    assert standards[0].commentary is None  # '-'는 미해당 → None


def test_missing_required_column_raises(make_univ_std_row) -> None:  # type: ignore[no-untyped-def]
    rows = [make_univ_std_row(**{"성취기준 내용": None})]
    with pytest.raises(TransformError, match="성취기준 내용"):
        transform_rows(rows)


def test_empty_rows_yield_empty(make_univ_std_row) -> None:  # type: ignore[no-untyped-def]
    standards, links = transform_rows([])
    assert standards == [] and links == []
