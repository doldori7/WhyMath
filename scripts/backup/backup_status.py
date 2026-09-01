#!/usr/bin/env python3
"""백업 회차 상태 기록·판정 — 조용한 누락을 관측 가능하게 (OPS-31 acceptance ③).

무엇을 고치나
-------------
`db_backup_dr_runbook.md` §2가 자인한 한계: 백업 스케줄이 **로그온 의존**이라 Kiki가
로그아웃하거나 PC가 꺼져 있으면 회차가 통째 누락되는데, **누락됐다는 사실이 어디에도
남지 않는다**. 백업이 안 도는 것과 백업이 필요 없던 것이 화면에서 같은 모양이다 —
CLAUDE.md "침묵 실패 금지"의 백업 축이다.

이 모듈은 성공 회차마다 상태 파일에 시각을 각인하고(`record`), 그 시각이 너무 오래됐으면
**exit 1**로 알린다(`check`). 누락은 이제 "아무 일도 안 일어남"이 아니라 **판정 가능한 사건**이다.

왜 상태 파일인가(설계 근거)
---------------------------
"마지막 성공 백업 시각"을 백업 *파일 목록*에서 유추할 수도 있다(가장 최신 mtime). 그러나
그 방식은 세 가지를 구분하지 못한다:
  · 백업이 성공했는가 vs 파일이 남아 있을 뿐인가(부분 실패 후 잔존물)
  · 그 산출물이 **암호화됐는가**(오프사이트 반출 가부 — §4-1)
  · 보존 정책이 옛 파일을 지워 목록이 비었을 때 "누락"인가 "정상 정리"인가
그래서 파일 시스템 추론이 아니라 **성공 경로가 스스로 각인**한다.

실패 경로 설계 (CLAUDE.md 2026-08-22)
-------------------------------------
  · 상태 파일 부재는 "정상"이 아니라 **판정 불가**(`never_recorded`) — 0회 기록과
    "오래됨"을 구분한다. 둘 다 exit 1이지만 사유가 다르다.
  · 파싱 실패는 예외 타입명과 함께 보고한다(무타입 경고 금지).
  · 기록은 원자적(tmp -> replace)이라 중단돼도 반쪽 JSON이 남지 않는다.

계층 경계: 순수 파일 I/O. backend·harness를 import하지 않는다(운영 스크립트 격리).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_MAX_AGE_HOURS",
    "BackupStatus",
    "StalenessVerdict",
    "evaluate_staleness",
    "load_status",
    "main",
    "record_success",
]

_EXIT_OK = 0
_EXIT_FAIL = 1

#: 기본 허용 나이 — 주 2회(월·목) 스케줄의 최대 간격 4일 + 여유 1일.
#: 이 값을 늘리면 누락 탐지가 그만큼 늦어진다(트레이드오프를 아는 채로 조정할 것).
DEFAULT_MAX_AGE_HOURS = 120

STATUS_FILENAME = "backup_status.json"


class BackupStatusError(RuntimeError):
    """상태 파일 적재 실패 — 조용한 기본값 대신 던진다."""


@dataclass(frozen=True, slots=True)
class BackupStatus:
    """마지막 성공 회차 1건."""

    last_success_utc: datetime
    artifact: str
    size_bytes: int
    encrypted: bool
    """산출물이 암호화됐는가 — **오프사이트 반출 가부의 판정 입력**(런북 §4-1)."""
    recipients_fingerprint: str | None = None
    """암호화 수신자 식별 단서(공개키 접미 8자) — 어느 키로 잠갔는지 추적용.

    개인키·패스프레이즈는 **절대** 여기 담지 않는다(§4-5 키 분리).
    """


@dataclass(frozen=True, slots=True)
class StalenessVerdict:
    """신선도 판정 — 통과/미달과 **사유**를 함께."""

    ok: bool
    reason: str
    age_hours: float | None
    """마지막 성공으로부터 경과 시간. `never_recorded`면 None(0이 아니다)."""


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """tmp -> replace 원자적 기록 — 중단돼도 반쪽 JSON이 남지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def record_success(
    status_path: Path,
    *,
    artifact: str,
    size_bytes: int,
    encrypted: bool,
    recipients_fingerprint: str | None = None,
    moment: datetime | None = None,
) -> BackupStatus:
    """성공 회차를 각인한다 — 백업 스크립트의 마지막 단계가 호출한다.

    **성공 경로에서만** 호출한다. 실패한 회차가 시각을 갱신하면 신선도 판정이
    "돌긴 돌았다"로 위장되어 이 모듈의 존재 이유가 사라진다.
    """
    stamped = (moment or datetime.now(UTC)).astimezone(UTC)
    status = BackupStatus(
        last_success_utc=stamped,
        artifact=artifact,
        size_bytes=int(size_bytes),
        encrypted=bool(encrypted),
        recipients_fingerprint=recipients_fingerprint,
    )
    _atomic_write(
        status_path,
        {
            "last_success_utc": stamped.isoformat(timespec="seconds"),
            "artifact": status.artifact,
            "size_bytes": status.size_bytes,
            "encrypted": status.encrypted,
            "recipients_fingerprint": status.recipients_fingerprint,
        },
    )
    return status


def load_status(status_path: Path) -> BackupStatus | None:
    """상태 파일 적재. 파일 부재는 `None`(= 기록된 적 없음), 손상은 예외."""
    if not status_path.exists():
        return None
    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
        moment = datetime.fromisoformat(str(raw["last_success_utc"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BackupStatusError(
            f"백업 상태 파일 판독 실패 ({status_path}): {type(exc).__name__}: {exc}"
        ) from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return BackupStatus(
        last_success_utc=moment.astimezone(UTC),
        artifact=str(raw.get("artifact", "")),
        size_bytes=int(raw.get("size_bytes", 0)),
        encrypted=bool(raw.get("encrypted", False)),
        recipients_fingerprint=raw.get("recipients_fingerprint"),
    )


def evaluate_staleness(
    status: BackupStatus | None,
    *,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> StalenessVerdict:
    """신선도 판정 — 기록 없음과 오래됨을 **다른 사유로** 구분한다.

    둘 다 exit 1이지만 대처가 다르다: 기록 없음은 "한 번도 안 돌았거나 상태 경로가 다르다",
    오래됨은 "스케줄이 죽었거나 최근 회차가 실패했다". 한 사유로 뭉치면 조사 방향을 잃는다.
    """
    if status is None:
        return StalenessVerdict(False, "never_recorded", None)
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    age_hours = (reference - status.last_success_utc).total_seconds() / 3600.0
    if age_hours > max_age_hours:
        return StalenessVerdict(False, "stale", age_hours)
    return StalenessVerdict(True, "fresh", age_hours)


# --------------------------------------------------------------------------
# CLI — 판정은 exit 0/1 (게이트 CLI 관례)
# --------------------------------------------------------------------------
def _default_status_path(backup_dir: str) -> Path:
    return Path(backup_dir) / STATUS_FILENAME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="백업 회차 상태 각인·신선도 판정 (OPS-31 — 조용한 누락 방지)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="성공 회차 각인(백업 스크립트가 호출)")
    rec.add_argument("--backup-dir", required=True)
    rec.add_argument("--artifact", required=True, help="산출물 파일 경로")
    rec.add_argument("--size-bytes", type=int, required=True)
    rec.add_argument(
        "--encrypted",
        choices=("true", "false"),
        required=True,
        help="산출물이 암호화됐는가 — 오프사이트 반출 가부의 입력",
    )
    rec.add_argument("--recipients-fingerprint", default=None)

    chk = sub.add_parser("check", help="신선도 판정(누락 탐지) — exit 0 통과 / 1 미달")
    chk.add_argument("--backup-dir", required=True)
    chk.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    chk.add_argument(
        "--require-encrypted",
        action="store_true",
        help="마지막 산출물이 암호화되지 않았으면 exit 1 — 오프사이트 운용 시 사용",
    )
    chk.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    status_path = _default_status_path(args.backup_dir)

    if args.command == "record":
        status = record_success(
            status_path,
            artifact=args.artifact,
            size_bytes=args.size_bytes,
            encrypted=args.encrypted == "true",
            recipients_fingerprint=args.recipients_fingerprint,
        )
        print(f"[OK] backup status recorded: {status_path} ({status.last_success_utc.isoformat()})")
        return _EXIT_OK

    try:
        status = load_status(status_path)
    except BackupStatusError as exc:
        # 판독 실패를 "신선함"으로 넘기면 상태 파일 손상이 무증상이 된다.
        print(f"[FAIL] {exc}", file=sys.stderr)
        return _EXIT_FAIL

    verdict = evaluate_staleness(status, max_age_hours=args.max_age_hours)
    payload = {
        "status_path": str(status_path),
        "ok": verdict.ok,
        "reason": verdict.reason,
        "age_hours": verdict.age_hours,
        "last_success_utc": status.last_success_utc.isoformat() if status else None,
        "encrypted": status.encrypted if status else None,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if verdict.reason == "never_recorded":
            print(
                f"[FAIL] 백업 성공 기록이 없다 ({status_path}) — 한 번도 안 돌았거나 "
                "상태 경로가 다르다. '0회'와 '오래됨'은 다른 사태다.",
                file=sys.stderr,
            )
        elif verdict.reason == "stale":
            assert verdict.age_hours is not None
            print(
                f"[FAIL] 마지막 성공 백업이 {verdict.age_hours:.1f}시간 전 "
                f"(임계 {args.max_age_hours:.0f}시간 초과) — 스케줄 누락 또는 최근 회차 실패. "
                f"기록: {status.last_success_utc.isoformat() if status else '-'}",
                file=sys.stderr,
            )
        else:
            assert verdict.age_hours is not None and status is not None
            enc = "암호화됨" if status.encrypted else "**평문**"
            print(
                f"[OK] 마지막 성공 백업 {verdict.age_hours:.1f}시간 전 · 산출물 {enc} · "
                f"{status.artifact}"
            )
    if not verdict.ok:
        return _EXIT_FAIL
    if args.require_encrypted and status is not None and not status.encrypted:
        print(
            "[FAIL] 마지막 산출물이 평문이다 — 오프사이트 반출 금지(런북 4-1). "
            "-RecipientsFile로 백업을 재실행하라.",
            file=sys.stderr,
        )
        return _EXIT_FAIL
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover - CLI 진입점
    raise SystemExit(main())
