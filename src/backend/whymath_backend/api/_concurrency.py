"""HTTP 낙관적 동시성 헬퍼 — content-hash 강한 ETag + If-Match 전제조건(RFC 7232).

라우터의 PATCH/DELETE가 last-write-wins로 동시 편집을 덮지 않도록, 행 표현의 해시를 ETag로
노출하고 `If-Match`로 조건부 변경을 강제한다. `updated_at` 컬럼/마이그레이션 없이 라우터
계층만으로 구현 — ETag가 *행 내용의 함수*라 내용이 바뀌면 ETag도 바뀐다.

클라이언트는 ETag를 *불투명 토큰*으로만 다룬다(GET에서 받아 If-Match로 되돌려 보냄). 서버가
GET·PATCH에서 동일한 `etag_for`로 계산하기만 하면 동시성 판정이 정확하다.
"""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, status
from pydantic import BaseModel


def etag_for(model: BaseModel) -> str:
    """행 표현(Pydantic)의 결정론적 강한 ETag(따옴표 포함). 내용이 바뀌면 ETag도 바뀐다.

    `model_dump_json()`은 필드 정의 순서가 안정적이라 결정론적이다. sha256 앞 16자리를 쓴다
    (충돌 무시 가능, ETag 길이 절약).
    """
    digest = hashlib.sha256(model.model_dump_json().encode("utf-8")).hexdigest()
    return f'"{digest[:16]}"'


def matches_if_none_match(if_none_match: str | None, current_etag: str) -> bool:
    """If-None-Match가 현재 ETag와 매칭되면 True → 호출부가 304 Not Modified를 돌려준다.

    조건부 GET(캐싱) 용도. `None`이면 조건 없음(False). `"*"`면 리소스 존재 시 매칭(True).
    쉼표로 구분된 ETag 목록 중 하나라도 현재 ETag와 같으면 True.
    """
    if if_none_match is None:
        return False
    tokens = [token.strip() for token in if_none_match.split(",")]
    return "*" in tokens or current_etag in tokens


def ensure_if_match(if_match: str | None, current_etag: str) -> None:
    """If-Match 전제조건 검사 — 불일치면 412 Precondition Failed.

    - `None`: 전제조건 없음 → 통과(무조건 진행 — 비파괴, 기존 클라이언트 호환).
    - `"*"`: 리소스 존재 시 매칭(호출부가 이미 404를 처리한 뒤 부른다).
    - 그 외: 정규화 비교 후 불일치면 412(그사이 변경됨 → 최신 재조회 유도).
    """
    if if_match is None:
        return
    candidate = if_match.strip()
    if candidate == "*" or candidate == current_etag:
        return
    raise HTTPException(
        status_code=status.HTTP_412_PRECONDITION_FAILED,
        detail="리소스가 그사이 변경되었습니다(If-Match 불일치). 최신 상태를 다시 읽으세요.",
    )
