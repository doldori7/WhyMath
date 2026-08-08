"""ADMIN-03 — 감사 2테이블(deletion_audit·privacy_audit)의 보존 파기 계획 *제외*를 동결.

`privacy/retention.py`의 `_RETENTION_PLAN`은 학습 활동 PII 시계열을 타임스탬프 기준으로 파기한다.
그러나 `deletion_audit`(`DeletionAudit`)·`privacy_audit`(`PrivacyAudit`)은 **법정 증빙(compliance
evidence)** 성격이라 즉시 파기 대상이 아니며(지우면 삭제·반출 사실 증빙이 함께 사라진다), 최종
보존 연한은 **미확정**(MGMT-02 변호사 회신 선행 — CLAUDE.md 「법령 유래 절차의 기계 대체 금지」)
이다. 상세 사유는 `retention.py` 모듈 docstring·`docs/standards/security_privacy.md` 「감사 로그」
편집자 부기 참조.

이 모듈은 그 제외가 *의도된 것*임을 기계로 동결한다 — 누군가 감사 테이블을 `_RETENTION_PLAN`에
실수로(또는 연한 확정 전에 성급히) 편입하면 red로 잡는다. hermetic: `_RETENTION_PLAN` 상수와
ORM 모델 메타데이터만 읽는다(DB 연결 0 — `test_erasure_plan_completeness.py` 순수 메타데이터
스윕 선례).

변별력(④): `_forbidden_in_plan` 헬퍼를 합성 플랜에 대해 양방향으로 실측한다 — 감사 테이블을
넣은 플랜엔 red, 뺀 플랜엔 green. 실 `_RETENTION_PLAN`에 감사 테이블을 임시 편입→red→원복→green
실측은 이 태스크 세션 보고에 별도 기록으로 남긴다("실패 상태에서 실제로 실패 신호를 내는지
확인된 검사만 동결" — CLAUDE.md).
"""

from __future__ import annotations

from whymath_backend.db.base import Base
from whymath_backend.db.models.audit import DeletionAudit, PrivacyAudit
from whymath_backend.privacy.retention import _RETENTION_PLAN

# 보존 파기 계획에서 *반드시 제외*돼야 하는 감사 테이블(법정 증빙·연한 미확정).
_AUDIT_TABLES = frozenset({"deletion_audit", "privacy_audit"})


def _plan_tablenames(plan: tuple[tuple[type[Base], str], ...]) -> frozenset[str]:
    """(모델, 컬럼) 플랜 → 테이블명 집합."""
    return frozenset(model.__tablename__ for model, _ in plan)


def _forbidden_in_plan(
    plan: tuple[tuple[type[Base], str], ...],
    *,
    forbidden: frozenset[str],
) -> frozenset[str]:
    """플랜에 등장하면 안 되는 테이블 중 *실제로 등장한* 것(있으면 위반)."""
    return _plan_tablenames(plan) & forbidden


# ===========================================================================
# 실측 — 현행 `_RETENTION_PLAN` 동결
# ===========================================================================


def test_deletion_audit_not_in_retention_plan() -> None:
    """`deletion_audit`는 `_RETENTION_PLAN`에 없다 — 법정 증빙·즉시 파기 대상 아님."""
    assert "deletion_audit" not in _plan_tablenames(_RETENTION_PLAN), (
        "deletion_audit(GDPR 삭제 증빙)이 _RETENTION_PLAN에 편입됐다 — 감사 로그는 즉시 파기 "
        "대상이 아니며 보존 연한은 미확정(MGMT-02 변호사 회신 선행)이다. 편입을 되돌리고, "
        "연한이 확정되면 별도 태스크로 감사 전용 파기 경로를 배선하라(CLAUDE.md 법령 절차 기계 "
        "대체 금지)."
    )


def test_privacy_audit_not_in_retention_plan() -> None:
    """`privacy_audit`는 `_RETENTION_PLAN`에 없다 — 반출·동의변경·관리자접근 감사 증빙."""
    assert "privacy_audit" not in _plan_tablenames(_RETENTION_PLAN), (
        "privacy_audit(개인정보 감사 증빙)이 _RETENTION_PLAN에 편입됐다 — deletion_audit와 동일 "
        "근거로 즉시 파기 대상이 아니다. 편입을 되돌려라(사유: retention.py docstring)."
    )


def test_both_audit_tables_excluded_from_retention_plan() -> None:
    """감사 2테이블이 모두 제외됐음을 한 번에 단언(집합 교집합 = 공집합)."""
    violations = _forbidden_in_plan(_RETENTION_PLAN, forbidden=_AUDIT_TABLES)
    assert violations == frozenset(), (
        f"보존 파기 계획에 감사 테이블이 편입됐다: {sorted(violations)} — 법정 증빙 성격·연한 "
        "미확정(MGMT-02 선행)이라 제외돼야 한다."
    )


def test_audit_models_map_to_expected_tablenames() -> None:
    """동결 대상 테이블명이 실제 ORM 모델의 `__tablename__`과 일치(유령 이름 방지)."""
    # 테이블명 문자열이 모델과 어긋나면 위 제외 단언이 헛것을 지키게 된다 — 그 표류를 막는다.
    assert DeletionAudit.__tablename__ == "deletion_audit"
    assert PrivacyAudit.__tablename__ == "privacy_audit"
    # 두 테이블이 실제 스키마에 존재하는지도 확인(실존 테이블에 대한 제외임을 보증).
    import whymath_backend.db.models  # noqa: F401  # 전 테이블 Base.metadata 등록

    assert _AUDIT_TABLES <= frozenset(Base.metadata.tables)


# ===========================================================================
# 변별력 (④) — 합성 플랜으로 red/green 양방향 실측(전역 `_RETENTION_PLAN` 무오염).
# ===========================================================================


def test_sweep_flags_injected_audit_table_then_clears_after_removal() -> None:
    """감사 테이블을 넣은 합성 플랜 → red, 뺀 플랜 → green(검사 자체의 변별력 증명)."""
    # ── 주입 상태: DeletionAudit을 성급히 파기 계획에 넣은 상황 시뮬레이션 → red ──
    plan_with_audit: tuple[tuple[type[Base], str], ...] = (
        *_RETENTION_PLAN,
        (DeletionAudit, "deleted_at"),  # ← 연한 확정 전 성급한 편입(실수) 시뮬레이션
    )
    violations = _forbidden_in_plan(plan_with_audit, forbidden=_AUDIT_TABLES)
    assert violations == frozenset(
        {"deletion_audit"}
    ), "감사 테이블 주입 상태에서 red가 나지 않았다 — 검사에 변별력이 없다(위장 검증)."

    # ── 제거 상태: 실 `_RETENTION_PLAN`(감사 테이블 없음) → green ──
    violations_clean = _forbidden_in_plan(_RETENTION_PLAN, forbidden=_AUDIT_TABLES)
    assert (
        violations_clean == frozenset()
    ), "감사 테이블 없는 실 플랜에서 red가 남았다 — 검사 로직 결함(성공/실패 같은 결과 금지)."
