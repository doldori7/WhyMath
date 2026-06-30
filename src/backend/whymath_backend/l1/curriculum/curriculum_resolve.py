"""교육과정 Overlay read-time 해석 — concept_id → required_depth(자동 커리큘럼 정렬 깊이 축).

`curriculum_entry` Overlay(개념 × 국가 매트릭스 셀)를 *조회 시점*에 읽어, 개념이 그 나라
교육과정에서 요구되는 깊이(`required_depth`)를 동적으로 해석한다. "자동 커리큘럼 정렬 — 표기·
깊이·풀이 스타일 자동 맞춤"(06_application_modes.md §자동정렬-3·PRD)의 **깊이 축**을 런타임에
공급하는 read seam이다. 이 resolver가 곧 `curriculum_entry`의 *첫 런타임 소비처*다 — 적재기(슬라이스
직전)가 채운 Overlay를 L6 학교진도 게이팅(깊이정렬)이 L5 api 경유로 소비한다.

순수 read: 어떤 데이터도 변경하지 않는다. 셀이 없거나 `required_depth`가 비면 그 개념은 결과 dict에
키 부재(graceful — 적재·큐레이션 전 초기엔 전부 빈 결과·정직). `is_present=False` 셀(그 나라에 개념
부재)은 제외한다(요구 깊이 신호가 성립하지 않음). `MisconceptionCrosslinkResolver`·node_projection과
동일 sync 엔진 좌석(신규 seam 0)이라 fake 엔진 주입으로 단위테스트 가능하다.

7계층: L1 데이터 기반의 *read-time 해석*. 소비(L6 깊이정렬·L5 api 주입)는 이 좌석을 호출하되
여기서 구현하지 않는다(역방향 의존 금지).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import RequiredDepth

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# Phase 1 기본 국가(한국). curriculum_entry는 (concept_id × country_code) 셀이라 해석은 국가별이다.
_DEFAULT_COUNTRY: str = "KR"


class CurriculumDepthResolver:
    """concept_id → required_depth 해석기 — `curriculum_entry` 조회(read-only·sync).

    `resolve`는 한 개념의 요구 깊이를, `resolve_many`는 여러 개념의 요구 깊이를 한 번에 반환한다
    (N+1 회피). `is_present=True`이고 `required_depth`가 있는 셀만 본다(부재 개념·깊이 미큐레이션
    셀은 결과에서 제외 → 키 부재로 graceful). `min_confidence`를 주면 그 이상 신뢰도 셀만(NULL은
    제외·보수). 결과 값은 `RequiredDepth` enum이다(PG enum 문자열 → enum 복원).
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

    def resolve(
        self,
        concept_id: str,
        *,
        country_code: str = _DEFAULT_COUNTRY,
        min_confidence: float | None = None,
    ) -> RequiredDepth | None:
        """한 개념의 그 나라 교육과정 요구 깊이(셀·깊이 부재 시 None)."""
        return self.resolve_many(
            [concept_id], country_code=country_code, min_confidence=min_confidence
        ).get(concept_id)

    def resolve_many(
        self,
        concept_ids: Sequence[str],
        *,
        country_code: str = _DEFAULT_COUNTRY,
        min_confidence: float | None = None,
    ) -> dict[str, RequiredDepth]:
        """여러 concept_id → {concept_id: RequiredDepth} (단일 조회·N+1 0).

        `country_code` 고정·`is_present=True`·`required_depth IS NOT NULL` 셀만 본다. 깊이가 없는
        (또는 부재) 개념은 키가 빠진다(graceful). `min_confidence`를 주면 NULL confidence는 제외
        (보수 — 검수 신뢰도 없는 셀은 임계 적용 시 배제). 같은 개념이 한 국가에 1셀이라(복합 유일키)
        중복은 없으나, 방어적으로 입력 중복은 dedup한다.
        """
        if not concept_ids:
            return {}

        import sqlalchemy as sa

        from whymath_backend.db.models.curriculum_entry import CurriculumEntry

        stmt = (
            sa.select(CurriculumEntry.concept_id, CurriculumEntry.required_depth)
            .where(CurriculumEntry.concept_id.in_(list(dict.fromkeys(concept_ids))))
            .where(CurriculumEntry.country_code == country_code)
            .where(CurriculumEntry.is_present.is_(True))
            .where(CurriculumEntry.required_depth.is_not(None))
        )
        if min_confidence is not None:
            # NULL confidence는 미만 취급(제외) — 검수 신뢰도 없는 셀은 임계 적용 시 배제(보수).
            stmt = stmt.where(CurriculumEntry.confidence >= min_confidence)

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()

        result: dict[str, RequiredDepth] = {}
        for row in rows:
            depth = row.required_depth
            # PG enum은 문자열로 올 수 있어 RequiredDepth로 복원(이미 enum이면 그대로).
            result[row.concept_id] = (
                depth if isinstance(depth, RequiredDepth) else RequiredDepth(depth)
            )
        return result


__all__ = ["CurriculumDepthResolver"]
