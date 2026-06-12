"""개념 메타 PG 프로젝션 적재 — `concept_node` 테이블 UC 키 멱등 upsert (소비 슬라이스 1).

슬1 산출 `graph.json`(UC 키·정제)의 개념 *안전 메타*를 `concept_node`(PG) 테이블에 멱등
upsert한다. 슬3 `embedding.py`(임베딩 *벡터* 적재)의 *메타 투영* 짝이다 — 같은 `graph.json`을
읽되, 슬3은 안전 필드를 *임베딩*해 벡터를 적재하고, 이 모듈은 안전 필드 *값 자체*를 메타로
적재한다. 둘 다 **동일 UC 키**라 검색이 한 키로 join한다(삼중 store: Neo4j 그래프·pgvector
벡터·PG 메타).

설계 결정(확정): 메타 브리지 = **PG 프로젝션**(backend↔Neo4j 런타임 연결 안 함). 검색
enrichment·게이팅을 PG 조인으로 하기 위한 *적재* 좌석이다(조회·조인은 슬3 retrieval 확장에서).

────────────────────────────────────────────────────────────────────────────
redaction (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
적재 필드는 **안전 메타만** — `name_ko`·`domain`·`review_status`·`standard_codes`·`ccss_code`·
`difficulty_tier`·`metaphor`·`accepted_expressions`. **`description`·`formal_definition`은 읽지도
적재하지도 않는다**(성취기준 본문 근접 필드·graph.json 부재·ORM 컬럼 부재의 삼중 방어). 슬3
임베딩 로더와 같은 redaction 규약을 메타 적재에도 적용한다.

────────────────────────────────────────────────────────────────────────────
sync 엔진 재사용 (신규 seam 0)
────────────────────────────────────────────────────────────────────────────
슬3 `embedding._build_sync_engine`(sync psycopg·지연 import·`db_disable_pool` NullPool 가드)을
*그대로 재사용*한다 — 같은 코드베이스 sync 좌석 규약. 이 테이블은 벡터 컬럼이 없어 pgvector
어댑터 등록이 불필요하나, 등록은 무해(벡터를 안 만지면 no-op)하고 신규 엔진 빌더를 만들지 않는
편이 정합하다(CLAUDE.md 신규 금지·로컬 우선). sync URL은 `Settings.sync_database_url`(env 파생)·
자격증명 0 하드코딩.

7계층: L1 데이터 기반의 *영속 프로젝션 적재*. 검색 조회·소비(L2/L4)는 후속(역방향 의존 금지).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — 같은 sync psycopg 좌석 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


@dataclass(frozen=True, slots=True)
class ConceptNodeMeta:
    """검색 enrichment용 *안전* 메타 한 묶음 — `concept_node` 조회 결과.

    `search_concepts`가 UC 키로 이 메타를 붙여 `ConceptSearchHit`를 풍부하게 한다(name_ko·
    domain 표시·review_status 게이팅). **본문 필드(description·formal_definition)는 없다** —
    `concept_node`에 컬럼 자체가 없으므로 구조적으로 흐를 수 없다(redaction). 검색 결과에 실리는
    안전 표시·게이팅 메타만 담는다.
    """

    name_ko: str
    domain: str
    review_status: str


# graph.json에서 프로젝션으로 *허용된* 안전 메타 키(자체 작성·코드·층위 — 본문 아님). 이 집합
# 밖(특히 description·formal_definition)은 읽지 않는다(graph.json 부재이며 로더가 무시 — 방어).
_SAFE_META_KEYS: tuple[str, ...] = (
    "concept_id",
    "name_ko",
    "domain",
    "review_status",
    "standard_codes",
    "ccss_code",
    "difficulty_tier",
    "metaphor",
    "accepted_expressions",
)


@dataclass(frozen=True, slots=True)
class ConceptNodeRecord:
    """프로젝션 대상 한 개념의 *안전 메타* — UC concept_id + 표시·게이팅 필드.

    `graph.json`의 `Concept.model_dump()` 항목에서 안전 키만 추린 값이다. **description·
    formal_definition은 슬롯 자체가 없다**(redaction — 구조적 차단). 적재기가 이 레코드를 UC
    키로 upsert한다.
    """

    concept_id: str
    name_ko: str
    domain: str
    review_status: str
    standard_codes: tuple[str, ...]
    ccss_code: str | None
    difficulty_tier: int | None
    metaphor: str | None
    accepted_expressions: str | None


def _opt_str(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 strip한 str(풍부 필드 정규화·transform `_opt` 미러)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_int(value: object) -> int | None:
    """정수 옵션 파싱 — 빈/None/비정수는 None(transform `_int_opt` 미러). 검증은 ORM/DB."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def load_concept_nodes_from_graph_json(path: Path) -> list[ConceptNodeRecord]:
    """슬1 산출 `graph.json` → 개념 *안전 메타* 레코드 목록(UC 키·redaction 청결).

    `concepts` 배열의 각 항목에서 **안전 키만**(`_SAFE_META_KEYS`) 읽어 `ConceptNodeRecord`를
    만든다 — `description`·`formal_definition`은 읽지 않는다(graph.json 부재이며 무시). 슬3
    임베딩 로더(`load_concepts_from_graph_json`)와 달리 *빈 표현 제외를 하지 않는다*: 메타
    프로젝션은 의미검색 enrichment·게이팅용이라 전 개념(403)을 적재해야 한다(검색이 잡은 UC의
    메타가 없으면 None graceful이지만, 누락 자체를 만들지 않는 게 옳다 — 슬3 임베딩은 전량,
    메타도 전량).

    `name_ko`·`domain`·`review_status`는 graph.json `Concept`이 항상 보유한다(필수 필드·
    use_enum_values). 누락 시(오염된 입력) 빈 문자열로 적재하지 않고 *건너뛴다*(NOT NULL 위반
    방지·정직). `standard_codes`는 리스트가 아니면 빈 튜플로 정규화한다.

    Raises:
        FileNotFoundError: graph.json 부재.
        ValueError: concept_id 없는 항목(슬1 산출은 항상 UC를 갖는다 — 방어).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[ConceptNodeRecord] = []
    for record in payload.get("concepts", []):
        concept_id = str(record.get("concept_id", "")).strip()
        if not concept_id:
            raise ValueError(f"graph.json 개념에 concept_id가 없습니다: {record!r}")

        name_ko = _opt_str(record.get("name_ko"))
        domain = _opt_str(record.get("domain"))
        review_status = _opt_str(record.get("review_status"))
        if name_ko is None or domain is None or review_status is None:
            # 필수 표시·게이팅 필드 누락 — NOT NULL 위반 대신 건너뛴다(정직·조용한 빈 적재 금지).
            # graph.json 정상 산출은 셋 다 보유하므로 실제 경로에선 발생하지 않는다.
            continue

        raw_codes = record.get("standard_codes")
        codes: tuple[str, ...] = (
            tuple(str(c) for c in raw_codes) if isinstance(raw_codes, (list, tuple)) else ()
        )
        out.append(
            ConceptNodeRecord(
                concept_id=concept_id,
                name_ko=name_ko,
                domain=domain,
                review_status=review_status,
                standard_codes=codes,
                ccss_code=_opt_str(record.get("ccss_code")),
                difficulty_tier=_opt_int(record.get("difficulty_tier")),
                metaphor=_opt_str(record.get("metaphor")),
                accepted_expressions=_opt_str(record.get("accepted_expressions")),
            )
        )
    return out


class ConceptNodeStore:
    """개념 메타 PG 프로젝션 적재기 — `concept_node` 테이블 UC 키 멱등 upsert(sync).

    슬3 `ConceptEmbeddingIndex`의 *메타 투영* 짝이다. `upsert`는 PK 충돌 upsert(`INSERT ... ON
    CONFLICT(concept_id) DO UPDATE`)로 멱등 적재한다(같은 UC 재적재 → 행 갱신). sync 엔진은
    슬3 `_build_sync_engine`을 재사용해 지연 생성·캐시한다(신규 seam 0). 벡터 컬럼이 없어 코사인
    검색 메서드는 두지 않는다 — *적재 전용* 좌석이다(조회·조인은 슬3 retrieval 확장에서 PG 조인).
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(슬3 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: ConceptNodeRecord) -> None:
        """단일 개념 메타 upsert (멱등·UC PK 충돌 갱신).

        `INSERT ... ON CONFLICT(concept_id) DO UPDATE` — 안전 메타 전 필드 + updated_at(now())을
        갱신한다. **description·formal_definition은 INSERT 컬럼에 없다**(redaction — 레코드에
        슬롯이 없어 구조적 차단). standard_codes는 리스트로 바인딩(PG TEXT[]).
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept_node import ConceptNode

        stmt = pg_insert(ConceptNode).values(
            concept_id=record.concept_id,
            name_ko=record.name_ko,
            domain=record.domain,
            review_status=record.review_status,
            standard_codes=list(record.standard_codes),
            ccss_code=record.ccss_code,
            difficulty_tier=record.difficulty_tier,
            metaphor=record.metaphor,
            accepted_expressions=record.accepted_expressions,
        )
        # PK 충돌 시 갱신 — updated_at은 now()로 새로 찍는다(server_default는 INSERT 전용).
        stmt = stmt.on_conflict_do_update(
            index_elements=[ConceptNode.concept_id],
            set_={
                "name_ko": stmt.excluded.name_ko,
                "domain": stmt.excluded.domain,
                "review_status": stmt.excluded.review_status,
                "standard_codes": stmt.excluded.standard_codes,
                "ccss_code": stmt.excluded.ccss_code,
                "difficulty_tier": stmt.excluded.difficulty_tier,
                "metaphor": stmt.excluded.metaphor,
                "accepted_expressions": stmt.excluded.accepted_expressions,
                "updated_at": func.now(),
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def fetch_node_meta(
    concept_ids: Sequence[str],
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
) -> dict[str, ConceptNodeMeta]:
    """UC 키 목록 → `concept_node` 안전 메타 dict (검색 enrichment용 단일 IN 조회·sync).

    `WHERE concept_id = ANY(:ids)` 단일 쿼리로 표시·게이팅 *안전 필드*(name_ko·domain·
    review_status)만 SELECT한다 — **description·formal_definition은 컬럼이 없어 조회 자체가
    불가**(redaction). `concept_node`에 없는 UC(메타 적재 누락)는 결과 dict에서 빠진다 →
    호출자가 None으로 graceful 처리(`search_concepts`). 입력이 비면 빈 dict(쿼리 생략).

    sync 엔진은 슬3 빌더를 재사용한다(신규 seam 0) — 검색 좌석이 이미 sync(블로킹)라 같은
    엔진 평면에서 enrichment 조회가 일어난다(`search` 직후 같은 워커 스레드). engine 주입
    가능(테스트 격리·검색 좌석이 같은 엔진을 넘김).
    """
    ids = [str(c) for c in concept_ids]
    if not ids:
        return {}
    from sqlalchemy import select

    from whymath_backend.db.models.concept_node import ConceptNode

    resolved = settings if settings is not None else get_settings()
    eng = engine if engine is not None else _build_sync_engine(resolved)
    stmt = select(
        ConceptNode.concept_id,
        ConceptNode.name_ko,
        ConceptNode.domain,
        ConceptNode.review_status,
    ).where(ConceptNode.concept_id.in_(ids))
    with eng.connect() as conn:
        rows = conn.execute(stmt).all()
    return {
        row.concept_id: ConceptNodeMeta(
            name_ko=row.name_ko,
            domain=row.domain,
            review_status=row.review_status,
        )
        for row in rows
    }


def populate_concept_nodes(
    records: Sequence[ConceptNodeRecord],
    *,
    settings: Settings | None = None,
    store: ConceptNodeStore | None = None,
) -> int:
    """개념 안전 메타를 `concept_node`에 멱등 upsert 적재(영속 프로젝션). 반환=적재 행 수.

    슬3 `populate_concept_embeddings`의 *메타 투영* 짝이다 — 임베딩 호출 없이(provider 불요) 각
    레코드를 UC 키로 upsert한다(403 전량·review_status 포함). 멱등(재실행 시 갱신). store 미주입
    시 슬3 sync 엔진 재사용 `ConceptNodeStore`를 만든다.
    """
    resolved = settings if settings is not None else get_settings()
    node_store = store if store is not None else ConceptNodeStore(settings=resolved)
    for record in records:
        node_store.upsert(record)
    return len(records)


__all__ = [
    "ConceptNodeMeta",
    "ConceptNodeRecord",
    "ConceptNodeStore",
    "fetch_node_meta",
    "load_concept_nodes_from_graph_json",
    "populate_concept_nodes",
]
