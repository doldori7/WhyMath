"""오개념 의미 매칭 — 임베딩 제공자 좌석 (L4 → 하위 인프라 호출, slice 104).

L4 SemanticMatcher가 의존하는 *임베딩 인프라* 좌석이다. L4는 임베딩을 어떻게 만드는지
*모르고*(EmbeddingProvider Protocol만 본다), 실제 모델 로드·API 호출은 이 모듈의 구현체가
담당한다 (7계층: L_n→L_{n-1} 호출, 구현 미소유). 좌석·지연 import·Fake 주입·통합 게이트
패턴은 l3/providers/ollama.py(`_OllamaClient` 시임 + `_build_default_client`)·
l3/trace/langfuse_sink.py(시크릿 SecretStr)를 그대로 미러링한다.

────────────────────────────────────────────────────────────────────────────
정직 스코프 (CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지")
────────────────────────────────────────────────────────────────────────────
bi-encoder 임베딩은 *의미 recall*(패러프레이즈·동의어)을 개선한다 — substring AND가 못
잡던 "다른 어휘·같은 오개념"을 코사인 유사도로 잡는다. 그러나 *방향·부정·등치*("연속⇒
미분" vs "미분⇒연속", "f∘g≠g∘f")는 두 문장이 의미상 가까워 **임베딩만으로 못 가린다**
(substring과 동일한 방향맹). 그 판별은 LLM-judged/NLI = *후속 슬라이스*다. 따라서 이
좌석은 recall 향상만 제공하고 방향 판별을 해결하지 않는다.

CI hermetic 절대 준수: `local`(sentence-transformers bge-m3)·`openai`는 *지연 import*라
모듈 import만으로는 모델 다운로드·네트워크가 일어나지 않는다. CI 단위테스트는
`FakeEmbeddingProvider`(결정론 해시 벡터)를 주입하고, 라이브 1~2건만
`WHYMATH_RUN_INTEGRATION`(+OpenAI는 키) 게이트로 돈다.

시크릿 처리 (CLAUDE.md 보안 금기): OpenAI 키는 Settings에서 SecretStr로 받아
*클라이언트 생성 인자로 넘기는 그 순간에만* 평문을 꺼낸다. 이 모듈은 키를 로그·repr로
내보내지 않는다(langfuse_sink.py 패턴).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings

# Fake 제공자 기본 차원 — 결정론 해시 벡터의 길이. 카탈로그 30종·테스트엔 소차원이 충분하고
# (라이브 불요), 작을수록 테스트 가독성↑. 라이브 모델 차원(bge-m3=1024, te-3-large=3072)과는
# 무관하다 — Fake는 *구조적 호환*(list[list[float]])만 지키면 된다.
_FAKE_DIM = 64


@runtime_checkable
class EmbeddingProvider(Protocol):
    """텍스트 배치를 임베딩 벡터로 바꾸는 좌석 (구조적 타이핑).

    `embed`는 *동기*다 — L4 오개념 진단 경로(diagnose)가 전부 동기이므로 같은 호출
    맥락에서 쓰도록 맞춘다(L3는 async지만 L4 misconception는 sync). sentence-transformers·
    OpenAI 모두 동기 API를 제공하므로 좌석을 동기로 두는 데 비용이 없다.

    반환은 입력과 *같은 길이·순서*의 벡터 리스트여야 한다(행 i = texts[i]의 임베딩).
    벡터 차원은 제공자·모델에 따라 다르되 한 제공자 안에서는 일정하다(코사인 비교 전제).
    """

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """텍스트 배치 → 임베딩 벡터 리스트(입력 순서 보존)."""
        ...


# ──────────────────────────────────────────────────────────────────────────
# FakeEmbeddingProvider — 결정론·소차원·CI hermetic 전용
# ──────────────────────────────────────────────────────────────────────────
class FakeEmbeddingProvider:
    """결정론 해시 기반 가짜 임베딩 — 테스트·CI 전용(라이브 의존 0).

    *단어*(공백 분할) 단위로 안정 해시(SHA-256)를 내 고정 차원 벡터에 누적한다. 따라서
    **어휘가 겹치면 코사인이 높아진다** — 패러프레이즈를 *부분적으로* 모사할 수 있고(공유
    어휘), 어휘가 완전히 다르면 직교에 가깝다. 단위테스트는 카탈로그 표현과 *겹치는 토큰*을
    심어 recall win을 결정론적으로 재현한다.

    한계(의도적): 이건 진짜 의미 임베딩이 아니라 *어휘 해시*다. 라이브 의미 recall(진짜
    동의어·언어 간)은 통합 테스트(bge-m3/OpenAI)에서만 검증된다. Fake의 목적은 매처
    *배선·임계값·랭킹·하위호환*을 라이브 없이 hermetic하게 못 박는 것이다.

    토크나이즈는 NFKC 정규화 후 공백 분할(diagnose의 _normalize와 다름 — 여기선 *단어*
    경계가 필요하므로 공백을 보존). 빈 텍스트·토큰 0개는 영벡터를 돌려준다(코사인 0).
    """

    def __init__(self, *, dim: int = _FAKE_DIM) -> None:
        if dim < 1:
            raise ValueError(f"FakeEmbeddingProvider dim은 1 이상이어야 한다(받음: {dim}).")
        self._dim = dim

    def _embed_one(self, text: str) -> list[float]:
        """단일 텍스트 → 단어 해시 누적 벡터(미정규화 — 코사인은 인덱스가 정규화)."""
        import unicodedata

        vec = [0.0] * self._dim
        # NFKC 후 공백 분할로 *단어* 토큰을 얻는다(diagnose는 공백을 지우지만, Fake는
        # 어휘 겹침이 신호이므로 단어 경계를 유지한다).
        tokens = unicodedata.normalize("NFKC", text).split()
        for token in tokens:
            # SHA-256으로 토큰→(인덱스, 부호) 결정론 매핑. 토큰마다 한 좌표에 ±1을 더해
            # 어휘 집합이 비슷하면 벡터가 가까워지게 한다(bag-of-words 해시 트릭).
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[index] += sign
        return vec

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """텍스트 배치 → 결정론 해시 벡터(EmbeddingProvider 구현)."""
        return [self._embed_one(t) for t in texts]


# ──────────────────────────────────────────────────────────────────────────
# LocalEmbeddingProvider — sentence-transformers bge-m3 (로컬 우선·지연 로드)
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _SentenceTransformerModel(Protocol):
    """sentence_transformers.SentenceTransformer의 최소 인터페이스(구조적 타이핑).

    우리가 *실제로 쓰는* `encode`만 좁게 선언한다(ollama.py `_OllamaClient` 패턴). 반환은
    numpy ndarray 또는 list 등 버전별로 달라 `Any`로 두고 제공자 쪽에서 정규화한다.
    """

    def encode(self, sentences: Any, **kwargs: Any) -> Any:
        """문장 배치 → 임베딩(sentence-transformers encode API의 부분집합)."""
        ...


def _to_float_rows(raw: Any) -> list[list[float]]:
    """encode 반환(ndarray/list)을 list[list[float]]로 방어적 정규화.

    sentence-transformers는 보통 numpy 2D ndarray를, 단건이면 1D를 돌려준다. `.tolist()`가
    있으면 그것으로(numpy), 없으면 그대로 순회한다. 1D(단일 벡터)면 한 행으로 감싼다.
    """
    rows = raw.tolist() if hasattr(raw, "tolist") else raw
    if not isinstance(rows, list):
        raise TypeError(f"임베딩 encode 반환을 list로 정규화하지 못함(타입={type(rows).__name__}).")
    # 비었으면 그대로(빈 입력). 첫 원소가 list/sequence가 아니면 1D → 한 행으로 승격.
    if rows and not isinstance(rows[0], (list, tuple)):
        return [[float(x) for x in rows]]
    return [[float(x) for x in row] for row in rows]


class LocalEmbeddingProvider:
    """sentence-transformers 로컬 임베딩 — 기본 bge-m3(로컬 우선·CLAUDE.md 비용·Phaiakes9).

    모델은 *지연 로드*(lazy)·주입 가능(injectable)하다 — 테스트는 가짜 모델을 `model=`로
    넣고, 프로덕션은 첫 embed에서 SentenceTransformer를 로드한다. `sentence_transformers`
    import는 *호출 시점*에만 일어나므로(ollama.py `_build_default_client` 패턴) 라이브러리·
    가중치가 없는 CI에서도 모듈 import·앱 구성이 깨지지 않는다.

    반환 텍스트(임베딩)는 학생 노출 산출물이 아니라 *매칭 신호*다 — 03 환각 방어와 무관
    (의미 유사도 점수일 뿐 생성 텍스트가 아님).
    """

    def __init__(
        self,
        *,
        model: _SentenceTransformerModel | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._model = model
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_model(self) -> _SentenceTransformerModel:
        """모델 지연 해석 — 주입 우선, 없으면 SentenceTransformer 로드(지연 import)."""
        if self._model is None:
            self._model = _build_local_model(self._resolved_settings)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """텍스트 배치 → bge-m3 임베딩(EmbeddingProvider 구현).

        빈 입력은 빈 리스트(모델 호출 생략). 그 외엔 encode 후 list[list[float]] 정규화.
        """
        if not texts:
            return []
        raw = self._get_model().encode(list(texts))
        return _to_float_rows(raw)


def _build_local_model(settings: Settings) -> _SentenceTransformerModel:
    """기본 SentenceTransformer 로드 (지연 import).

    `sentence_transformers`/가중치가 없는 환경(CI 단위테스트)에서도 모듈 import가 깨지지
    않도록 *호출 시점에만* import한다(ollama.py 패턴). 라이브러리 미설치는 명확한
    RuntimeError로 보고한다. 첫 호출은 가중치 다운로드/로드라 무겁다 — 그래서 단위테스트는
    절대 이 경로를 타지 않고(Fake 주입), 라이브는 통합 게이트로만 돈다.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover — 환경 의존(라이브러리 미설치)
        raise RuntimeError(
            "sentence-transformers가 설치되지 않았습니다. "
            "`pip install sentence-transformers` 후 다시 시도하세요."
        ) from exc
    # cast 사유: SentenceTransformer의 정밀 스텁(풍부한 encode overload·numpy 반환)은 우리의
    # 좁은 구조적 시임 `_SentenceTransformerModel`과 형태가 어긋난다. 우리가 실제로 쓰는
    # 호출 규약(encode(list[str]))은 런타임에 충족되므로 스텁 정밀도 차이만 cast로 좁힌다
    # (타입 무시 X — ollama.py가 AsyncClient를 다룬 방식과 동일).
    model = SentenceTransformer(settings.embedding_model_local)
    return cast(_SentenceTransformerModel, model)


# ──────────────────────────────────────────────────────────────────────────
# OpenAIEmbeddingProvider — text-embedding-3-large (클라우드·키 필요·지연 로드)
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _OpenAIEmbeddingsClient(Protocol):
    """openai.OpenAI().embeddings의 최소 인터페이스(구조적 타이핑).

    우리가 실제로 쓰는 `create(model=, input=)`만 좁게 선언한다. 반환은 SDK 버전별
    pydantic 객체이므로 `Any`로 두고 `_extract_openai_rows`로 정규화한다.
    """

    def create(self, *, model: str, input: Sequence[str]) -> Any:
        """임베딩 생성(openai embeddings.create API의 부분집합)."""
        ...


def _extract_openai_rows(response: Any) -> list[list[float]]:
    """openai embeddings.create 응답에서 벡터 행을 방어적 추출.

    SDK는 `response.data[i].embedding`(list[float])을 *입력 순서대로* 돌려준다(객체) 또는
    dict 형태일 수 있어 양쪽을 흡수한다(ollama.py `_extract_text`의 방어 정규화 패턴).
    """
    data: Any
    if hasattr(response, "data"):
        data = response.data
    elif isinstance(response, dict):
        data = response.get("data", [])
    else:
        return []

    rows: list[list[float]] = []
    for item in data or []:
        emb: Any
        if hasattr(item, "embedding"):
            emb = item.embedding
        elif isinstance(item, dict):
            emb = item.get("embedding")
        else:
            emb = None
        if emb is None:
            raise ValueError("OpenAI 임베딩 응답에 embedding 필드가 없습니다.")
        rows.append([float(x) for x in emb])
    return rows


class OpenAIEmbeddingProvider:
    """OpenAI 임베딩 — 기본 text-embedding-3-large(CLAUDE.md 임베딩 표준·클라우드).

    클라이언트는 *지연 로드*(lazy)·주입 가능(injectable)하다 — 테스트는 가짜 임베딩
    클라이언트를 `client=`로 넣고, 프로덕션은 키가 설정돼 있을 때 첫 embed에서 OpenAI
    클라이언트를 만든다. `openai` import는 호출 시점에만(ollama.py 패턴). 키가 없으면
    *명확한 오류*를 던진다(조용한 폴백 금지 — CLAUDE.md "모르면 모른다고", langfuse는
    no-op이지만 임베딩은 매칭 결과를 바꾸므로 침묵 금지).

    로컬 우선 원칙(CLAUDE.md): 기본 제공자는 local이고, OpenAI는 *명시 선택* 시에만 쓴다.
    """

    def __init__(
        self,
        *,
        client: _OpenAIEmbeddingsClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self) -> _OpenAIEmbeddingsClient:
        """클라이언트 지연 해석 — 주입 우선, 없으면 OpenAI 임베딩 클라이언트 생성."""
        if self._client is None:
            self._client = _build_openai_client(self._resolved_settings)
        return self._client

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """텍스트 배치 → OpenAI 임베딩(EmbeddingProvider 구현).

        빈 입력은 빈 리스트(API 호출 생략). 그 외엔 create 후 행 추출.
        """
        if not texts:
            return []
        response = self._get_client().create(
            model=self._resolved_settings.embedding_model_openai,
            input=list(texts),
        )
        return _extract_openai_rows(response)


def _build_openai_client(settings: Settings) -> _OpenAIEmbeddingsClient:
    """기본 OpenAI 임베딩 클라이언트 생성 (지연 import + 키 검증).

    `openai`가 없는 환경에서도 모듈 import가 깨지지 않도록 *호출 시점에만* import한다
    (ollama.py 패턴). 키 미설정이면 명확한 RuntimeError(조용한 폴백 금지). 키(SecretStr)는
    *클라이언트 생성 인자로 넘기는 그 순간에만* 평문을 꺼낸다(langfuse_sink.py 패턴) —
    로그·repr에 남기지 않는다.
    """
    if not settings.openai_configured:
        raise RuntimeError(
            "OpenAI API 키가 설정되지 않았습니다(WHYMATH_OPENAI_API_KEY). "
            "embedding_provider=openai는 키가 필요합니다 — local로 바꾸거나 키를 주입하세요."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover — 환경 의존(라이브러리 미설치)
        raise RuntimeError(
            "openai 클라이언트가 설치되지 않았습니다. `pip install openai` 후 다시 시도하세요."
        ) from exc
    # cast 사유: OpenAI().embeddings의 정밀 스텁(create overload·Embeddings 반환)은 우리의
    # 좁은 시임 `_OpenAIEmbeddingsClient`와 형태가 어긋난다. 실제 쓰는 규약(create(model=,
    # input=))은 런타임에 충족되므로 스텁 정밀도 차이만 cast로 좁힌다(타입 무시 X).
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    return cast(_OpenAIEmbeddingsClient, client.embeddings)


# ──────────────────────────────────────────────────────────────────────────
# 코사인 유사도 — 좌석 공용 헬퍼(VectorIndex·매처가 사용)
# ──────────────────────────────────────────────────────────────────────────
def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """두 벡터의 코사인 유사도 [-1, 1]. 한쪽이 영벡터면 0(정의 불가를 0으로 안전 처리).

    차원 불일치는 ValueError(서로 다른 제공자 벡터 비교 방지 — 좌석 불변식).
    """
    if len(a) != len(b):
        raise ValueError(f"코사인 비교 차원 불일치: {len(a)} vs {len(b)}.")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def build_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Settings.embedding_provider에 따라 기본 제공자를 만든다(좌석 팩토리).

    `local`(기본)·`openai`·`fake` 중 선택. 어떤 경우도 *모델·클라이언트는 지연*이라 이
    팩토리 호출만으로는 모델 로드·네트워크가 일어나지 않는다(첫 embed에서). 테스트는 보통
    이 팩토리를 거치지 않고 FakeEmbeddingProvider를 직접 주입한다(hermetic).
    """
    resolved = settings if settings is not None else get_settings()
    provider = resolved.embedding_provider
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings=resolved)
    # 기본 local — 로컬 우선(CLAUDE.md 비용·Phaiakes9).
    return LocalEmbeddingProvider(settings=resolved)
