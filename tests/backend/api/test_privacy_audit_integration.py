"""SEC-09 개인정보 감사(`privacy_audit`) — 실 PG 통합테스트 (기본 SKIP).

acceptance 3종 검증:
  1. `GET /v1/me/export`·`POST /v1/users/me/parental-consent`가 각각 감사 **정확히 1행**을
     주행위와 *동일 트랜잭션*으로 적재한다(`test_export_writes_exactly_one_audit_row_on_live_pg`·
     `test_consent_grant_writes_exactly_one_audit_row_on_live_pg`).
  2. 본인 조회 경로(`/v1/me/*`, `/export` 제외) 전부가 감사 **0행**을 유지한다 — 경계 동결
     (`test_self_scoped_routes_produce_zero_privacy_audit_rows`).
  3. 평문 IP는 어떤 행에도 없고(`test_no_plaintext_ip_ever_stored`), `deletion_audit`가 삭제
     감사의 단일 권위로 남아 `privacy_audit`에 삭제가 중복 적재되지 않는다
     (`test_account_deletion_does_not_write_privacy_audit`).

`get_settings`만 오버라이드(jwt 시크릿·pii_audit_ip_salt·parental_consent_grant_enabled),
`get_session`은 실 PG(`test_audit_integration.py`·`test_me_integration.py` 패턴 답습).
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_SALT = "integration-pii-audit-ip-salt-0123456789abcdef"


def _settings() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        pii_audit_ip_salt=SecretStr(_SALT),
        parental_consent_grant_enabled=True,
    )


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


async def _exec(stmts: list[tuple[str, dict[str, object]]]) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            for sql, params in stmts:
                await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _fetchall(sql: str, params: dict[str, object]) -> list[tuple[object, ...]]:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return [tuple(row) for row in result.all()]
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    # raise_server_exceptions=False: 경계 테스트는 임의 입력으로 다수 엔드포인트를 두드리므로
    # (성공/404/422 무관 — 감사 0행만 확인) 개별 엔드포인트의 내부 500도 응답으로 받아 처리한다
    # (raise 시 테스트가 그 엔드포인트의 *비즈니스 로직 버그*로 죽어 경계 확인 자체를 못함).
    return TestClient(app, raise_server_exceptions=False)


async def _seed_user(user_id: uuid.UUID, *, is_minor: bool = False) -> None:
    """ORM 경로로 적재(raw INSERT 대신) — Pydantic 스키마 기본값(빈 list 등)을 그대로 채워야
    `export_user_data`의 `UserProfile.to_schema()`(list-type 컬럼 NOT NULL 기대)가 안전하다.
    """
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                UserProfile.from_schema(
                    UserProfileSchema(
                        user_id=user_id, persona_primary=Persona.A_일반고고3, is_minor=is_minor
                    )
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup_user(user_id: uuid.UUID) -> None:
    await _exec(
        [
            ("DELETE FROM privacy_audit WHERE user_id = :u", {"u": str(user_id)}),
            ("DELETE FROM deletion_audit WHERE user_id = :u", {"u": str(user_id)}),
            ("DELETE FROM parental_consent WHERE user_id = :u", {"u": str(user_id)}),
            ("DELETE FROM learning_session WHERE user_id = :u", {"u": str(user_id)}),
            ("DELETE FROM user_profile WHERE user_id = :u", {"u": str(user_id)}),
        ]
    )


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(user_id, settings=_settings())
    return {"Authorization": f"Bearer {token}"}


# 본인 조회 경로 — `api/me.py`의 `@router.*` 28개(반출 제외) + SEC-09 신규 `/privacy-audit`
# = 29개. `{concept_id}`·`{session_id}` 등 경로 변수는 호출 시 무작위 UUID로 치환한다(존재하지
# 않는 리소스라 대부분 404/422 — 그래도 무관, 감사 0행만 확인). DELETE ""(계정 삭제)는 확인
# 문구 없이 보내 422로 막는다(실제 삭제는 별도 테스트가 검증 — 여기선 부작용 없이 라우팅만
# 두드린다).
_SELF_SCOPED_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/v1/me/sessions"),
    ("GET", "/v1/me/assessments"),
    ("GET", "/v1/me/dialogues"),
    ("GET", "/v1/me/deletions"),
    ("POST", "/v1/me/attempts"),
    ("GET", "/v1/me/mastery"),
    ("GET", "/v1/me/skill-mastery"),
    ("GET", "/v1/me/mastery/current"),
    ("GET", "/v1/me/ability"),
    ("POST", "/v1/me/ability/snapshots"),
    ("GET", "/v1/me/ability/snapshots"),
    ("GET", "/v1/me/ability/by-concept"),
    ("GET", "/v1/me/ability/history"),
    ("GET", "/v1/me/diagnosis/concepts"),
    ("GET", "/v1/me/diagnosis/summary"),
    ("GET", "/v1/me/weak-concepts"),
    ("GET", "/v1/me/weak-concepts/{concept_id}/prerequisites"),
    ("GET", "/v1/me/weak-concepts/{concept_id}/coaching"),
    ("GET", "/v1/me/weak-concepts/{concept_id}/learning-path"),
    ("GET", "/v1/me/next-problem"),
    ("PATCH", "/v1/me/sessions/{session_id}/end"),
    ("DELETE", "/v1/me/sessions/{session_id}"),
    ("PATCH", "/v1/me/dialogues/{dialogue_id}/end"),
    ("DELETE", "/v1/me/dialogues/{dialogue_id}"),
    ("PATCH", "/v1/me/assessments/{assessment_id}/complete"),
    ("DELETE", "/v1/me/assessments/{assessment_id}"),
    ("DELETE", "/v1/me"),  # 계정 삭제 — 확인 문구 없이 보내 422(부작용 0)
    ("GET", "/v1/me/harness-metrics"),
    ("GET", "/v1/me/privacy-audit"),  # 자기 자신의 감사 로그 조회도 감사 이벤트가 아니다
)


def _format_path(template: str) -> str:
    placeholders = {
        "concept_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "dialogue_id": str(uuid.uuid4()),
        "assessment_id": str(uuid.uuid4()),
    }
    return template.format(**placeholders)


class TestSelfScopedRoutesProduceZeroPrivacyAuditRows:
    def test_self_scoped_routes_produce_zero_privacy_audit_rows(self) -> None:
        """SEC-09 경계 동결: `/export` 제외 본인 조회/조작 경로는 전부 `privacy_audit` 0행."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        try:
            asyncio.run(_seed_user(uid))
            headers = _auth_headers(uid)
            with _client() as client:
                for method, template in _SELF_SCOPED_ROUTES:
                    path = _format_path(template)
                    # POST/PATCH/DELETE 전부 빈 JSON 본문(스키마 필수 필드 위반 → 대개
                    # 422/400 — 어떤 상태 코드든 무관, 아래 최종 카운트만 판정).
                    kwargs: dict[str, Any] = (
                        {"json": {}} if method in ("POST", "PATCH", "DELETE") else {}
                    )
                    resp = client.request(method, path, headers=headers, **kwargs)
                    assert resp.status_code < 600, f"{method} {path} -> {resp.status_code}"

            rows = asyncio.run(
                _fetchall(
                    "SELECT event_kind FROM privacy_audit WHERE user_id = :u", {"u": str(uid)}
                )
            )
            assert rows == [], f"본인 조회 경로가 감사를 남겼습니다(경계 위반): {rows}"
        finally:
            asyncio.run(_cleanup_user(uid))


class TestExportWritesPrivacyAudit:
    def test_export_writes_exactly_one_audit_row_on_live_pg(self) -> None:
        """`GET /v1/me/export` 200 → `privacy_audit`에 event_kind=export_data 정확히 1행."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        try:
            asyncio.run(_seed_user(uid))
            headers = _auth_headers(uid)
            with _client() as client:
                resp = client.get("/v1/me/export", headers=headers)
                assert resp.status_code == 200, resp.text

            rows = asyncio.run(
                _fetchall(
                    "SELECT event_kind, user_id, target_user_id, consent_scope, ip_hash, "
                    "occurred_at FROM privacy_audit WHERE user_id = :u",
                    {"u": str(uid)},
                )
            )
            assert len(rows) == 1
            event_kind, user_id, target_user_id, consent_scope, ip_hash, occurred_at = rows[0]
            assert event_kind == "export_data"
            assert str(user_id) == str(uid)
            assert target_user_id is None
            assert consent_scope is None
            assert occurred_at is not None
            # TestClient는 로컬 클라이언트라 ip_hash가 채워지면 salt로 해시된 값이어야 한다.
            if ip_hash is not None:
                assert ip_hash != "testclient"
                assert len(ip_hash) == 64

            # 반출을 다시 호출해도 감사는 append-only로 누적(2행) — 삭제되지 않는다.
            with _client() as client:
                resp2 = client.get("/v1/me/export", headers=headers)
                assert resp2.status_code == 200, resp2.text
            rows2 = asyncio.run(
                _fetchall(
                    "SELECT event_kind FROM privacy_audit WHERE user_id = :u", {"u": str(uid)}
                )
            )
            assert len(rows2) == 2
        finally:
            asyncio.run(_cleanup_user(uid))


class TestConsentChangeWritesPrivacyAudit:
    def test_consent_grant_writes_exactly_one_audit_row_on_live_pg(self) -> None:
        """`POST /v1/users/me/parental-consent` 201 → consent_change 1행(동일 TX)."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        try:
            asyncio.run(_seed_user(uid, is_minor=True))
            headers = _auth_headers(uid)
            with _client() as client:
                resp = client.post(
                    "/v1/users/me/parental-consent",
                    headers=headers,
                    json={"guardian_email": "parent@example.com"},
                )
                assert resp.status_code == 201, resp.text

            audit_rows = asyncio.run(
                _fetchall(
                    "SELECT event_kind, user_id, consent_scope, ip_hash "
                    "FROM privacy_audit WHERE user_id = :u",
                    {"u": str(uid)},
                )
            )
            assert len(audit_rows) == 1
            event_kind, user_id, consent_scope, ip_hash = audit_rows[0]
            assert event_kind == "consent_change"
            assert str(user_id) == str(uid)
            assert consent_scope == "service_core"

            # 같은 트랜잭션 원자성: parental_consent 행도 정확히 1개 존재(둘 다 성공했다는 증거 —
            # 부분 실패였다면 한쪽만 있었을 것).
            consent_rows = asyncio.run(
                _fetchall(
                    "SELECT count(*) FROM parental_consent WHERE user_id = :u", {"u": str(uid)}
                )
            )
            assert consent_rows[0][0] == 1
        finally:
            asyncio.run(_cleanup_user(uid))


class TestNoPlaintextIp:
    def test_no_plaintext_ip_ever_stored(self) -> None:
        """저장된 ip_hash는 원본과 다르고(평문 0), 같은 해시 함수로 재현 가능(진짜 값 검증)."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        try:
            asyncio.run(_seed_user(uid))
            headers = _auth_headers(uid)
            with _client() as client:
                # TestClient는 client.host="testclient" 고정(ASGI scope 기본값) — 실기기 IP가
                # 아니므로 저장된 해시가 이 고정값의 sha256(salt+"testclient")과 일치해야 한다.
                resp = client.get("/v1/me/export", headers=headers)
                assert resp.status_code == 200, resp.text

            rows = asyncio.run(
                _fetchall("SELECT ip_hash FROM privacy_audit WHERE user_id = :u", {"u": str(uid)})
            )
            assert len(rows) == 1
            (ip_hash,) = rows[0]
            # 평문(TestClient의 고정 클라이언트 host="testclient") 부재 단언.
            if ip_hash is not None:
                assert "testclient" not in ip_hash
                # 같은 해시 함수로 재현 가능(진짜 값을 테스트하지, 항상 참인 tautology가 아님).
                expected = hashlib.sha256(_SALT.encode("utf-8") + b"testclient").hexdigest()
                assert ip_hash == expected
                assert len(ip_hash) == 64
        finally:
            asyncio.run(_cleanup_user(uid))


class TestDeletionDoesNotWritePrivacyAudit:
    def test_account_deletion_does_not_write_privacy_audit(self) -> None:
        """`deletion_audit`가 삭제 감사의 단일 권위 — 세션 삭제가 `privacy_audit`에 미적재."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid, sid = uuid.uuid4(), uuid.uuid4()
        try:
            asyncio.run(_seed_user(uid))
            asyncio.run(
                _exec(
                    [
                        (
                            "INSERT INTO learning_session (session_id, user_id) VALUES (:s, :u)",
                            {"s": str(sid), "u": str(uid)},
                        ),
                    ]
                )
            )
            headers = _auth_headers(uid)
            with _client() as client:
                resp = client.delete(f"/v1/me/sessions/{sid}", headers=headers)
                assert resp.status_code == 204, resp.text

            # 기존 단일 권위(deletion_audit)엔 1행 — 회귀 없음(SEC-09가 건드리지 않았다).
            deletion_rows = asyncio.run(
                _fetchall(
                    "SELECT resource_type FROM deletion_audit WHERE user_id = :u "
                    "AND resource_id = :s",
                    {"u": str(uid), "s": str(sid)},
                )
            )
            assert len(deletion_rows) == 1
            assert deletion_rows[0][0] == "learning_session"

            # 신규 테이블엔 삭제 이벤트가 *전혀* 없다(이중 진실원천 금지 — D3 판단 근거).
            privacy_rows = asyncio.run(
                _fetchall(
                    "SELECT event_kind FROM privacy_audit WHERE user_id = :u", {"u": str(uid)}
                )
            )
            assert privacy_rows == []
        finally:
            asyncio.run(_cleanup_user(uid))
