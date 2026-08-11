"""CORS 정책 결정(2026-08-11, SEC-18) 동결 — 코드 변경 0, 현재 상태 자체가 정책.

CORS 정책 결정 원문: 현재 미들웨어 없음 — 학생 클라가 Flutter 네이티브 앱이라 브라우저
CORS가 적용되지 않는다(Origin 헤더·preflight 무관, 네이티브 앱은 브라우저 Same-Origin
정책의 적용 대상이 아니다). 웹 클라(React/Next.js 교사 대시보드·CLAUDE.md Phase 3+)를
추가할 때 이 결정을 재검토한다 — 그때는 `allow_origins`를 명시 화이트리스트로만
설정하고(`*` 금지, 특히 `allow_credentials=True`와 조합 시 브라우저가 요청을 거부하거나
보안 구멍이 된다), 이 테스트를 그 화이트리스트를 동결하는 형태로 갱신한다. 지금 이
테스트가 실패하면(=CORSMiddleware가 조용히 추가됨) 그 갱신 없이 결정이 우회된 것이므로
회귀다.
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from whymath_backend.app import create_app


def _has_cors_middleware(app: FastAPI) -> bool:
    """앱에 CORSMiddleware가 등록됐는지 판별하는 순수 술어.

    `app.user_middleware`(FastAPI/Starlette가 등록 미들웨어를 담는 리스트)를 순회해
    `Middleware.cls`가 `CORSMiddleware`인 항목이 있는지 확인한다.
    """
    return any(m.cls is CORSMiddleware for m in app.user_middleware)


class TestCorsPolicyFreeze:
    def test_current_app_has_no_cors_middleware(self) -> None:
        """현재 결정 동결 — 실 `create_app()`에 CORSMiddleware가 없다."""
        app = create_app()
        assert _has_cors_middleware(app) is False

    def test_predicate_detects_injected_cors_middleware(self) -> None:
        """결함주입 — 합성 앱에 CORSMiddleware를 실제로 붙이면 같은 술어가 검출한다.

        위 테스트가 "항상 통과하는 위장 검사"가 아님을 증명한다(이 저장소 결함주입 관례).
        """
        synthetic_app = FastAPI()
        assert _has_cors_middleware(synthetic_app) is False  # 붙이기 전엔 미검출.
        synthetic_app.add_middleware(CORSMiddleware, allow_origins=["*"])
        assert _has_cors_middleware(synthetic_app) is True  # 붙인 뒤엔 검출.
