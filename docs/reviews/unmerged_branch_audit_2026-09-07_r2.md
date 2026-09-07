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

### 4.1 7회차 ③ 삭제 판정 3건 — 반박자 2렌즈 결과

반박자는 "잃을 내용 0"을 뒤집을 것을 기본값으로 지시받았다(불확실하면 refuted=true). 렌즈 = **내용 유실**(브랜치에만 있는 모든 줄을 열거·판독) · **근거 실재**(판정문의 PR 번호·done 표기·이벤트 파일·정정판을 하나씩 실측).

| 브랜치 (head) | 내용 유실 렌즈 | 근거 실재 렌즈 | 8회차 판정 |
|---|---|---|---|
| `drive-eos-81-sequential-wbhw8v` (9d5f81b2) | **반박 실패(high)** — 브랜치 ref가 main first-parent의 squash 커밋 #1002를 그대로 가리킴(고유 커밋 0·3-dot diff 0파일·판정 기준 b75f495d와 현 HEAD 96790b46 양쪽 동일). 2-dot 트리 대조 M 108파일 전건 `comm -23` → 75파일·760줄이 브랜치에만 있으나 **75/75가 브랜치 head 이후 main PR(#1003~#1024)이 명시 수정한 파일**이고 열람한 줄 묶음은 전부 후행 판이 대체한 옛 상태(KICE 런북 재작성 지시서→실행 기록판 #1008 · answer_kind 하드코딩 튜플→EOS-85 불투명 통과 · composition pull→EOS-89 push · gates pending→cleared/kiki · CLAUDE.md 0.2.11→0.2.15). EOS-81 산출물 3종 main 실재·세션 이벤트 ndjson 190줄 바이트 동일·`86930abc`(#980) 착지 | **반박 실패(high)** — `merge-base` = 브랜치 head 자신(=#1002 squash 커밋)·`is-ancestor` 양 기준 exit 0. **7회차 근거 표기 정정**: 브랜치 이름은 eos-81이지만 이벤트 파일에 EOS-81 이벤트 0건 — 실제 수행 태스크는 **EOS-75(#994 · 59503f7f · 코드 6파일)·HARN-73(#1002 · 9d5f81b2 · backlog.py+테스트)**이고 둘 다 main done·코드 실재. EOS-81은 세션 9ain00이 #980으로 착지(claim/release be631f60·a42094b6). "EOS-81 main done(#980)"은 사실이나 이 브랜치의 흡수 근거로는 무관 — 판정은 불변, 근거만 바뀜 | **삭제 확정** (7차 배치 등재는 #1020이 보유 — 중복 등재 안 함) |
| `review-dydkkx-runbook` (dbdcdf6f) | **반박 실패(high)** — 전 트리 512파일 `comm -23` → 고유 938줄, merge-base(e90d2d6f)로 걸러 **브랜치가 실제 저작한 줄은 14파일 27줄**뿐. task yaml 12파일의 "[정정 2026-09-01] eos_priority …" notes는 main 동일 파일에 12/12 실재(grep count 1)하고 main이 09-02~09-06 후행 notes·게이트·상태 전이를 추가한 후행판. 런북 4줄은 main이 GH013 실측 근거로 명시 폐기한 `git push origin main` 안내와 `--as kiki` 이전 clear 명령. 유일하게 main 부재 = EOS-80 done 이벤트 1줄(ts 13:46) — main `claude_eos80-done.ndjson`(#966·ts 19:49)이 같은 id·같은 artifacts로 보유 → 손실 아닌 중복. `eos_priority` 실질 데이터 193파일 전건 브랜치=main 일치. 7회차 "53줄/21파일" 집계 정확히 재현 | **반박 실패(high)** — 근거 4종(#961 머지·main EOS-80 done·이벤트 파일·런북 정정판) 전건 참. **7회차 근거 표기 정정**: "PR #961 머지(91c348fd)"의 91c348fd는 브랜치 내부 `Merge origin/main` 커밋이고 main 스쿼시 커밋은 **b63c48e5** — 두 커밋의 **트리가 바이트 동일**(`rev-parse ^{tree}` 일치·`diff --stat` 0줄)이라 결론 불변. 머지 후 1커밋 dbdcdf6f는 backlog 2파일만 변경(코드·데이터 0) | **삭제 확정** (7차 배치 등재는 #1020 보유) |
| `gates/deploy-environment-approval` (907d4629) | *(도착 후 기재)* | *(도착 후 기재)* | *(2렌즈 후 확정)* |

### 4.2 7n9n72 잔여표 — 독립 재도출 vs 7회차 표

브랜치 `subject-problems-theory-check-7n9n72`(621b11f9 · diff 83파일)를 전건 `git cat-file -e` + `comm -23`으로 재도출했다.
**결과: 부재 17 + 상이 62 + 바이트 동일 4**(merge-base 대비로만 잡히는 이미 흡수분). 7회차 표의 **17파일 수와 그 목록은 정확**하다.
그러나 표가 "부재 파일"만 적고 **상이 파일 속 동반 변경**을 빠뜨린 곳이 있어, 표대로 테스트·모듈만 회수하면 RED가 된다.

| 7회차 표 행 | 표가 빠뜨린 동반 변경(main 부재 실측) | 7회차 좌석 amend에는? |
|---|---|---|
| PB-02 (tests/infra 2파일) | **`.github/workflows/ci.yml` 본체 56줄** — nightly corpus_reverify 인자 글롭 전환 + data_pipeline 잡 커버리지 재생성-diff 스텝. main `ci.yml:1507-1510`은 3파일 하드코딩(코퍼스 37종 중 3종만 야간 재검증) | **있음**("ci.yml·ops/provenance_audit.py 변경") — 표만 누락 |
| MISC-01·03 (테스트 3파일) | `config.py` `misconception_visualization_mode: Literal[off,shadow,on]` 39줄 · `l4/misconception/shadow.py` 관측기 122줄 · `api/coach.py` `_maybe_visualize`/`_similar_problem_for` + 응답 필드 2종 | **7회차는 amend 안 함.** main 좌석의 기존 HARN-34 참조가 가리키는 `human-bottleneck-tasks-6dszy0`은 **LIC-07 ⑪(09-06)로 삭제됨** — 좌석이 존재하지 않는 브랜치를 1차 위치로 가리키던 상태. → **이 8회차가 amend**(§7) |
| ASM-06 (distractor_link + 테스트 + alembic) | `schema/activity.py`·`db/models/activity.py`·`api/me.py`(슬롯 신설·적재·응답 `matched_misconception_id`)·`schema_version.py`·`l4/misconception/__init__.py` export + 테스트 3파일(test_me 6건·test_activity_orm·schema/test_activity). **alembic `0afd40ce1867`의 down_revision이 폐기 대상 `7ef2b5a8e69e`라 그대로 회수 불가·재채번 필수** | 부분(슬롯·alembic·distractor_link만). 커밋 087859bd를 적어 두어 diff로 전건 도달은 가능 |
| MISC-02 (prerequisite_link + 테스트) | `api/coach.py`·`api/me.py` 보충 경로(그래프 선수 0건일 때 `misconception_crosslink_mode!=off` 게이트) + 테스트 6건(test_coach 3·test_me 3) | 부분 — blocked·"대조 자료로만" 취지라 실피해 낮음 |
| MISC-05 (slip_report + 테스트) | `ops/declared_unwired_audit.py`에 `harness.misconception_slip_report` `_OFFLINE_REPORT` 등록 9줄 — 없으면 OPS-22 감사기 미분류로 CI RED 가능(읽어서 그렇게 보임·주입 미실측) | 없음 |
| MISC-06 | (표대로 hypothesis_store·warmstart·coach) — 단 main MISC-06 `paths`는 `hypothesis_store.py`+`harness/wh1_primary.py`이고 브랜치는 A안(`warmstart.py` 소비)이라 paths 정정 필요 | 있음(파일 열거 정확) |
| PED-14 | (표대로) — 단 main PED-14 acceptance ②("Flutter가 duration_seconds를 실제로 전송")·paths(`src/mobile/**`)와 브랜치 설계(서버 벽시계 파생·클라 변경 0)가 **충돌**. 브랜치 판정(acceptance ② stale)이 main 대장에 미반영 | 있음(파일 열거 정확·② 충돌 미언급) |
| PED-15/16 → "PED-37로 재등재" | PED-37 YAML은 **main에 없다**(PR #1020 미머지). main 기준 PED-15 코드 잔여(coach.py `started_at=dialogue.started_at`·me.py 역산·테스트 5건)는 좌석 무귀속 | #1020 머지 시 해소 |
| alembic `7ef2b5a8e69e` "좌석 미확정" | 미확정이 아니라 **대체·폐기 판정 가능**(§4.3) — `verify_final_answer.py`·`completion.py`·dialogue 필드·구 테스트까지 한 묶음으로 옛 설계 | — |

**좌석 없는 잔여(main 기준·미머지 PR 제외) 2건:**
- `.claude/agents/backend-engineer.md` "검증 명령 실행 규약" 17줄 — 위임 에이전트가 전체 스위트를 백그라운드로 던지고 보고 없이 턴을 끝낸 사고 3회(MISC-02·MISC-06·PED-14)의 재발방지 규칙. 역할 기반 검색(백그라운드·포그라운드·run_in_background·nohup) `.claude/`·`docs/standards/`·`CLAUDE.md` **0건**(무관 매치 Celery·비동기 제외). 재발방지 대책이 규칙·코드·태스크 어느 형태로도 main에 없는 상태 → **HARN-79 등재**(§7).
- S3-33 "착수 전 조사에서 전량 충족" 판정 근거 5항 — 코드 잔여 0. 7회차 amend가 "재확인만 하고 done"으로 이미 다룸(main 미착지). 추가 조치 없음.

`scripts/harness/store.py`의 PED-15/16 그랜드파더 2항은 재등재(PED-37)로 사유 소멸·불필요. `docs/data/problem_bank_coverage_2026-07.json` 덮어쓰기는 동결본 관례 위반·main 우세. MEMORY 402줄은 부기(회수 시 재기록).

**7회차 amend가 이미 실린 좌석(ASM-06·MISC-02·MISC-05·PB-02·PED-14·MISC-06)은 이 8회차가 손대지 않는다** — 같은 YAML의 acceptance 끝에 두 PR이 각각 줄을 붙이면 머지 충돌이다. 위 표의 보완 목록은 #1020 머지 후 소유자가 한 번의 `amend`로 붙일 수 있게 여기 고정해 둔다(§8 정직한 공백).

### 4.4 PED-15 "started_at 상시 NULL" 버그 — 반박 실패·**main 실존 확정**(high)

7회차가 priority 1 회수(PED-37)와 PII 파기 소급 게이트를 건 전제다. 반박 4축 전부 실패:

| 반박 축 | 실측 | 결과 |
|---|---|---|
| (a) 모델 default | `db/models/activity.py:177-186` `started_at: Mapped[datetime\|None] = mapped_column(sa.DateTime(timezone=True))` — default·server_default·onupdate 전무. DDL(`20260529_0224_bb30b816083d`)도 `nullable=True`·server_default 없음(같은 파일 `LearningSession.started_at`은 `server_default=now()`). 이후 ALTER·백필 0건 | 실패 |
| (b) 다른 writer | ProblemAttempt ORM 생성 지점은 정확히 2곳(`api/me.py:745` `submit_attempt` · `api/coach.py:1012` `_complete_problem`)·둘 다 `ended_at`만 대입. `.started_at =` 대입 0건·insert/bulk/scripts 백필 0건. `AttemptSubmitRequest`는 `extra=forbid`라 클라가 보낼 수단도 없음 | 실패 |
| (c) 기존 테스트 | attempt 관련 started_at 테스트 10건 전부 nullable 단언·retention 플랜 매핑·롤업 dataclass 입력·`from_schema`로 직접 심는 헬퍼 — **writer 산출물을 단언하는 테스트 0건** | 실패(구조적으로 못 잡음) |
| (d) retention 폴백 | `privacy/retention.py:80` `(ProblemAttempt, "started_at")`·`purge_expired_records`는 `getattr(model, column) < cutoff`만 — 폴백 없음·docstring이 "NULL은 파기 대상 아님(보수적)"을 명문화. `LearningSession` CASCADE 경로는 coach 경로가 `session_id`를 아예 안 넣고 main에 LearningSession ORM 생성 지점 0건이라 실서빙 성립 미확인 | 실패 |

**7회차가 꼽지 않은 독자 2건 추가**: `l2/learning_metrics_rollup.py:596-612` `_fetch_attempts`가 `started_at.is_not(None)`으로 NULL 행 전건 제외(**COLLAB-03 일별 롤업**이 서빙 적재분에 대해 0건 집계) · `l2/concept_diagnosis.py:170` `order_by(started_at.desc().nulls_last(), attempt_id)`(**SOL-02 앵커 '최근순'**이 UUID 순서로 퇴화). 기존 8건(`wh1_evaluation.py` 시간창 4·정렬 3·주석 1)은 `GET /v1/me/harness-metrics`·`/growth-evidence`가 since/until을 그대로 전달하므로 학생 API 2곳에서 가짜 NO_DATA다.
브랜치 수정(27faee2d)은 coach.py +13(`started_at=dialogue.started_at`)·me.py +20/-2(`now−timedelta(duration_seconds)` 역산)·테스트 +255이며 main 비조상. **PED-37(미머지)의 전제와 paths는 정합**하며 재등재하지 않는다 — 다만 PED-37 paths에 `l2/learning_metrics_rollup.py`·`l2/concept_diagnosis.py`는 없으므로(수정 대상이 아니라 독자이므로 무방) 회수 시 변별력 테스트가 그 두 독자도 덮으면 좋다(권고·집행 아님).

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

## 5. 추적 중 14건 — acceptance 커버리지 전수 정독 (6·7회차 공백 **닫힘**)

6·7회차가 "소유 태스크의 실재·생존·브랜치 지목까지만 기계 확인했고 acceptance가 잔여 전부를 덮는지는 보지 않았다"고
두 번 연속 남긴 공백이다. 좌석이 done이 되는 순간 acceptance 밖 잔여는 고아가 된다(vafylb·7n9n72 실사례). 브랜치마다 에이전트
1건이 ①`git diff --name-only` 전건 → `cat-file -e` 부재/상이 → `comm -23` 고유 줄 ②고유 줄 본문 판독 ③소유 태스크 YAML 전문
(acceptance·notes·paths·artifacts) 대조 ④항목별 covered / absorbed_main_superior / uncovered 판정을 수행했다. 읽기 전용·실행 검증 없음.

| 브랜치 | 소유(status) | 잔여 | uncovered | risk | 핵심 판정 | 8회차 조치 |
|---|---|---|---|---|---|---|
| `backup/ai-content-a3ysut-pre-rebase` | OPS-41(todo) | 6 | 1 | low | diff 16파일 **전부 PR #819(081d235a)로 착지**(파일 집합 정확히 일치). 잔여 고유 줄 전건 옛 판. 유일 uncovered = main `MEMORY.md:91` 글자 깨짐("회전 자omatica" ← #922) — 브랜치 유실이 아니라 main 결함 | OPS-41 ④(a): 이 축 충족·삭제 후보 근거 성립(착수 세션 재확인 후). MEMORY 1단어는 본 PR이 정정 |
| `whymath-constitution-rules-check-azdnov` | OPS-41(todo) | 5 | 1 | low | 판정서 `id_renumber_verdict_2026-08-11.md`(106줄·착지대 head 05a1a344 포인터 유일 기록)·HARN-22(azdnov판) YAML·MEMORY 판정 로그 7줄이 main 0건. acceptance ①이 "문서"로 간접 포섭하나 **YAML 재등재·CLI 재배정은 notes에만** — 그 YAML의 실질(충돌 조회 계기판·이중 배정 16건 추적·재채번 판정 권한 승계)은 main의 어떤 열린 태스크도 소유 안 함 | OPS-41 ④(c) |
| `whymath-data-platform-design-t608mk` | OPS-41(todo) | 7 | 6 | low | r2 문서(423줄)는 acceptance ①②가 덮으나 **태스크 YAML 4건(OPS-35/36/37·QUAL-05)·MEMORY 결정 로그 13줄(Kiki D-A "ClickHouse 미도입 확정·행동 로그 정본 = PG+TimescaleDB")이 notes에만**. 갭 4건 main 존속 실측(rollup 호출 주체 0·qa_report upload-artifact 0·CLAUDE.md:73 ClickHouse 선언·pilot_kpi_baseline.py:207). OPS-35·36은 main 동번호 별건 실재 | OPS-41 ④(b) |
| `whymath-ai-recommendation-review-q8tvcx` | OPS-38(todo) | 11 | 2 | **high** | 같은 커밋 ee9df6dc의 태스크 등재 4건 중 HARN-15 main done·OPS-21은 OPS-32 흡수. **SEC-13(삭제·반출 매니페스트가 미도입 ClickHouse·S3 선언 + 실재 반출처 Langfuse 누락 — 미성년자 데이터·법령)·OPS-20(AttemptEvent seam 강제 테스트 0건)은 acceptance·main 어디에도 없음.** main `privacy/erasure.py:182/188`·`export.py:196/201` clickhouse·s3 선언·langfuse 0건 실측. 후행 `eos_privacy_gap_analysis.md`가 허위 전제를 승계 | **SEC-32(priority 1)·OPS-67 재등재** + OPS-38 ⑦(③ 문서 폐기 시 §3 R2·R3·부록 B1·C1 근거 보존) |
| `whymath-service-operations-review-5t5lmv` | OPS-40(todo) | 33 | 29 | **high** | acceptance ①②가 head 7052c34a 기준 — 그 뒤 4커밋의 **OPS-35 클라 버전 게이트(backend app.py 92줄·config·test_app 3건·mobile update_required.dart+test·컨트롤러 7건·SLO 행 = 12파일)·A11Y-02 접근성 커버리지 가드(거버넌스 테스트 160·3축 155·06_design_system §7)·OPS-34 설계 YAML·r2 §4 정정 유실 6문서(main 여전히 flutter_tts·44dp)·CLAUDE.md 규칙 1줄·MEMORY 3건**이 무소유. HARN-35 notes는 "OPS-40 소유"로 미뤄 **상호 미소유** | OPS-40 ⑤로 전건 승격(main 우세 줄 이식 금지 목록 병기) |

| `remaining-track-34zvse` | CUR-07(todo)·CUR-04/05·OPS-29·CUR-08(done #810)·MATH-05(done #826) | 20 | 1 | low | **코드·데이터·테스트 잔여 0** — diff 33 중 13은 바이트 동일/상위집합, 20의 고유 줄 전건 main 후행 우세. 유일 uncovered = **대장 불일치**: CUR-07 산출물 12파일이 main `7b4fb546`(08-25 · doldori7 · first-parent 직접 커밋 · "Closes CUR-07" · PR 없음)에 착지(4파일 바이트 동일·6파일 main 후행·acceptance ③ 충족)인데 main YAML은 todo·artifacts []·session 34zvse(죽은 claim), HARN-34 notes(08-30)는 "고립·미이식". `done --artifact 7b4fb546` 시도 → **PR 증적 게이트 exit 1 거부**(실측) — `--no-pr` 4종 어디에도 "직접 커밋 착지"가 없다 | **HARN-80 등재**(`--no-pr direct-commit <sha>` + trunk 조상 실측) + CUR-07 amend(재구현 금지·전이 전 삭제 금지). 전이 후 34zvse는 삭제 후보 |
| `openrouter-setup-guide-e98dw4` | S3-28(todo)·VIZ-06(done #740)·NLP-04(done #732)·ARCH-23(todo)·S4-16(blocked) | 31 | 2 | low | S3-28 코드(qa_pipeline `_NON_EQUATION_DSL_ANSWER_KINDS` 6종 exempt 필터·테스트 3·ci.yml continue-on-error 제거)는 main 부재이나 S3-28 (b)+ARCH-23이 정확히 소유. S4-16 잔여(강등전·결함 주입기 ~990줄)는 같은 날 #683(vafylb 세션)이 **병렬 중복 구현**으로 대체·main 판만 #829 라이브 강등전을 거침 — 단 그 폐기 판정이 main 어디에도 기록 없음. uncovered ① `GraphingCalculator.smoke.test.jsx` show_extrema 회귀 테스트 8줄 — **VIZ-06(done) acceptance ④가 약속했으나 #740에 미포함**(회수 acceptance 전수 재대조 규칙 실사례) ② `docs/standards/openrouter_vscode_setup_guide.md` 73줄 — NLP-04 ⑥이 명시 제외한 뒤 소유자 0(Cline+OpenRouter 개발자 도구 가이드·앱 코드 무관) | ① **VIZ-11 등재**(승계). ② 폐기 권고 — OpenRouter는 라우터 미배선 프로바이더라 도입 시 재작성이 맞고(2026-08-16 개방 원칙) 브랜치는 S3-28이 지키므로 소실 위험 0 · S4-16 중복 폐기 판정은 §8 |

| `whymath-coding-architecture-iws58k` | ARCH-30(todo·P3·2027 이월) | 16 | 4 | high(형식)/low(실질) | acceptance ①②·paths는 `docs/strategy/**`·`models.py`만. **E7 태스크 YAML 6건**(subject: coding·main 0건)은 `models.py` SUBJECTS "coding"의 유일 소비자라 결합 의존 — 문서만 착지하면 E7-01/02/90 인용이 매달린 참조. `licensing_safety.md` 3행(백준/프로그래머스 본문 ❌·KOI 메타만·NCIC 정보과 가등록 — 법령 축·브랜치 유일)·`subject_expansion_readiness.md` §1·§8 10줄·`06_application_modes.md` 1줄이 paths 밖. 실질 위험 낮음(전부 금지/가등록 성격·E7 미착수) | ARCH-30 ③으로 전건 승격(E7 6건 재등재/기각을 models.py와 동일 판정) |

| `whymath-issues-review-k20m0w` | MOB-18·SEC-30·PB-14·HARN-25(todo)·SEC-24(done #816)·S3-24(blocked) | 131 | 2 | **high** | 코드 축: SEC-13~18 6건은 #816(31파일·+2,586)으로 흡수 확인(마커 실측 PublicProblem 16·_MAX_IMAGE_BYTES 12·META_KEY_USER_BINDING 11 등). 나머지 src/tests 잔여(PB-04·S4-22·OPS-25·ARCH-29·MOB-11/14/15·S3-37~50·NS-01/02)는 MOB-18 ①이 이름으로 다룸. uncovered ① **`functional_security_audit_2026-08-08.md`**(133줄·결함 11건 감사 정본) — SEC-24·HARN-25·MOB-18이 참조만 하고 이식 미약속(HARN-25 ⑥ "회수 범위 밖") ② **`MGMT-03` 연령 수집·prod 신호 정책 태스크**(owner kiki·PIPA 미성년 게이트 실집행·is_production_like 단일 신호가 안전장치 3중을 결박) — main 동등 태스크 0건. 정직한 공백 3: (a) MOB-18 paths가 `src/mobile/**`·`tests/backend/**`뿐이라 src/backend 20·src/web 4·tests/infra 2·docs 2·gates 1이 밖 (b) ARCH-29 회수는 main ARCH-12(Kiki 07-13 데모 예외 공식화)와 정면 상충 — 이식 즉시 RED (c) S3-42~48은 S3-24가 아니라 S3-25 소관(7회차 주석 정정) | **MGMT-03 재등재**(priority 1·P1·owner kiki·depends MGMT-02) + MOB-18 ⑤(감사 정본 착지·paths 사각·ARCH-12 재판정 선행·S3-25 소관) |
| `whymath-pedagogy-review-gdmwhk` | PED-26(todo) | 31 | 0 | low | **코드·테스트·데이터 잔여 0** — 22파일은 PED-22~25(#831·#834·#835·#832)가 흡수·후행 갱신(브랜치판 채택 시 mode_guard 판정·k_type 맹글링·secret 폴백 **회귀**). 유일 정보 = 판정 축 3건(04f §10 "REND-05 진짜 갭" 재판정·§12 행·04e 문서번호 이중 점유 지적 / `REND-05` yaml(Kiki 08-11 결정·main 대응 0건) / `PED-21` yaml(main `signal_assembly.py` 부재·04e §12 "PED-08 ②→PED-13" 참조가 번호 충돌로 허공)). 전부 PED-26 ②가 이름으로 다루나 **"필요분만 CLI 재배정" 재량 조항이라 처분 기록 의무 없음** → done 시 조용히 소실 가능. ②의 "04f 파일 단위 이식"은 main 04e 후행 갱신을 덮어씀 → 병합이어야 | PED-26 amend(uqyg79 결과와 묶어 1회) |

| `whymath-curriculum-design-6eejrv` | PB-08(todo) | 6 | 0 | none | 코드 3파일(problems.py·test_problems·test_problems_integration)의 검수·저작권 2축 게이트+집행 지점+변별력 테스트는 PB-08 ①②③⑤가 문면으로 다룸. 리댁션·ETag 축은 main SEC-24 `PublicProblem` 투영이 상위 방식으로 해소(PB-08 notes "재도입 금지") — 회수 시 2축 where·부모 404만 이식. PR #802 = closed·merged_at null(실측) → 브랜치 yaml의 `done · #802`는 무효, main todo가 정본. PB-12는 SEC-24가 gating 6라우트로 해소·재등재 불요. 선언 공백 1: `test_problems_integration.py`가 PB-08 paths에 없음(acceptance는 다룸) | 조치 없음(paths 보강은 HARN-57 착지 후 착수 세션 몫) |

| `whymath-pedagogy-review-uqyg79` | PED-22~25(done #831·#834·#835·#832)·PED-26(todo) | 49 | 6 | low | 고유 0줄 27파일(코퍼스 YAML 11·l3 생성기 5·테스트 8 등)은 PED-22/24가 바이트 동일 이식. PR #675는 main 머지 이력 0(미머지). uncovered: `l4/pedagogy/signal_assembly.py` 60줄+테스트 119줄(PED-08 ① 공용 좌석 — 로직은 main `_build_signals` get_state 리팩터가 우세·유실은 좌석 경계뿐) · `PED-08`(blocked)/`PED-13`(todo) YAML — coach `decide()` 소비 불가 원인(concept 그래프 code ↔ 원자 code ID 공간 불일치·runtime crosswalk 필요) 실측 분석이 main 0건·번호는 타 done 태스크 점유 · `.claude/agents` 3파일 PED-11 부기 4줄(main은 유령 필드 `preferred_solution_style`을 실재처럼 서술) · `00_overview.md` 04e 인덱스 줄. OPS-15 격리 가드 2종은 PED-25 ⑤ 의도적 제외+MEMORY 회수 경로 기록 → covered | PED-26 ⑤(gdmwhk와 묶음: 처분 기록 의무·04f 병합·04e 이중 점유 해소·PED-13 재배정·소액 문서 2건·③ stale 정정) |

| `whymath-ai-content-design-vafylb` | S4-59·OPS-53(todo) | 7 | 2 | low | 코드·데이터 잔여 전부 소유 있음 — 강등전 1차 기록 문서 104줄은 S4-59 ①③④, src cp949 가드+em dash 치환 21줄은 OPS-53 ①②⑤, OPS-24 yaml은 OPS-53 재등재. 08-31 감사가 "CLAUDE.md·MEMORY = main 우세 흡수"로 뭉뚱그린 판정을 줄 단위로 재검하니 **2건은 옛 판이 아니라 main 부재 신규 내용**: MEMORY 2026-08-09 병렬 충돌 사고 로그(e98dw4의 S4-16 중복 구현 "머지 금지" 판정·Kiki 머신 클론 브랜치 전환 사고·add CLI를 썼는데도 난 OPS-23 번호 충돌 3회차) · CLAUDE.md 규칙 "공유 클론 — 브랜치 의존 명령 블록에 `git log -1` 자가검증 필수". 부기: 인플라이트 PR #844가 같은 src에 UTF-8 reconfigure 가드 독자 보유 | S4-59 ⑤(④ 착지 시 함께 판정·기록) |

| `whymath-mvp-plan-architecture-trjg5x` | PB-13(in_progress·코드는 #969 착지·done 표기 #975 미머지)·PB-14(todo)·ADMIN-02(todo)·PB-06(done) | 93 | 18 | **high** | diff 233 = 부재 45 + 상이 188(고유 0줄 140은 #969 흡수). 코퍼스 2종의 "상이"는 유실이 아니라 #969 Codex P1/P2 수학 결함 정정(브랜치판이 오답). **uncovered 18파일 전부가 PB-13 ②가 "소관 분리"로 명시 제외한 파일인데 그 소관을 받은 태스크가 main에 없다**: ① S4-19 학년축 W0(40597d5c) — `curriculum_loader.py` 대학 원자→curriculum_entry 유도 115줄·`polya/prompts.py` 학년 register 45·engine 15·`__init__` 2 + 테스트 5(그중 `test_grade_axis_governance.py`는 Curriculum-as-Overlay 기계 집행 가드 — 보호 장치 자체가 고아) ② S4-20 대학 커버리지 축 W1(1325fae1) — `problem_bank_coverage.py` 167·테스트 187·리포트 3,440(main은 "대학 409코드 미관측" 자인) ③ PATH-03(7fb49e4d) — `learning_path.py` 136·테스트 256(main PATH-03 todo·함수명까지 동일 설계·회수 원천 미지목) ④ 설계 문서 2건(302·150줄) — **PB-13이 이식한 main 생성기 6파일+batch 1파일이 이미 파일명으로 인용(유령 참조)**. PB-14 ③은 S4-19/20을 todo 재등재(재구현 전제)하고, PB-13 done(#975 머지) 시 "삭제 금지" 조건 소멸 → 고아 | PATH-03 amend(회수 원천 7fb49e4d·재구현 금지) + PB-14 ⑤(재등재 시 원천 부착·설계 문서 2건 착지·**삭제 금지를 PB-14·PATH-03·ADMIN-02 완료 후로 연장**). PB-13 YAML은 #975 소유라 무접촉 |

**§5 총괄**: 14건 중 uncovered 0 = 3(6eejrv·gdmwhk·34zvse 코드축) · low = 6 · high = 5(q8tvcx·5t5lmv·k20m0w·trjg5x·iws58k[형식]). 6·7회차 "정직한 공백"이 예고한 유형이 실재했다 — **좌석은 살아 있는데 acceptance가 잔여를 안 덮는 상태가 14건 중 9건**이며, 그중 3건(q8tvcx SEC-13 · k20m0w MGMT-03 · 5t5lmv OPS-35/A11Y-02)은 보안·법령·코드 축이다.

*(§7·§8·§9는 결과 도착 후 기재)*
