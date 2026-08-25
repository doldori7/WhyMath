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

from whymath_backend.audit.event_bus import emit_identity_event
from whymath_backend.config import get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import dispose_engine, get_sessionmaker
from whymath_backend.privacy.audit import record_role_change_audit
from whymath_backend.schema.enums import AuditEventAuthorization, AuditEventSeverity, Role

__all__ = [
    "GrantFn",
    "ListFn",
    "PreflightFn",
    "RevokeFn",
    "RoleGrantError",
    "SchemaPreflightError",
    "apply_role_change",
    "judge_schema_readiness",
    "main",
]

# 기본(비권한) 역할 — revoke의 되돌림 대상(`schema/enums.py` Role.STUDENT "기본 역할" 정의와 동일
# 진실원천). Role이 2값뿐이라 지금은 상수 하나로 충분하지만, 장차 역할이 늘어도 "revoke = 기본
# 역할로 복귀"라는 의미는 변하지 않으므로 이름 있는 상수로 분리해둔다(매직 melting 방지).
_BASE_ROLE = Role.STUDENT


class RoleGrantError(Exception):
    """grant/revoke 거부 사유 — 존재하지 않는 user_id, 또는 revoke 시 역할 불일치."""


class SchemaPreflightError(Exception):
    """DB 스키마가 이 코드와 맞지 않아 어떤 서브커맨드도 실행할 수 없는 상태.

    2026-08-11 실측 사고: 이 CLI를 마이그레이션이 뒤처진 DB에 실행하자
    `column user_profile.role does not exist`가 **raw SQLAlchemy 트레이스백 100여 줄**로
    터졌다. 운영자는 그 출력에서 "무엇을 해야 하는지"를 읽어낼 수 없다 — CLAUDE.md가 금지하는
    *침묵 실패*의 반대편인 **소음 실패**다(정보가 있어도 행동으로 이어지지 않으면 같은 실패).

    이 예외는 그 상태를 실행 *전에* 잡아 한 줄의 행동 지시로 바꾼다.
    """


# grant/revoke/list 좌석 — 기본은 실 DB(단일 TX·커밋), 테스트는 합성 함수를 주입해 DB 없이
# CLI 배선(인자 파싱·거부 경로·JSON 직렬화·종료 코드)을 검증한다(`retention_purge_cli.PurgeFn`
# 미러).
GrantFn = Callable[[uuid.UUID, Role], Coroutine[Any, Any, dict[str, str]]]
RevokeFn = Callable[[uuid.UUID, Role], Coroutine[Any, Any, dict[str, str]]]
ListFn = Callable[[], Coroutine[Any, Any, list[dict[str, str]]]]
# 스키마 프리플라이트 좌석 — 실 DB 왕복이라 hermetic 테스트는 합성 함수를 주입한다.
PreflightFn = Callable[[], Coroutine[Any, Any, None]]


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
        emit_identity_event(
            session,
            action="iam.role.assign",
            actor_id=None,
            resource_id=user_id,
            source_service="role_grant_cli",
            authorization_decision=AuditEventAuthorization.allow,
            severity=AuditEventSeverity.high,
            metadata={"old_role": old_role.value, "new_role": role.value},
        )
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
        emit_identity_event(
            session,
            action="iam.role.revoke",
            actor_id=None,
            resource_id=user_id,
            source_service="role_grant_cli",
            authorization_decision=AuditEventAuthorization.allow,
            severity=AuditEventSeverity.high,
            metadata={"old_role": old_role.value, "new_role": _BASE_ROLE.value},
        )
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


def judge_schema_readiness(
    applied_heads: tuple[str, ...] | list[str],
    *,
    role_column_exists: bool,
) -> str | None:
    """스키마 준비 판정(순수 — DB 무관·단위 시험 가능). 문제 없으면 `None`.

    **판정 순서가 설계의 핵심**이다. 1차는 *직접 신호*(`user_profile.role` 실재), 2차가
    *간접 신호*(`alembic_version`). 첫 구현은 순서가 반대였고 그래서 실제 사고를 못 잡았다 —
    대상 DB의 기록 head가 `d6e7f8a9b0c1`(이 코드가 모르는 값)이라 `AHEAD`로 분류됐고,
    AHEAD는 정상 롤백이라 통과시키는데 **컬럼은 실제로 없었다**. 버전 테이블에는 무엇이든
    적혀 있을 수 있다(CLAUDE.md "간접 신호를 성공 판정으로 쓰기 금지").
    """
    from whymath_backend.db.schema_version import (
        EXPECTED_ALEMBIC_HEAD,
        SchemaVersionVerdict,
        classify_applied_head,
    )

    heads = tuple(applied_heads)
    applied_desc = ", ".join(heads) if heads else "(미적용)"
    if len(heads) > 1:
        verdict = (
            SchemaVersionVerdict.MATCH
            if EXPECTED_ALEMBIC_HEAD in heads
            else SchemaVersionVerdict.BEHIND
        )
    else:
        verdict = classify_applied_head(heads[0] if heads else None)

    # ── 1차: 직접 신호. 버전 테이블이 무엇을 말하든 이쪽이 정본이다. ──
    if not role_column_exists:
        if verdict is SchemaVersionVerdict.AHEAD:
            hint = (
                f" 기록된 head `{applied_desc}`는 **이 코드의 마이그레이션 체인에 없는 값**이라"
                " `alembic upgrade head`가 'Can't locate revision'으로 거부됩니다(실측) —"
                " 임의로 stamp하지 말고 실제 스키마 상태를 먼저 확인하세요."
            )
        else:
            hint = " 먼저 `alembic upgrade head`를 적용하세요."
        return (
            f"`user_profile.role` 컬럼이 DB에 없습니다 — 이 CLI의 모든 서브커맨드가 그 컬럼을 "
            f"읽습니다. 기록된 head={applied_desc} / 코드 기대={EXPECTED_ALEMBIC_HEAD}.{hint}"
        )

    # ── 2차: 컬럼은 있지만 스키마가 뒤처진 경우(다른 신규 컬럼이 빌 수 있다). ──
    if verdict is SchemaVersionVerdict.BEHIND:
        return (
            f"DB 스키마가 코드보다 뒤처졌습니다 — 적용={applied_desc} / 코드 기대="
            f"{EXPECTED_ALEMBIC_HEAD}. 먼저 `alembic upgrade head`를 적용하세요 "
            f"(대상 DB가 맞는지 `alembic current`로 먼저 대조할 것)."
        )
    # AHEAD 자체는 막지 않는다 — 필요한 컬럼의 실재를 위에서 직접 확인했고, 코드만 되돌린
    # 정상 롤백에서 막으면 가드가 장애 원인이 된다(verify_schema_version 동일 판단 승계).
    return None


async def _default_preflight_fn() -> None:  # pragma: no cover — 실 DB(integration)
    """DB 스키마가 이 코드의 기대 head와 일치하는지 *실행 전에* 확인한다.

    **`verify_schema_version()`을 쓰지 않는 이유**(실측 판단): 그 함수는 `is_production_like`
    (실 OAuth provider 구성 여부)가 True일 때만 raise하고, 그 밖에서는 **경고 로그만 남기고
    통과**시킨다. 운영자가 PowerShell에서 `WHYMATH_DATABASE_URL`만 지정하고 이 CLI를 돌리면
    provider가 미구성이라 `production_like=False`가 되어 **뒤처진 스키마인데도 통과**한다 —
    프리플라이트로서 변별력이 없다. 그래서 환경에 의존하지 않는 하위 순수 함수
    (`read_applied_heads` + `classify_applied_head`)를 직접 조합한다.

    좌석 부여는 *어느 환경에서든* 스키마가 맞아야 한다 — 여기서 환경에 따라 판정이 갈리면
    안 된다.

    **판정의 정본은 `alembic_version`이 아니라 `user_profile.role`의 실재다**(2026-08-11 2차
    실측 교훈). 첫 구현은 버전 테이블만 봤는데, 실제 대상 DB의 head가 `d6e7f8a9b0c1` —
    *이 코드가 모르는 리비전*이었다. 그 값은 `classify_applied_head`가 `AHEAD`로 분류하고
    AHEAD는 정상 롤백이라 통과시키므로, **버전 테이블만 보는 프리플라이트는 바로 그 사고를
    못 잡는다**(컬럼은 실제로 없는데 통과). 버전 테이블은 *다른 무엇이든 적혀 있을 수 있는*
    간접 신호다 — CLAUDE.md "간접 신호를 성공 판정으로 쓰기 금지"에 정확히 해당한다.
    그래서 **이 CLI가 실제로 필요로 하는 컬럼의 존재를 직접 확인**하고, 버전 정보는 안내
    메시지를 풍부하게 하는 부가 재료로만 쓴다.

    Raises:
        SchemaPreflightError: 필요한 컬럼이 없거나, 스키마가 뒤처졌거나(BEHIND), 확인 자체가
            실패한 경우. 확인 실패를 "통과"로 위장하지 않는다(측정 실패 ≠ 정상).
    """
    from sqlalchemy import text

    from whymath_backend.db.schema_version import (
        read_applied_heads,
    )

    try:
        async with get_sessionmaker()() as session:
            applied_heads = await read_applied_heads(session)
            # 직접 신호 — 이 CLI가 실제로 읽고 쓰는 컬럼이 있는가.
            role_column_exists = bool(
                (
                    await session.execute(
                        text(
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_name = 'user_profile' AND column_name = 'role'"
                        )
                    )
                ).first()
            )
    except Exception as exc:
        raise SchemaPreflightError(
            f"DB 스키마 버전을 확인하지 못했습니다({type(exc).__name__}) — "
            f"DB 도달성(WHYMATH_DATABASE_URL)과 `alembic_version` 접근 권한을 확인하세요."
        ) from exc
    finally:
        # 전역 엔진을 반드시 정리한다 — `main()`이 프리플라이트와 본 명령을 **서로 다른**
        # `asyncio.run()`으로 돌리므로, 여기서 만든 asyncpg 풀을 살려두면 다음 루프가 그 커넥션을
        # 물려받아 "attached to a different loop"로 죽는다(2026-08-11 실측: 프리플라이트를 붙인
        # 직후 `upgrade head` 뒤의 `list`가 바로 이 오류로 실패했다 — 통합 테스트는
        # `WHYMATH_DB_DISABLE_POOL=1`로 이 함정을 우회하고 있어 잡히지 않았다).
        # `recommendation_reach_report.py`의 `finally: await dispose_engine()` 선례와 동형.
        await dispose_engine()

    message = judge_schema_readiness(applied_heads, role_column_exists=role_column_exists)
    if message is not None:
        raise SchemaPreflightError(message)


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
    preflight_fn: PreflightFn = _default_preflight_fn,
) -> int:
    """CLI 엔트리 — grant/revoke/list 서브커맨드. 결과를 JSON으로 stdout, 거부는 stderr.

    반환 종료 코드: 0(성공) / 1(런타임 거부 — 스키마 프리플라이트 실패·사용자 없음·역할 불일치·
    그 밖의 DB 오류) / 2(argparse 파싱 실패 — 잘못된 UUID·알 수 없는 역할명, argparse가
    자체적으로 stderr+SystemExit(2)를 낸다).

    **세 서브커맨드 전부가 DB를 왕복하므로 프리플라이트를 공통 선행**시킨다(2026-08-11 사고:
    `list`는 아예 try 블록이 없어 raw 트레이스백이 그대로 나왔다). 예상 못 한 DB 예외도
    타입명과 함께 한 줄 JSON으로 바꾼다 — 트레이스백을 운영자에게 떠넘기지 않는다.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    def _fail(message: str) -> int:
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1

    try:
        asyncio.run(preflight_fn())
    except SchemaPreflightError as exc:
        return _fail(str(exc))

    try:
        if args.command == "grant":
            result = asyncio.run(grant_fn(args.user_id, args.role))
        elif args.command == "revoke":
            result = asyncio.run(revoke_fn(args.user_id, args.role))
        else:  # command == "list"
            users = asyncio.run(list_fn())
            print(json.dumps({"users": users, "total": len(users)}))
            return 0
    except RoleGrantError as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 — 침묵 실패 금지: 타입명을 남기고 종료 코드로 판정
        return _fail(f"실행 실패({type(exc).__name__}): {exc}")

    print(json.dumps(result))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
