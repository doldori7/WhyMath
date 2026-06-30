"""임베딩 프리미티브 단위테스트 — 단일 포맷 권위 `join_embedding_text`·버전 핀(감사 §2·§5).

개념·원자·오개념 빌더가 공유하는 결합 규칙(구분자 `". "`·strip·빈/None skip)을 한 곳에서
검증한다. 세 빌더 리팩터 전후 *출력 동일*(behavior-preserving)임을 못 박는다.
"""

from __future__ import annotations

from whymath_backend.l1.embedding_primitives import (
    EMBEDDING_TEXT_FORMAT_VERSION,
    join_embedding_text,
)


class TestJoinEmbeddingText:
    def test_joins_with_dot_space(self) -> None:
        assert join_embedding_text("이차함수", "포물선", "y=ax^2") == "이차함수. 포물선. y=ax^2"

    def test_skips_none_and_empty(self) -> None:
        assert join_embedding_text("이름", None, "", "   ", "전이") == "이름. 전이"

    def test_strips_each_part(self) -> None:
        assert join_embedding_text("  이름  ", "  은유 ") == "이름. 은유"

    def test_all_empty_returns_empty(self) -> None:
        assert join_embedding_text(None, "", "  ") == ""

    def test_single_part(self) -> None:
        assert join_embedding_text("이름") == "이름"

    def test_no_parts(self) -> None:
        assert join_embedding_text() == ""

    def test_matches_legacy_concept_pattern(self) -> None:
        # 과거 concept/atom 빌더의 `". ".join([str(v).strip() for v ... if non-empty])`와 동일.
        name_ko, metaphor, accepted = "이차함수", None, "y=ax^2"
        legacy = ". ".join(
            str(v).strip()
            for v in (name_ko, metaphor, accepted)
            if v is not None and str(v).strip()
        )
        assert join_embedding_text(name_ko, metaphor, accepted) == legacy


def test_format_version_is_positive_int() -> None:
    assert isinstance(EMBEDDING_TEXT_FORMAT_VERSION, int)
    assert EMBEDDING_TEXT_FORMAT_VERSION >= 1
