"""개념(concept) 도메인 HTTP API — 첫 DB-backed 라우터 (영속 레이어 → HTTP 표면).

엔드포인트(prefix `/v1/concepts`):
  - POST   /v1/concepts          — 개념 생성(검증된 schema.Concept → ORM → commit). 201.
  - GET    /v1/concepts/{id}     — 단건 조회(UUID). 없으면 404.
  - GET    /v1/concepts          — 목록(code 오름차순, limit/offset 페이지네이션).

세션 결선: `db.session.get_session` 의존성을 `Annotated[AsyncSession, Depends(...)]`로 받는다
(Depends를 기본인자에 두면 ruff B008·mypy가 막으므로 Annotated 메타데이터로 둔다 — FastAPI
현행 권장 패턴). 트랜잭션 commit/rollback은 *핸들러 책임*이다(get_session은 세션을 열고
닫기만 함 — 읽기 요청까지 강제 commit하지 않으려는 session.py 계약).

schema↔ORM seam은 `Concept.from_schema`/`to_schema`(problem.py 패턴)가 담당한다 — 핸들러는
PG 행을 직접 만지지 않고 검증된 Pydantic 모델만 주고받는다.

경계 메모(CLAUDE.md): `description`·`formal_definition` 등 교수 텍스트는 *자체 작성*이어야
하며(검정교과서·EBS 본문 복제 금지) — 이 불변식은 schema.Concept 검수 단계 책임이고 이
라우터는 이미 검증된 모델을 영속화할 뿐이다.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept import Concept, ConceptEdge
from whymath_backend.db.session import get_session
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ConceptEdge as ConceptEdgeSchema

router = APIRouter(prefix="/v1/concepts", tags=["concept"])

# get_session 의존성 — Annotated 메타데이터로 둬 기본인자 호출(B008)을 피한다.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ConceptSchema,
    summary="개념 노드 생성",
)
async def create_concept(body: ConceptSchema, session: SessionDep) -> ConceptSchema:
    """검증된 schema.Concept를 영속화하고 복원해 반환한다(201).

    `code`는 UNIQUE이므로 중복이면 PG가 IntegrityError를 던진다 → 롤백 후 **409**로
    명확히 보고한다(스택트레이스 노출 금지 — 시스템 경계 검증). commit은 핸들러 책임이며
    여기서 명시적으로 부른다(get_session은 commit하지 않음).
    """
    orm = Concept.from_schema(body)
    session.add(orm)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 존재하는 개념 code입니다: {body.code}",
        ) from exc
    await session.refresh(orm)
    return orm.to_schema()


@router.get("/{concept_id}", response_model=ConceptSchema, summary="개념 단건 조회")
async def read_concept(concept_id: uuid.UUID, session: SessionDep) -> ConceptSchema:
    """UUID로 개념 단건 조회 — 없으면 404."""
    orm = await session.get(Concept, concept_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"개념을 찾을 수 없습니다: {concept_id}",
        )
    return orm.to_schema()


@router.get("", response_model=list[ConceptSchema], summary="개념 목록")
async def list_concepts(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200, description="페이지 크기")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 행 수")] = 0,
) -> list[ConceptSchema]:
    """개념 목록 — `code` 오름차순, limit/offset 페이지네이션.

    정렬 키를 code(UNIQUE)로 고정해 페이지네이션이 안정적(동률 없는 전순서)이다.
    """
    stmt = select(Concept).order_by(Concept.code).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.get(
    "/{concept_id}/edges",
    response_model=list[ConceptEdgeSchema],
    summary="개념 의존 엣지 목록",
)
async def list_concept_edges(concept_id: uuid.UUID, session: SessionDep) -> list[ConceptEdgeSchema]:
    """이 개념에서 나가는(outgoing) 그래프 엣지 목록 — 개념 없으면 404.

    `from_concept_id == path`인 엣지만(나가는 방향, `idx_concept_edge_from` 활용). 역방향은 후속.
    주의: 이건 backend PG `concept_edge`이며, data-pipeline의 Neo4j concept_graph와 *별개*다
    (다른 키 공간·다른 저장소).
    """
    if await session.get(Concept, concept_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"개념을 찾을 수 없습니다: {concept_id}",
        )
    stmt = (
        select(ConceptEdge)
        .where(ConceptEdge.from_concept_id == concept_id)
        .order_by(ConceptEdge.to_concept_id, ConceptEdge.edge_type)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]
