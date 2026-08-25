"""운영자 좌석 발급 ops CLI(`ops/role_grant_cli.py`, ADMIN-01) — 단위(hermetic·러너/세션 주입).

DB 없이 검증하는 것:
  ① CLI 배선(argparse) — 잘못된 UUID·알 수 없는 역할명 → SystemExit(2, argparse 자체 거부)
  ② grant/revoke/list *러너 주입* — 합성 grant_fn/revoke_fn/list_fn으로 성공 JSON stdout·
     `RoleGrantError` → 종료 1 + stderr 사유(존재하지 않는 user_id·revoke 역할 불일치)
  ③ `apply_role_change`(session mutate만, commit 없음) — FakeSession으로 사용자 없음·
     `expected_current_role` 불일치·정상 mutate 3경로
  ④ `record_role_change_audit`(`privacy/audit.py`) — FakeSession으로 `session.add()` 조립만
     (commit은 호출자 — `test_audit.py`의 TestRecordExportAudit 등과 동형 패턴)

실 DB 왕복(부여 후 실제 role 변경·403→200/201→403 3상태·트랜잭션 원자성 강제 롤백)은
`test_role_grant_cli_integration.py`(`@pytest.mark.integration`)가 검증한다(중복 0).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from pydantic import SecretStr

from whymath_backend.audit.event_bus import emit_identity_event
from whymath_backend.config import Settings
from whymath_backend.db.models.audit import AuditEvent, PrivacyAudit
from whymath_backend.db.models.user import UserProfile
from whymath_backend.ops import role_grant_cli as cli
from whymath_backend.privacy.audit import record_role_change_audit
from whymath_backend.schema.enums import (
    AuditEventAuthorization,
    AuditEventSeverity,
    Role,
)

_UID = uuid.uuid4()


async def _preflight_ok() -> None:
    """스키마 프리플라이트 통과 좌석 — hermetic 테스트는 DB를 왕복하지 않는다.

    `main()`은 세 서브커맨드 **전부**에 프리플라이트를 선행시키므로, 주입하지 않으면 기본값
    (`_default_preflight_fn`)이 실 DB에 붙으려 한다. 아래 테스트들은 CLI *배선*만 보는 것이
    목적이라 통과 좌석을 명시 주입한다(프리플라이트 자체의 판정은 `TestSchemaPreflight`).
    """


# ===========================================================================
# argparse 배선 — 잘못된 인자는 CLI 함수 호출 전에 거부(SystemExit(2))
# ===========================================================================


class TestArgparseWiring:
    def test_grant_invalid_role_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit):
            cli.main(["grant", str(_UID), "not_a_role"])

    def test_revoke_invalid_role_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit):
            cli.main(["revoke", str(_UID), "super_admin"])

    def test_grant_invalid_uuid_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit):
            cli.main(["grant", "not-a-uuid", "content_admin"])

    def test_no_subcommand_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit):
            cli.main([])


# ===========================================================================
# grant/revoke/list — 주입 러너로 CLI 조립(파싱→호출→stdout/stderr→종료코드)만 검증
# ===========================================================================


class TestGrantSubcommand:
    def test_success_prints_json_and_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            assert role is Role.CONTENT_ADMIN
            return {"user_id": str(user_id), "old_role": "student", "new_role": role.value}

        code = cli.main(
            ["grant", str(_UID), "content_admin"], grant_fn=_fn, preflight_fn=_preflight_ok
        )
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"user_id": str(_UID), "old_role": "student", "new_role": "content_admin"}

    def test_nonexistent_user_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            raise cli.RoleGrantError(f"사용자를 찾을 수 없습니다: {user_id}")

        code = cli.main(
            ["grant", str(_UID), "content_admin"], grant_fn=_fn, preflight_fn=_preflight_ok
        )
        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        err = json.loads(captured.err)
        assert str(_UID) in err["error"]


class TestRevokeSubcommand:
    def test_success_prints_json_and_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            assert role is Role.CONTENT_ADMIN
            return {"user_id": str(user_id), "old_role": role.value, "new_role": "student"}

        code = cli.main(
            ["revoke", str(_UID), "content_admin"], revoke_fn=_fn, preflight_fn=_preflight_ok
        )
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"user_id": str(_UID), "old_role": "content_admin", "new_role": "student"}

    def test_role_mismatch_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            raise cli.RoleGrantError(
                "사용자가 보유한 역할이 아닙니다(현재: student, 회수 요청: content_admin)"
            )

        code = cli.main(
            ["revoke", str(_UID), "content_admin"], revoke_fn=_fn, preflight_fn=_preflight_ok
        )
        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        err = json.loads(captured.err)
        assert "보유한 역할이 아닙니다" in err["error"]


class TestListSubcommand:
    def test_prints_users_and_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn() -> list[dict[str, str]]:
            return [{"user_id": str(_UID), "role": "content_admin"}]

        code = cli.main(["list"], list_fn=_fn, preflight_fn=_preflight_ok)
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"users": [{"user_id": str(_UID), "role": "content_admin"}], "total": 1}

    def test_empty_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn() -> list[dict[str, str]]:
            return []

        code = cli.main(["list"], list_fn=_fn, preflight_fn=_preflight_ok)
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"users": [], "total": 0}


# ===========================================================================
# apply_role_change — FakeSession(get만 필요, add/commit 없음 — mutate-only 계약)
# ===========================================================================


class _FakeUserSession:
    def __init__(self, users: dict[uuid.UUID, UserProfile] | None = None) -> None:
        self._users = dict(users or {})
        self.added: list[Any] = []

    async def get(self, model: Any, pk: uuid.UUID) -> UserProfile | None:
        assert model is UserProfile
        return self._users.get(pk)

    def add(self, obj: Any) -> None:
        self.added.append(obj)


def _user(role: Role) -> UserProfile:
    return UserProfile(user_id=_UID, role=role)


class TestApplyRoleChange:
    @pytest.mark.asyncio
    async def test_missing_user_raises(self) -> None:
        session = _FakeUserSession()
        with pytest.raises(cli.RoleGrantError, match="찾을 수 없습니다"):
            await cli.apply_role_change(session, user_id=_UID, new_role=Role.CONTENT_ADMIN)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_grant_mutates_and_returns_old_role(self) -> None:
        user = _user(Role.STUDENT)
        session = _FakeUserSession({_UID: user})
        old = await cli.apply_role_change(session, user_id=_UID, new_role=Role.CONTENT_ADMIN)  # type: ignore[arg-type]
        assert old is Role.STUDENT
        assert user.role is Role.CONTENT_ADMIN
        # mutate-only 계약 — session.add()도 commit()도 호출하지 않는다(호출자 책임).
        assert session.added == []

    @pytest.mark.asyncio
    async def test_revoke_expected_role_mismatch_raises(self) -> None:
        user = _user(Role.STUDENT)  # 이미 STUDENT인데 CONTENT_ADMIN 회수를 시도
        session = _FakeUserSession({_UID: user})
        with pytest.raises(cli.RoleGrantError, match="보유한 역할이 아닙니다"):
            await cli.apply_role_change(  # type: ignore[arg-type]
                session,
                user_id=_UID,
                new_role=Role.STUDENT,
                expected_current_role=Role.CONTENT_ADMIN,
            )
        assert user.role is Role.STUDENT  # 거부됐으니 mutate 안 됨

    @pytest.mark.asyncio
    async def test_revoke_expected_role_match_mutates(self) -> None:
        user = _user(Role.CONTENT_ADMIN)
        session = _FakeUserSession({_UID: user})
        old = await cli.apply_role_change(  # type: ignore[arg-type]
            session,
            user_id=_UID,
            new_role=Role.STUDENT,
            expected_current_role=Role.CONTENT_ADMIN,
        )
        assert old is Role.CONTENT_ADMIN
        assert user.role is Role.STUDENT


# ===========================================================================
# record_role_change_audit — FakeSession(add만 추적, test_audit.py 패턴 동형)
# ===========================================================================


class _FakeAuditSession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)


def _settings(*, salt: str = "s") -> Settings:
    return Settings(pii_audit_ip_salt=SecretStr(salt))


class TestRecordRoleChangeAudit:
    def test_adds_role_change_row_self_scoped(self) -> None:
        session = _FakeAuditSession()
        row = record_role_change_audit(
            session,  # type: ignore[arg-type]
            user_id=_UID,
            ip="203.0.113.7",
            settings=_settings(),
        )
        assert session.added == [row]
        assert isinstance(row, PrivacyAudit)
        assert row.user_id == _UID
        assert row.target_user_id is None  # 본인 계정 사건(admin_access와 달리 actor≠target 없음)
        assert row.event_kind == "role_change"
        assert row.consent_scope is None
        assert row.ip_hash is not None

    def test_no_ip_yields_none_ip_hash(self) -> None:
        session = _FakeAuditSession()
        row = record_role_change_audit(
            session, user_id=_UID, ip=None, settings=_settings()  # type: ignore[arg-type]
        )
        assert row.ip_hash is None


# ===========================================================================
# ADMIN-10: IAM 이벤트 AuditEvent 배선
# ===========================================================================


class TestEmitIdentityEvent:
    """`emit_identity_event`가 `iam.role.assign/revoke` AuditEvent를 올바르게 생성한다."""

    @pytest.mark.asyncio
    async def test_role_assign_emits_audit_event(self) -> None:
        user = _user(Role.STUDENT)
        session = _FakeUserSession({_UID: user})
        old_role = await cli.apply_role_change(
            session,  # type: ignore[arg-type]
            user_id=_UID,
            new_role=Role.CONTENT_ADMIN,
        )
        emit_identity_event(
            session,  # type: ignore[arg-type]
            action="iam.role.assign",
            actor_id=None,
            resource_id=_UID,
            source_service="role_grant_cli",
            authorization_decision=AuditEventAuthorization.allow,
            severity=AuditEventSeverity.high,
            metadata={"old_role": old_role.value, "new_role": Role.CONTENT_ADMIN.value},
        )
        audit_rows = [a for a in session.added if isinstance(a, AuditEvent)]
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit.action == "iam.role.assign"
        assert audit.actor_type == "user"
        assert audit.resource_type == "UserProfile"
        assert audit.resource_id == str(_UID)
        assert audit.authorization_decision == "allow"
        assert audit.severity == "HIGH"
        assert audit.retention_policy_id == "RET_SECURITY"
        assert audit.event_metadata == {
            "old_role": "student",
            "new_role": "content_admin",
        }


# ===========================================================================
# 스키마 프리플라이트 — 2026-08-11 사고 재현 테스트
# ===========================================================================
#
# 사고: 마이그레이션이 뒤처진 DB에 이 CLI를 실행하자 `column user_profile.role does not
# exist`가 raw SQLAlchemy 트레이스백 100여 줄로 터졌고, 운영자는 그 출력에서 "무엇을 해야
# 하는지"를 읽어낼 수 없었다. 아래는 그 상태가 **실행 전에** 한 줄 지시로 바뀌는지를 본다.


class TestSchemaPreflight:
    def test_behind_schema_blocks_every_subcommand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """뒤처진 스키마면 grant/revoke/list 셋 다 DB를 건드리기 전에 거부된다."""

        async def _behind() -> None:
            raise cli.SchemaPreflightError(
                "DB 스키마가 코드보다 뒤처졌습니다 — 적용=f3a4b5c6d7e8 / 코드 기대=090d254a5d43. "
                "먼저 `alembic upgrade head`를 적용하세요."
            )

        async def _must_not_run(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
            raise AssertionError("프리플라이트가 막았어야 하는데 러너가 호출됐다")

        for argv in (
            ["grant", str(_UID), "content_admin"],
            ["revoke", str(_UID), "content_admin"],
            ["list"],
        ):
            code = cli.main(
                argv,
                grant_fn=_must_not_run,
                revoke_fn=_must_not_run,
                list_fn=_must_not_run,
                preflight_fn=_behind,
            )
            captured = capsys.readouterr()
            assert code == 1, f"{argv[0]}가 프리플라이트를 우회했다"
            assert captured.out == "", "거부인데 stdout에 결과가 찍혔다"
            err = json.loads(captured.err)
            # 행동 지시가 실제로 담겨 있어야 한다 — 트레이스백 대신 "무엇을 하라"가 나와야 의미가 있다.
            assert "alembic upgrade head" in err["error"]

    def test_passing_preflight_lets_subcommand_run(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """대조군 — 프리플라이트가 통과하면 종전대로 동작한다(변별력의 반대편)."""

        async def _fn() -> list[dict[str, str]]:
            return []

        code = cli.main(["list"], list_fn=_fn, preflight_fn=_preflight_ok)
        assert code == 0
        assert json.loads(capsys.readouterr().out) == {"users": [], "total": 0}

    def test_unreachable_db_is_named_not_swallowed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """확인 자체가 실패해도 '통과'로 위장하지 않고, 예외 타입명을 남긴다(침묵 실패 금지)."""

        async def _unreachable() -> None:
            raise cli.SchemaPreflightError(
                "DB 스키마 버전을 확인하지 못했습니다(OperationalError) — "
                "DB 도달성(WHYMATH_DATABASE_URL)과 `alembic_version` 접근 권한을 확인하세요."
            )

        code = cli.main(["list"], preflight_fn=_unreachable)
        assert code == 1
        err = json.loads(capsys.readouterr().err)
        assert "OperationalError" in err["error"]

    def test_unexpected_db_error_becomes_one_line_not_traceback(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """프리플라이트를 통과한 뒤 터지는 예상 못 한 DB 오류도 한 줄 JSON이 된다.

        사고 당시 `list`는 try 블록 자체가 없어 raw 트레이스백이 그대로 나왔다.
        """

        async def _boom() -> list[dict[str, str]]:
            raise RuntimeError("연결이 끊겼습니다")

        code = cli.main(["list"], list_fn=_boom, preflight_fn=_preflight_ok)
        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        err = json.loads(captured.err)
        assert "RuntimeError" in err["error"]


class TestJudgeSchemaReadiness:
    """판정 순수 함수 — 두 신호(컬럼 실재 × 버전 테이블)의 4조합 전수.

    2026-08-11 2차 실측: 첫 구현은 버전 테이블만 봤고, 그래서 **실제 사고를 못 잡았다**.
    대상 DB의 기록 head가 `d6e7f8a9b0c1`(코드가 모르는 값)이라 AHEAD로 분류돼 통과했는데
    컬럼은 실제로 없었다. 아래 `test_unknown_head_with_missing_column`이 바로 그 케이스다.
    """

    _HEAD = "090d254a5d43"  # EXPECTED_ALEMBIC_HEAD와 동일해야 의미가 있다(아래에서 대조)

    def test_head_and_column_present_passes(self) -> None:
        from whymath_backend.db.schema_version import EXPECTED_ALEMBIC_HEAD

        assert cli.judge_schema_readiness((EXPECTED_ALEMBIC_HEAD,), role_column_exists=True) is None

    def test_unknown_head_with_missing_column(self) -> None:
        """★ Kiki가 실제로 겪은 상태 — 버전 테이블만 보면 '통과'가 나오는 조합."""
        msg = cli.judge_schema_readiness(("d6e7f8a9b0c1",), role_column_exists=False)
        assert msg is not None, "버전 테이블이 AHEAD라고 통과시키면 실제 사고를 못 잡는다"
        assert "user_profile.role" in msg
        # 이 상태에서 alembic이 실제로 거부한다는 사실(실측)을 안내에 담아야 한다.
        assert "Can't locate revision" in msg
        assert "d6e7f8a9b0c1" in msg

    def test_known_behind_head_with_missing_column(self) -> None:
        msg = cli.judge_schema_readiness(("b4c5d6e7f0a2",), role_column_exists=False)
        assert msg is not None
        assert "alembic upgrade head" in msg
        # 알려진 리비전이면 'Can't locate revision' 경고는 오히려 오도다.
        assert "Can't locate revision" not in msg

    def test_behind_head_but_column_present_still_blocked(self) -> None:
        """컬럼은 있어도 다른 신규 컬럼이 빌 수 있으므로 뒤처짐은 여전히 막는다."""
        msg = cli.judge_schema_readiness(("b4c5d6e7f0a2",), role_column_exists=True)
        assert msg is not None
        assert "뒤처졌습니다" in msg

    def test_unknown_head_with_column_present_passes(self) -> None:
        """AHEAD(정상 롤백)인데 필요한 컬럼이 실재하면 막지 않는다 — 가드가 장애 원인이 되면 안 된다."""
        assert cli.judge_schema_readiness(("d6e7f8a9b0c1",), role_column_exists=True) is None

    def test_never_migrated_db(self) -> None:
        msg = cli.judge_schema_readiness((), role_column_exists=False)
        assert msg is not None
        assert "(미적용)" in msg
