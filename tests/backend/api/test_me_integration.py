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
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.enums import (
    AuditResourceType,
    ConceptLevel,
    ConceptRole,
    Curriculum,
    Persona,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
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


def _session_row(
    sid: uuid.UUID,
    uid: uuid.UUID,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> LearningSession:
    # started_at 생략 시 server_default now(). 시간창 테스트는 명시 값 주입.
    # ended_at은 nullable(미종료 None) — slice 69 ended_at 시간창 테스트용.
    return LearningSession.from_schema(
        LearningSessionSchema(
            session_id=sid, user_id=uid, started_at=started_at, ended_at=ended_at
        )
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

            # slice 68: 다중 OR(IN) — learning_session + dialogue → 3건(2+1)
            resp = client.get(
                "/v1/me/deletions",
                headers=auth,
                params=[
                    ("resource_type", "learning_session"),
                    ("resource_type", "dialogue"),
                ],
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            assert len(rows) == 3
            assert {r["resource_type"] for r in rows} == {
                "learning_session",
                "dialogue",
            }

            # slice 71: include_total → X-Total-Count = 필터 적용 총 건수(limit/offset 무시)
            resp = client.get(
                "/v1/me/deletions", headers=auth, params={"include_total": "true"}
            )
            assert resp.headers["X-Total-Count"] == "3", resp.headers
            # 필터 + 페이지 축소에도 total은 *전체 필터 건수* — learning_session 2건
            resp = client.get(
                "/v1/me/deletions",
                headers=auth,
                params={
                    "resource_type": "learning_session",
                    "limit": "1",
                    "include_total": "true",
                },
            )
            assert len(resp.json()) == 1  # 페이지는 1건
            assert resp.headers["X-Total-Count"] == "2", resp.headers  # 총 2건
            # include_total 생략 → 헤더 없음
            resp = client.get("/v1/me/deletions", headers=auth)
            assert "X-Total-Count" not in resp.headers
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


def test_me_sessions_time_window_filter_on_live_pg() -> None:
    """slice 67: /me/sessions의 ?since/until이 실 PG에서 started_at 시간창으로 필터.

    1·6·12월 세션 적재 → since=6월 2건·until=6월 2건·양끝=6월 1건·생략 3건. deletions와
    동일한 시간창 의미(apply_time_window 공용)를 다른 도메인에서도 검증.
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
                _session_row(uuid.uuid4(), uid_a, jan),
                _session_row(uuid.uuid4(), uid_a, jun),
                _session_row(uuid.uuid4(), uid_a, dec),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            assert len(client.get("/v1/me/sessions", headers=auth).json()) == 3

            resp = client.get(
                "/v1/me/sessions", headers=auth, params={"since": jun.isoformat()}
            )
            assert len(resp.json()) == 2, resp.text

            resp = client.get(
                "/v1/me/sessions", headers=auth, params={"until": jun.isoformat()}
            )
            assert len(resp.json()) == 2, resp.text

            resp = client.get(
                "/v1/me/sessions",
                headers=auth,
                params={"since": jun.isoformat(), "until": jun.isoformat()},
            )
            assert len(resp.json()) == 1, resp.text
    finally:
        asyncio.run(_cleanup([uid_a]))


def test_me_sessions_order_param_on_live_pg() -> None:
    """slice 70: ?order=asc/desc가 실 PG에서 started_at 정렬 방향을 뒤집는다.

    1·6·12월 세션(고정 id) 적재 → desc(기본)=[12,6,1]월·asc=[1,6,12]월 순서. PK 2차키는
    안정 정렬용(고유 시각이라 무영향).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    jan = datetime(2024, 1, 15, tzinfo=UTC)
    jun = datetime(2024, 6, 15, tzinfo=UTC)
    dec = datetime(2024, 12, 15, tzinfo=UTC)
    uid_a = uuid.uuid4()
    s_jan, s_jun, s_dec = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a)))
        asyncio.run(
            _add_all(
                _session_row(s_jan, uid_a, jan),
                _session_row(s_jun, uid_a, jun),
                _session_row(s_dec, uid_a, dec),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            # 기본(생략) = desc = 최신순 [12,6,1]월
            ids = [
                s["session_id"]
                for s in client.get("/v1/me/sessions", headers=auth).json()
            ]
            assert ids == [str(s_dec), str(s_jun), str(s_jan)], ids

            # order=asc = 오래된순 [1,6,12]월
            resp = client.get("/v1/me/sessions", headers=auth, params={"order": "asc"})
            ids = [s["session_id"] for s in resp.json()]
            assert ids == [str(s_jan), str(s_jun), str(s_dec)], ids
    finally:
        asyncio.run(_cleanup([uid_a]))


def test_me_sessions_ended_at_window_filter_on_live_pg() -> None:
    """slice 69: /me/sessions의 ?ended_since/until이 ended_at 시간창으로 필터.

    종료 시각 1·6월 세션 2개 + 미종료(ended_at NULL) 세션 1개 적재 → ended_since=6월은
    6월 1건(NULL·1월 제외)·ended_until=3월은 1월 1건·필터 생략은 3건. 미종료는 종료 시간창에서
    항상 제외(SQL NULL 비교).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    jan = datetime(2024, 1, 15, tzinfo=UTC)
    mar = datetime(2024, 3, 15, tzinfo=UTC)
    jun = datetime(2024, 6, 15, tzinfo=UTC)
    uid_a = uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a)))
        asyncio.run(
            _add_all(
                _session_row(uuid.uuid4(), uid_a, jan, jan),  # 1월 종료
                _session_row(uuid.uuid4(), uid_a, jan, jun),  # 6월 종료
                _session_row(uuid.uuid4(), uid_a, jan, None),  # 미종료(NULL)
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            # 필터 생략 → 3건(미종료 포함)
            assert len(client.get("/v1/me/sessions", headers=auth).json()) == 3

            # ended_since=6월 → 6월 종료 1건(1월 종료·미종료 제외)
            resp = client.get(
                "/v1/me/sessions", headers=auth, params={"ended_since": jun.isoformat()}
            )
            assert len(resp.json()) == 1, resp.text

            # ended_until=3월 → 1월 종료 1건(6월 종료·미종료 제외)
            resp = client.get(
                "/v1/me/sessions", headers=auth, params={"ended_until": mar.isoformat()}
            )
            assert len(resp.json()) == 1, resp.text
    finally:
        asyncio.run(_cleanup([uid_a]))


def test_submit_attempt_records_and_propagates_mastery_on_live_pg() -> None:
    """POST /v1/me/attempts — ProblemAttempt 적재 + 평가 개념 숙달 갱신(end-to-end)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    suffix = pid.hex[:8]

    async def _setup() -> None:
        # user(FK) + problem(FK) + concept + problem_concept(PRIMARY)
        await _add_all(_user(uid))
        await _add_all(
            Problem.from_schema(
                ProblemSchema(
                    problem_id=pid,
                    source_type=SourceType.자체생성,
                    curriculum_version=Curriculum.REVISION_2022,
                    valid_from_year=2022,
                    subject=Subject.공통,
                    unit_codes=[f"U-{suffix}"],
                )
            ),
            Concept.from_schema(
                ConceptSchema(
                    concept_id=cid,
                    code=f"C-{suffix}",
                    name_ko="채점테스트개념",
                    level=ConceptLevel.세부개념,
                )
            ),
        )
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY
                )
            )
        )

    async def _counts() -> tuple[int, int]:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.connect() as conn:
                pa = (
                    await conn.execute(
                        text("SELECT count(*) FROM problem_attempt WHERE user_id=:u"),
                        {"u": str(uid)},
                    )
                ).scalar()
                cm = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM concept_mastery_history WHERE user_id=:u"
                        ),
                        {"u": str(uid)},
                    )
                ).scalar()
            return int(pa or 0), int(cm or 0)
        finally:
            await engine.dispose()

    async def _full_cleanup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql, params in (
                    ("DELETE FROM problem_attempt WHERE user_id=:u", {"u": str(uid)}),
                    (
                        "DELETE FROM concept_mastery_history WHERE user_id=:u",
                        {"u": str(uid)},
                    ),
                    (
                        "DELETE FROM problem_concept WHERE problem_id=:p",
                        {"p": str(pid)},
                    ),
                    ("DELETE FROM problem WHERE problem_id=:p", {"p": str(pid)}),
                    ("DELETE FROM concept WHERE concept_id=:c", {"c": str(cid)}),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ):
                    await conn.execute(text(sql), params)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.post(
                "/v1/me/attempts",
                headers={"Authorization": f"Bearer {token}"},
                json={"problem_id": str(pid), "is_correct": True},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert len(body["mastery_updates"]) == 1
            assert body["mastery_updates"][0]["concept_id"] == str(cid)
            assert body["mastery_updates"][0]["mastery"] == 0.69
            # 무토큰 401
            assert (
                client.post(
                    "/v1/me/attempts", json={"problem_id": str(pid), "is_correct": True}
                ).status_code
                == 401
            )
        pa_count, cm_count = asyncio.run(_counts())
        assert pa_count == 1  # ProblemAttempt 1건
        assert cm_count == 1  # ConceptMasteryHistory 1건
    finally:
        asyncio.run(_full_cleanup())


async def _cleanup_mastery(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
    finally:
        await engine.dispose()


async def _cleanup_concepts(concept_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:ids)"), {"ids": ids}
            )
    finally:
        await engine.dispose()


def _mastery_row(
    uid: uuid.UUID, cid: uuid.UUID, measured_at: datetime, mastery: float
) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        ConceptMasteryHistorySchema(
            user_id=uid,
            concept_id=cid,
            measured_at=measured_at,
            mastery=mastery,
            sample_size=1,
        )
    )


def test_me_mastery_curve_scoped_and_concept_filter_on_live_pg() -> None:
    """GET /v1/me/mastery — A 토큰은 A의 측정만(B 차단)·?concept_id로 한 개념 곡선."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    try:
        # A: c1 2측정(t1,t2)·c2 1측정 / B: c1 1측정(스코핑 차단 확인)
        asyncio.run(
            _add_all(
                _mastery_row(uid_a, c1, t1, 0.5),
                _mastery_row(uid_a, c1, t2, 0.69),
                _mastery_row(uid_a, c2, t1, 0.3),
                _mastery_row(uid_b, c1, t1, 0.9),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            # 전체: A의 3측정만(B 제외)
            resp = client.get("/v1/me/mastery", headers=auth)
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) == 3
            # ?concept_id=c1 → c1의 2측정만
            resp = client.get(
                "/v1/me/mastery", headers=auth, params={"concept_id": str(c1)}
            )
            rows = resp.json()
            assert len(rows) == 2
            assert {str(c1)} == {r["concept_id"] for r in rows}
            # order=asc → 오래된 측정 먼저(t1의 0.5)
            resp = client.get(
                "/v1/me/mastery",
                headers=auth,
                params={"concept_id": str(c1), "order": "asc"},
            )
            asc_rows = resp.json()
            assert float(asc_rows[0]["mastery"]) == 0.5
            # 무토큰 401
            assert client.get("/v1/me/mastery").status_code == 401
    finally:
        asyncio.run(_cleanup_mastery([uid_a, uid_b]))


def test_me_mastery_current_latest_per_concept_on_live_pg() -> None:
    """GET /v1/me/mastery/current — 개념마다 최신 측정 1건만(DISTINCT ON)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    suffix = uid.hex[:8]
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    try:
        # 개념 메타(c1만 concept 행 존재·c2는 orphan → name null로 LEFT JOIN 검증)
        asyncio.run(
            _add_all(
                Concept.from_schema(
                    ConceptSchema(
                        concept_id=c1,
                        code=f"CAL-{suffix}",
                        name_ko="정적분",
                        level=ConceptLevel.세부개념,
                    )
                )
            )
        )
        # c1: 2측정(t1 0.5 → t2 0.69 최신)·c2: 1측정(0.3)
        asyncio.run(
            _add_all(
                _mastery_row(uid, c1, t1, 0.5),
                _mastery_row(uid, c1, t2, 0.69),
                _mastery_row(uid, c2, t1, 0.3),
            )
        )
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/mastery/current", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            # 3측정이지만 개념별 최신 → 2행
            assert len(rows) == 2
            by_concept = {r["concept_id"]: r for r in rows}
            assert float(by_concept[str(c1)]["mastery"]) == 0.69  # t2(최신)
            assert by_concept[str(c1)]["concept_name"] == "정적분"  # 조인된 개념명
            assert by_concept[str(c1)]["concept_code"] == f"CAL-{suffix}"
            assert float(by_concept[str(c2)]["mastery"]) == 0.3
            assert by_concept[str(c2)]["concept_name"] is None  # orphan(LEFT JOIN)
            assert client.get("/v1/me/mastery/current").status_code == 401  # 무토큰
    finally:
        asyncio.run(_cleanup_mastery([uid]))
        asyncio.run(_cleanup_concepts([c1]))


def test_me_ability_estimates_theta_from_attempts_on_live_pg() -> None:
    """GET /v1/me/ability — 채점 풀이(난이도 join)에서 IRT θ 추정(end-to-end)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    pid = uuid.uuid4()
    suffix = pid.hex[:8]

    async def _setup() -> None:
        await _add_all(_user(uid))
        await _add_all(
            Problem.from_schema(
                ProblemSchema(
                    problem_id=pid,
                    source_type=SourceType.자체생성,
                    curriculum_version=Curriculum.REVISION_2022,
                    valid_from_year=2022,
                    subject=Subject.공통,
                    unit_codes=[f"U-{suffix}"],
                    difficulty_overall=5.0,  # 어려운 문항
                )
            )
        )
        await _add_all(
            ProblemAttempt(
                attempt_id=uuid.uuid4(), user_id=uid, problem_id=pid, is_correct=True
            )
        )

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql in (
                    "DELETE FROM problem_attempt WHERE user_id=:u",
                    "DELETE FROM problem WHERE problem_id=:p",
                    "DELETE FROM user_profile WHERE user_id=:u",
                ):
                    await conn.execute(text(sql), {"u": str(uid), "p": str(pid)})
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/ability", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["response_count"] == 1
            assert body["theta"] == 4.0  # 채점 1건 전부 정답 → 능력 상한
            # slice 14: 측정 정밀도 — 응답 있으니 SE·CI 노출(유한)
            assert body["standard_error"] is not None
            assert body["standard_error"] > 0.0
            lo, hi = body["confidence_interval"]
            assert lo < body["theta"] < hi
            assert client.get("/v1/me/ability").status_code == 401  # 무토큰
            # slice 28: θ 성장 곡선 — 채점 1건 → 시점 1개(response_count 1·θ 상한)
            hist = client.get(
                "/v1/me/ability/history", headers={"Authorization": f"Bearer {token}"}
            )
            assert hist.status_code == 200, hist.text
            hpoints = hist.json()
            assert len(hpoints) == 1
            assert hpoints[0]["response_count"] == 1
            assert hpoints[0]["theta"] == 4.0
            assert hpoints[0]["as_of"]  # created_at 노출
            assert client.get("/v1/me/ability/history").status_code == 401
    finally:
        asyncio.run(_cleanup_all())


def test_me_next_problem_recommends_unattempted_on_live_pg() -> None:
    """GET /v1/me/next-problem — θ 근방·미응답 문항을 NOT IN 제외 후 정보량 최대로 추천."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    pid_done = uuid.uuid4()  # 이미 푼(정답·난이도 5) → θ 상한 + NOT IN 제외 대상
    pid_mid = uuid.uuid4()  # 미응답 난이도 3
    pid_hard = uuid.uuid4()  # 미응답 난이도 5 → θ=4에서 정보량 최대
    suffix = pid_done.hex[:8]

    def _problem(pid: uuid.UUID, difficulty: float) -> Problem:
        return Problem.from_schema(
            ProblemSchema(
                problem_id=pid,
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.공통,
                unit_codes=[f"U-{suffix}"],
                difficulty_overall=difficulty,
            )
        )

    async def _setup() -> None:
        await _add_all(_user(uid))
        await _add_all(_problem(pid_done, 5.0))
        await _add_all(_problem(pid_mid, 3.0))
        await _add_all(_problem(pid_hard, 5.0))
        await _add_all(
            ProblemAttempt(
                attempt_id=uuid.uuid4(),
                user_id=uid,
                problem_id=pid_done,
                is_correct=True,
            )
        )

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM problem_attempt WHERE user_id=:u"),
                    {"u": str(uid)},
                )
                for pid in (pid_done, pid_mid, pid_hard):
                    await conn.execute(
                        text("DELETE FROM problem WHERE problem_id=:p"),
                        {"p": str(pid)},
                    )
                await conn.execute(
                    text("DELETE FROM user_profile WHERE user_id=:u"), {"u": str(uid)}
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/next-problem", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["theta"] == 4.0  # 정답 1건 → 능력 상한
            # 이미 푼 난이도-5 문항(pid_done)은 NOT IN 제외 → 미응답 난이도-5(pid_hard) 추천
            assert body["problem_id"] == str(pid_hard)
            assert body["problem_id"] != str(pid_done)
            assert body["difficulty"] == 5.0
            # slice 15: 응답 1건뿐 → SE 노출(유한)·측정 불충분
            assert body["standard_error"] is not None
            assert body["measurement_sufficient"] is False
            assert client.get("/v1/me/next-problem").status_code == 401  # 무토큰
    finally:
        asyncio.run(_cleanup_all())


def test_me_next_problem_weak_concept_priority_on_live_pg() -> None:
    """GET /v1/me/next-problem?prioritize_weak_concepts=true — 동일 난이도 두 문항 중
    약점 개념(저숙달) 문항을 BKT 숙달 스냅샷 조인으로 우선 추천(BKT+IRT 융합·end-to-end)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    pid_strong = uuid.uuid4()  # 강점 개념 문항(난이도3)
    pid_weak = uuid.uuid4()  # 약점 개념 문항(난이도3·저숙달)
    c_strong, c_weak = uuid.uuid4(), uuid.uuid4()
    suffix = uid.hex[:8]
    t1 = datetime(2026, 1, 1, tzinfo=UTC)

    def _problem(pid: uuid.UUID) -> Problem:
        return Problem.from_schema(
            ProblemSchema(
                problem_id=pid,
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.공통,
                unit_codes=[f"U-{suffix}"],
                difficulty_overall=3.0,
            )
        )

    def _concept(cid: uuid.UUID, code: str) -> Concept:
        return Concept.from_schema(
            ConceptSchema(
                concept_id=cid, code=code, name_ko=code, level=ConceptLevel.세부개념
            )
        )

    async def _setup() -> None:
        await _add_all(_user(uid))
        await _add_all(
            _concept(c_strong, f"S-{suffix}"), _concept(c_weak, f"W-{suffix}")
        )
        await _add_all(_problem(pid_strong), _problem(pid_weak))
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=pid_strong, concept_id=c_strong, role=ConceptRole.PRIMARY
                )
            ),
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=pid_weak, concept_id=c_weak, role=ConceptRole.PRIMARY
                )
            ),
        )
        # 숙달: 강점 1.0 · 약점 0.0
        await _add_all(
            _mastery_row(uid, c_strong, t1, 1.0),
            _mastery_row(uid, c_weak, t1, 0.0),
        )

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql, params in (
                    (
                        "DELETE FROM concept_mastery_history WHERE user_id=:u",
                        {"u": str(uid)},
                    ),
                    (
                        "DELETE FROM problem_concept WHERE problem_id = ANY(:p)",
                        {"p": [str(pid_strong), str(pid_weak)]},
                    ),
                    (
                        "DELETE FROM problem WHERE problem_id = ANY(:p)",
                        {"p": [str(pid_strong), str(pid_weak)]},
                    ),
                    (
                        "DELETE FROM concept WHERE concept_id = ANY(:c)",
                        {"c": [str(c_strong), str(c_weak)]},
                    ),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ):
                    await conn.execute(text(sql), params)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            auth = {"Authorization": f"Bearer {token}"}
            # 약점 우선 → 저숙달 개념(pid_weak) 추천(동일 난이도·가중으로 역전)
            resp = client.get(
                "/v1/me/next-problem?prioritize_weak_concepts=true", headers=auth
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["problem_id"] == str(pid_weak)
    finally:
        asyncio.run(_cleanup_all())


def test_me_ability_by_concept_on_live_pg() -> None:
    """GET /v1/me/ability/by-concept — 채점 풀이를 개념별로 묶어 θ 분리 추정·약점 먼저(end-to-end)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    p_strong, p_weak = uuid.uuid4(), uuid.uuid4()
    c_strong, c_weak = uuid.uuid4(), uuid.uuid4()
    suffix = uid.hex[:8]

    def _problem(pid: uuid.UUID) -> Problem:
        return Problem.from_schema(
            ProblemSchema(
                problem_id=pid,
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.공통,
                unit_codes=[f"U-{suffix}"],
                difficulty_overall=3.0,
            )
        )

    def _concept(cid: uuid.UUID, code: str, name: str) -> Concept:
        return Concept.from_schema(
            ConceptSchema(
                concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념
            )
        )

    async def _setup() -> None:
        await _add_all(_user(uid))
        await _add_all(
            _concept(c_strong, f"S-{suffix}", "강점개념"),
            _concept(c_weak, f"W-{suffix}", "약점개념"),
        )
        await _add_all(_problem(p_strong), _problem(p_weak))
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=p_strong, concept_id=c_strong, role=ConceptRole.PRIMARY
                )
            ),
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=p_weak, concept_id=c_weak, role=ConceptRole.PRIMARY
                )
            ),
        )
        # 강점 문항 정답(θ↑)·약점 문항 오답(θ↓)
        await _add_all(
            ProblemAttempt(
                attempt_id=uuid.uuid4(),
                user_id=uid,
                problem_id=p_strong,
                is_correct=True,
            ),
            ProblemAttempt(
                attempt_id=uuid.uuid4(),
                user_id=uid,
                problem_id=p_weak,
                is_correct=False,
            ),
        )

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql, params in (
                    ("DELETE FROM problem_attempt WHERE user_id=:u", {"u": str(uid)}),
                    (
                        "DELETE FROM problem_concept WHERE problem_id = ANY(:p)",
                        {"p": [str(p_strong), str(p_weak)]},
                    ),
                    (
                        "DELETE FROM problem WHERE problem_id = ANY(:p)",
                        {"p": [str(p_strong), str(p_weak)]},
                    ),
                    (
                        "DELETE FROM concept WHERE concept_id = ANY(:c)",
                        {"c": [str(c_strong), str(c_weak)]},
                    ),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ):
                    await conn.execute(text(sql), params)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/ability/by-concept",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            assert len(rows) == 2
            # 약점(오답·θ=-4) 개념 먼저, 강점(정답·θ=4) 나중
            assert rows[0]["concept_id"] == str(c_weak)
            assert rows[0]["theta"] == -4.0
            assert rows[0]["concept_name"] == "약점개념"
            assert rows[1]["concept_id"] == str(c_strong)
            assert rows[1]["theta"] == 4.0
            assert client.get("/v1/me/ability/by-concept").status_code == 401
    finally:
        asyncio.run(_cleanup_all())


def test_me_concept_diagnosis_cross_check_on_live_pg() -> None:
    """GET /v1/me/diagnosis/concepts — BKT 숙달↔IRT θ 불일치(irt_higher·bkt_higher) 교차검증(end-to-end)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    # c1: BKT 낮음(0.1)인데 정답(θ↑) → irt_higher / c2: BKT 높음(0.9)인데 오답(θ↓) → bkt_higher
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    suffix = uid.hex[:8]
    t1 = datetime(2026, 1, 1, tzinfo=UTC)

    def _problem(pid: uuid.UUID) -> Problem:
        return Problem.from_schema(
            ProblemSchema(
                problem_id=pid,
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.공통,
                unit_codes=[f"U-{suffix}"],
                difficulty_overall=3.0,
            )
        )

    def _concept(cid: uuid.UUID, code: str, name: str) -> Concept:
        return Concept.from_schema(
            ConceptSchema(
                concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념
            )
        )

    async def _setup() -> None:
        await _add_all(_user(uid))
        await _add_all(
            _concept(c1, f"A-{suffix}", "개념1"), _concept(c2, f"B-{suffix}", "개념2")
        )
        await _add_all(_problem(p1), _problem(p2))
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=p1, concept_id=c1, role=ConceptRole.PRIMARY
                )
            ),
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=p2, concept_id=c2, role=ConceptRole.PRIMARY
                )
            ),
        )
        await _add_all(
            ProblemAttempt(
                attempt_id=uuid.uuid4(), user_id=uid, problem_id=p1, is_correct=True
            ),
            ProblemAttempt(
                attempt_id=uuid.uuid4(), user_id=uid, problem_id=p2, is_correct=False
            ),
        )
        # BKT: c1 낮음·c2 높음(IRT와 반대 → 불일치 신호)
        await _add_all(_mastery_row(uid, c1, t1, 0.1), _mastery_row(uid, c2, t1, 0.9))

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql, params in (
                    ("DELETE FROM problem_attempt WHERE user_id=:u", {"u": str(uid)}),
                    (
                        "DELETE FROM concept_mastery_history WHERE user_id=:u",
                        {"u": str(uid)},
                    ),
                    (
                        "DELETE FROM problem_concept WHERE problem_id = ANY(:p)",
                        {"p": [str(p1), str(p2)]},
                    ),
                    (
                        "DELETE FROM problem WHERE problem_id = ANY(:p)",
                        {"p": [str(p1), str(p2)]},
                    ),
                    (
                        "DELETE FROM concept WHERE concept_id = ANY(:c)",
                        {"c": [str(c1), str(c2)]},
                    ),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ):
                    await conn.execute(text(sql), params)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/diagnosis/concepts",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, resp.text
            by_concept = {r["concept_id"]: r for r in resp.json()}
            assert by_concept[str(c1)]["agreement"] == "irt_higher"  # 정답인데 BKT 낮음
            assert by_concept[str(c2)]["agreement"] == "bkt_higher"  # 오답인데 BKT 높음
            assert by_concept[str(c1)]["bkt_mastery"] == 0.1
            assert by_concept[str(c2)]["irt_theta"] == -4.0
            # slice 21: L4 코칭 처방 결선(L2→L4→L5 풀 스택)
            assert by_concept[str(c1)]["coaching"]["focus"] == "consolidate"
            assert by_concept[str(c2)]["coaching"]["focus"] == "retrieval"
            assert client.get("/v1/me/diagnosis/concepts").status_code == 401
    finally:
        asyncio.run(_cleanup_all())
