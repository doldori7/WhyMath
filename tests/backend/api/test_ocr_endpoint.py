"""POST /v1/ocr 단위테스트 — 인증·부품 주입·구조 응답. (L5 OCR)

라이브 모델·이미지 디코드 없음: dependency_overrides(get_consented_user·get_ocr_components)로
가짜 부품을 주입하고, run_ocr_pipeline을 monkeypatch해 엔드포인트 글루(인증·503·구조 응답)를
hermetic 검증(test_scene_endpoint 미러).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api import ocr as ocr_module
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._ocr_state import get_ocr_components
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.enums import ContentType, Persona
from whymath_backend.schema.ocr import BBox, OcrPagesResult, OcrRegion, OcrResult
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_PATH = "/v1/ocr"
_PAGES_PATH = "/v1/ocr/pages"


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


class _FakeComponents:
    """get_ocr_components 오버라이드용 — 파이프라인 monkeypatch라 내용 무관."""


class _FakeSession:
    """get_session 오버라이드용 빈 스텁 — 401 경로는 세션 사용 전 인증 거부라 충분."""


async def _fake_session() -> AsyncIterator[_FakeSession]:
    """실 get_session(→ get_engine) 대신 주입 — 전역 _engine 생성을 막아 테스트 격리 보존."""
    yield _FakeSession()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _ocr_result() -> OcrResult:
    """구조 응답 검증용 — bbox+type+latex+confidence를 가진 OcrResult."""
    return OcrResult(
        regions=[
            OcrRegion(
                bbox=BBox(x=0, y=0, width=50, height=20),
                content_type=ContentType.수식,
                latex="x = 2",
                confidence=0.9,
                verified=True,
            )
        ],
        plain_latex="x = 2",
        solution_steps=["x = 2"],
        solution_step_types=[],
        markdown="$x = 2$",
        overall_confidence=0.9,
        min_confidence=0.9,
    )


def _client(*, authed: bool = True, components_loaded: bool = True) -> TestClient:
    app = create_app(provider=_StubProvider())
    if authed:
        app.dependency_overrides[get_consented_user] = _user
    if components_loaded:
        app.dependency_overrides[get_ocr_components] = _FakeComponents
    # 인증 미오버라이드(401) 경로에서도 실 get_session(→ get_engine)이 돌지 않도록 가짜 세션 주입.
    # 전역 db.session._engine 오염을 막아 뒤 순서의 db lazy-import 테스트가 깨지지 않게 한다
    # (다른 hermetic api 테스트와 동일 규약).
    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app)


def test_happy_returns_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """이미지 업로드 → 200 + 구조 OcrResult(bbox·type·latex·confidence·단계)."""

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        return _ocr_result()

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    resp = _client().post(_PATH, files={"image": ("solution.png", b"fakebytes", "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    # 응답은 *구조*다(맨문자열 아님) — 영역에 bbox·유형·latex·신뢰도가 있다.
    assert body["plain_latex"] == "x = 2"
    assert body["overall_confidence"] == 0.9
    assert len(body["regions"]) == 1
    region = body["regions"][0]
    assert region["content_type"] == "수식"
    assert region["latex"] == "x = 2"
    assert region["confidence"] == 0.9
    assert region["bbox"] == {"x": 0.0, "y": 0.0, "width": 50.0, "height": 20.0}


def test_unauthenticated_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """토큰 없음 → 401(부품·파이프라인 도달 전)."""

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        return _ocr_result()

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    resp = _client(authed=False).post(_PATH, files={"image": ("s.png", b"x", "image/png")})
    assert resp.status_code == 401


def test_ocr_disabled_503() -> None:
    """OCR 부품 미로드(비활성) → 503(get_ocr_components 기본 동작·오버라이드 안 함)."""
    # components_loaded=False → 오버라이드 없음 → app.state에 키 없음 → 503.
    resp = _client(components_loaded=False).post(
        _PATH, files={"image": ("s.png", b"x", "image/png")}
    )
    assert resp.status_code == 503


def test_missing_file_422() -> None:
    """이미지 파일 누락 → 422(FastAPI 검증)."""
    resp = _client().post(_PATH)
    assert resp.status_code == 422


# ── 다중 페이지(POST /v1/ocr/pages) ──────────────────────────────────────────


def _image_field(name: str) -> tuple[str, tuple[str, bytes, str]]:
    """멀티파트 images 필드 1개(같은 필드명 반복으로 list[UploadFile] 구성)."""
    return ("images", (name, b"fakebytes", "image/png"))


def test_pages_happy_returns_pages_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """여러 이미지 업로드 → 200 + OcrPagesResult(페이지별 + 신뢰도 롤업)."""

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        return OcrPagesResult.from_pages([_ocr_result() for _ in images])

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    resp = _client().post(_PAGES_PATH, files=[_image_field("p1.png"), _image_field("p2.png")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["page_count"] == 2
    assert len(body["pages"]) == 2
    assert body["overall_confidence"] == 0.9
    assert body["needs_reconfirmation"] is False
    # 페이지별 구조가 그대로 담긴다(표현 ≠ 의미).
    assert body["pages"][0]["plain_latex"] == "x = 2"


def test_pages_empty_422() -> None:
    """이미지 0장 → 422(필수 파일 누락·FastAPI 검증)."""
    resp = _client().post(_PAGES_PATH)
    assert resp.status_code == 422


def test_pages_too_many_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """상한(_MAX_OCR_PAGES) 초과 → 422(파이프라인 도달 전 가드)."""

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        raise AssertionError("상한 초과는 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    too_many = [_image_field(f"p{i}.png") for i in range(ocr_module._MAX_OCR_PAGES + 1)]
    resp = _client().post(_PAGES_PATH, files=too_many)
    assert resp.status_code == 422


def test_pages_unauthenticated_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """토큰 없음 → 401(부품·파이프라인 도달 전)."""

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        return OcrPagesResult.from_pages([_ocr_result()])

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    resp = _client(authed=False).post(_PAGES_PATH, files=[_image_field("p1.png")])
    assert resp.status_code == 401


def test_pages_disabled_503() -> None:
    """OCR 부품 미로드(비활성) → 503."""
    resp = _client(components_loaded=False).post(_PAGES_PATH, files=[_image_field("p1.png")])
    assert resp.status_code == 503


# ── SEC-17: 업로드 크기·MIME 상한(인증 DoS 방어) ──────────────────────────────


def _image_field_of_size(
    name: str, size: int, *, content_type: str = "image/png"
) -> tuple[str, tuple[str, bytes, str]]:
    """지정 바이트 크기의 멀티파트 images 필드 1개(경계값·상한 테스트용)."""
    return ("images", (name, b"a" * size, content_type))


def test_oversized_image_413(monkeypatch: pytest.MonkeyPatch) -> None:
    """단건 이미지가 _MAX_IMAGE_BYTES 초과 → 413(detail에 상한 MB 명시)."""

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        raise AssertionError("상한 초과 이미지는 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    oversized = b"a" * (ocr_module._MAX_IMAGE_BYTES + 1)
    resp = _client().post(_PATH, files={"image": ("s.png", oversized, "image/png")})
    assert resp.status_code == 413
    assert "10MB" in resp.json()["detail"]


def test_image_size_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """경계값: 정확히 _MAX_IMAGE_BYTES바이트 = 통과(200)·+1바이트 = 거부(413)."""

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        return _ocr_result()

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    at_limit = b"a" * ocr_module._MAX_IMAGE_BYTES
    resp_ok = _client().post(_PATH, files={"image": ("s.png", at_limit, "image/png")})
    assert resp_ok.status_code == 200

    over_limit = b"a" * (ocr_module._MAX_IMAGE_BYTES + 1)
    resp_over = _client().post(_PATH, files={"image": ("s.png", over_limit, "image/png")})
    assert resp_over.status_code == 413


def test_wrong_mime_type_415(monkeypatch: pytest.MonkeyPatch) -> None:
    """비이미지 MIME(application/pdf) → 415(파이프라인 미도달)."""

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        raise AssertionError("허용되지 않은 MIME은 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    resp = _client().post(_PATH, files={"image": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert resp.status_code == 415


def test_none_content_type_415(monkeypatch: pytest.MonkeyPatch) -> None:
    """content-type 미전송(빈 문자열) → 415.

    TestClient(httpx)는 files 튜플에 content_type을 생략하면 파일 확장자로 자동 추론해
    "image/png" 등을 채워 넣으므로(우회), 명시적으로 빈 문자열("")을 3번째 요소로 넘겨
    "Content-Type: " 빈 헤더를 강제한다 — 이때 UploadFile.content_type은 빈 문자열이 되고,
    이는 허용목록에 없으므로(None과 동일하게) 415로 거부된다.
    """

    async def _fake_pipeline(image_bytes: bytes, *, components: object) -> OcrResult:
        raise AssertionError("content-type 없는 업로드는 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline", _fake_pipeline)
    resp = _client().post(_PATH, files={"image": ("s.png", b"abc", "")})
    assert resp.status_code == 415


def test_pages_individual_oversized_413(monkeypatch: pytest.MonkeyPatch) -> None:
    """페이지 중 1장이 _MAX_IMAGE_BYTES 초과 → 413(어느 페이지인지는 불문)."""

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        raise AssertionError("상한 초과 페이지 포함 시 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    normal = _image_field_of_size("p1.png", 1024)
    oversized = _image_field_of_size("p2.png", ocr_module._MAX_IMAGE_BYTES + 1)
    resp = _client().post(_PAGES_PATH, files=[normal, oversized])
    assert resp.status_code == 413


def test_pages_total_exceeds_413(monkeypatch: pytest.MonkeyPatch) -> None:
    """개별 상한 이내라도 합계가 _MAX_PAGES_TOTAL_BYTES 초과 → 413.

    3MB × 18장 = 54MB > 50MB(_MAX_PAGES_TOTAL_BYTES) — 각 장(3MB)은 개별 상한(10MB) 이내라
    단건 검증은 전부 통과하지만, 누적 합계가 50MB를 넘는 순간(17번째 장에서 17×3MB=51MB로
    초과) 조기 중단되어 413이 되어야 한다(18번째 장은 읽히지 않음 — 파이프라인 미도달로 확인).
    """

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        raise AssertionError("합계 초과는 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    page_size = 3 * 1024 * 1024  # 3MB — 개별 상한(10MB) 이내.
    pages = [_image_field_of_size(f"p{i}.png", page_size) for i in range(18)]
    resp = _client().post(_PAGES_PATH, files=pages)
    assert resp.status_code == 413


def test_pages_wrong_mime_type_415(monkeypatch: pytest.MonkeyPatch) -> None:
    """여러 장 중 1장이 비이미지 MIME → 415."""

    async def _fake_pages(images: list[bytes], *, components: object) -> OcrPagesResult:
        raise AssertionError("허용되지 않은 MIME 포함 시 파이프라인에 도달하지 않아야 한다")

    monkeypatch.setattr(ocr_module, "run_ocr_pipeline_pages", _fake_pages)
    ok_page = _image_field("p1.png")
    bad_page = ("images", ("p2.txt", b"not an image", "text/plain"))
    resp = _client().post(_PAGES_PATH, files=[ok_page, bad_page])
    assert resp.status_code == 415
