"""L4 오개념 crosswalk shadow *통합테스트* — 실 resolver 관측 end-to-end (WHYMATH_RUN_INTEGRATION).

`observe_crosslink_shadow`가 **실 PostgreSQL** resolver로 kebab-id를 해석해 record 로거에 emit한
`MisconceptionCrosslinkShadowObservation`이 실 crosslink 행을 정직하게 반영하는지 본다. 이 관측은
Kiki가 `promote --load` 후 돌릴 shadow 측정 윈도가 *실제로 emit하는 레코드*이며(harvest 커버리지
수치의 원천), 기존 shadow 테스트(`test_misconception_crosslink_shadow.py`)는 `_FakeEngine` 주입이라
실 DB 해석 위 관측을 검증하지 못한다. #443(resolver 직접)의 capstone — 실 행 → observe → record
경로를 실 PG로 동결해 shadow 파이프라인(적재→해석→관측→harvest)의 실 PG 커버리지를 완성한다.

기록 캡처는 hermetic 테스트와 동형(record 로거 이름 필터 + `model_validate_json`), 시딩은 #443
loader/resolver 통합 테스트와 동형(catalog·crosslink 로더 재사용). PG 미도달 시 graceful skip.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.misconception.catalog_loader import load_misconceptions
from whymath_backend.l1.misconception.crosslink_loader import load_crosslinks
from whymath_backend.l1.misconception.crosslink_resolve import MisconceptionCrosslinkResolver
from whymath_backend.l4.misconception.crosslink_shadow import (
    MisconceptionCrosslinkShadowObservation,
    observe_crosslink_shadow,
)

pytestmark = pytest.mark.integration

_RECORD_LOGGER = "whymath.l4.misconception.crosslink_shadow.record"

# kebab_id — 느슨참조. it 슬러그로 실 데이터 비충돌.
_KEBAB = "zzit-shadow-a"
_KEBAB_EMPTY = "zzit-shadow-none"
# mis_id — 합성. misconception_catalog에 먼저 시딩(FK).
_MIS_1 = "MITSH01"
_MIS_2 = "MITSH02"
_ALL_MIS = [_MIS_1, _MIS_2]


# ── 실 PG 좌석(#443 통합 테스트 미러) ──────────────────────────────────────
def _sync_engine() -> Any:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT count(*) FROM misconception_crosslink"))
            conn.execute(text("SELECT count(*) FROM misconception_catalog"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()


def _skip_if_unreachable() -> None:
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _cleanup() -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM misconception_crosslink WHERE mis_id = ANY(:ids)"),
                {"ids": _ALL_MIS},
            )
            conn.execute(
                text("DELETE FROM misconception_catalog WHERE mis_id = ANY(:ids)"),
                {"ids": _ALL_MIS},
            )
    finally:
        engine.dispose()


def _seed_catalog(*mis_ids: str) -> None:
    load_misconceptions(
        None,
        {
            "misconceptions": [
                {
                    "mis_id": m,
                    "canonical_statement": "통합테스트 오개념.",
                    "error_type": "개념오류",
                    "difficulty": "중",
                }
                for m in mis_ids
            ]
        },
        settings=Settings(),
    )


def _link(
    *,
    kebab_id: str,
    mis_id: str,
    link_type: str = "직접매핑",
    confidence: float | None = 0.9,
) -> dict[str, Any]:
    return {
        "kebab_id": kebab_id,
        "mis_id": mis_id,
        "link_type": link_type,
        "confidence": confidence,
        "method": "manual",
        "note": "통합테스트 시드",
    }


def _seed_crosslinks(rows: list[dict[str, Any]]) -> None:
    load_crosslinks(None, {"crosslinks": rows}, engine=_sync_engine())


def _observe_record(
    kebab_id: str, caplog: pytest.LogCaptureFixture
) -> MisconceptionCrosslinkShadowObservation:
    """실 resolver로 observe → record 로거 JSON 1건 파싱(hermetic 테스트 캡처 패턴 동형)."""
    resolver = MisconceptionCrosslinkResolver(engine=_sync_engine())
    with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
        observe_crosslink_shadow(kebab_id, resolver=resolver)
    lines = [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]
    assert len(lines) == 1
    return MisconceptionCrosslinkShadowObservation.model_validate_json(lines[0])


# ── 테스트: 실 행 → observe → record ───────────────────────────────────────
def test_observe_records_real_single_direct(caplog: pytest.LogCaptureFixture) -> None:
    """단독 직접매핑 실 행 → record가 mis_ids·canonical·direct_count를 실 DB대로 반영."""
    _skip_if_unreachable()
    try:
        _cleanup()
        _seed_catalog(_MIS_1)
        _seed_crosslinks([_link(kebab_id=_KEBAB, mis_id=_MIS_1, confidence=0.85)])
        obs = _observe_record(_KEBAB, caplog)
        assert obs.kebab_id == _KEBAB
        assert obs.mis_ids == [_MIS_1]
        assert obs.mis_id_count == 1
        assert obs.mapped is True
        assert obs.canonical_mis_id == _MIS_1  # 단독 최대 confidence 직접매핑 선정
        assert obs.canonical_ambiguous is False
        assert obs.direct_count == 1
    finally:
        _cleanup()


def test_observe_records_confidence_desc(caplog: pytest.LogCaptureFixture) -> None:
    """2 직접매핑(0.9/0.7) 실 행 → mis_ids confidence 내림차순·canonical=최고."""
    _skip_if_unreachable()
    try:
        _cleanup()
        _seed_catalog(_MIS_1, _MIS_2)
        _seed_crosslinks(
            [
                _link(kebab_id=_KEBAB, mis_id=_MIS_2, confidence=0.7),
                _link(kebab_id=_KEBAB, mis_id=_MIS_1, confidence=0.9),
            ]
        )
        obs = _observe_record(_KEBAB, caplog)
        assert obs.mis_ids == [_MIS_1, _MIS_2]  # confidence desc
        assert obs.canonical_mis_id == _MIS_1
        assert obs.direct_count == 2
    finally:
        _cleanup()


def test_observe_tie_recorded_ambiguous(caplog: pytest.LogCaptureFixture) -> None:
    """직접매핑 동률 최고 conf 실 행 → canonical 미선정·canonical_ambiguous=True(오귀속 방지)."""
    _skip_if_unreachable()
    try:
        _cleanup()
        _seed_catalog(_MIS_1, _MIS_2)
        _seed_crosslinks(
            [
                _link(kebab_id=_KEBAB, mis_id=_MIS_1, confidence=0.9),
                _link(kebab_id=_KEBAB, mis_id=_MIS_2, confidence=0.9),
            ]
        )
        obs = _observe_record(_KEBAB, caplog)
        assert obs.mis_id_count == 2
        assert obs.canonical_mis_id is None
        assert obs.canonical_ambiguous is True
        assert obs.direct_count == 2
    finally:
        _cleanup()


def test_observe_empty_records_uncovered(caplog: pytest.LogCaptureFixture) -> None:
    """미시드 kebab(빈 실 테이블) → mapped=False·count=0·canonical None(coverage 0 정직 기록)."""
    _skip_if_unreachable()
    try:
        _cleanup()
        obs = _observe_record(_KEBAB_EMPTY, caplog)
        assert obs.mis_ids == []
        assert obs.mis_id_count == 0
        assert obs.mapped is False
        assert obs.canonical_mis_id is None
        assert obs.direct_count == 0
    finally:
        _cleanup()
