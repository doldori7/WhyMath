"""L2 — `LearnerState` v0 조립기: L2가 L3/L4에 주입하는 *단일 요약 상태*.

설계 정본: `docs/architecture/02_learner_model.md` §"출력 — LearnerState"(L131-159, 2026-07-30
PED-05 편집자 부기로 v0 범위 축소). 원안은 11필드를 명세했으나 코드에 `LearnerState` 클래스 자체가
없어 소비처(`api/coach.py`·`api/study.py`)마다 `compute_concept_diagnoses`·`get_current_theta` 등
조각을 직접 호출해 흩어져 있었다. 이 모듈이 그 조각들을 **재사용만**(신규 계산 0) 해 단일 조립기로
묶는다.

**v0 범위 원칙**: `l4/pedagogy/runtime_selector.py:96-118`의 `StudentSignals` 결정("생산자 없는
신호는 필드로 만들지 않는다 — 항상 None인 필드는 '읽고 있다'는 착시만 준다")과 동형이다. 원안
11필드 중 실제 생산자가 있는 8개(mastery·general_ability·domain_abilities·active_misconceptions·
recent_struggles·recent_successes·grade·goals)만 v0에 담는다. 나머지 5개(curriculum·affect·
mastery_states·active_textbook_id·shadow_curriculum_progress)의 제외 사유는 `LearnerState`
클래스 docstring 참조.

**7계층 경계(중요)**: 이 모듈은 **L4를 import하지 않는다**(CLAUDE.md "L_n은 L_{n+1}을 알지
못한다" — 역방향 의존 금지). `active_misconceptions`가 필요로 하는 활성 오개념 가설은
`l4/misconception/hypothesis_store.py:get_active_hypotheses`와 **같은 모양의 SELECT**를
`_get_active_misconception_ids`가 이 모듈 안에서 직접 재구현한다(ORM `MisconceptionHypothesisRecord`
는 `db/models/`로 계층 소속이 아니라 공유 인프라이므로 import 가능 — L2 자신도 이미 자기
테이블들을 이렇게 직접 쿼리한다). 전체 레코드→Pydantic 변환 없이 `misconception_id` 컬럼만
select한다(이 조립기는 id 리스트만 필요).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.ability_tracking import get_current_theta
from whymath_backend.l2.concept_diagnosis import compute_concept_diagnoses

__all__ = ["LearnerState", "get_state"]

# LTHC 숙달도 임계값의 **값만 미러링**(import 아님) — `l4/lthc/adapt.py`의 `_DEVELOPING_THRESHOLD`
# (0.4)·`_MASTERED_THRESHOLD`(0.8)와 반드시 같은 값을 유지해야 하지만, L2는 L4를 import할 수
# 없다(CLAUDE.md "L_n은 L_{n+1}을 알지 못한다" — 역방향 의존 금지·본 모듈 최상단 docstring).
# `from whymath_backend.l4.lthc.adapt import ...`는 L2→L4 역방향 의존이라 금지 대상 자체이므로,
# 두 계층이 공유할 수 있는 더 낮은 위치(schema/ 등)로 상수가 이동하기 전까지는 **값을 복제**하고
# 이 주석으로 원본 출처·동기화 의무를 명시한다(새 매직넘버가 아니라 "기존 상수의 문서화된 사본").
_DEVELOPING_THRESHOLD = 0.4  # l4/lthc/adapt.py::_DEVELOPING_THRESHOLD와 동기화 필수
_MASTERED_THRESHOLD = 0.8  # l4/lthc/adapt.py::_MASTERED_THRESHOLD와 동기화 필수


class LearnerState(BaseModel):
    """L2가 조립하는 학습자 요약 상태 v0 — 생산자 실재 필드만.

    `02_learner_model.md`의 원안 11필드 중 생산자가 있는 8개(mastery·general_ability·
    domain_abilities·active_misconceptions·recent_struggles·recent_successes·grade·goals)만
    담는다.

    **v0 제외 필드(생산자 부재 — `runtime_selector.py:96-118` 결정의 이행)**:
    - `curriculum`: `user_profile`에 대응 컬럼이 없다(교육과정 버전 필드 부재 — grep 0건 실측.
      2026-07-29 편집자 부기가 이 필드를 v0에 포함시켰던 것은 사실 오류였고, 2026-07-30 정정).
    - `affect`: `AffectState` 분류기 자체가 없음(§D6 페이퍼 설계만).
    - `mastery_states: dict[str, MasteryState]`: `MasteryState` 자체가 코드에 미실체화(문서 스케치).
    - `active_textbook_id`: `user_profile`에 학생-교과서 FK 없음(`textbook_mapping`은 콘텐츠
      자산일 뿐, 학생 프로필과 연결되지 않는다).
    - `shadow_curriculum_progress`: 학원·인강 진도 컬럼 없음(`uses_inkang` 불리언만 존재).

    이 필드들이 필요해지면 생산자(추정기·컬럼)를 먼저 만들고 그때 이 클래스에 연다.
    """

    student_id: str = Field(description="학생 user_id 문자열.")
    timestamp: datetime = Field(description="조립 시각(UTC) — 호출 시점 스냅샷.")
    mastery: dict[str, float] = Field(
        description="개념코드 → BKT 최신 숙달 P(L). "
        "`compute_concept_diagnoses`의 `bkt_mastery` 소스(측정 없으면 키 자체가 없음)."
    )
    general_ability: float | None = Field(
        description="전과목 IRT 능력 θ — `get_current_theta(concept_id=None)`. "
        "측정 이력 없으면 None."
    )
    domain_abilities: dict[str, float] = Field(
        description="개념코드 → IRT 능력 θ. **이름과 실제 의미가 다름에 유의**: 원안의 "
        "`domain_abilities`는 '수와 연산' 같은 굵은 도메인 단위를 뜻했지만, 실제 생산자"
        "(`compute_concept_diagnoses`)는 *개념(concept) 단위* θ만 낸다. 필드명은 acceptance대로 "
        "`domain_abilities`를 유지하되, 키는 도메인명이 아니라 concept_code다 — v0 의도적 단순화, "
        "실제 도메인 집계는 후속."
    )
    active_misconceptions: list[str] = Field(
        description="활성(is_active=true) 오개념 가설 id 목록(confidence 내림차순)."
    )
    recent_struggles: list[str] = Field(
        description="BKT 숙달 < 발전중 임계(`_DEVELOPING_THRESHOLD`)인 개념코드 목록. **주의**: "
        "이건 '최근 사건'이 아니라 '현재 낮은 숙달 개념'의 v0 근사다 — `ConceptMasteryHistory`의 "
        "시간축 기반 진짜 recency는 후속, v0은 현재 숙달도 임계 근사."
    )
    recent_successes: list[str] = Field(
        description="BKT 숙달 >= 숙달 임계(`_MASTERED_THRESHOLD`)인 개념코드 목록. "
        "`recent_struggles`와 동일한 v0 근사(현재 숙달도 임계, 시간축 recency 아님)."
    )
    grade: int | None = Field(description="`user_profile.grade` — 학년(정수). 미입력이면 None.")
    goals: dict[str, str] = Field(
        description="`user_profile`의 target_grade·target_score·target_exam_date·"
        "target_universities를 문자열화한 목표 사전. 값 없는 필드는 키 생략, 전부 없으면 빈 dict. "
        "**PII 주의**: 이 필드는 이번 슬라이스(PED-05)에서 프롬프트에 착지되지 않는다 — 목표 "
        "점수/등급/대학을 학생 대면 프롬프트에 노출하는 것은 CLAUDE.md PII 가드 위반이다."
    )


async def _get_active_misconception_ids(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """학생의 활성 오개념 가설 id만 confidence 내림차순으로 조회 — L4 import 없이 직접 SELECT.

    `l4/misconception/hypothesis_store.py::get_active_hypotheses`와 같은 모양의 WHERE/정렬이지만,
    L2→L4 역방향 의존을 피하려 전체 ORM 레코드→Pydantic 변환 없이 `misconception_id` 컬럼만 뽑는다
    (이 조립기는 id 리스트 `list[str]`만 필요하므로 그 이상은 과공학).
    """
    stmt = (
        select(MisconceptionHypothesisRecord.misconception_id)
        .where(
            MisconceptionHypothesisRecord.user_id == user_id,
            MisconceptionHypothesisRecord.is_active.is_(True),
        )
        .order_by(
            MisconceptionHypothesisRecord.confidence.desc(),
            MisconceptionHypothesisRecord.misconception_id,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _build_goals(profile: UserProfile) -> dict[str, str]:
    """`user_profile`의 4개 target_* 필드를 문자열화 — None인 필드는 키 생략.

    `target_universities`(JSONB 리스트)는 `repr`이 아니라 `str()`로 문자열화한다(v0은 사람이 읽는
    사전 값이면 충분 — 구조화 파싱이 필요해지면 후속에서 JSON 문자열로 교체).
    """
    goals: dict[str, str] = {}
    if profile.target_grade is not None:
        goals["target_grade"] = str(profile.target_grade)
    if profile.target_score is not None:
        goals["target_score"] = str(profile.target_score)
    if profile.target_exam_date is not None:
        goals["target_exam_date"] = profile.target_exam_date.isoformat()
    if profile.target_universities:
        goals["target_universities"] = str(profile.target_universities)
    return goals


async def get_state(session: AsyncSession, user_id: uuid.UUID) -> LearnerState:
    """L2 학습자 요약 상태 v0 조립 — 기존 좌석 재사용만(신규 계산 0).

    `compute_concept_diagnoses` 단 1회 호출로 `mastery`·`domain_abilities`·`recent_struggles`·
    `recent_successes` 4필드를 함께 도출한다(중복 쿼리 금지). `general_ability`는
    `get_current_theta(concept_id=None)`(전과목), `active_misconceptions`는 자체 SELECT(위
    `_get_active_misconception_ids`), `grade`·`goals`는 `user_profile` 단건 조회.

    진단·오개념·프로필이 전부 없는 신규 학생도 예외 없이 반환한다 — 각 컬렉션은 빈 dict/list,
    `general_ability`·`grade`는 None, `goals`는 빈 dict(NO_DATA 센티널이 아니라 그냥 빈 값 —
    이 조립기는 Metric 패턴이 아니라 단순 조립기다).
    """
    diagnoses = await compute_concept_diagnoses(session, user_id)

    mastery: dict[str, float] = {
        d.concept_code: d.bkt_mastery
        for d in diagnoses
        if d.concept_code and d.bkt_mastery is not None
    }
    domain_abilities: dict[str, float] = {
        d.concept_code: d.irt_theta for d in diagnoses if d.concept_code and d.irt_theta is not None
    }
    recent_struggles = [
        d.concept_code
        for d in diagnoses
        if d.concept_code and d.bkt_mastery is not None and d.bkt_mastery < _DEVELOPING_THRESHOLD
    ]
    recent_successes = [
        d.concept_code
        for d in diagnoses
        if d.concept_code and d.bkt_mastery is not None and d.bkt_mastery >= _MASTERED_THRESHOLD
    ]

    general_ability = await get_current_theta(session, user_id)
    active_misconceptions = await _get_active_misconception_ids(session, user_id)

    profile = await session.get(UserProfile, user_id)
    grade = profile.grade if profile is not None else None
    goals = _build_goals(profile) if profile is not None else {}

    return LearnerState(
        student_id=str(user_id),
        timestamp=datetime.now(timezone.utc),
        mastery=mastery,
        general_ability=general_ability,
        domain_abilities=domain_abilities,
        active_misconceptions=active_misconceptions,
        recent_struggles=recent_struggles,
        recent_successes=recent_successes,
        grade=grade,
        goals=goals,
    )
