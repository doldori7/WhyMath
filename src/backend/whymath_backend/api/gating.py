"""L6 응용 모드 게이팅 HTTP API — retake·suneung·school_progress·thinking 4모드를 HTTP로 노출.

엔드포인트(prefix `/v1/gating`):
  - GET /v1/gating/retake           — RT(재수전용/N수) 트랙 게이팅 결과(페르소나 B·C 대상).
  - GET /v1/gating/suneung          — 수능(정시) 모드 게이팅 결과(페르소나 A·B·C 대상).
  - GET /v1/gating/school-progress  — 학교진도 모드 게이팅 결과(페르소나 A·D 대상).
  - GET /v1/gating/thinking         — 사고력 모드 게이팅 결과(Bloom 상위 3단계 주신호·D·E 주 대상).

레이어 경계(CLAUDE.md 7계층): 이 라우터는 **L5(상호작용·api)** 표면이다. L6 응용 모드
게이팅(`whymath_backend.l6`)을 *호출(소비)*해 HTTP로 노출할 뿐, 게이팅 로직을 *구현하지
않는다*(경계 침범 금지). 그리고 L6 게이팅 자신은 **L6→L1만** 의존한다 — 후보 문항은 L1
영속 레이어(`db.models.problem.Problem`)를 `get_session`으로 읽어 `to_schema()`로 L1
Pydantic(`schema.problem.Problem`)으로 복원한 뒤 게이팅에 넘긴다(L6은 L1 필드의 *존재·값*만
본다). 즉 흐름은 `HTTP → get_session(PG) → ORM Problem → to_schema() → L6 게이팅 →
list[ProblemSchema]`이며, api 레이어는 "DB 조회 + L6 함수 호출 + schema 반환" 조합만 한다.

**게이팅이 저작권·페르소나 진실 게이트**(CLAUDE.md 우선순위 #2 법적 ≫ #5 UX): 어떤 문항을
어떤 페르소나에게 노출해도 되는가의 판정 — 저작권 노출 가능성(`is_exposable`)·대상 페르소나·
진도/시험 정합 — 은 **전부 L6 게이팅이** 수행한다. 이 라우터의 SQL 조회는 *후보 축소*가
목적인 *최소* 조회이며(사전 필터 없이 단순 `select(Problem)` + fetch 상한), 게이팅이 모든
부적격 문항을 거른다. 특히 **평가원/EBS/교과서처럼 본문 미보유(구조 메타 전용) 출처는 학생
노출이 불가**하므로(저작권법 §32 단서·영리 금지) L6 저작권 게이트가 응답에서 원천 차단한다 —
이 라우터는 그 차단을 우회하지 않는다(테스트로 입증).

세션 결선·`SessionDep` 의존성 패턴은 problems.py와 동일(session.py 계약). 응답은 게이팅이
선별·우선순위 정렬·limit 적용을 마친 `list[ProblemSchema]`를 그대로 돌려준다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.problem import Problem
from whymath_backend.db.session import get_session
from whymath_backend.l6 import (
    select_retake_items,
    select_school_progress_items,
    select_suneung_items,
    select_thinking_items,
)
from whymath_backend.schema.enums import Curriculum, Persona
from whymath_backend.schema.problem import Problem as ProblemSchema

router = APIRouter(prefix="/v1/gating", tags=["gating"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 게이팅에 넘길 후보 문항 fetch 상한(합리적 상한) — 게이팅은 *메모리 안에서* 적격성·우선순위·
# limit을 적용하므로, DB에서는 후보를 *최소 사전 필터 없이* 한 번에 끌어와 게이팅이 모두 거르게
# 한다(게이팅이 진실 게이트라는 설계 규칙). 다만 무제한 조회는 비현실적이라 상한을 둔다 —
# 게이팅이 다시 limit으로 줄이므로 이 상한은 "게이팅에 먹일 후보 풀의 크기"일 뿐 응답 크기가
# 아니다. 응답 limit은 각 엔드포인트의 `limit` 쿼리 파라미터(기본 20·최대 200)가 정한다.
# (사전 필터를 두지 않는 이유: 저작권·페르소나·진도 정합 판정을 SQL로 흩지 않고 L6 한 곳에
# 모은다 — SQL 사전 필터가 없어도 게이팅이 부적격을 전부 차단해 *입증 가능한 단일 게이트*가 된다.)
_CANDIDATE_FETCH_LIMIT = 1000


async def _fetch_candidates(session: SessionDep) -> list[ProblemSchema]:
    """게이팅에 넘길 후보 문항을 L1 영속 레이어에서 읽어 L1 schema로 복원한다.

    `select(Problem)`(ORM)으로 후보를 fetch 상한(`_CANDIDATE_FETCH_LIMIT`)까지 끌어와, 각
    ORM 행을 `to_schema()`로 `schema.Problem`(Pydantic)으로 변환해 돌려준다. **사전 SQL 필터를
    두지 않는다** — 저작권/페르소나/진도 정합 판정은 전부 L6 게이팅 소관이며(라우터 docstring),
    이 함수는 후보를 *축소만*(상한) 한다. `to_schema()`는 본문 미보유 불변식을 다시 통과시키므로
    (problem.py `to_schema` 계약) 게이팅에는 항상 검증된 L1 모델만 들어간다.

    안정적 결과를 위해 `created_at desc, problem_id`로 정렬한다(problems.py 목록과 동일 보조키 —
    동일 created_at에서도 결정적 순서). 게이팅이 다시 우선순위로 재정렬하지만, fetch 상한에 걸릴
    때 *어떤* 후보가 잘리는지를 결정적으로 만들기 위함이다.

    Args:
      session: 요청 수명 AsyncSession(`get_session` 주입).

    Returns:
      후보 문항의 `schema.Problem` 리스트(최대 `_CANDIDATE_FETCH_LIMIT`개·게이팅 입력).
    """
    stmt = (
        select(Problem)
        .order_by(Problem.created_at.desc(), Problem.problem_id)
        .limit(_CANDIDATE_FETCH_LIMIT)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


CandidatesDep = Annotated[list[ProblemSchema], Depends(_fetch_candidates)]


@router.get(
    "/retake",
    response_model=list[ProblemSchema],
    summary="RT(재수전용) 트랙 게이팅",
)
async def gating_retake(
    candidates: CandidatesDep,
    persona: Annotated[Persona, Query(description="노출 대상 페르소나(필수). RT는 B·C 대상")],
    min_fit: Annotated[float, Query(description="persona_fit 임계값(0~1)")] = 0.5,
    limit: Annotated[int, Query(ge=1, le=200, description="응답 최대 개수")] = 20,
) -> list[ProblemSchema]:
    """RT(재수전용/N수) 트랙 노출 문항을 게이팅해 반환한다(페르소나 B·C 대상).

    후보를 L1에서 읽어(`_fetch_candidates`) `select_retake_items`에 넘긴다 — 적격 필터(대상
    페르소나·저작권 노출 게이트·RT 적합 신호) → 우선순위 내림차순 안정정렬 → limit 적용까지
    *전부 L6 게이팅이* 수행한 결과를 그대로 돌려준다. 비대상 페르소나(A·D·E)는 게이팅이 전부
    걸러 빈 리스트가 된다. 평가원/EBS/교과서(본문 미보유) 출처는 저작권 게이트가 차단한다.
    """
    return select_retake_items(candidates, persona, min_fit=min_fit, limit=limit)


@router.get(
    "/suneung",
    response_model=list[ProblemSchema],
    summary="수능(정시) 모드 게이팅",
)
async def gating_suneung(
    candidates: CandidatesDep,
    persona: Annotated[
        Persona, Query(description="노출 대상 페르소나. 수능은 A·B·C 대상")
    ] = Persona.A_일반고고3,
    min_fit: Annotated[float, Query(description="persona_fit 임계값(0~1)")] = 0.5,
    limit: Annotated[int, Query(ge=1, le=200, description="응답 최대 개수")] = 20,
) -> list[ProblemSchema]:
    """수능(정시) 모드 노출 문항을 게이팅해 반환한다(페르소나 A·B·C 대상).

    후보를 L1에서 읽어 `select_suneung_items`에 넘긴다 — 적격 필터(대상 페르소나·저작권 노출
    게이트·수능 적합 신호) → 우선순위(출처 권위>시그니처>난이도) 내림차순 안정정렬 → limit
    적용까지 *전부 L6 게이팅이* 수행한 결과를 그대로 돌려준다. **수능 모드 특히 중요**: 평가원
    기출 *본문*은 절대 노출 불가 → 저작권 게이트가 원천 차단하고, 학생에겐 자체생성 동등문제만
    노출된다(CLAUDE.md 우선순위 #2 법적). D(수시·학종)·E(영재)는 게이팅이 비대상으로 거른다.
    """
    return select_suneung_items(candidates, persona, min_fit=min_fit, limit=limit)


@router.get(
    "/school-progress",
    response_model=list[ProblemSchema],
    summary="학교진도 모드 게이팅",
)
async def gating_school_progress(
    candidates: CandidatesDep,
    persona: Annotated[
        Persona, Query(description="노출 대상 페르소나. 학교진도는 A·D 대상")
    ] = Persona.A_일반고고3,
    target_unit_codes: Annotated[
        list[str] | None,
        Query(
            alias="unit_codes",
            description="현재 진도 단원 코드(반복 지정 가능 — `?unit_codes=X&unit_codes=Y`). "
            "주어지면 단원 겹침으로 진도 정합 판정",
        ),
    ] = None,
    curriculum_version: Annotated[
        Curriculum | None, Query(description="교육과정 버전 정합 기준(선택)")
    ] = None,
    min_fit: Annotated[
        float, Query(description="persona_fit 임계값(0~1·진도 미지정 시 폴백)")
    ] = 0.5,
    limit: Annotated[int, Query(ge=1, le=200, description="응답 최대 개수")] = 20,
) -> list[ProblemSchema]:
    """학교진도 모드 노출 문항을 게이팅해 반환한다(페르소나 A·D 대상).

    후보를 L1에서 읽어 `select_school_progress_items`에 넘긴다 — 적격 필터(대상 페르소나·저작권
    노출 게이트·교육과정 버전 정합·진도 단원 정합) → 우선순위(진도 단원 겹침 개수>난이도) 내림차순
    안정정렬 → limit 적용까지 *전부 L6 게이팅이* 수행한 결과를 그대로 돌려준다.

    `unit_codes` 쿼리를 반복 지정하면(예: `?unit_codes=X&unit_codes=Y`) 그 코드 집합과 *하나라도
    겹치는* 문항만 진도 정합으로 통과하고, 미지정이면 `persona_fit` 폴백으로 판정한다(게이팅 계약).
    리스트는 `set(...) or None`으로 변환해 넘긴다 — 빈 리스트(쿼리 미지정)는 None과 같이 폴백을
    타게 하기 위함이다. `curriculum_version`이 문항과 불일치면 게이팅이 차단한다(예: 2022 진도에
    2015 문항 미혼입). N수(B·C)·영재(E)는 비재학이라 게이팅이 비대상으로 거른다.
    """
    # 빈 리스트(쿼리 미지정·`?unit_codes=` 빈값)는 None과 동일하게 polya-fit 폴백을 타도록
    # `set(...) or None`으로 정규화한다(빈 set은 falsy → None). 게이팅은 None이면 진도 단원
    # 정보 부재로 보고 persona_fit으로 판정한다(school_progress.gating 계약).
    unit_code_set = set(target_unit_codes) if target_unit_codes else None
    return select_school_progress_items(
        candidates,
        persona,
        target_unit_codes=unit_code_set,
        curriculum_version=curriculum_version,
        min_fit=min_fit,
        limit=limit,
    )


@router.get(
    "/thinking",
    response_model=list[ProblemSchema],
    summary="사고력 모드 게이팅",
)
async def gating_thinking(
    candidates: CandidatesDep,
    persona: Annotated[
        Persona, Query(description="노출 대상 페르소나. 사고력 주 대상 D·E(닫힌 집합 게이트 없음)")
    ] = Persona.D_학종고2,
    min_fit: Annotated[float, Query(description="persona_fit 임계값(0~1)")] = 0.5,
    limit: Annotated[int, Query(ge=1, le=200, description="응답 최대 개수")] = 20,
) -> list[ProblemSchema]:
    """사고력 모드 노출 문항을 게이팅해 반환한다(Bloom 상위 3단계가 주신호·D·E 주 대상).

    후보를 L1에서 읽어(`_fetch_candidates`) `select_thinking_items`에 넘긴다 — 적격 필터(저작권
    노출 게이트·페르소나 적합도·사고력 주신호) → 우선순위(Bloom 상위 단계>사고력 시그니처 개수>
    케이스/융합/종합 난이도) 내림차순 안정정렬 → limit 적용까지 *전부 L6 게이팅이* 수행한 결과를
    그대로 돌려준다.

    **사고력 주신호는 `bloom_level`**(상위 3단계 ANALYZE/EVALUATE/CREATE) — 사고력 미표지
    (bloom None)·하위 인지 수준(APPLY 이하) 문항은 게이팅이 전부 거른다. **닫힌 페르소나 집합으로
    좁히지 않는다**: 주 대상은 D(학종)·E(영재)이나 A(MVP 고3)도 `persona_fit`이 임계 이상이면
    노출된다(MVP 페르소나 배제 금지·persona_fit 메커니즘만 사용). 평가원/EBS/교과서(본문 미보유)
    출처는 저작권 게이트가 차단하고, 학생에겐 자체생성 동등문제만 노출된다(CLAUDE.md 우선순위 #2).
    """
    return select_thinking_items(candidates, persona, min_fit=min_fit, limit=limit)
