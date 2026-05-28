"""사전생성 결과 → `GenerationLog` 변환 어댑터 (L3 → schema 연결).

설계 정본: `schemas/v1.0/schema_v1.0.md` §10.1 `generation_log`(슬라이스 2 모델).

계층 규칙(7계층 아키텍처, 절대원칙):
  `schema/`(L1 데이터)는 `l3`(L3)를 *import 금지*(역방향 의존 금지). 반대로 `l3 →
  schema`는 허용된다. 따라서 사전생성(`PrewarmItemResult`) 결과를 `GenerationLog`로
  바꾸는 *연결* 코드는 반드시 L3쪽(이 파일)에 둔다. 이렇게 두면 schema 패키지는 l3를
  전혀 모른 채 순수하게 유지된다.

텔레메트리 메모: 현재 `LLMProvider.generate`는 응답 문자열만 반환하고 토큰/비용/지연을
  노출하지 않는다(`prewarmer.py` L111). 따라서 이 어댑터는 그 텔레메트리를 *지어내지
  않고* None으로 둔다. 후속: provider 인터페이스에 usage(토큰/비용/지연)가 추가되면
  여기서 채운다.
"""

from __future__ import annotations

import uuid

from whymath_backend.l3.pregenerate.models import PrewarmItemResult
from whymath_backend.schema.provenance import GenerationLog

# 사전적재 결과 status 중 *유효 시드 확보=성공*으로 간주하는 집합.
# - "written": 새로 검증·적재됨 → 시드 확보.
# - "skipped_exists": 이미 같은 키의 시드가 존재(overwrite=False) → 유효 시드 이미 확보.
# - "failed_validation"/"error": 시드 미확보 → 실패.
_SUCCESS_STATUSES: frozenset[str] = frozenset({"written", "skipped_exists"})


def generation_log_from_result(
    result: PrewarmItemResult,
    *,
    problem_id: uuid.UUID,
    model_name: str,
    provenance_id: uuid.UUID | None = None,
    prompt_template_id: uuid.UUID | None = None,
) -> GenerationLog:
    """사전적재 항목 결과(`PrewarmItemResult`)를 `GenerationLog`로 변환한다(순수 함수).

    매핑:
      - `success`: `result.status ∈ {"written","skipped_exists"}` → True.
        (written/skipped_exists=유효 시드 확보=성공, failed_validation/error=실패)
      - `error_detail`: `result.error`(status별 의미는 `PrewarmItemResult` docstring).
      - `problem_id`/`model_name`/`provenance_id`/`prompt_template_id`: 인자에서 그대로.
      - `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms`: None.
        (현재 provider가 usage를 노출하지 않음 — 지어내지 않는다. 모듈 docstring 참조.)

    이 함수는 *정의만 추가*하는 순수 함수다 — `prewarmer.py`의 prewarm 흐름(런타임)은
    전혀 건드리지 않는다. 호출자가 사전적재 후 감사 로그를 남기고 싶을 때 사용한다.
    """
    return GenerationLog(
        problem_id=problem_id,
        provenance_id=provenance_id,
        model_name=model_name,
        prompt_template_id=prompt_template_id,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        latency_ms=None,
        success=result.status in _SUCCESS_STATUSES,
        error_detail=result.error,
    )
