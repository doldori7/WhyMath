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
concept_src_id → concept_code 해석 (P2b — backend_edge resolve-via-map 템플릿 답습)
────────────────────────────────────────────────────────────────────────────
**P2b 재ID 전파의 핵심 변경.** 코퍼스 링크의 `concept_src_id`는 *원천 src_id*(예 'N1'·'HK01')다.
재ID(2026-06-16) 후 backend `concept`의 식별자는 `code`(`{TRACK}-{AREA}-{NNN}`·예 'HIGH-CALC-001')
이고, src_id는 `concept.source_id` 컬럼에 보존된다. 따라서 링크는 `concept_src_id`(src_id)를
backend `concept`의 새 `code`로 **해석해서** `concept_code`에 저장해야 한다 — 그래야 링크가 재ID된
개념 식별자 공간과 정합한다.

해석 방식은 **backend_edge의 resolve-via-map을 그대로 답습**한다(P2b 명세 지정 템플릿): backend
`concept` 전량을 *단일 조회*(`SELECT concept.source_id, concept.code`)로 `{source_id: code}` 맵을
만들고(N+1 0), 각 링크의 `concept_src_id`를 그 맵으로 새 `code`로 바꾼다. backend_edge가
`{code: uuid}`로 UC→UUID FK를 푼 것과 *동형*이되, 여기선 `{source_id: code}`로 src_id→새 code를
푼다(둘 다 단일 SELECT·N+1 0·resolve-via-map). 해석 후 저장하는 `concept_code`는 여전히 **FK가
아니라 느슨참조**다(ORM docstring: 개념 식별자 공간 진화 중) — 맵으로 *값을 새 code로 정규화*할
뿐 DB FK를 거는 것은 아니다.

이전(P1)엔 `concept_src_id`를 *그대로* `concept_code`에 넣는 store-direct였으나, 재ID로 src_id와
code가 *달라졌으므로* 더는 그대로 둘 수 없다 — 반드시 해석한다. *조용한 누락 금지* 원칙은 동일:
backend_edge가 맵에 없는 UC를 orphan skip·보고하듯, 이 로더는 ① 맵에 없는 src_id(unresolved 개념
참조)와 ② 적재 성취기준 집합에 없는 `norm_id`(unresolved 성취기준 참조·실 FK) **양쪽**을 orphan으로
skip·보고한다(개념 해석 실패·FK 위반 둘 다 차단).

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

    seam: 코퍼스는 개념 소스 식별자를 `concept_src_id`(src_id) 키로 두지만 backend schema는
    `concept_code`다. 여기서 `concept_src_id`(src_id)를 꺼내 `concept_code` 슬롯에 옮긴다 — 단 이
    값은 *아직 해석 전 src_id*다(backend_edge의 record.src_code/dst_code가 *해석 전 lookup 키*인
    것과 동형). 실제 새 `code`로의 해석은 `store.populate`가 `{source_id: code}` 맵으로 수행한다
    (모듈 docstring 핵심 변경 — P2b resolve-via-map). schema는 extra=forbid라 `concept_src_id` 키가
    남으면 거부되므로 pop으로 옮긴다(`concept_code` 필드 검증은 src_id 문자열에도 통과 — 느슨참조라
    형식 자유). 나머지(`norm_id`·`link_type`·`note`)는 동명 직결이며 schema가 재검증한다.
    """
    data = dict(row)  # 원본 불변(호출자 dict 보호)
    # 코퍼스 `concept_src_id`(src_id) → schema `concept_code` 슬롯(해석 전 lookup 키). schema는
    # extra=forbid라 `concept_src_id`를 남기면 거부되므로 pop으로 옮긴다. 새 code 해석은 populate.
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
    `schema.ConceptStandardLink`로 빌드(코퍼스 `concept_src_id`(src_id)→`concept_code` 슬롯)한 뒤
    의미 유일키 `(concept_code, norm_id, link_type)` 충돌 멱등 upsert한다. **P2b 변경**: backend
    `concept`을 단일 조회해 `{source_id: code}` 맵을 만들고 각 링크의 src_id를 새 `code`로 *해석*해
    저장한다(backend_edge가 UC→UUID로 해석한 것과 동형 — 모듈 docstring·해석 후에도 concept_code는
    FK 아닌 느슨참조). 맵에 없는 src_id(unresolved 개념)와 적재 성취기준 집합에 없는 `norm_id`(실
    FK)는 **둘 다** orphan으로 skip한다(FK 위반·해석 실패 방지·조용한 누락 금지 — backend_edge
    orphan skip 미러). 빈 컬렉션은 0.

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

    `BackendEdgeStore`(개념 엣지)의 *링크* 짝이다(같은 sync 좌석·멱등 규약·orphan skip). **P2b
    변경 — 이제 backend_edge resolve-via-map을 그대로 답습한다**: backend_edge가 개념 양끝(UC)을
    `{code: uuid}` 맵으로 UUID FK로 해석했듯, 이 store는 링크의 `concept_code` 슬롯에 든 *src_id*를
    `{source_id: code}` 맵으로 backend `concept`의 새 `code`로 *해석*해 저장한다(재ID 정합). 해석
    후 `concept_code`는 여전히 **FK가 아니라 느슨참조**다(맵으로 값을 새 code로 정규화·DB FK 아님).
    `populate`는 ① `SELECT concept.source_id, concept.code` 단일 조회로 `{source_id: code}` 맵을,
    ② `SELECT achievement_standard.norm_id` 단일 조회로 알려진 norm_id 집합을 만든 뒤(둘 다 N+1 0),
    각 링크에 대해 (a) src_id를 맵으로 새 code로 해석(맵에 없으면 orphan skip)하고 (b) norm_id가
    집합에 있는지 확인(없으면 orphan skip)한 다음 `INSERT ... ON CONFLICT(concept_code, norm_id,
    link_type) DO UPDATE`로 적재한다 — `note`만 갱신하고 **link_id(UUID PK)는 SET하지 않아 보존**
    한다(backend_edge가 edge_id를 보존하듯). 두 orphan(개념 해석 실패·성취기준 FK 위반) 모두
    메시지로 보고한다(조용한 누락 금지). sync 엔진은 슬3 `_build_sync_engine`을 재사용한다(seam 0).
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

    def _load_source_id_to_code(self) -> dict[str, str]:
        """backend `concept` 전량을 단일 조회해 `{source_id: code}` 맵 구축(N+1 0·P2b).

        링크의 src_id(`concept_src_id`)를 재ID된 새 `code`로 해석하는 데 쓴다 — backend_edge의
        `_load_code_to_uuid`(`{code: uuid}`)와 *동형*이되, 여기선 src_id→새 code를 푼다. 개념이 먼저
        적재돼야(backend_concept) source_id 컬럼이 채워지므로, 링크 적재는 개념 적재 다음에 와야
        한다. `source_id`가 NULL인 개념(옛 데이터·재ID 전)은 맵 키가 될 수 없어 제외하고(None 키
        방지), code가 NULL일 수 없으므로(NOT NULL) 값은 항상 유효하다. 같은 source_id가 둘 이상의
        code에 달리면(이론상 src_id는 개념당 유일) 나중 행이 이긴다(dict 갱신 — 정상 데이터엔 없음).
        """
        from sqlalchemy import select

        from whymath_backend.db.models.concept import Concept

        stmt = select(Concept.source_id, Concept.code)
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        # source_id가 NULL인 행은 키로 쓸 수 없어 제외(옛 데이터·재ID 전 개념).
        return {row.source_id: row.code for row in rows if row.source_id is not None}

    def _load_known_norm_ids(self) -> set[str]:
        """`achievement_standard` 전량을 단일 조회해 알려진 `norm_id` 집합 구축(N+1 0).

        링크의 실 FK(`norm_id`)가 존재하는 성취기준을 가리키는지 대조하는 데 쓴다(orphan skip).
        성취기준이 먼저 적재돼야(load_standards) 이 집합이 채워지므로, 링크 적재는 성취기준 적재
        다음에 와야 한다. backend_edge의 `_load_code_to_uuid` 짝이되, norm_id는 *값 맵*이 아니라
        *존재 집합*만 만든다(실 FK라 존재 여부만 대조하면 됨).
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
        """링크 schema 모델들을 `concept_standard_link`에 멱등 upsert (해석·orphan skip·PK 보존).

        ① `{source_id: code}` 맵·알려진 norm_id 집합을 각각 단일 조회로 구축(둘 다 N+1 0) → ② 각
        링크의 `concept_code` 슬롯(=src_id)을 맵으로 새 `code`로 *해석*(맵에 없으면 개념 orphan
        skip) → ③ 해석된 `(code, norm_id, link_type)` 기준 *마지막 우선* dedup(단일 배치 ON CONFLICT
        중복행 오류 방지·해석 후 키로 dedup해야 정합) → ④ 실 FK `norm_id`가 집합에 없으면 성취기준
        orphan skip → ⑤ `ON CONFLICT(concept_code, norm_id, link_type) DO UPDATE`로 `note`만 갱신
        (link_id·created 미-SET·보존)·바인딩하는 `concept_code`는 *해석된 새 code*다. 두 orphan(개념
        해석 실패·성취기준 FK 위반) 모두 메시지로 보고한다(조용한 누락 금지). 반환: (적재 행 수,
        orphan skip 메시지 목록). 입력이 비면 (0, [])."""
        if not links:
            return 0, []

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept_standard_link import (
            ConceptStandardLink as ConceptStandardLinkORM,
        )

        source_id_to_code = self._load_source_id_to_code()
        known_norm_ids = self._load_known_norm_ids()
        skipped: list[str] = []

        # ② src_id → 새 code 해석. 맵에 없는 src_id(unresolved 개념)는 개념 orphan으로 skip.
        #    `link.concept_code` 슬롯엔 _link_from_row가 넣은 *해석 전 src_id*가 들어 있다.
        resolved: list[tuple[str, ConceptStandardLink]] = []
        for link in links:
            src_id = link.concept_code  # 해석 전 src_id(슬롯 재사용 — backend_edge record 키 동형)
            code = source_id_to_code.get(src_id)
            if code is None:
                # 개념 orphan — 맵에 없는 src_id(개념 미적재·재ID 전 데이터·오타). 조용한 누락 금지.
                skipped.append(
                    f"orphan link skip(개념 미해석): concept_src_id={src_id}(맵에 없음) "
                    f"norm_id={link.norm_id} link_type={link.link_type}"
                )
                continue
            resolved.append((code, link))

        # ③ 해석된 의미키 (code, norm_id, link_type) 기준 dedup(마지막 우선) — 단일 배치 ON CONFLICT
        # 중복행 오류 방지. 해석 *후* 키로 dedup해야 같은 새 code로 모인 중복을 올바로 접는다.
        # backend의 link_type은 Literal이라 항상 한글 정본 문자열이다.
        by_key: dict[tuple[str, str, str], tuple[str, ConceptStandardLink]] = {
            (code, link.norm_id, link.link_type): (code, link) for code, link in resolved
        }
        deduped = list(by_key.values())

        loaded = 0
        with self._get_engine().begin() as conn:
            for code, link in deduped:
                if link.norm_id not in known_norm_ids:
                    # 성취기준 orphan — 적재 집합에 없는 norm_id(실 FK 위반 방지·정직).
                    skipped.append(
                        f"orphan link skip(성취기준 미적재): concept_code={code} "
                        f"norm_id={link.norm_id}(미적재) link_type={link.link_type}"
                    )
                    continue
                stmt = pg_insert(ConceptStandardLinkORM).values(
                    concept_code=code,  # 해석된 새 code(src_id 아님)
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
