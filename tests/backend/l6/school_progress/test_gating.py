"""L6 학교진도 모드 게이팅 단위테스트 — 적격성·우선순위·선별·저작권/교육과정 게이트.

검증:
  ① 대상 페르소나(A·D 재학생) + 진도 신호(단원 겹침 또는 persona_fit 폴백) → 적격(True).
  ② 비재학 페르소나(B·C N수·E 홈스쿨) → 부적격(False).
  ③ 본문 미보유 출처(평가원/EBS/교과서) → 저작권 노출 게이트로 차단(진도 정합이어도 False).
  ④ target_unit_codes 겹침 有 → 적격 / 無 → 부적격(단원 정합 게이트).
  ⑤ target_unit_codes 미지정 시 persona_fit 폴백 동작(>=min_fit → 적격).
  ⑥ curriculum_version 불일치 → 부적격(진도는 교육과정 버전 정합 필수).
  ⑦ `select_school_progress_items` — 혼합 풀에서 진도 적합만 남고 우선순위·limit 동작.
  ⑧ `school_progress_priority` 단조성 — 겹치는 단원이 많을수록 큼·난이도 보조 축 등.
  ⑨ 성취기준 매칭 심화(이 슬라이스): 성취기준 겹침 적격·우선순위 위계(×3.0>단원×2.0 단조)·
     **OR 폴백(성취기준 불일치+단원 일치→적격, AND 아님)**·데이터부재 폴백(빈 codes+성취기준
     타깃+단원 일치→통과)·차단 불변(평가원+성취기준 완벽일치→여전히 False)·하위호환
     (target_achievement_codes 미지정 시 기존 케이스 그대로)·결정성(정확 합).

합성 픽스처만(실데이터 0). `_problem(**over)` 빌더로 자체생성 최소 문항을 만들고 오버라이드한다
(`tests/backend/l6/retake/test_gating.py`·`tests/backend/l6/suneung/test_gating.py` 헬퍼 패턴 답습).

레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·L6(`l6.school_progress`)만
import한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l6.school_progress.gating import (
    SCHOOL_PROGRESS_PERSONAS,
    curriculum_depth_alignment,
    is_school_progress_eligible,
    school_progress_priority,
    select_school_progress_items,
)
from whymath_backend.schema.enums import (
    Curriculum,
    Persona,
    RequiredDepth,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem


def _problem(**over: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본은 `source_type=자체생성`(저작권 노출 게이트를 통과하는 출처)·`curriculum_version=
    2022 개정`·`unit_codes=['CAL-INT-DEF']`이라 진도 신호만 오버라이드하면 적격/부적격을
    자유로이 만든다. 본문 미보유 출처(평가원/EBS/교과서)는 `source_type=...`로 오버라이드해
    저작권 게이트를 시험한다.
    (`l6/retake/test_gating.py`·`l6/suneung/test_gating.py`의 `_problem` 패턴 답습 —
    type: ignore 동일.)
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
    def test_school_progress_personas_are_a_and_d(self) -> None:
        """학교진도 대상 페르소나는 정확히 A(일반고고3)·D(학종고2) 둘(재학생)."""
        assert SCHOOL_PROGRESS_PERSONAS == frozenset({Persona.A_일반고고3, Persona.D_학종고2})

    def test_school_progress_personas_exclude_retakers_and_homeschool(self) -> None:
        """N수(B·C 비재학)·영재(E 홈스쿨)는 학교진도 모드 대상이 아니다."""
        assert Persona.B_자사고N수 not in SCHOOL_PROGRESS_PERSONAS
        assert Persona.C_검정고시N수 not in SCHOOL_PROGRESS_PERSONAS
        assert Persona.E_홈스쿨링영재 not in SCHOOL_PROGRESS_PERSONAS


# ──────────────────────────────────────────────────────────────────────
# is_school_progress_eligible — 적격성 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsSchoolProgressEligible:
    def test_target_persona_with_unit_overlap_eligible(self) -> None:
        """A 페르소나 + 현재 진도 단원과 겹침 → 적격(진도 정합 신호로 통과)."""
        problem = _problem(unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"])
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is True
        )

    def test_default_persona_is_a_general_high_grade3(self) -> None:
        """persona 인자 생략 시 기본 A_일반고고3(MVP 재학생 정면 대상)."""
        problem = _problem(unit_codes=["CAL-INT-DEF"])
        # persona 미지정 → A로 판정되어 적격.
        assert is_school_progress_eligible(problem, target_unit_codes={"CAL-INT-DEF"}) is True

    def test_persona_d_haksong_is_eligible(self) -> None:
        """D 페르소나(학종 고2·재학생)도 학교진도 모드 대상이다."""
        problem = _problem(unit_codes=["CAL-INT-DEF"])
        assert (
            is_school_progress_eligible(
                problem,
                Persona.D_학종고2,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is True
        )

    def test_unit_overlap_absent_rejected(self) -> None:
        """target_unit_codes가 주어졌는데 겹치는 단원이 없으면 부적격(진도 부정합)."""
        problem = _problem(unit_codes=["GEO-VECTOR"])
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is False
        )

    def test_persona_fit_fallback_when_no_target_units(self) -> None:
        """target_unit_codes 미지정 시 persona_fit 폴백 — 적합도 충족(>=0.5)이면 적격."""
        problem = _problem(persona_fit={Persona.A_일반고고3: 0.8})
        # target_unit_codes 없음 → persona_fit 폴백 경로.
        assert is_school_progress_eligible(problem, Persona.A_일반고고3) is True

    def test_persona_fit_fallback_at_threshold_is_eligible(self) -> None:
        """경계값 — persona_fit == min_fit(0.5)이면 폴백 적격(>= 비교)."""
        problem = _problem(persona_fit={Persona.A_일반고고3: 0.5})
        assert is_school_progress_eligible(problem, Persona.A_일반고고3, min_fit=0.5) is True

    def test_persona_fit_fallback_below_threshold_rejected(self) -> None:
        """폴백 경로에서 persona_fit 미달(<0.5)이면 부적격."""
        problem = _problem(persona_fit={Persona.A_일반고고3: 0.3})
        assert is_school_progress_eligible(problem, Persona.A_일반고고3) is False

    def test_no_target_units_and_no_persona_fit_rejected(self) -> None:
        """target_unit_codes 없고 persona_fit도 비어 있으면 부적격(적합도 0.0 < 0.5)."""
        problem = _problem()
        assert is_school_progress_eligible(problem, Persona.A_일반고고3) is False

    def test_non_target_personas_rejected(self) -> None:
        """비재학 페르소나(B·C·E) → 부적격 — 진도 정합·적합도가 있어도 막힌다."""
        # 진도 단원 겹침 + 높은 적합도라도 비재학 페르소나면 ① 게이트에서 탈락.
        problem = _problem(
            unit_codes=["CAL-INT-DEF"],
            persona_fit={
                Persona.B_자사고N수: 0.9,
                Persona.C_검정고시N수: 0.9,
                Persona.E_홈스쿨링영재: 0.9,
            },
        )
        for persona in (Persona.B_자사고N수, Persona.C_검정고시N수, Persona.E_홈스쿨링영재):
            assert (
                is_school_progress_eligible(problem, persona, target_unit_codes={"CAL-INT-DEF"})
                is False
            ), persona

    def test_copyright_gate_blocks_metadata_only_sources(self) -> None:
        """저작권 노출 게이트 — 본문 미보유 출처는 A 페르소나·진도 정합이어도 차단.

        평가원/EBS/교과서는 본문 미보유(구조 메타 전용)라 학생 노출 불가 →
        ② 게이트에서 무조건 탈락. 본문 필드(question_text 등)를 비워 둬야 Problem
        검증을 통과하므로 빌더 기본(본문 None)을 그대로 쓰되 source_type만 바꾼다.
        """
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            problem = _problem(
                source_type=source,
                unit_codes=["CAL-INT-DEF"],  # 진도 단원이 겹쳐도
                persona_fit={Persona.A_일반고고3: 0.99},  # 적합도가 높아도
            )
            assert (
                is_school_progress_eligible(
                    problem,
                    Persona.A_일반고고3,
                    target_unit_codes={"CAL-INT-DEF"},
                )
                is False
            ), source

    def test_curriculum_version_mismatch_rejected(self) -> None:
        """교육과정 버전 불일치 → 부적격(진도는 교육과정 버전 정합 필수)."""
        # 문항은 2015 개정인데 진도(기준)는 2022 개정 → 불일치로 탈락.
        problem = _problem(
            curriculum_version=Curriculum.REVISION_2015,
            unit_codes=["CAL-INT-DEF"],
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
                curriculum_version=Curriculum.REVISION_2022,
            )
            is False
        )

    def test_curriculum_version_match_eligible(self) -> None:
        """교육과정 버전 일치 + 진도 단원 겹침 → 적격."""
        problem = _problem(
            curriculum_version=Curriculum.REVISION_2022,
            unit_codes=["CAL-INT-DEF"],
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
                curriculum_version=Curriculum.REVISION_2022,
            )
            is True
        )

    def test_curriculum_version_none_skips_gate(self) -> None:
        """curriculum_version 인자 미지정 → 버전 게이트 건너뜀(문항 버전 무관 통과)."""
        # 문항은 2015 개정이지만 기준 버전을 안 주면 ③ 게이트를 건너뛰어 진도 단원만 본다.
        problem = _problem(
            curriculum_version=Curriculum.REVISION_2015,
            unit_codes=["CAL-INT-DEF"],
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is True
        )

    def test_use_enum_values_string_keys_handled(self) -> None:
        """use_enum_values=True로 persona_fit 키가 문자열이어도 적합도가 조회된다(폴백 경로).

        Problem이 use_enum_values=True라, 키를 enum이 아닌 *문자열 값*으로 줘도
        `_shared.persona_fit`이 문자열 폴백으로 적중해야 한다(정규화 계약).
        """
        problem = _problem(persona_fit={Persona.D_학종고2.value: 0.7})
        assert is_school_progress_eligible(problem, Persona.D_학종고2) is True

    # ── 성취기준 매칭 심화(이 슬라이스) ──────────────────────────────────────
    def test_achievement_overlap_eligible(self) -> None:
        """성취기준 겹침 → 적격(단원 미지정·성취기준 단독 신호로 통과)."""
        # 진도 단원은 안 주고 성취기준만 겹치게 — 성취기준 단독으로 적격이 되는지 본다.
        problem = _problem(
            unit_codes=["GEO-VECTOR"],  # 진도 단원과 무관(단원 타깃 미지정)
            achievement_standard_codes=["[12미적01-01]", "[12미적01-02]"],
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_achievement_codes={"[12미적01-01]"},
            )
            is True
        )

    def test_achievement_mismatch_with_no_unit_target_rejected(self) -> None:
        """성취기준 타깃만 주고 안 겹치면 부적격(성취기준 단독 신호 불일치)."""
        problem = _problem(achievement_standard_codes=["[12미적02-99]"])
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_achievement_codes={"[12미적01-01]"},
            )
            is False
        )

    def test_achievement_mismatch_but_unit_match_eligible_or_not_and(self) -> None:
        """★ OR 핵심 — 성취기준 불일치라도 단원이 겹치면 적격(AND였다면 부적격)."""
        problem = _problem(
            unit_codes=["CAL-INT-DEF"],  # 단원은 진도와 겹침
            achievement_standard_codes=["[12미적09-09]"],  # 성취기준은 불일치
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
                target_achievement_codes={"[12미적01-01]"},
            )
            is True
        )

    def test_empty_achievement_codes_falls_back_to_unit(self) -> None:
        """데이터0 — 문항 성취기준이 빈 리스트여도 단원이 겹치면 통과(데이터 부재 폴백).

        성취기준 코퍼스·태깅 미적재 상태(빈 achievement_standard_codes)에서 성취기준 타깃을 줘도,
        단원이 맞으면 OR로 통과한다(성취기준 불일치가 단원 적합을 덮지 않음 — 데이터0 무회귀).
        """
        problem = _problem(
            unit_codes=["CAL-INT-DEF"],
            achievement_standard_codes=[],  # 데이터0(태깅 부재)
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
                target_achievement_codes={"[12미적01-01]"},
            )
            is True
        )

    def test_achievement_only_target_with_empty_codes_rejected(self) -> None:
        """데이터0 + 단원 타깃 미지정 → 부적격(폴백할 단원 신호가 없음)."""
        # 성취기준 타깃만 주고(단원 미지정) 문항 성취기준이 비면 OR이 둘 다 실패 → 부적격.
        problem = _problem(achievement_standard_codes=[])
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_achievement_codes={"[12미적01-01]"},
            )
            is False
        )

    def test_copyright_gate_blocks_even_with_achievement_match(self) -> None:
        """차단 불변 — 평가원(본문 미보유) + 성취기준 완벽 일치여도 여전히 False(②가 ④보다 앞).

        성취기준이 진도와 완벽 일치해도 저작권 노출 게이트(②)가 ④ 진도 신호보다 우선하므로
        본문 미보유 출처는 무조건 차단된다(법적 우선순위 불변).
        """
        problem = _problem(
            source_type=SourceType.평가원,
            unit_codes=["CAL-INT-DEF"],
            achievement_standard_codes=["[12미적01-01]"],  # 성취기준 완벽 일치여도
            persona_fit={Persona.A_일반고고3: 0.99},
        )
        assert (
            is_school_progress_eligible(
                problem,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
                target_achievement_codes={"[12미적01-01]"},
            )
            is False
        )

    def test_achievement_target_none_preserves_legacy_unit_behavior(self) -> None:
        """하위호환 — target_achievement_codes 미지정 시 기존 단원 정합 케이스 그대로.

        성취기준 코드가 채워져 있어도, 성취기준 타깃을 안 주면 적격성은 *기존 단원 경로*와 완전히
        동일하다(성취기준 항 비관여). 단원 겹침 有→적격·無→부적격이 기존과 같아야 한다.
        """
        with_codes_unit_match = _problem(
            unit_codes=["CAL-INT-DEF"],
            achievement_standard_codes=["[12미적01-01]"],
        )
        with_codes_unit_miss = _problem(
            unit_codes=["GEO-VECTOR"],
            achievement_standard_codes=["[12미적01-01]"],
        )
        # target_achievement_codes 미지정 → 단원만으로 판정(기존 동작).
        assert (
            is_school_progress_eligible(
                with_codes_unit_match,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is True
        )
        assert (
            is_school_progress_eligible(
                with_codes_unit_miss,
                Persona.A_일반고고3,
                target_unit_codes={"CAL-INT-DEF"},
            )
            is False
        )


# ──────────────────────────────────────────────────────────────────────
# school_progress_priority — 우선순위 가중치(단조성)
# ──────────────────────────────────────────────────────────────────────
class TestSchoolProgressPriority:
    def test_more_unit_overlap_increases_priority(self) -> None:
        """현재 진도 단원과 더 많이 겹치는 문항이 우선순위가 크다(겹침 개수 단조)."""
        target = {"CAL-INT-DEF", "FUN-COMPOSITE", "SEQ-LIMIT"}
        two_overlap = _problem(unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"])  # 겹침 2
        one_overlap = _problem(unit_codes=["CAL-INT-DEF", "GEO-VECTOR"])  # 겹침 1
        assert school_progress_priority(
            two_overlap, target_unit_codes=target
        ) > school_progress_priority(one_overlap, target_unit_codes=target)

    def test_unit_overlap_outweighs_no_overlap(self) -> None:
        """겹치는 단원이 있는 문항이 없는 문항보다 우선순위가 크다(다른 조건 동일)."""
        target = {"CAL-INT-DEF"}
        with_overlap = _problem(unit_codes=["CAL-INT-DEF"], difficulty_overall=2.0)
        without_overlap = _problem(unit_codes=["GEO-VECTOR"], difficulty_overall=2.0)
        assert school_progress_priority(
            with_overlap, target_unit_codes=target
        ) > school_progress_priority(without_overlap, target_unit_codes=target)

    def test_higher_difficulty_increases_priority(self) -> None:
        """종합 난이도가 높을수록 우선순위가 크다(보조 축·다른 조건 동일)."""
        target = {"CAL-INT-DEF"}
        hard = _problem(unit_codes=["CAL-INT-DEF"], difficulty_overall=5.0)
        easy = _problem(unit_codes=["CAL-INT-DEF"], difficulty_overall=1.0)
        assert school_progress_priority(hard, target_unit_codes=target) > school_progress_priority(
            easy, target_unit_codes=target
        )

    def test_none_target_units_uses_difficulty_only(self) -> None:
        """target_unit_codes 미지정 시 겹침 항은 0.0 — 난이도만으로 우선순위 산정."""
        # 겹침 항이 없으니 priority == difficulty_overall.
        problem = _problem(unit_codes=["CAL-INT-DEF"], difficulty_overall=3.0)
        assert school_progress_priority(problem) == 3.0

    def test_none_difficulty_treated_as_zero(self) -> None:
        """difficulty_overall=None은 0.0으로 취급 — 난이도 신호 없음(target도 없으면 0.0)."""
        no_diff = _problem()  # difficulty_overall 기본 None·target 없음
        assert school_progress_priority(no_diff) == 0.0

    def test_priority_is_deterministic(self) -> None:
        """같은 입력은 같은 가중치(결정적)·가중 합 정확."""
        target = {"CAL-INT-DEF", "FUN-COMPOSITE"}
        problem = _problem(
            unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"],
            difficulty_overall=4.0,
        )
        # 겹침 2개 ×2.0 = 4.0 + 난이도 4.0 = 8.0.
        assert (
            school_progress_priority(problem, target_unit_codes=target)
            == school_progress_priority(problem, target_unit_codes=target)
            == 8.0
        )


# ──────────────────────────────────────────────────────────────────────
# select_school_progress_items — 선별·정렬·limit
# ──────────────────────────────────────────────────────────────────────
class TestSelectSchoolProgressItems:
    def test_filters_to_eligible_only(self) -> None:
        """혼합 풀(타단원·다른교육과정·진도적합 섞음)에서 진도 적합만 남는다."""
        target = {"CAL-INT-DEF"}
        fit_item = _problem(slug="fit", unit_codes=["CAL-INT-DEF"])
        # 타 단원(진도 단원과 안 겹침) → 탈락.
        other_unit = _problem(slug="other-unit", unit_codes=["GEO-VECTOR"])
        # 다른 교육과정(2015) → 버전 불일치로 탈락.
        old_curriculum = _problem(
            slug="old-curriculum",
            curriculum_version=Curriculum.REVISION_2015,
            unit_codes=["CAL-INT-DEF"],
        )

        selected = select_school_progress_items(
            [other_unit, fit_item, old_curriculum],
            Persona.A_일반고고3,
            target_unit_codes=target,
            curriculum_version=Curriculum.REVISION_2022,
        )
        assert [p.slug for p in selected] == ["fit"]

    def test_orders_by_overlap_count_descending(self) -> None:
        """진도 단원 겹침이 많은 문항이 앞에 온다(우선순위 내림차순)."""
        target = {"CAL-INT-DEF", "FUN-COMPOSITE", "SEQ-LIMIT"}
        # 셋 다 진도 적합(>=1 겹침). 겹침 개수만 다르게 설계(난이도 0 → 겹침으로만 정렬).
        one = _problem(slug="one", unit_codes=["CAL-INT-DEF"])  # 겹침 1 → 2.0
        three = _problem(
            slug="three",
            unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE", "SEQ-LIMIT"],
        )  # 겹침 3 → 6.0
        two = _problem(slug="two", unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"])  # 겹침 2 → 4.0

        # 입력은 우선순위 역순으로 줘서 정렬이 실제로 일어나는지 본다.
        selected = select_school_progress_items(
            [one, two, three], Persona.A_일반고고3, target_unit_codes=target
        )
        assert [p.slug for p in selected] == ["three", "two", "one"]

    def test_limit_truncates_to_top_n(self) -> None:
        """limit이 상위 N개로 자른다(우선순위 상위부터)."""
        target = {"CAL-INT-DEF"}
        items = [
            _problem(
                slug=f"item-{i}",
                unit_codes=["CAL-INT-DEF"],
                difficulty_overall=float(i),
            )
            for i in (1, 2, 3, 4, 5)
        ]
        # 겹침 1(2.0) 동일 + 난이도 5,4가 상위 2개.
        selected = select_school_progress_items(
            items, Persona.A_일반고고3, target_unit_codes=target, limit=2
        )
        assert [p.slug for p in selected] == ["item-5", "item-4"]

    def test_limit_none_returns_all_eligible(self) -> None:
        """limit=None(기본) → 적격 전부 반환(무제한)."""
        target = {"CAL-INT-DEF"}
        items = [_problem(slug=f"i-{i}", unit_codes=["CAL-INT-DEF"]) for i in range(3)]
        selected = select_school_progress_items(
            items, Persona.A_일반고고3, target_unit_codes=target
        )
        assert len(selected) == 3

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 → 빈 리스트(상위 0개)."""
        target = {"CAL-INT-DEF"}
        items = [_problem(unit_codes=["CAL-INT-DEF"])]
        assert (
            select_school_progress_items(
                items, Persona.A_일반고고3, target_unit_codes=target, limit=0
            )
            == []
        )

    def test_empty_input_returns_empty(self) -> None:
        """빈 입력 → 빈 결과."""
        assert select_school_progress_items([], Persona.A_일반고고3) == []

    def test_non_target_persona_selects_nothing(self) -> None:
        """비재학 페르소나(B)면 적합 문항이 많아도 전부 탈락 → 빈 결과."""
        target = {"CAL-INT-DEF"}
        items = [
            _problem(
                unit_codes=["CAL-INT-DEF"],
                persona_fit={Persona.B_자사고N수: 0.9},
            )
            for _ in range(3)
        ]
        assert (
            select_school_progress_items(items, Persona.B_자사고N수, target_unit_codes=target) == []
        )

    def test_copyright_blocked_items_excluded_from_selection(self) -> None:
        """선별에서도 본문 미보유 출처는 빠진다(저작권 게이트가 필터에 적용)."""
        target = {"CAL-INT-DEF"}
        ok = _problem(slug="ok", unit_codes=["CAL-INT-DEF"])
        # 평가원 출처(본문 미보유) — 진도 정합이어도 노출 불가.
        blocked = _problem(
            slug="blocked",
            source_type=SourceType.평가원,
            unit_codes=["CAL-INT-DEF"],
        )
        selected = select_school_progress_items(
            [blocked, ok], Persona.A_일반고고3, target_unit_codes=target
        )
        assert [p.slug for p in selected] == ["ok"]

    def test_persona_fit_fallback_selection(self) -> None:
        """target_unit_codes 미지정 시 persona_fit 폴백으로 선별(적합도 충족만 남음)."""
        fit = _problem(slug="fit", persona_fit={Persona.A_일반고고3: 0.8})
        unfit = _problem(slug="unfit", persona_fit={Persona.A_일반고고3: 0.2})
        selected = select_school_progress_items([unfit, fit], Persona.A_일반고고3)
        assert [p.slug for p in selected] == ["fit"]

    def test_default_persona_used_when_omitted(self) -> None:
        """persona 생략 시 기본 A로 선별(MVP 재학생 정면 대상)."""
        target = {"CAL-INT-DEF"}
        items = [_problem(slug=f"d-{i}", unit_codes=["CAL-INT-DEF"]) for i in range(2)]
        # persona 미지정 → A로 판정되어 둘 다 적격.
        selected = select_school_progress_items(items, target_unit_codes=target)
        assert {p.slug for p in selected} == {"d-0", "d-1"}

    def test_stable_sort_preserves_input_order_on_ties(self) -> None:
        """동률(같은 우선순위)은 입력 순서를 보존한다(안정정렬 계약)."""
        target = {"CAL-INT-DEF"}
        # 셋 다 겹침 1·난이도 3.0 → 동일 우선순위(2.0 + 3.0 = 5.0).
        first = _problem(slug="first", unit_codes=["CAL-INT-DEF"], difficulty_overall=3.0)
        second = _problem(slug="second", unit_codes=["CAL-INT-DEF"], difficulty_overall=3.0)
        third = _problem(slug="third", unit_codes=["CAL-INT-DEF"], difficulty_overall=3.0)
        selected = select_school_progress_items(
            [first, second, third], Persona.A_일반고고3, target_unit_codes=target
        )
        assert [p.slug for p in selected] == ["first", "second", "third"]


# ──────────────────────────────────────────────────────────────────────
# ⑩ 자동 커리큘럼 정렬 — 깊이 축(required_depth) 정렬 보너스
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumDepthAlignment:
    def test_perfect_match_gives_max_bonus(self) -> None:
        # conceptual → 목표 난이도 3.5. difficulty 3.5면 거리 0 → 최대 보너스(_DEPTH_ALIGN_WEIGHT).
        p = _problem(curriculum_required_depth=RequiredDepth.conceptual, difficulty_overall=3.5)
        assert curriculum_depth_alignment(p) == pytest.approx(1.5)

    def test_far_off_gives_small_bonus(self) -> None:
        # awareness → 목표 1.5. difficulty 5.0 → 거리 3.5 → 1.5*(1-3.5/4)=0.1875.
        p = _problem(curriculum_required_depth=RequiredDepth.awareness, difficulty_overall=5.0)
        assert curriculum_depth_alignment(p) == pytest.approx(0.1875)

    def test_none_depth_returns_zero(self) -> None:
        # 깊이 미주입(curriculum_entry 미적재) → 0.0(하위호환).
        p = _problem(difficulty_overall=3.5)
        assert p.curriculum_required_depth is None
        assert curriculum_depth_alignment(p) == 0.0

    def test_none_difficulty_returns_zero(self) -> None:
        # 난이도 미평가 → 정합 판정 불가 → 0.0.
        p = _problem(curriculum_required_depth=RequiredDepth.mastery, difficulty_overall=None)
        assert curriculum_depth_alignment(p) == 0.0

    def test_enum_value_string_works(self) -> None:
        # use_enum_values=True로 값이 문자열이어도 정규화돼 동작.
        p = _problem(curriculum_required_depth="mastery", difficulty_overall=4.5)
        assert curriculum_depth_alignment(p) == pytest.approx(1.5)

    def test_priority_includes_depth_bonus(self) -> None:
        # 같은 단원 겹침·같은 난이도라도 깊이정합 문항이 우선순위가 더 높다.
        target = {"CAL-INT-DEF"}
        aligned = _problem(
            curriculum_required_depth=RequiredDepth.conceptual, difficulty_overall=3.5
        )
        misaligned = _problem(
            curriculum_required_depth=RequiredDepth.awareness, difficulty_overall=3.5
        )
        w_aligned = school_progress_priority(aligned, target_unit_codes=target)
        w_misaligned = school_progress_priority(misaligned, target_unit_codes=target)
        assert w_aligned > w_misaligned

    def test_priority_backward_compatible_without_depth(self) -> None:
        # 깊이 미주입이면 기존 가중치(단원×2.0 + 난이도)와 정확히 동일.
        target = {"CAL-INT-DEF"}
        p = _problem(difficulty_overall=3.0)
        # 단원 1겹침×2.0 + 난이도 3.0 + 깊이 0.0 = 5.0.
        assert school_progress_priority(p, target_unit_codes=target) == pytest.approx(5.0)
