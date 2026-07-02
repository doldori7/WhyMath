"""오개념 임베딩 영속 ORM — 슬라이스 105 `PgVectorIndex` 백킹 테이블 (pgvector).

슬104 `VectorIndex` 좌석의 *영속(pgvector) 백엔드*가 적재·검색하는 테이블이다. 카탈로그
각 항목의 *표현*(`catalog_text` = `f"{name_kr}. {canonical_statement}"`) 임베딩을 한 행으로
보관하고, 질의 벡터에 코사인 거리(`<=>`)로 상위 후보를 찾는다. 슬98 결정(벡터 DB=pgvector·
Postgres 16 통합)의 첫 실 결선.

설계 결정:
- **PK는 misconception_id(TEXT)**: 카탈로그 항목 식별자(`Misconception.id`, kebab-case). `add`
  upsert가 PK 충돌로 동작하고(`ON CONFLICT(misconception_id) DO UPDATE`), 같은 항목 재적재가
  멱등하다. `concept.embedding_id`(슬98)와 달리 *이 테이블이 실 벡터 컬럼을 소유*한다.
- **embedding은 `pgvector.sqlalchemy.Vector(dim)`**(차원 고정·`config.embedding_dim` 기본 1024):
  pgvector `vector(N)` 컬럼. 30종 코퍼스는 seq-scan이라 *고정 차원이 검색 성능엔 무관*하나
  SQLAlchemy `Vector` 타입·마이그레이션이 차원을 박아야 정합하므로 config와 동기화한다(모델
  교체[Fake 64·bge-m3 1024·te-3-large 3072] 시 config+마이그레이션 함께 조정). **무차원
  `Vector()`도 가능**하나(차원 유연) 타입 명세가 덜 깔끔해 *고정 차원*을 택했다(태스크 결정).
- **provider/model/dim 메타**: 같은 임베딩 공간만 비교하려고 보관한다(서로 다른 모델 벡터
  혼재 방지 — `PgVectorIndex.search`가 현재 provider/model 행만 본다). dim은 디버그·정합 점검용.
- **text_hash(TEXT)**: 임베딩 *원본 표현*의 해시 — 카탈로그 표현(`catalog_text`)이 바뀌면
  재임베딩이 필요함을 감지하는 신호(populate가 비교에 쓸 수 있다). 표현 변경 추적용.
- **subject(TEXT·NOT NULL·server_default '수학')**: 임베딩 namespace의 *교과 축*(과목 확장 S1 —
  `l1/embedding_primitives.py` namespace 불변식 "namespace = 테이블(kind) × subject"). 축 구분 명문:
  ① 수학 내부 영역 축(`concept_node.domain`류)과 **직교**한다 — subject는 교과('수학'·'물리')
  경계다. ② 교육과정 스코핑의 진실 출처는 `CurriculumEntry.subject`(Overlay 정본)다 — 임베딩
  행의 subject는 **콘텐츠 팩 태그**(적재기가 적재 시점에 `DEFAULT_EMBEDDING_SUBJECT` 상수를
  주입하는 스코프 라벨)이지 교육과정 매핑 주장이 아니다. ③ 오개념 id의 kebab 접두(`phys-` 등 —
  subject_expansion_readiness.md §5)는 **명명 규약**이고 이 컬럼이 **질의 축**이다 — 접두는
  사람이 읽는 유래 표기, 스코프 필터는 컬럼으로만 건다(이중 진실 아님·접두 파싱으로 스코핑
  금지). server_default '수학'으로 기존 행이 무손상 백필된다(재임베딩 0 — subject는 컬럼/
  스코프에만 들어가고 임베딩 *텍스트*에는 안 들어간다).
- **updated_at**: 마지막 upsert 시각(운영·신선도 추적). server_default now().
- **HNSW/IVFFlat 인덱스 없음**: 30종은 seq-scan이 최적이라 ANN 인덱스를 두지 않는다.
  스케일 코퍼스(개념그래프 401+·문제은행·학생 풀이)는 *fixed-dim + HNSW cosine 인덱스*가
  정석(이 테이블은 *영속화 + 패턴 groundwork*이지 스케일 검색 최적화가 아님 — 과장 금지).
- **schema/ 상응물 없음**: 서버 내부 검색 인덱스라 Pydantic schema 표면이 없다(device_credential
  선례 — 검색 결과는 `IndexHit`로 좌석 인터페이스에 흡수).

7계층: 이 테이블도 L4 매처가 호출하는 *하위 인프라 좌석*(영속/검색)의 영속 표면이다. L4
SemanticMatcher는 ORM을 모르고 `VectorIndex` Protocol만 본다.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.config import get_settings
from whymath_backend.db.base import Base

# 컬럼 차원은 모듈 로드 시점의 Settings에서 읽는다(기본 1024). PgVectorIndex·마이그레이션과
# *같은 값*을 써야 정합한다(config.embedding_dim 단일 출처). lru_cache라 프로세스 1회 해석.
_EMBEDDING_DIM = get_settings().embedding_dim


class MisconceptionEmbedding(Base):
    """오개념 임베딩 영속 — `PgVectorIndex.add/search`의 백킹 행(pgvector `vector`).

    한 행 = 한 카탈로그 항목의 표현 임베딩. PK(misconception_id) upsert로 멱등 적재하고,
    provider/model로 임베딩 공간을 구분해 *같은 공간 행끼리만* 코사인 비교한다.
    """

    __tablename__ = "misconception_embedding"

    # PK = misconception.id(카탈로그 식별자·kebab-case). upsert 충돌 키.
    misconception_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # pgvector vector(N) — config.embedding_dim 고정 차원. 코사인 거리 <=> 로 검색.
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    # 임베딩 공간 식별 — provider(local/openai/fake)·model(bge-m3 등). 같은 공간만 비교.
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 교과 축(namespace = 테이블 × subject) — 콘텐츠 팩 태그. kebab 접두(phys-)는 명명 규약,
    # 질의 축은 이 컬럼(모듈 docstring ③). server_default는 DEFAULT_EMBEDDING_SUBJECT와 동일.
    subject: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="수학")
    # 임베딩 차원(디버그·정합 점검). 컬럼 타입 차원과 일치해야 한다.
    dim: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # 임베딩 원본 표현(catalog_text)의 해시 — 표현 변경(재임베딩 필요) 감지 신호.
    text_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(upsert 시 코드가 갱신).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["MisconceptionEmbedding"]
