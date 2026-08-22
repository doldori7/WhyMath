#!/usr/bin/env python3
"""PowerShell 스크립트 정적 검사 — 실행 검증이 불가능한 환경(Linux CI·샌드박스)용 최소 안전망.

이 저장소의 PS 스크립트는 Kiki 머신(Windows)에서만 실행된다. 즉 CI도 개발 세션도
`pwsh -NoProfile -Command { }` 같은 실행 검증을 할 수 없다. 그 공백에서 반복 발생한
결함을 기계로 고정한다.

검사 3종 (전부 실측 사고에서 유래):
  ① BOM 부재 — PS 5.1은 BOM 없는 UTF-8을 로케일(cp949)로 읽어 한국어 주석이 깨진다.
  ② 괄호 불균형 — 문자열·주석을 인식하는 파서로 (), {}, [] 짝을 본다.
  ③ 정의보다 먼저 호출되는 스크립트 지역 함수 — PowerShell은 위에서 아래로 실행하므로
     정의 아래에서만 호출할 수 있다.
     (사고 경위: 2026-08-22 bench_ollama.ps1이 Get-CommitFreeGB를 정의 79줄 위에서 호출해
      CommandNotFoundException으로 측정 1회가 공전했다.)

사용:  python3 scripts/ops/check_ps_scripts.py [경로...]
종료:  0 통과 / 1 위반
"""

from __future__ import annotations

import pathlib
import re
import sys

PAIRS = {"(": ")", "{": "}", "[": "]"}


def strip_noncode(src: str) -> str:
    """주석·문자열을 공백으로 치환한다. 줄 번호와 길이는 보존한다."""
    out = list(src)
    i, n = 0, len(src)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if src.startswith("<#", i):  # 블록 주석
            j = src.find("#>", i)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif c == "#":  # 줄 주석
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c == "'":  # 작은따옴표 문자열
            j = i + 1
            while j < n:
                if src[j] == "'":
                    if j + 1 < n and src[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            blank(i, j)
            i = j
        elif c == '"':  # 큰따옴표 문자열
            j = i + 1
            while j < n:
                if src[j] == "`":
                    j += 2
                    continue
                if src[j] == '"':
                    if j + 1 < n and src[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            blank(i, j)
            i = j
        elif c == "`":  # 이스케이프
            i += 2
        else:
            i += 1
    return "".join(out)


def check_balance(code: str) -> list[str]:
    stack: list[tuple[str, int]] = []
    issues: list[str] = []
    line = 1
    for ch in code:
        if ch == "\n":
            line += 1
        elif ch in PAIRS:
            stack.append((ch, line))
        elif ch in ")}]":
            if not stack:
                issues.append(f"L{line}: 짝 없는 닫는 괄호 {ch!r}")
            else:
                op, ol = stack.pop()
                if PAIRS[op] != ch:
                    issues.append(f"L{line}: {op!r}(L{ol})와 {ch!r}가 짝이 맞지 않음")
    issues += [f"L{ol}: 닫히지 않은 {op!r}" for op, ol in stack]
    return issues


def check_call_before_def(code: str) -> list[str]:
    lines = code.split("\n")
    defs: dict[str, int] = {}
    for idx, ln in enumerate(lines, start=1):
        m = re.match(r"\s*function\s+([A-Za-z][\w-]*)", ln)
        if m:
            defs.setdefault(m.group(1), idx)

    issues: list[str] = []
    for name, def_line in defs.items():
        pat = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        for idx, ln in enumerate(lines, start=1):
            if idx >= def_line or not pat.search(ln):
                continue
            if re.match(r"\s*function\s", ln):  # 다른 함수 정의 줄은 제외
                continue
            issues.append(
                f"L{idx}: {name}() 를 정의(L{def_line})보다 먼저 호출한다 "
                "— PowerShell은 위에서 아래로 실행하므로 CommandNotFoundException 이 난다"
            )
            break
    return issues


def check_file(path: pathlib.Path) -> list[str]:
    raw = path.read_bytes()
    issues: list[str] = []
    body = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    has_non_ascii = any(b > 0x7F for b in body)
    # BOM은 비ASCII가 있을 때만 필요하다. ASCII 전용 파일에 요구하면 변별력 없는 검사가 된다
    # (2026-08-22: backup_whymath_pg.ps1을 오탐했다 — 순수 ASCII라 BOM이 불필요하다).
    if has_non_ascii and not raw.startswith(b"\xef\xbb\xbf"):
        issues.append(
            "L1: 비ASCII 문자가 있는데 UTF-8 BOM이 없음 "
            "— PS 5.1이 로케일(cp949)로 읽어 한국어가 깨진다"
        )
    code = strip_noncode(raw.decode("utf-8-sig", errors="replace"))
    issues += check_balance(code)
    issues += check_call_before_def(code)
    return issues


def main(argv: list[str]) -> int:
    targets = [pathlib.Path(a) for a in argv[1:]] or sorted(pathlib.Path("scripts").rglob("*.ps1"))
    files = [t for t in targets if t.is_file()]
    if not files:
        print("검사할 .ps1 파일이 없다.")
        return 0

    failed = 0
    for f in files:
        issues = check_file(f)
        if issues:
            failed += 1
            print(f"[FAIL] {f}")
            for msg in issues:
                print(f"    {msg}")
        else:
            print(f"[ok  ] {f}")
    print(f"\n검사 {len(files)}건 / 위반 {failed}건")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
