"""독립 다관점 LLM 교차검증(S4-13 ②) — hermetic(스크립트 provider·라이브 호출 0).

검증 축:
  ① **독립성 강제**: 원리·시스템 프롬프트·가시 필드가 겹치거나 K<3이면 *구성 시점에* 거부.
     "같은 프롬프트 3회"는 다관점이 아니다.
  ② **생성자≠검증자**: 대상의 저작 서명이 검증자 서명과 같으면 자기승인으로 거부.
  ③ **정보 은닉**: 재구성 관점 프롬프트에 정답이 실리지 않는다(앵커링 차단이 실제로 성립).
  ④ **집계**: 만장일치 ok만 통과·결함 지목은 다수결로 덮이지 않음·판정 실패는 unclear.
  ⑤ **측정 실패 가시화**: provider 예외·JSON 파싱 실패가 'ok'로 위장되지 않는다.
  ⑥ **라우터 경유**: 직접 호출 0 — 라우터 결정(호출지점 ⑤ 자기검증 좌석)이 provider로 전달.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace

import pytest

from whymath_backend.l3.cross_verify import (
    PROBABILITY_PERSPECTIVES,
    CrossVerifier,
    IndependenceError,
    Perspective,
    ResidueSubject,
)
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    LocalModelTier,
    RoutingDecision,
)

_SUBJECT = ResidueSubject(
    problem_id="wm-finite-test",
    question_text="서로 구별되는 두 개의 주사위를 던질 때 눈의 합이 7일 확률은?",
    answer="1/6",
    answer_explanation="전체 36가지 중 6가지.",
    machine_model_ko="표본공간: 36가지.\n사건 A: 값들의 합이 7과 같다.\n확률 = 6/36.",
    machine_total=36,
    machine_favorable=6,
    authored_by="corpus:FULLY_GENERATED",
)

_RECONSTRUCT_OK = json.dumps({"total": 36, "favorable": 6})
_LABEL_OK = json.dumps({"verdict": "ok", "reason": "문제 없음"}, ensure_ascii=False)
_LABEL_DEFECT = json.dumps(
    {"verdict": "defect", "defect_class": "ambiguous_condition", "reason": "구별 여부 미명시"},
    ensure_ascii=False,
)


class ScriptedProvider:
    """관점 순서대로 응답을 방출하는 provider 대역 — LLMProvider 충족(네트워크 0)."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []
        self.decisions: list[RoutingDecision] = []

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
        self.calls.append((prompt, system))
        self.decisions.append(decision)
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return GenerationResult(out)
        return GenerationResult("응답 없음")


class RaisingProvider:
    """항상 예외를 던지는 provider 대역 — 측정 실패가 통과로 위장되지 않는지 본다."""

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
        raise RuntimeError("provider 다운(테스트)")


class RecordingSink:
    """관측 싱크 대역 — 기록 dict를 모은다(Langfuse 미사용)."""

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, fields: dict[str, object]) -> None:
        self.records.append(fields)


def _verifier(provider: object, **kwargs: object) -> CrossVerifier:
    return CrossVerifier(provider, trace=RecordingSink(), **kwargs)  # type: ignore[arg-type]


# ── ① 독립성 강제 ─────────────────────────────────────────────────────
def test_fewer_than_three_perspectives_is_rejected() -> None:
    with pytest.raises(IndependenceError, match="최소 K"):
        _verifier(ScriptedProvider([]), perspectives=PROBABILITY_PERSPECTIVES[:2])


def test_same_prompt_repeated_is_not_independent() -> None:
    """같은 프롬프트 K회는 독립이 아니다 — 원리·프롬프트가 모두 같은 복제는 거부된다."""
    base = PROBABILITY_PERSPECTIVES[1]
    clones = tuple(base for _ in range(3))
    with pytest.raises(IndependenceError, match="원리 중복"):
        _verifier(ScriptedProvider([]), perspectives=clones)


def test_same_visible_fields_is_not_independent() -> None:
    """원리·프롬프트가 달라도 *같은 정보*를 보면 같은 앵커링을 공유해 독립이 아니다."""
    a, b, c = PROBABILITY_PERSPECTIVES
    shadow = Perspective(
        principle="second_opinion",
        system_prompt="다른 문구지만 같은 정보를 본다.",
        visible_fields=b.visible_fields,  # ②와 동일 가시 집합
        render=b.render,
        judge=b.judge,
    )
    with pytest.raises(IndependenceError, match="가시 필드 집합 중복"):
        _verifier(ScriptedProvider([]), perspectives=(a, b, shadow, c))


def test_default_perspectives_have_three_distinct_principles() -> None:
    principles = {p.principle for p in PROBABILITY_PERSPECTIVES}
    prompts = {p.system_prompt for p in PROBABILITY_PERSPECTIVES}
    fields = {p.visible_fields for p in PROBABILITY_PERSPECTIVES}
    assert len(principles) == len(prompts) == len(fields) == 3


# ── ② 생성자 ≠ 검증자 ─────────────────────────────────────────────────
def test_self_approval_is_refused() -> None:
    """대상을 만든 주체가 곧 검증자면 자기승인 — 검증 자체를 거부한다."""
    verifier = _verifier(ScriptedProvider([_RECONSTRUCT_OK, _LABEL_OK, _LABEL_OK]))
    subject = replace(_SUBJECT, authored_by=verifier.signature)
    with pytest.raises(IndependenceError, match="자기승인"):
        verifier.verify(subject)


# ── ③ 정보 은닉 ───────────────────────────────────────────────────────
def test_reconstruction_prompt_hides_answer_and_model() -> None:
    """재구성 관점은 발문만 본다 — 정답·형식모델이 프롬프트에 새면 독립 재계산이 아니다."""
    provider = ScriptedProvider([_RECONSTRUCT_OK, _LABEL_OK, _LABEL_OK])
    _verifier(provider).verify(_SUBJECT)
    reconstruction_prompt = provider.calls[0][0]
    assert _SUBJECT.question_text in reconstruction_prompt
    assert _SUBJECT.answer not in reconstruction_prompt
    assert "표본공간: 36가지" not in reconstruction_prompt
    # 반증 관점은 답을 보지만 형식모델은 보지 않는다(빈틈을 모델로 메워 읽지 않게).
    falsify_prompt = provider.calls[1][0]
    assert _SUBJECT.answer in falsify_prompt
    assert "표본공간: 36가지" not in falsify_prompt


# ── ④ 집계 ────────────────────────────────────────────────────────────
def test_unanimous_ok_passes() -> None:
    result = _verifier(ScriptedProvider([_RECONSTRUCT_OK, _LABEL_OK, _LABEL_OK])).verify(_SUBJECT)
    assert result.aggregate == "ok"
    assert len(result.verdicts) == 3


def test_single_defect_beats_majority_ok() -> None:
    """결함 지목은 다수결로 덮이지 않는다(2 ok vs 1 defect → defect)."""
    result = _verifier(ScriptedProvider([_RECONSTRUCT_OK, _LABEL_DEFECT, _LABEL_OK])).verify(
        _SUBJECT
    )
    assert result.aggregate == "defect"
    assert result.defect_class == "adversarial_falsification:ambiguous_condition"


def test_reconstruction_mismatch_is_machine_judged_defect() -> None:
    """①의 판정 주체는 기계다 — LLM이 낸 숫자를 전수 열거 값과 대조한다."""
    wrong = json.dumps({"total": 21, "favorable": 3})  # 두 주사위를 구별하지 않은 흔한 오독
    result = _verifier(ScriptedProvider([wrong, _LABEL_OK, _LABEL_OK])).verify(_SUBJECT)
    assert result.aggregate == "defect"
    assert result.defect_class == "independent_reconstruction:model_mismatch"
    assert "3/21" in result.reason


def test_reconstruction_decline_is_unclear_not_ok() -> None:
    declined = json.dumps({"total": None, "favorable": None, "reason": "조건 부족"})
    result = _verifier(ScriptedProvider([declined, _LABEL_OK, _LABEL_OK])).verify(_SUBJECT)
    assert result.aggregate == "unclear"


# ── ⑤ 측정 실패 가시화 ────────────────────────────────────────────────
def test_provider_failure_is_unclear_with_exception_type() -> None:
    """provider가 죽으면 '결함 0건 통과'가 아니라 측정 실패로 남고 타입명이 기록된다."""
    result = _verifier(RaisingProvider()).verify(_SUBJECT)
    assert result.aggregate == "unclear"
    assert "RuntimeError" in result.reason


def test_unparseable_response_is_unclear() -> None:
    result = _verifier(ScriptedProvider(["JSON이 아님", _LABEL_OK, _LABEL_OK])).verify(_SUBJECT)
    assert result.aggregate == "unclear"
    assert result.verdicts[0].defect_class == "response_unparsed"


def test_unknown_verdict_label_is_unclear() -> None:
    weird = json.dumps({"verdict": "maybe", "reason": "글쎄"}, ensure_ascii=False)
    result = _verifier(ScriptedProvider([_RECONSTRUCT_OK, weird, _LABEL_OK])).verify(_SUBJECT)
    assert result.aggregate == "unclear"
    assert result.verdicts[1].defect_class == "verdict_unparsed"


# ── ⑥ 라우터 경유 ─────────────────────────────────────────────────────
def test_calls_go_through_router_self_verify_seat() -> None:
    """직접 호출 0 — 라우터가 호출지점 ⑤(자기검증) 좌석으로 결정한 값이 provider로 간다."""
    provider = ScriptedProvider([_RECONSTRUCT_OK, _LABEL_OK, _LABEL_OK])
    sink = RecordingSink()
    CrossVerifier(provider, trace=sink).verify(_SUBJECT)  # type: ignore[arg-type]
    assert len(provider.decisions) == 3
    for decision in provider.decisions:
        assert decision.cost_tier == CostTier.LOCAL.value
        assert decision.local_model == LocalModelTier.QUALITY.value
        assert decision.mode == "async"
    # 모든 LLM 호출은 관측에 남는다(Langfuse 필드 dict).
    assert len(sink.records) == 3
    assert sink.records[0]["call_site"] == "self_verify"
