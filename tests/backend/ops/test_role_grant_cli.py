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

from whymath_backend.config import Settings
from whymath_backend.db.models.audit import PrivacyAudit
from whymath_backend.db.models.user import UserProfile
from whymath_backend.ops import role_grant_cli as cli
from whymath_backend.privacy.audit import record_role_change_audit
from whymath_backend.schema.enums import Role

_UID = uuid.uuid4()


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

        code = cli.main(["grant", str(_UID), "content_admin"], grant_fn=_fn)
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"user_id": str(_UID), "old_role": "student", "new_role": "content_admin"}

    def test_nonexistent_user_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            raise cli.RoleGrantError(f"사용자를 찾을 수 없습니다: {user_id}")

        code = cli.main(["grant", str(_UID), "content_admin"], grant_fn=_fn)
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

        code = cli.main(["revoke", str(_UID), "content_admin"], revoke_fn=_fn)
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"user_id": str(_UID), "old_role": "content_admin", "new_role": "student"}

    def test_role_mismatch_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn(user_id: uuid.UUID, role: Role) -> dict[str, str]:
            raise cli.RoleGrantError(
                "사용자가 보유한 역할이 아닙니다(현재: student, 회수 요청: content_admin)"
            )

        code = cli.main(["revoke", str(_UID), "content_admin"], revoke_fn=_fn)
        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        err = json.loads(captured.err)
        assert "보유한 역할이 아닙니다" in err["error"]


class TestListSubcommand:
    def test_prints_users_and_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn() -> list[dict[str, str]]:
            return [{"user_id": str(_UID), "role": "content_admin"}]

        code = cli.main(["list"], list_fn=_fn)
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"users": [{"user_id": str(_UID), "role": "content_admin"}], "total": 1}

    def test_empty_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        async def _fn() -> list[dict[str, str]]:
            return []

        code = cli.main(["list"], list_fn=_fn)
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
