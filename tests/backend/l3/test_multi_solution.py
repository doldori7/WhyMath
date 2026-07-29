"""다중 풀이 생성 파이프라인(`l3/multi_solution.py`) 테스트 — S4-10·D2 (hermetic).

검증 축(acceptance 동결):
  - **검증 실패 뱅크 유입 0**: 오답(SymPy 불통과)·판정 불가 답·incorrect 전이 주입 → 뱅크
    카운트 0 + 리포트 실패 카운트 증가(변별력 — 실패 상태에서 실패 신호).
  - approach 폐쇄 6종·중복 approach·파싱 실패의 정직 카운트.
  - 정직 플래그: unverifiable 전이 스텝은 `sympy_verified=False`로 기록(뱅크는 진행).
  - 멱등: 내용 지문 dedup — 재실행 시 `duplicates_skipped`·add 0.
  - 다중 경로 재론: 헤더 N경로·`problem_step`은 대표 1경로만.
  - 드리프트 동결(상향 import 회피의 보상): 지문·sp-id 체계·§4 등급 규칙이 whs 구현과 일치.
  - gen_meta는 `review_status="ai_estimated"` 게이팅 + **api/ 소스 결선 0**(거버넌스).
  - CLI: stdout=검수 큐 JSONL·stderr=리포트·기본 dry-run·provider 전멸 시 exit 1.

DB는 FakeSession(실사용 표면 execute/add/flush만 — `test_path_promotion.py` 선례),
LLM은 결정론 canned provider(라이브 0 — hermetic)로 검증한다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import whymath_backend
from whymath_backend.db.models.problem import Problem, ProblemStep
from whymath_backend.db.models.solution_path import SolutionPath as SolutionPathOrm
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.l3.interfaces import RecordingTraceSink
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.multi_solution import (
    AI_ESTIMATED,
    DeterministicFakeProvider,
    MultiSolutionReport,
    RunConfig,
    RunOutcome,
    SeedProblem,
    answer_equivalence_verdict,
    bank_candidates,
    content_fingerprint,
    evaluate_response,
    extract_json,
    generate_candidates,
    generation_routing_request,
    generated_path_id,
    load_seeds,
    main,
)
from whymath_backend.l3.router import Router
from whymath_backend.l3.verify_answer import AnswerVerdict
from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.schema.enums import ApproachType

_NOW = datetime(2026, 7, 29, 14, 0, 0, tzinfo=UTC)


def _seed(**overrides: Any) -> SeedProblem:
    """유효 시드 빌더 — 단일 변수·canonical 정답 x=3."""
    data: dict[str, Any] = {
        "problem_id": uuid.uuid4(),
        "question_text": "일차방정식 2*x = 6 을 푸시오.",
        "conditions": ("2*x = 6",),
        "answer_map": {"x": "3"},
    }
    data.update(overrides)
    return SeedProblem(**data)


def _solution(**overrides: Any) -> dict[str, Any]:
    """유효 후보 풀이 dict 빌더 — 전 전이 correct(동일 표현식) + 정답."""
    data: dict[str, Any] = {
        "approach": "algebraic",
        "key_insight": "식을 정리한다",
        "steps": ["(x) - (3)", "(x) - (3)"],
        "final_answer": "3",
        "educational_value": "기본 절차",
        "difficulty": "easy",
        "elegance": 3,
    }
    data.update(overrides)
    return data


def _evaluate(
    seed: SeedProblem, solutions: list[dict[str, Any]], *, comparison: str | None = "비교"
) -> tuple[list[Any], MultiSolutionReport]:
    """evaluate_response 호출 헬퍼 — (뱅크 후보, 리포트) 반환."""
    report = MultiSolutionReport()
    data: dict[str, Any] = {"solutions": solutions}
    if comparison is not None:
        data["comparison"] = comparison
    return evaluate_response(seed, data, now=_NOW, report=report), report


# ==========================================================================
# 순수 부품 — JSON 추출·최종답 동치·드리프트 동결
# ==========================================================================
class TestExtractJson:
    def test_plain_and_fenced_and_prose(self) -> None:
        """성공: 순수 JSON·코드펜스·주변 산문 전부 추출."""
        obj = {"solutions": []}
        raw = json.dumps(obj)
        assert extract_json(raw) == obj
        assert extract_json(f"```json\n{raw}\n```") == obj
        assert extract_json(f"설명입니다.\n{raw}\n감사합니다.") == obj

    def test_invalid_returns_none(self) -> None:
        """실패: JSON이 아니면 None(호출자가 parse_failures 카운트)."""
        assert extract_json("풀이를 만들 수 없습니다.") is None
        assert extract_json("[1, 2, 3]") is None  # 객체 아님


class TestAnswerEquivalence:
    def test_equivalent_forms_pass(self) -> None:
        """성공: 표기가 달라도 SymPy 동치면 pass(6/2 ≡ 3)."""
        assert answer_equivalence_verdict({"x": "3"}, {"x": "3"}).state == "pass"
        assert answer_equivalence_verdict({"x": "3"}, {"x": "6/2"}).state == "pass"

    def test_wrong_value_fails(self) -> None:
        """실패: 오답은 fail(잔차 ≠ 0 확정)."""
        assert answer_equivalence_verdict({"x": "3"}, {"x": "4"}).state == "fail"

    def test_variable_mismatch_unverifiable(self) -> None:
        """변수 집합 불일치 — pass로 위장하지 않고 unverifiable(보수)."""
        verdict = answer_equivalence_verdict({"x": "3"}, {"y": "3"})
        assert verdict.state == "unverifiable"

    def test_unparseable_generated_unverifiable(self) -> None:
        """파싱 불가 생성값 — unverifiable(verify_answer 정직성 상속)."""
        assert answer_equivalence_verdict({"x": "3"}, {"x": "abc("}).state == "unverifiable"

    def test_internal_symbol_collision_unverifiable(self) -> None:
        """내부 검산 심볼 충돌(방어) — unverifiable."""
        assert answer_equivalence_verdict({"x": "wm_ans_0"}, {"x": "3"}).state == "unverifiable"

    def test_parametric_answer_pass(self) -> None:
        """파라미터 정답(자유변수 잔차) — 고정 시드 샘플링 경로로 pass."""
        verdict = answer_equivalence_verdict({"x": "b/(2*a)"}, {"x": "b/(2*a)"})
        assert verdict.state == "pass"


class TestDriftFreeze:
    """l3→whs 상향 import 회피의 보상 — 세 규약이 whs 구현과 동일함을 기계 동결."""

    def test_fingerprint_matches_whs_solution_bank(self) -> None:
        """내용 지문 알고리즘 = `whs/solution_bank.solution_fingerprint`(정렬 canonical sha256)."""
        from whymath_backend.whs.solution_bank import solution_fingerprint

        payload = {"conditions": ["2*x = 6"], "answer": {"x": "3"}, "steps": ["a", "b"]}
        assert content_fingerprint(payload) == solution_fingerprint(payload)
        reordered = {"steps": ["a", "b"], "answer": {"x": "3"}, "conditions": ["2*x = 6"]}
        assert content_fingerprint(reordered) == solution_fingerprint(payload)

    def test_path_id_scheme_matches_promotion(self) -> None:
        """sp-id 체계 = `whs/path_promotion.solution_path_id_for` — promotion 멱등 스킵의 열쇠."""
        from whymath_backend.whs.path_promotion import solution_path_id_for

        vs_id = uuid.uuid4()
        assert generated_path_id(vs_id) == solution_path_id_for(vs_id)

    def test_bank_grade_matches_final_verdict(self) -> None:
        """뱅크 등급 규칙 = §4 `whs/verdict.final_verdict` — 뱅크 제한 도메인에서 완전 일치.

        뱅크된 후보의 grade는 final_verdict grade와 같아야 하고, 뱅크 거부는 final_verdict가
        failed(오답·틀린 과정)이거나 답 판정 불가(unverifiable)인 경우와 정확히 일치한다.
        """
        from whymath_backend.l3.multi_solution import _bank_grade
        from whymath_backend.whs.verdict import final_verdict

        step_cases = {
            "all_correct": verify_solution(["(x) - (3)", "(x) - (3)"]),
            "some_unverifiable": verify_solution(["산문 설명", "(x) - (3)"]),
            "incorrect": verify_solution(["x - 3", "x - 4"]),
        }
        for answer_state in ("pass", "fail", "unverifiable"):
            answer = AnswerVerdict(
                state=answer_state,  # type: ignore[arg-type]
                reason=None if answer_state == "pass" else "사유",
                samples_checked=1,
            )
            for steps_result in step_cases.values():
                grade = _bank_grade(answer, steps_result)
                verdict = final_verdict(answer, steps_result)
                if grade is not None:
                    assert grade.value == verdict.grade  # 뱅크 등급 = §4 등급(드리프트 0)
                else:
                    assert verdict.grade == "failed" or answer_state == "unverifiable"


# ==========================================================================
# evaluate_response — 후보별 검증 분기 전건 (뱅크 유입 0 동결 포함)
# ==========================================================================
class TestEvaluateResponse:
    def test_fully_verified_candidate_banked(self) -> None:
        """정상: 정답 + 전 전이 correct → 뱅크 대상·grade=verified·플래그 실측."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution()])
        assert report.verified_pass == 1
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.grade is WhsSolutionGrade.VERIFIED
        assert candidate.approach is ApproachType.algebraic
        assert candidate.step_flags == (False, True)  # 첫 스텝 False·유입 전이 correct만 True

    def test_unverifiable_steps_banked_with_honest_flags(self) -> None:
        """산문 스텝(unverifiable 전이) — 뱅크는 진행·grade=unverified·플래그 정직 False."""
        seed = _seed()
        candidates, report = _evaluate(
            seed, [_solution(steps=["조건을 정리한다", "x = 3"])]
        )
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.grade is WhsSolutionGrade.UNVERIFIED
        assert candidate.step_flags == (False, False)
        assert [s.sympy_verified for s in candidate.path.steps] == [False, False]
        assert report.verified_pass == 1

    def test_wrong_answer_never_banked(self) -> None:
        """실패 주입(변별력): SymPy 불통과 오답 → 뱅크 0 + answer_failed 증가."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution(final_answer="4")])
        assert candidates == []
        assert report.answer_failed == 1
        assert report.verified_pass == 0

    def test_incorrect_step_never_banked(self) -> None:
        """실패 주입(변별력): 답은 맞아도 incorrect 전이(틀린 과정) → 뱅크 0(§4 이중 체크)."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution(steps=["x - 3", "x - 4"])])
        assert candidates == []
        assert report.step_incorrect == 1

    def test_unverifiable_answer_never_banked(self) -> None:
        """판정 불가 답 — pass로 위장하지 않고 뱅크 0(answer_unverifiable 분리 카운트)."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution(final_answer={"y": "3"})])
        assert candidates == []
        assert report.answer_unverifiable == 1

    def test_invalid_approach_rejected(self) -> None:
        """approach 폐쇄 6종 밖("비유적" — 구 프롬프트 불일치 실측값) → 거부."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution(approach="비유적")])
        assert candidates == []
        assert report.approach_invalid == 1

    def test_korean_label_approach_accepted(self) -> None:
        """한글 라벨은 단일 번역표로 수용(약한 로컬 모델 방어) — enum 값으로 정규화."""
        seed = _seed()
        candidates, _ = _evaluate(seed, [_solution(approach="대수적")])
        assert len(candidates) == 1
        assert candidates[0].approach is ApproachType.algebraic

    def test_duplicate_approach_first_wins(self) -> None:
        """같은 응답 안 중복 approach — 첫 후보만 채택(다양성 취지·중복 카운트)."""
        seed = _seed()
        candidates, report = _evaluate(seed, [_solution(), _solution()])
        assert len(candidates) == 1
        assert report.duplicate_approach == 1

    def test_missing_steps_and_answer_counted(self) -> None:
        """steps·final_answer 형식 위반 — 각각 분리 카운트(조용한 통과 금지)."""
        seed = _seed()
        candidates, report = _evaluate(
            seed,
            [
                _solution(steps=[]),
                _solution(approach="backward", final_answer=""),
                "문자열 원소",  # type: ignore[list-item]
            ],
        )
        assert candidates == []
        assert report.steps_invalid == 2  # 빈 steps + 비-dict 원소
        assert report.final_answer_invalid == 1

    def test_string_answer_with_var_prefix_normalized(self) -> None:
        """`"x = 3"` 형태 문자열 답 — 자기 변수 접두를 벗겨 치환맵으로 정규화."""
        seed = _seed()
        candidates, _ = _evaluate(seed, [_solution(final_answer="x = 3")])
        assert len(candidates) == 1
        assert dict(candidates[0].final_answer_map) == {"x": "3"}

    def test_gen_meta_gated_and_sanitized(self) -> None:
        """gen_meta — review_status=ai_estimated 항상 동반·허용 밖 값은 버림·comparison 동반."""
        seed = _seed()
        candidates, _ = _evaluate(
            seed,
            [_solution(elegance=7, difficulty="brutal", key_insight="  핵심  ")],
            comparison="접근 비교",
        )
        meta = dict(candidates[0].gen_meta)
        assert meta["review_status"] == AI_ESTIMATED
        assert "elegance" not in meta  # 범위(1~5) 밖 → 버림
        assert "difficulty" not in meta  # 허용 3종 밖 → 버림
        assert meta["key_insight"] == "핵심"
        assert meta["comparison"] == "접근 비교"


# ==========================================================================
# 라우팅·생성 — 라우터 경유·provider 오류 정직 카운트·관측 기록
# ==========================================================================
class _CannedProvider:
    """고정 응답 provider — LLMProvider 표면 충족(hermetic)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(text=self._text, usage=None)


class _ExplodingProvider:
    """항상 예외 provider — 라이브 도달 불가 시나리오(침묵 폴백 금지 검증)."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        raise ConnectionError("Ollama 도달 불가")


class TestGeneration:
    def test_routing_request_routes_local_math_mid_sync(self) -> None:
        """생성 라우팅 — free 구독 기본이라 LOCAL/MATH/MID·동기(큐 불요·0원)."""
        decision = Router().route(generation_routing_request())
        assert decision.cost_tier == CostTier.LOCAL.value
        assert decision.local_family == ModelFamily.MATH.value
        assert decision.local_model == LocalModelTier.MID.value
        assert decision.mode == "sync"

    @pytest.mark.asyncio
    async def test_generate_traces_every_call(self) -> None:
        """LLM 호출 성공마다 관측 기록(파싱 성패 무관 — 비용 발생 시점 기록)."""
        seed = _seed()
        provider = _CannedProvider("JSON 아님")
        trace = RecordingTraceSink()
        report = MultiSolutionReport()
        candidates = await generate_candidates([seed], provider, trace=trace, report=report)
        assert candidates == []
        assert report.parse_failures == 1
        assert len(trace.records) == 1
        assert trace.records[0]["cost_tier"] == "local"

    @pytest.mark.asyncio
    async def test_provider_error_counted_with_type_name(self) -> None:
        """provider 예외 — 침묵 폴백 없이 카운트 + 예외 *타입명* 기록(침묵 실패 금지)."""
        seed = _seed()
        report = MultiSolutionReport()
        candidates = await generate_candidates(
            [seed], _ExplodingProvider(), trace=RecordingTraceSink(), report=report
        )
        assert candidates == []
        assert report.provider_errors == 1
        assert any("ConnectionError" in failure for failure in report.failures)

    @pytest.mark.asyncio
    async def test_verification_failure_never_reaches_bank(self) -> None:
        """실패 주입 end-to-end(변별력): 오답 응답 → 후보 0 → 뱅크 add 0(유입 0 동결)."""
        seed = _seed()
        wrong = json.dumps(
            {"solutions": [_solution(final_answer="4", steps=["조건 정리", "x = 4"])]},
            ensure_ascii=False,
        )
        report = MultiSolutionReport()
        candidates = await generate_candidates(
            [seed], _CannedProvider(wrong), trace=RecordingTraceSink(), report=report
        )
        assert candidates == []
        assert report.answer_failed == 1
        session = _BankFakeSession([], [])
        queue = await bank_candidates(
            cast(AsyncSession, session), candidates, report=report
        )
        assert session.added == []
        assert queue == []
        assert report.banked_paths == 0


# ==========================================================================
# 뱅크 적재 — FakeSession 배선(3좌석·대표 단계·멱등·게이팅)
# ==========================================================================
class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._items)


class _BankFakeSession:
    """bank_candidates가 부르는 표면만 — execute(순서대로 canned)·add·flush(id 부여)."""

    def __init__(self, vs_rows: list[Any], step_problem_ids: list[Any]) -> None:
        self._results = [_FakeResult(vs_rows), _FakeResult(step_problem_ids)]
        self.added: list[Any] = []

    async def execute(self, _stmt: Any) -> _FakeResult:
        return self._results.pop(0)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        # server_default id 시뮬레이션 — 새 VerifiedSolution 행에 id 부여(실 flush 동형).
        for obj in self.added:
            if isinstance(obj, VerifiedSolution) and obj.id is None:
                obj.id = uuid.uuid4()


async def _banked_candidates(
    seed: SeedProblem, solutions: list[dict[str, Any]]
) -> tuple[list[Any], MultiSolutionReport]:
    """평가→뱅크 대상 후보 목록 헬퍼(리포트 동반)."""
    report = MultiSolutionReport()
    candidates = evaluate_response(
        seed, {"solutions": solutions, "comparison": "비교"}, now=_NOW, report=report
    )
    return candidates, report


class TestBankCandidates:
    @pytest.mark.asyncio
    async def test_three_seats_written_with_gating(self) -> None:
        """정상: vs(전략 enum 값)+헤더(gen_meta ai_estimated)+대표 스텝 — 3좌석 배선."""
        seed = _seed()
        candidates, report = await _banked_candidates(seed, [_solution()])
        session = _BankFakeSession([], [])
        queue = await bank_candidates(cast(AsyncSession, session), candidates, report=report)

        solutions = [o for o in session.added if isinstance(o, VerifiedSolution)]
        headers = [o for o in session.added if isinstance(o, SolutionPathOrm)]
        steps = [o for o in session.added if isinstance(o, ProblemStep)]
        assert len(solutions) == 1 and len(headers) == 1 and len(steps) == 2
        # strategy_tag 승격 — 자유 텍스트가 아니라 enum 값.
        assert solutions[0].strategy_tag == ApproachType.algebraic.value
        assert solutions[0].grade is WhsSolutionGrade.VERIFIED
        assert solutions[0].solution_path["answer"] == {"x": "3"}
        # 헤더 — promotion과 같은 sp-id 체계·gen_meta 게이팅·미검수.
        header = headers[0]
        assert header.solution_path_id == generated_path_id(solutions[0].id)
        assert header.approach_type == ApproachType.algebraic.value
        assert header.gen_meta is not None
        assert header.gen_meta["review_status"] == AI_ESTIMATED
        assert header.verified_by_human is False
        # 대표 스텝 — 실측 전이 플래그(첫 False·correct 전이 True)·개념 매칭 검수 대기.
        assert sorted(s.step_order for s in steps) == [1, 2]
        assert [s.sympy_verified for s in sorted(steps, key=lambda s: s.step_order)] == [
            False,
            True,
        ]
        assert all(s.concept_node_id is None for s in steps)
        assert {s.solution_path_id for s in steps} == {header.solution_path_id}
        # 검수 큐 — 자동 적재 불가 형식·ai_estimated 검수 대상.
        assert len(queue) == 1
        assert queue[0]["queue"] == "multi_solution_generation_review"
        assert queue[0]["solution_path_id"] == header.solution_path_id
        assert report.banked_paths == 1 and report.banked_verified == 1
        assert report.ai_estimated_meta == 1

    @pytest.mark.asyncio
    async def test_second_path_same_problem_header_only(self) -> None:
        """다중 경로 재론: 같은 문제 두 경로 — 헤더 2·스텝은 대표(첫 경로)만(UNIQUE 불변)."""
        seed = _seed()
        candidates, report = await _banked_candidates(
            seed, [_solution(), _solution(approach="backward")]
        )
        assert len(candidates) == 2
        session = _BankFakeSession([], [])
        await bank_candidates(cast(AsyncSession, session), candidates, report=report)
        headers = [o for o in session.added if isinstance(o, SolutionPathOrm)]
        steps = [o for o in session.added if isinstance(o, ProblemStep)]
        assert len(headers) == 2
        assert len(steps) == 2  # 첫 경로(2스텝)만
        assert report.banked_paths == 2
        assert report.banked_header_only == 1
        assert report.banked_steps_rows == 2
        summary = report.summary()
        assert summary["problems_with_multi_approach"] == 1
        assert summary["distinct_approaches_per_problem"] == {"2": 1}

    @pytest.mark.asyncio
    async def test_legacy_steps_block_step_rows(self) -> None:
        """레거시 problem_step 선점 문제 — 헤더만 적재(클로버 금지)."""
        seed = _seed()
        candidates, report = await _banked_candidates(seed, [_solution()])
        session = _BankFakeSession([], [seed.problem_id])
        await bank_candidates(cast(AsyncSession, session), candidates, report=report)
        assert [o for o in session.added if isinstance(o, ProblemStep)] == []
        assert report.banked_paths == 1
        assert report.banked_header_only == 1

    @pytest.mark.asyncio
    async def test_idempotent_rerun_dedups_by_fingerprint(self) -> None:
        """멱등: 1차 적재분과 같은 내용 재실행 — duplicates_skipped·add 0(재적재 금지)."""
        seed = _seed()
        candidates, report = await _banked_candidates(seed, [_solution()])
        first = _BankFakeSession([], [])
        await bank_candidates(cast(AsyncSession, first), candidates, report=report)
        banked_vs = [o for o in first.added if isinstance(o, VerifiedSolution)]

        rerun_report = MultiSolutionReport()
        rerun_candidates = evaluate_response(
            seed, {"solutions": [_solution()]}, now=_NOW, report=rerun_report
        )
        second = _BankFakeSession(banked_vs, [seed.problem_id])
        queue = await bank_candidates(
            cast(AsyncSession, second), rerun_candidates, report=rerun_report
        )
        assert second.added == []
        assert queue == []
        assert rerun_report.duplicates_skipped == 1
        assert rerun_report.banked_paths == 0

    @pytest.mark.asyncio
    async def test_unverified_grade_recorded_honestly(self) -> None:
        """산문 스텝 경로 — grade=unverified 정직 기록(verified로 위장 금지·격리 축 유지)."""
        seed = _seed()
        candidates, report = await _banked_candidates(
            seed, [_solution(steps=["조건을 정리한다", "x = 3"])]
        )
        session = _BankFakeSession([], [])
        await bank_candidates(cast(AsyncSession, session), candidates, report=report)
        solutions = [o for o in session.added if isinstance(o, VerifiedSolution)]
        assert solutions[0].grade is WhsSolutionGrade.UNVERIFIED
        assert report.banked_unverified == 1
        steps = [o for o in session.added if isinstance(o, ProblemStep)]
        assert all(s.sympy_verified is False for s in steps)  # 정직 False 플래그


# ==========================================================================
# 결정론 가짜 provider — 전 파이프라인 hermetic 루프(정직 고지 동반)
# ==========================================================================
class TestFakeProviderLoop:
    @pytest.mark.asyncio
    async def test_full_loop_banks_two_grades(self) -> None:
        """가짜 provider 전 루프 — 시드당 2후보(verified+unverified)·다양성 2·고지 동반."""
        seed = _seed()
        provider = DeterministicFakeProvider.for_seeds([seed])
        trace = RecordingTraceSink()
        report = MultiSolutionReport(provider_kind="fake")
        candidates = await generate_candidates([seed], provider, trace=trace, report=report)
        assert len(candidates) == 2
        assert sorted(c.grade.value for c in candidates) == ["unverified", "verified"]
        session = _BankFakeSession([], [])
        queue = await bank_candidates(cast(AsyncSession, session), candidates, report=report)
        assert report.banked_paths == 2
        assert report.banked_verified == 1 and report.banked_unverified == 1
        assert len(queue) == 2
        summary = report.summary()
        assert summary["generation_rate"] == 1.0
        assert summary["verification_pass_rate"] == 1.0
        assert summary["distinct_approaches_per_problem"] == {"2": 1}
        # 자기답 되먹임 정직 고지(S2-02 선례) — fake 수치의 의미 한정 문구 항상 동반.
        assert "파이프라인 무결성" in summary["fake_disclosure"]

    @pytest.mark.asyncio
    async def test_unknown_prompt_raises(self) -> None:
        """미지 프롬프트 — 조용한 빈 응답 대신 명확한 오류(가짜도 침묵 실패 금지)."""
        provider = DeterministicFakeProvider.for_seeds([_seed()])
        decision = Router().route(generation_routing_request())
        with pytest.raises(LookupError):
            await provider.generate("전혀 다른 프롬프트", "sys", decision)


# ==========================================================================
# 시드 로딩 — verified 코퍼스 조인·형식 위반·발문 부재 정직 카운트
# ==========================================================================
class _SeedFakeSession:
    def __init__(self, vs_rows: list[Any], problems: list[Any]) -> None:
        self._results = [_FakeResult(vs_rows), _FakeResult(problems)]

    async def execute(self, _stmt: Any) -> _FakeResult:
        return self._results.pop(0)


def _vs_row(
    problem_id: uuid.UUID,
    *,
    payload: dict[str, Any] | None = None,
) -> VerifiedSolution:
    row = VerifiedSolution(
        problem_id=problem_id,
        grade=WhsSolutionGrade.VERIFIED,
        solution_path=(
            payload
            if payload is not None
            else {"conditions": ["2*x = 6"], "answer": {"x": "3"}, "steps": ["2*x = 6", "x = 3"]}
        ),
        strategy_tag="algebraic",
        answer="x=3",
    )
    row.id = uuid.uuid4()
    row.created_at = _NOW
    return row


def _problem(problem_id: uuid.UUID, question_text: str | None) -> Problem:
    problem = Problem()
    problem.problem_id = problem_id
    problem.question_text = question_text
    return problem


class TestLoadSeeds:
    @pytest.mark.asyncio
    async def test_seeds_joined_and_counted(self) -> None:
        """정상 시드 + 발문 부재 + 형식 위반 — 각각 채택/스킵 정직 카운트."""
        ok_id, no_question_id, malformed_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = [
            _vs_row(ok_id),
            _vs_row(no_question_id),
            _vs_row(malformed_id, payload={"steps": ["x"]}),  # conditions/answer 결측
        ]
        problems = [
            _problem(ok_id, "문제 본문"),
            _problem(no_question_id, None),
            _problem(malformed_id, "형식 위반 문제"),
        ]
        report = MultiSolutionReport()
        session = _SeedFakeSession(rows, problems)
        seeds = await load_seeds(cast(AsyncSession, session), limit=10, report=report)
        assert len(seeds) == 1
        assert seeds[0].problem_id == ok_id
        assert seeds[0].conditions == ("2*x = 6",)
        assert dict(seeds[0].answer_map) == {"x": "3"}
        assert report.seeds_total == 3
        assert report.seeds_skipped_no_question == 1
        assert report.seeds_skipped_malformed == 1
        assert any("seed_malformed" in failure for failure in report.failures)

    @pytest.mark.asyncio
    async def test_first_row_per_problem_and_limit(self) -> None:
        """문제당 첫 행만 대표·limit는 문제 수 기준."""
        problem_id = uuid.uuid4()
        other_id = uuid.uuid4()
        rows = [
            _vs_row(problem_id),
            _vs_row(problem_id, payload={"conditions": ["x = 1"], "answer": {"x": "1"}}),
            _vs_row(other_id),
        ]
        report = MultiSolutionReport()
        session = _SeedFakeSession(rows, [_problem(problem_id, "첫 문제")])
        seeds = await load_seeds(cast(AsyncSession, session), limit=1, report=report)
        assert len(seeds) == 1
        assert seeds[0].problem_id == problem_id
        assert seeds[0].answer_map == {"x": "3"}  # 첫 행(결정적 대표)의 정답
        assert report.seeds_total == 1


# ==========================================================================
# CLI — stdout/stderr 분리·기본 dry-run·provider 전멸 exit 1
# ==========================================================================
class TestCli:
    def _run_fn(self, outcome: RunOutcome) -> tuple[Any, list[RunConfig]]:
        received: list[RunConfig] = []

        async def fake(config: RunConfig) -> RunOutcome:
            received.append(config)
            return outcome

        return fake, received

    def test_dry_run_default_and_output_split(self, capsys: Any) -> None:
        """기본 dry-run — stdout 검수 큐 JSONL·stderr 리포트 JSON(mode=dry-run)·exit 0."""
        report = MultiSolutionReport()
        report.generation_calls = 1
        report.banked_paths = 1
        outcome = RunOutcome(
            report=report,
            queue_entries=[{"queue": "multi_solution_generation_review", "problem_id": "p"}],
        )
        fake, received = self._run_fn(outcome)
        assert main([], run_fn=fake) == 0
        config = received[0]
        assert config.apply is False
        assert config.fake_provider is False
        assert config.seed_scope == "verified"
        captured = capsys.readouterr()
        queue_lines = [json.loads(line) for line in captured.out.strip().splitlines()]
        assert len(queue_lines) == 1
        assert queue_lines[0]["queue"] == "multi_solution_generation_review"
        summary = json.loads(captured.err.strip())
        assert summary["mode"] == "dry-run"
        assert summary["banked_paths"] == 1

    def test_flags_passed_through(self, capsys: Any) -> None:
        """--apply·--fake-provider·--limit·--problem-ids — RunConfig로 정확 전달."""
        problem_id = uuid.uuid4()
        fake, received = self._run_fn(RunOutcome(report=MultiSolutionReport()))
        code = main(
            ["--apply", "--fake-provider", "--limit", "3", "--problem-ids", str(problem_id)],
            run_fn=fake,
        )
        assert code == 0
        config = received[0]
        assert config.apply is True
        assert config.fake_provider is True
        assert config.limit == 3
        assert config.problem_ids == (problem_id,)
        summary = json.loads(capsys.readouterr().err.strip())
        assert summary["mode"] == "apply"

    def test_invalid_problem_ids_rejected(self, capsys: Any) -> None:
        """--problem-ids 형식 위반 — argparse 오류(exit 2·실행 없음)."""
        fake, received = self._run_fn(RunOutcome(report=MultiSolutionReport()))
        with pytest.raises(SystemExit) as exc_info:
            main(["--problem-ids", "not-a-uuid"], run_fn=fake)
        assert exc_info.value.code == 2
        assert received == []

    def test_total_provider_failure_exits_nonzero(self, capsys: Any) -> None:
        """provider 전멸(전 호출 오류) — '0건 통과' 위장 금지·측정 실패로 exit 1."""
        report = MultiSolutionReport()
        report.generation_calls = 2
        report.provider_errors = 2
        report.failures = ["provider_error problem=p: ConnectError: ..."]
        fake, _ = self._run_fn(RunOutcome(report=report))
        assert main([], run_fn=fake) == 1
        summary = json.loads(capsys.readouterr().err.strip())
        assert summary["provider_errors"] == 2

    def test_partial_provider_failure_exits_zero(self, capsys: Any) -> None:
        """부분 실패는 exit 0 — 측정이 일부 성립(카운트로 정직 보고)."""
        report = MultiSolutionReport()
        report.generation_calls = 2
        report.provider_errors = 1
        fake, _ = self._run_fn(RunOutcome(report=report))
        assert main([], run_fn=fake) == 0


# ==========================================================================
# 거버넌스 — 학생 대면 서빙 결선 0 (gen_meta·ai_estimated 게이팅)
# ==========================================================================
class TestServingGovernance:
    def test_gen_meta_not_referenced_in_api_sources(self) -> None:
        """api/ 소스 어디에도 gen_meta 참조 0 — 주관 메타 학생 노출 경로 없음(§4-⑥ 유보).

        누군가 gen_meta를 API에 결선하면 이 테스트가 빨간불을 낸다(게이팅 해제는 사람 검수
        절차·별도 태스크와 함께여야 한다는 신호).
        """
        api_dir = Path(whymath_backend.__file__).resolve().parent / "api"
        offenders = [
            path.name
            for path in sorted(api_dir.rglob("*.py"))
            if "gen_meta" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"gen_meta가 api/ 소스에 결선됨: {offenders}"

    def test_report_summary_zero_division_honest(self) -> None:
        """0/0 비율은 None — 빈 실행을 100% 통과로 위장하지 않는다."""
        summary = MultiSolutionReport().summary()
        assert summary["generation_rate"] is None
        assert summary["verification_pass_rate"] is None
        assert "fake_disclosure" not in summary  # live 리포트에는 고지 불요
