"""오개념 방향 판별 judge 단위테스트 — slice 108 (hermetic·라이브 0·결정론).

네 갈래로 검증한다:
  ① **parse_verdict**: 예/아니오/불확실 파싱·근거 추출·형식 위반→UNCERTAIN 폴백(거짓 단정 금지).
  ② **judge_filter**: FakeJudge로 `아니오`만 제거·예/불확실 유지·순서 보존·빈 입력·병렬 판정.
  ③ **LLMJudge**: Fake seam(스크립트 텍스트)→파싱→verdict·seam 예외→UNCERTAIN(never-break).
  ④ **judge_prompts**: 플레이스홀더 치환·`misconception_judge.md` 원문 정합(드리프트 가드).

coach·`diagnose`·`semantic_matches`·`combine_diagnoses`는 무변경(judge는 추가 필터 계층).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from whymath_backend.config import Settings
from whymath_backend.l3.models import LocalModelTier, ModelFamily
from whymath_backend.l3.router import Router, resolve_model
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.judge import (
    FakeJudge,
    JudgeProtocol,
    JudgeResult,
    JudgeVerdict,
    LLMJudge,
    judge_filter,
    judge_verdicts,
    parse_verdict,
)
from whymath_backend.l4.misconception.judge_prompts import (
    JUDGE_SYSTEM,
    JUDGE_USER_TEMPLATE,
    build_judge_user,
)
from whymath_backend.l4.misconception.judge_seam import _judge_routing_request
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch

# 테스트에 쓰는 실 카탈로그 오개념(doc few-shot이 쓰는 것들 — 원문 정합 가드와 일관).
_CONTINUITY = CATALOG_BY_ID["continuity-implies-differentiability"]
_COMPOSITE = CATALOG_BY_ID["composite-function-commutes"]
_LIMIT = CATALOG_BY_ID["limit-equals-function-value"]
_DIVZERO = CATALOG_BY_ID["division-by-zero"]


def _match(m: Misconception, *, confidence: float = 0.9) -> MisconceptionMatch:
    """의미 경로 매치 합성 — judge_filter 입력(semantic_similarity 채움·substring 경로 아님)."""
    return MisconceptionMatch(
        misconception=m, confidence=confidence, semantic_similarity=confidence
    )


# ──────────────────────────────────────────────────────────────────────────
# 결정론 seam — LLMJudge 배선용(스크립트 텍스트를 그대로 돌려줌, 라이브 0)
# ──────────────────────────────────────────────────────────────────────────
class _ScriptedSeam:
    """주입된 텍스트를 그대로 내는 Fake seam(LLMSeam 충족) — LLMJudge 파싱 배선 검증용."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str]] = []

    async def generate(self, prompt: str, system: str) -> str:
        self.calls.append((prompt, system))
        return self._text


class _BoomSeam:
    """항상 예외를 던지는 Fake seam — LLMJudge never-break(예외→UNCERTAIN) 검증용."""

    async def generate(self, prompt: str, system: str) -> str:
        raise RuntimeError("ollama 미도달(테스트 시뮬레이션)")


# ══════════════════════════════════════════════════════════════════════════
# ① parse_verdict — 3값 파싱·근거 추출·보수적 폴백
# ══════════════════════════════════════════════════════════════════════════
class TestParseVerdict:
    def test_parses_expresses(self) -> None:
        r = parse_verdict("판정: 예\n근거: 함의를 그대로 단정함")
        assert r.verdict is JudgeVerdict.EXPRESSES
        assert r.reason == "함의를 그대로 단정함"

    def test_parses_not_expresses(self) -> None:
        r = parse_verdict("판정: 아니오\n근거: 방향이 역(미분가능⇒연속)")
        assert r.verdict is JudgeVerdict.NOT_EXPRESSES
        assert r.reason == "방향이 역(미분가능⇒연속)"

    def test_parses_uncertain(self) -> None:
        r = parse_verdict("판정: 불확실\n근거: 두 개념을 언급만 함")
        assert r.verdict is JudgeVerdict.UNCERTAIN
        assert r.reason == "두 개념을 언급만 함"

    def test_extracts_reason_into_field(self) -> None:
        # 근거는 reason에·raw에 원문 보존.
        r = parse_verdict("판정: 예\n근거: 등치 단정")
        assert r.reason == "등치 단정"
        assert "판정: 예" in r.raw

    def test_empty_response_falls_back_uncertain(self) -> None:
        # 빈 응답 → UNCERTAIN(보수·후보 유지).
        assert parse_verdict("").verdict is JudgeVerdict.UNCERTAIN

    def test_format_violation_falls_back_uncertain(self) -> None:
        # `판정:` 라벨 없는 형식 위반 → UNCERTAIN.
        assert parse_verdict("그냥 막 적은 응답입니다").verdict is JudgeVerdict.UNCERTAIN

    def test_unknown_token_falls_back_uncertain(self) -> None:
        # `판정:` 뒤 토큰이 3값 외 → UNCERTAIN.
        assert parse_verdict("판정: 아마도\n근거: 모름").verdict is JudgeVerdict.UNCERTAIN

    def test_ambiguous_multiple_tokens_falls_back_uncertain(self) -> None:
        # 여러 판정이 동시에(이상 응답) → 모호로 보고 UNCERTAIN(거짓 단정 금지).
        assert parse_verdict("판정: 예 아니오").verdict is JudgeVerdict.UNCERTAIN

    def test_whitespace_and_single_line_tolerated(self) -> None:
        # 공백·근거 없는 한 줄도 판정만 식별되면 OK(근거는 빈 문자열).
        r = parse_verdict("  판정:   아니오  ")
        assert r.verdict is JudgeVerdict.NOT_EXPRESSES
        assert r.reason == ""

    def test_verdict_on_later_line_found(self) -> None:
        # `판정:` 줄이 첫 줄이 아니어도 관대하게 스캔(첫 매칭 줄 사용).
        r = parse_verdict("서두 텍스트\n판정: 예\n근거: 단정")
        assert r.verdict is JudgeVerdict.EXPRESSES

    def test_result_is_frozen(self) -> None:
        r = JudgeResult(verdict=JudgeVerdict.UNCERTAIN)
        with pytest.raises(FrozenInstanceError):
            r.verdict = JudgeVerdict.EXPRESSES  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════
# ② judge_filter — 아니오만 제거·예/불확실 유지·순서 보존
# ══════════════════════════════════════════════════════════════════════════
class TestJudgeFilter:
    @pytest.mark.asyncio
    async def test_removes_only_not_expresses(self) -> None:
        # m1=아니오(제거)·m2=불확실(유지)·m3=예(유지). 순서 보존.
        matches = [_match(_CONTINUITY), _match(_COMPOSITE), _match(_LIMIT)]
        judge = FakeJudge(
            {
                _CONTINUITY.id: JudgeVerdict.NOT_EXPRESSES,
                _COMPOSITE.id: JudgeVerdict.UNCERTAIN,
                _LIMIT.id: JudgeVerdict.EXPRESSES,
            }
        )
        kept = await judge_filter(matches, "미분가능하면 연속이다", judge=judge)
        assert [k.misconception.id for k in kept] == [_COMPOSITE.id, _LIMIT.id]

    @pytest.mark.asyncio
    async def test_keeps_all_when_no_not_expresses(self) -> None:
        # 예·불확실만이면 전부 유지(recall 보존).
        matches = [_match(_CONTINUITY), _match(_COMPOSITE)]
        judge = FakeJudge(default=JudgeVerdict.EXPRESSES)
        kept = await judge_filter(matches, "x", judge=judge)
        assert len(kept) == 2

    @pytest.mark.asyncio
    async def test_removes_all_when_all_not_expresses(self) -> None:
        matches = [_match(_CONTINUITY), _match(_COMPOSITE)]
        judge = FakeJudge(default=JudgeVerdict.NOT_EXPRESSES)
        kept = await judge_filter(matches, "x", judge=judge)
        assert kept == []

    @pytest.mark.asyncio
    async def test_uncertain_default_keeps(self) -> None:
        # 기본 UNCERTAIN(매핑 안 된 id) → 유지(보수).
        matches = [_match(_DIVZERO)]
        judge = FakeJudge()  # default UNCERTAIN
        kept = await judge_filter(matches, "x", judge=judge)
        assert [k.misconception.id for k in kept] == [_DIVZERO.id]

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self) -> None:
        assert await judge_filter([], "x", judge=FakeJudge()) == []

    @pytest.mark.asyncio
    async def test_order_preserved_after_partial_removal(self) -> None:
        # 중간 후보만 제거돼도 나머지 순서 유지(asyncio.gather 순서 보존 계약).
        matches = [_match(_DIVZERO), _match(_CONTINUITY), _match(_LIMIT)]
        judge = FakeJudge({_CONTINUITY.id: JudgeVerdict.NOT_EXPRESSES})
        kept = await judge_filter(matches, "x", judge=judge)
        assert [k.misconception.id for k in kept] == [_DIVZERO.id, _LIMIT.id]

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_matches(self) -> None:
        # 입력 match 객체를 변형하지 않는다(같은 객체 재배치만).
        matches = [_match(_DIVZERO), _match(_CONTINUITY)]
        original = list(matches)
        judge = FakeJudge({_CONTINUITY.id: JudgeVerdict.NOT_EXPRESSES})
        kept = await judge_filter(matches, "x", judge=judge)
        assert matches == original  # 원본 리스트 불변
        assert kept[0] is matches[0]  # 유지된 것은 동일 객체

    @pytest.mark.asyncio
    async def test_rule_based_fake_judge(self) -> None:
        # rule 콜러블로 statement 내용에 따라 판정(동적 시나리오).
        def rule(stmt: str, m: Misconception) -> JudgeVerdict:
            # "올바른"이 들어가면 아니오(제거)·아니면 예(유지).
            return JudgeVerdict.NOT_EXPRESSES if "올바른" in stmt else JudgeVerdict.EXPRESSES

        judge = FakeJudge(rule=rule)
        kept_correct = await judge_filter([_match(_CONTINUITY)], "올바른 진술", judge=judge)
        kept_wrong = await judge_filter([_match(_CONTINUITY)], "틀린 진술", judge=judge)
        assert kept_correct == []  # 올바른 → 아니오 → 제거
        assert len(kept_wrong) == 1  # 틀린 → 예 → 유지


# ══════════════════════════════════════════════════════════════════════════
# ②-b judge_verdicts — 판정 근거(verdict·reason) 보존(측정·감사 원자료)
# ══════════════════════════════════════════════════════════════════════════
class TestJudgeVerdicts:
    @pytest.mark.asyncio
    async def test_returns_pairs_in_order_with_verdicts(self) -> None:
        # 각 후보의 (match, JudgeResult)를 입력 순서 그대로 반환(verdict 보존·필터 이전 원자료).
        matches = [_match(_CONTINUITY), _match(_COMPOSITE), _match(_LIMIT)]
        judge = FakeJudge(
            {
                _CONTINUITY.id: JudgeVerdict.NOT_EXPRESSES,
                _COMPOSITE.id: JudgeVerdict.UNCERTAIN,
                _LIMIT.id: JudgeVerdict.EXPRESSES,
            }
        )
        decided = await judge_verdicts(matches, "x", judge=judge)
        assert [m.misconception.id for m, _ in decided] == [
            _CONTINUITY.id,
            _COMPOSITE.id,
            _LIMIT.id,
        ]
        assert [r.verdict for _, r in decided] == [
            JudgeVerdict.NOT_EXPRESSES,
            JudgeVerdict.UNCERTAIN,
            JudgeVerdict.EXPRESSES,
        ]

    @pytest.mark.asyncio
    async def test_preserves_reason(self) -> None:
        # JudgeResult.reason까지 보존(판정근거 캐처 — FakeJudge는 reason="fake").
        decided = await judge_verdicts([_match(_DIVZERO)], "x", judge=FakeJudge())
        assert decided[0][1].reason == "fake"

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self) -> None:
        assert await judge_verdicts([], "x", judge=FakeJudge()) == []

    @pytest.mark.asyncio
    async def test_filter_consistent_with_verdicts(self) -> None:
        # judge_filter는 judge_verdicts에서 아니오 제외와 동일(필터는 verdicts의 파생).
        matches = [_match(_DIVZERO), _match(_CONTINUITY), _match(_LIMIT)]
        judge = FakeJudge({_CONTINUITY.id: JudgeVerdict.NOT_EXPRESSES})
        decided = await judge_verdicts(matches, "x", judge=judge)
        kept = await judge_filter(matches, "x", judge=judge)
        expected = [m for m, r in decided if r.verdict is not JudgeVerdict.NOT_EXPRESSES]
        assert kept == expected


# ══════════════════════════════════════════════════════════════════════════
# ③ LLMJudge — seam 텍스트 파싱 + never-break
# ══════════════════════════════════════════════════════════════════════════
class TestLLMJudge:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(LLMJudge(seam=_ScriptedSeam("판정: 예\n근거: x")), JudgeProtocol)

    @pytest.mark.asyncio
    async def test_parses_scripted_not_expresses(self) -> None:
        seam = _ScriptedSeam("판정: 아니오\n근거: 역방향이라 다른 명제")
        judge = LLMJudge(seam=seam)
        r = await judge.judge("미분가능하면 연속", _CONTINUITY)
        assert r.verdict is JudgeVerdict.NOT_EXPRESSES
        assert r.reason == "역방향이라 다른 명제"

    @pytest.mark.asyncio
    async def test_parses_scripted_expresses(self) -> None:
        judge = LLMJudge(seam=_ScriptedSeam("판정: 예\n근거: 함의 단정"))
        r = await judge.judge("연속이면 미분가능", _CONTINUITY)
        assert r.verdict is JudgeVerdict.EXPRESSES

    @pytest.mark.asyncio
    async def test_passes_system_and_user_prompt_to_seam(self) -> None:
        # seam에 JUDGE_SYSTEM(원문)과 빌드된 USER(오개념 주입)가 전달되는지.
        seam = _ScriptedSeam("판정: 불확실\n근거: x")
        judge = LLMJudge(seam=seam)
        await judge.judge("어떤 진술", _CONTINUITY)
        assert len(seam.calls) == 1
        user_prompt, system = seam.calls[0]
        assert system == JUDGE_SYSTEM
        assert _CONTINUITY.name_kr in user_prompt
        assert _CONTINUITY.canonical_statement in user_prompt
        assert "어떤 진술" in user_prompt

    @pytest.mark.asyncio
    async def test_seam_exception_falls_back_uncertain(self) -> None:
        # never-break: seam 예외 → UNCERTAIN(후보 유지·가용성).
        judge = LLMJudge(seam=_BoomSeam())
        r = await judge.judge("x", _CONTINUITY)
        assert r.verdict is JudgeVerdict.UNCERTAIN

    @pytest.mark.asyncio
    async def test_malformed_seam_output_falls_back_uncertain(self) -> None:
        # seam이 형식 위반 텍스트를 내면 parse_verdict가 UNCERTAIN 폴백.
        judge = LLMJudge(seam=_ScriptedSeam("음 잘 모르겠네요 형식 무시"))
        r = await judge.judge("x", _CONTINUITY)
        assert r.verdict is JudgeVerdict.UNCERTAIN


# ══════════════════════════════════════════════════════════════════════════
# ④ judge_prompts — 플레이스홀더 치환 + doc 원문 정합(드리프트 가드)
# ══════════════════════════════════════════════════════════════════════════
class TestJudgePrompts:
    def test_build_user_substitutes_placeholders(self) -> None:
        out = build_judge_user("연속이면 미분가능해요", _CONTINUITY)
        assert _CONTINUITY.name_kr in out
        assert _CONTINUITY.canonical_statement in out
        assert "연속이면 미분가능해요" in out
        # 미치환 플레이스홀더가 남지 않는다.
        for ph in (
            "{misconception_name}",
            "{canonical_statement}",
            "{student_statement}",
        ):
            assert ph not in out

    def test_build_user_handles_braces_in_canonical(self) -> None:
        # canonical에 리터럴 중괄호(lim_{x→a})가 있어도 .format이 *값*으로 안전 주입.
        out = build_judge_user("극한값 항상 같다 {weird}", _LIMIT)
        assert _LIMIT.canonical_statement in out  # lim_{x→a} ... 그대로
        assert "{weird}" in out  # 학생 진술 중괄호도 리터럴 보존

    def test_user_template_has_three_placeholders(self) -> None:
        for ph in (
            "{misconception_name}",
            "{canonical_statement}",
            "{student_statement}",
        ):
            assert ph in JUDGE_USER_TEMPLATE

    def test_system_matches_doc_canonical(self) -> None:
        """**드리프트 가드**: SYSTEM 상수가 doc(`misconception_judge.md`) 원문과 핵심 문구 정합.

        doc SYSTEM 블록의 *식별 가능한 정본 문구*를 단언한다 — 코드 상수가 doc과 어긋나면(문구
        변경을 doc 먼저 하지 않으면) 깨진다(doc-first 불변·`l4/polya/prompts.py` 패턴).
        """
        assert "당신은 한국 중·고등학교 수학교육의 *진단 검증자*다." in JUDGE_SYSTEM
        # 출력 형식 — 정확히 두 줄·판정/근거(doc L81-83).
        assert "[출력 형식 — 반드시 정확히 두 줄, 다른 말 금지]" in JUDGE_SYSTEM
        assert "판정: 예|아니오|불확실" in JUDGE_SYSTEM
        # 핵심 원칙 — 방향·부정·등치(doc L65-74).
        assert "[핵심 원칙 — 방향·부정·등치를 정밀히 구분]" in JUDGE_SYSTEM
        # 보수성 — 불확실 적극 허용(doc L76-79).
        assert "[보수성 — 불확실을 적극 허용]" in JUDGE_SYSTEM

    def test_user_template_matches_doc_canonical(self) -> None:
        # doc USER 템플릿(L93-104)의 식별 문구 정합.
        assert "다음 학생 진술이 이 오개념(틀린 믿음)을 표현하는가?" in JUDGE_USER_TEMPLATE
        assert "정확히 두 줄(판정/근거)로만 답하라." in JUDGE_USER_TEMPLATE


# ──────────────────────────────────────────────────────────────────────────
# 슬109 — 파서 정확 일치 교정: 헤징 응답 오파싱(보수성 불변식 파괴)의 회귀 잠금
# ──────────────────────────────────────────────────────────────────────────
class TestParseVerdictStrictHedging:
    """전문가 리뷰가 실증한 파서 결함의 회귀 가드.

    결함: 부분 문자열 포함 검사로 "아니오라고 단정하기 어렵다"(의도=불확실·유지)가
    NOT_EXPRESSES로 오파싱돼 후보를 *제거* — 가장 위험한 방향. 교정: 정확 일치만 인정.
    """

    def test_hedged_no_falls_back_to_uncertain(self) -> None:
        # 실증 케이스: 헤징된 '아니오'는 제거가 아니라 유지(UNCERTAIN)여야 한다.
        r = parse_verdict("판정: 아니오라고 단정하기 어렵다\n근거: 모호함")
        assert r.verdict is JudgeVerdict.UNCERTAIN

    def test_hedged_yes_falls_back_to_uncertain(self) -> None:
        r = parse_verdict("판정: 예라고 보기 어려움\n근거: 모호함")
        assert r.verdict is JudgeVerdict.UNCERTAIN

    def test_trailing_period_tolerated(self) -> None:
        # 후행 문장부호는 사소한 변형으로 관용(정확 일치의 실용 완화).
        assert parse_verdict("판정: 예.\n근거: 단정").verdict is JudgeVerdict.EXPRESSES
        assert parse_verdict("판정: 아니오.\n근거: 역방향").verdict is JudgeVerdict.NOT_EXPRESSES
        assert parse_verdict("판정: 불확실.\n근거: 모호").verdict is JudgeVerdict.UNCERTAIN

    def test_modifier_suffix_falls_back_to_uncertain(self) -> None:
        # '아니오입니다'·'예요' 같은 수식 변형도 계약 밖 → UNCERTAIN(추측 금지).
        assert parse_verdict("판정: 아니오입니다").verdict is JudgeVerdict.UNCERTAIN
        assert parse_verdict("판정: 예요").verdict is JudgeVerdict.UNCERTAIN


# ──────────────────────────────────────────────────────────────────────────
# 슬108 후속 — judge 라우팅 프로파일(Settings.misconception_judge_routing) → 실모델 해석
# ──────────────────────────────────────────────────────────────────────────
class TestJudgeRoutingProfile:
    """`_judge_routing_request`가 프로파일별로 의도한 로컬 모델로 라우팅되는지 (hermetic·LLM 0).

    2026-06-15 라이브 측정에서 기본 fast_math(qwen2-math:1.5b)가 한국어 판정 형식을 못 맞춰 전부
    UNCERTAIN(FP 감소 0)이었다 — judge는 NLP 분류라 일반 instruct 모델이 적합. general_mid는
    GENERAL MID(qwen2.5:7b) 재측정용 라우팅 레버. 라우터를 실제로 태워 모델 ID를 못 박는다.
    """

    def test_fast_math_routes_to_local_fast_math_model(self) -> None:
        req = _judge_routing_request(Settings(misconception_judge_routing="fast_math"))
        decision = Router().route(req)
        assert decision.local_family == ModelFamily.MATH
        assert decision.local_model == LocalModelTier.FAST
        assert resolve_model(decision.local_family, decision.local_model) == "qwen2-math:1.5b"

    def test_general_mid_routes_to_general_mid_instruct_model(self) -> None:
        req = _judge_routing_request(Settings(misconception_judge_routing="general_mid"))
        decision = Router().route(req)
        assert decision.local_family == ModelFamily.GENERAL
        assert decision.local_model == LocalModelTier.MID
        assert resolve_model(decision.local_family, decision.local_model) == "qwen2.5:7b"

    def test_default_settings_preserve_fast_math(self) -> None:
        # env/오버라이드 없으면 현행(fast_math) 보존 — 회귀 0.
        decision = Router().route(_judge_routing_request(Settings()))
        assert resolve_model(decision.local_family, decision.local_model) == "qwen2-math:1.5b"
