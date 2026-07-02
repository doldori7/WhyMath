"""개념 임베딩 영속 ORM — L1 개념그래프 의미검색 백킹 테이블 (pgvector·슬라이스 3).

L1 개념그래프 적재 아크의 *의미 임베딩 좌석*이다. 슬2가 개념을 Neo4j 그래프 저장소에 멱등
적재했고(노드 키=UC concept_id), 이 테이블은 **같은 UC 키로** 개념의 *의미 임베딩 벡터*를
pgvector에 한 행씩 보관한다 — 이중 store(Neo4j 그래프 + pgvector 벡터)가 *단일 UC 키*로
join된다. 슬98 결정(벡터 DB=pgvector·Postgres 16 통합)을 개념 자산으로 확장한 두 번째 결선
(첫 결선은 L4 `misconception_embedding`).

이 모듈은 L4 `misconception_embedding.py`를 개념용으로 *미러링*한다. 차이는 ① PK가
`concept_id`(UC TEXT — Neo4j 노드 키와 동일) ② **원문 비저장**(`source_text` 미보유 — 표현
해시 `text_hash`만 둔다·아래 redaction 근거)이다. 나머지(provider/model/dim 메타·고정 차원
`vector(N)`·HNSW 인덱스 없음)는 동일 규약이다.

설계 결정:
- **PK는 concept_id(TEXT·UC)**: 슬1 `idmap`이 발급한 Universal Concept ID(`UC.<domain>.
  <topic>.<slug>`). 슬2 Neo4j 노드 키와 *동일 키 공간*이라 그래프↔벡터가 한 키로 join된다
  (이중 store 단일 키 일관성). upsert가 PK 충돌로 멱등 동작한다(`ON CONFLICT(concept_id) DO
  UPDATE`) — 같은 개념 재적재가 행을 갱신.
- **embedding은 `pgvector.sqlalchemy.Vector(dim)`**(차원 고정·`config.embedding_dim` 기본
  1024·bge-m3): `misconception_embedding`과 *같은 컬럼 차원 규약*. 401+ 개념도 현재 규모에선
  seq-scan이 정합하나(스케일 시 HNSW cosine 인덱스가 정석 — 후속), SQLAlchemy `Vector` 타입·
  마이그레이션이 차원을 박으므로 config와 동기화한다(모델 교체[Fake 64·bge-m3 1024·te-3-large
  3072] 시 config+마이그레이션 함께 조정).
- **provider/model/dim 메타**: 같은 임베딩 공간만 비교하려고 보관한다(서로 다른 모델 벡터
  혼재 방지 — 검색이 현재 provider/model 행만 본다). dim은 디버그·정합 점검용.
- **text_hash(TEXT)**: 임베딩 *원본 표현*(개념 표현 = name_ko + metaphor + accepted_expressions)
  의 해시 — 표현이 바뀌면 재임베딩이 필요함을 감지하는 신호(적재기가 비교에 쓸 수 있다).
  **원문 자체는 저장하지 않고 해시만** 둔다(아래 redaction).
- **source_text 비저장(redaction·프라이버시·중복 — CLAUDE.md 우선순위 #2)**: 임베딩 *원문*은
  컬럼으로 두지 않는다. ① 임베딩 입력은 안전 필드(name_ko·metaphor·accepted_expressions)뿐이라
  본문 누수는 없으나, *원문 재저장을 구조적으로 차단*해 두면 향후 입력이 오염돼도 이 테이블엔
  본문이 못 들어온다(방어). ② 임베딩 벡터만이 의미검색에 필요하고 원문은 Neo4j 노드 속성에
  이미 있다(중복 제거). 변경 감지는 `text_hash`로 충분하다.
- **subject(TEXT·NOT NULL·server_default '수학')**: 임베딩 namespace의 *교과 축*(과목 확장 S1 —
  `l1/embedding_primitives.py` namespace 불변식 "namespace = 테이블(kind) × subject"). 축 구분 명문:
  ① `concept_node.domain`(영역명 '[고]미적분' 등 — *수학 내부* 영역 축)과 **직교**한다 — domain은
  수학 안의 세부 영역이고 subject는 교과('수학'·'물리') 경계다. ② 교육과정 스코핑의 진실 출처는
  `CurriculumEntry.subject`(Overlay 정본)다 — 임베딩 행의 subject는 **콘텐츠 팩 태그**(적재기가
  적재 시점에 `DEFAULT_EMBEDDING_SUBJECT` 상수를 주입하는 스코프 라벨)이지 교육과정 매핑 주장이
  아니다(이중 진실 아님·정본 조회는 Overlay로). ③ server_default '수학'으로 기존 행이 무손상
  백필된다(재임베딩 0 — subject는 컬럼/스코프에만 들어가고 임베딩 *텍스트*에는 안 들어간다).
- **updated_at**: 마지막 upsert 시각(운영·신선도 추적). server_default now().
- **HNSW/IVFFlat 인덱스 없음**: `misconception_embedding`과 동일 — 현 규모는 seq-scan이 최적.
  스케일 코퍼스(문제은행·학생 풀이까지)는 *fixed-dim + HNSW cosine 인덱스*가 정석이나, 이
  테이블은 *영속화 + 의미검색 groundwork*이지 스케일 검색 최적화가 아니다(과장 금지).
- **schema/ 상응물 없음**: 서버 내부 의미검색 인덱스라 Pydantic schema 표면이 없다
  (`misconception_embedding` 선례 — 검색 결과는 좌석 인터페이스에 흡수).

7계층: 이 테이블은 L1 데이터 기반의 *영속/검색 인프라*다. **L1은 임베딩 저장소·적재만**
소유하고, 의미검색 *로직*(L2/L3/L4가 이 벡터로 무엇을 하는지)은 후속 슬라이스(슬4+)에서
조회 좌석으로 얹는다. 게이팅(review_status 보류분 제외)도 적재가 아니라 *조회* 몫이다 —
이 테이블엔 검수 상태와 무관하게 전 개념을 적재한다(의미검색 recall 보존).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.config import get_settings
from whymath_backend.db.base import Base

# 컬럼 차원은 모듈 로드 시점의 Settings에서 읽는다(기본 1024). 적재기·마이그레이션과 *같은
# 값*을 써야 정합한다(config.embedding_dim 단일 출처·misconception_embedding 동일 규약).
# lru_cache라 프로세스 1회 해석.
_EMBEDDING_DIM = get_settings().embedding_dim


class ConceptEmbedding(Base):
    """개념 의미 임베딩 영속 — pgvector `vector` 백킹 행(UC 키·슬3).

    한 행 = 한 개념의 표현 임베딩. PK(concept_id=UC) upsert로 멱등 적재하고, provider/model로
    임베딩 공간을 구분해 *같은 공간 행끼리만* 코사인 비교한다. 원문은 저장하지 않고 표현 해시
    (text_hash)만 둔다(redaction·중복 — docstring 참조).
    """

    __tablename__ = "concept_embedding"

    # PK = Universal Concept ID(슬1 idmap 발급·슬2 Neo4j 노드 키와 동일). upsert 충돌 키.
    concept_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # pgvector vector(N) — config.embedding_dim 고정 차원. 코사인 거리 <=> 로 검색.
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    # 임베딩 공간 식별 — provider(local/openai/fake)·model(bge-m3 등). 같은 공간만 비교.
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 교과 축(namespace = 테이블 × subject) — 콘텐츠 팩 태그(정본은 CurriculumEntry.subject).
    # server_default는 DEFAULT_EMBEDDING_SUBJECT('수학')와 동일해야 한다(거버넌스 테스트 동결).
    subject: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="수학")
    # 임베딩 차원(디버그·정합 점검). 컬럼 타입 차원과 일치해야 한다.
    dim: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # 임베딩 원본 표현의 해시 — 표현 변경(재임베딩 필요) 감지 신호. **원문은 미저장**(해시만).
    text_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(upsert 시 코드가 갱신).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["ConceptEmbedding"]
