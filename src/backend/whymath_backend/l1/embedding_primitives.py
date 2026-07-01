"""임베딩 *레이어-중립* 프리미티브 — provider 좌석 Protocol·표현 해시·공간 식별자.

L1 개념/원자 그래프 임베딩(`l1/concept_graph/embedding.py`·`l1/atom_graph/embedding.py`)과 L4
오개념 의미 매칭(`l4/misconception/semantic/*`)이 *공유*하는 임베딩 프리미티브를 둔다. 이전에는
이 심볼들이 `l4/.../pgvector_index.py`·`provider.py`(L4)에 살아서 **L1 임베딩 모듈이 L4를 위로
import**하는 역방향 의존(지연 import로 가린 순환)이 있었다 — 본 모듈이 그 의존을 *아래로* 뒤집는다
(의존성 역전: 추상은 하위 중립 레이어, 구현체는 상위 L4). config(중립)·stdlib만 의존하므로 어떤
L계층도 import하지 않는다(순환 불가).

담는 것(전부 순수·인프라):
  - `EmbeddingProvider`(Protocol): 텍스트 배치 → 벡터. 구조적 타이핑(구현체는 L4 provider.py).
  - `text_hash`: 임베딩 원본 표현의 안정 해시(표현 변경=재임베딩 필요 감지).
  - `provider_model_identity`: provider 객체 + Settings → (provider_name, model_name) 공간 식별자.
  - `embed_changed`: skip-if-unchanged 적재 코어(개념·원자·오개념 공유).
  - `build_sync_engine`: pgvector sync(psycopg) 엔진 빌더 + register_vector 리스너(sync 좌석 공유).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from whymath_backend.config import Settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# 임베딩 원본 표현(embed-text) *포맷 계약 버전*. 개념·원자·오개념 텍스트 빌더가 공유하는
# 결합 규칙(구분자 `". "`·strip·빈값 skip)을 바꾸면(예: 구분자 교체·필드 순서) 이 값을 올린다 —
# 사전 계산된 벡터가 *조용히* stale 되는 것을 감지할 근거(차후 임베딩 행에 함께 영속 시 drift
# 비교). math_dsl 감사 §5(포맷 계약 미고정) 대응. 현재 v1 = `". ".join(strip·non-empty)`.
EMBEDDING_TEXT_FORMAT_VERSION = 1


def join_embedding_text(*parts: object) -> str:
    """임베딩 원본 표현 결합 — *단일 포맷 권위*(개념·원자·오개념 빌더 공유·감사 §2 3중복 제거).

    각 조각을 `str().strip()`하고 빈/None은 건너뛴 뒤 `". "`로 잇는다(포맷 v1·
    `EMBEDDING_TEXT_FORMAT_VERSION`). 과거엔 이 결합 규칙이 `concept_embedding_text`·
    `atom_embedding_text`·`catalog_text` 세 곳에 따로 박혀 있어 구분자·순서 변경이 *조용한* drift를
    낳을 수 있었다 — 한 곳으로 모아 포맷 계약을 고정한다(필드 *선택*은 호출자 몫·결합만 공유).
    """
    return ". ".join(str(part).strip() for part in parts if part is not None and str(part).strip())


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


def text_hash(text: str) -> str:
    """임베딩 원본 표현의 안정 해시(SHA-256 hex) — 표현 변경(재임베딩 필요) 감지 신호.

    카탈로그 표현(`catalog_text`)·개념 표현(`concept_embedding_text`)이 바뀌면 해시가 달라져
    stale 행을 식별할 수 있다(populate가 비교에 쓸 수 있고, 행 메타로도 보관한다). 결정론·짧은
    hex(32바이트→64자)면 충분하다.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_changed(
    items: Sequence[tuple[str, str]],
    *,
    provider: EmbeddingProvider,
    existing_hashes: Callable[[Sequence[str]], dict[str, str]],
    upsert: Callable[[str, list[float], str], None],
    item_noun: str = "항목",
) -> int:
    """skip-if-unchanged 임베딩 적재 코어 — *변경분만* embed·upsert (개념·원자·오개념 공유).

    개념(`populate_concept_embeddings`)·원자(`populate_atom_embeddings`)·오개념
    (`populate_pgvector`) 세 적재기가 문자 그대로 같은 절차를 반복하던 것을 한곳으로 모은다
    (감사 §2 3중복 제거·drift 리스크 hidden dependency 차단). 각 호출자는 (키, 표현) 쌍 목록과
    좌석 두 개(`existing_hashes`·`upsert`)·provider만 넘기고, *어떤 필드로 표현을 만들지*와
    *어느 테이블에 어떻게 upsert할지*는 그대로 호출자 몫으로 남긴다(결합만 공유).

    절차: ① `existing_hashes(keys)`로 현행 `text_hash`를 한 번에 조회 ② `text_hash(text)`와 다른
    (=표현 변경·신규·다른 임베딩 공간) 항목만 추린다 ③ 없으면 provider 호출 없이 0 반환(비용
    절감·CLAUDE.md #6) ④ 변경분만 `provider.embed` ⑤ 개수 불일치는 fail-loud(RuntimeError) ⑥ 각
    변경분을 `upsert(key, vector, text)`로 적재. 반환은 *실제 적재한(변경분)* 개수.

    `text_hash`는 *포맷된 표현 문자열*의 해시라 포맷 변경(구분자·필드 순서)도 표현이 바뀌어
    해시에 반영된다 → 별도 format_version 불필요. `existing_hashes`가 같은 provider·model 행만
    보므로 다른 임베딩 공간은 조회에 안 잡혀 재임베딩된다(호출자 인덱스 계약).
    """
    existing = existing_hashes([key for key, _ in items])
    changed = [(key, text) for key, text in items if existing.get(key) != text_hash(text)]
    if not changed:
        return 0
    vectors = provider.embed([text for _, text in changed])
    if len(vectors) != len(changed):
        raise RuntimeError(
            f"임베딩 개수({len(vectors)})가 대상 {item_noun} 개수({len(changed)})와 다릅니다 "
            "— provider.embed가 입력 순서·길이를 보존해야 합니다."
        )
    for (key, text), vec in zip(changed, vectors, strict=True):
        upsert(key, vec, text)
    return len(changed)


def provider_model_identity(provider: EmbeddingProvider, settings: Settings) -> tuple[str, str]:
    """provider 객체 + Settings에서 (provider_name, model_name) 임베딩 공간 식별자를 해석.

    provider 좌석은 `embed`만 노출하므로 model 이름을 객체에서 못 읽는다. Settings의
    `embedding_provider`/모델 ID로 식별자를 짓는다(add/search가 같은 규약을 공유해 공간 일치).
    클래스명을 provider_name으로 써(local/openai/fake와 무관하게 *주입된 객체* 기준) 테스트가
    임의 provider를 넣어도 일관된다.
    """
    cls_name = type(provider).__name__
    if cls_name == "OpenAIEmbeddingProvider":
        return "openai", settings.embedding_model_openai
    if cls_name == "LocalEmbeddingProvider":
        return "local", settings.embedding_model_local
    if cls_name == "FakeEmbeddingProvider":
        return "fake", "fake-hash"
    # 알 수 없는 주입 provider — 클래스명을 공간 식별자로(테스트 scripted 등). 모델은 클래스명.
    return cls_name, cls_name


def build_sync_engine(settings: Settings) -> Engine:
    """기본 sync(psycopg) 엔진 생성 + pgvector 어댑터 등록 (지연 import·전 sync 좌석 공유 빌더).

    앱 본체는 async 전용(asyncpg)이고, pgvector add/search·적재/투영 좌석만 sync 엔진(psycopg)을
    쓴다. 그 빌더가 과거 `concept_graph/embedding.py`(L1)와 `l4/.../pgvector_index.py`(L4)에 *바이트
    동일하게 2벌* 복제돼 있어(감사 §2 hidden dependency·drift 리스크) 레이어-중립 프리미티브로
    합친다 — 개념/원자/투영 등 L1 적재기와 L4 오개념 pgvector가 *같은 한 좌석*을 공유한다.

    psycopg/SQLAlchemy/pgvector import는 *호출 시점*에만(모듈 import 깨짐 방지·순환 회피).
    `sync_database_url`(async URL에서 드라이버만 `+psycopg`로 파생)로 sync 엔진을 만들고, 각 raw
    연결에 `register_vector`를 거는 connect 리스너를 단다 — psycopg가 vector 타입을 바인딩/디코딩
    하게. `db_disable_pool`(통합테스트)면 NullPool(매 체크아웃 새 연결)로 다중 루프 충돌을 회피한다
    (async 엔진과 같은 가드). 확장(CREATE EXTENSION)은 마이그레이션이 보장하므로 여기선 타입 등록만.
    """
    from pgvector.psycopg import register_vector
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import NullPool

    if settings.db_disable_pool:
        engine = create_engine(settings.sync_database_url, poolclass=NullPool)
    else:
        engine = create_engine(settings.sync_database_url)

    @event.listens_for(engine, "connect")
    def _register_vector_on_connect(dbapi_connection: object, _record: object) -> None:
        # 각 새 psycopg 연결에 vector 어댑터 등록(바인딩 list[float]→vector·디코딩 역).
        register_vector(dbapi_connection)

    return engine


__all__ = [
    "EMBEDDING_TEXT_FORMAT_VERSION",
    "EmbeddingProvider",
    "build_sync_engine",
    "embed_changed",
    "join_embedding_text",
    "provider_model_identity",
    "text_hash",
]
