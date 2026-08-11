"""오답 선지(distractor) 오개념 신호 사장(死藏) 규모 관측 리포트 — ASM-09 acceptance②.

설계 정본: `docs/architecture/assessment_module_gap_review_r2.md` §3 D4. `distractor_map`
(선지 index → 오개념 id·`schema/problem.py::DistractorEntry` — `choice_index`·
`misconception_id`·`op_code` 완비)은 코퍼스에 이미 심어져 있는데, 학생이 *몇 번을 골랐는지*
(선택 인덱스)를 담는 요청 슬롯이 `AttemptSubmitRequest`(`api/me.py`)에 없어 그 신호를 서버가
영원히 읽지 못한다. 이 리포트는 그 사장 규모를 수치화한다 — 낼 것은 ① `distractor_map` 보유
문항 수 ② 그 문항들에 대한 실제 시도 수(`problem_attempt` — 시도를 담는 ORM 좌석은
`db/models/activity.py::ProblemAttempt` 실측 확정) ③ 그 시도 중 **오개념 가설로 역추적 가능한
건수**다. ③은 "0건"이 아니라 **`unreachable_no_capture_slot`(포착 슬롯 부재로 원천 불가)**
이라는 명시 상태로 표기한다(ASM-01 "생성 경로 부재" 정직 표기 선례) — "아무도 안 풀었다"
(②가 0)와 "풀었지만 신호를 못 읽었다"(③이 원천 불가)는 서로 다른 값이어야 한다.

**게이트가 아니다**(`assessment_seat_reach_report` 등 시리즈 동일 원칙) — 사장 규모가 얼마든
exit 1을 내지 않는다(0=성공 / 2=DB·입력 오류). 목표는 해소가 아니라 가시화다 — 포착 슬롯
(`selected_choice_index`) 신설·적재·클라 변경·마이그레이션은 **ASM-06 재정의 소관**(범위 밖).

**교수학 제약(acceptance③ — 리포트 어휘까지)**: 오답을 오개념으로 **단정하지 않는다** —
`distractor_map`은 *가설의 근거*이지 판정이 아니므로, 이 리포트의 어휘는 '오개념 검출'이
아니라 **'오개념 가설 역추적 가능성'**이다. 학생별 오답률·정답률·서열은 산출하지 않는다
(v1 §2-① 게임화 금기 승계) — 사용자 단위 필터·분해 자체를 두지 않는다.

**코퍼스 정적 재실측(acceptance① — 2026-08-11 이 세션)**: r2 §3 D4의 1,616/2,647건(61.1%)
주장을 재실측한 결과 **1,612/2,638건(61.1%)** — 총량 -9·MC -4의 델타는 전량 QUAL-02(#777)의
실중복 은퇴 9건으로 설명된다(은퇴 9건 중 `choices` 보유 정확히 4건 — 커밋 `50b43b6e` diff
실측·재추가(수정) 3건에는 `choices` 0건). choices↔distractor_map은 재실측에서도 동일 집합
(불일치 0건)이다. 재실측 수치가 정본이며,
이 정적 각주는 `_CORPUS_REMEASUREMENT_2026_08_11`로 리포트에 함께 렌더된다(라이브 DB 수치와
구분되는 각주 — 드리프트 시 동결 테스트가 재실측 갱신을 강제한다).

**포착 슬롯 프로브(구조 관측)**: `unreachable_no_capture_slot` 판정을 정적 문자열로 박지 않고
`probe_capture_slot`이 실물 `AttemptSubmitRequest`의 필드·`extra` 설정을 런타임 조사해 낸다 —
ASM-06이 슬롯을 신설하면 상태가 `capture_slot_present_backtrace_unmeasured`로 스스로 뒤집혀
이 리포트의 진실 갱신(ASM-05 선례)을 강제한다. 슬롯이 생겨도 역추적 *건수*는 이 판이 세지
않는다(적재·역추적 조인은 ASM-06 착지 후의 일 — 미측정을 0으로 위장하지 않는다).

사용:
    python -m whymath_backend.harness.distractor_signal_dormancy_report
    python -m whymath_backend.harness.distractor_signal_dormancy_report --json out/dormancy.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import ProblemAttempt as ProblemAttemptORM
from whymath_backend.db.models.problem import Problem as ProblemORM

__all__ = [
    "AttemptSeatRecord",
    "CaptureSlotProbe",
    "DormancyReport",
    "ProblemSeatCounts",
    "build_report",
    "collect_attempt_seat_records",
    "collect_problem_seat_counts",
    "dump_json",
    "main",
    "probe_capture_slot",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# 역추적 가능성 상태 2종 — "0건"으로 뭉개지 않는 명시 상태(§D4 정직 표기·상호 배타).
#   unreachable_no_capture_slot: 요청 계약에 선택 인덱스 슬롯이 없어 *원천 불가*(현행).
#   capture_slot_present_backtrace_unmeasured: 슬롯은 생겼으나(ASM-06 착지) 이 리포트 판은
#     적재·역추적 조인을 모른다 — 건수를 0으로 위장하지 않고 미측정을 명시(진실 갱신 강제).
_BACKTRACE_UNREACHABLE = "unreachable_no_capture_slot"
_BACKTRACE_SLOT_PRESENT_UNMEASURED = "capture_slot_present_backtrace_unmeasured"

# r2 §3 D4 ②(정합 설계)가 정본으로 지정한 포착 슬롯 필드명 — ASM-06이 이 이름으로 신설한다.
_CANONICAL_SLOT_FIELD = "selected_choice_index"
# 정본명이 아니어도 선택 인덱스 의미를 실을 법한 필드명 표지 — 프로브의 보수적 그물
# (이름이 달라도 슬롯 신설을 놓치지 않기 위한 부분문자열 매칭·소문자 비교).
_SLOT_NAME_MARKERS = ("choice", "chosen", "selected")

# acceptance① 코퍼스 정적 재실측 각주(2026-08-11) — 라이브 DB 수치가 아니라 코퍼스 JSONL
# (`data/corpus/problem_bank*/problems.jsonl` 7파일) 직접 파싱 결과다. 델타 설명 1줄 포함.
# 수치가 코퍼스와 어긋나게 되면(후속 은퇴·증설) 동결 테스트를 통해 재실측 갱신한다.
_CORPUS_REMEASUREMENT_2026_08_11 = (
    "코퍼스 정적 재실측(2026-08-11·ASM-09): 총 2,638건 중 MC 선지(choices) 보유 "
    "1,612건(61.1%)·distractor_map 보유 1,612건(동일 집합·불일치 0건) — r2 §3 D4의 "
    "1,616/2,647건 대비 -4/-9는 QUAL-02(#777) 실중복 은퇴 9건(객관식 4건 포함)으로 전량 설명"
)


# ──────────────────────────────────────────────────────────────────────────
# DB 조회 결과 투영 (collect_* 산출물 — build_report의 입력)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ProblemSeatCounts:
    """`problem` 테이블의 문항 좌석 집계 — `collect_problem_seat_counts`의 산출물."""

    total_problem_count: int
    distractor_map_problem_count: int  # jsonb_array_length(distractor_map) > 0 인 행 수


@dataclass(slots=True, frozen=True)
class AttemptSeatRecord:
    """`problem_attempt` 1행의 최소 투영(외부 조인) — 분류는 순수 `build_report`가 한다.

    `joined_problem_id`가 `None`이면 `problem_id`가 NULL이거나 FK가 고아(조인 실패)인
    경우다 — 조용히 skip해 분모를 왜곡하지 않고 별도 버킷으로 정직 집계한다(NLP-02
    `AttemptRecord.problem=None` 관례 동형). `distractor_entry_count`는 조인된 문항의
    `distractor_map` 원소 수(NULL·조인 실패 → 0)다.
    """

    attempt_id: uuid.UUID
    joined_problem_id: uuid.UUID | None
    distractor_entry_count: int


@dataclass(slots=True, frozen=True)
class CaptureSlotProbe:
    """요청 계약(`AttemptSubmitRequest`)의 선택 인덱스 포착 슬롯 유무 — 런타임 구조 관측.

    `slot_present`가 False인 동안 역추적 건수는 *원천 불가*다(r2 §3 D4 — 선택 인덱스는
    클라이언트만 아는 사실이라 슬롯이 없으면 서버는 영원히 알 수 없다). `extra_forbid`는
    acceptance①의 두 번째 축 — `extra='forbid'`라 클라가 임의 필드로 실어 보낼 수도 없다.
    """

    probed_model: str  # 무엇을 조사했는지 기록(정직성)
    slot_present: bool
    matched_field_names: tuple[str, ...]  # 슬롯 후보로 매칭된 필드명(정렬 고정)
    extra_forbid: bool


@dataclass(slots=True, frozen=True)
class DormancyReport:
    """사장 규모 관측 결과 전량(불변·렌더/직렬화의 단일 입력).

    시도 3버킷(`attempts_on_*`·`attempts_unjoinable`)은 총 시도를 상호 배타로 분할한다 —
    분모(역추적 신호가 *있어야 했던* 시도)는 `attempts_on_distractor_map_problems`뿐이고,
    `distractor_map` 없는 문항의 시도는 분모에서 제외하되 조용히 생략하지 않는다(acceptance④
    변별력의 양방향이 이 분할을 동결한다).
    """

    total_problem_count: int
    distractor_map_problem_count: int
    total_attempt_count: int
    attempts_on_distractor_map_problems: int  # 분모 — distractor_map 보유 문항에 대한 시도
    attempts_on_problems_without_distractor_map: int  # 분모 제외(명시)
    attempts_unjoinable: int  # problem_id NULL·고아 FK — 문항 판정 불능(별도 버킷)
    capture_slot: CaptureSlotProbe
    backtrace_state: str  # _BACKTRACE_UNREACHABLE | _BACKTRACE_SLOT_PRESENT_UNMEASURED
    backtraceable_count: None  # 항상 None — 이 판은 건수를 세지 않는다(0으로 위장 금지)

    @property
    def distractor_map_problem_ratio(self) -> float | None:
        """distractor_map 보유 문항 비율. 문항 0건이면 None(분모 없는 0% 위장 금지)."""
        if self.total_problem_count == 0:
            return None
        return self.distractor_map_problem_count / self.total_problem_count


# ──────────────────────────────────────────────────────────────────────────
# 조회 — 유일한 DB 접근 지점(전부 ORM 쿼리빌더 — 원시 SQL 금지·CLAUDE.md 원칙)
# ──────────────────────────────────────────────────────────────────────────
async def collect_problem_seat_counts(session: AsyncSession) -> ProblemSeatCounts:
    """`problem` 총 행 수 + `distractor_map` 보유(원소 1개 이상) 행 수를 조회.

    `func.jsonb_array_length`는 SQLAlchemy `func` 네임스페이스의 표준 함수 호출이라 원시 SQL
    문자열이 아니다(`assessment_seat_reach_report.collect_seat_counts` 동일 관례). NULL 컬럼은
    `jsonb_array_length(NULL) > 0`이 NULL(≠true)로 떨어져 자연히 미보유로 집계된다 — 빈 배열
    `[]`(길이 0)도 보유로 세지 않는다(신호가 실릴 자리가 없으므로).
    """
    total = await session.execute(select(func.count()).select_from(ProblemORM))
    with_map = await session.execute(
        select(func.count())
        .select_from(ProblemORM)
        .where(func.jsonb_array_length(ProblemORM.distractor_map) > 0)
    )
    return ProblemSeatCounts(
        total_problem_count=total.scalar_one(),
        distractor_map_problem_count=with_map.scalar_one(),
    )


async def collect_attempt_seat_records(session: AsyncSession) -> list[AttemptSeatRecord]:
    """`problem_attempt` ⟕ `problem` 외부 조인 → 최소 투영 레코드(분류 로직 0 — 순수는 build).

    사용자 단위 필터를 의도적으로 두지 않는다(acceptance③ — 학생별 분해 산출 0). 정렬은
    `attempt_id`로 고정(결정론). 조인 실패(FK 고아·NULL `problem_id`) 행은 outer join으로
    `joined_problem_id=None`을 받아 `build_report`가 별도 버킷으로 정직 집계한다.
    """
    stmt = (
        select(
            ProblemAttemptORM.attempt_id,
            ProblemORM.problem_id,
            func.coalesce(func.jsonb_array_length(ProblemORM.distractor_map), 0),
        )
        .select_from(ProblemAttemptORM)
        .outerjoin(ProblemORM, ProblemAttemptORM.problem_id == ProblemORM.problem_id)
        .order_by(ProblemAttemptORM.attempt_id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        AttemptSeatRecord(
            attempt_id=row[0],
            joined_problem_id=row[1],
            distractor_entry_count=row[2],
        )
        for row in rows
    ]


# ──────────────────────────────────────────────────────────────────────────
# 포착 슬롯 프로브 — 요청 계약의 런타임 구조 관측(DB 0·순수 조사)
# ──────────────────────────────────────────────────────────────────────────
def probe_capture_slot(model: type[BaseModel] | None = None) -> CaptureSlotProbe:
    """요청 모델의 필드명·`extra` 설정을 조사해 선택 인덱스 포착 슬롯 유무를 판정.

    `model=None`(기본)이면 실물 `AttemptSubmitRequest`를 lazy import로 조사한다 — 관측 도구가
    L5 표면을 *읽기만* 하는 예외적 참조라 함수 안으로 격리했다(`ops/dialogue_encryption_
    preflight`의 api lazy import 선례·harness는 import-linter 계약 밖). 테스트는 합성 모델을
    주입해 양방향(슬롯 유/무)을 hermetic으로 변별한다.

    매칭 규칙(보수적 그물): 정본명 `selected_choice_index`(r2 §3 D4 ②) 일치 **또는** 필드명에
    `choice`/`chosen`/`selected` 부분문자열 포함(소문자 비교) — 이름이 정본과 달라도 슬롯
    신설을 놓치지 않는다. 현행 6필드(problem_id·is_correct·student_answer·duration_seconds·
    session_id·confidence_self_reported)는 어느 표지에도 걸리지 않음을 실측 확인했다.
    """
    if model is None:
        # lazy import — 모듈 import 시점에 L5(api) 전체를 끌지 않는다(관측 시점에만 조사).
        from whymath_backend.api.me import AttemptSubmitRequest

        model = AttemptSubmitRequest
    matched = tuple(
        sorted(
            name
            for name in model.model_fields
            if name == _CANONICAL_SLOT_FIELD
            or any(marker in name.lower() for marker in _SLOT_NAME_MARKERS)
        )
    )
    return CaptureSlotProbe(
        probed_model=model.__name__,
        slot_present=bool(matched),
        matched_field_names=matched,
        extra_forbid=model.model_config.get("extra") == "forbid",
    )


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 순수 코어(DB·LLM·HTTP 0)
# ──────────────────────────────────────────────────────────────────────────
def build_report(
    problem_counts: ProblemSeatCounts,
    attempt_records: list[AttemptSeatRecord],
    capture_slot: CaptureSlotProbe,
) -> DormancyReport:
    """조회 결과 → `DormancyReport`(순수·부작용 0·DB 세션 불요).

    시도 분류(상호 배타 3버킷 — 합이 총 시도와 일치):
      1. `joined_problem_id is None` → `attempts_unjoinable`(문항 판정 불능 — 분모 아님).
      2. `distractor_entry_count > 0` → `attempts_on_distractor_map_problems`(**분모**).
      3. 그 외(조인됐으나 distractor_map 없음·빈 배열) → 분모 제외 버킷(명시 집계).

    역추적 상태는 프로브가 결정한다: 슬롯 부재 → `unreachable_no_capture_slot`(원천 불가),
    슬롯 실재 → `capture_slot_present_backtrace_unmeasured`(이 판은 건수 미측정 — 진실 갱신
    강제). 어느 쪽이든 `backtraceable_count`는 None이다 — 0으로 위장하지 않는다.
    """
    on_distractor = 0
    without_map = 0
    unjoinable = 0
    for record in attempt_records:
        if record.joined_problem_id is None:
            unjoinable += 1
        elif record.distractor_entry_count > 0:
            on_distractor += 1
        else:
            without_map += 1

    backtrace_state = (
        _BACKTRACE_SLOT_PRESENT_UNMEASURED if capture_slot.slot_present else _BACKTRACE_UNREACHABLE
    )
    return DormancyReport(
        total_problem_count=problem_counts.total_problem_count,
        distractor_map_problem_count=problem_counts.distractor_map_problem_count,
        total_attempt_count=len(attempt_records),
        attempts_on_distractor_map_problems=on_distractor,
        attempts_on_problems_without_distractor_map=without_map,
        attempts_unjoinable=unjoinable,
        capture_slot=capture_slot,
        backtrace_state=backtrace_state,
        backtraceable_count=None,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def render_report(report: DormancyReport, *, max_listed: int = 40) -> str:
    """사장 규모 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음).

    `max_listed`는 이 리포트에 목록형 산출물이 없어 현재 미사용이나, 시리즈 관례
    (`assessment_seat_reach_report.render_report`)와 시그니처를 맞춰 향후 목록 확장 시
    호출부를 바꾸지 않아도 되게 한다. 어휘 제약(acceptance③): '오개념 검출'이 아니라
    '오개념 가설 역추적 가능성' — 오답을 오개념으로 단정하지 않는다.
    """
    del max_listed  # 현재 렌더에는 목록이 없다 — 시그니처만 관례에 맞춘다.
    ratio = report.distractor_map_problem_ratio
    ratio_text = f"{ratio:.1%}" if ratio is not None else "데이터없음(문항 0건)"
    slot = report.capture_slot
    lines: list[str] = [
        "# 오답 선지 오개념 신호 사장 규모 관측 리포트 (ASM-09 D4)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(사장 규모가 얼마든 실패시키지 않는다).",
        "> 오답을 오개념으로 **단정하지 않는다** — `distractor_map`은 가설의 근거이지 판정이",
        "> 아니므로, 이 리포트가 말하는 것은 '오개념 가설 역추적 가능성'뿐이다. 학생별",
        "> 통계·서열은 산출하지 않는다. 포착 슬롯 신설은 범위 밖(ASM-06 소관)이다.",
        "",
        "## 1. 문항 좌석 (`problem` 테이블 — 라이브 DB)",
        "",
        f"- 총 문항: **{report.total_problem_count}**",
        f"- `distractor_map` 보유 문항(원소 1개 이상): **{report.distractor_map_problem_count}**"
        f" ({ratio_text})",
        f"- 정적 각주: {_CORPUS_REMEASUREMENT_2026_08_11}",
        "",
        "## 2. 시도 좌석 (`problem_attempt` ⟕ `problem` — 상호 배타 3버킷)",
        "",
        f"- 총 시도: **{report.total_attempt_count}**",
        f"- `distractor_map` 보유 문항에 대한 시도(**분모** — 역추적 신호가 실렸어야 할 시도): "
        f"**{report.attempts_on_distractor_map_problems}**",
        f"- `distractor_map` 없는 문항에 대한 시도(분모 제외 — 조용한 생략 아님): "
        f"**{report.attempts_on_problems_without_distractor_map}**",
        f"- 문항 판정 불능 시도(`problem_id` NULL·고아 FK): **{report.attempts_unjoinable}**",
        "",
        "## 3. 오개념 가설 역추적 가능성 (분모 시도 중 역추적 가능 건수)",
        "",
    ]
    if report.backtrace_state == _BACKTRACE_UNREACHABLE:
        lines += [
            f"- 상태: **`{_BACKTRACE_UNREACHABLE}`(포착 슬롯 부재로 원천 불가)** — 건수는"
            " 0건이 아니라 *미산출*이다(요청 계약에 선택 인덱스가 없어 서버가 영원히 알 수"
            " 없다).",
            f"- 근거(런타임 프로브): `{slot.probed_model}`에 선택 인덱스 슬롯 필드 없음"
            f"(정본명 `{_CANONICAL_SLOT_FIELD}` 및 표지 {list(_SLOT_NAME_MARKERS)} 매칭 0건)"
            f" · `extra='forbid'` {'확인' if slot.extra_forbid else '아님(임의 필드 유입 가능)'}"
            " — 클라가 임의 필드로 실어 보낼 수도 없다.",
        ]
    else:
        lines += [
            f"- 상태: **`{_BACKTRACE_SLOT_PRESENT_UNMEASURED}`** — 포착 슬롯"
            f"({', '.join(f'`{n}`' for n in slot.matched_field_names)})이 `{slot.probed_model}`에"
            " 실재한다. 이 리포트 판은 그 적재·역추적 조인을 알지 못해 건수를 세지 않는다 —"
            " 0으로 위장하는 대신 미측정을 명시한다(ASM-06 착지 후 이 리포트를 갱신하라).",
        ]
    lines += [
        "- '아무도 안 풀었다'(분모 시도 0)와 '풀었지만 신호를 못 읽었다'(역추적 원천 불가)는"
        " **서로 다른 값**이다 — 전자는 §2의 분모, 후자는 이 상태 표기가 각각 담당한다.",
        "",
        "## 4. 해소 소유 (범위 밖 명시)",
        "",
        f"- 포착 슬롯(`{_CANONICAL_SLOT_FIELD}`) 신설·적재·클라 변경·마이그레이션 = ASM-06"
        " 재정의 소관. 오개념 가설 갱신은 기존 `misconception_hypothesis` 좌석으로만 흘린다"
        "(이중 진실원천 금지) · 오개념 preload 0(reactive retrieval만).",
        "",
    ]
    return "\n".join(lines)


def report_to_json(report: DormancyReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정).

    `backtraceable_count`는 항상 `null`이다 — 소비자가 0과 혼동하지 않도록 상태 문자열
    (`backtrace_state`)과 쌍으로 읽어야 한다.
    """
    return {
        "total_problem_count": report.total_problem_count,
        "distractor_map_problem_count": report.distractor_map_problem_count,
        "distractor_map_problem_ratio": report.distractor_map_problem_ratio,
        "total_attempt_count": report.total_attempt_count,
        "attempts_on_distractor_map_problems": report.attempts_on_distractor_map_problems,
        "attempts_on_problems_without_distractor_map": (
            report.attempts_on_problems_without_distractor_map
        ),
        "attempts_unjoinable": report.attempts_unjoinable,
        "backtrace_state": report.backtrace_state,
        "backtraceable_count": report.backtraceable_count,
        "capture_slot": {
            "probed_model": report.capture_slot.probed_model,
            "slot_present": report.capture_slot.slot_present,
            "matched_field_names": list(report.capture_slot.matched_field_names),
            "extra_forbid": report.capture_slot.extra_forbid,
        },
        "corpus_remeasurement_note": _CORPUS_REMEASUREMENT_2026_08_11,
    }


def dump_json(report: DormancyReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 조회·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
async def _run() -> DormancyReport:  # pragma: no cover — 라이브 PG 연결 glue
    """세션을 열어 문항·시도 좌석을 조회하고 리포트를 조립한다(DB 조회 전용·쓰기 0)."""
    from whymath_backend.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        problem_counts = await collect_problem_seat_counts(session)
        attempt_records = await collect_attempt_seat_records(session)
    return build_report(problem_counts, attempt_records, probe_capture_slot())


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 사장 규모 관측 리포트를 stdout에 출력. **0=성공(사장 규모 무관) / 2=DB 오류**.

    DB 접속·쿼리 실패는 예외 타입명을 stderr에 포함해 보고한다(CLAUDE.md 침묵 실패 금지 —
    무타입 경고 금지 원칙).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.distractor_signal_dormancy_report",
        description=(
            "오답 선지 오개념 신호 사장 규모 관측 리포트(ASM-09 D4) — distractor_map 보유 "
            "문항 수·그 문항들에 대한 시도 수·오개념 가설 역추적 가능성(포착 슬롯 부재로 "
            "원천 불가) 명시. 결정론 아님(DB 실측)·게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="JSON 산출물 경로(선택)",
    )
    args = parser.parse_args(argv)

    try:
        report = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 오류는 타입명과 함께 보고하고 exit 2
        print(
            f"DB 오류 — 사장 규모 조회 실패({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
