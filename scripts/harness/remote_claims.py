"""원격 claim — refs/claims/* 네임스페이스, git ref push의 CAS 원자성 이용.

배경: 태스크 claim(Task.session)은 각 세션 worktree의 backlog/ 사본에만 기록되어
merge 전까지 병렬 세션끼리 서로 보이지 않는다(TOCTOU 레이스). 이 모듈은 origin에
`refs/claims/<task-id>` ref를 push해 claim을 실시간 공유한다.

원자성 (CAS — compare-and-swap):
    git push --force-with-lease=refs/claims/<id>: origin <blob>:refs/claims/<id>
    expect가 빈 값인 force-with-lease = "원격에 그 ref가 아직 없어야만 성공".
    서버가 ref 갱신을 트랜잭션 처리하므로 두 세션이 동시에 push해도 정확히
    한쪽만 성공한다 — lock 파일 없는 진짜 원자적 claim.
    2차 방어: blob→blob 갱신은 ancestry가 없어 non-fast-forward로 항상 거부.

폴백 (fail-open — 훅·CLI가 개발을 볼모로 잡지 않는다):
    - offline/error(네트워크·권한): 경고 + 이벤트 로그 후 로컬 claim만으로 진행.
    - conflict(다른 세션이 이미 claim): 정보가 확정적이므로 이것만 차단.
    원격이 refs/claims/* push 자체를 거부하는 환경(프록시 정책 등)에서도
    offline으로 분류되어 기능 저하는 로컬 claim 수준에 그친다.

stale claim 청소: 세션이 release 없이 죽으면 ref가 남는다 → `claims reap`이
3중 기준(TTL 초과·태스크 이미 done/cancelled·태스크 미존재)으로 감지·삭제.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import Backlog

CLAIMS_NS = "refs/claims"
# 메타 fetch용 로컬 미러 네임스페이스 (로컬 refs와 충돌 없는 전용 공간)
LOCAL_MIRROR_NS = "refs/whymath-claims"

# push 거부(=이미 claim됨) 판별 패턴 — git 버전별 문구 차이 흡수
_CONFLICT_MARKERS = ("[rejected]", "stale info", "already exists", "non-fast-forward")
# 네트워크·환경 문제 판별 패턴
_OFFLINE_MARKERS = (
    "could not resolve", "unable to access", "connection", "timed out",
    "no such remote", "does not appear to be a git repository",
    "could not read from remote",
)


@dataclass
class RemoteClaim:
    """원격 claim 1건 = refs/claims/<task_id> ref 1개."""

    task_id: str
    sha: str
    branch: str = ""        # 메타 fetch 후 채워짐
    ts: str = ""            # UTC ISO8601
    meta: dict | None = None


@dataclass
class ClaimResult:
    """claim/release 시도 결과."""

    status: str                          # ok | conflict | offline | error
    claim: RemoteClaim | None = None     # conflict 시 상대 claim 정보 (메타 조회 성공 시)
    message: str = ""


def _git(root: Path, *argv: str, timeout: int = 15,
         input_text: str | None = None) -> subprocess.CompletedProcess:
    """git 실행 — 테스트 monkeypatch 지점. 인증 프롬프트 행 방지."""
    import os
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", *argv], cwd=root, capture_output=True, text=True,
        timeout=timeout, input=input_text, env=env,
    )


def has_remote(root: Path) -> bool:
    """origin 원격이 설정되어 있는가."""
    try:
        return _git(root, "remote", "get-url", "origin", timeout=10).returncode == 0
    except Exception:
        return False


def _classify_failure(stderr: str) -> str:
    """push 실패 stderr → conflict | offline | error."""
    low = stderr.lower()
    if any(m in low for m in _CONFLICT_MARKERS):
        return "conflict"
    if any(m in low for m in _OFFLINE_MARKERS):
        return "offline"
    return "error"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def claim(root: Path, task_id: str, branch: str) -> ClaimResult:
    """태스크를 원자적으로 원격 claim. 이미 claim되어 있으면 conflict."""
    if not has_remote(root):
        return ClaimResult("offline", message="origin 원격 없음 — 로컬 claim만 사용")
    meta = {
        "task": task_id,
        "branch": branch,
        "ts": _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "harness": "1.1",
    }
    try:
        blob = _git(root, "hash-object", "-w", "--stdin",
                    input_text=json.dumps(meta, ensure_ascii=False))
        if blob.returncode != 0:
            return ClaimResult("error", message=f"blob 생성 실패: {blob.stderr.strip()}")
        sha = blob.stdout.strip()
        ref = f"{CLAIMS_NS}/{task_id}"
        # CAS: expect 빈 값 = "원격에 ref가 없어야만 성공"
        push = _git(root, "push", "--quiet", f"--force-with-lease={ref}:",
                    "origin", f"{sha}:{ref}")
        if push.returncode == 0:
            return ClaimResult("ok", claim=RemoteClaim(task_id, sha, branch, meta["ts"], meta))
        status = _classify_failure(push.stderr)
        if status == "conflict":
            other = _describe_existing(root, task_id)
            return ClaimResult("conflict", claim=other,
                               message=push.stderr.strip().splitlines()[-1] if push.stderr else "")
        return ClaimResult(status, message=push.stderr.strip())
    except subprocess.TimeoutExpired:
        return ClaimResult("offline", message="git push 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        return ClaimResult("error", message=str(exc))


def _describe_existing(root: Path, task_id: str) -> RemoteClaim | None:
    """conflict 시 상대 claim의 메타를 best-effort 조회."""
    claims, status = list_claims(root, with_meta=True)
    if status != "ok":
        return None
    for c in claims:
        if c.task_id == task_id:
            return c
    return None


def release(root: Path, task_id: str, branch: str, force: bool = False) -> ClaimResult:
    """원격 claim 해제. 기본은 내 branch의 claim만 — 남의 claim은 force 필수."""
    if not has_remote(root):
        return ClaimResult("offline", message="origin 원격 없음")
    try:
        if not force:
            claims, status = list_claims(root, with_meta=True)
            if status == "ok":
                mine = next((c for c in claims if c.task_id == task_id), None)
                if mine is None:
                    return ClaimResult("ok", message="원격 claim 없음 (해제 불필요)")
                if mine.branch and mine.branch != branch:
                    return ClaimResult(
                        "error", claim=mine,
                        message=f"'{mine.branch}'의 claim — 강제 해제는 --force 필수",
                    )
            # status != ok(offline 등)면 메타 확인 불가 — 해제 시도는 계속 (fail-open)
        push = _git(root, "push", "--quiet", "origin", f":{CLAIMS_NS}/{task_id}")
        if push.returncode == 0:
            return ClaimResult("ok")
        low = push.stderr.lower()
        # 이미 없는 ref 삭제 시도는 성공으로 간주 (멱등성)
        if "unable to delete" in low and "remote ref does not exist" in low:
            return ClaimResult("ok", message="원격 claim 이미 없음")
        return ClaimResult(_classify_failure(push.stderr), message=push.stderr.strip())
    except subprocess.TimeoutExpired:
        return ClaimResult("offline", message="git push 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        return ClaimResult("error", message=str(exc))


def list_claims(root: Path, with_meta: bool = False) -> tuple[list[RemoteClaim], str]:
    """원격 claim 목록. (목록, 상태) — 상태 ok|offline|error."""
    if not has_remote(root):
        return [], "offline"
    try:
        ls = _git(root, "ls-remote", "origin", f"{CLAIMS_NS}/*")
        if ls.returncode != 0:
            return [], _classify_failure(ls.stderr)
        claims: list[RemoteClaim] = []
        for line in ls.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            sha, ref = parts
            claims.append(RemoteClaim(task_id=ref[len(CLAIMS_NS) + 1:], sha=sha))
        if with_meta and claims:
            fetch_claim_meta(root, claims)
        return claims, "ok"
    except subprocess.TimeoutExpired:
        return [], "offline"
    except Exception:  # pragma: no cover - 환경 의존
        return [], "error"


def fetch_claim_meta(root: Path, claims: list[RemoteClaim]) -> None:
    """claim blob들의 메타 JSON을 fetch해 in-place 보강 (best-effort)."""
    try:
        fetch = _git(root, "fetch", "--quiet", "origin",
                     f"+{CLAIMS_NS}/*:{LOCAL_MIRROR_NS}/*", timeout=20)
        if fetch.returncode != 0:
            return
        for c in claims:
            cat = _git(root, "cat-file", "blob", c.sha, timeout=10)
            if cat.returncode != 0:
                continue
            try:
                meta = json.loads(cat.stdout)
            except json.JSONDecodeError:
                continue
            c.meta = meta
            c.branch = str(meta.get("branch", ""))
            c.ts = str(meta.get("ts", ""))
    except Exception:  # pragma: no cover - 환경 의존
        return


def stale_claims(claims: list[RemoteClaim], backlog: Backlog, ttl_hours: int,
                 now: datetime | None = None) -> list[tuple[RemoteClaim, str]]:
    """stale claim 판정 — (claim, 사유) 목록. 사유: ttl | task_done | task_missing."""
    now = now or _utcnow()
    result: list[tuple[RemoteClaim, str]] = []
    for c in claims:
        task = backlog.tasks.get(c.task_id)
        if task is None:
            result.append((c, "task_missing"))
            continue
        if task.status in ("done", "cancelled"):
            result.append((c, "task_done"))
            continue
        if c.ts:
            try:
                ts = datetime.strptime(c.ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if now - ts > timedelta(hours=ttl_hours):
                    result.append((c, "ttl"))
            except ValueError:
                pass  # 파싱 불가 메타는 판정 보류 (보수적)
    return result


def reap(root: Path, backlog: Backlog, ttl_hours: int,
         dry_run: bool = True) -> list[str]:
    """stale claim 청소. dry_run이면 목록만 반환, 아니면 실제 삭제.

    반환: "task_id (사유)" 문자열 목록.
    """
    claims, status = list_claims(root, with_meta=True)
    if status != "ok":
        return []
    stale = stale_claims(claims, backlog, ttl_hours)
    reaped: list[str] = []
    for c, reason in stale:
        label = f"{c.task_id} ({reason}" + (f", {c.branch}" if c.branch else "") + ")"
        if not dry_run:
            result = release(root, c.task_id, branch="", force=True)
            if result.status != "ok":
                continue
        reaped.append(label)
    return reaped
