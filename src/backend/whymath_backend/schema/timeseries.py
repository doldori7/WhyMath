"""Schema v1.0 도메인7 시간 시계열(Time Series) 모델 (Pydantic) — 슬라이스 7(도메인 마지막).

설계 정본: `schemas/v1.0/schema_v1.0.md` §9.1(`daily_learning_metrics`·
`problem_solve_time_distribution`·`user_behavior_metrics` DDL 3테이블). 일별 학습 활동
집계, 문항별·페르소나별 풀이 시간 분포, 학생 학습 행동 시계열(페르소나 변화·이탈 예측)을
담는 도메인. 세 테이블 모두 TimescaleDB hypertable·복합 PK다.

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1~6 동일 패턴).

컨벤션(`problem.py`·`concept.py`·`user.py`·`activity.py`·`assessment.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - 신규 enum 없음 — §9가 쓰는 enum은 `persona_enum`(기존 `Persona`) 하나뿐이고,
    `metric_name`은 `VARCHAR(50)`이라 enum이 아니라 `str`(open set)이다. 따라서 이
    슬라이스는 `enums.py`를 수정하지 않는다.
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic, 슬라이스 1~6 선례 그대로):
  - `UUID`(복합 PK 구성요소) → required `uuid.UUID`(slice5 `AttemptEvent`·slice6
    `ConceptMasteryHistory` PK 선례)
  - `DATE`(복합 PK 구성요소) → required `datetime.date`(`user.py` `target_exam_date`가
    DATE를 `date`로 매핑한 선례. 복합 PK 구성요소이므로 NOT NULL → required)
  - `enum`(복합 PK 구성요소) → required `Enum`(예: persona — PK라 Optional 아님,
    `ConceptMasteryHistory.measured_at`이 PK라 required였던 것과 같은 논리)
  - `VARCHAR(n)`(복합 PK 구성요소) → required `str`(max_length=n; enum 아닌 open set,
    예: metric_name)
  - `TIMESTAMPTZ`(복합 PK 구성요소) → required `datetime`(예: measured_at)
  - `INTEGER` → `int | None`(ge/le)
  - `DECIMAL(p,s)` → `float | None`(ge/le); 범위는 DDL 인라인 주석을 따르고, 미명시는
    의미에 맞는 보수값을 골라 각 필드 description에 1줄로 명시(슬라이스 1~6 방식)
  - `TEXT[]`(단원 코드 배열) → `list[str]`(default_factory=list)

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`activity.py`·`assessment.py`
방침과 동일):
  이 시계열들은 *미성년 학생 학습 행동 데이터*다. 특히 `user_behavior_metrics`는
  `churn_risk`(이탈 위험) 등 *행동 분석* 지표를 담고, `daily_learning_metrics`는
  학생별 일일 활동량을, `problem_solve_time_distribution`은 페르소나별 풀이 시간을
  집계한다. CLAUDE.md 절대 금기("미성년자 개인정보를 분석·마케팅 외부 공유 금지"·
  "학교·학년 정보로 개인 식별 가능한 분석 결과 외부 노출 금지")는 *저장·노출·분석
  거버넌스 계층* 책임이다 — 권한 게이팅(PIPA 데이터 권한 매트릭스)·암호화 저장·외부
  공유 차단은 인프라/미들웨어가 시행한다. 모델 필드는 그 사실을 *상기*시키되 cross-field
  강제(가짜 validator)를 두지 않는다(슬라이스 1~2가 `source_type`/`license`라는 *구조
  신호*로 강제 가능했던 것과 달리, 여기엔 강제할 구조 신호가 없다 —
  `user.py`/`activity.py`/`assessment.py` 법적 메모와 같은 방침: 문서화만).

  또한 이 도메인에는 자기관계(self-relation) 같은 구조 cross-field 불변식이 없다.
  분위수 정합(예: p10 ≤ p50 ≤ p90)·카운트 정합(예: problems_correct ≤
  problems_attempted)은 표본·집계 산출물이라 측정 시점·표본에 따라 항상 성립한다는
  보장이 없어 모델 불변식으로 강제하지 않는다(`assessment.py`/`activity.py` 방침 —
  없는 게 맞다).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import Persona


# ──────────────────────────────────────────────────────────────────────────
# 핵심: DailyLearningMetrics (§9.1 daily_learning_metrics — 일별 학습 활동 집계)
# ──────────────────────────────────────────────────────────────────────────
class DailyLearningMetrics(BaseModel):
    """일별 학습 활동 집계 — §9.1 `daily_learning_metrics`(자동 집계).

    복합 PK `(user_id, metric_date)` — DB 제약. PK 구성요소는 NOT NULL이므로 `user_id`·
    `metric_date` 둘 다 required로 둔다(슬라이스 5 `AttemptEvent`·슬라이스 6
    `ConceptMasteryHistory`가 PK 구성요소를 모두 required로 둔 선례 답습).

    `metric_date`는 DDL `DATE`라 시각이 아닌 *날짜*다 — `user.py` `target_exam_date`가
    DATE를 `datetime.date`로 매핑한 선례를 따른다(`datetime` 아님).

    운영 시 `daily_learning_metrics`는 TimescaleDB hypertable로 변환되어 `metric_date`
    기준 30일 청크로 분할된다(런타임/DB 레벨; 단일 모델 레벨에서는 표현하지 않음 —
    `AttemptEvent`·`ConceptMasteryHistory` 선례).

    개인정보 메모(모듈 docstring 참조): 학생별 일일 활동량을 집계한 *미성년 학습 행동
    데이터*다. CLAUDE.md 절대 금기(미성년 개인정보 분석·외부 공유 금지)는 *저장·노출·분석
    거버넌스 계층*(PIPA 권한 매트릭스·암호화·미들웨어) 책임이며, 이 모델 필드는 그 사실을
    *상기*시키되 가짜 validator를 두지 않는다(문서화만).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(이 모델엔 enum 필드 없음 — 다른 모델과 설정 통일)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 복합 PK (user_id, metric_date) =====
    user_id: uuid.UUID = Field(..., description="학생 FK (복합 PK 구성요소)")
    metric_date: date = Field(
        ...,
        description="집계 대상 날짜 — DDL DATE → datetime.date(`user.py` target_exam_date "
        "선례). 복합 PK 구성요소·hypertable 30일 청크 분할 키.",
    )

    # ===== 활동량 집계 =====
    minutes_active: int | None = Field(
        default=None,
        description="활동 시간(분). DDL에 범위 미명시 → 시간 길이라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    problems_attempted: int | None = Field(
        default=None,
        description="시도한 문제 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    problems_correct: int | None = Field(
        default=None,
        description="정답 문제 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    socratic_turns: int | None = Field(
        default=None,
        description="Socratic 대화 턴 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== 학습 내용·품질 =====
    concepts_practiced: list[str] = Field(
        default_factory=list,
        description="이날 연습한 단원(개념) 코드 배열 — DDL TEXT[](단원 코드 배열).",
    )
    avg_focus_score: float | None = Field(
        default=None,
        description="평균 집중도. DDL 'DECIMAL(3,2)' → 정규화 점수로 보아 ge=0 le=1 설정 "
        "(`activity.py` focus_score 선례).",
        ge=0.0,
        le=1.0,
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ProblemSolveTimeDistribution
#       (§9.1 problem_solve_time_distribution — 문항별·페르소나별 풀이 시간 분포)
# ──────────────────────────────────────────────────────────────────────────
class ProblemSolveTimeDistribution(BaseModel):
    """풀이 시간 분포 — §9.1 `problem_solve_time_distribution`(문항별·페르소나별).

    복합 PK `(problem_id, persona, measured_at)` — DB 제약. PK 구성요소는 NOT NULL이므로
    `problem_id`·`persona`·`measured_at` 셋 다 required로 둔다(슬라이스 5·6 선례). 특히
    `persona`는 `Persona` enum이지만 *복합 PK 구성요소*라 Optional이 아니라 required다
    (`ConceptMasteryHistory.measured_at`이 PK라 required였던 것과 같은 논리).

    운영 시 `problem_solve_time_distribution`은 TimescaleDB hypertable로 변환되어
    `measured_at` 기준 7일 청크로 분할된다(런타임/DB 레벨; 단일 모델 레벨에서는 표현하지
    않음 — `AttemptEvent`·`ConceptMasteryHistory` 선례).

    분위수 정합(p10 ≤ p50 ≤ p90)은 모델 불변식으로 강제하지 않는다(모듈 docstring 참조 —
    표본·집계 산출물이라 측정 시점에 따라 항상 성립한다는 보장이 없다).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 복합 PK (problem_id, persona, measured_at) =====
    problem_id: uuid.UUID = Field(..., description="문제 FK (복합 PK 구성요소)")
    persona: Persona = Field(
        ...,
        description="페르소나 — A_일반고고3/B_자사고N수/C_검정고시N수/D_학종고2/E_홈스쿨링영재. "
        "Persona enum이지만 복합 PK 구성요소라 required(Optional 아님).",
    )
    measured_at: datetime = Field(
        ...,
        description="측정 시각 — 복합 PK 구성요소·hypertable 7일 청크 분할 키.",
    )

    # ===== 분위수 (단위: 초) =====
    p10_seconds: int | None = Field(
        default=None,
        description="상위 10% 학생 풀이 시간(초). DDL에 범위 미명시 → 시간 길이라 음수 불가 "
        "ge=0만 설정.",
        ge=0,
    )
    p50_seconds: int | None = Field(
        default=None,
        description="중앙값 풀이 시간(초). DDL에 범위 미명시 → 시간 길이라 음수 불가 ge=0만 "
        "설정.",
        ge=0,
    )
    p90_seconds: int | None = Field(
        default=None,
        description="하위 10% 학생 풀이 시간(초). DDL에 범위 미명시 → 시간 길이라 음수 불가 "
        "ge=0만 설정.",
        ge=0,
    )

    # ===== 표본 =====
    sample_size: int | None = Field(
        default=None,
        description="이 분포의 표본 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: UserBehaviorMetrics (§9.1 user_behavior_metrics — 학생 학습 행동 시계열)
# ──────────────────────────────────────────────────────────────────────────
class UserBehaviorMetrics(BaseModel):
    """학생 학습 행동 시계열 — §9.1 `user_behavior_metrics`(페르소나 변화·이탈 예측).

    복합 PK `(user_id, metric_name, measured_at)` — DB 제약. PK 구성요소는 NOT NULL이므로
    `user_id`·`metric_name`·`measured_at` 셋 다 required로 둔다(슬라이스 5·6 선례).

    `metric_name`은 DDL `VARCHAR(50)`이라 enum이 아니라 `str`(open set)이다 — 지표 종류가
    운영 중 계속 늘어날 수 있어 닫힌 enum으로 고정하지 않는다(`activity.py` `network_type`이
    VARCHAR을 str로 둔 선례). 예: 'session_length'/'streak'/'churn_risk'. *복합 PK
    구성요소*라 required다.

    운영 시 `user_behavior_metrics`는 TimescaleDB hypertable로 변환되어 `measured_at`
    기준 7일 청크로 분할된다(런타임/DB 레벨; 단일 모델 레벨에서는 표현하지 않음 —
    `AttemptEvent`·`ConceptMasteryHistory` 선례).

    개인정보 메모(모듈 docstring 참조): `churn_risk`(이탈 위험) 등 *행동 분석* 지표를 담는
    *미성년 학습 행동 데이터*다. CLAUDE.md 절대 금기(미성년 개인정보 분석·마케팅 외부 공유
    금지)는 *저장·노출·분석 거버넌스 계층*(PIPA 권한 매트릭스·암호화·미들웨어) 책임이며,
    이 모델 필드는 그 사실을 *상기*시키되 가짜 validator를 두지 않는다(문서화만).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 복합 PK (user_id, metric_name, measured_at) =====
    user_id: uuid.UUID = Field(..., description="학생 FK (복합 PK 구성요소)")
    metric_name: str = Field(
        ...,
        description="지표 이름 — DDL VARCHAR(50)이라 enum 아닌 str(open set, 예: "
        "'session_length'/'streak'/'churn_risk'). 복합 PK 구성요소라 required.",
        max_length=50,
    )
    measured_at: datetime = Field(
        ...,
        description="측정 시각 — 복합 PK 구성요소·hypertable 7일 청크 분할 키.",
    )

    # ===== 측정값 =====
    metric_value: float | None = Field(
        default=None,
        description="지표 값 — DDL DECIMAL(10,4). metric_name마다 의미·범위가 달라(시간 길이·"
        "연속 일수·이탈 확률 등) ge/le 범위 제약을 두지 않는다(음수·큰 값 모두 허용).",
    )
