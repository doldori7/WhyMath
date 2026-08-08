"""L6 사고력(thinking) 모드 게이팅 단위테스트 — 적격성·우선순위·선별·저작권 게이트.

검증:
  ① 사고력 주신호(bloom_level 상위 3단계 ANALYZE/EVALUATE/CREATE) + 페르소나 적합(persona_fit
     >= min_fit) → 적격(True).
  ② bloom_level 하위 단계(APPLY 이하) → 부적격(False·사고력 미해당).
  ③ bloom_level None(사고력 미표지) → 부적격(False).
  ④ 본문 미보유 출처(평가원/EBS/교과서) → 저작권 노출 게이트로 차단(상위 bloom·높은 적합도라도).
  ⑤ 비대상 페르소나(persona_fit 미달) → 부적격(False). 단 *닫힌 집합 게이트는 없다* — A(MVP)도
     적합도 충족이면 통과(MVP 페르소나 배제 금지).
  ⑥ `thinking_priority` 단조성 — Bloom 상위 단계(CREATE>EVALUATE>ANALYZE) 큰 쪽이 큼·사고력
     시그니처 개수 가산·diff_case_analysis/diff_integration 가산.
  ⑦ `select_thinking_items` — 혼합 풀에서 사고력만 남김·우선순위 순(CREATE>EVALUATE)·limit·안정정렬.

합성 픽스처만(실데이터 0). `_problem(**over)` 빌더로 자체생성 최소 문항을 만들고 오버라이드한다
(`tests/backend/l6/suneung/test_gating.py`·`tests/backend/schema/test_problem.py` 헬퍼 패턴 답습).

레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·L6(`l6.thinking`)만 import한다.
"""

from __future__ import annotations

from whymath_backend.l6.thinking.gating import (
    THINKING_BLOOM_LEVELS,
    is_thinking_eligible,
    select_thinking_items,
    thinking_priority,
)
from whymath_backend.schema.enums import (
    BloomLevel,
    Curriculum,
    Persona,
    ReviewStatus,
    SignaturePattern,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem


def _problem(**over: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본은 `source_type=자체생성`(저작권 노출 게이트를 통과하는 출처)이라 사고력 신호만
    오버라이드하면 적격/부적격을 자유로이 만든다. 본문 미보유 출처(평가원/EBS/교과서)는
    `source_type=...`로 오버라이드해 저작권 게이트를 시험한다.
    (`l6/suneung/test_gating.py`의 `_problem` 패턴 답습 — type: ignore도 동일.)
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


# 사고력 적격을 만드는 *공통 페르소나 적합* 헬퍼 — 주신호(bloom)만 시험할 때 페르소나
# 게이트는 항상 통과시키려고 기본 페르소나(D) 적합도를 충분히 둔다. 닫힌 집합 게이트가
# 없으므로 페르소나 적합은 persona_fit으로만 열린다(모듈 계약).
def _fit(persona: Persona = Persona.D_학종고2, score: float = 0.9) -> dict[Persona, float]:
    """주어진 페르소나에 충분한 persona_fit dict(기본 D·0.9)."""
    return {persona: score}


# ──────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────
class TestConstants:
    def test_thinking_bloom_levels_are_top_three(self) -> None:
        """사고력 주신호 Bloom 단계는 정확히 상위 3단계(ANALYZE·EVALUATE·CREATE)."""
        assert THINKING_BLOOM_LEVELS == frozenset(
            {BloomLevel.ANALYZE, BloomLevel.EVALUATE, BloomLevel.CREATE}
        )

    def test_thinking_bloom_levels_exclude_lower_three(self) -> None:
        """하위 3단계(REMEMBER·UNDERSTAND·APPLY)는 사고력 주신호가 아니다."""
        assert BloomLevel.REMEMBER not in THINKING_BLOOM_LEVELS
        assert BloomLevel.UNDERSTAND not in THINKING_BLOOM_LEVELS
        assert BloomLevel.APPLY not in THINKING_BLOOM_LEVELS


# ──────────────────────────────────────────────────────────────────────
# is_thinking_eligible — 적격성 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsThinkingEligible:
    def test_top_bloom_levels_with_fit_eligible(self) -> None:
        """상위 3단계(ANALYZE/EVALUATE/CREATE) + 페르소나 적합 → 적격."""
        for level in (BloomLevel.ANALYZE, BloomLevel.EVALUATE, BloomLevel.CREATE):
            problem = _problem(bloom_level=level, persona_fit=_fit())
            assert is_thinking_eligible(problem, Persona.D_학종고2) is True, level

    def test_default_persona_is_d_haksong(self) -> None:
        """persona 인자 생략 시 기본 D_학종고2(사고력 주 대상)."""
        problem = _problem(bloom_level=BloomLevel.CREATE, persona_fit=_fit())
        # persona 미지정 → D로 판정되어 적격.
        assert is_thinking_eligible(problem) is True

    def test_lower_bloom_levels_rejected(self) -> None:
        """하위 3단계(REMEMBER/UNDERSTAND/APPLY)는 페르소나 적합이어도 부적격(사고력 미해당)."""
        for level in (BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.APPLY):
            problem = _problem(bloom_level=level, persona_fit=_fit())
            assert is_thinking_eligible(problem, Persona.D_학종고2) is False, level

    def test_none_bloom_level_rejected(self) -> None:
        """bloom_level None(사고력 미표지)이면 페르소나 적합이어도 부적격."""
        problem = _problem(persona_fit=_fit())  # bloom_level 기본 None
        assert is_thinking_eligible(problem, Persona.D_학종고2) is False

    def test_insufficient_persona_fit_rejected(self) -> None:
        """페르소나 적합도 미달(<min_fit)이면 상위 bloom이어도 부적격."""
        problem = _problem(
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.D_학종고2: 0.3},  # 0.5 미만
        )
        assert is_thinking_eligible(problem, Persona.D_학종고2) is False

    def test_persona_fit_at_threshold_is_eligible(self) -> None:
        """경계값 — persona_fit == min_fit(0.5)이면 적격(>= 비교)."""
        problem = _problem(
            bloom_level=BloomLevel.ANALYZE,
            persona_fit={Persona.D_학종고2: 0.5},
        )
        assert is_thinking_eligible(problem, Persona.D_학종고2, min_fit=0.5) is True

    def test_mvp_persona_a_not_excluded_by_closed_set(self) -> None:
        """MVP 페르소나 A(일반고 고3)도 적합도 충족이면 통과한다(닫힌 집합 게이트 없음).

        사고력은 페르소나가 아니라 문항의 사고 수준이 본질 — 주 대상 D·E가 아닌 A도
        persona_fit이 임계 이상이면 사고력 문항을 노출받아야 한다(MVP 페르소나 배제 금지).
        """
        problem = _problem(
            bloom_level=BloomLevel.EVALUATE,
            persona_fit={Persona.A_일반고고3: 0.8},
        )
        assert is_thinking_eligible(problem, Persona.A_일반고고3) is True

    def test_persona_without_fit_rejected(self) -> None:
        """persona_fit에 해당 페르소나가 없으면(0.0 취급) 상위 bloom이어도 부적격."""
        problem = _problem(
            bloom_level=BloomLevel.CREATE,
            persona_fit={Persona.E_홈스쿨링영재: 0.9},  # 조회 대상 A는 없음
        )
        assert is_thinking_eligible(problem, Persona.A_일반고고3) is False

    def test_copyright_gate_blocks_metadata_only_sources(self) -> None:
        """저작권 노출 게이트 — 본문 미보유 출처는 상위 bloom·높은 적합도라도 차단.

        평가원/EBS/교과서는 본문 미보유(구조 메타 전용)라 학생 노출 불가 → ① 게이트에서
        무조건 탈락. 본문 필드(question_text 등)를 비워 둬야 Problem 검증을 통과하므로
        빌더 기본(본문 None)을 그대로 쓰되 source_type만 바꾼다.
        """
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            problem = _problem(
                source_type=source,
                bloom_level=BloomLevel.CREATE,  # 최상위 사고력 신호여도
                signature_patterns=[SignaturePattern.CASE_ANALYSIS_DEEP],  # 시그니처가 있어도
                persona_fit={Persona.D_학종고2: 0.99},  # 적합도가 높아도
            )
            assert is_thinking_eligible(problem, Persona.D_학종고2) is False, source

    def test_use_enum_values_string_keys_handled(self) -> None:
        """use_enum_values=True로 persona_fit 키·bloom_level이 문자열이어도 정규화 적중.

        Problem이 use_enum_values=True라, 키를 enum이 아닌 *문자열 값*으로 줘도
        `_persona_fit`이 문자열 폴백으로 적중하고 bloom_level 문자열도 정규화돼야 한다.
        """
        problem = _problem(
            bloom_level=BloomLevel.ANALYZE,
            persona_fit={Persona.E_홈스쿨링영재.value: 0.7},
        )
        assert is_thinking_eligible(problem, Persona.E_홈스쿨링영재) is True


# ──────────────────────────────────────────────────────────────────────
# thinking_priority — 우선순위 가중치(단조성)
# ──────────────────────────────────────────────────────────────────────
class TestThinkingPriority:
    def test_higher_bloom_level_increases_priority(self) -> None:
        """Bloom 상위 단계(CREATE>EVALUATE>ANALYZE)가 우선순위가 크다(다른 조건 동일)."""
        create = _problem(bloom_level=BloomLevel.CREATE)
        evaluate = _problem(bloom_level=BloomLevel.EVALUATE)
        analyze = _problem(bloom_level=BloomLevel.ANALYZE)
        assert thinking_priority(create) > thinking_priority(evaluate)
        assert thinking_priority(evaluate) > thinking_priority(analyze)

    def test_bloom_is_primary_signal_outweighs_signature(self) -> None:
        """주신호 Bloom(ANALYZE 2.0)이 사고력 시그니처 단독(+1.0)보다 크다(상대 순서 계약)."""
        bloom_only = _problem(bloom_level=BloomLevel.ANALYZE)  # 2.0
        signature_only = _problem(
            bloom_level=None,
            signature_patterns=[SignaturePattern.CASE_ANALYSIS_DEEP],
        )  # +1.0(bloom 가중 0)
        assert thinking_priority(bloom_only) > thinking_priority(signature_only)

    def test_thinking_signature_count_increases_priority(self) -> None:
        """사고력 시그니처를 더 많이 가질수록 우선순위가 크다(개수 단조·다른 조건 동일)."""
        two = _problem(
            bloom_level=BloomLevel.ANALYZE,
            signature_patterns=[
                SignaturePattern.CASE_ANALYSIS_DEEP,
                SignaturePattern.CROSS_UNIT_FUSION,
            ],
        )
        one = _problem(
            bloom_level=BloomLevel.ANALYZE,
            signature_patterns=[SignaturePattern.CASE_ANALYSIS_DEEP],
        )
        assert thinking_priority(two) > thinking_priority(one)

    def test_non_thinking_signature_not_counted(self) -> None:
        """사고력 3종이 아닌 시그니처(예: COMPOUND_CHOICES)는 가산하지 않는다."""
        with_other = _problem(
            bloom_level=BloomLevel.ANALYZE,
            signature_patterns=[SignaturePattern.COMPOUND_CHOICES],  # 사고력 3종 아님
        )
        bare = _problem(bloom_level=BloomLevel.ANALYZE)
        assert thinking_priority(with_other) == thinking_priority(bare)

    def test_diff_case_analysis_increases_priority(self) -> None:
        """케이스 분류 깊이(diff_case_analysis)가 높을수록 우선순위가 크다(보조 축)."""
        deep = _problem(bloom_level=BloomLevel.ANALYZE, diff_case_analysis=5.0)
        shallow = _problem(bloom_level=BloomLevel.ANALYZE, diff_case_analysis=1.0)
        assert thinking_priority(deep) > thinking_priority(shallow)

    def test_diff_integration_increases_priority(self) -> None:
        """단원 융합도(diff_integration)가 높을수록 우선순위가 크다(보조 축)."""
        fused = _problem(bloom_level=BloomLevel.ANALYZE, diff_integration=5.0)
        single = _problem(bloom_level=BloomLevel.ANALYZE, diff_integration=1.0)
        assert thinking_priority(fused) > thinking_priority(single)

    def test_higher_difficulty_increases_priority(self) -> None:
        """종합 난이도가 높을수록 우선순위가 크다(보조 축·다른 조건 동일)."""
        hard = _problem(bloom_level=BloomLevel.ANALYZE, difficulty_overall=5.0)
        easy = _problem(bloom_level=BloomLevel.ANALYZE, difficulty_overall=1.0)
        assert thinking_priority(hard) > thinking_priority(easy)

    def test_priority_is_deterministic_and_sum_exact(self) -> None:
        """같은 입력은 같은 가중치(결정적)·가중 합 정확."""
        problem = _problem(
            bloom_level=BloomLevel.CREATE,  # 4.0
            signature_patterns=[
                SignaturePattern.CASE_ANALYSIS_DEEP,
                SignaturePattern.CROSS_UNIT_FUSION,
            ],  # 2개 × 1.0 = 2.0
            diff_case_analysis=3.0,  # 3.0
            diff_integration=2.0,  # 2.0
            difficulty_overall=4.0,  # 4.0
        )
        # 4.0 + 2.0 + 3.0 + 2.0 + 4.0 = 15.0
        assert thinking_priority(problem) == thinking_priority(problem) == 15.0

    def test_none_diffs_treated_as_zero(self) -> None:
        """diff_case_analysis·diff_integration·difficulty_overall=None은 0.0으로 취급."""
        bare = _problem(bloom_level=BloomLevel.ANALYZE)  # 보조 축 전부 기본 None
        # ANALYZE(2.0) + 시그니처 0 + diff 0 = 2.0
        assert thinking_priority(bare) == 2.0

    def test_empty_signature_patterns_no_bonus(self) -> None:
        """빈 signature_patterns([])는 사고력 시그니처 0개 — 가산 없음."""
        empty = _problem(bloom_level=BloomLevel.ANALYZE, signature_patterns=[])
        bare = _problem(bloom_level=BloomLevel.ANALYZE)
        assert thinking_priority(empty) == thinking_priority(bare) == 2.0


# ──────────────────────────────────────────────────────────────────────
# select_thinking_items — 선별·정렬·limit
# ──────────────────────────────────────────────────────────────────────
class TestSelectThinkingItems:
    def test_filters_to_eligible_only(self) -> None:
        """혼합 풀(하위 bloom·bloom None·사고력 적합 섞음)에서 사고력 적합만 남는다."""
        thinking_item = _problem(
            slug="thinking-fit",
            bloom_level=BloomLevel.CREATE,
            persona_fit=_fit(),
        )
        # 하위 인지 수준(APPLY) → 탈락.
        apply_item = _problem(
            slug="apply-only",
            bloom_level=BloomLevel.APPLY,
            persona_fit=_fit(),
        )
        # bloom 미표지(None) → 탈락.
        bloom_none_item = _problem(slug="no-bloom", persona_fit=_fit())

        selected = select_thinking_items(
            [apply_item, thinking_item, bloom_none_item], Persona.D_학종고2
        )
        assert [p.slug for p in selected] == ["thinking-fit"]

    def test_orders_by_bloom_level_descending(self) -> None:
        """Bloom 상위 단계 순(CREATE>EVALUATE>ANALYZE)으로 앞에 온다(우선순위 내림차순)."""
        analyze = _problem(slug="analyze", bloom_level=BloomLevel.ANALYZE, persona_fit=_fit())
        create = _problem(slug="create", bloom_level=BloomLevel.CREATE, persona_fit=_fit())
        evaluate = _problem(slug="evaluate", bloom_level=BloomLevel.EVALUATE, persona_fit=_fit())

        # 입력은 우선순위 역순으로 줘서 정렬이 실제로 일어나는지 본다.
        selected = select_thinking_items([analyze, evaluate, create], Persona.D_학종고2)
        assert [p.slug for p in selected] == ["create", "evaluate", "analyze"]

    def test_signature_count_breaks_tie_within_same_bloom(self) -> None:
        """같은 Bloom 단계에서 사고력 시그니처 개수가 많은 문항이 앞에 온다."""
        more_sig = _problem(
            slug="more-sig",
            bloom_level=BloomLevel.ANALYZE,
            signature_patterns=[
                SignaturePattern.CASE_ANALYSIS_DEEP,
                SignaturePattern.GRAPH_SHAPE_INFERENCE,
            ],
            persona_fit=_fit(),
        )
        less_sig = _problem(
            slug="less-sig",
            bloom_level=BloomLevel.ANALYZE,
            signature_patterns=[SignaturePattern.CASE_ANALYSIS_DEEP],
            persona_fit=_fit(),
        )
        selected = select_thinking_items([less_sig, more_sig], Persona.D_학종고2)
        assert [p.slug for p in selected] == ["more-sig", "less-sig"]

    def test_limit_truncates_to_top_n(self) -> None:
        """limit이 상위 N개로 자른다(우선순위 상위부터)."""
        items = [
            _problem(
                slug=f"item-{i}",
                bloom_level=BloomLevel.ANALYZE,
                difficulty_overall=float(i),
                persona_fit=_fit(),
            )
            for i in (1, 2, 3, 4, 5)
        ]
        # 난이도 5,4가 상위 2개(ANALYZE 2.0 동일 + 난이도).
        selected = select_thinking_items(items, Persona.D_학종고2, limit=2)
        assert [p.slug for p in selected] == ["item-5", "item-4"]

    def test_limit_none_returns_all_eligible(self) -> None:
        """limit=None(기본) → 적격 전부 반환(무제한)."""
        items = [
            _problem(slug=f"i-{i}", bloom_level=BloomLevel.EVALUATE, persona_fit=_fit())
            for i in range(3)
        ]
        selected = select_thinking_items(items, Persona.D_학종고2)
        assert len(selected) == 3

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 → 빈 리스트(상위 0개)."""
        items = [_problem(bloom_level=BloomLevel.CREATE, persona_fit=_fit())]
        assert select_thinking_items(items, Persona.D_학종고2, limit=0) == []

    def test_empty_input_returns_empty(self) -> None:
        """빈 입력 → 빈 결과."""
        assert select_thinking_items([], Persona.D_학종고2) == []

    def test_non_target_persona_without_fit_selects_nothing(self) -> None:
        """조회 페르소나의 적합도가 없으면(0.0) 상위 bloom 문항이 많아도 전부 탈락 → 빈 결과.

        닫힌 집합 게이트는 없으나 persona_fit이 열어주지 않으면 통과하지 못한다(주 게이트).
        """
        items = [
            _problem(
                bloom_level=BloomLevel.CREATE,
                persona_fit={Persona.E_홈스쿨링영재: 0.9},  # 조회 대상 A는 없음
            )
            for _ in range(3)
        ]
        assert select_thinking_items(items, Persona.A_일반고고3) == []

    def test_mvp_persona_a_selected_when_fit(self) -> None:
        """A(MVP)도 적합도 충족이면 사고력 문항을 선별받는다(닫힌 집합 게이트 없음)."""
        items = [
            _problem(
                slug=f"a-{i}",
                bloom_level=BloomLevel.EVALUATE,
                persona_fit={Persona.A_일반고고3: 0.8},
            )
            for i in range(2)
        ]
        selected = select_thinking_items(items, Persona.A_일반고고3)
        assert {p.slug for p in selected} == {"a-0", "a-1"}

    def test_copyright_blocked_items_excluded_from_selection(self) -> None:
        """선별에서도 본문 미보유 출처는 빠진다(저작권 게이트가 필터에 적용).

        평가원 기출 본문은 노출 불가(자체생성 동등문제만).
        """
        ok = _problem(slug="ok", bloom_level=BloomLevel.CREATE, persona_fit=_fit())
        # 평가원 출처(본문 미보유) — 최상위 사고력 신호여도 노출 불가.
        blocked = _problem(
            slug="blocked",
            source_type=SourceType.평가원,
            bloom_level=BloomLevel.CREATE,
            persona_fit=_fit(),
        )
        selected = select_thinking_items([blocked, ok], Persona.D_학종고2)
        assert [p.slug for p in selected] == ["ok"]

    def test_default_persona_used_when_omitted(self) -> None:
        """persona 생략 시 기본 D로 선별(사고력 주 대상)."""
        items = [
            _problem(slug=f"d-{i}", bloom_level=BloomLevel.ANALYZE, persona_fit=_fit())
            for i in range(2)
        ]
        # persona 미지정 → D로 판정되어 둘 다 적격.
        selected = select_thinking_items(items)
        assert {p.slug for p in selected} == {"d-0", "d-1"}

    def test_stable_sort_preserves_input_order_on_ties(self) -> None:
        """동률(같은 우선순위)은 입력 순서를 보존한다(안정정렬 계약)."""
        # 셋 다 ANALYZE·시그니처 없음·diff 동일 → 동일 우선순위(2.0).
        first = _problem(slug="first", bloom_level=BloomLevel.ANALYZE, persona_fit=_fit())
        second = _problem(slug="second", bloom_level=BloomLevel.ANALYZE, persona_fit=_fit())
        third = _problem(slug="third", bloom_level=BloomLevel.ANALYZE, persona_fit=_fit())
        selected = select_thinking_items([first, second, third], Persona.D_학종고2)
        assert [p.slug for p in selected] == ["first", "second", "third"]
