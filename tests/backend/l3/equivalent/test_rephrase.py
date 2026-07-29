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
    REASON_QUESTION_HYGIENE,
    QuestionRephraser,
    classify_invariance_failure,
    extract_equation,
    verify_numeric_invariance,
)
from whymath_backend.l3.models import GenerationResult, RoutingDecision

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
    ) -> GenerationResult:
        self.calls.append(
            {"prompt": prompt, "system": system, "decision": decision, "temperature": temperature}
        )
        out = self._outputs[min(self._index, len(self._outputs) - 1)]
        self._index += 1
        return GenerationResult(out)


class _RaisingProvider:
    async def generate(self, *args: object, **kwargs: object) -> GenerationResult:
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

    def test_extracts_exponential_forms(self) -> None:
        # 지수방정식 — '^' 지수 표기 포함 통째 추출(회귀 방지).
        cases = {
            "지수방정식 5^x = 25 을 만족하는 x의 값을 구하시오.": "5^x = 25",
            "2^x = 64 일 때, x의 값을 구하시오.": "2^x = 64",
        }
        for question, equation in cases.items():
            assert extract_equation(question) == equation

    def test_extracts_logarithmic_forms_with_prefix(self) -> None:
        # 로그방정식 — **log_ 접두를 포함해 통째** 추출(2026-07-07 수복). 접두를 놓쳐 'log_5 x = 2'
        # 를 '5 x = 2'로 오추출하면 프롬프트 앵커가 틀려 log rephrase 수율이 붕괴한다(라이브 실측).
        cases = {
            "로그방정식 log_5 x = 2 을 만족하는 x의 값을 구하시오.": "log_5 x = 2",
            "log_2 x = 6 일 때, x의 값을 구하시오.": "log_2 x = 6",
            "방정식 log_10 x = 3 의 해를 구하시오.": "log_10 x = 3",
        }
        for question, equation in cases.items():
            assert extract_equation(question) == equation

    def test_no_equation_returns_none(self) -> None:
        assert extract_equation("발문에 방정식이 없습니다.") is None
        # 미적분 'f(x) = 다항식' 꼴은 봉인 대상 밖(설계상 rephrase 스킵)임을 재확인.
        assert extract_equation("함수 f(x) = x^3 - 6x^2 + 9x 의 극댓값을 구하시오.") is None


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

    def test_question_hygiene_axis_wired(self) -> None:
        # S3-12 ⑤축 배선 봉인 — 수치 봉인은 지켰지만 발문 텍스트 위생(한자 주입·메타 라벨·조사
        # 오류)을 어긴 출력은 QUESTION_HYGIENE로 fail-closed된다(감사 결함 5류 ⑤ 회귀 방지).
        hanja = "이차방정식 3x^2 - 7x + 4 = 0 의 두解 중 큰 근을 구하시오."
        assert classify_invariance_failure(hanja, equation=_EQ) == REASON_QUESTION_HYGIENE
        meta = "원 발문: 이차방정식 3x^2 - 7x + 4 = 0 의 큰 근을 구하시오."
        assert classify_invariance_failure(meta, equation=_EQ) == REASON_QUESTION_HYGIENE
        josa = "이차방정식 3x^2 - 7x + 4 = 0 의 두 근의 합 10 를 구하시오."
        assert classify_invariance_failure(josa, equation=_EQ) == REASON_QUESTION_HYGIENE


class TestRephrase:
    def test_valid_rephrase_returns_diversified(self) -> None:
        out = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어 두 해 중 더 큰 값을 답하시오."
        provider = _FakeProvider([out])
        result = QuestionRephraser(provider).rephrase(_Q)
        assert result.rephrased is True
        assert result.text == out

    def test_routes_with_general_family_and_temperature(self) -> None:
        # 라우터 경유·저작 패밀리(GENERAL)·명시 온도(0.9) 전달 봉인.
        provider = _FakeProvider(["이차방정식 3x^2 - 7x + 4 = 0 의 더 큰 근을 구하라."])
        QuestionRephraser(provider, temperature=0.9).rephrase(_Q)
        call = provider.calls[0]
        assert call["temperature"] == 0.9
        decision = call["decision"]
        assert isinstance(decision, RoutingDecision)
        assert decision.local_family == "general"

    def test_default_temperature_is_live_measured_sweet_spot(self) -> None:
        # 기본 온도 0.7 봉인 — 라이브 스윕 실측(repeats 5·n=250/온도: 0.7=78.4% vs 0.9=72.8%).
        provider = _FakeProvider(["이차방정식 3x^2 - 7x + 4 = 0 의 더 큰 근을 구하라."])
        QuestionRephraser(provider).rephrase(_Q)
        assert provider.calls[0]["temperature"] == 0.7

    def test_system_prompt_is_lean_with_policy_anchor(self) -> None:
        # v3 프롬프트 봉인 — 라이브 A/B 실측(v2 5계층이 82%→57% 역행·EXTRA_EQUATION 누출·
        # attention 희석)에 따라: 정책 앵커(v2에서 유일 유효 계층)는 유지하되, 역효과 계층
        # (negative example·마크다운 섹션)의 재유입을 회귀 차단한다.
        provider = _FakeProvider(["이차방정식 3x^2 - 7x + 4 = 0 의 더 큰 근을 구하라."])
        QuestionRephraser(provider).rephrase(_Q)
        system = provider.calls[0]["system"]
        assert isinstance(system, str)
        assert "원 발문을 그대로" in system  # 정책 앵커 — 보존 불가 시 원문(NO_CHANGE 안전 흡수).
        assert "잘못된 예" not in system  # negative example 금지 — 소형 모델 시연 오독·누출(실측).
        # 방정식 리터럴은 규칙 예시 1개만 — 프롬프트 내 방정식 수가 곧 출력 누출 표면(실측).
        assert system.count("= 0") == 1

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
