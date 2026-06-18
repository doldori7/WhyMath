"""학습 증거 보존기한 파기 *ops CLI* — `evidence_store.purge_expired` 실행 진입점.

GDPR 데이터 최소화 — `retention_until`이 *경과*한 `evidence_links`(미성년 오개념 진단 증거)를
야간 배치/cron으로 파기한다. `purge_expired`(설계 04a §2.3 자동 파기)는 *함수만* 있고 실행
진입점이 없어 retention이 *집행되지 않았다* — 이 CLI가 그 표면이다(`agreement_gate_cli` ops
컨벤션 미러: 전역 배치는 HTTP 미노출·스크립트가 직접 돌린다).

사용법:
    python -m whymath_backend.privacy.retention_purge_cli [--as-of YYYY-MM-DD]

동작: `retention_until < as_of`(기본 오늘 UTC)인 증거를 *단일 트랜잭션*으로 삭제하고 커밋한 뒤,
파기 행수를 **JSON으로 stdout**에 낸다(`{"as_of": ..., "purged": N}`·머신 파싱·cron 로그). 종료
코드 0(파기 0건도 정상 — 만료분이 없을 뿐). `retention_until=NULL`(무기한)은 파기 대상 아님.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Coroutine
from datetime import UTC, date, datetime
from typing import Any

from whymath_backend.db.session import get_sessionmaker
from whymath_backend.l4.misconception.evidence_store import purge_expired

__all__ = ["PurgeFn", "main"]

# 파기 좌석 — as_of(기준일) → 파기 행수. 기본은 실 DB(단일 TX·커밋), 테스트는 합성 카운트를
# 주입해 DB 없이 CLI 배선(인자 파싱·as_of 해석·JSON 직렬화·종료 코드)을 검증한다.
PurgeFn = Callable[[date], Coroutine[Any, Any, int]]


async def _default_purge_fn(as_of: date) -> int:  # pragma: no cover — 실 DB(integration)
    """기본 파기 — 세션 1개를 열어 `purge_expired`를 돌리고 커밋(만료분 영구 삭제)."""
    async with get_sessionmaker()() as session:
        purged = await purge_expired(session, as_of=as_of)
        await session.commit()
        return purged


def main(argv: list[str] | None = None, *, purge_fn: PurgeFn = _default_purge_fn) -> int:
    """CLI 엔트리 — 만료 증거를 파기하고 `{"as_of","purged"}` JSON을 stdout에 낸다.

    `--as-of`(YYYY-MM-DD) 미지정 시 오늘(UTC). 이 날짜 *이전* 만료분(`retention_until < as_of`)을
    파기한다. `purge_fn`은 테스트 주입 좌석(기본 실 DB). 종료 코드 0(파기 0건도 정상).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.privacy.retention_purge_cli",
        description=(
            "학습 증거 보존기한 파기 — retention_until 경과 evidence_links를 단일 TX로 삭제"
            "(GDPR 데이터 최소화·무기한 보존 금지)."
        ),
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="기준일(YYYY-MM-DD·기본 오늘 UTC). 이 날짜 이전 만료분(retention_until < as_of) 파기.",
    )
    args = parser.parse_args(argv)
    as_of: date = args.as_of if args.as_of is not None else datetime.now(UTC).date()

    purged: int = asyncio.run(purge_fn(as_of))
    print(json.dumps({"as_of": as_of.isoformat(), "purged": purged}))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
