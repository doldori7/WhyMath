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
from whymath_backend.api._ocr_state import (
    OcrReachCounters,
    get_ocr_components,
    get_ocr_counters,
)
from whymath_backend.l5.ocr.factory import OcrComponents
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline, run_ocr_pipeline_pages
from whymath_backend.schema.ocr import OcrPagesResult, OcrResult

router = APIRouter(prefix="/v1/ocr", tags=["ocr"])

# 다중 페이지 업로드 상한 — 한 풀이 세션 분량 가드(과도 업로드로 인한 자원·지연 방어). 초과는 422.
# 결정 우선순위 ①학생안전≫⑥비용: 상한은 보수적으로 두되, 일반적 손글씨 풀이(수 페이지)는 충분.
_MAX_OCR_PAGES = 20

# SEC-24(원 SEC-17): 인증 DoS(메모리 고갈) 방어. ConsentedUser 게이트라 무인증은 아니나,
# 인증된(탈취) 계정이 대용량 파일을 반복 업로드하거나 /pages로 페이지 수 상한(20장)까지
# 동시 업로드해 메모리 고갈을 일으킬 수 있다
# (정본: docs/reviews/functional_security_audit_2026-08-08.md M4).
# 페이지 수 캡만으론 단건 대용량·합계 증폭을 막지 못하므로 바이트 상한·MIME
# 허용목록을 추가한다(verify.py의 _MAX_EXPR_LEN 선례 — 캡 상수 중앙화 +
# 초과 시 명확한 4xx).
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 단건 상한 10MB — 결정 우선순위 ①학생안전 보수적 상한(일반
# 손글씨 풀이 사진은 수 MB 이내).
_MAX_PAGES_TOTAL_BYTES = 50 * 1024 * 1024  # /pages 합계 상한 50MB. 개별 상한(10MB)만으로는
# 20장 × 10MB = 200MB까지 열려 20배 증폭을 막지 못한다 — 합계 캡이 진짜 방어선.
_ALLOWED_IMAGE_CONTENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/webp"}
)  # docstring이 PNG/JPEG를 명시하므로 그 축에 webp만 실무 여유로 추가(과도 확장 금지).

# app.state 주입 — Depends로 노출해 테스트가 dependency_overrides로 가짜 부품을 넣을 수 있게
# 한다(scene.py가 get_provider를 직접 호출한 것과 달리, OCR은 부품 묶음 1개라 Depends가 깔끔).
OcrComponentsDep = Annotated[OcrComponents, Depends(get_ocr_components)]
# NLP-01: 도달 카운터 주입 — 핸들러가 정상 완료 시 succeeded를 기록한다(get_ocr_components는
# 요청 도달·503 사유만 세고, 성공은 파이프라인 완료를 아는 핸들러만 정직하게 판단할 수 있다).
OcrCountersDep = Annotated[OcrReachCounters, Depends(get_ocr_counters)]


async def _read_and_validate_image(image: UploadFile, *, max_bytes: int) -> bytes:
    """업로드 이미지 1장을 읽어 MIME·크기를 검증한 뒤 바이트를 반환한다(SEC-24(원 SEC-17)).

    ①content-type이 허용목록(`_ALLOWED_IMAGE_CONTENT_TYPES`)에 없으면(None 포함) 415.
    ②읽은 바이트가 `max_bytes`를 초과하면 413 — 이후 파이프라인에 전달되지 않도록 read() 직후
    즉시 검증한다. 스트리밍 청크 읽기는 하지 않는다(과공학 방지 — UploadFile은
    SpooledTemporaryFile 기반이라 read() 자체가 이미 디스크 스필로 일부 방어하고, 이 저장소의
    기존 관례도 즉시 read()다).

    한계(정직 표기): content_type은 클라이언트가 보낸 헤더를 신뢰한 값이라 위조되면 실제
    바이트와 다를 수 있다 — 매직바이트 검증은 이 태스크 범위 밖이다(OCR 파이프라인이 디코드
    실패 시 RuntimeError로 명확히 보고하는 기존 계약이 이미 이중 방어이고, 매직바이트 검증
    도입은 별건 하드닝).
    """
    if image.content_type not in _ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"지원하지 않는 이미지 형식입니다({image.content_type}). "
                "PNG/JPEG/WEBP만 허용됩니다."
            ),
        )
    data = await image.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"이미지 크기가 너무 큽니다(최대 {max_bytes // (1024 * 1024)}MB).",
        )
    return data


@router.post(
    "",
    response_model=OcrResult,
    summary="손글씨 풀이 이미지 OCR → 구조(OcrResult)",
)
async def post_ocr(
    user: ConsentedUser,
    components: OcrComponentsDep,
    counters: OcrCountersDep,
    image: Annotated[UploadFile, File(description="손글씨 풀이 이미지(PNG/JPEG)")],
) -> OcrResult:
    """업로드 이미지를 OCR 파이프라인으로 인식해 *구조*(`OcrResult`)를 반환한다(순수·코치 미조합).

    인증된(동의 게이트 통과·미성년 학부모 동의) 학생만 호출할 수 있다(`ConsentedUser`). 부품
    (검출기·라우터·인식기)은 app.state에서 주입한다 — OCR 비활성/미로드면 503
    (`get_ocr_components`). 이미지 디코드·모델 의존 미설치는 파이프라인이 명확한 RuntimeError로
    보고한다(조용한 폴백 없음).

    SEC-24(원 SEC-17): 업로드는 `_MAX_IMAGE_BYTES`(10MB) 이하·MIME이 `_ALLOWED_IMAGE_CONTENT_TYPES`
    (PNG/JPEG/WEBP)여야 한다 — 초과·미허용 형식은 각각 413/415(인증 DoS 방어).

    NLP-01: 정상 완료 시 `counters.record_success()`로 도달 관측을 남긴다(`/health/ready`의
    `ocr.succeeded`). 파이프라인이 예외를 던지면(디코드 실패 등) 이 줄에 도달하지 않아
    성공으로 오집계되지 않는다.

    7계층 경계: 여기서 코치(L4)를 부르지 않는다 — 클라이언트가 응답 `OcrResult`를
    `CoachRequest`로 매핑해 `/v1/coach/sessions`에 *별도 호출*한다(2-콜 핸드오프·모듈 docstring).
    """
    image_bytes = await _read_and_validate_image(image, max_bytes=_MAX_IMAGE_BYTES)
    result = await run_ocr_pipeline(image_bytes, components=components)
    counters.record_success()
    return result


@router.post(
    "/pages",
    response_model=OcrPagesResult,
    summary="다중 페이지 손글씨 풀이 이미지 OCR → 구조(OcrPagesResult)",
)
async def post_ocr_pages(
    user: ConsentedUser,
    components: OcrComponentsDep,
    counters: OcrCountersDep,
    images: Annotated[
        list[UploadFile], File(description="손글씨 풀이 이미지들(PNG/JPEG·페이지 순)")
    ],
) -> OcrPagesResult:
    """업로드한 여러 이미지를 페이지별 인식해 *구조*(`OcrPagesResult`)로 반환(순수·코치 미조합).

    단일 `POST /v1/ocr`(하위호환 유지)의 다중 페이지 변형이다 — 각 페이지를 독립 인식해
    업로드(페이지) 순서대로 `pages`에 담고 신뢰도를 롤업한다. 1장 이상·상한
    `_MAX_OCR_PAGES`장까지 허용하며, 0장·초과는 422다. 인증·부품 주입·디코드 정책은
    단일 엔드포인트와 동일하다(`ConsentedUser`·app.state·조용한 폴백 없음).

    SEC-24(원 SEC-17): 각 페이지는 `_MAX_IMAGE_BYTES`(10MB)·MIME 허용목록을 개별 통과해야
    한다(위반 시 413/415). 페이지 수 캡(20장)만으로는 20 × 10MB = 200MB까지 열려 증폭
    방어가 안 되므로, 합계가 `_MAX_PAGES_TOTAL_BYTES`(50MB)를 넘는 순간(마지막
    페이지까지 기다리지 않고) 즉시 413으로 조기 중단한다(인증 DoS 방어).

    NLP-01: FastAPI는 의존성(`components`)을 핸들러 본문보다 먼저 해석하므로 422(장수
    가드)에서도 `get_ocr_components`의 요청 카운터(`requests_total`)는 이미 증가한
    뒤다 — 성공 카운터(`succeeded`)만 파이프라인 완료 시점(본문 마지막)에 남는다.

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
    page_bytes: list[bytes] = []
    total_bytes = 0
    for image in images:
        data = await _read_and_validate_image(image, max_bytes=_MAX_IMAGE_BYTES)
        total_bytes += len(data)
        if total_bytes > _MAX_PAGES_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "전체 이미지 용량이 너무 큽니다"
                    f"(최대 {_MAX_PAGES_TOTAL_BYTES // (1024 * 1024)}MB)."
                ),
            )
        page_bytes.append(data)
    result = await run_ocr_pipeline_pages(page_bytes, components=components)
    counters.record_success()
    return result
