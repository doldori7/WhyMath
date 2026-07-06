"""LLM 발문 다양화 — 스켈레톤이 확정한 수치를 보존하며 발문만 rephrase(S2-p 후속).

스켈레톤 생성기(S2-o·LLM 0)는 발문을 소수의 한국어 템플릿 회전으로 조립한다 — 구조 다양성
(수백 조합)은 크지만 문장 표현은 단조롭다. 이 모듈은 확정된 문제의 *수치·수식·정답은 그대로
두고* 발문 문장 표현만 LLM으로 다양화한다. LLM이 수식을 못 바꾸게 **결정론 검증 게이트**로
봉인하므로, LLM 비결정성이 문제의 수학적 실체에 새는 것을 원천 차단한다.

핵심 원칙(왜 안전한가):
  1. **수치는 코드가 소유** — conditions·answer·answer_map·answer_selection·choices·difficulty·
     distractor_map은 rephrase가 건드리지 않는다(입력을 그대로 반환). 오직 `question_text`만
     LLM이 다시 쓴다. 따라서 S2-a 정확성 게이트(verify_answer+근 선택+derive-and-verify)는
     rephrase 후에도 무료로 재통과한다(재검증 대상 필드가 불변).
  2. **방정식 substring 봉인** — 스켈레톤이 발문에 박은 정확한 방정식 문자열(예 '3x^2 - 7x + 4
     = 0')을 원 발문에서 추출해, rephrase 결과에 그 문자열이 *글자·공백까지 그대로* substring으로
     남아 있는지 검사한다. 없으면 fail-closed(원문 유지). 프롬프트가 "방정식은 글자 그대로 보존"을
     명령하고, 검증이 그 준수를 결정론으로 확인한다(오탐 0).
  3. **위생 재검사** — rephrase가 새로 도입한 거짓 수치 등식('3×4=11' 등)을 위생 validator
     (`default_seed_validator`)로 다시 거른다(acceptance._evaluate_hygiene와 같은 검증기).

라우터 경유(CLAUDE.md "LLM 호출은 항상 라우터 경유"): `Router().route()`로 결정하고
`provider.generate(...)`로 위임한다. 저작 패밀리 GENERAL(qwen2.5) — rephrase는 수학 풀이가
아니라 instruction-following(문장 다양화)이라 MATH(qwen2-math)보다 GENERAL이 낫다(S2-h 논거 동형).

hermetic: provider 주입 좌석(테스트=FakeProvider). 이 환경엔 LLM이 없어 라이브 호출을 하지
않는다 — 실 다양화는 Phaiakes9에서 실 provider 주입으로 구동한다(llm_generator 라이브 핸드오프
동형). **결정론 배치와 분리**: 이 rephrase는 비결정적이라 스켈레톤 배치(`run_corpus_batch`·바이트
동일 봉인)에 넣지 않고, 그 산출물을 입력으로 받는 별도 opt-in 후처리다(harness CLI).

7계층: L3 지역. schema·동일 패키지·L3 인프라(interfaces·models·router·pregenerate validator)만
import한다(L4 import 0).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import ModelFamily, RoutingDecision, RoutingRequest
from whymath_backend.l3.pregenerate.validator import (
    SeedValidator,
    default_seed_validator,
    validate_response,
)
from whymath_backend.l3.router import Router

__all__ = ["QuestionRephraser", "RephraseOutcome", "extract_equation", "verify_numeric_invariance"]

_logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 WhyMath의 **발문 다양화 편집자**입니다. 주어진 한국어 수학 문제의
*발문 문장 표현만* 자연스럽게 다시 씁니다. 절대 규칙:

1. 문장에 포함된 **방정식·수식 문자열**(예: `3x^2 - 7x + 4 = 0`)은 글자·공백·기호까지 **그대로**
   두십시오. 계수·부호·지수를 바꾸거나 표기(^, *, 괄호)를 변형하지 마십시오.
2. 요구하는 것(큰 근/작은 근/근 등)의 **수학적 의미를 바꾸지** 마십시오.
3. 새로운 수·계산·등식을 **추가하지** 마십시오(예: "3×4=12" 같은 부연 금지).
4. 출력은 다양화된 **발문 문장 한 줄만**. 설명·따옴표·코드펜스·머리말 없이 문장만 내십시오.

같은 문제라도 어투·어순·연결어를 바꿔 표현을 다양화하되, 위 규칙을 어기면 안 됩니다."""

# 발문에서 방정식 문자열을 추출하는 정규식 — 우리 템플릿이 박는 형태(예 '3x^2 - 7x + 4 = 0'·
# '(x - 1)^2 = 2'·'x^2 = 5')를 겨냥한다. 시작은 숫자/x/여는 괄호, 중간은 수식 문자(한글 미포함이라
# 발문 자연어 경계에서 멈춘다), 끝은 '= 정수'. 우변 상수만(우리 문제는 전부 =0 또는 =q 꼴).
_EQUATION_RE = re.compile(r"[0-9x(][0-9x^()+\-*/ ]*=\s*[0-9]+")


@dataclass(frozen=True, slots=True)
class RephraseOutcome:
    """rephrase 1건 결과 — 최종 발문 + 실제 변경 여부 + 사유(fail-closed 관측).

    `text`는 항상 유효한 발문이다: rephrase가 검증을 통과하면 다양화된 문장, 실패(추출 불가·검증
    실패·provider 예외)면 **원문 그대로**(fail-closed — 비결정 오염이 수치에 새지 않음). `rephrased`
    가 False면 `reason`이 왜 원문을 유지했는지 설명한다(조용한 실패 금지).
    """

    text: str
    rephrased: bool
    reason: str | None = None


def extract_equation(question_text: str) -> str | None:
    """발문에서 방정식 문자열을 추출 — 없으면 None(rephrase 봉인 불가·fail-closed 신호).

    우리 스켈레톤 템플릿이 박은 단일 방정식을 겨냥한다. 매치가 없으면(예상 밖 형태) None을
    돌려 호출부가 rephrase를 건너뛰게 한다(수치 봉인 대상을 못 찾으면 변형하지 않는다).
    """
    match = _EQUATION_RE.search(question_text)
    return match.group(0).strip() if match is not None else None


def verify_numeric_invariance(
    rephrased_text: str,
    *,
    equation: str,
    validator: SeedValidator | None = None,
) -> str | None:
    """rephrase 결과의 수치 불변을 결정론으로 검증 — 통과=정제 문자열, 실패=None.

    ① 비어있지 않음 ② 방정식 문자열이 substring으로 그대로 보존 ③ **추가 등식 금지**(보존
    방정식을 제거한 나머지에 `=`가 없음 — 거짓 등식 주입 벡터의 구조적 봉인) ④ 위생 validator
    통과(보강). 하나라도 어기면 None(호출부가 원문 유지). LLM·DB·네트워크 0(순수 결정론).

    ③이 핵심 봉인인 이유: 위생 validator(default_seed_validator)는 한글 문장 사이에 임베디드된
    거짓 산술식('… 2+2=5 …')을 토큰화 한계로 놓친다(실측). 우리 발문은 방정식 외 `=`이 없으므로,
    보존 방정식을 뺀 나머지에 `=`가 남으면 곧 LLM이 새 등식을 주입한 것이다 — 구조로 차단한다.
    정상 rephrase는 발문에 `=`을 추가하지 않으므로(프롬프트도 명령) 거짓 거부가 없다.
    """
    text = rephrased_text.strip()
    if not text:
        return None
    if equation not in text:
        return None  # 방정식 substring 봉인 위반 — 수식이 바뀌었거나 표기 변형됨.
    if "=" in text.replace(equation, "", 1):
        return None  # 방정식 외 추가 등식 — 거짓 등식 주입 차단(구조적 봉인).
    active = validator if validator is not None else default_seed_validator()
    if validate_response(active, text) is not None:
        return None  # 위생 게이트(보강) — 격리된 거짓 수치 등식/부등식/틀린 해.
    return text


class QuestionRephraser:
    """발문 다양화기 — provider 주입·라우터 경유·수치 불변 검증(fail-closed).

    `provider`(LLMProvider)를 주입한다(테스트=FakeProvider·라이브=CompositeProvider). None이면
    표준 CompositeProvider를 지연 구성하나, 이 환경엔 LLM이 없어 라이브 호출을 하지 않는다(실
    구동은 Phaiakes9). `rephrase`는 항상 유효한 발문을 돌려준다(검증 실패 시 원문 — fail-closed).
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        temperature: float = 0.9,
        authoring_family: ModelFamily | None = ModelFamily.GENERAL,
        subscription: str = "free",
        validator: SeedValidator | None = None,
    ) -> None:
        self._provider = provider
        self._temperature = temperature
        self._authoring_family = authoring_family
        self._subscription = subscription
        self._validator = validator if validator is not None else default_seed_validator()
        self._loop: asyncio.AbstractEventLoop | None = None

    def rephrase(self, question_text: str) -> RephraseOutcome:
        """발문 1건을 다양화 — 수식 보존·위생 통과 시 정제, 아니면 원문(fail-closed)."""
        equation = extract_equation(question_text)
        if equation is None:
            return RephraseOutcome(question_text, False, "방정식 추출 실패 — 봉인 대상 부재")

        try:
            raw = self._invoke(question_text, equation)
        except Exception as error:  # noqa: BLE001 — provider 장애는 조용한 크래시 금지·원문 폴백
            _logger.warning("발문 rephrase provider 예외 — 원문 유지: %s", error)
            return RephraseOutcome(question_text, False, f"provider 예외: {error}")

        verified = verify_numeric_invariance(raw, equation=equation, validator=self._validator)
        if verified is None:
            return RephraseOutcome(question_text, False, "수치 불변 검증 실패 — 원문 유지")
        if verified == question_text:
            return RephraseOutcome(question_text, False, "출력이 원문과 동일 — 다양화 없음")
        return RephraseOutcome(verified, True, None)

    # ── LLM 호출(라우터 경유·GENERAL 저작 패밀리·지속 이벤트 루프) ────────
    def _invoke(self, question_text: str, equation: str) -> str:
        provider = self._resolve_provider()
        decision = self._decide_routing()
        prompt = _build_prompt(question_text, equation)
        return self._ensure_loop().run_until_complete(
            provider.generate(
                prompt,
                _SYSTEM_PROMPT,
                decision,
                temperature=self._temperature,
            )
        )

    def _resolve_provider(self) -> LLMProvider:
        if self._provider is None:
            # 지연 구성 — 라이브(Phaiakes9)만 도달. hermetic 테스트는 항상 주입.
            from whymath_backend.l3.providers.anthropic import AnthropicProvider
            from whymath_backend.l3.providers.composite import CompositeProvider
            from whymath_backend.l3.providers.ollama import OllamaProvider

            self._provider = CompositeProvider(local=OllamaProvider(), cloud=AnthropicProvider())
        return self._provider

    def _decide_routing(self) -> RoutingDecision:
        """라우터 결정 + 저작 패밀리 선호(GENERAL) — llm_generator._decide_routing 축소 미러.

        rephrase는 다단계 추론이 아니라 문장 다양화(instruction-following)라 requires_reasoning=
        False·난이도 easy로 라우팅한다(로컬 FAST 즉답·저비용). 로컬 FAST/MID 결정의 패밀리 축만
        GENERAL로 갈아탄다(라우터의 비용·크기·모드는 존중).
        """
        from whymath_backend.l3.models import CostTier, LocalModelTier

        request = RoutingRequest(
            task_type="generate",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription=self._subscription,
            sync=True,
        )
        decision = Router().route(request)
        if self._authoring_family is None:
            return decision
        is_local = decision.cost_tier == CostTier.LOCAL.value
        family_applicable = is_local and decision.local_model in (
            LocalModelTier.FAST.value,
            LocalModelTier.MID.value,
        )
        if not family_applicable or decision.local_family == self._authoring_family.value:
            return decision
        return RoutingDecision(
            cost_tier=decision.cost_tier,
            local_family=self._authoring_family,
            local_model=decision.local_model,
            mode=decision.mode,
            reason=f"{decision.reason} → rephrase:{self._authoring_family.value}",
            est_latency_ms=decision.est_latency_ms,
            est_cost_krw=decision.est_cost_krw,
        )

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """인스턴스 전용 지속 이벤트 루프 — provider 커넥션 풀 재사용(llm_generator 동형)."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop


def _build_prompt(question_text: str, equation: str) -> str:
    """사용자 프롬프트 — 원 발문 + 보존해야 할 방정식 문자열을 명시(Minimal context)."""
    return (
        f"다음 수학 문제의 발문을 다양화하세요.\n\n"
        f"원 발문: {question_text}\n"
        f"보존할 방정식 문자열(글자 그대로): {equation}\n\n"
        f"다양화된 발문 한 줄만 출력하세요."
    )
