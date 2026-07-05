"""실 LLM 동등문제 생성기(S2-e `llm_generator.py`) — hermetic 단위·통합(FakeProvider·라이브 0).

FakeProvider(스크립트된 JSON)로 생성기 계약을 검증한다 — 실 네트워크·직접 LLM 호출 0.
검증 축:
  ① 정상 JSON → CandidateProblem 조립(source_type 자체생성·provenance WHYMATH_GENERATED·
     conditions/answer_map 정합).
  ② 그 후보가 S2-a 게이트 통과(evaluate_equivalent_candidate accepted=True) — 생성기→게이트 결선.
  ③ 깨진 JSON·필수 결측·미지 오개념 id → 안전 폴백(None 또는 드롭).
  ④ provider 예외 → None(크래시 금지).
  ⑤ 저작권: 응답에 평가원 운운해도 provenance는 자체생성·WHYMATH_GENERATED로 구조적 고정.
  ⑥ 오케스트레이터 결선: run_equivalent_generation(spec, LLMEquivalentProblemGenerator(fake))
     → accepted(dry-run)·accepted_stored(fake store) — S2-d와 실제로 이어짐.

주의: 이 테스트는 tests/ 아래라 import-linter 계약 밖 → L4 `CATALOG_BY_ID`를 자유롭게 주입한다
(생성기 본체는 L3라 L4를 import하지 않고 카탈로그를 *주입*받는다 — 레이어 순수성).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from whymath_backend.l1.problem_bank.populate import (
    ProblemBankPopulateReport,
    ProblemBankRecord,
)
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.schema.enums import AnswerFormat, LicenseType, SourceType

# S2-d 오케스트레이터 테스트와 동일한 대응 스펙(전 게이트 통과 기준).
_STANDARD = "[12미적01-01]"
_MISCONCEPTION = "distribution-over-power"  # 실 카탈로그 id
_CATALOG = {mid: m.name_kr for mid, m in CATALOG_BY_ID.items()}

# 정상 응답 JSON — x=3은 x²-5x+6=0의 근(9-15+6=0) → Tier1 pass. 발문·해설은 위생-청정(거짓 등식 0).
_HAPPY = json.dumps(
    {
        "question_text": "주어진 이차 방정식의 자연수 근을 구하시오.",
        "answer": "3",
        "answer_explanation": "조건을 만족하는 자연수 근을 구하면 됩니다.",
        "conditions": "x**2 - 5*x + 6 = 0",
        "answer_map": {"x": "3"},
        "difficulty_overall": 3.0,
        "unit_codes": ["CAL-INT-DEF"],
        "answer_format": "자연수",
        "achievement_standard_codes": [_STANDARD],
        "distractor_map": [{"choice_index": 1, "misconception_id": _MISCONCEPTION}],
        "concept_tags": [{"concept_src_id": "HK06", "role": "PRIMARY", "relevance": 0.9}],
    },
    ensure_ascii=False,
)


# ──────────────────────────────────────────────────────────────────────
# provider 대역 — 스크립트 JSON / 예외 (LLMTutorPolicy 테스트 미러·라이브 0).
# ──────────────────────────────────────────────────────────────────────
class FakeProvider:
    """스크립트된 응답을 순서대로 방출하는 L3 provider 대역 — LLMProvider 충족(네트워크 0)."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> str:
        self.calls.append((prompt, system))
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return out
        return "{}"  # 소진 시 빈 객체(필수 결측 → 생성 실패)


class RaisingProvider:
    """generate가 항상 예외를 던지는 provider 대역 — provider 장애 안전 폴백 검증용."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> str:
        raise RuntimeError("provider 다운(테스트)")


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset({_MISCONCEPTION}),
        "difficulty_overall": 3.0,
        "answer_format": AnswerFormat.자연수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _gen(provider: object, **overrides: object) -> LLMEquivalentProblemGenerator:
    kwargs: dict[str, object] = {"misconception_catalog": _CATALOG}
    kwargs.update(overrides)
    return LLMEquivalentProblemGenerator(provider, **kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# ① 정상 JSON → CandidateProblem 조립.
# ──────────────────────────────────────────────────────────────────────
class TestAssembly:
    def test_happy_json_assembles_candidate(self) -> None:
        candidate = _gen(FakeProvider([_HAPPY])).generate(_spec())
        assert isinstance(candidate, CandidateProblem)
        # 저작권 메타는 구조적으로 고정(LLM 무관).
        assert candidate.problem.source_type == SourceType.자체생성
        assert candidate.provenance.license == LicenseType.WHYMATH_GENERATED
        # 검산 재료 정합.
        assert candidate.conditions == "x**2 - 5*x + 6 = 0"
        assert candidate.answer_map == {"x": "3"}
        assert candidate.problem.question_text == "주어진 이차 방정식의 자연수 근을 구하시오."
        assert candidate.problem.answer == "3"

    def test_slug_is_stable_and_deterministic(self) -> None:
        c1 = _gen(FakeProvider([_HAPPY])).generate(_spec())
        c2 = _gen(FakeProvider([_HAPPY])).generate(_spec())
        assert c1 is not None and c2 is not None
        assert c1.problem.slug == c2.problem.slug  # 같은 내용 → 같은 slug(멱등 upsert 키)
        assert c1.problem.slug is not None and c1.problem.slug.startswith("wm-gen-")

    def test_latex_backslash_in_response_still_parses(self) -> None:
        # 실 LLM(Phaiakes9 qwen2-math:7b) 실측 회귀 — 발문에 LaTeX `\(`·`\)`가 있어
        # `json.loads`가 "Invalid \escape"로 실패하던 케이스. sanitize 폴백이 구제해야 한다.
        raw = (
            '{\n  "question_text": "이차방정식 \\( x^2 - 5x + 6 = 0 \\)의 해는?",\n'
            '  "answer": "3",\n  "conditions": "x**2 - 5*x + 6 = 0",\n'
            '  "answer_map": {"x": "3"},\n  "unit_codes": ["QUAD-EQ"]\n}'
        )
        candidate = _gen(FakeProvider([raw])).generate(_spec())
        assert candidate is not None  # 파싱 구제(None 폴백 아님)
        assert candidate.answer_map == {"x": "3"}
        assert candidate.conditions == "x**2 - 5*x + 6 = 0"
        assert "\\(" in candidate.problem.question_text  # LaTeX는 보존(파싱만 구제)

    def test_concept_tags_parsed(self) -> None:
        candidate = _gen(FakeProvider([_HAPPY])).generate(_spec())
        assert candidate is not None
        assert candidate.concept_tags[0].concept_src_id == "HK06"
        assert candidate.concept_tags[0].role == "PRIMARY"

    def test_distractor_maps_known_misconception(self) -> None:
        candidate = _gen(FakeProvider([_HAPPY])).generate(_spec())
        assert candidate is not None
        assert candidate.problem.distractor_map is not None
        assert candidate.problem.distractor_map[0].misconception_id == _MISCONCEPTION

    def test_spec_not_leaked_verbatim_but_ids_present(self) -> None:
        provider = FakeProvider([_HAPPY])
        _gen(provider).generate(_spec())
        prompt, system = provider.calls[0]
        # 프롬프트는 저작권 금기를 명시하고, 스펙 성취기준·오개념 id를 싣는다(Minimal context).
        assert "복제" in system
        assert _STANDARD in prompt
        assert _MISCONCEPTION in prompt

    def test_topic_hint_injected_into_prompt(self) -> None:
        # S2-f: 성취기준 코드만으론 모델이 주제를 못 맞히므로(이차 요청에 일차 생성) topic_hint를
        # 프롬프트에 실어 코드→주제를 사람이 번역해 준다. 주입 시 유저 프롬프트에 나타나야 한다.
        provider = FakeProvider([_HAPPY])
        _gen(provider, topic_hint="이차방정식 — 두 근 중 큰 근").generate(_spec())
        prompt, _ = provider.calls[0]
        assert "이차방정식 — 두 근 중 큰 근" in prompt

    def test_system_prompt_requires_single_answer_and_forbids_placeholders(self) -> None:
        # S2-f: 답 하나로 정해지게(이차 검증 가능) + 플레이스홀더 베끼기 금지 지시가 시스템에 있다.
        provider = FakeProvider([_HAPPY])
        _gen(provider).generate(_spec())
        _, system = provider.calls[0]
        assert "하나로" in system  # 답 유일성 지시
        assert "플레이스홀더" in system  # 예시 텍스트 베끼기 금지


# ──────────────────────────────────────────────────────────────────────
# ② 생성기 → S2-a 게이트 결선(accepted=True).
# ──────────────────────────────────────────────────────────────────────
class TestGatePasses:
    def test_generated_candidate_passes_acceptance_gate(self) -> None:
        candidate = _gen(FakeProvider([_HAPPY])).generate(_spec())
        assert candidate is not None
        verdict = evaluate_equivalent_candidate(
            _spec(),
            candidate.problem,
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map=candidate.answer_map,
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is True
        assert verdict.copyright_ok is True
        assert verdict.verification == "verified"
        assert verdict.equivalence == "동치후보"


# ──────────────────────────────────────────────────────────────────────
# ③ 깨진 JSON·필수 결측·미지 오개념 → 안전 폴백(None 또는 드롭).
# ──────────────────────────────────────────────────────────────────────
class TestSafeFallback:
    def test_broken_json_returns_none(self) -> None:
        assert _gen(FakeProvider(["이건 JSON이 아니다 {{{"])).generate(_spec()) is None

    def test_missing_required_field_returns_none(self) -> None:
        payload = json.loads(_HAPPY)
        del payload["question_text"]
        assert _gen(FakeProvider([json.dumps(payload)])).generate(_spec()) is None

    def test_missing_conditions_returns_none(self) -> None:
        payload = json.loads(_HAPPY)
        del payload["conditions"]  # 정확성 검산 재료 결측
        assert _gen(FakeProvider([json.dumps(payload)])).generate(_spec()) is None

    def test_unknown_misconception_is_dropped(self) -> None:
        payload = json.loads(_HAPPY)
        payload["distractor_map"] = [
            {"choice_index": 1, "misconception_id": "totally-unknown-xyz-오개념"}
        ]
        candidate = _gen(FakeProvider([json.dumps(payload)])).generate(_spec())
        # 후보는 조립되지만 미지 오개념은 드롭 → distractor_map None(조용한 채택 금지).
        assert candidate is not None
        assert candidate.problem.distractor_map is None

    def test_missing_unit_codes_without_fallback_returns_none(self) -> None:
        payload = json.loads(_HAPPY)
        del payload["unit_codes"]
        assert _gen(FakeProvider([json.dumps(payload)])).generate(_spec()) is None

    def test_missing_unit_codes_with_fallback_assembles(self) -> None:
        payload = json.loads(_HAPPY)
        del payload["unit_codes"]
        gen = _gen(FakeProvider([json.dumps(payload)]), fallback_unit_codes=["CAL-INT-DEF"])
        candidate = gen.generate(_spec())
        assert candidate is not None
        assert candidate.problem.unit_codes == ["CAL-INT-DEF"]


# ──────────────────────────────────────────────────────────────────────
# ④ provider 예외 → None.
# ──────────────────────────────────────────────────────────────────────
class TestProviderFailure:
    def test_provider_exception_returns_none(self) -> None:
        assert _gen(RaisingProvider()).generate(_spec()) is None


# ──────────────────────────────────────────────────────────────────────
# ⑤ 저작권 구조적 강제 — 응답이 평가원 운운해도 provenance 고정.
# ──────────────────────────────────────────────────────────────────────
class TestCopyrightStructuralForcing:
    def test_source_claim_in_response_is_ignored(self) -> None:
        payload = json.loads(_HAPPY)
        payload["question_text"] = (
            "평가원 2024 수능 기출을 참고한 이차 방정식의 자연수 근을 구하시오."
        )
        payload["source_type"] = "평가원"  # LLM이 출처를 주장해도 코드가 읽지 않는다
        payload["license"] = "EBS_LICENSED"
        candidate = _gen(FakeProvider([json.dumps(payload)])).generate(_spec())
        assert candidate is not None
        # 구조적 강제 — 자체생성·WHYMATH_GENERATED로 고정(LLM 출처 주장 무시).
        assert candidate.problem.source_type == SourceType.자체생성
        assert candidate.provenance.license == LicenseType.WHYMATH_GENERATED
        # provenance original_source는 None(본문성 키 0).
        assert candidate.provenance.original_source is None


# ──────────────────────────────────────────────────────────────────────
# ⑥ 오케스트레이터 결선(S2-d와 실제 연결).
# ──────────────────────────────────────────────────────────────────────
class _FakeStore:
    """`ProblemBankSink` 구조 호환 fake — populate 호출·레코드 캡처(실 DB 0)."""

    def __init__(self) -> None:
        self.calls: list[list[ProblemBankRecord]] = []

    def populate(self, records: list[ProblemBankRecord]) -> ProblemBankPopulateReport:
        self.calls.append(list(records))
        return ProblemBankPopulateReport(
            problems_loaded=len(records),
            problem_concepts_loaded=sum(len(r.concept_tags) for r in records),
            concepts_skipped=0,
            skipped_messages=[],
        )


class TestOrchestratorWiring:
    def test_dry_run_accepted_through_orchestrator(self) -> None:
        gen = _gen(FakeProvider([_HAPPY]))
        outcome = run_equivalent_generation(_spec(), gen)
        assert outcome.status == "accepted"
        assert outcome.acceptance is not None and outcome.acceptance.accepted is True
        assert outcome.stored_problem_id is None

    def test_accepted_stored_through_orchestrator(self) -> None:
        gen = _gen(FakeProvider([_HAPPY]))
        store = _FakeStore()
        outcome = run_equivalent_generation(_spec(), gen, store=store)
        assert outcome.status == "accepted_stored"
        assert outcome.stored_problem_id is not None
        assert len(store.calls) == 1
        (records,) = store.calls
        assert records[0].slug is not None and records[0].slug.startswith("wm-gen-")

    def test_generation_failure_through_orchestrator(self) -> None:
        # provider 예외 → 생성기 None → 오케스트레이터 generation_failed(정직 처리).
        outcome = run_equivalent_generation(_spec(), _gen(RaisingProvider()))
        assert outcome.status == "generation_failed"


# 라이브 LLM 호출이 이 파일에 없음을 문서화(FakeProvider·RaisingProvider만).
def test_no_live_provider_used() -> None:
    assert not hasattr(FakeProvider, "_live")
    with pytest.raises(RuntimeError):
        # RaisingProvider가 실제로 예외를 던지는지(=라이브 아님) 확인.
        import asyncio

        asyncio.run(
            RaisingProvider().generate(
                "p",
                "s",
                RoutingDecision(cost_tier="cloud_mid", est_latency_ms=0),  # type: ignore[arg-type]
            )
        )
