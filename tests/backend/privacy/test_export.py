"""개인정보 열람·이동권(`privacy/export.py`) — 단위(hermetic·FakeSession) + 실 PG 통합.

단위(FakeSession): `export_user_data`의 *조립 로직*만 검증한다 — `_EXPORT_PLAN` 카테고리별 직렬화·
user_profile 단건·`exported_at`·`not_included` 고지·**읽기 전용**(execute만·commit/flush 0).
`external_export_pending`(외부 store 매니페스트)도 검증. ★실제 ORM 직렬화·**대화 턴 조인 스코핑**
(증분 6·`dialogue_turn`엔 user_id 없음)은 *실 PG 통합테스트*가 seed→export로 검증한다(중복 0).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.dialogue import Dialogue, DialogueTurn
from whymath_backend.db.models.user import UserProfile
from whymath_backend.privacy.export import (
    ExternalDataLocation,
    UserDataExport,
    export_user_data,
    external_export_pending,
)
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.dialogue import DialogueTurn as DialogueTurnSchema
from whymath_backend.schema.enums import ContentType, Persona, TurnRole
from whymath_backend.schema.user import UserProfile as UserProfileSchema

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
    "daily_learning_metrics",
    "user_behavior_metrics",
    "dialogues",
    "dialogue_turns",
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
        """15종 카테고리(+대화 턴 조인) 직렬화 + user_profile 단건 + exported_at + 읽기 전용."""
        uid = uuid.uuid4()
        # _EXPORT_PLAN(14) + dialogue_turns 조인(1) + profile(1) = 16 execute. learning_sessions
        # (0)·ability_snapshots(4)·parental_consents(5)·misconception_hypotheses(9)·
        # misconception_evidence(10)·daily_learning_metrics(11)·user_behavior_metrics(12)·
        # dialogues(13)·dialogue_turns(14)에 구분 행, 나머지 빈, 마지막 profile.
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
                [_StubRow({"cat": "dlm"})],
                [_StubRow({"cat": "ubm"})],
                [_StubRow({"cat": "dlg"})],
                [_StubRow({"cat": "dlt"})],
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
        assert out.data["misconception_hypotheses"] == [{"cat": "mh"}]  # 증분 3
        assert out.data["misconception_evidence"] == [{"cat": "me"}]  # 증분 3(student_id 스코핑)
        assert out.data["daily_learning_metrics"] == [{"cat": "dlm"}]  # 증분 4 신규
        assert out.data["user_behavior_metrics"] == [{"cat": "ubm"}]  # 증분 4 신규
        assert out.data["dialogues"] == [{"cat": "dlg"}]  # 증분 5 신규(대화 세션 메타)
        assert out.data["dialogue_turns"] == [{"cat": "dlt"}]  # 증분 6 신규(대화 턴 본문·조인)
        assert out.user_profile == {"cat": "profile"}
        assert len(out.not_included) >= 1  # 부분 export 정직 고지
        assert fake.commits == 0 and fake.flushes == 0  # 읽기 전용(저장소 패턴)
        assert len(fake.executed) == 16

    def test_no_profile_yields_none(self) -> None:
        """프로필 행이 없으면 user_profile=None·각 카테고리 빈 리스트."""
        fake = _FakeSession([[] for _ in range(16)])
        out = _run(fake, uuid.uuid4())
        assert out.user_profile is None
        assert all(rows == [] for rows in out.data.values())
        assert set(out.data.keys()) == _CATEGORIES

    def test_multiple_rows_preserved(self) -> None:
        """카테고리당 다행 직렬화 보존(리스트 순서)."""
        fake = _FakeSession([[_StubRow({"n": 1}), _StubRow({"n": 2})], *([[]] * 15)])
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


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — seed→export 왕복(증분 6 대화 턴 조인 스코핑 검증)
# ===========================================================================

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _build_user(user_id: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(
            user_id=user_id,
            persona_primary=Persona.A_일반고고3,
            nickname="열람학생",
            email_hash=f"HASH-{user_id.hex[:8]}",
            is_minor=True,
        )
    )


def _build_turn(dialogue_id: uuid.UUID, order: int, content: str) -> DialogueTurn:
    return DialogueTurn.from_schema(
        DialogueTurnSchema(
            dialogue_id=dialogue_id,
            turn_order=order,
            role=TurnRole.student,
            content=content,
            content_type=ContentType.텍스트,
            spoken_at=datetime.now(UTC),
        )
    )


async def _cleanup(user_ids: tuple[uuid.UUID, ...], dialogue_ids: tuple[uuid.UUID, ...]) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            for did in dialogue_ids:
                await conn.execute(
                    text("DELETE FROM dialogue_turn WHERE dialogue_id = :k"), {"k": str(did)}
                )
            for uid in user_ids:
                await conn.execute(text("DELETE FROM dialogue WHERE user_id = :k"), {"k": str(uid)})
                await conn.execute(
                    text("DELETE FROM user_profile WHERE user_id = :k"), {"k": str(uid)}
                )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_export_dialogue_turns_scoped_by_join_on_live_pg() -> None:
    """증분 6 — `dialogue_turns`는 user_id 직접 키가 없어 `Dialogue` 조인으로 본인 턴만(타인 제외).

    학생 A의 대화 턴 2건(역순 삽입)·학생 B의 턴 1건을 심고, A의 export가 A의 2턴만 turn_order
    오름차순·본문 round-trip으로 담고 B의 턴은 *조인 WHERE user_id 스코핑*으로 제외함을 실 PG로
    검증한다(hermetic FakeSession이 못 잡는 실제 조인 SQL·정렬·직렬화).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    a_uid = uuid.uuid4()
    b_uid = uuid.uuid4()
    a_did = uuid.uuid4()
    b_did = uuid.uuid4()

    async def _seed(sm: async_sessionmaker[AsyncSession]) -> None:
        async with sm() as session:
            session.add(_build_user(a_uid))
            session.add(_build_user(b_uid))
            session.add(
                Dialogue.from_schema(
                    DialogueSchema(dialogue_id=a_did, user_id=a_uid, total_turns=2)
                )
            )
            session.add(
                Dialogue.from_schema(
                    DialogueSchema(dialogue_id=b_did, user_id=b_uid, total_turns=1)
                )
            )
            await session.flush()
            session.add(_build_turn(a_did, 2, "두번째 턴"))  # 역순 삽입 → 정렬 검증
            session.add(_build_turn(a_did, 1, "첫번째 턴"))
            session.add(_build_turn(b_did, 1, "타인 턴"))
            await session.commit()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            await _seed(sm)
            async with sm() as session:
                export = await export_user_data(session, user_id=a_uid)

            # 대화 세션 메타 — A의 대화만(B 제외).
            dialogues = export.data["dialogues"]
            assert [d["dialogue_id"] for d in dialogues] == [str(a_did)]

            # 대화 턴 — A의 2턴만·turn_order 오름차순·본문 round-trip·B 턴 제외(조인 스코핑).
            turns = export.data["dialogue_turns"]
            assert [t["turn_order"] for t in turns] == [1, 2]
            assert [t["content"] for t in turns] == ["첫번째 턴", "두번째 턴"]
            assert all(t["dialogue_id"] == str(a_did) for t in turns)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup((a_uid, b_uid), (a_did, b_did)))
