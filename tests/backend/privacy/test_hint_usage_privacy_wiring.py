"""hint_usage privacy 3종 배선(EOS-45 acceptance ③) — 삭제·보존·반출 계획 등재 검증.

`test_answer_submission_privacy_wiring.py`(EOS-32) 컨벤션 미러. 전수 완결성은
`test_erasure_plan_completeness.py`(metadata 스윕 — EOS-45 배선 전 red 실측·세션 보고 기록)가
강제하고, 본 모듈은 신규 테이블의 배선을 *이름으로 못박아* 회귀를 지역화한다. hermetic — DB 0.
"""

from __future__ import annotations

from whymath_backend.db.models.hint_usage import HintUsage
from whymath_backend.privacy.erasure import _ERASURE_PLAN
from whymath_backend.privacy.export import _EXPORT_PLAN
from whymath_backend.privacy.retention import _RETENTION_PLAN


class TestErasureWiring:
    def test_planned_with_user_id(self) -> None:
        """삭제권 — `(HintUsage, "user_id")`가 `_ERASURE_PLAN`에 등재(미성년 행동 데이터)."""
        assert (HintUsage, "user_id") in _ERASURE_PLAN

    def test_deleted_before_problem_attempt(self) -> None:
        """자식 우선 — attempt→hint_usage CASCADE 역순 방지(FK 의존 안전 순서)."""
        names = [m.__tablename__ for m, _ in _ERASURE_PLAN]
        assert names.index("hint_usage") < names.index("problem_attempt")


class TestRetentionWiring:
    def test_planned_with_requested_at(self) -> None:
        """보존 파기 — `(HintUsage, "requested_at")` 등재(NOT NULL 축·NULL-미파기 없음)."""
        assert (HintUsage, "requested_at") in _RETENTION_PLAN
        assert HintUsage.__table__.columns["requested_at"].nullable is False

    def test_purged_before_problem_attempt(self) -> None:
        """자식 우선 — attempt가 보존 창 안에 남아도 만료 힌트 이력은 파기(순서 보존)."""
        names = [m.__tablename__ for m, _ in _RETENTION_PLAN]
        assert names.index("hint_usage") < names.index("problem_attempt")


class TestExportWiring:
    def test_planned_as_hint_usages_category(self) -> None:
        """열람·이동권 — user_id 키·`hint_usages` 카테고리로 `_EXPORT_PLAN`에 등재."""
        assert (HintUsage, "user_id", "hint_usages") in _EXPORT_PLAN

    def test_orm_has_to_schema_for_export_serialization(self) -> None:
        """`_EXPORT_PLAN` 계약 — 등재 모델은 `to_schema()`를 보유해야 직렬화된다."""
        assert callable(getattr(HintUsage, "to_schema", None))
