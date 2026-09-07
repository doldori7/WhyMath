# 미머지 브랜치 전수 감사 8회차 — 2026-09-07 (r2)

> **시점 스냅샷 선언.** 이 문서는 2026-09-07 `origin/main = b75f495d` 시점의 원격 상태를 고정한 것이다.
> 이후 브랜치·PR·태스크 상태 변화는 반영하지 않는다. **선행 판정 문서(08-04·08-11·08-29·08-31·09-07 r1)는 수정하지 않는다.**
>
> **직전 정본 = 7회차 `docs/reviews/unmerged_branch_audit_2026-09-07.md` — 미머지(PR #1020 · `claude/status-9dti04` · 스냅샷 main `98925b0e`).**
> 같은 날 3시간 앞선 다른 세션의 감사다. 이 8회차는 그 판정을 *재생산하지 않고* ①그 스냅샷 이후 델타 ②그 판정의 **독립 적대 검증**
> ③6·7회차가 두 번 연속 "정직한 공백"으로 남긴 **추적 중 14건의 acceptance 커버리지 전수 정독**을 수행한다.
> 7회차가 등재한 항목(`PED-37`·`G-attempt-retention-purge-backfill-decision`·좌석 8건 amend·7차 삭제 배치)은 **재등재하지 않는다** —
> 미머지이므로 "착지했다"고도 적지 않는다(CLAUDE.md "미머지 존재를 충족으로 단정 금지"). 두 PR이 모두 머지되면 두 문서는 서로를 보강한다.

## 0. 전제 복구 — shallow 해소

```bash
git rev-parse --is-shallow-repository        # true → 판정 금지
git fetch --unshallow origin                 # EXIT=0
git fetch --prune origin '+refs/heads/*:refs/remotes/origin/*'   # EXIT=0
git rev-parse --is-shallow-repository        # false (실측)
```

## 1. 모집단 분리 (실측)

| 구분 | 건수 | 비고 |
|---|---|---|
| 원격 ref 전수 | 40 | `git for-each-ref refs/remotes/origin` (HEAD 제외) |
| 제외: `main`·`harness-claims` | 2 | harness-claims는 하네스 claim 저장소·작업 브랜치 아님 |
| 열린 PR이 소유 | 18 | `list_pull_requests(state=open)` — #1024·#1021·#1020·#1018·#1015·#1010·#1007·#975·#893·#882·#880·#865·#860·#858·#856·#847·#846·#844 |
| 원격 claim 활성(PR 없음·다른 세션 소유) | 2 | `status-f6qz0c`(EOS-63 block) · `status-f9lp65`(HARN-56 block) |
| **감사 대상(PR 미오픈·claim 없음)** | **18** | 아래 §3~§6 |

**유령 PR(head 브랜치가 원격에 없는 열린 PR): 0건** — 18건의 head가 전부 원격에 실재한다.

**7회차 대비 모집단 변화**: ref 40 → 40(불변). `test-driven-development-03elxp`가 claim-only에서 **PR #1021 소유**로 이동(7회차 ④ 3건 → 2건).
`claims/CUR-17.json`·`CUR-18.json`이 원격에 없는 `status-5kvqkv`를 가리키는 잔류 기록은 7회차 ⓐ와 동일(변화 없음·하네스 소관).

## 2. 직전 배치 집행 확인 (`.github/branch-cleanup-request.txt` 관례)

4·5·6차 배치 19건 + 허용 패턴 밖 수동 삭제 4건을 `git ls-remote --heads`로 재확인: **잔존 0/19 · 수동 4건 전건 삭제 완료.**
7차 배치(PR #1020 등재분 — 미머지)의 대상 3건(`wbhw8v` 9d5f81b2 · `review-dydkkx-runbook` dbdcdf6f · `gates/deploy-environment-approval` 907d4629)은
**아직 원격에 실재**한다(배치 미집행 — PR 미머지이므로 당연). 이 8회차는 그 배치를 **중복 등재하지 않고 §4에서 판정을 검증**한다.

## 3. 3축 측정 (감사 대상 18 + 참고로 claim 2)

`git rev-list --left-right --count origin/main...origin/<b>` · `git diff --name-only` · done-less 사각(HARN-31: `src|tests|data|scripts|backend|mobile` 신규 파일) · 고립 done 스캔(#701 선례).

| 브랜치 | head | ahead | behind | diff | src | 고립 done | merge-base |
|---|---|---|---|---|---|---|---|
| `backup/ai-content-a3ysut-pre-rebase` | b271671b | 5 | 198 | 16 | 7 | 0 | b636c976 |
| `drive-eos-81-sequential-wbhw8v` | 9d5f81b2 | **0** | 16 | **0** | 0 | 0 | 9d5f81b2 |
| `openrouter-setup-guide-e98dw4` | f8c0e3b6 | 13 | 320 | 37 | 27 | 2 | 92575678 |
| `remaining-track-34zvse` | 7fb78470 | 16 | 224 | 33 | 23 | 1 | 4cfe10da |
| `review-dydkkx-runbook` | dbdcdf6f | 6 | 57 | 195 | 0 | 0 | e90d2d6f |
| `subject-problems-theory-check-7n9n72` | 621b11f9 | 34 | 233 | 83 | 49 | **11** | 959ec4ad |
| `whymath-ai-content-design-vafylb` | b1218739 | 8 | 256 | 7 | 1 | 0 | 4620f747 |
| `whymath-ai-recommendation-review-q8tvcx` | e1835c0c | 3 | 298 | 11 | 2 | 1 | de446ec3 |
| `whymath-coding-architecture-iws58k` | a8e01be2 | 1 | 239 | 16 | 1 | 0 | 684aa430 |
| `whymath-constitution-rules-check-azdnov` | c335a787 | 1 | 233 | 5 | 0 | 0 | 959ec4ad |
| `whymath-curriculum-design-6eejrv` | 2f428729 | 9 | 197 | 6 | 3 | 1 | 00386fe4 |
| `whymath-data-platform-design-t608mk` | d876b523 | 1 | 229 | 7 | 0 | 0 | d088ae77 |
| `whymath-issues-review-k20m0w` | 2330a095 | 45 | 245 | 133 | 95 | 21 | 5f60f37e |
| `whymath-mvp-plan-architecture-trjg5x` | c8abbc17 | 81 | 286 | 233 | 188 | 34 | ad06c6e5 |
| `whymath-pedagogy-review-gdmwhk` | 2915bf4e | 1 | 233 | 31 | 21 | 0 | 959ec4ad |
| `whymath-pedagogy-review-uqyg79` | 5dc040b3 | 38 | 314 | 76 | 51 | 9 | 98e923f1 |
| `whymath-service-operations-review-5t5lmv` | dd3e9475 | 6 | 229 | 33 | 17 | 2 | d088ae77 |
| `gates/deploy-environment-approval` | 907d4629 | 2 | 56 | 3 | 0 | 0 | b63c48e5 |
| *(claim)* `status-f6qz0c` | e90d2d6f | **0** | 57 | **0** | 0 | 0 | e90d2d6f |
| *(claim)* `status-f9lp65` | d792c9d0 | 2 | 40 | 5 | 2 | 0 | f0376888 |

7회차 표와 **수치 정합**(behind만 main 전진분 +5만큼 증가). diff 0파일 = `wbhw8v`·`f6qz0c` 2건(7회차와 동일).

## 3.1 7회차 스냅샷(98925b0e) 이후 main 델타

```bash
git log --oneline 98925b0e..origin/main
# b75f495d EOS-99 (#1023) · f36f53f9 HARN-66/68 결정 로그 (#1022) · 41756ccf HARN-66+68 (#1011) · 402053c4 LIC-07 ⑯ (#1019) · e410c181 LIC-07 ④ (#1016)
git diff --name-only 98925b0e..origin/main -- backlog/tasks/
# EOS-02 · EOS-99 · HARN-66 · HARN-68 · LIC-07 — 추적 중 14건의 소유 태스크는 한 건도 바뀌지 않았다
```

즉 7회차의 ② 표(소유 태스크 status)는 이 시점에도 그대로 성립한다. 델타에서 새 판정이 필요한 브랜치는 없다.

## 3.2 별건 발견 — 하네스 탐지기의 "PR 제출됨"이 닫힌 미머지 PR을 소유자로 센다

`python3 scripts/harness/backlog.py branches`(full clone에서 실행, EXIT=0)가 다음 3건을 **"[PR] — 처분은 해당 PR에서"**로 분류했다:

| 브랜치 | 탐지기 근거 | GitHub 실측(`pull_request_read get`) | 실제 소유 |
|---|---|---|---|
| `gates/deploy-environment-approval` | PR #967 | **closed · merged=false** (2026-09-01) | 없음 — 7회차 ③ 삭제 후보 |
| `whymath-curriculum-design-6eejrv` | PR #802 | **closed · merged=false** (2026-08-14) | PB-08(todo) — 고립 done 1 |
| `whymath-pedagogy-review-uqyg79` | PR #675 | **closed · merged=false** (2026-08-14) | PED-26(todo) — 고립 done 9 |

원인은 `scripts/harness/remote_claims.py:1601`이 **스스로 적어 둔 한계**다 — `refs/pull/<N>/head`는 닫힌 PR에도 남고, `refs/pull/<N>/merge`
휴리스틱은 08-31 실측에서 변별력 없음으로 폐기됐다(열린 14건 중 merge ref 8건뿐). 설계는 "열림/닫힘은 사람이 PR 번호로 1클릭 확인"으로 위임했다.
그러나 그 위임의 결과가 **브리핑 문구 "처분은 해당 PR에서"**다 — 닫힌 PR에는 처분할 자리가 없으므로 이 문구는 막다른 길이고,
읽는 세션은 그 브랜치를 "소유됨"으로 넘긴다. 08-11 ④(느슨한 needle → 거짓 `ported`)·HARN-37(문서 커밋 → 거짓 `ported`)에 이은
**"결정 불요로 위장" 계열 3번째 변형**이며, 이번엔 `pr_filed` 축이다. 오늘 실피해 0(3건 모두 다른 경로로 소유·판정됨)이지만
그것은 stray-code 감사가 GitHub API로 PR 상태를 따로 확인하기 때문이지 탐지기 덕이 아니다. 조치 = §7 등재.

## 4. 7회차(PR #1020) 판정의 독립 검증

검증은 워크플로(에이전트 25건·읽기 전용 git 조회)로 수행했다. 삭제 판정은 브랜치마다 **반박자 2렌즈**(내용 유실·근거 실재)가
"잃을 내용 0"을 뒤집으려 시도했고, 나머지는 독립 재도출 후 7회차 표와 대조했다. 기본값은 의심(불확실하면 반박)이다.

*(§4.1·§4.2·§4.4는 결과 도착 순으로 아래에 기재)*

### 4.3 7n9n72 alembic 좌석 — 7회차 공백 **닫힘**

7회차가 "S3-32 회수 세션의 대체 리비전명을 확인해야 닫히는 공백"으로 남긴 건이다.

| 브랜치 리비전 | 변경 | main 대체 | 판정 |
|---|---|---|---|
| `20260808_1200_7ef2b5a8e69e_dialogue_server_verified_completion.py` (af2e9b39) | `dialogue.server_verified_completed_at` TIMESTAMPTZ nullable 1컬럼(완료 플래그+멱등 가드) | **PR #738 (f5de0450 · 2026-08-14)** `20260807_1305_d1e2f3c4b5a6_dialogue_review_turns_remaining.py` — `dialogue.review_turns_remaining` + "완료 여부는 `dialogue.attempt_id` 존재로 판정, 별도 완료 플래그 컬럼은 두지 않는다"(리비전 docstring) | **superseded** — 같은 기능을 다른 스키마로 구현·ORM(`db/models/dialogue.py:102`)·`coach.py`·`l4/completion.py`가 main 컬럼을 소비 중. 브랜치 컬럼은 main 전수 grep 0건(유일 hit = `374fb620de9e` docstring의 "그 리비전은 main에 없다" 언급). down_revision `090d254a5d43`도 stale(main은 이미 `c6d7e8f1a2b4`가 자식 — 그대로 포트 시 multiple heads) |
| `20260810_1200_0afd40ce1867_attempt_selected_choice_index.py` (087859bd · ASM-06) | `problem_attempt.selected_choice_index` Integer nullable | **없음** — main alembic·ORM(`db/models/activity.py`)·`schema/activity.py`·`api/me.py` 전건 부재. main의 hit는 `harness/distractor_signal_dormancy_report.py`(정본 슬롯명 예약·"ASM-06 재정의 소관")와 그 테스트·문서뿐 = 언급이지 흡수 아님 | **미흡수 고립** — 좌석 ASM-06(blocked)이 소유. 회수 시 down_revision을 현 head `c1a5e07b4d38`로 재지정 + `schema_version.py` 등재 + me.py/ORM/`distractor_link.py` 동반 이식 + 차단 사유(요청 슬롯 신설·ASM-09 착지 후) 재대조 |

```bash
git cat-file -e origin/main:src/backend/alembic/versions/20260808_1200_7ef2b5a8e69e_dialogue_server_verified_completion.py   # 실패(부재)
git log origin/main -S review_turns_remaining --oneline -- src/backend/alembic/versions   # f5de0450 (#738) 단 1건
git grep -c server_verified_completed_at origin/main -- src   # 0 (docstring 언급 1건 제외)
git grep -l selected_choice_index origin/main -- src/backend/alembic src/backend/whymath_backend/db   # 0
```

**부수 발견 — 대장·MEMORY 불일치**: `MEMORY.md:1978`(2026-08-10)은 ASM-06을 "브랜치 7n9n72에 실물 done(artifacts 087859bd)·불가침"으로 적었으나
main `ASM-06` yaml은 `status: blocked · artifacts: []`(updated 09-01)다. 판정 자체는 main 대장이 옳다(차단 사유가 그 실물을 "재정의 방향과 동형·무비판 이식 금지"로
규정) — 7회차가 ASM-06 좌석에 부착한 고립 참조(미머지)가 착지하면 이 불일치는 대장 쪽에서 해소된다. 별도 조치 없음(기록만).

**S3-32 yaml의 artifact `ca19c9c2`는 로컬 full clone에 객체가 없다**(스쿼시 전 브랜치 커밋 추정) — 실제 main 착지 커밋은 `f5de0450`(#738)이며 yaml에는 PR 번호·대체 리비전명 표기가 없다. 정정은 HARN-57(증적 정정 경로·PR #1021)이 착지한 뒤 소유자가 낼 일이라 이 감사는 기록만 한다.

## 6. claim 활성 브랜치 `status-f9lp65` — 판정 아님·다음 회차용 줄 단위 대조 (7회차 공백 **닫힘**)

HARN-56 block claim이 살아 있어 판정하지 않는다. 7회차가 "main #993/#1009가 같은 결함을 재구현한 것으로 *보인다*"까지만 적은 것을 줄 단위로 대조했다(정적 대조·실행 검증 없음).

| 파일 | 고유 줄 | main 대응 | 흡수 |
|---|---|---|---|
| `scripts/backup/register_backup_schedule.ps1` | 19 | #993(dc2e6583)·#1009(09894ddd · 이 파일 +44 실코드). 브랜치의 `-ErrorAction Stop`+try/catch는 main 163·165·209·211행에 동일. 브랜치의 HRESULT `0x80070005` 힌트는 main이 **Step 0a `IsInRole(Administrator)` 사전 검사**(81~93행)로 등록 *전에* Fail시켜 불필요해짐. 역으로 main에만 있는 우세 검사 = Unregister try/catch·되읽은 인자↔조립 인자 대조(`$registeredArgs -ne $argList`)·`[OK] (read back from the task)` — 브랜치는 조립값을 그대로 출력(09-06 r2 결함 ⓒ 그대로) | **예 (옛 판)** |
| `tests/infra/test_backup_encryption.py` | 18 | 브랜치 신규 2건에 대응하는 main 검사 = 355·1213·1230·336·1238·1260행(`TestScheduledTaskRegistrationFailsClosed` 등, 주석 제외 실행 라인 스캔). 브랜치 단언 2종('reported success but' 부재·'0x80070005' 존재)은 **main 스크립트에 대해 RED** — main이 그 문면을 유지하고 HRESULT 매칭을 미채택했으므로 그대로 이식 불가·이식 이유도 없음 | **예 (옛 판)** |
| `docs/architecture/db_backup_dr_runbook.md` | 48 | main #993(+193)·#1009(+37). 브랜치 §2/§4-1c '사람이 관리자 창을 연다' 절차는 main이 UAC 자가 승격 런처로 교체(09-06 사람 단계 2회 실패 후) · §4-1b 클라우드 반출 블록은 main 415~430행에 `-LiteralPath`·Count 형태 + 자가검증 2b/3 추가 · §6 '오프사이트 사본 부재'는 main 563행이 09-07 게이트 clear로 해소 표기 | **예 (옛 판)** |
| `backlog/tasks/HARN-56-merge-queue-adoption.yaml` | 3 | main = `in_progress · session: claude/status-f9lp65`, 브랜치 = `blocked · session: null` + "[차단 2026-09-03] 부분 착지 후 사람 게이트 대기" 문단 | **아니오** — 코드가 아니라 하네스 대장 전이 |
| `backlog/events/claude_status-f9lp65.ndjson` | 1 | block 이벤트(2026-09-03T10:50) main 부재 | **아니오** — 위와 한 쌍 |

**다음 회차용 결론(판정 아님)**: 코드·문서 3파일은 잃을 내용 0(main 우세). 남는 것은 HARN-56의 **block 전이 2줄**뿐인데, 이것은 claim 소유 세션이
`backlog.py block`으로 낸 대장 상태라 타 세션이 대행하거나 손편집할 수 없다(거부 우회 금지). claim 해제 시 소유자가 다시 내야 하며, 그 뒤에는 삭제 후보다.
브랜치 ps1의 HRESULT 로케일 독립 힌트 문구(한국어 Windows에서 'Access is denied' 번역 문제)는 main 실행 라인에 없으나, main 설계(사전 검사)가 그 경로를 막으므로
검사 축의 유실은 아니다 — 사전 검사를 통과하고도 정책 차단 등으로 실패하는 경우의 안내 문구 수준이다(읽어서 그렇게 보인다·실행 검증 없음).

*(§5·§7·§8·§9는 결과 도착 후 기재)*
