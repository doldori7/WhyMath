"""me 라우터 통합테스트 — 실 PG로 본인 데이터 스코핑 검증 (기본 SKIP).

핵심: 두 사용자 A·B의 학습 세션을 적재하고, A 토큰으로 /v1/me/sessions를 부르면 **A의 것만**
나오는지(타인 데이터 차단 — CLAUDE.md 미성년 PII·식별 분석 금기) 검증한다. get_settings만
오버라이드(jwt 시크릿), get_session은 실 PG. 행은 독립 엔진으로 ORM 적재·정리(FK 순서 준수).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import LearningSession
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.enums import AuditResourceType, Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

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


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: 자식(learning_session) 먼저, 부모(user_profile) 나중.
            await conn.execute(
                text("DELETE FROM learning_session WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            # deletion_audit는 user_id가 FK 아님(독립 잔존 로그) — user_id로 정리.
            await conn.execute(
                text("DELETE FROM deletion_audit WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
    finally:
        await engine.dispose()


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
    )


def _session_row(sid: uuid.UUID, uid: uuid.UUID) -> LearningSession:
    return LearningSession.from_schema(
        LearningSessionSchema(session_id=sid, user_id=uid)
    )


def _deletion_row(
    uid: uuid.UUID,
    resource_type: AuditResourceType,
    deleted_at: datetime | None = None,
) -> DeletionAudit:
    # from_schema는 deleted_at을 명시 전달하므로 None이면 NOT NULL 위반 위험(운영 경로는
    # deleted_at 생략→server_default now()). 시드는 항상 명시 timestamp(미지정 시 현재) 주입.
    return DeletionAudit.from_schema(
        DeletionAuditSchema(
            user_id=uid,
            resource_type=resource_type,
            resource_id=uuid.uuid4(),
            deleted_at=deleted_at or datetime.now(UTC),
        )
    )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_me_sessions_scoped_to_current_user_on_live_pg() -> None:
    """A·B 세션 적재 → A 토큰 /me/sessions는 A의 것만(B 제외). 무토큰 401."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
    try:
        # FK 순서: 부모(user_profile) 먼저 커밋 → 자식(learning_session). user_id는
        # 원시 FK 컬럼(관계 아님)이라 한 flush에 섞으면 INSERT 순서를 못 정한다.
        asyncio.run(_add_all(_user(uid_a), _user(uid_b)))
        asyncio.run(_add_all(_session_row(sid_a, uid_a), _session_row(sid_b, uid_b)))
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            resp = client.get("/v1/me/sessions", headers=auth)
            assert resp.status_code == 200, resp.text
            ids = {s["session_id"] for s in resp.json()}
            assert str(sid_a) in ids  # 본인 것 보임
            assert str(sid_b) not in ids  # 타인 것 차단 — 핵심 보안

            # 데이터 없는 본인 도메인은 [](스코핑·결선 확인)
            assert client.get("/v1/me/assessments", headers=auth).json() == []
            assert client.get("/v1/me/dialogues", headers=auth).json() == []

            assert client.get("/v1/me/sessions").status_code == 401  # 무토큰
    finally:
        asyncio.run(_cleanup([uid_a, uid_b]))


def test_me_deletions_resource_type_filter_on_live_pg() -> None:
    """slice 65: ?resource_type 필터가 실 PG에서 해당 도메인만 반환·생략 시 전체.

    A의 삭제 감사를 도메인별로 적재(learning_session×2·dialogue×1) → ?resource_type=
    learning_session은 2건·dialogue는 1건·필터 생략은 3건 모두. 본인 스코핑도 함께 확인.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid_a = uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a)))
        asyncio.run(
            _add_all(
                _deletion_row(uid_a, AuditResourceType.learning_session),
                _deletion_row(uid_a, AuditResourceType.learning_session),
                _deletion_row(uid_a, AuditResourceType.dialogue),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            # 필터 생략 → 3건 전체
            resp = client.get("/v1/me/deletions", headers=auth)
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) == 3

            # learning_session 필터 → 2건, 모두 해당 도메인
            resp = client.get(
                "/v1/me/deletions",
                headers=auth,
                params={"resource_type": "learning_session"},
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            assert len(rows) == 2
            assert {r["resource_type"] for r in rows} == {"learning_session"}

            # dialogue 필터 → 1건
            resp = client.get(
                "/v1/me/deletions", headers=auth, params={"resource_type": "dialogue"}
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) == 1

            # 삭제 이력 없는 도메인 → []
            resp = client.get(
                "/v1/me/deletions", headers=auth, params={"resource_type": "assessment"}
            )
            assert resp.status_code == 200, resp.text
            assert resp.json() == []
    finally:
        asyncio.run(_cleanup([uid_a]))


def test_me_deletions_time_window_filter_on_live_pg() -> None:
    """slice 66: ?since/until이 실 PG에서 deleted_at 시간창으로 필터(inclusive).

    A의 삭제 감사를 1월·6월·12월로 적재 → since=6월은 6·12월 2건·until=6월은 1·6월 2건·
    since=6월&until=6월은 6월 1건(inclusive 경계 확인)·필터 생략은 3건 전체.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    jan = datetime(2024, 1, 15, tzinfo=UTC)
    jun = datetime(2024, 6, 15, tzinfo=UTC)
    dec = datetime(2024, 12, 15, tzinfo=UTC)
    uid_a = uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a)))
        asyncio.run(
            _add_all(
                _deletion_row(uid_a, AuditResourceType.dialogue, jan),
                _deletion_row(uid_a, AuditResourceType.dialogue, jun),
                _deletion_row(uid_a, AuditResourceType.dialogue, dec),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            # 필터 생략 → 3건
            assert len(client.get("/v1/me/deletions", headers=auth).json()) == 3

            # since=6월 → 6·12월(inclusive)
            resp = client.get(
                "/v1/me/deletions", headers=auth, params={"since": jun.isoformat()}
            )
            assert len(resp.json()) == 2, resp.text

            # until=6월 → 1·6월(inclusive)
            resp = client.get(
                "/v1/me/deletions", headers=auth, params={"until": jun.isoformat()}
            )
            assert len(resp.json()) == 2, resp.text

            # since=6월 & until=6월 → 6월 1건(양끝 inclusive 경계)
            resp = client.get(
                "/v1/me/deletions",
                headers=auth,
                params={"since": jun.isoformat(), "until": jun.isoformat()},
            )
            assert len(resp.json()) == 1, resp.text
    finally:
        asyncio.run(_cleanup([uid_a]))
