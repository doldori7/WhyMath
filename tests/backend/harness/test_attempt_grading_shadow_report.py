"""서버측 답안 채점 shadow 리포트 테스트(NLP-02) — acceptance①~⑤ 대응.

구성:
  - `derive_verify_inputs` 단위 테스트(파생 정확성 위험 — y를 x로 오인하지 않는지 등, 순수·
    DB 0)
  - `build_report` 회귀 테스트(unverifiable이 mismatch로 새지 않음 — 순수·DB 0)
  - `submit_attempt` BKT 입력 동결 구조 테스트(소스 레벨 — api/me.py 무변경 증명)
  - 변별력 discriminating 테스트(acceptance⑤) — 실 PostgreSQL 필요(`pytest.mark.integration`,
    `tests/backend/api/test_me_integration.py`의 async 엔진 seed/cleanup 관례 답습)
"""

from __future__ import annotations

import inspect
import re
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api import me as api_me
from whymath_backend.config import Settings
from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.db.models.user import UserProfile
from whymath_backend.harness.attempt_grading_shadow_report import (
    AttemptRecord,
    build_report,
    derive_verify_inputs,
    fetch_attempt_records,
    grade_attempt,
    render_report,
    report_to_json,
)
from whymath_backend.schema.enums import Curriculum, Persona, SourceType, Subject
from whymath_backend.schema.problem import Condition, Problem
from whymath_backend.schema.user import UserProfile as UserProfileSchema

pytestmark = pytest.mark.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼 — 최소 Problem(schema) 구성
# ──────────────────────────────────────────────────────────────────────────
def _problem(
    *,
    conditions: list[Condition] | None = None,
    answer: str | None = "3",
) -> Problem:
    return Problem(
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2022,
        subject=Subject.공통,
        unit_codes=["U-TEST"],
        conditions_parsed=conditions if conditions is not None else [],
        answer=answer,
    )


def _cond(formal: str | None, label: str = "가") -> Condition:
    return Condition(label=label, text="조건", formal=formal)


# ──────────────────────────────────────────────────────────────────────────
# derive_verify_inputs 단위 테스트
# ──────────────────────────────────────────────────────────────────────────
class TestDeriveVerifyInputs:
    def test_single_condition_x_derives(self) -> None:
        """단일 조건·자유기호 x·유효 answer → 정확한 (conditions, answer_map)."""
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        result = derive_verify_inputs(problem)
        assert result is not None
        conditions, answer_map = result
        assert conditions == ["2*x - 6"]
        assert answer_map == {"x": "3"}

    def test_unknown_is_y_not_x_returns_none(self) -> None:
        """조건의 실제 미지수가 y(≠x) → None(비파생·verify_answer 호출 안 함).

        이것이 이 태스크의 핵심 위험 시나리오다: {"x": problem.answer}를 순진하게 만들면
        엉뚱한 변수에 값을 대입한 거짓 결과를 낼 수 있으므로, y를 발견하면 파생을 포기해야
        한다.
        """
        problem = _problem(conditions=[_cond("2*y - 6")], answer="3")
        assert derive_verify_inputs(problem) is None

    def test_no_formal_at_all_returns_none(self) -> None:
        """formal이 아예 없는 조건(None) → None(비파생)."""
        problem = _problem(conditions=[_cond(None)], answer="3")
        assert derive_verify_inputs(problem) is None

    def test_multiple_conditions_combined_symbols_not_exactly_x_returns_none(self) -> None:
        """여러 조건의 자유기호 합집합이 {"x"}가 아님(다중 변수) → None(비파생).

        이 슬라이스는 단일 미지수 문항만 지원한다(모듈 docstring 명시 스코프 밖).
        """
        problem = _problem(
            conditions=[_cond("x + y - 3"), _cond("x - y - 1")],
            answer="2",
        )
        assert derive_verify_inputs(problem) is None

    def test_no_conditions_returns_none(self) -> None:
        problem = _problem(conditions=[], answer="3")
        assert derive_verify_inputs(problem) is None

    def test_no_answer_returns_none(self) -> None:
        problem = _problem(conditions=[_cond("2*x - 6")], answer=None)
        assert derive_verify_inputs(problem) is None

    def test_unparseable_formal_returns_none(self) -> None:
        """formal이 SymPy로 파싱 불가(단일 등호 등) → None(보수적 비파생·크래시 금지).

        단일 `=`는 파이썬 대입문이라 sympify가 예외를 던진다 — verify_answer._parse_condition과
        달리 이 파생 게이트는 등호 전처리를 하지 않는다(단순 자유기호 추출용 — 모듈 docstring).
        """
        problem = _problem(conditions=[_cond("2*x - 6 = 0")], answer="3")
        assert derive_verify_inputs(problem) is None

    def test_multiple_conditions_all_x_derives(self) -> None:
        """여러 조건이 모두 x만 포함 → 파생 성공(연립 conditions 리스트로 전달)."""
        problem = _problem(
            conditions=[_cond("x - 2", label="가"), _cond("x**2 - 4", label="나")],
            answer="2",
        )
        result = derive_verify_inputs(problem)
        assert result is not None
        conditions, answer_map = result
        assert conditions == ["x - 2", "x**2 - 4"]
        assert answer_map == {"x": "2"}


# ──────────────────────────────────────────────────────────────────────────
# grade_attempt — student_answer가 항상 채점 대상값임을 확인
# ──────────────────────────────────────────────────────────────────────────
class TestGradeAttempt:
    def test_grades_student_answer_not_problem_answer(self) -> None:
        """Problem.answer(정답 본문)가 아니라 student_answer가 실제 채점 대상."""
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        # 문항 정답은 3이지만 학생 제출은 5(오답) — verdict는 fail이어야 한다.
        verdict = grade_attempt(problem, "5")
        assert verdict is not None
        assert verdict.state == "fail"

    def test_correct_student_answer_passes(self) -> None:
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        verdict = grade_attempt(problem, "3")
        assert verdict is not None
        assert verdict.state == "pass"

    def test_no_student_answer_returns_none(self) -> None:
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        assert grade_attempt(problem, None) is None
        assert grade_attempt(problem, "   ") is None

    def test_non_derivable_problem_returns_none(self) -> None:
        problem = _problem(conditions=[_cond("2*y - 6")], answer="3")
        assert grade_attempt(problem, "3") is None

    def test_unverifiable_via_singularity(self) -> None:
        """특이점(0으로 나눔)에서 unverifiable — pass/fail로 위장하지 않음."""
        problem = _problem(conditions=[_cond("1/(x-3)")], answer="3")
        verdict = grade_attempt(problem, "3")
        assert verdict is not None
        assert verdict.state == "unverifiable"


# ──────────────────────────────────────────────────────────────────────────
# build_report 회귀 테스트 — unverifiable이 mismatch/오답으로 새지 않음(acceptance②)
# ──────────────────────────────────────────────────────────────────────────
class TestBuildReportRegression:
    def test_unverifiable_never_counted_as_mismatch(self) -> None:
        """unverifiable verdict는 client_is_correct와 무관하게 mismatch에 절대 반영 안 됨."""
        problem = _problem(conditions=[_cond("1/(x-3)")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",  # 특이점 → unverifiable
                client_is_correct=True,
                problem=problem,
            ),
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",
                client_is_correct=False,  # 클라 보고가 반대여도 mismatch 0이어야 함
                problem=problem,
            ),
        ]
        report = build_report(records)
        assert report.verdict_counts["unverifiable"] == 2
        assert report.client_grade_mismatch_count == 0
        assert report.verifiable_count == 2
        assert report.not_derivable_count == 0

    def test_unverifiable_not_downgraded_to_fail(self) -> None:
        """unverifiable은 verdict_counts에서 fail 버킷으로 새지 않는다(별도 키로 집계)."""
        problem = _problem(conditions=[_cond("1/(x-3)")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",
                client_is_correct=True,
                problem=problem,
            )
        ]
        report = build_report(records)
        assert report.verdict_counts["fail"] == 0
        assert report.verdict_counts["unverifiable"] == 1

    def test_not_derivable_and_unverifiable_are_disjoint_buckets(self) -> None:
        """비파생(재료 없음)과 unverifiable(검증기 결과)은 겹치지 않는 별개 분모."""
        derivable_but_unverifiable = _problem(conditions=[_cond("1/(x-3)")], answer="3")
        non_derivable = _problem(conditions=[_cond("2*y - 6")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",
                client_is_correct=True,
                problem=derivable_but_unverifiable,
            ),
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",
                client_is_correct=True,
                problem=non_derivable,
            ),
        ]
        report = build_report(records)
        assert report.total_attempts == 2
        assert report.not_derivable_count == 1
        assert report.verifiable_count == 1
        assert report.verdict_counts["unverifiable"] == 1

    def test_client_is_correct_none_excluded_from_mismatch_but_counted_verifiable(self) -> None:
        """client_is_correct가 None(레거시 미채점)이면 mismatch 대상에서 제외되나 verdict는 집계."""
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",  # pass
                client_is_correct=None,
                problem=problem,
            )
        ]
        report = build_report(records)
        assert report.verifiable_count == 1
        assert report.verdict_counts["pass"] == 1
        assert report.client_grade_mismatch_count == 0

    def test_zero_verifiable_denominator_is_not_bare_zero(self) -> None:
        """분모(verifiable_count)가 0이면 rate 프로퍼티는 None(0%로 위장 금지)."""
        problem = _problem(conditions=[_cond("2*y - 6")], answer="3")  # 비파생
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",
                client_is_correct=True,
                problem=problem,
            )
        ]
        report = build_report(records)
        assert report.verifiable_count == 0
        assert report.mismatch_rate is None
        assert report.unverifiable_rate is None
        rendered = render_report(report)
        assert "측정 불가" in rendered

    def test_mismatch_zero_with_positive_denominator_shows_denominator(self) -> None:
        """acceptance④ 리터럴 문구 — 검산 가능 표본 N건 중 0건(분모 없는 '0건' 금지)."""
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(),
                student_answer="3",  # pass, 클라도 True → mismatch 0
                client_is_correct=True,
                problem=problem,
            )
        ]
        report = build_report(records)
        assert report.client_grade_mismatch_count == 0
        assert report.verifiable_count == 1
        rendered = render_report(report)
        assert "검산 가능 표본 1건 중 0건" in rendered

    def test_report_to_json_roundtrip(self) -> None:
        problem = _problem(conditions=[_cond("2*x - 6")], answer="3")
        records = [
            AttemptRecord(
                attempt_id=uuid.uuid4(), student_answer="3", client_is_correct=True, problem=problem
            ),
            AttemptRecord(
                attempt_id=uuid.uuid4(), student_answer="5", client_is_correct=True, problem=problem
            ),
        ]
        report = build_report(records)
        payload = report_to_json(report)
        assert payload["total_attempts"] == 2
        assert payload["client_grade_mismatch_count"] == 1  # 두 번째는 fail인데 클라는 True
        assert payload["mismatch_rate"] == pytest.approx(0.5)


# ──────────────────────────────────────────────────────────────────────────
# acceptance③ — submit_attempt BKT 입력 불변 동결(소스 레벨 구조 테스트)
# ──────────────────────────────────────────────────────────────────────────
class TestSubmitAttemptUnchanged:
    """이 태스크는 api/me.py를 건드리지 않는다 — 소스 레벨로 그 사실과 BKT 입력 불변을 동결."""

    def test_verify_answer_not_wired_into_live_path(self) -> None:
        """`api/me.py`가 shadow 채점기(`verify_answer`)를 import/사용하지 않음(라이브 미배선)."""
        source = inspect.getsource(api_me)
        assert "verify_answer" not in source
        assert "attempt_grading_shadow_report" not in source

    def test_mastery_propagation_still_takes_client_is_correct(self) -> None:
        """두 mastery 전파 콜사이트가 여전히 body.is_correct를 그대로 넘김(권위 이관 아님)."""
        submit_source = inspect.getsource(api_me.submit_attempt)
        concept_call = re.search(
            r"record_problem_attempt_mastery\(\s*session,\s*user\.user_id,\s*"
            r"body\.problem_id,\s*body\.is_correct\s*\)",
            submit_source,
        )
        skill_call = re.search(
            r"record_problem_attempt_skill_mastery\(\s*session,\s*user\.user_id,\s*"
            r"body\.problem_id,\s*body\.is_correct\s*\)",
            submit_source,
        )
        assert concept_call is not None, "개념 숙달 전파 콜사이트가 body.is_correct를 넘기지 않음"
        assert skill_call is not None, "스킬 숙달 전파 콜사이트가 body.is_correct를 넘기지 않음"


# ──────────────────────────────────────────────────────────────────────────
# acceptance⑤ — 변별력 discriminating 테스트(실 PostgreSQL 필요)
# ──────────────────────────────────────────────────────────────────────────
_SECRET_SETTINGS = Settings()


async def _pg_reachable() -> bool:
    engine = create_async_engine(_SECRET_SETTINGS.database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_SECRET_SETTINGS.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_id: uuid.UUID, problem_id: uuid.UUID) -> None:
    """FK 순서(자식→부모): problem_attempt → problem → user_profile."""
    engine = create_async_engine(_SECRET_SETTINGS.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = :uid"), {"uid": str(user_id)}
            )
            await conn.execute(
                text("DELETE FROM problem WHERE problem_id = :pid"), {"pid": str(problem_id)}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(user_id)}
            )
    finally:
        await engine.dispose()


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
    )


def _problem_orm(pid: uuid.UUID) -> ProblemORM:
    suffix = pid.hex[:8]
    return ProblemORM.from_schema(_problem_with_id(pid, suffix))


def _problem_with_id(pid: uuid.UUID, suffix: str) -> Problem:
    return Problem(
        problem_id=pid,
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2022,
        subject=Subject.공통,
        unit_codes=[f"U-{suffix}"],
        conditions_parsed=[_cond("2*x - 6")],
        answer="3",
    )


def _attempt(
    aid: uuid.UUID,
    uid: uuid.UUID,
    pid: uuid.UUID,
    *,
    student_answer: str,
    is_correct: bool,
) -> ProblemAttempt:
    return ProblemAttempt(
        attempt_id=aid,
        user_id=uid,
        problem_id=pid,
        student_answer=student_answer,
        is_correct=is_correct,
        ended_at=None,
    )


@pytest.mark.integration
class TestDiscriminatingMismatchCounter:
    """acceptance⑤ — 의도적 불일치 주입 → 카운터 실측 증가 → 복원 → 원복 실측(변별력 증명).

    단일 이벤트 루프 내에서 전 과정을 `await`한다(asyncio_mode=auto가 이 `async def` 테스트를
    그대로 코루틴으로 실행) — 헬퍼별로 `asyncio.run()`을 반복 호출하면 각 호출이 *새 이벤트
    루프*를 열어, 먼저 만든 엔진의 커넥션 풀이 죽은 루프에 바인딩된 채 재사용되며
    "Event loop is closed"/"attached to a different loop"로 깨진다(`db/session.py`
    `db_disable_pool` 독스트링이 경고하는 바로 그 실패 모드).
    """

    async def test_mismatch_counter_rises_and_falls_with_injected_disagreement(self) -> None:
        if not await _pg_reachable():
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀(WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        pid = uuid.uuid4()
        aid1 = uuid.uuid4()
        aid2 = uuid.uuid4()

        try:
            # 1. 사용자 + 검산 가능 문항(2*x-6=0, 정답 x=3) 시딩.
            await _add_all(_user(uid), _problem_orm(pid))

            # 2. 정상 attempt(학생 답 3=정답, 클라도 True → 서버판정 pass, 불일치 0).
            await _add_all(_attempt(aid1, uid, pid, student_answer="3", is_correct=True))

            engine = create_async_engine(_SECRET_SETTINGS.database_url)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)

                async def _report() -> object:
                    async with sm() as session:
                        records = await fetch_attempt_records(session, user_id=uid)
                    return build_report(records)

                report_before = await _report()
                assert report_before.verifiable_count == 1
                assert report_before.client_grade_mismatch_count == 0

                # 3. 의도적으로 어긋난 attempt 주입: 학생 답 3(=정답, 서버판정 pass)인데
                #    클라는 is_correct=False로 오보고 → 불일치 1건 발생해야 함.
                await _add_all(_attempt(aid2, uid, pid, student_answer="3", is_correct=False))
                report_injected = await _report()
                assert report_injected.verifiable_count == 2
                assert (
                    report_injected.client_grade_mismatch_count
                    == report_before.client_grade_mismatch_count + 1
                ), "의도적으로 주입한 불일치가 카운터에 반영되지 않음(변별력 없음)"

                # 4. 주입한 attempt 제거 → 원복 실측(같은 값으로 돌아옴).
                async with sm() as session:
                    await session.execute(
                        text("DELETE FROM problem_attempt WHERE attempt_id = :aid"),
                        {"aid": str(aid2)},
                    )
                    await session.commit()

                report_restored = await _report()
                assert (
                    report_restored.client_grade_mismatch_count
                    == report_before.client_grade_mismatch_count
                )
                assert report_restored.verifiable_count == report_before.verifiable_count
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid, pid)
