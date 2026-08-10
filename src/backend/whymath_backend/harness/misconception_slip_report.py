"""root/symptom·slip 판별 관측 리포트 — MISC-05(신규 분류축 0, 기존 신호 재해석만).

설계 정본: `docs/architecture/04c_misconception_seven_stage_separation.md` §6-4(root vs
symptom·slip 판별 — "최대 미구현 갭" · "라이브 오진단 실측 시 결정") · `docs/architecture/
04e_misconception_remediation_design.md` §3("이 리포트가 'slip을 오개념으로 오코칭한 비율'을
측정 가능하게 만들면, 04c가 예고한 '명시 도입 결정'의 트리거를 발화시킨다").

04c §6-4는 이 축의 *명시 도입*을 "라이브 오진단이 실측될 때 결정"으로 유예했다 — 이 모듈은 그
유예를 그대로 존중한다(신규 분류축·신규 스키마·신규 DB 필드 **0**, `l4/misconception/
hypothesis.py` 무수정). 대신 이미 있는 신호(가설 감쇠 반감기 5턴·강화 횟수·judge EXPRESSES/
NOT_EXPRESSES 방향판별)만 재해석해 "이 오답이 slip처럼 보이는가 vs 지속 오개념처럼 보이는가"를
**읽기 전용**으로 산출한다.

────────────────────────────────────────────────────────────────────────────
데이터 소스 — 스냅샷 vs 이력(교차 사용, 04e §3 조사 결과)
────────────────────────────────────────────────────────────────────────────
- `misconception_hypothesis`(스냅샷 테이블) — `(user_id, misconception_id)` 유니크. 매 턴
  `confidence`/`evidence_count`가 *덮어써진다* — "지금" 값만 남는다. `is_active`(가지치기
  플래그)는 상태로 남는다(비활성 행도 삭제되지 않음 — slip-like 판별에 그대로 쓸 수 있다).
- `evidence_links`(append-only 이력) — `polarity`(+1 지지/−1 반박)·`weight`·`created_at`.
  같은 (student, misconception) 쌍이 몇 번 강화됐는지(반복성)는 스냅샷이 아니라 여기서만
  재구성할 수 있다.

이 리포트는 **둘을 교차**한다 — `evidence_links`의 polarity=+1 개수(강화 이력)를 스냅샷의
`evidence_count`(현재 값)와 대조해서, 일치하면 slip-like/지속오개념-like로 분류하고
**불일치하면 정직하게 '불일치' 버킷으로 집계한다**(다수결로 임의 분류하지 않음 — CLAUDE.md
정직 회계).

────────────────────────────────────────────────────────────────────────────
분류(`classify_pair`) — "3분류 + 잔여"의 완전 분할
────────────────────────────────────────────────────────────────────────────
04e §3의 조작적 정의를 코드 신호로 매핑:
  - **slip-like**: `evidence_count == 1` and `is_active == False`(1회·비강화·가지치기로 소멸).
  - **지속오개념-like**: `evidence_count >= 2` and `is_active == True`(≥2회 강화·judge
    EXPRESSES 유지 근사 — 아래 judge 갭 절 참조).
  - **불일치**(mismatch) — 두 세부로 정직하게 나눈다:
      · `mismatch_disagreement`: 스냅샷·이력 둘 다 있으나 evidence_count 값이 서로 다름.
      · `mismatch_absent`: 이력엔 강화 증거가 있으나 스냅샷 자체가 없음.
  - **undetermined**(잔여) — 카운트는 일치하나 위 두 정의 어느 쪽에도 맞지 않는 나머지
    (예: 1회·아직 활성 — 아직 갈림길 / ≥2회·비활성 — 반박되거나 오래 방치돼 감쇠). 이
    버킷이 필요한 이유: slip-like/지속오개념-like 둘 중 하나로 *강제로* 밀어 넣으면 04c
    §6-4가 실제로 묻는 질문에 답하지 않는 조합까지 답한 것처럼 위장하게 된다
    (`attempt_grading_shadow_report.not_derivable_count`와 동형인 "정직한 잔여 버킷" 관례).

  분모 완전성 불변식: `total_pairs == slip_like_count + persistent_like_count +
  mismatch_count(두 세부 합) + undetermined_count` — 관측된 모든 쌍이 정확히 하나의
  버킷에만 들어간다(테스트로 동결).

────────────────────────────────────────────────────────────────────────────
핵심 트리거 지표 — slip-like 오코칭 가능성 근사 (04e §3 "오진단 비율", §4)
────────────────────────────────────────────────────────────────────────────
slip-like로 분류된 쌍 중, **그 감쇠 전(최고점) confidence가 개입 임계 이상이었던 것의 비율**을
낸다 — "실수인데 실제로 코칭까지 발화됐을 가능성이 있었던 사례"의 근사치이자 이 리포트의 존재
이유(04c §6-4 트리거)다. 개입 임계는 `l4/misconception/intervene.py::_LOW_CONFIDENCE`
(0.5·반례/거꾸로사고 개입이 발화되는 하한)를 `_INTERVENTION_CONFIDENCE_THRESHOLD`로 미러한다
— private 상수를 모듈 경계 넘어 직접 import하지 않고 값을 복제 + 교차참조 주석을 남기는
관례(`l4/socratic/select.py`의 `_PRUNE_THRESHOLD`/`_HALF_LIFE_TURNS` 미러 선례)를 따른다.

**근사 방법(설계 판단, §4)**: `hypothesis.py::reinforce()` 공식을 재시뮬레이션하지 않는다
(이 모듈은 순수 관측이지 재현이 아니다). `evidence_links`의 강화(polarity=+1) 레코드마다
`weight`가 이미 "그 시점 confidence"로 기록돼 있으므로(`api/coach.py::_log_match_evidence`가
`weight=match.confidence`로 적재), 그 쌍의 polarity=+1 레코드 중 **최대 weight**를 감쇠 전
최고점 confidence의 근사치로 쓴다. weight가 전무한(전부 None — 미평가 강화) slip-like 쌍은
판정 불가로 별도 집계(`slip_like_unknown_confidence_count`)하고 비율 분모에서 제외한다(0으로
위장하지 않는다).

────────────────────────────────────────────────────────────────────────────
judge 방향판별 갭 (정직 회계 — 침묵하지 않고 명시)
────────────────────────────────────────────────────────────────────────────
`JudgeVerdict`(EXPRESSES/NOT_EXPRESSES/UNCERTAIN, `l4/misconception/judge.py`)는 (student,
misconception) 단위로 **DB 어디에도 영속되지 않는다** — `judge_filter()`는 필터링된 리스트만
반환하고 개별 판정은 버려진다. 구조화된 shadow 로그(`shadow.py::
MisconceptionJudgeShadowObservation`)조차 **student_id 필드 자체가 없다**(PII 회피 설계)·
DB가 아닌 별도 JSONL·`misconception_semantic_mode == "shadow"`일 때만 동작(이 리포트가 읽는
라이브 게이트와는 별개 스위치)한다. 그래서 이 리포트가 쓸 수 있는 유일한 근사는:
`misconception_judge_enabled=True` 기간에 남은 `evidence_links`가 "judge가 NOT_EXPRESSES를
이미 걸러낸 이후의 생존자"라는 **간접 전제**뿐이다 — EXPRESSES vs UNCERTAIN 구분은 **불가능**
하다. `main()`이 실행 시점의 `get_settings().misconception_judge_enabled`를 읽어 이 전제가
성립하는 기간이었는지를 리포트에 정직하게 표기한다(`judge_enabled` 필드 — 이 리포트가
스캔하는 evidence_links가 통째로 하나의 시점값일 뿐, 기간별 분할 관측은 아니라는 한계도 이와
함께 명시).

**문서 정정 발견(이 태스크 범위 밖 — 기록만)**: `config.py`의 `misconception_judge_enabled`
필드 docstring은 "coach 미배선"·"현재 어떤 런타임 경로도 읽지 않는다"고 적혀 있으나, 실측
(`api/coach.py`의 `_gate` 내부 — `judge_filter` 호출부)은 이미 이 플래그를 읽어 배선돼 있다.
문서가 stale하다(직접 수정은 이 모듈 범위 밖).

────────────────────────────────────────────────────────────────────────────
프라이버시(미성년자 데이터) — 개별 학생 식별자 비노출
────────────────────────────────────────────────────────────────────────────
`student_id`는 (학생, 오개념) 쌍을 묶는 그룹핑 키로만 쓰인다 — `render_report`/
`report_to_json` 어느 출력에도 개별 학생 식별자는 나열되지 않는다(`problem_bank_
coverage.py` 등 기존 리포트의 "집계 수치만 노출" 관례 답습). 이 리포트는 집계 리포트이지
개별 학생 열람 화면이 아니다.

**게이트가 아니다**(다른 관측 리포트 5종과 동일 원칙) — 오진단 비율이 얼마든 exit 1을 내지
않는다. 종료 코드는 성공(0)과 DB 접속 실패 등 입력 오류(2)만 구분한다.

계층 메모(CLAUDE.md 7계층): `harness/`는 빌드타임 도구층 — DB read-only(ORM/쿼리빌더만·원시
SQL 0), LLM·HTTP 0(hermetic). `l4/misconception/hypothesis.py`(순수 감쇠·강화 로직)는
*무수정*이다 — 이 리포트는 런타임 엔진을 재구현하지 않고 이미 영속된 결과만 읽는다.

사용:
    python -m whymath_backend.harness.misconception_slip_report
    python -m whymath_backend.harness.misconception_slip_report --json out/slip_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.db.models.evidence_link import EvidenceLink as EvidenceLinkORM
from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord as MisconceptionHypothesisORM,
)

__all__ = [
    "EvidenceRecord",
    "HypothesisSnapshotRecord",
    "SlipObservationReport",
    "build_report",
    "classify_pair",
    "dump_json",
    "fetch_evidence_history",
    "fetch_hypothesis_snapshot",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# 개입(반례/거꾸로사고) 발화 하한 — l4/misconception/intervene.py::_LOW_CONFIDENCE(0.5) 미러.
# private 상수를 모듈 경계 넘어 직접 import하지 않는다(l4/socratic/select.py의
# _PRUNE_THRESHOLD/_HALF_LIFE_TURNS 교차참조 주석 관례 답습) — 값이 바뀌면 이 주석이 신호다.
_INTERVENTION_CONFIDENCE_THRESHOLD: float = 0.5

_JUDGE_GAP_NOTE: str = (
    "judge 방향판별(EXPRESSES/NOT_EXPRESSES/UNCERTAIN)은 (student, misconception) 단위로 "
    "영속되지 않는다(JudgeVerdict가 judge_filter 내부에서 소비되고 버려짐 · shadow 로그는 "
    "student_id 필드 자체가 없음 — PII 회피 설계). 이 리포트가 쓸 수 있는 신호는 "
    "misconception_judge_enabled=True 기간에 남은 evidence_links가 'NOT_EXPRESSES가 이미 "
    "걸러진 이후의 생존자'라는 간접 전제뿐이다 — EXPRESSES vs UNCERTAIN 구분은 불가능하다. "
    "judge_enabled=False로 실행됐다면 이 전제 자체가 성립하지 않는다(judge가 전혀 개입 안 함)."
)

_JUDGE_DOCSTRING_STALE_NOTE: str = (
    "문서 정정 발견(이 리포트 범위 밖 — 기록만): config.py의 misconception_judge_enabled "
    "필드 docstring은 'coach 미배선' · '현재 어떤 런타임 경로도 읽지 않는다'고 적혀 있으나, "
    "실측(api/coach.py의 _gate 내부 — judge_filter 호출부)은 이미 이 플래그를 읽어 배선돼 "
    "있다 — 문서가 stale하다(직접 수정은 이 모듈 범위 밖)."
)


# ──────────────────────────────────────────────────────────────────────────
# 조회 — 스냅샷/이력 최소 투영(얇은 I/O, 집계 로직 0 — 순수 코어는 build_report)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class HypothesisSnapshotRecord:
    """`misconception_hypothesis` 1행의 최소 투영(관측 전용) — `build_report`의 스냅샷측 입력.

    `student_id`가 `None`이면 원본 행의 `user_id`가 NULL(방어적 nullable 컬럼 — 실제 운영
    경로는 항상 채움)이었다는 뜻이다. `build_report`가 이를 페어링 불가로 *정직하게* 집계하지,
    fetch 계층이 조용히 드롭하지 않는다(`attempt_grading_shadow_report.AttemptRecord.problem
    =None` 인코딩 관례 답습 — 필터링은 집계 계층 몫).
    """

    student_id: uuid.UUID | None
    misconception_id: str
    evidence_count: int
    is_active: bool


@dataclass(slots=True, frozen=True)
class EvidenceRecord:
    """`evidence_links` 1행의 최소 투영(관측 전용) — `build_report`의 이력측 입력.

    `student_id`는 FK NOT NULL이라 결측 가능성이 없다(모델 정본 — `db/models/
    evidence_link.py`). `created_at`은 04e §3 "타임스탬프 간격" 논의를 위해 투영하되, 이번
    슬라이스의 산출 지표(§4 근사)는 count·weight만으로 계산된다 — 시간축 기반 신규 분류축은
    만들지 않는다(태스크 제약·04c §6-4 유예 존중과 정합). `polarity`는 +1(강화 지지)/
    −1(반박)만 유효(DB CHECK) — `build_report`가 +1만 골라 쓴다(이력측 필터링도 집계 계층 몫).
    """

    student_id: uuid.UUID
    misconception_id: str
    polarity: int
    weight: float | None
    created_at: datetime


async def fetch_hypothesis_snapshot(session: AsyncSession) -> list[HypothesisSnapshotRecord]:
    """`misconception_hypothesis` 테이블 전량(활성·비활성 무관) → 스냅샷 최소 투영.

    `is_active`로 필터링하지 않는다 — 비활성(가지치기된) 행이야말로 slip-like 판별의 핵심
    신호다(04e §3 "1회·비강화·즉시감쇠"). 얇은 I/O만 하고 집계·필터링은 `build_report`(순수)
    몫이다(`attempt_grading_shadow_report.fetch_attempt_records` 관례 답습).
    """
    stmt = select(MisconceptionHypothesisORM).order_by(
        MisconceptionHypothesisORM.user_id, MisconceptionHypothesisORM.misconception_id
    )
    result = await session.execute(stmt)
    return [
        HypothesisSnapshotRecord(
            student_id=row.user_id,
            misconception_id=row.misconception_id,
            evidence_count=row.evidence_count,
            is_active=row.is_active,
        )
        for row in result.scalars().all()
    ]


async def fetch_evidence_history(session: AsyncSession) -> list[EvidenceRecord]:
    """`evidence_links` 테이블 전량(강화·반박 모두) → 이력 최소 투영.

    극성으로 필터링하지 않는다 — `build_report`가 polarity=+1(강화)만 골라 쓴다(얇은 I/O·
    집계 로직 0 원칙). 정렬은 진단 조인 관례(`evidence_store.get_evidence_for_student`)와
    동형으로 시간순을 보장한다(디버그·재현성).
    """
    stmt = select(EvidenceLinkORM).order_by(
        EvidenceLinkORM.student_id,
        EvidenceLinkORM.misconception_id,
        EvidenceLinkORM.created_at,
        EvidenceLinkORM.link_id,
    )
    result = await session.execute(stmt)
    return [
        EvidenceRecord(
            student_id=row.student_id,
            misconception_id=row.misconception_id,
            polarity=row.polarity,
            weight=row.weight,
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 분류 + 관측 리포트(순수 코어 — DB·LLM·HTTP 0)
# ──────────────────────────────────────────────────────────────────────────
_Classification = Literal[
    "slip_like", "persistent_like", "undetermined", "mismatch_disagreement", "mismatch_absent"
]


def classify_pair(
    snapshot: HypothesisSnapshotRecord | None, history_reinforcement_count: int
) -> _Classification:
    """(student, misconception) 쌍 1개 → 5-way 분류(04e §3 slip-like/지속오개념-like 정의).

    순서(우선순위 — 정직 회계가 배경우선):
      1. 스냅샷 자체가 없음(`snapshot is None`) → `mismatch_absent`(이력에만 존재).
      2. 스냅샷·이력 evidence_count 불일치 → `mismatch_disagreement`(값이 다르면 어느 쪽도
         신뢰해 강제 분류하지 않는다 — 다수결 임의 처리 금지, CLAUDE.md 정직 회계).
      3. 카운트가 일치할 때만 04e §3 조작적 정의를 적용: `evidence_count==1 and not
         is_active` → `slip_like`; `evidence_count>=2 and is_active` → `persistent_like`.
      4. 그 외(카운트는 일치하나 위 두 패턴 어느 쪽도 아님 — 예: 1회·아직 활성, ≥2회·비활성)
         → `undetermined`(잔여 — 강제 분류하지 않는다).
    """
    if snapshot is None:
        return "mismatch_absent"
    if snapshot.evidence_count != history_reinforcement_count:
        return "mismatch_disagreement"
    if snapshot.evidence_count == 1 and not snapshot.is_active:
        return "slip_like"
    if snapshot.evidence_count >= 2 and snapshot.is_active:
        return "persistent_like"
    return "undetermined"


@dataclass(slots=True, frozen=True)
class SlipObservationReport:
    """slip-like vs 지속오개념-like 관측 집계 결과(불변) — 04c §6-4 트리거 발화용 재료.

    분모 완전성: `total_pairs == slip_like_count + persistent_like_count + mismatch_count +
    undetermined_count`(테스트로 동결). `mismatch_count == mismatch_disagreement_count +
    mismatch_snapshot_absent_count`. 비율 프로퍼티는 분모 0이면 `None`을 낸다(0%로 위장
    금지 — `attempt_grading_shadow_report.ShadowGradingReport` 관례 답습).
    """

    total_pairs: int
    slip_like_count: int
    persistent_like_count: int
    undetermined_count: int
    mismatch_count: int
    mismatch_disagreement_count: int
    mismatch_snapshot_absent_count: int
    slip_like_high_confidence_count: int
    slip_like_unknown_confidence_count: int
    snapshot_anonymous_rows_skipped: int
    judge_enabled: bool
    judge_gap_note: str
    judge_docstring_stale_note: str

    @property
    def slip_like_confidence_known_count(self) -> int:
        """slip-like 중 confidence 근사 판정이 *가능했던* 쌍 수(전부 weight 미기록이면 제외)."""
        return self.slip_like_count - self.slip_like_unknown_confidence_count

    @property
    def slip_like_high_confidence_rate(self) -> float | None:
        """slip-like(판정 가능분) 중 개입 임계 이상 근사 비율 — 04c §6-4 핵심 트리거 지표.

        판정 가능 표본(`slip_like_confidence_known_count`)이 0이면 `None`(분모 없는 0% 위장
        금지 — slip-like 자체가 0건인 경우와 "전부 weight 미기록"인 경우 둘 다 여기 해당).
        """
        denom = self.slip_like_confidence_known_count
        if denom <= 0:
            return None
        return self.slip_like_high_confidence_count / denom


def build_report(
    snapshots: Sequence[HypothesisSnapshotRecord],
    evidence_records: Sequence[EvidenceRecord],
    *,
    judge_enabled: bool,
) -> SlipObservationReport:
    """스냅샷·이력 레코드 → `SlipObservationReport`(순수·부작용 0).

    절차:
      1. 스냅샷을 `(student_id, misconception_id)`로 인덱싱(student_id=None 행은 별도 카운트
         — 페어링 불가·정직 회계).
      2. 이력에서 polarity=+1(강화)만 골라 쌍별 개수·최대 weight(§4 confidence 근사)를 집계.
      3. 두 인덱스의 합집합 키를 정렬 순회하며 `classify_pair`로 5-way 분류.
      4. slip-like로 분류된 쌍은 최대 weight를 개입 임계(§4)와 비교해 근사 초과 여부를 추가
         집계(weight 전무면 판정불가로 별도 카운트).
    """
    snapshot_by_pair: dict[tuple[uuid.UUID, str], HypothesisSnapshotRecord] = {}
    anonymous_skipped = 0
    for snap in snapshots:
        if snap.student_id is None:
            anonymous_skipped += 1
            continue
        # DB UNIQUE(user_id, misconception_id)가 유일성을 보장한다 — 방어적으로 마지막 값 승자
        # (어댑터 테스트가 중복을 넣어도 크래시하지 않음, 실제로는 발생 안 함).
        snapshot_by_pair[(snap.student_id, snap.misconception_id)] = snap

    reinforcement_count: dict[tuple[uuid.UUID, str], int] = {}
    max_weight: dict[tuple[uuid.UUID, str], float | None] = {}
    for ev in evidence_records:
        if ev.polarity != 1:
            continue  # 반박(-1)은 "강화 횟수"가 아니다(04e §3) — 슬립 판별 신호는 +1만.
        key = (ev.student_id, ev.misconception_id)
        reinforcement_count[key] = reinforcement_count.get(key, 0) + 1
        if ev.weight is not None:
            weight = ev.weight
            prior = max_weight.get(key)
            max_weight[key] = weight if prior is None else max(prior, weight)
        else:
            max_weight.setdefault(key, None)

    all_pairs = sorted(
        set(snapshot_by_pair) | set(reinforcement_count),
        key=lambda pair: (str(pair[0]), pair[1]),
    )

    slip_like = 0
    persistent_like = 0
    undetermined = 0
    mismatch_disagreement = 0
    mismatch_absent = 0
    slip_high_conf = 0
    slip_unknown_conf = 0

    for key in all_pairs:
        # 위 for snap in snapshots 루프의 snap(HypothesisSnapshotRecord, non-optional)와 이름이
        # 겹치면 mypy가 재대입을 타입 불일치로 본다(같은 함수 스코프 — 변수명을 분리해 회피).
        matched_snapshot = snapshot_by_pair.get(key)
        hist_count = reinforcement_count.get(key, 0)
        label = classify_pair(matched_snapshot, hist_count)
        if label == "mismatch_absent":
            mismatch_absent += 1
        elif label == "mismatch_disagreement":
            mismatch_disagreement += 1
        elif label == "undetermined":
            undetermined += 1
        elif label == "persistent_like":
            persistent_like += 1
        else:  # "slip_like"
            slip_like += 1
            hw = max_weight.get(key)
            if hw is None:
                slip_unknown_conf += 1
            elif hw >= _INTERVENTION_CONFIDENCE_THRESHOLD:
                slip_high_conf += 1

    return SlipObservationReport(
        total_pairs=len(all_pairs),
        slip_like_count=slip_like,
        persistent_like_count=persistent_like,
        undetermined_count=undetermined,
        mismatch_count=mismatch_disagreement + mismatch_absent,
        mismatch_disagreement_count=mismatch_disagreement,
        mismatch_snapshot_absent_count=mismatch_absent,
        slip_like_high_confidence_count=slip_high_conf,
        slip_like_unknown_confidence_count=slip_unknown_conf,
        snapshot_anonymous_rows_skipped=anonymous_skipped,
        judge_enabled=judge_enabled,
        judge_gap_note=_JUDGE_GAP_NOTE,
        judge_docstring_stale_note=_JUDGE_DOCSTRING_STALE_NOTE,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def _format_pct(count: int, total: int) -> str:
    """백분율 포맷(분모 0은 호출 전 상위에서 걸러짐 — 이 함수는 total>0 전제)."""
    return f"{count / total:.2%}"


def render_report(report: SlipObservationReport) -> str:
    """리포트를 마크다운으로 렌더(순수·입력 외 계산 없음).

    "데이터없음"(관측된 쌍 자체가 0)과 "0건"(관측은 됐으나 특정 유형이 0건)을 문구로
    구분한다(정직 회계 — `problem_bank_coverage.py` 관례 답습). 개별 student_id는 어디에도
    나열하지 않는다(집계 수치만).
    """
    lines = [
        "# root/symptom·slip 판별 관측 리포트 (MISC-05)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**. 새 분류축 0(04c §6-4 유예 존중) — 기존 "
        "신호(가설 감쇠·강화 횟수·is_active)만 재해석한다(04e §3).",
        "",
    ]

    if report.total_pairs == 0:
        lines += [
            "## 관측 대상",
            "",
            "- (학생, 오개념) 쌍: **데이터없음**(가설 스냅샷·강화 증거 이력이 모두 비어 있음 "
            "— 관측된 것이 0건인 게 아니라 관측 대상 자체가 없음).",
            "",
        ]
    else:
        total = report.total_pairs
        lines += [
            f"## 관측 대상 — 총 {total}쌍",
            "",
            f"- slip-like(1회·비강화·즉시감쇠 근사 — evidence_count==1·is_active==False): "
            f"**{report.slip_like_count}**건 ({_format_pct(report.slip_like_count, total)})",
            f"- 지속오개념-like(≥2회 강화·is_active==True 유지): "
            f"**{report.persistent_like_count}**건 "
            f"({_format_pct(report.persistent_like_count, total)})",
            f"- 불일치(스냅샷↔이력 evidence_count 불일치 — 다수결 임의분류 금지): "
            f"**{report.mismatch_count}**건 ({_format_pct(report.mismatch_count, total)})",
            f"  - 값 불일치(스냅샷·이력 둘 다 있으나 evidence_count가 다름): "
            f"{report.mismatch_disagreement_count}건",
            f"  - 스냅샷 부재(이력엔 강화 증거가 있으나 가설 스냅샷 자체가 없음): "
            f"{report.mismatch_snapshot_absent_count}건",
            f"- 잔여(카운트는 일치하나 slip-like/지속오개념-like 정의 밖 — 예: 1회·아직 "
            f"활성 또는 ≥2회·비활성): **{report.undetermined_count}**건 "
            f"({_format_pct(report.undetermined_count, total)})",
            "",
            "## 핵심 트리거 지표 — slip 오코칭 가능성 근사 (04e §3, §4 근사)",
            "",
        ]
        if report.slip_like_count == 0:
            lines.append(
                "- slip-like로 분류된 쌍: **0건**(관측은 이뤄졌음 — 데이터없음이 아니라 이 "
                "유형이 관측되지 않음). 트리거 지표 계산 대상이 없다."
            )
        else:
            known = report.slip_like_confidence_known_count
            lines.append(
                f"- slip-like {report.slip_like_count}건 중 confidence 근사 판정 가능 "
                f"{known}건."
            )
            if report.slip_like_unknown_confidence_count > 0:
                lines.append(
                    f"  - 판정 불가(강화 증거에 weight 미기록): "
                    f"{report.slip_like_unknown_confidence_count}건(비율 분모에서 제외 — "
                    "0으로 위장하지 않음)."
                )
            rate = report.slip_like_high_confidence_rate
            if rate is None:
                lines.append(
                    "  - 개입 임계 초과 비율: **계산 불가**(판정 가능 표본 0건 — 데이터없음)."
                )
            else:
                lines.append(
                    f"  - 개입 임계({_INTERVENTION_CONFIDENCE_THRESHOLD:.1f}) 이상 근사: "
                    f"**{report.slip_like_high_confidence_count}건 ({rate:.2%})** — '실수인데 "
                    "실제로 코칭까지 발화됐을 가능성이 있었던 사례'의 근사치. 04c §6-4 '명시 "
                    "도입 결정' 트리거 재료다(이 리포트 자체는 결정을 내리지 않는다)."
                )
        lines.append("")

    lines += [
        "## judge 방향판별 갭 (정직 회계)",
        "",
        f"- 이번 실행 시점 `misconception_judge_enabled` = **{report.judge_enabled}**.",
        f"  - {report.judge_gap_note}",
        f"  - {report.judge_docstring_stale_note}",
        "",
        "## 부가 정직 회계",
        "",
        f"- 학생 식별자 결측으로 페어링에서 제외된 스냅샷 행: "
        f"{report.snapshot_anonymous_rows_skipped}건.",
        "",
    ]
    return "\n".join(lines)


def report_to_json(report: SlipObservationReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(분모 없는 비율은 `None` 그대로 보존, 개별 student_id 0건)."""
    return {
        "total_pairs": report.total_pairs,
        "slip_like_count": report.slip_like_count,
        "persistent_like_count": report.persistent_like_count,
        "undetermined_count": report.undetermined_count,
        "mismatch_count": report.mismatch_count,
        "mismatch_disagreement_count": report.mismatch_disagreement_count,
        "mismatch_snapshot_absent_count": report.mismatch_snapshot_absent_count,
        "slip_like_high_confidence_count": report.slip_like_high_confidence_count,
        "slip_like_unknown_confidence_count": report.slip_like_unknown_confidence_count,
        "slip_like_confidence_known_count": report.slip_like_confidence_known_count,
        "slip_like_high_confidence_rate": report.slip_like_high_confidence_rate,
        "intervention_confidence_threshold": _INTERVENTION_CONFIDENCE_THRESHOLD,
        "snapshot_anonymous_rows_skipped": report.snapshot_anonymous_rows_skipped,
        "judge_enabled": report.judge_enabled,
        "judge_gap_note": report.judge_gap_note,
        "judge_docstring_stale_note": report.judge_docstring_stale_note,
    }


def dump_json(report: SlipObservationReport) -> str:
    """`report_to_json`을 결정론 JSON 문자열로(`sort_keys=True` — 같은 입력→같은 바이트)."""
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 접속·출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI — DB에서 스냅샷·이력을 읽어 slip 관측 리포트를 출력. **게이트가 아니다**(항상
    exit 0, DB 접속·조회 실패만 exit 2 — exit 1 경로는 존재하지 않는다).

    `misconception_judge_enabled`는 이 함수가 실행 시점 값을 직접 읽어 `build_report`에
    넘긴다 — 리포트가 자기 실행 시점의 플래그 상태를 정직하게 표기하게 하기 위함(04e §3).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.misconception_slip_report",
        description=(
            "root/symptom·slip 판별 관측 리포트(MISC-05) — misconception_hypothesis "
            "스냅샷과 evidence_links 이력을 교차해 slip-like/지속오개념-like/불일치를 "
            "관측한다. 게이트 아님(항상 exit 0, DB 접속 실패만 exit 2)."
        ),
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    judge_enabled = get_settings().misconception_judge_enabled

    async def _run() -> SlipObservationReport:
        # lazy import — CLI를 실제로 실행할 때만 DB 세션 팩토리를 물게 한다(다른 함수의 모듈
        # top-level import는 순수 유지 — attempt_grading_shadow_report.py 관례 답습).
        from whymath_backend.db.session import get_session

        async for session in get_session():
            snapshots = await fetch_hypothesis_snapshot(session)
            evidence_records = await fetch_evidence_history(session)
            return build_report(snapshots, evidence_records, judge_enabled=judge_enabled)
        raise RuntimeError("DB 세션을 얻지 못함")  # pragma: no cover — get_session은 항상 1회 yield

    try:
        report = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 접속·조회 실패는 타입명과 함께 보고 후 exit 2
        print(f"입력/접속 오류({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
