"""오개념 수치평가 객관식 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), 극값 MC `test_calculus_skeleton_generator.py` 미러:
  ① 후보는 전부 S2-a 게이트 통과(accepted·verified) — 결정론 코어가 곧 검증 가능성.
  ② conditions(dummy x 등식)가 answer_map으로 Tier1 검산 pass(정답값 자기정합).
  ③ 4지선다는 4개 서로 다른 표기·정답이 선지에 있음·오개념 오답 1건만 태깅(정답 선지 제외).
  ④ 각 kebab당 서로 다른 문항 ≥24·구조 signature 전부 상이·풀 소진 시 None·재현 결정론.
  ⑤ 개념/단원 태깅이 템플릿별 L1 데이터로 주입·주입쌍 무결성(빈 주입·미지원 템플릿 거부).
"""

from __future__ import annotations

import pytest

from whymath_backend.harness.misconception_mc_batch import (
    build_kebab_distractor_codes_optional,
)
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.equivalent.misconception_eval_mc_generator import (
    MisconceptionEvalMCSkeletonGenerator,
    TemplateKind,
)
from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.schema.enums import QuestionFormat

# (template, kebab, 성취기준, 개념 src_id, 단원 코드) — 배치 스펙과 정합.
_CASES: tuple[tuple[TemplateKind, str, str, str, str], ...] = (
    ("distribution", "distribution-over-power", "[9수02-19]", "J0219", "POLY-PRODUCT"),
    (
        "chain_rule",
        "chain-rule-inner-derivative-omitted",
        "[12미적Ⅰ-02-01]",
        "H:12미적Ⅰ02-01",
        "CALC-CHAIN",
    ),
    ("sine_sum", "sine-distributes-over-sum", "[12미적Ⅱ-02-02]", "H:12미적Ⅱ02-02", "TRIG-ADD"),
    # 신규 5종(op-code 부재) — 커버리지 8→13.
    ("exp_zero", "exponent-zero", "[9수02-08]", "J0208", "EXP-ZERO"),
    ("sqrt_pos", "square-root-positivity", "[9수01-07]", "J0107", "SQRT-POS"),
    ("log_dist", "log-distribution", "[12대수01-05]", "H:12대수01-05", "LOG-DIST"),
    ("func_compose", "composite-function-commutes", "[10공수2-03-02]", "HK35", "FUNC-COMPOSE"),
    ("sine_period", "period-of-scaled-sine", "[12미적Ⅱ-02-02]", "H:12미적Ⅱ02-02", "TRIG-PERIOD"),
)


def _spec(kebab: str, code: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({code}),
        target_misconception_ids=frozenset({kebab}),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _gen(template: TemplateKind, kebab: str, **kw: object) -> MisconceptionEvalMCSkeletonGenerator:
    # op-code 有/無 무관 주입(부재 시 op_code=None) — 신규 5종은 op-code 없음.
    return MisconceptionEvalMCSkeletonGenerator(
        template, build_kebab_distractor_codes_optional(kebab), **kw  # type: ignore[arg-type]
    )


def _drain(
    gen: MisconceptionEvalMCSkeletonGenerator, spec: EquivalenceSpec
) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    guard = 0
    while True:
        guard += 1
        assert guard < 5000  # 무한루프 방어(풀 유한)
        candidate = gen.generate(spec)
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestSeatContract:
    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_satisfies_generator_protocol(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        assert isinstance(_gen(template, kebab), EquivalentProblemGenerator)

    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_deterministic_sequence(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        spec = _spec(kebab, code)
        a = [c.problem.slug for c in _drain(_gen(template, kebab), spec)]
        b = [c.problem.slug for c in _drain(_gen(template, kebab), spec)]
        assert a == b

    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_yield_at_least_24_then_none(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        gen = _gen(template, kebab)
        spec = _spec(kebab, code)
        drawn = _drain(gen, spec)
        assert len(drawn) >= 24  # 각 kebab당 서로 다른 문항 ≥24(커버리지 요구)
        assert gen.generate(spec) is None  # 소진 후에도 안정적으로 None


class TestMathematicalSoundness:
    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_all_candidates_pass_acceptance_gate(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        spec = _spec(kebab, code)
        drawn = _drain(_gen(template, kebab), spec)
        for candidate in drawn:
            verdict = evaluate_equivalent_candidate(
                spec,
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
                answer_aggregate=candidate.answer_aggregate,
            )
            assert verdict.accepted, (candidate.problem.slug, verdict.reasons)
            assert verdict.verification == "verified"

    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_conditions_tier1_verify_pass(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        # ② conditions(dummy x 등식)가 answer_map으로 Tier1 검산 pass — 정답값 자기정합.
        for candidate in _drain(_gen(template, kebab), _spec(kebab, code)):
            assert isinstance(candidate.conditions, str)
            assert verify_answer(candidate.conditions, candidate.answer_map).state == "pass"


class TestChoicesAndTagging:
    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_four_distinct_choices_answer_present(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        for candidate in _drain(_gen(template, kebab), _spec(kebab, code)):
            problem = candidate.problem
            assert problem.question_format == QuestionFormat.객관식.value
            assert problem.choices is not None and len(problem.choices) == 4
            assert len(set(problem.choices)) == 4  # 4지선다 상이
            assert problem.answer in problem.choices  # 정답이 선지에 존재
            # answer_map 값이 정답 선지와 일치(선지 문자열 = 검산 정답).
            assert candidate.answer_map["x"] == problem.answer

    @pytest.mark.parametrize("template,kebab,code,_src,_unit", _CASES)
    def test_single_misconception_tag_not_on_answer(
        self, template: TemplateKind, kebab: str, code: str, _src: str, _unit: str
    ) -> None:
        # ③ 오개념 오답 *1건*만 태깅·정답 선지 제외·op-code 정본 일치(부재 시 None).
        expected_op = next(iter(build_kebab_distractor_codes_optional(kebab).values()))[1]
        for candidate in _drain(_gen(template, kebab), _spec(kebab, code)):
            problem = candidate.problem
            assert problem.distractor_map is not None and len(problem.distractor_map) == 1
            entry = problem.distractor_map[0]
            assert entry.misconception_id == kebab
            assert entry.op_code == expected_op
            answer_index = problem.choices.index(problem.answer)  # type: ignore[union-attr]
            assert entry.choice_index != answer_index  # 정답 선지엔 태깅 안 함
            assert 0 <= entry.choice_index < 4

    @pytest.mark.parametrize("template,kebab,code,src,unit", _CASES)
    def test_concept_and_unit_tagging(
        self, template: TemplateKind, kebab: str, code: str, src: str, unit: str
    ) -> None:
        # ⑤ 개념/단원 태깅이 템플릿별 L1 데이터로 주입.
        candidate = _gen(template, kebab).generate(_spec(kebab, code))
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == [src]
        assert candidate.problem.unit_codes == [unit]
        assert candidate.problem.achievement_standard_codes == [code]


class TestInjectionIntegrity:
    def test_empty_distractor_codes_rejected(self) -> None:
        with pytest.raises(ValueError):
            MisconceptionEvalMCSkeletonGenerator("distribution", {})

    def test_unknown_template_rejected(self) -> None:
        with pytest.raises(ValueError):
            MisconceptionEvalMCSkeletonGenerator(
                "nope",  # type: ignore[arg-type]
                {"k": ("distribution-over-power", "power-distributed-no-cross-term")},
            )

    def test_skip_signatures_are_honored(self) -> None:
        # ④ 이미 코퍼스에 있는 구조 signature는 건너뛴다(배치 재실행 dedup 낭비 방지).
        from whymath_backend.l3.equivalent.canonicalize import canonical_signature

        template, kebab, code = "distribution", "distribution-over-power", "[9수02-19]"
        spec = _spec(kebab, code)
        first = _gen(template, kebab).generate(spec)
        assert first is not None
        assert isinstance(first.conditions, str)
        sig = canonical_signature(first.conditions, None)
        assert sig is not None
        gen2 = _gen(template, kebab, skip_signatures={sig})
        # skip된 첫 뼈대는 나오지 않는다 — 남은 후보 전부 다른 conditions.
        for candidate in _drain(gen2, spec):
            assert candidate.conditions != first.conditions
