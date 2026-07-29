"""OCR → coach 핸드오프 매핑·E2E 테스트 — `api/ocr_handoff.py`(L5 OcrResult → L4 CoachRequest).

두 층위:
  1. **매핑 단위**(순수): `ocr_result_to_coach_request`·`ocr_pages_to_coach_request`가 매핑 표
     (plain_latex→student_solution·overall_confidence→ocr_confidence·steps/types)대로 빌드하고,
     빈 OCR은 dormant(전 OCR 필드 None·기존 동작 불변)임을 못 박는다.
  2. **E2E**: 매핑한 `CoachRequest`를 실제 `POST /v1/coach`로 보내 핸드오프가 끝까지 동작함을
     증명한다 — 특히 저신뢰 OCR(<0.8)이 `match_low_quality`(재확인 신호)로 표면화되는 경로.

hermetic: DB 무접근(_FakeSession)·인증/한도 dependency_overrides(test_coach 미러).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.api.coach import CoachRequest
from whymath_backend.api.ocr_handoff import (
    ocr_pages_to_coach_request,
    ocr_result_to_coach_request,
)
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import ContentType, Persona, StepType
from whymath_backend.schema.ocr import BBox, OcrPagesResult, OcrRegion, OcrResult
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _ocr_result(*, steps: list[str], conf: float, plain: str | None = None) -> OcrResult:
    """균일 신뢰도 `conf`의 수식 단계들로 `OcrResult`를 만든다(검증 규약 만족·테스트용)."""
    regions = [
        OcrRegion(
            bbox=BBox(x=0, y=float(i * 30), width=50, height=20),
            content_type=ContentType.수식,
            latex=s,
            confidence=conf,
            verified=True,
        )
        for i, s in enumerate(steps)
    ]
    return OcrResult(
        regions=regions,
        plain_latex=plain if plain is not None else " ".join(steps),
        solution_steps=list(steps),
        # 전이 수 = max(len-1, 0) — OcrResult 검증 규약을 만족한다.
        solution_step_types=[StepType.계산] * max(len(steps) - 1, 0),
        markdown="",
        overall_confidence=conf,
        min_confidence=conf,
    )


# ── 1. 매핑 단위(순수) ────────────────────────────────────────────────────────


def test_single_page_maps_ocr_fields() -> None:
    """단일 페이지 — 매핑 표대로 student_solution·ocr_confidence·steps·types를 채운다."""
    result = _ocr_result(steps=["x = 1", "y = 2"], conf=0.9)
    req = ocr_result_to_coach_request(result, student_input="이게 맞나요?")
    assert isinstance(req, CoachRequest)
    assert req.student_input == "이게 맞나요?"  # OCR 산출 아님(별도 인자)
    assert req.student_solution == "x = 1 y = 2"
    assert req.ocr_confidence == 0.9
    assert req.solution_steps == ["x = 1", "y = 2"]
    assert req.solution_step_types == [StepType.계산]


def test_empty_ocr_is_dormant() -> None:
    """빈 OCR(영역 0) — 전 OCR 필드 None(dormant)이라 coach 기존 동작 불변."""
    req = ocr_result_to_coach_request(OcrResult(), student_input="음")
    assert req.student_solution is None
    assert req.ocr_confidence is None  # 0.0을 넘기면 match_low_quality 거짓 발동 → None이 옳다
    assert req.solution_steps is None
    assert req.solution_step_types is None


def test_low_confidence_carried_and_single_step_has_no_types() -> None:
    """저신뢰는 그대로 ocr_confidence로 운반·단계 1개면 전이 유형은 None(빈→None)."""
    req = ocr_result_to_coach_request(_ocr_result(steps=["x = 1"], conf=0.5), student_input="확인")
    assert req.ocr_confidence == 0.5
    assert req.solution_steps == ["x = 1"]
    assert req.solution_step_types is None


def test_coach_fields_passthrough() -> None:
    """비-OCR coach 필드(bkt_mastery 등)는 패스스루된다."""
    req = ocr_result_to_coach_request(
        _ocr_result(steps=["x = 1"], conf=0.9), student_input="음", bkt_mastery=0.9
    )
    assert req.bkt_mastery == 0.9


def test_multipage_merges_pages_in_order() -> None:
    """다중 페이지 — plain_latex 줄바꿈 연결·steps 순서 이어붙임·types는 None(경계 모호)."""
    page1 = _ocr_result(steps=["a = 1"], conf=0.9)
    page2 = _ocr_result(steps=["b = 2"], conf=0.7)
    pages = OcrPagesResult.from_pages([page1, page2])
    req = ocr_pages_to_coach_request(pages, student_input="두 장이에요")
    assert req.student_solution == "a = 1\nb = 2"
    assert req.solution_steps == ["a = 1", "b = 2"]
    assert req.solution_step_types is None
    # 전 페이지 모든 영역 평균 = mean(0.9, 0.7) = 0.8
    assert req.ocr_confidence is not None
    assert abs(req.ocr_confidence - 0.8) < 1e-9


def test_multipage_empty_is_dormant() -> None:
    """빈 다중 페이지 — OCR 필드 None(dormant)."""
    req = ocr_pages_to_coach_request(OcrPagesResult.from_pages([]), student_input="음")
    assert req.student_solution is None
    assert req.ocr_confidence is None
    assert req.solution_steps is None


# ── 2. E2E (POST /v1/coach) ───────────────────────────────────────────────────


def _settings() -> Settings:
    """한도 0(비활성)·테스트 secret — test_coach `_settings_override` 미러."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
        coach_device_hmac_secret=SecretStr(""),
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """`/v1/coach`(stateless)용 — DB 호출 시 AssertionError."""

    async def execute(self, stmt: object) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach 미러)."""
    import asyncio

    asyncio.run(reset_store())


def _post(req: CoachRequest) -> dict[str, object]:
    """매핑한 CoachRequest를 /v1/coach로 보내고 JSON 응답을 돌려준다."""
    resp = _client().post("/v1/coach", json=req.model_dump(mode="json", exclude_none=True))
    assert resp.status_code == 200, resp.text
    body: dict[str, object] = resp.json()
    return body


def test_e2e_high_confidence_no_low_quality_flag() -> None:
    """고신뢰 OCR(≥0.8) 핸드오프 — match_low_quality False(재확인 불필요)."""
    req = ocr_result_to_coach_request(
        _ocr_result(steps=["x = 1", "y = 2"], conf=0.9), student_input="이렇게 풀었어요"
    )
    body = _post(req)
    assert body["match_low_quality"] is False


def test_e2e_low_confidence_surfaces_reconfirmation_gate() -> None:
    """저신뢰 OCR(<0.8) 핸드오프 — match_low_quality True(재확인 신호가 끝까지 전달)."""
    req = ocr_result_to_coach_request(
        _ocr_result(steps=["x = 1"], conf=0.5), student_input="이렇게 풀었어요"
    )
    body = _post(req)
    assert body["match_low_quality"] is True


def test_e2e_multipage_low_confidence_gate() -> None:
    """다중 페이지 평균<0.8이면 재확인 게이트가 끝까지 발동한다(병합 핸드오프 E2E)."""
    pages = OcrPagesResult.from_pages(
        [_ocr_result(steps=["a = 1"], conf=0.9), _ocr_result(steps=["b = 2"], conf=0.5)]
    )  # mean(0.9, 0.5) = 0.7 < 0.8
    req = ocr_pages_to_coach_request(pages, student_input="두 장 풀었어요")
    body = _post(req)
    assert body["match_low_quality"] is True
