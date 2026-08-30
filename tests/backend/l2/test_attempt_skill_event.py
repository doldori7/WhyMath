"""EOS-57 writer — 해소된 스킬 배열의 `문제시도` 이벤트 적재 (hermetic·DB 없이).

검증 축 3개:
  ① **기록 계약** — event_type·source·is_correct·skill_ids가 약속대로 실린다(계약 경유).
  ② **None ≠ []** — 해소 0건은 `[]`로 적재된다(None으로 접히면 미기록과 구분 불가).
  ③ **경계 준수** — 스킬 배열이 `event_data`로 새지 않고 1급 컬럼에만 실린다.

실 PG 적재(enum 값 존재·ARRAY 왕복)는 마이그레이션·통합 축이 본다 — 여기서는 writer가 만드는
객체의 모양만 못박는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2.attempt_skill_event import AttemptSource, record_attempt_skill_event
from whymath_backend.schema.enums import EventType

_UID = uuid.uuid4()
_AID = uuid.uuid4()
_PID = uuid.uuid4()


class _FakeSession:
    """add/commit만 시뮬 — writer는 조회를 하지 않는다(해소는 호출부가 이미 끝냈다)."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


async def _record(**kwargs: Any) -> tuple[_FakeSession, Any]:
    session = _FakeSession()
    event = await record_attempt_skill_event(
        cast(AsyncSession, session),
        user_id=_UID,
        attempt_id=_AID,
        problem_id=_PID,
        **kwargs,
    )
    return session, event


async def test_records_resolved_skills_with_contract_payload() -> None:
    """① 기록 계약 — `문제시도` 1건 add + commit 1회, 페이로드는 계약 2키뿐."""
    session, event = await _record(
        is_correct=True,
        skill_ids=["skill.a", "skill.b"],
        source=AttemptSource.attempt_submit,
    )
    assert len(session.added) == 1 and session.commits == 1
    assert event.event_type is EventType.문제시도
    assert event.skill_ids == ["skill.a", "skill.b"]
    assert event.event_data == {"is_correct": True, "source": "attempt_submit"}
    assert event.attempt_id == _AID and event.user_id == _UID and event.problem_id == _PID


async def test_empty_resolution_is_recorded_as_empty_list_not_none() -> None:
    """② None ≠ [] — 해소 0건은 실측이므로 `[]`로 남는다(미기록 NULL로 접지 않는다).

    이 구분이 무너지면 기록률 리포트가 "writer가 안 돌았다"와 "돌았는데 0건"을 구별할 수 없다.
    """
    _, event = await _record(is_correct=False, skill_ids=[], source=AttemptSource.coach_completion)
    assert event.skill_ids == []
    assert event.skill_ids is not None


async def test_duplicate_skills_are_deduped_in_order() -> None:
    """같은 스킬이 여러 개념에서 해소돼도 배열엔 1회만 — 집계 분모 왜곡 0(순서는 보존)."""
    _, event = await _record(
        is_correct=True,
        skill_ids=["skill.b", "skill.a", "skill.b"],
        source=AttemptSource.attempt_submit,
    )
    assert event.skill_ids == ["skill.b", "skill.a"]


async def test_skill_ids_never_leak_into_event_data() -> None:
    """③ 경계 — 스킬 배열은 1급 컬럼에만. JSONB 병기는 두 진실원을 만든다."""
    _, event = await _record(
        is_correct=True, skill_ids=["skill.a"], source=AttemptSource.attempt_submit
    )
    assert "skill_ids" not in event.event_data


async def test_event_at_is_server_time_and_event_time_stays_null() -> None:
    """`event_at`=서버 수신 시각(이 테이블 전 writer의 실측 의미)·`event_time`은 NULL.

    채점 경로엔 클라 신고 발생 시각 축이 없다 — 수신 시각을 발생으로 복제하면 날조다(EOS-48).
    """
    fixed = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)
    _, event = await _record(
        is_correct=True,
        skill_ids=["skill.a"],
        source=AttemptSource.attempt_submit,
        event_at=fixed,
    )
    assert event.event_at == fixed
    assert event.event_time is None


async def test_source_labels_are_closed_two() -> None:
    """경로 라벨은 폐쇄 2종 — 기록률 리포트의 경로별 분모가 이 집합에 의존한다."""
    assert {s.value for s in AttemptSource} == {"attempt_submit", "coach_completion"}
