"""운영자 계정 부트스트랩 *ops CLI* — 이메일로 `UserProfile` 1행을 멱등 생성(ADMIN-11).

배경
----
2026-08-31 `G-operator-seat-first-grant` 4단계에서 드러났다: whymath-pg의 `user_profile`이
**0행**이라 `role_grant_cli grant`에 줄 대상 자체가 없었다(`list`가 exit 0에
`{"users": [], "total": 0}` — CLI는 정상, 대상이 부재). 저장소 전체에서 `UserProfile`을
만드는 경로는 `api/auth.py`의 `resolve_user` 하나뿐이고 그것은 OAuth 콜백에서만 불린다.
즉 provider를 붙이기 전에는 **아무 계정도 존재할 수 없고**, 따라서 좌석도 발급할 수 없다.
이 CLI가 그 부트스트랩 구멍을 메운다(`role_grant_cli`·`retention_purge_cli` ops 컨벤션
미러: HTTP 미노출·운영자가 셸에서 직접 실행).

사용법
------
    python -m whymath_backend.ops.account_bootstrap_cli create 사람이메일@example.com

**`email_hash`를 `api/auth.py`에서 그대로 재사용하는 것이 이 모듈의 핵심 계약이다.**
그 함수는 비밀값 없는 순수 `sha256(소문자 이메일)`이라 결정론적이고, 같은 이메일로 나중에
실제 OAuth 로그인을 하면 `resolve_user`가 `email_hash`로 조회해 **이 CLI가 만든 바로 그 행**을
찾는다 — 부여해 둔 좌석이 그대로 유지된다. 값을 복제하면(같은 알고리즘을 여기 다시 구현하면)
두 경로가 조용히 갈라질 수 있으므로 import로 묶는다(단일 진실원천).

권한은 만들지 않는다
--------------------
생성되는 계정의 `role`은 DB 기본값 `student`다. `content_admin` 부여는 `role_grant_cli grant`가
단독 담당하며 그쪽이 `privacy_audit.role_change` 감사 1행을 같은 트랜잭션으로 남긴다. 이 CLI가
role을 직접 쓰면 **권한 변경의 감사 경로가 둘로 갈라진다** — 그래서 쓰지 않는다.

멱등
----
같은 이메일로 두 번 돌려도 계정이 2개가 되지 않는다. 2회차는 기존 행의 `user_id`를 그대로
돌려주고 `created=false`를 낸다(`resolve_user`의 upsert 의미와 동형).

거부(비0 종료코드 + 사유 stderr, 커밋 0):
  - 스키마 프리플라이트 실패 → `SchemaPreflightError`(exit 1)
  - `@`가 없는 등 이메일 형태가 아닌 인자 → argparse 단계에서 거부(SystemExit(2))
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

# `email_hash`·`_DEFAULT_PERSONA`는 로그인 경로(`api/auth.py`)의 값을 **재사용**한다 — 이 CLI가
# 만든 행과 장차 OAuth 로그인이 만드는 행이 같아야 하기 때문이다. ops가 api의 상수를 가져오는
# 선례: `ops/repeat_recommendation_report.py`(api.me), `ops/dialogue_encryption_preflight.py`.
from whymath_backend.api.auth import _DEFAULT_PERSONA, email_hash
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import dispose_engine, get_sessionmaker

__all__ = [
    "AccountBootstrapError",
    "CreateFn",
    "PreflightFn",
    "SchemaPreflightError",
    "bootstrap_account",
    "judge_schema_readiness",
    "main",
]

# 이 CLI가 실제로 읽고 쓰는 컬럼 — 프리플라이트가 *직접* 실재를 확인하는 대상이다.
# `user_id`·`role`은 서버 기본값이 있어 INSERT에서 생략되지만, 아래 둘은 이 코드가 값을 넣는다.
_REQUIRED_COLUMNS: tuple[str, ...] = ("email_hash", "persona_primary")


class AccountBootstrapError(Exception):
    """계정 생성 거부 사유(현재는 없음 — 멱등이라 중복도 거부가 아니다).

    자리는 비워 두지 않고 둔다: 장차 거부 조건(도메인 허용목록 등)이 생기면 `RoleGrantError`와
    같은 모양으로 exit 1 + stderr 사유가 되도록 `main()`이 이미 잡고 있다.
    """


class SchemaPreflightError(Exception):
    """DB 스키마가 이 코드와 맞지 않아 실행할 수 없는 상태.

    `role_grant_cli.SchemaPreflightError`와 같은 취지다 — 2026-08-11 실측 사고에서
    마이그레이션이 뒤처진 DB에 ops CLI를 돌리자 `column ... does not exist`가 raw
    트레이스백 100여 줄로 터졌다. 운영자는 거기서 "무엇을 해야 하는지"를 읽어낼 수 없다.
    이 예외는 그 상태를 실행 *전에* 잡아 한 줄의 행동 지시로 바꾼다.
    """


# 계정 생성 좌석 — 기본은 실 DB(단일 TX·커밋), 테스트는 합성 함수를 주입해 DB 없이 CLI 배선
# (인자 파싱·거부 경로·JSON 직렬화·종료 코드)을 검증한다(`role_grant_cli.GrantFn` 미러).
CreateFn = Callable[[str], Coroutine[Any, Any, dict[str, Any]]]
PreflightFn = Callable[[], Coroutine[Any, Any, None]]


async def bootstrap_account(session: AsyncSession, *, email: str) -> tuple[UserProfile, bool]:
    """이메일에 대응하는 `UserProfile`을 찾거나 만들고 `(user, created)`를 돌려준다.

    `session.commit()`은 하지 않는다 — 커밋은 호출자의 몫이다(`role_grant_cli.
    apply_role_change`의 "mutate만 하고 commit은 호출자" 계약과 동형).

    조회 키는 `email_hash(email)`이며 이 함수는 `api/auth.py`의 것을 그대로 쓴다.
    `persona_primary`가 NOT NULL이라 로그인 경로와 **같은 기본 페르소나**로 채운다.
    `birth_year`는 넣지 않는다 — `is_minor`는 서버가 `birth_year`에서 파생하는 값이고
    (외부 입력 미신뢰·`consent.py` 단일 진실), 여기서 알 수 없는 값을 지어내면 그 파생
    계약을 우회하게 된다. 미상(None)은 동의 게이트를 막지 않는다.
    """
    digest = email_hash(email)
    existing = await session.scalar(select(UserProfile).where(UserProfile.email_hash == digest))
    if isinstance(existing, UserProfile):
        return existing, False
    user = UserProfile(
        user_id=uuid.uuid4(),
        email_hash=digest,
        persona_primary=_DEFAULT_PERSONA,
    )
    session.add(user)
    return user, True


async def _default_create_fn(email: str) -> dict[str, Any]:  # pragma: no cover — 실 DB
    """기본 create — 없으면 만들고, 있으면 그대로. 한 트랜잭션으로 커밋.

    **커밋 뒤 `refresh`가 필요한 이유**(2026-08-31 예행연습 실측): `role`은 이 코드가 값을
    넣지 않고 DB의 `server_default`가 채운다. 그래서 INSERT 직후의 ORM 객체는 그 값을 모르고,
    커밋 전에 읽으면 1회차만 `null`이 나온다 — *같은 상태를 회차에 따라 다른 값으로 보고하는*
    출력이 된다(2회차는 조회 경로라 `student`가 나왔다). 커밋은 속성을 만료시키고 async에서
    만료 속성 접근은 lazy load를 유발하므로, 명시적으로 한 번 다시 읽는다.
    """
    async with get_sessionmaker()() as session:
        user, created = await bootstrap_account(session, email=email)
        await session.commit()
        await session.refresh(user)
        return {"user_id": str(user.user_id), "created": created, "role": user.role.value}


def judge_schema_readiness(missing_columns: tuple[str, ...] | list[str]) -> str | None:
    """스키마 준비 판정(순수 — DB 무관·단위 시험 가능). 문제 없으면 `None`.

    판정의 정본은 `alembic_version`이 **아니라** 컬럼의 실재다. 버전 테이블에는 무엇이든
    적혀 있을 수 있다 — whymath-pg는 실제로 코드 체인에 없는 `d6e7f8a9b0c1`을 들고 있었고,
    그 값만 보는 프리플라이트는 정작 컬럼이 없는 상태를 통과시켰다(CLAUDE.md "간접 신호를
    성공 판정으로 쓰기 금지"·`role_grant_cli.judge_schema_readiness` 동일 교훈).
    """
    missing = tuple(missing_columns)
    if not missing:
        return None
    listed = ", ".join(f"user_profile.{name}" for name in missing)
    return (
        f"DB에 필요한 컬럼이 없습니다: {listed} — 이 CLI가 그 컬럼에 값을 씁니다. "
        "먼저 `alembic upgrade head`를 적용하세요(대상 DB가 맞는지 `alembic current`로 "
        "먼저 대조할 것)."
    )


async def _default_preflight_fn() -> None:  # pragma: no cover — 실 DB
    """이 CLI가 쓰는 컬럼의 실재를 실행 *전에* 확인한다.

    확인 자체가 실패하면 "통과"로 위장하지 않는다(측정 실패 ≠ 정상). 예외 타입명을 메시지에
    실어 침묵 실패를 막는다.

    `finally: dispose_engine()` — `main()`이 프리플라이트와 본 명령을 **서로 다른**
    `asyncio.run()`으로 돌리므로 여기서 만든 asyncpg 풀을 살려두면 다음 루프가 그 커넥션을
    물려받아 "attached to a different loop"로 죽는다(`role_grant_cli` 2026-08-11 실측).
    """
    from sqlalchemy import text

    try:
        async with get_sessionmaker()() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'user_profile'"
                    )
                )
            ).scalars()
            present = {str(name) for name in rows}
    except Exception as exc:
        raise SchemaPreflightError(
            f"DB 스키마를 확인하지 못했습니다({type(exc).__name__}) — "
            "DB 도달성(WHYMATH_DATABASE_URL)과 접근 권한을 확인하세요."
        ) from exc
    finally:
        await dispose_engine()

    message = judge_schema_readiness(tuple(c for c in _REQUIRED_COLUMNS if c not in present))
    if message is not None:
        raise SchemaPreflightError(message)


def _email_arg(value: str) -> str:
    """최소 형태 검사 — 오타로 UUID나 빈 문자열을 넣는 사고만 막는다(정규식 검증 아님).

    이메일의 유효성은 결국 provider가 판정한다. 여기서 과도하게 좁히면 정상 주소를 거부하는
    쪽이 더 흔한 실패가 되므로, `@`를 낀 공백 없는 문자열만 통과시킨다.
    """
    candidate = value.strip()
    local, _, domain = candidate.partition("@")
    if not local or not domain or any(ch.isspace() for ch in candidate):
        raise argparse.ArgumentTypeError(f"이메일 형태가 아닙니다: {value!r}")
    return candidate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.account_bootstrap_cli",
        description=(
            "운영자 계정 부트스트랩 — 이메일로 user_profile 1행을 멱등 생성"
            "(HTTP 미노출, 운영자 직접 실행). 권한 부여는 role_grant_cli가 담당."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    create_p = sub.add_parser(
        "create", help="이메일에 대응하는 계정을 만들거나 기존 것을 반환한다."
    )
    create_p.add_argument("email", type=_email_arg, help="장차 OAuth 로그인에 쓸 이메일 주소")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    create_fn: CreateFn = _default_create_fn,
    preflight_fn: PreflightFn = _default_preflight_fn,
) -> int:
    """CLI 엔트리 — create 서브커맨드. 결과를 JSON으로 stdout, 거부는 stderr.

    반환 종료 코드: 0(성공) / 1(런타임 거부 — 스키마 프리플라이트 실패·그 밖의 DB 오류) /
    2(argparse 파싱 실패 — 이메일 형태 아님, argparse가 자체적으로 stderr+SystemExit(2)).

    예상 못 한 DB 예외도 타입명과 함께 한 줄 JSON으로 바꾼다 — 트레이스백을 운영자에게
    떠넘기지 않는다(`role_grant_cli.main` 동형).
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
        result = asyncio.run(create_fn(args.email))
    except AccountBootstrapError as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 — 침묵 실패 금지: 타입명을 남기고 종료 코드로 판정
        return _fail(f"실행 실패({type(exc).__name__}): {exc}")

    print(json.dumps(result))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
