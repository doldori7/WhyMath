"""notes/acceptance에 *선언된* 선행 의존이 depends_on으로 *집행되는지* 대조한다.

**왜 필요한가 (사고 경위 2026-09-01)**: `EOS-62` 등재 시 notes에 "선행: EOS-54 착지 후
착수"라고 적었으나 `depends_on: []`이었다. `selector.py`의 착수 가능 판정은 **notes를 읽지
않는다** — `depends_on`만 본다. 따라서 다른 세션이 그 태스크를 즉시 후보로 받아 trunk에
없는 파일을 대상으로 착수할 수 있었다(#911 codex 리뷰 P2가 지적).

이것은 1회성 실수가 아니다. 이 모듈을 저장소 전체에 돌린 결과 **미완료 태스크에서 동일
패턴이 다수 실재**했다 — 즉 사람이 "선행 조건을 적었다"고 믿는 것과 하네스가 "착수를
막는다"는 것이 저장소 전반에서 어긋나 있었다. CLAUDE.md의 **"정본화를 집행으로 착각한
완료 선언 금지"** 가 acceptance·서빙 경로 축으로만 등재돼 있고 **백로그 대장 축**에는
집행 장치가 없던 공백이다.

**설계 3원칙**:

1. **탐지는 보수적으로** — 순서를 *단언하는* 어구(선행·착지 후·후 착수·선결·머지 후)
   근처에서만 타 태스크 참조를 찾는다. 단순 언급("EOS-54가 만든 계측기를 쓴다")은 의존
   선언이 아니므로 잡지 않는다. 오탐이 잦은 게이트는 습관화되어 무력해진다(CLAUDE.md:
   상시 실패하는 fail-open 보호를 보호로 신뢰 금지).

   **`notes`만 스캔하고 `acceptance`는 보지 않는다** — 원칙적 구분이다. 의존 *선언*이
   적히는 곳은 notes이고("선행: X 착지 후"), acceptance는 *사양 산문*이라 타 태스크 ID와
   "선행"이 일반적 의미로 섞여 등장한다. 실측(2026-09-01): acceptance를 포함하면 12건 중
   4건이 오탐이었다 — 대표적으로 `HARN-53`의 "ⓐ진짜 선행 → … / ⓑ소프트 권고(SEC-26 …)"
   에서 분류 기준어 "선행"과 예시로 든 `SEC-26`이 60자 창에 함께 들어왔다. notes 한정으로
   그 4건이 전부 사라지고 6건만 남았다.
2. **이미 해소된 참조는 위반이 아니다** — 참조 대상이 done/cancelled면 순서 제약이 실효
   없으므로 통과시킨다. 과거형 서술("EOS-54는 #909로 착지 완료")까지 잡으면 소음이 된다.
3. **레거시는 그랜드파더하되 만료를 건다** — 기존 위반을 즉시 red로 만들면 게이트가
   꺼진다. ARCH-25 `provenance_audit._KNOWN_GAPS` 선례를 그대로 답습해 **면제마다 추적
   가능한 백로그 태스크 ID를 못박고**, 그 태스크가 done인데 면제가 남아 있으면 위반으로
   승격한다(만료 없는 유예 금지 — CLAUDE.md 2026-08-03).

**이 모듈이 하지 않는 것**: 의존을 자동으로 채우지 않는다. 어느 것이 진짜 선행인지는 사람
판단이며, 정정 경로는 `backlog.py amend <id> --depends <task-id> --reason ...`이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "DEPENDENCY_PHRASES",
    "Finding",
    "LEGACY_EXEMPT",
    "find_expiry_violations",
    "find_undeclared_dependencies",
]

# 순서를 *단언하는* 어구만. "…를 쓴다"·"…가 만든" 같은 단순 참조는 의도적으로 제외한다.
DEPENDENCY_PHRASES: tuple[str, ...] = (
    "선행",
    "착지 후",
    "머지 후",
    "후 착수",
    "선결",
    "완료 후",
)

# 어구 기준 좌우 탐색 폭(문자). 한 문장 안의 참조만 잡히도록 좁게 둔다 — 넓히면 무관한
# 태스크 ID가 딸려 들어와 오탐이 된다(실측으로 정한 값).
_WINDOW = 60

# 태스크 ID의 *번호 부분까지* (전체 슬러그는 문서에서 자주 생략된다: "EOS-54 착지 후").
_REF_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,7}-\d{1,3})\b")

# 스캔 *대상*에서 빼는 상태 — 이미 끝났거나 취소된 태스크는 착수되지 않으므로 순서 강제가
# 무의미하다.
_SCAN_SKIP_STATUSES = frozenset({"done", "cancelled"})

# 참조가 *해소됐다*고 보는 상태 — **`done`만**이다. `selector.unmet_dependencies`가
# "done이 아니면 미해소"로 판정하므로(selector.py:39-44), 여기서 cancelled를 해소로 치면
# 게이트와 스케줄러의 의미가 어긋난다: 취소된 선행을 지목한 태스크는 선언 없이 착수 가능
# 상태로 남는데 그 선행은 영원히 done이 되지 않는다 — 이 게이트가 막으려던 바로 그
# 불일치다(#946 리뷰 P2). 취소된 선행은 재계획 대상이므로 드러나는 편이 옳다
# (`--depends`로 붙이면 영구 차단이 되니 이 경우의 정답은 notes 표현 정정이며,
# CLI 거부 메시지가 두 경로를 모두 안내한다).
_RESOLVED_STATUSES = frozenset({"done"})

# ── 레거시 그랜드파더 (ARCH-25 패턴) ──────────────────────────────────────
# key = (위반 태스크 full id, 참조 접두) **쌍** · value = 이 면제를 해소할 백로그 태스크 id.
# 태스크 단위가 아니라 쌍 단위인 이유: 태스크 전체를 면제하면 그 notes에 *새로운* 미선언
# 선행이 추가돼도 계속 green이 나고 회귀가 HARN-53 완료까지 숨는다(#946 리뷰 P2).
# 그 태스크가 done이 되면 면제는 만료된다(find_expiry_violations가 red를 낸다).
# 신규 위반은 여기에 추가하지 않는다 — 게이트의 존재 이유가 사라진다.
_TRIAGE = "HARN-53-legacy-dependency-declaration-triage"
LEGACY_EXEMPT: dict[tuple[str, str], str] = {
    # 2026-09-01 HARN-52 착지 실측 — 미완료 태스크 6건(notes 한정 스캔). 전건 즉시 수정하지
    # 않은 이유 ② 일부는 하드 의존이 아닐 수 있다(예: 스테이지 순서상 불가능하다고 자인한
    # 건) — 소프트 권고와 하드 의존의 구분은 사람 판단이다. 이 6건은 HARN-53이 분류한다.
    ("ADMIN-04-module-registry", "ADMIN-05"): _TRIAGE,
    ("ADMIN-09-profile-collection-inventory-contract", "ADMIN-02"): _TRIAGE,
    ("EOS-50-publish-gate-pipeline", "ARCH-31"): _TRIAGE,
    ("LIC-03-provenance-enforcement-layer-decision", "LIC-01"): _TRIAGE,
    ("OPS-35-audit-membership-consumption-detection", "S4-22"): _TRIAGE,
    ("SEC-30-declared-unwired-waiver-staleness", "MOB-18"): _TRIAGE,
}


@dataclass(slots=True, frozen=True)
class Finding:
    """선언은 있으나 집행되지 않은 의존 1건."""

    task_id: str
    referenced: str
    phrase: str
    excerpt: str

    def render(self) -> str:
        return (
            f"{self.task_id}: notes/acceptance가 '{self.phrase}'로 {self.referenced} 를 "
            f"선행으로 선언하나 depends_on에 없다 — “…{self.excerpt}…”"
        )


def _ref_prefix(task_id: str) -> str:
    """'EOS-62-review-verdict' → 'EOS-62' (참조 표기와 대조할 번호까지의 접두)."""
    m = _REF_RE.match(task_id)
    return m.group(1) if m else task_id


def find_undeclared_dependencies(
    tasks: dict[str, object],
    *,
    apply_exemptions: bool = True,
) -> list[Finding]:
    """선언↔집행 불일치 목록을 반환한다(빈 리스트 = 위반 없음).

    Args:
      tasks: `{task_id: Task}` — `status`·`notes`·`acceptance`·`depends_on` 속성을 읽는다.
      apply_exemptions: False면 `LEGACY_EXEMPT`를 무시하고 전건 보고(감사·베이스라인 산출용).
    """
    statuses = {tid: getattr(t, "status", "") for tid, t in tasks.items()}
    # 참조 접두(EOS-54) → 그 접두를 가진 태스크들의 상태
    by_prefix: dict[str, list[str]] = {}
    for tid in tasks:
        by_prefix.setdefault(_ref_prefix(tid), []).append(tid)

    findings: list[Finding] = []
    for tid, task in sorted(tasks.items()):
        if statuses.get(tid, "") in _SCAN_SKIP_STATUSES:
            continue
        self_prefix = _ref_prefix(tid)
        declared = {_ref_prefix(d) for d in (getattr(task, "depends_on", None) or [])}
        # notes만 — acceptance는 사양 산문이라 오탐원이다(모듈 docstring 설계원칙 1 실측).
        text = getattr(task, "notes", "") or ""
        seen: set[str] = set()
        for phrase in DEPENDENCY_PHRASES:
            for m in re.finditer(re.escape(phrase), text):
                lo = max(0, m.start() - _WINDOW)
                window = text[lo : m.end() + _WINDOW]
                for ref in _REF_RE.finditer(window):
                    prefix = ref.group(1)
                    if prefix == self_prefix or prefix in declared or prefix in seen:
                        continue
                    targets = by_prefix.get(prefix)
                    if not targets:
                        continue  # 저장소에 없는 참조 — 이 게이트의 책임 밖(오타·외부 표기)
                    # 대상이 전부 해소(done/cancelled)면 순서 제약이 실효 없다
                    if all(statuses.get(t, "") in _RESOLVED_STATUSES for t in targets):
                        continue
                    seen.add(prefix)
                    if apply_exemptions and (tid, prefix) in LEGACY_EXEMPT:
                        continue
                    findings.append(
                        Finding(
                            task_id=tid,
                            referenced=prefix,
                            phrase=phrase,
                            excerpt=" ".join(window.split())[:110],
                        )
                    )
    return findings


def find_expiry_violations(tasks: dict[str, object]) -> list[str]:
    """그랜드파더 만료 계약 위반 (ARCH-25 패턴 — 빈 리스트 = 정상).

    ① 면제 대상 태스크가 백로그에 없다(삭제·오타 — 추적 불가능한 면제)
    ② 면제를 해소할 태스크가 백로그에 없다
    ③ 해소 태스크가 종료 상태(done·cancelled)인데 면제가 남아 있다
       (만료 — 면제를 지우고 실제로 고쳐야 한다)
    """
    violations: list[str] = []
    for (exempt_id, ref), owner_id in sorted(LEGACY_EXEMPT.items()):
        label = f"{exempt_id} → {ref}"
        if exempt_id not in tasks:
            violations.append(f"면제 대상 '{exempt_id}' 가 백로그에 없다 — 면제를 제거하라")
        if owner_id not in tasks:
            violations.append(f"면제 '{label}' 의 해소 태스크 '{owner_id}' 가 백로그에 없다")
            continue
        # done뿐 아니라 **cancelled도 만료**다 — 취소된 태스크는 영원히 done이 되지 않으므로
        # done만 보면 해소 태스크가 취소되는 순간 면제가 영구화되고 CI는 계속 green을 낸다
        # (#946 리뷰 P2). 종료 상태 전부를 만료로 친다.
        owner_status = getattr(tasks[owner_id], "status", "")
        if owner_status in _SCAN_SKIP_STATUSES:
            violations.append(
                f"면제 '{label}' 의 해소 태스크 '{owner_id}' 가 {owner_status} 인데 면제가 "
                "남아 있다 — 만료된 유예(면제를 제거하고 depends_on을 채우거나 notes를 고쳐라)"
            )
    return violations
