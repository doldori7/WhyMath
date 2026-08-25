"""AI training 동의가 /v1/generate에 올바르게 배선되는 통합 단위테스트.

EOS §48·§50의 핵심 요구: AI inference(서비스 제공)와 AI training(모델 개선)을 분리하고,
/v1/generate 호출 시 `ConsentScope.ai_training` 동의 여부를 판정해 Langfuse trace 메타데이터로
전달해야 한다. 본 테스트는 HTTP 엔드포인트 수준에서 그 배선을 검증한다.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from whymath_backend.api._auth import get_current_user
from whymath_backend.app import create_app
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l3.providers.ollama import OllamaStatus


class _StubProvider:
    """Ollama 상태 보고 + 텍스트 생성 스텁."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult(text="stub-output")

    async def check_status(self) -> OllamaStatus:
        return OllamaStatus(reachable=True, models=())


class _FakeSession:
    """/v1/generate PEP 판정용 가짜 세션 — 동의 원장 1건 반환(user·scope 일치 확인)."""

    def __init__(
        self,
        user: UserProfile,
        consent: ParentalConsent | None = None,
    ) -> None:
        self._user = user
        self._consent = consent

    async def get(self, model: Any, pk: uuid.UUID) -> UserProfile | None:
        return None

    async def scalar(self, stmt: Any) -> ParentalConsent | None:
        compiled = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        match = re.search(r"consent_scope = '([^']+)'", compiled)
        expected_scope = match.group(1) if match else None
        if self._consent is None:
            return None
        if self._consent.user_id != self._user.user_id:
            return None
        if expected_scope is not None and self._consent.consent_scope != expected_scope:
            return None
        return self._consent


async def _fake_session(
    user: UserProfile,
    consent: ParentalConsent | None = None,
) -> AsyncIterator[_FakeSession]:
    yield _FakeSession(user, consent)


def _minor_user(*, training_consent: bool = False) -> UserProfile:
    user = UserProfile(
        user_id=uuid.uuid4(),
        is_minor=True,
        parent_consent_at=datetime.now(tz=timezone.utc),
    )
    if not training_consent:
        return user
    return user


def _consent(scope: str, user_id: uuid.UUID) -> ParentalConsent:
    return ParentalConsent(
        consent_id=uuid.uuid4(),
        user_id=user_id,
        consent_scope=scope,
        consent_signed_at=datetime.now(tz=timezone.utc),
    )


def _client(
    user: UserProfile,
    consent: ParentalConsent | None = None,
) -> tuple[TestClient, RecordingTraceSink]:
    trace = RecordingTraceSink()
    app = create_app(
        provider=_StubProvider(),
        cache=InMemoryCache(),
        trace=trace,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession(user, consent)

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), trace


def _payload() -> dict[str, Any]:
    return {
        "request": {
            "task_type": "explain",
            "difficulty": "easy",
            "requires_reasoning": False,
            "student_subscription": "free",
            "sync": True,
        },
        "prompt": "이차방정식이 뭐야?",
        "system": "너는 수학 코치다",
    }


class TestAiTrainingConsentGate:
    def test_minor_without_ai_training_consent_records_false(self) -> None:
        """미성년자가 ai_training 동의가 없으면 /v1/generate trace에 training_allowed=False."""
        user = _minor_user(training_consent=False)
        # service_core 동의만 있고 ai_training 동의는 없는 상황.
        client, trace = _client(user, consent=_consent("service_core", user.user_id))
        resp = client.post("/v1/generate", json=_payload())
        assert resp.status_code == 200, resp.text
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is False

    def test_minor_with_ai_training_consent_records_true(self) -> None:
        """미성년자가 ai_training 동의가 있으면 /v1/generate trace에 training_allowed=True."""
        user = _minor_user(training_consent=True)
        client, trace = _client(user, consent=_consent("ai_training", user.user_id))
        resp = client.post("/v1/generate", json=_payload())
        assert resp.status_code == 200, resp.text
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is True

    def test_adult_records_false_by_default(self) -> None:
        """성인은 별도 성인 동의 저장소가 없어 /v1/generate trace에 training_allowed=False."""
        user = UserProfile(
            user_id=uuid.uuid4(), is_minor=False, parent_consent_at=datetime.now(tz=timezone.utc)
        )
        client, trace = _client(user)
        resp = client.post("/v1/generate", json=_payload())
        assert resp.status_code == 200, resp.text
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is False
