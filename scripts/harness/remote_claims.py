"""원격 claim — 단일 `harness-claims` 브랜치, git ref push의 CAS 원자성 이용.

배경: 태스크 claim(Task.session)은 각 세션 worktree의 backlog/ 사본에만 기록되어
merge 전까지 병렬 세션끼리 서로 보이지 않는다(TOCTOU 레이스). 이 모듈은 origin의
`refs/heads/harness-claims` 브랜치에 `claims/<task-id>.json`을 두어 claim을 실시간
공유한다.

왜 브랜치인가 (HARN-09 — 네임스페이스 이전):
    원래 설계는 `refs/claims/<id>`였으나 **이 실행 환경의 git 프록시가 그 네임스페이스
    push를 거부**한다(HTTP 403 → hung up). 2026-07-28 실측이 원인을 좁혔다:

        refs/claims/<id>  blob push  → 거부
        refs/heads/<id>   커밋 push  → **성공**

    권한이 아니라 네임스페이스 문제였다. 그래서 브랜치 네임스페이스로 옮긴다.
    **태스크당 브랜치가 아니라 단일 브랜치**인 이유는 같은 프록시가 ref *삭제*도
    거부하기 때문이다 — 태스크당 브랜치면 해제가 불가능해 93개+가 영구 누적된다.
    단일 브랜치면 해제가 그냥 "파일을 지우는 커밋"이라 삭제 push가 아예 불필요하다.

원자성 (CAS — compare-and-swap):
    git push --force-with-lease=refs/heads/harness-claims:<base-sha> \
             origin <commit>:refs/heads/harness-claims
    lease가 base sha와 다르면(= 그 사이 남이 push했으면) 서버가 거부한다. 서버는 ref
    갱신을 트랜잭션 처리하므로 두 세션이 동시에 push해도 정확히 한쪽만 성공한다 —
    lock 파일 없는 진짜 원자적 claim. 브랜치 최초 생성은 lease를 빈 값으로 준다
    (= "그 ref가 아직 없어야만 성공").

    **경합 재시도**: lease 거부는 "이 태스크가 남에게 잡혔다"가 아니라 "그 사이 *누군가*
    브랜치를 갱신했다"는 뜻이다(대개 다른 태스크의 claim). 그래서 재fetch 후 재시도하며,
    재시도 중 내 태스크가 실제로 잡혔음을 트리에서 확인했을 때만 conflict로 판정한다.
    **태스크 점유 판정은 push stderr가 아니라 트리 내용이 결정한다** — 이 분리가
    "남의 claim"과 "동시 갱신"을 혼동하지 않게 한다.

    트리는 `git mktree`로 직접 만든다(인덱스 미사용) — 사용자의 인덱스·작업 트리를
    건드릴 수 없는 구조라 GIT_INDEX_FILE 오염 위험이 원천 차단된다.

폴백 (fail-open — 훅·CLI가 개발을 볼모로 잡지 않는다):
    - offline/error(네트워크·권한): 경고 + 이벤트 로그 후 아래 *읽기측 탐지*로 폴백.
    - conflict(다른 세션이 이미 claim): 정보가 확정적이므로 이것만 차단.

읽기측 교차 세션 탐지 (HARN-07 — CAS가 막힌 환경의 부분 방어):
    HARN-09 이전에는 CAS가 **한 번도 성공한 적이 없어**(위 403) fail-open이 모든
    start를 통과시켰고, 중복 방지가 상시 무력이었다 — 그 결과가 병렬 중복 구현 2회
    (OPS-07 → #611, OPS-12 → #618)다. 쓰기가 막혀도 **읽기는 됐으므로**
    `scan_remote_in_progress()`가 원격 브랜치들의 backlog 사본을 읽어 같은 태스크가
    이미 in_progress인지 탐지한다.

    HARN-09로 CAS가 복구된 뒤에도 이 경로는 **제거하지 않는다** — 진짜 오프라인·권한
    문제로 CAS가 실패하는 환경에서 여전히 2선 방어다. 다만 CAS가 성공하면 읽기측
    스캔은 돌지 않는다(중복이며 느리다).

    이것은 CAS의 대체가 아니라 *부분* 방어다 (과장 금지):
      · 상대 세션이 **브랜치를 push한 뒤에만** 보인다 — push 전 로컬에서 작업 중인
        세션은 이 방법으로 절대 잡히지 않는다.
      · **원자성이 없다** — 두 세션이 동시에 스캔하면 둘 다 "충돌 없음"을 볼 수 있다.
    그러므로 CAS 경로는 제거하지 않는다. 프록시 정책이 다른 환경(로컬 개발·다른 러너)
    에서는 CAS가 작동하며 원자성은 그쪽이 우월하다. 읽기측은 CAS 실패 시에만 돈다.

stale 홀더 처리 (HARN-08 — 읽기측의 과탐 해소):
    머지·폐기된 브랜치에 남은 in_progress가 그 태스크를 **영구 차단**하던 문제를
    2개 규칙으로 해소한다(SQUASH 머지 저장소라 조상 검사는 쓸 수 없다 — 머지된
    브랜치도 trunk의 조상이 아니다. 2026-07-27 5건 전수 실측):
      · 규칙 A(트렁크 권위) — 트렁크(origin/HEAD)의 사본이 done/cancelled면 그 작업은
        이미 착륙했다. 다른 브랜치 사본의 in_progress는 역사적 잔재 → 홀더 전부 무시.
      · 규칙 B(트렁크는 세션이 아니다) — claim의 의미는 "어떤 *세션*이 그 브랜치에서
        작업 중"이다. 트렁크는 머지된 결과지 작업 세션이 아니므로 홀더 후보에서 제외.
        트렁크에 남은 in_progress는 활성 claim이 아니라 대장 위생 실패(done 미기입 머지)다.
    나이(최종 커밋 경과일) 휴리스틱은 **의도적으로 넣지 않았다** — 실측 5건이 A+B로
    전부 해소되며, 나이 컷오프는 느리게 진행하는 실 세션을 오탐 해제할 위험만 더한다.
    걸러낸 홀더는 버리지 않고 ScanResult.skipped에 사유와 함께 남긴다(관측 가능성).

stale claim 청소: 세션이 release 없이 죽으면 claim 파일이 남는다 → `claims reap`이
3중 기준(TTL 초과·태스크 이미 done/cancelled·태스크 미존재)으로 감지·삭제.

    ⚠️ `list_claims`의 **상태값을 반드시 확인하라**. "claim 0건"과 "조회 실패"를
    구분하지 않으면 인프라가 죽었을 때 "0건 통과"로 위장된다 — HARN-09 착수 실측에서
    CI의 교차검증 스텝이 정확히 그 상태였다(refs/claims/*가 0건이라 `reap`이 늘
    "stale claim 없음"을 보고). 빈 목록은 상태가 ok일 때만 "없음"을 의미한다.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import Backlog

# claim 저장소 = origin의 단일 브랜치. 태스크당 파일 1개.
CLAIMS_BRANCH = "harness-claims"
CLAIMS_REF = f"refs/heads/{CLAIMS_BRANCH}"
CLAIMS_DIR = "claims"
# 로컬 미러 ref (로컬 브랜치와 충돌 없는 전용 공간 — 체크아웃 대상이 아니다)
LOCAL_MIRROR_REF = "refs/whymath-claims/head"
# lease 거부 후 재시도 횟수. 경합은 "남이 *다른* 태스크를 claim했다"가 대부분이라
# 몇 번이면 수렴한다. 무한 재시도는 start를 볼모로 잡으므로 유한하게 자른다.
CAS_RETRIES = 3

# push 거부 = **lease 경합**(그 사이 남이 브랜치를 갱신) 판별 패턴.
# 주의: 이것은 "내 태스크가 잡혔다"가 아니다 — 태스크 점유는 트리에서만 판정한다.
_LEASE_MARKERS = ("[rejected]", "stale info", "already exists", "non-fast-forward", "fetch first")
# 네트워크·환경 문제 판별 패턴
_OFFLINE_MARKERS = (
    "could not resolve",
    "unable to access",
    "connection",
    "timed out",
    "no such remote",
    "does not appear to be a git repository",
    "could not read from remote",
)


@dataclass
class RemoteClaim:
    """원격 claim 1건 = refs/claims/<task_id> ref 1개."""

    task_id: str
    sha: str
    branch: str = ""  # 메타 fetch 후 채워짐
    ts: str = ""  # UTC ISO8601
    meta: dict | None = None


@dataclass
class ClaimResult:
    """claim/release 시도 결과."""

    status: str  # ok | conflict | offline | error
    claim: RemoteClaim | None = None  # conflict 시 상대 claim 정보 (메타 조회 성공 시)
    message: str = ""


def _git(
    root: Path,
    *argv: str,
    timeout: int = 15,
    input_text: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """git 실행 — 테스트 monkeypatch 지점. 인증 프롬프트 행 방지.

    `env_extra`는 `commit-tree`의 신원(author/committer)용이다. CI 러너나 갓 만든
    클론에는 `user.email`이 없어 commit-tree가 실패할 수 있는데, claim 커밋은 사람의
    저작물이 아니라 하네스의 기록이므로 전역 git 설정에 의존하지 않는다.
    """
    import os

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env_extra or {})}
    return subprocess.run(
        ["git", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
        env=env,
    )


# claim 커밋의 고정 신원 — 전역 git 설정 부재 환경에서도 commit-tree가 성립하게 한다.
_COMMIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "whymath-harness",
    "GIT_AUTHOR_EMAIL": "harness@whymath.invalid",
    "GIT_COMMITTER_NAME": "whymath-harness",
    "GIT_COMMITTER_EMAIL": "harness@whymath.invalid",
}


def has_remote(root: Path) -> bool:
    """origin 원격이 설정되어 있는가."""
    try:
        return _git(root, "remote", "get-url", "origin", timeout=10).returncode == 0
    except Exception:
        return False


def _classify_failure(stderr: str) -> str:
    """git 실패 stderr → lease | offline | error.

    `lease`는 **경합 재시도** 신호이지 태스크 점유가 아니다(모듈 docstring 참조).
    태스크 점유는 오직 claim 브랜치의 트리를 읽어 판정한다.
    """
    low = stderr.lower()
    if any(m in low for m in _LEASE_MARKERS):
        return "lease"
    if any(m in low for m in _OFFLINE_MARKERS):
        return "offline"
    return "error"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── claim 캐시 — check-edit 훅용 (편집마다 네트워크 조회 금지) ────────────────
# brief/next/start가 원격 조회에 성공할 때마다 스냅샷을 남기고, 훅은 이것만 읽는다.
# .git/ 아래라 커밋 대상이 아니며 세션(클론)별 독립이다.


def _cache_path(root: Path) -> Path:
    return root / ".git" / "whymath-claims-cache.json"


def save_cache(root: Path, claims: list[RemoteClaim]) -> None:
    """원격 claim 스냅샷 저장 (best-effort — 실패 무시)."""
    try:
        payload = [{"task": c.task_id, "branch": c.branch, "ts": c.ts} for c in claims]
        _cache_path(root).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_cache(root: Path) -> dict[str, str]:
    """캐시된 claim 스냅샷 로드 — task_id → branch (실패 시 빈 dict)."""
    try:
        raw = json.loads(_cache_path(root).read_text(encoding="utf-8"))
        return {str(e["task"]): str(e.get("branch", "?")) for e in raw}
    except Exception:
        return {}


def _claim_path(task_id: str) -> str:
    return f"{CLAIMS_DIR}/{task_id}.json"


def _fetch_claims_branch(root: Path) -> tuple[str, str]:
    """claim 브랜치를 로컬 미러로 가져온다 → (base_sha, 상태).

    base_sha가 빈 문자열이면 **브랜치가 아직 없다**(= claim 0건). 이것은 정상 상태이며
    상태 ok로 보고한다 — 조회 실패(offline/error)와 구분되어야 한다. 그 구분이 없으면
    인프라 장애가 "0건 통과"로 위장된다.
    """
    ls = _git(root, "ls-remote", "origin", CLAIMS_REF, timeout=20)
    if ls.returncode != 0:
        return "", _classify_failure(ls.stderr)
    if not ls.stdout.strip():
        return "", "ok"  # 브랜치 미존재 = claim 0건
    fetch = _git(
        root,
        "fetch",
        "--quiet",
        "--force",
        "origin",
        f"+{CLAIMS_REF}:{LOCAL_MIRROR_REF}",
        timeout=30,
    )
    if fetch.returncode != 0:
        return "", _classify_failure(fetch.stderr)
    rev = _git(root, "rev-parse", LOCAL_MIRROR_REF, timeout=10)
    if rev.returncode != 0:
        return "", "error"
    return rev.stdout.strip(), "ok"


def _read_claims(root: Path, base_sha: str) -> list[RemoteClaim]:
    """base 커밋의 트리에서 claim 전건을 읽는다 — 왕복 없이 로컬 객체만 본다."""
    if not base_sha:
        return []
    ls = _git(root, "ls-tree", "-r", "-z", base_sha, "--", f"{CLAIMS_DIR}/", timeout=15)
    if ls.returncode != 0:
        return []
    claims: list[RemoteClaim] = []
    for entry in ls.stdout.split("\0"):
        if not entry.strip():
            continue
        info, _, path = entry.partition("\t")
        fields = info.split()
        if len(fields) < 3 or fields[1] != "blob":
            continue
        blob_sha = fields[2]
        if not path.startswith(f"{CLAIMS_DIR}/") or not path.endswith(".json"):
            continue
        task_id = path[len(CLAIMS_DIR) + 1 : -len(".json")]
        cat = _git(root, "cat-file", "blob", blob_sha, timeout=10)
        meta: dict | None = None
        if cat.returncode == 0:
            try:
                meta = json.loads(cat.stdout)
            except json.JSONDecodeError:
                meta = None
        claims.append(
            RemoteClaim(
                task_id=task_id,
                sha=blob_sha,
                branch=str((meta or {}).get("branch", "")),
                ts=str((meta or {}).get("ts", "")),
                meta=meta,
            )
        )
    return claims


def _write_claims(root: Path, base_sha: str, claims: list[RemoteClaim], message: str) -> str:
    """claim 목록을 담은 커밋을 만들어 sha를 돌려준다 (push는 하지 않는다).

    트리는 `git mktree`로 직접 만든다 — **인덱스를 쓰지 않으므로** 사용자의 스테이징
    영역·작업 트리를 건드릴 수 없다(구조적 차단).
    """
    entries: list[str] = []
    for c in sorted(claims, key=lambda x: x.task_id):
        payload = json.dumps(c.meta or {}, ensure_ascii=False, sort_keys=True)
        blob = _git(root, "hash-object", "-w", "--stdin", input_text=payload)
        if blob.returncode != 0:
            raise RuntimeError(f"blob 생성 실패: {blob.stderr.strip()}")
        entries.append(f"100644 blob {blob.stdout.strip()}\t{c.task_id}.json")

    if entries:
        sub = _git(root, "mktree", input_text="\n".join(entries) + "\n")
        if sub.returncode != 0:
            raise RuntimeError(f"claims 트리 생성 실패: {sub.stderr.strip()}")
        root_entries = f"040000 tree {sub.stdout.strip()}\t{CLAIMS_DIR}\n"
    else:
        root_entries = ""  # claim 0건 = 빈 트리 (해제로 마지막 claim이 사라진 경우)

    tree = _git(root, "mktree", input_text=root_entries)
    if tree.returncode != 0:
        raise RuntimeError(f"루트 트리 생성 실패: {tree.stderr.strip()}")

    argv = ["commit-tree", tree.stdout.strip()]
    if base_sha:
        argv += ["-p", base_sha]
    argv += ["-m", message]
    commit = _git(root, *argv, env_extra=_COMMIT_IDENTITY)
    if commit.returncode != 0:
        raise RuntimeError(f"커밋 생성 실패: {commit.stderr.strip()}")
    return commit.stdout.strip()


def _push_claims(root: Path, base_sha: str, commit_sha: str) -> subprocess.CompletedProcess:
    """CAS push — lease가 base_sha와 다르면 서버가 거부한다."""
    return _git(
        root,
        "push",
        "--quiet",
        f"--force-with-lease={CLAIMS_REF}:{base_sha}",
        "origin",
        f"{commit_sha}:{CLAIMS_REF}",
        timeout=30,
    )


def _mutate_claims(
    root: Path,
    task_id: str,
    message: str,
    apply: "callable",
) -> ClaimResult:
    """fetch → 검사 → 커밋 → CAS push를 lease 경합에 대해 재시도하는 공통 루프.

    `apply(existing, current_claims)`는 (새 목록, 조기반환 ClaimResult|None)을 돌려준다.
    조기반환이 있으면 push 없이 그대로 반환한다(예: 남의 claim이라 conflict).
    """
    last = ""
    for _attempt in range(CAS_RETRIES):
        base_sha, status = _fetch_claims_branch(root)
        if status != "ok":
            return ClaimResult(status, message=f"claim 브랜치 조회 실패: {status}")
        current = _read_claims(root, base_sha)
        existing = next((c for c in current if c.task_id == task_id), None)
        new_claims, early = apply(existing, current)
        if early is not None:
            return early
        try:
            commit_sha = _write_claims(root, base_sha, new_claims, message)
        except RuntimeError as exc:
            return ClaimResult("error", message=str(exc))
        push = _push_claims(root, base_sha, commit_sha)
        if push.returncode == 0:
            return ClaimResult("ok")
        last = push.stderr.strip()
        kind = _classify_failure(push.stderr)
        if kind != "lease":
            return ClaimResult(kind, message=last)
        # lease 경합 — 그 사이 남이 브랜치를 갱신했다. 재fetch 후 다시 시도한다.
        # (내 태스크가 실제로 잡혔는지는 다음 회차의 트리 검사가 판정한다.)
    return ClaimResult(
        "error",
        message=f"CAS 재시도 {CAS_RETRIES}회 초과 (lease 경합 지속): {last}",
    )


def claim(root: Path, task_id: str, branch: str) -> ClaimResult:
    """태스크를 원자적으로 원격 claim. 이미 다른 세션이 잡고 있으면 conflict."""
    if not has_remote(root):
        return ClaimResult("offline", message="origin 원격 없음 — 로컬 claim만 사용")
    meta = {
        "task": task_id,
        "branch": branch,
        "ts": _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "harness": "2.0",
    }
    mine = RemoteClaim(task_id, "", branch, str(meta["ts"]), meta)

    def apply(
        existing: RemoteClaim | None, current: list[RemoteClaim]
    ) -> tuple[list[RemoteClaim], ClaimResult | None]:
        if existing is not None and existing.branch != branch:
            # 태스크 점유 판정은 **트리 내용**이 한다 — push stderr가 아니라.
            #
            # `existing.branch`가 비어 있어도(메타 파손·구버전 기록) **conflict로 친다**.
            # "홀더를 특정할 수 없으니 통과"는 조용한 탈취이고, 그건 이 모듈이 막으려는
            # 바로 그 사고다. 막힌 경우의 복구 경로는 `claims release --force`로 명시한다.
            holder = existing.branch or "홀더 불명(메타 파손)"
            return [], ClaimResult(
                "conflict",
                claim=existing,
                message=f"'{holder}'가 이미 claim (ts={existing.ts or '?'})"
                + ("" if existing.branch else f" — 복구: claims release {task_id} --force"),
            )
        others = [c for c in current if c.task_id != task_id]
        return [*others, mine], None

    try:
        result = _mutate_claims(root, task_id, f"claim {task_id} ({branch})", apply)
        if result.status == "ok" and result.claim is None:
            result.claim = mine
        return result
    except subprocess.TimeoutExpired:
        return ClaimResult("offline", message="git 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        return ClaimResult("error", message=f"{type(exc).__name__}: {exc}")


def release(root: Path, task_id: str, branch: str, force: bool = False) -> ClaimResult:
    """원격 claim 해제 = claim 파일을 지우는 커밋. 남의 claim은 force 필수.

    ref 삭제 push를 쓰지 않는다 — 이 환경의 프록시가 삭제를 거부하기 때문이며,
    그 제약이 단일 브랜치 설계를 고른 이유다(모듈 docstring 참조).
    """
    if not has_remote(root):
        return ClaimResult("offline", message="origin 원격 없음")

    def apply(
        existing: RemoteClaim | None, current: list[RemoteClaim]
    ) -> tuple[list[RemoteClaim], ClaimResult | None]:
        if existing is None:
            return [], ClaimResult("ok", message="원격 claim 없음 (해제 불필요)")
        if not force and existing.branch and existing.branch != branch:
            return [], ClaimResult(
                "error",
                claim=existing,
                message=f"'{existing.branch}'의 claim — 강제 해제는 --force 필수",
            )
        return [c for c in current if c.task_id != task_id], None

    try:
        return _mutate_claims(root, task_id, f"release {task_id}", apply)
    except subprocess.TimeoutExpired:
        return ClaimResult("offline", message="git 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        return ClaimResult("error", message=f"{type(exc).__name__}: {exc}")


def list_claims(root: Path, with_meta: bool = False) -> tuple[list[RemoteClaim], str]:
    """원격 claim 목록. (목록, 상태) — 상태 ok|offline|error.

    ⚠️ 호출자는 **상태를 반드시 확인**하라. 빈 목록은 상태가 ok일 때만 "claim 없음"을
    뜻한다. 상태를 무시하면 조회 실패가 "0건"으로 위장된다(모듈 docstring 참조).

    `with_meta`는 이제 무의미하다 — 브랜치 트리를 읽는 순간 메타가 함께 온다
    (구 구현은 ref마다 왕복했다). 호출부 호환을 위해 인자만 남긴다.
    """
    if not has_remote(root):
        return [], "offline"
    try:
        base_sha, status = _fetch_claims_branch(root)
        if status != "ok":
            return [], status
        return _read_claims(root, base_sha), "ok"
    except subprocess.TimeoutExpired:
        return [], "offline"
    except Exception:  # pragma: no cover - 환경 의존
        return [], "error"


def fetch_claim_meta(root: Path, claims: list[RemoteClaim]) -> None:
    """구 API 호환 — 메타는 `list_claims`가 이미 채운다(별도 왕복 불요)."""
    return


# ── 읽기측 교차 세션 탐지 (HARN-07) ─────────────────────────────────────────
# CAS push가 막힌 환경의 폴백. 쓰기는 403이어도 읽기(fetch/ls-remote)는 통과한다는
# 실측(2026-07-27)에 근거한다. 한계는 모듈 docstring 참조 — CAS 대체 아님.

# 원격 브랜치 스캔 상한 — 브랜치가 폭증한 저장소에서 start가 볼모가 되지 않게 자른다.
# 최근 커밋순으로 자르며, 잘렸으면 결과에 명시한다(조용한 축소 금지).
SCAN_MAX_REFS = 300
# 전체 브랜치 fetch 타임아웃 — 44브랜치 기준 실측 ~5초. 콜드 클론 여유 포함.
SCAN_FETCH_TIMEOUT = 90
REMOTE_REF_PREFIX = "refs/remotes/origin/"
# 트렁크 ref 해소 실패 시의 최종 폴백 브랜치명 (_resolve_trunk_ref 주석 참조)
FALLBACK_TRUNK_BRANCH = "main"
# 규칙 A — 트렁크에서 이 상태면 작업이 착륙한 것으로 본다 (둘 다 models.py 종결 상태)
TRUNK_SETTLED_STATUSES = ("done", "cancelled")


@dataclass
class InProgressHolder:
    """원격 브랜치의 backlog 사본에서 발견한 타 세션 in_progress claim 1건."""

    task_id: str
    ref: str  # refs/remotes/origin/<branch>
    branch: str  # <branch>
    session: str  # 태스크 YAML의 session 값 (claim한 세션 브랜치)


@dataclass
class SkippedHolder:
    """stale 판정으로 홀더에서 제외한 1건 (HARN-08).

    조용히 버리지 않는다 — 무엇을 왜 무시했는지 호출자가 보고할 수 있어야
    "보호가 걸렸다"와 "보호를 스스로 껐다"가 구분된다.
    """

    task_id: str
    ref: str
    branch: str
    session: str
    reason: str  # trunk_done | trunk_cancelled | trunk_not_session


@dataclass
class ScanResult:
    """읽기측 탐지 결과. status: ok | offline | error (ok가 아니면 판정 불가)."""

    status: str
    holders: list[InProgressHolder] = field(default_factory=list)
    skipped: list[SkippedHolder] = field(default_factory=list)
    scanned_refs: int = 0
    truncated: bool = False
    message: str = ""
    trunk_ref: str = ""  # 규칙 A·B의 기준 ref (refs/remotes/origin/<기본브랜치>)
    trunk_branch: str = ""  # 기준 ref의 브랜치명 (메시지용)
    trunk_status: str = ""  # 트렁크 사본의 태스크 status ("" = 파일 없음 → 규칙 A 신호 없음)
    trunk_source: str = ""  # symbolic-ref | ls-remote | fallback (해소 경로 — 관측용)


def _top_level_field(text: str, key: str) -> str:
    """태스크 YAML 본문에서 최상위 스칼라 키 1개를 뽑는다 (PyYAML 비의존).

    store.dump_task는 1단 매핑만 쓰고 리스트는 '  - ' 들여쓰기로 내므로,
    들여쓰기 없는 '<key>: ' 줄만 보면 값 안의 콜론과 충돌하지 않는다.
    손편집으로 형식이 어긋난 파일은 못 읽고 넘어간다 — 탐지 실패는 미탐이며,
    미탐은 호출측이 '부분 방어'로 이미 선언한 한계 안에 있다.
    """
    prefix = f"{key}:"
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        return "" if value in ("null", "~", "") else value
    return ""


def _resolve_trunk_ref(root: Path) -> tuple[str, str]:
    """기본(트렁크) 브랜치의 원격 ref를 해소한다 — (ref, 해소 경로).

    기본 브랜치명을 하드코딩하지 않는다 (main/master/trunk 어느 쪽이든 따라간다).
    **원격 권위를 먼저 묻는다** — 순서가 핵심이다:
      1) `git ls-remote --symref origin HEAD` — 원격이 지금 무엇을 HEAD로 두는지
         직접 묻는다(실측 0.3초). 읽기측 스캔은 어차피 전체 fetch(~5초)를 하므로
         왕복 1회는 예산 안이다.
      2) `git symbolic-ref refs/remotes/origin/HEAD` — 로컬 캐시(네트워크 0).
         **stale일 수 있어 2순위다**: 이 값은 clone 시점(또는 마지막
         `git remote set-head`) 스냅샷이라 origin을 갈아끼우면 그대로 남는다.
         2026-07-27 실측에서 **세션 브랜치를 가리키는 클론**이 관측됐다 — 그 상태로
         1순위였다면 규칙 A가 남의 세션 브랜치를 '트렁크 권위'로 삼아 **미탐(보호
         무력화)** 을 냈다. 원격이 대답하지 못할 때만 쓰는 폴백으로 강등한 이유다.
      3) 둘 다 실패(오프라인·권한) → 폴백 'main'.

    폴백이 틀린 경우(기본 브랜치가 master 등)의 방향: 그 ref가 존재하지 않아 규칙 A의
    신호가 '없음'이 되고 규칙 B는 아무것도 거르지 않는다 — HARN-07의 과탐(차단 과다)
    상태로 되돌아갈 뿐 미탐은 만들지 않는다. 해소 경로는 ScanResult.trunk_source로
    노출되어 '어느 근거로 판정했는가'가 매번 보인다.
    """
    try:
        ls = _git(root, "ls-remote", "--symref", "origin", "HEAD", timeout=15)
        if ls.returncode == 0:
            for line in ls.stdout.splitlines():
                # 형식: "ref: refs/heads/main\tHEAD"
                if line.startswith("ref:") and "HEAD" in line:
                    head = line[len("ref:") :].split("\t")[0].strip()
                    if head.startswith("refs/heads/"):
                        return REMOTE_REF_PREFIX + head[len("refs/heads/") :], "ls-remote"
    except Exception:  # pragma: no cover - 환경 의존
        pass
    try:
        sym = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", timeout=10)
        ref = sym.stdout.strip()
        if sym.returncode == 0 and ref.startswith(REMOTE_REF_PREFIX):
            return ref, "symbolic-ref"
    except Exception:  # pragma: no cover - 환경 의존 (git 부재 등)
        pass
    return REMOTE_REF_PREFIX + FALLBACK_TRUNK_BRANCH, "fallback"


def _trunk_task_status(root: Path, trunk_ref: str, task_id: str) -> str:
    """트렁크 사본의 태스크 status. 파일이 없거나 못 읽으면 "" (= 규칙 A 신호 없음)."""
    try:
        show = _git(root, "show", f"{trunk_ref}:backlog/tasks/{task_id}.yaml", timeout=10)
    except Exception:  # pragma: no cover - 환경 의존
        return ""
    if show.returncode != 0:
        return ""  # 브랜치에서 신설된 태스크 — 트렁크에 아직 없다
    return _top_level_field(show.stdout, "status")


def scan_remote_in_progress(
    root: Path, task_id: str, session: str, max_refs: int = SCAN_MAX_REFS
) -> ScanResult:
    """원격 브랜치들의 backlog 사본에서 이 태스크의 타 세션 in_progress를 찾는다.

    CAS claim(refs/claims/*)이 offline/error일 때만 호출하는 폴백이다
    (CAS 성공 시에는 불필요 — 전체 fetch 비용을 물지 않는다).

    한계 — 이것은 CAS의 원자성을 대체하지 못하는 *부분* 방어다:
        · 상대 세션이 **브랜치를 push한 뒤에만** 보인다.
        · 두 세션이 동시에 스캔하면 둘 다 '충돌 없음'을 볼 수 있다(원자성 없음).

    stale 처리 (HARN-08): 트렁크가 done/cancelled면 홀더 전부 무시(규칙 A),
    트렁크 ref 자신은 홀더가 될 수 없다(규칙 B). 걸러낸 건은 버리지 않고
    result.skipped에 사유와 함께 남긴다.

    반환 status가 'ok'가 아니면 **판정 자체가 불가**했다는 뜻이며, 빈 holders를
    '충돌 없음'으로 읽어서는 안 된다(측정 실패와 통과는 같은 색이면 안 된다).
    """
    if not has_remote(root):
        return ScanResult("offline", message="origin 원격 없음 — 교차 세션 탐지 불가")
    try:
        fetch = _git(
            root,
            "fetch",
            "--quiet",
            "origin",
            "+refs/heads/*:refs/remotes/origin/*",
            timeout=SCAN_FETCH_TIMEOUT,
        )
        if fetch.returncode != 0:
            return ScanResult(
                _classify_failure(fetch.stderr),
                message=f"원격 브랜치 fetch 실패: {fetch.stderr.strip()}",
            )
        listing = _git(
            root,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname)",
            "refs/remotes/origin",
        )
        if listing.returncode != 0:
            return ScanResult(
                _classify_failure(listing.stderr),
                message=f"원격 ref 열거 실패: {listing.stderr.strip()}",
            )
        refs = [
            r.strip()
            for r in listing.stdout.splitlines()
            if r.strip() and not r.strip().endswith("/HEAD")
        ]
        truncated = len(refs) > max_refs
        refs = refs[:max_refs]

        # 규칙 A·B의 기준점 — 기본 브랜치는 해소하고 하드코딩하지 않는다.
        trunk_ref, trunk_source = _resolve_trunk_ref(root)
        trunk_status = _trunk_task_status(root, trunk_ref, task_id)
        trunk_settled = trunk_status in TRUNK_SETTLED_STATUSES

        holders: list[InProgressHolder] = []
        skipped: list[SkippedHolder] = []
        for ref in refs:
            show = _git(root, "show", f"{ref}:backlog/tasks/{task_id}.yaml", timeout=10)
            if show.returncode != 0:
                continue  # 그 브랜치엔 이 태스크 파일이 없다 (태스크 신설 이전 시점 등)
            if _top_level_field(show.stdout, "status") != "in_progress":
                continue
            holder = _top_level_field(show.stdout, "session")
            if not holder or holder == session:
                continue  # 내 세션의 claim은 나를 막지 않는다
            branch = ref[len(REMOTE_REF_PREFIX) :] if ref.startswith(REMOTE_REF_PREFIX) else ref
            # [규칙 B] 트렁크는 머지된 결과지 작업 세션이 아니다 — 홀더가 될 수 없다.
            # 트렁크의 in_progress는 활성 claim이 아니라 done 미기입 머지(대장 위생 실패)다.
            if ref == trunk_ref:
                skipped.append(SkippedHolder(task_id, ref, branch, holder, "trunk_not_session"))
                continue
            # [규칙 A] 트렁크가 done/cancelled면 작업은 이미 착륙 — 사본의 in_progress는 잔재.
            if trunk_settled:
                skipped.append(SkippedHolder(task_id, ref, branch, holder, f"trunk_{trunk_status}"))
                continue
            holders.append(
                InProgressHolder(
                    task_id=task_id,
                    ref=ref,
                    branch=branch,
                    session=holder,
                )
            )
        return ScanResult(
            "ok",
            holders=holders,
            skipped=skipped,
            scanned_refs=len(refs),
            truncated=truncated,
            trunk_ref=trunk_ref,
            trunk_branch=(
                trunk_ref[len(REMOTE_REF_PREFIX) :]
                if trunk_ref.startswith(REMOTE_REF_PREFIX)
                else trunk_ref
            ),
            trunk_status=trunk_status,
            trunk_source=trunk_source,
        )
    except subprocess.TimeoutExpired:
        return ScanResult("offline", message="원격 브랜치 조회 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        # 침묵 실패 금지 — 예외 타입명을 반드시 남긴다 (CLAUDE.md AI·신뢰)
        return ScanResult("error", message=f"{type(exc).__name__}: {exc}")


def stale_claims(
    claims: list[RemoteClaim], backlog: Backlog, ttl_hours: int, now: datetime | None = None
) -> list[tuple[RemoteClaim, str]]:
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


def reap(
    root: Path, backlog: Backlog, ttl_hours: int, dry_run: bool = True
) -> tuple[list[str], str]:
    """stale claim 청소. dry_run이면 목록만 반환, 아니면 실제 삭제.

    반환: (["task_id (사유)", ...], 조회 상태 ok|offline|error).

    **상태를 함께 돌려주는 이유**(HARN-09): 구 구현은 조회 실패 시 빈 목록만 돌려줘서
    호출자가 "stale 없음"과 "판정 불가"를 구분할 수 없었다. CI의 교차검증 스텝이 정확히
    그 상태로 공전했다 — 인프라가 죽어도 "0건 통과"로 보였다. 측정·게이트 도구가 실패를
    통과로 위장하면 안 된다(CLAUDE.md AI·신뢰).
    """
    claims, status = list_claims(root)
    if status != "ok":
        return [], status
    stale = stale_claims(claims, backlog, ttl_hours)
    reaped: list[str] = []
    for c, reason in stale:
        label = f"{c.task_id} ({reason}" + (f", {c.branch}" if c.branch else "") + ")"
        if not dry_run:
            result = release(root, c.task_id, branch="", force=True)
            if result.status != "ok":
                continue
        reaped.append(label)
    return reaped, "ok"


# ── 미머지 done 탐지 (HARN-11) ────────────────────────────────────────────────
#
# HARN-07/08이 다룬 축의 **반대 방향**이다.
#   · HARN-08(과탐): 머지된 브랜치에 남은 in_progress가 착수를 영구 차단 → 규칙 A·B로 무시
#   · HARN-11(미탐): 타 세션이 **done 처리했으나 아직 머지 안 된** 태스크가 어디에도 안 보임
#
# 왜 안 보이는가: done 처리 시 원격 claim은 release되어 대장에서 사라지고, 트렁크의 백로그
# 사본은 그 브랜치가 머지되기 전까지 여전히 todo다. 즉 **claim 대장·로컬 백로그 양쪽 모두
# '가용'** 으로 보인다 — `next`가 이미 끝난 일을 최우선으로 추천한다.
#
# 사고 경위(2026-07-29 근접사고): /drive가 S3-09를 1순위로 계산해 claim까지 진행했으나, 타
# 세션이 이미 720문 검수를 마치고 done 처리한 상태였다(브랜치 미머지). 후속 태스크 notes의
# 감사 결과 인용을 우연히 보고 발견 — 중복 구현 직전 회피.
#
# 비용: ref 53개 × 태스크 N건을 `git cat-file --batch` **단일 프로세스**로 조회한다
# (실측 12ms). `next`처럼 자주 도는 경로에도 붙일 수 있는 이유다.


@dataclass
class DoneElsewhere:
    """어떤 브랜치가 이 태스크를 done으로 들고 있는가 (미머지 완료분)."""

    task_id: str
    ref: str
    branch: str


def scan_remote_done(
    root: Path,
    task_ids: Sequence[str],
    *,
    fetch: bool = False,
    max_refs: int = SCAN_MAX_REFS,
) -> tuple[dict[str, list[DoneElsewhere]], str]:
    """원격 브랜치 사본에서 `status: done`인 태스크를 찾는다 → {task_id: [DoneElsewhere]}.

    `fetch=False`(기본)는 **이미 있는 remote-tracking ref만** 본다 — 네트워크 0.
    `next`처럼 자주 도는 경로용이며, 그만큼 stale할 수 있다(마지막 fetch 시점 기준).
    `start`처럼 되돌리기 비싼 확정 지점은 `fetch=True`로 최신 상태를 본다.

    제외 규칙(기존 스캔과 동형):
        · 트렁크 ref는 제외 — 트렁크가 done이면 로컬 백로그도 done이라 애초에 후보가 아니다.
        · 파일이 없는 브랜치(태스크 신설 이전 시점)는 조용히 건너뛴다.

    두 번째 반환값은 status(`ok`/`offline`/`error`)다. `ok`가 아니면 **판정 불가**이며,
    빈 결과를 '완료분 없음'으로 읽어서는 안 된다(측정 실패와 통과는 같은 색이면 안 된다).
    """
    if not task_ids:
        return {}, "ok"
    if not has_remote(root):
        return {}, "offline"
    try:
        if fetch:
            fetched = _git(
                root,
                "fetch",
                "--quiet",
                "origin",
                "+refs/heads/*:refs/remotes/origin/*",
                timeout=SCAN_FETCH_TIMEOUT,
            )
            if fetched.returncode != 0:
                return {}, _classify_failure(fetched.stderr)
        listing = _git(
            root,
            "for-each-ref",
            "--format=%(refname)",
            "refs/remotes/origin",
        )
        if listing.returncode != 0:
            return {}, _classify_failure(listing.stderr)
        refs = [
            r.strip()
            for r in listing.stdout.splitlines()
            if r.strip() and not r.strip().endswith("/HEAD")
        ][:max_refs]
        trunk_ref, _ = _resolve_trunk_ref(root)
        refs = [r for r in refs if r != trunk_ref]
        if not refs:
            return {}, "ok"

        # (ref, task) 전 조합을 한 프로세스로 — 개별 `git show` N×M회를 피한다.
        pairs = [(ref, tid) for ref in refs for tid in task_ids]
        request = "".join(f"{ref}:backlog/tasks/{tid}.yaml\n" for ref, tid in pairs)
        batch = _git(root, "cat-file", "--batch", input_text=request, timeout=SCAN_FETCH_TIMEOUT)
        if batch.returncode != 0:
            return {}, _classify_failure(batch.stderr)

        found: dict[str, list[DoneElsewhere]] = {}
        for (ref, task_id), blob in zip(pairs, _iter_batch_blobs(batch.stdout), strict=False):
            if blob is None or _top_level_field(blob, "status") != "done":
                continue
            branch = ref[len(REMOTE_REF_PREFIX) :] if ref.startswith(REMOTE_REF_PREFIX) else ref
            found.setdefault(task_id, []).append(DoneElsewhere(task_id, ref, branch))
        return found, "ok"
    except subprocess.TimeoutExpired:
        return {}, "offline"
    except Exception as exc:  # pragma: no cover - 환경 의존
        # 침묵 실패 금지 — 예외 타입명을 남긴다 (CLAUDE.md AI·신뢰)
        return {}, f"error:{type(exc).__name__}"


# ── 장기 미머지 브랜치 감지 (HARN-13) ──────────────────────────────────────
#
# HARN-11(미머지 done)이 다루는 축과 가깝지만 다른 신호다 — HARN-11은 "이 태스크,
# 어디선가 이미 끝났나"(status: done 여부)를 backlog 사본에서 읽는 반면, 이 스캔은
# 태스크 상태와 무관하게 "이 *브랜치*가 트렁크에 아직 안 흡수된 채 얼마나 오래
# 방치됐는가"를 커밋 그래프 자체(committerdate·ahead count)로 잰다. 2026-07-30
# 사고(claude/shadow-data-s3-pilot-nh5kbz 9일·40+커밋 고립)는 태스크 status와
# 무관하게 벌어졌다 — 텍스트 재발방지 규칙("머지 타이밍은 Kiki의 pr 지시 대기")이
# 2회 반복 무력화된 뒤에야 이 스캔을 코드로 대체한다(CLAUDE.md "시스템 실수 재발
# 시 재발방지대책은 규칙 텍스트가 아니라 코드·CI로 등재").
#
# HARN-08이 claim(in_progress) 판정에 "나이" 휴리스틱을 **의도적으로 빼둔 것**과
# 모순되지 않는다 — 그건 "아직 활성 세션인가"를 나이로 오판하지 않기 위한 결정이었고,
# 여기는 "사람에게 존재 자체를 알릴 가치가 있는가"를 판정한다. 전자는 자동 판정을
# 내리면 안 되는 축이고, 후자는 정보성 경고일 뿐 태스크 진행을 막지 않는다.

STALE_BRANCH_DEFAULT_DAYS = 3


@dataclass(frozen=True)
class StaleBranch:
    """N일 이상 트렁크에 흡수되지 않은 원격 브랜치 1건.

    status(HARN-13 잔여 — 2026-08-05 3분류 확장):
      · "unresolved" — 진짜 Kiki 결정 대기. 기본값.
      · "ported"     — 이 브랜치의 유용한 부분이 이미 별도 소형 PR로 trunk에
                        흡수된 흔적(커밋 메시지에 브랜치 세션 접미사 언급)이 있다.
                        원본은 정리 대상일 뿐 결정 대기가 아니다.
      · "active"     — 다른 세션이 지금 이 브랜치에서 태스크를 claim 중(원격
                        claim 맵에 존재). 방치가 아니라 진행 중인 정상 작업.
    evidence: ported일 때 근거 커밋(짧은 sha + 제목), 그 외 "".
    """

    branch: str
    ref: str
    last_commit_at: datetime
    age_days: float
    ahead: int
    status: str = "unresolved"
    evidence: str = ""


_SESSION_SUFFIX_RE = re.compile(r"-([a-z0-9]{6})$")


def _find_ported_evidence(root: Path, trunk_ref: str, branch: str) -> str:
    """`branch`의 세션 접미사를 trunk 커밋 로그에서 찾는다 — 있으면 "이미 포팅됨" 근거.

    이 저장소의 관측된 명명 관행(예 `claude/whymath-ai-tutor-design-953m1e`)은 세션마다
    6자 영숫자 접미사를 붙인다. 그 브랜치의 유용한 부분을 뽑아 trunk에 흡수할 때(예:
    `merge: claude/whymath-ai-tutor-design-953m1e (PED-05, S3-16)`) 커밋 메시지가 그
    접미사를 그대로 인용하는 패턴이 반복 관측됐다(PR#705·#702·#707 등). 접미사가 이
    패턴에 안 맞거나 grep이 실패하면 "포팅 근거 없음"으로 안전 폴백한다(전체 스캔을
    막지 않음 — 이 브랜치만 unresolved로 남는다).
    """
    match = _SESSION_SUFFIX_RE.search(branch)
    if not match:
        return ""
    suffix = match.group(1)
    try:
        found = _git(
            root,
            "log",
            trunk_ref,
            f"--grep={suffix}",
            "--fixed-strings",
            "--oneline",
            "-n",
            "5",
            timeout=15,
        )
    except Exception:  # pragma: no cover - 환경 의존
        return ""
    if found.returncode != 0:
        return ""
    line = found.stdout.strip().splitlines()[0] if found.stdout.strip() else ""
    return line


@dataclass
class StaleBranchScanResult:
    """장기 미머지 브랜치 스캔 결과. status: ok | offline | error(판정 불가는 stale 무시 금지)."""

    status: str
    stale: list[StaleBranch] = field(default_factory=list)
    scanned_refs: int = 0
    truncated: bool = False
    message: str = ""
    trunk_ref: str = ""
    trunk_branch: str = ""
    trunk_source: str = ""


def scan_stale_branches(
    root: Path,
    *,
    days_threshold: int = STALE_BRANCH_DEFAULT_DAYS,
    fetch: bool = True,
    max_refs: int = SCAN_MAX_REFS,
    now: datetime | None = None,
    active_branches: frozenset[str] = frozenset(),
) -> StaleBranchScanResult:
    """트렁크에 `days_threshold`일 이상 흡수되지 않은 원격 브랜치를 찾는다.

    "흡수되지 않음"의 판정은 두 조건의 AND다 — 둘 다 필요하다:
      1. 최종 커밋(`committerdate`)이 `days_threshold`일 이상 경과.
      2. 트렁크 기준 `ahead count > 0`(SQUASH 머지 저장소이므로 커밋 그래프 조상
         관계가 아니라 `rev-list --count trunk..ref`로 판정 — `scan_remote_in_progress`
         의 규칙 A·B가 같은 이유로 조상 검사 대신 트렁크 사본 상태를 쓰는 것과 동형
         근거: SQUASH 머지 후에도 원본 브랜치의 커밋들은 트렁크의 조상이 되지 않는다).
      ahead==0이면 실질적으로 머지됐거나 애초에 커밋이 없는 것이므로 stale이 아니다.

    `fetch=True`(기본)는 이 스캔이 세션당 드물게(SessionStart 1회 또는 CI 1회) 도는
    것을 전제로 한다 — `scan_remote_done`의 `fetch=False` 기본(고빈도 `next` 경로용)과
    반대 선택이다. 최신 브랜치 목록이 없으면 "9일째 아무도 모른다"는 이 스캔의
    존재 이유 자체가 무너진다(캐시된 오래된 remote-tracking ref만 보면 새로 생긴
    방치 브랜치를 못 본다).

    반환 status가 'ok'가 아니면 **판정 자체가 불가**했다는 뜻이며, 빈 stale 목록을
    '방치 브랜치 없음'으로 읽어서는 안 된다(측정 실패와 통과는 같은 색이면 안 된다).

    active_branches(HARN-13 잔여 — 2026-08-05): 호출부가 이미 계산해둔 원격 claim
    맵의 브랜치 집합(`remote_claimed.values()`)을 그대로 넘긴다 — 새 스캔을 추가하지
    않고 기존 데이터를 재사용해 "타 세션이 지금 이 브랜치에서 작업 중"을 판별한다.
    """
    if not has_remote(root):
        return StaleBranchScanResult("offline", message="origin 원격 없음 — 브랜치 스캔 불가")
    now = now or _utcnow()
    try:
        if fetch:
            fetched = _git(
                root,
                "fetch",
                "--quiet",
                "origin",
                "+refs/heads/*:refs/remotes/origin/*",
                timeout=SCAN_FETCH_TIMEOUT,
            )
            if fetched.returncode != 0:
                return StaleBranchScanResult(
                    _classify_failure(fetched.stderr),
                    message=f"원격 브랜치 fetch 실패: {fetched.stderr.strip()}",
                )
        listing = _git(
            root,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname)%09%(committerdate:iso-strict)",
            "refs/remotes/origin",
        )
        if listing.returncode != 0:
            return StaleBranchScanResult(
                _classify_failure(listing.stderr),
                message=f"원격 ref 열거 실패: {listing.stderr.strip()}",
            )

        entries: list[tuple[str, str]] = []
        for line in listing.stdout.splitlines():
            ref, _, date_str = line.partition("\t")
            ref, date_str = ref.strip(), date_str.strip()
            if not ref or ref.endswith("/HEAD"):
                continue
            entries.append((ref, date_str))
        truncated = len(entries) > max_refs
        entries = entries[:max_refs]

        trunk_ref, trunk_source = _resolve_trunk_ref(root)
        trunk_branch = (
            trunk_ref[len(REMOTE_REF_PREFIX) :]
            if trunk_ref.startswith(REMOTE_REF_PREFIX)
            else trunk_ref
        )

        stale: list[StaleBranch] = []
        for ref, date_str in entries:
            if ref == trunk_ref:
                continue
            try:
                last_commit_at = datetime.fromisoformat(date_str)
            except ValueError:
                continue  # 파싱 불가 — 이 브랜치만 조용히 제외(전체 스캔은 실패시키지 않음)
            age_days = (now - last_commit_at).total_seconds() / 86400
            if age_days < days_threshold:
                continue
            ahead_result = _git(root, "rev-list", "--count", f"{trunk_ref}..{ref}", timeout=15)
            if ahead_result.returncode != 0:
                continue
            try:
                ahead = int(ahead_result.stdout.strip() or "0")
            except ValueError:
                continue
            if ahead <= 0:
                continue  # 트렁크에 이미 흡수됨(또는 커밋 0) — 방치 아님
            branch = ref[len(REMOTE_REF_PREFIX) :] if ref.startswith(REMOTE_REF_PREFIX) else ref
            if branch in active_branches:
                status, evidence = "active", ""
            else:
                evidence = _find_ported_evidence(root, trunk_ref, branch)
                status = "ported" if evidence else "unresolved"
            stale.append(
                StaleBranch(
                    branch=branch,
                    ref=ref,
                    last_commit_at=last_commit_at,
                    age_days=age_days,
                    ahead=ahead,
                    status=status,
                    evidence=evidence,
                )
            )

        return StaleBranchScanResult(
            "ok",
            stale=stale,
            scanned_refs=len(entries),
            truncated=truncated,
            trunk_ref=trunk_ref,
            trunk_branch=trunk_branch,
            trunk_source=trunk_source,
        )
    except subprocess.TimeoutExpired:
        return StaleBranchScanResult("offline", message="원격 브랜치 조회 타임아웃")
    except Exception as exc:  # pragma: no cover - 환경 의존
        # 침묵 실패 금지 — 예외 타입명을 반드시 남긴다 (CLAUDE.md AI·신뢰)
        return StaleBranchScanResult("error", message=f"{type(exc).__name__}: {exc}")


def _iter_batch_blobs(stdout: str):
    """`git cat-file --batch` 출력을 요청 순서대로 blob 본문(또는 None)으로 흘린다.

    형식: 존재하면 `<sha> blob <size>\\n<본문>\\n`, 없으면 `<요청> missing\\n`.
    **요청 1건당 정확히 1개**를 내보내야 zip 정렬이 어긋나지 않는다.

    ⚠ `<size>`는 **문자 수가 아니라 바이트 수**다. 이 저장소의 태스크 YAML은 한국어라
    문자 길이로 세면 헤더 위치가 밀려 결과가 **엉뚱한 브랜치에 붙는다**(2026-07-29 실측:
    S3-09의 done 보유 브랜치를 problem-bank 대신 teaching-strategy로 오보고). 그래서
    바이트로 디코드해 오프셋을 잡고, 본문만 다시 문자열로 되돌린다.
    """
    data = stdout.encode("utf-8", errors="surrogateescape")
    pos = 0
    total = len(data)
    while pos < total:
        newline = data.find(b"\n", pos)
        if newline == -1:
            break
        header = data[pos:newline]
        pos = newline + 1
        if not header:
            continue
        parts = header.rsplit(b" ", 2)
        if len(parts) == 3 and parts[1] == b"blob" and parts[2].isdigit():
            size = int(parts[2])
            body = data[pos : pos + size]
            pos += size + 1  # 본문 뒤 개행
            yield body.decode("utf-8", errors="surrogateescape")
        else:
            yield None  # missing / ambiguous
