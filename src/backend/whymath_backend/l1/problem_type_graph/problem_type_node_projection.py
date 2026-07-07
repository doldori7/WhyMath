"""문제유형 메타 PG 프로젝션 적재 — `problem_type_node` 테이블 problem_type_id 키 멱등 upsert (P3).

`l1/skill_graph/skill_node_projection.py`(스킬 메타 프로젝션)의 *문제유형 그래프* 짝이다. data
산출 `problem_type_graph_v1/graph.json`(문제유형 노드)의 *안전 메타*를 `problem_type_node`
(PG)에 멱등 upsert한다 — 검색 enrichment·필터·(후속) 문제 분류·추천 조인 백킹.

차이(`skill_node_projection.py` 대비):
  - **키가 problem_type_id**(graph.json `problem_type_id`·`ptype.<slug>`) — 타 노드 공간과 분리.
  - **입력 배열이 `problem_types`**(skill의 `skills`가 아님).
  - **behavior_area enum 없음(D1)**: cognitive-action은 `behavior_skills`(skill 참조 배열)로 표현·
    native enum을 두지 않는다. 로더는 enum 검증 없이 안전 TEXT/TEXT[]만 읽는다.
  - **review_status는 상수**('ai_estimated'·v1 자체작성이나 전문 검수 전·정직 표기).

법적(CLAUDE.md 우선순위 #2): 문제유형 택소노미는 전량 자체작성이라 redaction 무관. 적재 필드는 전부
안전 메타·자체 라벨이다(기출 문항 본문 0). 유형 연결은 참조 키(`behavior_skills`)만.

sync 엔진 재사용(신규 seam 0): 슬3 `embedding._build_sync_engine`을 그대로 재사용한다
(skill_node_projection·atom_node_projection과 동일 sync 좌석 규약·자격증명 하드코딩 0).

7계층: L1 데이터 기반의 *영속 프로젝션 적재*. 조회·소비(L2/L4·문제 태깅)는 후속(역방향 의존 금지).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.problem_type_node import PROBLEM_TYPE_REVIEW_STATUS_DEFAULT

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — skill_node_projection·atom_node_projection과 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _opt_str(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 strip한 str(skill_node_projection `_opt_str` 미러)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True, slots=True)
class ProblemTypeNodeRecord:
    """프로젝션 대상 한 문제유형 노드의 *안전 메타* — problem_type_id + 표시·필터 필드.

    `graph.json`의 한 problem_type에서 안전 키만 추린 값이다. 본문·표면·오개념·프롬프트 슬롯은 없다
    (순수 cognitive-action 택소노미·구조적 차단). 적재기가 이 레코드를 problem_type_id 키로 upsert.
    `review_status`는 슬롯이 없다 — 적재기가 상수로 박는다(v1 자체작성·전문 검수 전).
    """

    problem_type_id: str
    name_ko: str
    family: str
    behavior_skills: tuple[str, ...]
    mastery_estimable: bool
    description: str | None
    standard_codes: tuple[str, ...]


def load_problem_types_from_graph_json(path: Path) -> list[ProblemTypeNodeRecord]:
    """data-pipeline 산출 `graph.json` → 문제유형 *안전 메타* 레코드 목록(problem_type_id 키).

    `problem_types` 배열의 각 항목에서 안전 키만 읽어 `ProblemTypeNodeRecord`를 만든다.
    `problem_type_id`·`name_ko`·`family`는 필수라 누락 시 건너뛴다(NOT NULL 위반 방지·정직·조용한
    빈 적재 금지). `behavior_skills`도 ≥1개가 계약이나, 비었으면 건너뛴다(cognitive-action 표현 부재
    행 차단). 정상 코퍼스는 전 필드를 보유하므로 실경로에선 skip이 없다.

    Raises:
        FileNotFoundError: graph.json 부재.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[ProblemTypeNodeRecord] = []
    for record in payload.get("problem_types", []):
        problem_type_id = _opt_str(record.get("problem_type_id"))
        name_ko = _opt_str(record.get("name_ko"))
        family = _opt_str(record.get("family"))
        if problem_type_id is None or name_ko is None or family is None:
            continue

        raw_skills = record.get("behavior_skills")
        skills: tuple[str, ...] = (
            tuple(str(s) for s in raw_skills) if isinstance(raw_skills, (list, tuple)) else ()
        )
        if not skills:
            # behavior_skills ≥1 계약 위반(cognitive-action 표현 부재) — 조용한 빈 적재 대신 skip.
            continue

        raw_codes = record.get("standard_codes")
        codes: tuple[str, ...] = (
            tuple(str(c) for c in raw_codes) if isinstance(raw_codes, (list, tuple)) else ()
        )
        out.append(
            ProblemTypeNodeRecord(
                problem_type_id=problem_type_id,
                name_ko=name_ko,
                family=family,
                behavior_skills=skills,
                mastery_estimable=bool(record.get("mastery_estimable", True)),
                description=_opt_str(record.get("description")),
                standard_codes=codes,
            )
        )
    return out


class ProblemTypeNodeStore:
    """문제유형 메타 PG 프로젝션 적재기 — `problem_type_node` 키 멱등 upsert(sync).

    `SkillNodeStore`(스킬 메타 프로젝션)의 *문제유형 그래프* 짝이다. `upsert`는 PK 충돌 upsert
    (`INSERT ... ON CONFLICT(problem_type_id) DO UPDATE`)로 멱등 적재한다(같은 id 재적재 → 행 갱신·
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(skill_node_projection 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: ProblemTypeNodeRecord) -> None:
        """단일 문제유형 메타 upsert (멱등·problem_type_id PK 충돌 갱신).

        `INSERT ... ON CONFLICT(problem_type_id) DO UPDATE` — 안전 메타 전 필드 + review_status +
        updated_at(now())을 갱신한다. behavior_skills·standard_codes는 리스트로 바인딩(PG TEXT[]).
        본문·표면·오개념·프롬프트 컬럼은 없다(구조적 차단·native enum 없음).
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.problem_type_node import ProblemTypeNode

        stmt = pg_insert(ProblemTypeNode).values(
            problem_type_id=record.problem_type_id,
            name_ko=record.name_ko,
            family=record.family,
            behavior_skills=list(record.behavior_skills),
            mastery_estimable=record.mastery_estimable,
            description=record.description,
            standard_codes=list(record.standard_codes),
            review_status=PROBLEM_TYPE_REVIEW_STATUS_DEFAULT,
        )
        # PK 충돌 시 갱신 — updated_at은 now()로 새로 찍는다(server_default는 INSERT 전용).
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProblemTypeNode.problem_type_id],
            set_={
                "name_ko": stmt.excluded.name_ko,
                "family": stmt.excluded.family,
                "behavior_skills": stmt.excluded.behavior_skills,
                "mastery_estimable": stmt.excluded.mastery_estimable,
                "description": stmt.excluded.description,
                "standard_codes": stmt.excluded.standard_codes,
                "review_status": stmt.excluded.review_status,
                "updated_at": func.now(),
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_problem_type_nodes(
    records: Sequence[ProblemTypeNodeRecord],
    *,
    settings: Settings | None = None,
    store: ProblemTypeNodeStore | None = None,
) -> int:
    """문제유형 안전 메타를 `problem_type_node`에 멱등 upsert 적재(영속 프로젝션). 반환=적재 행 수.

    `populate_skill_nodes`의 *문제유형 그래프* 짝이다 — 각 레코드를 problem_type_id 키로 upsert한다
    (전량·review_status='ai_estimated'). 멱등(재실행 시 갱신). store 미주입 시 슬3 sync 엔진 재사용
    `ProblemTypeNodeStore`를 만든다.
    """
    resolved = settings if settings is not None else get_settings()
    node_store = store if store is not None else ProblemTypeNodeStore(settings=resolved)
    for record in records:
        node_store.upsert(record)
    return len(records)


__all__ = [
    "ProblemTypeNodeRecord",
    "ProblemTypeNodeStore",
    "load_problem_types_from_graph_json",
    "populate_problem_type_nodes",
]
