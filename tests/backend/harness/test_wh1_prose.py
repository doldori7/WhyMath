"""wh1_prose(S4-04 코치 프로즈 계층) hermetic 테스트 — 라이브 LLM 0.

검증 축:
  ① 프로필 S(`classify_prose_violation`) — reason 코드별 위반 검출(전각 우회 포함)·통과.
  ② 프로필 C(`gate_policy_prose`) — 학생 등식 echo 허용·외래 등식 차단·위생 거부.
  ③ `rephrase_coach_utterance` fail-closed — 화이트리스트 밖·provider 부재/예외/타임아웃·
     게이트 거부·NO_CHANGE 전부 **원 템플릿 항등**(text가 항상 유효한 발화).
  ④ 프라이버시 — 프롬프트 캡처에 학생 원문·풀이 단계 sentinel 부재(비민감 컨텍스트만).

provider 대역은 test_rephrase.py `_FakeProvider` 미러(스크립트 응답·호출 인자 캡처).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence

import pytest
from whymath_backend.config import get_settings
from whymath_backend.harness.wh1_loop import (
    ENCOURAGE_FALLBACK_UTTERANCE,
    NEUTRAL_GUIDE_UTTERANCE,
)
from whymath_backend.harness.wh1_primary import run_wh1_primary_turn
from whymath_backend.harness.wh1_prose import (
    REASON_NO_PROVIDER,
    REASON_NOT_REPHRASABLE,
    REASON_PROSE_ANSWER_KEYWORD,
    REASON_PROSE_DIGIT,
    REASON_PROSE_EQUATION,
    REASON_PROSE_FOREIGN_EQUATION,
    REASON_PROSE_SOLUTION_ECHO,
    REASON_PROSE_TIMEOUT,
    REASON_PROSE_TOO_LONG,
    REPHRASABLE_TEMPLATES,
    classify_prose_violation,
    gate_policy_prose,
    rephrase_coach_utterance,
)
from whymath_backend.harness.wh1_shadow import Wh1HarnessShadowObservation
from whymath_backend.l3.equivalent.rephrase import (
    REASON_EMPTY,
    REASON_HYGIENE_REJECT,
    REASON_NO_CHANGE,
    REASON_PROVIDER_ERROR,
)
from whymath_backend.l3.models import GenerationResult, RoutingDecision

# 학생 원문·풀이 단계 sentinel — 프롬프트 유입 봉인용(test_wh1_primary ZZPIIZZ 관례 미러).
_STUDENT_SENTINEL = "ZZPIIZZ 학생 개인 풀이"
_STEPS = ["2x+3=7", "2x=4", "x=2"]


class _FakeProvider:
    """스크립트 응답을 순서대로 방출 + 호출 인자 캡처(프라이버시 봉인 검증용) — 네트워크 0."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.temperatures: list[float | None] = []

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
        self.prompts.append(prompt)
        self.systems.append(system)
        self.temperatures.append(temperature)
        out = self._responses[self._index] if self._index < len(self._responses) else ""
        self._index += 1
        return GenerationResult(out)


class _RaisingProvider:
    """generate가 항상 예외 — provider 장애 fail-closed 검증용."""

    async def generate(self, *args: object, **kwargs: object) -> GenerationResult:
        raise RuntimeError("provider 다운(테스트)")


class _SlowProvider:
    """timeout 예산보다 오래 걸리는 provider — 타임아웃 fail-closed 검증용."""

    async def generate(self, *args: object, **kwargs: object) -> GenerationResult:
        await asyncio.sleep(0.5)
        return GenerationResult("늦은 응답")  # pragma: no cover — 타임아웃으로 미도달


def _rephrase(utterance: str, provider: object, **overrides: object) -> object:
    """rephrase_coach_utterance 동기 래퍼 — 공통 인자 채움(테스트 가독성)."""
    kwargs: dict[str, object] = {
        "action_type": "힌트",
        "verdict": "incorrect",
        "turn_index": 1,
        "hypothesis_label": None,
        "forbidden_fragments": [_STUDENT_SENTINEL, *_STEPS],
        "provider": provider,
        "timeout_seconds": 2.0,
    }
    kwargs.update(overrides)
    return asyncio.run(rephrase_coach_utterance(utterance, **kwargs))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# ① 프로필 S — classify_prose_violation
# ──────────────────────────────────────────────────────────────────────
class TestProfileS:
    def test_clean_prose_passes(self) -> None:
        assert classify_prose_violation("방금 왜 그렇게 했는지 이유를 들려줄래?") is None

    def test_empty_rejected(self) -> None:
        assert classify_prose_violation("   ") == REASON_EMPTY

    def test_equation_rejected(self) -> None:
        assert classify_prose_violation("힌트: x=3으로 두면 어때?") == REASON_PROSE_EQUATION

    def test_fullwidth_equation_rejected(self) -> None:
        """전각 등호(＝) 우회 — NFKC 정규화가 붕괴시켜 잡는다."""
        assert classify_prose_violation("x＝삼이야") == REASON_PROSE_EQUATION

    def test_digit_rejected(self) -> None:
        """등호 없는 정답 진술("x는 3")도 숫자 금지가 구조 차단."""
        assert classify_prose_violation("x는 3이야, 잘 봐") == REASON_PROSE_DIGIT

    def test_fullwidth_digit_rejected(self) -> None:
        assert classify_prose_violation("답은 ３이지") == REASON_PROSE_DIGIT

    def test_solution_echo_rejected_despite_whitespace(self) -> None:
        """GT(학생 풀이) echo — 공백 변형 우회도 정규형 비교로 차단."""
        code = classify_prose_violation(
            "네가 쓴 ZZPIIZZ   학생 개인   풀이 부분을 보자",
            forbidden_fragments=[_STUDENT_SENTINEL],
        )
        assert code == REASON_PROSE_SOLUTION_ECHO

    def test_answer_keyword_rejected(self) -> None:
        assert classify_prose_violation("정답을 알려줄게") == REASON_PROSE_ANSWER_KEYWORD

    def test_too_long_rejected(self) -> None:
        assert classify_prose_violation("아" * 121) == REASON_PROSE_TOO_LONG

    def test_short_fragment_not_false_echo(self) -> None:
        """1자 조각은 echo 판정에서 제외 — 우연 일치 오탐 방지(_MIN_ECHO_LEN)."""
        assert classify_prose_violation("스스로 확인해 볼까?", forbidden_fragments=["스"]) is None


# ──────────────────────────────────────────────────────────────────────
# ② 프로필 C — gate_policy_prose
# ──────────────────────────────────────────────────────────────────────
class TestProfileC:
    def test_prose_without_equation_passes(self) -> None:
        assert gate_policy_prose("좋아, 다음 단계도 스스로 해보자!") is None

    def test_student_equation_echo_allowed(self) -> None:
        """학생이 쓴 등식의 echo는 정당한 코칭 — 허용."""
        code = gate_policy_prose(
            "네가 쓴 2x=4 다음이 뭘까?",
            student_material=[_STUDENT_SENTINEL, *_STEPS],
        )
        assert code is None

    def test_foreign_equation_rejected(self) -> None:
        """학생 재료에 없는 등식(LLM 날조 정답) — 거짓 정답·추가 등식의 정의라 차단."""
        code = gate_policy_prose(
            "그러니까 x=9가 되는 거야",
            student_material=[_STUDENT_SENTINEL, *_STEPS],
        )
        assert code == REASON_PROSE_FOREIGN_EQUATION

    def test_fragment_boundary_not_false_allowed(self) -> None:
        """조각 경계 연접("…x=" + "9…")이 우연히 외래 등식을 허용하지 않는다(§ 구분자)."""
        code = gate_policy_prose(
            "그러니까 x=9가 되는 거야", student_material=["어쩌면 x=", "9번 문제"]
        )
        assert code == REASON_PROSE_FOREIGN_EQUATION

    def test_false_arithmetic_echo_hygiene_rejected(self) -> None:
        """학생이 쓴 거짓 산술의 echo — 외래 게이트는 통과하나 위생 체인이 거른다."""
        code = gate_policy_prose(
            "네 말대로 3*4=11 이라고 하자",
            student_material=["3*4=11"],
        )
        assert code == REASON_HYGIENE_REJECT

    def test_empty_rejected(self) -> None:
        assert gate_policy_prose("") == REASON_EMPTY


# ──────────────────────────────────────────────────────────────────────
# ③ rephrase_coach_utterance — fail-closed 오케스트레이션
# ──────────────────────────────────────────────────────────────────────
class TestRephraseFailClosed:
    def test_whitelist_covers_both_templates(self) -> None:
        assert REPHRASABLE_TEMPLATES == {NEUTRAL_GUIDE_UTTERANCE, ENCOURAGE_FALLBACK_UTTERANCE}

    def test_non_whitelisted_passes_through_without_llm(self) -> None:
        """개입 프롬프트류(화이트리스트 밖) — LLM 호출 0·무변형 통과."""
        provider = _FakeProvider(["안 쓰일 응답"])
        intervention = "(a+b)^2 = a^2 + 2ab + b^2 를 다시 볼까?"
        out = _rephrase(intervention, provider)
        assert out.text == intervention  # type: ignore[attr-defined]
        assert out.rephrased is False  # type: ignore[attr-defined]
        assert out.reason_code == REASON_NOT_REPHRASABLE  # type: ignore[attr-defined]
        assert provider.prompts == []  # LLM 미호출 봉인

    def test_no_provider_keeps_template(self) -> None:
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, None)
        assert out.text == NEUTRAL_GUIDE_UTTERANCE  # type: ignore[attr-defined]
        assert out.reason_code == REASON_NO_PROVIDER  # type: ignore[attr-defined]

    def test_provider_exception_keeps_template(self) -> None:
        out = _rephrase(ENCOURAGE_FALLBACK_UTTERANCE, _RaisingProvider())
        assert out.text == ENCOURAGE_FALLBACK_UTTERANCE  # type: ignore[attr-defined]
        assert out.reason_code == REASON_PROVIDER_ERROR  # type: ignore[attr-defined]

    def test_timeout_keeps_template(self) -> None:
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, _SlowProvider(), timeout_seconds=0.05)
        assert out.text == NEUTRAL_GUIDE_UTTERANCE  # type: ignore[attr-defined]
        assert out.reason_code == REASON_PROSE_TIMEOUT  # type: ignore[attr-defined]

    def test_leaky_output_gated_to_template_with_raw(self) -> None:
        """정답 유출 응답 주입 → 게이트 거부·원 템플릿 유지·raw_output 사후 분석 봉인."""
        leak = "정답은 x=3이야."
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, _FakeProvider([leak]))
        assert out.text == NEUTRAL_GUIDE_UTTERANCE  # type: ignore[attr-defined]
        assert out.reason_code == REASON_PROSE_EQUATION  # type: ignore[attr-defined]
        assert out.raw_output == leak  # type: ignore[attr-defined]

    def test_identical_output_is_no_change(self) -> None:
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, _FakeProvider([NEUTRAL_GUIDE_UTTERANCE]))
        assert out.rephrased is False  # type: ignore[attr-defined]
        assert out.reason_code == REASON_NO_CHANGE  # type: ignore[attr-defined]

    def test_clean_rephrase_succeeds(self) -> None:
        prose = "방금 그 단계, 어떤 생각으로 그렇게 풀었는지 말해줄래?"
        provider = _FakeProvider([prose])
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, provider)
        assert out.text == prose  # type: ignore[attr-defined]
        assert out.rephrased is True  # type: ignore[attr-defined]
        assert provider.temperatures == [0.7]  # 실측 최적 온도 배선

    def test_gt_echo_output_gated(self) -> None:
        """LLM이 학생 풀이 단계를 흘리면(숫자·등호 게이트가 먼저 잡아도) 템플릿 유지."""
        out = _rephrase(NEUTRAL_GUIDE_UTTERANCE, _FakeProvider(["네 풀이 2x=4 를 보면 알 수 있지"]))
        assert out.text == NEUTRAL_GUIDE_UTTERANCE  # type: ignore[attr-defined]
        assert out.rephrased is False  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────
# ④ 프라이버시 — 프롬프트에 학생 원문·풀이 단계 미유입
# ──────────────────────────────────────────────────────────────────────
class TestPromptPrivacy:
    def test_student_material_never_in_prompt(self) -> None:
        """forbidden_fragments(학생 원문·단계)는 게이트 입력일 뿐 프롬프트엔 절대 미유입."""
        provider = _FakeProvider(["괜찮아, 계속 이어가 보자."])
        _rephrase(ENCOURAGE_FALLBACK_UTTERANCE, provider)
        assert len(provider.prompts) == 1
        captured = provider.prompts[0] + provider.systems[0]
        assert _STUDENT_SENTINEL not in captured
        for step in _STEPS:
            assert step not in captured

    def test_prompt_carries_nonsensitive_context_only(self) -> None:
        provider = _FakeProvider(["좋아, 다음으로 넘어가 보자!"])
        _rephrase(
            ENCOURAGE_FALLBACK_UTTERANCE,
            provider,
            action_type="격려",
            verdict="correct",
            hypothesis_label="지수법칙 혼동",
        )
        prompt = provider.prompts[0]
        assert "격려" in prompt
        assert "correct" in prompt
        assert "지수법칙 혼동" in prompt
        assert ENCOURAGE_FALLBACK_UTTERANCE in prompt  # 원 발화 앵커


# ──────────────────────────────────────────────────────────────────────
# ⑤ seam 통합 — run_wh1_primary_turn 경유(플래그 ON/OFF·관측 레코드·백스톱 공존)
# ──────────────────────────────────────────────────────────────────────
_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"
_ANSWER_LEAK = "정답은 x=3이야"


def _flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """프로즈 플래그 ON — env 킬스위치 관례 + settings 캐시 무효화(test_wh1_loop 선례)."""
    monkeypatch.setenv("WHYMATH_WH1_PROSE_REPHRASE_ENABLED", "true")
    get_settings.cache_clear()


def _run_primary(provider: object, **kwargs: object) -> str | None:
    kwargs.setdefault("student_solution", "학생 개인 풀이 ZZPIIZZ")
    kwargs.setdefault("solution_steps", [])
    kwargs.setdefault("active_hypotheses", [])
    kwargs.setdefault("timeout_seconds", 5.0)
    return asyncio.run(run_wh1_primary_turn(provider=provider, **kwargs))  # type: ignore[arg-type]


def _prose_records(caplog: pytest.LogCaptureFixture) -> list[Wh1HarnessShadowObservation]:
    return [
        Wh1HarnessShadowObservation.model_validate_json(r.getMessage())
        for r in caplog.records
        if r.name == _RECORD_LOGGER
    ]


class TestPrimarySeamIntegration:
    """seam 통합 — 프로즈 계층이 발화 확정 후·톤필터 직전에만 개입한다(OFF=비트동일)."""

    def test_flag_off_serves_template_without_prose_call(self) -> None:
        """기본 OFF — 파생 템플릿 그대로 노출·프로즈 LLM 호출 0(정책 호출 1회뿐)."""
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "격려"}'])
        served = _run_primary(provider)
        assert served == ENCOURAGE_FALLBACK_UTTERANCE
        assert len(provider.prompts) == 1  # 정책 루프 1회 — 프로즈 호출 없음(비트동일 증명)

    def test_derived_template_rephrased_when_on(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ON + 파생 격려 템플릿 → 게이트 통과 프로즈로 문맥화 노출·관측 prose_rephrased=True."""
        _flag_on(monkeypatch)
        prose = "여기까지 잘 따라왔어, 다음 고비도 스스로 넘어가 보자!"
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "격려"}', prose])
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                served = _run_primary(provider)
        finally:
            get_settings.cache_clear()
        assert served == prose
        records = _prose_records(caplog)
        assert len(records) == 1
        assert records[0].prose_rephrased is True
        assert records[0].prose_reason_code is None

    def test_leaky_rephrase_gated_back_to_template(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ON + rephrase 출력에 정답 유출 주입 → 게이트가 차단·원 템플릿 노출(fail-closed)."""
        _flag_on(monkeypatch)
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "격려"}', _ANSWER_LEAK])
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                served = _run_primary(provider)
        finally:
            get_settings.cache_clear()
        assert served == ENCOURAGE_FALLBACK_UTTERANCE  # 유출 프로즈는 학생에게 닿지 않는다
        records = _prose_records(caplog)
        assert records[0].prose_rephrased is False
        assert records[0].prose_reason_code == REASON_PROSE_EQUATION

    def test_policy_foreign_equation_falls_back_deterministic(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ON + correct/무verdict 턴 정책 발화가 외래 등식(날조 정답) → None(결정론 폴백 신호)."""
        _flag_on(monkeypatch)
        provider = _FakeProvider(
            ['{"kind": "end_turn", "action_type": "질문", "utterance": "그러니까 x=9가 되는 거야"}']
        )
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                served = _run_primary(provider)
        finally:
            get_settings.cache_clear()
        assert served is None  # coach가 기존 결정론 템플릿으로 폴백
        records = _prose_records(caplog)
        assert records[0].prose_reason_code == REASON_PROSE_FOREIGN_EQUATION

    def test_policy_clean_prose_passes_gate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ON + 등식 없는 정책 자유발화 → 게이트 통과·그대로 노출(rephrase 아님)."""
        _flag_on(monkeypatch)
        msg = "방금 왜 그렇게 전개했는지 이유를 말해줄래?"
        provider = _FakeProvider(
            ['{"kind": "end_turn", "action_type": "질문", "utterance": "' + msg + '"}']
        )
        try:
            served = _run_primary(provider)
        finally:
            get_settings.cache_clear()
        assert served == msg

    def test_policy_student_echo_allowed_end_to_end(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ON + 학생이 쓴 등식 echo 발화(correct 턴) → 외래 아님·허용(오차단 없음)."""
        _flag_on(monkeypatch)
        msg = "네가 쓴 2x=4 다음이 뭘까?"
        action = '{"kind": "end_turn", "action_type": "질문", "utterance": "' + msg + '"}'
        # 첫 end_turn은 verify 의무로 재지정되므로 같은 스크립트 2회(선례 패턴).
        provider = _FakeProvider([action, action])
        try:
            served = _run_primary(provider, solution_steps=["2x+3=7", "2x=4"])
        finally:
            get_settings.cache_clear()
        assert served == msg

    def test_suppressed_leak_blocked_and_template_rephrased(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ON + 오답 턴 정책 유출 시도 → 백스톱(파생)과 프로즈 문맥화가 공존·유출 0."""
        _flag_on(monkeypatch)
        leak_action = (
            '{"kind": "end_turn", "action_type": "힌트", "utterance": "' + _ANSWER_LEAK + '"}'
        )
        prose = "방금 그 단계는 어떤 근거로 그렇게 적었는지 들려줄래?"
        provider = _FakeProvider([leak_action, leak_action, prose])
        try:
            served = _run_primary(provider, solution_steps=["x+x", "3*x"])  # incorrect 전이
        finally:
            get_settings.cache_clear()
        assert served == prose  # 파생 358 템플릿이 프로즈로 문맥화
        assert _ANSWER_LEAK not in (served or "")  # 정답 억제 불변
