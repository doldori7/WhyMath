"""데이터 열람·이동권 엔드포인트(`GET /v1/me/export`) — hermetic(FakeSession·인증 오버라이드).

`export_my_data`의 *엔드포인트 결선*만 검증한다: 인증(401)·정상 경로(200 + data·not_included +
user_id 스코핑)·외부 store 상세는 응답 미노출·ops 로그 가시화. ★실제 ORM 직렬화·실 PG 조회는
`privacy/test_export.py`·통합테스트가 검증한다(중복 0).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _StubSchema:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        return dict(self._payload)


class _StubRow:
    def __init__(
        self,
        payload: dict[str, Any],
        *,
        content: str | None = None,
        content_encrypted: bytes | None = None,
        content_nonce: bytes | None = None,
        image_uri: str | None = None,
        image_uri_encrypted: bytes | None = None,
        image_uri_nonce: bytes | None = None,
        image_analysis: dict[str, Any] | None = None,
        image_analysis_encrypted: bytes | None = None,
        image_analysis_nonce: bytes | None = None,
    ) -> None:
        self._payload = payload
        # 감사상환 #2: export가 dialogue_turns 행에서 봉투 암호화 컬럼을 읽어 노출 직전 복호한다.
        # SEC-01: 이미지 두 축(image_uri·image_analysis)도 같은 시점에 복호되므로 함께 흉내낸다.
        self.content = content
        self.content_encrypted = content_encrypted
        self.content_nonce = content_nonce
        self.image_uri = image_uri
        self.image_uri_encrypted = image_uri_encrypted
        self.image_uri_nonce = image_uri_nonce
        self.image_analysis = image_analysis
        self.image_analysis_encrypted = image_analysis_encrypted
        self.image_analysis_nonce = image_analysis_nonce

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
    """execute(select)별 scalars 큐(15종 + 대화 턴 조인 + profile = 17)를 순서대로 반환."""

    def __init__(self, result_rows: list[list[Any]]) -> None:
        self._queue = list(result_rows)

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self._queue.pop(0) if self._queue else [])


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user

    async def _sess() -> AsyncIterator[_FakeSession]:
        # 15종 카테고리 + 대화 턴 조인(15) + profile(16) = 17 execute. learning_sessions(0)·
        # parental_consents(5)·misconception_evidence(10)·user_behavior_metrics(12)·dialogues(13)·
        # attempt_events(14)·dialogue_turns(15)에 1행씩, 나머지 빈, profile 1행.
        yield _FakeSession(
            [
                [_StubRow({"sid": "s1"})],
                [],
                [],
                [],
                [],  # skill_mastery_history(Phase 2b-2·빈 구간)
                [],
                [_StubRow({"cid": "c1"})],
                [],
                [],
                [],
                [],
                [_StubRow({"link_id": 7})],
                [],
                [_StubRow({"metric": "churn_risk"})],
                [_StubRow({"resolution": "자기풀이"})],
                [_StubRow({"event": "step_submit"})],
                [_StubRow({"content": "x=2?"}, content="x=2?")],
                [_StubRow({"uid": str(_UID)})],
            ]
        )

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession([])

    app.dependency_overrides[get_session] = _sess  # 무토큰 401은 세션 사용 전 발생
    return TestClient(app)


class TestExportMyData:
    def test_returns_user_data_200(self) -> None:
        """200 — user_id 스코핑·data 카테고리·user_profile·not_included 고지."""
        resp = _client().get("/v1/me/export")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"] == str(_UID)
        assert body["data"]["learning_sessions"] == [{"sid": "s1"}]
        assert body["data"]["assessments"] == []
        assert body["data"]["parental_consents"] == [{"cid": "c1"}]  # 증분 2 신규 카테고리
        assert body["data"]["misconception_hypotheses"] == []  # 슬 신규 카테고리(빈)
        assert body["data"]["misconception_evidence"] == [
            {"link_id": 7}
        ]  # 증분 3(student_id 스코핑)
        assert body["data"]["daily_learning_metrics"] == []  # 증분 4 신규(빈)
        assert body["data"]["user_behavior_metrics"] == [{"metric": "churn_risk"}]  # 증분 4 신규
        assert body["data"]["dialogues"] == [{"resolution": "자기풀이"}]  # 증분 5 신규(세션 메타)
        assert body["data"]["attempt_events"] == [{"event": "step_submit"}]  # 증분 7 신규
        # 증분 6 신규(턴 본문) + SEC-01: 이미지 두 축도 복호 표면에 올라 응답에 실린다.
        assert body["data"]["dialogue_turns"] == [
            {"content": "x=2?", "image_uri": None, "image_analysis": None}
        ]
        assert body["user_profile"] == {"uid": str(_UID)}
        assert len(body["not_included"]) >= 1  # 부분 export 정직 고지
        assert "exported_at" in body

    def test_external_store_not_in_response(self) -> None:
        """외부 store 상세(인프라 store명·locator)는 응답에 미노출(정보 누출 0)."""
        body_text = _client().get("/v1/me/export").text
        assert "clickhouse" not in body_text
        assert "locator" not in body_text

    def test_no_token_401(self) -> None:
        """무토큰 → 401(인증 필수·본인 데이터만)."""
        resp = _no_auth_client().get("/v1/me/export")
        assert resp.status_code == 401

    def test_pending_external_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """외부 store 별도 export 필요를 *ops 로그*로 가시화(store명·user_id)."""
        with caplog.at_level(logging.INFO, logger="whymath.api.me"):
            _client().get("/v1/me/export")
        msgs = [r.getMessage() for r in caplog.records]
        assert any("열람·이동권 export" in m and str(_UID) in m for m in msgs)
        assert any("clickhouse" in m for m in msgs)  # ops 로그엔 store명 포함
