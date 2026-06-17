"""L6 영재(gifted) 트랙 게이팅 단위테스트 — 적격성·우선순위·선별·저작권 게이트.

검증:
  ① 대상 페르소나(E) + 높은 적합(>=0.7) + 심화(>=4.0) + (창안 CREATE 또는 융합) → 적격.
  ② 비대상 페르소나(A·B·C·D) → 부적격(닫힌 집합·RT 동형).
  ③ 본문 미보유 출처(평가원/EBS/교과서) → 저작권 노출 게이트로 차단(E라도).
  ④ 난이도 미달(<4.0)·난이도 None → 부적격(심화 하한 AND).
  ⑤ 창안·융합 어느 쪽도 아님 → 부적격(④ OR 둘 다 거짓).
  ⑥ 적합도 미달(<0.7) → 부적격.
  ⑦ `gifted_priority` 단조성 — CREATE>EVALUATE·융합·diff_integration·난이도 가산.
  ⑧ `select_gifted_items` — 혼합 풀에서 영재 적합만·우선순위 순·limit·안정정렬·데이터0 안전.

합성 픽스처만(실데이터 0). `_problem(**over)` 빌더(thinking/retake 패턴 답습).

레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·L6(`l6.gifted`)만 import한다.
"""

from __future__ import annotations

from whymath_backend.l6.gifted.gating import (
    GIFTED_MIN_DIFFICULTY,
    GIFTED_PERSONAS,
    gifted_priority,
    is_gifted_eligible,
    select_gifted_items,
)
from whymath_backend.schema.enums import (
    BloomLevel,
    Curriculum,
    Persona,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem


def _problem(**over: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본은 `source_type=자체생성`이라 영재 신호만 오버라이드하면 적격/부적격을 만든다
    (thinking/retake `_problem` 답습 — type: ignore 동일).
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


def _gifted_fit(score: float = 0.9) -> dict[Persona, float]:
    """페르소나 E에 충분한 persona_fit dict(기본 0.9 — 영재 임계 0.7 이상)."""
    return {Persona.E_홈스쿨링영재: score}


def _eligible(**over: object) -> Problem:
    """영재 적격 기본형(E 적합 0.9·난이도 4.5·CREATE) — 한 신호만 바꿔 경계를 시험."""
    base: dict[str, object] = {
        "persona_fit": _gifted_fit(),
        "difficulty_overall": 4.5,
        "bloom_level": BloomLevel.CREATE,
    }
    base.update(over)
    return _problem(**base)


# ──────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────
class TestConstants:
    def test_gifted_personas_are_e_only(self) -> None:
        """영재 대상 페르소나는 정확히 E(홈스쿨링 영재) 하나(닫힌 집합)."""
        assert GIFTED_PERSONAS == frozenset({Persona.E_홈스쿨링영재})

    def test_min_difficulty_default(self) -> None:
        """영재 심화 하한 기본은 4.0(KMO 입문 수준)."""
        assert GIFTED_MIN_DIFFICULTY == 4.0


# ──────────────────────────────────────────────────────────────────────
# is_gifted_eligible — 적격성 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsGiftedEligible:
    def test_e_high_fit_difficult_create_eligible(self) -> None:
        """E + 높은 적합 + 심화 + 창안(CREATE) → 적격."""
        assert is_gifted_eligible(_eligible(), Persona.E_홈스쿨링영재) is True

    def test_cross_unit_satisfies_without_create(self) -> None:
        """창안이 아니어도 단원 융합(is_cross_unit)이면 ④ 통과(OR)."""
        problem = _eligible(bloom_level=BloomLevel.ANALYZE, is_cross_unit=True)
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is True

    def test_default_persona_is_e(self) -> None:
        """persona 인자 생략 시 기본 E_홈스쿨링영재."""
        assert is_gifted_eligible(_eligible()) is True

    def test_non_target_personas_rejected(self) -> None:
        """비대상 페르소나(A·B·C·D) → 부적격(닫힌 집합·신호가 충분해도)."""
        # 모든 페르소나에 높은 적합도를 줘도 E 외엔 ① 게이트에서 탈락.
        problem = _eligible(
            persona_fit={
                Persona.A_일반고고3: 0.9,
                Persona.B_자사고N수: 0.9,
                Persona.C_검정고시N수: 0.9,
                Persona.D_학종고2: 0.9,
            }
        )
        for persona in (
            Persona.A_일반고고3,
            Persona.B_자사고N수,
            Persona.C_검정고시N수,
            Persona.D_학종고2,
        ):
            assert is_gifted_eligible(problem, persona) is False, persona

    def test_insufficient_fit_rejected(self) -> None:
        """E 적합도 미달(<0.7)이면 심화·창안이어도 부적격."""
        problem = _eligible(persona_fit=_gifted_fit(0.6))
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is False

    def test_fit_at_threshold_eligible(self) -> None:
        """경계값 — persona_fit == min_fit(0.7)이면 적격(>= 비교)."""
        problem = _eligible(persona_fit=_gifted_fit(0.7))
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재, min_fit=0.7) is True

    def test_below_min_difficulty_rejected(self) -> None:
        """난이도 미달(<4.0)이면 창안이어도 부적격(심화 하한 AND)."""
        problem = _eligible(difficulty_overall=3.9)
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is False

    def test_difficulty_at_threshold_eligible(self) -> None:
        """경계값 — difficulty_overall == min_difficulty(4.0)이면 적격(>= 비교)."""
        problem = _eligible(difficulty_overall=4.0)
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is True

    def test_none_difficulty_rejected(self) -> None:
        """difficulty_overall None이면 부적격(심화 하한 판정 불가)."""
        problem = _eligible(difficulty_overall=None)
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is False

    def test_neither_create_nor_cross_unit_rejected(self) -> None:
        """심화여도 창안(CREATE)도 융합(is_cross_unit)도 아니면 부적격(④ OR 둘 다 거짓)."""
        problem = _eligible(bloom_level=BloomLevel.ANALYZE, is_cross_unit=False)
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is False

    def test_custom_min_difficulty(self) -> None:
        """min_difficulty 파라미터로 하한을 조정할 수 있다."""
        problem = _eligible(difficulty_overall=4.2)
        # 하한을 4.5로 올리면 4.2는 미달 → 부적격.
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재, min_difficulty=4.5) is False

    def test_copyright_gate_blocks_metadata_only_sources(self) -> None:
        """저작권 노출 게이트 — 본문 미보유 출처는 E·심화·창안이어도 차단."""
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            problem = _eligible(source_type=source, persona_fit=_gifted_fit(0.99))
            assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is False, source

    def test_use_enum_values_string_keys_handled(self) -> None:
        """use_enum_values=True로 persona_fit 키·bloom_level이 문자열이어도 정규화 적중."""
        problem = _problem(
            persona_fit={Persona.E_홈스쿨링영재.value: 0.8},
            difficulty_overall=4.5,
            bloom_level=BloomLevel.CREATE.value,
        )
        assert is_gifted_eligible(problem, Persona.E_홈스쿨링영재) is True


# ──────────────────────────────────────────────────────────────────────
# gifted_priority — 우선순위 가중치(단조성)
# ──────────────────────────────────────────────────────────────────────
class TestGiftedPriority:
    def test_create_outweighs_evaluate(self) -> None:
        """창안(CREATE 2.0)이 평가(EVALUATE 1.5)보다 우선순위가 크다(다른 조건 동일)."""
        create = _problem(bloom_level=BloomLevel.CREATE)
        evaluate = _problem(bloom_level=BloomLevel.EVALUATE)
        assert gifted_priority(create) > gifted_priority(evaluate)

    def test_cross_unit_increases_priority(self) -> None:
        """단원 융합(is_cross_unit)이면 없을 때보다 우선순위가 크다."""
        fused = _problem(bloom_level=BloomLevel.CREATE, is_cross_unit=True)
        single = _problem(bloom_level=BloomLevel.CREATE, is_cross_unit=False)
        assert gifted_priority(fused) > gifted_priority(single)

    def test_diff_integration_increases_priority(self) -> None:
        """단원 융합도(diff_integration)가 높을수록 우선순위가 크다(보조 축)."""
        deep = _problem(bloom_level=BloomLevel.CREATE, diff_integration=5.0)
        shallow = _problem(bloom_level=BloomLevel.CREATE, diff_integration=1.0)
        assert gifted_priority(deep) > gifted_priority(shallow)

    def test_higher_difficulty_increases_priority(self) -> None:
        """종합 난이도가 높을수록 우선순위가 크다(보조 축·타이브레이커)."""
        hard = _problem(bloom_level=BloomLevel.CREATE, difficulty_overall=5.0)
        easy = _problem(bloom_level=BloomLevel.CREATE, difficulty_overall=4.0)
        assert gifted_priority(hard) > gifted_priority(easy)

    def test_non_top_bloom_no_bonus(self) -> None:
        """CREATE·EVALUATE가 아닌 bloom(ANALYZE·None)은 bloom 가중 0."""
        analyze = _problem(bloom_level=BloomLevel.ANALYZE, is_cross_unit=True)  # 융합 1.0만
        none_bloom = _problem(bloom_level=None, is_cross_unit=True)  # 융합 1.0만
        assert gifted_priority(analyze) == gifted_priority(none_bloom) == 1.0

    def test_priority_is_deterministic_and_sum_exact(self) -> None:
        """같은 입력은 같은 가중치(결정적)·가중 합 정확."""
        problem = _problem(
            bloom_level=BloomLevel.CREATE,  # 2.0
            is_cross_unit=True,  # 1.0
            diff_integration=3.0,  # 3.0
            difficulty_overall=4.5,  # 4.5
        )
        # 2.0 + 1.0 + 3.0 + 4.5 = 10.5
        assert gifted_priority(problem) == gifted_priority(problem) == 10.5

    def test_none_signals_treated_as_zero(self) -> None:
        """bloom None·is_cross_unit False·diff None은 0.0으로 취급."""
        bare = _problem()  # bloom None·is_cross_unit 기본 False·diff None
        assert gifted_priority(bare) == 0.0


# ──────────────────────────────────────────────────────────────────────
# select_gifted_items — 선별·정렬·limit
# ──────────────────────────────────────────────────────────────────────
class TestSelectGiftedItems:
    def test_filters_to_eligible_only(self) -> None:
        """혼합 풀(저난도·비창안·영재 적합 섞음)에서 영재 적합만 남는다."""
        gifted_item = _eligible(slug="gifted-fit")
        # 난이도 미달 → 탈락.
        easy = _eligible(slug="easy", difficulty_overall=2.0)
        # 창안·융합 아님 → 탈락.
        plain = _eligible(slug="plain", bloom_level=BloomLevel.APPLY, is_cross_unit=False)

        selected = select_gifted_items([easy, gifted_item, plain], Persona.E_홈스쿨링영재)
        assert [p.slug for p in selected] == ["gifted-fit"]

    def test_orders_by_priority_descending(self) -> None:
        """창안·융합·고난도가 앞에 온다(우선순위 내림차순)."""
        # low: ANALYZE(0) + 융합 1.0 + 난이도 4.0 = 5.0
        low = _eligible(
            slug="low",
            bloom_level=BloomLevel.ANALYZE,
            is_cross_unit=True,
            difficulty_overall=4.0,
        )
        # high: CREATE 2.0 + 융합 1.0 + 난이도 5.0 = 8.0
        high = _eligible(
            slug="high",
            bloom_level=BloomLevel.CREATE,
            is_cross_unit=True,
            difficulty_overall=5.0,
        )
        # mid: CREATE 2.0 + 난이도 4.0 = 6.0
        mid = _eligible(
            slug="mid",
            bloom_level=BloomLevel.CREATE,
            is_cross_unit=False,
            difficulty_overall=4.0,
        )

        selected = select_gifted_items([low, mid, high], Persona.E_홈스쿨링영재)
        assert [p.slug for p in selected] == ["high", "mid", "low"]

    def test_limit_truncates_to_top_n(self) -> None:
        """limit이 상위 N개로 자른다(우선순위 상위부터)."""
        items = [_eligible(slug=f"item-{i}", difficulty_overall=float(i)) for i in (4, 5)]
        # 더 어려운 item-5가 앞.
        selected = select_gifted_items(items, Persona.E_홈스쿨링영재, limit=1)
        assert [p.slug for p in selected] == ["item-5"]

    def test_limit_none_returns_all_eligible(self) -> None:
        """limit=None(기본) → 적격 전부 반환(무제한)."""
        items = [_eligible(slug=f"i-{i}") for i in range(3)]
        assert len(select_gifted_items(items, Persona.E_홈스쿨링영재)) == 3

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 → 빈 리스트(상위 0개)."""
        assert select_gifted_items([_eligible()], Persona.E_홈스쿨링영재, limit=0) == []

    def test_empty_input_returns_empty(self) -> None:
        """빈 입력 → 빈 결과."""
        assert select_gifted_items([], Persona.E_홈스쿨링영재) == []

    def test_non_target_persona_selects_nothing(self) -> None:
        """비대상 페르소나(A)면 적합 문항이 많아도 전부 탈락 → 빈 결과(닫힌 집합)."""
        items = [
            _problem(
                persona_fit={Persona.A_일반고고3: 0.9},
                difficulty_overall=4.5,
                bloom_level=BloomLevel.CREATE,
            )
            for _ in range(3)
        ]
        assert select_gifted_items(items, Persona.A_일반고고3) == []

    def test_copyright_blocked_items_excluded_from_selection(self) -> None:
        """선별에서도 본문 미보유 출처는 빠진다(저작권 게이트가 필터에 적용)."""
        ok = _eligible(slug="ok")
        blocked = _eligible(slug="blocked", source_type=SourceType.평가원)
        selected = select_gifted_items([blocked, ok], Persona.E_홈스쿨링영재)
        assert [p.slug for p in selected] == ["ok"]

    def test_default_persona_used_when_omitted(self) -> None:
        """persona 생략 시 기본 E로 선별(영재 트랙 대상)."""
        items = [_eligible(slug=f"e-{i}") for i in range(2)]
        selected = select_gifted_items(items)
        assert {p.slug for p in selected} == {"e-0", "e-1"}

    def test_data_zero_safe_empty_corpus(self) -> None:
        """영재 콘텐츠 미존재(전부 일반 난이도·비창안)면 빈 결과(데이터0 안전).

        영재 게이팅을 선깔아도 코퍼스에 영재급 문항이 없으면 아무것도 노출되지 않는다 —
        데이터가 차오르면 자동 활성(학교진도 성취기준 선례).
        """
        ordinary = [
            _problem(
                slug=f"ord-{i}",
                persona_fit=_gifted_fit(),
                difficulty_overall=3.0,  # 심화 하한 미달
                bloom_level=BloomLevel.APPLY,
            )
            for i in range(5)
        ]
        assert select_gifted_items(ordinary, Persona.E_홈스쿨링영재) == []

    def test_stable_sort_preserves_input_order_on_ties(self) -> None:
        """동률(같은 우선순위)은 입력 순서를 보존한다(안정정렬 계약)."""
        # 셋 다 CREATE·융합 없음·diff 없음·난이도 4.0 → 동일 우선순위(2.0+4.0=6.0).
        first = _eligible(slug="first", is_cross_unit=False, difficulty_overall=4.0)
        second = _eligible(slug="second", is_cross_unit=False, difficulty_overall=4.0)
        third = _eligible(slug="third", is_cross_unit=False, difficulty_overall=4.0)
        selected = select_gifted_items([first, second, third], Persona.E_홈스쿨링영재)
        assert [p.slug for p in selected] == ["first", "second", "third"]
