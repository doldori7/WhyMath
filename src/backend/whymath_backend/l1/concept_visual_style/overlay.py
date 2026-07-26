"""권장 시각화 양식 Overlay 조회·적재 — 개념 code ↔ 권장 시각화 양식 배열 (슬88·ARCH-14 ③).

개념의 권장 시각화 양식(단위원·수형도·수직선 등)은 시각화 계층의 투영 정보다(노드 비내장·ADR
concept_node_layering §1·`concept_visualization` Overlay 선례). ARCH-14 ③으로
`concept.recommended_visual_styles` 컬럼을 이 Overlay로 외부화했다. 이 모듈은 두 경로를 제공한다:
  - **런타임 조회**(async): `get_recommended_visual_styles(session, code)` — API seam(scene.py·
    visualization.py)이 개념별 양식을 조회해 스키마 필드에 주입한다(행 부재=미태깅→`[]`).
  - **시드 적재**(sync): `load_concept_visual_style_from_json`+`populate_concept_visual_style` —
    개념↔양식 코퍼스를 code 키로 멱등 upsert(`ConceptVisualization` Overlay 패턴 답습). 전용
    코퍼스가 아직 없어 로더는 *최소 구현*이다(빈 시드도 정상 — 소비처는 async 리졸버).

7계층: L1 데이터 기반. 힌트 소비는 L3/L4(`l3/visualization`·`l4/scene_generation`)가 스키마 필드로
읽고, 이 모듈은 값 보관·조회만 한다(역방향 의존 없음).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.concept_visual_style import ConceptVisualStyle

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — concept_visualization Overlay와 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import VisualizationStyle

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


async def get_recommended_visual_styles(
    session: AsyncSession, code: str
) -> list[VisualizationStyle]:
    """개념 code의 권장 시각화 양식 배열을 Overlay에서 조회(런타임·async). 행 부재→`[]`(미태깅).

    API seam(`scene.py`·`visualization.py`)이 이 값을 `Concept` 스키마 필드
    `recommended_visual_styles`에 주입해 L3/L4 힌트로 흐르게 한다. 없으면 빈 배열(하위호환·기존
    동작 유지). PK(code) 단건 조회라 `session.get`으로 충분하다.
    """
    row = await session.get(ConceptVisualStyle, code)
    if row is None:
        return []
    # use_enum_values 미적용 ORM이라 이미 VisualizationStyle이나, 방어적으로 정규화한다.
    return [VisualizationStyle(v) for v in row.recommended_styles]


@dataclass(frozen=True, slots=True)
class ConceptVisualStyleRecord:
    """시드 적재 대상 한 개념의 권장 시각화 양식 배열(code 키)."""

    code: str
    recommended_styles: tuple[VisualizationStyle, ...]


def load_concept_visual_style_from_json(path: Path) -> list[ConceptVisualStyleRecord]:
    """권장 시각화 양식 코퍼스 JSON → 레코드 목록(code 키).

    `entries` 배열의 각 항목에서 `code`·`recommended_styles`(양식 어휘 배열)를 읽는다. code가
    비었거나 양식 배열이 통제 어휘 밖이면 *건너뛴다*(오염 입력 방어). 어휘 밖 원소는 개별로
    걸러내고, 유효 원소가 하나도 없으면 그 항목은 건너뛴다.

    Raises:
        FileNotFoundError: 코퍼스 JSON 부재.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[ConceptVisualStyleRecord] = []
    for record in payload.get("entries", []):
        code = record.get("code")
        raw_styles = record.get("recommended_styles")
        if not code or not isinstance(code, str) or not isinstance(raw_styles, list):
            continue
        styles: list[VisualizationStyle] = []
        for raw in raw_styles:
            try:
                styles.append(VisualizationStyle(raw))
            except ValueError:
                # 통제 어휘 밖(오염) — 해당 원소만 건너뛴다(정직).
                continue
        if not styles:
            # 유효 양식이 하나도 없으면 태깅 의미가 없어 건너뛴다.
            continue
        out.append(ConceptVisualStyleRecord(code=code.strip(), recommended_styles=tuple(styles)))
    return out


class ConceptVisualStyleStore:
    """권장 양식 Overlay 적재 store — code PK 멱등 upsert(`ConceptVisualizationStore` 패턴)."""

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

    def upsert(self, record: ConceptVisualStyleRecord) -> None:
        """단일 레코드 upsert(멱등·code PK 충돌 시 recommended_styles 갱신)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(ConceptVisualStyle).values(
            code=record.code,
            recommended_styles=list(record.recommended_styles),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ConceptVisualStyle.code],
            set_={"recommended_styles": stmt.excluded.recommended_styles},
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_concept_visual_style(
    records: Sequence[ConceptVisualStyleRecord],
    *,
    settings: Settings | None = None,
    store: ConceptVisualStyleStore | None = None,
) -> int:
    """권장 양식 레코드를 `concept_visual_style`에 멱등 upsert 적재. 반환=적재 행 수."""
    resolved_store = store if store is not None else ConceptVisualStyleStore(settings=settings)
    count = 0
    for record in records:
        resolved_store.upsert(record)
        count += 1
    return count
