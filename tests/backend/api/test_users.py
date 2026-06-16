"""user 라우터 단위테스트 — /v1/users/me 조회·수정(hermetic).

엔드포인트 로직(PII 제외·자가수정 화이트리스트·If-Match·ETag)은 `get_consented_user`를
오버라이드해 고정 사용자로 검증한다(인증 자체는 test_auth.py가 검증). 무토큰 401은 실제
의존성으로 한 건 확인(라우트 결선).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema


def _user(**over: Any) -> UserProfile:
    data: dict[str, Any] = {
        "persona_primary": Persona.A_일반고고3,
        "nickname": "기존닉",
        "email_hash": "HASHED_EMAIL_VALUE",
    }
    data.update(over)
    return UserProfile.from_schema(UserProfileSchema(**data))


class FakeSession:
    """PATCH 경로용 — merge/commit/rollback만 모사."""

    def __init__(self, commit_error: Exception | None = None) -> None:
        self._commit_error = commit_error
        self.committed = False
        self.rolled_back = False

    async def merge(self, obj: Any) -> Any:
        return obj

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _client(user: UserProfile, fake: FakeSession | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = lambda: user
    if fake is not None:

        async def _sess() -> AsyncIterator[FakeSession]:
            yield fake

        app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_me_without_token_returns_401() -> None:
    """토큰 없이 /me → 401(실제 인증 의존성 결선 확인).

    get_session은 가짜로 오버라이드한다 — 무토큰 401은 세션을 쓰기 전에 발생하므로 실 엔진
    생성(전역 lazy 캐시 오염)을 피한다(다른 테스트의 import-격리 가정 보호).
    """
    app = create_app()

    async def _sess() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = _sess
    resp = TestClient(app).get("/v1/users/me")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


class TestReadMe:
    def test_returns_profile_without_pii(self) -> None:
        user = _user()
        resp = _client(user).get("/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nickname"] == "기존닉"
        assert "email_hash" not in body  # PII 제외
        assert "parent_email_hash" not in body
        assert resp.headers.get("ETag", "").startswith('"')


class TestPatchMe:
    def test_updates_whitelisted_field(self) -> None:
        user = _user()
        fake = FakeSession()
        resp = _client(user, fake).patch("/v1/users/me", json={"nickname": "새닉"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["nickname"] == "새닉"
        assert fake.committed is True

    def test_rejects_consent_field_422(self) -> None:
        """parent_consent_at 자가수정 시도 → 422(동의 게이트 우회 차단)."""
        user = _user()
        resp = _client(user, FakeSession()).patch(
            "/v1/users/me", json={"parent_consent_at": "2020-01-01T00:00:00Z"}
        )
        assert resp.status_code == 422

    def test_rejects_identity_field_422(self) -> None:
        """email_hash·is_minor 등 신원/동의 필드 자가수정 → 422."""
        user = _user()
        client = _client(user, FakeSession())
        assert client.patch("/v1/users/me", json={"email_hash": "x"}).status_code == 422
        assert client.patch("/v1/users/me", json={"is_minor": False}).status_code == 422

    def test_birth_year_change_recomputes_is_minor_true(self) -> None:
        """birth_year를 미성년 값으로 PATCH → is_minor가 서버에서 True로 재파생(클라 미요청)."""
        minor_birth_year = datetime.now(tz=timezone.utc).year - 8  # 연나이 8 ≤ 14
        user = _user(is_minor=False)  # 기존값은 False지만 birth_year로 덮어써져야 함
        fake = FakeSession()
        resp = _client(user, fake).patch(
            "/v1/users/me", json={"birth_year": minor_birth_year}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["birth_year"] == minor_birth_year
        assert resp.json()["is_minor"] is True
        assert fake.committed is True

    def test_birth_year_change_recomputes_is_minor_false(self) -> None:
        """birth_year를 성인 값으로 PATCH → is_minor가 서버에서 False로 재파생."""
        adult_birth_year = datetime.now(tz=timezone.utc).year - 30  # 연나이 30 > 14
        user = _user(is_minor=True)  # 기존 True도 birth_year 기준으로 재계산되어야 함
        resp = _client(user, FakeSession()).patch(
            "/v1/users/me", json={"birth_year": adult_birth_year}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_minor"] is False

    def test_client_supplied_is_minor_cannot_bypass_gate(self) -> None:
        """우회 차단: 미성년 birth_year + is_minor=false 동시 PATCH → 422(is_minor 자가수정 불가).

        is_minor는 화이트리스트에 없어 *직접 지정 자체*가 422다(서버 파생값에 도달하기도 전에
        거부). 즉 미성년이 is_minor=false를 끼워 넣어 게이트를 우회할 수 없다.
        """
        minor_birth_year = datetime.now(tz=timezone.utc).year - 8
        user = _user()
        resp = _client(user, FakeSession()).patch(
            "/v1/users/me",
            json={"birth_year": minor_birth_year, "is_minor": False},
        )
        assert resp.status_code == 422

    def test_unrelated_patch_self_heals_stale_is_minor(self) -> None:
        """birth_year를 안 건드는 PATCH라도 is_minor는 현재 birth_year에서 재파생(자가 치유).

        기존 레코드가 미성년 birth_year인데 is_minor가 (잘못) False로 남아 있으면, 닉네임만
        바꾸는 무관한 PATCH에도 is_minor가 True로 교정된다(is_minor=birth_year의 순수 투영).
        """
        minor_birth_year = datetime.now(tz=timezone.utc).year - 8
        user = _user(birth_year=minor_birth_year, is_minor=False)  # stale False
        resp = _client(user, FakeSession()).patch("/v1/users/me", json={"nickname": "새닉"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["nickname"] == "새닉"
        assert resp.json()["is_minor"] is True  # 서버가 birth_year 기준으로 교정

    def test_stale_if_match_returns_412(self) -> None:
        user = _user()
        resp = _client(user, FakeSession()).patch(
            "/v1/users/me",
            json={"nickname": "새닉"},
            headers={"If-Match": '"deadbeefdeadbeef"'},
        )
        assert resp.status_code == 412

    def test_matching_if_match_succeeds(self) -> None:
        user = _user()
        fake = FakeSession()
        client = _client(user, fake)
        etag = client.get("/v1/users/me").headers["ETag"]
        resp = client.patch(
            "/v1/users/me", json={"nickname": "새닉"}, headers={"If-Match": etag}
        )
        assert resp.status_code == 200

    def test_invalid_value_for_whitelisted_field_422(self) -> None:
        """화이트리스트 필드라도 잘못된 enum 값이면 병합 재검증 422."""
        user = _user()
        resp = _client(user, FakeSession()).patch(
            "/v1/users/me", json={"primary_device": "없는기기"}
        )
        assert resp.status_code == 422

    def test_integrity_conflict_returns_409(self) -> None:
        """commit 단계 IntegrityError → 롤백 후 409."""
        user = _user()
        err = IntegrityError("UPDATE", {}, Exception("duplicate"))
        fake = FakeSession(commit_error=err)
        resp = _client(user, fake).patch("/v1/users/me", json={"nickname": "새닉"})
        assert resp.status_code == 409
        assert fake.rolled_back is True
