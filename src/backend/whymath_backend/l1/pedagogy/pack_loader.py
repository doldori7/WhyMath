"""교수법 팩 YAML → backend ORM 적재기 (PED-01 후속 — pedagogy_pack 시더).

`l1/misconception/catalog_loader.py`(오개념 카탈로그)·`l1/standards/standard_loader.py`(성취기준)의
*교수법 팩* 짝이다. ORM(`db/models/pedagogy_dsl.py::PedagogyPack`)·enum(`schema/enums.py::
KnowledgeType`)·마이그레이션은 PED-01(교수법 DSL v2 이관)이 이미 세웠고, 이 모듈이 그 *시더*를
놓는다 — `data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형 팩)을 backend 영속 `pedagogy_pack`
테이블로 멱등 적재한다. 그러면 런타임(L3 콘텐츠 생성·L4 교수학 엔진)이 유형별 교수법 팩을 조회할
수 있다(소비는 이 좌석을 호출하되 여기서 구현하지 않는다 — 후속·역방향 의존 금지).

────────────────────────────────────────────────────────────────────────────
입력 포맷 (팩당 1 YAML 파일 — Collection JSON 아님)
────────────────────────────────────────────────────────────────────────────
성취기준·오개념 로더는 *단일 Collection JSON*(표지 메타 + 배열)을 받았지만, 교수법 팩은
사람이 저작하는 *데이터*라 **팩당 1 YAML 파일**(k_type 하나)로 둔다(`_provenance.json`은 표지
메타로 별도). 따라서 이 로더의 `_as_collection`은 성취기준 로더와 달리:
  - 디렉터리 Path → `*.yaml` glob(정렬)로 각 파일을 `yaml.safe_load`해 팩 dict 리스트로,
  - 단일 파일 Path → 그 YAML 하나를 로드해 1원소 리스트로,
  - 메모리 dict → 1원소 리스트로(테스트·in-memory 단일 팩),
  - 메모리 list → 이미 팩 dict 리스트로 보고 그대로(테스트·in-memory 다중 팩).
`yaml.safe_load`만 쓴다(임의 객체 역직렬화 금지 — 안전 로더). 각 팩 dict는 schema
`PedagogyPack.model_validate`가 형식·교수학 불변식으로 게이트한다(extra=forbid·발문 lint).

────────────────────────────────────────────────────────────────────────────
멱등 (PG ON CONFLICT — misconception/standard 로더 규약)
────────────────────────────────────────────────────────────────────────────
PK `k_type`(native enum) 충돌 시 `INSERT ... ON CONFLICT(k_type) DO UPDATE`로 나머지 컬럼을
갱신한다. PK는 SET하지 않아 보존한다(멱등). 입력 내 k_type 중복은 *마지막 우선* dedup한다
(단일 배치 ON CONFLICT가 같은 행을 두 번 건드리는 오류 방지 — standard_loader 선례).
rename·해석 seam은 없다 — schema 필드명 = ORM 컬럼명이라 `model_dump()`를 ORM 컬럼 키로
직접 바인딩한다(misconception 로더가 rename seam 0였던 것과 동형). `k_type`은
`use_enum_values=True`로 문자열 값이 되어 PG native enum 컬럼에 그대로 실린다.

sync 엔진은 슬3 `_build_sync_engine`을 재사용한다(신규 seam 0 — misconception/standard 로더와
동일 좌석 규약). 자격은 env(`Settings.sync_database_url`)·하드코딩 0.

7계층: L1 데이터 기반의 *런타임 엔티티 적재*. ORM 이름 충돌(schema `PedagogyPack` vs ORM
`PedagogyPack`)은 ORM을 `PedagogyPackORM` alias로 import해 피한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from whymath_backend.config import Settings, get_settings

# ORM·schema 이름 충돌 주의 — ORM은 alias(PedagogyPackORM). schema는 PedagogyPack.
from whymath_backend.db.models.pedagogy_dsl import PedagogyPack as PedagogyPackORM

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — misconception/standard 로더와 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.pedagogy_pack import PedagogyPack

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# ──────────────────────────────────────────────────────────────────────────
# 입력 정규화 (dict | Path(디렉터리·파일) | list → 팩 dict 리스트)
# ──────────────────────────────────────────────────────────────────────────
def _as_collection(
    source: dict[str, Any] | Path | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """팩 입력을 raw 팩 dict 리스트로 정규화 — 디렉터리·단일 파일·메모리 dict/list 모두 수용.

    성취기준 로더의 `_as_collection`(단일 Collection dict 반환)과 달리, 교수법 팩은 *팩당 1 YAML
    파일*이라 이 함수는 **팩 dict 리스트**를 낸다:
      - `Path`이고 디렉터리면 → `*.yaml`을 정렬 glob해 각각 `yaml.safe_load`(결정적 순서).
      - `Path`이고 파일이면 → 그 YAML 하나를 로드해 1원소 리스트.
      - `list`면 → 이미 팩 dict 리스트로 보고 그대로(테스트·in-memory 다중 팩).
      - `dict`면 → 단일 팩으로 보고 1원소 리스트(테스트·in-memory 단일 팩).
    `yaml.safe_load`만 쓴다(안전 로더). 그 외 타입은 거부한다(정직).

    Raises:
        FileNotFoundError: Path가 가리키는 파일·디렉터리 부재(read_text/glob).
        TypeError: dict·Path·list가 아닌 입력.
    """
    if isinstance(source, list):
        return source
    if isinstance(source, dict):
        return [source]
    if isinstance(source, Path):
        if source.is_dir():
            # 디렉터리 — *.yaml만 정렬 glob(_provenance.json은 .yaml 아니라 제외·결정적 순서).
            packs: list[dict[str, Any]] = []
            for path in sorted(source.glob("*.yaml")):
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
                packs.append(loaded)
            return packs
        # 단일 파일 — YAML 하나를 로드해 1원소 리스트.
        single: dict[str, Any] = yaml.safe_load(source.read_text(encoding="utf-8"))
        return [single]
    raise TypeError(f"팩 입력은 dict·Path·list여야 합니다: {type(source).__name__}")


# ──────────────────────────────────────────────────────────────────────────
# 팩 적재 (YAML → pedagogy_pack·k_type ON CONFLICT)
# ──────────────────────────────────────────────────────────────────────────
def load_packs(
    session: dict[str, Any] | Path | None,
    source: dict[str, Any] | Path | list[dict[str, Any]],
    *,
    store: PedagogyPackStore | None = None,
) -> int:
    """교수법 팩 YAML(디렉터리·파일·메모리)을 `pedagogy_pack`에 멱등 upsert. 반환=적재 행 수.

    `load_misconceptions`(오개념)의 *교수법 팩* 짝이다 — 입력을 `_as_collection`으로 팩 dict
    리스트로 정규화한 뒤 각 dict를 `schema.PedagogyPack.model_validate`로 검증(형식·교수학
    불변식 게이트)하고 `k_type` PK 충돌 멱등 upsert한다. 입력 내 k_type 중복은 store가 *마지막
    우선* dedup한다. 빈 입력은 0(조기 반환).

    `session` 인자는 misconception/standard 로더의 store 좌석 규약 호환을 위한 *자리표시*다(이
    적재기는 sync 엔진으로 동작하므로 ORM async Session을 쓰지 않는다 — None 허용). store
    미주입 시 슬3 sync 엔진 재사용 `PedagogyPackStore`를 만든다.

    Raises:
        FileNotFoundError: source가 Path인데 파일·디렉터리 부재.
        pydantic.ValidationError: 팩 dict가 schema 형식·교수학 불변식을 위반(게이트는 schema 몫).
    """
    del session  # async Session 미사용(sync 엔진 좌석) — 호환 자리표시.
    raw_packs = _as_collection(source)
    records = [PedagogyPack.model_validate(raw) for raw in raw_packs]
    if not records:
        return 0
    pack_store = store if store is not None else PedagogyPackStore()
    return pack_store.populate(records)


class PedagogyPackStore:
    """교수법 팩 YAML → `pedagogy_pack` 적재기 — k_type PK 멱등 upsert(sync).

    `MisconceptionCatalogStore`(오개념)의 *교수법 팩* 짝이다(같은 sync 좌석·멱등 규약). `populate`는
    각 팩을 `INSERT ... ON CONFLICT(k_type) DO UPDATE`로 멱등 적재한다 — 같은 k_type 재적재는
    나머지 컬럼을 갱신한다(k_type은 native enum PK라 server_default 없음·시더가 채움). 입력 내
    k_type 중복은 적재 전 *마지막 우선* dedup한다(단일 배치 ON CONFLICT가 같은 행을 두 번 건드리는
    오류 방지). sync 엔진은 슬3 `_build_sync_engine`을 재사용해 지연 생성·캐시한다(신규 seam 0).

    본문 적재(와이매스 자체 저작): `socratic_prompt` 등 팩 데이터는 자체 저작이라 보유가 허용된다
    (redaction 불요 — ORM 모듈 docstring 법적 메모).
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(misconception 로더 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def populate(self, records: Sequence[PedagogyPack]) -> int:
        """교수법 팩 schema 모델들을 `pedagogy_pack`에 멱등 upsert. 반환=적재 행 수(dedup 후).

        ① k_type PK 기준 *마지막 우선* dedup(단일 배치 ON CONFLICT 중복행 오류 방지) → ② 각 행을
        `ON CONFLICT(k_type) DO UPDATE`로 적재(나머지 컬럼 갱신·PK는 SET 안 함·보존). 입력 빈 0.
        컬럼 값은 검증된 schema 모델의 `model_dump()`에서 ORM 컬럼키(mapper 도출)만 추려 바인딩한다
        (schema 필드명=ORM 컬럼명). `k_type`은 use_enum_values=True라 문자열 값이고,
        `required_slots`는 `list[{type,count}]` dict 리스트로 뽑혀 JSONB에 실린다. 반환은 적재
        시도 행 수(dedup 후 길이)다.
        """
        if not records:
            return 0

        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # k_type PK 기준 dedup(마지막 우선) — 단일 배치 INSERT의 ON CONFLICT 중복행 오류 방지.
        # use_enum_values=True라 r.k_type은 문자열 값("CONCEPT")이라 dict 키로 안전하다.
        by_k_type: dict[str, PedagogyPack] = {r.k_type: r for r in records}
        deduped = list(by_k_type.values())

        # PK k_type을 제외한 갱신 컬럼 집합(ON CONFLICT DO UPDATE SET) — mapper 컬럼키에서 도출.
        all_keys = {col.key for col in sa.inspect(PedagogyPackORM).mapper.column_attrs}
        update_keys = all_keys - {"k_type"}

        with self._get_engine().begin() as conn:
            for record in deduped:
                # 검증된 schema에서 ORM 컬럼 값만 추린다(schema 필드명=ORM 컬럼명·rename 0).
                payload = record.model_dump()
                stmt = pg_insert(PedagogyPackORM).values(**{k: payload[k] for k in all_keys})
                # k_type(PK) 충돌 시 나머지 컬럼 갱신 — PK는 SET하지 않아 보존(멱등).
                stmt = stmt.on_conflict_do_update(
                    index_elements=[PedagogyPackORM.k_type],
                    set_={key: stmt.excluded[key] for key in update_keys},
                )
                conn.execute(stmt)
        return len(deduped)


__all__ = [
    "PedagogyPackStore",
    "load_packs",
]
