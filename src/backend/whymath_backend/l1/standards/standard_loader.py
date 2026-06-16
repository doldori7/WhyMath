"""NCIC 성취기준 코퍼스 → backend ORM 적재기 (P1 — achievement_standard·concept_standard_link).

`l1/concept_graph/backend_concept.py`(개념 노드 적재)·`backend_edge.py`(개념 엣지 적재)의 *성취기준*
짝이다. P1-2 슬라이스가 성취기준의 ORM·계약(`schema/standard.py`)·마이그레이션만 세우고 코퍼스
로더는 *후속 몫*으로 보류했는데(두 모델 docstring), 이 모듈이 그 로더를 놓는다 — data-pipeline
NCIC 수집기가 낸 *코퍼스 컬렉션 JSON*을 backend 영속 두 테이블로 멱등 적재한다. 그러면 L1 데이터
기반의 성취기준이 런타임에서 조회 가능해지고(소비처: 커리큘럼 정렬·진단), 개념↔성취기준 N:M 링크가
채워져 개념그래프(backend `concept`)와 성취기준이 이어진다.

────────────────────────────────────────────────────────────────────────────
코퍼스 포맷 (단일 Collection 객체 — jsonl 아님)
────────────────────────────────────────────────────────────────────────────
data-pipeline `data_pipeline/ncic/load.py`의 `write_json`·`write_links_json`은 *한 개의 JSON 객체*
(Collection)를 낸다 — graph.json처럼 줄 단위 jsonl이 아니다. 성취기준 컬렉션은
`{"source_citation":..., "license_notice":..., "curriculum_revision":..., "collected_at":...,
"crawler_version":..., "standards":[ {...} ]}`, 링크 컬렉션은 같은 표지 + 최상위 `"links":[...]`.
이 로더는 그 Collection의 배열 키(`standards`/`links`)만 본다(표지 메타는 무시 — 출처 표시는
수집기·노출 계층 몫). 입력은 `dict`(이미 로드된 컬렉션) 또는 `Path`(파일 경로) 둘 다 받는다.

성취기준 dict 키: `norm_id, code, grade_band, school_type, subject, domain, sub_domain, statement,
commentary, big_idea, curriculum_revision, effective_from, parent_codes, source_url,
source_document`. 링크 dict 키: `concept_src_id, norm_id, link_type, note`.

────────────────────────────────────────────────────────────────────────────
키 이름 seam (로더가 메우는 rename — 두 schema docstring이 지정)
────────────────────────────────────────────────────────────────────────────
data-pipeline 코퍼스와 backend schema의 키 이름이 두 군데 다르다. 이 로더가 *그 seam을 메운다*:
  - 성취기준: 코퍼스 `code`(고시 원문코드) → backend `official_code`. (`code`는 backend 도메인2
    Concept의 개념코드와 어휘가 겹쳐 혼동을 부르므로 `official_code`로 명시. `schema/standard.py`
    모듈 docstring "⚠️ 키 명칭 차이" 지정.)
  - 링크: 코퍼스 `concept_src_id`(개념 소스 식별자) → backend `concept_code`(개념 식별자 느슨참조).
나머지 키는 동명 직결이다(`norm_id`·`statement`·`link_type`·`note` 등).

────────────────────────────────────────────────────────────────────────────
concept_src_id → concept_code 참조 처리 (backend_edge와의 *구조적 차이* — store-direct)
────────────────────────────────────────────────────────────────────────────
backend_edge는 개념 양끝(UC)을 backend `concept` 단일 조회 맵(`{code: uuid}`)으로 *해석*해 UUID FK로
저장한다 — `concept_edge.from/to_concept_id`가 실 FK(UUID)이기 때문이다. **링크는 다르다**:
`concept_standard_link.concept_code`는 **FK가 아니라 느슨참조**다(ORM docstring: "FK 아님 — 개념
식별자 공간이 진화 중이라 DB FK로 묶지 않는다"). 컬럼이 *코드 문자열 자체*를 담으므로 해석할 UUID가
없다 — 따라서 `concept_src_id`는 **그대로 `concept_code`에 저장**한다(store-direct). 이는
backend_edge가 *맵 해석*을 한 것과 대비되는 이 로더의 핵심 결정이며, 두 경우 모두 *조용한 누락을
만들지 않는다*는 원칙은 같다: backend_edge가 맵에 없는 개념 UC를 orphan으로 skip·보고하듯, 이
로더는 실 FK인 `norm_id`가 적재 성취기준 집합에 없는 링크(unresolved 성취기준 참조)를 orphan으로
skip·보고한다(FK 위반 방지).

────────────────────────────────────────────────────────────────────────────
멱등 (PG ON CONFLICT — backend_concept·backend_edge 규약)
────────────────────────────────────────────────────────────────────────────
  - 성취기준: PK `norm_id` 충돌 시 `INSERT ... ON CONFLICT(norm_id) DO UPDATE`로 나머지 컬럼을
    갱신한다(backend_concept의 ON CONFLICT(code) 미러). `official_code`는 교육과정 간 *비유일*이라
    PK가 아니라 일반 컬럼 — 2022·2015에 동일 `code`(예 `[12미적01-01]`)가 와도 `norm_id`가 달라
    **2행으로** 적재된다(official_code 충돌쌍이 PK 충돌이 아님). norm_id PK 기준 입력 내 중복은
    *마지막 우선* dedup한다(단일 배치 ON CONFLICT가 같은 행을 두 번 건드리는 오류 방지 —
    data-pipeline load.py 선례).
  - 링크: 의미 유일키 `(concept_code, norm_id, link_type)` 충돌 시 `DO UPDATE`로 `note`만 갱신하고
    **link_id(UUID PK)는 SET하지 않아 보존**한다(backend_edge가 edge_id를 보존하듯).

sync 엔진은 슬3 `_build_sync_engine`을 재사용한다(신규 seam 0 — backend_concept·backend_edge와 동일
좌석 규약). 자격증명은 env(`Settings.sync_database_url`)·하드코딩 0. `from_schema`/`to_schema`는
계약·검증 정본이나, 멱등 upsert는 ORM `insert()`가 아니라 PG `pg_insert`(ON CONFLICT)를 써야
하므로 적재 컬럼 값은 검증된 `schema` 모델에서 뽑아 바인딩한다(schema가 형식·rename 게이트,
upsert가 멱등).

법적 메모(공공누리 1유형): 성취기준 본문(`statement`)·해설(`commentary`)은 NCIC 공공누리
제1유형이라 본문 보유가 *허용*된다(`schema/standard.py` 법적 메모·`licensing_safety.md` 가이드
v2.0). 검정교과서·EBS·평가원 본문 금지와 대비 — 따라서 backend_concept이 본문 3컬럼을 redaction한
것과 달리, 이
로더는 성취기준 본문을 *적재한다*(공공누리 1유형 예외). 출처 표시는 수집기·노출 계층이 동봉한다.

7계층: L1 데이터 기반의 *런타임 엔티티·관계 적재*. 소비(커리큘럼 정렬·진단·개념↔기준 조회)는 이
행을 *조회*하되 여기서 구현하지 않는다(역방향 의존 금지·후속).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from whymath_backend.config import Settings, get_settings

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — backend_concept·backend_edge와 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.standard import AchievementStandard, ConceptStandardLink

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 입력 정규화 (dict | Path → Collection dict)
# ──────────────────────────────────────────────────────────────────────────
def _as_collection(source: dict[str, Any] | Path) -> dict[str, Any]:
    """코퍼스 입력을 Collection dict로 정규화 — `dict`는 그대로, `Path`는 단일 JSON 객체로 로드.

    data-pipeline `write_json`/`write_links_json`은 *한 개의 JSON 객체*(Collection)를 내므로
    `json.loads`로 통째 읽는다(graph.json·jsonl과 달리 줄 단위 파싱 아님). dict가 들어오면 이미
    로드된 컬렉션으로 보고 그대로 쓴다(테스트·in-memory 경로). 그 외 타입은 거부한다(정직).

    Raises:
        FileNotFoundError: Path가 가리키는 파일 부재.
        TypeError: dict·Path가 아닌 입력.
    """
    if isinstance(source, dict):
        return source
    if isinstance(source, Path):
        loaded: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
        return loaded
    raise TypeError(f"코퍼스 입력은 dict 또는 Path여야 합니다: {type(source).__name__}")


# ──────────────────────────────────────────────────────────────────────────
# 성취기준 적재 (코퍼스 standards → achievement_standard·norm_id ON CONFLICT)
# ──────────────────────────────────────────────────────────────────────────
def _standard_from_row(row: dict[str, Any]) -> AchievementStandard:
    """코퍼스 성취기준 dict → 검증된 `schema.AchievementStandard` (`code`→`official_code` rename).

    seam: 코퍼스는 고시 원문코드를 `code` 키로 두지만 backend schema는 `official_code`다(혼동
    회피·`schema/standard.py` 모듈 docstring). 여기서 `code`를 꺼내 `official_code`로 옮긴다 — 이
    rename이 이 슬라이스의 핵심이다. 나머지 키는 동명 직결이며, schema가 형식·필수성을 재검증한다
    (extra=forbid라 `code` 키가 그대로 남아 있으면 거부되므로 *반드시* pop으로 제거해 rename한다).
    """
    data = dict(row)  # 원본 불변(호출자 dict 보호)
    # 코퍼스 `code` → schema `official_code` (필수 rename). schema는 extra=forbid라 `code`를
    # 남기면 거부되므로 pop으로 옮긴다. `code`가 없으면 official_code 누락으로 schema가 검증
    # 단계에서 ValidationError를 낸다(형식 게이트는 schema 몫).
    if "code" in data:
        data["official_code"] = data.pop("code")
    return AchievementStandard.model_validate(data)


def load_standards(
    session: dict[str, Any] | Path | None,
    collection_json: dict[str, Any] | Path,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    store: AchievementStandardStore | None = None,
) -> int:
    """성취기준 Collection JSON을 backend `achievement_standard`에 멱등 upsert. 반환=적재 행 수.

    `populate_backend_concepts`(개념 노드)의 *성취기준* 짝이다 — Collection의 `standards` 배열을
    행마다 `schema.AchievementStandard`로 빌드(코퍼스 `code`→`official_code` rename)한 뒤 `norm_id`
    PK 충돌 멱등 upsert한다. `official_code`는 비유일(2022·2015 충돌 가능)이라 PK가 아니므로 같은
    `code`라도 `norm_id`가 다르면 2행으로 적재된다. 입력 내 norm_id 중복은 *마지막 우선* dedup한다
    (단일 배치 ON CONFLICT 중복행 오류 방지). 빈 컬렉션은 0(조기 반환).

    `session` 인자는 backend_concept·backend_edge 적재기의 store/engine 좌석 규약과의 호환을 위한
    *자리표시*다(이 적재기는 sync 엔진으로 동작하므로 ORM async Session을 쓰지 않는다 — None 허용).
    store/engine/settings 미주입 시 슬3 sync 엔진 재사용 `AchievementStandardStore`를 만든다.

    Raises:
        FileNotFoundError: collection_json이 Path인데 파일 부재.
        pydantic.ValidationError: 코퍼스 행이 schema 형식을 위반(형식 게이트는 schema 몫).
    """
    del session  # async Session 미사용(sync 엔진 좌석) — 호환 자리표시.
    collection = _as_collection(collection_json)
    rows = collection.get("standards", [])
    standards = [_standard_from_row(row) for row in rows]
    if not standards:
        return 0
    resolved = settings if settings is not None else get_settings()
    std_store = (
        store if store is not None else AchievementStandardStore(engine=engine, settings=resolved)
    )
    return std_store.populate(standards)


class AchievementStandardStore:
    """성취기준 코퍼스 → backend `achievement_standard` 적재기 — norm_id PK 충돌 멱등 upsert(sync).

    `BackendConceptStore`(개념 노드)의 *성취기준* 짝이다(같은 sync 좌석·멱등 규약). `populate`는 각
    성취기준을 `INSERT ... ON CONFLICT(norm_id) DO UPDATE`로 멱등 적재한다 — 같은 norm_id 재적재는
    나머지 컬럼을 갱신한다(norm_id는 의미 문자열 PK라 server_default 없음·로더가 채움).
    `official_code`는 교육과정 간 비유일이라 일반 컬럼으로 적재된다(같은 code·다른 norm_id → 2행).
    입력 내 norm_id 중복은 적재 전 *마지막 우선* dedup한다(단일 배치 ON CONFLICT가 같은 행을 두 번
    건드리는 오류 방지 — data-pipeline load.py 선례). sync 엔진은 슬3 `_build_sync_engine`을
    재사용해 지연 생성·캐시한다(신규 seam 0).

    본문 적재(공공누리 1유형): backend_concept이 description·formal_definition을 redaction한 것과
    *달리* 이 적재기는 성취기준 본문(`statement`)·해설(`commentary`)을 적재한다 — NCIC 공공누리
    제1유형이라 본문 보유가 허용되는 예외 출처다(모듈 docstring 법적 메모).
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(backend_concept 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def populate(self, standards: Sequence[AchievementStandard]) -> int:
        """성취기준 schema 모델들을 `achievement_standard`에 멱등 upsert. 반환=적재 행 수(dedup 후).

        ① norm_id PK 기준 *마지막 우선* dedup(단일 배치 ON CONFLICT 중복행 오류 방지) → ② 각 행을
        `ON CONFLICT(norm_id) DO UPDATE`로 적재(나머지 컬럼 갱신·PK는 SET 안 함·보존). 입력 빈 0.
        컬럼 값은 검증된 schema 모델의 `model_dump()`에서 뽑되 `parent_codes`(NOT NULL 배열·
        default_factory=list)는 항상 list라 그대로 바인딩한다. `code`(official_code)는 이미 rename된
        값이다(로더가 메움). 반환은 적재 시도 행 수(dedup 후 길이)다.
        """
        if not standards:
            return 0

        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.achievement_standard import (
            AchievementStandard as AchievementStandardORM,
        )

        # norm_id PK 기준 dedup(마지막 우선) — 단일 배치 INSERT의 ON CONFLICT 중복행 오류 방지.
        by_norm_id: dict[str, AchievementStandard] = {s.norm_id: s for s in standards}
        deduped = list(by_norm_id.values())

        # PK norm_id를 제외한 갱신 컬럼 집합(ON CONFLICT DO UPDATE SET) — mapper 컬럼키에서 도출.
        all_keys = {col.key for col in sa.inspect(AchievementStandardORM).mapper.column_attrs}
        update_keys = all_keys - {"norm_id"}

        with self._get_engine().begin() as conn:
            for standard in deduped:
                # 검증된 schema에서 ORM 컬럼 값만 추린다(schema 필드명=ORM 컬럼명·official_code).
                payload = standard.model_dump()
                values = {k: v for k, v in payload.items() if k in all_keys}
                stmt = pg_insert(AchievementStandardORM).values(**values)
                # norm_id(PK) 충돌 시 나머지 컬럼 갱신 — PK는 SET하지 않아 보존(멱등).
                stmt = stmt.on_conflict_do_update(
                    index_elements=[AchievementStandardORM.norm_id],
                    set_={key: stmt.excluded[key] for key in update_keys},
                )
                conn.execute(stmt)
        return len(deduped)


# ──────────────────────────────────────────────────────────────────────────
# 링크 적재 (코퍼스 links → concept_standard_link·의미키 ON CONFLICT·orphan skip)
# ──────────────────────────────────────────────────────────────────────────
def _link_from_row(row: dict[str, Any]) -> ConceptStandardLink:
    """코퍼스 링크 dict → 검증된 `schema.ConceptStandardLink` (`concept_src_id`→`concept_code`).

    seam: 코퍼스는 개념 소스 식별자를 `concept_src_id` 키로 두지만 backend schema는
    `concept_code`다. 여기서 `concept_src_id`를 꺼내 `concept_code`로 옮긴다(store-direct — 해석할
    UUID 없음·느슨참조, 모듈 docstring 핵심 결정). schema는 extra=forbid라 `concept_src_id` 키가
    남으면 거부되므로 pop으로 rename한다. 나머지(`norm_id`·`link_type`·`note`)는 동명 직결이며
    schema가 재검증한다.
    """
    data = dict(row)  # 원본 불변(호출자 dict 보호)
    # 코퍼스 `concept_src_id` → schema `concept_code` (store-direct rename·느슨참조). schema는
    # extra=forbid라 `concept_src_id`를 남기면 거부되므로 pop으로 옮긴다.
    if "concept_src_id" in data:
        data["concept_code"] = data.pop("concept_src_id")
    return ConceptStandardLink.model_validate(data)


def load_links(
    session: dict[str, Any] | Path | None,
    collection_json: dict[str, Any] | Path,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    store: ConceptStandardLinkStore | None = None,
) -> int:
    """링크 Collection JSON을 backend `concept_standard_link`에 멱등 upsert. 반환=적재 행 수.

    `populate_backend_edges`(개념 엣지)의 *링크* 짝이다 — Collection의 `links` 배열을 행마다
    `schema.ConceptStandardLink`로 빌드(코퍼스 `concept_src_id`→`concept_code` store-direct
    rename)한 뒤 의미 유일키 `(concept_code, norm_id, link_type)` 충돌 멱등 upsert한다.
    `concept_code`는 FK가 아니라 느슨참조라 *그대로 저장*한다(backend_edge가 UC→UUID로 *해석*한 것과
    대비 — 모듈 docstring). 실 FK인 `norm_id`는 적재 성취기준 집합에 없으면 orphan으로 skip한다
    (FK 위반 방지·조용한 누락 금지 — backend_edge orphan skip 미러). 빈 컬렉션은 0.

    `session` 인자는 좌석 규약 호환 자리표시다(sync 엔진 사용 — None 허용). store/engine/settings
    미주입 시 슬3 sync 엔진 재사용 `ConceptStandardLinkStore`를 만든다. orphan skip 수는
    (적재 행 수 ≤ 링크 수)로 드러난다(상세 메시지는 store.populate 반환의 둘째 원소).

    Raises:
        FileNotFoundError: collection_json이 Path인데 파일 부재.
        pydantic.ValidationError: 코퍼스 행이 schema 형식을 위반(형식 게이트는 schema 몫).
    """
    del session  # async Session 미사용(sync 엔진 좌석) — 호환 자리표시.
    collection = _as_collection(collection_json)
    rows = collection.get("links", [])
    links = [_link_from_row(row) for row in rows]
    if not links:
        return 0
    resolved = settings if settings is not None else get_settings()
    link_store = (
        store if store is not None else ConceptStandardLinkStore(engine=engine, settings=resolved)
    )
    loaded, _skipped = link_store.populate(links)
    return loaded


class ConceptStandardLinkStore:
    """개념↔성취기준 링크 → backend `concept_standard_link` 적재기 — 의미키 멱등 upsert(sync).

    `BackendEdgeStore`(개념 엣지)의 *링크* 짝이다(같은 sync 좌석·멱등 규약·orphan skip). 핵심 차이:
    backend_edge는 개념 양끝(UC)을 backend `concept` 맵으로 *해석*해 UUID FK로 저장했으나, 링크의
    `concept_code`는 **FK가 아니라 느슨참조**라 해석 없이 *그대로 저장*한다(store-direct·모듈
    docstring). 대신 *실 FK*인 `norm_id`(→`achievement_standard.norm_id`)를 적재 성취기준 집합과
    대조해, 그 집합에 없는 링크는 orphan으로 skip한다(FK 위반 방지 — backend_edge가 맵에 없는 UC를
    skip한 것의 짝). `populate`는 먼저 `achievement_standard.norm_id` 전량을 단일 조회해 알려진
    norm_id 집합을 만들고(N+1 0), 각 링크의 norm_id가 그 집합에 있을 때만 `INSERT ... ON
    CONFLICT(concept_code, norm_id, link_type) DO UPDATE`로 적재한다 — `note`만 갱신하고
    **link_id(UUID PK)는 SET하지 않아 보존**한다(backend_edge가 edge_id를 보존하듯). sync 엔진은
    슬3 `_build_sync_engine`을 재사용한다(신규 seam 0).
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(backend_edge 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def _load_known_norm_ids(self) -> set[str]:
        """`achievement_standard` 전량을 단일 조회해 알려진 `norm_id` 집합 구축(N+1 0).

        링크의 실 FK(`norm_id`)가 존재하는 성취기준을 가리키는지 대조하는 데 쓴다(orphan skip).
        성취기준이 먼저 적재돼야(load_standards) 이 집합이 채워지므로, 링크 적재는 성취기준 적재
        다음에 와야 한다. backend_edge의 `_load_code_to_uuid` 짝이되, 링크는 해석할 UUID가 없어
        *값 맵*이 아니라 *존재 집합*만 만든다(concept_code는 느슨참조라 대조 불요).
        """
        from sqlalchemy import select

        from whymath_backend.db.models.achievement_standard import (
            AchievementStandard as AchievementStandardORM,
        )

        stmt = select(AchievementStandardORM.norm_id)
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return {row.norm_id for row in rows}

    def populate(self, links: Sequence[ConceptStandardLink]) -> tuple[int, list[str]]:
        """링크 schema 모델들을 `concept_standard_link`에 멱등 upsert (orphan skip·link_id 보존).

        ① 알려진 norm_id 집합 단일 구축 → ② 각 링크의 실 FK `norm_id`가 그 집합에 없으면 orphan
        skip(조용한 누락 금지·메시지 수집) → ③ `ON CONFLICT(concept_code, norm_id, link_type) DO
        UPDATE`로 `note`만 갱신(link_id·created 미-SET·보존). `concept_code`는 느슨참조라 그대로
        바인딩한다(해석 없음). 입력 내 의미키 중복은 *마지막 우선* dedup한다(단일 배치 ON CONFLICT
        중복행 오류 방지·성취기준 적재 dedup과 동형). 반환: (적재 행 수, orphan skip 메시지 목록).
        입력이 비면 (0, []).
        """
        if not links:
            return 0, []

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept_standard_link import (
            ConceptStandardLink as ConceptStandardLinkORM,
        )

        # 의미키 (concept_code, norm_id, link_type) 기준 dedup(마지막 우선) — 단일 배치 ON CONFLICT
        # 중복행 오류 방지. backend의 link_type은 Literal이라 항상 한글 정본 문자열이다.
        by_key: dict[tuple[str, str, str], ConceptStandardLink] = {
            (link.concept_code, link.norm_id, link.link_type): link for link in links
        }
        deduped = list(by_key.values())

        known_norm_ids = self._load_known_norm_ids()
        loaded = 0
        skipped: list[str] = []
        with self._get_engine().begin() as conn:
            for link in deduped:
                if link.norm_id not in known_norm_ids:
                    # orphan — 적재 성취기준 집합에 없는 norm_id(실 FK 위반 방지·정직).
                    skipped.append(
                        f"orphan link skip: concept_code={link.concept_code} "
                        f"norm_id={link.norm_id}(미적재) link_type={link.link_type}"
                    )
                    continue
                stmt = pg_insert(ConceptStandardLinkORM).values(
                    concept_code=link.concept_code,
                    norm_id=link.norm_id,
                    link_type=link.link_type,
                    note=link.note,
                )
                # 의미 유일키 충돌 시 note만 갱신 — link_id(PK)는 SET 안 함(보존·재적재가 PK 불변).
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        ConceptStandardLinkORM.concept_code,
                        ConceptStandardLinkORM.norm_id,
                        ConceptStandardLinkORM.link_type,
                    ],
                    set_={"note": stmt.excluded.note},
                )
                conn.execute(stmt)
                loaded += 1
        return loaded, skipped


__all__ = [
    "AchievementStandardStore",
    "ConceptStandardLinkStore",
    "load_links",
    "load_standards",
]
