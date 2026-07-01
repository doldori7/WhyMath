"""오개념 crosswalk 로더+resolver *통합테스트* — 실 PG 적재 경로 (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**(`misconception_catalog`·`misconception_crosslink`)에
합성 대표 부분집합을 적재해, ops 프로덕션 적재(`crosslink_populate` → `load_crosslinks`)가 실제로
서는지 본다 — 단위테스트(`test_misconception_crosslink.py`)는 fake 엔진이라 잡지 못하는 *실 FK 제약·
ON CONFLICT 멱등 upsert·resolver SQL*을 검증한다. PG 미도달 시 graceful skip
(`test_misconception_resolve_integration.py` 미러).

검증:
  ① 적재+read-back — 카탈로그(FK 선행) + crosslink 적재 → `resolve`가 매핑 mis_ids를 confidence
     내림차순으로 반환(1:N 포함).
  ② 멱등 — 같은 Collection 재적재 시 행 수 불변(트리플 upsert)·confidence 갱신.
  ③ FK 실 강제 — 카탈로그에 없는 mis_id crosslink 적재 → IntegrityError(실 FK·"카탈로그 선행" 요건).
  ④ resolve_many — 다중 kebab 일괄 해소(N+1 회피)·kebab별 그룹.

적재 키는 실 데이터와 충돌하지 않도록 `it`-슬러그(mis_id `MITXL…`·kebab `zzit-xlink-…`)를 쓴다.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.misconception.catalog_loader import load_misconceptions
from whymath_backend.l1.misconception.crosslink_loader import load_crosslinks
from whymath_backend.l1.misconception.crosslink_resolve import MisconceptionCrosslinkResolver

pytestmark = pytest.mark.integration

# ── 적재 키(it 슬러그·실 데이터 비충돌) ──
_MIS_A = "MITXL01"  # 카탈로그 실재(FK 대상)
_MIS_B = "MITXL02"
_MIS_ABSENT = "MITXL99"  # 카탈로그 미적재(FK 위반 유발)
_KEBAB_A = "zzit-xlink-a"  # 1:N(두 mis_id)
_KEBAB_B = "zzit-xlink-b"  # 1:1
_KEBAB_FK = "zzit-xlink-c"  # FK 위반 시도
_ALL_MIS = [_MIS_A, _MIS_B]
_ALL_KEBAB = [_KEBAB_A, _KEBAB_B, _KEBAB_FK]


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·도달 점검용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + 두 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM misconception_catalog"))
            conn.execute(text("SELECT count(*) FROM misconception_crosslink"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _cleanup() -> None:
    """crosslink(kebab 기준) + 카탈로그(mis_id 기준) 적재 행 정리."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM misconception_crosslink WHERE kebab_id = ANY(:kebabs)"),
                {"kebabs": _ALL_KEBAB},
            )
            conn.execute(
                text("DELETE FROM misconception_catalog WHERE mis_id = ANY(:ids)"),
                {"ids": _ALL_MIS},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _mis_row(mis_id: str) -> dict[str, object]:
    """코퍼스 오개념 dict(rename 0) — FK 대상 카탈로그 행."""
    return {
        "mis_id": mis_id,
        "canonical_statement": "합성 오개념(통합테스트).",
        "student_wrong_thinking": "합성 잘못된 사고.",
        "distractor_rule": "잘못 처리한 결과를 오답 보기로.",
        "error_type": "해석오류",
        "difficulty": "중",
        "correction_point": "합성 교정.",
        "ccss_code": None,
        "concept_src_id": None,
        "standard_code": None,
        "school_level": "고등학교(일반선택)",
        "domain": "삼각함수",
        "subunit": "합성 단원",
        "mapping_confidence": "기준(원본)",
        "mapping_score": 1.0,
        "provenance_note": "통합테스트 합성",
    }


def _catalog(mis_ids: list[str]) -> dict[str, object]:
    return {"count": len(mis_ids), "misconceptions": [_mis_row(m) for m in mis_ids]}


def _xlink(kebab_id: str, mis_id: str, confidence: float) -> dict[str, object]:
    return {
        "kebab_id": kebab_id,
        "mis_id": mis_id,
        "link_type": "직접매핑",
        "confidence": confidence,
        "method": "manual",
        "note": "통합테스트 합성",
    }


def _valid_crosslinks() -> dict[str, object]:
    """유효 매핑 3행 — kebab_a는 1:N(conf 0.7·0.9), kebab_b는 1:1(conf 0.85)."""
    return {
        "crosslinks": [
            _xlink(_KEBAB_A, _MIS_A, 0.7),
            _xlink(_KEBAB_A, _MIS_B, 0.9),
            _xlink(_KEBAB_B, _MIS_A, 0.85),
        ]
    }


def _seed_catalog_and_valid_links() -> None:
    """카탈로그(FK 선행) → 유효 crosslink 적재."""
    load_misconceptions(None, _catalog(_ALL_MIS))
    load_crosslinks(None, _valid_crosslinks())


# ── ① 적재 + read-back ───────────────────────────────────────────────────────
class TestLoadAndResolve:
    def test_resolve_returns_mapped_mids_confidence_desc(self) -> None:
        """kebab_a → [MITXL02, MITXL01](confidence 내림차순)·kebab_b → [MITXL01]."""
        _skip_if_unreachable()
        try:
            _seed_catalog_and_valid_links()
            resolver = MisconceptionCrosslinkResolver()
            assert resolver.resolve(_KEBAB_A) == [_MIS_B, _MIS_A]  # 0.9 먼저
            assert resolver.resolve(_KEBAB_B) == [_MIS_A]
            assert resolver.resolve("zzit-xlink-none") == []  # 미매핑 kebab → 빈 목록
        finally:
            _cleanup()


# ── ② 멱등(트리플 upsert) ────────────────────────────────────────────────────
class TestIdempotent:
    def test_reload_stable_rows_and_updates_confidence(self) -> None:
        """같은 트리플 재적재 → 행 증가 0·confidence 갱신(link_id 보존·ON CONFLICT)."""
        _skip_if_unreachable()
        from sqlalchemy import text

        try:
            _seed_catalog_and_valid_links()
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    n1 = conn.execute(
                        text(
                            "SELECT count(*) FROM misconception_crosslink "
                            "WHERE kebab_id = ANY(:k)"
                        ),
                        {"k": _ALL_KEBAB},
                    ).scalar_one()
            finally:
                engine.dispose()  # type: ignore[attr-defined]
            assert n1 == 3

            # confidence 바꿔 재적재 → 행 수 불변·값 갱신.
            bumped = {"crosslinks": [_xlink(_KEBAB_B, _MIS_A, 0.99)]}
            load_crosslinks(None, bumped)
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    n2 = conn.execute(
                        text(
                            "SELECT count(*) FROM misconception_crosslink "
                            "WHERE kebab_id = ANY(:k)"
                        ),
                        {"k": _ALL_KEBAB},
                    ).scalar_one()
                    conf = conn.execute(
                        text(
                            "SELECT confidence FROM misconception_crosslink "
                            "WHERE kebab_id = :k AND mis_id = :m AND link_type = :t"
                        ),
                        {"k": _KEBAB_B, "m": _MIS_A, "t": "직접매핑"},
                    ).scalar_one()
            finally:
                engine.dispose()  # type: ignore[attr-defined]
            assert n2 == 3  # 행 증가 없음(upsert)
            assert float(conf) == pytest.approx(0.99)  # 값 갱신
        finally:
            _cleanup()


# ── ③ FK 실 강제(카탈로그 선행 요건) ─────────────────────────────────────────
class TestForeignKeyEnforced:
    def test_crosslink_to_absent_mid_raises(self) -> None:
        """카탈로그에 없는 mis_id crosslink 적재 → IntegrityError(실 FK → misconception_catalog)."""
        _skip_if_unreachable()
        from sqlalchemy.exc import IntegrityError

        try:
            # 카탈로그만 적재(FK 대상 존재)하되, MITXL99는 *적재 안 함*.
            load_misconceptions(None, _catalog(_ALL_MIS))
            bad = {"crosslinks": [_xlink(_KEBAB_FK, _MIS_ABSENT, 0.9)]}
            with pytest.raises(IntegrityError):
                load_crosslinks(None, bad)
        finally:
            _cleanup()


# ── ④ resolve_many(N+1 회피·kebab별 그룹) ────────────────────────────────────
class TestResolveMany:
    def test_resolve_many_groups_by_kebab(self) -> None:
        """다중 kebab 일괄 해소 — kebab별 mis_id 목록(confidence desc)."""
        _skip_if_unreachable()
        try:
            _seed_catalog_and_valid_links()
            resolver = MisconceptionCrosslinkResolver()
            out = resolver.resolve_many([_KEBAB_A, _KEBAB_B, "zzit-xlink-none"])
            assert out.get(_KEBAB_A) == [_MIS_B, _MIS_A]
            assert out.get(_KEBAB_B) == [_MIS_A]
            assert out.get("zzit-xlink-none", []) == []
        finally:
            _cleanup()
