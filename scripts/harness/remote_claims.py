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
    - offline/error(네트워크·권한): 경고 + 이벤트 로그 후 아래 *읽기측 탐지*로 폴백.
    - conflict(다른 세션이 이미 claim): 정보가 확정적이므로 이것만 차단.

읽기측 교차 세션 탐지 (HARN-07 — CAS가 막힌 환경의 부분 방어):
    2026-07-27 실측: 이 실행 환경의 git 프록시는 refs/claims/* push를 HTTP 403으로
    거부한다. 즉 CAS claim은 "가끔 실패"가 아니라 **한 번도 성공한 적이 없고**,
    fail-open이 모든 start를 통과시켜 중복 방지가 상시 무력이었다(OPS-07을 두 세션이
    병렬 구현해 한쪽을 폐기한 사고). 쓰기는 막혔지만 **읽기는 된다** —
    `scan_remote_in_progress()`가 원격 브랜치들의 backlog 사본을 읽어 같은 태스크가
    이미 in_progress인지 탐지한다.

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
    root: Path, *argv: str, timeout: int = 15, input_text: str | None = None
) -> subprocess.CompletedProcess:
    """git 실행 — 테스트 monkeypatch 지점. 인증 프롬프트 행 방지."""
    import os

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
        env=env,
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
        blob = _git(
            root, "hash-object", "-w", "--stdin", input_text=json.dumps(meta, ensure_ascii=False)
        )
        if blob.returncode != 0:
            return ClaimResult("error", message=f"blob 생성 실패: {blob.stderr.strip()}")
        sha = blob.stdout.strip()
        ref = f"{CLAIMS_NS}/{task_id}"
        # CAS: expect 빈 값 = "원격에 ref가 없어야만 성공"
        push = _git(root, "push", "--quiet", f"--force-with-lease={ref}:", "origin", f"{sha}:{ref}")
        if push.returncode == 0:
            return ClaimResult("ok", claim=RemoteClaim(task_id, sha, branch, meta["ts"], meta))
        status = _classify_failure(push.stderr)
        if status == "conflict":
            other = _describe_existing(root, task_id)
            return ClaimResult(
                "conflict",
                claim=other,
                message=push.stderr.strip().splitlines()[-1] if push.stderr else "",
            )
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
                        "error",
                        claim=mine,
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
            claims.append(RemoteClaim(task_id=ref[len(CLAIMS_NS) + 1 :], sha=sha))
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
        fetch = _git(
            root, "fetch", "--quiet", "origin", f"+{CLAIMS_NS}/*:{LOCAL_MIRROR_NS}/*", timeout=20
        )
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


def reap(root: Path, backlog: Backlog, ttl_hours: int, dry_run: bool = True) -> list[str]:
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
