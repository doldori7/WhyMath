"""L6 메타인지(metacognition) 모드 게이팅 단위테스트 — 적격성·우선순위·선별·저작권 게이트.

검증:
  ① 메타인지 주신호(distractor_map 존재) + 페르소나 적합(persona_fit >= min_fit) → 적격(True).
  ② 보조 신호(scoring_type ∈ {진단,루브릭})만으로도 적격(distractor_map 없어도·OR 계약).
  ③ 메타인지 신호 둘 다 없음(distractor_map None + 정오답/None 등) → 부적격(False).
  ④ 본문 미보유 출처(평가원/EBS/교과서) → 저작권 노출 게이트로 차단(distractor_map 있어도).
  ⑤ 페르소나 적합(persona_fit 미달) → 부적격. 단 *닫힌 집합 게이트는 없다* — A(첫 노출 공유
     코어)부터 E까지 적합도 충족이면 통과.
  ⑥ `metacognition_priority` 단조성 — distractor_map 개수 가산·scoring_type 진단/루브릭 가산·
     난이도 가산.
  ⑦ `select_metacognition_items` — 혼합 풀에서 메타인지 적합만 남김·우선순위 순·limit·안정정렬.

합성 픽스처만(실데이터 0). `_problem(**over)` 빌더로 자체생성 최소 문항을 만들고 오버라이드한다
(`tests/backend/l6/thinking/test_gating.py`·`tests/backend/l6/retake/test_gating.py` 패턴 답습).

레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·L6(`l6.metacognition`)만 import한다.
"""

from __future__ import annotations

from whymath_backend.l6.metacognition.gating import (
    METACOGNITION_SCORING_TYPES,
    is_metacognition_eligible,
    metacognition_priority,
    select_metacognition_items,
)
from whymath_backend.schema.enums import (
    Curriculum,
    Persona,
    ReviewStatus,
    ScoringType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem


def _problem(**over: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본은 `source_type=자체생성`(저작권 노출 게이트를 통과하는 출처)이라 메타인지 신호만
    오버라이드하면 적격/부적격을 자유로이 만든다. 본문 미보유 출처(평가원/EBS/교과서)는
    `source_type=...`로 오버라이드해 저작권 게이트를 시험한다(thinking/retake `_problem` 답습).
    """
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        # PB-03 — 검수 노출 게이트(`is_review_cleared`) 추가로 기본값도 approved가 필요.
        "review_status": ReviewStatus.approved,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
    }
    kwargs.update(over)
    return Problem(**kwargs)  # type: ignore[arg-type]


def _fit(persona: Persona = Persona.A_일반고고3, score: float = 0.9) -> dict[Persona, float]:
    """주어진 페르소나에 충분한 persona_fit dict(기본 A — 공유 코어 첫 노출·0.9)."""
    return {persona: score}


def _distractors(n: int) -> list[DistractorEntry]:
    """오답→오개념 매핑 n개(서로 다른 choice_index·misconception_id)."""
    return [DistractorEntry(choice_index=i, misconception_id=f"m-{i}") for i in range(n)]


# ──────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────
class TestConstants:
    def test_scoring_types_are_diagnostic_and_rubric(self) -> None:
        """메타인지 보조 신호 채점 유형은 정확히 진단·루브릭 둘."""
        assert METACOGNITION_SCORING_TYPES == frozenset({ScoringType.진단, ScoringType.루브릭})

    def test_scoring_types_exclude_plain(self) -> None:
        """정오답·부분점수·시간은 메타인지 보조 신호가 아니다."""
        assert ScoringType.정오답 not in METACOGNITION_SCORING_TYPES
        assert ScoringType.부분점수 not in METACOGNITION_SCORING_TYPES
        assert ScoringType.시간 not in METACOGNITION_SCORING_TYPES


# ──────────────────────────────────────────────────────────────────────
# is_metacognition_eligible — 적격성 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsMetacognitionEligible:
    def test_distractor_map_with_fit_eligible(self) -> None:
        """distractor_map 존재 + 페르소나 적합 → 적격(주신호)."""
        problem = _problem(distractor_map=_distractors(1), persona_fit=_fit())
        assert is_metacognition_eligible(problem, Persona.A_일반고고3) is True

    def test_scoring_type_alone_eligible(self) -> None:
        """distractor_map이 없어도 scoring_type 진단/루브릭이면 적격(OR 보조 신호)."""
        for scoring in (ScoringType.진단, ScoringType.루브릭):
            problem = _problem(scoring_type=scoring, persona_fit=_fit())
            assert is_metacognition_eligible(problem, Persona.A_일반고고3) is True, scoring

    def test_default_persona_is_a_general_high(self) -> None:
        """persona 인자 생략 시 기본 A_일반고고3(공유 코어 첫 노출 대상)."""
        problem = _problem(distractor_map=_distractors(1), persona_fit=_fit())
        assert is_metacognition_eligible(problem) is True

    def test_no_signal_rejected(self) -> None:
        """distractor_map 없음 + scoring_type 정오답(또는 None) → 부적격(메타인지 자원 부재)."""
        plain = _problem(scoring_type=ScoringType.정오답, persona_fit=_fit())
        assert is_metacognition_eligible(plain, Persona.A_일반고고3) is False
        # scoring_type None + distractor 없음도 부적격.
        bare = _problem(persona_fit=_fit())
        assert is_metacognition_eligible(bare, Persona.A_일반고고3) is False

    def test_empty_distractor_map_is_not_signal(self) -> None:
        """빈 distractor_map([])은 존재하지 않음으로 취급 — 보조 신호도 없으면 부적격."""
        problem = _problem(distractor_map=[], persona_fit=_fit())
        assert is_metacognition_eligible(problem, Persona.A_일반고고3) is False

    def test_insufficient_persona_fit_rejected(self) -> None:
        """페르소나 적합도 미달(<min_fit)이면 메타인지 신호가 있어도 부적격."""
        problem = _problem(
            distractor_map=_distractors(2),
            persona_fit={Persona.A_일반고고3: 0.3},
        )
        assert is_metacognition_eligible(problem, Persona.A_일반고고3) is False

    def test_persona_fit_at_threshold_is_eligible(self) -> None:
        """경계값 — persona_fit == min_fit(0.5)이면 적격(>= 비교)."""
        problem = _problem(
            distractor_map=_distractors(1),
            persona_fit={Persona.A_일반고고3: 0.5},
        )
        assert is_metacognition_eligible(problem, Persona.A_일반고고3, min_fit=0.5) is True

    def test_all_personas_not_excluded_by_closed_set(self) -> None:
        """전 페르소나 공유 코어 — A~E 누구든 적합도 충족이면 통과(닫힌 집합 게이트 없음)."""
        for persona in (
            Persona.A_일반고고3,
            Persona.B_자사고N수,
            Persona.C_검정고시N수,
            Persona.D_학종고2,
            Persona.E_홈스쿨링영재,
        ):
            problem = _problem(distractor_map=_distractors(1), persona_fit={persona: 0.8})
            assert is_metacognition_eligible(problem, persona) is True, persona

    def test_persona_without_fit_rejected(self) -> None:
        """persona_fit에 해당 페르소나가 없으면(0.0) 메타인지 신호가 있어도 부적격."""
        problem = _problem(
            distractor_map=_distractors(1),
            persona_fit={Persona.E_홈스쿨링영재: 0.9},  # 조회 대상 A는 없음
        )
        assert is_metacognition_eligible(problem, Persona.A_일반고고3) is False

    def test_copyright_gate_blocks_metadata_only_sources(self) -> None:
        """저작권 노출 게이트 — 본문 미보유 출처는 distractor_map·높은 적합도라도 차단."""
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            problem = _problem(
                source_type=source,
                distractor_map=_distractors(2),  # 메타인지 주신호가 있어도
                scoring_type=ScoringType.진단,  # 보조 신호가 있어도
                persona_fit={Persona.A_일반고고3: 0.99},  # 적합도가 높아도
            )
            assert is_metacognition_eligible(problem, Persona.A_일반고고3) is False, source

    def test_use_enum_values_string_keys_handled(self) -> None:
        """use_enum_values=True로 persona_fit 키·scoring_type이 문자열이어도 정규화 적중."""
        problem = _problem(
            scoring_type=ScoringType.루브릭.value,
            persona_fit={Persona.D_학종고2.value: 0.7},
        )
        assert is_metacognition_eligible(problem, Persona.D_학종고2) is True


# ──────────────────────────────────────────────────────────────────────
# metacognition_priority — 우선순위 가중치(단조성)
# ──────────────────────────────────────────────────────────────────────
class TestMetacognitionPriority:
    def test_more_distractors_increase_priority(self) -> None:
        """distractor_map 개수가 많을수록 우선순위가 크다(개수 단조·다른 조건 동일)."""
        two = _problem(distractor_map=_distractors(2))
        one = _problem(distractor_map=_distractors(1))
        assert metacognition_priority(two) > metacognition_priority(one)

    def test_distractor_is_primary_outweighs_scoring(self) -> None:
        """주신호 distractor_map(1개 2.0)이 보조 scoring_type 단독(+1.0)보다 크다."""
        distractor_only = _problem(distractor_map=_distractors(1))  # 2.0
        scoring_only = _problem(scoring_type=ScoringType.진단)  # 1.0
        assert metacognition_priority(distractor_only) > metacognition_priority(scoring_only)

    def test_scoring_type_increases_priority(self) -> None:
        """scoring_type 진단/루브릭이면 없을 때보다 우선순위가 크다(보조)."""
        for scoring in (ScoringType.진단, ScoringType.루브릭):
            with_scoring = _problem(distractor_map=_distractors(1), scoring_type=scoring)
            without = _problem(distractor_map=_distractors(1), scoring_type=ScoringType.정오답)
            assert metacognition_priority(with_scoring) > metacognition_priority(without), scoring

    def test_higher_difficulty_increases_priority(self) -> None:
        """종합 난이도가 높을수록 우선순위가 크다(보조 축·다른 조건 동일)."""
        hard = _problem(distractor_map=_distractors(1), difficulty_overall=5.0)
        easy = _problem(distractor_map=_distractors(1), difficulty_overall=1.0)
        assert metacognition_priority(hard) > metacognition_priority(easy)

    def test_priority_is_deterministic_and_sum_exact(self) -> None:
        """같은 입력은 같은 가중치(결정적)·가중 합 정확."""
        problem = _problem(
            distractor_map=_distractors(2),  # 2개 × 2.0 = 4.0
            scoring_type=ScoringType.진단,  # +1.0
            difficulty_overall=3.0,  # 3.0
        )
        # 4.0 + 1.0 + 3.0 = 8.0
        assert metacognition_priority(problem) == metacognition_priority(problem) == 8.0

    def test_none_signals_treated_as_zero(self) -> None:
        """distractor_map None·scoring_type None·difficulty None은 0.0으로 취급."""
        bare = _problem()
        assert metacognition_priority(bare) == 0.0

    def test_empty_distractor_map_no_bonus(self) -> None:
        """빈 distractor_map([])은 존재하지 않음으로 취급 — 가산 없음."""
        empty = _problem(distractor_map=[], difficulty_overall=2.0)
        none_map = _problem(difficulty_overall=2.0)
        assert metacognition_priority(empty) == metacognition_priority(none_map) == 2.0


# ──────────────────────────────────────────────────────────────────────
# select_metacognition_items — 선별·정렬·limit
# ──────────────────────────────────────────────────────────────────────
class TestSelectMetacognitionItems:
    def test_filters_to_eligible_only(self) -> None:
        """혼합 풀(신호 없음·정오답·메타 적합 섞음)에서 메타인지 적합만 남는다."""
        meta_item = _problem(slug="meta-fit", distractor_map=_distractors(1), persona_fit=_fit())
        # 신호 없음(정오답·distractor 없음) → 탈락.
        plain = _problem(slug="plain", scoring_type=ScoringType.정오답, persona_fit=_fit())
        # distractor도 진단/루브릭도 없음 → 탈락.
        bare = _problem(slug="bare", persona_fit=_fit())

        selected = select_metacognition_items([plain, meta_item, bare], Persona.A_일반고고3)
        assert [p.slug for p in selected] == ["meta-fit"]

    def test_orders_by_distractor_count_descending(self) -> None:
        """distractor_map 개수 많은 문항이 앞에 온다(우선순위 내림차순)."""
        one = _problem(slug="one", distractor_map=_distractors(1), persona_fit=_fit())
        three = _problem(slug="three", distractor_map=_distractors(3), persona_fit=_fit())
        two = _problem(slug="two", distractor_map=_distractors(2), persona_fit=_fit())

        # 입력은 우선순위 역순 비슷하게 줘서 정렬이 실제로 일어나는지 본다.
        selected = select_metacognition_items([one, two, three], Persona.A_일반고고3)
        assert [p.slug for p in selected] == ["three", "two", "one"]

    def test_limit_truncates_to_top_n(self) -> None:
        """limit이 상위 N개로 자른다(우선순위 상위부터)."""
        items = [
            _problem(slug=f"item-{i}", distractor_map=_distractors(i), persona_fit=_fit())
            for i in (1, 2, 3, 4, 5)
        ]
        # distractor 5,4개가 상위 2개.
        selected = select_metacognition_items(items, Persona.A_일반고고3, limit=2)
        assert [p.slug for p in selected] == ["item-5", "item-4"]

    def test_limit_none_returns_all_eligible(self) -> None:
        """limit=None(기본) → 적격 전부 반환(무제한)."""
        items = [
            _problem(slug=f"i-{i}", distractor_map=_distractors(1), persona_fit=_fit())
            for i in range(3)
        ]
        assert len(select_metacognition_items(items, Persona.A_일반고고3)) == 3

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 → 빈 리스트(상위 0개)."""
        items = [_problem(distractor_map=_distractors(1), persona_fit=_fit())]
        assert select_metacognition_items(items, Persona.A_일반고고3, limit=0) == []

    def test_empty_input_returns_empty(self) -> None:
        """빈 입력 → 빈 결과."""
        assert select_metacognition_items([], Persona.A_일반고고3) == []

    def test_copyright_blocked_items_excluded_from_selection(self) -> None:
        """선별에서도 본문 미보유 출처는 빠진다(저작권 게이트가 필터에 적용)."""
        ok = _problem(slug="ok", distractor_map=_distractors(1), persona_fit=_fit())
        blocked = _problem(
            slug="blocked",
            source_type=SourceType.평가원,
            distractor_map=_distractors(3),
            persona_fit=_fit(),
        )
        selected = select_metacognition_items([blocked, ok], Persona.A_일반고고3)
        assert [p.slug for p in selected] == ["ok"]

    def test_default_persona_used_when_omitted(self) -> None:
        """persona 생략 시 기본 A로 선별(공유 코어 첫 노출)."""
        items = [
            _problem(slug=f"a-{i}", distractor_map=_distractors(1), persona_fit=_fit())
            for i in range(2)
        ]
        selected = select_metacognition_items(items)
        assert {p.slug for p in selected} == {"a-0", "a-1"}

    def test_stable_sort_preserves_input_order_on_ties(self) -> None:
        """동률(같은 우선순위)은 입력 순서를 보존한다(안정정렬 계약)."""
        # 셋 다 distractor 1개·scoring 없음·diff 없음 → 동일 우선순위(2.0).
        first = _problem(slug="first", distractor_map=_distractors(1), persona_fit=_fit())
        second = _problem(slug="second", distractor_map=_distractors(1), persona_fit=_fit())
        third = _problem(slug="third", distractor_map=_distractors(1), persona_fit=_fit())
        selected = select_metacognition_items([first, second, third], Persona.A_일반고고3)
        assert [p.slug for p in selected] == ["first", "second", "third"]
