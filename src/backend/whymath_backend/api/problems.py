"""문제(problem) 도메인 HTTP API — concept 라우터와 동형의 DB-backed CRUD-read.

엔드포인트(prefix `/v1/problems`):
  - POST   /v1/problems          — 문제 생성(검증된 schema.Problem → ORM → commit). 201.
  - GET    /v1/problems/{id}     — 단건 조회(UUID). 없으면 404.
  - GET    /v1/problems          — 목록(최신순, limit/offset, subject 선택 필터).

세션 결선·트랜잭션 책임·Annotated 의존성 패턴은 concepts.py와 동일(session.py 계약).
`external_id`/`slug`는 UNIQUE라 중복 시 IntegrityError→409.

경계 메모(CLAUDE.md 절대 금기): 본문 보유 금지 불변식(평가원·EBS·교과서 출처는 question_text
미저장·license=WHYMATH_GENERATED 강제 등)은 *schema.Problem after-validator*가 이미 강제한다
— 이 라우터는 검증 통과한 모델만 영속화한다. 학생 표면화 전 LLM 생성물은 L3/app.py 소관.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._concurrency import (
    ensure_if_match,
    etag_for,
    matches_if_none_match,
)
from whymath_backend.db.models.problem import Problem, ProblemRelation, ProblemStep
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Subject
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.problem import ProblemRelation as ProblemRelationSchema
from whymath_backend.schema.problem import ProblemStep as ProblemStepSchema

router = APIRouter(prefix="/v1/problems", tags=["problem"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProblemSchema,
    summary="문제 생성",
)
async def create_problem(
    body: ProblemSchema, session: SessionDep, response: Response
) -> ProblemSchema:
    """검증된 schema.Problem을 영속화하고 복원해 반환한다(201).

    `external_id`/`slug`는 UNIQUE이므로 중복이면 PG가 IntegrityError → 롤백 후 **409**.
    본문 보유 금지 등 출처별 불변식은 schema.Problem이 이미 검증했다(경계 메모 참조).
    응답에 ETag를 실어 이후 조건부 수정(If-Match)을 가능케 한다.
    """
    orm = Problem.from_schema(body)
    session.add(orm)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 external_id 또는 slug입니다.",
        ) from exc
    await session.refresh(orm)
    result = orm.to_schema()
    response.headers["ETag"] = etag_for(result)
    return result


@router.get("/{problem_id}", response_model=ProblemSchema, summary="문제 단건 조회")
async def read_problem(
    problem_id: uuid.UUID,
    session: SessionDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> ProblemSchema | Response:
    """UUID로 문제 단건 조회 — 없으면 404.

    ETag를 싣고, `If-None-Match`가 현재 ETag와 일치하면 **304 Not Modified**(빈 본문)로
    응답해 모바일 대역폭을 아낀다.
    """
    orm = await session.get(Problem, problem_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    result = orm.to_schema()
    etag = etag_for(result)
    if matches_if_none_match(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return result


@router.get("", response_model=list[ProblemSchema], summary="문제 목록")
async def list_problems(
    session: SessionDep,
    subject: Annotated[Subject | None, Query(description="과목 필터(선택)")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="페이지 크기")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 행 수")] = 0,
) -> list[ProblemSchema]:
    """문제 목록 — 최신순(created_at desc, problem_id로 안정 정렬), limit/offset.

    `subject`를 주면 해당 과목만 필터한다. 정렬 보조키로 problem_id(UNIQUE)를 둬 동일
    created_at에서도 페이지네이션이 안정적이다.
    """
    stmt = select(Problem)
    if subject is not None:
        stmt = stmt.where(Problem.subject == subject)
    stmt = stmt.order_by(Problem.created_at.desc(), Problem.problem_id).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.get(
    "/{problem_id}/steps",
    response_model=list[ProblemStepSchema],
    summary="문제 풀이 단계 목록",
)
async def list_problem_steps(problem_id: uuid.UUID, session: SessionDep) -> list[ProblemStepSchema]:
    """문제의 풀이 단계(Polya·Socratic) 목록 — step_order 순. 문제 없으면 404.

    하위 리소스 read 전용(단계 생성/수정은 범위 밖). 부모 부재를 빈 목록과 구분하기 위해
    먼저 문제 존재를 확인한다.
    """
    if await session.get(Problem, problem_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    stmt = (
        select(ProblemStep)
        .where(ProblemStep.problem_id == problem_id)
        .order_by(ProblemStep.step_order)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.get(
    "/{problem_id}/relations",
    response_model=list[ProblemRelationSchema],
    summary="문항 간 관계 목록",
)
async def list_problem_relations(
    problem_id: uuid.UUID, session: SessionDep
) -> list[ProblemRelationSchema]:
    """이 문제가 출발점인(outgoing) 문항 관계 목록 — 문제 없으면 404.

    `parent_problem_id == path`인 관계만(나가는 방향). 역방향·양방향은 후속.
    """
    if await session.get(Problem, problem_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    stmt = (
        select(ProblemRelation)
        .where(ProblemRelation.parent_problem_id == problem_id)
        .order_by(ProblemRelation.related_problem_id, ProblemRelation.relation_type)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.patch("/{problem_id}", response_model=ProblemSchema, summary="문제 부분 수정")
async def patch_problem(
    problem_id: uuid.UUID,
    body: dict[str, Any],
    session: SessionDep,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ProblemSchema:
    """제공된 필드만 부분 수정 — 병합 결과를 schema로 *재검증*해 불변식(본문 보유 금지 등)을
    유지한다. `problem_id`(PK)는 경로 고정. 없으면 404, 병합 결과 스키마 위반 422,
    `external_id`/`slug` UNIQUE 충돌 409. **낙관적 동시성**: `If-Match`(GET ETag)를 보내면
    그사이 변경됐을 때 412로 거부한다(미전송 시 무조건 진행 — 비파괴). 응답에 새 ETag를 싣는다.
    """
    existing = await session.get(Problem, problem_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    ensure_if_match(if_match, etag_for(existing.to_schema()))
    merged = existing.to_schema().model_dump()
    merged.update(body)
    merged["problem_id"] = problem_id  # PK는 경로 고정
    try:
        validated = ProblemSchema.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "수정 본문 병합 결과가 스키마를 위반합니다(본문 보유 금지 등).",
                "errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()],
            },
        ) from exc
    updated = await session.merge(Problem.from_schema(validated))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 external_id 또는 slug입니다.",
        ) from exc
    result = updated.to_schema()
    response.headers["ETag"] = etag_for(result)
    return result


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT, summary="문제 삭제")
async def delete_problem(
    problem_id: uuid.UUID,
    session: SessionDep,
    if_match: Annotated[str | None, Header()] = None,
) -> Response:
    """문제 삭제 — 없으면 404. 풀이단계·관계·시도 등 참조가 있으면 FK 위반 → 409.

    cascade를 ORM에 두지 않았으므로 참조가 있으면 삭제를 거부한다(가짜 cascade 금지).
    `If-Match`를 보내면 그사이 변경된 리소스의 삭제를 412로 막는다(조건부 삭제).
    """
    existing = await session.get(Problem, problem_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    ensure_if_match(if_match, etag_for(existing.to_schema()))
    await session.delete(existing)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 문제를 참조하는 단계·관계·시도가 있어 삭제할 수 없습니다.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
