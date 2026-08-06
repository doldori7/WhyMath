"""`defect_report`에 `user_id` 컬럼이 없음을 동결 — RPT-01 핵심 설계 제약.

`docs/architecture/service_operations_gap_review.md` §3 D1: 결함 대장은 "누가"가 아니라
"무엇을" 신고했는지만 기록한다. `user_id` 컬럼 자체가 없어야 ⑴ 미성년 PII 미저촉 ⑵ 보존·
파기 대상 아님 ⑶ 반출·삭제권 대상 아님 ⑷ 회신 유혹 차단(CS로 새지 않음)이 구조적으로
성립한다. `test_no_lockout_columns.py`(SEC-08) 패턴을 그대로 따른다 — 실제 매퍼 컬럼 목록을
직접 조회해(추측 아님) 컬럼 부재를 동결한다.
"""

from __future__ import annotations

import sqlalchemy as sa

from whymath_backend.db.models.audit import DefectReport
from whymath_backend.schema.audit import DefectReport as DefectReportSchema


def _orm_column_names() -> set[str]:
    return {col.key for col in sa.inspect(DefectReport).mapper.column_attrs}


def test_defect_report_orm_has_no_user_id_column() -> None:
    """ORM 컬럼 목록에 `user_id`(및 흔한 변형)가 전혀 없다."""
    columns = _orm_column_names()
    forbidden = {"user_id", "student_id", "owner_id", "reporter_id", "reported_by"}
    present = columns & forbidden
    assert not present, f"RPT-01 설계(user_id 컬럼 부재)를 어기고 신원 컬럼이 추가됨: {present}"


def test_defect_report_orm_column_snapshot_is_exactly_four_fields() -> None:
    """참고용 — 현재 `defect_report` 컬럼 전체 목록(v0는 4필드뿐: PK·카테고리·대상·시각)."""
    assert _orm_column_names() == {
        "report_id",
        "category",
        "problem_id",
        "reported_at",
    }


def test_defect_report_schema_has_no_user_id_field() -> None:
    """Pydantic 스키마(`schema.audit.DefectReport`)에도 `user_id` 필드가 없다(ORM과 이중 확인)."""
    fields = set(DefectReportSchema.model_fields.keys())
    forbidden = {"user_id", "student_id", "owner_id", "reporter_id", "reported_by"}
    present = fields & forbidden
    assert not present, f"schema에 신원 필드가 추가됨: {present}"


def test_defect_report_schema_rejects_unknown_fields_including_user_id() -> None:
    """`extra=\"forbid\"`이므로 `user_id`를 넣어 생성하면 즉시 검증 실패(구조적 차단 재확인)."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DefectReportSchema(category="기타", user_id="11111111-1111-1111-1111-111111111111")
