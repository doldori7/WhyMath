"""보존기한 파기 *ops CLI* — 증거(`evidence_links`) + 학습 활동 PII 시계열을 함께 파기.

GDPR 데이터 최소화 — 보존기한 *경과* 데이터를 야간 배치/cron으로 파기한다. 두 경로를 한 번에:
  ① `evidence_store.purge_expired`(증거 그래프·`retention_until < as_of`).
  ② `privacy.retention.purge_expired_records`(대화·세션·시도·평가·시계열 지표·타임스탬프 <
     `as_of − pii_retention_years`).
둘 다 *실행 진입점*이 없어 retention이 집행되지 않았다 — 이 CLI가 그 표면이다(`agreement_gate_cli`
ops 컨벤션 미러: 전역 배치는 HTTP 미노출·스크립트가 직접 돌린다).

사용법:
    python -m whymath_backend.privacy.retention_purge_cli [--as-of YYYY-MM-DD]

동작: 경과분을 *단일 트랜잭션*으로 삭제·커밋하고, **테이블별 파기 행수를 JSON으로 stdout**에
낸다(`{"as_of": ..., "purged": {table: n, ...}, "total": N}`·머신 파싱·cron 로그). 종료 코드
0(파기 0건도 정상). NULL 타임스탬프/`retention_until=NULL`(무기한)은 파기 대상 아님(보수적).
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
from whymath_backend.privacy.retention import purge_expired_records

__all__ = ["PurgeFn", "main"]

# 파기 좌석 — as_of(기준일) → {table: 파기 행수}. 기본은 실 DB(단일 TX·커밋), 테스트는 합성
# 카운트를 주입해 DB 없이 CLI 배선(인자 파싱·as_of 해석·JSON 직렬화·종료 코드)을 검증한다.
PurgeFn = Callable[[date], Coroutine[Any, Any, dict[str, int]]]


async def _default_purge_fn(as_of: date) -> dict[str, int]:  # pragma: no cover — 실 DB(integration)
    """기본 파기 — 세션 1개로 증거(`purge_expired`)+PII 시계열(`purge_expired_records`)을 파기·커밋.

    같은 트랜잭션이라 어느 단계 실패도 전부 롤백(부분 파기 0). 반환은 테이블별 파기 행수
    (evidence_links 포함)·커밋은 여기서 한다(ops 배치 1회 실행).
    """
    async with get_sessionmaker()() as session:
        counts: dict[str, int] = {"evidence_links": await purge_expired(session, as_of=as_of)}
        counts.update(await purge_expired_records(session, as_of=as_of))
        await session.commit()
        return counts


def main(argv: list[str] | None = None, *, purge_fn: PurgeFn = _default_purge_fn) -> int:
    """CLI 엔트리 — 만료 데이터를 파기하고 `{as_of, purged{table:n}, total}` JSON을 stdout에 낸다.

    `--as-of`(YYYY-MM-DD) 미지정 시 오늘(UTC). `purge_fn`은 테스트 주입 좌석(기본 실 DB).
    종료 코드 0(파기 0건도 정상 — 만료분이 없을 뿐).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.privacy.retention_purge_cli",
        description=(
            "보존기한 파기 — 증거(retention_until)+학습 활동 PII 시계열(타임스탬프 경과)을 단일 "
            "TX로 삭제(GDPR 데이터 최소화·무기한 보존 금지)."
        ),
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="기준일(YYYY-MM-DD·기본 오늘 UTC). 이 날짜 이전 만료분 파기.",
    )
    args = parser.parse_args(argv)
    as_of: date = args.as_of if args.as_of is not None else datetime.now(UTC).date()

    purged: dict[str, int] = asyncio.run(purge_fn(as_of))
    print(json.dumps({"as_of": as_of.isoformat(), "purged": purged, "total": sum(purged.values())}))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
