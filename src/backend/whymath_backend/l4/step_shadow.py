"""L4 중간 step 등가성 shadow 관측 — 학생 풀이의 단계-비보존을 *로그로만* 진단(비노출·비차단).

`docs/architecture/04_pedagogy_engine.md`: L4는 *결정* 계층. 본 모듈은 L3 결정론 도구
`detect_step_breaks`(slice 62)를 호출해 다단계 풀이의 인접 단계 해집합 비보존을 *관측*한다 —
**student-facing이 아니다**. pedagogy-designer 결론(slice 61): 순차유도 오류(A)와 변수재사용(B)은
정보이론적으로 구문 분리 불가하므로 *단계 위치 지목은 학생에게 금지*. 검출 신호는 노이즈((A)/(B)
미분리)이므로 진단 데이터로만 흡수한다(향후 L7·교사 대시보드·KPI sink; 당장은 로그가 유일 sink).

레이어·shadow 위생: L4는 L3 도구를 *호출*만(검출 로직은 L3 소유). 워커 shadow(slice 43·
`whymath.l3.quality` 로거)·`l3_shadow_validation_enabled` 게이트의 직접 선례를 따른다 —
**비차단**(반환 None·예외 흡수)이라 본류(코칭 결정·반환)를 어떤 경우에도 바꾸지 않는다.
"""

from __future__ import annotations

import logging
import uuid

from whymath_backend.config import get_settings
from whymath_backend.l3.pregenerate.validator import detect_step_breaks

logger = logging.getLogger("whymath.l4.step_shadow")  # 워커 "whymath.l3.quality" 네이밍 동형


def observe_step_breaks(
    solution_text: str,
    *,
    problem_id: uuid.UUID | None = None,
    expected_answer: str | None = None,
) -> None:
    """학생 풀이의 단계-비보존 의심을 *로그로만* 관측(shadow·비차단·비노출). 반환 `None`.

    반환이 `None`이라 호출자가 신호를 받을 변수가 *없다* — student-facing 누출을 구조적으로 차단한다
    (오케스트레이터는 fire-and-forget으로 호출하고 반환을 쓰지 않는다). `l4_step_shadow_enabled`
    게이트 off(기본)면 검출조차 안 돌리고 즉시 반환(비용 0). 예외는 삼킨다 — 관측이 본류(코칭
    결정·반환)를 깨면 안 된다(우선순위: 학생 경험 > 진단 관측).

    `problem_id`·`expected_answer`는 *진단 맥락*(slice 64) — 검출된 break를 *어느 문항·기대정답*에
    귀속시켜 향후 (A)순차유도 오류 vs (B)변수재사용 라벨 정확도를 증거 기반으로 측정하게 한다(결정
    로그 2026-06-06 해금 경로 ①). 둘 다 *서버 로그 sink에만* 흐른다 — 반환은 여전히 `None`이라
    비노출 불변이 보존된다(특히 `expected_answer`는 절대 student-facing이면 안 됨 = 정답 누출).
    `expected_answer`는 *서버 DB 조회*(api 계층)로만 얻고 요청/응답엔 결코 싣지 않는다.
    """
    if not get_settings().l4_step_shadow_enabled:
        return
    try:
        breaks = detect_step_breaks(solution_text)
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(방어선·테스트 커버)
        return
    for b in breaks:
        logger.info(
            "단계 비보존 의심(shadow·비노출) — problem_id=%s expected=%r "
            "var=%s step=%d %s→%s marker=%r",
            problem_id,
            expected_answer,
            b.var,
            b.step_index,
            b.solset_before,
            b.solset_after,
            b.marker,
        )


__all__ = ["observe_step_breaks"]
