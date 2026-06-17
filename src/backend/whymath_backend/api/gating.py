"""L6 응용 모드 게이팅 HTTP API — retake·suneung·school_progress·thinking 4모드를 HTTP로 노출.

엔드포인트(prefix `/v1/gating`):
  - GET /v1/gating/retake           — RT(재수전용/N수) 트랙 게이팅 결과(페르소나 B·C 대상).
  - GET /v1/gating/suneung          — 수능(정시) 모드 게이팅 결과(페르소나 A·B·C 대상).
  - GET /v1/gating/school-progress  — 학교진도 모드 게이팅 결과(페르소나 A·D 대상). 단원·성취기준
    고시코드 정합(OR·성취기준이 더 세밀). 성취기준 코드는 4단계 조인(problem_concept→concept→
    concept_standard_link→achievement_standard)으로 후보에 주입(school-progress 전용 의존성).
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

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
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


# ──────────────────────────────────────────────────────────────────────────
# 성취기준 조인 — school-progress 전용(다른 3모드는 조인 비용 안 얹음)
# ──────────────────────────────────────────────────────────────────────────
# 채택 link_type — '직접'만 본다. '재매핑'(개정 간 대응)·'준용'(교수학적 준용)은 연결이 느슨해
# 진도 정합 신호로는 노이즈라 MVP에서 제외한다(데이터가 차오르면 재검토할 상수 손잡이). 한글
# 정본 값('직접'/'재매핑'/'준용')은 schema.standard.ConceptStandardLink.link_type와 동일.
_DIRECT_LINK_TYPE = "직접"


async def _fetch_achievement_codes(
    session: AsyncSession, problem_ids: list[uuid.UUID]
) -> dict[uuid.UUID, set[str]]:
    """문항 id 목록 → {problem_id: {성취기준 official_code, ...}} (4단계 조인·N+1 없음).

    경로(모두 L1 영속 테이블): `problem_concept`(문항↔개념 N:M) → `concept`(개념) →
    `concept_standard_link`(개념↔성취기준 N:M·느슨참조 concept_code) → `achievement_standard`
    (성취기준). 조인 키: `ProblemConcept.concept_id == Concept.concept_id`,
    `ConceptStandardLink.concept_code == Concept.code`(FK 아님·느슨참조),
    `AchievementStandard.norm_id == ConceptStandardLink.norm_id`(실 FK). 매칭 축으로 꺼내는
    값은 `official_code`(고시코드 — 클라이언트 입력 형태, `unit_codes`가 "사람이 읽는 코드"인
    것과 정합)다.

    `me.py`의 `select(...).join(...).where(...in_(...))` 선례를 답습한 *단일 쿼리 IN 일괄*이라
    후보 수와 무관하게 쿼리 1회(N+1 0). INNER 조인이라 성취기준이 달린 (문항,개념) 행만 나오고,
    성취기준이 없는 문항은 결과 dict의 *키 자체가 없다*(주입 시 빈 리스트로 남음). `link_type`은
    `_DIRECT_LINK_TYPE`('직접')만 필터한다(모듈 상수 주석).

    Args:
      session: 요청 수명 AsyncSession.
      problem_ids: 성취기준을 조회할 문항 id 목록(후보 풀). 비면 빈 dict(쿼리 생략).

    Returns:
      `{problem_id: {official_code, ...}}` — 성취기준이 하나도 없는 문항은 키 부재.
    """
    if not problem_ids:
        return {}
    stmt = (
        select(ProblemConcept.problem_id, AchievementStandard.official_code)
        .join(Concept, ProblemConcept.concept_id == Concept.concept_id)
        .join(ConceptStandardLink, ConceptStandardLink.concept_code == Concept.code)
        .join(AchievementStandard, AchievementStandard.norm_id == ConceptStandardLink.norm_id)
        .where(ProblemConcept.problem_id.in_(problem_ids))
        .where(ConceptStandardLink.link_type == _DIRECT_LINK_TYPE)
    )
    result = await session.execute(stmt)
    mapping: dict[uuid.UUID, set[str]] = {}
    for problem_id, official_code in result.all():
        mapping.setdefault(problem_id, set()).add(official_code)
    return mapping


async def _fetch_candidates_with_standards(session: SessionDep) -> list[ProblemSchema]:
    """학교진도 후보를 읽고 *성취기준 코드*(비영속 필드)를 4단계 조인으로 주입해 돌려준다.

    `_fetch_candidates`(기존 후보 조회·재사용)로 후보를 끌어온 뒤, `_fetch_achievement_codes`로
    그 문항들의 성취기준 official_code를 일괄(IN) 조회해 각 `ProblemSchema`의 비영속 필드
    `achievement_standard_codes`에 *결정적으로*(sorted) 채운다. 성취기준이 없는 문항은 맵 키가
    없어 빈 리스트로 남는다(데이터0 안전·단원/persona_fit 폴백). school-progress 게이팅 핸들러
    전용 의존성이라 retake·suneung·thinking은 이 조인 비용을 지지 않는다(그들은 `CandidatesDep`
    유지).

    Args:
      session: 요청 수명 AsyncSession(`get_session` 주입).

    Returns:
      성취기준 코드가 주입된 후보 `schema.Problem` 리스트(게이팅 입력).
    """
    candidates = await _fetch_candidates(session)
    codes = await _fetch_achievement_codes(session, [p.problem_id for p in candidates])
    for problem in candidates:
        if problem.problem_id in codes:
            # sorted로 결정적 순서(집합→리스트). 키 부재 문항은 기본 빈 리스트 유지.
            problem.achievement_standard_codes = sorted(codes[problem.problem_id])
    return candidates


SchoolProgressCandidatesDep = Annotated[
    list[ProblemSchema], Depends(_fetch_candidates_with_standards)
]


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
    candidates: SchoolProgressCandidatesDep,
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
    target_achievement_codes: Annotated[
        list[str] | None,
        Query(
            alias="achievement_codes",
            description="현재 진도 성취기준 고시코드 반복지정 "
            "— `?achievement_codes=X&achievement_codes=Y`. "
            "단원과 더불어 성취기준 겹침으로 추가 정합(OR·더 세밀하면 우선)",
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

    후보를 L1에서 읽어(`_fetch_candidates_with_standards` — 후보 + 성취기준 코드 4단계 조인 주입)
    `select_school_progress_items`에 넘긴다 — 적격 필터(대상 페르소나·저작권 노출 게이트·교육과정
    버전 정합·진도 성취기준/단원 정합) → 우선순위(성취기준 겹침 개수>단원 겹침 개수>난이도) 내림차순
    안정정렬 → limit 적용까지 *전부 L6 게이팅이* 수행한 결과를 그대로 돌려준다.

    `unit_codes`(단원)·`achievement_codes`(성취기준 고시코드)를 반복 지정하면 그 집합과 *하나라도
    겹치는* 문항이 진도 정합으로 통과한다 — 둘은 **OR**로 결합되며(성취기준은 단원보다 세밀한 추가
    신호), 우선순위에서는 성취기준 겹침(×3.0)이 단원 겹침(×2.0)보다 앞선다. 둘 다 미지정이면
    `persona_fit` 폴백으로 판정한다(게이팅 계약). 각 리스트는 `set(...) or None`으로 변환해 넘긴다 —
    빈 리스트(쿼리 미지정)는 None과 같이 폴백/비신호로 취급하기 위함이다. 성취기준 코드는 비영속
    필드라 *문항 태깅·성취기준 코퍼스가 없으면* 빈 리스트로 주입돼 단원 신호로 자연 폴백한다
    (데이터0 안전). `curriculum_version`이 문항과 불일치면 게이팅이 차단한다(예: 2022 진도에 2015
    문항 미혼입). N수(B·C)·영재(E)는 비재학이라 게이팅이 비대상으로 거른다.
    """
    # 빈 리스트(쿼리 미지정·`?unit_codes=` 빈값)는 None과 동일하게 폴백/비신호를 타도록
    # `set(...) or None`으로 정규화한다(빈 set은 falsy → None). 게이팅은 둘 다 None이면 진도 정보
    # 부재로 보고 persona_fit으로 판정한다(school_progress.gating 계약).
    unit_code_set = set(target_unit_codes) if target_unit_codes else None
    achievement_code_set = set(target_achievement_codes) if target_achievement_codes else None
    return select_school_progress_items(
        candidates,
        persona,
        target_unit_codes=unit_code_set,
        target_achievement_codes=achievement_code_set,
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
