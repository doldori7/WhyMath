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

런북 검사 (OPS-57) — `docs/**/*.md`의 ```powershell 코드펜스도 같은 대상이다.
Kiki에게 건네는 PowerShell의 대부분은 .ps1이 아니라 **런북 코드펜스**인데 그쪽이
통째로 미검사였다. 붙여넣어 실행되는 순간 .ps1과 위험이 같다.

런북 전용 규칙 3종 (2026-09-01 관여도 트리아지 게이트 clear 사고에서 유래):
  ④ 보호 브랜치 직접 push — `git push origin main`은 `GH013: Changes must be made
     through a pull request`로 거부된다. 절차의 마지막 단계가 항상 실패한다.
  ⑤ `git reset --hard` 앞의 청결 확인 부재 — `git status --porcelain`으로 작업 트리가
     빈 것을 먼저 보지 않으면 미커밋 작업분을 무증상으로 지운다(2026-08-10 유형).
  ⑥ python 출력의 파이프·리다이렉트 — 한국어 Windows에서 stdout이 콘솔이 아니면
     로케일(cp949)로 인코딩돼 `UnicodeEncodeError`로 죽는다. 문서 앞부분에 UTF-8
     강제(PYTHONUTF8·PYTHONIOENCODING·Console::OutputEncoding)가 있어야 한다.

**판정 범위 (과신 금지)**: ④~⑥은 "런북이 주의를 지시하는가"를 **문서 순서**로 본다 —
위험 명령보다 앞에 선행 스텝이 있는지만 확인한다. 특정 붙여넣기가 실제로 안전한지,
사람이 그 스텝을 실제로 실행했는지는 판정하지 않는다. 그리고 **의미적 결함**
(예: 변별력 없는 검증 스텝을 차단 지점으로 오인)은 정적 검사로 잡히지 않는다.

사용:  python3 scripts/ops/check_ps_scripts.py [경로...]
       인자 없으면 scripts/**/*.ps1 + docs/**/*.md 코드펜스 전부
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


# ── 런북(마크다운 코드펜스) 전용 규칙 ─────────────────────────────────────────
#
# .ps1과 규칙을 나눈 이유: .ps1은 파일 하나가 완결 절차지만, 런북은 **여러 블록이
# 순서대로 사람에게 건네지는 절차**다. 그래서 선행 스텝의 존재를 *문서 순서*로 본다.

_FENCE_OPEN_RE = re.compile(r"^[ \t]*```[ \t]*(powershell|pwsh|ps1)[ \t]*$", re.I)
_FENCE_CLOSE_RE = re.compile(r"^[ \t]*```[ \t]*$")
# 마크다운 인용문 접두 — `> `, `>> ` 등. 인용문 안의 펜스도 붙여넣어 실행된다.
_BLOCKQUOTE_RE = re.compile(r"^[ \t]*(?:>[ \t]?)+")

# 보호 브랜치 직접 push — origin/upstream 어느 리모트든 main·master 지목이면 거부된다.
_PUSH_PROTECTED_RE = re.compile(r"\bgit\s+push\b[^\n|;]*?\b(main|master)\b")
# 선행 확인 스텝
_CLEAN_CHECK_RE = re.compile(r"\bgit\s+status\b[^\n]*--porcelain")
_RESET_HARD_RE = re.compile(r"\bgit\s+reset\b[^\n]*--hard")
# 같은 블록에서 fail-closed로 중단시키는 형태 (조건문 + 중단)
_FAIL_CLOSED_RE = re.compile(r"\bif\b[^\n]*porcelain|\b(throw|exit|return)\b", re.I)

# UTF-8 강제 — **활성화하는 대입**만 인정한다. 단순 토큰 등장(주석·설명·`="0"`)은
# 보호가 아니다: `$env:PYTHONUTF8="0"`가 뒤따르는 파이프를 전부 보호로 표시하면
# 정확히 이 규칙이 막으려는 UnicodeEncodeError가 그대로 난다(codex P2 지적).
_UTF8_ENABLE_RES = (
    re.compile(r"\$env:PYTHONUTF8\s*=\s*[\"\']?1[\"\']?"),
    re.compile(r"\$env:PYTHONIOENCODING\s*=\s*[\"\']?utf-?8", re.I),
    re.compile(r"\[Console\]::OutputEncoding\s*=[^\n]*UTF8", re.I),
    re.compile(r"\bchcp\s+65001\b"),
)
# python 출력이 콘솔을 벗어나는 형태 (파이프 / 리다이렉트).
#
# 리다이렉트는 `\s>` 로만 잡는다 — 앞이 공백이 아닌 `>`는 대개 `<플레이스홀더>`의 닫는
# 꺾쇠다(실측 오탐: `--until <파일럿종료YYYY-MM-DD> --shadow-ledger ...`가 리다이렉트로
# 잡혔다). 오탐이 있는 가드는 사람이 끄게 만들므로 좁히는 쪽을 택한다.
_PY_PIPED_RE = re.compile(r"\bpython[0-9.]*\b[^\n]*?(\||\s>+\s*\S)")


def _dequote(line: str) -> str:
    """마크다운 인용문 접두를 벗긴다 — 인용문 안의 펜스도 실행 대상이다."""
    return _BLOCKQUOTE_RE.sub("", line, count=1)


def iter_powershell_blocks(text: str) -> list[tuple[int, str]]:
    """마크다운에서 powershell 코드펜스를 (시작 줄번호, 본문)로 뽑는다.

    인용문(`> `) 안의 펜스도 대상이다 — 실측(2026-09-01): 런북 §7의 롤백 절차가 전부
    인용문 안에 있었고, 그 안에 `git reset --hard`가 있는데 가드가 **한 줄도 보지
    못했다**. 대상을 못 찾은 전수 가드는 공허하게 통과한다.
    """
    lines = text.split("\n")
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        if _FENCE_OPEN_RE.match(_dequote(lines[i])):
            body: list[str] = []
            start = i + 1
            j = start
            while j < len(lines) and not _FENCE_CLOSE_RE.match(_dequote(lines[j])):
                body.append(_dequote(lines[j]))
                j += 1
            blocks.append((i + 1, "\n".join(body)))
            i = j + 1
        else:
            i += 1
    return blocks


def check_runbook_markdown(path: pathlib.Path) -> list[str]:
    """런북 마크다운 1건 — 코드펜스를 **문서 순서**로 훑는다.

    선행 스텝(UTF-8 강제)은 위험 명령보다 *앞선 줄*에 있어야 인정한다. 청결 확인은
    더 엄격하다 — **다른(앞선) 펜스**에 있거나 같은 펜스라면 fail-closed 중단이
    있어야 한다. 같은 펜스의 `status` → `reset --hard`는 보호가 아니다: 붙여넣으면
    PowerShell이 status를 찍고 **결과와 무관하게** 곧바로 reset을 실행한다
    (codex P1 지적 — 초판은 이 형태를 테스트로 축복하고 있었다).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = iter_powershell_blocks(text)
    if not blocks:
        return []

    rows: list[tuple[int, str, str, int]] = []  # (줄번호, 원문, 코드, 블록 index)
    for bi, (line_no, body) in enumerate(blocks):
        code_lines = strip_noncode(body).split("\n")
        for off, raw_line in enumerate(body.split("\n")):
            code_line = code_lines[off] if off < len(code_lines) else ""
            rows.append((line_no + 1 + off, raw_line, code_line, bi))

    def _utf8_enabled(raw: str) -> bool:
        head = raw.split("#", 1)[0]  # 주석은 실행되지 않는다
        return any(r.search(head) for r in _UTF8_ENABLE_RES)

    utf8_at = next((i for i, r in enumerate(rows) if _utf8_enabled(r[1])), float("inf"))
    # 청결 확인이 등장한 **블록 index** — 같은 블록은 인정하지 않으므로 블록 단위로 본다.
    clean_blocks = {r[3] for r in rows if _CLEAN_CHECK_RE.search(r[2])}
    failclosed_blocks = {
        bi for bi, (_ln, body) in enumerate(blocks) if _FAIL_CLOSED_RE.search(strip_noncode(body))
    }

    issues: list[str] = []
    for line_no, body in blocks:
        issues += [f"L{line_no}+ {m}" for m in check_balance(strip_noncode(body))]

    for idx, (ln, _raw, code, bi) in enumerate(rows):
        m = _PUSH_PROTECTED_RE.search(code)
        if m:
            issues.append(
                f"L{ln}: 보호 브랜치 직접 push: {m.group(0).strip()!r} "
                "— 저장소 규칙이 'Changes must be made through a pull request'를 강제해 "
                "GH013으로 거부된다(2026-09-01 실측). 브랜치 push + PR로 바꾼다"
            )

        if _RESET_HARD_RE.search(code):
            earlier_clean = any(b < bi for b in clean_blocks)
            if not earlier_clean and bi not in failclosed_blocks:
                issues.append(
                    f"L{ln}: `git reset --hard` 앞에 **차단력 있는** 청결 확인이 없다 "
                    "— 같은 블록의 `git status --porcelain`은 보호가 아니다(붙여넣으면 "
                    "출력과 무관하게 곧바로 reset이 실행된다). 앞선 블록으로 분리해 사람이 "
                    "보게 하거나, 같은 블록이라면 비어있지 않을 때 중단하는 조건을 둔다"
                )

        if _PY_PIPED_RE.search(code) and utf8_at > idx:
            issues.append(
                f"L{ln}: python 출력을 파이프·리다이렉트하는데 앞서 UTF-8 강제가 없다 "
                "— 한국어 Windows에서 stdout이 로케일(cp949)로 인코딩돼 UnicodeEncodeError로 "
                ' 죽는다(2026-09-01 실측 2건). $env:PYTHONUTF8="1" 등을 앞에 둔다'
            )

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
    if argv[1:]:
        targets = [pathlib.Path(a) for a in argv[1:]]
    else:
        targets = sorted(pathlib.Path("scripts").rglob("*.ps1"))
        # OPS-57 — Kiki에게 건네는 PowerShell의 대부분은 런북 코드펜스다.
        targets += sorted(pathlib.Path("docs").rglob("*.md"))
    files = [t for t in targets if t.is_file()]
    if not files:
        print("검사할 파일이 없다.")
        return 0

    failed = 0
    for f in files:
        if f.suffix.lower() == ".md":
            issues = check_runbook_markdown(f)
            if not issues and not iter_powershell_blocks(
                f.read_text(encoding="utf-8", errors="replace")
            ):
                continue  # powershell 펜스가 없는 문서는 조용히 넘긴다
        else:
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
