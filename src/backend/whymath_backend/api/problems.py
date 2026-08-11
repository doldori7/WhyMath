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

인가(SEC-07 D1): POST/PATCH/DELETE 3개는 `RequireContentAdmin`(`Role.CONTENT_ADMIN`)로
게이팅한다 — 이전엔 인증 의존성이 0건이라 누구나 문제를 생성·수정·삭제할 수 있었다(실측
`docs/architecture/account_security_gap_review.md` D1). GET(단건·목록·steps·relations)은
*무인증 유지*(공개 카탈로그·현 클라·데모 경로 파괴 금지 — 봉인 범위 과확대 방지).

**PB-08 — 공개 카탈로그 노출 계약(무엇이 보이는가)**: PB-08 이전 이 라우터의 GET 4개는
노출 계약을 *전혀* 경유하지 않아, 무인증으로 `review_status=pending` 문항(실측 158건 —
killer_v0 120·probability_finite_v0 34·v1 4)과 정답이 그대로 나갔다(방어가 클라이언트
단독이었다 — `src/mobile/.../problem_models.dart`가 정답 필드를 선언하지 않을 뿐). 이제
GET 4개 전부가 아래 두 축을 경유한다:

  - 축① 저작권 — `l6._shared.is_exposable`(본문 미보유 출처 평가원/EBS/교과서 차단)
  - 축② 검수   — `l6._shared.is_review_cleared`(`review_status == approved`만 통과)

두 축은 **절대 하나로 합치지 않는다**(`l6/_shared.py` docstring — 법적 축과 운영 축이 독립).
목록은 SQL where(`METADATA_ONLY_SOURCES` + `ReviewStatus.approved`)로 1차 축소하고, 행 단위
`_public_catalog_row`가 같은 두 축을 fail-closed로 재확인한다 — SQL where가 회귀로 사라져도
무증상 통과하지 않게 하는 2차 확인이며, *같은 l6 계약 함수*를 부르므로 판정 기준 이원화가
아니다(`api/me.py`의 기본 CAT SQL과 동일한 상수·enum 재사용).

*무인증 자체는 이 태스크가 건드리지 않는다* — 바뀌는 것은 "누가 보는가"가 아니라 "무엇이
보이는가"뿐이다.

**집행 지점 열거(계약과 별항 — PED-06형 "정본화≠집행" 재발 방지)**: `is_exposable`/
`is_review_cleared`(또는 그 SQL 등가물)를 경유하는 *서빙* 경로 전수와, PB-08이 닫는 경로·
남는 경로는 다음과 같다.

  [PB-03이 이미 배선한 경로 — 그대로 유지]
    1. `GET  /v1/gating/retake`           → `l6.retake.gating.is_retake_eligible`
    2. `GET  /v1/gating/suneung`          → `l6.suneung.gating.is_suneung_eligible`
    3. `GET  /v1/gating/school-progress`  → `l6.school_progress.gating`
    4. `GET  /v1/gating/thinking`         → `l6.thinking.gating`
    5. `GET  /v1/gating/metacognition`    → `l6.metacognition.gating`
    6. `GET  /v1/gating/gifted`           → `l6.gifted.gating`
    7. `POST /v1/me/assessments/assemble` → `l6.blueprint.assembly.is_blueprint_eligible`
    8. `GET  /v1/me/next-problem`(기본 CAT) → `api/me.py` 후보 SQL 두 축(축①+축②)
    9. `GET  /v1/me/next-problem?mode=suneung` → 후보 SQL은 축①만(성능 사전축소),
       최종 판정은 `is_suneung_eligible`이 두 축 재수행(진실 게이트)

  [PB-08이 닫는 경로 — 이 파일]
   10. `GET /v1/problems/{id}`            → `_load_public_problem`(두 축 + 정답 리댁션)
   11. `GET /v1/problems`                 → SQL where 두 축 + `_public_catalog_row` 재확인
   12. `GET /v1/problems/{id}/steps`      → 부모 문항이 부적격이면 함께 404
   13. `GET /v1/problems/{id}/relations`  → 부모 문항이 부적격이면 함께 404

  [남는 경로 — PB-08 범위 밖, 후속 후보]
    A. `GET /v1/gating/*` 6종은 노출 2축은 통과하지만 응답 모델이 `ProblemSchema` 원형이라
       **정답 4필드를 무인증으로 그대로 반환**한다(2026-08-11 실측: `api/gating.py`에 인증
       참조 0건). PB-08의 리댁션은 `/v1/problems`에만 적용했다(범위 한정) — 같은 리댁션의
       gating 확대는 **`PB-12-gating-answer-redaction`**(등재 완료·priority 1)이 닫는다.
       산문으로 "별도 태스크가 필요하다"고만 적으면 추적되지 않으므로 태스크 id를 박아 둔다
       (CLAUDE.md "docstring 속 계획은 백로그를 대신하지 못한다").
    B. `api/coach.py::_expected_answer_for`는 `problem.answer`를 읽지만 shadow 로그 sink
       전용이고 HTTP 응답에 싣지 않는다(그 docstring이 계약) — 노출 경로 아님.
    C. `whs/self_evolution.py`는 저작권 축만 본다(검수 축 없음) — 하네스(비서빙).
    D. 이 파일의 POST/PATCH/DELETE는 `RequireContentAdmin` write 경로라 *의도적으로* 계약
       밖이다(관리자는 pending 문항과 정답을 봐야 검수·수정할 수 있다).
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import RequireContentAdmin
from whymath_backend.api._concurrency import (
    ensure_if_match,
    etag_for,
    matches_if_none_match,
)
from whymath_backend.db.models.problem import Problem, ProblemRelation, ProblemStep
from whymath_backend.db.session import get_session

# 노출 계약 정본은 L6 공용 모듈(`l6/_shared.py`)이다 — api(L5 표면)는 상위 계층이라 L6을
# import해도 7계층 단방향(L_n→L_{n-1})을 어기지 않는다(import-linter `layers` 계약에서
# api가 최상단). `api/me.py`가 `METADATA_ONLY_SOURCES`를 L6에서 그대로 끌어다 쓰는 선례와
# 동일 원칙 — 여기서는 재노출 경로(`l6.suneung`)가 아니라 정본 모듈을 직접 가리켜
# "판정 기준이 둘로 갈리는" 여지를 없앤다(같은 객체다).
from whymath_backend.l6._shared import (
    METADATA_ONLY_SOURCES,
    is_exposable,
    is_review_cleared,
)
from whymath_backend.schema.enums import ReviewStatus, Subject
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.problem import ProblemRelation as ProblemRelationSchema
from whymath_backend.schema.problem import ProblemStep as ProblemStepSchema

router = APIRouter(prefix="/v1/problems", tags=["problem"])

_logger = logging.getLogger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# ──────────────────────────────────────────────────────────────────────────
# PB-08 — 공개 카탈로그 노출 계약(모듈 docstring "집행 지점 열거" 참조)
# ──────────────────────────────────────────────────────────────────────────

_REDACTED_ANSWER_FIELDS: tuple[str, ...] = (
    "answer",  # 정답 원문
    "answer_explanation",  # 공식 해설(정답 포함)
    "multiple_answers",  # 복수해 — 정답 집합 그 자체
    "distractor_map",  # *오답 선지만* 매핑 → 소거법으로 정답이 드러난다
)
"""무인증 공개 카탈로그 GET 응답에서 서버가 비우는(None) 정답 축 필드.

**왜 클라이언트가 아니라 서버가 None으로 비우는가**(결정 — PB-08): 이 GET은 무인증이라
*막힌 학생을 포함해 누구나* 정답을 끌어갈 수 있다. CLAUDE.md 의사결정 우선순위 #1(학생
안전·웰빙)과 절대 금기 "학생이 막혔을 때 바로 정답 제공 금지"는 교수학 이전에 노출 계약의
문제이며, 클라이언트 모델이 필드를 선언하지 않는 방식의 방어는 *계약이 아니라 소비자 구현*이라
소비자(웹·PDF·AI·서드파티)가 늘 때마다 재발한다. 그래서 표면이 아니라 서버에서 비운다.

후속 후보(범위 밖): 지금은 `ProblemSchema`를 재사용해 필드를 None으로 덮는다 — 응답 스키마에
필드가 *존재하되 항상 null*이다. 전용 public 스키마(필드 자체가 없는 모델)로 분리하면 OpenAPI
문서에서도 정답 축이 사라지지만, 응답 모델 교체는 클라 계약 변경이라 별도 태스크로 남긴다.

관리자 write 경로(POST/PATCH — `RequireContentAdmin`)는 리댁션 대상이 **아니다**(검수·수정을
하려면 정답을 봐야 한다).
"""


def _public_exposure_block_reason(problem: ProblemSchema) -> str | None:
    """공개 카탈로그 노출을 막아야 하는 사유 — `None`이면 노출 적격.

    두 축을 **각각 독립된 `if`로** 확인한다(`l6/_shared.py` docstring: 저작권 축과 검수 축은
    절대 합치지 않는다). 사유 문자열은 서버 로그용이며 HTTP 응답에는 싣지 않는다 — 존재 여부를
    흘리지 않으려고 부적격은 403이 아니라 404로 응답하기 때문이다(무인증 의미론 유지).

    Args:
      problem: 판정할 문항(L1 `Problem` 스키마).

    Returns:
      차단 사유(로그용 한국어 문자열) 또는 `None`(노출 적격).
    """
    # 축① 저작권(법적·협상 불가) — 본문 미보유 출처(평가원/EBS/교과서).
    if not is_exposable(problem):
        return "저작권(본문 미보유 출처)"
    # 축② 검수(운영) — 축①과 독립. `None`·`pending`·`rejected` 전부 fail-closed.
    if not is_review_cleared(problem):
        return "검수 미통과(review_status != approved)"
    return None


def _redact_answers(problem: ProblemSchema) -> ProblemSchema:
    """정답 축 4필드를 None으로 덮은 공개 표현을 만든다(원본 불변 — `model_copy`).

    `model_copy(update=...)`는 재검증을 하지 않지만 여기서는 안전하다 — 네 필드 모두 Optional
    이고 `None`은 어느 출처에서든 유효한 값이다(오히려 메타데이터 전용 출처는 None이 강제된다).
    """
    return problem.model_copy(update=dict.fromkeys(_REDACTED_ANSWER_FIELDS, None))


def _public_catalog_row(orm: Problem) -> ProblemSchema | None:
    """ORM 행 → 공개 카탈로그 표현. 노출 부적격이면 `None`(호출부가 404 또는 목록 제외).

    목록 경로의 SQL where가 이미 같은 두 축을 걸지만, 여기서 **fail-closed로 한 번 더** 확인한다
    — where 절이 회귀로 사라져도 무증상 통과하지 않게 하는 2차 확인이며, 같은 l6 계약 함수를
    부르므로 판정 기준 이원화가 아니다.
    """
    schema = orm.to_schema()
    reason = _public_exposure_block_reason(schema)
    if reason is not None:
        # 침묵 실패 금지 — 차단은 정상 정책 동작이므로 debug 레벨이되, 사유·문항 id를 남긴다.
        _logger.debug("공개 카탈로그 노출 차단: problem_id=%s reason=%s", schema.problem_id, reason)
        return None
    return _redact_answers(schema)


async def _load_public_problem(session: AsyncSession, problem_id: uuid.UUID) -> ProblemSchema:
    """공개 카탈로그 노출 적격 문항을 읽어 *리댁션된* 표현으로 돌려준다.

    부재와 부적격을 **같은 404**로 응답한다 — 부적격을 403으로 구분하면 "그 id의 문항이
    존재한다"는 사실이 무인증 호출자에게 새어 나간다(pending 문항의 존재 자체가 신호).
    """
    orm = await session.get(Problem, problem_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    public = _public_catalog_row(orm)
    if public is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문제를 찾을 수 없습니다: {problem_id}",
        )
    return public


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProblemSchema,
    summary="문제 생성",
)
async def create_problem(
    body: ProblemSchema, session: SessionDep, response: Response, admin: RequireContentAdmin
) -> ProblemSchema:
    """검증된 schema.Problem을 영속화하고 복원해 반환한다(201). `Role.CONTENT_ADMIN` 전용.

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

    PB-08: 노출 계약 두 축(`is_exposable` 저작권 · `is_review_cleared` 검수)을 각각 독립된
    `if`로 통과해야 하며(`_public_exposure_block_reason`), 미통과면 존재를 흘리지 않기 위해
    부재와 같은 **404**로 응답한다. 통과한 응답도 정답 축 4필드는 서버가 비운다
    (`_REDACTED_ANSWER_FIELDS`).

    ETag를 싣고, `If-None-Match`가 현재 ETag와 일치하면 **304 Not Modified**(빈 본문)로
    응답해 모바일 대역폭을 아낀다. ETag는 *실제로 서빙되는 공개 표현*의 해시다(RFC 7232 —
    표현별 ETag). 따라서 정답을 가진 행에서는 공개 GET의 ETag와 관리자 write 경로(POST/PATCH
    응답)의 ETag가 갈린다 — 관리자가 `If-Match`에 쓸 토큰은 write 응답의 ETag다.
    """
    result = await _load_public_problem(session, problem_id)
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

    PB-08: 노출 계약 두 축을 **SQL where로 1차 축소**한 뒤(`api/me.py` 기본 CAT 후보 SQL과
    동일한 상수·enum 재사용 — 판정 기준 이원화 방지), 행 단위로 `_public_catalog_row`가 같은
    두 축을 fail-closed로 재확인하고 정답 축 4필드를 비운다.

    한계(정직 표기): `limit`/`offset`은 SQL 축소 *뒤* 적용되므로 페이지 크기는 SQL 두 축을
    기준으로 정확하다. 2차 재확인이 행을 더 걸러내면 그 페이지만 짧아진다 — 재확인이 걸러야 할
    행이 있다는 것 자체가 SQL where 회귀 신호이므로, 짧아진 페이지는 은폐가 아니라 증상이다.
    """
    stmt = select(Problem).where(
        # PB-08 축① — 저작권 노출 게이트(법적·협상 불가). 본문 미보유 출처(평가원/EBS/교과서)
        # 배제. `api/me.py`가 쓰는 것과 *같은 상수*를 재사용한다.
        Problem.source_type.notin_([s.value for s in METADATA_ONLY_SOURCES]),
        # PB-08 축② — 검수 노출 게이트(운영 축, 축①과 독립 — 절대 합치지 않는다).
        # `None`(미평가)·`pending`·`rejected`는 SQL 비교에서 자연히 탈락(fail-closed).
        Problem.review_status == ReviewStatus.approved,
    )
    if subject is not None:
        stmt = stmt.where(Problem.subject == subject)
    stmt = stmt.order_by(Problem.created_at.desc(), Problem.problem_id).limit(limit).offset(offset)
    result = await session.execute(stmt)
    rows = [_public_catalog_row(row) for row in result.scalars().all()]
    return [row for row in rows if row is not None]


@router.get(
    "/{problem_id}/steps",
    response_model=list[ProblemStepSchema],
    summary="문제 풀이 단계 목록",
)
async def list_problem_steps(problem_id: uuid.UUID, session: SessionDep) -> list[ProblemStepSchema]:
    """문제의 풀이 단계(Polya·Socratic) 목록 — step_order 순. 문제 없으면 404.

    하위 리소스 read 전용(단계 생성/수정은 범위 밖). 부모 부재를 빈 목록과 구분하기 위해
    먼저 문제 존재를 확인한다.

    PB-08: 부모 문항이 노출 부적격이면(저작권·검수 두 축) 이 하위 리소스도 **함께 404**다.
    풀이 단계는 정답보다 민감하다 — 단계별 유도가 곧 해답 경로이기 때문이다. 부모 판정 결과는
    버리고 접근 가부로만 쓴다(`_load_public_problem`).
    """
    await _load_public_problem(session, problem_id)
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

    PB-08: `/steps`와 동일하게 부모 문항이 노출 부적격이면 함께 404다(관계 그래프는 미노출
    문항의 존재·연결을 드러낸다).

    한계(정직 표기): *관계로 가리켜지는* `related_problem_id` 쪽 문항의 노출 적격성은 확인하지
    않는다 — 이 응답은 id 참조만 담고 본문·정답을 담지 않으며, 그 id를 실제로 열람하려면 단건
    GET을 거쳐야 하고 거기서 계약이 다시 걸린다.
    """
    await _load_public_problem(session, problem_id)
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
    admin: RequireContentAdmin,
    if_match: Annotated[str | None, Header()] = None,
) -> ProblemSchema:
    """제공된 필드만 부분 수정 — 병합 결과를 schema로 *재검증*해 불변식(본문 보유 금지 등)을
    유지한다. `Role.CONTENT_ADMIN` 전용. `problem_id`(PK)는 경로 고정. 없으면 404, 병합 결과
    스키마 위반 422, `external_id`/`slug` UNIQUE 충돌 409. **낙관적 동시성**: `If-Match`(GET
    ETag)를 보내면 그사이 변경됐을 때 412로 거부한다(미전송 시 무조건 진행 — 비파괴). 응답에
    새 ETag를 싣는다.
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
    admin: RequireContentAdmin,
    if_match: Annotated[str | None, Header()] = None,
) -> Response:
    """문제 삭제 — 없으면 404. 풀이단계·관계·시도 등 참조가 있으면 FK 위반 → 409.
    `Role.CONTENT_ADMIN` 전용.

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
