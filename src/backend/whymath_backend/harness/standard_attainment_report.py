"""학생별 성취기준 도달 관측 리포트 — ASM-05(수요측·ARCH-18 공급측 커버리지의 짝).

ARCH-18 `problem_bank_coverage`가 **공급측**(문항 코퍼스가 성취기준을 얼마나 덮는가)을 관측한다면,
이 모듈은 **수요측**(학생들의 최신 숙달 측정이 성취기준 도달로 얼마나 번역되는가)을 관측한다.
새 mastery/진도 테이블·마이그레이션 0 — 전부 기존 자산의 투영이다(교육과정은 Overlay 원칙):

    ConceptMasteryHistory  (user·concept별 최신 측정 1건 — DISTINCT ON,
      |                     `l2/concept_diagnosis.py` 선례)
      → Concept.concept_id → Concept.code             (개념 축 해소 — 느슨참조라 미해소 가능)
      → AtomNode.code → AtomNode.standard_codes       (원자 축 투영 → 성취기준 코드 TEXT[])
      → standards_v1 대장(`load_standards` 재사용)      (개정별 분모·코드 3분류 — ARCH-18 관례)

**게이트가 아니다**(`problem_bank_coverage`·`assessment_seat_reach_report`와 동일 원칙) — 도달이
0이어도 exit 1을 내지 않는다(종료 코드는 0=성공 / 2=입력·DB 오류만). 도달률에 임계를 걸어 CI를
빨갛게 만드는 순간 "관측 좌석"이라는 이 도구의 용도가 파괴된다.

도달 경계는 **기존 L4 정본 숙달 0.8을 재사용**한다(`l4/lthc/adapt.py::_MASTERED_THRESHOLD` —
`wh1_evaluation._RECOVERY_MASTERY_THRESHOLD`가 이미 재사용하는 선례·임계 신설 금지). 경계 포함
방향(≥)도 정본과 동일하다("경계 포함은 상위 라벨" — adapt.py 주석).

**정직 회계**(CLAUDE.md 침묵 실패 금지·NO_DATA 정직 — acceptance ③):
  - 측정 사용자 0이면 비율은 None·렌더는 "데이터없음"(0.0% 위장 금지 — ARCH-18 `_pct` 관례).
  - 서로 다른 결손 상태를 하나로 뭉개지 않는다: concept 미해소(개념 축 밖 concept_id) /
    원자 축 밖 개념(concept은 있으나 atom_node 없음) / 매핑 빈 원자(standard_codes 빈 배열) /
    다른 개정 코드 / 대장 밖 코드 — 각각 별도 카운터.
  - 분모 이중 회계: ①`user_profile` role=STUDENT 전체 vs ②측정 이력 보유 사용자. 두 수를
    혼동하지 않으며, 느슨참조(FK 아님) 불일치(user_profile 밖 측정 user_id)도 계상한다.
  - 대상 개정 코드 중 원자 매핑이 없는 코드는 "미도달"이 아니라 **관측 불가**로 구분한다 —
    0도달 목록은 관측 가능(매핑 ∩ 대상 개정) 코드 위에서만 정의된다.

**개인 식별자 미노출**: 렌더/JSON 어디에도 user_id를 나열하지 않는다 — 집계만(미성년자 데이터
원칙·CLAUDE.md "개인 식별 가능한 분석 결과 외부 노출 금지").

계층 메모(CLAUDE.md 7계층): harness는 횡단 관측 인프라라 layers 계약 밖이다(pyproject 주석 —
"harness/whs는 L3/L4 하네스라 상위 호출이 정상"). L1/L2 영속 모델을 *조회만* 하고 L4 임계 상수를
재사용하며, API/UI 노출은 없다(관측 좌석 — 학생 대면 노출은 범위 밖·acceptance ⑦).

사용:
    python -m whymath_backend.harness.standard_attainment_report
    python -m whymath_backend.harness.standard_attainment_report --json out/attainment.json
    python -m whymath_backend.harness.standard_attainment_report --revision "2015 개정"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.harness.problem_bank_coverage import (
    DEFAULT_REVISION,
    DEFAULT_STANDARDS_PATH,
    StandardsCatalog,
    _pct,
    _sorted_counts,
    load_standards,
)
from whymath_backend.l4.lthc.adapt import _MASTERED_THRESHOLD
from whymath_backend.schema.enums import Role

__all__ = [
    "AttainmentInputs",
    "LatestMeasurement",
    "StandardAttainmentReport",
    "build_report",
    "collect_attainment_inputs",
    "dump_json",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# 도달 경계 — **재선언하지 않고 정본에서 가져온다**(임계 신설 금지·acceptance ②).
# `l4/lthc/adapt.py::_MASTERED_THRESHOLD`(0.8)가 유일 정본이고, `harness/wh1_evaluation.py`의
# `_RECOVERY_MASTERY_THRESHOLD`가 이미 같은 경로로 재사용한다(:112 import 선례). harness는
# 7계층 layers 계약 밖(무제약)이라 이 L4 import가 lint-imports를 깨지 않는다.
_ATTAINMENT_MASTERY_THRESHOLD: float = float(_MASTERED_THRESHOLD)


@dataclass(slots=True, frozen=True)
class LatestMeasurement:
    """(user, concept) 최신 측정 1건의 코드 축 투영 — `collect_attainment_inputs`의 원시 산출.

    결손 상태 3종을 필드 조합으로 구분한다(조용한 유실 금지 — 각각 다른 카운터로 계상):
      - `concept_code is None`  → concept_id가 `concept` 테이블에 없다(느슨참조 미해소).
      - `atom_code is None`     → concept은 있으나 `atom_node` 투영에 없다(원자 축 밖 개념).
      - `standard_codes == ()`  → 원자는 있으나 성취기준 매핑이 빈 배열이다(매핑 부재).
    `standard_codes`는 `atom_code`가 None이면 항상 빈 튜플이다(원자가 없으면 매핑도 없다 —
    구분은 `atom_code` 쪽이 담당). `profile_role is None`은 `user_profile` 밖 측정 user_id.
    `mastery`는 DB Numeric(3,2)이 Decimal로 오는 것을 collect가 float로 정규화한 값이다.
    """

    user_id: uuid.UUID
    concept_id: uuid.UUID
    mastery: float | None
    concept_code: str | None
    atom_code: str | None
    standard_codes: tuple[str, ...]
    profile_role: Role | None


@dataclass(slots=True, frozen=True)
class AttainmentInputs:
    """`collect_attainment_inputs`의 DB 원시 조회 결과 — `build_report`의 유일한 입력.

    성취기준 대장(파일)은 여기 담지 않는다 — DB 축(이 클래스)과 파일 축(catalog)을 분리해야
    단위테스트가 실 DB 없이 분류·집계 로직 전체를 검증할 수 있다(ASM-01 `SeatCounts` 관례).
    """

    student_profile_count: int
    latest_measurements: tuple[LatestMeasurement, ...]
    atom_mapped_codes: tuple[str, ...]  # atom_node.standard_codes distinct 전량(정렬)


@dataclass(slots=True, frozen=True)
class StandardAttainmentReport:
    """도달 관측 결과 전량(불변·렌더/직렬화의 단일 입력)."""

    revision: str
    threshold: float
    # ── 공급 축 요약(도달 판정이 *가능한* 코드) ──
    standards_record_count: int
    target_codes_total: int
    atom_mapped_code_count: int
    observable_codes: tuple[str, ...]  # 매핑 ∩ 대상 개정(정렬) — 도달 판정 가능 코드
    unobservable_codes: tuple[str, ...]  # 대상 개정 − 매핑(정렬) — "관측 불가"(미도달 아님)
    mapped_other_revision_code_count: int
    mapped_unknown_code_count: int
    # ── 분모 이중 회계 ──
    student_profile_count: int
    measured_user_count: int
    measured_users_outside_profile: int
    measured_users_non_student: int
    # ── 수요 축 집계(개별 user_id는 담지 않는다 — 집계만) ──
    latest_measurement_count: int
    attained_measurement_count: int
    attained_user_code_pair_count: int
    users_with_any_attainment: int
    per_user_attained_min: int | None
    per_user_attained_max: int | None
    per_user_attained_mean: float | None
    attained_users_per_code: dict[str, int]  # 대상 개정 코드 → 도달 사용자 수(≥1만 수록)
    # ── 정직 회계 ──
    measurements_without_mastery: int
    measurements_concept_unresolved: int
    measurements_outside_atom_axis: int
    measurements_with_empty_standard_codes: int
    attained_other_revision_codes: dict[str, int]  # 도달이 가리킨 다른 개정 코드 → 사용자 수
    attained_unknown_codes: dict[str, int]  # 도달이 가리킨 대장 밖 코드 → 사용자 수

    @property
    def observable_code_count(self) -> int:
        return len(self.observable_codes)

    @property
    def unobservable_code_count(self) -> int:
        return len(self.unobservable_codes)

    @property
    def attained_code_count(self) -> int:
        """도달 사용자가 1명 이상인 대상 개정 코드 수."""
        return len(self.attained_users_per_code)

    @property
    def code_attainment_rate(self) -> float | None:
        """도달 코드 / 관측 가능 코드 — 측정 사용자 0 또는 분모 0이면 None(가짜 0/1 금지).

        측정 사용자가 0인데 0.0%를 내면 "측정했더니 아무도 도달 못함"으로 위장된다 —
        '측정 이력 0'은 별도 상태다(acceptance ③).
        """
        if self.measured_user_count == 0 or self.observable_code_count == 0:
            return None
        return self.attained_code_count / self.observable_code_count

    @property
    def zero_attainment_codes(self) -> tuple[str, ...]:
        """관측 가능 코드 중 도달 사용자 0명인 코드(정렬) — 관측 불가 코드는 여기 안 들어간다."""
        return tuple(
            sorted(c for c in self.observable_codes if c not in self.attained_users_per_code)
        )


async def collect_attainment_inputs(session: AsyncSession) -> AttainmentInputs:
    """학생 분모 + (user, concept)별 최신 측정 + 원자 매핑 코드 전량을 조회(유일한 DB 접근 지점).

    전부 ORM 쿼리빌더로만 조립한다(원시 SQL 금지 — CLAUDE.md 원칙). `func.unnest`는 SQLAlchemy
    `func` 네임스페이스를 통한 표준 함수 호출이라 원시 SQL 문자열이 아니다(ASM-01
    `func.jsonb_array_length` 선례). 최신 1건은 PostgreSQL DISTINCT ON —
    `l2/concept_diagnosis.py:80-94`와 같은 `.distinct(...)+order_by(..., desc)` 조합이며, 여기는
    (user_id, concept_id) 쌍 기준이다. 조인 3종(Concept·AtomNode·UserProfile)은 전부 키가
    unique/PK라 1:1 — DISTINCT ON 행이 불어나지 않는다.
    """
    # ① 학생 분모 — user_profile role=STUDENT 전체 수(이중 회계의 첫째 축).
    student_count_result = await session.execute(
        select(func.count()).select_from(UserProfile).where(UserProfile.role == Role.STUDENT)
    )
    student_profile_count: int = student_count_result.scalar_one()

    # ② (user, concept)별 최신 측정 1건 + 코드 축·프로필 축 투영(전부 outer join — 결손도 행으로).
    latest_stmt = (
        select(
            ConceptMasteryHistory.user_id,
            ConceptMasteryHistory.concept_id,
            ConceptMasteryHistory.mastery,
            Concept.code,
            AtomNode.code,
            AtomNode.standard_codes,
            UserProfile.role,
        )
        .outerjoin(Concept, ConceptMasteryHistory.concept_id == Concept.concept_id)
        .outerjoin(AtomNode, Concept.code == AtomNode.code)
        .outerjoin(UserProfile, ConceptMasteryHistory.user_id == UserProfile.user_id)
        .distinct(ConceptMasteryHistory.user_id, ConceptMasteryHistory.concept_id)
        .order_by(
            ConceptMasteryHistory.user_id,
            ConceptMasteryHistory.concept_id,
            ConceptMasteryHistory.measured_at.desc(),
        )
    )
    rows = (await session.execute(latest_stmt)).all()
    measurements = tuple(
        LatestMeasurement(
            user_id=row[0],
            concept_id=row[1],
            # Numeric(3,2)은 Decimal로 온다 — 경계 비교 전에 float로 정규화(모듈 docstring).
            mastery=float(row[2]) if row[2] is not None else None,
            concept_code=row[3],
            atom_code=row[4],
            standard_codes=tuple(row[5]) if row[5] is not None else (),
            profile_role=row[6],
        )
        for row in rows
    )

    # ③ 원자 축이 매핑하는 distinct 성취기준 코드 전량(공급 축 요약의 재료).
    mapped_stmt = select(func.unnest(AtomNode.standard_codes)).distinct()
    mapped_codes = tuple(sorted((await session.execute(mapped_stmt)).scalars().all()))

    return AttainmentInputs(
        student_profile_count=student_profile_count,
        latest_measurements=measurements,
        atom_mapped_codes=mapped_codes,
    )


def build_report(
    inputs: AttainmentInputs, catalog: StandardsCatalog, *, revision: str
) -> StandardAttainmentReport:
    """DB 조회 결과 + 성취기준 대장 → `StandardAttainmentReport`(순수·부작용 0·DB 세션 불요).

    분류·집계 전량을 여기서 한다(collect가 아니라) — 단위테스트가 실 DB 없이 경계값·결손 계상·
    3분류·결정론을 직접 검증할 수 있게 하기 위함이다(ASM-01 `build_report` 관례). 입력 순서에
    의존하지 않는다(집합·Counter 기반 + 렌더 시점 정렬 — 결정론).
    """
    target_codes = catalog.codes_for(revision)
    all_codes = catalog.unique_codes

    # ── 공급 축: 원자 매핑 코드 3분류(대상 개정/다른 개정/대장 밖 — ARCH-18 관례) ──
    observable = tuple(sorted(c for c in inputs.atom_mapped_codes if c in target_codes))
    mapped_other = sum(
        1 for c in inputs.atom_mapped_codes if c in all_codes and c not in target_codes
    )
    mapped_unknown = sum(1 for c in inputs.atom_mapped_codes if c not in all_codes)
    unobservable = tuple(sorted(target_codes - set(observable)))

    # ── 수요 축: 사용자·측정 순회(집합 기반 — 입력 순서 무의존) ──
    measured_users: set[uuid.UUID] = set()
    users_outside_profile: set[uuid.UUID] = set()
    users_non_student: set[uuid.UUID] = set()
    no_mastery = concept_unresolved = outside_atom = empty_codes = 0
    attained_measurements = 0
    attained_target_pairs: set[tuple[uuid.UUID, str]] = set()
    attained_other: dict[str, set[uuid.UUID]] = {}
    attained_unknown: dict[str, set[uuid.UUID]] = {}

    for m in inputs.latest_measurements:
        measured_users.add(m.user_id)
        if m.profile_role is None:
            users_outside_profile.add(m.user_id)  # 느슨참조 불일치 — 조용히 접지 않는다.
        elif m.profile_role is not Role.STUDENT:
            users_non_student.add(m.user_id)
        # 코드 축 결손 3상태 — 서로 다른 상태이므로 각각 계상(상호 배타 elif).
        if m.concept_code is None:
            concept_unresolved += 1
        elif m.atom_code is None:
            outside_atom += 1
        elif not m.standard_codes:
            empty_codes += 1
        # 도달 판정 — mastery 없음은 도달도 미도달도 아닌 별도 상태.
        if m.mastery is None:
            no_mastery += 1
            continue
        if m.mastery < _ATTAINMENT_MASTERY_THRESHOLD:
            continue
        attained_measurements += 1
        # 도달 측정의 코드 전파 — 코드 3분류(대상/다른 개정/대장 밖)를 여기서도 유지.
        for code in m.standard_codes:
            if code in target_codes:
                attained_target_pairs.add((m.user_id, code))
            elif code in all_codes:
                attained_other.setdefault(code, set()).add(m.user_id)
            else:
                attained_unknown.setdefault(code, set()).add(m.user_id)

    # 사용자별 도달 코드 수 — 도달 0인 측정 사용자도 분포에 0으로 들어간다(min이 0일 수 있다).
    per_user: dict[uuid.UUID, int] = {u: 0 for u in measured_users}
    for pair_user_id, _code in attained_target_pairs:
        per_user[pair_user_id] += 1
    per_code: Counter[str] = Counter(code for _u, code in attained_target_pairs)

    measured_user_count = len(measured_users)
    pair_count = len(attained_target_pairs)
    per_user_mean = (pair_count / measured_user_count) if measured_user_count else None
    per_user_min = min(per_user.values()) if per_user else None
    per_user_max = max(per_user.values()) if per_user else None

    return StandardAttainmentReport(
        revision=revision,
        threshold=_ATTAINMENT_MASTERY_THRESHOLD,
        standards_record_count=catalog.record_count,
        target_codes_total=len(target_codes),
        atom_mapped_code_count=len(inputs.atom_mapped_codes),
        observable_codes=observable,
        unobservable_codes=unobservable,
        mapped_other_revision_code_count=mapped_other,
        mapped_unknown_code_count=mapped_unknown,
        student_profile_count=inputs.student_profile_count,
        measured_user_count=measured_user_count,
        measured_users_outside_profile=len(users_outside_profile),
        measured_users_non_student=len(users_non_student),
        latest_measurement_count=len(inputs.latest_measurements),
        attained_measurement_count=attained_measurements,
        attained_user_code_pair_count=pair_count,
        users_with_any_attainment=sum(1 for n in per_user.values() if n > 0),
        per_user_attained_min=per_user_min,
        per_user_attained_max=per_user_max,
        per_user_attained_mean=per_user_mean,
        attained_users_per_code=dict(per_code),
        measurements_without_mastery=no_mastery,
        measurements_concept_unresolved=concept_unresolved,
        measurements_outside_atom_axis=outside_atom,
        measurements_with_empty_standard_codes=empty_codes,
        attained_other_revision_codes={c: len(users) for c, users in attained_other.items()},
        attained_unknown_codes={c: len(users) for c, users in attained_unknown.items()},
    )


def render_report(report: StandardAttainmentReport, *, max_listed: int = 40) -> str:
    """도달 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음·정렬 고정).

    0도달 코드 목록은 `max_listed`개까지만 본문에 싣고 나머지는 건수로 요약한다(전량은 `--json`
    산출물에 있다). 잘렸다는 사실 자체를 문장으로 남긴다 — 조용한 절단 금지(ARCH-18 관례).
    측정 사용자 0이면 사용자·코드 축 집계를 "데이터없음"으로 표기한다 — 0.0%로 위장하지 않는다.
    """
    lines: list[str] = [
        "# 성취기준 도달 관측 리포트 (ASM-05)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(도달이 0이어도 실패시키지 않는다).",
        "> ARCH-18 `problem_bank_coverage`(공급측: 문항 코퍼스가 성취기준을 얼마나 덮는가)의 짝 —",
        "> 수요측(학생별 최신 숙달 측정이 성취기준 도달로 얼마나 번역되는가)을 관측한다.",
        f"> 도달 경계: mastery ≥ **{report.threshold:.2f}** — L4 LTHC 정본"
        "(`_MASTERED_THRESHOLD`) 재사용(임계 신설 0).",
        "",
        "## 0. 공급 축 요약 — 도달 판정이 *가능한* 코드",
        "",
        f"- 대상 개정: **{report.revision}** · 대장 고유 코드 **{report.target_codes_total}**"
        f" (대장 레코드 {report.standards_record_count})",
        f"- 원자(`atom_node.standard_codes`) 매핑 distinct 코드:"
        f" **{report.atom_mapped_code_count}** — 대상 개정 {report.observable_code_count} ·"
        f" 다른 개정 {report.mapped_other_revision_code_count} ·"
        f" 대장 밖 {report.mapped_unknown_code_count}",
        f"- 관측 가능 코드(원자 매핑 ∩ 대상 개정): **{report.observable_code_count}**"
        f" / {report.target_codes_total}",
        f"- 관측 불가 코드(대상 개정이나 원자 매핑 없음): **{report.unobservable_code_count}**"
        " — *미도달이 아니라 도달 판정 자체가 불가*다(전량은 `--json`의 `unobservable_codes`·"
        "공급 공백 해소는 ARCH-18 공급측 리포트의 몫).",
        "",
        "## 1. 분모 이중 회계 — 두 수를 혼동하지 않는다",
        "",
        "| 분모 | 값 |",
        "|---|---:|",
        f"| ① 등록 학생(`user_profile` role=STUDENT) | {report.student_profile_count} |",
        "| ② 측정 사용자(`concept_mastery_history` distinct user)"
        f" | {report.measured_user_count} |",
        "",
        "- ①은 등록 모집단, ②는 측정 이력이 실제로 있는 사용자다. `user_id`는 느슨참조(FK 아님)라"
        " 두 집합이 일치할 보장이 없다 — 불일치도 조용히 접지 않고 아래에 계상한다.",
        f"- ② 중 `user_profile` 밖 user_id: **{report.measured_users_outside_profile}**",
        f"- ② 중 role≠STUDENT: **{report.measured_users_non_student}**",
        "",
        "## 2. 수요 축 — 사용자별 도달 집계",
        "",
        "> 개별 학생 식별자(user_id)는 이 리포트 어디에도 나열하지 않는다(집계만 — 미성년자"
        " 데이터 원칙).",
        "",
    ]
    if report.measured_user_count == 0:
        lines.append(
            "- 측정 사용자 **0** — 사용자 축 집계는 **데이터없음**"
            "(가짜 0이나 백분율 표기로 위장하지 않는다)."
        )
    else:
        mean_cell = (
            f"{report.per_user_attained_mean:.2f}"
            if report.per_user_attained_mean is not None
            else "데이터없음"
        )
        lines += [
            "| 지표 | 값 |",
            "|---|---:|",
            f"| 최신 측정 (사용자,개념) 쌍 | {report.latest_measurement_count} |",
            f"| 그중 도달 측정(mastery ≥ {report.threshold:.2f})"
            f" | {report.attained_measurement_count} |",
            f"| 도달 (사용자, 대상 개정 코드) 쌍 | {report.attained_user_code_pair_count} |",
            f"| 도달 코드 1개 이상 사용자 | {report.users_with_any_attainment} |",
            f"| 사용자당 도달 코드 평균 | {mean_cell} |",
            f"| 사용자당 도달 코드 최소~최대 | {report.per_user_attained_min}"
            f"~{report.per_user_attained_max} |",
        ]

    lines += ["", "## 3. 코드 축 — 코드별 도달 사용자 수", ""]
    if report.measured_user_count == 0:
        lines.append(
            "- 측정 사용자 0 — 코드 축 도달 집계는 **데이터없음**"
            "(측정이 없는데 '아무도 도달하지 못함'이라고 쓰지 않는다)."
        )
    else:
        lines.append(
            f"- 도달 코드(도달 사용자 ≥ 1): **{report.attained_code_count}** / 관측 가능"
            f" {report.observable_code_count}"
            f" ({_pct(report.attained_code_count, report.observable_code_count)})"
        )
        lines += [
            "",
            "### 3.1 도달 상위 코드 (도달 사용자 수)",
            "",
            "| 성취기준 | 도달 사용자 |",
            "|---|---:|",
        ]
        for code, count in _sorted_counts(report.attained_users_per_code)[:20]:
            lines.append(f"| `{code}` | {count} |")

        shown = report.zero_attainment_codes[:max_listed]
        remainder = len(report.zero_attainment_codes) - len(shown)
        lines += ["", "### 3.2 0도달 코드 (관측 가능 코드 중)", ""]
        if not report.zero_attainment_codes:
            lines.append("- 없음(관측 가능 전 코드에 도달 사용자가 1명 이상).")
        else:
            lines.append("- " + " ".join(f"`{c}`" for c in shown))
            if remainder > 0:
                lines.append(
                    f"- …외 **{remainder}**건(전량은 `--json` 산출물의 `zero_attainment_codes`)."
                )

    lines += [
        "",
        "## 4. 정직 회계 (누락·미지 값)",
        "",
        "> 조용히 버리지 않는다 — 아래 상태들은 서로 다른 상태이며 하나로 뭉개지 않는다.",
        "",
        "| 항목 | 건수 |",
        "|---|---:|",
        f"| mastery 값 없는 최신 측정 | {report.measurements_without_mastery} |",
        "| concept 미해소 측정(concept_id가 `concept`에 없음)"
        f" | {report.measurements_concept_unresolved} |",
        "| 원자 축 밖 개념 측정(`concept`은 있으나 `atom_node`에 없음)"
        f" | {report.measurements_outside_atom_axis} |",
        "| 성취기준 매핑 없는 원자 측정(`standard_codes` 빈 배열)"
        f" | {report.measurements_with_empty_standard_codes} |",
        f"| 도달이 가리킨 다른 개정 코드(종) | {len(report.attained_other_revision_codes)} |",
        f"| 도달이 가리킨 대장 밖 코드(종) | {len(report.attained_unknown_codes)} |",
    ]
    if report.attained_other_revision_codes:
        lines += ["", f"### 4.1 {report.revision} 밖(다른 개정) 도달 코드 — 도달 사용자 수", ""]
        for code, count in _sorted_counts(report.attained_other_revision_codes):
            lines.append(f"- `{code}` — {count}명")
    if report.attained_unknown_codes:
        lines += ["", "### 4.2 대장에 없는 도달 코드 — 도달 사용자 수", ""]
        for code, count in _sorted_counts(report.attained_unknown_codes):
            lines.append(f"- `{code}` — {count}명")
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: StandardAttainmentReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정).

    user_id는 어디에도 싣지 않는다(집계만 — 모듈 docstring 개인 식별자 미노출 원칙).
    """
    return {
        "revision": report.revision,
        "threshold": report.threshold,
        "supply": {
            "standards_record_count": report.standards_record_count,
            "target_codes_total": report.target_codes_total,
            "atom_mapped_code_count": report.atom_mapped_code_count,
            "observable_code_count": report.observable_code_count,
            "observable_codes": list(report.observable_codes),
            "unobservable_code_count": report.unobservable_code_count,
            "unobservable_codes": list(report.unobservable_codes),
            "mapped_other_revision_code_count": report.mapped_other_revision_code_count,
            "mapped_unknown_code_count": report.mapped_unknown_code_count,
        },
        "denominators": {
            "student_profile_count": report.student_profile_count,
            "measured_user_count": report.measured_user_count,
            "measured_users_outside_profile": report.measured_users_outside_profile,
            "measured_users_non_student": report.measured_users_non_student,
        },
        "attainment": {
            "latest_measurement_count": report.latest_measurement_count,
            "attained_measurement_count": report.attained_measurement_count,
            "attained_user_code_pair_count": report.attained_user_code_pair_count,
            "users_with_any_attainment": report.users_with_any_attainment,
            "per_user_attained_min": report.per_user_attained_min,
            "per_user_attained_max": report.per_user_attained_max,
            "per_user_attained_mean": report.per_user_attained_mean,
            "attained_code_count": report.attained_code_count,
            "code_attainment_rate": report.code_attainment_rate,
            "attained_users_per_code": report.attained_users_per_code,
            "zero_attainment_code_count": len(report.zero_attainment_codes),
            "zero_attainment_codes": list(report.zero_attainment_codes),
        },
        "honest_accounting": {
            "measurements_without_mastery": report.measurements_without_mastery,
            "measurements_concept_unresolved": report.measurements_concept_unresolved,
            "measurements_outside_atom_axis": report.measurements_outside_atom_axis,
            "measurements_with_empty_standard_codes": (
                report.measurements_with_empty_standard_codes
            ),
            "attained_other_revision_codes": report.attained_other_revision_codes,
            "attained_unknown_codes": report.attained_unknown_codes,
        },
    }


def dump_json(report: StandardAttainmentReport) -> str:
    """JSON 직렬화 — 키 정렬·들여쓰기 고정으로 같은 입력에 같은 바이트를 보장(결정론)."""
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 조회·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
async def _run() -> AttainmentInputs:  # pragma: no cover — 라이브 PG 연결 glue
    """세션을 열어 도달 관측 입력을 조회한다(DB 조회 전용·쓰기 0)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await collect_attainment_inputs(session)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 도달 관측 리포트를 stdout에 출력. **0=성공(도달 0이어도) / 2=입력·DB 오류**.

    성취기준 대장 적재 실패·대장에 없는 개정·DB 접속/쿼리 실패는 예외 타입명을 stderr에 포함해
    보고하고 exit 2(CLAUDE.md 침묵 실패 금지 — 무타입 경고 금지 원칙). 도달률이 0%여도 exit 0
    이다 — 게이트가 아니라 관측이기 때문(`problem_bank_coverage`와 동일).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.standard_attainment_report",
        description=(
            "성취기준 도달 관측 리포트(ASM-05·수요측) — 분모 이중 회계·사용자별/코드별 도달"
            " 집계·정직 회계. ARCH-18 공급측 커버리지의 짝. 결정론 아님(DB 실측)·게이트 아님"
            "(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--standards",
        type=Path,
        default=DEFAULT_STANDARDS_PATH,
        help=f"NCIC 성취기준 JSON 경로(기본 {DEFAULT_STANDARDS_PATH}).",
    )
    parser.add_argument(
        "--revision",
        type=str,
        default=DEFAULT_REVISION,
        help=f"도달 분모로 쓸 교육과정 개정(기본 '{DEFAULT_REVISION}').",
    )
    parser.add_argument(
        "--max-listed",
        type=int,
        default=40,
        help="본문에 나열할 0도달 코드 최대 개수(기본 40·전량은 --json).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="JSON 산출물 경로(선택·미지정이면 stdout 마크다운만)",
    )
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.standards.read_text(encoding="utf-8"))
        catalog = load_standards(payload)
    except Exception as exc:  # noqa: BLE001 — 입력 오류는 타입명과 함께 보고하고 exit 2
        print(f"입력 오류 — 성취기준 대장 적재 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    if args.revision not in catalog.revisions:
        print(
            f"입력 오류 — 대장에 없는 개정 '{args.revision}'"
            f"(가능: {', '.join(catalog.revisions) or '없음'})",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    try:
        inputs = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 오류는 타입명과 함께 보고하고 exit 2
        print(f"DB 오류 — 도달 관측 조회 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    report = build_report(inputs, catalog, revision=args.revision)
    print(render_report(report, max_listed=args.max_listed))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
