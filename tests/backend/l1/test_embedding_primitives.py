"""임베딩 프리미티브 단위테스트 — 단일 포맷 권위 `join_embedding_text`·버전 핀(감사 §2·§5).

개념·원자·오개념 빌더가 공유하는 결합 규칙(구분자 `". "`·strip·빈/None skip)을 한 곳에서
검증한다. 세 빌더 리팩터 전후 *출력 동일*(behavior-preserving)임을 못 박는다. skip-if-unchanged
적재 코어 `embed_changed`(세 적재기 공유·감사 §2 3중복 제거)도 좌석 주입으로 라이브 PG 없이 검증.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from whymath_backend.l1.embedding_primitives import (
    EMBEDDING_TEXT_FORMAT_VERSION,
    embed_changed,
    join_embedding_text,
    text_hash,
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


class _SpyProvider:
    """embed 호출 수·마지막 입력을 기록하는 provider 좌석(라이브 임베딩 없이 계약 검증)."""

    def __init__(self) -> None:
        self.embed_calls = 0
        self.last_texts: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls += 1
        self.last_texts = list(texts)
        # 결정론 벡터 — 각 텍스트당 길이 2(내용 무관, 개수·순서만 계약).
        return [[float(i), 0.0] for i in range(len(texts))]


class TestEmbedChanged:
    """skip-if-unchanged 코어 — 변경분만 embed·upsert(개념·원자·오개념 공유 절차)."""

    def test_embeds_and_upserts_all_when_none_exist(self) -> None:
        """기존 해시 0(신규) → 전부 embed·upsert, 반환은 적재 수."""
        provider = _SpyProvider()
        upserts: list[tuple[str, list[float], str]] = []
        n = embed_changed(
            [("a", "텍스트 A"), ("b", "텍스트 B")],
            provider=provider,
            existing_hashes=lambda keys: {},
            upsert=lambda key, vec, text: upserts.append((key, vec, text)),
        )
        assert n == 2
        assert provider.embed_calls == 1
        assert provider.last_texts == ["텍스트 A", "텍스트 B"]
        assert [u[0] for u in upserts] == ["a", "b"]

    def test_skips_unchanged(self) -> None:
        """현행 해시가 표현 해시와 같으면(불변) embed·upsert 0·반환 0(provider 미호출·비용 절감)."""
        provider = _SpyProvider()
        upserts: list[str] = []
        existing = {"a": text_hash("텍스트 A"), "b": text_hash("텍스트 B")}
        n = embed_changed(
            [("a", "텍스트 A"), ("b", "텍스트 B")],
            provider=provider,
            existing_hashes=lambda keys: existing,
            upsert=lambda key, vec, text: upserts.append(key),
        )
        assert n == 0
        assert provider.embed_calls == 0
        assert upserts == []

    def test_embeds_only_changed(self) -> None:
        """일부만 변경(a 불변·b 변경·c 신규) → 변경분만 embed·upsert(순서 보존)."""
        provider = _SpyProvider()
        upserts: list[str] = []
        existing = {"a": text_hash("A"), "b": text_hash("옛 B")}
        n = embed_changed(
            [("a", "A"), ("b", "새 B"), ("c", "C")],
            provider=provider,
            existing_hashes=lambda keys: existing,
            upsert=lambda key, vec, text: upserts.append(key),
        )
        assert n == 2
        assert provider.embed_calls == 1
        assert provider.last_texts == ["새 B", "C"]
        assert upserts == ["b", "c"]

    def test_empty_items_no_provider_call(self) -> None:
        """빈 입력 → embed 0·반환 0(존재 조회 결과와 무관)."""
        provider = _SpyProvider()
        n = embed_changed(
            [],
            provider=provider,
            existing_hashes=lambda keys: {},
            upsert=lambda key, vec, text: None,
        )
        assert n == 0
        assert provider.embed_calls == 0

    def test_length_mismatch_fails_loud(self) -> None:
        """provider가 입력과 다른 개수 벡터를 내면 RuntimeError(fail-loud·item_noun 반영)."""

        class _BadProvider:
            def embed(self, texts: Sequence[str]) -> list[list[float]]:
                return [[0.0]]  # 항상 1개(입력 2개와 불일치)

            embed_calls = 0

        with pytest.raises(RuntimeError, match="임베딩 개수.*대상 원자 개수"):
            embed_changed(
                [("a", "A"), ("b", "B")],
                provider=_BadProvider(),
                existing_hashes=lambda keys: {},
                upsert=lambda key, vec, text: None,
                item_noun="원자",
            )
