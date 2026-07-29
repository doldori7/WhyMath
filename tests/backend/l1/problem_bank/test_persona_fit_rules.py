"""페르소나 적합도 결정론 백필 규칙(S3-10) 단위테스트 — 밴드 분류·가산·클립·근거·결정론 봉인.

핵심 봉인: ① 난이도 밴드 5구간 경계값 ② 밴드 기본 적합도(A/B/C/D/E)가 표와 일치 ③ 시그니처·
질문형식·distractor_map 가산이 *해당 페르소나에만* 적용 ④ [0,1] 클립(가산 누적으로 1.0 초과
방지) ⑤ 근거(`PersonaFitRationale`)가 적용된 가산만 담는다 ⑥ 결정론(같은 입력→같은 출력, 재실행
동일) ⑦ 갭 리뷰 문서가 든 실사례("킬러 Vieta → A 고3·B 자사고 고적합")를 그대로 재현.
"""

from __future__ import annotations

from whymath_backend.l1.problem_bank.persona_fit_rules import (
    DifficultyBand,
    classify_difficulty_band,
    derive_persona_fit,
)
from whymath_backend.schema.enums import Persona, SignaturePattern
from whymath_backend.schema.problem import Problem


def _problem(**overrides: object) -> Problem:
    """최소 유효 Problem 픽스처 — 자체생성·필수 필드만 채우고 overrides로 케이스 구성."""
    base: dict[str, object] = {
        "source_type": "자체생성",
        "curriculum_version": "2022_REVISION",
        "valid_from_year": 2022,
        "subject": "공통",
        "unit_codes": ["QUAD-EQ"],
        "question_format": "단답형",
        "question_text": "이차방정식 x^2 + 4x - 2 = 0 의 서로 다른 두 근의 합의 값을 구하시오.",
        "answer": "-4",
        "difficulty_overall": 2.0,
    }
    base.update(overrides)
    return Problem.model_validate(base)


class TestClassifyDifficultyBand:
    def test_none_is_unknown(self) -> None:
        assert classify_difficulty_band(None) is DifficultyBand.UNKNOWN

    def test_boundaries(self) -> None:
        assert classify_difficulty_band(1.99) is DifficultyBand.BASIC
        assert classify_difficulty_band(2.0) is DifficultyBand.CORE
        assert classify_difficulty_band(2.99) is DifficultyBand.CORE
        assert classify_difficulty_band(3.0) is DifficultyBand.MID_HIGH
        assert classify_difficulty_band(3.49) is DifficultyBand.MID_HIGH
        assert classify_difficulty_band(3.5) is DifficultyBand.HIGH
        assert classify_difficulty_band(3.99) is DifficultyBand.HIGH
        assert classify_difficulty_band(4.0) is DifficultyBand.KILLER
        assert classify_difficulty_band(5.0) is DifficultyBand.KILLER


class TestBandBaseFit:
    def test_core_band_no_modifiers(self) -> None:
        """CORE 밴드·시그니처 없음·distractor 없음·질문형식 미가산(합답형)이면 기본표 그대로."""
        problem = _problem(difficulty_overall=2.0, question_format="합답형")
        final, rationale = derive_persona_fit(problem)
        assert final == {
            "A_일반고고3": 0.90,
            "B_자사고N수": 0.60,
            "C_검정고시N수": 0.85,
            "D_학종고2": 0.55,  # 합답형 D 가산 +0.05
            "E_홈스쿨링영재": 0.35,
        }
        assert rationale.band is DifficultyBand.CORE
        assert rationale.format_bonus == {"D_학종고2": 0.05}
        assert rationale.signature_bonus == {}
        assert rationale.distractor_bonus == {}

    def test_unknown_difficulty_is_neutral_low(self) -> None:
        problem = _problem(difficulty_overall=None, question_format=None)
        final, rationale = derive_persona_fit(problem)
        assert all(v == 0.30 for v in final.values())
        assert rationale.band is DifficultyBand.UNKNOWN


class TestKillerVietaGapReviewExample:
    """갭 리뷰 문서(`problem_bank_gap_review.md` §3 D3) 실사례 재현.

    킬러(POLY-ROOT·근과 계수 관계·단답형·시그니처 없음·distractor 없음) → "A 고3·B 자사고 고적합"
    (둘 다 min_fit 0.5 이상)이 그대로 성립해야 한다.
    """

    def test_killer_vieta_favors_a_and_b(self) -> None:
        problem = _problem(
            unit_codes=["POLY-ROOT"],
            difficulty_overall=4.0,
            question_format="단답형",
            signature_patterns=[],
            distractor_map=None,
        )
        final, rationale = derive_persona_fit(problem)
        assert final["A_일반고고3"] >= 0.5
        assert final["B_자사고N수"] >= 0.5
        assert final["A_일반고고3"] == 0.70
        assert final["B_자사고N수"] == 0.95  # 킬러 밴드 0.90 + 단답형 가산 0.05
        assert final["C_검정고시N수"] == 0.50
        assert rationale.band is DifficultyBand.KILLER


class TestModifiersApplyOnlyToTargetedPersonas:
    def test_signature_bonus_only_abc(self) -> None:
        problem = _problem(
            difficulty_overall=2.0,
            question_format="합답형",
            signature_patterns=[SignaturePattern.CONDITION_LIST],
        )
        _final, rationale = derive_persona_fit(problem)
        assert set(rationale.signature_bonus) == {"A_일반고고3", "B_자사고N수", "C_검정고시N수"}
        assert "D_학종고2" not in rationale.signature_bonus
        assert "E_홈스쿨링영재" not in rationale.signature_bonus

    def test_complex_reasoning_bonus_only_de(self) -> None:
        """케이스분류·그래프개형·단원융합 3종만 D·E 가산 — 나머지 7종 시그니처는 가산 안 한다."""
        problem = _problem(
            difficulty_overall=2.0,
            question_format="합답형",  # D는 이미 +0.05 형식 가산 대상 — 복합사고 가산과 별개 확인
            signature_patterns=[SignaturePattern.CASE_ANALYSIS_DEEP],
        )
        _final, rationale = derive_persona_fit(problem)
        assert rationale.complex_reasoning_bonus == {
            "D_학종고2": 0.10,
            "E_홈스쿨링영재": 0.10,
        }

    def test_non_complex_signature_grants_no_reasoning_bonus(self) -> None:
        """**변별력** — 시그니처가 있어도 복합사고 3종 밖이면 D·E 가산이 없다."""
        problem = _problem(
            difficulty_overall=2.0,
            signature_patterns=[SignaturePattern.CONDITION_LIST],
        )
        _final, rationale = derive_persona_fit(problem)
        assert rationale.complex_reasoning_bonus == {}

    def test_distractor_bonus_all_plus_extra_bc(self) -> None:
        problem = _problem(
            difficulty_overall=2.0,
            question_format="합답형",
            distractor_map=[{"choice_index": 0, "misconception_id": "sign-error-basic"}],
        )
        _final, rationale = derive_persona_fit(problem)
        assert rationale.distractor_bonus == {
            "A_일반고고3": 0.05,
            "B_자사고N수": 0.10,
            "C_검정고시N수": 0.10,
            "D_학종고2": 0.05,
            "E_홈스쿨링영재": 0.05,
        }

    def test_unrecognized_question_format_grants_no_bonus(self) -> None:
        """표에 없는 형식(신규 P3a 유형 등)은 조용히 추측하지 않고 가산 0(결정론 기본값)."""
        problem = _problem(difficulty_overall=2.0, question_format="객관식진단")
        _final, rationale = derive_persona_fit(problem)
        assert rationale.format_bonus == {}


class TestClipping:
    def test_score_never_exceeds_one(self) -> None:
        """HIGH 밴드 E(0.65) + 복합사고(+0.10) + 단답형(+0.05) + distractor(+0.05) = 0.85 <= 1.0.

        가산이 누적돼 1.0을 넘는 경우가 생기면(예: 미래 규칙 확장) 클립이 실제로 동작하는지
        확인 — 인위적으로 HIGH·전 가산을 동시에 태워 상한을 실측한다.
        """
        problem = _problem(
            difficulty_overall=3.5,
            question_format="단답형",
            signature_patterns=[SignaturePattern.CROSS_UNIT_FUSION],
            distractor_map=[{"choice_index": 0, "misconception_id": "sign-error-basic"}],
        )
        final, _rationale = derive_persona_fit(problem)
        assert final["E_홈스쿨링영재"] == 0.85
        assert all(0.0 <= v <= 1.0 for v in final.values())


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        problem = _problem(difficulty_overall=3.2, question_format="객관식")
        first, _ = derive_persona_fit(problem)
        second, _ = derive_persona_fit(problem)
        assert first == second

    def test_output_key_order_is_fixed_a_to_e(self) -> None:
        problem = _problem(difficulty_overall=3.2)
        final, _ = derive_persona_fit(problem)
        assert list(final.keys()) == [
            "A_일반고고3",
            "B_자사고N수",
            "C_검정고시N수",
            "D_학종고2",
            "E_홈스쿨링영재",
        ]


class TestRationaleIsReconstructible:
    def test_final_equals_base_plus_applied_bonuses(self) -> None:
        """근거에 담긴 구성요소를 합산하면 최종값이 재구성된다(사후 설명이 아니라 계산 추적)."""
        problem = _problem(
            difficulty_overall=3.2,
            question_format="객관식",
            signature_patterns=[SignaturePattern.CONDITION_LIST],
            distractor_map=[{"choice_index": 0, "misconception_id": "sign-error-basic"}],
        )
        final, rationale = derive_persona_fit(problem)
        for persona in Persona:
            key = persona.value
            expected = (
                rationale.band_base[key]
                + rationale.signature_bonus.get(key, 0.0)
                + rationale.complex_reasoning_bonus.get(key, 0.0)
                + rationale.format_bonus.get(key, 0.0)
                + rationale.distractor_bonus.get(key, 0.0)
            )
            assert final[key] == round(min(1.0, max(0.0, expected)), 2)
