"""L5 OCR HTTP 표면 — 손글씨 풀이 이미지 → 구조. POST /v1/ocr(단일)·POST /v1/ocr/pages(다중).

7계층 경계(CLAUDE.md): L5(상호작용)는 이미지를 *구조*로 인식해 돌려주는 것까지만 책임진다.
**이 엔드포인트들은 순수**하다 — L4 코치를 *조합하지 않는다*. 클라이언트는 2-콜 핸드오프로
쓴다:
  1. `POST /v1/ocr`            — 단일 이미지 → `OcrResult`(구조: bbox·유형·LaTeX·신뢰도).
     `POST /v1/ocr/pages`      — 여러 이미지(페이지) → `OcrPagesResult`(페이지별 + 신뢰도 롤업).
  2. `POST /v1/coach/sessions` — 위 `OcrResult`를 `CoachRequest`에 매핑(plain_latex→
     student_solution·overall_confidence→ocr_confidence·solution_steps/types→동명 필드)해
     호출. 매핑 표는 `schema/ocr.py` 모듈 docstring·coach.py 무변경.

표현 ≠ 의미: 응답은 화면 문자열이 아니라 *구조*다 — 렌더는 클라이언트 책임.
미성년 풀이 데이터(저장계층 보호 책임): 이미지·인식 결과는 *미성년 개인 학습 데이터*다(평문
장기 저장·외부 공유 금지·CLAUDE.md). 모델·부품은 app.state에서 주입(전역 로드 없음).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._ocr_state import get_ocr_components
from whymath_backend.l5.ocr.factory import OcrComponents
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline, run_ocr_pipeline_pages
from whymath_backend.schema.ocr import OcrPagesResult, OcrResult

router = APIRouter(prefix="/v1/ocr", tags=["ocr"])

# 다중 페이지 업로드 상한 — 한 풀이 세션 분량 가드(과도 업로드로 인한 자원·지연 방어). 초과는 422.
# 결정 우선순위 ①학생안전≫⑥비용: 상한은 보수적으로 두되, 일반적 손글씨 풀이(수 페이지)는 충분.
_MAX_OCR_PAGES = 20

# app.state 주입 — Depends로 노출해 테스트가 dependency_overrides로 가짜 부품을 넣을 수 있게
# 한다(scene.py가 get_provider를 직접 호출한 것과 달리, OCR은 부품 묶음 1개라 Depends가 깔끔).
OcrComponentsDep = Annotated[OcrComponents, Depends(get_ocr_components)]


@router.post(
    "",
    response_model=OcrResult,
    summary="손글씨 풀이 이미지 OCR → 구조(OcrResult)",
)
async def post_ocr(
    user: ConsentedUser,
    components: OcrComponentsDep,
    image: Annotated[UploadFile, File(description="손글씨 풀이 이미지(PNG/JPEG)")],
) -> OcrResult:
    """업로드 이미지를 OCR 파이프라인으로 인식해 *구조*(`OcrResult`)를 반환한다(순수·코치 미조합).

    인증된(동의 게이트 통과·미성년 학부모 동의) 학생만 호출할 수 있다(`ConsentedUser`). 부품
    (검출기·라우터·인식기)은 app.state에서 주입한다 — OCR 비활성/미로드면 503
    (`get_ocr_components`). 이미지 디코드·모델 의존 미설치는 파이프라인이 명확한 RuntimeError로
    보고한다(조용한 폴백 없음).

    7계층 경계: 여기서 코치(L4)를 부르지 않는다 — 클라이언트가 응답 `OcrResult`를
    `CoachRequest`로 매핑해 `/v1/coach/sessions`에 *별도 호출*한다(2-콜 핸드오프·모듈 docstring).
    """
    image_bytes = await image.read()
    return await run_ocr_pipeline(image_bytes, components=components)


@router.post(
    "/pages",
    response_model=OcrPagesResult,
    summary="다중 페이지 손글씨 풀이 이미지 OCR → 구조(OcrPagesResult)",
)
async def post_ocr_pages(
    user: ConsentedUser,
    components: OcrComponentsDep,
    images: Annotated[
        list[UploadFile], File(description="손글씨 풀이 이미지들(PNG/JPEG·페이지 순)")
    ],
) -> OcrPagesResult:
    """업로드한 여러 이미지를 페이지별 인식해 *구조*(`OcrPagesResult`)로 반환(순수·코치 미조합).

    단일 `POST /v1/ocr`(하위호환 유지)의 다중 페이지 변형이다 — 각 페이지를 독립 인식해
    업로드(페이지) 순서대로 `pages`에 담고 신뢰도를 롤업한다. 1장 이상·상한
    `_MAX_OCR_PAGES`장까지 허용하며, 0장·초과는 422다. 인증·부품 주입·디코드 정책은
    단일 엔드포인트와 동일하다(`ConsentedUser`·app.state·조용한 폴백 없음).

    7계층 경계: 여기서도 코치(L4)를 부르지 않는다 — 클라이언트가 `pages`를 페이지 순서로
    이어 `CoachRequest`로 매핑해 `/v1/coach/sessions`에 *별도 호출*한다(2-콜 핸드오프).
    """
    if not images:
        raise HTTPException(status_code=422, detail="이미지가 최소 1장 필요합니다.")
    if len(images) > _MAX_OCR_PAGES:
        raise HTTPException(
            status_code=422,
            detail=f"이미지는 최대 {_MAX_OCR_PAGES}장까지 허용됩니다(받음: {len(images)}).",
        )
    page_bytes = [await image.read() for image in images]
    return await run_ocr_pipeline_pages(page_bytes, components=components)
