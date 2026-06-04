"""시간창(time-window) 쿼리 파라미터 공용 검증 — slice 66 추출.

`GET /v1/devices`(slice 41~45)와 `GET /v1/me/deletions`(slice 66)가 동일한 since/until
시간창 필터를 노출한다. 검증 로직(naive datetime 거부·since>until 거부)을 한 곳으로 모아
두 라우터가 *동일 에러 표면*을 공유한다(메시지·status 코드 분기 방지·slice 55 헬퍼 추출 선례).

원래 `api/devices.py`에 있던 `_validate_tz_aware`·`_validate_time_window`를 그대로 옮기되
docstring만 일반화(created_at → 임의 시각 컬럼).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status


def _validate_tz_aware(value: datetime | None, field_name: str) -> datetime | None:
    """slice 42: naive datetime 거부 — PG의 TZ-aware 시각 컬럼(created_at·deleted_at 등)과
    비교 시 의미 모호.

    클라이언트는 *반드시* timezone 정보 포함 ISO8601 전송(`Z` 또는 `±HH:MM`). 위반 시 422.
    """
    if value is not None and value.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"`{field_name}`은 timezone 정보 포함 ISO8601 형식이 필요합니다 "
                "(예: '2024-01-01T00:00:00Z' 또는 '2024-01-01T09:00:00+09:00'). "
                "naive datetime은 PG의 TZ-aware 시각 컬럼과 비교 시 의미 모호."
            ),
        )
    return value


def _validate_time_window(
    since: datetime | None,
    until: datetime | None,
    since_name: str,
    until_name: str,
) -> None:
    """slice 45: 시간창 일관성 — `since > until`이면 불가능 조합·422.

    빈 결과 자체는 자연스러우나 *클라이언트 버그를 조용히 통과시키지 않기 위해* 명시 거부.
    한쪽만 None이면 검증 skip(단방향 시간창). 둘 다 None이면 적용 0.
    """
    if since is not None and until is not None and since > until:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"`{since_name}`({since.isoformat()})은 "
                f"`{until_name}`({until.isoformat()})보다 이전(또는 같음)이어야 합니다. "
                "since > until은 빈 시간창."
            ),
        )
