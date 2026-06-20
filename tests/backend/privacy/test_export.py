"""개인정보 열람·이동권(`privacy/export.py`) — 순수 단위(hermetic·FakeSession).

`export_user_data`의 *조립 로직*만 검증한다: `_EXPORT_PLAN` 카테고리별 직렬화·user_profile 단건·
`exported_at`·`not_included` 고지·**읽기 전용**(execute만·commit/flush 0). 실제 ORM 직렬화·실 PG
조회는 통합테스트가 검증한다(중복 0). `external_export_pending`(외부 store 매니페스트)도 검증.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.privacy.export import (
    ExternalDataLocation,
    UserDataExport,
    export_user_data,
    external_export_pending,
)

_CATEGORIES = {
    "learning_sessions",
    "problem_attempts",
    "assessments",
    "concept_mastery_history",
    "ability_snapshots",
    "parental_consents",
    "track_history",
    "persona_history",
    "state_snapshots",
    "misconception_hypotheses",
    "misconception_evidence",
}


class _StubSchema:
    """to_schema() 반환 흉내 — model_dump(mode="json")로 JSON-safe dict를 낸다."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        assert mode == "json"
        return dict(self._payload)


class _StubRow:
    """ORM 행 흉내 — to_schema()만 가진다(_row_to_json이 부르는 표면)."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def to_schema(self) -> _StubSchema:
        return _StubSchema(self._payload)


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """execute(select)별 scalars 큐를 순서대로 반환 + commit/flush 캡처(읽기 전용 검증)."""

    def __init__(self, result_rows: list[list[Any]]) -> None:
        self._queue = list(result_rows)
        self.executed: list[Any] = []
        self.commits = 0
        self.flushes = 0

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(self._queue.pop(0))

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        self.flushes += 1


def _run(session: _FakeSession, user_id: uuid.UUID) -> UserDataExport:
    return asyncio.run(export_user_data(cast(AsyncSession, session), user_id=user_id))


class TestExportUserData:
    def test_assembles_categories_and_profile(self) -> None:
        """11종 카테고리 직렬화 + user_profile 단건 + exported_at + not_included·읽기 전용."""
        uid = uuid.uuid4()
        # _EXPORT_PLAN 순서(11) + profile(1) = 12 execute. learning_sessions(0)·ability_snapshots
        # (4)·parental_consents(5)·misconception_hypotheses(9)·misconception_evidence(10)에 구분
        # 행, 나머지 빈, 마지막 profile.
        fake = _FakeSession(
            [
                [_StubRow({"cat": "ls"})],
                [],
                [],
                [],
                [_StubRow({"cat": "ab"})],
                [_StubRow({"cat": "pc"})],
                [],
                [],
                [],
                [_StubRow({"cat": "mh"})],
                [_StubRow({"cat": "me"})],
                [_StubRow({"cat": "profile"})],
            ]
        )
        out = _run(fake, uid)
        assert out.user_id == uid
        assert isinstance(out.exported_at, datetime)
        assert set(out.data.keys()) == _CATEGORIES
        assert out.data["learning_sessions"] == [{"cat": "ls"}]
        assert out.data["ability_snapshots"] == [{"cat": "ab"}]
        assert out.data["parental_consents"] == [{"cat": "pc"}]  # 증분 2 신규 카테고리
        assert out.data["misconception_hypotheses"] == [{"cat": "mh"}]  # 슬 신규
        assert out.data["misconception_evidence"] == [{"cat": "me"}]  # 슬 신규(student_id 스코핑)
        assert out.user_profile == {"cat": "profile"}
        assert len(out.not_included) >= 1  # 부분 export 정직 고지
        assert fake.commits == 0 and fake.flushes == 0  # 읽기 전용(저장소 패턴)
        assert len(fake.executed) == 12

    def test_no_profile_yields_none(self) -> None:
        """프로필 행이 없으면 user_profile=None·각 카테고리 빈 리스트."""
        fake = _FakeSession([[] for _ in range(12)])
        out = _run(fake, uuid.uuid4())
        assert out.user_profile is None
        assert all(rows == [] for rows in out.data.values())
        assert set(out.data.keys()) == _CATEGORIES

    def test_multiple_rows_preserved(self) -> None:
        """카테고리당 다행 직렬화 보존(리스트 순서)."""
        fake = _FakeSession([[_StubRow({"n": 1}), _StubRow({"n": 2})], *([[]] * 11)])
        out = _run(fake, uuid.uuid4())
        assert out.data["learning_sessions"] == [{"n": 1}, {"n": 2}]


class TestExternalExportPending:
    def test_three_stores_with_user_locator(self) -> None:
        """ClickHouse·S3·Redis 3종·각 locator에 user_id 포함."""
        uid = uuid.uuid4()
        pending = external_export_pending(uid)
        assert {t.store for t in pending} == {"clickhouse", "s3", "redis"}
        assert all(str(uid) in t.locator for t in pending)
        assert all(isinstance(t, ExternalDataLocation) for t in pending)

    def test_frozen(self) -> None:
        """ExternalDataLocation은 frozen(불변)."""
        loc = external_export_pending(uuid.uuid4())[0]
        with pytest.raises(Exception):  # noqa: B017 — pydantic frozen ValidationError
            loc.store = "x"  # type: ignore[misc]
