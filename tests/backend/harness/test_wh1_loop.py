"""WH-1 튜터링 턴 루프 골격(`harness/wh1_loop.py`) — 단위(hermetic·순수·결정론).

§3 도구 8종 디스패치 + §3.4/§2.2 불변식(end_turn만 발화·verify 의무·ε-탐색·증거 게이트·예산)을
`ScriptedTutorPolicy`로 결정론 검증한다(DB·async-DB·LLM 불요 — 작업 메모리 in-memory). 순수 도구
(`diagnose`·`curate`·`plan_probe`·`verify_solution`·개입 발화 결선)와의 결선을 확인한다.

**정직 스코프**: 영속(curate_hypothesis/log_evidence 스토어·BKT 커밋)·LLM 정책·fast path는 후속 —
본 테스트는 순수 루프 드라이버 + 불변식만 검증한다.
"""

from __future__ import annotations

import asyncio

import pytest

from whymath_backend.harness.wh1_loop import (
    Action,
    CurateHypothesisAction,
    EndTurnAction,
    LogEvidenceAction,
    MatchMisconceptionAction,
    QueryCurriculumAction,
    ReadStateAction,
    ScriptedTutorPolicy,
    SelectProbeAction,
    VerifyStepAction,
    run_tutoring_turn,
)
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import ProbeCandidate

# diagnose가 confidence 1.0으로 잡는 실 신호(distribution-over-power).
_MATCH_TEXT = "(a+b) a² + b²"
_MID = "distribution-over-power"


def _run(actions: list[Action], **kw: object) -> object:
    return asyncio.run(run_tutoring_turn(policy=ScriptedTutorPolicy(actions), **kw))  # type: ignore[arg-type]


def _hyp(mid: str, confidence: float) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=confidence, turns_since_evidence=0, evidence_count=1
    )


def _cand(pid: str, tags: set[str], *, difficulty: float = 0.0) -> ProbeCandidate:
    return ProbeCandidate(problem_id=pid, difficulty=difficulty, misconception_tags=frozenset(tags))


class TestLoopTermination:
    def test_end_turn_terminates(self) -> None:
        """end_turn → status=ended·발화 산출·action_type 기록."""
        out = _run([EndTurnAction(action_type="격려", utterance="잘하고 있어.")])
        assert out.status == "ended"  # type: ignore[attr-defined]
        assert out.action_type == "격려"  # type: ignore[attr-defined]
        assert out.utterance == "잘하고 있어."  # type: ignore[attr-defined]

    def test_scripted_exhaustion_emits_encouragement(self) -> None:
        """스크립트 소진 → ScriptedTutorPolicy가 격려 end_turn 방출 → 종료."""
        out = _run([])
        assert out.status == "ended"  # type: ignore[attr-defined]
        assert out.action_type == "격려"  # type: ignore[attr-defined]

    def test_budget_exhausted(self) -> None:
        """예산 소진(비종료 액션만) → budget_exhausted."""
        out = _run([ReadStateAction(), ReadStateAction()], max_tool_calls=1)
        assert out.status == "budget_exhausted"  # type: ignore[attr-defined]
        assert out.tool_calls == 1  # type: ignore[attr-defined]
        assert out.utterance is None  # type: ignore[attr-defined]

    def test_invalid_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="max_tool_calls"):
            _run([], max_tool_calls=0)


class TestInternalToolsNoSpeak:
    """end_turn만 학생에게 말한다(§3.4-3) — 중간 도구는 ok=True 내부 동작·발화 0."""

    def test_match_curate_updates_working_memory(self) -> None:
        """match(diagnose)→curate(순수) → 작업 메모리 가설 세트 갱신(내부·발화 없음)."""
        out = _run(
            [
                MatchMisconceptionAction(student_text=_MATCH_TEXT),
                CurateHypothesisAction(),
                EndTurnAction(action_type="격려", utterance="ok"),
            ]
        )
        ids = {h.misconception_id for h in out.hypotheses}  # type: ignore[attr-defined]
        assert _MID in ids  # 매치→가설로 누적
        # 중간 도구는 발화를 만들지 않음 — 발화는 end_turn(격려)만.
        assert out.utterance == "ok"  # type: ignore[attr-defined]

    def test_read_and_query_are_internal_ok(self) -> None:
        """read_student_state·query_curriculum → ok=True 내부 기록."""
        out = _run(
            [
                ReadStateAction(node_ids=["HIGH-ALG-001"]),
                QueryCurriculumAction(node_id="HIGH-ALG-001", relation="선수"),
                EndTurnAction(action_type="격려", utterance="ok"),
            ]
        )
        kinds = {(r.kind, r.ok) for r in out.trace}  # type: ignore[attr-defined]
        assert ("read_student_state", True) in kinds
        assert ("query_curriculum", True) in kinds


class TestVerifyObligation:
    """풀이 단계 제출 턴은 verify_step 호출 의무(§3.1·§3.4-1)."""

    def test_end_turn_rejected_without_verify(self) -> None:
        """has_solution_steps인데 verify 미호출 → end_turn 거부 → 예산 소진 종료."""
        out = _run(
            [EndTurnAction(action_type="질문", utterance="왜 그렇게 했어?")],
            has_solution_steps=True,
            max_tool_calls=3,
        )
        # 첫 end_turn 거부(ok=False) + 스크립트 소진 후 격려 end_turn도 거부 → budget_exhausted.
        assert out.status == "budget_exhausted"  # type: ignore[attr-defined]
        assert any(r.kind == "end_turn" and not r.ok for r in out.trace)  # type: ignore[attr-defined]

    def test_end_turn_passes_after_verify(self) -> None:
        """verify_step 호출 후 end_turn 통과(unverifiable이어도 호출했으면 통과)."""
        out = _run(
            [
                VerifyStepAction(steps=["x+1", "어떤 서술형 논증"]),  # unverifiable 가능
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            has_solution_steps=True,
        )
        assert out.status == "ended"  # type: ignore[attr-defined]
        assert any(r.kind == "verify_step" and r.ok for r in out.trace)  # type: ignore[attr-defined]

    def test_verify_correct_verdict(self) -> None:
        """동치 전이 → correct 판정(내부 기록)."""
        out = _run(
            [
                VerifyStepAction(steps=["x+x", "2*x"]),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            has_solution_steps=True,
        )
        assert any(r.kind == "verify_step" and "correct" in r.detail for r in out.trace)  # type: ignore[attr-defined]

    def test_verify_incorrect_verdict(self) -> None:
        """비동치 전이 → incorrect 판정(내부 기록·학생에게 '틀렸다' 직접 노출 아님)."""
        out = _run(
            [
                VerifyStepAction(steps=["x+x", "3*x"]),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            has_solution_steps=True,
        )
        assert any(r.kind == "verify_step" and "incorrect" in r.detail for r in out.trace)  # type: ignore[attr-defined]


class TestExploreInvariant:
    """ε-탐색 강제(§2.2 규칙2) — 탐색 턴 probe는 활성 세트 밖을 겨냥해야 한다."""

    def test_exploration_turn_rejects_inside_probe(self) -> None:
        """탐색 턴(turn_index=5)인데 외부 후보 없음 → probe 거부(활용 폴백 불가)."""
        out = _run(
            [
                SelectProbeAction(candidates=[_cand("p", {_MID})], theta=0.0, outside_mids=[]),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            turn_index=5,
            initial_hypotheses=[_hyp(_MID, 0.8)],
        )
        probe_results = [r for r in out.trace if r.kind == "select_probe"]  # type: ignore[attr-defined]
        assert probe_results and not probe_results[0].ok  # 거부

    def test_exploration_turn_accepts_outside_probe(self) -> None:
        """탐색 턴 + 외부 후보 → 활성 세트 밖 겨냥 probe 수락."""
        out = _run(
            [
                SelectProbeAction(
                    candidates=[_cand("pOut", {"OUT"})], theta=0.0, outside_mids=["OUT"]
                ),
                EndTurnAction(action_type="출제", utterance=None),
            ],
            turn_index=5,
            initial_hypotheses=[_hyp(_MID, 0.8)],
        )
        probe_results = [r for r in out.trace if r.kind == "select_probe"]  # type: ignore[attr-defined]
        assert probe_results and probe_results[0].ok
        # 출제 발화는 직전 probe 문항을 참조.
        assert "pOut" in (out.utterance or "")  # type: ignore[attr-defined]

    def test_non_exploration_turn_exploits(self) -> None:
        """비탐색 턴(turn_index=1) → 최상위 가설 판별 probe 수락(외부 불요)."""
        out = _run(
            [
                SelectProbeAction(candidates=[_cand("pA", {_MID})], theta=0.0),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            turn_index=1,
            initial_hypotheses=[_hyp(_MID, 0.8)],
        )
        probe_results = [r for r in out.trace if r.kind == "select_probe"]  # type: ignore[attr-defined]
        assert probe_results and probe_results[0].ok

    def test_no_discriminating_candidate_rejected(self) -> None:
        """판별 문항 없음(비탐색 턴) → probe 거부(억지 매칭 금지)."""
        out = _run(
            [
                SelectProbeAction(candidates=[_cand("pB", {"OTHER"})], theta=0.0),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            turn_index=1,
            initial_hypotheses=[_hyp(_MID, 0.8)],
        )
        probe_results = [r for r in out.trace if r.kind == "select_probe"]  # type: ignore[attr-defined]
        assert probe_results and not probe_results[0].ok


class TestEvidenceGateAndRefutation:
    """log_evidence 게이트(§정확성 #1) + 증거→curate 반박(§2.2·§5.1)."""

    def test_log_evidence_gate(self) -> None:
        """미등록 오개념·잘못된 극성 → 거부, 유효 → 적재."""
        out = _run(
            [
                LogEvidenceAction(misconception_id="nonexistent-xyz", polarity=1),  # 미등록
                LogEvidenceAction(misconception_id=_MID, polarity=2),  # 극성 위반
                LogEvidenceAction(misconception_id=_MID, polarity=1, weight=1.0),  # 유효
                EndTurnAction(action_type="격려", utterance="ok"),
            ]
        )
        ev_results = [r for r in out.trace if r.kind == "log_evidence"]  # type: ignore[attr-defined]
        assert [r.ok for r in ev_results] == [False, False, True]
        assert len(out.evidence) == 1  # type: ignore[attr-defined]
        assert out.evidence[0].misconception_id == _MID  # type: ignore[attr-defined]

    def test_negative_evidence_refutes_hypothesis_in_curate(self) -> None:
        """반박 증거(net_support<0)면 curate가 그 가설을 archived(작업 메모리에서 제거)."""
        out = _run(
            [
                LogEvidenceAction(misconception_id=_MID, polarity=-1, weight=2.0),
                CurateHypothesisAction(),
                EndTurnAction(action_type="격려", utterance="ok"),
            ],
            initial_hypotheses=[_hyp(_MID, 0.8)],
        )
        ids = {h.misconception_id for h in out.hypotheses}  # type: ignore[attr-defined]
        assert _MID not in ids  # 반박으로 제거


class TestEndTurnUtterance:
    """end_turn 발화 산출(§3.4-3) — 질문/힌트는 누적 가설 개입 발화로 결선(#237)."""

    def test_question_derives_intervention_from_hypotheses(self) -> None:
        """질문 + 발화 미지정 → 최상위 가설의 개입 발화(반례 유도 프롬프트)."""
        out = _run(
            [EndTurnAction(action_type="질문", utterance=None)],
            initial_hypotheses=[_hyp(_MID, 0.95)],
        )
        assert out.status == "ended"  # type: ignore[attr-defined]
        # distribution-over-power 반례 어셈블이 canonical_statement를 담는다.
        assert "(a+b)" in (out.utterance or "")  # type: ignore[attr-defined]

    def test_question_neutral_when_no_hypothesis(self) -> None:
        """가설 없음 + 발화 미지정 → 중립 유도 발화(보류)."""
        out = _run([EndTurnAction(action_type="힌트", utterance=None)])
        assert out.status == "ended"  # type: ignore[attr-defined]
        assert out.utterance  # type: ignore[attr-defined]  # 비어있지 않음

    def test_explicit_utterance_wins(self) -> None:
        """명시 발화가 있으면 그대로 사용(결선 우회)."""
        out = _run(
            [EndTurnAction(action_type="질문", utterance="명시 발화")],
            initial_hypotheses=[_hyp(_MID, 0.95)],
        )
        assert out.utterance == "명시 발화"  # type: ignore[attr-defined]

    def test_encouragement_fallback_utterance(self) -> None:
        """격려 + 발화 미지정 → 격려 폴백 발화."""
        out = _run([EndTurnAction(action_type="격려", utterance=None)])
        assert out.utterance == "좋아, 지금까지 잘 하고 있어. 다음으로 가보자."  # type: ignore[attr-defined]
