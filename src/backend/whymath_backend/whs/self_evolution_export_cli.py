"""자기 진화 SFT 데이터셋 export *ops CLI* — 전 문제 verified 풀이 → JSONL(설계 §5·§7.5).

솔버가 적재한 검증 풀이(`verified_solutions`)를 SFT(지도 미세조정) 학습 데이터셋으로 내보낸다.
WH-S 오프라인 업스트림(§7.5)이라 *전역 배치는 HTTP 미노출* — ops 스크립트/cron이 직접 돌린다
(`retention_purge_cli` ops 컨벤션 미러).

흐름(일괄·기본): `get_all_verified`(전 문제 verified·R-S2 안전) → `build_sft_dataset`(verified만·
재발견 dedup·정직 회계) → `iter_sft_jsonl`(레코드/줄). 출력 분리:
  - **stdout = JSONL 레코드**(레코드 1개/줄·파이프 가능한 데이터셋·`> dataset.jsonl`).
  - **stderr = 정직 요약 JSON 한 줄**(`{total_input, records, excluded_unverified, deduped}`·ops
    회계 로그·데이터 스트림에 섞지 않음).

흐름(`--stream`·옵트인·대규모 메모리 가드): `stream_all_verified`(서버측 커서·1건씩) →
`stream_sft_jsonl`(verified 필터·dedup·직렬화를 스트리밍·`SftStreamAccounting`에 누적) → 소진 후
`accounting.summary()`. 출력 분리는 동일(stdout JSONL·stderr 요약). 전량 list 미적재라 검증 풀이가
수만~수십만이어도 메모리를 행 1건 + dedup 키셋으로만 바운드한다. 일괄 경로는 그대로 남는다.

사용법:
    python -m whymath_backend.whs.self_evolution_export_cli [--no-dedup] > dataset.jsonl
    python -m whymath_backend.whs.self_evolution_export_cli --stream [--no-dedup] > dataset.jsonl

종료 코드 0(verified 0건도 정상 — 빈 데이터셋). `--no-dedup`은 재발견 중복까지 그대로 내보낸다
(기본은 dedup ON·`(problem_id, 지문)` 중복 제거·일괄·스트리밍 양쪽 동일). `--stream`은 출력은 같되
전량 적재 없이 흘린다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any

from sqlalchemy import select

from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.verified_solution import VerifiedSolution
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.whs.self_evolution import (
    SftDataset,
    SftStreamAccounting,
    build_sft_dataset,
    iter_sft_jsonl,
    stream_sft_jsonl,
)
from whymath_backend.whs.solution_bank import get_all_verified, stream_all_verified

__all__ = ["ExportFn", "ProblemLoader", "StreamFn", "main"]

# export 좌석 — (dedup, with_problem) → SftDataset. 기본은 실 DB(전 문제 verified 조회·변환·문제
# 조인), 테스트는 합성 데이터셋을 주입해 DB 없이 CLI 배선(인자 파싱·JSONL stdout·요약 stderr·종료
# 코드)을 검증한다.
ExportFn = Callable[[bool, bool], Coroutine[Any, Any, SftDataset]]

# stream 좌석 — 검증 풀이를 1건씩 흘리는 async 이터레이터 팩토리. 기본은 실 DB(서버측 커서),
# 테스트는 고정 행 async generator를 주입해 DB 없이 스트리밍 CLI 배선을 검증한다.
StreamFn = Callable[[], AsyncIterator[VerifiedSolution]]

# 문제 조인 좌석 — problem_id → Problem|None(async). 기본은 실 DB(문제별 별도 세션·커서 인터리브
# 회피), 테스트는 고정 dict 가짜 loader를 주입해 DB 없이 조인 배선을 검증한다.
ProblemLoader = Callable[[uuid.UUID], Awaitable[Problem | None]]


async def _default_export_fn(
    dedup: bool, with_problem: bool
) -> SftDataset:  # pragma: no cover — 실 DB(integration)
    """기본 export — 세션 1개로 전 문제 verified를 조회해 SFT 데이터셋으로 변환한다(읽기 전용).

    `get_all_verified`(verified만·R-S2)→`build_sft_dataset`. `with_problem`이면 verified의
    problem_id를 모아 `select(Problem).where(problem_id.in_(...))` IN-일괄로 코퍼스를 조회해
    `problem_map`을 만들고 컨텍스트를 결합한다(미존재는 NO_DATA·problems_missing). 읽기뿐이라
    commit 없음.
    """
    async with get_sessionmaker()() as session:
        rows = await get_all_verified(session)
        problem_map: dict[uuid.UUID, Problem] | None = None
        if with_problem:
            ids = {row.problem_id for row in rows}
            result = await session.execute(select(Problem).where(Problem.problem_id.in_(ids)))
            problem_map = {problem.problem_id: problem for problem in result.scalars().all()}
        return build_sft_dataset(rows, dedup=dedup, problem_map=problem_map)


async def _default_stream_fn() -> AsyncIterator[VerifiedSolution]:  # pragma: no cover — 실 DB
    """기본 stream — 세션 1개로 전 문제 verified를 서버측 커서로 1건씩 흘린다(읽기 전용).

    `stream_all_verified`(verified만·R-S2·전량 적재 없음). 세션은 스트림이 소진될 때까지
    `async with`로 살려둔다. 읽기뿐이라 commit 없음(integration 테스트가 실 PG 거동 검증).
    """
    async with get_sessionmaker()() as session:
        async for solution in stream_all_verified(session):
            yield solution


async def _default_problem_loader(
    problem_id: uuid.UUID,
) -> Problem | None:  # pragma: no cover — 실 DB
    """기본 문제 loader — problem_id로 코퍼스 단건 조회(읽기 전용·문제별 *별도 세션*).

    스트림 커서 세션과 분리된 세션을 *호출마다* 열고 닫아 asyncpg 단일 커서 제약(열린
    `stream_scalars` 커서 중 같은 연결로 점 조회 금지)을 피한다. `stream_sft_jsonl`의 단일 항목
    캐시 덕에 호출은 O(distinct problems)뿐이라 오프라인 배치에 충분하다.
    """
    async with get_sessionmaker()() as session:
        return await session.get(Problem, problem_id)


async def _run_stream(
    stream_fn: StreamFn, *, dedup: bool, problem_loader: ProblemLoader | None
) -> SftStreamAccounting:
    """스트리밍 경로 본체 — 행을 흘리며 JSONL을 stdout에 즉시 print, 회계를 누적해 반환한다.

    `stream_sft_jsonl`(verified 필터·dedup·직렬화·문제 조인)을 `async for`로 소비하며 한 줄씩
    print — 전량 적재 없음. `problem_loader`를 주면 컨텍스트를 결합한다(단일 캐시). 소진 후
    누산기를 돌려주면 호출자가 `summary()`로 stderr 요약을 낸다.
    """
    accounting = SftStreamAccounting()
    async for line in stream_sft_jsonl(
        stream_fn(), accounting, dedup=dedup, problem_loader=problem_loader
    ):
        print(line)
    return accounting


def main(
    argv: list[str] | None = None,
    *,
    export_fn: ExportFn = _default_export_fn,
    stream_fn: StreamFn = _default_stream_fn,
    problem_loader: ProblemLoader = _default_problem_loader,
) -> int:
    """CLI 엔트리 — verified 풀이를 SFT JSONL로 stdout에, 회계 요약을 stderr에 낸다.

    `--no-dedup`(기본 dedup ON)·`--stream`(옵트인·전량 적재 없이 서버측 커서로 흘림·메모리 가드)·
    `--with-problem`(옵트인·코퍼스 조인으로 question_text·unit_codes 결합·미설정 시 컨텍스트 None).
    `export_fn`/`stream_fn`/`problem_loader`는 테스트 주입 좌석(기본 실 DB). 종료 코드 0(verified
    0건도 정상). `--stream` 유무로 출력은 동일하고 메모리 프로파일만 다르다.

    저작권 안전(§13.2): `question_text`는 코퍼스 불변식상 라이선스 청정만 본문을 보유하고 제한
    출처는 NULL이라 조인해도 새지 않는다. NO_DATA: 코퍼스에 없는 problem_id는 컨텍스트를 비우고
    `problems_missing`로 정직 집계한다(날조 0).
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
    parser.add_argument(
        "--stream",
        action="store_true",
        help="전량 적재 없이 서버측 커서로 1건씩 흘림(대규모 메모리 가드·출력은 일괄과 동일).",
    )
    parser.add_argument(
        "--with-problem",
        action="store_true",
        help="코퍼스를 조인해 문제 본문·성취기준(question_text·unit_codes)을 결합(기본 미조인).",
    )
    args = parser.parse_args(argv)
    dedup = not args.no_dedup
    with_problem = args.with_problem

    if args.stream:
        loader = problem_loader if with_problem else None
        accounting = asyncio.run(_run_stream(stream_fn, dedup=dedup, problem_loader=loader))
        print(json.dumps(accounting.summary()), file=sys.stderr)
        return 0

    dataset: SftDataset = asyncio.run(export_fn(dedup, with_problem))
    for line in iter_sft_jsonl(dataset):
        print(line)
    summary = {
        "total_input": dataset.total_input,
        "records": dataset.size,
        "excluded_unverified": dataset.excluded_unverified,
        "deduped": dataset.deduped,
        "problems_missing": dataset.problems_missing,
    }
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
