"""WH-S 솔버 루프 골격(`whs/harness.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): 루프 불변식을 hermetic 검증한다 — 탐색예산 상한·end_search·verified finalize
적재·failed finalize 거부·검증 보조정리만 log_lemma·dead-end 회피·retrieve 웜스타트·verify 등급.
검증기 스택은 *실제로* 돌린다(verify_answer/verify_solution/final_verdict는 순수). 저장소 영속·
enum 왕복은 *실 PG 통합테스트*가 끝까지 한 번 굴린다(scripted solve).
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
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs.harness import (
    ApplyStrategyAction,
    ConjectureCheckAction,
    DecomposeAction,
    EndSearchAction,
    FinalizeAction,
    LogDeadEndAction,
    LogLemmaAction,
    ParseProblemAction,
    RetrieveSimilarAction,
    ScriptedPolicy,
    VerifyAction,
    run_solver,
)

# ===========================================================================
# 단위 (hermetic·FakeSession) — 루프 불변식
# ===========================================================================

# 검증기 스택이 통과/실패하는 실제 조건·답(기존 verify_answer 테스트 포맷).
_COND = ["x**2 - 5*x + 6 = 0"]
_ANS_PASS = {"x": "3"}  # 3은 근 → pass
_ANS_FAIL = {"x": "4"}  # 4는 근 아님 → fail


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeResult:
    def __init__(self, *, scalar: Any = None, scalars_list: list[Any] | None = None) -> None:
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar(self) -> Any:
        return self._scalar

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)


class _FakeSession:
    """harness가 부르는 저장소 연산을 시뮬 — add/flush/refresh + execute(scalar|scalars)."""

    def __init__(
        self,
        *,
        dead_end: bool = False,
        verified_list: list[Any] | None = None,
        lemmas_list: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self._dead_end = dead_end
        self._verified_list = verified_list or []
        self._lemmas_list = lemmas_list or []
        self._scalars_round = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        # server_default(id) 시뮬 — 새 행에 id를 채워 harness가 바로 쓰게 한다.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        # retrieve_similar: get_verified(1번째)·get_lemmas(2번째). is_dead_end: scalar.
        scalars = self._verified_list if self._scalars_round == 0 else self._lemmas_list
        self._scalars_round += 1
        return _FakeResult(scalar=self._dead_end, scalars_list=scalars)


def _run(session: Any, policy: ScriptedPolicy, **kw: Any) -> Any:
    return asyncio.run(
        run_solver(cast(AsyncSession, session), problem_id=uuid.uuid4(), policy=policy, **kw)
    )


class TestLoopControl:
    def test_end_search_returns_ended(self) -> None:
        """정책이 end_search → status=ended·도구 호출 0."""
        out = _run(_FakeSession(), ScriptedPolicy([EndSearchAction()]))
        assert out.status == "ended"
        assert out.tool_calls == 0

    def test_budget_exhausted(self) -> None:
        """예산 소진(finalize 없음) → budget_exhausted·호출 = 상한."""
        policy = ScriptedPolicy([ParseProblemAction(structured={"goal": "x"})] * 5)
        out = _run(_FakeSession(), policy, max_tool_calls=2)
        assert out.status == "budget_exhausted"
        assert out.tool_calls == 2

    def test_invalid_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="max_tool_calls"):
            _run(_FakeSession(), ScriptedPolicy([]), max_tool_calls=0)


class TestFinalizeInvariants:
    def test_verified_finalize_banks_and_ends(self) -> None:
        """verified finalize → 적재·status=finalized·banked id 존재."""
        policy = ScriptedPolicy(
            [FinalizeAction(conditions=_COND, answer=_ANS_PASS, steps=[], strategy_tag="대수적")]
        )
        session = _FakeSession()
        out = _run(session, policy)
        assert out.status == "finalized"
        assert out.final_grade == "verified"
        assert out.banked_solution_id is not None
        assert len(session.added) == 1  # bank_solution 1행

    def test_failed_finalize_rejected_not_banked(self) -> None:
        """failed finalize → 거부(미적재)·finalized 아님. 검색은 종료 안 됨(이후 end_search)."""
        policy = ScriptedPolicy([FinalizeAction(conditions=_COND, answer=_ANS_FAIL, steps=[])])
        session = _FakeSession()
        out = _run(session, policy)
        # finalize 실패 후 스크립트 소진 → end_search → ended
        assert out.status == "ended"
        assert out.banked_solution_id is None
        assert session.added == []  # 적재 0
        assert out.trace[0].ok is False
        assert out.trace[0].grade == "failed"

    def test_finalize_dedup_reuses_existing(self) -> None:
        """finalize는 dedup=True로 적재 — 같은 문제의 동일 경로 기존 행이 있으면 재사용(멱등·#256).

        재발견 풀이가 자기진화 데이터(§5)에 중복 적재되지 않는다(위생). status는 여전히
        finalized이고 banked_solution_id는 *기존* 행 id다(새 적재 0).
        """
        existing = VerifiedSolution(
            problem_id=uuid.uuid4(),
            grade=WhsSolutionGrade.VERIFIED,
            # finalize가 만드는 경로와 바이트 동일(같은 지문) → dedup 히트.
            solution_path={"conditions": _COND, "answer": _ANS_PASS, "steps": []},
        )
        existing.id = uuid.uuid4()
        policy = ScriptedPolicy(
            [FinalizeAction(conditions=_COND, answer=_ANS_PASS, steps=[], strategy_tag="대수적")]
        )
        session = _FakeSession(verified_list=[existing])
        out = _run(session, policy)
        assert out.status == "finalized"
        assert out.final_grade == "verified"
        assert out.banked_solution_id == existing.id  # 기존 행 재사용
        assert session.added == []  # 새 적재 0(중복 차단)


class TestLemmaGate:
    def test_log_lemma_without_verified_rejected(self) -> None:
        """직전 verify=verified 없이 log_lemma → 거부(미적재)."""
        policy = ScriptedPolicy([LogLemmaAction(lemma_key="k", lemma_repr={"f": 1})])
        session = _FakeSession()
        out = _run(session, policy)
        assert out.trace[0].ok is False
        assert session.executed == []  # log_lemma INSERT 미발행

    def test_log_lemma_after_verified_ok(self) -> None:
        """verify=verified 직후 log_lemma → 적재(INSERT 발행)."""
        policy = ScriptedPolicy(
            [
                VerifyAction(conditions=_COND, answer=_ANS_PASS, steps=[]),
                LogLemmaAction(lemma_key="k", lemma_repr={"f": 1}),
            ]
        )
        session = _FakeSession()
        out = _run(session, policy)
        assert out.trace[0].grade == "verified"
        assert out.trace[1].ok is True
        assert len(session.executed) == 1  # log_lemma INSERT


class TestApplyStrategy:
    def test_dead_end_skipped(self) -> None:
        """막다른 길이면 노드 생성 안 함(건너뜀)."""
        policy = ScriptedPolicy(
            [ApplyStrategyAction(action_label="치환", state_repr={"s": 1}, state_hash="h")]
        )
        session = _FakeSession(dead_end=True)
        out = _run(session, policy)
        assert out.trace[0].ok is False
        assert "dead-end" in out.trace[0].detail
        assert session.added == []  # 노드 미생성

    def test_creates_node_when_not_dead_end(self) -> None:
        """막다른 길 아니면 트리 노드 생성·node_id 채움."""
        policy = ScriptedPolicy(
            [ApplyStrategyAction(action_label="치환", state_repr={"s": 1}, state_hash="h")]
        )
        session = _FakeSession(dead_end=False)
        out = _run(session, policy)
        assert out.trace[0].ok is True
        assert out.trace[0].node_id is not None
        assert len(session.added) == 1


class TestRetrieveSimilar:
    def test_warm_start_counts(self) -> None:
        """retrieve_similar → 검증풀이·보조정리 개수 보고(웜스타트)."""
        policy = ScriptedPolicy([RetrieveSimilarAction()])
        session = _FakeSession(verified_list=[1, 2], lemmas_list=[1])
        out = _run(session, policy)
        assert out.trace[0].ok is True
        assert "2" in out.trace[0].detail and "1" in out.trace[0].detail


class TestOtherTools:
    def test_conjecture_check_refuted(self) -> None:
        """수치 반례 발견(candidate가 조건 위반) → 반증."""
        policy = ScriptedPolicy([ConjectureCheckAction(conditions=_COND, candidate=_ANS_FAIL)])
        out = _run(_FakeSession(), policy)
        assert out.trace[0].ok is True
        assert "반례 발견" in out.trace[0].detail

    def test_conjecture_check_no_counterexample(self) -> None:
        """반례 없음(candidate가 조건 만족)."""
        policy = ScriptedPolicy([ConjectureCheckAction(conditions=_COND, candidate=_ANS_PASS)])
        out = _run(_FakeSession(), policy)
        assert out.trace[0].ok is True
        assert "반례 없음" in out.trace[0].detail

    def test_decompose_records_subgoals(self) -> None:
        policy = ScriptedPolicy([DecomposeAction(subgoals=["보조1", "보조2"])])
        out = _run(_FakeSession(), policy)
        assert out.trace[0].ok is True
        assert "2" in out.trace[0].detail

    def test_log_deadend_records(self) -> None:
        policy = ScriptedPolicy(
            [LogDeadEndAction(state_hash="h", action_label="치환", reason="순환")]
        )
        session = _FakeSession()
        out = _run(session, policy)
        assert out.trace[0].ok is True
        assert len(session.executed) == 1  # log_dead_end INSERT


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — scripted solve 끝까지(저장소 영속·enum 왕복)
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


async def _cleanup(problem_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    pid = str(problem_id)
    try:
        async with engine.begin() as conn:
            for tbl in ("verified_solutions", "verified_lemmas", "solution_nodes"):
                await conn.execute(text(f"DELETE FROM {tbl} WHERE problem_id = :pid"), {"pid": pid})
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_scripted_solve_persists_on_live_pg() -> None:
    """전체 scripted solve: apply→verify→log_lemma→finalize(verified) → 4 저장소 영속 왕복."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()

    async def _go() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                policy = ScriptedPolicy(
                    [
                        ApplyStrategyAction(
                            action_label="인수분해", state_repr={"s": "(x-2)(x-3)"}, state_hash="h0"
                        ),
                        VerifyAction(conditions=_COND, answer=_ANS_PASS, steps=[]),
                        LogLemmaAction(
                            lemma_key="root:3", lemma_repr={"root": 3}, statement="x=3 근"
                        ),
                        FinalizeAction(
                            conditions=_COND, answer=_ANS_PASS, steps=[], strategy_tag="대수적"
                        ),
                    ]
                )
                out = await run_solver(session, problem_id=pid, policy=policy)
                await session.commit()

                assert out.status == "finalized"
                assert out.final_grade == "verified"
                assert out.banked_solution_id is not None
                # 트레이스: apply(ok)·verify(verified)·log_lemma(ok)·finalize(ok)
                kinds = [(t.kind, t.ok) for t in out.trace]
                assert kinds == [
                    ("apply_strategy", True),
                    ("verify", True),
                    ("log_lemma", True),
                    ("finalize", True),
                ]
        finally:
            await engine.dispose()

    try:
        asyncio.run(_go())
    finally:
        asyncio.run(_cleanup(pid))
