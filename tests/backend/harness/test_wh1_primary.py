"""WH-1 primary(flip) 실행 좌석 단위테스트 — S1-11(발화 승격·검증 게이트·톤필터·폴백·관측 연속).

`run_wh1_primary_turn`을 `asyncio.run`으로 직접 호출하고 `_FakeProvider`(스크립트된 JSON)로 정책
결정을 제어해, 학생-대면 발화 산출·톤필터 재작성·결정론 폴백 신호(None)·관측 레코드(primary=True)
를 실 네트워크·직접 LLM 호출 0으로 검증한다(`test_wh1_shadow.py` 패턴 답습).

핵심 단언:
- 하네스가 산출한 발화가 그대로(또는 톤필터 재작성으로) 반환된다 — flip 방침 ① 발화 승격.
- **톤필터**: 금지 패턴 발화는 rewritten 텍스트로 노출·위반 사실이 레코드/로그에 남는다(KPI3).
- **폴백 신호**: 타임아웃·예산 소진·하네스 예외 → `None`(호출자 결정론 폴백) + 예외 타입명 로그.
- **검증 게이트 유지**: incorrect verdict에선 정책 명시 발화(정답 누출)가 억제된 파생 발화만 나온다.
- **관측 연속**: primary 경로도 shadow와 동일 레코드 계약으로 emit(`primary=True` 회계 분리).
- **프라이버시**: 학생 풀이 원문·발화 원문이 서버 로그(record 외 평문 로그 포함)에 새지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

import pytest
from whymath_backend.harness import wh1_primary
from whymath_backend.harness.wh1_primary import run_wh1_primary_turn
from whymath_backend.harness.wh1_shadow import Wh1HarnessShadowObservation
from whymath_backend.l3.models import GenerationResult, RoutingDecision

_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"
_PRIMARY_LOGGER = "whymath.harness.wh1_primary"

# 학생 풀이 원문 — 로그에 *절대* 새면 안 되는 프라이버시 sentinel(미성년 PII·shadow 테스트 미러).
_STUDENT_SOLUTION = "내 풀이는 (a+b)² = a² + b²로 전개했어 ZZPIIZZ"
# 정책이 실을 수 있는 정답 누출 발화 — incorrect verdict에선 학생에게 닿으면 안 된다(§3.4).
_ANSWER_LEAK = "정답은 x=3이야"


class _FakeProvider:
    """스크립트된 JSON만 돌려주는 L3 provider 대역 — 소진 시 end_turn(격려)로 종료."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return GenerationResult(out)
        return GenerationResult('{"kind": "end_turn", "action_type": "격려"}')


class _SlowProvider:
    """타임아웃 검증용 — generate가 오래 걸리는 provider 대역."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        await asyncio.sleep(1.0)
        return GenerationResult('{"kind": "end_turn", "action_type": "격려"}')


class _BoomProvider:
    """provider 장애 대역 — 정책의 안전 강등(결정론 파생 발화) 경로 검증용."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        raise ConnectionError("LLM 도달 불가(테스트)")


def _records(caplog: pytest.LogCaptureFixture) -> list[Wh1HarnessShadowObservation]:
    return [
        Wh1HarnessShadowObservation.model_validate_json(r.getMessage())
        for r in caplog.records
        if r.name == _RECORD_LOGGER
    ]


def _run(**kwargs: object) -> str | None:
    kwargs.setdefault("student_solution", _STUDENT_SOLUTION)
    kwargs.setdefault("solution_steps", [])
    kwargs.setdefault("active_hypotheses", [])
    kwargs.setdefault("timeout_seconds", 5.0)
    return asyncio.run(run_wh1_primary_turn(**kwargs))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# ① 발화 승격 — 하네스 발화가 반환되고 관측 레코드가 primary=True로 남는다
# ──────────────────────────────────────────────────────────────────────────
class TestServesHarnessUtterance:
    def test_explicit_utterance_served_and_recorded(self, caplog: pytest.LogCaptureFixture) -> None:
        # 풀이 단계 없음(verdict None) → 정책 명시 발화 존중 → 그대로 반환(톤 위반 0).
        utterance = "방금 왜 제곱을 각 항에 나눠 적었는지 이유를 말해줄래?"
        provider = _FakeProvider(
            ['{"kind": "end_turn", "action_type": "질문", "utterance": "' + utterance + '"}']
        )
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            served = _run(provider=provider, dialogue_id="d-1", turn_index=3, problem_id="p-1")
        assert served == utterance
        records = _records(caplog)
        assert len(records) == 1
        obs = records[0]
        assert obs.primary is True  # shadow(False)와 회계 분리(S1-11)
        assert obs.tone_rewritten is False
        assert obs.tone_violations == 0
        assert obs.status == "ended"
        assert obs.dialogue_id == "d-1"
        assert obs.turn_index == 3
        assert obs.problem_id == "p-1"

    def test_provider_failure_degrades_to_deterministic_safe_utterance(self) -> None:
        # provider 장애는 정책이 안전 강등(격려·utterance 없음) → 하네스 파생 결정론 발화 반환.
        # 이 발화도 하네스 게이트 통과분(정답 미포함)이라 노출 가능 — coach 폴백(None)과 구분.
        served = _run(provider=_BoomProvider())
        assert served == "좋아, 지금까지 잘 하고 있어. 다음으로 가보자."


# ──────────────────────────────────────────────────────────────────────────
# ② 톤필터 라이브 배선 — rewritten 노출 + 위반 사실 관측(KPI3)
# ──────────────────────────────────────────────────────────────────────────
class TestToneFilterWiring:
    def test_violation_rewritten_and_observed(self, caplog: pytest.LogCaptureFixture) -> None:
        bad = "그건 틀렸어. 다시 봐."
        provider = _FakeProvider(
            ['{"kind": "end_turn", "action_type": "힌트", "utterance": "' + bad + '"}']
        )
        with caplog.at_level(logging.INFO):
            served = _run(provider=provider)
        assert served is not None
        assert "틀렸" not in served  # 금지 패턴 미노출(rewritten 텍스트 노출)
        assert "다시 봐도 좋아" in served  # 권장 표현 치환(filter_tone 정본)
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].tone_rewritten is True
        assert records[0].tone_violations == 1
        # 위반 사실은 WARNING 구조화 로그(패턴 라벨만·발화 원문 미포함)로도 남는다.
        warnings = [
            r.getMessage()
            for r in caplog.records
            if r.name == _PRIMARY_LOGGER and "톤필터" in r.getMessage()
        ]
        assert len(warnings) == 1
        assert "틀렸" in warnings[0]  # 패턴 라벨(고정 카탈로그 상수)
        assert bad not in warnings[0]  # 발화 원문은 로그에 안 싣는다

    def test_clean_utterance_untouched(self) -> None:
        clean = "이 단계에서 어떤 규칙을 썼는지 스스로 설명해볼까?"
        provider = _FakeProvider(
            ['{"kind": "end_turn", "action_type": "질문", "utterance": "' + clean + '"}']
        )
        assert _run(provider=provider) == clean


# ──────────────────────────────────────────────────────────────────────────
# ③ 폴백 신호 — 타임아웃·예산 소진·하네스 예외 → None + 예외 타입명 로그
# ──────────────────────────────────────────────────────────────────────────
class TestFallbackSignals:
    def test_timeout_returns_none_with_typed_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger=_PRIMARY_LOGGER):
            served = _run(provider=_SlowProvider(), timeout_seconds=0.05)
        assert served is None  # 호출자 결정론 폴백 신호
        messages = " ".join(r.getMessage() for r in caplog.records if r.name == _PRIMARY_LOGGER)
        assert "TimeoutError" in messages  # 침묵 실패 금지 — 예외 타입명 포함

    def test_budget_exhausted_returns_none_but_still_records(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 정책이 내부 도구만 반복 → 예산 소진(발화 없음) → None. 관측 레코드는 남는다(원장 연속).
        provider = _FakeProvider(['{"kind": "read_student_state"}'] * 10)
        with caplog.at_level(logging.INFO):
            served = _run(provider=provider, max_tool_calls=3)
        assert served is None
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].status == "budget_exhausted"
        assert records[0].primary is True

    def test_harness_exception_returns_none_with_typed_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def _boom(**_kwargs: object) -> None:
            raise RuntimeError("하네스 내부 실패(테스트)")

        monkeypatch.setattr(wh1_primary, "run_tutoring_turn", _boom)
        with caplog.at_level(logging.WARNING, logger=_PRIMARY_LOGGER):
            served = _run(provider=_FakeProvider([]))
        assert served is None
        messages = " ".join(r.getMessage() for r in caplog.records if r.name == _PRIMARY_LOGGER)
        assert "RuntimeError" in messages  # 예외 타입명 로그(무타입 경고 금지)


# ──────────────────────────────────────────────────────────────────────────
# ④ 검증 게이트 유지 — verify 의무·정답 억제가 primary 발화에도 그대로 강제
# ──────────────────────────────────────────────────────────────────────────
class TestVerificationGateHeld:
    def test_incorrect_verdict_suppresses_policy_answer_leak(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 풀이 단계 제출(비동치 전이=incorrect) + 정책이 정답 누출 발화 시도 → 정책/하네스 이중
        # 방어로 명시 발화가 버려지고 파생 소크라테스 발화만 나온다(§3.4 — flip에서도 불변).
        provider = _FakeProvider(
            [
                # 정책 레벨 방어: verify 의무 pending이라 end_turn이 verify_step으로 재지정됨.
                '{"kind": "end_turn", "action_type": "힌트", "utterance": "' + _ANSWER_LEAK + '"}',
                # verify 후 재시도 — incorrect verdict라 명시 발화 억제·파생 발화로 대체.
                '{"kind": "end_turn", "action_type": "힌트", "utterance": "' + _ANSWER_LEAK + '"}',
            ]
        )
        with caplog.at_level(logging.INFO):
            served = _run(provider=provider, solution_steps=["x+x", "3*x"])
        assert served is not None
        assert _ANSWER_LEAK not in served  # 정답 억제 백스톱 통과분만 노출
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].verify_verdict == "incorrect"  # verify 의무가 실제 이행됐다(§3.1)

    def test_verify_obligation_enforced_before_utterance(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 풀이 단계 제출 턴 — 발화가 나왔다면 반드시 verify_step이 선행됐다(트레이스 검증).
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "질문"}'] * 3)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            served = _run(provider=provider, solution_steps=["2*x", "x+x"])
        assert served is not None
        records = _records(caplog)
        assert records[0].verify_verdict == "correct"


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 프라이버시 — 학생 원문·발화 원문이 서버 로그에 새지 않는다
# ──────────────────────────────────────────────────────────────────────────
class TestPrivacy:
    def test_student_solution_never_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        provider = _FakeProvider(
            [
                '{"kind": "match_misconception"}',  # 학생 원문은 정책 사적 사용(비노출)
                '{"kind": "end_turn", "action_type": "격려", "utterance": "좋아, 계속 가보자."}',
            ]
        )
        with caplog.at_level(logging.DEBUG):
            served = _run(provider=provider)
        assert served == "좋아, 계속 가보자."
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "ZZPIIZZ" not in joined  # 학생 풀이 원문 sentinel 부재(레코드·평문 로그 전부)
        assert "(a+b)" not in joined
