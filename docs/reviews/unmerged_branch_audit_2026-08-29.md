# 미머지 브랜치 전수 감사(52건) — 처리 판정 · 2026-08-29

> **시점 스냅샷 선언**: origin fetch(`--unshallow`+`--prune`) 기준 2026-08-29, main = `3d79abd8`(#898).
> 원격 refs 총 53(main·harness-claims 포함), 감사 모집단 = **PR 미오픈 40건**.
> 선행 판정 정본: `unmerged_branch_verdict_2026-08-11.md` · `unmerged_branch_audit_full_2026-08-11.md`
> (그 판정을 수정하지 않고, 이후 18일간의 변화분만 재판정한다).
> 코드 이식 0줄 — 이 감사의 산출물은 판정 + 태스크 등재(HARN-34·35·36) + 삭제 배치(4차)다.

## 1. 방법 · 재현 명령

```bash
git fetch --unshallow origin && git fetch --prune origin '+refs/heads/*:refs/remotes/origin/*'
# ① 규모: git rev-list --left-right --count origin/main...origin/<b> · diff --name-only | wc -l
# ② 고립 done 대조: 브랜치 yaml status=done vs main status
# ③ 잔여 blob 대조(파일 단위): git cat-file -e로 존재 판정 후 rev-parse --verify 해시 비교
#    ⚠ 함정(이 감사 실측): `git rev-parse origin/main:<부재경로>`는 인자를 그대로 stdout에
#    에코한다 — 존재 판정은 반드시 `git cat-file -e`로. (--verify 없는 rev-parse로 부재/상이를
#    가르면 부재 파일이 전건 '상이'로 위장된다)
# ④ 고유 내용: comm -23 <(git show <b>:<f>|sort) <(git show main:<f>|sort) 줄수 + diff 방향 정독
```

열린 PR 11건(#844 #846 #847 #856 #858 #860 #865 #880 #882 #885 #893) — head 전건 원격 실재,
**유령 PR 0건**. 활성 원격 claim 1건(MISC-16 → #893 head, 손대지 않음).

## 2. 전수 판정표

### 🔴 미추적 고립 — 이번 세션이 회수 태스크 등재 (→ HARN-34 · HARN-35 · HARN-36)

| # | 고립 내용 | 실측 근거 | 등재 |
|---|---|---|---|
| A1 | **법령 게이트 유실**: `G-export-prediction-disclosure`(PIPA §35/GDPR Art.15 변호사 검토·30일 리마인드)가 `ph1ad7`(905ed311) gates.yaml에만 존재 | ASM-12 코드는 #822로 main 착지(blob 동일 실측)됐는데 게이트·done 기록은 미착지 — main `grep export-prediction gates.yaml` 0건. `export_prediction_disclosure_verdict.md`(main 실재)가 이 게이트를 지목하는데 대장에 없음 | **HARN-34** (P1) |
| A2 | **done 부기 유실 4건**: ASM-12(#822 머지)·MISC-04(#821 머지)는 main yaml이 `todo`·artifacts 공란. S4-52는 #866 증적 누락. SEC-28 done 기록은 `eos-curriculum-semantic-backbone-adr`(2f2e311e)에만 — #885 head가 yaml 미보유라 머지돼도 착지 불가 | `git log --grep '(#821)' '(#822)' '(#866)'` 머지 확인 + yaml diff | **HARN-34** |
| A3 | **태스크 등재 유실 7건**: MISC-07~11(오개념 r2 갭 5종 — `backup/whymath-misconception-review-r1skwr-pre-rebase` a95bb456에만) · SEC-25(면제 만료 조건 — `backup/school-subject-6ybkis-pre-rebase` 5d2c2b71에만) · OPS-24 cp949 감사(`vafylb` b1218739에만) | 전건 `git cat-file -e origin/main:backlog/tasks/<f>` 실패. 슬러그 검색으로 재채번 승계 여부 교차(OPS-26→OPS-36 승계 1건 제외 전건 부재) | **HARN-35** (P2) |
| A4 | **claim 경로 CRLF 오염**: harness-claims 트리가 `"claims\r/MISC-16.json\r"` — Windows 세션 기록분의 개행 미정규화 | `git ls-tree origin/harness-claims \| cat -A` | **HARN-36** (P2) |

### 🟡 이미 추적 중 — 재등재 금지 (기존 태스크·PR이 소유)

| 브랜치 | 소유자 (main 상태) |
|---|---|
| `k20m0w` | **MOB-18**(todo) — SEC-24는 done 착지 |
| `gdmwhk` · `uqyg79` | **PED-26**(todo) — PED-22~25는 done |
| `34zvse` | 잔여 = **CUR-07**(main todo·브랜치 done) — CUR-08 회수는 done. HARN-34 ③이 참조 병기 |
| `e98dw4` | 잔여 = **S3-28**(main todo·브랜치 done) — NLP-04·VIZ-06 done. VIZ-04는 VIZ-06으로 재채번 승계 |
| `5t5lmv` | **OPS-40**(todo) — A11Y-02·OPS-35(클라버전) done 기록이 브랜치에만 |
| `iws58k` | **ARCH-30**(todo) |
| `t608mk` · `azdnov` · `backup/ai-content-a3ysut-pre-rebase` | **OPS-41**(todo) — ai콘텐츠 r3·데이터플랫폼 r2 doc은 여전히 main 부재, 게임화 r3·학습경로 r3 doc은 착지 확인. **원 a3ysut·8ap436·p1hubt 브랜치는 소멸**(HARN-34 ④가 notes 현행화) |
| `vafylb` | **S4-16**(blocked) + HARN-35(OPS-24 등재분) |
| `trjg5x` | **PB-06**(done — 회수조건 확정)·실행은 Kiki 소유 (233파일 최대 고립 — 변동 없음) |
| `6dszy0` · `merge/6dszy0` | main **MISC-01·MISC-03·PB-02**(전건 todo)가 소유 — #739는 의도 close(S3-32→#738, REC-02→#735, MISC-04→#821로 각각 착지). 미착지 잔여 = 위 3건 구현+테스트 5파일(main 부재 실측) |
| `6eejrv` | main **PB-08**(todo) 참고 자산 — redaction 접근 자체는 #802 close로 폐기(main은 SEC-24 projection 채택·정답 축 해소, gating 6종도 `PublicProblem` 실측). **검수 축(pending 노출)은 여전히 미해소·PB-08 소유** |
| `q8tvcx` | **OPS-38**(todo) |
| `7n9n72` · `40xspg` | SOL-01(done) 잔여 재열거 **이번 감사 미완** — §5 정직한 공백 |
| `ph1ad7` · `misc-04-recovery` · `s4-52-status` · `eos-semantic-backbone` · `r1skwr backup` · `6ybkis backup` | **HARN-34/35** — 회수 완료 전 삭제 금지 |

### 🟢 삭제 후보 — 잃을 내용 없음 실측 (4차 배치 등재 8건)

| 브랜치 (head) | 근거 |
|---|---|
| `pr/collab-07` (d45bbf38) | COLLAB-07 #817 머지·잔여 3파일 중 2 blob 동일·ci.yml 고유줄 **0** |
| `backup/collaboration-qlzq5m-pre-rebase` (65b90308) | 고유줄 총합 **0** |
| `backup/whymath-collaboration-design-qlzq5m-pre-rebase` (65b90308) | 위와 **동일 head**·중복 백업 |
| `backup/webpage-plan-8pma1f-pre-rebase` (eef8aee3) | 상이 0·부재 0 — 웹 전략 정본(`web_strategy.md`) 착지 완료 |
| `backend/cur-16-concept-edge-prerequisite-meta` (6d751b57) | v2 재작업분이 #892로 착지. 상이 전건 정독: 브랜치 고유줄 = 옛 `down_revision`(d5e6f7a8b9c0)·S4-10 이전 판 — **전건 main 우세** |
| `claude/whymath-nlp-design-my18a1` (a89a6c99) | 08-04 삭제 계보 재확인. config.py 고유 2줄 = #783(머지)이 대체한 옛 docstring 구문 실측 |
| `claude/whymath-math-engine-design-4qbaru` (f0edfac1) | 08-04 삭제 계보 재확인 — 잔여 yaml/doc 고유줄 = 낡은 판(MATH-01~04·NLP-03 전건 main 실재) |
| `claude/whymath-ai-recommendation-review-tv1f08` (fdf46d7b) | REC-09 회수 done. 잔여 정독: 수치 2,647은 main이 2,638로 현행화(QUAL-02)·ci.yml `claims reap` 구문은 main 재작성판 실재·REC-06 고유 3줄 = 옛 메타 — **전건 main 우세** |

### ⚪ 조건부 보류 — 다음 배치 (정독 미완 또는 회수 대기)

- `backup/whymath-account-security-dw9lww-pre-rebase` (고유줄 71) · `backup/learning-analytics-3pbkcx-pre-rebase` (53 — PATH-09·10은 done) · `backup/visualization-review-28d0yx-pre-rebase` (30) · `backup/whymath-visualization-review-r3-pre-rebase` (9 — #759는 머지·VIZ-07 done) · `backup/gamification-8ap436-pre-rebase` (3 — OPS-41 ③ MOB-17 축 확인 후) · `backup/ai-integration-5qqcp4-pre-rebase` (16 — OPS-26은 OPS-36으로 재채번 승계 확인) · `backup/whymath-curriculum-design-6eejrv-pre-rebase` (라이브 6eejrv와 동일 head — 라이브 처분 확정 후) · `curriculum/cur-15-eos-concept-db-review-adr` (고유줄 4 — EOS-44 claim은 해제 상태)
- HARN-34/35 참조 브랜치 6건 (🟡 마지막 행) — 회수 착지 후 삭제 배치

### ⚪ 판정 대상 아님

`harness-claims`(하네스 소유) · 열린 PR head 11건(각 PR 소유 — steward 규약)

## 3. 구조적 발견 4건

1. **"재생성-머지" 패턴이 부기를 유실한다** — #815→#822, #744→#821처럼 PR을 다른 브랜치로
   재생성해 머지하면 코드는 착지하는데 원 브랜치의 done·게이트·artifacts가 남는다. 법령
   게이트(G-export-prediction-disclosure)까지 유실된 것이 이번 실피해. "회수 시 acceptance
   전수 재대조 생략 금지"(2026-08-10)의 네 번째 축 — **약속한 부기가 다 왔는가**.
2. **backup/*-pre-rebase 12건이 무주공산** — 08-10/11 리베이스 백업들이 어느 판정 문서의
   소유도 아닌 채 잔존. 이 중 2건(r1skwr·6ybkis)은 **유일 사본**(태스크 등재 6건)을 품고
   있었다 — 백업이라는 이름이 "원본은 따로 있다"는 착시를 만든다.
3. **ID 재사용 신규 실측 3건** — OPS-35(5t5lmv 클라버전 ↔ t608mk 메트릭 롤업), OPS-24
   (vafylb cp949 ↔ CLAUDE.md 사고 경위의 backfill), HARN-22(main id-number-suggestion-race ↔
   azdnov id-collision-inventory). 08-11 감사의 9건에 이어 누적 — 재채번 권위(HARN-22-azdnov판)
   자신이 고립인 상태. OPS-41 이식 시 전건 CLI 재배정.
4. **claim 경로 CRLF 오염**(§2-A4 → HARN-36) — Linux 세션의 활성 claim 대조가 경로 불일치로
   무력화될 수 있는 상태였다(이번 감사는 트리 직접 조회로 우회).

## 4. 이번 세션 조치 요약

- 등재: **HARN-34**(P1 부기·게이트 회수) · **HARN-35**(P2 등재 유실 7건) · **HARN-36**(P2 CRLF)
- 삭제 배치 4차: §2 🟢 8건 → `.github/branch-cleanup-request.txt` (head SHA 스냅샷 병기)
- 3차 배치(admin-01) 집행 확인: `ls-remote` 잔존 **0/1**

## 5. 정직한 공백

- **코드 이식 0줄** — 이식은 등재된 태스크(/drive)가 실행한다.
- `7n9n72`(83파일)·`40xspg`(27파일)의 SOL-01-이후 잔여 재열거는 하지 못했다 — 삭제 후보로
  내리지 않고 보류가 그 공백의 처리다.
- ⚪ 조건부 8건의 고유줄 정독은 총합 수치까지만 — 내용 판정은 다음 배치 몫.
- 각 브랜치 구현의 정확성은 보지 않았다(고유한가·추적되는가까지).
