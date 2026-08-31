"""운영자 계정 부트스트랩 ops CLI(`ops/account_bootstrap_cli.py`, ADMIN-11) — 단위(hermetic).

DB 없이 검증하는 것:
  ① CLI 배선(argparse) — 이메일 형태가 아닌 인자 → SystemExit(2, argparse 자체 거부)
  ② create *러너 주입* — 합성 create_fn으로 성공 JSON stdout·`AccountBootstrapError` →
     종료 1 + stderr 사유·예상 못 한 예외의 타입명 봉합
  ③ `bootstrap_account`(session mutate만, commit 없음) — FakeSession으로 신규 생성·기존 반환
     2경로. **`email_hash`가 `api/auth.py`의 것과 같은 값을 낸다**는 것이 이 태스크의 핵심
     계약이라 별도로 고정한다(값 복제 시 로그인 경로와 조용히 갈라짐)
  ④ 프리플라이트 판정(`judge_schema_readiness`) — 누락 컬럼 유무로 갈리는 순수 함수

실 DB 왕복(실제 INSERT·멱등 재실행·트랜잭션)은 통합 테스트 범위이며 여기서 중복하지 않는다.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from whymath_backend.api.auth import _DEFAULT_PERSONA, email_hash
from whymath_backend.db.models.user import UserProfile
from whymath_backend.ops import account_bootstrap_cli as cli

_EMAIL = "operator@example.com"


async def _preflight_ok() -> None:
    """스키마 프리플라이트 통과 좌석 — 주입하지 않으면 기본값이 실 DB에 붙으려 한다."""


class _FakeSession:
    """`bootstrap_account`가 쓰는 표면만 흉내낸다(scalar/add) — commit은 계약상 호출되지 않는다."""

    def __init__(self, existing: UserProfile | None = None) -> None:
        self._existing = existing
        self.added: list[UserProfile] = []
        self.committed = False

    async def scalar(self, _statement: Any) -> UserProfile | None:
        return self._existing

    def add(self, obj: UserProfile) -> None:
        self.added.append(obj)

    async def commit(self) -> None:  # pragma: no cover — 불려서는 안 되는 경로
        self.committed = True


# ===========================================================================
# ① argparse 배선 — 잘못된 인자는 러너 호출 전에 거부
# ===========================================================================


class TestArgparseWiring:
    @pytest.mark.parametrize("bad", ["", "   ", "no-at-sign", "@domain.com", "local@", "a b@c.com"])
    def test_non_email_exits_two(self, bad: str) -> None:
        with pytest.raises(SystemExit):
            cli.main(["create", bad], preflight_fn=_preflight_ok)

    def test_missing_subcommand_exits(self) -> None:
        with pytest.raises(SystemExit):
            cli.main([], preflight_fn=_preflight_ok)

    def test_email_is_stripped(self, capsys: pytest.CaptureFixture[str]) -> None:
        """앞뒤 공백은 제거해서 넘긴다 — 붙여넣기 사고가 다른 계정을 만들면 안 된다."""
        seen: list[str] = []

        async def _create(email: str) -> dict[str, Any]:
            seen.append(email)
            return {"user_id": str(uuid.uuid4()), "created": True, "role": "student"}

        assert (
            cli.main(["create", f"  {_EMAIL}  "], create_fn=_create, preflight_fn=_preflight_ok)
            == 0
        )
        assert seen == [_EMAIL]
        capsys.readouterr()


# ===========================================================================
# ② 러너 주입 — 성공 JSON·거부 경로·예외 봉합
# ===========================================================================


class TestCreateRunner:
    def test_success_prints_json_and_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        uid = str(uuid.uuid4())

        async def _create(_email: str) -> dict[str, Any]:
            return {"user_id": uid, "created": True, "role": "student"}

        assert cli.main(["create", _EMAIL], create_fn=_create, preflight_fn=_preflight_ok) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"user_id": uid, "created": True, "role": "student"}

    def test_idempotent_second_run_reports_created_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """④ 멱등 — 2회차는 기존 user_id + created=false. 운영자가 재실행을 두려워하면 안 된다."""
        uid = str(uuid.uuid4())

        async def _create(_email: str) -> dict[str, Any]:
            return {"user_id": uid, "created": False, "role": "student"}

        assert cli.main(["create", _EMAIL], create_fn=_create, preflight_fn=_preflight_ok) == 0
        assert json.loads(capsys.readouterr().out)["created"] is False

    def test_bootstrap_error_exits_one_with_reason(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        async def _create(_email: str) -> dict[str, Any]:
            raise cli.AccountBootstrapError("거부 사유")

        assert cli.main(["create", _EMAIL], create_fn=_create, preflight_fn=_preflight_ok) == 1
        assert json.loads(capsys.readouterr().err) == {"error": "거부 사유"}

    def test_unexpected_exception_keeps_type_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        """침묵 실패 금지 — 예외 타입명이 stderr에 남아야 한다(무타입 경고 금지 규칙)."""

        async def _create(_email: str) -> dict[str, Any]:
            raise RuntimeError("boom")

        assert cli.main(["create", _EMAIL], create_fn=_create, preflight_fn=_preflight_ok) == 1
        assert "RuntimeError" in json.loads(capsys.readouterr().err)["error"]

    def test_preflight_failure_blocks_before_runner(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """프리플라이트가 막으면 러너는 아예 불리지 않는다(스키마 불일치 시 쓰기 0)."""
        called: list[str] = []

        async def _create(email: str) -> dict[str, Any]:  # pragma: no cover — 불리면 실패
            called.append(email)
            return {}

        async def _preflight_bad() -> None:
            raise cli.SchemaPreflightError("컬럼 없음")

        assert cli.main(["create", _EMAIL], create_fn=_create, preflight_fn=_preflight_bad) == 1
        assert called == []
        assert json.loads(capsys.readouterr().err) == {"error": "컬럼 없음"}


# ===========================================================================
# ③ bootstrap_account — mutate만, commit 없음 / email_hash 재사용 계약
# ===========================================================================


class TestBootstrapAccount:
    @pytest.mark.asyncio
    async def test_creates_new_user_without_commit(self) -> None:
        session = _FakeSession(existing=None)
        user, created = await cli.bootstrap_account(session, email=_EMAIL)  # type: ignore[arg-type]
        assert created is True
        assert session.added == [user]
        assert session.committed is False, "commit은 호출자의 몫이다"
        assert user.persona_primary is _DEFAULT_PERSONA

    @pytest.mark.asyncio
    async def test_existing_user_is_returned_and_not_added(self) -> None:
        existing = UserProfile(
            user_id=uuid.uuid4(),
            email_hash=email_hash(_EMAIL),
            persona_primary=_DEFAULT_PERSONA,
        )
        session = _FakeSession(existing=existing)
        user, created = await cli.bootstrap_account(session, email=_EMAIL)  # type: ignore[arg-type]
        assert created is False
        assert user is existing
        assert session.added == []

    @pytest.mark.asyncio
    async def test_email_hash_matches_login_path(self) -> None:
        """★ 핵심 계약 — 이 CLI가 넣는 email_hash가 로그인 경로(`resolve_user`)의 조회 키와 같다.

        이게 깨지면 나중에 같은 이메일로 로그인했을 때 `resolve_user`가 이 행을 못 찾고 새
        계정을 만들며, 부여해 둔 좌석은 아무도 쓰지 않는 유령 행에 남는다.
        """
        session = _FakeSession(existing=None)
        user, _ = await cli.bootstrap_account(session, email=_EMAIL)  # type: ignore[arg-type]
        assert user.email_hash == email_hash(_EMAIL)

    @pytest.mark.asyncio
    async def test_email_is_normalized_like_login_path(self) -> None:
        """대소문자가 달라도 같은 계정이어야 한다 — email_hash가 소문자 정규화하기 때문."""
        session = _FakeSession(existing=None)
        user, _ = await cli.bootstrap_account(session, email="OPERATOR@Example.COM")  # type: ignore[arg-type]
        assert user.email_hash == email_hash(_EMAIL)

    @pytest.mark.asyncio
    async def test_birth_year_is_not_invented(self) -> None:
        """`is_minor`는 서버가 birth_year에서 파생하는 값이다 — 여기서 지어내지 않는다."""
        session = _FakeSession(existing=None)
        user, _ = await cli.bootstrap_account(session, email=_EMAIL)  # type: ignore[arg-type]
        assert user.birth_year is None
        assert user.is_minor is None


# ===========================================================================
# ④ 프리플라이트 판정 — 순수 함수
# ===========================================================================


class TestJudgeSchemaReadiness:
    def test_no_missing_columns_passes(self) -> None:
        assert cli.judge_schema_readiness(()) is None

    @pytest.mark.parametrize(
        "missing", [("email_hash",), ("persona_primary",), ("email_hash", "persona_primary")]
    )
    def test_missing_columns_name_them_and_the_action(self, missing: tuple[str, ...]) -> None:
        message = cli.judge_schema_readiness(missing)
        assert message is not None
        for name in missing:
            assert f"user_profile.{name}" in message
        assert "alembic upgrade head" in message, "행동 지시가 없으면 소음 실패다"
