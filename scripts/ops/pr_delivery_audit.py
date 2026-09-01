#!/usr/bin/env python3
"""HARN-30 ③ — PR 배송 상태 관측 좌석: '체크런 0건'과 'green인데 미머지'를 구분한다.

두 상태의 **처방이 다르다**:
  · `NO_CHECKS`      — 트리거가 안 걸렸다 → 깨워야 한다(base 재동기화 push 등)
  · `READY_UNMERGED` — 조건 충족인데 안 붙었다 → 사람 결정/머지 실행 대기

이 둘을 한 덩어리("미머지 PR")로 보면 처방을 못 고른다. 실제로 이 저장소에서
`NO_CHECKS`는 무증상이다 — 아무도 보지 않으면 PR이 조용히 방치된다(PR #779가
57분, #751이 1일 넘게).

**도구 함정 (acceptance ①)**: `GET /repos/{repo}/statuses|status`(MCP의
`pull_request_read method=get_status`)는 이 저장소에서 **항상 total_count 0**을
낸다 — commit status API인데 이 저장소는 check runs를 쓴다. 체크런 16건이 확실한
PR에서도 0이다(2026-08-31 재확인). **판정에 쓰지 말 것.**
대신 쓸 신호: `GET /commits/{sha}/check-runs` 또는 `/actions/runs?head_sha=`.

**fail-open 판정 (acceptance ④)**: 조회 실패는 "이상 없음"이 아니라 **측정 실패**로
보인다. 상시 무력 보호를 만들지 않기 위해(CLAUDE.md 2026-07-27 금기) 이 도구는
조회에 실패하면 exit 1과 함께 실패 사유를 낸다 — 조용히 빈 목록을 반환하지 않는다.

사용:
    python3 scripts/ops/pr_delivery_audit.py doldori7/WhyMath

exit code
    0 — 열린 PR 전부가 정상 배송 중(대기·진행)
    1 — 주의 필요(NO_CHECKS 또는 READY_UNMERGED 존재) 또는 **측정 실패**
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

API = "https://api.github.com"
TIMEOUT = 30
_CA_PATH = "/root/.ccr/ca-bundle.crt"  # 에이전트 프록시 CA (있을 때만 사용)
SATISFYING = frozenset({"success", "skipped", "neutral"})

# 상태 → (라벨, 처방). 처방을 함께 들고 다니는 이유: 상태만 알려주면
# 다음 세션이 다시 판단해야 하고, 그 판단이 이 태스크가 고치려는 오판 지점이다.
PRESCRIPTION = {
    "NO_CHECKS": "트리거 미발화 — origin/main 재병합 push로 깨운다(빈 커밋·재개폐 금지)",
    "REQUIRED_FAILING": "필수 체크 실패 — 고쳐서 다시 push",
    "REQUIRED_PENDING": "필수 체크 진행 중 — 대기(전체 CI는 기다리지 않는다·HARN-32)",
    "BEHIND": "base 전진 — origin/main 재병합 후 push(strict policy)",
    "CONFLICT": "머지 충돌 — 해소 필요",
    "READY_UNMERGED": "조건 충족 · 머지만 남음 — 사람 결정 대기",
}
ATTENTION = frozenset({"NO_CHECKS", "READY_UNMERGED"})


def _auth_args() -> list[str]:
    """토큰이 있으면 `["-H", "Authorization: Bearer <token>"]`, 없으면 `[]`.

    **왜 필수인가** (2026-09-01 main red 실측): GitHub API의 **미인증** 한도는
    IP당 60req/h인데, GitHub 러너는 IP를 공유하므로 실질적으로 상시 소진 상태다.
    실제 실패: `API rate limit exceeded for 52.157.2.240`.

    더 나쁜 것은 이 실패가 **간헐적**이라는 점이다 — 같은 코드가 앞선 실행에서는
    통과했다(그때는 한도가 남아 있었다). 그래서 "한 번 초록이었다"가 안전의 증거가
    되지 못한다. 워크플로가 `GITHUB_TOKEN` 환경변수를 넘겨도 **스크립트가 읽지
    않으면 아무 효과가 없다** — 환경변수 설정과 실제 소비는 다른 일이다.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return ["-H", f"Authorization: Bearer {token}"] if token else []


def _ca_args() -> list[str]:
    """프록시 CA를 쓸 수 있으면 `["--cacert", <경로>]`, 아니면 `[]`.

    **왜 존재 검사를 예외로 감싸는가** (2026-09-01 main red 실측): `Path.exists()`는
    실패를 False로 돌려주지 **않는다** — `pathlib._IGNORED_ERRNOS`는
    `(ENOENT, ENOTDIR, EBADF, ELOOP)`뿐이라 **EACCES는 전파된다**. GitHub 러너의
    `runner` 유저는 `/root`(mode 700)를 통과할 수 없으므로 검사 자체가
    `PermissionError`로 죽는다.

    그리고 CA를 **무조건** `--cacert`로 넘기면 러너에서 `curl (77) error setting
    certificate file`이 난다. 이 경로는 에이전트 프록시가 있는 실행 환경에만
    존재하므로, 없으면 시스템 신뢰저장소를 쓰는 것이 정상 동작이다.
    """
    try:
        with open(_CA_PATH, "rb"):  # 존재 + 읽기 권한을 한 번에 확인한다
            return ["--cacert", _CA_PATH]
    except OSError:
        return []


def classify(
    required: set[str],
    check_runs: dict[str, str | None],
    *,
    mergeable_state: str,
) -> str:
    """PR 1건의 배송 상태 — **순수 함수**(네트워크 없음).

    순서가 곧 처방 우선순위다. `NO_CHECKS`를 가장 먼저 보는 이유: 체크런이 0건이면
    다른 판정이 전부 무의미하기 때문이다(진행 중인지 실패인지 알 수 없다).
    """
    if not check_runs:
        return "NO_CHECKS"
    for name in required:
        concl = check_runs.get(name, "__missing__")
        if concl == "__missing__":
            return "NO_CHECKS"  # 필수가 아예 안 돌았다 — 부분 미발화도 미발화다
    if any(check_runs.get(n) not in SATISFYING and check_runs.get(n) is not None for n in required):
        return "REQUIRED_FAILING"
    if any(check_runs.get(n) is None for n in required):
        return "REQUIRED_PENDING"
    if mergeable_state == "dirty":
        return "CONFLICT"
    if mergeable_state == "behind":
        return "BEHIND"
    return "READY_UNMERGED"


def _get(path: str) -> object:
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        str(TIMEOUT),
        *_ca_args(),
        *_auth_args(),
        "-H",
        "Accept: application/vnd.github+json",
        f"{API}{path}",
    ]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",  # HARN-19 — 로케일(cp949) 디코드 금지
            timeout=TIMEOUT + 10,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"❌ 측정 실패(타임아웃 {TIMEOUT}s): {path}") from exc
    if out.returncode != 0:
        raise SystemExit(
            f"❌ 측정 실패(curl rc={out.returncode}): {path}\n{out.stderr[:400]}"
        ) from None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"❌ 측정 실패(JSON): {path}\n앞 400자: {out.stdout[:400]}") from exc


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(f"사용: {sys.argv[0]} <owner/repo>")
    repo = sys.argv[1]

    rules = _get(f"/repos/{repo}/rules/branches/main")
    required = {
        c["context"]
        for r in rules
        if isinstance(r, dict) and r.get("type") == "required_status_checks"
        for c in r.get("parameters", {}).get("required_status_checks", [])
    }
    if not required:
        raise SystemExit(
            "❌ 측정 실패 — 필수 체크 0건(규칙 미조회/권한 부족). '이상 없음'이 아니다"
        )

    prs = _get(f"/repos/{repo}/pulls?state=open&per_page=50")
    if not isinstance(prs, list):
        raise SystemExit(f"❌ 측정 실패 — PR 목록 조회: {str(prs)[:300]}")
    if not prs:
        print("열린 PR 0건")
        return 0

    buckets: dict[str, list[str]] = {}
    for pr in prs:
        sha = pr["head"]["sha"]
        cr = _get(f"/repos/{repo}/commits/{sha}/check-runs?per_page=100")
        runs = {
            c["name"]: (c.get("conclusion") if c.get("status") == "completed" else None)
            for c in (cr.get("check_runs", []) if isinstance(cr, dict) else [])
        }
        state = classify(required, runs, mergeable_state=str(pr.get("mergeable_state")))
        buckets.setdefault(state, []).append(f"#{pr['number']} {pr['title'][:52]}")

    attention = 0
    for state in (
        "NO_CHECKS",
        "REQUIRED_FAILING",
        "CONFLICT",
        "BEHIND",
        "REQUIRED_PENDING",
        "READY_UNMERGED",
    ):
        items = buckets.get(state)
        if not items:
            continue
        flag = "⚠" if state in ATTENTION else "·"
        print(f"\n{flag} {state} ({len(items)}건) — {PRESCRIPTION[state]}")
        for it in items:
            print(f"    {it}")
        if state in ATTENTION:
            attention += len(items)

    print(f"\n열린 PR {len(prs)}건 · 주의 필요 {attention}건")
    print("주의: get_status(commit status API)는 이 저장소에서 항상 0을 낸다 — 판정에 쓰지 말 것")
    return 1 if attention else 0


if __name__ == "__main__":
    raise SystemExit(main())
