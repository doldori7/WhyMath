"""예심 단계 — 콘텐츠 슬롯 기계 점수(0..3) + `DRAFT → PRESCREENED` 승격.

PED-01 파일럿 E2E의 두 번째 중간 단계다. 생성된 슬롯 payload를 결정론 루브릭으로 0~3점 매긴다.
`v_prescreen_calibration` 뷰가 **`prescreen_score >= 2`를 "통과(passed)"**로 정의하므로, 루브릭도
정상 슬롯이 2점 이상, 결함 슬롯이 2점 미만이 되도록 설계한다(변별력).

fail-closed: 숫자형인데 SymPy 검증이 실패(답 틀림)한 슬롯은 즉시 0점(예심 탈락). 상태 승격은
오직 `DRAFT` 행만 대상으로 하며(WHERE 가드), 이미 검수된 행은 재예심하지 않는다.

7계층: L3 콘텐츠 검증. 순수 루브릭 함수 + sync 엔진 재사용(`ContentSlotStore` 미러).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.pedagogy_dsl import PedagogyContentSlot
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# `v_prescreen_calibration`이 통과로 보는 임계(마이그레이션 뷰 정의와 동결 정합).
PRESCREEN_PASS_THRESHOLD = 2


# ──────────────────────────────────────────────────────────────────────────
# 루브릭 (0..3 결정론)
# ──────────────────────────────────────────────────────────────────────────
def prescreen_slot(
    payload: dict[str, Any],
    *,
    sympy_verified: bool | None,
    tts_safe: bool | None,
) -> int:
    """슬롯 1개 예심 점수(0..3) — 결정론 루브릭.

    - 숫자형인데 `sympy_verified is False`(답 틀림) → 즉시 0(fail-closed, 수학 결함은 하드 탈락).
    - 그 외: ①TTS 안전 ②구조 태그 존재 ③본문+유형 명시 — 각 +1.

    정상 슬롯(숫자형 검증 통과·개념형 무관)은 3점, 구조 결함(빈 본문·태그 없음)은 2점 미만이 된다.
    개념형(`sympy_verified is None`)은 수치 결함이 없어 구조 3요건만으로 3점에 도달한다.
    """
    if sympy_verified is False:
        return 0
    score = 0
    if tts_safe:
        score += 1
    if payload.get("structure_tags"):
        score += 1
    if payload.get("body") and payload.get("reasoning_type"):
        score += 1
    return min(score, 3)


def prescreen_rows(rows: Sequence[dict[str, Any]]) -> list[tuple[str, int]]:
    """생성 슬롯 행들 → `(id, prescreen_score)` 리스트(각 행에 `prescreen_slot` 적용).

    생성 단계가 낸 in-memory 행(payload·sympy_verified·tts_safe 보유)을 그대로 채점한다 —
    같은 파이프라인 내 소비라 DB 재조회 없이 결정론적으로 점수를 낸다.
    """
    return [
        (
            str(row["id"]),
            prescreen_slot(
                row["payload"],
                sympy_verified=row.get("sympy_verified"),
                tts_safe=row.get("tts_safe"),
            ),
        )
        for row in rows
    ]


# ──────────────────────────────────────────────────────────────────────────
# 시더: PrescreenStore (DRAFT → PRESCREENED, WHERE 가드)
# ──────────────────────────────────────────────────────────────────────────
class PrescreenStore:
    """예심 점수 → `pedagogy_content_slot` 갱신(`DRAFT`만 `PRESCREENED`로 승격).

    각 슬롯을 `id` 일치 + `status='DRAFT'` 조건에서만 UPDATE한다 — 이미 검수·반려된 행을 되돌리지
    않는다(fail-closed·멱등적 전이). sync 엔진은 슬3 `_build_sync_engine` 재사용.
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

    def apply(self, scored: Sequence[tuple[str, int]]) -> int:
        """`(id, score)` 리스트를 DRAFT→PRESCREENED로 갱신. 반환=갱신 시도 행 수.

        각 UPDATE는 `id == :id AND status == 'DRAFT'` 가드를 건다(다른 상태는 무시).
        """
        from sqlalchemy import update

        with self._get_engine().begin() as conn:
            for slot_id, score in scored:
                stmt = (
                    update(PedagogyContentSlot)
                    .where(
                        PedagogyContentSlot.id == slot_id,
                        PedagogyContentSlot.status == "DRAFT",
                    )
                    .values(prescreen_score=score, status="PRESCREENED")
                )
                conn.execute(stmt)
        return len(scored)


__all__ = [
    "PRESCREEN_PASS_THRESHOLD",
    "prescreen_slot",
    "prescreen_rows",
    "PrescreenStore",
]
