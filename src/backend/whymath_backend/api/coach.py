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
from typing import Annotated, Literal, NamedTuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._concurrency import etag_for, matches_if_none_match
from whymath_backend.api._crypto import (
    SupportsEnvelope,
    build_dialogue_content_cipher,
    encrypt_dialogue_content,
    resolve_dialogue_content,
)
from whymath_backend.api._l3_state import (
    CACHE_KEY as _CACHE_KEY,
)
from whymath_backend.api._l3_state import (
    PROVIDER_KEY as _PROVIDER_KEY,
)
from whymath_backend.api._l3_state import (
    TRACE_KEY as _TRACE_KEY,
)
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
from whymath_backend.harness.wh1_shadow import observe_wh1_harness_shadow
from whymath_backend.l1.embedding_provider import build_provider
from whymath_backend.l2 import (
    AbilityReading,
    get_current_ability,
    get_current_mastery,
    get_current_theta,
    get_primary_concept_id,
    theta_to_mastery_proxy,
)
from whymath_backend.l2.prerequisite_recommendation import recommend_prerequisite_gaps
from whymath_backend.l3.interfaces import (
    CacheBackend,
    LLMProvider,
    TraceSink,
)
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
    correct_form_present,
    diagnose,
    select_intervention,
    select_intervention_from_hypotheses,
)
from whymath_backend.l4.misconception.catalog import CATALOG, CATALOG_BY_ID
from whymath_backend.l4.misconception.evidence_store import log_evidence
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.hypothesis_store import curate_hypothesis
from whymath_backend.l4.misconception.judge import JudgeProtocol, LLMJudge, judge_filter
from whymath_backend.l4.misconception.judge_seam import L3JudgeSeam
from whymath_backend.l4.misconception.match_gate import apply_match_quality_gate
from whymath_backend.l4.misconception.probe_selection import is_exploration_turn
from whymath_backend.l4.misconception.shadow import (
    _spawn,
    observe_misconception_judge_shadow,
    observe_misconception_shadow,
)
from whymath_backend.l4.misconception.warmstart import assemble_warmstart_probe_hints
from whymath_backend.l4.prerequisite_coaching import recommend_prerequisite_coaching
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.dialogue import DialogueTurn as DialogueTurnSchema
from whymath_backend.schema.enums import ContentType, EventType, Persona, StepType, TurnRole
from whymath_backend.schema.event_data_contract import build_event_data

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

# WH-1 §2.3 — clean하게 검증된 풀이 1턴이 *현재 의심* 오개념에 주는 *약한* 반박 가중(−1 polarity).
# net_support=Σ(polarity×weight)라, 강한 실제 오개념(다회 +1·weight≤1.0 누적)은 한 turn(−0.5)으로
# 죽지 않고 약·stale 의심만 누적으로 archived된다(낙인 방지하며 실신호 보존·CLAUDE.md #1). 0.5는
# KPI 튜닝 대상(#266 신뢰 floor 0.65 선례처럼 상수로 노출해 A/B 조정 여지를 남긴다).
_REFUTE_WEIGHT: float = 0.5

# WH-1 §2.3 정밀 귀속 — 검증 풀이가 *특정 오개념의 정정 형태*(`correct_form`)를 실제로 보일 때 주는
# *강한* 반박 가중. 막연한 clean 작업(0.5)과 달리 "학생이 M의 올바른 형태를 직접 보였다"는 정밀
# 모순이라 만점 매치(weight 1.0)와 대칭되는 강도를 준다 — 단발 정정이 confident 단일 매치(+1.0)를
# *즉시* 지우진 않고(net 0·archived 아님) 반복·decay와 합쳐 죽인다(신호 보존). 1.0은 KPI 튜닝 대상.
_REFUTE_STRONG_WEIGHT: float = 1.0


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
    mode: Literal["suneung"] | None = Field(
        default=None,
        description=(
            "S3-03 응용 모드 태그 — 'suneung'이면 이 코칭 턴이 *수능 세션*의 일부임을 표식한다"
            "(`GET /me/next-problem?mode=suneung` 값 공간과 정합). 스테이트풀 세션(세션 생성·턴 "
            "추가)에서 검산/힌트 `attempt_event.event_data`에 실려 mode-scoped 측정을 가능하게 "
            "한다(수능 세션 식별). **None(기본)이면 기존 동작 완전 불변(회귀 0)** — 이벤트 mode "
            "태그가 None이라 mode-agnostic 집계 그대로. stateless `/v1/coach`는 이벤트를 적재하지 "
            "않아 이 값이 소비되지 않는다(무해). 멀티턴은 클라가 매 턴 같은 mode를 실어 보낸다."
        ),
    )
    persona: Persona | None = Field(
        default=None,
        description=(
            "S3-03 대상 페르소나 태그(선택) — 수능 모드 세션의 응시 페르소나(A/B/C 등). 제공 시 "
            "검산/힌트 이벤트에 `persona` 값 문자열로 실려 후속 per-persona 측정을 돕는다. None"
            "(기본)이면 미태깅(기존 동작 불변). `mode`와 독립적으로 실린다."
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
    """`/v1/coach/sessions` 요청 — `CoachRequest` + 선택적 problem_id(FK).

    S3-03: `mode`·`persona`(응용 모드/페르소나 태그)는 `CoachRequest`에서 상속한다 — 세션 생성
    턴의 검산/힌트 이벤트에 실려 수능 세션을 측정 계층에서 식별 가능하게 한다(멀티턴은 turns
    요청에도 같은 값을 실어 보낸다).
    """

    problem_id: uuid.UUID | None = Field(
        default=None,
        description="이 대화가 속한 문제(있으면 dialogue.problem_id로 영속·없으면 NULL).",
    )


# WH-1 2단계 §8.4 슬라이스 3: 활성 가설 세트 노출 필드 설명(SessionCreateResponse·
# TurnAppendResponse 공통). stateless `CoachResponse`에는 *싣지 않는다* — stateless 경로는
# DB가 없어 가설을 영속·누적할 수 없기 때문(슬라이스 3 결선은 세션 엔드포인트 한정).
_ACTIVE_HYPOTHESES_DESC = (
    "이 학생의 *누적·감쇠된* 활성 오개념 가설 세트(confidence 내림차순). 매 턴 매칭(증거)으로 "
    "갱신·영속되며, 증거가 끊긴 가설은 감쇠하고 임계 미만이면 가지치기된다. 각 항목은 *확정 "
    "오개념이 아니라 후보*다(낙인 금지 — `misconceptions`와 동형 노출). 학생 *본인*의 가설만 "
    "노출되며(ConsentedUser 게이트 통과), 민감정보 평문 저장·동의는 저장/동의 계층(암호화·"
    "미들웨어·PIPA 권한 매트릭스) 책임이다. 매칭이 없으면 빈 리스트. select_focus 기반 개입 "
    "변경·evidence_links(증거 연결)·진단 일치율 게이트는 후속 슬라이스(이번은 per-turn 영속+노출)."
)


class SessionCreateResponse(CoachResponse):
    """`/v1/coach/sessions` 응답 — `CoachResponse` + 영속된 dialogue/turn ID + 활성 가설 세트."""

    dialogue_id: uuid.UUID = Field(description="새로 생성된 대화 PK.")
    student_turn_id: uuid.UUID = Field(description="학생 발화 턴 PK(turn_order=1).")
    assistant_turn_id: uuid.UUID = Field(
        description="AI 결정 턴 PK(turn_order=2, content=decision.prompt)."
    )
    active_hypotheses: list[MisconceptionHypothesis] = Field(
        default_factory=list,
        description=_ACTIVE_HYPOTHESES_DESC,
    )
    wh1_turn_index: int = Field(
        ge=1, description="이 교환의 WH-1 턴 번호(1-기반·세션 누적·ε-탐색 카운터·§2.2). 생성=1."
    )
    wh1_exploration_turn: bool = Field(
        description="이 턴이 ε-탐색 강제 턴인지(기본 5턴마다·활성 세트 밖 프로브 의무·§2.2 규칙2)."
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
    active_hypotheses: list[MisconceptionHypothesis] = Field(
        default_factory=list,
        description=_ACTIVE_HYPOTHESES_DESC,
    )
    wh1_turn_index: int = Field(
        ge=1, description="이 교환의 WH-1 턴 번호(1-기반·세션 누적·ε-탐색 카운터·§2.2)."
    )
    wh1_exploration_turn: bool = Field(
        description="이 턴이 ε-탐색 강제 턴인지(기본 5턴마다·활성 세트 밖 프로브 의무·§2.2 규칙2)."
    )


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
    misconception_hypotheses: list[MisconceptionHypothesis] | None = None,
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

    `misconception_hypotheses`(누적 활성 가설 세트·confidence 내림차순)를 주입받으면 `decide`로
    thread해 *소크라테스 카테고리*를 정밀화한다 — 학생이 머무르며 막혀 있고 명시 신호가 없을 때
    고신뢰+최근 가설이면 ASSUMPTION(가정 표면화). **미주입(기본 None)이면 현행 비트동일**
    (stateless `/v1/coach`·sync 직접호출). 세션/턴 핸들러가 `_apply_hypotheses` 반환 세트를 넘긴다
    (개입 채널 `_intervention_from_hypotheses_or`와 *같은* post-apply 세트·단일 진실원천).
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
    decision = _coach.decide(
        body.student_input,
        body.polya_state,
        mastery_level=level,
        misconception_hypotheses=misconception_hypotheses,
    )
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
    # WH-1 1단계 잔여(hint 점층 결선): Polya 결정이 이미 계산한 hint_level(decide_hint_level·
    # 턴/좌절/숙달 기반)을 solution 코칭에 thread한다 — *단계 자가검산* 발화가 3·4단계에서 과정
    # 재구성 비계로 점층된다(정답/"틀렸다" 미포함·답 미루기). 재계산 0(L4 decide_hint_level 단일
    # 산정처)·verify_steps 아니거나 1·2단계면 발화 불변(하위호환).
    sol = recommend_coaching_for_solution(
        solution_text,
        effective_bkt,
        server_theta,
        problem_id=problem_id,
        expected_answer=expected_answer,
        solution_steps=body.solution_steps,
        solution_step_types=body.solution_step_types,
        ocr_confidence=body.ocr_confidence,
        hint_level=decision.hint_level,
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


class _JudgeSeamDeps(NamedTuple):
    """judge seam에 주입할 *앱 공유* L3 인프라(관측·provider·캐시) 묶음.

    프로덕션에서 `_judge_for_gate`가 이 셋을 `L3JudgeSeam`에 넘겨, judge LLM 호출의
    usage/cost가 앱 전역 `LangfuseSink`로 흐르고(관측 누락 해소) provider·캐시도 앱 전역과
    공유되게 한다(매 호출 새 `OllamaProvider`·`InMemoryCache` 생성 회피). 셋 다 `None`이면
    `L3JudgeSeam`이 자기 기본값(throwaway trace/새 provider/새 cache)으로 폴백한다 — app.state가
    없는 경로(단위테스트 등) 하위호환.
    """

    provider: LLMProvider | None
    cache: CacheBackend | None
    trace: TraceSink | None


def _get_judge_seam_deps(request: Request) -> _JudgeSeamDeps:
    """app.state의 공유 provider/cache/trace를 judge seam 주입용으로 묶는 얇은 의존성.

    `create_app`이 `app.state`에 1회 올린 공유 인스턴스(`CompositeProvider`·`RedisCache`·
    `LangfuseSink`)를 요청마다 조회한다(DB 세션과 달리 앱 수명 공유라 `app.py:296-298` 패턴과
    동형). 키가 없으면(app.state 미구성) `None` — `L3JudgeSeam` 기본값 폴백이라 안전. 이
    조회는 *부작용 0*이며, judge 게이트 off 경로에서도 주입값이 소비되지 않으므로 현행 동작 불변.
    """

    return _JudgeSeamDeps(
        provider=getattr(request.app.state, _PROVIDER_KEY, None),
        cache=getattr(request.app.state, _CACHE_KEY, None),
        trace=getattr(request.app.state, _TRACE_KEY, None),
    )


JudgeSeamDeps = Annotated[_JudgeSeamDeps, Depends(_get_judge_seam_deps)]


def _judge_for_gate(
    *,
    provider: LLMProvider | None = None,
    cache: CacheBackend | None = None,
    trace: TraceSink | None = None,
) -> JudgeProtocol:
    """coach 오개념 게이트용 judge 좌석 — 기본 L3 백킹(라우터 경유·로컬 FAST·never-break).

    슬108 플래그(`misconception_judge_enabled`)가 on일 때만 `_gate`가 호출한다. 기본은 L3 백킹
    seam(`L3JudgeSeam`→`l3.pipeline`·로컬 FAST·Langfuse·캐시)을 문 `LLMJudge`다 — "LLM 라우터
    경유·로컬 우선·추적" 절대원칙을 자동 충족(직접 호출 0).

    provider/cache/trace는 L5(엔드포인트→`_compute_matches`)가 app.state 공유 인스턴스
    (`CompositeProvider`·`RedisCache`·`LangfuseSink`)를 주입한다 — 그래야 judge의 usage/cost가
    실제 Langfuse 관측으로 흐르고 캐시도 공유된다(계층 경계: L5가 L3 인프라를 L4 seam에 주입,
    L4 코어는 비용을 모른 채 유지). 미주입(모두 None)이면 `L3JudgeSeam` 기본값 폴백(하위호환).
    테스트는 이 팩토리를 monkeypatch해 `FakeJudge`(결정론·라이브 0)를 주입한다(좌석 주입점·
    hermetic) — 대체물은 kwargs를 받아 무시한다(`lambda **_: judge`). 플래그 off면 호출되지 않아
    provider/cache 구성도 0(현행 비트동일).
    """
    return LLMJudge(L3JudgeSeam(provider=provider, cache=cache, trace=trace))


async def _compute_matches(
    student_input: str,
    *,
    ocr_confidence: float | None = None,
    judge_deps: _JudgeSeamDeps | None = None,
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

    def _make_judge() -> JudgeProtocol:
        # judge 좌석 생성 — 엔드포인트가 넘긴 app.state 공유 provider/cache/trace를 주입한다
        # (미주입이면 `L3JudgeSeam` 기본값 폴백·하위호환). `_judge_for_gate`를 *모듈 전역*으로
        # 참조하므로 테스트의 monkeypatch(`coach._judge_for_gate`)가 그대로 적용된다(좌석 유지).
        if judge_deps is None:
            return _judge_for_gate()
        return _judge_for_gate(
            provider=judge_deps.provider,
            cache=judge_deps.cache,
            trace=judge_deps.trace,
        )

    async def _gate(candidates: list[MisconceptionMatch]) -> _MatchOutcome:
        # §3.3 품질 게이트 후처리 — 세 모드 공통 출구. 게이트를 *한 번만* 적용해 결과 전체를 받고
        # matches+플래그를 함께 반환한다(직전엔 .matches만 반환해 플래그를 드롭했음). 게이트 ①은
        # top-1<floor면 후보를 비우고(억지 매칭 금지) no_confident_match=True를, 게이트 ②는 OCR
        # confidence<0.8(None이면 dormant)면 low_quality=True를 세운다(매칭은 유지). 게이트는
        # *재정렬·변형 없이* 통과분만 그대로 통과시킨다(`combine_diagnoses` 순서 보존).
        # 슬108 결선: judge 게이트 on이면 품질 게이트 *이전*에 방향 판별 필터를 적용한다 —
        # NOT_EXPRESSES(올바름/다른 말)만 제거하고 예·불확실은 유지(recall 보존)해, 품질 게이트의
        # no_confident_match가 *judge 통과 후* top-1을 반영하게 한다. 세 모드(off/shadow/on) 공통
        # 출구라 게이트가 한 곳에 일관 적용된다. off면 좌석 호출 0·LLM 0·현행 비트동일.
        if candidates and get_settings().misconception_judge_enabled:
            candidates = await judge_filter(candidates, student_input, judge=_make_judge())
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
        return await _gate(substr[:_DEFAULT_TOP_K])
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
        return await _gate(substr[:_DEFAULT_TOP_K])
    if mode == "shadow":
        # shadow — 노출은 substring 그대로(off 비트동일)·substring↔semantic 불일치만 로깅한다
        # (비노출·실 분포 플립 근거 수집·slice 111). 학생 원문은 로그에 안 담는다(프라이버시).
        # shadow 로깅은 *게이트 전* 원본 substr/sem으로 수행(게이트가 비교 분포를 왜곡하지 않게).
        observe_misconception_shadow(substr, sem)
        # G1: judge-shadow 토글이 켜져 있고 의미 후보가 있으면, 그 후보에 judge를 돌려 *걸러질
        # 결과*(would-be removed/kept)를 무노출로 로깅한다(04b Phase 1·합성↔실 갭 검증). judge는
        # LLM(수 초)이라 *비차단*(_spawn=create_task)으로 띄우고 즉시 반환한다 — 응답 경로는 judge를
        # await하지 않는다(노출 무지연). `_make_judge()`(공유 provider/cache/trace 주입 좌석)를
        # spawn 직전 만들어 인자로 넘긴다(monkeypatch 타이밍 호환). 레코드엔 학생 원문·judge
        # reason 미저장(미성년 PII).
        if get_settings().misconception_judge_shadow and sem:
            _spawn(
                observe_misconception_judge_shadow(
                    sem,
                    student_input,
                    judge=_make_judge(),
                    feed_threshold=get_settings().misconception_semantic_threshold,
                    judge_routing=get_settings().misconception_judge_routing,
                )
            )
        return await _gate(substr[:_DEFAULT_TOP_K])
    # on — substring 아래에 semantic-only 후보를 결합해 *노출*(substring 우선·재정렬 없음).
    return await _gate(combine_diagnoses(substr, sem, top_k=_DEFAULT_TOP_K))


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
    mode: str | None = None,
    persona: str | None = None,
) -> bool | None:
    """학생 풀이 검산(verify) 결과를 `attempt_event`(검산결과)로 1행 적재 + 통과여부 반환.

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

    **반환(반박 증거 결선용)**: 풀이 제출 턴이 아니면 `None`(검산 신호 없음)·clean 검증이면 `True`·
    거짓 수치관계 적발이면 `False`. 핸들러가 이 값으로 `_log_refutation_evidence`(clean→약한 −1)를
    구동한다 — 적재(부수효과)는 불변이고 *통과여부 신호만* 추가 노출한다(기존 호출자는 반환 무시·
    하위호환).

    **S3-03 mode 태깅**: `mode`·`persona`(선택)를 event_data에 실어 이 검산결과가 어느 응용 모드/
    페르소나 세션에서 나왔는지 표식한다(수능 세션 식별·측정 계층 도달). 둘 다 None(기본)이면
    mode-agnostic으로 기존 event_data 모양과 *비트동일*은 아니지만(계약이 mode/persona=None 키를
    항상 채움) 의미상 완전 불변이다 — 측정 필터가 None을 mode 미지정으로 취급(회귀 0).
    """
    solution_text = student_solution or ""
    if not solution_text.strip():
        return None  # 풀이 제출 턴이 아님(빈/대화 턴) → 적재 안 함(false-pass 방지)·검산 신호 없음.

    signal = validate_response(arithmetic_validator(), solution_text)
    passed = signal is None  # None=거짓관계 미적발(통과)·아니면 적발(실패).

    event = AttemptEventORM(
        event_at=datetime.now(timezone.utc),
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        event_type=EventType.검산결과,
        event_data=build_event_data(
            EventType.검산결과,
            passed=passed,
            error_kind=(signal.kind if signal else None),
            mode=mode,
            persona=persona,
        ),
    )
    session.add(event)  # commit은 핸들러가 — 같은 트랜잭션에 합류(별도 commit 금지).
    return passed  # clean→True·거짓관계 적발→False(핸들러의 반박 증거 결선이 소비).


async def _log_hint_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    problem_id: uuid.UUID | None,
    attempt_id: uuid.UUID | None,
    hint_level: int | None,
    mode: str | None = None,
    persona: str | None = None,
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

    **S3-03 mode 태깅**: `_log_verify_event`와 동형으로 `mode`·`persona`(선택)를 event_data에
    실어 ⑤(도움 감소)·⑧(도달 깊이)의 mode-scoped 집계를 가능하게 한다. None(기본)이면 미태깅.
    """
    if hint_level is None:
        return  # 힌트 레벨 없음(이론적 경계) → 적재 안 함(날조 회피).

    event = AttemptEventORM(
        event_at=datetime.now(timezone.utc),
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        event_type=EventType.힌트제공,
        event_data=build_event_data(
            EventType.힌트제공, hint_level=hint_level, mode=mode, persona=persona
        ),
    )
    session.add(event)  # commit은 핸들러가 — 같은 트랜잭션에 합류(별도 commit 금지).


async def _apply_hypotheses(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    matches: list[MisconceptionMatch],
) -> list[MisconceptionHypothesis]:
    """이번 턴 매칭(증거)으로 학생 활성 가설 세트를 1턴 *큐레이션*·영속해 반환 — coach 세션/턴 전용.

    WH-1 2단계 §8.4 슬라이스 3 *결선* 좌석. #191 순수 로직·#192 저장소(`curate_hypothesis`)를
    *재사용만* 한다(재구현 0). 핸들러의 `session`/트랜잭션에 합류하고 `curate_hypothesis`가 flush만
    하므로(commit은 핸들러), 가설 갱신이 dialogue/turn 쓰기와 *같은 트랜잭션*에서 원자적으로
    영속된다(별도 commit 없음). 반환 가설은 응답 `active_hypotheses`로 노출된다(매칭 없으면
    빈 리스트 — 감쇠·가지치기 후 빈 세트면 그대로).

    **하네스 동치(parity)**: `apply_matches`(매치만)가 아니라 §3 도구4 `curate_hypothesis`를 쓴다
    — `evidence_links` 순지지도(`net_support`)가 *음수*(반박 우세)인 가설은 archived하고(R4 확증
    편향·거짓 낙인 방지) 최대 5개 활성으로 캡한다(§2.2 큐레이션 규칙·초점). 같은 `student_id` 증거
    그래프를 하네스(`harness/wh1_session.py`)와 공유하므로 *단일 진실원천*이다 — 하네스가 반박한
    오개념을 라이브도 동일 제외. 반박 증거 없고 활성 ≤5면 `apply_matches`와 결과 동일(하위호환).

    `user_id` 가드: `ConsentedUser` 인증 게이트라 실제론 항상 채워지지만, 방어적으로 None이면
    가설을 적용·영속하지 않고 빈 리스트를 반환한다(`curate_hypothesis`는 per-student·user_id 필수).

    범위(정직): per-turn *영속+노출* + 개입 발화 결선까지다. 갱신된 가설 세트는 바로 아래
    `_intervention_from_hypotheses_or`로 *개입 발화*도 구동한다(select_focus 기반 intervention —
    이 슬라이스에서 결선). 라이브 경로 증거 *적재*(`log_evidence`)는 아직 하네스 몫이라 net_support
    는 하네스가 쌓은 증거를 *소비*만 한다(라이브 자가 적재는 후속). 진단-실제 *일치율* 게이트·도구
    루프 오케스트레이션도 후속 슬라이스다.
    """
    if user_id is None:
        return []  # 인증 게이트라 도달 안 함(방어 가드 — curate_hypothesis는 user_id 필수).
    return await curate_hypothesis(session, student_id=user_id, matches=matches)


async def _log_match_evidence(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    student_id: uuid.UUID | None,
    matches: list[MisconceptionMatch],
) -> None:
    """이번 턴 *확정 매치*를 +1 지지 증거로 `evidence_links`에 적재한다(§2.3 생산측 좌석).

    #268이 라이브 coach를 증거 그래프의 *소비측*(`curate_hypothesis`→`net_support<0` 반박)으로
    결선했다면, 본 헬퍼는 그 짝인 ***생산측***이다 — 하네스(`run_persisted_turn`)의 `log_evidence`
    영속 패턴을 결정론 규칙으로 모사한다(재구현 0). `outcome.matches`는 이미 신뢰 게이트
    (top-1<0.65→후보 비움)를 통과한 *확정 진단*이라 추가 floor 불요·match당 +1(지지·진단이 오개념
    신호를 드러냄)·`weight=confidence`(net_support 가중).

    **순서(비순환)**: 호출자는 본 헬퍼를 `_apply_hypotheses`(=`curate_hypothesis`·*직전까지* 누적된
    net_support로 반박 판정) **뒤에** 둔다 — 이번 턴 지지가 같은 턴의 반박을 순환적으로 막지 않고
    *미래 턴* net_support에만 반영된다(소비는 과거 증거·생산은 미래 증거).

    **짝**: −1 *반박* 생산은 `_log_refutation_evidence`(바로 아래)가 담당한다 — clean 검증 풀이가
    의심 오개념을 약하게 반박. no-match 게이트로 둘은 *상호배타*(한 턴은 지지 또는 반박 중 하나).

    `log_evidence`는 주입 `session`에 합류·flush만(commit은 핸들러). `student_id` None이면 가드(인증
    게이트라 미도달)·빈 matches면 no-op. `session_id`는 dialogue UUID(느슨참조·FK 아님).
    """
    if student_id is None:
        return  # 인증 게이트라 도달 안 함(방어 가드 — log_evidence는 student_id 필수).
    for match in matches:
        await log_evidence(
            session,
            session_id=session_id,
            student_id=student_id,
            misconception_id=match.misconception.id,
            polarity=1,  # 매치 = 오개념 *지지* 증거(진단이 오개념 신호를 드러냄).
            weight=match.confidence,
        )


async def _log_refutation_evidence(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    student_id: uuid.UUID | None,
    passed: bool | None,
    matches: list[MisconceptionMatch],
    active_hypotheses: list[MisconceptionHypothesis],
    solution_text: str | None,
) -> None:
    """clean하게 검증된 풀이 1턴을 *현재 의심* 오개념에 대한 −1 *반박* 증거로 적재(§2.3 짝).

    #269가 +1 *지지* 생산(`_log_match_evidence`)을 결선했으나 −1 *반박* 생산이 없어, #268의
    `curate_hypothesis` archived 가드(`net_support<0`)가 라이브-단독 학생에겐 발동하지 못했다
    (net_support≥0). 본 헬퍼가 그 −1 좌석을 *보수적*으로 결선해 evidence 아크를 닫는다 — 04a §2.3
    "verify가 가설 *예측*과 모순되면 −1"의 결정론 조작화.

    **규칙(보수)**: ① 풀이 제출 턴이 clean 검증(`passed is True`)이고 ② 이번 턴 *확정 매치가 없을*
    때만(`not matches`) ③ *현재 active 가설 각각*에 `polarity=-1·weight=_REFUTE_WEIGHT(0.5)`를 적재.
      - **passed 게이트**: 도구 검증된 올바른 풀이 = "학생이 (오류 유발) 오개념을 가졌다"는 예측과
        모순(약한 반대 증거). `passed is None`(풀이 아님)·`False`(거짓관계 적발)은 반박 안 함 — `is
        True` 명시 비교로 None/False를 한 번에 배제(현재 슬라이스는 −1만·verify-fail→+1은 후속).
      - **no-match 게이트(정합·핵심)**: 이번 턴이 오개념을 *매치*했으면(`_log_match_evidence`가 +1)
        반박 안 함 → 한 턴은 지지(매치) 또는 반박(clean 정답) *둘 중 하나*(같은 턴 모순 적재 차단·
        매치+정답 동시 턴은 +1 우선).
      - **tier 가중(정밀 귀속)**: active 가설 각각에 −1을 적재하되 *증거 강도로 가중을 tier*한다.
        풀이에 그 오개념의 *정정 형태*(`correct_form`)가 검출되면(`correct_form_present`) `_REFUTE_
        STRONG_WEIGHT`(1.0·정밀: "학생이 M의 올바른 형태를 직접 보임"), 아니면 `_REFUTE_WEIGHT`
        (0.5·막연한 clean 작업). 대상은 curate가 ≤5·recency로 좁힌 *현재* 의심(active_hypotheses)뿐
        — 오래된 무관 오개념은 이미 decay/prune. 과거 한계(verify 신호는 *일반* 계산정합이라 특정
        오개념 귀속 불가·'올바른 형태' 부재)를 `correct_form`(identity-shaped에 부여) 검출로 *부분
        해소* — 정정이 검출되는 오개념은 정밀(강), 나머지는 보수(약). 강·약 모두 낙인
        방지(−1 방향)·실신호 보존(강 1.0도 만점 단일 매치를 *즉시* 죽이진 않음). domain 스코핑은
        데이터 부재로 보류(후속·NOT).

    **순서(생산=미래)**: `_log_match_evidence`와 동일하게 `_apply_hypotheses`(curate·*직전까지*
    net_support 소비) **뒤에** 둔다 — 이번 턴 −1은 같은 턴 curation을 바꾸지 않고 *미래*
    net_support에만 반영(소비=과거·생산=미래). decay(자연 감쇠)에 더해 *능동적 clearing*을 준다.

    `log_evidence`는 주입 `session`에 합류·flush만(commit은 핸들러). `student_id` None(인증 게이트라
    미도달)·게이트 미충족·빈 active면 no-op. `session_id`는 dialogue UUID(느슨참조·FK 아님).
    """
    if student_id is None:
        return  # 인증 게이트라 도달 안 함(방어 가드 — log_evidence는 student_id 필수).
    if passed is not True:
        return  # clean 검증(통과)만 반박 — None(풀이 아님)·False(거짓관계 적발)은 제외.
    if matches:
        return  # no-match 게이트 — 이번 턴이 매치(+1 지지)면 같은 턴 반박 안 함(모순 차단).
    text = solution_text or ""  # passed is True ⟹ student_solution 비어있지 않음(verify 게이트).
    for hyp in active_hypotheses:
        # 정정 형태 검출 시 정밀·강한 반박(1.0), 아니면 막연한 clean 작업의 약한 반박(0.5).
        entry = CATALOG_BY_ID.get(hyp.misconception_id)
        strong = entry is not None and correct_form_present(entry, text)
        await log_evidence(
            session,
            session_id=session_id,
            student_id=student_id,
            misconception_id=hyp.misconception_id,
            polarity=-1,  # clean 정답 = 의심 오개념 *반박* 증거(#1 낙인 방지).
            weight=_REFUTE_STRONG_WEIGHT if strong else _REFUTE_WEIGHT,
        )


def _wh1_turn_state(total_turns_before: int) -> tuple[int, bool]:
    """이 교환(student↔AI)의 WH-1 턴 번호 + ε-탐색 턴 여부 — 멀티턴 연속성 카운터(§2.2).

    `total_turns_before`(이번 턴 추가 *전* `dialogue.total_turns` — 교환당 +2라 짝수)에서 1-기반
    WH-1 턴 번호를 유도한다(create=0→1·n번째 append=2n→n+1). `is_exploration_turn`으로 ε-탐색
    주기(기본 5턴마다)도 함께 표식한다 — 설계 §2.2 "하네스가 카운터를 관리"를 *세션 상태(dialogue)*
    에서 충족한다. 활성 가설 세트(웜 스타트로 복원·`active_hypotheses`)와 함께 노출돼 멀티턴 연속성
    (직전 누적 상태 위에 이번 턴 진행)을 클라이언트·후속 도구 루프가 관측할 수 있게 한다.
    """
    turn_index = total_turns_before // 2 + 1
    return turn_index, is_exploration_turn(turn_index)


def _intervention_from_hypotheses_or(
    active_hypotheses: list[MisconceptionHypothesis],
    fallback: InterventionDecision | None,
) -> InterventionDecision | None:
    """개입 발화를 *누적 가설 세트* 기준으로 재결정 — WH-1 2단계 §8.4 *결선* 좌석.

    `_apply_hypotheses` docstring이 예고한 "select_focus 기반 intervention 변경(ε 탐색→개입
    발화)"의 실현. 단일 턴 raw 매치(`fallback` = `_build_response_payload`의 substring-우선
    매치 기반 결정)가 아니라, 시간 감쇠·강화로 **누적된 활성 가설 세트**가 개입을 구동하게
    한다(#191 `select_focus`·`select_intervention_from_hypotheses` 재사용·재구현 0).

    *폴백 보존*(회귀 0): 가설 세트가 결정을 못 내면(빈 세트·focus<0.5 보류·느슨 id) `fallback`을
    그대로 둔다. **턴1**은 가설이 이번 턴 매치로 막 시드되어(감쇠 전) 신뢰도=매치 신뢰도이므로,
    최상위 가설이 raw 매치 1위와 같으면 결과가 비트동일하다. 차이는 *멀티턴 누적*(강화로 반례
    임계 돌파·감쇠로 보류 전환) 또는 가설 세트가 substring-우선과 다른 1위를 가질 때만 난다 —
    그게 정확히 WH-1이 의도한 "상태(누적 증거)가 개입을 결정한다"이다. stateless `/v1/coach`는
    가설 세트가 없어 *호출하지 않는다*(raw 매치 유지).
    """
    return select_intervention_from_hypotheses(active_hypotheses) or fallback


def _build_dialogue_turn(
    schema: DialogueTurnSchema, cipher: SupportsEnvelope | None
) -> DialogueTurnORM:
    """감사상환 #2: 스키마 → 대화 턴 ORM(본문 봉투 암호화 적용) — 4개 write 경로의 단일 좌석.

    순수 seam(`from_schema`)엔 cipher를 주입하지 않고(device store가 handler 층에서 암호화하는
    선례 미러), 이 *handler/헬퍼 층* 함수가 `content`를 암호화해 저장 표현을 결정한다.
    `encrypt_dialogue_content`가 cipher 유무·content None을 분기: cipher 있으면 content=NULL·
    content_encrypted/content_nonce 세팅(평문 원문 DB 부재), cipher None이면 평문 폴백
    (content=평문·encrypted=None — 조용한 무동작 아닌 *명시* 폴백·CI/기존 배포 무영향).
    create_session·append_turns의 학생/AI 턴 4곳이 모두 이 헬퍼를 거쳐 중복·누락을 없앤다.
    """
    turn = DialogueTurnORM.from_schema(schema)
    content_plain, content_encrypted, content_nonce = encrypt_dialogue_content(
        cipher, schema.content
    )
    turn.content = content_plain
    turn.content_encrypted = content_encrypted
    turn.content_nonce = content_nonce
    return turn


@router.post(
    "/coach",
    response_model=CoachResponse,
    summary="L4 교수학 통합 결정(stateless)",
    dependencies=[RateLimitedTripleWrite],
)
async def coach_decide(
    body: CoachRequest,
    user: ConsentedUser,
    judge_deps: JudgeSeamDeps,
) -> CoachResponse:
    """학생 발화 → Polya 결정 + 오개념 진단 + LTHC 조정안을 *한 번에* 반환.

    *DB 무접근* — 영속이 필요하면 `/v1/coach/sessions`를 호출. `user`는 인증 게이트만.
    """
    _ = user.user_id  # 인증 게이트 통과 확인용(stateless라 user 데이터 미사용)

    # slice 106: 오개념 후보를 비블로킹 결합(게이트 off면 substring만)으로 미리 계산해 주입.
    # WH-1: ocr_confidence를 게이트로 thread하고(§3.3 게이트 ②), 게이트 플래그를 응답에 노출한다.
    outcome = await _compute_matches(
        body.student_input, ocr_confidence=body.ocr_confidence, judge_deps=judge_deps
    )
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
    judge_deps: JudgeSeamDeps,
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
    outcome = await _compute_matches(
        body.student_input, ocr_confidence=body.ocr_confidence, judge_deps=judge_deps
    )
    # WH-1 2단계 §8.4 슬라이스 3 — 이번 턴 매칭(증거)으로 학생 활성 가설 세트를 큐레이션·영속한다
    # (#191 순수 로직 + #192 저장소 재사용·재구현 0). 같은 `session`/같은 트랜잭션에 합류하며
    # curate_hypothesis(증거 반박·캡)는 flush만 하고 commit은 *핸들러의 기존 commit*이 담당(별도 X).
    # `user.user_id`는 ConsentedUser 게이트라 채워지지만, None이면 빈 리스트로 가드(per-student라
    # user_id 필요). 가설은 *후보*일 뿐 확정 오개념 아님(낙인 금지)·학생 본인 데이터만 노출.
    # 결정 *앞에서* 적용한다 — 갱신된 가설 세트를 _build_response_payload로 넘겨 소크라테스
    # 카테고리(ASSUMPTION 가정 표면화)까지 구동(개입 채널과 동일한 post-apply 세트·단일 진실원천).
    active_hypotheses = await _apply_hypotheses(session, user.user_id, outcome.matches)
    # S1-b: WH-1 하네스 *shadow 관측*(비노출·비블로킹·무영속). 플래그 ON일 때만 하네스를 병렬로
    # 돌려 '하네스가 어떤 도구를 골랐는지·verify 판정이 무엇인지'만 서버 로그로 남긴다 — 학생 응답은
    # 아래 결정론 경로(`_build_response_payload`) 그대로다(노출 불변). judge shadow의 `_spawn`
    # (fire-and-forget) 패턴 미러 — 응답 경로는 하네스 도구 루프(수 초)를 await하지 않는다. 플래그
    # OFF(기본)면 spawn 0·기존과 비트동일(완전 되돌리기 가능·04a '측정 없는 도입 없음').
    if get_settings().wh1_harness_shadow_enabled:
        # S1-c: 웜스타트 probe 힌트(outside_mids) 조립 — 진단 시작 시 하네스 탐색 probe가 겨냥할
        # 외부 오개념 후보를 단원 고빈도+atom 확장으로 미리 공급한다(감사 Q5). **진단 probe 타깃팅
        # 전용** — 코칭 context·개입엔 오개념을 preload하지 않는다(reactive 유지·CLAUDE.md). 플래그
        # ON일 때만 호출(OFF면 warmstart 비용 0). warmstart는 조회만이라 실패해도 학생 응답을 깨면
        # 안 되므로 never-break로 감싸 빈 리스트로 폴백한다(가용성 #1≫진단 관측 #6).
        warmstart_mids: list[str] = []
        try:
            warmstart_mids = await assemble_warmstart_probe_hints(
                session,
                problem_id=body.problem_id,
                provider=build_provider(get_settings()),
            )
        except Exception:  # noqa: BLE001 — 웜스타트 실패는 학생 응답을 안 깬다(never-break).
            logger.warning("웜스타트 probe 힌트 조립 실패 — 빈 힌트로 진행", exc_info=True)
        _spawn(
            observe_wh1_harness_shadow(
                # 학생 원문·풀이 단계는 정책의 *사적 필드*로만 주입(S1-a·프롬프트·레코드 미노출).
                student_solution=body.student_solution or body.student_input,
                solution_steps=body.solution_steps or [],
                active_hypotheses=active_hypotheses,
                problem_id=str(body.problem_id) if body.problem_id is not None else None,
                # 웜스타트 outside_mids는 정책 사적 probe 컨텍스트로만(plan_probe 전용).
                warmstart_outside_mids=warmstart_mids,
            )
        )
    decision, matches, intervention, lthc, entry_category, solution_coaching = (
        _build_response_payload(
            body,
            problem_id=body.problem_id,
            expected_answer=expected_answer,
            server_mastery=server_mastery,
            server_theta=server_theta,
            matches=outcome.matches,
            misconception_hypotheses=active_hypotheses,
        )
    )
    intervention = _intervention_from_hypotheses_or(active_hypotheses, intervention)

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

    # 감사상환 #2: 대화 본문 봉투 암호화기(키 미설정 시 None=평문 폴백). 학생/AI 턴 2곳이 동일
    # 헬퍼(`_build_dialogue_turn`)로 content를 암호화 저장(중복 회피).
    content_cipher = build_dialogue_content_cipher(get_settings())
    student_turn = _build_dialogue_turn(
        DialogueTurnSchema(
            dialogue_id=dialogue.dialogue_id,
            turn_order=1,
            spoken_at=now,
            role=TurnRole.student,
            content=body.student_input,
            content_type=ContentType.텍스트,
        ),
        content_cipher,
    )
    assistant_turn = _build_dialogue_turn(
        DialogueTurnSchema(
            dialogue_id=dialogue.dialogue_id,
            turn_order=2,
            spoken_at=now,
            role=TurnRole.assistant,
            content=decision.prompt,
            content_type=ContentType.텍스트,
        ),
        content_cipher,
    )
    session.add_all([student_turn, assistant_turn])
    # S3-03 mode 태깅 — 요청의 응용 모드/페르소나를 event_data에 실을 문자열로 정규화한다.
    # persona는 Persona enum이라 .value(문자열)로 싣는다(둘 다 None이면 미태깅·기존 동작 불변).
    event_persona = body.persona.value if body.persona is not None else None
    # WH-1 지표 ① 적재 — 풀이 제출(student_solution 비어있지 않음)이면 검산 결과를 attempt_event로
    # 기록(같은 트랜잭션 합류·별도 commit 없음). stateless /v1/coach는 미적재(DB 무접근 계약).
    # S3-03: body.mode·persona를 실어 수능 세션 검산결과를 측정 계층에서 식별 가능하게 한다.
    verify_passed = await _log_verify_event(
        session,
        user_id=user.user_id,
        problem_id=body.problem_id,
        attempt_id=dialogue.attempt_id,
        student_solution=body.student_solution,
        mode=body.mode,
        persona=event_persona,
    )
    # WH-1 지표 ⑤ 적재 — 이미 계산된 decision.hint_level(supply·1~4)을 그대로 기록(재계산 0·
    # _build_response_payload 불변). verify 적재 바로 옆·같은 트랜잭션 합류(별도 commit 없음).
    # S3-03: verify와 동일 mode·persona 태그를 실어 ⑤⑧ mode-scoped 집계를 가능하게 한다.
    await _log_hint_event(
        session,
        user_id=user.user_id,
        problem_id=body.problem_id,
        attempt_id=dialogue.attempt_id,
        hint_level=decision.hint_level,
        mode=body.mode,
        persona=event_persona,
    )
    # WH-1 §2.3 — 이번 턴 확정 매치를 +1 지지 증거로 적재(#268 소비측의 짝·생산측 좌석). curate
    # *뒤*에 둬 이번 턴 지지가 같은 턴 반박을 순환 차단 안 함(미래 net_support 반영). 같은 트랜잭션.
    await _log_match_evidence(
        session,
        session_id=dialogue.dialogue_id,
        student_id=user.user_id,
        matches=outcome.matches,
    )
    # WH-1 §2.3 짝 — clean 검증 풀이(no-match)면 현재 active 가설을 약하게 −1 반박(낙인 방지·#268
    # archived 가드 라이브 발동). +1 생산 뒤·no-match 게이트로 한 턴은 지지/반박 중 하나(상호배타).
    await _log_refutation_evidence(
        session,
        session_id=dialogue.dialogue_id,
        student_id=user.user_id,
        passed=verify_passed,
        matches=outcome.matches,
        active_hypotheses=active_hypotheses,
        solution_text=body.student_solution,
    )
    await session.commit()

    # WH-1 멀티턴 연속성 — 새 dialogue라 직전 total_turns=0 → 첫 교환은 턴 1(§2.2 ε 카운터).
    wh1_turn_index, wh1_exploration = _wh1_turn_state(0)
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
        active_hypotheses=active_hypotheses,
        dialogue_id=dialogue.dialogue_id,
        student_turn_id=student_turn.turn_id,
        assistant_turn_id=assistant_turn.turn_id,
        wh1_turn_index=wh1_turn_index,
        wh1_exploration_turn=wh1_exploration,
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
    judge_deps: JudgeSeamDeps,
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
    outcome = await _compute_matches(
        body.student_input, ocr_confidence=body.ocr_confidence, judge_deps=judge_deps
    )
    # WH-1 2단계 §8.4 슬라이스 3 — create_session과 동형. 이번 턴 매칭으로 *기존* 활성 가설
    # 세트를 큐레이션(감쇠/강화·누적·증거 반박·캡)·영속한다(트랜잭션 합류·별도 commit 없음·재사용).
    # 멀티턴이라 직전 턴들의 가설 위에 누적되어 감쇠·강화가 실제로 가동된다(2단계 메커니즘).
    # 결정 *앞에서* 적용한다 — 누적 가설 세트를 _build_response_payload로 넘겨 소크라테스 카테고리
    # (ASSUMPTION 가정 표면화)까지 구동(개입 채널과 동일한 post-apply 세트·단일 진실원천).
    active_hypotheses = await _apply_hypotheses(session, user.user_id, outcome.matches)
    # S1-11(flip-없는 수렴 잔여): 멀티턴에도 WH-1 shadow 관측 배선 — create_session(위 :1191)과
    # 동형. verdict가 실제 발생하는 곳은 멀티턴(풀이 단계 제출)이라, 여기 배선이 없으면 shadow
    # verdict 분포(S1-11 primary 승격 판정의 근거·live_cost 문서 §verdict 분포)가 구조적으로
    # 빈약하다. 플래그 OFF(기본)면 spawn 0·기존과 비트동일 — 학생 응답은 결정론 경로 그대로
    # (노출 불변·비블로킹 _spawn·무영속·04a '측정 없는 도입 없음' 준수). problem_id만 출처가
    # 다르다(create=body·append=dialogue — expected_answer 조회와 동일한 출처 규약).
    if get_settings().wh1_harness_shadow_enabled:
        warmstart_mids_turn: list[str] = []
        try:
            warmstart_mids_turn = await assemble_warmstart_probe_hints(
                session,
                problem_id=dialogue.problem_id,
                provider=build_provider(get_settings()),
            )
        except Exception:  # noqa: BLE001 — 웜스타트 실패는 학생 응답을 안 깬다(never-break).
            logger.warning("웜스타트 probe 힌트 조립 실패(멀티턴) — 빈 힌트로 진행", exc_info=True)
        _spawn(
            observe_wh1_harness_shadow(
                student_solution=body.student_solution or body.student_input,
                solution_steps=body.solution_steps or [],
                active_hypotheses=active_hypotheses,
                # 멀티턴 관측 메타 — dialogue_id로 세션 내 verdict 추이를, turn_index로 턴별
                # 분포를 묶을 수 있게 한다(레코드 스키마 기존 필드·PII 아님·UUID·정수).
                dialogue_id=str(dialogue_id),
                turn_index=(dialogue.total_turns or 0) // 2 + 1,
                problem_id=str(dialogue.problem_id) if dialogue.problem_id is not None else None,
                warmstart_outside_mids=warmstart_mids_turn,
            )
        )
    decision, matches, intervention, lthc, entry_category, solution_coaching = (
        _build_response_payload(
            body,
            problem_id=dialogue.problem_id,
            expected_answer=expected_answer,
            server_mastery=server_mastery,
            server_theta=server_theta,
            matches=outcome.matches,
            misconception_hypotheses=active_hypotheses,
        )
    )
    intervention = _intervention_from_hypotheses_or(active_hypotheses, intervention)

    current_total = dialogue.total_turns or 0
    student_order = current_total + 1
    assistant_order = current_total + 2

    now = datetime.now(timezone.utc)
    # 감사상환 #2: create_session과 동형 — 본문 봉투 암호화기·동일 헬퍼로 학생/AI 턴 저장.
    content_cipher = build_dialogue_content_cipher(get_settings())
    student_turn = _build_dialogue_turn(
        DialogueTurnSchema(
            dialogue_id=dialogue_id,
            turn_order=student_order,
            spoken_at=now,
            role=TurnRole.student,
            content=body.student_input,
            content_type=ContentType.텍스트,
        ),
        content_cipher,
    )
    assistant_turn = _build_dialogue_turn(
        DialogueTurnSchema(
            dialogue_id=dialogue_id,
            turn_order=assistant_order,
            spoken_at=now,
            role=TurnRole.assistant,
            content=decision.prompt,
            content_type=ContentType.텍스트,
        ),
        content_cipher,
    )
    session.add_all([student_turn, assistant_turn])

    # dialogue 카운트 증가 — 다음 append의 `total_turns` 입력.
    dialogue.total_turns = current_total + 2
    dialogue.student_turns = (dialogue.student_turns or 0) + 1
    dialogue.assistant_turns = (dialogue.assistant_turns or 0) + 1

    # S3-03 mode 태깅 — 멀티턴은 클라가 매 턴 같은 mode/persona를 실어 보낸다(dialogue 컬럼 대신
    # 요청 재사용·least-invasive·zero-migration). body가 CoachRequest라 두 값을 그대로 가진다.
    event_persona = body.persona.value if body.persona is not None else None
    # WH-1 지표 ① 적재 — create_session과 동형(풀이 제출 턴만·같은 트랜잭션 합류). problem_id·
    # attempt_id는 dialogue에서 출처(append는 dialogue 컨텍스트).
    # S3-03: body.mode·persona를 실어 수능 세션 후속 턴의 검산결과도 측정 계층에서 식별 가능.
    verify_passed = await _log_verify_event(
        session,
        user_id=user.user_id,
        problem_id=dialogue.problem_id,
        attempt_id=dialogue.attempt_id,
        student_solution=body.student_solution,
        mode=body.mode,
        persona=event_persona,
    )
    # WH-1 지표 ⑤ 적재 — create_session과 동형(이미 계산된 decision.hint_level·supply 1~4을 그대로
    # 기록·재계산 0·_build_response_payload 불변). verify 적재 바로 옆·같은 트랜잭션 합류(별도
    # commit 없음). problem_id·attempt_id는 dialogue 출처(append는 dialogue 컨텍스트).
    # S3-03: verify와 동일 mode·persona 태그를 실어 후속 턴의 ⑤⑧ 집계도 mode-scoped 가능.
    await _log_hint_event(
        session,
        user_id=user.user_id,
        problem_id=dialogue.problem_id,
        attempt_id=dialogue.attempt_id,
        hint_level=decision.hint_level,
        mode=body.mode,
        persona=event_persona,
    )
    # WH-1 §2.3 — create_session과 동형. 이번 턴 확정 매치를 +1 지지 증거로 적재(생산측·curate 뒤).
    await _log_match_evidence(
        session,
        session_id=dialogue_id,
        student_id=user.user_id,
        matches=outcome.matches,
    )
    # WH-1 §2.3 짝 — create_session과 동형. clean 풀이(no-match)면 active 가설 약한 −1 반박.
    await _log_refutation_evidence(
        session,
        session_id=dialogue_id,
        student_id=user.user_id,
        passed=verify_passed,
        matches=outcome.matches,
        active_hypotheses=active_hypotheses,
        solution_text=body.student_solution,
    )
    await session.commit()

    # WH-1 멀티턴 연속성 — 이번 교환 *전* total_turns(current_total)에서 누적 턴 번호 유도(§2.2).
    wh1_turn_index, wh1_exploration = _wh1_turn_state(current_total)
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
        active_hypotheses=active_hypotheses,
        student_turn_id=student_turn.turn_id,
        assistant_turn_id=assistant_turn.turn_id,
        student_turn_order=student_order,
        assistant_turn_order=assistant_order,
        wh1_turn_index=wh1_turn_index,
        wh1_exploration_turn=wh1_exploration,
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
    # 감사상환 #2: 암호화 행은 content=NULL·content_encrypted에 저장 — 노출 직전 복호한다.
    # to_schema는 ciphertext 컬럼을 제외하므로 복호값을 schema.content에 덮어쓴다(키 유실 시
    # resolve_dialogue_content가 RuntimeError·조용한 평문 유출/빈 응답 금지).
    content_cipher = build_dialogue_content_cipher(get_settings())
    turns = []
    for row in result.scalars().all():
        turn_schema = row.to_schema()
        turn_schema.content = resolve_dialogue_content(
            content_cipher, row.content, row.content_encrypted, row.content_nonce
        )
        turns.append(turn_schema)
    payload = SessionGetResponse(dialogue=dialogue.to_schema(), turns=turns)
    etag = etag_for(payload)
    if matches_if_none_match(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return payload
