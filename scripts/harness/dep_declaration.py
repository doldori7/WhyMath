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
    "SOFT_DECLARED",
    "SOFT_REASON_CODES",
    "find_expiry_violations",
    "find_soft_declaration_violations",
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

# 소프트 분류 근거의 최소 길이. "왜 하드가 아닌가"는 한 줄로 설명되지 않는다 — 실측 6건의
# 최단 근거가 약 90자였다. 코드만 찍고 근거를 "N/A"로 채우는 것을 막는 하한이다.
_MIN_SOFT_REASON_CHARS = 40

# ── 레거시 그랜드파더 (ARCH-25 패턴) ──────────────────────────────────────
# key = (위반 태스크 full id, 참조 접두) **쌍** · value = 이 면제를 해소할 백로그 태스크 id.
# 태스크 단위가 아니라 쌍 단위인 이유: 태스크 전체를 면제하면 그 notes에 *새로운* 미선언
# 선행이 추가돼도 계속 green이 나고 회귀가 HARN-53 완료까지 숨는다(#946 리뷰 P2).
# 그 태스크가 done이 되면 면제는 만료된다(find_expiry_violations가 red를 낸다).
# 신규 위반은 여기에 추가하지 않는다 — 게이트의 존재 이유가 사라진다.
LEGACY_EXEMPT: dict[tuple[str, str], str] = {}
"""레거시 그랜드파더 — **현재 0건**(HARN-53이 6건 전부 분류해 비웠다, 2026-09-06).

빈 dict를 남겨 두는 이유: 다음에 게이트를 새로 세울 때 같은 패턴이 필요하면 여기에 담는다.
**신규 위반은 여기에 추가하지 않는다** — 게이트의 존재 이유가 사라진다. 새 유예를 넣을 때는
반드시 해소 태스크 id를 값으로 두어 `find_expiry_violations`가 만료를 강제하게 한다.
"""


# ── 소프트 선행 분류 (HARN-53 — 하드 의존이 *틀린* 경우의 정본 표기) ──────────
# 왜 필요한가: `DEPENDENCY_PHRASES`는 "선행"류 어구 + 근처 태스크 ID를 잡는다. 그 조합이
# 언제나 "이 태스크가 저 태스크를 기다린다"를 뜻하지는 않는다 — HARN-53 실측 6건 중
# **하드 부착이 옳은 것은 0건**이었고, 다섯 가지 서로 다른 이유로 전부 하드가 아니었다.
# 그 경우 남는 선택지는 셋뿐이다: ⓐnotes를 고쳐 어구를 피한다(자연어를 게이트에 맞추는
# 꼬리-개-흔들기) ⓑ틀린 하드 의존을 붙인다(영구 오차단) ⓒ**왜 하드가 아닌지를 코드로
# 분류한다**. 이 표가 ⓒ다.
#
# 유예(LEGACY_EXEMPT)와 다르다 — 유예는 "아직 안 고쳤다"라서 만료가 필요하고, 이것은
# "고칠 것이 없다(하드가 아니다)"라는 **판정**이라 만료가 없다. 대신 느슨해지지 않도록
# 세 가지를 강제한다(`find_soft_declaration_violations`):
#   ① 사유 **코드**는 아래 고정 집합에서만 — 자유 서술로 "소프트니까"가 불가능하다
#   ② 근거 문장이 비어 있으면 위반 — 코드만 찍고 넘어갈 수 없다
#   ③ 같은 쌍이 `depends_on`에도 있으면 위반 — 하드로 걸어 놓고 소프트라 적는 모순 차단
SOFT_REASON_CODES: dict[str, str] = {
    "REVERSED": "방향이 반대다 — 이 태스크가 참조 대상의 선행이다(참조 대상 쪽에 부착한다)",
    "DISJUNCTIVE": "A 또는 B 택일이라 하드로 표현 불가(depends_on은 전건 AND)",
    "STAGE_BLOCKED": "로드맵 순서 위반이라 검증기가 거부한다(후행 스테이지 의존)",
    "HISTORICAL": "이미 완료된 과거 사실 서술 — 앞으로의 순서 제약이 아니다",
    "MISREAD_REF": "창(window)이 잡은 ID가 선행이 아니다 — 진짜 선행은 별개(있으면 부착)",
}

# key = (위반 태스크 full id, 참조 접두) · value = (사유 코드, 근거 문장)
SOFT_DECLARED: dict[tuple[str, str], tuple[str, str]] = {
    ("ADMIN-04-module-registry", "ADMIN-05"): (
        "REVERSED",
        "notes '\u2026ADMIN-05 선결'은 ADMIN-04가 ADMIN-05의 선결이라는 뜻이다. 진짜 방향은 "
        "이미 대장에 있다 — ADMIN-05.depends_on=['ADMIN-04-module-registry']. 반대로 붙이면 "
        "순환이며 validate가 실제로 거부한다(2026-09-06 시뮬레이션 실측: ADMIN-04→05→06→07 순환).",
    ),
    ("ADMIN-09-profile-collection-inventory-contract", "ADMIN-02"): (
        "REVERSED",
        "notes 'ADMIN-02 (c)의 선결 — 처분 근거는 이 대장이 있어야 성립한다'는 ADMIN-09가 "
        "ADMIN-02의 선결이라는 뜻이다. 진짜 방향을 ADMIN-02에 부착했다(HARN-53).",
    ),
    ("EOS-50-publish-gate-pipeline", "ARCH-31"): (
        "DISJUNCTIVE",
        "notes '선행: ARCH-31 **또는** EOS-49의 버전 테이블 실체화' — 택일이라 depends_on"
        "(AND)으로 표현하면 둘 다 기다리게 되어 실제보다 강하게 막는다. 둘 중 하나가 done이 "
        "되는 시점에 그때 남은 쪽을 부착하는 것이 정답이다.",
    ),
    ("LIC-03-provenance-enforcement-layer-decision", "LIC-01"): (
        "STAGE_BLOCKED",
        "LIC-03(S3)이 LIC-01(E2)에 의존하면 store.validate_backlog가 '후행 스테이지 태스크에 "
        "의존 — 로드맵 순서 위반'으로 거부한다(2026-09-06 시뮬레이션으로 재현 확인 — notes의 "
        "2026-08-30 실측이 오늘도 유효). 스케줄러 제외는 status=blocked가 담당한다.",
    ),
    ("OPS-35-audit-membership-consumption-detection", "S4-22"): (
        "HISTORICAL",
        "notes 'S4-22 범위 정정(3종→2종)은 2026-08-10 R3 점검 커밋에서 **선행 완료**' — 이미 "
        "끝난 과거 사실이지 앞으로의 순서 제약이 아니다. 본 태스크는 탐지기·대장 축만 다룬다.",
    ),
    # ↓ 2건은 **이 태스크(HARN-53)의 정정 사유 문구가 스스로 만든** 위반이다. `amend --reason`이
    # notes에 append되는데 사유가 "…'선결'이라 선언한 방향을 부착한다"처럼 선행 어구와 태스크
    # ID를 한 문장에 담아, 스캐너가 그 인용을 새 선언으로 읽었다. notes는 append 전용이라
    # 되돌릴 CLI 경로가 없어 분류로 남긴다 — **재발은 `amend`의 되먹임 가드가 쓰기 전에 막는다**
    # (같은 PR). 분류로 덮은 것이 아니라, 덮을 수밖에 없게 만든 결함을 함께 고쳤다는 뜻이다.
    ("ADMIN-02-dead-tenancy-billing-columns", "HARN-53"): (
        "MISREAD_REF",
        "notes의 HARN-53 언급은 *정정 사유 인용*이다 — ADMIN-09의 '선결' 문장을 그대로 옮겨 "
        "적었을 뿐 ADMIN-02가 HARN-53을 기다린다는 뜻이 아니다(HARN-53은 이 정정을 수행한 "
        "태스크다). 실제 부착된 선행은 ADMIN-09이다.",
    ),
    ("SEC-30-declared-unwired-waiver-staleness", "HARN-53"): (
        "MISREAD_REF",
        "위와 같은 정정 사유 인용 — SEC-30의 실제 선행은 부착된 PB-04이고, HARN-53은 그 부착을 "
        "수행한 태스크로서 사유 문장에 등장할 뿐이다.",
    ),
    ("SEC-30-declared-unwired-waiver-staleness", "MOB-18"): (
        "MISREAD_REF",
        "notes '선행 조건 PB-04는 여전히 k20m0w 고립(MOB-18 소유)' — 선행은 PB-04이고 MOB-18은 "
        "그 브랜치의 *소유 태스크*일 뿐이다. 창이 60자 안의 MOB-18을 함께 잡았다. 진짜 선행 "
        "PB-04를 부착했다(HARN-53).",
    ),
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
                    # 소프트 분류는 `apply_exemptions`와 **무관하게** 언제나 억제한다 —
                    # 유예는 "아직 안 고쳤다"(감사 시 보여야 한다)이고 소프트는 "고칠 것이
                    # 없다"(판정)라서, 감사 모드에서까지 위반으로 세면 분류가 무의미해진다.
                    # 대신 감사 출력이 소프트 건수를 따로 보고한다(보이지 않게 쌓이지 않는다).
                    if (tid, prefix) in SOFT_DECLARED:
                        continue
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


def find_soft_declaration_violations(tasks: dict[str, object]) -> list[str]:
    """소프트 분류 계약 위반 (빈 리스트 = 정상).

    소프트 분류에는 만료가 없다(판정이지 유예가 아니다). 그래서 느슨해질 여지를 **다섯**
    지점에서 막는다 — 하나라도 빠지면 "소프트라고 적으면 통과"가 되어 게이트가 옵트아웃이 된다.

    ① 분류 대상 태스크가 백로그에 없다(삭제·오타 — 추적 불가능한 분류)
    ② 참조 접두가 백로그의 어떤 태스크와도 맞지 않는다(유령 참조)
    ③ 사유 코드가 `SOFT_REASON_CODES` 밖이다(자유 서술로 "소프트니까" 금지)
    ④ 근거 문장이 비었거나 지나치게 짧다(코드만 찍고 넘어가기 금지)
    ⑤ 같은 쌍이 `depends_on`에도 있다 — 하드로 걸어 놓고 소프트라 적는 **모순**
       (또는 하드가 붙은 뒤 분류를 안 지운 것. 둘 다 표가 거짓이 된다)

    같은 쌍이 `LEGACY_EXEMPT`에도 있으면 ⑥ 이중 분류로 위반이다 — 유예는 "고칠 예정",
    소프트는 "고칠 것 없음"이라 동시에 참일 수 없다.
    """
    violations: list[str] = []
    prefixes = {_ref_prefix(tid) for tid in tasks}
    for (task_id, ref), value in sorted(SOFT_DECLARED.items()):
        label = f"{task_id} → {ref}"
        if task_id not in tasks:
            violations.append(f"소프트 분류 대상 '{task_id}' 가 백로그에 없다 — 분류를 제거하라")
            continue
        if ref not in prefixes:
            violations.append(f"소프트 분류 '{label}' 의 참조 '{ref}' 가 백로그에 없다")
        code, reason = value
        if code not in SOFT_REASON_CODES:
            violations.append(
                f"소프트 분류 '{label}' 의 사유 코드 '{code}' 가 허용 집합 밖이다 "
                f"(허용: {sorted(SOFT_REASON_CODES)})"
            )
        if len(reason.strip()) < _MIN_SOFT_REASON_CHARS:
            violations.append(
                f"소프트 분류 '{label}' 의 근거가 비었거나 너무 짧다 "
                f"({len(reason.strip())}자 < {_MIN_SOFT_REASON_CHARS}) — 왜 하드가 아닌지 적어라"
            )
        declared = {_ref_prefix(d) for d in (getattr(tasks[task_id], "depends_on", None) or [])}
        if ref in declared:
            violations.append(
                f"소프트 분류 '{label}' 인데 depends_on에도 '{ref}' 가 있다 — 하드로 걸어 놓고 "
                "소프트라 적을 수 없다(분류를 지우거나 의존을 빼라)"
            )
        if (task_id, ref) in LEGACY_EXEMPT:
            violations.append(
                f"'{label}' 가 소프트 분류와 레거시 유예에 **모두** 있다 — "
                "'고칠 것 없음'과 '아직 안 고침'은 동시에 참일 수 없다"
            )
    return violations


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
