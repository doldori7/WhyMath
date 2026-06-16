"""L6 재수전용(RT/N수) 트랙 게이팅 단위테스트 — 적격성·우선순위·선별·저작권 게이트.

검증:
  ① 대상 페르소나(B·C) + RT 신호(재수전용형 또는 persona_fit 충족) → 적격(True).
  ② 비대상 페르소나(A·D·E) → 부적격(False).
  ③ 본문 미보유 출처(평가원/EBS/교과서) → 저작권 노출 게이트로 차단(B라도 False).
  ④ persona_fit 미달 + 재수전용형 아님 → 부적격(False).
  ⑤ `select_retake_items` — 혼합 풀에서 RT 적합만 남고 우선순위·limit 동작.
  ⑥ `retake_priority` 단조성 — distractor_map 있는 쪽이 큼 등.

합성 픽스처만(실데이터 0). `_problem(**over)` 빌더로 자체생성 최소 문항을 만들고 오버라이드한다
(`tests/backend/schema/test_problem.py`의 `_minimal_self_generated` 헬퍼 패턴 답습).

레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·L6(`l6.retake`)만 import한다.
"""

from __future__ import annotations

from whymath_backend.l6.retake.gating import (
    METADATA_ONLY_SOURCES,
    RETAKE_PERSONAS,
    is_retake_eligible,
    retake_priority,
    select_retake_items,
)
from whymath_backend.schema.enums import (
    Curriculum,
    Persona,
    QuestionFormat,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem


def _problem(**over: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본은 `source_type=자체생성`(저작권 노출 게이트를 통과하는 출처)이라 RT 적합 신호만
    오버라이드하면 적격/부적격을 자유로이 만든다. 본문 미보유 출처(평가원/EBS/교과서)는
    `source_type=...`로 오버라이드해 저작권 게이트를 시험한다.
    (`test_problem.py`의 `_minimal_self_generated` 패턴 답습 — type: ignore도 동일.)
    """
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
    }
    kwargs.update(over)
    return Problem(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────
class TestConstants:
    def test_retake_personas_are_b_and_c(self) -> None:
        """RT 대상 페르소나는 정확히 B(자사고N수)·C(검정고시N수) 둘."""
        assert RETAKE_PERSONAS == frozenset({Persona.B_자사고N수, Persona.C_검정고시N수})

    def test_metadata_only_sources_are_three_no_body_sources(self) -> None:
        """저작권 게이트 차단 집합은 평가원·EBS·교과서(본문 미보유 3종)."""
        assert METADATA_ONLY_SOURCES == frozenset(
            {SourceType.평가원, SourceType.EBS, SourceType.교과서}
        )


# ──────────────────────────────────────────────────────────────────────
# is_retake_eligible — 적격성 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsRetakeEligible:
    def test_target_persona_with_retake_format_eligible(self) -> None:
        """B 페르소나 + 재수전용형 자체생성 문항 → 적격(persona_fit 없어도 라벨로 통과)."""
        problem = _problem(question_format=QuestionFormat.재수전용형)
        assert is_retake_eligible(problem, Persona.B_자사고N수) is True

    def test_target_persona_with_sufficient_fit_eligible(self) -> None:
        """C 페르소나 + persona_fit 충족(>=0.5)이면 재수전용형이 아니어도 적격."""
        problem = _problem(
            question_format=QuestionFormat.객관식,
            persona_fit={Persona.C_검정고시N수: 0.8},
        )
        assert is_retake_eligible(problem, Persona.C_검정고시N수) is True

    def test_target_persona_fit_at_threshold_is_eligible(self) -> None:
        """경계값 — persona_fit == min_fit(0.5)이면 적격(>= 비교)."""
        problem = _problem(persona_fit={Persona.B_자사고N수: 0.5})
        assert is_retake_eligible(problem, Persona.B_자사고N수, min_fit=0.5) is True

    def test_non_target_personas_rejected(self) -> None:
        """비대상 페르소나(A·D·E) → 부적격 — RT 적합 신호가 있어도 막힌다."""
        # 재수전용형 + 높은 적합도라도 비대상 페르소나면 ① 게이트에서 탈락.
        problem = _problem(
            question_format=QuestionFormat.재수전용형,
            persona_fit={
                Persona.A_일반고고3: 0.9,
                Persona.D_학종고2: 0.9,
                Persona.E_홈스쿨링영재: 0.9,
            },
        )
        for persona in (Persona.A_일반고고3, Persona.D_학종고2, Persona.E_홈스쿨링영재):
            assert is_retake_eligible(problem, persona) is False

    def test_insufficient_fit_and_not_retake_format_rejected(self) -> None:
        """persona_fit 미달 + 재수전용형 아님 → 부적격(③ 신호 둘 다 거짓)."""
        problem = _problem(
            question_format=QuestionFormat.객관식,
            persona_fit={Persona.B_자사고N수: 0.3},  # 0.5 미만
        )
        assert is_retake_eligible(problem, Persona.B_자사고N수) is False

    def test_no_persona_fit_and_not_retake_format_rejected(self) -> None:
        """persona_fit 비어 있고 재수전용형도 아니면 부적격(적합도 0.0 < 0.5)."""
        problem = _problem(question_format=QuestionFormat.객관식)
        assert is_retake_eligible(problem, Persona.B_자사고N수) is False

    def test_copyright_gate_blocks_metadata_only_sources(self) -> None:
        """저작권 노출 게이트 — 본문 미보유 출처는 B 페르소나·RT 신호라도 차단.

        평가원/EBS/교과서는 본문 미보유(구조 메타 전용)라 학생 노출 불가 →
        ② 게이트에서 무조건 탈락. 본문 필드(question_text 등)를 비워 둬야 Problem
        검증을 통과하므로 빌더 기본(본문 None)을 그대로 쓰되 source_type만 바꾼다.
        """
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            problem = _problem(
                source_type=source,
                question_format=QuestionFormat.재수전용형,  # RT 라벨이 있어도
                persona_fit={Persona.B_자사고N수: 0.99},  # 적합도가 높아도
            )
            assert is_retake_eligible(problem, Persona.B_자사고N수) is False, source

    def test_use_enum_values_string_keys_handled(self) -> None:
        """use_enum_values=True로 persona_fit 키가 문자열이어도 적합도가 조회된다.

        Problem이 use_enum_values=True라, 키를 enum이 아닌 *문자열 값*으로 줘도
        `_persona_fit`이 문자열 폴백으로 적중해야 한다(정규화 계약).
        """
        problem = _problem(persona_fit={Persona.C_검정고시N수.value: 0.7})
        assert is_retake_eligible(problem, Persona.C_검정고시N수) is True


# ──────────────────────────────────────────────────────────────────────
# retake_priority — 우선순위 가중치(단조성)
# ──────────────────────────────────────────────────────────────────────
class TestRetakePriority:
    def test_distractor_map_increases_priority(self) -> None:
        """distractor_map 있는 문항이 없는 문항보다 우선순위가 크다(다른 조건 동일)."""
        with_map = _problem(
            difficulty_overall=3.0,
            distractor_map=[DistractorEntry(choice_index=1, misconception_id="m-a")],
        )
        without_map = _problem(difficulty_overall=3.0)
        assert retake_priority(with_map) > retake_priority(without_map)

    def test_retake_format_increases_priority(self) -> None:
        """재수전용형 라벨이 있으면 없을 때보다 우선순위가 크다(다른 조건 동일)."""
        retake_fmt = _problem(difficulty_overall=3.0, question_format=QuestionFormat.재수전용형)
        plain_fmt = _problem(difficulty_overall=3.0, question_format=QuestionFormat.객관식)
        assert retake_priority(retake_fmt) > retake_priority(plain_fmt)

    def test_higher_difficulty_increases_priority(self) -> None:
        """종합 난이도가 높을수록 우선순위가 크다(보조 축·다른 조건 동일)."""
        hard = _problem(difficulty_overall=5.0)
        easy = _problem(difficulty_overall=1.0)
        assert retake_priority(hard) > retake_priority(easy)

    def test_none_difficulty_treated_as_zero(self) -> None:
        """difficulty_overall=None은 0.0으로 취급 — 난이도 신호 없음."""
        no_diff = _problem()  # difficulty_overall 기본 None
        assert retake_priority(no_diff) == 0.0

    def test_priority_is_deterministic(self) -> None:
        """같은 입력은 같은 가중치(결정적)."""
        problem = _problem(
            difficulty_overall=4.0,
            question_format=QuestionFormat.재수전용형,
            distractor_map=[DistractorEntry(choice_index=2, misconception_id="m-b")],
        )
        # distractor(+2.0) + 재수전용형(+1.5) + 난이도(4.0) = 7.5
        assert retake_priority(problem) == retake_priority(problem) == 7.5

    def test_empty_distractor_map_no_bonus(self) -> None:
        """빈 distractor_map([])은 *존재하지 않음*으로 취급 — 가산 없음."""
        empty = _problem(difficulty_overall=2.0, distractor_map=[])
        none_map = _problem(difficulty_overall=2.0)
        assert retake_priority(empty) == retake_priority(none_map) == 2.0


# ──────────────────────────────────────────────────────────────────────
# select_retake_items — 선별·정렬·limit
# ──────────────────────────────────────────────────────────────────────
class TestSelectRetakeItems:
    def test_filters_to_eligible_only(self) -> None:
        """혼합 풀(고3용·메타전용·RT적합 섞음)에서 RT 적합만 남는다."""
        rt_item = _problem(
            slug="rt-fit",
            question_format=QuestionFormat.재수전용형,
            persona_fit={Persona.B_자사고N수: 0.9},
        )
        # 고3 전용(B 적합도 미달·재수전용형 아님) → 탈락.
        grade3_item = _problem(
            slug="grade3-only",
            question_format=QuestionFormat.객관식,
            persona_fit={Persona.A_일반고고3: 0.9, Persona.B_자사고N수: 0.1},
        )
        # 메타전용(적합 신호 없음) → 탈락.
        meta_item = _problem(slug="meta-only", question_format=QuestionFormat.서술형)

        selected = select_retake_items([grade3_item, rt_item, meta_item], Persona.B_자사고N수)
        assert [p.slug for p in selected] == ["rt-fit"]

    def test_orders_by_priority_descending(self) -> None:
        """distractor_map 있는 고난도가 앞에 온다(우선순위 내림차순)."""
        # 셋 다 B에게 RT 적합(재수전용형). 우선순위만 다르게 설계.
        low = _problem(
            slug="low",
            question_format=QuestionFormat.재수전용형,
            difficulty_overall=2.0,
        )  # 1.5 + 2.0 = 3.5
        high_with_map = _problem(
            slug="high-with-map",
            question_format=QuestionFormat.재수전용형,
            difficulty_overall=4.0,
            distractor_map=[DistractorEntry(choice_index=1, misconception_id="m-x")],
        )  # 2.0 + 1.5 + 4.0 = 7.5
        mid = _problem(
            slug="mid",
            question_format=QuestionFormat.재수전용형,
            difficulty_overall=3.0,
        )  # 1.5 + 3.0 = 4.5

        # 입력은 우선순위 역순으로 줘서 정렬이 실제로 일어나는지 본다.
        selected = select_retake_items([low, mid, high_with_map], Persona.B_자사고N수)
        assert [p.slug for p in selected] == ["high-with-map", "mid", "low"]

    def test_limit_truncates_to_top_n(self) -> None:
        """limit이 상위 N개로 자른다(우선순위 상위부터)."""
        items = [
            _problem(
                slug=f"item-{i}",
                question_format=QuestionFormat.재수전용형,
                difficulty_overall=float(i),
            )
            for i in (1, 2, 3, 4, 5)
        ]
        # 난이도 5,4가 상위 2개(1.5 + 난이도).
        selected = select_retake_items(items, Persona.B_자사고N수, limit=2)
        assert [p.slug for p in selected] == ["item-5", "item-4"]

    def test_limit_none_returns_all_eligible(self) -> None:
        """limit=None(기본) → 적격 전부 반환(무제한)."""
        items = [
            _problem(slug=f"i-{i}", question_format=QuestionFormat.재수전용형) for i in range(3)
        ]
        selected = select_retake_items(items, Persona.B_자사고N수)
        assert len(selected) == 3

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 → 빈 리스트(상위 0개)."""
        items = [_problem(question_format=QuestionFormat.재수전용형)]
        assert select_retake_items(items, Persona.B_자사고N수, limit=0) == []

    def test_empty_input_returns_empty(self) -> None:
        """빈 입력 → 빈 결과."""
        assert select_retake_items([], Persona.B_자사고N수) == []

    def test_non_target_persona_selects_nothing(self) -> None:
        """비대상 페르소나(A)면 적합 문항이 많아도 전부 탈락 → 빈 결과."""
        items = [
            _problem(
                question_format=QuestionFormat.재수전용형,
                persona_fit={Persona.A_일반고고3: 0.9},
            )
            for _ in range(3)
        ]
        assert select_retake_items(items, Persona.A_일반고고3) == []

    def test_copyright_blocked_items_excluded_from_selection(self) -> None:
        """선별에서도 본문 미보유 출처는 빠진다(저작권 게이트가 필터에 적용)."""
        ok = _problem(slug="ok", question_format=QuestionFormat.재수전용형)
        # 평가원 출처(본문 미보유) — RT 라벨이 있어도 노출 불가.
        blocked = _problem(
            slug="blocked",
            source_type=SourceType.평가원,
            question_format=QuestionFormat.재수전용형,
        )
        selected = select_retake_items([blocked, ok], Persona.B_자사고N수)
        assert [p.slug for p in selected] == ["ok"]

    def test_stable_sort_preserves_input_order_on_ties(self) -> None:
        """동률(같은 우선순위)은 입력 순서를 보존한다(안정정렬 계약)."""
        # 셋 다 재수전용형·난이도 3.0·distractor 없음 → 동일 우선순위(4.5).
        first = _problem(
            slug="first", question_format=QuestionFormat.재수전용형, difficulty_overall=3.0
        )
        second = _problem(
            slug="second", question_format=QuestionFormat.재수전용형, difficulty_overall=3.0
        )
        third = _problem(
            slug="third", question_format=QuestionFormat.재수전용형, difficulty_overall=3.0
        )
        selected = select_retake_items([first, second, third], Persona.B_자사고N수)
        assert [p.slug for p in selected] == ["first", "second", "third"]
