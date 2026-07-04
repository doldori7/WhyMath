"""오개념 crosswalk 후보 자동생성 단위테스트 — FakeEmbeddingProvider 결정론(PG·실모델 불요).

Fake 임베딩은 *단어 bag-of-words 해시*라 토큰을 공유하면 코사인이 높다. 합성 kebab·M-id로
top 후보·임계 필터·top_k 캡·link_type 밴드·결정론을 검증한다. 충돌 회피 위해 dim을 키운다.
"""

from __future__ import annotations

from whymath_backend.l1.embedding_provider import FakeEmbeddingProvider
from whymath_backend.l4.misconception.crosslink_candidates import (
    CrosslinkCandidate,
    propose_crosslink_candidates,
)
from whymath_backend.l4.misconception.models import Misconception
from whymath_backend.schema.misconception_catalog import MisconceptionCatalog


def _kebab(id_: str, statement: str) -> Misconception:
    return Misconception(
        id=id_,
        name_kr="라벨",
        domain="대수",
        canonical_statement=statement,
        counterexample="x",
        signals=("a",),
        regex_signals=(),
        correct_form=None,
    )


def _mid(mis_id: str, statement: str, domain: str | None = "수와 연산") -> MisconceptionCatalog:
    return MisconceptionCatalog(mis_id=mis_id, canonical_statement=statement, domain=domain)


# 토큰 공유로 코사인을 통제: kebab "alpha beta gamma" ↔ MATCH 동일·PARTIAL 2/3·NONE 무공유.
_KEBAB = _kebab("k-test", "alpha beta gamma")
_MATCH = _mid(
    "M001", "라벨. alpha beta gamma"
)  # catalog_text("라벨. alpha beta gamma")와 동일 토큰
_PARTIAL = _mid("M002", "라벨. alpha beta zzz")  # 3/4 공유
_NONE = _mid("M003", "ppp qqq rrr sss")  # 무공유
_PROVIDER = FakeEmbeddingProvider(dim=2048)  # 충돌 회피용 대차원


def _run(**kw: object) -> list[CrosslinkCandidate]:
    params: dict[str, object] = {
        "provider": _PROVIDER,
        "mid_records": [_MATCH, _PARTIAL, _NONE],
        "kebab_catalog": [_KEBAB],
        "top_k": 3,
        "min_confidence": 0.5,
    }
    params.update(kw)
    return propose_crosslink_candidates(**params)  # type: ignore[arg-type]


def test_identical_text_is_top_direct() -> None:
    cands = _run()
    assert cands[0].kebab_id == "k-test"
    assert cands[0].mis_id == "M001"  # 동일 토큰 → 최상위
    assert cands[0].confidence >= 0.99  # 사실상 cosine 1
    assert cands[0].link_type == "직접매핑"
    assert cands[0].method == "embedding"
    assert "cosine=" in cands[0].rationale


def test_disjoint_filtered_by_threshold() -> None:
    # M003(무공유)은 cosine ~0 → min_confidence 0.5 미만으로 탈락.
    ids = {c.mis_id for c in _run()}
    assert "M003" not in ids


def test_partial_is_partial_band() -> None:
    partial = next(c for c in _run() if c.mis_id == "M002")
    assert 0.6 <= partial.confidence < 0.85
    assert partial.link_type == "부분매핑"


def test_top_k_caps() -> None:
    cands = _run(top_k=1)
    assert len(cands) == 1
    assert cands[0].mis_id == "M001"  # 최상위만


def test_empty_records_returns_empty() -> None:
    assert _run(mid_records=[]) == []


def test_nonpositive_top_k_returns_empty() -> None:
    assert _run(top_k=0) == []


def test_high_threshold_keeps_only_direct() -> None:
    cands = _run(min_confidence=0.9)
    assert {c.mis_id for c in cands} == {"M001"}


def test_deterministic_ordering() -> None:
    # 같은 입력 → 같은 출력(결정론).
    assert _run() == _run()
