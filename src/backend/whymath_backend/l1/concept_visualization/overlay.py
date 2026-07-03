"""시각화 가능성 Overlay 조회·적재 — 개념 code ↔ 시각화 4분류 (플레이북 Part 5).

개념의 시각화 가능성(직접/동적/추상/불가)은 시각화 계층의 판별 정보다(노드 비내장·ADR
concept_node_layering §1). 이 모듈은 두 경로를 제공한다:
  - **런타임 조회**(async): `get_visualizability(session, code)` — L4 시각화 게이트가 개념별
    분류를 조회한다(행 부재=미태깅→None). `api/scene.py`·`api/visualization.py`가 소비.
  - **시드 적재**(sync): `load_concept_visualization_from_json`+`populate_concept_visualization` —
    대표 개념 4분류 코퍼스(`data/corpus/concept_visualization_v1/visualizability.json`)를 code 키로
    멱등 upsert(`ConceptContent` projection 패턴 답습).

7계층: L1 데이터 기반. 정책 판단은 L4(`visualization_policy`)가 하고 이 모듈은 값 보관·조회만 한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.concept_visualization import ConceptVisualization

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — concept_content projection과 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import Visualizability

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


async def get_visualizability(session: AsyncSession, code: str) -> Visualizability | None:
    """개념 code의 시각화 4분류를 Overlay에서 조회(런타임·async). 행 부재→None(미태깅).

    L4 시각화 게이트의 입력원 — 추상·불가면 억지 시각화를 막고, 없으면 기존 동작(하위호환).
    PK(code) 단건 조회라 `session.get`으로 충분하다.
    """
    row = await session.get(ConceptVisualization, code)
    if row is None:
        return None
    # use_enum_values 미적용 ORM이라 이미 Visualizability enum이나, 방어적으로 정규화한다.
    return Visualizability(row.visualizability)


@dataclass(frozen=True, slots=True)
class ConceptVisualizabilityRecord:
    """시드 적재 대상 한 개념의 시각화 4분류(code 키)."""

    code: str
    visualizability: Visualizability


def load_concept_visualization_from_json(path: Path) -> list[ConceptVisualizabilityRecord]:
    """시각화 가능성 코퍼스 `visualizability.json` → 레코드 목록(code 키).

    `entries` 배열의 각 항목에서 `code`·`visualizability`(4분류 한글 값)를 읽는다. 값이 4분류
    어휘가 아니거나 code가 비면 *건너뛴다*(오염 입력 방어·정상 코퍼스에선 미발생).

    Raises:
        FileNotFoundError: visualizability.json 부재.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[ConceptVisualizabilityRecord] = []
    for record in payload.get("entries", []):
        code = record.get("code")
        raw = record.get("visualizability")
        if not code or not isinstance(code, str):
            continue
        try:
            value = Visualizability(raw)
        except ValueError:
            # 4분류 어휘 밖(오염) — 건너뛴다(정직).
            continue
        out.append(ConceptVisualizabilityRecord(code=code.strip(), visualizability=value))
    return out


class ConceptVisualizationStore:
    """시각화 가능성 Overlay 적재 store — code PK 멱등 upsert(`ConceptContentStore` 패턴)."""

    def __init__(self, *, engine: Engine | None = None, settings: Settings | None = None) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: ConceptVisualizabilityRecord) -> None:
        """단일 레코드 upsert(멱등·code PK 충돌 시 visualizability 갱신)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(ConceptVisualization).values(
            code=record.code,
            visualizability=record.visualizability,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ConceptVisualization.code],
            set_={"visualizability": stmt.excluded.visualizability},
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_concept_visualization(
    records: Sequence[ConceptVisualizabilityRecord],
    *,
    settings: Settings | None = None,
    store: ConceptVisualizationStore | None = None,
) -> int:
    """시각화 4분류 레코드를 `concept_visualization`에 멱등 upsert 적재. 반환=적재 행 수."""
    resolved_store = store if store is not None else ConceptVisualizationStore(settings=settings)
    count = 0
    for record in records:
        resolved_store.upsert(record)
        count += 1
    return count
