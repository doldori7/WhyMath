"""계정 잠금(lockout) 미도입 동결 테스트 — SEC-08 완료조건 ③.

`api/auth.py` 모듈 docstring·`oauth_callback` 근처 주석의 근거(미성년 학습 중단=우선순위1
침해) 참조. 여기서는 그 *의도된 결정*이 조용히 뒤집히지 않도록 `UserProfile`에 잠금/실패
카운트 관련 컬럼이 없음을 컬럼 목록 기반으로 동결한다(추측이 아니라 실제 매퍼 컬럼 조회).
"""

from __future__ import annotations

import sqlalchemy as sa

from whymath_backend.db.models.user import UserProfile


def _column_names() -> set[str]:
    return {col.key for col in sa.inspect(UserProfile).mapper.column_attrs}


def test_user_profile_has_no_lockout_columns() -> None:
    """`UserProfile`에 계정 잠금/로그인 실패 카운트 컬럼이 없다(SEC-08 의도된 미도입).

    실제 컬럼 목록 전수(41개, 이 테스트 작성 시점 실측)에서 잠금류 이름이 하나도 없음을
    확인 — 향후 누군가 잠금 기능을 추가하려면 이 테스트를 먼저 고쳐야 하므로(신호),
    조용한 재도입을 막는다.
    """
    columns = _column_names()
    forbidden = {
        "locked",
        "is_locked",
        "account_locked",
        "locked_at",
        "locked_until",
        "lockout_until",
        "failed_login_attempts",
        "failed_attempts",
        "login_attempt_count",
    }
    present = columns & forbidden
    assert not present, f"의도된 미도입(SEC-08)을 어기고 잠금 관련 컬럼이 추가됨: {present}"


def test_user_profile_column_snapshot_unchanged_by_lockout() -> None:
    """참고용 — 현재 `UserProfile` 컬럼 전체 목록(변경 시 diff로 어떤 컬럼이 늘었는지 보인다)."""
    expected = {
        "user_id",
        "email_hash",
        "nickname",
        "birth_year",
        "gender",
        "school_type",
        "school_region",
        "school_id",
        "grade",
        "track_type",
        "target_universities",
        "target_major_category",
        "target_grade",
        "target_score",
        "target_exam_date",
        "persona_primary",
        "persona_secondary",
        "persona_confidence",
        "primary_device",
        "has_apple_pencil",
        "note_app",
        "current_grade_estimate",
        "current_grade_updated_at",
        "diagnostic_completed",
        "diagnostic_completed_at",
        "uses_inkang",
        "inkang_provider",
        "uses_offline_academy",
        "monthly_education_spend",
        "subscription_tier",
        "subscription_started_at",
        "subscription_renewed_at",
        "is_minor",
        "parent_consent_at",
        "parent_email_hash",
        "accessibility_needs",
        "created_at",
        "last_active_at",
        "is_active",
        "is_deleted",
        "deleted_at",
    }
    assert _column_names() == expected
