"""사전생성 결과 → `GenerationLog` 변환 어댑터 (L3 → schema 연결).

설계 정본: `schemas/v1.0/schema_v1.0.md` §10.1 `generation_log`(슬라이스 2 모델).

계층 규칙(7계층 아키텍처, 절대원칙):
  `schema/`(L1 데이터)는 `l3`(L3)를 *import 금지*(역방향 의존 금지). 반대로 `l3 →
  schema`는 허용된다. 따라서 사전생성(`PrewarmItemResult`) 결과를 `GenerationLog`로
  바꾸는 *연결* 코드는 반드시 L3쪽(이 파일)에 둔다. 이렇게 두면 schema 패키지는 l3를
  전혀 모른 채 순수하게 유지된다.

텔레메트리 메모 (S1 게이트 ② 배선): provider `generate`가 `GenerationResult(text,
  usage)`를 반환하게 되어(usage=실측 토큰·지연), `PrewarmItemResult.usage`가 그 실측을
  담는다. 이 어댑터는 usage가 *있을 때만* 토큰·지연을 채우고, 없으면(인제스트 모드·
  usage 미노출 provider) 종전대로 None을 둔다 — *지어내지 않는다*. 비용(cost_usd)은
  호출자가 `router.actual_cost_usd` 등으로 산정해 인자로 준다(이 어댑터는 티어·단가를
  모른 채 순수 변환만 한다).
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
    cost_usd: float | None = None,
) -> GenerationLog:
    """사전적재 항목 결과(`PrewarmItemResult`)를 `GenerationLog`로 변환한다(순수 함수).

    매핑:
      - `success`: `result.status ∈ {"written","skipped_exists"}` → True.
        (written/skipped_exists=유효 시드 확보=성공, failed_validation/error=실패)
      - `error_detail`: `result.error`(status별 의미는 `PrewarmItemResult` docstring).
      - `problem_id`/`model_name`/`provenance_id`/`prompt_template_id`: 인자에서 그대로.
      - `input_tokens`/`output_tokens`/`latency_ms`: `result.usage`(provider 실측)에서.
        usage가 None(인제스트 모드·usage 미노출)이면 종전대로 None — 지어내지 않는다.
        latency는 float(ms) 실측을 스키마 계약(int)에 맞춰 반올림한다.
      - `cost_usd`: 인자에서 그대로(호출자가 `router.actual_cost_usd`로 산정 — 로컬
        사전생성=0.0, 미상=None). 이 어댑터는 단가를 모른다(순수 변환).

    이 함수는 *정의만 추가*하는 순수 함수다 — `prewarmer.py`의 prewarm 흐름(런타임)은
    전혀 건드리지 않는다. 호출자가 사전적재 후 감사 로그를 남기고 싶을 때 사용한다.
    """
    usage = result.usage
    latency_ms: int | None = None
    if usage is not None and usage.latency_ms is not None:
        # 실측은 float(ms), 스키마는 int(ms) — 반올림(음수 방어는 스키마 ge=0이 담당).
        latency_ms = int(round(usage.latency_ms))
    return GenerationLog(
        problem_id=problem_id,
        provenance_id=provenance_id,
        model_name=model_name,
        prompt_template_id=prompt_template_id,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        success=result.status in _SUCCESS_STATUSES,
        error_detail=result.error,
    )
