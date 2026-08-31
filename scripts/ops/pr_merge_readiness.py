#!/usr/bin/env python3
"""HARN-32 ③ — PR 머지 가능 시점 판정 (경합 창 22분 단축).

**결함**: 세션이 *전체 CI*(중앙값 28.6분)를 기다린 뒤 머지를 시도한다. 그런데 이
저장소의 브랜치 보호가 실제로 요구하는 것은 **필수 체크 6종**(중앙값 6.5분)뿐이다 —
최장 잡 `backend — lint·type·test`(~30분)는 필수 목록에 **없다**.

main은 중앙값 40.7분마다 전진하고 보호 규칙은 `strict_required_status_checks_policy:
true`(= 머지 시점에 브랜치가 up-to-date여야 함)다. 따라서 대기 시간이 곧 패배 확률이다:

    필수만 대기(6.5분)  → base 전진 확률 ≈ 16%
    전체 대기(28.6분)   → base 전진 확률 ≈ 70%

이 세션은 전체를 기다렸고 머지 시도 3회가 전부 base 전진으로 실패했다.

**완화**: 필수 체크가 green이 되는 즉시 머지한다. 이 도구가 그 시점을 판정한다.
브랜치 보호 규칙이나 ci.yml은 건드리지 않는다(HARN-32 ⑥ 범위 밖 — 사람 결정).

사용:
    python3 scripts/ops/pr_merge_readiness.py doldori7/WhyMath 916

exit code (게이트 CLI 관례)
    0 — 지금 머지 가능(필수 전부 green + up-to-date + 스레드 해소)
    1 — 아직 아님(사유를 stdout에 명시) 또는 측정 실패
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field

API = "https://api.github.com"
TIMEOUT = 30
CA = "/root/.ccr/ca-bundle.crt"

# 필수 체크를 만족시키는 결론 — skipped도 만족이다(GitHub 규칙).
SATISFYING = frozenset({"success", "skipped", "neutral"})


@dataclass
class Verdict:
    """판정 결과 — 순수 함수의 산출물(I/O와 분리해 테스트 가능하게)."""

    ready: bool
    reasons: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    failing: list[str] = field(default_factory=list)


def decide(
    required: set[str],
    runs: dict[str, str | None],
    *,
    mergeable_state: str,
    unresolved_threads: int,
) -> Verdict:
    """머지 가능 여부 판정 — **순수 함수**(네트워크 없음).

    `runs`: 체크런 이름 → conclusion(미완료는 None).

    필수 목록에 없는 체크는 **판정에 넣지 않는다** — 그것이 이 도구의 요점이다.
    다만 실패한 비필수 체크는 `reasons`에 정보로 남긴다(머지는 막지 않되 숨기지도 않는다).
    """
    v = Verdict(ready=True)

    missing = required - set(runs)
    for name in sorted(missing):
        v.pending.append(name)
        v.reasons.append(f"필수 체크 미발화: {name}")
        v.ready = False

    for name in sorted(required & set(runs)):
        concl = runs[name]
        if concl is None:
            v.pending.append(name)
            v.reasons.append(f"필수 체크 진행 중: {name}")
            v.ready = False
        elif concl not in SATISFYING:
            v.failing.append(name)
            v.reasons.append(f"필수 체크 실패({concl}): {name}")
            v.ready = False

    # up-to-date 요구(strict policy) — behind면 필수 체크가 병합 커밋 기준으로
    # 재평가되고 그 커밋엔 체크가 없어 머지 API가 405를 낸다(2026-08-31 실측).
    if mergeable_state == "behind":
        v.reasons.append("base 전진 — origin/main 재병합 후 push 필요(strict policy)")
        v.ready = False
    elif mergeable_state == "dirty":
        v.reasons.append("머지 충돌 — 해소 필요")
        v.ready = False

    if unresolved_threads > 0:
        v.reasons.append(
            f"미해결 리뷰 스레드 {unresolved_threads}건 (required_review_thread_resolution)"
        )
        v.ready = False

    # 비필수 실패는 정보로만 — 머지를 막지 않는다는 사실을 눈에 보이게 한다.
    for name in sorted(set(runs) - required):
        if runs[name] not in SATISFYING and runs[name] is not None:
            v.reasons.append(f"(비필수·머지 차단 안 함) 실패: {name}")

    if v.ready:
        v.reasons.append("필수 체크 전부 충족 · up-to-date · 스레드 해소 — 지금 머지")
    return v


def _get(path: str) -> object:
    cmd = ["curl", "-sS", "--max-time", str(TIMEOUT), "--cacert", CA, f"{API}{path}"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 10)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"❌ 타임아웃({TIMEOUT}s): {path}") from exc
    if out.returncode != 0:
        raise SystemExit(f"❌ curl 실패(rc={out.returncode}): {path}\n{out.stderr[:400]}")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"❌ JSON 파싱 실패: {path}\n앞 400자: {out.stdout[:400]}") from exc


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"사용: {sys.argv[0]} <owner/repo> <pr-number>")
    repo, pr = sys.argv[1], sys.argv[2]

    rules = _get(f"/repos/{repo}/rules/branches/main")
    required = {
        c["context"]
        for r in rules
        if isinstance(r, dict) and r.get("type") == "required_status_checks"
        for c in r.get("parameters", {}).get("required_status_checks", [])
    }
    if not required:
        raise SystemExit("❌ 필수 체크 0건 — 규칙 미조회/권한 부족(측정 실패, 통과 아님)")

    pr_data = _get(f"/repos/{repo}/pulls/{pr}")
    if not isinstance(pr_data, dict) or "head" not in pr_data:
        raise SystemExit(f"❌ PR 조회 실패: {str(pr_data)[:300]}")
    sha = pr_data["head"]["sha"]

    cr = _get(f"/repos/{repo}/commits/{sha}/check-runs?per_page=100")
    runs = {
        c["name"]: (c.get("conclusion") if c.get("status") == "completed" else None)
        for c in (cr.get("check_runs", []) if isinstance(cr, dict) else [])
    }
    if not runs:
        print(f"⚠ head {sha[:8]} 에 체크런 0건 — 트리거 미발화 의심(HARN-30)")

    v = decide(
        required,
        runs,
        mergeable_state=str(pr_data.get("mergeable_state")),
        unresolved_threads=0,  # 스레드는 GraphQL 필요 — 현행은 0 가정(한계 명시)
    )
    print(f"PR #{pr} · head {sha[:8]} · mergeable_state={pr_data.get('mergeable_state')}")
    print(f"필수 {len(required)}종 / 관측된 체크런 {len(runs)}건")
    for r in v.reasons:
        print(f"  · {r}")
    print(
        "\n한계: 미해결 리뷰 스레드는 GraphQL이 필요해 이 도구가 보지 않는다 "
        "— required_review_thread_resolution=true 이므로 스레드가 남아 있으면 "
        "여기서 ready여도 머지 API가 거부한다(2026-08-31 실측)."
    )
    return 0 if v.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
