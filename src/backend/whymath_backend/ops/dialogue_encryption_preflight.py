"""대화 암호화 프리플라이트 — 키 주입 *직후 1회* 실행하는 at-rest 암호화 즉석 검증 (SEC-05).

배경
----
배포 체크리스트(§2)는 "앱 기동 후 대화 1건 왕복(생성 → 조회)이 성공한다"만 적고 **방법을
적지 않았다** — 2026-07-27 실측 시도가 그 지점에서 멈췄다. 이 모듈이 그 항목을 단일 명령으로
turnkey화한다(`ops/live_preflight` 선례 — 라이브 키 투입 직후 손끝 검증).

**왕복 성공은 암호화의 증거가 아니다**
--------------------------------------
키가 없으면 코드는 *평문 폴백*으로 동작하고 왕복은 그대로 성공한다. 따라서 왕복만 보면
"암호화됐다"는 잘못된 결론에 이른다. 이 도구는 왕복과 **저장 표현**(암호문/평문 컬럼의
증가분)을 함께 보고, 평문이 늘었으면 실패로 판정한다.

두 모드 — 무엇이 증명되는지가 다르다
------------------------------------
① **direct**(기본) — 서버·토큰 없이 저장 좌석을 직접 태운다. 키 구성·스키마·암복호 경로를
   검증한다. **이 프로세스의 env만 증명하며, 서버 프로세스가 같은 키를 보는지는 증명하지
   않는다** — 다른 셸/다른 env로 절반씩 성립하는 함정이 실제로 있었다(2026-07-16 교훈).
② **--via-api** — *실제 기동 중인 서버*에 HTTP로 대화를 만들고 조회한다. 서버 프로세스가
   키를 실제로 쓰는지 증명하는 **유일한 모드**다. 배포 검증에는 이쪽을 쓴다.

   프로덕션에서는 데모 인증이 거부되므로(`api/demo_auth.register_demo_provider` — 실 OAuth
   구성 시 미등록) **실제 로그인으로 얻은 토큰**을 `--token`으로 넘겨야 한다.

실행
----
    python -m whymath_backend.ops.dialogue_encryption_preflight
    python -m whymath_backend.ops.dialogue_encryption_preflight --via-api \
        --api-url http://127.0.0.1:8000 --token <실제_로그인_토큰>

종료 코드: 0 통과 / 1 실패(평문 저장·왕복 불일치·측정 불가).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - 콘솔 인코딩(Windows) 안전장치, 선례 미러
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

_PROBE_TEXT = "프리플라이트 검증 발화 — 이 행은 검사 후 삭제됩니다"

__all__ = ["EncryptionCounts", "PreflightReport", "main", "run_preflight"]


@dataclass(frozen=True, slots=True)
class EncryptionCounts:
    """`dialogue_turn` 저장 표현 카운트 — 체크리스트 §3 판정 쿼리와 같은 축."""

    content_encrypted: int
    content_plaintext: int
    image_uri_encrypted: int
    image_uri_plaintext: int
    analysis_encrypted: int
    analysis_plaintext: int

    @property
    def encrypted_total(self) -> int:
        return self.content_encrypted + self.image_uri_encrypted + self.analysis_encrypted

    @property
    def plaintext_total(self) -> int:
        return self.content_plaintext + self.image_uri_plaintext + self.analysis_plaintext


@dataclass
class PreflightReport:
    """판정 결과 — 실패는 *사유*를 남긴다(조용한 실패 금지)."""

    mode: str
    key_configured: bool
    round_trip_ok: bool = False
    before: EncryptionCounts | None = None
    after: EncryptionCounts | None = None
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def encrypted_delta(self) -> int | None:
        if self.before is None or self.after is None:
            return None
        return self.after.encrypted_total - self.before.encrypted_total

    @property
    def plaintext_delta(self) -> int | None:
        if self.before is None or self.after is None:
            return None
        return self.after.plaintext_total - self.before.plaintext_total

    @property
    def passed(self) -> bool:
        return not self.failures


# `jsonb_typeof(...) NOT IN ('null')` — SEC-04: JSONB 스칼라 null("분석 없음")을 평문으로
# 계수하면 "암호화 안 됨" 거짓경보가 난다. 체크리스트 §3 쿼리와 동일 술어를 쓴다.
_COUNT_SQL = """
SELECT
  count(*) FILTER (WHERE content_encrypted IS NOT NULL),
  count(*) FILTER (WHERE content IS NOT NULL),
  count(*) FILTER (WHERE image_uri_encrypted IS NOT NULL),
  count(*) FILTER (WHERE image_uri IS NOT NULL),
  count(*) FILTER (WHERE image_analysis_encrypted IS NOT NULL),
  count(*) FILTER (WHERE jsonb_typeof(image_analysis) NOT IN ('null'))
FROM dialogue_turn
"""


async def _read_counts(session: Any) -> EncryptionCounts:
    from sqlalchemy import text

    row = (await session.execute(text(_COUNT_SQL))).one()
    return EncryptionCounts(*(int(value) for value in row))


async def _probe_direct(settings: Any, report: PreflightReport) -> None:
    """서버 없이 저장 좌석을 직접 태워 암호화·복호를 확인하고 흔적을 지운다."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from whymath_backend.api._crypto import (
        require_dialogue_content_cipher,
        resolve_dialogue_content,
    )
    from whymath_backend.api.coach import _build_dialogue_turn
    from whymath_backend.schema.dialogue import DialogueTurn as DialogueTurnSchema

    engine = create_async_engine(settings.database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    dialogue_id = uuid.uuid4()
    try:
        async with sessionmaker() as session:
            report.before = await _read_counts(session)

        cipher = require_dialogue_content_cipher(settings)
        async with sessionmaker() as session:
            await session.execute(
                text("INSERT INTO dialogue (dialogue_id) VALUES (:d)"), {"d": str(dialogue_id)}
            )
            session.add(
                _build_dialogue_turn(
                    DialogueTurnSchema(dialogue_id=dialogue_id, turn_order=1, content=_PROBE_TEXT),
                    cipher,
                )
            )
            await session.commit()

        async with sessionmaker() as session:
            report.after = await _read_counts(session)
            stored = (
                await session.execute(
                    text(
                        "SELECT content, content_encrypted, content_nonce FROM dialogue_turn "
                        "WHERE dialogue_id = :d"
                    ),
                    {"d": str(dialogue_id)},
                )
            ).one()
            restored = resolve_dialogue_content(cipher, stored[0], stored[1], stored[2])
            report.round_trip_ok = restored == _PROBE_TEXT
    finally:
        try:  # 프로브 흔적 제거 — 실패해도 판정은 유지하되 사유를 남긴다(조용한 실패 금지)
            async with sessionmaker() as session:
                await session.execute(
                    text("DELETE FROM dialogue_turn WHERE dialogue_id = :d"),
                    {"d": str(dialogue_id)},
                )
                await session.execute(
                    text("DELETE FROM dialogue WHERE dialogue_id = :d"), {"d": str(dialogue_id)}
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            report.notes.append(
                f"프로브 행 정리 실패({type(exc).__name__}) — "
                f"dialogue_id={dialogue_id} 수동 삭제 필요"
            )
        await engine.dispose()


async def _probe_via_api(settings: Any, api_url: str, token: str, report: PreflightReport) -> None:
    """실제 기동 중인 서버에 HTTP로 왕복 — *서버 프로세스가 키를 쓰는지*를 증명하는 모드."""
    import httpx
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    dialogue_id: uuid.UUID | None = None
    try:
        async with sessionmaker() as session:
            report.before = await _read_counts(session)

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(base_url=api_url.rstrip("/"), timeout=60.0) as client:
            created = await client.post(
                "/v1/coach/sessions", headers=headers, json={"student_input": _PROBE_TEXT}
            )
            if created.status_code != 201:
                report.failures.append(
                    f"대화 생성 실패 — HTTP {created.status_code}. 토큰·서버 주소를 확인하세요"
                    "(프로덕션은 데모 토큰이 거부되므로 실제 로그인 토큰이 필요합니다)."
                )
                return
            dialogue_id = uuid.UUID(created.json()["dialogue_id"])
            fetched = await client.get(f"/v1/coach/sessions/{dialogue_id}", headers=headers)
            if fetched.status_code != 200:
                report.failures.append(f"대화 조회 실패 — HTTP {fetched.status_code}.")
                return
            turns = fetched.json()["turns"]
            report.round_trip_ok = any(turn.get("content") == _PROBE_TEXT for turn in turns)

        async with sessionmaker() as session:
            report.after = await _read_counts(session)
    finally:
        if dialogue_id is not None:
            try:
                async with sessionmaker() as session:
                    await session.execute(
                        text("DELETE FROM dialogue_turn WHERE dialogue_id = :d"),
                        {"d": str(dialogue_id)},
                    )
                    await session.execute(
                        text("DELETE FROM dialogue WHERE dialogue_id = :d"), {"d": str(dialogue_id)}
                    )
                    await session.commit()
            except Exception as exc:  # noqa: BLE001
                report.notes.append(
                    f"프로브 행 정리 실패({type(exc).__name__}) — "
                    f"dialogue_id={dialogue_id} 수동 삭제 필요"
                )
        await engine.dispose()


def _judge(report: PreflightReport) -> None:
    """수집된 관측에 판정을 붙인다 — 실패 사유는 *무엇을 고쳐야 하는지*까지 적는다."""
    if not report.round_trip_ok:
        report.failures.append(
            "왕복 불일치 — 저장한 발화가 그대로 복원되지 않았습니다(암·복호 경로 점검)."
        )
    encrypted_delta = report.encrypted_delta
    plaintext_delta = report.plaintext_delta
    if encrypted_delta is None or plaintext_delta is None:
        report.failures.append("저장 표현을 측정하지 못했습니다 — 통과로 간주하지 않습니다.")
        return
    if plaintext_delta > 0:
        # via-api에서 평문이 늘었다면 범인은 *서버* 프로세스다 — CLI에 키가 있어도(키 구성: 예)
        # 서버가 못 보면 이렇게 된다. 2026-07-16 "서로 다른 env로 절반씩 성립" 함정의 검출점이라
        # 어느 프로세스를 고쳐야 하는지 메시지에 명시한다.
        culprit = "서버 프로세스" if report.mode == "via-api" else "이 프로세스"
        report.failures.append(
            f"평문 저장이 늘었습니다(+{plaintext_delta}) — 키가 {culprit}에 실제로 붙지 "
            "않았습니다(오타·프로세스 미재시작·다른 env 파일 로드)."
        )
    if encrypted_delta <= 0:
        report.failures.append(
            "암호문이 늘지 않았습니다 — 프로브 행이 생성되지 않았거나 암호화가 비활성입니다."
        )


def run_preflight(
    settings: Any, *, via_api: bool = False, api_url: str = "", token: str = ""
) -> PreflightReport:
    """프리플라이트 1회 실행 — 관측 후 판정된 리포트를 돌려준다."""
    from whymath_backend.api._crypto import build_dialogue_content_cipher

    mode = "via-api" if via_api else "direct"
    report = PreflightReport(
        mode=mode, key_configured=build_dialogue_content_cipher(settings) is not None
    )
    if not report.key_configured:
        report.failures.append(
            "`WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY`가 이 프로세스에 설정돼 있지 않습니다."
        )
    if not via_api:
        report.notes.append(
            "direct 모드 — 이 프로세스의 env만 증명합니다. 서버가 같은 키를 쓰는지는 "
            "`--via-api`로만 확인됩니다."
        )
    try:
        if via_api:
            asyncio.run(_probe_via_api(settings, api_url, token, report))
        else:
            asyncio.run(_probe_direct(settings, report))
    except Exception as exc:  # noqa: BLE001
        report.failures.append(f"프로브 실행 실패({type(exc).__name__}) — {exc}")
    _judge(report)
    return report


def _render(report: PreflightReport) -> str:
    enc = report.encrypted_delta if report.encrypted_delta is not None else "측정 실패"
    plain = report.plaintext_delta if report.plaintext_delta is not None else "측정 실패"
    lines = [
        "── 대화 암호화 프리플라이트 (SEC-05) ─────────────────────────",
        f"  모드          : {report.mode}",
        f"  키 구성       : {'예' if report.key_configured else '아니오'}",
        f"  왕복 일치     : {'예' if report.round_trip_ok else '아니오'}",
        f"  암호문 증가   : {enc}",
        f"  평문 증가     : {plain}",
    ]
    for note in report.notes:
        lines.append(f"  · {note}")
    for failure in report.failures:
        lines.append(f"  ✗ {failure}")
    lines.append(f"  판정          : {'PASS' if report.passed else 'FAIL'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 통과 0 / 실패 1."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.dialogue_encryption_preflight",
        description=(
            "대화 at-rest 암호화가 실제로 작동하는지 1회 검증(배포 체크리스트 §2 왕복 항목). "
            "왕복 성공만으로 판정하지 않고 저장 표현(암호문/평문 증가분)까지 본다."
        ),
    )
    parser.add_argument(
        "--via-api",
        action="store_true",
        help="기동 중인 서버에 HTTP로 왕복(서버 프로세스가 키를 쓰는지 증명하는 유일한 모드).",
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="서버 주소(--via-api).")
    parser.add_argument(
        "--token", default="", help="Bearer 토큰(--via-api). 프로덕션은 실제 로그인 토큰이 필요."
    )
    parser.add_argument("--json", dest="json_path", default="", help="JSON 리포트 저장 경로.")
    args = parser.parse_args(argv)

    from whymath_backend.config import get_settings

    if args.via_api and not args.token:
        print("--via-api 에는 --token 이 필요합니다(프로덕션은 실제 로그인 토큰).")
        return 1

    report = run_preflight(
        get_settings(), via_api=args.via_api, api_url=args.api_url, token=args.token
    )
    print(_render(report))
    if args.json_path:
        payload = {
            "mode": report.mode,
            "key_configured": report.key_configured,
            "round_trip_ok": report.round_trip_ok,
            "encrypted_delta": report.encrypted_delta,
            "plaintext_delta": report.plaintext_delta,
            "failures": report.failures,
            "notes": report.notes,
            "passed": report.passed,
        }
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"JSON 리포트 저장: {args.json_path}")
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
