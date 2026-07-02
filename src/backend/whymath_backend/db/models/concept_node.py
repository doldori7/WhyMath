"""개념 메타 *PG 프로젝션* ORM — UC 키 안전 표시·게이팅 필드 (개념그래프 소비 슬라이스 1).

L1 개념그래프 *소비* 트랙의 첫 좌석이다. 적재 아크(슬1~4)가 개념을 Neo4j 그래프(슬2)·pgvector
벡터(슬3)에 *동일 UC 키*로 적재했고, 슬4 의미검색(`GET /v1/concepts/search`)은 현재 UC
concept_id + similarity만 돌려준다 — `name_ko` 같은 *안전 메타*는 빠져 있다. 그 enrichment를
가로막던 건 **UC↔backend-PG 키 공간 차이**(`concept_embedding.concept_id`는 UC 키인데 backend
PG `concept` 테이블은 UUID PK + `code`라 UC 컬럼이 없다 — `retrieval.py`·`api/concepts.py`
노출 계약 주석)였다. 이 테이블이 그 다리다.

────────────────────────────────────────────────────────────────────────────
메타 브리지 = PG 프로젝션 (확정 설계 결정 — backend↔Neo4j 런타임 연결 안 함)
────────────────────────────────────────────────────────────────────────────
backend는 async-PG 단일 데이터 평면을 유지한다(런타임 Neo4j 드라이버 도입 0). 대신 슬1 산출
`graph.json`의 개념 *메타*를 **UC 키 PG 테이블(`concept_node`)로 프로젝션**한다 — 검색
enrichment·검수 게이팅을 **PG 조인**(이 테이블과 `concept_embedding`을 UC로 join)으로 한다.
`concept_embedding`(슬3)이 *임베딩 벡터*의 UC 키 영속이라면, `concept_node`는 *표시·게이팅
메타*의 UC 키 영속이다 — 같은 UC 공간에 두 투영이 나란히 서고, 검색이 둘을 한 키로 잇는다.

이 테이블은 Neo4j 노드의 *부분 미러*다(전체 traversal·엣지는 여전히 Neo4j 소관). 미러하는 건
검색 결과를 풍부하게 할 *안전 표시 필드*와 *검수 게이팅 플래그*뿐이다.

────────────────────────────────────────────────────────────────────────────
redaction (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
**`description`·`formal_definition`은 이 테이블에 컬럼으로 두지 않는다.** 성취기준 *본문* 근접
복제 위험 필드이고, ① 슬1 `Concept` 모델에 슬롯이 없어 `graph.json`에도 없으며(`_provenance.
json`의 redacted: `concepts.description`·`concepts.formal_definition`) ② 적재기가 *읽지도 않고*
③ 여기 *둘 곳도 없다*(삼중 방어). `concept_embedding`이 원문 자체를 컬럼으로 두지 않은 것과
같은 redaction 규약을 메타 프로젝션에도 그대로 적용한다 — 안전 표시 필드만 투영한다.

수록 필드는 *전부 안전*이다:
  - `name_ko`·`domain`(영역명): 표시·식별용 자체 메타(본문 아님).
  - `review_status`(reviewed/pending): 검수 게이팅 플래그(메타 상태값).
  - `standard_codes`(NCIC 코드[])·`ccss_code`·`difficulty_tier`: 코드·층위(코드는 사실정보·
    공공이며 *본문 statement는 아님* — `Concept` 모델 §법적 주석과 동일).

pedagogy 이관(2026-07-02 Part 2 §3 Stage B): `metaphor`·`accepted_expressions` 컬럼을 *제거*했다.
두 필드는 pedagogy 정보라 identity/메타 프로젝션이 아니라 pedagogy 계층 `concept_content`(code 키)가
단일 진실이다(Concept Purity). 이 컬럼들은 reader가 없던 write-only였고(`fetch_node_meta`는
name_ko·domain·review_status만 조회), 임베딩은 이제 ConceptContent에서 소싱한다. Alembic drop.

review_status는 PG enum 타입을 새로 만들지 않고 **plain `sa.Text`**로 둔다(`concept_embedding`이
enum 타입 없이 plain text만 쓴 것과 동형). graph.json은 `use_enum_values=True`로 이미 문자열
('reviewed'/'pending')을 싣고, 게이팅 필터는 리터럴 'reviewed'와 비교한다 — 새 PG 타입을 도입해
data-pipeline `ReviewStatus`에 결합하기보다, 경량 프로젝션엔 문자열 보관이 정합하다.

────────────────────────────────────────────────────────────────────────────
키 일관성 (이중→삼중 store 단일 UC 키)
────────────────────────────────────────────────────────────────────────────
PK `concept_id`(TEXT·UC)는 **슬2 Neo4j 노드 키·슬3 `concept_embedding.concept_id`와 동일 키
공간**(`UC.<domain>.<topic>.<slug>`). 이로써 한 UC 키가 *세 투영*(Neo4j 그래프·pgvector 벡터·
PG 메타)을 잇는다. upsert가 PK 충돌로 멱등(`ON CONFLICT(concept_id) DO UPDATE`) — 같은 개념
재적재가 행을 갱신한다. (주의: backend PG `concept` 테이블[UUID PK+code]과는 *여전히 별개*다 —
이 테이블은 UC 공간 전용 프로젝션이고, 그 둘을 잇지 않는다.)

7계층: L1 데이터 기반의 *영속 프로젝션*(검색 서빙 백킹). 표시·게이팅 메타를 보관할 뿐, 검색
*로직*(L1 retrieval)·소비(L2 약개념 추천·L4 오개념↔개념 결선)는 이 좌석을 쓰되 여기서 구현하지
않는다(역방향 의존 금지·후속). schema/ 상응 Pydantic 표면은 없다(`concept_embedding` 선례 —
프로젝션은 검색 enrichment에 흡수되고 독립 CRUD 표면을 갖지 않는다).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class ConceptNode(Base):
    """개념 메타 PG 프로젝션 — UC 키 안전 표시·게이팅 필드(검색 enrichment 백킹).

    한 행 = 한 개념의 *안전 메타*(name_ko·domain·review_status·코드·교수 주석). PK(concept_id=
    UC)로 슬3 `concept_embedding`·슬2 Neo4j 노드와 join된다(삼중 store 단일 키). upsert로 멱등
    적재한다(`ON CONFLICT(concept_id) DO UPDATE`). **description·formal_definition은 컬럼으로
    두지 않는다**(redaction — 안전 표시 필드만 투영·docstring 참조).
    """

    __tablename__ = "concept_node"

    # PK = Universal Concept ID(슬1 idmap 발급·슬2 Neo4j 노드 키·슬3 concept_embedding과 동일).
    # upsert 충돌 키 — 같은 UC 재적재 시 행 갱신(멱등).
    concept_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 한국어 명칭(graph.json name_ko·필수). 검색 enrichment의 핵심 표시 필드.
    name_ko: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 영역명(graph.json domain=category, 예 '[고]미적분'·필수). 표시·필터 보조.
    domain: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 검수 게이팅 플래그 — 'reviewed'/'pending' 문자열(graph.json review_status·use_enum_values).
    # PG native enum을 새로 만들지 않고 plain text(concept_embedding 동형·docstring 참조).
    # 게이팅(reviewed_only)이 이 값을 리터럴 'reviewed'와 비교한다. NOT NULL(graph.json 항상 보유).
    review_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 매핑된 NCIC 성취기준 *코드* 목록(graph.json standard_codes·기본 빈 배열). 코드는 사실정보·
    # 공공이며 *본문 statement는 아님*(redaction 무관). nullable=False·server_default 빈 배열.
    standard_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 매칭 미국 CCSS 코드(graph.json ccss_code·nullable). CCSS *본문*은 복제 금지·코드만.
    ccss_code: Mapped[str | None] = mapped_column(sa.Text)
    # 난이도층 [0, 24](graph.json difficulty_tier·nullable). 0=가장 기초.
    difficulty_tier: Mapped[int | None] = mapped_column(sa.Integer)
    # (metaphor·accepted_expressions 컬럼은 Part 2 §3 Stage B로 제거 — pedagogy=concept_content.)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(upsert 시 코드가 갱신·슬3 동형).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["ConceptNode"]
