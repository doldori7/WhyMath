"""EOS-48 privacy 3종 영향 검토(acceptance ③) — 신규 테이블 0·기존 플랜 커버 유지의 검증.

이번 태스크는 신규 테이블이 없어(기존 3테이블 컬럼 추가) `_ERASURE_PLAN`·`_RETENTION_PLAN`·
`_EXPORT_PLAN` *변경이 0*이다 — 그러나 "검토했음"이 검증 가능해야 하므로(조율 지시) 다음을
기계로 못박는다: ① 컬럼이 추가된 3테이블이 기존 플랜에 이미 등재돼 있어 신규 컬럼도 같은
삭제·파기·반출 경로를 그대로 탄다 ② 신규 컬럼이 export payload(`to_schema().model_dump()`)에
실제로 실린다(실측 — schema 필드 대응이 없으면 to_schema가 깨지거나 payload에서 누락된다)
③ 전수 완결성 스윕은 여전히 green(신규 소유 테이블 0). hermetic — DB 0.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from whymath_backend.db.models.activity import AttemptEvent, LearningSession, ProblemAttempt
from whymath_backend.privacy.erasure import _ERASURE_PLAN
from whymath_backend.privacy.export import _EXPORT_PLAN
from whymath_backend.privacy.retention import _RETENTION_PLAN

_ALTERED_MODELS = (AttemptEvent, ProblemAttempt, LearningSession)


class TestExistingPlansStillCoverAlteredTables:
    def test_erasure_covers_all_three(self) -> None:
        """삭제권 — 컬럼이 추가된 3테이블 전부 기존 `_ERASURE_PLAN` 등재 유지(user_id 단위
        행 삭제라 신규 컬럼도 행과 함께 지워진다 — 플랜 변경 불요의 근거)."""
        planned = {m for m, _ in _ERASURE_PLAN}
        for model in _ALTERED_MODELS:
            assert model in planned, f"{model.__tablename__}이 _ERASURE_PLAN에서 빠졌다"

    def test_retention_covers_all_three_with_unchanged_axes(self) -> None:
        """보존 파기 — 3테이블 등재 유지 + 파기 축이 기존 컬럼 그대로(event_at·started_at —
        신규 event_time/ingested_at으로 *바뀌지 않았다*: 파기 창 의미 불변·회귀 0)."""
        plan = dict(_RETENTION_PLAN)
        assert plan[AttemptEvent] == "event_at"
        assert plan[ProblemAttempt] == "started_at"
        assert plan[LearningSession] == "started_at"

    def test_export_covers_all_three(self) -> None:
        """반출 — 3테이블 전부 기존 `_EXPORT_PLAN` 카테고리 유지."""
        planned = {m for m, _, _ in _EXPORT_PLAN}
        for model in _ALTERED_MODELS:
            assert model in planned, f"{model.__tablename__}이 _EXPORT_PLAN에서 빠졌다"


class TestNewColumnsLandInExportPayload:
    """`_EXPORT_PLAN` 직렬화는 `to_schema().model_dump(mode='json')` — 신규 컬럼이 payload에
    실리는지 실측(열람권 완전성: 새 개인 데이터 축이 export에서 조용히 빠지면 부분 export를
    완전 export로 위장하게 된다)."""

    def test_attempt_event_payload_carries_event_time(self) -> None:
        from whymath_backend.schema.activity import AttemptEvent as AttemptEventSchema

        orm = AttemptEvent.from_schema(
            AttemptEventSchema(
                event_at=datetime(2026, 8, 31, 1, 0, tzinfo=UTC),
                event_time=datetime(2026, 8, 30, 22, 0, tzinfo=UTC),
                user_id=uuid.uuid4(),
            )
        )
        payload = orm.to_schema().model_dump(mode="json")
        assert "event_time" in payload
        assert payload["event_time"] == "2026-08-30T22:00:00Z"

    def test_problem_attempt_payload_carries_new_fields(self) -> None:
        from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema

        orm = ProblemAttempt.from_schema(
            ProblemAttemptSchema(
                user_id=uuid.uuid4(),
                ingested_at=datetime(2026, 8, 31, 1, 0, tzinfo=UTC),
                active_seconds=300,
                idle_seconds=60,
            )
        )
        payload = orm.to_schema().model_dump(mode="json")
        assert payload["active_seconds"] == 300
        assert payload["idle_seconds"] == 60
        assert "ingested_at" in payload

    def test_learning_session_payload_carries_measured_seconds(self) -> None:
        from whymath_backend.schema.activity import LearningSession as LearningSessionSchema

        orm = LearningSession.from_schema(
            LearningSessionSchema(user_id=uuid.uuid4(), active_seconds=900, idle_seconds=120)
        )
        payload = orm.to_schema().model_dump(mode="json")
        assert payload["active_seconds"] == 900
        assert payload["idle_seconds"] == 120
