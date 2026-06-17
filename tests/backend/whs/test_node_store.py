"""WH-S 풀이 트리 노드 저장소(`whs/node_store.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `create_node`의 ORM 객체 구성·기본값, `update_evaluation`의 무동작
short-circuit(준 값만 갱신)을 hermetic 검증한다. 트리 의미(self-FK·get_children/get_roots
정렬·격리)·`increment_visits` 원자성·enum 라운드트립은 *실 PG 통합테스트*가 검증한다
(SQL 표현·CASCADE는 실 DB라야 의미가 있다 — mastery_tracking 분리 선례).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from whymath_backend.config import Settings
from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode
from whymath_backend.whs.node_store import (
    create_node,
    get_children,
    get_node,
    get_roots,
    increment_visits,
    update_evaluation,
)

# ===========================================================================
# 단위 (hermetic·FakeSession) — DB 무관 로직만
# ===========================================================================


class _FakeSession:
    """`create_node`(add·flush·refresh)·`update_evaluation`(execute)만 시뮬.

    SQL 실행 의미는 무시하고 *래퍼가 무엇을 호출하는지*만 본다. `executed`에 execute로 넘어온
    statement를 모아 short-circuit(무동작) 검증에 쓴다.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.refreshes = 0
        self.executed: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, _obj: Any) -> None:
        self.refreshes += 1

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        return None


class TestCreateNodeUnit:
    def test_builds_node_with_given_fields(self) -> None:
        """create_node가 인자대로 SolutionNode를 구성해 add·flush·refresh한다."""
        fake = _FakeSession()
        pid = uuid.uuid4()
        parent = uuid.uuid4()
        node = asyncio.run(
            create_node(
                cast(AsyncSession, fake),
                problem_id=pid,
                parent_id=parent,
                state_repr={"expr": "x^2"},
                action="치환",
                prm_score=0.7,
                verify_status=NodeVerifyStatus.VERIFIED,
            )
        )
        assert isinstance(node, SolutionNode)
        assert node.problem_id == pid
        assert node.parent_id == parent
        assert node.state_repr == {"expr": "x^2"}
        assert node.action == "치환"
        assert node.prm_score == 0.7
        assert node.verify_status is NodeVerifyStatus.VERIFIED
        assert fake.added == [node]
        assert fake.flushes == 1
        assert fake.refreshes == 1

    def test_defaults_root_pending(self) -> None:
        """parent_id 미지정=루트(None)·verify_status 기본 pending·옵션 None."""
        fake = _FakeSession()
        node = asyncio.run(
            create_node(
                cast(AsyncSession, fake),
                problem_id=uuid.uuid4(),
                state_repr={},
            )
        )
        assert node.parent_id is None
        assert node.action is None
        assert node.prm_score is None
        assert node.verify_status is NodeVerifyStatus.PENDING


class TestUpdateEvaluationUnit:
    def test_noop_when_both_none(self) -> None:
        """둘 다 None이면 UPDATE를 발행하지 않는다(불필요 updated_at 변동 방지)."""
        fake = _FakeSession()
        asyncio.run(update_evaluation(cast(AsyncSession, fake), uuid.uuid4()))
        assert fake.executed == []

    def test_issues_update_when_value_given(self) -> None:
        """값을 하나라도 주면 UPDATE 1건 발행."""
        fake = _FakeSession()
        asyncio.run(
            update_evaluation(
                cast(AsyncSession, fake),
                uuid.uuid4(),
                verify_status=NodeVerifyStatus.FAILED,
            )
        )
        assert len(fake.executed) == 1


class TestEnumValues:
    def test_node_verify_status_labels(self) -> None:
        """enum 값=마이그레이션 라벨(pending·verified·unverified·failed)·소문자 정합."""
        assert [s.value for s in NodeVerifyStatus] == [
            "pending",
            "verified",
            "unverified",
            "failed",
        ]


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — 트리 의미·원자성·enum 라운드트립
# ===========================================================================

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
            # parent_id CASCADE가 자식을 지우지만, 안전하게 problem_id로 전량 삭제.
            await conn.execute(
                text("DELETE FROM solution_nodes WHERE problem_id = ANY(:pids)"),
                {"pids": pids},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_create_get_tree_and_visits_on_live_pg() -> None:
    """create→get·트리(부모-자식·get_children/get_roots)·increment_visits·update_evaluation."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    other_pid = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 루트 + 자식 2개 생성(트리)
                root = await create_node(session, problem_id=pid, state_repr={"step": "root"})
                child_a = await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "a"},
                    action="치환",
                )
                child_b = await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "b"},
                    action="케이스분할",
                )
                # 다른 문제의 루트(격리 확인용)
                other_root = await create_node(
                    session, problem_id=other_pid, state_repr={"step": "other"}
                )
                await session.commit()

                # 기본값 검증: server_default(visits=0·pending·id)
                assert root.visits == 0
                assert root.verify_status is NodeVerifyStatus.PENDING
                assert root.parent_id is None

                # get_node 라운드트립
                fetched = await get_node(session, root.id)
                assert fetched is not None
                assert fetched.id == root.id
                assert fetched.state_repr == {"step": "root"}
                assert await get_node(session, uuid.uuid4()) is None

                # get_children: 루트의 자식 2개(형제 순서는 무의미 — 같은 트랜잭션 INSERT는
                # created_at[now()]이 동일하고 tiebreak id가 랜덤 UUID라 순서 비결정적·집합 비교).
                children = await get_children(session, root.id)
                assert {c.id for c in children} == {child_a.id, child_b.id}
                # 자식은 자식이 없음
                assert await get_children(session, child_a.id) == []

                # get_roots: pid의 루트 1개·other_pid의 루트 1개(문제 격리)
                roots = await get_roots(session, pid)
                assert [r.id for r in roots] == [root.id]
                other_roots = await get_roots(session, other_pid)
                assert [r.id for r in other_roots] == [other_root.id]

                # increment_visits 원자성: 3회 → visits=3
                for _ in range(3):
                    await increment_visits(session, child_a.id)
                await session.commit()
                refetched_a = await get_node(session, child_a.id)
                assert refetched_a is not None
                assert refetched_a.visits == 3

                # update_evaluation: prm_score·verify_status 갱신
                await update_evaluation(
                    session,
                    child_a.id,
                    prm_score=0.85,
                    verify_status=NodeVerifyStatus.VERIFIED,
                )
                await session.commit()
                evaluated = await get_node(session, child_a.id)
                assert evaluated is not None
                assert evaluated.prm_score == 0.85
                assert evaluated.verify_status is NodeVerifyStatus.VERIFIED

                # update_evaluation 부분 갱신: verify_status만(child_b)
                await update_evaluation(session, child_b.id, verify_status=NodeVerifyStatus.FAILED)
                await session.commit()
                evaluated_b = await get_node(session, child_b.id)
                assert evaluated_b is not None
                assert evaluated_b.verify_status is NodeVerifyStatus.FAILED
                assert evaluated_b.prm_score is None
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid, other_pid]))


@pytest.mark.integration
def test_parent_cascade_delete_on_live_pg() -> None:
    """self-FK CASCADE: 부모 노드 삭제 시 자식 가지가 함께 제거된다(고아 노드 방지)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                root = await create_node(session, problem_id=pid, state_repr={"step": "root"})
                child = await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "child"},
                )
                await session.commit()
                root_id, child_id = root.id, child.id

            # 부모(root) 삭제 → 자식 CASCADE 제거
            async with sm() as session:
                await session.execute(
                    text("DELETE FROM solution_nodes WHERE id = :rid"),
                    {"rid": str(root_id)},
                )
                await session.commit()

            async with sm() as session:
                assert await get_node(session, root_id) is None
                # 자식도 CASCADE로 사라짐
                assert await get_node(session, child_id) is None
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid]))
