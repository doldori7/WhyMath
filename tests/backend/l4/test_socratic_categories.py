"""소크라테스 6카테고리 enum·라벨·예시질문 단위테스트.

스펙 `docs/architecture/04_pedagogy_engine.md` L65-70 정본과의 1:1 정렬 확인.
"""

from __future__ import annotations

from whymath_backend.l4.socratic import EXAMPLE_QUESTION, KOREAN_LABEL, SocraticCategory


class TestSixCategories:
    def test_exactly_six(self) -> None:
        assert len(list(SocraticCategory)) == 6

    def test_canonical_identifiers(self) -> None:
        # 스펙 L65-70 영어 식별자 1:1.
        assert SocraticCategory.CLARIFICATION.value == "clarification"
        assert SocraticCategory.ASSUMPTION.value == "assumption"
        assert SocraticCategory.EVIDENCE.value == "evidence"
        assert SocraticCategory.PERSPECTIVE.value == "perspective"
        assert SocraticCategory.IMPLICATION.value == "implication"
        assert SocraticCategory.META.value == "meta"


class TestKoreanLabels:
    def test_every_category_has_korean_label(self) -> None:
        for c in SocraticCategory:
            assert c in KOREAN_LABEL
            assert KOREAN_LABEL[c]  # 비공 문자열

    def test_canonical_korean_labels(self) -> None:
        # 스펙 L65-70 한글 라벨 정본
        assert KOREAN_LABEL[SocraticCategory.CLARIFICATION] == "명료화"
        assert KOREAN_LABEL[SocraticCategory.ASSUMPTION] == "가정 탐색"
        assert KOREAN_LABEL[SocraticCategory.EVIDENCE] == "근거·증거"
        assert KOREAN_LABEL[SocraticCategory.PERSPECTIVE] == "관점"
        assert KOREAN_LABEL[SocraticCategory.IMPLICATION] == "함의"
        assert KOREAN_LABEL[SocraticCategory.META] == "메타인지"


class TestExampleQuestions:
    def test_every_category_has_example(self) -> None:
        for c in SocraticCategory:
            assert c in EXAMPLE_QUESTION
            q = EXAMPLE_QUESTION[c]
            assert q.endswith("?")  # 정본 질문은 모두 물음표로 끝남

    def test_canonical_example_questions(self) -> None:
        # 스펙 L65-70 정본 예시 질문 그대로.
        assert EXAMPLE_QUESTION[SocraticCategory.CLARIFICATION] == "어디까지 이해됐어?"
        assert EXAMPLE_QUESTION[SocraticCategory.ASSUMPTION] == "왜 그렇게 가정했어?"
        assert EXAMPLE_QUESTION[SocraticCategory.EVIDENCE] == "어떻게 알아?"
        assert EXAMPLE_QUESTION[SocraticCategory.PERSPECTIVE] == "다른 방법은?"
        assert EXAMPLE_QUESTION[SocraticCategory.IMPLICATION] == "그러면 다음은?"
        assert EXAMPLE_QUESTION[SocraticCategory.META] == "어떻게 도달했어?"
