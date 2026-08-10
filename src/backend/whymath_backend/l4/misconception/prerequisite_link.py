"""L4 오개념→선수코칭 브릿지 — 활성 오개념(kebab-id)을 `PrerequisiteGap`으로 변환하는 얇은 어댑터.

정본: `docs/architecture/04e_misconception_remediation_design.md` §1-2 "선수학습 복습 ↔ 오개념
연동". 기존 `recommend_prerequisite_coaching(gaps: Sequence[PrerequisiteGap])`
(`l4/prerequisite_coaching.py`)의 시그니처는 **불변**(회귀 0) — 이 모듈은 그 입력을 만드는 신규
*신호원*(오개념)을 추가할 뿐, 결정 로직 자체는 건드리지 않는다.

────────────────────────────────────────────────────────────────────────────
두 오개념 ID 공간(절대 혼동 금지) — 이 체인이 하나를 다른 하나로 잇는 다리다
────────────────────────────────────────────────────────────────────────────
- **kebab-id**(`LearnerState.active_misconceptions` 원소·`l4/misconception/catalog.py::
  CATALOG_BY_ID` 공간·예 `"distribution-over-power"`) — 런타임 탐지·가설 저장 키.
- **M-id**(`MisconceptionCatalog.mis_id` 공간·예 `"M0425"`) — 콘텐츠 카탈로그 키(본문·
  `concept_src_id` 느슨참조 보유).
둘은 FK로 이어져 있지 않고, 다리는 사람 검수 테이블 `misconception_crosslink`뿐이다.

변환 체인:
  kebab-id → `MisconceptionCrosslinkResolver`(sync·crosswalk 조회) → canonical M-id(선정되면)
    → M-id로 `MisconceptionCatalog` 행 조회(async) → `concept_src_id`
    → `l1.misconception.resolve.resolve_many`(기존 좌석 재사용 — 신규 매칭 로직 0) → `ConceptRef`
    → 최소 `PrerequisiteGap`(`agreement="insufficient"` — BKT/IRT 교차검증이 없음을 정직히 표시)

────────────────────────────────────────────────────────────────────────────
`crosslink_shadow.py`를 재사용하지 않는 이유
────────────────────────────────────────────────────────────────────────────
`observe_crosslink_shadow`/`_async`는 **의도적으로 `None`만 반환**한다(student-facing 누출을
구조적으로 차단 — 그 모듈 자체 docstring). 이 모듈은 반대로 실제 `PrerequisiteGap`을 만들어
코칭 행동에 반영해야 하므로 그 함수들을 쓸 수 없다 — 대신 `MisconceptionCrosslinkResolver`를
*직접* 호출하되, sync 엔진을 async 컨텍스트에서 블로킹 없이 쓰기 위해 `observe_crosslink_shadow_
async`가 쓰는 것과 동일한 `asyncio.to_thread` 오프로드 패턴을 그대로 답습한다.

────────────────────────────────────────────────────────────────────────────
게이트(`misconception_crosslink_mode`) — 기존 4개 소비처와 동일 플래그를 재사용한다
────────────────────────────────────────────────────────────────────────────
`config.py`의 `misconception_crosslink_mode`(기본 `"off"`)를 그대로 재사용한다: `wh1_loop.py`·
`learning_scene.py`·`evidence_store.py`·`hypothesis_store.py`가 전부 `if get_settings().
misconception_crosslink_mode != "off":` 패턴으로 게이팅하므로 이 모듈도 동일 패턴을 따른다.
**"off"(기본값)면 이 함수는 즉시 빈 리스트를 반환하고 crosslink·catalog·concept 조회를 전혀
하지 않는다** — 오늘 프로덕션 행동이 전혀 바뀌지 않는 핵심 메커니즘(회귀 0).

**의미론적 확장에 대한 정직한 기록**: 기존 4개 소비처는 이 모드에서 *관측만* 하고 그 값으로
어떤 호출자도 행동을 바꾸지 않는다(`crosslink_shadow.py`의 설계 의도 — "None만 반환"). 이
모듈은 다르다 — mode가 `"shadow"`가 되는 순간부터 *실제로* `PrerequisiteGap`을 만들어 코칭
트리거에 반영한다(04e §1-2가 애초에 요구한 것 자체가 "관측"이 아니라 "연동"이다). 즉 이 플래그를
`off`→`shadow`로 바꾸는 운영 판단은 이제 "오개념 crosswalk shadow 로깅을 켠다"뿐 아니라 "선수
코칭에 오개념 신호가 실제로 섞이기 시작한다"도 함께 의미한다 — 이 확장은 MEMORY.md 결정 로그에
남겨야 한다(이 슬라이스 자체는 그 기록을 대신하지 않는다 — 구현 세션은 MEMORY.md를 건드리지
않기로 합의됨).

────────────────────────────────────────────────────────────────────────────
reactive retrieval (CLAUDE.md — 오개념을 초기 context에 preload 금지)
────────────────────────────────────────────────────────────────────────────
이 함수는 이미 조립된 `active_misconceptions`(호출자가 `LearnerState`/`get_active_hypotheses`
등 기존 좌석으로 로드한 신호)를 입력으로만 받는다 — 그 이상 오개념을 추가로 긁어오지 않는다.

────────────────────────────────────────────────────────────────────────────
정직한 스킵 (잘못된 concept으로 코칭하는 것보다 안전)
────────────────────────────────────────────────────────────────────────────
canonical 미선정(ambiguous·no_direct·no_links)·`MisconceptionCatalog` 행 부재·`concept_src_id`
없음·`concept_orphan` — 각각 그 kebab-id 1건만 조용히 건너뛴다(크래시 없음·잘못된 gap 생성
없음). 이건 *예외*가 아니라 *흔한 정상 경로*(crosswalk 테이블이 아직 부분 검수 상태)라 매 건
로깅하지 않는다. 반면 예기치 못한 예외(DB 연결 실패 등)는 **never-break**로 감싸 전체를 빈
리스트로 강등하고 예외 타입명만 로그한다(CLAUDE.md 침묵 실패 금지) — 이 신호는 *부가 기능*이라
실패해도 기존에 잘 동작하던 코칭 엔드포인트 전체를 깨면 안 된다(우선순위: 학생 경험 > 신규 신호).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog
from whymath_backend.l1.misconception.crosslink_resolve import (
    MisconceptionCrosslinkResolver,
    select_canonical,
)
from whymath_backend.l1.misconception.resolve import resolve_many
from whymath_backend.l2.prerequisite_recommendation import PrerequisiteGap

__all__ = ["gaps_from_active_misconceptions"]

_logger = logging.getLogger("whymath.l4.misconception.prerequisite_link")


async def gaps_from_active_misconceptions(
    session: AsyncSession,
    active_misconceptions: Sequence[str],
    *,
    resolver: MisconceptionCrosslinkResolver | None = None,
) -> list[PrerequisiteGap]:
    """활성 오개념(kebab-id) 목록 → 최소 `PrerequisiteGap` 목록(선수 코칭 신호원 확장).

    입력 `active_misconceptions`는 **confidence 내림차순**이라고 가정한다(`LearnerState.
    active_misconceptions`·`hypothesis_store.get_active_hypotheses`의 공통 계약) — 출력 순서도
    그 순서를 보존하므로, `recommend_prerequisite_coaching`이 `gaps[0]`을 top blocker로 다룰 때
    "가장 확신도 높은 활성 오개념의 연결 개념"이 된다.

    `misconception_crosslink_mode == "off"`(기본)면 즉시 빈 리스트 — crosslink·catalog·concept
    조회가 *전혀* 없다(회귀 0). 빈 입력도 빈 리스트(조회 스킵 — 조기 반환).

    흐름(모드가 off가 아닐 때만 실행):
      ① kebab-id 전량을 **한 번에** crosswalk 조회(`resolve_links_many`·N+1 회피) — sync 엔진이라
         `asyncio.to_thread`로 오프로드(이벤트 루프 논블로킹·`crosslink_shadow.py`와 동일 패턴).
      ② 각 kebab-id의 링크에 `select_canonical`(순수 함수·DB 0) 적용 — 미선정(ambiguous/
         no_direct/no_links)은 그 kebab-id를 정직하게 제외.
      ③ 선정된 M-id 집합을 `MisconceptionCatalog`에서 **일괄** IN 조회(N+1 회피).
      ④ `concept_src_id`가 있는 행만 `l1.misconception.resolve.resolve_many`(기존 좌석 재사용 —
         신규 매칭 로직 0)로 개념 해소. `concept_orphan`(참조는 있으나 못 찾음)은 제외.
      ⑤ 해소된 개념의 안전 표시명(`Concept.name_ko`)을 일괄 enrich(선택적 — 코칭 문구 품질
         향상용. 못 찾아도 `concept_name=None`으로 graceful — `prerequisite_coaching.py`가 이미
         "선수개념" 일반어로 폴백한다).

    같은 개념으로 귀결되는 서로 다른 오개념은 dedup한다(confidence 내림차순 입력이라 첫 등장이
    최고 confidence 유지 — 중복 gap 방지). `weakness`/`bkt_mastery`/`irt_mastery_proxy`는 채우지
    않는다(이 신호원엔 BKT/IRT 측정이 없다) — `agreement="insufficient"`로 정직 표시한다(허위
    측정치 날조 금지).

    never-break: 예기치 못한 예외(DB 연결 실패 등)는 빈 리스트로 강등하고 예외 타입명만 로그한다
    (이 신호는 부가 기능 — 실패해도 기존 코칭 엔드포인트 자체는 무영향이어야 함).
    """
    if get_settings().misconception_crosslink_mode == "off":
        return []  # 회귀 0 핵심 메커니즘 — 조회 0(crosslink·catalog·concept 어디도 안 건드림).
    if not active_misconceptions:
        return []  # 활성 오개념 없음 — 조회할 대상 자체가 없음(조기 반환).

    try:
        return await _resolve_gaps(session, active_misconceptions, resolver=resolver)
    except Exception as exc:  # noqa: BLE001 — never-break(부가 신호·본류 코칭을 깨면 안 됨).
        _logger.warning(
            "오개념→선수코칭 브릿지 실패(%s) — 이 신호 없이 진행(코칭 엔드포인트 자체는 무영향)",
            type(exc).__name__,
        )
        return []


async def _resolve_gaps(
    session: AsyncSession,
    active_misconceptions: Sequence[str],
    *,
    resolver: MisconceptionCrosslinkResolver | None,
) -> list[PrerequisiteGap]:
    """`gaps_from_active_misconceptions`의 본체 — never-break 래퍼 밖으로 분리(가독성 목적)."""
    resolver = resolver or MisconceptionCrosslinkResolver()

    # ① crosswalk 일괄 조회(sync·blocking → to_thread 오프로드). N+1 회피(resolver 자체 배치 API).
    links_by_kebab = await asyncio.to_thread(resolver.resolve_links_many, active_misconceptions)

    # ② canonical 선정(순수 함수·DB 0) — kebab-id 원본 순서(confidence desc) 그대로 순회.
    canonical_mis_id_by_kebab: dict[str, str] = {}
    for kebab_id in active_misconceptions:
        selection = select_canonical(links_by_kebab.get(kebab_id, []))
        if selection.canonical_mis_id is not None:
            canonical_mis_id_by_kebab[kebab_id] = selection.canonical_mis_id
    if not canonical_mis_id_by_kebab:
        return []  # 전부 미선정(크로스워크 테이블이 아직 비었거나 부분 검수) — 정직한 빈 결과.

    # ③ M-id → MisconceptionCatalog 일괄 조회(IN쿼리·N+1 회피).
    mis_ids = set(canonical_mis_id_by_kebab.values())
    catalog_result = await session.execute(
        select(MisconceptionCatalog).where(MisconceptionCatalog.mis_id.in_(mis_ids))
    )
    catalog_by_mis_id: dict[str, MisconceptionCatalog] = {
        row.mis_id: row for row in catalog_result.scalars().all()
    }

    # ④ concept_src_id 있는 행만 해소 대상("참조 없음"은 orphan이 아니라 애초에 스킵 — resolve.py
    # 정직 회계 규약과 동형). 기존 좌석(resolve_many) 그대로 재사용 — 신규 매칭 로직 0.
    rows_with_concept_ref = [
        row for row in catalog_by_mis_id.values() if row.concept_src_id is not None
    ]
    resolved_by_mis_id = {r.mis_id: r for r in await resolve_many(session, rows_with_concept_ref)}

    # ⑤ 해소된 개념의 안전 표시명(name_ko) 일괄 enrich(선택적 — 실패해도 graceful None 유지).
    concept_ids = {
        r.concept.concept_id for r in resolved_by_mis_id.values() if r.concept is not None
    }
    name_ko_by_concept: dict[uuid.UUID, str | None] = {}
    if concept_ids:
        name_result = await session.execute(
            select(Concept.concept_id, Concept.name_ko).where(Concept.concept_id.in_(concept_ids))
        )
        for cid, name_ko in name_result.all():
            name_ko_by_concept[cid] = name_ko

    # 조립 — kebab-id 원본 순서(confidence desc) 보존 + 개념 dedup(첫 등장=최고 confidence 유지).
    gaps: list[PrerequisiteGap] = []
    seen_concepts: set[uuid.UUID] = set()
    for kebab_id in active_misconceptions:
        mis_id = canonical_mis_id_by_kebab.get(kebab_id)
        if mis_id is None:
            continue  # canonical 미선정 — ②에서 이미 걸러짐.
        resolved = resolved_by_mis_id.get(mis_id)
        if resolved is None or resolved.concept is None:
            continue  # catalog 행 없음(방어적) / concept_src_id 없음 / concept_orphan — 정직 스킵.
        cid = resolved.concept.concept_id
        if cid in seen_concepts:
            continue  # 서로 다른 오개념이 같은 개념으로 귀결 → 중복 gap 방지.
        seen_concepts.add(cid)
        gaps.append(
            PrerequisiteGap(
                concept_id=cid,
                concept_code=resolved.concept.code,
                concept_name=name_ko_by_concept.get(cid),
                agreement="insufficient",  # BKT/IRT 교차검증 없음(오개념 신호만) — 정직 표시.
                depth=1,  # 그래프 traversal 깊이가 아니라 "직접 신호" sentinel(필드 기본값과 동일).
            )
        )
    return gaps
