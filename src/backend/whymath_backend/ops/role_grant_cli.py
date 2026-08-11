"""운영자 좌석 발급 *ops CLI* — `user_profile.role` 부여/회수/조회(ADMIN-01).

배경
----
`require_content_admin`(`api/_auth.py`)이 콘텐츠 CUD 라우터 6개(`/v1/concepts`·`/v1/problems`의
POST/PATCH/DELETE)를 `Role.CONTENT_ADMIN`으로 게이팅하지만, 그 역할을 실제 사용자에게 *부여하는
경로가 저장소 전체에 0건*이었다(`resolve_user`는 role kwarg 없이 사용자를 만들고, `.role =` 대입은
어디에도 없다 — grep 무일치). 이 CLI가 그 첫 발급·회수 표면이다(`retention_purge_cli` ops 컨벤션
미러: HTTP 미노출·운영자가 셸에서 직접 실행).

사용법
------
    python -m whymath_backend.ops.role_grant_cli grant  <user_id> <role>
    python -m whymath_backend.ops.role_grant_cli revoke <user_id> <role>
    python -m whymath_backend.ops.role_grant_cli list

동작
----
`grant`: 지정 사용자의 `role`을 인자로 준 값으로 바꾸고, 역할 변경 + `privacy_audit.role_change`
감사 1행 적재를 *같은 트랜잭션*으로 커밋한다(부분 성공 0 — `apply_role_change`가 mutate만 하고
`record_role_change_audit`이 `session.add()`만 한 뒤, 이 모듈의 기본 함수가 단일 `session.commit()`
을 호출한다). `revoke`: 지정 역할을 사용자가 **현재 보유하고 있을 때만** 기본 역할(`Role.STUDENT`
— `schema/enums.py` "기본 역할" 정의)로 되돌린다(보유하지 않은 역할을 회수하려 하면 거부).
`list`: 기본 역할이 아닌(`role != Role.STUDENT`) 사용자 전원을 반환한다.

거부(비0 종료코드 + 사유 stderr, 커밋 0):
  - 존재하지 않는 `user_id` → `RoleGrantError`("사용자를 찾을 수 없습니다")
  - `revoke`가 현재 역할과 불일치 → `RoleGrantError`("사용자가 보유한 역할이 아닙니다")
  - `role` 인자가 `Role` enum에 없는 문자열 → argparse 파싱 단계에서 거부(SystemExit(2),
    `--as-of` 잘못된 날짜의 `retention_purge_cli` 선례와 동형)

DB 왕복(`_default_grant_fn`/`_default_revoke_fn`/`_default_list_fn`)은 실 PostgreSQL을 요구하므로
단위테스트는 이 함수들을 합성(fake) 함수로 주입해 CLI 배선(인자 파싱·거부·JSON stdout·종료 코드)만
hermetic 검증한다 — 실 DB 왕복(부여 후 role 실제로 바뀜·감사 행 적재·트랜잭션 원자성)은
`@pytest.mark.integration`이 검증한다(`retention_purge_cli`·`test_erasure.py` 선례).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.privacy.audit import record_role_change_audit
from whymath_backend.schema.enums import Role

__all__ = [
    "GrantFn",
    "ListFn",
    "RevokeFn",
    "RoleGrantError",
    "apply_role_change",
    "main",
]

# 기본(비권한) 역할 — revoke의 되돌림 대상(`schema/enums.py` Role.STUDENT "기본 역할" 정의와 동일
# 진실원천). Role이 2값뿐이라 지금은 상수 하나로 충분하지만, 장차 역할이 늘어도 "revoke = 기본
# 역할로 복귀"라는 의미는 변하지 않으므로 이름 있는 상수로 분리해둔다(매직 melting 방지).
_BASE_ROLE = Role.STUDENT


class RoleGrantError(Exception):
    """grant/revoke 거부 사유 — 존재하지 않는 user_id, 또는 revoke 시 역할 불일치."""


# grant/revoke/list 좌석 — 기본은 실 DB(단일 TX·커밋), 테스트는 합성 함수를 주입해 DB 없이
# CLI 배선(인자 파싱·거부 경로·JSON 직렬화·종료 코드)을 검증한다(`retention_purge_cli.PurgeFn`
# 미러).
GrantFn = Callable[[uuid.UUID, Role], Coroutine[Any, Any, dict[str, str]]]
RevokeFn = Callable[[uuid.UUID, Role], Coroutine[Any, Any, dict[str, str]]]
ListFn = Callable[[], Coroutine[Any, Any, list[dict[str, str]]]]


async def apply_role_change(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    new_role: Role,
    expected_current_role: Role | None = None,
) -> Role:
    """`user_id`의 role을 `new_role`로 바꾸고 *이전* role을 반환한다(commit은 호출자).

    `expected_current_role`을 주면(=revoke 경로) 현재 role이 그 값과 다를 때 `RoleGrantError`로
    거부한다(보유하지 않은 역할을 회수하려는 실수 방지). 사용자가 없으면 `RoleGrantError`.
    이 함수는 `session.add`/`session.commit`을 하지 않는다 — ORM 객체 mutate만 하고 실제 UPDATE는
    호출자의 flush/commit에서 나간다(`privacy/audit.py`의 "add만 하고 commit은 호출자" 계약과 동형
    — 역할 변경 + 감사 적재가 같은 트랜잭션으로 원자적이어야 하기 때문).
    """
    user = await session.get(UserProfile, user_id)
    if user is None:
        raise RoleGrantError(f"사용자를 찾을 수 없습니다: {user_id}")
    if expected_current_role is not None and user.role != expected_current_role:
        raise RoleGrantError(
            "사용자가 보유한 역할이 아닙니다(현재: "
            f"{user.role.value}, 회수 요청: {expected_current_role.value})"
        )
    old_role = user.role
    user.role = new_role
    return old_role


async def _default_grant_fn(  # pragma: no cover — 실 DB(integration)
    user_id: uuid.UUID, role: Role
) -> dict[str, str]:
    """기본 grant — role 변경 + role_change 감사 1행을 한 트랜잭션으로 커밋.

    같은 세션·같은 commit이라 감사 함수 호출 이후 커밋 전 어느 예외도 *둘 다* 롤백한다
    (부분 성공 0 — `test_role_grant_cli_integration.py`가 강제 실패로 실측).
    """
    settings = get_settings()
    async with get_sessionmaker()() as session:
        old_role = await apply_role_change(session, user_id=user_id, new_role=role)
        record_role_change_audit(session, user_id=user_id, ip=None, settings=settings)
        await session.commit()
    return {"user_id": str(user_id), "old_role": old_role.value, "new_role": role.value}


async def _default_revoke_fn(  # pragma: no cover — 실 DB(integration)
    user_id: uuid.UUID, role: Role
) -> dict[str, str]:
    """기본 revoke — 보유 확인 후 기본 역할(`Role.STUDENT`)로 되돌리고 감사 1행을 같은 TX로 커밋."""
    settings = get_settings()
    async with get_sessionmaker()() as session:
        old_role = await apply_role_change(
            session, user_id=user_id, new_role=_BASE_ROLE, expected_current_role=role
        )
        record_role_change_audit(session, user_id=user_id, ip=None, settings=settings)
        await session.commit()
    return {"user_id": str(user_id), "old_role": old_role.value, "new_role": _BASE_ROLE.value}


async def _default_list_fn() -> list[dict[str, str]]:  # pragma: no cover — 실 DB(integration)
    """기본 role이 아닌(`role != Role.STUDENT`) 사용자 전원을 `[{user_id, role}, ...]`로 반환."""
    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                select(UserProfile.user_id, UserProfile.role).where(UserProfile.role != _BASE_ROLE)
            )
        ).all()
    return [{"user_id": str(uid), "role": role.value} for uid, role in rows]


def _uuid_arg(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"올바른 UUID가 아닙니다: {value!r}") from exc


def _role_arg(value: str) -> Role:
    try:
        return Role(value)
    except ValueError as exc:
        valid = ", ".join(r.value for r in Role)
        raise argparse.ArgumentTypeError(
            f"알 수 없는 역할입니다: {value!r} (유효값: {valid})"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.role_grant_cli",
        description=(
            "운영자 좌석 발급 — user_profile.role 부여/회수/조회(HTTP 미노출, 운영자 직접 실행)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    grant_p = sub.add_parser("grant", help="지정 사용자에게 역할을 부여한다.")
    grant_p.add_argument("user_id", type=_uuid_arg, help="대상 사용자 UUID")
    grant_p.add_argument("role", type=_role_arg, help="부여할 역할(예: content_admin)")

    revoke_p = sub.add_parser("revoke", help="지정 사용자의 역할을 회수하고 기본 역할로 되돌린다.")
    revoke_p.add_argument("user_id", type=_uuid_arg, help="대상 사용자 UUID")
    revoke_p.add_argument("role", type=_role_arg, help="회수할 역할(현재 보유 역할과 일치해야 함)")

    sub.add_parser("list", help="기본 역할이 아닌 사용자 전원을 나열한다.")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    grant_fn: GrantFn = _default_grant_fn,
    revoke_fn: RevokeFn = _default_revoke_fn,
    list_fn: ListFn = _default_list_fn,
) -> int:
    """CLI 엔트리 — grant/revoke/list 서브커맨드. 결과를 JSON으로 stdout, 거부는 stderr.

    반환 종료 코드: 0(성공) / 1(런타임 거부 — 사용자 없음·역할 불일치) / 2(argparse 파싱 실패 —
    잘못된 UUID·알 수 없는 역할명, argparse가 자체적으로 stderr+SystemExit(2)를 낸다).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "grant":
        try:
            result = asyncio.run(grant_fn(args.user_id, args.role))
        except RoleGrantError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0

    if args.command == "revoke":
        try:
            result = asyncio.run(revoke_fn(args.user_id, args.role))
        except RoleGrantError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0

    # command == "list"
    users = asyncio.run(list_fn())
    print(json.dumps({"users": users, "total": len(users)}))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
