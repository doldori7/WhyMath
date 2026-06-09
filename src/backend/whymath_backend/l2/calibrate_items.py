"""문항 난이도 보정 배치 CLI — 채점 응답 전수 → JMLE 보정 → Problem.irt_difficulty_b 영속.

slice 80: 슬라이스 79의 `calibrate_item_difficulties`(L2)를 *운영에서 실제 실행*하는 진입점.
이 명령이 없으면 `irt_difficulty_b`는 전량 NULL로 남아 보정이 휴면한다(θ 추정이 휴리스틱 폴백).
ops가 cron·k8s CronJob으로 주기 실행한다(예: 매일 02:00). 살아있는 PostgreSQL 필요.

사용법:
    python -m whymath_backend.l2.calibrate_items

종료 코드 0(성공). 보정한 문항 수를 stdout 1줄(`calibrated_items=N`)로 리포트한다.
스케줄은 *외부*(cron/CronJob) 책임 — 이 명령은 1회 실행한다(Celery beat·워커 불요,
단일 동시성 QUALITY GPU 워커와 무경합). 증분 적합·`--since` 등은 후속.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from whymath_backend.config import get_settings
from whymath_backend.db.session import dispose_engine, get_sessionmaker
from whymath_backend.l2.item_calibration import calibrate_item_difficulties


async def _run() -> int:
    """세션 1개로 보정 배치 실행 → 보정 수 리포트 → 엔진 정리. 종료 코드 반환.

    `calibrate_item_difficulties`가 채점 응답 전수를 JMLE 적합해 `Problem.irt_difficulty_b`를
    갱신하고 commit한다(내부 수행). 배치 1회 실행이므로 끝에 엔진 풀을 비워 프로세스를 깔끔히
    내린다(`dispose_engine`).
    """
    sessionmaker = get_sessionmaker(get_settings())
    try:
        async with sessionmaker() as session:
            calibrated = await calibrate_item_difficulties(session)
    finally:
        await dispose_engine()
    print(f"calibrated_items={calibrated}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리. 종료 코드 0(성공). cron/CronJob에서 주기 호출."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l2.calibrate_items",
        description=(
            "문항 난이도 b 보정 배치 — 채점 응답 전수 JMLE 적합 → "
            "Problem.irt_difficulty_b 영속(슬라이스 79 calibrate_item_difficulties 실행)."
        ),
    )
    parser.parse_args(argv)  # 현재 인자 없음(향후 --since 등 증분 적합 여지)
    return asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())
