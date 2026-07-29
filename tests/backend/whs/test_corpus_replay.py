"""WH-S 코퍼스 replay 배치 테스트 — 순수부(hermetic) + 실 PG 왕복(@integration·기본 skip).

순수부: 로더 필터·결함 주입(비동치 증명 전제)·액션 명세 빌더의 형태를 못 박는다.
통합부: 실 PG에서 replay 1건이 ① run_solver finalize=verified ② solution_nodes 체인+오분기
생성·라벨(VERIFIED/FAILED) ③ Verified Solution Bank 적재 ④ prm_builder가 good+bad 학습쌍을
산출함을 왕복으로 봉인한다(테스트 후 전건 cleanup).
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from whymath_backend.config import Settings
from whymath_backend.whs.corpus_replay import (
    ReplayItem,
    build_replay_actions,
    corrupt_final_step,
    load_replay_items,
    replay_one,
)

# ── 순수부(hermetic) ──────────────────────────────────────────────────


def _record(slug: str, steps: list[str] | None) -> dict[str, object]:
    verify: dict[str, object] = {
        "conditions": "x**2 - 3*x - 10 = 0",
        "answer_map": {"x": "5"},
    }
    if steps is not None:
        verify["solution_steps"] = steps
    return {
        "problem_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"whymath:test:{slug}")),
        "slug": slug,
        "verify": verify,
    }


def test_load_replay_items_filters_stepless() -> None:
    # steps 보유 레코드만 대상 — 없거나 1원소(전이 0)면 정직 제외.
    lines = [
        json.dumps(_record("with-steps", ["x**2 - 3*x - 10", "(x - 5)*(x + 2)"])),
        json.dumps(_record("no-steps", None)),
        json.dumps(_record("single-step", ["x**2 - 3*x - 10"])),
    ]
    items = load_replay_items("\n".join(lines))
    assert [i.slug for i in items] == ["with-steps"]
    assert items[0].steps == ("x**2 - 3*x - 10", "(x - 5)*(x + 2)")


def test_corrupt_final_step_proven_incorrect() -> None:
    # 부호 반전은 비동치가 SymPy로 증명될 때만 반환된다(날조 금지).
    corrupted = corrupt_final_step(("x**2 - 3*x - 10", "(x - 5)*(x + 2)"))
    assert corrupted == "-((x - 5)*(x + 2))"


def test_build_replay_actions_shape() -> None:
    item = ReplayItem(
        problem_id=uuid.uuid4(),
        slug="t",
        conditions="x**2 - 3*x - 10 = 0",
        answer_map={"x": "5"},
        steps=("a", "b"),
    )
    specs = build_replay_actions(item, bad_step="-(b)")
    kinds = [s["kind"] for s in specs]
    # parse → retrieve → 체인 2 → 오분기 apply+deadend → finalize
    assert kinds == [
        "parse_problem",
        "retrieve_similar",
        "apply_strategy",
        "apply_strategy",
        "apply_strategy",
        "log_deadend",
        "finalize",
    ]
    # 루트는 부모 없음·체인은 prev·오분기는 branch(마지막 정상 단계의 부모에서 갈라짐).
    parents = [s.get("parent") for s in specs if s["kind"] == "apply_strategy"]
    assert parents == [None, "prev", "branch"]
    # 오분기 없으면 apply 2 + finalize.
    kinds_clean = [s["kind"] for s in build_replay_actions(item, bad_step=None)]
    assert kinds_clean.count("apply_strategy") == 2
    assert "log_deadend" not in kinds_clean


# ── 통합 (실 PG·기본 SKIP) — replay 왕복·PRM 라벨 ─────────────────────

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _cleanup(problem_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    pids = [str(p) for p in problem_ids]
    try:
        async with engine.begin() as conn:
            for table in ("verified_solutions", "solution_nodes", "dead_end_log"):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE problem_id = ANY(:pids)"),  # noqa: S608
                    {"pids": pids},
                )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_replay_one_labels_and_banks_on_live_pg() -> None:
    """replay 1건 왕복 — finalize verified·노드 라벨(good/bad)·bank 적재·PRM 학습쌍."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    item = ReplayItem(
        problem_id=pid,
        slug="replay-int-quad",
        conditions="x**2 - 3*x - 10 = 0",
        answer_map={"x": "5"},
        steps=("x**2 - 3*x - 10", "(x - 5)*(x + 2)"),
    )

    async def _run() -> None:
        from whymath_backend.whs.node_store import get_problem_nodes
        from whymath_backend.whs.prm_builder import build_prm_dataset
        from whymath_backend.whs.solution_bank import get_verified

        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                outcome, counts = await replay_one(session, item, bad_branch=True)
                await session.commit()
                assert outcome.status == "finalized"
                assert outcome.final_grade == "verified"
                # 노드 3(루트+체인1+오분기1) — good 1·bad 1.
                assert counts == {
                    "nodes": 3,
                    "good": 1,
                    "bad": 1,
                    "unverified": 0,
                    "bad_skipped": 0,
                }
                nodes = await get_problem_nodes(session, pid)
                statuses = sorted(n.verify_status.value for n in nodes)
                assert statuses == ["failed", "pending", "verified"]  # 루트=pending(비step)
                banked = await get_verified(session, pid)
                assert len(banked) == 1
                # PRM 빌더 왕복 — good 1·bad 1(pending 루트는 구조 배제).
                dataset = build_prm_dataset(nodes)
                labels = sorted(r.label for r in dataset.records)
                assert labels == ["bad", "good"]
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid]))
