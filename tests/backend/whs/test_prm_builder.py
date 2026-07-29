"""WH-S PRM 학습셋 빌더(`whs/prm_builder.py`) — 순수 단위(hermetic·in-memory 트리).

`build_prm_dataset`의 *추출·라벨·회계* 로직만 검증한다: 비루트 step 추출·verify_status→good/bad
라벨·PENDING/UNVERIFIED 배제(R-S2)·prefix 상태열·정직 집계·JSONL 직렬화. DB 무관(SolutionNode
in-memory 구성). 실 DB 트리 조회는 후속 슬라이스(self_evolution 순수→DB 선례).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from whymath_backend.config import Settings
from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode
from whymath_backend.whs.node_store import create_node, get_all_nodes
from whymath_backend.whs.prm_builder import (
    PrmDataset,
    build_prm_dataset,
    collect_prm_dataset,
    iter_prm_jsonl,
)

_PID = uuid.uuid4()


def _node(
    *,
    state: dict[str, object],
    status: NodeVerifyStatus,
    parent_id: uuid.UUID | None = None,
    action: str | None = None,
    node_id: uuid.UUID | None = None,
    prm_score: float | None = None,
    problem_id: uuid.UUID | None = None,
) -> SolutionNode:
    """in-memory SolutionNode 1개(DB 없음·id 명시 발급·problem_id 기본 `_PID`)."""
    return SolutionNode(
        id=node_id or uuid.uuid4(),
        problem_id=problem_id or _PID,
        parent_id=parent_id,
        state_repr=state,
        action=action,
        verify_status=status,
        prm_score=prm_score,
    )


class TestBuildPrmDataset:
    def test_extracts_good_and_bad_from_verify_status(self) -> None:
        """root + verified child + failed child → good 1·bad 1·배제 0."""
        root = _node(state={"expr": "2x+1=7"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"expr": "2x=6"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="양변에서 1 빼기",
        )
        bad = _node(
            state={"expr": "x^2=9"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="잘못된 제곱",
        )
        ds = build_prm_dataset([root, good, bad])
        assert isinstance(ds, PrmDataset)
        assert ds.total_input == 2  # 비루트 step 2(root는 step 아님)
        assert ds.good_labels == 1 and ds.bad_labels == 1
        assert ds.excluded_uncertain == 0
        assert ds.size == 2
        by_label = {r.label: r for r in ds.records}
        assert by_label["good"].step_action == "양변에서 1 빼기"
        assert by_label["good"].step_state == {"expr": "2x=6"}
        assert by_label["good"].prefix_states == ({"expr": "2x+1=7"},)  # root만
        assert by_label["bad"].label == "bad"

    def test_excludes_pending_and_unverified_r_s2(self) -> None:
        """PENDING·UNVERIFIED step은 학습 배제(uncertain)·정직 집계·verified만 레코드."""
        root = _node(state={"s": 0}, status=NodeVerifyStatus.PENDING)
        pending = _node(
            state={"s": 1}, status=NodeVerifyStatus.PENDING, parent_id=root.id, action="a"
        )
        unverified = _node(
            state={"s": 2}, status=NodeVerifyStatus.UNVERIFIED, parent_id=root.id, action="b"
        )
        verified = _node(
            state={"s": 3}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="c"
        )
        ds = build_prm_dataset([root, pending, unverified, verified])
        assert ds.total_input == 3  # 비루트 step 3
        assert ds.excluded_uncertain == 2  # PENDING·UNVERIFIED 배제
        assert ds.size == 1 and ds.good_labels == 1
        assert all(r.label in ("good", "bad") for r in ds.records)
        assert ds.records[0].step_action == "c"

    def test_prefix_states_multi_level(self) -> None:
        """깊은 트리 — step의 prefix는 루트~부모 상태열(순서 보존)."""
        root = _node(state={"d": 0}, status=NodeVerifyStatus.PENDING)
        a = _node(state={"d": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="a1")
        b = _node(state={"d": 2}, status=NodeVerifyStatus.VERIFIED, parent_id=a.id, action="a2")
        ds = build_prm_dataset([root, a, b])
        by_state = {tuple(sorted(r.step_state.items())): r for r in ds.records}
        rec_a = by_state[(("d", 1),)]
        rec_b = by_state[(("d", 2),)]
        assert rec_a.prefix_states == ({"d": 0},)  # root
        assert rec_b.prefix_states == ({"d": 0}, {"d": 1})  # root → a

    def test_root_only_yields_no_records(self) -> None:
        """루트만 있으면 step 0(들어온 행동 없음)."""
        root = _node(state={"x": 1}, status=NodeVerifyStatus.PENDING)
        ds = build_prm_dataset([root])
        assert ds.total_input == 0 and ds.size == 0

    def test_empty_input(self) -> None:
        """빈 입력 → 빈 데이터셋(전부 0)."""
        ds = build_prm_dataset([])
        assert ds.size == 0
        assert ds.total_input == 0 and ds.excluded_uncertain == 0

    def test_non_root_without_action_is_not_a_step(self) -> None:
        """비루트인데 action 결손(엣지 미상) → 후보 step 아님(total_input 미포함)."""
        root = _node(state={"x": 0}, status=NodeVerifyStatus.PENDING)
        orphan_action = _node(
            state={"x": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action=None
        )
        ds = build_prm_dataset([root, orphan_action])
        assert ds.total_input == 0 and ds.size == 0

    def test_input_order_preserved(self) -> None:
        """레코드는 입력 순서 보존(결정론)."""
        root = _node(state={"n": 0}, status=NodeVerifyStatus.PENDING)
        c1 = _node(state={"n": 1}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="1")
        c2 = _node(state={"n": 2}, status=NodeVerifyStatus.FAILED, parent_id=root.id, action="2")
        c3 = _node(state={"n": 3}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="3")
        ds = build_prm_dataset([root, c1, c2, c3])
        assert [r.step_action for r in ds.records] == ["1", "2", "3"]

    def test_prm_score_embedded_on_record(self) -> None:
        """prm_score는 confidence 메타로 레코드에 부가(node 출처값 그대로·prefix 불변)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="g",
            prm_score=0.9,
        )
        bad = _node(
            state={"e": "2"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="b",
            prm_score=0.2,
        )
        ds = build_prm_dataset([root, good, bad])
        by_label = {r.label: r for r in ds.records}
        assert by_label["good"].prm_score == 0.9
        assert by_label["bad"].prm_score == 0.2
        assert by_label["good"].prefix_states == ({"e": "0"},)  # 부가가 prefix를 건드리지 않음

    def test_prm_score_none_preserved(self) -> None:
        """미평가 노드의 prm_score(None)는 레코드에 None으로 보존된다."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="g"
        )
        ds = build_prm_dataset([root, good])
        assert ds.records[0].prm_score is None

    def test_scored_steps_and_mean(self) -> None:
        """레코드화된 step의 점수만 집계 — 0.5+1.0+None → scored 2·mean 0.75."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        a = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="a",
            prm_score=0.5,
        )
        b = _node(
            state={"e": "2"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="b",
            prm_score=1.0,
        )
        c = _node(state={"e": "3"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="c")
        ds = build_prm_dataset([root, a, b, c])
        assert ds.size == 3
        assert ds.scored_steps == 2  # None은 통계 제외
        assert ds.mean_prm_score == 0.75  # (0.5 + 1.0) / 2

    def test_mean_none_when_no_scores(self) -> None:
        """점수 보유 레코드가 0건이면 mean_prm_score는 None(0 나눗셈 회피)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="g"
        )
        ds = build_prm_dataset([root, good])
        assert ds.size == 1 and ds.scored_steps == 0
        assert ds.mean_prm_score is None

    def test_excluded_step_score_not_counted(self) -> None:
        """배제(PENDING/UNVERIFIED) step의 prm_score는 통계에서도 제외(scored ≤ size)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        pending = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.PENDING,
            parent_id=root.id,
            action="p",
            prm_score=0.99,  # 배제 step이라 임베드·통계 모두 제외
        )
        good = _node(
            state={"e": "2"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="g",
            prm_score=0.4,
        )
        ds = build_prm_dataset([root, pending, good])
        assert ds.size == 1 and ds.excluded_uncertain == 1
        assert ds.scored_steps == 1  # good만
        assert ds.mean_prm_score == 0.4  # pending의 0.99는 평균에 끼지 않음


class TestBuildPrmDatasetDedup:
    """(prefix, step) dedup — 같은 `(problem_id, 지문)` 재발견 제거(`build_sft_dataset` 미러)."""

    def test_dedup_same_prefix_step_collapses(self) -> None:
        """같은 prefix·같은 step(지문 키 순서 무관) 재발견은 1건만 — deduped로 집계."""
        root = _node(state={"a": 1, "b": 2}, status=NodeVerifyStatus.PENDING)
        s1 = _node(
            state={"x": 1, "y": 2},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="치환",
        )
        # 같은 부모·같은 action·같은 state(키 순서만 뒤집음) — 지문 동일.
        s2 = _node(
            state={"y": 2, "x": 1},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="치환",
        )
        ds = build_prm_dataset([root, s1, s2])
        assert ds.size == 1
        assert ds.deduped == 1
        assert ds.total_input == 2
        assert ds.good_labels == 1 and ds.bad_labels == 0
        # 불변식: total == excluded + size + deduped.
        assert ds.total_input == ds.excluded_uncertain + ds.size + ds.deduped

    def test_dedup_disabled_keeps_duplicates(self) -> None:
        """dedup=False → 같은 지문 step이라도 모두 보존(deduped=0)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        s1 = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="s"
        )
        s2 = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="s"
        )
        ds = build_prm_dataset([root, s1, s2], dedup=False)
        assert ds.size == 2 and ds.deduped == 0

    def test_dedup_prm_score_only_differs_collapses(self) -> None:
        """점수만 다른 같은 step → 1건(첫 레코드 prm_score 유지·prm_score 키 제외 회귀)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        first = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="s",
            prm_score=0.9,
        )
        second = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="s",
            prm_score=0.1,  # 점수만 다름 — 지문에서 제외되므로 중복으로 봄.
        )
        ds = build_prm_dataset([root, first, second])
        assert ds.size == 1 and ds.deduped == 1
        assert ds.records[0].prm_score == 0.9  # 첫 레코드 유지
        assert ds.scored_steps == 1 and ds.mean_prm_score == 0.9  # 둘째 0.1은 집계 안 됨

    def test_dedup_different_problem_no_collision(self) -> None:
        """*다른 problem_id*의 우연히 같은 지문은 보존(키=(problem_id, 지문))."""
        p2 = uuid.uuid4()
        root1 = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        s1 = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root1.id, action="s"
        )
        root2 = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING, problem_id=p2)
        s2 = _node(
            state={"e": "1"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root2.id,
            action="s",
            problem_id=p2,
        )
        ds = build_prm_dataset([root1, s1, root2, s2])
        assert ds.size == 2 and ds.deduped == 0

    def test_dedup_different_step_kept(self) -> None:
        """같은 문제라도 step(action·state)이 다르면 둘 다 보존(다중 전략)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        s1 = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="대수"
        )
        s2 = _node(
            state={"e": "2"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="기하"
        )
        ds = build_prm_dataset([root, s1, s2])
        assert ds.size == 2 and ds.deduped == 0

    def test_dedup_excluded_step_not_counted_as_dup(self) -> None:
        """PENDING은 dedup 게이트 전에 배제 — excluded_uncertain만 세고 deduped는 안 셈(직교)."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        pending = _node(
            state={"e": "1"}, status=NodeVerifyStatus.PENDING, parent_id=root.id, action="s"
        )
        # PENDING step과 지문이 같지만 라벨 불가라 dedup 게이트 전에 빠진다(중복 충돌 없음).
        verified = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="s"
        )
        ds = build_prm_dataset([root, pending, verified])
        assert ds.size == 1 and ds.good_labels == 1
        assert ds.excluded_uncertain == 1 and ds.deduped == 0
        assert ds.total_input == ds.excluded_uncertain + ds.size + ds.deduped


class TestIterPrmJsonl:
    def test_yields_one_json_line_per_record(self) -> None:
        """레코드당 JSONL 1줄 — UUID·nested state dict 직렬화·round-trip."""
        root = _node(state={"expr": "a"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"expr": "b"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="step"
        )
        ds = build_prm_dataset([root, good])
        lines = list(iter_prm_jsonl(ds))
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["problem_id"] == str(_PID)
        assert obj["label"] == "good"
        assert obj["step_action"] == "step"
        assert obj["step_state"] == {"expr": "b"}
        assert obj["prefix_states"] == [{"expr": "a"}]

    def test_empty_dataset_yields_no_lines(self) -> None:
        """빈 데이터셋 → 0줄."""
        assert list(iter_prm_jsonl(build_prm_dataset([]))) == []

    def test_jsonl_includes_prm_score(self) -> None:
        """JSONL에 prm_score 키 포함 — 점수 보유는 값·미평가는 null."""
        root = _node(state={"e": "a"}, status=NodeVerifyStatus.PENDING)
        scored = _node(
            state={"e": "b"},
            status=NodeVerifyStatus.VERIFIED,
            parent_id=root.id,
            action="s",
            prm_score=0.6,
            node_id=uuid.UUID(int=1),
        )
        unscored = _node(
            state={"e": "c"},
            status=NodeVerifyStatus.FAILED,
            parent_id=root.id,
            action="u",
            node_id=uuid.UUID(int=2),
        )
        lines = list(iter_prm_jsonl(build_prm_dataset([root, scored, unscored])))
        objs = {json.loads(ln)["step_action"]: json.loads(ln) for ln in lines}
        assert objs["s"]["prm_score"] == 0.6
        assert "prm_score" in objs["u"] and objs["u"]["prm_score"] is None


# ===========================================================================
# DB 시ام (collect_prm_dataset) — 단위(hermetic·FakeSession) + 실 PG 통합
# ===========================================================================


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """`get_problem_nodes`의 execute(select).scalars().all()만 시뮬(stmt 무시)."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._rows)


class TestCollectPrmDatasetUnit:
    def test_wires_fetch_to_pure_builder(self) -> None:
        """collect = get_problem_nodes 조회 → build_prm_dataset(순수)와 동일 결과."""
        root = _node(state={"e": "0"}, status=NodeVerifyStatus.PENDING)
        good = _node(
            state={"e": "1"}, status=NodeVerifyStatus.VERIFIED, parent_id=root.id, action="s1"
        )
        bad = _node(
            state={"e": "2"}, status=NodeVerifyStatus.FAILED, parent_id=root.id, action="s2"
        )
        fake = _FakeSession([root, good, bad])
        ds = asyncio.run(collect_prm_dataset(cast(AsyncSession, fake), _PID))
        assert ds == build_prm_dataset([root, good, bad])  # frozen 모델 동등성
        assert ds.good_labels == 1 and ds.bad_labels == 1


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


async def _cleanup(problem_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM solution_nodes WHERE problem_id = :pid"),
                {"pid": str(problem_id)},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_collect_prm_dataset_on_live_pg() -> None:
    """실 PG — 트리 seed → collect_prm_dataset → verify_status 라벨(good/bad)·prefix·배제 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                root = await create_node(session, problem_id=pid, state_repr={"step": "root"})
                # verified step(good·prm_score 부여)
                await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "ok"},
                    action="치환",
                    verify_status=NodeVerifyStatus.VERIFIED,
                    prm_score=0.7,
                )
                # failed step(bad)
                await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "wrong"},
                    action="오변형",
                    verify_status=NodeVerifyStatus.FAILED,
                )
                # pending step(배제·uncertain)
                await create_node(
                    session,
                    problem_id=pid,
                    parent_id=root.id,
                    state_repr={"step": "todo"},
                    action="미평가",
                    verify_status=NodeVerifyStatus.PENDING,
                )
                await session.commit()

            async with sm() as session:
                ds = await collect_prm_dataset(session, pid)
            assert ds.total_input == 3  # 비루트 step 3(root 제외)
            assert ds.good_labels == 1 and ds.bad_labels == 1
            assert ds.excluded_uncertain == 1  # PENDING 배제
            assert ds.size == 2
            # good step만 prm_score 0.7 부여 → scored 1·mean 0.7(bad는 None).
            assert ds.scored_steps == 1 and ds.mean_prm_score == 0.7
            # 모든 레코드의 prefix는 루트 상태로 시작(루트 직후 step).
            assert all(r.prefix_states == ({"step": "root"},) for r in ds.records)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(pid))


@pytest.mark.integration
def test_build_prm_dataset_from_all_nodes_cross_problem_isolation() -> None:
    """실 PG — 2문제 트리 seed → get_all_nodes→build_prm_dataset 합산·크로스-문제 오염 0."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid_a = uuid.uuid4()
    pid_b = uuid.uuid4()

    async def _seed_tree(session: AsyncSession, problem_id: uuid.UUID, root_tag: str) -> None:
        root = await create_node(session, problem_id=problem_id, state_repr={"root": root_tag})
        await create_node(
            session,
            problem_id=problem_id,
            parent_id=root.id,
            state_repr={"step": "ok"},
            action="치환",
            verify_status=NodeVerifyStatus.VERIFIED,
        )
        await create_node(
            session,
            problem_id=problem_id,
            parent_id=root.id,
            state_repr={"step": "wrong"},
            action="오변형",
            verify_status=NodeVerifyStatus.FAILED,
        )
        await create_node(
            session,
            problem_id=problem_id,
            parent_id=root.id,
            state_repr={"step": "todo"},
            action="미평가",
            verify_status=NodeVerifyStatus.PENDING,
        )

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                await _seed_tree(session, pid_a, "A")
                await _seed_tree(session, pid_b, "B")
                await session.commit()

            async with sm() as session:
                nodes = await get_all_nodes(session)
            # 시드 두 문제로 좁혀 합산 검증(무관 행 영향 배제).
            seeded = [n for n in nodes if n.problem_id in {pid_a, pid_b}]
            ds = build_prm_dataset(seeded)
            assert ds.good_labels == 2 and ds.bad_labels == 2  # 문제당 good1·bad1
            assert ds.excluded_uncertain == 2  # 문제당 PENDING 1
            assert ds.size == 4
            # 크로스-문제 오염 0: 각 레코드 prefix는 *자기 문제* 루트로 시작.
            tag_by_pid = {pid_a: "A", pid_b: "B"}
            for rec in ds.records:
                assert rec.prefix_states == ({"root": tag_by_pid[rec.problem_id]},)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(pid_a))
        asyncio.run(_cleanup(pid_b))
