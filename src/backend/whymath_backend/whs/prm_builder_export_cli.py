"""WH-S PRM 학습셋 export *ops CLI* — 전 문제 풀이 트리 → PRM process-supervision JSONL(§5).

솔버가 적재한 풀이 트리(`solution_nodes`)를 PRM(Process Reward Model) 학습셋으로 내보낸다.
WH-S 오프라인 업스트림(§7.5)이라 *전역 배치는 HTTP 미노출* — ops 스크립트/cron이 직접 돌린다
(`self_evolution_export_cli` ops 컨벤션 미러).

흐름(일괄·기본): `get_all_nodes`(전 문제 노드 평탄·problem_id별 인접) → `build_prm_dataset`
(비루트 step만·VERIFIED→good·FAILED→bad·PENDING/UNVERIFIED 배제·정직 회계·dedup 기본 ON) →
`iter_prm_jsonl`(레코드/줄). dedup은 같은 `(problem_id, 지문)` 재발견을 `deduped`로 정직 제거하며
`--no-dedup`로 끈다. 출력 분리:
  - **stdout = JSONL 레코드**(레코드 1개/줄·파이프 가능한 데이터셋·`> prm.jsonl`).
  - **stderr = 정직 요약 JSON 한 줄**(`{total_input, records, excluded_uncertain, deduped,
    good_labels, bad_labels, scored_steps, mean_prm_score}`·ops 회계 로그·데이터 스트림에 섞지
    않음).

흐름(`--stream`·옵트인·대규모 메모리 가드): `stream_all_problem_ids`(서버측 커서·distinct
problem_id 1건씩) → 문제별 `get_problem_nodes`→`build_prm_dataset`→`iter_prm_jsonl` print →
`PrmStreamAccounting.merge`에 누적 → 소진 후 `accounting.summary()`. PRM은 prefix 계산에 부모
노드가 필요해 SFT처럼 행 1건씩 독립 직렬화가 불가능하므로 최소 단위는 *문제 트리*다. 전 노드
list 미적재라 노드가 수만~수십만이어도 메모리를 *한 문제 트리 + 정수 카운터*로만 바운드한다.

사용법:
    python -m whymath_backend.whs.prm_builder_export_cli [--no-dedup] > prm.jsonl
    python -m whymath_backend.whs.prm_builder_export_cli --stream [--no-dedup] > prm.jsonl

종료 코드 0(노드 0건도 정상 — 빈 데이터셋). `--stream`은 출력은 같되 전량 적재 없이 흘린다.
`--no-dedup`은 (prefix, step) 중복 제거를 끈다(기본 ON·`deduped` 회계).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any

from whymath_backend.db.models.solution_node import SolutionNode
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.whs.node_store import (
    get_all_nodes,
    get_problem_nodes,
    stream_all_problem_ids,
)
from whymath_backend.whs.prm_builder import (
    PrmDataset,
    PrmStreamAccounting,
    build_prm_dataset,
    iter_prm_jsonl,
)

__all__ = ["ExportFn", "NodeLoader", "StreamFn", "main"]

# export 좌석 — (dedup) → PrmDataset. 기본은 실 DB(전 문제 노드 평탄 조회·순수 빌더 호출),
# 테스트는 합성 데이터셋을 주입해 DB 없이 CLI 배선(인자 파싱·dedup 전달·JSONL stdout·요약
# stderr·종료 코드)을 검증한다.
ExportFn = Callable[[bool], Coroutine[Any, Any, PrmDataset]]

# stream 좌석 — distinct problem_id를 1건씩 흘리는 async 이터레이터 팩토리. 기본은 실 DB(서버측
# 커서), 테스트는 고정 problem_id async generator를 주입해 DB 없이 스트리밍 CLI 배선을 검증한다.
StreamFn = Callable[[], AsyncIterator[uuid.UUID]]

# 노드 loader 좌석 — problem_id → 그 문제 트리 노드 list(async). 기본은 실 DB(문제별 *별도 세션*·
# 커서 인터리브 회피), 테스트는 고정 dict 가짜 loader를 주입해 DB 없이 문제별 빌드 배선을 검증한다.
NodeLoader = Callable[[uuid.UUID], Awaitable[list[SolutionNode]]]


async def _default_export_fn(dedup: bool) -> PrmDataset:  # pragma: no cover — 실 DB(integration)
    """기본 export — 세션 1개로 전 문제 노드를 평탄 조회해 PRM 데이터셋으로 변환한다(읽기 전용).

    `get_all_nodes`(problem_id별 인접·결정적)→`build_prm_dataset(nodes, dedup=dedup)`(순수).
    `parent_id` 체인은 같은 문제 트리 내부에서만 연결되어 전 문제 노드를 한 리스트로 넘겨도
    크로스-문제 오염이 0이다. 읽기뿐이라 commit 없음.
    """
    async with get_sessionmaker()() as session:
        nodes = await get_all_nodes(session)
        return build_prm_dataset(nodes, dedup=dedup)


async def _default_stream_fn() -> AsyncIterator[uuid.UUID]:  # pragma: no cover — 실 DB
    """기본 stream — 세션 1개로 distinct problem_id를 서버측 커서로 1건씩 흘린다(읽기 전용).

    `stream_all_problem_ids`(distinct·결정적·전량 적재 없음). 세션은 스트림이 소진될 때까지
    `async with`로 살려둔다. 읽기뿐이라 commit 없음(integration 테스트가 실 PG 거동 검증).
    """
    async with get_sessionmaker()() as session:
        async for problem_id in stream_all_problem_ids(session):
            yield problem_id


async def _default_node_loader(
    problem_id: uuid.UUID,
) -> list[SolutionNode]:  # pragma: no cover — 실 DB
    """기본 노드 loader — problem_id로 그 문제 트리 전체 조회(읽기 전용·문제별 *별도 세션*).

    스트림 커서 세션과 분리된 세션을 *호출마다* 열고 닫아 asyncpg 단일 커서 제약(열린
    `stream_scalars` 커서 중 같은 연결로 점 조회 금지)을 피한다. 호출은 O(distinct problems)뿐이라
    오프라인 배치에 충분하다(`self_evolution_export_cli._default_problem_loader` 주석과 동형).
    """
    async with get_sessionmaker()() as session:
        return await get_problem_nodes(session, problem_id)


async def _run_stream(
    stream_fn: StreamFn, node_loader: NodeLoader, *, dedup: bool
) -> PrmStreamAccounting:
    """스트리밍 경로 본체 — problem_id를 흘리며 문제별 JSONL을 stdout에 print, 회계를 누적해 반환.

    `stream_fn`이 흘린 problem_id마다 `node_loader`로 그 문제 트리를 로드해
    `build_prm_dataset(nodes, dedup=dedup)`로 빌드하고 `iter_prm_jsonl`을 한 줄씩 print한다 — 전
    노드 적재 없음(한 문제 트리씩). dedup은 문제 트리 단위라 스트림에서도 build 내부 `seen`으로
    충분하다(같은 키는 같은 문제 트리에서만 발생). 회계는 `PrmStreamAccounting.merge`로 누적. 소진
    후 누산기를 돌려주면 호출자가 `summary()`로 stderr 요약을 낸다.
    """
    accounting = PrmStreamAccounting()
    async for problem_id in stream_fn():
        nodes = await node_loader(problem_id)
        dataset = build_prm_dataset(nodes, dedup=dedup)
        for line in iter_prm_jsonl(dataset):
            print(line)
        accounting.merge(dataset)
    return accounting


def main(
    argv: list[str] | None = None,
    *,
    export_fn: ExportFn = _default_export_fn,
    stream_fn: StreamFn = _default_stream_fn,
    node_loader: NodeLoader = _default_node_loader,
) -> int:
    """CLI 엔트리 — 풀이 트리를 PRM JSONL로 stdout에, 회계 요약을 stderr에 낸다.

    `--stream`(옵트인·전량 적재 없이 distinct problem_id를 서버측 커서로 흘려 문제별 빌드·메모리
    가드). `--no-dedup`(같은 문제·같은 지문 재발견도 모두 보존·기본 dedup ON). `export_fn`/
    `stream_fn`/`node_loader`는 테스트 주입 좌석(기본 실 DB). 종료 코드 0(노드 0건도 정상).
    `--stream` 유무로 출력은 동일하고 메모리 프로파일만 다르다.

    학습 안전(§3·R-S2): VERIFIED→good·FAILED→bad만 레코드화하고 PENDING·UNVERIFIED는
    `excluded_uncertain`으로 *정직하게* 집계해 배제한다(빌더가 보장 — uncertain 학습 누수 0).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.whs.prm_builder_export_cli",
        description=(
            "WH-S PRM 학습셋 export — 전 문제 풀이 트리를 process-supervision JSONL(stdout)로, "
            "회계 요약을 stderr로(§5·VERIFIED/FAILED만·R-S2 배제 집계)."
        ),
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="전량 적재 없이 distinct problem_id를 서버측 커서로 흘려 문제별 빌드(메모리 가드).",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="(prefix, step) 중복 제거 비활성화 — 같은 문제·같은 지문 재발견도 모두 보존(기본 ON).",
    )
    args = parser.parse_args(argv)
    dedup = not args.no_dedup

    if args.stream:
        accounting = asyncio.run(_run_stream(stream_fn, node_loader, dedup=dedup))
        print(json.dumps(accounting.summary()), file=sys.stderr)
        return 0

    dataset: PrmDataset = asyncio.run(export_fn(dedup))
    for line in iter_prm_jsonl(dataset):
        print(line)
    summary: dict[str, float | int | None] = {
        "total_input": dataset.total_input,
        "records": dataset.size,
        "excluded_uncertain": dataset.excluded_uncertain,
        "deduped": dataset.deduped,
        "good_labels": dataset.good_labels,
        "bad_labels": dataset.bad_labels,
        "scored_steps": dataset.scored_steps,
        "mean_prm_score": dataset.mean_prm_score,
    }
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
