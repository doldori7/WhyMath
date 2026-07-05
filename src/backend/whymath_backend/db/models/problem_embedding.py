"""문제 임베딩 영속 ORM — L1 자체생성 동등문제 dedup pgvector 백킹 테이블 (S2-c).

`atom_embedding`(원자 의미검색 pgvector 좌석·Phase 2b)의 *문제 코퍼스* 짝이다. S2-b가 자체생성
동등문제를 backend `problem` 테이블에 적재했고(`l1/problem_bank/populate.py`), 이 테이블은 각
문제의 *발문(question_text) 임베딩 벡터*를 **같은 problem_id 키로** pgvector에 한 행씩 보관한다 —
`problem.problem_id`(UUID PK)와 *동일 키 공간*이라 문제 엔티티와 임베딩이 한 키로 join된다.

이 모듈은 `atom_embedding.py`를 문제용으로 *미러링*한다. 차이는 ① PK가 `problem_id`(UUID —
`problem.problem_id` FK·code(TEXT)가 아님) ② 임베딩 입력이 *발문(question_text)*(원자판의
name+transfer 대신 — 중복 정의축이 발문이므로) ③ `subject` 교과 축을 **두지 않는다**(dedup은 문제
코퍼스 *내부* 자기-kind 질의이고 Phase 1 코퍼스가 전량 수학이라, provider·model 임베딩 공간
필터만으로 충분하다 — 필요 시 후속 슬라이스가 세 임베딩 테이블과 함께 subject 축을 얹는다)
④ 시각 필드가 `created_at`(원자판 `updated_at` 대신 — 임베딩 행의 *생성* 시각·재임베딩 시
embedding/text_hash만 갱신하고 created_at은 보존)이다. 나머지(provider/model/dim 메타·고정 차원
`vector(N)`·HNSW 인덱스 없음·원문 비저장·ON CONFLICT 멱등)는 동일 규약이다.

과유사 dedup 게이트(S2-c 목적): 자체생성 동등문제의 *과유사 변형*(거의 동일한 발문 남발)을
막으려면 신규 후보를 코퍼스에 저장하기 *전에* 이 테이블의 기존 벡터와 코사인 유사도를 비교해야
한다. 이 ORM은 그 비교의 *영속 백킹*만 소유하고, 판정 로직(threshold·find_near_duplicates)은
`l1/problem_bank/embedding.py`가 순수 질의 함수로 얹는다(적재에 강제 결선하지 않음 — 게이팅은
authoring/생성 시점 조회 몫).

설계 결정(atom_embedding 미러):
- **PK는 problem_id(UUID)·느슨참조(hard FK 없음)**: `problem.problem_id`와 *동일 키 공간*이되
  atom_embedding이 `concept.code`를 FK 없이 *같은 키로만* 참조하는 것과 동형으로, 하드 FK를
  두지 않는다. 이유: ① 임베딩 적재(`populate_problem_embeddings`)를 `problem` 적재 순서·트랜잭션
  경계와 *분리*(FK면 문제 행이 먼저 있어야만 임베딩 upsert 가능·backfill/재임베딩 결합) ②
  atom_embedding 규약과 정합. 고아 벡터(삭제된 문제의 임베딩)는 dedup에서 최악 *삭제된 문제와의
  과유사 1건*을 낳는 경미한 비용이며, 재적재/정리로 수렴한다. upsert가 PK 충돌로 멱등 동작한다
  (`ON CONFLICT(problem_id) DO UPDATE`) — 같은 문제 재적재가 행을 갱신.
- **embedding은 `pgvector.sqlalchemy.Vector(dim)`**(차원 고정·`config.embedding_dim` 기본 1024·
  bge-m3): `atom_embedding`과 *같은 컬럼 차원 규약*. SQLAlchemy `Vector` 타입·마이그레이션이
  차원을 박으므로 config와 동기화한다(모델 교체[Fake 64·bge-m3 1024·te-3-large 3072] 시
  config+마이그레이션 함께 조정).
- **provider/model/dim 메타**: 같은 임베딩 공간만 비교하려고 보관한다(서로 다른 모델 벡터
  혼재 방지 — dedup 검색이 현재 provider/model 행만 본다). dim은 디버그·정합 점검용.
- **text_hash(TEXT)**: 임베딩 *원본 표현*(발문 = question_text)의 해시 — 표현이 바뀌면
  재임베딩이 필요함을 감지하는 신호(멱등 재적재 스킵용). **원문 자체는 저장하지 않고 해시만**
  둔다(redaction·중복 — 발문 원문은 `problem.question_text`에 이미 있다).
- **source_text 비저장(redaction·중복 — atom_embedding 동형)**: 임베딩 *원문*(발문)은 컬럼으로
  두지 않는다. 임베딩 벡터만이 dedup에 필요하고 원문은 `problem`에 이미 있다. 변경 감지는
  `text_hash`로 충분하다.
- **created_at**: 임베딩 행 최초 생성 시각(운영·추적). server_default now()이며 ON CONFLICT 갱신
  시엔 SET하지 않아 *생성 시각을 보존*한다(재임베딩은 벡터/해시만 갱신).
- **HNSW/IVFFlat 인덱스 없음**: `atom_embedding`과 동일 — 현 규모(Phase 1 손저작 코퍼스)는
  seq-scan이 최적. 스케일 코퍼스는 *fixed-dim + HNSW cosine 인덱스*가 정석이나, 이 테이블은
  *영속화 + dedup groundwork*이지 스케일 검색 최적화가 아니다(과장 금지).
- **schema/ 상응물 없음**: 서버 내부 dedup 인덱스라 Pydantic schema 표면이 없다
  (`atom_embedding`·`concept_embedding` 선례 — 검색 결과는 좌석 인터페이스에 흡수).

7계층: 이 테이블은 L1 데이터 기반의 *영속/검색 인프라*다. **L1은 임베딩 저장소·적재·순수
dedup 질의만** 소유하고, dedup 게이트를 *언제* 부를지(생성 파이프라인 결선)는 S2-d 생성기 몫이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.config import get_settings
from whymath_backend.db.base import Base

# 컬럼 차원은 모듈 로드 시점의 Settings에서 읽는다(기본 1024). 적재기·마이그레이션과 *같은
# 값*을 써야 정합한다(config.embedding_dim 단일 출처·atom_embedding 동일 규약). lru_cache라
# 프로세스 1회 해석.
_EMBEDDING_DIM = get_settings().embedding_dim


class ProblemEmbedding(Base):
    """문제 발문 의미 임베딩 영속 — pgvector `vector` 백킹 행(problem_id 키·S2-c).

    한 행 = 한 문제의 발문(question_text) 임베딩. PK(problem_id) upsert로 멱등 적재하고,
    provider/model로 임베딩 공간을 구분해 *같은 공간 행끼리만* 코사인 비교한다(과유사 dedup).
    원문은 저장하지 않고 표현 해시(text_hash)만 둔다(redaction·중복 — docstring 참조).
    """

    __tablename__ = "problem_embedding"

    # PK = 문제 problem_id(`problem.problem_id`와 동일 키 공간·느슨참조·하드 FK 없음). upsert
    # 충돌 키. atom_embedding이 concept.code를 FK 없이 같은 키로만 참조하는 것과 동형(docstring).
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    # pgvector vector(N) — config.embedding_dim 고정 차원. 코사인 거리 <=> 로 검색.
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    # 임베딩 공간 식별 — provider(local/openai/fake)·model(bge-m3 등). 같은 공간만 비교.
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 임베딩 차원(디버그·정합 점검). 컬럼 타입 차원과 일치해야 한다.
    dim: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # 임베딩 원본 표현(발문 = question_text)의 해시 — 표현 변경(재임베딩 필요) 감지·멱등 스킵
    # 신호. **원문은 미저장**(해시만).
    text_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 임베딩 행 최초 생성 시각 — 운영·추적. server_default now()이며 ON CONFLICT 갱신 시엔
    # SET하지 않아 생성 시각을 보존한다(atom_embedding의 updated_at과 대비되는 시각 축).
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["ProblemEmbedding"]
