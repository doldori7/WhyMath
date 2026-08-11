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
