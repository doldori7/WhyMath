"""L5 OCR → L4 coach 핸드오프 매핑 — `OcrResult`/`OcrPagesResult` → `CoachRequest`(실행 가능).

`schema/ocr.py` 모듈 docstring의 *매핑 표*(주석)를 **실행 가능한·테스트되는 코드**로 고정한다.
그동안 핸드오프는 docstring 표로만 명시돼 계약이 *조용히 썩을* 위험(예: `CoachRequest` 필드가
바뀌어도 표는 모름)이 있었다 — 이 모듈이 진짜 `CoachRequest` 모델로 빌드하고, E2E 테스트가
`POST /v1/coach`까지 엮어 계약을 못 박는다(`tests/backend/api/test_ocr_handoff.py`).

7계층 경계(중요): 이건 *빌더 함수*지 *오케스트레이터 엔드포인트가 아니다*. 백엔드는 여전히
두 호출(`/v1/ocr` → `/v1/coach`)을 *조합하지 않는다*(OCR 엔드포인트는 순수 인식만). 클라이언트
(또는 상위 오케스트레이션)가 이 헬퍼로 `CoachRequest`를 만들어 *별도로* coach를 호출한다 —
이 함수는 그 매핑의 *정전(canonical) 구현*이라 Flutter 등 클라가 미러링할 기준이 된다.
위치가 `api/`인 이유: `CoachRequest`가 api 레이어 모델이라(스키마가 아님) 매핑은 그 소비처
옆에 둔다(스키마→api 역의존 회피).

매핑 표(단일 페이지 `OcrResult`):
  - `plain_latex`         → `CoachRequest.student_solution`(빈 문자열이면 None=발화 폴백).
  - `overall_confidence`  → `CoachRequest.ocr_confidence`(영역 0이면 None=dormant·게이트 비활성).
  - `solution_steps`      → `CoachRequest.solution_steps`(빈 목록이면 None).
  - `solution_step_types` → `CoachRequest.solution_step_types`(빈 목록이면 None).
`student_input`(대화 발화)은 OCR 산출이 아니라 *별도 인자*다 — 핸드오프 호출자가 제공한다.
"""

from __future__ import annotations

from typing import Any

from whymath_backend.api.coach import CoachRequest
from whymath_backend.schema.ocr import OcrPagesResult, OcrResult


def ocr_result_to_coach_request(
    result: OcrResult,
    *,
    student_input: str,
    **coach_fields: Any,
) -> CoachRequest:
    """단일 페이지 `OcrResult`를 `CoachRequest`로 매핑한다 — **순수**(매핑 표 정전 구현).

    Args:
        result: `/v1/ocr` 산출 구조(한 장).
        student_input: 학생의 *대화 발화*(OCR 산출 아님·호출자 제공). 빈 문자열 허용.
        **coach_fields: 비-OCR coach 필드 패스스루(예: `polya_state`·`mastery_level`·
            `bkt_mastery`·`coaching_focus`). `CoachRequest`(extra=forbid)가 미지 키를 거부한다.

    Returns:
        OCR 착지점이 채워진 `CoachRequest`. 빈 OCR(영역 0)이면 OCR 필드가 모두 None이라
        coach 동작이 *완전 불변*(dormant) — `student_input`만 작동.
    """
    return CoachRequest(
        student_input=student_input,
        student_solution=result.plain_latex or None,
        # 영역이 하나도 없으면 overall_confidence는 0.0인데, 이를 그대로 넘기면 0<0.8로
        # match_low_quality가 *거짓 발동*한다 — OCR이 없을 땐 None(dormant)이 옳다.
        ocr_confidence=result.overall_confidence if result.regions else None,
        solution_steps=result.solution_steps or None,
        solution_step_types=result.solution_step_types or None,
        **coach_fields,
    )


def ocr_pages_to_coach_request(
    pages: OcrPagesResult,
    *,
    student_input: str,
    **coach_fields: Any,
) -> CoachRequest:
    """다중 페이지 `OcrPagesResult`를 단일 `CoachRequest`로 병합 매핑한다 — **순수**.

    `OcrPagesResult`는 *페이지 경계 전이 의미가 모호*해 텍스트를 합치지 않는다(스키마 docstring).
    이 헬퍼가 바로 그 병합(클라가 한다던 것)을 정전 구현한다:
      - `student_solution` = 각 페이지 `plain_latex`를 페이지(업로드) 순서로 줄바꿈 연결.
      - `solution_steps`   = 각 페이지 `solution_steps`를 순서대로 이어붙임.
      - `ocr_confidence`   = `pages.overall_confidence`(전 페이지 모든 영역 평균·영역 0이면 None).
      - `solution_step_types` = **None**(페이지 경계 전이 유형이 모호 — 보수적 미지정).

    Args:
        pages: `/v1/ocr/pages` 산출(다중 페이지).
        student_input: 학생의 대화 발화(호출자 제공).
        **coach_fields: 비-OCR coach 필드 패스스루.

    Returns:
        페이지를 순서대로 이은 `CoachRequest`. 빈 입력(영역 0)이면 OCR 필드 None(dormant).
    """
    combined_solution = "\n".join(p.plain_latex for p in pages.pages if p.plain_latex) or None
    combined_steps: list[str] = []
    for page in pages.pages:
        combined_steps.extend(page.solution_steps)
    has_regions = any(page.regions for page in pages.pages)
    return CoachRequest(
        student_input=student_input,
        student_solution=combined_solution,
        ocr_confidence=pages.overall_confidence if has_regions else None,
        solution_steps=combined_steps or None,
        # 페이지 경계 전이 유형은 모호 — 미지정(None)으로 둔다(verify가 untyped로 보수 처리).
        solution_step_types=None,
        **coach_fields,
    )
