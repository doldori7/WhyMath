"""오개념 crosswalk 적재 *통합테스트* — promote→load 실 PG 라운드트립 (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에서 검수 승인분(`promote_approved`)이 실제
`misconception_crosslink` 테이블에 적재되는지(`load_crosslinks`)를 관통 검증한다. 기존
`test_misconception_crosslink.py`는 `_FakeEngine` 주입 hermetic 테스트라 실 `ON CONFLICT`·FK·
CASCADE를 검증하지 못했다 — 이 파일이 그 갭(사람이 `promote --load`로 돌릴 마지막 구간)을 실 PG로
동결한다. PG 미도달 시 graceful skip(`test_misconception_resolve_integration.py` 미러).

검증(계획 §Context):
  ① promote→load 라운드트립 — 승인 행이 실제 적재(kebab/mis 조회·컬럼값·검수 서명 note)
  ② 멱등 재적재 — 같은 payload 2회 → 행수·link_id 불변, confidence/note만 갱신
  ③ FK CASCADE — 카탈로그 mis_id 삭제 시 crosslink 행 삭제
  ④ 승인분만 적재 — pending/rejected/approved 섞인 큐 → approved만 land

적재 키는 실 데이터와 충돌하지 않도록 합성 mis_id(`MITCL...`·`it` 슬러그)를 쓰고, kebab_id는
promote가 요구하는 실 L4 카탈로그 id(느슨참조·FK 아님)를 재사용한다.
"""

from __future__ import annotations

from typing import Any

import pytest
from whymath_backend.config import Settings
from whymath_backend.l1.misconception.catalog_loader import load_misconceptions
from whymath_backend.l1.misconception.crosslink_loader import load_crosslinks
from whymath_backend.l4.misconception.crosslink_review import promote_approved

pytestmark = pytest.mark.integration

# kebab_id — 실 L4 카탈로그(CATALOG_BY_ID) id(느슨참조·FK 아님·promote가 실재 강제).
_KEBAB_A = "distribution-over-power"
_KEBAB_B = "sign-flip-in-inequality"
# mis_id — 합성(it 슬러그·실 데이터 비충돌). misconception_catalog에 먼저 시딩(FK).
_MIS_A = "MITCL01"
_MIS_B = "MITCL02"
_MIS_PENDING = "MITCL08"
_MIS_REJECTED = "MITCL09"
_ALL_MIS = [_MIS_A, _MIS_B, _MIS_PENDING, _MIS_REJECTED]


# ── 실 PG 좌석(정본 파일 미러) ────────────────────────────────────────────
def _sync_engine() -> Any:
    """통합테스트용 sync(psycopg) 엔진 — 적재·정리·조회용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + crosswalk·카탈로그 테이블 존재(마이그레이션 적용) 여부."""
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
    """적재 행 정리 — FK 역순(crosslink 먼저·그다음 catalog). 실 데이터 비충돌 키 스코프."""
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


# ── 시드·조회 헬퍼 ─────────────────────────────────────────────────────────
def _mis_row(mis_id: str) -> dict[str, Any]:
    """최소 코퍼스 오개념 dict(FK 시딩용) — mis_id만 필수(rename 0)."""
    return {
        "mis_id": mis_id,
        "canonical_statement": "통합테스트 오개념.",
        "error_type": "개념오류",
        "difficulty": "중",
    }


def _seed_catalog(*mis_ids: str) -> None:
    """crosslink FK(mis_id→misconception_catalog) 충족용 카탈로그 시딩(멱등 upsert)."""
    load_misconceptions(
        None,
        {"misconceptions": [_mis_row(m) for m in mis_ids]},
        settings=Settings(),
    )


def _queue_row(
    *,
    kebab_id: str,
    mis_id: str,
    link_type: str = "직접매핑",
    confidence: float | None = 0.9,
    status: str = "approved",
    reviewer: str | None = "kiki",
    reviewed_on: str | None = "2026-07-06",
) -> dict[str, Any]:
    """검수 큐 1행 dict — 기본은 승인 행(서명·직접매핑 conf≥0.6, promote 승격 규칙 충족)."""
    return {
        "kebab_id": kebab_id,
        "mis_id": mis_id,
        "link_type": link_type,
        "confidence": confidence,
        "rationale": "통합테스트 근거",
        "status": status,
        "reviewer": reviewer,
        "reviewed_on": reviewed_on,
        "note": None,
    }


def _fetch_crosslinks(mis_ids: list[str]) -> list[dict[str, Any]]:
    """적재된 crosslink 행 조회(mis_id 스코프·정렬) — 단언용."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT link_id, kebab_id, mis_id, link_type, confidence, method, note "
                    "FROM misconception_crosslink WHERE mis_id = ANY(:ids) "
                    "ORDER BY mis_id, link_type"
                ),
                {"ids": mis_ids},
            )
            return [dict(row) for row in result.mappings()]
    finally:
        engine.dispose()


# ── 테스트 ─────────────────────────────────────────────────────────────────
def test_promote_to_load_roundtrip() -> None:
    """승인 큐 → promote_approved → load_crosslinks → 실 PG에 적재·컬럼값·검수 서명 관통."""
    _skip_if_unreachable()
    try:
        _cleanup()
        _seed_catalog(_MIS_A, _MIS_B)
        queue = {
            "review_queue": [
                _queue_row(kebab_id=_KEBAB_A, mis_id=_MIS_A, confidence=0.95),
                _queue_row(kebab_id=_KEBAB_B, mis_id=_MIS_B, confidence=0.9),
            ]
        }
        payload = promote_approved(queue)
        assert len(payload["crosslinks"]) == 2

        loaded = load_crosslinks(None, payload, engine=_sync_engine())
        assert loaded == 2

        rows = _fetch_crosslinks([_MIS_A, _MIS_B])
        assert len(rows) == 2
        by_mis = {r["mis_id"]: r for r in rows}
        assert by_mis[_MIS_A]["kebab_id"] == _KEBAB_A
        assert by_mis[_MIS_A]["link_type"] == "직접매핑"
        assert float(by_mis[_MIS_A]["confidence"]) == pytest.approx(0.95)
        # method="manual"(채택 주체=사람)·note에 검수 서명이 병합됨(promote 규약).
        assert by_mis[_MIS_A]["method"] == "manual"
        assert "검수:kiki 2026-07-06" in by_mis[_MIS_A]["note"]
    finally:
        _cleanup()


def test_idempotent_reload_preserves_link_id_updates_fields() -> None:
    """같은 payload 2회 → 행수·link_id 불변. confidence 변경분만 갱신(멱등 upsert)."""
    _skip_if_unreachable()
    try:
        _cleanup()
        _seed_catalog(_MIS_A)
        queue = {"review_queue": [_queue_row(kebab_id=_KEBAB_A, mis_id=_MIS_A, confidence=0.8)]}
        payload = promote_approved(queue)

        load_crosslinks(None, payload, engine=_sync_engine())
        first = _fetch_crosslinks([_MIS_A])
        assert len(first) == 1
        link_id_1 = first[0]["link_id"]
        assert float(first[0]["confidence"]) == pytest.approx(0.8)

        # 재적재(같은 의미키) — link_id 보존·행수 불변.
        load_crosslinks(None, payload, engine=_sync_engine())
        second = _fetch_crosslinks([_MIS_A])
        assert len(second) == 1
        assert second[0]["link_id"] == link_id_1

        # confidence 변경 payload 재적재 — 의미키 동일이라 upsert가 값만 갱신(link_id 보존).
        changed = {"review_queue": [_queue_row(kebab_id=_KEBAB_A, mis_id=_MIS_A, confidence=0.95)]}
        load_crosslinks(None, promote_approved(changed), engine=_sync_engine())
        third = _fetch_crosslinks([_MIS_A])
        assert len(third) == 1
        assert third[0]["link_id"] == link_id_1
        assert float(third[0]["confidence"]) == pytest.approx(0.95)
    finally:
        _cleanup()


def test_fk_cascade_deletes_crosslink_on_catalog_delete() -> None:
    """카탈로그 mis_id 삭제 → crosslink 행이 FK CASCADE로 함께 삭제."""
    _skip_if_unreachable()
    from sqlalchemy import text

    try:
        _cleanup()
        _seed_catalog(_MIS_A)
        payload = promote_approved({"review_queue": [_queue_row(kebab_id=_KEBAB_A, mis_id=_MIS_A)]})
        load_crosslinks(None, payload, engine=_sync_engine())
        assert len(_fetch_crosslinks([_MIS_A])) == 1

        engine = _sync_engine()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM misconception_catalog WHERE mis_id = :m"),
                    {"m": _MIS_A},
                )
        finally:
            engine.dispose()

        # CASCADE(ondelete="CASCADE")로 crosslink 행이 사라짐.
        assert _fetch_crosslinks([_MIS_A]) == []
    finally:
        _cleanup()


def test_only_approved_rows_loaded() -> None:
    """pending/rejected/approved 섞인 큐 → approved만 실 적재(승인분 필터 관통)."""
    _skip_if_unreachable()
    try:
        _cleanup()
        # approved 대상 mis만 카탈로그 시딩(pending/rejected는 적재되지 않으므로 FK 불요).
        _seed_catalog(_MIS_A)
        queue = {
            "review_queue": [
                _queue_row(kebab_id=_KEBAB_A, mis_id=_MIS_A, status="approved"),
                _queue_row(
                    kebab_id=_KEBAB_B,
                    mis_id=_MIS_PENDING,
                    status="pending",
                    reviewer=None,
                    reviewed_on=None,
                ),
                _queue_row(
                    kebab_id=_KEBAB_B,
                    mis_id=_MIS_REJECTED,
                    status="rejected",
                    reviewer="kiki",
                    reviewed_on="2026-07-06",
                ),
            ]
        }
        payload = promote_approved(queue)
        assert len(payload["crosslinks"]) == 1  # approved 1건만 승격

        loaded = load_crosslinks(None, payload, engine=_sync_engine())
        assert loaded == 1

        assert len(_fetch_crosslinks([_MIS_A])) == 1
        assert _fetch_crosslinks([_MIS_PENDING, _MIS_REJECTED]) == []
    finally:
        _cleanup()
