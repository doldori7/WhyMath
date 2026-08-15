"""비유·예시 결함 검출기(analogy_checker) 단위 테스트 — 폐쇄 어휘 동결 + 축별 변별력.

hermetic(LLM·IO 0·순수 규칙). 변별력 원칙: 각 축은 결함 표본에서 실제로 검출 신호를 내고,
무결함(경계 스트레스 포함) 표본에서 침묵해야 한다 — 성공/실패 양쪽에서 같은 값을 내는 검사는
검증이 아니다(CLAUDE.md).
"""

from __future__ import annotations

from whymath_backend.l3.pedagogy.analogy_checker import (
    ANALOGY_DEFECT_CODES,
    DEFERRED_DEFECT_AXES,
    GAMIFICATION_VOCAB,
    RULE_DETECTABLE_DEFECT_AXES,
    check_analogy_defects,
    check_example_defects,
)

# 한계 명시를 갖춘 무결함 비유(전 축 clean) — 각 테스트의 기준 대조 표본.
_CLEAN_ANALOGY = (
    "함수는 자판기와 같아. 다만 실제 함수는 버튼 없는 입력도 받는다는 점이 다르다 — "
    "이 비유는 정의가 아니라 디딤돌이다."
)


class TestClosedVocabulary:
    """폐쇄 어휘 동결 — 결함 코드·커버리지 회계가 임의 확장되면 여기서 깨진다."""

    def test_defect_codes_frozen(self) -> None:
        """검출 코드 5종 폐쇄 어휘 — 추가·개명은 의도적 결정(테스트 갱신)이어야 한다."""
        assert ANALOGY_DEFECT_CODES == frozenset(
            {
                "MISSING_BREAK_CLAUSE",
                "OVERIDENTIFICATION",
                "DEFINITION_USURPATION",
                "ANSWER_LEAK",
                "GAMIFIED",
            }
        )

    def test_coverage_accounting(self) -> None:
        """규칙 검출 축=코드 전량, DEFERRED=의미론 축 — 정직한 커버리지 회계(mode_guard 동형)."""
        assert RULE_DETECTABLE_DEFECT_AXES == ANALOGY_DEFECT_CODES
        assert DEFERRED_DEFECT_AXES == frozenset({"SEMANTIC_MISCONCEPTION"})
        assert not (RULE_DETECTABLE_DEFECT_AXES & DEFERRED_DEFECT_AXES)

    def test_gamification_vocab_excludes_bare_game_word(self) -> None:
        """맨 '게임'은 어휘 밖 — 주사위 게임(확률 소재)류 정당 예시의 오탐 방지 설계 동결."""
        assert "게임" not in GAMIFICATION_VOCAB
        assert "게임형" in GAMIFICATION_VOCAB
        assert "게임화" in GAMIFICATION_VOCAB

    def test_checker_emits_only_closed_codes(self) -> None:
        """검출기 산출은 폐쇄 어휘 안 — 자유 문자열 reason_code 금지."""
        detected = check_analogy_defects("이것이 정의다. 완전 게임화 레벨업.")
        assert detected
        assert set(detected) <= ANALOGY_DEFECT_CODES


class TestMissingBreakClause:
    """①-a 한계 명시 부재 — 깨짐·차이 어휘 전무 시에만 검출."""

    def test_no_break_clause_detected(self) -> None:
        text = "함수는 자판기와 같아. 동전을 넣으면 음료가 나온다."
        assert "MISSING_BREAK_CLAUSE" in check_analogy_defects(text)

    def test_break_clause_silences(self) -> None:
        assert "MISSING_BREAK_CLAUSE" not in check_analogy_defects(_CLEAN_ANALOGY)

    def test_various_break_vocab_accepted(self) -> None:
        """'깨진다'·'차이'·'한계' 등 어느 형태든 한계 명시로 인정(존재 검사·보수 방향)."""
        for clause in ("이 비유는 여기서 깨진다", "둘의 차이가 있다", "이 빗댐의 한계가 있다"):
            text = f"극한은 과녁으로 가는 화살과 같다. {clause}."
            assert "MISSING_BREAK_CLAUSE" not in check_analogy_defects(text)


class TestOveridentification:
    """①-b 동일시 단정 — 조사 결합형만 검출(수학적 상등 서술은 침묵)."""

    def test_identity_assertion_detected(self) -> None:
        assert "OVERIDENTIFICATION" in check_analogy_defects("함수는 자판기와 완전히 같다.")
        assert "OVERIDENTIFICATION" in check_analogy_defects("미분은 속도계 그 자체다.")

    def test_mathematical_equality_not_flagged(self) -> None:
        """'똑같이 나누기'(등분)·'크기가 완전히 같아'(합동)는 수학 서술 — 오탐 금지.

        코퍼스 846행 실측에서 확인된 오탐 계급(2026-07-29) — 조사 결합형 조임의 회귀 방어.
        """
        assert "OVERIDENTIFICATION" not in check_analogy_defects(
            "12개를 3명에게 똑같이 나눠 주기. 나눗셈은 곱셈의 거꾸로다. 다만 몫이 다르다."
        )
        assert "OVERIDENTIFICATION" not in check_analogy_defects(
            "모양과 크기가 완전히 같아 포개면 딱 맞는 두 도형이 합동. 주의할 차이도 있다."
        )

    def test_likeness_style_not_flagged(self) -> None:
        """'~처럼'·'~같이' 빗댐 서법은 동일시가 아니다(정당한 비유 문체)."""
        assert "OVERIDENTIFICATION" not in check_analogy_defects(_CLEAN_ANALOGY)


class TestDefinitionUsurpation:
    """② 정의 참칭 — 단정 서술 검출·면책(정의가 아니다)과 정의역 서술은 침묵."""

    def test_usurpation_detected(self) -> None:
        assert "DEFINITION_USURPATION" in check_analogy_defects(
            "함수란 자판기라고 정의된다. 그렇게 외우면 된다."
        )
        assert "DEFINITION_USURPATION" in check_analogy_defects("집합의 정의는 바로 서랍장이다.")

    def test_disclaimer_silences(self) -> None:
        """'정의가 아니라'는 면책 — 참칭이 아니다(오탐 방지)."""
        assert "DEFINITION_USURPATION" not in check_analogy_defects(_CLEAN_ANALOGY)

    def test_domain_of_definition_not_flagged(self) -> None:
        """함수 정의역 서술('~에서만 정의된다')은 수학 서술 — 오탐 금지(코퍼스 실측 조임)."""
        assert "DEFINITION_USURPATION" not in check_analogy_defects(
            "제곱의 되돌리기. 근호 안이 0 이상인 곳에서만 정의된다(정의역 제한). 주의가 필요하다."
        )


class TestGamified:
    """④ 게임형 — 게임화 메커닉 검출·수학 소재 게임 언급은 침묵(경계 변별)."""

    def test_gamification_mechanics_detected(self) -> None:
        assert "GAMIFIED" in check_analogy_defects(
            "문제를 풀면 경험치를 얻고 레벨업한다. 다만 이 비유는 깨진다."
        )
        assert "GAMIFIED" in check_example_defects("퀘스트를 깨면 포인트 적립이 되는 이야기.")

    def test_dice_game_context_clean(self) -> None:
        """주사위 게임(확률 소재)·보드게임 카페 — 게임화가 아니라 수학 소재(오탐 금지)."""
        assert check_example_defects("주사위 게임을 하던 두 친구가 합의 가능성을 궁금해했다.") == ()
        assert check_example_defects("보드게임 카페에서 카드 조합의 수를 세는 상황.") == ()

    def test_nfkc_normalization_defeats_ideographic_space_bypass(self) -> None:
        """전각(U+3000) 공백 우회 — NFKC 붕괴로 '레벨　업'이 '레벨 업' 어휘에 잡힌다."""
        # U+3000(전각 공백)을 끼운 "레벨　업"은 NFKC 정규화로 "레벨 업"이 되어 검출된다 —
        # 정규화가 없으면 우회 성공(미검출)이므로 이 케이스가 NFKC 계층의 변별 검증이다.
        assert "GAMIFIED" in check_analogy_defects("공부할수록 레벨　업 하는 비유. 다만 다르다.")


class TestAnswerLeak:
    """③ 정답 유출(예시 grain) — 정답 문자열 본문 노출 검출."""

    def test_leak_detected(self) -> None:
        assert "ANSWER_LEAK" in check_example_defects("의자 수를 세니 답은 12개였다.", "12")

    def test_no_answer_no_leak_axis(self) -> None:
        """answer가 없으면 유출 축 자체가 비적용 — 빈 튜플(무결함)."""
        assert check_example_defects("의자 수를 세어 보는 상황.", None) == ()

    def test_clean_body_silent(self) -> None:
        assert check_example_defects("의자 수를 어떻게 셀지 고민하는 장면.", "12") == ()

    def test_analogy_grain_has_no_answer_axis(self) -> None:
        """비유 grain은 answer 개념이 없어 ANSWER_LEAK을 내지 않는다(축 분담 동결)."""
        detected = check_analogy_defects("답은 12다. 이 비유는 깨진다.")
        assert "ANSWER_LEAK" not in detected


class TestDeterminism:
    def test_deterministic_and_ordered(self) -> None:
        """같은 입력 → 같은 튜플(순서 포함) — 게이트 판정 재현성."""
        text = "이것이 정의다. 레벨업 비유."
        assert check_analogy_defects(text) == check_analogy_defects(text)
        # 결정론 순서: 한계 부재 → 동일시 → 정의 참칭 → 게임형.
        assert check_analogy_defects(text) == (
            "MISSING_BREAK_CLAUSE",
            "DEFINITION_USURPATION",
            "GAMIFIED",
        )
