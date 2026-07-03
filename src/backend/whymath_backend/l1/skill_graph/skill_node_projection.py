"""스킬 메타 PG 프로젝션 적재 — `skill_node` 테이블 skill_id 키 멱등 upsert (Part 2 Phase 2a).

`l1/atom_graph/atom_node_projection.py`(원자 메타 code 키 프로젝션)의 *스킬 그래프* 짝이다.
data-pipeline 산출 `data/corpus/skill_graph_v1/graph.json`(스킬 노드)의 *안전 메타*를 `skill_node`
(PG) 테이블에 멱등 upsert한다 — 검색 enrichment·필터·(Phase 2b) skill mastery 조인 백킹.

차이(`atom_node_projection.py` 대비):
  - **키가 skill_id**(graph.json `skill_id`·`skill.<slug>`) — concept/atom code 공간과 분리.
  - **입력 배열이 `skills`**(concept/atom의 `concepts`가 아님).
  - **behavior_area는 6종 폐쇄 enum**: 로더가 `BehaviorArea(value)`로 검증·구성한다(잘못된 값이면
    ValueError — 조용한 오염 차단). PG native `behavior_area_enum` 컬럼에 적재.
  - **review_status는 상수**('ai_estimated'·v1 자체작성이나 전문 검수 전·정직 표기).

법적(CLAUDE.md 우선순위 #2): 스킬 택소노미는 전량 자체작성이라 redaction 무관. 적재 필드는 전부
안전 메타·자체 라벨이다. 스킬 연결은 참조 키(`prerequisite_skill_ids`)만.

sync 엔진 재사용(신규 seam 0): 슬3 `embedding._build_sync_engine`을 그대로 재사용한다
(atom_node_projection·node_projection과 동일 sync 좌석 규약·자격증명 하드코딩 0).

7계층: L1 데이터 기반의 *영속 프로젝션 적재*. 조회·소비(L2 mastery·L4)는 후속(역방향 의존 금지).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.skill_node import SKILL_REVIEW_STATUS_DEFAULT

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — atom_node_projection·node_projection과 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import BehaviorArea

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _opt_str(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 strip한 str(atom_node_projection `_opt_str` 미러)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True, slots=True)
class SkillNodeRecord:
    """프로젝션 대상 한 스킬 노드의 *안전 메타* — skill_id + 표시·필터 필드.

    `graph.json`의 한 skill에서 안전 키만 추린 값이다. 본문·오개념·프롬프트 슬롯은 없다(순수 스킬
    택소노미·구조적 차단). 적재기가 이 레코드를 skill_id 키로 upsert한다. `review_status`는 슬롯이
    없다 — 적재기가 상수로 박는다(v1 자체작성·전문 검수 전).
    """

    skill_id: str
    name_ko: str
    behavior_area: BehaviorArea
    family: str
    mastery_estimable: bool
    description: str | None
    prerequisite_skill_ids: tuple[str, ...]
    standard_codes: tuple[str, ...]


def load_skill_nodes_from_graph_json(path: Path) -> list[SkillNodeRecord]:
    """data-pipeline 산출 `graph.json` → 스킬 *안전 메타* 레코드 목록(skill_id 키).

    `skills` 배열의 각 항목에서 안전 키만 읽어 `SkillNodeRecord`를 만든다. `behavior_area`는
    `BehaviorArea(value)`로 검증·구성한다(6종 밖이면 ValueError — 조용한 오염 차단). `skill_id`·
    `name_ko`·`behavior_area`·`family`는 필수라 누락 시 건너뛴다(NOT NULL 위반 방지·정직·조용한
    빈 적재 금지). 정상 코퍼스는 전 필드를 보유하므로 실경로에선 skip이 없다.

    Raises:
        FileNotFoundError: graph.json 부재.
        ValueError: behavior_area가 6종 폐쇄 집합 밖(오염 입력 방어).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[SkillNodeRecord] = []
    for record in payload.get("skills", []):
        skill_id = _opt_str(record.get("skill_id"))
        name_ko = _opt_str(record.get("name_ko"))
        family = _opt_str(record.get("family"))
        raw_area = _opt_str(record.get("behavior_area"))
        if skill_id is None or name_ko is None or family is None or raw_area is None:
            continue
        behavior_area = BehaviorArea(raw_area)  # 6종 밖이면 ValueError(방어).

        raw_pre = record.get("prerequisite_skill_ids")
        prereqs: tuple[str, ...] = (
            tuple(str(p) for p in raw_pre) if isinstance(raw_pre, (list, tuple)) else ()
        )
        raw_codes = record.get("standard_codes")
        codes: tuple[str, ...] = (
            tuple(str(c) for c in raw_codes) if isinstance(raw_codes, (list, tuple)) else ()
        )
        out.append(
            SkillNodeRecord(
                skill_id=skill_id,
                name_ko=name_ko,
                behavior_area=behavior_area,
                family=family,
                mastery_estimable=bool(record.get("mastery_estimable", True)),
                description=_opt_str(record.get("description")),
                prerequisite_skill_ids=prereqs,
                standard_codes=codes,
            )
        )
    return out


class SkillNodeStore:
    """스킬 메타 PG 프로젝션 적재기 — `skill_node` 테이블 skill_id 키 멱등 upsert(sync).

    `AtomNodeStore`(원자 메타 프로젝션)의 *스킬 그래프* 짝이다. `upsert`는 PK 충돌 upsert
    (`INSERT ... ON CONFLICT(skill_id) DO UPDATE`)로 멱등 적재한다(같은 skill_id 재적재 → 행 갱신·
    updated_at 갱신). `review_status`는 상수('ai_estimated')로 박는다. sync 엔진은 슬3
    `_build_sync_engine`을 재사용해 지연 생성·캐시한다(신규 seam 0). *적재 전용* 좌석이다.
    """

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(atom_node_projection 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: SkillNodeRecord) -> None:
        """단일 스킬 메타 upsert (멱등·skill_id PK 충돌 갱신).

        `INSERT ... ON CONFLICT(skill_id) DO UPDATE` — 안전 메타 전 필드 + review_status 상수 +
        updated_at(now())을 갱신한다. behavior_area는 native enum(값 바인딩)·prerequisite_skill_ids·
        standard_codes는 리스트로 바인딩(PG TEXT[]). 본문·오개념·프롬프트 컬럼은 없다(구조적 차단).
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.skill_node import SkillNode

        stmt = pg_insert(SkillNode).values(
            skill_id=record.skill_id,
            name_ko=record.name_ko,
            behavior_area=record.behavior_area.value,
            family=record.family,
            mastery_estimable=record.mastery_estimable,
            description=record.description,
            prerequisite_skill_ids=list(record.prerequisite_skill_ids),
            standard_codes=list(record.standard_codes),
            review_status=SKILL_REVIEW_STATUS_DEFAULT,
        )
        # PK 충돌 시 갱신 — updated_at은 now()로 새로 찍는다(server_default는 INSERT 전용).
        stmt = stmt.on_conflict_do_update(
            index_elements=[SkillNode.skill_id],
            set_={
                "name_ko": stmt.excluded.name_ko,
                "behavior_area": stmt.excluded.behavior_area,
                "family": stmt.excluded.family,
                "mastery_estimable": stmt.excluded.mastery_estimable,
                "description": stmt.excluded.description,
                "prerequisite_skill_ids": stmt.excluded.prerequisite_skill_ids,
                "standard_codes": stmt.excluded.standard_codes,
                "review_status": stmt.excluded.review_status,
                "updated_at": func.now(),
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_skill_nodes(
    records: Sequence[SkillNodeRecord],
    *,
    settings: Settings | None = None,
    store: SkillNodeStore | None = None,
) -> int:
    """스킬 안전 메타를 `skill_node`에 멱등 upsert 적재(영속 프로젝션). 반환=적재 행 수.

    `populate_atom_nodes`의 *스킬 그래프* 짝이다 — 각 레코드를 skill_id 키로 upsert한다(전량·
    review_status='ai_estimated'). 멱등(재실행 시 갱신). store 미주입 시 슬3 sync 엔진 재사용
    `SkillNodeStore`를 만든다.
    """
    resolved = settings if settings is not None else get_settings()
    node_store = store if store is not None else SkillNodeStore(settings=resolved)
    for record in records:
        node_store.upsert(record)
    return len(records)


__all__ = [
    "SkillNodeRecord",
    "SkillNodeStore",
    "load_skill_nodes_from_graph_json",
    "populate_skill_nodes",
]
