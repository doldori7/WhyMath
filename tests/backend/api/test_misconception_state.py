"""오개념 의미 매처 프로세스 싱글톤(`api/_misconception_state.py`) — 단위(hermetic).

lazy 자가구성(`_build_matcher`→`build_semantic_matcher` 위임)·주입·격리를 라이브 모델 없이
검증한다. `get_settings`를 fake provider Settings로 패치해 `build_provider`가 Fake를 내게
하고(vector_store 기본 memory) lazy 빌드가 모델 로드·DB 없이 끝나게 한다. 매 테스트는
싱글톤을 reset해 격리한다(전역 상태 오염 방지).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from whymath_backend.api import _misconception_state as state
from whymath_backend.config import Settings
from whymath_backend.l4.misconception.semantic.matcher import SemanticMatcher
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    """각 테스트 전후로 싱글톤을 비워 전역 상태 격리."""
    state.reset_semantic_matcher()
    yield
    state.reset_semantic_matcher()


def test_lazy_builds_on_first_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """미주입 첫 get → `_build_matcher` lazy 구성(fake provider·memory) → SemanticMatcher."""
    monkeypatch.setattr(state, "get_settings", lambda: Settings(embedding_provider="fake"))
    matcher = state.get_semantic_matcher()
    assert isinstance(matcher, SemanticMatcher)
    # 두 번째 get은 같은 인스턴스(싱글톤·재구성 안 함).
    assert state.get_semantic_matcher() is matcher


def test_injected_matcher_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    """set_으로 주입하면 그 인스턴스를 그대로(자가구성 우회·fast path)."""
    # get_settings 패치 불요 — 주입 경로는 build를 타지 않는다(라이브 모델 0).
    injected = SemanticMatcher(provider=FakeEmbeddingProvider(dim=16))
    state.set_semantic_matcher(injected)
    assert state.get_semantic_matcher() is injected


def test_reset_forces_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    """reset 후 get은 다시 lazy 구성(주입 인스턴스와 다른 새 매처)."""
    injected = SemanticMatcher(provider=FakeEmbeddingProvider(dim=16))
    state.set_semantic_matcher(injected)
    state.reset_semantic_matcher()
    monkeypatch.setattr(state, "get_settings", lambda: Settings(embedding_provider="fake"))
    rebuilt = state.get_semantic_matcher()
    assert isinstance(rebuilt, SemanticMatcher)
    assert rebuilt is not injected
