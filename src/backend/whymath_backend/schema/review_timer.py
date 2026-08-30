"""검수 세션 타이머 이벤트 계약(Pydantic) — HIT(CU당 인간 개입 시간) 계측기 (EOS-54).

설계 정본: `docs/standards/eos_verification_design_v1.md` §6 — 주 기준 KPI **HIT(중앙값 ≤4분·
P90 ≤8분)**의 측정 방법은 "검수 타이머 이벤트(시작·종료·중단) 전수 자동 수집"으로 **동결**돼
있다. 이 모듈이 그 이벤트의 검증 계약이다(★이 계측기가 없으면 12월 검증에서 잴 것이 없다 —
G1(9/27) 차단 조건, `eos_plan52_crosswalk_2026-09.md` §2 후보 #1).

이 Pydantic 모델은 검증·전송 계약이고, 영속 매핑은 `db/models/review_timer_event.py`(ORM)가
별도로 세운다 — `from_schema`/`to_schema` seam(`hint_usage.py` 동일 패턴·EOS-45 관례).

이벤트 계약(폐쇄 3종 — started/finished/aborted):
  - **started** — 검수 착수. 판정·실패코드·경과 전부 금지(착수 시점엔 존재하지 않는 사실).
  - **finished** — 검수 종결. `verdict`(approved|rejected) **필수** — 판정 없는 종결은 없다.
    `verdict=rejected`면 `failure_code`(F1~F8) **필수** — 설계서 §4 "모든 검수 반려는 8코드 중
    하나로 강제 분류(자유 텍스트 단독 금지)"의 함수 레벨 집행. 이 모듈이
    `GenerationFailureCode`(EOS-51 동결)의 첫 소비 지점 중 하나다.
  - **aborted** — 중단(이탈·보류). 판정 없음(판정이 있으면 finished다). 부분 경과는 기록 가능.

설계 판단(근거 병기):
  - `cu_slug` — CU 식별 축. CU는 신설 스키마 없이 기존 Problem 조합으로 표현한다(설계서 §3
    동결)이고, 검수 흐름의 공통 식별자는 slug다 — 실측: 코퍼스 JSONL 레코드(`slug` 키)·검수
    워크리스트(`needs_review_worklist.WorklistItem.slug`)·DB(`problem.slug` UNIQUE String(128))
    전부 slug 축. max_length=128은 `problem.slug` 폭과 일치.
  - `problem_id` — **nullable FK**(DB 계층). 검수 대상은 "적재된 problem"만이 아니다 —
    needs_review 후보는 `accepted_stored` 전이라 problem 행이 없다(orchestrator 실측). NOT NULL
    FK를 강제하면 적재 전 후보의 검수가 기록 불가 = 측정 실패를 스키마가 제조한다. 적재된
    CU만 채우고, 미적재 후보는 None(정직 — 가짜 id 생성 금지·`hint_id` 느슨 방침과 동계열).
  - `reviewer_id` — 검수 *행위자* 핸들(TEXT). **학생 소유 축이 아니다** — privacy 스윕
    (`test_erasure_plan_completeness.OWNER_COLUMN_NAMES`)은 user_id/student_id/target_user_id만
    소유 축으로 보고, created_by·approved_by·reviewed_by류는 "콘텐츠 저작/검수 행위자"로
    분류한다(그 파일 주석 실측). 기존 검수 라벨 형식(#841 `reviewed_by: "kiki"`)과 동형.
  - `elapsed_ms` — **nullable**(0 날조 금지·acceptance ④). 경과는 검수 도구(클라) 계측인데
    도구 강제 종료·크래시 복구 등 계측 실패 케이스가 구조적으로 존재한다. None=미측정 —
    finished인데 elapsed가 None이면 "판정은 있으나 HIT 미계측"으로 집계가 **분리 카운트**한다
    (`ops/hit_cu_metrics` — 0초 산입 금지). started에는 경과 자체가 금지(아직 잰 것이 없다).
  - `occurred_at`/`recorded_at` — 발생/수신 시각 분리(EOS-48 계약·`activity.py` event_time/
    event_at 동형). occurred_at=검수 도구 신고 발생 시각(None=미신고), recorded_at=매체 도달
    시각(DB는 server_default now()·JSONL은 append 시각 — writer가 스탬프).

개인정보 판정(실측 — 추측 금지): 이 이벤트는 **검수자 운영 텔레메트리**이지 학생 데이터가
아니다. user_id/student_id/target_user_id 컬럼이 없으므로 privacy 스윕
(`tests/backend/privacy/test_erasure_plan_completeness.py`)의 소유 축에 걸리지 않음을 실측
확인했고(green), `tests/backend/db/test_review_timer_event_orm.py`가 학생 축 컬럼 부재를
`test_defect_report_no_user_id.py`(RPT-01) 선례대로 동결한다. 따라서 erasure/retention/export
3종 배선은 **필요 없음**(배선하면 오히려 "검수자 텔레메트리를 학생 삭제권으로 지우는" 오배선).

집행 별항(정본화≠집행 — acceptance ③): 검수 UI(ADMIN-07)가 타이머·반려코드 없이 판정 제출
자체를 불가하게 하는 **UI 결선은 후속 태스크**다 — ADMIN-07 acceptance 확장은 amend CLI 부재
(HARN-24 todo)로 등재 세션 판정 사안. 이 모듈은 함수 레벨 계약(rejected→failure_code 필수)
까지만 집행하고, UI 강제는 `ops/hit_cu_metrics` 리포트가 상시 명기한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import GenerationFailureCode

__all__ = ["ReviewTimerEvent", "ReviewTimerEventType", "ReviewVerdict"]


class ReviewTimerEventType(str, Enum):
    """검수 타이머 이벤트 3종 — 설계서 §6 "시작·종료·중단" 폐쇄 집합(추가 금지)."""

    STARTED = "started"
    """검수 착수 — 타이머 시작. 판정·실패코드·경과 없음."""

    FINISHED = "finished"
    """검수 종결 — 판정(approved|rejected) 동반 필수. rejected면 failure_code 필수."""

    ABORTED = "aborted"
    """검수 중단 — 판정 없이 이탈·보류. 부분 경과는 기록 가능(있는 만큼만·날조 금지)."""


# 종결 판정 폐쇄 2종 — `ReviewStatus`(pending/approved/rejected)의 부분집합과 *같은 문자열*을
# 쓴다(값 정합 — 노출 판정 단일 권위 `is_review_status_cleared`가 그대로 성립). pending은
# "판정"이 아니라 미판정 상태라 종결 이벤트에 올 수 없다 — Literal로 구조 차단.
ReviewVerdict = Literal["approved", "rejected"]


class ReviewTimerEvent(BaseModel):
    """검수 타이머 이벤트 1건 — 한 검수 세션(sitting)의 시작/종료/중단 중 한 사건.

    한 CU(`cu_slug`)는 여러 세션(`review_session_id`)으로 검수될 수 있다(시작→중단→재시작→
    종결). CU당 HIT = 그 CU 전 세션의 계측 경과 합 — 집계 계약은 `ops/hit_cu_metrics` 정본.
    append-only: 이벤트는 사실 기록이며 수정·삭제하지 않는다(EOS-45/46 관례).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    event_id: uuid.UUID = Field(default_factory=uuid4, description="이벤트 PK (UUID)")
    review_session_id: uuid.UUID = Field(
        description="검수 세션(sitting) id — 같은 앉음의 started/finished/aborted가 공유하는 "
        "페어링 축(required). writer의 start가 발급하고 finish/abort가 재사용한다"
    )

    # ===== 검수 대상 CU =====
    cu_slug: str = Field(
        min_length=1,
        max_length=128,
        description="검수 대상 CU 식별 slug — 코퍼스 JSONL·워크리스트·problem.slug 공통 축"
        "(폭 128 = problem.slug String(128) 일치)",
    )
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="적재된 CU의 problem FK(느슨 채움 — DB nullable FK). None = 미적재 후보"
        "(needs_review 등 accepted_stored 전) 또는 미확인. 가짜 id 생성 금지",
    )

    # ===== 검수 행위자 =====
    reviewer_id: str = Field(
        min_length=1,
        max_length=100,
        description="검수 행위자 핸들(#841 reviewed_by 선례 — 예: 'kiki'). 학생 소유 축이 "
        "아님(모듈 docstring 개인정보 판정)",
    )

    # ===== 이벤트 내용 =====
    event_type: ReviewTimerEventType = Field(
        description="이벤트 3종(started/finished/aborted) — 교차 필드 규칙은 validator가 강제"
    )
    verdict: ReviewVerdict | None = Field(
        default=None,
        description="종결 판정(approved|rejected) — finished에서만 필수, 그 외 금지. "
        "ReviewStatus와 같은 문자열(값 정합)",
    )
    failure_code: GenerationFailureCode | None = Field(
        default=None,
        description="반려 실패코드 F1~F8(EOS-51 동결 enum 소비) — verdict=rejected면 필수"
        "(설계서 §4 강제 분류), 그 외 금지",
    )
    failure_note: str | None = Field(
        default=None,
        max_length=2000,
        description="반려 부기 자유 텍스트 — failure_code가 있을 때만 허용(§4: 자유 텍스트 "
        "단독 금지·부기만)",
    )

    # ===== 시간·계측 =====
    elapsed_ms: int | None = Field(
        default=None,
        ge=0,
        description="검수 도구 계측 경과(ms). None=미측정(계측 실패 — 0 날조 금지·집계에서 "
        "미계측 분리). started에는 금지(validator)",
    )
    occurred_at: datetime | None = Field(
        default=None,
        description="검수 도구 신고 *발생* 시각(EOS-48 발생/수신 분리). None=미신고",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="매체 *수신* 시각 — DB는 server_default now(), JSONL은 writer append가 "
        "스탬프. None = 적재 계층이 채움",
    )

    # ── 교차 필드 계약(이벤트 3종 × 판정/코드/경과) ──────────────────────
    @model_validator(mode="after")
    def _enforce_event_shape(self) -> Self:
        """이벤트 유형별 필수/금지 필드 강제 — "반려코드 없는 반려" 같은 미계측 판정을 차단.

        규칙(모듈 docstring 이벤트 계약과 1:1):
          started  → verdict·failure_code·failure_note·elapsed_ms 전부 금지.
          finished → verdict 필수. rejected → failure_code 필수 / approved → failure_code 금지.
          aborted  → verdict·failure_code 금지(판정이 있으면 finished다).
          공통     → failure_note는 failure_code 없이 금지(자유 텍스트 단독 금지 — §4).
        """
        # use_enum_values=True라 event_type은 str 값으로 저장돼 있다 — str Enum 동등 비교 안전.
        etype = self.event_type
        if etype == ReviewTimerEventType.STARTED:
            if self.verdict is not None or self.failure_code is not None:
                raise ValueError("started 이벤트에 판정/실패코드 금지 — 착수 시점엔 없는 사실")
            if self.elapsed_ms is not None:
                raise ValueError("started 이벤트에 elapsed_ms 금지 — 아직 잰 것이 없다")
        elif etype == ReviewTimerEventType.FINISHED:
            if self.verdict is None:
                raise ValueError(
                    "finished 이벤트는 verdict(approved|rejected) 필수 — 판정 없는 종결 없음"
                )
        else:  # ABORTED
            if self.verdict is not None:
                raise ValueError("aborted 이벤트에 verdict 금지 — 판정이 있으면 finished다")
            if self.failure_code is not None:
                raise ValueError("aborted 이벤트에 failure_code 금지 — 반려는 finished+rejected로")
        if self.verdict == "rejected" and self.failure_code is None:
            raise ValueError(
                "반려(rejected)는 failure_code(F1~F8) 필수 — §4 강제 분류(EOS-51 동결)"
            )
        if self.verdict in (None, "approved") and self.failure_code is not None:
            raise ValueError(
                "failure_code는 verdict=rejected에서만 허용 — 승인/미판정에 반려코드 금지"
            )
        if self.failure_note is not None and self.failure_code is None:
            raise ValueError(
                "failure_note는 failure_code 부기로만 허용 — 자유 텍스트 단독 금지(§4)"
            )
        return self
