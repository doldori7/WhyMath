"""인메모리 sliding window rate limiter — L4 코치 엔드포인트 사용자당 분당 상한.

**범위(v1)**: 단일 프로세스 인메모리 — 분산/HA 환경에서는 Redis-backed로 교체(후속 인프라
슬라이스). 본 모듈은 *단순한 결정론적 게이트*: `Settings.coach_rate_limit_per_minute`가
0이면 비활성(테스트·개발 편의), 그 외엔 사용자당(=`user_id`별) 직전 60초 슬라이딩 윈도우의
요청 수가 상한 이상이면 **429 Too Many Requests** + `Retry-After: 60` 헤더.

**경계**:
- 키 = `user_id`(인증된 사용자 단위). IP·세션 단위는 후속(미인증 표면 노출 시).
- 시계 = `time.monotonic()`(단조 — DST·NTP 조정 무관). 테스트는 클럭 주입 없이 *낮은 상한*
  으로 검증(요청 수만 차이).
- 동시성 = FastAPI 단일 이벤트 루프 가정(asyncio.Lock 없이 정합 — Python GIL). 멀티프로세스
  배포에서는 Redis로 이관.
- *미성년 PII 정합*: 본 모듈은 user_id(UUID)만 키로 사용, 학생 발화 내용 무접근(`store`엔
  타임스탬프만).
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Annotated

from fastapi import Depends, HTTPException, status

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.config import Settings, get_settings

_WINDOW_SECONDS = 60.0


class _SlidingWindow:
    """사용자별 직전 60초 요청 타임스탬프 deque. 만료 항목은 옆에서 자동 prune."""

    def __init__(self) -> None:
        self._by_user: dict[uuid.UUID, deque[float]] = {}

    def hit(self, user_id: uuid.UUID, *, limit: int, now: float) -> bool:
        """요청을 기록하고 *제한 내*면 True, 초과면 False(요청 미기록)."""
        cutoff = now - _WINDOW_SECONDS
        bucket = self._by_user.setdefault(user_id, deque())
        # 만료 항목 prune(deque 앞)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        """모든 사용자 카운트 초기화 — 테스트 격리용(production 미사용)."""
        self._by_user.clear()


# 모듈 전역 — FastAPI 단일 프로세스 가정. 분산은 Redis-backed 후속.
_STORE = _SlidingWindow()


def reset_store() -> None:
    """테스트 격리용 카운트 리셋. production 미호출."""
    _STORE.reset()


async def rate_limit_user(
    user: ConsentedUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """사용자당 분당 상한 검사. 초과 시 429 + Retry-After: 60.

    `coach_rate_limit_per_minute=0`이면 비활성(테스트·개발). 인증된 사용자에만 적용
    (`ConsentedUser` 의존성 통과 후 — 미성년 동의 게이트와 직렬).
    """
    limit = settings.coach_rate_limit_per_minute
    if limit == 0:
        return
    if not _STORE.hit(user.user_id, limit=limit, now=time.monotonic()):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 너무 많습니다(분당 한도 초과). 잠시 후 다시 시도하세요.",
            headers={"Retry-After": "60"},
        )


RateLimited = Depends(rate_limit_user)
"""의존성 별칭 — coach 엔드포인트에 `_: None = RateLimited` 형태로 부착."""
