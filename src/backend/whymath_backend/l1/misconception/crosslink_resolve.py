"""오개념 crosswalk read-time 해석 — kebab-id → M-id(들) 조회(학생 데이터 rekey 불필요).

학생 데이터(`misconception_hypothesis`·`evidence_links`)는 kebab-id를 *그대로* 보존한다(rekey·
마이그레이션·미성년 PII 이동 0). 학부모/학생 리포트 등에서 M-id 콘텐츠가 필요하면 *조회 시점*에
이 resolver로 `misconception_crosslink`를 조인해 동적으로 해석한다 — risk_register Q10-⑥
"단일 canonical 정체성"을 rekey 없이 실현(math_dsl_remediation_design.md §1).

순수 read: 어떤 학생 데이터·게이트도 변경하지 않는다. 매핑이 없으면 `[]`(graceful — 골격만 깔린
초기엔 전부 빈 결과·정직). `MisconceptionCatalogStore` 등과 동일 sync 엔진 좌석(신규 seam 0)이라
fake 엔진 주입으로 단위테스트 가능하다. async API 결선은 후속(본 슬라이스 비목표).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class MisconceptionCrosslinkResolver:
    """kebab-id → M-id 해석기 — `misconception_crosslink` 조회(read-only·sync).

    `resolve`는 한 kebab-id에 매핑된 M-id 목록을, `resolve_many`는 여러 kebab-id의 매핑을 한 번에
    반환한다(N+1 회피). `min_confidence`를 주면 그 이상만(NULL confidence는 제외 — 보수). 결과는
    confidence 내림차순(NULL 마지막)·mis_id 보조정렬로 결정론적이다.
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
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def resolve(self, kebab_id: str, *, min_confidence: float | None = None) -> list[str]:
        """한 kebab-id에 매핑된 M-id 목록(매핑 없으면 []). min_confidence 미만·NULL은 제외(보수)."""
        return self.resolve_many([kebab_id], min_confidence=min_confidence).get(kebab_id, [])

    def resolve_many(
        self,
        kebab_ids: Sequence[str],
        *,
        min_confidence: float | None = None,
    ) -> dict[str, list[str]]:
        """여러 kebab-id → {kebab_id: [mis_id...]} (단일 조회·N+1 0). 없는 kebab은 키 부재."""
        if not kebab_ids:
            return {}

        import sqlalchemy as sa

        from whymath_backend.db.models.misconception_crosslink import MisconceptionCrosslink

        stmt = sa.select(
            MisconceptionCrosslink.kebab_id,
            MisconceptionCrosslink.mis_id,
            MisconceptionCrosslink.confidence,
        ).where(MisconceptionCrosslink.kebab_id.in_(list(dict.fromkeys(kebab_ids))))
        if min_confidence is not None:
            # NULL confidence는 미만 취급(제외) — 검수 신뢰도 없는 매핑은 임계 적용 시 배제(보수).
            stmt = stmt.where(MisconceptionCrosslink.confidence >= min_confidence)

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()

        # confidence 내림차순(NULL 마지막)·mis_id 보조정렬로 결정론적 순서.
        def _sort_key(row: sa.Row) -> tuple[int, float, str]:  # type: ignore[type-arg]
            conf = row.confidence
            has_conf = 0 if conf is not None else 1  # 값 있는 것 먼저
            return (has_conf, -float(conf) if conf is not None else 0.0, row.mis_id)

        result: dict[str, list[str]] = {}
        for row in sorted(rows, key=_sort_key):
            result.setdefault(row.kebab_id, []).append(row.mis_id)
        return result


__all__ = ["MisconceptionCrosslinkResolver"]
