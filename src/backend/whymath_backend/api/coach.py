"""L4 교수학 코치 HTTP 표면 — `POST /v1/coach` + `POST /v1/coach/sessions`.

학생 발화·Polya 상태(+옵션 숙달도)를 받아 *통합 결정*을 반환한다. L4 슬라이스 1-5의 모든
결정 함수를 한 발화로 묶는 엔드포인트:
- `PolyaCoach.decide()` — 단계 전이·prompt 조립·socratic_category·hint_level·reveals
- `diagnose()` — 오개념 후보 top-K
- `select_intervention()` — top-1 신뢰도 0.5+ 시 개입 결정
- `adapt_lthc()` — 숙달도 제공 시 진입점·확장·비계 조정

**경계**:
- `/v1/coach` — *stateless* (state in/out·DB 무접근·LLM 호출 0).
- `/v1/coach/sessions` — *DB 쓰기*(새 dialogue + 학생/AI 2턴 영속). LLM 호출은 여전히 0
  (decision.prompt를 AI 턴 content로 저장 — 결정된 발화 보존).
- 인증 = `ConsentedUser`(미성년 동의 게이트 통과) — 학생 발화는 PII 가능(CLAUDE.md).
- 응답에 `system`/`prompt` 본문이 노출되므로 *학생 발화를 그대로 에코하지 않음*(에코 시
  필터·검증 없이 표면화될 위험).
- 미성년 채팅 평문 저장(CLAUDE.md 금기)은 *저장 계층 책임*(DB 암호화 at-rest·미들웨어).
  본 라우터는 schema/ORM의 기존 방침을 따라 평문 저장 + docstring 상기만(슬라이스 1
  schema 노트와 동일 — `schema/dialogue.py` 모듈 docstring 참조).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, NamedTuple

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._concurrency import etag_for, matches_if_none_match
from whymath_backend.api._misconception_state import get_semantic_matcher
from whymath_backend.api._rate_limit import (
    RateLimitedTripleRead,
    RateLimitedTripleWrite,
)
from whymath_backend.config import get_settings
from whymath_backend.db.models.activity import AttemptEvent as AttemptEventORM
from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
from whymath_backend.db.models.dialogue import DialogueTurn as DialogueTurnORM
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.db.session import get_session
from whymath_backend.l2 import (
    AbilityReading,
    get_current_ability,
    get_current_mastery,
    get_current_theta,
    get_primary_concept_id,
    theta_to_mastery_proxy,
)
from whymath_backend.l2.prerequisite_recommendation import recommend_prerequisite_gaps
from whymath_backend.l3.pregenerate.validator import (
    arithmetic_validator,
    validate_response,
)
from whymath_backend.l4 import (
    CoachingFocus,
    CoachingTrigger,
    LthcAdaptation,
    MasteryLevel,
    PedagogyDecision,
    PolyaCoach,
    PolyaState,
    SolutionCoaching,
    adapt_lthc,
    focus_to_socratic_category,
    mastery_to_level,
    recommend_coaching_for_solution,
)
from whymath_backend.l4.misconception import (
    InterventionDecision,
    MisconceptionMatch,
    combine_diagnoses,
    diagnose,
    select_intervention,
)
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.match_gate import apply_match_quality_gate
from whymath_backend.l4.misconception.shadow import observe_misconception_shadow
from whymath_backend.l4.prerequisite_coaching import recommend_prerequisite_coaching
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.dialogue import DialogueTurn as DialogueTurnSchema
from whymath_backend.schema.enums import ContentType, EventType, StepType, TurnRole

router = APIRouter(prefix="/v1", tags=["coach"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]

logger = logging.getLogger(__name__)

_coach = PolyaCoach()  # 상태 비저장 — 단일 인스턴스 재사용

# slice 106: 오개념 진단 결합(substring + 의미)에서 *결합 끝* top_k 컷에 쓰는 상수.
# `_DEFAULT_TOP_K`=3은 diagnose 기본(노출 상한 top-3·CoachResponse.misconceptions 계약)과 정합.
# `_FANOUT`은 결합 *전* 양쪽을 넉넉히 뽑는 폭 — substr/semantic을 미리 top_k로 자르면 한쪽이
# 다른 쪽을 밀어내므로, 카탈로그 전수(len(CATALOG)=30종·선형 스캔이라 저렴)로 뽑아 결합 끝에서만
# 자른다. substring도 _FANOUT으로 뽑아 semantic-only가 substr를 부당히 잘라내지 않게 한다.
_DEFAULT_TOP_K = 3
_FANOUT = len(CATALOG)

# slice 73: θ 기반 BKT↔θ 교차검증 코칭 중 *노출*할 포커스 — 불일치(consolidate·retrieval)만.
# verify(계산오류)는 arithmetic_error 경로로 별도 노출·합의(foundation/advance)는 LTHC가 담당·
# diagnose(한쪽 신호만·θ 희소)는 비노출. `_build_response_payload` 노출 게이트에서 사용.
_THETA_SURFACED_FOCI: frozenset[str] = frozenset({"consolidate", "retrieval"})


class CoachRequest(BaseModel):
    """`/v1/coach` 요청 본문 — 학생 발화·현재 상태·옵션 숙달도."""

    model_config = ConfigDict(extra="forbid")

    student_input: str = Field(
        min_length=0,
        max_length=4000,
        description="학생 발화(자연어). 빈 문자열 허용(첫 진입). 길이 상한은 남용·비용 방어.",
    )
    student_solution: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "학생의 *풀이/작업* 텍스트(예: L5 OCR로 인식한 손글씨 풀이) — 대화 발화"
            "(`student_input`)와 분리. 계산 슬립 검증(`solution_coaching`)은 이 필드가 "
            "있으면 *이 필드*를 대상으로 한다(없거나 빈 문자열이면 `student_input` 폴백 — "
            "발화에 풀이가 인라인일 수 있음). L5 OCR 결과의 자연 착지점(slice 54 한글 산문 "
            "검출과 결합). Polya·오개념·LTHC 결정은 여전히 `student_input` 기준(대화 흐름)."
        ),
    )
    polya_state: PolyaState = Field(
        default_factory=PolyaState,
        description="세션의 현재 Polya 상태. 기본값=UNDERSTAND 진입.",
    )
    mastery_level: MasteryLevel | None = Field(
        default=None,
        description="학생 숙달도 라벨(있을 때만 LTHC 조정안 반환).",
    )
    bkt_mastery: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "L2 BKT 숙달도(0~1). `mastery_level` 미지정 시 이 값을 라벨로 환산해 LTHC 도출"
            "(slice 25 `mastery_to_level`). `mastery_level`이 있으면 그쪽 우선."
        ),
    )
    coaching_focus: CoachingFocus | None = Field(
        default=None,
        description=(
            "L2 진단(`/me/diagnosis/concepts`)이 권한 코칭 포커스(slice 20). 주면 응답의 "
            "`entry_socratic_category`를 그 포커스에 맞춰 시드(대화 진입 질문 종류)."
        ),
    )
    solution_steps: list[str] | None = Field(
        default=None,
        description=(
            "L5가 공간정보로 분해한 풀이 단계 시퀀스(표현식 리스트). 제공 시 "
            "`verify_solution`으로 단계별(전이별) 검증을 수행해 검산 코칭을 정밀화하고 "
            "`solution_coaching.solution_verification`으로 노출한다(텍스트 신호와 *추가적 OR* "
            "결합). 미제공 시 텍스트 레벨 폴백 — 기존 동작 완전 불변. 텍스트→단계 *분해*는 "
            "L5 OCR 책임이라 백엔드는 제공된 단계만 검증한다."
        ),
    )
    solution_step_types: list[StepType] | None = Field(
        default=None,
        description=(
            "전이별 단계 유형(조건해석/케이스분류/그래프스케치/계산/검산). 제공 시 "
            "`verify_solution`이 비대수 단계를 unverifiable로 보수 처리하는 데 쓴다. 길이는 "
            "전이 수(`len(solution_steps)-1`)와 같아야 한다(규약·길이 검증은 `verify_solution` "
            "위임). 미제공 시 모든 전이를 타입 미지정으로 검증."
        ),
    )
    ocr_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "학생 풀이가 L5 OCR 산출물일 때 인식 신뢰도(0~1). 제공+<0.8이면 §3.3 게이트 ②로 "
            "`match_low_quality`를 표시해 L5가 재확인을 유도. None=OCR 아님/미제공→dormant "
            "(low_quality 항상 False·기존 동작 완전 불변). 이 값은 *입력 품질* 신호지 매칭 "
            "오류가 아니며, 매칭을 비우지 않는다(플래그만)."
        ),
    )


class CoachResponse(BaseModel):
    """`/v1/coach` 응답 — 통합 교수학 결정.

    `decision`은 *반드시* 채워지고(`PolyaCoach.decide()`는 항상 결정 반환), 나머지는 조건부.
    """

    model_config = ConfigDict(extra="forbid")

    decision: PedagogyDecision = Field(
        description="Polya 단계 전이·프롬프트·hint_level·socratic_category 등 핵심 결정.",
    )
    misconceptions: list[MisconceptionMatch] = Field(
        default_factory=list,
        description="오개념 후보 top-3(없으면 빈 리스트). confidence 내림차순.",
    )
    intervention: InterventionDecision | None = Field(
        default=None,
        description=(
            "top-1 misconception이 신뢰도 0.5+면 개입 결정(반례 유도/거꾸로 사고)."
            " 미만이면 None — 진단 보류(라벨링 회피)."
        ),
    )
    lthc: LthcAdaptation | None = Field(
        default=None,
        description="요청에 `mastery_level`이 있을 때만 LTHC 조정안. 없으면 None.",
    )
    entry_socratic_category: SocraticCategory | None = Field(
        default=None,
        description=(
            "요청에 `coaching_focus`가 있을 때만 — 진단 포커스가 권한 대화 진입 소크라테스 "
            "카테고리(slice 22). PolyaCoach의 매 턴 `decision.socratic_category`와 별개(진입 시드)."
        ),
    )
    solution_coaching: SolutionCoaching | None = Field(
        default=None,
        description=(
            "학생 풀이(`student_solution` 우선·없으면 `student_input`)에서 *거짓 수치 관계*"
            "(계산 슬립, 예: '2+3=6')가 L3 결정론 검증으로 "
            "검출되면 검산(verify) 코칭 + L3 신호(slice 52 오케스트레이터). 없으면 None — "
            "이때는 기존 `decision`/`coaching_focus`를 따른다. *실시간 슬립은 배경 진단보다 "
            "우선*(slice 51: 구체적 계산 오류 > θ/숙달 추정). 검증기는 보수적이라 질문·산문은 "
            "거의 발화하지 않는다(false-positive 0 우선). 요청에 `solution_steps`가 있으면 "
            "`solution_verification`(verify_solution 단계별 결과)이 채워지고 단계 레벨 incorrect는 "
            "텍스트 신호와 *추가적 OR*로 결합돼 verify 코칭을 깨운다(미제공 시 None·동작 불변)."
        ),
    )
    prerequisite_coaching: CoachingTrigger | None = Field(
        default=None,
        description=(
            "이 문제 개념의 막힌 선수가 있으면 '선수 복습 먼저' 코칭(L4 prerequisite_review)·"
            "없으면 null. Polya 결정과 *별개의 추가 신호* — 클라/L5가 우선 제시 여부 결정."
        ),
    )
    match_low_quality: bool = Field(
        default=False,
        description=(
            "§3.3 게이트 ② — 요청 `ocr_confidence`가 제공되고 0.8 미만이면 True. 학생 풀이가 "
            "OCR로 오염됐을 수 있으니 L5/LLM이 *재확인을 유도*하라는 신호다. 매칭은 *유지*되고 "
            "(이 플래그는 매칭을 비우지 않는다) intervention도 변경하지 않는다 — 백엔드는 신호만 "
            "노출하고 재확인 발화 생성·intervention 보류는 후속(L5)이 맡는다. `ocr_confidence` "
            "미제공(None)이면 항상 False(기존 동작 불변)."
        ),
    )
    no_confident_match: bool = Field(
        default=False,
        description=(
            "§3.3 게이트 ① — top-1 신뢰도가 0.65 미만이라 후보를 *비웠는지* 여부(억지 매칭 금지). "
            "True면 `misconceptions`는 빈 리스트다 — '매칭 없음'(애초에 후보 0)과 '약해서 비움'을 "
            "구분하는 신호. 게이트가 비우던 기존 동작의 *노출*일 뿐 매칭 결과 자체는 불변."
        ),
    )


class SessionCreateRequest(CoachRequest):
    """`/v1/coach/sessions` 요청 — `CoachRequest` + 선택적 problem_id(FK)."""

    problem_id: uuid.UUID | None = Field(
        default=None,
        description="이 대화가 속한 문제(있으면 dialogue.problem_id로 영속·없으면 NULL).",
    )


class SessionCreateResponse(CoachResponse):
    """`/v1/coach/sessions` 응답 — `CoachResponse` + 영속된 dialogue/turn ID."""

    dialogue_id: uuid.UUID = Field(description="새로 생성된 대화 PK.")
    student_turn_id: uuid.UUID = Field(description="학생 발화 턴 PK(turn_order=1).")
    assistant_turn_id: uuid.UUID = Field(
        description="AI 결정 턴 PK(turn_order=2, content=decision.prompt)."
    )


class TurnAppendResponse(CoachResponse):
    """`/v1/coach/sessions/{id}/turns` 응답 — `CoachResponse` + 추가 턴 PK·turn_order."""

    student_turn_id: uuid.UUID = Field(description="추가된 학생 턴 PK(turn_order=직전+1).")
    assistant_turn_id: uuid.UUID = Field(
        description="추가된 AI 턴 PK(turn_order=직전+2, content=decision.prompt)."
    )
    student_turn_order: int = Field(
        ge=1, description="학생 턴 순번(append 후 dialogue.total_turns에 반영)."
    )
    assistant_turn_order: int = Field(ge=1, description="AI 턴 순번(=student_turn_order + 1).")


class SessionGetResponse(BaseModel):
    """`GET /v1/coach/sessions/{id}` 응답 — dialogue 메타 + turn 목록(turn_order 정렬)."""

    model_config = ConfigDict(extra="forbid")

    dialogue: DialogueSchema = Field(description="대화 세션 메타데이터.")
    turns: list[DialogueTurnSchema] = Field(
        default_factory=list,
        description="대화 턴(turn_order ASC). 학생 발화·AI 결정 본문 포함 — PII 가능.",
    )


def _ability_level(bkt_mastery: float | None, theta: float | None) -> MasteryLevel | None:
    """BKT 숙달(0~1)과 신뢰 θ(logistic 프록시)를 평균해 적응형 스캐폴딩용 ability 라벨 산출.

    힌트(`decide_hint_level`)·Polya 전이(`should_advance`)·LTHC(`adapt_lthc`)가 공유하는
    `mastery_level` 라벨을 *능력 θ까지 반영*해 만든다(slice 77). 둘 다 None이면 None·한쪽만
    있으면 그 신호·둘 다면 평균→`mastery_to_level`. θ는 `_build_response_payload`에서 이미
    slice 76 게이트(`_server_theta_for`)를 통과한 값(신뢰 θ만)이라 여기선 추가 게이팅 불필요.
    """
    proxy = theta_to_mastery_proxy(theta) if theta is not None else None
    parts = [v for v in (bkt_mastery, proxy) if v is not None]
    if not parts:
        return None
    return mastery_to_level(sum(parts) / len(parts))


def _build_response_payload(
    body: CoachRequest,
    *,
    problem_id: uuid.UUID | None = None,
    expected_answer: str | None = None,
    server_mastery: float | None = None,
    server_theta: float | None = None,
    matches: list[MisconceptionMatch] | None = None,
) -> tuple[
    PedagogyDecision,
    list[MisconceptionMatch],
    InterventionDecision | None,
    LthcAdaptation | None,
    SocraticCategory | None,
    SolutionCoaching | None,
]:
    """공통 결정 계산 — `/v1/coach`·`/v1/coach/sessions`·turns append 셋 다 사용.

    `problem_id`·`expected_answer`(slice 64)는 step shadow 진단 맥락으로만 하류 전달되고
    반환(노출 payload)엔 *싣지 않는다*. stateless `/v1/coach`는 DB가 없어 None(맥락 없음),
    세션 엔드포인트는 서버 DB 조회값을 넘긴다 — `expected_answer`(정답)는 결코 응답에 노출하지
    않는다(student-facing이면 정답 누출).

    slice 106: `matches`(오개념 후보)를 *주입*받으면 그 리스트를 그대로 쓴다(핸들러가
    `_compute_matches`로 substring+의미 결합을 미리 비블로킹 계산). **미주입(기본 None)이면
    `diagnose(body.student_input)`로 폴백** — 게이트 off·직접 호출(`TestThetaIntoScaffolding`
    sync 직접호출) 시 *현행 동작과 비트동일*이다(추가 인자는 기본값 only·sync성·반환 튜플 형태
    불변). `intervention`은 *결합 후* matches[0] 기준(combine_diagnoses가 substr 우선이라
    substr 진단이 있으면 그대로 1위 유지).
    """
    # slice 25: mastery_level 명시값 우선·없으면 BKT 숙달(0~1)을 라벨로 환산(L2→L4 브릿지).
    # slice 69: level을 _coach.decide 이전에 계산해 hint level 보수화에도 전달(적응형 코칭).
    # slice 70: 세션/턴은 서버 L2 숙달도(server_mastery)로 클라 bkt를 대체(서버 진실원천)·명시
    # mastery_level은 여전히 최우선·stateless는 server_mastery=None(클라값). 숙달도는 비노출.
    # slice 77: 능력 라벨에 신뢰 θ도 통합 — BKT+θ(logistic) 평균→라벨. 힌트·전이·LTHC가 같은
    # 라벨을 쓰므로 θ가 적응형 스캐폴딩 전반에 일관 반영(θ None=stateless·희소면 BKT만·현행 동일).
    effective_bkt = server_mastery if server_mastery is not None else body.bkt_mastery
    level = body.mastery_level
    if level is None:
        level = _ability_level(effective_bkt, server_theta)
    decision = _coach.decide(body.student_input, body.polya_state, mastery_level=level)
    # slice 106: 주입된 결합 matches 우선·미주입(sync 직접호출·게이트 off 경로)이면 substring
    # diagnose 폴백(현행 비트동일). combine_diagnoses가 substr 우선이라 resolved[0]은 substr가
    # 있으면 substr → select_intervention이 substring 진단(검증된 표면 신호) 기준으로 구동.
    resolved = matches if matches is not None else diagnose(body.student_input)
    intervention = select_intervention(resolved[0]) if resolved else None
    lthc = adapt_lthc(body.polya_state.current_stage, level) if level is not None else None
    # slice 23: 진단 코칭 포커스 → 대화 진입 소크라테스 카테고리 시드(L4 매핑·slice 22).
    entry_category = (
        focus_to_socratic_category(body.coaching_focus) if body.coaching_focus is not None else None
    )
    # slice 53: L3→L4 오케스트레이터(slice 52) — 학생 풀이의 *거짓 수치 관계*를 L3 결정론
    # 검증으로 검출해 검산(verify) 코칭을 처방(실시간 슬립은 배경 진단보다 우선·slice 51).
    # slice 55: 검증 대상은 *풀이 전용* student_solution 우선(L5 OCR 착지점)·없거나 비면
    # student_input 폴백(발화 인라인 풀이). Polya/오개념/LTHC는 위에서 student_input 기준 유지.
    # slice 73: θ는 세션/턴에서 서버 L2(AbilitySnapshot) 소싱값(server_theta)을 주입 — BKT↔θ
    # 교차검증 코칭(recommend_coaching)을 깨운다. stateless /v1/coach는 None(DB 없음).
    solution_text = body.student_solution or body.student_input
    # WH-1 1단계 결선: L5가 분해한 단계 시퀀스(solution_steps)가 있으면 verify_solution으로
    # 단계별 검증해 검산 코칭을 정밀화한다(텍스트 신호와 추가적 OR 결합·미제공 시 동작 불변).
    # WH-1 1단계 OCR 게이팅: ocr_confidence를 함께 넘겨, 저신뢰 OCR이면 step-incorrect 신호를
    # 코칭 결정에서 누그러뜨리고(거짓 지적 방지·정확성 #1) verification_ocr_gated로 노출한다.
    # 텍스트 레벨 신호·미제공/고신뢰 OCR은 게이팅 안 됨(하위호환). 이미 _compute_matches(게이트
    # ②)에 전달 중인 동일 값을 solution coaching에도 thread한다.
    sol = recommend_coaching_for_solution(
        solution_text,
        effective_bkt,
        server_theta,
        problem_id=problem_id,
        expected_answer=expected_answer,
        solution_steps=body.solution_steps,
        solution_step_types=body.solution_step_types,
        ocr_confidence=body.ocr_confidence,
    )
    # slice 73: 노출은 *불일치 신호만* — 계산오류 verify(기존·arithmetic_error) + BKT↔θ 불일치
    # (consolidate·retrieval). 합의(foundation/advance)는 LTHC가 담당·한쪽 신호만(diagnose)은
    # θ 희소 노이즈라 비노출. θ 수치 자체는 노출 안 함(노출되는 건 trigger의 정성 발화뿐).
    solution_coaching = (
        sol if (sol.arithmetic_error or sol.trigger.focus in _THETA_SURFACED_FOCI) else None
    )
    return decision, resolved, intervention, lthc, entry_category, solution_coaching


class _MatchOutcome(NamedTuple):
    """`_compute_matches` 반환 — 게이트 통과 매칭 + §3.3 게이트 플래그 2종.

    WH-1 1단계 슬라이스: 직전 슬라이스에서 `_gate`가 `MatchGateResult.matches`만 반환하고
    `low_quality`/`no_confident_match`를 *드롭*했다. 이 컨테이너로 플래그를 핸들러까지 thread해
    `CoachResponse`(`match_low_quality`/`no_confident_match`)로 노출한다 — 매칭 *알고리즘*과
    리스트 내용은 불변, 반환 *형태*만 확장(드롭 제거)이다.
    """

    matches: list[MisconceptionMatch]
    low_quality: bool
    no_confident_match: bool


async def _compute_matches(
    student_input: str, *, ocr_confidence: float | None = None
) -> _MatchOutcome:
    """오개념 후보 계산 + §3.3 품질 게이트 — `misconception_semantic_mode` 3값 분기(off/shadow/on).

    WH-1 1단계 슬라이스 1(`match_misconception` 도구화): 모드별 후보 산출 *직후* 결과에
    `apply_match_quality_gate`를 *후처리*로 적용한다(`_gate` 헬퍼). 게이트는 매칭 *알고리즘*
    (`diagnose`/의미 매처/`combine_diagnoses`)을 전혀 바꾸지 않고, top-1 신뢰도<0.65면 후보를
    *비운다*(억지 매칭 금지·CLAUDE.md "확실하지 않으면 모른다"). 따라서 세 모드(off/shadow/on)
    *모두* 동일한 게이트를 거쳐 약한 top-1 매칭이 하류(가설·intervention)로 새지 않는다.

    **게이트 플래그 thread(이 슬라이스)**: 직전엔 `_gate`가 `MatchGateResult.matches`만 반환해
    `low_quality`/`no_confident_match`를 드롭했다. 이제 게이트를 *한 번만* 적용해 `MatchGateResult`
    전체를 받고 matches+플래그를 `_MatchOutcome`으로 함께 반환한다(드롭 제거). 매칭 리스트·재정렬은
    불변 — 반환 *형태*만 확장된다. 세 모드 모두 *같은* `_gate`를 통과하므로 플래그 의미가 일관된다.

    `ocr_confidence`는 OCR 산출물일 때 인식 신뢰도(0~1)다. 제공+<0.8이면 게이트 ②가 `low_quality`를
    세운다(매칭은 *유지*·플래그만). **None(미제공)이면 게이트 ②는 dormant** — `low_quality=False`로
    기존 동작 완전 불변. `low_quality`는 *입력 OCR 품질* 신호라 매칭 유무와 *독립*이다(매칭이 있어도
    low_quality 가능). `no_confident_match`는 top-1<0.65로 후보가 비워졌는지(매칭 결과는 게이트 ①의
    기존 동작 그대로·노출만 추가)다.

    slice 106: 핸들러가 호출해 `_build_response_payload(matches=...)`로 *matches만* 주입한다(직접
    sync 호출 경로는 미주입→`diagnose` 폴백이라 잠긴 `_build_response_payload(body)` 계약 불변).
    플래그는 핸들러가 `_MatchOutcome`에서 직접 꺼내 응답에 싣는다(payload 6-튜플 계약과 분리).

    **§3.3 범위(정직)**: 이 슬라이스는 *신호 노출까지*다 — low OCR→`match_low_quality=True` 노출.
    *재확인 발화 생성*·*intervention 보류*는 L5/LLM·후속(백엔드는 신호 제공·답 미루기 원칙 유지).
    intervention/matches 자체는 여기서 *변경하지 않는다*(억지매칭 차단[no_confident_match]은 기존
    게이트 동작 그대로).

    **`off`(기본)**: `diagnose(student_input)`만 — 의미 매처를 *호출하지 않는다*(임베딩 로드 0·
    현행 비트동일). substring 결과를 그대로 반환.

    **`shadow`(slice 111)**: 의미 매처를 라이브로 *돌리되* 노출은 substring 그대로(off와 비트동일
    반환)이고, `observe_misconception_shadow`로 substring↔semantic *불일치만 로깅*한다(비노출·
    실 분포 플립 근거 수집·학생 원문 미포함). 의미 매처 호출·폴백은 `on`과 동일(아래).

    **`on`**: 의미 매처를 `asyncio.to_thread`로 *워커 스레드*에서 호출한다 — 블로킹 임베딩
    (bge-m3 등)이 이벤트 루프를 막지 않게(CLAUDE.md p50<2s·동시 요청 보호). 결과를
    `combine_diagnoses`로 substring 위·semantic-only 아래로 결합해 *노출*한다(substr 우선·재정렬
    없음). substr/semantic 둘 다 `_FANOUT`(카탈로그 전수)으로 뽑아 *결합 끝에서만*
    `_DEFAULT_TOP_K`로 자른다(한쪽이 다른 쪽을 미리 잘라내지 않게).

    **graceful 폴백(CLAUDE.md 가용성 우선 #1≫#6)**: 의미 매칭이 *어떤 이유로든* 실패하면
    (모델 미설치·DB 미도달·임베딩 오류) 예외를 삼키고 substring 결과로 폴백한다(500이 아니라
    200·진단 1위는 substr라 학생 경험 유지). 실패는 *조용히 넘기지 않고* warning 로그로 남긴다
    (CLAUDE.md "환각/장애 조용히 넘어가지 말고 로그").
    """

    def _gate(candidates: list[MisconceptionMatch]) -> _MatchOutcome:
        # §3.3 품질 게이트 후처리 — 세 모드 공통 출구. 게이트를 *한 번만* 적용해 결과 전체를 받고
        # matches+플래그를 함께 반환한다(직전엔 .matches만 반환해 플래그를 드롭했음). 게이트 ①은
        # top-1<floor면 후보를 비우고(억지 매칭 금지) no_confident_match=True를, 게이트 ②는 OCR
        # confidence<0.8(None이면 dormant)면 low_quality=True를 세운다(매칭은 유지). 게이트는
        # *재정렬·변형 없이* 통과분만 그대로 통과시킨다(`combine_diagnoses` 순서 보존).
        result = apply_match_quality_gate(candidates, ocr_confidence=ocr_confidence)
        return _MatchOutcome(
            matches=result.matches,
            low_quality=result.low_quality,
            no_confident_match=result.no_confident_match,
        )

    substr = diagnose(student_input, top_k=_FANOUT)
    mode = get_settings().misconception_semantic_mode
    if mode == "off":
        # off — substring만(의미 매처 미호출). 노출 상한 top-3로 자른다(결합 없음·현행 비트동일).
        return _gate(substr[:_DEFAULT_TOP_K])
    # shadow·on — 의미 매처를 비블로킹(워커 스레드)으로 돌린다. 실패는 substring graceful 폴백.
    try:
        sem = await asyncio.to_thread(
            get_semantic_matcher().match,
            student_input,
            top_k=_FANOUT,
            threshold=get_settings().misconception_semantic_threshold,
        )
    except Exception:
        # 의미 매칭 실패 — substring 폴백(가용성 우선·200 유지). 조용히 넘기지 않고 로그.
        logger.warning("의미 매칭 실패 — substring 폴백", exc_info=True)
        return _gate(substr[:_DEFAULT_TOP_K])
    if mode == "shadow":
        # shadow — 노출은 substring 그대로(off 비트동일)·substring↔semantic 불일치만 로깅한다
        # (비노출·실 분포 플립 근거 수집·slice 111). 학생 원문은 로그에 안 담는다(프라이버시).
        # shadow 로깅은 *게이트 전* 원본 substr/sem으로 수행(게이트가 비교 분포를 왜곡하지 않게).
        observe_misconception_shadow(substr, sem)
        return _gate(substr[:_DEFAULT_TOP_K])
    # on — substring 아래에 semantic-only 후보를 결합해 *노출*(substring 우선·재정렬 없음).
    return _gate(combine_diagnoses(substr, sem, top_k=_DEFAULT_TOP_K))


async def _expected_answer_for(session: AsyncSession, problem_id: uuid.UUID | None) -> str | None:
    """문항 기대정답을 서버 DB에서 조회 — step shadow 진단 맥락 전용(slice 64·비노출).

    shadow 게이트(`l4_step_shadow_enabled`)가 off(프로덕션 기본)거나 `problem_id`가 None이면
    조회를 *건너뛴다*(None) — 소비처(`observe_step_breaks`)와 같은 게이트라, 안 쓸 정답을
    불필요하게 DB에서 끌어와 메모리에 적재하지 않는다(비용·데이터 최소화). 문항 부재면 None
    (graceful — 코퍼스 미적재·신규 문항도 안전). 반환값은 *절대 HTTP 응답에 싣지 않는다*
    (정답 누출 차단) — `_build_response_payload`의 `expected_answer` 인자로만 흘러
    `observe_step_breaks` 로그 sink에 도달한다.
    """
    if problem_id is None or not get_settings().l4_step_shadow_enabled:
        return None
    problem = await session.get(ProblemORM, problem_id)
    return problem.answer if problem is not None else None


async def _server_mastery_for(
    session: AsyncSession, user_id: uuid.UUID, problem_id: uuid.UUID | None
) -> float | None:
    """학생의 *실제* 숙달도를 서버 L2 저장소에서 조회 — coach 세션/턴 전용(slice 70·비노출).

    게이트(`l4_server_mastery_enabled`)가 off거나 `problem_id`가 None이면 None(조회 skip).
    문항의 PRIMARY 개념(없으면 TESTED 폴백)을 해석해 그 개념의 현재 숙달도를 돌려준다. 문항-개념
    미매핑·측정 이력 없음이면 graceful None → 호출자는 클라이언트 bkt로 폴백. 반환값은 코칭
    *결정에만* 쓰이고 HTTP 응답엔 싣지 않는다(slice 69 숙달도 비노출 불변).
    """
    if problem_id is None or not get_settings().l4_server_mastery_enabled:
        return None
    concept_id = await get_primary_concept_id(session, problem_id)
    if concept_id is None:
        return None
    return await get_current_mastery(session, user_id, concept_id)


def _theta_reading_reliable(reading: AbilityReading) -> bool:
    """개념 θ를 코칭 교차검증에 쓸 만큼 *신뢰*할 수 있나 — 응답수·SE 게이트(slice 76 노이즈 가드).

    응답이 충분(`l4_theta_min_responses` 이상)하고 SE가 측정 가능(None 아님)하며 상한
    (`l4_theta_max_se`) 이하일 때만 True. 응답 1~2개의 극단 θ(±4·SE inf→None)나 SE가 큰 개념
    θ는 False → 호출자가 전과목 θ로 폴백한다. 임계는 config(운영 튜닝·기본 응답 3·SE 1.0).
    """
    settings = get_settings()
    return (
        reading.response_count >= settings.l4_theta_min_responses
        and reading.standard_error is not None
        and reading.standard_error <= settings.l4_theta_max_se
    )


async def _server_theta_for(
    session: AsyncSession, user_id: uuid.UUID, problem_id: uuid.UUID | None
) -> float | None:
    """학생의 *실제* IRT 능력 θ를 서버 L2(AbilitySnapshot)에서 조회 — coach 세션/턴
    전용(slice 73·74·76·비노출).

    게이트(`l4_server_theta_enabled`)가 off면 None(조회 skip). slice 74: 문항 PRIMARY 개념의
    *개념별* θ를 우선 조회해(같은 개념 BKT와 동일 개념끼리 교차검증·정밀) `_server_mastery_for`와
    대칭을 이룬다. **slice 76 노이즈 가드**: 개념 θ는 *신뢰도*(응답수·SE)가 충분할 때만 쓴다
    (`_theta_reading_reliable`) — 응답 1~2개의 극단 θ는 무시하고 전과목 θ로 폴백(허위
    consolidate/retrieval 차단). 개념 θ가 없거나·불신뢰·problem_id/개념 미해석이면 *전과목* θ
    폴백(slice 73 동작·전과목은 게이팅 안 함). 둘 다 없으면 graceful None → `recommend_coaching`이
    diagnose 폴백(노출 안 함). 반환값(θ 수치)은 코칭 *결정에만* 쓰이고 HTTP 응답엔 싣지 않는다
    (slice 70 숙달도 비노출과 동일 — θ도 student-facing 비노출).
    """
    if not get_settings().l4_server_theta_enabled:
        return None
    if problem_id is not None:
        concept_id = await get_primary_concept_id(session, problem_id)
        if concept_id is not None:
            reading = await get_current_ability(session, user_id, concept_id)
            if reading is not None and _theta_reading_reliable(reading):
                return reading.theta  # 신뢰도 충분한 개념 θ(정밀 교차검증)
    return await get_current_theta(session, user_id)  # 전과목 폴백(slice 73·게이팅 안 함)


async def _prerequisite_coaching_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    problem_id: uuid.UUID | None,
    *,
    mastery_threshold: float = 0.7,
    max_depth: int = 1,
) -> CoachingTrigger | None:
    """이 문제 개념의 *막힌 선수*가 있으면 "선수 복습 먼저" 코칭을 반환 — coach 세션/턴 전용.

    `GET /v1/me/weak-concepts/{id}/coaching`과 *동일 오케스트레이션*(L5가 L2 fetch + L4 decide를
    배선·L2/L4 좌석 무변경 재사용·역의존 0)을 상호작용 코칭 흐름에 옮긴 것이다. 학생이 어떤 문제를
    풀 때 그 문제 개념의 막힌 선수가 있으면 응답에 *별개 추가 신호*로 "선수 복습 먼저"를 실어준다
    (Polya 결정을 *대체하지 않음*·클라/L5가 우선 제시 여부 결정·코칭 턴을 가로채 풀이를 끊지 않음).

    흐름:
      ① `problem_id` None → None(문제 맥락 없음·stateless·매핑 불가).
      ② `get_primary_concept_id`로 문항 PRIMARY 개념(없으면 TESTED 폴백) 해석 → None이면 None
         (문항-개념 미매핑).
      ③ L2 `recommend_prerequisite_gaps(weak_only=True)`로 그 개념의 *막힌 선수*(weakness asc·
         `gaps[0]`=top blocker)를 조회.
      ④ L4 `recommend_prerequisite_coaching(gaps)` — 막힌 선수가 있으면 `prerequisite_review`
         코칭 trigger·없으면 None(순수 결정·L5는 fetch만).

    redaction: `CoachingTrigger`의 rationale/prompt에는 *안전 표시 필드*(name_ko)만 들어가고
    개념 본문·정답은 구조적으로 흐를 수 없다(`PrerequisiteGap`/`recommend_prerequisite_coaching`이
    이미 보장). 톤은 재사용 함수가 격려·비난 0(직전 슬 톤 가드)으로 추가 문구 생성 없음. 반환값은
    HTTP 응답의 `prerequisite_coaching`으로 노출되나 *추가 신호*일 뿐이다.
    """
    if problem_id is None:
        return None  # 문제 맥락 없음 → 선수 코칭 불가(stateless·매핑 없음).
    concept_id = await get_primary_concept_id(session, problem_id)
    if concept_id is None:
        return None  # 문항-개념 미매핑 → 선수 traversal 불가.
    gaps = await recommend_prerequisite_gaps(
        session,
        user_id,
        concept_id,
        mastery_threshold=mastery_threshold,
        weak_only=True,
        max_depth=max_depth,
    )
    return recommend_prerequisite_coaching(gaps)  # 막힌 선수 없으면 None.


async def _log_verify_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    problem_id: uuid.UUID | None,
    attempt_id: uuid.UUID | None,
    student_solution: str | None,
) -> None:
    """학생 풀이의 검산(verify) 결과를 `attempt_event`(event_type=검산결과)로 1행 적재.

    WH-1 0단계 지표 ①(verify 통과율)을 NOT_INSTRUMENTED→MEASURED로 끌어올리는 *적재 좌석*.
    스테이트풀 coach(`create_session`·`append_turns`)에서만 호출하며, stateless `/v1/coach`
    (`coach_decide`)는 DB 무접근 계약이라 적재하지 않는다.

    적재 조건(false-pass 방지): `student_solution`(풀이 전용 필드)이 *비어 있으면 적재 안 함* —
    풀이를 제출한 턴만 검산 신호로 기록한다(빈/대화 턴이 '통과'로 오집계되는 걸 차단). 검증은
    coach 본문(`recommend_coaching_for_solution`)이 쓰는 것과 *동일한* 결정론 검증기를 다시
    호출한다(순수·결정론·저비용 — `_build_response_payload`를 건드리지 않고 신호만 재산출하는
    게 목적). `signal is None`=거짓 수치관계 *미적발*(passed=True), `signal is not None`=적발
    (passed=False). **binary 검산**이지 3-state(정답/오답/검증불가) verify가 아니다.

    트랜잭션: ORM 1행을 `session.add`만 하고 *commit은 하지 않는다* — 호출 핸들러가 이미 자기
    트랜잭션을 commit하므로 그 트랜잭션에 합류한다(별도 commit 금지). `event_at`은 핸들러와 동일
    시각으로 명시(server_default 의존 회피·복합 PK 구성요소).
    """
    solution_text = student_solution or ""
    if not solution_text.strip():
        return  # 풀이 제출 턴이 아님(빈/대화 턴) → 적재 안 함(false-pass 방지).

    signal = validate_response(arithmetic_validator(), solution_text)
    passed = signal is None  # None=거짓관계 미적발(통과)·아니면 적발(실패).

    event = AttemptEventORM(
        event_at=datetime.now(timezone.utc),
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        event_type=EventType.검산결과,
        event_data={"passed": passed, "error_kind": (signal.kind if signal else None)},
    )
    session.add(event)  # commit은 핸들러가 — 같은 트랜잭션에 합류(별도 commit 금지).


async def _log_hint_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    problem_id: uuid.UUID | None,
    attempt_id: uuid.UUID | None,
    hint_level: int | None,
) -> None:
    """AI가 제공한 힌트 노출량(hint_level)을 `attempt_event`(event_type=힌트제공)로 1행 적재.

    WH-1 0단계 지표 ⑤(도움 감소 곡선)을 NOT_INSTRUMENTED→MEASURED로 끌어올리는 *적재 좌석*.
    직전 verify 슬라이스(`_log_verify_event`·검산결과) **동형**: 스테이트풀 coach
    (`create_session`·`append_turns`)에서만 호출하고, stateless `/v1/coach`(`coach_decide`)는
    DB 무접근 계약이라 적재하지 않는다.

    **재계산 0**: `hint_level`은 핸들러가 이미 보유한 `decision.hint_level`을 그대로 전달받는다
    (`decision`은 `_build_response_payload`가 반환하는 6-튜플의 첫 요소). verify와 달리 검증기를
    다시 부를 필요 없이 *이미 계산된* 값만 적재한다 — `_build_response_payload` 시그니처·반환을
    건드리지 않는다(읽기만).

    적재 신호의 의미: 이 hint_level은 AI가 *제공한* 노출량(supply·graded 1~4·1=가장 은근/
    4=전체 풀이)이지 학생이 *요청*한 demand(`힌트요청`)가 아니다 — 도움 감소 곡선은 supply 추세를
    본다. `hint_level`이 None이면(이론적 경계·decision은 항상 int지만 방어적) early return으로
    적재하지 않는다(날조 회피 — 신호 없는 행 미생성).

    트랜잭션: `_log_verify_event`와 동일하게 ORM 1행을 `session.add`만 하고 *commit은 하지
    않는다* — 호출 핸들러가 자기 트랜잭션을 commit하므로 그 트랜잭션에 합류한다(별도 commit 금지).
    `event_at`은 핸들러와 동일하게 now(복합 PK 구성요소·시계열 순서축).
    """
    if hint_level is None:
        return  # 힌트 레벨 없음(이론적 경계) → 적재 안 함(날조 회피).

    event = AttemptEventORM(
        event_at=datetime.now(timezone.utc),
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        event_type=EventType.힌트제공,
        event_data={"hint_level": hint_level},
    )
    session.add(event)  # commit은 핸들러가 — 같은 트랜잭션에 합류(별도 commit 금지).


@router.post(
    "/coach",
    response_model=CoachResponse,
    summary="L4 교수학 통합 결정(stateless)",
    dependencies=[RateLimitedTripleWrite],
)
async def coach_decide(
    body: CoachRequest,
    user: ConsentedUser,
) -> CoachResponse:
    """학생 발화 → Polya 결정 + 오개념 진단 + LTHC 조정안을 *한 번에* 반환.

    *DB 무접근* — 영속이 필요하면 `/v1/coach/sessions`를 호출. `user`는 인증 게이트만.
    """
    _ = user.user_id  # 인증 게이트 통과 확인용(stateless라 user 데이터 미사용)

    # slice 106: 오개념 후보를 비블로킹 결합(게이트 off면 substring만)으로 미리 계산해 주입.
    # WH-1: ocr_confidence를 게이트로 thread하고(§3.3 게이트 ②), 게이트 플래그를 응답에 노출한다.
    outcome = await _compute_matches(body.student_input, ocr_confidence=body.ocr_confidence)
    decision, matches, intervention, lthc, entry_category, solution_coaching = (
        _build_response_payload(body, matches=outcome.matches)
    )
    return CoachResponse(
        decision=decision,
        misconceptions=matches,
        intervention=intervention,
        lthc=lthc,
        entry_socratic_category=entry_category,
        solution_coaching=solution_coaching,
        match_low_quality=outcome.low_quality,
        no_confident_match=outcome.no_confident_match,
    )


@router.post(
    "/coach/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="L4 코치 세션 생성(dialogue + 학생/AI 2턴 영속)",
    dependencies=[RateLimitedTripleWrite],
)
async def create_session(
    body: SessionCreateRequest,
    user: ConsentedUser,
    session: SessionDep,
) -> SessionCreateResponse:
    """새 대화 + 학생/AI 첫 2턴 영속. LLM 호출은 0 — AI 턴은 `decision.prompt` 저장.

    트랜잭션: dialogue 먼저 commit(PK 확보) → turns commit(FK 의존). `user_id`는 인증된
    `user.user_id`로 자동 설정(타인 데이터 차단). 미성년 채팅 평문 저장은 *저장 계층*
    책임(모듈 docstring 참조 — DB 암호화 at-rest는 후속 인프라 슬라이스).
    """
    # slice 64: 문항 기대정답을 서버 DB에서 조회해 step shadow 진단 맥락으로 주입(비노출 — 응답엔
    # 결코 싣지 않음·정답 누출 차단). 문항 부재/없음이면 None(graceful).
    expected_answer = await _expected_answer_for(session, body.problem_id)
    # slice 70: 서버 L2 저장소의 실제 숙달도를 조회해 클라 bkt 대체(게이트 ON·비노출).
    server_mastery = await _server_mastery_for(session, user.user_id, body.problem_id)
    # slice 73·74: 서버 L2의 실제 θ도 조회 — BKT↔θ 교차검증(게이트 ON·θ 수치 비노출). slice 74:
    # 문항 개념의 *개념별* θ 우선·없으면 전과목 폴백(_server_theta_for 내부).
    server_theta = await _server_theta_for(session, user.user_id, body.problem_id)
    # 선수 복습 코칭 — 이 문제 개념의 막힌 선수가 있으면 "선수 복습 먼저" 신호(L2 fetch + L4 decide
    # 배선·`/me/.../coaching`과 동형). Polya 결정과 *별개의 추가 신호*(non-override·턴 비가로채기).
    prereq = await _prerequisite_coaching_for(session, user.user_id, body.problem_id)
    # slice 106: 오개념 후보를 비블로킹 결합(게이트 off면 substring만)으로 미리 계산해 주입.
    # WH-1: ocr_confidence를 게이트로 thread하고(§3.3 게이트 ②), 게이트 플래그를 응답에 노출한다.
    outcome = await _compute_matches(body.student_input, ocr_confidence=body.ocr_confidence)
    decision, matches, intervention, lthc, entry_category, solution_coaching = (
        _build_response_payload(
            body,
            problem_id=body.problem_id,
            expected_answer=expected_answer,
            server_mastery=server_mastery,
            server_theta=server_theta,
            matches=outcome.matches,
        )
    )

    now = datetime.now(timezone.utc)
    dialogue = DialogueORM.from_schema(
        DialogueSchema(
            user_id=user.user_id,
            problem_id=body.problem_id,
            started_at=now,
            total_turns=2,
            student_turns=1,
            assistant_turns=1,
        )
    )
    session.add(dialogue)
    await session.commit()
    await session.refresh(dialogue)

    student_turn = DialogueTurnORM.from_schema(
        DialogueTurnSchema(
            dialogue_id=dialogue.dialogue_id,
            turn_order=1,
            spoken_at=now,
            role=TurnRole.student,
            content=body.student_input,
            content_type=ContentType.텍스트,
        )
    )
    assistant_turn = DialogueTurnORM.from_schema(
        DialogueTurnSchema(
            dialogue_id=dialogue.dialogue_id,
            turn_order=2,
            spoken_at=now,
            role=TurnRole.assistant,
            content=decision.prompt,
            content_type=ContentType.텍스트,
        )
    )
    session.add_all([student_turn, assistant_turn])
    # WH-1 지표 ① 적재 — 풀이 제출(student_solution 비어있지 않음)이면 검산 결과를 attempt_event로
    # 기록(같은 트랜잭션 합류·별도 commit 없음). stateless /v1/coach는 미적재(DB 무접근 계약).
    await _log_verify_event(
        session,
        user_id=user.user_id,
        problem_id=body.problem_id,
        attempt_id=dialogue.attempt_id,
        student_solution=body.student_solution,
    )
    # WH-1 지표 ⑤ 적재 — 이미 계산된 decision.hint_level(supply·1~4)을 그대로 기록(재계산 0·
    # _build_response_payload 불변). verify 적재 바로 옆·같은 트랜잭션 합류(별도 commit 없음).
    await _log_hint_event(
        session,
        user_id=user.user_id,
        problem_id=body.problem_id,
        attempt_id=dialogue.attempt_id,
        hint_level=decision.hint_level,
    )
    await session.commit()

    return SessionCreateResponse(
        decision=decision,
        misconceptions=matches,
        intervention=intervention,
        lthc=lthc,
        entry_socratic_category=entry_category,
        solution_coaching=solution_coaching,
        prerequisite_coaching=prereq,
        match_low_quality=outcome.low_quality,
        no_confident_match=outcome.no_confident_match,
        dialogue_id=dialogue.dialogue_id,
        student_turn_id=student_turn.turn_id,
        assistant_turn_id=assistant_turn.turn_id,
    )


@router.post(
    "/coach/sessions/{dialogue_id}/turns",
    response_model=TurnAppendResponse,
    status_code=status.HTTP_201_CREATED,
    summary="L4 코치 세션에 학생/AI 2턴 추가",
    dependencies=[RateLimitedTripleWrite],
)
async def append_turns(
    dialogue_id: uuid.UUID,
    body: CoachRequest,
    user: ConsentedUser,
    session: SessionDep,
) -> TurnAppendResponse:
    """기존 dialogue에 학생/AI 2턴 추가.

    소유권 검증: `dialogue.user_id != user.user_id`거나 dialogue 부재 시 **404**
    (존재 노출 회피 — 타인 데이터 존재 여부 자체를 숨김; 403 분리는 정보 누출).
    `turn_order`는 `dialogue.total_turns` 기반으로 계산(max 쿼리 회피·증분 정합).
    LLM 호출 0 — AI 턴 content는 `decision.prompt` 그대로(slice 7 정합).
    """
    dialogue = await session.get(DialogueORM, dialogue_id)
    if dialogue is None or dialogue.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다."
        )

    # slice 64: 멀티턴 경로도 문항 맥락 주입 — dialogue에 이미 실린 problem_id로 기대정답 조회
    # (비노출 진단 로그 전용). create_session과 동형(create는 body, append는 dialogue 출처).
    expected_answer = await _expected_answer_for(session, dialogue.problem_id)
    # slice 70: 멀티턴도 서버 L2 숙달도 조회(dialogue.problem_id·user 출처)·클라 bkt 대체.
    server_mastery = await _server_mastery_for(session, user.user_id, dialogue.problem_id)
    # slice 73·74: 멀티턴도 서버 L2 θ 조회 — BKT↔θ 교차검증(θ 수치 비노출). slice 74: 개념별 θ
    # 우선(dialogue.problem_id)·없으면 전과목 폴백.
    server_theta = await _server_theta_for(session, user.user_id, dialogue.problem_id)
    # 선수 복습 코칭 — dialogue에 실린 problem_id로 막힌 선수 조회(create_session과 동형·dialogue
    # 출처). 별개 추가 신호(non-override·턴 비가로채기).
    prereq = await _prerequisite_coaching_for(session, user.user_id, dialogue.problem_id)
    # slice 106: 오개념 후보를 비블로킹 결합(게이트 off면 substring만)으로 미리 계산해 주입.
    # WH-1: ocr_confidence를 게이트로 thread하고(§3.3 게이트 ②), 게이트 플래그를 응답에 노출한다.
    outcome = await _compute_matches(body.student_input, ocr_confidence=body.ocr_confidence)
    decision, matches, intervention, lthc, entry_category, solution_coaching = (
        _build_response_payload(
            body,
            problem_id=dialogue.problem_id,
            expected_answer=expected_answer,
            server_mastery=server_mastery,
            server_theta=server_theta,
            matches=outcome.matches,
        )
    )

    current_total = dialogue.total_turns or 0
    student_order = current_total + 1
    assistant_order = current_total + 2

    now = datetime.now(timezone.utc)
    student_turn = DialogueTurnORM.from_schema(
        DialogueTurnSchema(
            dialogue_id=dialogue_id,
            turn_order=student_order,
            spoken_at=now,
            role=TurnRole.student,
            content=body.student_input,
            content_type=ContentType.텍스트,
        )
    )
    assistant_turn = DialogueTurnORM.from_schema(
        DialogueTurnSchema(
            dialogue_id=dialogue_id,
            turn_order=assistant_order,
            spoken_at=now,
            role=TurnRole.assistant,
            content=decision.prompt,
            content_type=ContentType.텍스트,
        )
    )
    session.add_all([student_turn, assistant_turn])

    # dialogue 카운트 증가 — 다음 append의 `total_turns` 입력.
    dialogue.total_turns = current_total + 2
    dialogue.student_turns = (dialogue.student_turns or 0) + 1
    dialogue.assistant_turns = (dialogue.assistant_turns or 0) + 1

    # WH-1 지표 ① 적재 — create_session과 동형(풀이 제출 턴만·같은 트랜잭션 합류). problem_id·
    # attempt_id는 dialogue에서 출처(append는 dialogue 컨텍스트).
    await _log_verify_event(
        session,
        user_id=user.user_id,
        problem_id=dialogue.problem_id,
        attempt_id=dialogue.attempt_id,
        student_solution=body.student_solution,
    )
    # WH-1 지표 ⑤ 적재 — create_session과 동형(이미 계산된 decision.hint_level·supply 1~4을 그대로
    # 기록·재계산 0·_build_response_payload 불변). verify 적재 바로 옆·같은 트랜잭션 합류(별도
    # commit 없음). problem_id·attempt_id는 dialogue 출처(append는 dialogue 컨텍스트).
    await _log_hint_event(
        session,
        user_id=user.user_id,
        problem_id=dialogue.problem_id,
        attempt_id=dialogue.attempt_id,
        hint_level=decision.hint_level,
    )
    await session.commit()

    return TurnAppendResponse(
        decision=decision,
        misconceptions=matches,
        intervention=intervention,
        lthc=lthc,
        entry_socratic_category=entry_category,
        solution_coaching=solution_coaching,
        prerequisite_coaching=prereq,
        match_low_quality=outcome.low_quality,
        no_confident_match=outcome.no_confident_match,
        student_turn_id=student_turn.turn_id,
        assistant_turn_id=assistant_turn.turn_id,
        student_turn_order=student_order,
        assistant_turn_order=assistant_order,
    )


@router.get(
    "/coach/sessions/{dialogue_id}",
    response_model=SessionGetResponse,
    summary="L4 코치 세션 조회(dialogue 메타 + 턴 목록)",
    dependencies=[RateLimitedTripleRead],
)
async def get_session_detail(
    dialogue_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> SessionGetResponse | Response:
    """세션 메타 + 정렬된 턴 목록 반환. 소유권 검증은 slice 8 패턴(404·존재 노출 회피).

    `turn_order` 오름차순으로 학생/AI/system 모든 턴을 그대로 반환 — content는 학생 PII
    가능(이미 본인 소유 확정·`ConsentedUser` 게이트 통과 후). 페이지네이션 없음(한 세션의
    턴은 소량 가정·필요 시 후속).

    조건부 GET(RFC 7232): 응답에 ETag를 싣고, `If-None-Match`가 현재 ETag와 일치하면
    **304 Not Modified**(빈 본문)로 응답해 모바일 대역폭을 아낀다. ETag는 *dialogue +
    turns 전체 표현*의 해시라 턴 1개 추가만으로도 ETag가 바뀐다(slice 8 append 후 캐시
    무효화 자동).
    """
    dialogue = await session.get(DialogueORM, dialogue_id)
    if dialogue is None or dialogue.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다."
        )

    stmt = (
        select(DialogueTurnORM)
        .where(DialogueTurnORM.dialogue_id == dialogue_id)
        .order_by(DialogueTurnORM.turn_order)
    )
    result = await session.execute(stmt)
    turns = [row.to_schema() for row in result.scalars().all()]
    payload = SessionGetResponse(dialogue=dialogue.to_schema(), turns=turns)
    etag = etag_for(payload)
    if matches_if_none_match(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return payload
