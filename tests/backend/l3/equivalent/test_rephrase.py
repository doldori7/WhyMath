"""발문 다양화(S2-p 후속) — 수치 불변 검증·fail-closed·라우터 경유 단위테스트(hermetic).

라이브 LLM 0 — FakeProvider(스크립트 응답) 주입으로 rephrase 흐름을 검증한다. 핵심 봉인:
방정식 substring 보존·추가 등식 차단·위생·provider 예외 폴백, 전부 원문 fail-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from whymath_backend.l3.equivalent.rephrase import (
    REASON_EMPTY,
    REASON_EQUATION_ALTERED,
    REASON_EXTRA_EQUATION,
    REASON_HYGIENE_REJECT,
    REASON_NO_CHANGE,
    REASON_NO_EQUATION,
    REASON_PROVIDER_ERROR,
    QuestionRephraser,
    classify_invariance_failure,
    extract_equation,
    verify_numeric_invariance,
)
from whymath_backend.l3.models import RoutingDecision

_Q = "이차방정식 3x^2 - 7x + 4 = 0 의 두 근 중 큰 근을 구하시오."
_EQ = "3x^2 - 7x + 4 = 0"


class _FakeProvider:
    """스크립트 응답을 순차 방출하고 호출 인자(온도·decision)를 캡처(hermetic 좌석)."""

    def __init__(self, outputs: Sequence[str]) -> None:
        self._outputs = list(outputs)
        self._index = 0
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> str:
        self.calls.append(
            {"prompt": prompt, "system": system, "decision": decision, "temperature": temperature}
        )
        out = self._outputs[min(self._index, len(self._outputs) - 1)]
        self._index += 1
        return out


class _RaisingProvider:
    async def generate(self, *args: object, **kwargs: object) -> str:
        raise RuntimeError("provider 연결 실패")


class TestExtractEquation:
    def test_extracts_all_template_forms(self) -> None:
        cases = {
            "이차방정식 3x^2 - 7x + 4 = 0 의 두 근 중 큰 근을 구하시오.": "3x^2 - 7x + 4 = 0",
            "이차방정식 (x - 1)^2 = 2 의 두 근 중 작은 근을 구하시오.": "(x - 1)^2 = 2",
            "이차방정식 x^2 = 5 의 근을 구하시오.": "x^2 = 5",
            "이차방정식 3x^2 - 7x + 4 = 0 의 두 근 중 큰 근은?": "3x^2 - 7x + 4 = 0",
        }
        for question, equation in cases.items():
            assert extract_equation(question) == equation

    def test_no_equation_returns_none(self) -> None:
        assert extract_equation("발문에 방정식이 없습니다.") is None


class TestVerifyNumericInvariance:
    def test_preserved_equation_passes(self) -> None:
        text = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어 더 큰 해를 구하시오."
        assert verify_numeric_invariance(text, equation=_EQ) == text

    def test_missing_equation_fails(self) -> None:
        assert verify_numeric_invariance("방정식이 사라진 발문", equation=_EQ) is None

    def test_altered_coefficient_fails(self) -> None:
        # 계수 변조(4→5) → substring 봉인 위반.
        altered = "이차방정식 3x^2 - 7x + 5 = 0 큰 근은?"
        assert verify_numeric_invariance(altered, equation=_EQ) is None

    def test_notation_change_fails(self) -> None:
        # 표기 변형(^2→²) → substring 봉인 위반(글자 그대로 보존 요구).
        notated = "이차방정식 3x² - 7x + 4 = 0 큰 근은?"
        assert verify_numeric_invariance(notated, equation=_EQ) is None

    def test_injected_equation_fails(self) -> None:
        # 방정식 외 추가 등식('2+2=5') → 구조적 봉인(위생 validator 임베디드 한계 상환).
        text = "이차방정식 3x^2 - 7x + 4 = 0 (참고 2+2=5) 큰 근은?"
        assert verify_numeric_invariance(text, equation=_EQ) is None

    def test_empty_fails(self) -> None:
        assert verify_numeric_invariance("   ", equation=_EQ) is None


class TestClassifyInvarianceFailure:
    """reason-code taxonomy — 실제 게이트 코드 경로에 1:1(정직 분류)."""

    def test_pass_returns_none(self) -> None:
        text = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어 더 큰 해를 구하시오."
        assert classify_invariance_failure(text, equation=_EQ) is None

    def test_empty(self) -> None:
        assert classify_invariance_failure("   ", equation=_EQ) == REASON_EMPTY

    def test_equation_altered(self) -> None:
        altered = "이차방정식 3x^2 - 7x + 5 = 0 큰 근은?"  # 계수 변조.
        assert classify_invariance_failure(altered, equation=_EQ) == REASON_EQUATION_ALTERED

    def test_extra_equation(self) -> None:
        text = "이차방정식 3x^2 - 7x + 4 = 0 (참고 2+2=5) 큰 근은?"
        assert classify_invariance_failure(text, equation=_EQ) == REASON_EXTRA_EQUATION

    def test_hygiene_reject_false_inequality(self) -> None:
        # 추가 '='은 없으나 거짓 부등식 → EXTRA_EQUATION 통과 후 위생 게이트가 잡음.
        text = "이차방정식 3x^2 - 7x + 4 = 0, 참고로 5 < 3 인 큰 근은?"
        assert classify_invariance_failure(text, equation=_EQ) == REASON_HYGIENE_REJECT


class TestRephrase:
    def test_valid_rephrase_returns_diversified(self) -> None:
        out = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어 두 해 중 더 큰 값을 답하시오."
        provider = _FakeProvider([out])
        result = QuestionRephraser(provider).rephrase(_Q)
        assert result.rephrased is True
        assert result.text == out

    def test_routes_with_general_family_and_temperature(self) -> None:
        # 라우터 경유·저작 패밀리(GENERAL)·고온도(0.9) 전달 봉인.
        provider = _FakeProvider(["이차방정식 3x^2 - 7x + 4 = 0 의 더 큰 근을 구하라."])
        QuestionRephraser(provider, temperature=0.9).rephrase(_Q)
        call = provider.calls[0]
        assert call["temperature"] == 0.9
        decision = call["decision"]
        assert isinstance(decision, RoutingDecision)
        assert decision.local_family == "general"

    def test_altered_equation_fails_closed_to_original(self) -> None:
        altered = "이차방정식 3x^2 - 7x + 9 = 0 큰 근은?"
        provider = _FakeProvider([altered])
        result = QuestionRephraser(provider).rephrase(_Q)
        assert result.rephrased is False
        assert result.text == _Q  # 원문 유지(fail-closed)
        assert result.reason is not None
        assert result.reason_code == REASON_EQUATION_ALTERED
        assert result.raw_output == altered  # 실제 LLM 출력 보존(사후 dump).

    def test_provider_exception_fails_closed(self) -> None:
        result = QuestionRephraser(_RaisingProvider()).rephrase(_Q)
        assert result.rephrased is False
        assert result.text == _Q
        assert "provider 예외" in (result.reason or "")
        assert result.reason_code == REASON_PROVIDER_ERROR
        assert result.raw_output is None  # 예외라 출력 없음.

    def test_no_equation_skips_rephrase(self) -> None:
        # 방정식 추출 실패 → provider 호출 없이 원문(봉인 대상 부재).
        provider = _FakeProvider(["무엇이든"])
        result = QuestionRephraser(provider).rephrase("발문에 방정식이 없다.")
        assert result.rephrased is False
        assert provider.calls == []  # LLM 미호출
        assert result.reason_code == REASON_NO_EQUATION

    def test_identical_output_not_counted_as_rephrase(self) -> None:
        provider = _FakeProvider([_Q])  # 원문 그대로 반환
        result = QuestionRephraser(provider).rephrase(_Q)
        assert result.rephrased is False
        assert result.text == _Q
        assert result.reason_code == REASON_NO_CHANGE
        assert result.raw_output == _Q
