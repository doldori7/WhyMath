"""런타임 배선 — 문제의 개념 코드(concept_code) → 지식 유형(k_type) 해석.

PED-01 파일럿 E2E의 런타임 단계 진입점이다. 튜터링 턴에서 다루는 문제의 *개념 노드 코드*로
`learning_objective`를 조회해 그 목표의 `k_type`을 얻는다. 소비처는 `get_pack(k_type)`로 교수법
팩을 뽑아 `PolyaCoach.decide(pack=...)`에 주입한다(그 훅·플래그 게이트는 PED-02에서 이미 착지).

────────────────────────────────────────────────────────────────────────────
경계 (deferred GA)
────────────────────────────────────────────────────────────────────────────
이 슬라이스는 *해석기*만 낸다. `api/coach.py` 세션 핸들러가 매 턴 이 해석을 호출해 팩을 주입하고
`pedagogy_pack_prompt_enabled`를 기본 ON으로 뒤집는 건 **별도 GA 커밋**이다(카나리 규율·config
docstring). 그 flip 전까지 런타임 발문은 무변경이며, E2E가 `resolve→get_pack→decide(pack=)`
사슬을 플래그 강제 ON으로 증명한다.

7계층: L4 교수학. `learning_objective`(기존 컬럼·무마이그) 조회·sync 엔진 재사용.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.pedagogy_dsl import LearningObjective
from whymath_backend.l1.embedding_primitives import build_sync_engine
from whymath_backend.schema.enums import KnowledgeType

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.sql import Select


def k_type_query(concept_code: str) -> Select[tuple[KnowledgeType]]:
    """개념 코드로 k_type 1건을 뽑는 SELECT — `:code = ANY(concept_nodes)`.

    같은 개념을 여러 목표가 다룰 수 있으므로 `k_type_verified`가 True인 목표를 우선한다(사람/기계
    확정 유형 우선·결정론 tie-break). 기존 컬럼만 쓰므로 마이그레이션이 없다.
    """
    from sqlalchemy import any_, literal, select

    # `:code = ANY(concept_nodes)` — literal+any_ 형태(ARRAY 멤버십·mypy 정합).
    return (
        select(LearningObjective.k_type)
        .where(literal(concept_code) == any_(LearningObjective.concept_nodes))
        .order_by(LearningObjective.k_type_verified.desc())
        .limit(1)
    )


class KTypeResolver:
    """개념 코드 → k_type 해석기(sync 엔진·`ContentSlotStore` 미러).

    `resolve`는 매칭 목표가 없으면 None(fail-soft — 소비처가 팩 미주입=발문 무변경으로 폴백).
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
            self._engine = build_sync_engine(self._resolved_settings)
        return self._engine

    def resolve(self, concept_code: str) -> str | None:
        """개념 코드 → k_type 문자열(예: 'CONCEPT'). 매칭 없으면 None.

        native enum 컬럼이 KnowledgeType/str 어느 쪽으로 오든 `get_pack` 키(문자열)로 정규화한다.
        """
        with self._get_engine().begin() as conn:
            row = conn.execute(k_type_query(concept_code)).first()
        if row is None:
            return None
        value = row[0]
        # KnowledgeType(.value 보유)·평문 str 모두 문자열 키로 접는다.
        return str(getattr(value, "value", value))


__all__ = ["k_type_query", "KTypeResolver"]
