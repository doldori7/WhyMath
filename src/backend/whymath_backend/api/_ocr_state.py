"""OCR 부품(`OcrComponents`)을 app.state에 보관·조회 — app.py(저장)와 ocr 라우터(조회) 공유.

`OcrComponents`는 *앱 수명 동안 공유*되는 의존(모델 1회 로드)이라, `_l3_state.py`(provider·
cache·trace)와 동형으로 `create_app`/lifespan이 `app.state`에 저장하고 라우터가
`request.app.state`로 조회한다. 이 모듈로 키·세터·게터를 모아 app.py와 라우터가 *순환 import
없이* 공유한다(라우터가 app.py를 import하면 순환).

OCR 비활성(`ocr_enabled=False`)·미로드 상태에서 `get_ocr_components`는 **503**으로 명확히
보고한다(조용한 폴백 없음·CLAUDE.md 가용성 우선 — 학생에겐 '잠시 후 재시도'가 정직·안전).
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from whymath_backend.l5.ocr.factory import OcrComponents

# app.state 속성 키 — create_app/lifespan(app.py)이 저장하고 아래 getter가 조회(단일 출처).
OCR_COMPONENTS_KEY = "ocr_components"


def set_ocr_components(app_state_holder: object, components: OcrComponents | None) -> None:
    """app(또는 app.state 보유 객체)에 OCR 부품을 저장 — lifespan이 부팅 시 1회 호출.

    `app_state_holder`는 `.state`를 가진 FastAPI 앱이다(타입을 object로 둬 app.py 순환 회피).
    `None`을 저장하면 비활성(getter가 503)으로 표시한다 — `set_device_store(None)` 미러.
    """
    app_state_holder.state.__setattr__(OCR_COMPONENTS_KEY, components)  # type: ignore[attr-defined]


def get_ocr_components(request: Request) -> OcrComponents:
    """요청의 app.state에서 OCR 부품을 꺼낸다 — 비활성/미로드면 503(조용한 폴백 없음).

    OCR이 꺼져 있거나(`ocr_enabled=False`) 부품 적재가 실패했으면 app.state에 키가 없거나
    None이라 503으로 명확히 보고한다(500 스택트레이스 금지 — 가용성 우선·정직).
    """
    components: OcrComponents | None = getattr(request.app.state, OCR_COMPONENTS_KEY, None)
    if components is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR 기능이 현재 비활성이거나 준비되지 않았습니다(잠시 후 재시도).",
        )
    return components
