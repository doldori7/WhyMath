"""법정대리인 동의 기록 엔드포인트 단위테스트 — POST /v1/users/me/parental-consent (hermetic).

PIPA 만14세 미만 법정대리인 동의 GRANT(docs/legal/pipa_data_matrix.md §3). 인증은
`get_current_user`(동의 게이트 *아님* — 닭-달걀 회피), 신원 확인은 seam(`_default_guardian_
verifier`)을 오버라이드해 검증한다. 핵심 종단 검증: 동의 기록이 `parent_consent_at`을 설정해 그
미성년의 `get_consented_user` 게이트가 *통과*하는 전체 사슬(test_users.py 오버라이드 패턴 답습).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user, get_current_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.consent_grant import (
    GuardianVerificationRequest,
    StubGuardianVerifier,
    VerificationResult,
    _default_guardian_verifier,
)
from whymath_backend.db.models.audit import PrivacyAudit
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_GRANT_PATH = "/v1/users/me/parental-consent"
_TEST_SECRET = "consent-test-secret-key-0123456789abcdef"  # 테스트용 더미(길이만 충족)


def _minor_user(**over: Any) -> UserProfile:
    """동의 *없는* 미성년 사용자(is_minor=True·parent_consent_at=None — 게이트 대상)."""
    data: dict[str, Any] = {
        "persona_primary": Persona.A_일반고고3,
        "nickname": "미성년학생",
        "email_hash": "STUDENT_EMAIL_HASH",
        "is_minor": True,
        "parent_consent_at": None,
    }
    data.update(over)
    return UserProfile.from_schema(UserProfileSchema(**data))


class FakeSession:
    """동의 기록 경로용 — add/merge/commit/rollback 모사 + added 객체 추적.

    merge는 인자를 그대로 반환(test_users.FakeSession 동형). add된 ParentalConsent를 수집해
    테스트가 *무엇이 적재됐는지*(해시·방식·범위) 검사할 수 있게 한다.
    """

    def __init__(self, commit_error: Exception | None = None) -> None:
        self._commit_error = commit_error
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def merge(self, obj: Any) -> Any:
        return obj

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    def added_consents(self) -> list[ParentalConsent]:
        return [o for o in self.added if isinstance(o, ParentalConsent)]

    def added_privacy_audits(self) -> list[PrivacyAudit]:
        """SEC-09: 이번 호출로 적재된 `privacy_audit` 행(동의변경 감사) — added 스캔."""
        return [o for o in self.added if isinstance(o, PrivacyAudit)]


def _client(
    user: UserProfile,
    fake: FakeSession,
    *,
    verifier: Any | None = None,
    grant_enabled: bool = True,
) -> TestClient:
    """앱 + get_current_user/get_session/get_settings 오버라이드(+ 선택적 verifier seam).

    `grant_enabled`로 동의 GRANT 기능 플래그를 토글한다(기본 켬 — 기존 테스트 유지).
    """
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user

    async def _sess() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr(_TEST_SECRET),
        parental_consent_grant_enabled=grant_enabled,
    )
    if verifier is not None:
        app.dependency_overrides[_default_guardian_verifier] = lambda: verifier
    return TestClient(app)


class TestGrantParentalConsent:
    def test_records_consent_and_sets_parent_consent_at(self) -> None:
        """동의 기록 → 201 + ParentalConsent 1행 적재 + user.parent_consent_at 설정."""
        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": "parent@example.com"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["verification_method"] == "stub"
        assert body["consent_scope"] == "service_core"
        assert body["parent_consent_at"] is not None
        # 동의 행 1개 적재.
        consents = fake.added_consents()
        assert len(consents) == 1
        # user_profile.parent_consent_at이 설정됨(게이트 통과 근거) + 커밋.
        assert user.parent_consent_at is not None
        assert fake.committed is True

    def test_disabled_by_default_returns_404(self) -> None:
        """기능 플래그 off면 동의 경로가 막힌다(stub self-consent 우회 방지·prod 기본)."""
        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake, grant_enabled=False).post(
            _GRANT_PATH, json={"guardian_email": "parent@example.com"}
        )
        assert resp.status_code == 404
        assert fake.added_consents() == []  # 동의 미적재
        assert user.parent_consent_at is None  # 게이트 통과 근거 미설정

    def test_consent_then_gate_passes_end_to_end(self) -> None:
        """**종단**: 동의 기록 후 같은 미성년의 ConsentedUser 게이트가 통과한다(구멍 폐쇄).

        동의 전에는 get_consented_user가 403이지만, 엔드포인트가 parent_consent_at을 설정한 뒤엔
        통과해야 한다 — 동의를 *받는* 경로가 게이트를 *실제로* 여는지 확인.
        """
        import asyncio

        user = _minor_user()
        # 사전 조건: 동의 전엔 게이트가 막는다(403).
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_consented_user(user=user))
        assert exc.value.status_code == 403

        # 동의 기록.
        fake = FakeSession()
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": "parent@example.com"})
        assert resp.status_code == 201, resp.text

        # 이제 같은 user 객체로 게이트가 통과(parent_consent_at 설정됨).
        passed = asyncio.run(get_consented_user(user=user))
        assert passed is user

    def test_no_plaintext_guardian_pii_persisted(self) -> None:
        """법정대리인 이메일은 *평문 미저장* — 적재 행엔 sha256 해시만(평문 부재 단언)."""
        import hashlib

        guardian_email = "parent@example.com"
        expected_hash = hashlib.sha256(guardian_email.strip().lower().encode("utf-8")).hexdigest()
        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": guardian_email})
        assert resp.status_code == 201, resp.text
        consent = fake.added_consents()[0]
        # 해시만 저장 — 평문 이메일은 어떤 필드에도 없다.
        assert consent.guardian_email_hash == expected_hash
        assert guardian_email not in (consent.guardian_email_hash or "")
        assert consent.verification_ref is None  # 불투명 참조(PII 아님)·stub은 None
        # 응답에도 평문 PII·해시가 새지 않는다.
        assert guardian_email not in resp.text
        assert expected_hash not in resp.text

    def test_verifier_seam_overridable_with_fake(self) -> None:
        """seam 주입성: 가짜 verifier(method 다름)를 주입하면 그 결과가 레코드에 반영된다."""

        class _FakeVerifier:
            def verify(self, request: GuardianVerificationRequest) -> VerificationResult:
                return VerificationResult(verified=True, method="fake-test", reference="ref-123")

        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake, verifier=_FakeVerifier()).post(
            _GRANT_PATH, json={"guardian_email": "parent@example.com"}
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["verification_method"] == "fake-test"
        consent = fake.added_consents()[0]
        assert consent.verification_method == "fake-test"
        assert consent.verification_ref == "ref-123"

    def test_verifier_failure_blocks_consent_403(self) -> None:
        """신원 확인 미통과(verified=False) → 403 + 동의 미기록·parent_consent_at 미설정."""

        class _FailingVerifier:
            def verify(self, request: GuardianVerificationRequest) -> VerificationResult:
                return VerificationResult(verified=False, method="stub", reference=None)

        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake, verifier=_FailingVerifier()).post(
            _GRANT_PATH, json={"guardian_email": "parent@example.com"}
        )
        assert resp.status_code == 403
        assert fake.added_consents() == []
        assert user.parent_consent_at is None
        assert fake.committed is False

    def test_stub_default_verifier_used_when_not_overridden(self) -> None:
        """오버라이드 없으면 기본 StubGuardianVerifier 사용(method='stub')."""
        user = _minor_user()
        fake = FakeSession()
        # verifier 미주입 → create_app 기본(_default_guardian_verifier = stub).
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": "p@example.com"})
        assert resp.status_code == 201, resp.text
        assert resp.json()["verification_method"] == StubGuardianVerifier.METHOD

    def test_records_privacy_audit_row_same_transaction(self) -> None:
        """SEC-09: 동의 기록 성공 → `privacy_audit` 1행(event_kind=consent_change) 동일 TX 적재."""
        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": "parent@example.com"})
        assert resp.status_code == 201, resp.text
        audits = fake.added_privacy_audits()
        assert len(audits) == 1
        assert audits[0].user_id == user.user_id
        assert audits[0].event_kind == "consent_change"
        assert audits[0].consent_scope == "service_core"
        assert fake.committed is True

    def test_disabled_grant_writes_no_privacy_audit(self) -> None:
        """기능 플래그 off(404)면 동의도 감사도 적재되지 않는다(주행위 실패 시 부작용 0)."""
        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake, grant_enabled=False).post(
            _GRANT_PATH, json={"guardian_email": "parent@example.com"}
        )
        assert resp.status_code == 404
        assert fake.added_privacy_audits() == []

    def test_verifier_failure_writes_no_privacy_audit(self) -> None:
        """신원 확인 미통과(403)면 동의도 감사도 적재되지 않는다."""

        class _FailingVerifier:
            def verify(self, request: GuardianVerificationRequest) -> VerificationResult:
                return VerificationResult(verified=False, method="stub", reference=None)

        user = _minor_user()
        fake = FakeSession()
        resp = _client(user, fake, verifier=_FailingVerifier()).post(
            _GRANT_PATH, json={"guardian_email": "parent@example.com"}
        )
        assert resp.status_code == 403
        assert fake.added_privacy_audits() == []

    def test_idempotent_repeat_grant_keeps_gate_open(self) -> None:
        """멱등성: 이미 동의가 있어도 재호출이 안전(새 행 적재·parent_consent_at 유지·200대)."""
        user = _minor_user()
        fake = FakeSession()
        client = _client(user, fake)
        first = client.post(_GRANT_PATH, json={"guardian_email": "p@example.com"})
        assert first.status_code == 201, first.text
        # 재호출 — append-only로 두 번째 행, parent_consent_at은 여전히 설정.
        second = client.post(_GRANT_PATH, json={"guardian_email": "p@example.com"})
        assert second.status_code == 201, second.text
        assert len(fake.added_consents()) == 2
        assert user.parent_consent_at is not None

    def test_empty_guardian_email_rejected_422(self) -> None:
        """빈 guardian_email → 422(요청 스키마 min_length=1 — 통지 대상 없음)."""
        user = _minor_user()
        resp = _client(user, FakeSession()).post(_GRANT_PATH, json={"guardian_email": ""})
        assert resp.status_code == 422

    def test_unknown_field_rejected_422(self) -> None:
        """알 수 없는 필드 → 422(요청 스키마 extra='forbid')."""
        user = _minor_user()
        resp = _client(user, FakeSession()).post(
            _GRANT_PATH, json={"guardian_email": "p@example.com", "hacker": "x"}
        )
        assert resp.status_code == 422

    def test_integrity_conflict_returns_409(self) -> None:
        """commit 단계 IntegrityError → 롤백 후 409."""
        from sqlalchemy.exc import IntegrityError

        user = _minor_user()
        err = IntegrityError("INSERT", {}, Exception("conflict"))
        fake = FakeSession(commit_error=err)
        resp = _client(user, fake).post(_GRANT_PATH, json={"guardian_email": "p@example.com"})
        assert resp.status_code == 409
        assert fake.rolled_back is True


def test_grant_without_token_returns_401() -> None:
    """토큰 없이 동의 기록 → 401(실제 인증 의존성 결선 확인·게이트가 아닌 get_current_user).

    get_session은 가짜로 오버라이드 — 무토큰 401은 세션 사용 전에 발생(실 엔진 생성 회피·
    test_users.test_me_without_token_returns_401 동형).
    """
    app = create_app()

    async def _sess() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = _sess
    resp = TestClient(app).post(_GRANT_PATH, json={"guardian_email": "p@example.com"})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
