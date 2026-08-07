"""COLLAB-02 — 파기 계획 완전성 검사의 *방향 역전*(실행→계획, 소유 테이블 중 계획 누락 검출).

`test_erasure.py:94 test_covers_all_planned_tables`는 "`_ERASURE_PLAN`에 있는 테이블은 전부 실제
삭제 순서(`_delete_order`)에 등장하는가"(계획→실행, `planned <= order`)만 단언한다. 그 역방향 —
"소유 컬럼(`user_id`·`student_id`·`target_user_id`)을 가진 테이블인데 `_ERASURE_PLAN`에 아예 없는
것이 있는가"(실행→계획) — 는 검사되지 않았다. 새 테이블을 만들며 사용자 데이터를 담는데 실수로
`_ERASURE_PLAN` 등재를 깜빡하면, 그 테이블은 삭제권 요청에도 영원히 안 지워지는데 아무 테스트도
잡지 못했다. 본 모듈이 그 역방향을 강제한다.

hermetic: `Base.metadata.tables`(SQLAlchemy 선언적 메타데이터)만 읽는다 — DB 연결 0
(`tests/backend/l1/test_edge_relation_governance.py` 순수 메타데이터 스윕 선례).

실측(2026-08 COLLAB-02, 현행 62테이블 전수):
  owner 컬럼(`user_id`·`student_id`·`target_user_id`) 보유 테이블 = 21개
    = `_ERASURE_PLAN` 18개 + `user_profile`(계획 밖에서 `erase_user()`가 마지막에 명시 삭제)
    + `deletion_audit`·`privacy_audit`(E형 감사 — `_ERASURE_PLAN_EXEMPTIONS`에 사유와 함께 등재).
  → **현행 누락 0건**(반증 결과 — 문제를 억지로 만들지 않는다). 상세 스캔 명령·출력은 이 태스크의
  세션 보고에 기록.

허용목록(`_ERASURE_PLAN_EXEMPTIONS`)은 `privacy/erasure.py`에 사유와 함께 정의돼 있다 — 무사유
예외 금지(CLAUDE.md). 협업(다자 소유) 스키마가 만들 B·C·D형 테이블의 파기 규칙은
`docs/architecture/collaboration_landing_design.md` §2.2·§3(5분류·3배관 처리표·변호사 검토
대상)이 정본이다 — 이 테스트는 "분류·지정이 있어야 한다"는 *구조적 요건*만 기계로 강제한다.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import Column, MetaData, Table, Uuid

from whymath_backend.privacy.erasure import _ERASURE_PLAN, _ERASURE_PLAN_EXEMPTIONS

# `_ERASURE_PLAN`이 실제로 쓰는 소유 컬럼명(user_id·student_id) + `privacy_audit`의 target_user_id
# (다른 사용자의 데이터가 대상일 때의 소유 표지). 실제 스키마(db/models/*.py) 전수 확인 결과 이
# 3개 외에 "비슷한 의미"(owner_id·author_id 등)의 컬럼은 *소유 축*이 아니라 *콘텐츠 저작/검수
# 행위자*(problem.created_by·content_provenance.approved_by·curriculum_entry.verified_by·
# pedagogy_content_slot.reviewed_by)다 — 그 테이블 자체가 공유 콘텐츠(문항·성취기준·교수법 팩)라
# "이 행의 데이터 주체가 이 사용자다"라는 삭제권 의미가 성립하지 않는다(스캔 근거는 세션 보고 참조).
OWNER_COLUMN_NAMES: frozenset[str] = frozenset({"user_id", "student_id", "target_user_id"})


def _owner_tables(metadata: MetaData) -> dict[str, frozenset[str]]:
    """메타데이터 전수에서 소유 컬럼을 가진 테이블명 → 매칭된 컬럼명 집합."""
    result: dict[str, frozenset[str]] = {}
    for name, table in metadata.tables.items():
        matched = frozenset(c.name for c in table.columns) & OWNER_COLUMN_NAMES
        if matched:
            result[name] = matched
    return result


def _missing_from_plan(
    metadata: MetaData,
    *,
    planned: frozenset[str],
    exemptions: dict[str, str],
) -> frozenset[str]:
    """소유 테이블 중 계획(`planned`)·허용목록(`exemptions`) 둘 다에 없는 것(실행→계획)."""
    return frozenset(_owner_tables(metadata)) - planned - frozenset(exemptions)


# ===========================================================================
# 실측 — 현행 62테이블 실제 검사(red면 이 태스크에서 상환 필요)
# ===========================================================================


def test_no_owner_column_table_missing_from_erasure_plan() -> None:
    """실행→계획 방향 — `_ERASURE_PLAN`·허용목록 밖의 소유 컬럼 보유 테이블 검출(0건이어야 함).

    `user_profile`은 `_ERASURE_PLAN` 튜플엔 없지만 `erase_user()`가 자식 삭제 후 마지막에 명시
    삭제하므로(erasure.py 삭제 순서 주석) 별도로 "계획됨"에 합류시킨다 — 미계획 누락이 아니다.
    """
    import whymath_backend.db.models  # noqa: F401  # 62테이블 전부 Base.metadata에 등록(실측 필수)
    from whymath_backend.db.base import Base

    planned = frozenset({m.__tablename__ for m, _ in _ERASURE_PLAN}) | {"user_profile"}
    missing = _missing_from_plan(
        Base.metadata, planned=planned, exemptions=_ERASURE_PLAN_EXEMPTIONS
    )

    assert missing == frozenset(), (
        f"소유 컬럼(user_id/student_id/target_user_id)을 가졌으나 _ERASURE_PLAN에도 "
        f"_ERASURE_PLAN_EXEMPTIONS에도 없는 테이블: {sorted(missing)} — "
        "삭제권 요청에도 영원히 지워지지 않는 테이블이다. _ERASURE_PLAN에 추가하거나, "
        "정당한 사유와 함께 _ERASURE_PLAN_EXEMPTIONS에 등재하라(무사유 예외 금지)."
    )


def test_exemptions_have_nonempty_reasons() -> None:
    """허용목록의 모든 예외는 사유가 비어 있지 않다 — 무사유 예외 금지(CLAUDE.md 하드 게이트)."""
    assert _ERASURE_PLAN_EXEMPTIONS, "허용목록이 비어 있으면 안 된다(감사 테이블 최소 2종 존재)."
    for table_name, reason in _ERASURE_PLAN_EXEMPTIONS.items():
        assert reason.strip(), f"{table_name}의 예외 사유가 비어 있다(무사유 예외 금지)."
        assert (
            len(reason.strip()) >= 20
        ), f"{table_name}의 예외 사유가 지나치게 짧다(형식적 사유 의심)."


def test_exemptions_are_subset_of_actual_owner_tables() -> None:
    """허용목록에 등재된 테이블은 실제로 소유 컬럼을 가진 실존 테이블이어야 한다(유령 예외 방지)."""
    import whymath_backend.db.models  # noqa: F401
    from whymath_backend.db.base import Base

    owner_tables = frozenset(_owner_tables(Base.metadata))
    planned = frozenset({m.__tablename__ for m, _ in _ERASURE_PLAN})
    for table_name in _ERASURE_PLAN_EXEMPTIONS:
        if table_name == "user_profile":
            # user_profile은 user_id가 PK(소유 컬럼과 동일 이름) — 실제 테이블로 존재 확인.
            assert table_name in Base.metadata.tables, "user_profile 테이블이 존재하지 않는다."
            continue
        assert table_name in owner_tables, f"{table_name}은 소유 컬럼이 없는데 예외로 등재돼 있다."
        assert table_name not in planned, f"{table_name}은 이미 _ERASURE_PLAN에 있다(중복 예외)."


# ===========================================================================
# 변별력 (④) — 합성 MetaData로 리크 테이블을 주입→red, 제거→green을 같은 세션에서 실측.
#
# 실 Base.metadata를 오염시키지 않기 위해(선언적 베이스는 프로세스 전역 싱글턴 — 여기서 서브클래싱
# 하면 이후 alembic·다른 테스트가 보는 메타데이터가 영구 오염된다) 독립 MetaData로 "소유 컬럼을
# 가진 테이블 중 계획 밖의 것"을 합성 구성해 `_missing_from_plan` 자체의 변별력을 증명한다. 실
# Base.metadata에 대한 실제 red/green 재현은 세션 보고에 별도 스크립트 실행 기록으로 남긴다
# ("실패 상태에서 실제로 실패 신호를 내는지 확인된 검사만 동봉" — CLAUDE.md).
# ===========================================================================


def test_sweep_flags_injected_leak_table_then_clears_after_removal() -> None:
    """더미 user_id 테이블 주입 → red 실측 → 제거 → green 실측(양방향 변별력 증명)."""
    planned = frozenset({"planned_tbl"})

    # ── 주입 상태: 계획에 없는 leaked_tbl이 user_id를 가짐 → red ──
    meta_with_leak = MetaData()
    Table(
        "planned_tbl",
        meta_with_leak,
        Column("id", Uuid, primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid),
    )
    Table(
        "leaked_tbl",  # ← 방금 만들었는데 _ERASURE_PLAN 등재를 깜빡한 신설 테이블 시뮬레이션
        meta_with_leak,
        Column("id", Uuid, primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid),
        Column("payload", sa.Text),
    )
    missing_with_leak = _missing_from_plan(meta_with_leak, planned=planned, exemptions={})
    assert missing_with_leak == frozenset(
        {"leaked_tbl"}
    ), "리크 테이블 주입 상태에서 red가 나지 않았다 — 검사에 변별력이 없다(위장 검증)."

    # ── 제거 상태: leaked_tbl 없이 동일 스윕 → green ──
    meta_clean = MetaData()
    Table(
        "planned_tbl",
        meta_clean,
        Column("id", Uuid, primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid),
    )
    missing_clean = _missing_from_plan(meta_clean, planned=planned, exemptions={})
    assert missing_clean == frozenset(), "리크 테이블 제거 후에도 red가 남았다 — 검사 로직 결함."


def test_sweep_respects_exemptions() -> None:
    """허용목록에 등재된 테이블은 소유 컬럼이 있어도 red를 내지 않는다(사유 명시 예외 경로 검증)."""
    meta = MetaData()
    Table(
        "audit_tbl",
        meta,
        Column("id", Uuid, primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid),
    )
    missing_without_exemption = _missing_from_plan(meta, planned=frozenset(), exemptions={})
    assert missing_without_exemption == frozenset({"audit_tbl"})  # 예외 미등재 시 red(대조군)

    missing_with_exemption = _missing_from_plan(
        meta, planned=frozenset(), exemptions={"audit_tbl": "감사 로그 — 계정 삭제 후에도 잔존."}
    )
    assert missing_with_exemption == frozenset()  # 사유 명시 예외 등재 시 green
