"""개념↔성취기준 정렬(alignment) 통합 조회 — 3축을 하나의 함수로 (CUR-12).

무엇을 통합하나 (실측 3축 — acceptance ①)
------------------------------------------
  1. `concept_standard_link` — `ConceptStandardLink`(concept_code ↔ norm_id, link_type)
  2. `curriculum_entry`      — `CurriculumEntry.national_standard_codes` 배열(concept_id ↔ 코드)
  3. `atom_node`             — `AtomNode.standard_codes` 배열(원자 code ↔ 코드)

같은 조인이 저장소 곳곳에 복제돼 있었다 — `api/coach.py::_standard_code_for`·
`l2/target_progress.py`·`api/gating.py::_fetch_achievement_codes`가 각자 원자 축 조인을 다시
썼고, `api/alignments.py`(CUR-11)는 핸들러 안에서 3축을 직접 SELECT했다. 이 모듈이 그
**단일 진실 원천**이고, 소비처는 여기를 경유한다(CUR-11 docstring이 "CUR-12가 통합 함수를
세우면 이 핸들러는 그 함수를 경유하도록 갈아끼우는 것이 의도된 진화"라고 미리 지목한 좌석).

어휘는 통일하지 않는다 (조용한 가짜 통일 금지)
----------------------------------------------
축마다 개념 측·성취기준 측 어휘가 다르다. 이 함수는 그 차이를 **없애지 않고 표시**한다
(CUR-11이 세운 정책 계승):

| 축 | 개념 측(`concept_key`) | 성취기준 측(`standard_ref`) | 종류 |
|---|---|---|---|
| concept_standard_link | `concept_code`(구 437 공간) | `norm_id`(`2022_2수_01_01`) | `norm_id` |
| curriculum_entry | `concept_id`(개념 키 문자열) | 고시코드(`[2수01-01]`) | `official_code` |
| atom_node | 원자 `code` | 고시코드 | `official_code` |

`standard_ref_kind`를 함께 실어 소비처가 어휘를 오인 조인하지 않게 한다. 어휘 번역·물리
`curriculum_alignment` 테이블은 **Phase 2**다(acceptance ⑤ 범위 밖).

**결과물에서도 섞이면 안 된다**(#933 리뷰 P2): 여러 축을 함께 조회한 소비처가
`standard_refs()`를 필터 없이 쓰면 `2022_...`(norm_id)와 `[...]`(official_code)가 한 리스트에
섞여 어느 쪽 조회도 성립하지 않는다 — 축을 나눠 표시해 놓고 결과에서 도로 뭉개는 셈이다.
그래서 `standard_refs(kind=...)`로 어휘를 고를 수 있고, 다축 소비처는 반드시 지정한다.

UUID로 물어도 되고 코드로 물어도 된다 (추가 쿼리 0)
---------------------------------------------------
`concept_ids`(DB `Concept.concept_id` UUID)를 주면 각 축이 **자체 조인으로** 개념 키를 푼다 —
별도 해석 쿼리를 먼저 돌리지 않는다. 그래서 축 1개만 요청하면 쿼리도 1회다(소비처의 기존
"쿼리 수 불변·N+1 0" 계약을 깨지 않는다). `concept_ids`는 리스트뿐 아니라 **서브쿼리
(`Select`)** 도 받는다 — `l2/target_progress`가 `ConceptMasteryHistory` 서브쿼리로 대상을
좁히면서도 쿼리 1회를 유지하던 방식을 그대로 살리기 위해서다.

"작동한 비율" 원칙 — 조인 성립 건수 (acceptance ② · CLAUDE.md 절대 금기)
------------------------------------------------------------------------
정상 응답은 조인이 성립했다는 증거가 아니다. `AlignmentResult.stats`가 축별로
**probed(훑은 행)·joined(축 엔티티가 붙은 행)·matched(성취기준이 실린 행)·items(산출 항목)**
를 항상 들고 나온다. 3분류인 이유는 2분류로는 **"조인이 안 됐다"와 "매핑이 없다"가 같은 0**
으로 뭉개지기 때문이다(#933 리뷰 P2 실측):

    조인 미스  probed=1 joined=0 matched=0   ← 배선·적재 이상 의심
    매핑 없음  probed=1 joined=1 matched=0   ← 정상 상태일 수 있다
    정상       probed=1 joined=1 matched=1

`log_join_stats()`가 이것을 로그로 내고, probed>0인데 **joined==0**이면 **warning**으로
승격한다(`l2/target_progress`가 이미 쓰던 "0%가 '미도달'이 아니라 '조인 실패'일 가능성"
경고의 일반화 — 그 경고가 가리키던 사태가 바로 joined다). 소비처는 이 신호를 지우지 않는다.

`alignment_type`은 **로깅 전용**이다 (acceptance ③)
---------------------------------------------------
`AlignmentType`(TEACHES/PRACTICES/ASSESSES/REMEDIATES/EXTENDS/REVIEWS)을 닫힌 어휘로 정의하되,
**판정·필터·분기에 쓰지 않는다**. 그리고 지금은 어느 축도 이 값을 채우지 못한다 — 세 축 중
교수학적 의도를 기록하는 축이 하나도 없기 때문이다(1축의 `link_type` '직접/재매핑/준용'은
*매핑 출처*이지 교수학적 역할이 아니다). 그래서 현재 전 항목이 `alignment_type=None`이고,
로그가 그 사실을 `type_counts={'(미상)': N}`으로 **드러낸다**. 축이 의도를 싣기 시작하면
(Phase 2 물리 테이블) 그때 채워진다 — 지금 임의로 TEACHES를 찍는 것은 날조다.

7계층: L1(데이터 기반)의 조회 함수. 상위(L2 진도·L5 api)가 호출하고, 이 모듈은 상위를 모른다.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.curriculum_entry import CurriculumEntry

__all__ = [
    "ALL_AXES",
    "AXIS_ORDER",
    "Alignment",
    "AlignmentAxis",
    "AlignmentJoinStats",
    "AlignmentResult",
    "AlignmentType",
    "StandardRefKind",
    "get_alignments",
    "log_join_stats",
]

_logger = logging.getLogger(__name__)


class AlignmentAxis(str, Enum):
    """정렬 재료가 나온 축 — 실측 3축 폐쇄 집합(모듈 docstring 표와 1:1)."""

    CONCEPT_STANDARD_LINK = "concept_standard_link"
    CURRICULUM_ENTRY = "curriculum_entry"
    ATOM_NODE = "atom_node"


ALL_AXES: frozenset[AlignmentAxis] = frozenset(AlignmentAxis)
"""기본 조회 축 — 3축 전부. 소비처가 필요한 축만 좁히면 쿼리도 그만큼만 돈다."""

AXIS_ORDER: tuple[AlignmentAxis, ...] = (
    AlignmentAxis.CONCEPT_STANDARD_LINK,
    AlignmentAxis.CURRICULUM_ENTRY,
    AlignmentAxis.ATOM_NODE,
)
"""합성 순서 — **선언 순서(1→2→3)** 이지 값의 사전순이 아니다.

`api/alignments.py`의 페이지네이션이 "축-우선 prefix 보존"에 기대므로 이 순서는 계약이다.
알파벳 정렬로 두면 atom_node가 앞으로 와 그 계약이 조용히 깨진다(실측으로 잡은 함정 —
`test_alignment_query.py`가 순서를 동결한다)."""

StandardRefKind = Literal["norm_id", "official_code"]
"""성취기준 참조 어휘 — 축마다 다르다(가짜 통일 금지·모듈 docstring 표)."""


class AlignmentType(str, Enum):
    """정렬의 교수학적 역할 — **로깅 전용 어휘**(acceptance ③).

    판정·필터·분기에 쓰지 않는다. 현재 세 축 중 이 값을 기록하는 축이 없어 전 항목이 None이며,
    그 사실 자체를 로그가 드러낸다(모듈 docstring "`alignment_type`은 로깅 전용이다"). 값을
    채우는 것은 Phase 2 물리 `curriculum_alignment` 테이블의 몫이다.
    """

    TEACHES = "TEACHES"
    """이 개념이 성취기준을 가르친다(주 도달 경로)."""

    PRACTICES = "PRACTICES"
    """숙달 연습으로 성취기준을 다룬다."""

    ASSESSES = "ASSESSES"
    """성취기준 도달을 평가한다."""

    REMEDIATES = "REMEDIATES"
    """미도달 보충으로 성취기준을 다룬다."""

    EXTENDS = "EXTENDS"
    """성취기준을 넘어 확장한다(심화)."""

    REVIEWS = "REVIEWS"
    """이전에 다룬 성취기준을 복습한다."""


@dataclass(frozen=True, slots=True)
class Alignment:
    """정렬 1건 — (개념 키, 성취기준 참조) 쌍 + 출처 축 표시."""

    axis: AlignmentAxis
    concept_key: str
    """개념 측 식별자 — 축별 어휘 그대로(모듈 docstring 표)."""

    standard_ref: str
    """성취기준 측 참조 — 축별 어휘 그대로."""

    standard_ref_kind: StandardRefKind
    """`standard_ref`의 어휘 종류 — 소비처의 오인 조인 차단용."""

    concept_id: uuid.UUID | None = None
    """DB `Concept.concept_id` — UUID로 물었을 때만 채워진다(코드로 물으면 None)."""

    link_type: str | None = None
    """연결 의미('직접'/'재매핑'/'준용') — concept_standard_link 축만."""

    framework_id: str | None = None
    """소속 프레임워크 — curriculum_entry 축만(미분류·타 축은 None)."""

    alignment_type: AlignmentType | None = None
    """교수학적 역할 — **로깅 전용**. 현재 전 축이 미기록이라 항상 None(모듈 docstring)."""


@dataclass(frozen=True, slots=True)
class AlignmentJoinStats:
    """조인 성립 회계 — "작동한 비율" 원칙의 자료(침묵 실패 금지·acceptance ②).

    **3분류**여야 한다(#933 리뷰 P2 실측 — 2분류로는 두 사태가 같은 숫자로 뭉갠다):

    | | probed | joined | matched | 뜻 |
    |---|---|---|---|---|
    | 조인 미스 | 1 | 0 | 0 | 개념은 조회했으나 그 축에 행이 **없다**(배선/적재 문제 의심) |
    | 매핑 없음 | 1 | 1 | 0 | 축 행은 있는데 성취기준이 **비어 있다**(정상 상태일 수 있다) |
    | 정상 | 1 | 1 | 1 | 성취기준이 실렸다 |

    `probed`(훑은 행) · `joined`(그 축 엔티티가 실제로 붙은 행) · `matched`(성취기준이 실려
    항목을 낳은 행). joined를 빼면 "조인이 안 됐다"와 "매핑이 없다"가 같은 0으로 보이고, 그러면
    0%의 원인을 영원히 알 수 없다 — 이 모듈의 존재 이유 중 하나가 그 구분이다.
    """

    axes: tuple[AlignmentAxis, ...]
    """요청된 축(필터로 걸러진 뒤의 최종 요청 목록)."""

    queried_axes: tuple[AlignmentAxis, ...]
    """실제로 SQL을 돌린 축. `axes`와 다르면 조기 종료(limit 충족)로 뒤 축을 건너뛴 것이다 —
    건너뛴 축의 0은 "조회했는데 없음"이 아니라 **"조회 안 함"** 이다(미측정 ≠ 0)."""

    probed_by_axis: Mapping[str, int]
    joined_by_axis: Mapping[str, int]
    """그 축 엔티티가 실제로 붙은 행 수 — probed와 다르면 조인 미스가 있다는 뜻."""

    matched_by_axis: Mapping[str, int]
    items_by_axis: Mapping[str, int]
    type_counts: Mapping[str, int]
    """`alignment_type` 분포 — 미상은 '(미상)' 키로 센다(로깅 전용 축의 가시화)."""

    @property
    def probed(self) -> int:
        return sum(self.probed_by_axis.values())

    @property
    def joined(self) -> int:
        return sum(self.joined_by_axis.values())

    @property
    def matched(self) -> int:
        return sum(self.matched_by_axis.values())

    @property
    def items(self) -> int:
        return sum(self.items_by_axis.values())

    @property
    def join_blackout(self) -> bool:
        """조회는 했는데 **조인이 전건 실패** — "미도달"이 아니라 "조인 실패"를 의심할 상태.

        기준은 `matched`가 아니라 `joined`다(#933 리뷰 P2): 축 행은 다 붙었는데 성취기준 매핑만
        비어 있는 것은 정상 상태일 수 있어 경고 대상이 아니고, 축 행 자체가 하나도 안 붙는 것이
        배선·적재 이상이다. `l2/target_progress`의 원래 경고(`standard_codes is not None`을
        matched로 세던)가 가리키던 사태가 바로 이 joined다.

        조회 자체를 안 한 경우(probed==0)는 blackout이 아니다 — 그건 "안 봄"이지 "안 맞음"이
        아니다(미측정 ≠ 0). 그래서 경고가 남발되지 않는다.
        """
        return self.probed > 0 and self.joined == 0


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """통합 조회 결과 — 항목 + 조인 회계. 회계 없이 항목만 돌려주지 않는다(설계 의도)."""

    alignments: tuple[Alignment, ...]
    stats: AlignmentJoinStats

    def standard_refs(self, *, kind: StandardRefKind | None = None) -> tuple[str, ...]:
        """성취기준 참조 중복 제거 + 정렬 — 결정론(소비처가 '첫 코드'를 골라도 안정).

        `kind`를 주면 그 어휘의 참조만 남긴다. **어휘를 섞어 담는 소비처는 반드시 지정해야
        한다**(#933 리뷰 P2): 축마다 어휘가 달라(1축=norm_id, 2·3축=official_code) 필터 없이
        평탄화하면 `2022_...`와 `[...]`가 한 리스트에 섞이고, 그 리스트로는 어느 쪽 조회도
        성립하지 않는다 — 이 모듈이 금지하는 "조용한 가짜 통일"이 결과물에서 일어난다.
        단일 축만 조회하는 소비처는 어휘가 하나뿐이라 생략해도 안전하지만, 축 집합이 나중에
        늘어날 수 있으므로 **명시를 권장**한다.
        """
        refs = {
            a.standard_ref for a in self.alignments if kind is None or a.standard_ref_kind == kind
        }
        return tuple(sorted(refs))

    def refs_by_concept_id(self) -> dict[uuid.UUID, tuple[str, ...]]:
        """concept_id → 성취기준 참조(정렬). UUID로 묻지 않은 항목은 빠진다."""
        grouped: dict[uuid.UUID, set[str]] = {}
        for item in self.alignments:
            if item.concept_id is None:
                continue
            grouped.setdefault(item.concept_id, set()).add(item.standard_ref)
        return {cid: tuple(sorted(refs)) for cid, refs in grouped.items()}

    def refs_by_concept_key(self) -> dict[str, tuple[str, ...]]:
        """개념 키(축별 어휘) → 성취기준 참조(정렬)."""
        grouped: dict[str, set[str]] = {}
        for item in self.alignments:
            grouped.setdefault(item.concept_key, set()).add(item.standard_ref)
        return {key: tuple(sorted(refs)) for key, refs in grouped.items()}


# 개념 지정 방식 — 리스트 또는 서브쿼리(Select). 서브쿼리 수용은 소비처의 "쿼리 수 불변"
# 계약을 지키기 위해서다(모듈 docstring "UUID로 물어도 되고 코드로 물어도 된다").
ConceptIdSpec = Sequence[uuid.UUID] | Select[Any]
ConceptCodeSpec = Sequence[str] | Select[Any]


def _is_empty_spec(spec: ConceptIdSpec | ConceptCodeSpec | None) -> bool:
    """빈 시퀀스는 "대상 없음" — 쿼리를 돌리지 않는다. Select는 비었는지 알 수 없으므로 돈다."""
    return spec is not None and isinstance(spec, Sequence) and len(spec) == 0


async def get_alignments(
    session: AsyncSession,
    *,
    concept_ids: ConceptIdSpec | None = None,
    concept_codes: ConceptCodeSpec | None = None,
    framework_id: str | None = None,
    outcome_id: str | None = None,
    axes: Collection[AlignmentAxis] = ALL_AXES,
    limit: int | None = None,
    require_nonempty: bool = False,
) -> AlignmentResult:
    """개념↔성취기준 정렬 통합 조회 (acceptance ① — 3축 단일 함수).

    Args:
      session: 요청 수명 AsyncSession.
      concept_ids: DB `Concept.concept_id` UUID 목록 **또는 서브쿼리**. 각 축이 자체 조인으로
        개념 키를 풀므로 별도 해석 쿼리가 없다(축 1개 요청 = 쿼리 1회).
      concept_codes: 개념 *키* 목록(축별 어휘 그대로 대조 — 1축=concept_code, 2축=concept_id
        문자열, 3축=원자 code). `concept_ids`와 함께 주면 둘 다 AND로 걸린다.
      framework_id: 프레임워크 필터. **curriculum_entry 축만** 이 컬럼을 가지므로, 지정하면
        나머지 축은 조회 대상에서 빠진다(없는 축에 필터를 조용히 무시하지 않는다).
      outcome_id: 성취기준 참조 필터 — 축별 어휘 그대로 대조한다(norm_id 어휘로 2·3축이
        잡히지 않는 것은 정직한 결과다·번역은 Phase 2).
      axes: 조회할 축(기본 3축 전부). 좁히면 쿼리도 그만큼만 돈다.
      limit: 인출 상한. 각 축 SQL에 그대로 걸리고, 앞 축만으로 이미 `limit`개가 차면 뒤 축은
        **조회하지 않는다**(합성 순서가 축-우선이라 뒤 축은 그 페이지에 기여할 수 없다).
        건너뛴 축은 `stats.queried_axes`에서 빠진다 — 그 0은 "없음"이 아니라 "안 봄"이다.
      require_nonempty: True면 배열 축(2·3축)에서 `cardinality(...) > 0` 행만 SELECT한다 —
        "행 1건 ≥ 항목 1건"이 보장돼야 축별 상한 인출이 합성 순서의 prefix를 보존한다
        (`api/alignments.py` 페이지네이션의 요구). 기본 False인 이유는 정반대 소비처 때문이다:
        `l2/target_progress`는 **빈 배열 행도 probed로 세어야** "매핑 없음"과 "조인 실패"를
        구분할 수 있다. 두 요구가 상충하므로 플래그로 갈라 두고 소비처가 명시하게 한다.

    Returns:
      `AlignmentResult` — 항목 + 축별 조인 회계(`stats`).
    """
    selected = set(axes)
    requested = tuple(a for a in AXIS_ORDER if a in selected)
    if framework_id is not None:
        # framework_id를 가진 축은 curriculum_entry 하나뿐 — 나머지 축에 이 필터를 "적용한 척"
        # 하면 필터가 무시된 결과가 통과한다(조용한 무시 금지).
        requested = tuple(a for a in requested if a is AlignmentAxis.CURRICULUM_ENTRY)

    empty_target = _is_empty_spec(concept_ids) or _is_empty_spec(concept_codes)

    alignments: list[Alignment] = []
    probed: dict[str, int] = {}
    joined: dict[str, int] = {}
    matched: dict[str, int] = {}
    items: dict[str, int] = {}

    queried: list[AlignmentAxis] = []
    for axis in requested:
        probed[axis.value] = 0
        joined[axis.value] = 0
        matched[axis.value] = 0
        items[axis.value] = 0
        if empty_target:
            continue  # 대상 0건 — 쿼리 생략(빈 IN은 SQL 낭비)
        if limit is not None and len(alignments) >= limit:
            # 조기 종료 — 합성 순서가 축-우선이라 앞 축만으로 limit이 차면 뒤 축은 그 페이지에
            # 기여할 수 없다. 건너뛴 축은 `queried_axes`에서 빠져 "조회 안 함"으로 남는다.
            continue
        queried.append(axis)
        if axis is AlignmentAxis.CONCEPT_STANDARD_LINK:
            found = await _query_link_axis(
                session,
                concept_ids=concept_ids,
                concept_codes=concept_codes,
                outcome_id=outcome_id,
                limit=limit,
            )
        elif axis is AlignmentAxis.CURRICULUM_ENTRY:
            found = await _query_entry_axis(
                session,
                concept_ids=concept_ids,
                concept_codes=concept_codes,
                framework_id=framework_id,
                outcome_id=outcome_id,
                limit=limit,
                require_nonempty=require_nonempty,
            )
        else:
            found = await _query_atom_axis(
                session,
                concept_ids=concept_ids,
                concept_codes=concept_codes,
                outcome_id=outcome_id,
                limit=limit,
                require_nonempty=require_nonempty,
            )
        probed[axis.value] = found.probed
        joined[axis.value] = found.joined
        matched[axis.value] = found.matched
        items[axis.value] = len(found.alignments)
        alignments.extend(found.alignments)

    type_counts: dict[str, int] = {}
    for item in alignments:
        key = item.alignment_type.value if item.alignment_type is not None else "(미상)"
        type_counts[key] = type_counts.get(key, 0) + 1

    return AlignmentResult(
        alignments=tuple(alignments),
        stats=AlignmentJoinStats(
            axes=requested,
            queried_axes=tuple(queried),
            probed_by_axis=probed,
            joined_by_axis=joined,
            matched_by_axis=matched,
            items_by_axis=items,
            type_counts=type_counts,
        ),
    )


@dataclass(frozen=True, slots=True)
class _AxisRows:
    """축 1개의 조회 산출 — 항목 + 그 축의 probed/joined/matched 회계."""

    alignments: tuple[Alignment, ...]
    probed: int
    joined: int
    matched: int


def _apply_concept_filters(
    stmt: Select[Any],
    *,
    concept_ids: ConceptIdSpec | None,
    concept_codes: ConceptCodeSpec | None,
    code_column: InstrumentedAttribute[str],
) -> Select[Any]:
    """개념 필터 공통 적용 — UUID는 Concept 조인(호출부가 이미 걸었다), 코드는 축 컬럼 대조."""
    if concept_ids is not None:
        stmt = stmt.where(Concept.concept_id.in_(concept_ids))
    if concept_codes is not None:
        stmt = stmt.where(code_column.in_(concept_codes))
    return stmt


async def _query_link_axis(
    session: AsyncSession,
    *,
    concept_ids: ConceptIdSpec | None,
    concept_codes: ConceptCodeSpec | None,
    outcome_id: str | None,
    limit: int | None,
) -> _AxisRows:
    """1축 — ConceptStandardLink(행 1건 = 항목 1건이라 probed == matched)."""
    stmt: Select[Any] = select(ConceptStandardLink, Concept.concept_id)
    # UUID로 물었으면 Concept를 INNER 조인해 code 공간으로 내려간다(별도 해석 쿼리 0).
    # 코드로만 물었으면 조인 자체가 불필요하므로 OUTER로 붙여 링크 행을 잃지 않는다.
    join_kind_inner = concept_ids is not None
    stmt = stmt.join(
        Concept,
        Concept.code == ConceptStandardLink.concept_code,
        isouter=not join_kind_inner,
    )
    stmt = _apply_concept_filters(
        stmt,
        concept_ids=concept_ids,
        concept_codes=concept_codes,
        code_column=ConceptStandardLink.concept_code,
    )
    if outcome_id is not None:
        stmt = stmt.where(ConceptStandardLink.norm_id == outcome_id)
    stmt = stmt.order_by(
        ConceptStandardLink.concept_code,
        ConceptStandardLink.norm_id,
        ConceptStandardLink.link_type,
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    found = tuple(
        Alignment(
            axis=AlignmentAxis.CONCEPT_STANDARD_LINK,
            concept_key=link.concept_code,
            standard_ref=link.norm_id,
            standard_ref_kind="norm_id",
            concept_id=concept_id,
            link_type=link.link_type,
        )
        for link, concept_id in rows
    )
    # 링크 행은 정의상 성취기준(norm_id)을 실고 있다 — 이 축엔 "붙었는데 빈 매핑"이 없다.
    return _AxisRows(alignments=found, probed=len(rows), joined=len(rows), matched=len(rows))


async def _query_entry_axis(
    session: AsyncSession,
    *,
    concept_ids: ConceptIdSpec | None,
    concept_codes: ConceptCodeSpec | None,
    framework_id: str | None,
    outcome_id: str | None,
    limit: int | None,
    require_nonempty: bool = False,
) -> _AxisRows:
    """2축 — CurriculumEntry.national_standard_codes(배열 평탄화·빈 배열은 matched 아님)."""
    stmt: Select[Any] = select(CurriculumEntry, Concept.concept_id)
    stmt = stmt.join(
        Concept,
        Concept.code == CurriculumEntry.concept_id,
        isouter=concept_ids is None,
    )
    stmt = _apply_concept_filters(
        stmt,
        concept_ids=concept_ids,
        concept_codes=concept_codes,
        code_column=CurriculumEntry.concept_id,
    )
    if require_nonempty:
        stmt = stmt.where(sa.func.cardinality(CurriculumEntry.national_standard_codes) > 0)
    if framework_id is not None:
        stmt = stmt.where(CurriculumEntry.framework_id == framework_id)
    if outcome_id is not None:
        # `x = ANY(배열)` — ARRAY comparator `.any()`는 관계용 PropComparator.any와 스텁이
        # 충돌해 mypy --strict가 거부한다(api/alignments.py 선례). typed 표면 sa.any_를 쓴다.
        stmt = stmt.where(
            sa.literal(outcome_id) == sa.any_(CurriculumEntry.national_standard_codes)
        )
    stmt = stmt.order_by(CurriculumEntry.entry_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    found: list[Alignment] = []
    matched = 0
    for entry, concept_id in rows:
        codes = [
            code
            for code in (entry.national_standard_codes or [])
            # 행 매칭 ≠ 항목 매칭 — 배열엔 다른 코드도 함께 있다(api/alignments.py 선례).
            if outcome_id is None or code == outcome_id
        ]
        if codes:
            matched += 1
        found.extend(
            Alignment(
                axis=AlignmentAxis.CURRICULUM_ENTRY,
                concept_key=entry.concept_id,
                standard_ref=code,
                standard_ref_kind="official_code",
                concept_id=concept_id,
                framework_id=entry.framework_id,
            )
            for code in codes
        )
    # CurriculumEntry가 기준 테이블이라 나온 행은 전부 "붙은" 행이다(probed == joined).
    return _AxisRows(alignments=tuple(found), probed=len(rows), joined=len(rows), matched=matched)


async def _query_atom_axis(
    session: AsyncSession,
    *,
    concept_ids: ConceptIdSpec | None,
    concept_codes: ConceptCodeSpec | None,
    outcome_id: str | None,
    limit: int | None,
    require_nonempty: bool = False,
) -> _AxisRows:
    """3축 — AtomNode.standard_codes(배열 평탄화).

    `concept_ids`로 물으면 **Concept 기준 LEFT OUTER JOIN**이다 — 원자 축에 매핑되지 않는
    개념도 행으로 살아남아야 probed(조회 대상)와 matched(원자 축 히트)를 구분할 수 있다
    (`l2/target_progress`가 measured/matched를 세던 방식 그대로). 코드로만 물으면 AtomNode가
    기준 테이블이므로 그 축의 행만 나온다.
    """
    if concept_ids is not None:
        stmt: Select[Any] = (
            select(AtomNode.code, AtomNode.standard_codes, Concept.concept_id)
            .select_from(Concept)
            .outerjoin(AtomNode, AtomNode.code == Concept.code)
            .where(Concept.concept_id.in_(concept_ids))
        )
        if concept_codes is not None:
            stmt = stmt.where(Concept.code.in_(concept_codes))
        order_column: InstrumentedAttribute[str] = Concept.code
    else:
        stmt = select(AtomNode.code, AtomNode.standard_codes, sa.literal(None).label("concept_id"))
        if concept_codes is not None:
            stmt = stmt.where(AtomNode.code.in_(concept_codes))
        order_column = AtomNode.code
    if require_nonempty:
        stmt = stmt.where(sa.func.cardinality(AtomNode.standard_codes) > 0)
    if outcome_id is not None:
        stmt = stmt.where(sa.literal(outcome_id) == sa.any_(AtomNode.standard_codes))
    stmt = stmt.order_by(order_column)
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    found: list[Alignment] = []
    joined = 0
    matched = 0
    for atom_code, standard_codes, concept_id in rows:
        if atom_code is None:
            # OUTER JOIN 미스 — 조회는 했으나(probed) 원자 행이 없다(joined 아님).
            # 이 분리가 "조인 실패"와 "매핑 없음"을 가른다(#933 리뷰 P2).
            continue
        joined += 1
        codes = [
            code for code in (standard_codes or []) if outcome_id is None or code == outcome_id
        ]
        if codes:
            matched += 1
        found.extend(
            Alignment(
                axis=AlignmentAxis.ATOM_NODE,
                concept_key=atom_code,
                standard_ref=code,
                standard_ref_kind="official_code",
                concept_id=concept_id,
            )
            for code in codes
        )
    return _AxisRows(alignments=tuple(found), probed=len(rows), joined=joined, matched=matched)


def log_join_stats(
    stats: AlignmentJoinStats,
    *,
    logger: logging.Logger | None = None,
    context: str,
) -> None:
    """조인 성립 회계를 로그로 — 침묵 실패 금지(acceptance ② · CLAUDE.md 절대 금기).

    항상 debug 1줄을 내고, **probed>0 · matched==0**(전건 미매칭)이면 **warning**으로 승격한다.
    "성취기준 매핑이 없다"와 "조인이 안 됐다"는 둘 다 0%로 보이지만 원인이 다르다 — 이 경고가
    그 구분을 사람에게 넘긴다(`l2/target_progress`가 쓰던 경고의 일반화).
    """
    target = logger if logger is not None else _logger
    target.debug(
        "alignment 조인 회계 [%s]: axes=%s queried=%s probed=%d joined=%d matched=%d "
        "items=%d probed_by_axis=%s joined_by_axis=%s matched_by_axis=%s items_by_axis=%s "
        "type_counts=%s",
        context,
        [a.value for a in stats.axes],
        [a.value for a in stats.queried_axes],
        stats.probed,
        stats.joined,
        stats.matched,
        stats.items,
        dict(stats.probed_by_axis),
        dict(stats.joined_by_axis),
        dict(stats.matched_by_axis),
        dict(stats.items_by_axis),
        dict(stats.type_counts),
    )
    if stats.join_blackout:
        target.warning(
            "alignment 조인 0건 [%s]: 조회 %d행 전부 조인 실패(축 행 0건) — 결과 0건이 "
            "'매핑 없음'이 아니라 '조인 실패'다. 배선·적재를 점검하라(axes=%s)",
            context,
            stats.probed,
            [a.value for a in stats.axes],
        )
