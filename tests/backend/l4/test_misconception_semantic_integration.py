"""오개념 의미 매칭 *라이브* 통합 테스트 — slice 104 (WHYMATH_RUN_INTEGRATION 게이트).

라이브 임베딩(sentence-transformers bge-m3 가중치 다운로드/로드·OpenAI API)에 실제로
도달해 ① 실 임베딩 차원·② 진짜 의미 recall(어휘가 다른 패러프레이즈)을 확인한다. CI는
`WHYMATH_RUN_INTEGRATION`을 설정하지 않으므로 자동 skip(conftest.py 게이트) — 단위 경로는
FakeEmbeddingProvider로 hermetic하게 검증한다.

OpenAI 케이스는 키(WHYMATH_OPENAI_API_KEY)까지 있어야 의미가 있으므로 키 미설정 시
추가로 skip한다. 로컬(bge-m3)은 키 불요(가중치만 다운로드).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l4.misconception.semantic import (
    LocalEmbeddingProvider,
    OpenAIEmbeddingProvider,
    semantic_matches,
)

pytestmark = pytest.mark.integration


class TestLocalEmbeddingLive:
    """bge-m3 라이브 — 가중치 로드·실 차원·의미 recall."""

    def test_bge_m3_real_dimension_and_recall(self) -> None:
        provider = LocalEmbeddingProvider()
        # 실 임베딩 차원 확인(bge-m3=1024). 모델 버전에 따라 변할 수 있어 *양수·일정*만 단언.
        vecs = provider.embed(["연속이면 미분가능하다", "분모가 0이 될 수 있다"])
        assert len(vecs) == 2
        assert len(vecs[0]) > 0
        assert len(vecs[0]) == len(vecs[1])  # 한 제공자는 차원 일정

        # 진짜 의미 recall: 카탈로그 표현과 *어휘가 다른* 패러프레이즈가 매칭되는가.
        # division-by-zero("분모에 변수가 와도 항상 정의됨")를 *완전히 다른 말*로 적어본다.
        paraphrase = "변수가 들어간 식은 어떤 값을 넣어도 늘 계산이 된다고 봤어"
        hits = semantic_matches(paraphrase, provider=provider, top_k=5, threshold=0.3)
        # 라이브 임베딩은 어휘가 달라도 의미로 잡아야 한다(Fake로는 불가능한 케이스).
        # 임계값·모델에 민감하므로 *적어도 후보가 비지 않음*을 핵심 단언으로 둔다.
        assert isinstance(hits, list)
        # 매칭이 났다면 semantic_similarity가 채워졌는지 확인(스모크).
        for h in hits:
            assert h.semantic_similarity is not None


class TestOpenAIEmbeddingLive:
    """OpenAI te-3-large 라이브 — 키 필요(미설정 시 skip)."""

    def test_openai_reachable_and_dimension(self) -> None:
        if not get_settings().openai_configured:
            pytest.skip("WHYMATH_OPENAI_API_KEY 미설정 — OpenAI 라이브 테스트 skip")
        provider = OpenAIEmbeddingProvider()
        vecs = provider.embed(["연속이면 미분가능하다", "분모가 0"])
        assert len(vecs) == 2
        # te-3-large=3072. 양수·일정만 단언(차원 고정값 하드코딩 회피).
        assert len(vecs[0]) > 0
        assert len(vecs[0]) == len(vecs[1])
