"""자기 진화 SFT 데이터셋 export *ops CLI* — 전 문제 verified 풀이 → JSONL(설계 §5·§7.5).

솔버가 적재한 검증 풀이(`verified_solutions`)를 SFT(지도 미세조정) 학습 데이터셋으로 내보낸다.
WH-S 오프라인 업스트림(§7.5)이라 *전역 배치는 HTTP 미노출* — ops 스크립트/cron이 직접 돌린다
(`retention_purge_cli` ops 컨벤션 미러).

흐름: `get_all_verified`(전 문제 verified·R-S2 안전) → `build_sft_dataset`(verified만·재발견 dedup·
정직 회계) → `iter_sft_jsonl`(레코드/줄). 출력 분리:
  - **stdout = JSONL 레코드**(레코드 1개/줄·파이프 가능한 데이터셋·`> dataset.jsonl`).
  - **stderr = 정직 요약 JSON 한 줄**(`{total_input, records, excluded_unverified, deduped}`·ops
    회계 로그·데이터 스트림에 섞지 않음).

사용법:
    python -m whymath_backend.whs.self_evolution_export_cli [--no-dedup] > dataset.jsonl

종료 코드 0(verified 0건도 정상 — 빈 데이터셋). `--no-dedup`은 재발견 중복까지 그대로 내보낸다
(기본은 dedup ON·`(problem_id, 지문)` 중복 제거).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Coroutine
from typing import Any

from whymath_backend.db.session import get_sessionmaker
from whymath_backend.whs.self_evolution import (
    SftDataset,
    build_sft_dataset,
    iter_sft_jsonl,
)
from whymath_backend.whs.solution_bank import get_all_verified

__all__ = ["ExportFn", "main"]

# export 좌석 — dedup 플래그 → SftDataset. 기본은 실 DB(전 문제 verified 조회·변환), 테스트는 합성
# 데이터셋을 주입해 DB 없이 CLI 배선(인자 파싱·JSONL stdout·요약 stderr·종료 코드)을 검증한다.
ExportFn = Callable[[bool], Coroutine[Any, Any, SftDataset]]


async def _default_export_fn(dedup: bool) -> SftDataset:  # pragma: no cover — 실 DB(integration)
    """기본 export — 세션 1개로 전 문제 verified를 조회해 SFT 데이터셋으로 변환한다(읽기 전용).

    `get_all_verified`(verified만·R-S2)→`build_sft_dataset(dedup=dedup)`. 읽기뿐이라 commit 없음.
    """
    async with get_sessionmaker()() as session:
        rows = await get_all_verified(session)
        return build_sft_dataset(rows, dedup=dedup)


def main(argv: list[str] | None = None, *, export_fn: ExportFn = _default_export_fn) -> int:
    """CLI 엔트리 — verified 풀이를 SFT JSONL로 stdout에, 회계 요약을 stderr에 낸다.

    `--no-dedup`(기본 dedup ON). `export_fn`은 테스트 주입 좌석(기본 실 DB). 종료 코드 0
    (verified 0건도 정상 — 빈 데이터셋·요약 total=0).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.whs.self_evolution_export_cli",
        description=(
            "자기 진화 SFT 데이터셋 export — 전 문제 verified 풀이를 JSONL(stdout)로, 회계 요약을 "
            "stderr로(§5·verified만·재발견 dedup)."
        ),
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="재발견 중복(같은 문제·같은 지문)도 그대로 내보냄(기본은 dedup ON).",
    )
    args = parser.parse_args(argv)
    dedup = not args.no_dedup

    dataset: SftDataset = asyncio.run(export_fn(dedup))
    for line in iter_sft_jsonl(dataset):
        print(line)
    summary = {
        "total_input": dataset.total_input,
        "records": dataset.size,
        "excluded_unverified": dataset.excluded_unverified,
        "deduped": dataset.deduped,
    }
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
