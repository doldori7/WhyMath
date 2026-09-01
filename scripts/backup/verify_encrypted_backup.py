#!/usr/bin/env python3
"""암호화 백업 양방향 검증 — 잠겼는가 + 열면 진짜 복원 가능한가 (OPS-31 acceptance ④).

왜 양방향인가
-------------
"암호화했다"를 산출물을 열어보지 않고 선언하면 위장이다. 두 방향이 **동시에** 참이어야
암호화가 성립한다:

  ① **잠김(negative)** — 암호문을 그대로 `pg_restore --list`에 물리면 **실패**해야 한다.
     실패하지 않으면 그 파일은 암호화된 것이 아니다(혹은 헤더만 붙은 평문이다).
  ② **열림(positive)** — 복호한 산출물은 `pg_restore --list`를 **통과**해야 한다.
     통과하지 않으면 잠긴 것은 맞아도 **복구 불가능한 벽돌**이다.

①만 보면 벽돌을, ②만 보면 평문을 놓친다. 한 방향만 검사하는 구현은 "성공/실패 양쪽에서
같은 값을 내는" 검사와 같은 부류다(CLAUDE.md 변별력 규칙).

도구 부재는 통과가 아니다
-------------------------
`age`나 `pg_restore`가 없으면 **판정 불가**(exit 2)이고 통과(0)가 아니다. 도구가 없어서
검사를 못 한 것을 "검사했는데 문제 없음"으로 바꾸면, 백업 검증이 도구 미설치 환경에서
영구 green이 된다 — 이 저장소가 반복해서 겪은 형태다.

계층 경계: 순수 파일·서브프로세스 I/O. backend를 import하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PG_CUSTOM_DUMP_MAGIC",
    "VerificationResult",
    "looks_like_pg_custom_dump",
    "main",
    "verify_encrypted_backup",
]

_EXIT_OK = 0
_EXIT_FAIL = 1
_EXIT_UNDECIDABLE = 2

#: pg_dump 커스텀 포맷(-Fc) 아카이브의 선두 매직. 평문 덤프면 이 바이트로 시작한다.
#: 암호문이 이걸로 시작하면 암호화가 안 된 것이다(값싼 1차 판별 — 최종 판정은 pg_restore).
PG_CUSTOM_DUMP_MAGIC = b"PGDMP"

#: 외부 프로세스 타임아웃 — 무한 대기 금지(CLAUDE.md 2026-08-22).
_TIMEOUT_SECONDS = 120


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """양방향 검증 결과 — 각 축의 통과 여부와 사유."""

    locked_ok: bool
    """① 암호문이 pg_restore로 읽히지 않는가."""
    restorable_ok: bool
    """② 복호본이 pg_restore --list를 통과하는가."""
    reason: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.locked_ok and self.restorable_ok


def looks_like_pg_custom_dump(path: Path) -> bool:
    """선두 매직으로 평문 pg 커스텀 덤프인지 값싸게 본다(파일 전체를 읽지 않는다)."""
    try:
        with path.open("rb") as handle:
            return handle.read(len(PG_CUSTOM_DUMP_MAGIC)) == PG_CUSTOM_DUMP_MAGIC
    except OSError:
        return False


def _run(argv: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, capture_output=True, timeout=_TIMEOUT_SECONDS, check=False)


def verify_encrypted_backup(
    encrypted_path: Path,
    *,
    identity_file: Path,
    age_bin: str = "age",
    pg_restore_bin: str = "pg_restore",
) -> VerificationResult:
    """암호문 1건을 양방향 검증한다.

    ① 암호문 그대로 `pg_restore --list` -> **비0이어야** 통과(잠김 확인).
    ② `age -d` 복호 -> `pg_restore --list` -> **0이어야** 통과(복원 가능 확인).

    복호본은 임시 디렉터리에 만들고 **반드시 지운다** — 실데이터 복제본이 남으면 이 검증
    자체가 §4 취급 규칙 위반이 된다(리허설 scratch를 즉시 폐기하는 것과 같은 이유).
    """
    if not encrypted_path.is_file():
        return VerificationResult(False, False, "missing_input", str(encrypted_path))

    # ── ① 잠김 — 값싼 매직 판별 먼저(명백한 평문을 pg_restore까지 갈 것 없이 잡는다) ──
    if looks_like_pg_custom_dump(encrypted_path):
        return VerificationResult(
            False,
            False,
            "not_encrypted",
            "산출물이 PGDMP 매직으로 시작한다 — 평문 덤프다(암호화되지 않음).",
        )
    locked = _run([pg_restore_bin, "--list", str(encrypted_path)])
    if locked.returncode == 0:
        return VerificationResult(
            False,
            False,
            "not_encrypted",
            "pg_restore가 암호문을 그대로 읽었다 — 암호화되지 않았거나 껍데기뿐이다.",
        )

    # ── ② 열림 — 복호 후 카탈로그 판독 ──
    with tempfile.TemporaryDirectory(prefix="wm-verify-") as tmpdir:
        decrypted = Path(tmpdir) / "decrypted.dump"
        dec = _run(
            [age_bin, "-d", "-i", str(identity_file), "-o", str(decrypted), str(encrypted_path)]
        )
        if dec.returncode != 0:
            return VerificationResult(
                True,
                False,
                "decrypt_failed",
                f"age 복호 실패(exit {dec.returncode}): "
                f"{dec.stderr.decode('utf-8', 'replace').strip()[:200]}",
            )
        listed = _run([pg_restore_bin, "--list", str(decrypted)])
        if listed.returncode != 0:
            return VerificationResult(
                True,
                False,
                "restore_list_failed",
                f"복호는 됐으나 pg_restore --list 실패(exit {listed.returncode}) — "
                "복구 불가능한 산출물이다.",
            )
        entries = len(
            [
                line
                for line in listed.stdout.decode("utf-8", "replace").splitlines()
                if line.strip() and not line.startswith(";")
            ]
        )
    return VerificationResult(True, True, "ok", f"카탈로그 항목 {entries}건")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "암호화 백업 양방향 검증 — 잠김(①) + 복원 가능(②). "
            "exit 0 통과 / 1 미달 / 2 판정 불가."
        )
    )
    parser.add_argument("encrypted", help="검증할 .dump.age 경로")
    parser.add_argument("--identity", required=True, help="age 개인키 파일(키 분리 — 4-5)")
    parser.add_argument("--age-bin", default="age")
    parser.add_argument("--pg-restore-bin", default="pg_restore")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # 도구 부재는 통과가 아니라 판정 불가다.
    missing = [b for b in (args.age_bin, args.pg_restore_bin) if shutil.which(b) is None]
    if missing:
        print(
            f"[판정 불가] 필요한 도구 부재: {', '.join(missing)} — "
            "검사를 못 한 것을 '문제 없음'으로 바꾸지 않는다.",
            file=sys.stderr,
        )
        return _EXIT_UNDECIDABLE
    identity = Path(args.identity)
    if not identity.is_file():
        print(f"[판정 불가] 개인키 파일 부재: {identity}", file=sys.stderr)
        return _EXIT_UNDECIDABLE

    try:
        result = verify_encrypted_backup(
            Path(args.encrypted),
            identity_file=identity,
            age_bin=args.age_bin,
            pg_restore_bin=args.pg_restore_bin,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"[판정 불가] TimeoutExpired: {exc}", file=sys.stderr)
        return _EXIT_UNDECIDABLE

    if args.json:
        print(
            json.dumps(
                {
                    "encrypted": args.encrypted,
                    "locked_ok": result.locked_ok,
                    "restorable_ok": result.restorable_ok,
                    "ok": result.ok,
                    "reason": result.reason,
                    "detail": result.detail,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        lock = "OK" if result.locked_ok else "FAIL"
        rest = "OK" if result.restorable_ok else "FAIL"
        print(f"① 잠김(암호문이 pg_restore로 안 읽힘): {lock}")
        print(f"② 열림(복호 후 카탈로그 판독):        {rest}")
        print(f"사유: {result.reason}" + (f" — {result.detail}" if result.detail else ""))
    return _EXIT_OK if result.ok else _EXIT_FAIL


if __name__ == "__main__":  # pragma: no cover - CLI 진입점
    raise SystemExit(main())
