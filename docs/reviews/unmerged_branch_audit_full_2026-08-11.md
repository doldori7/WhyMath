# 미머지 브랜치 전수 감사(46건) — 미추적 고립분 판정 · 2026-08-11

> **이 문서는 시점 스냅샷이며 정본이 아니다.** 실행 정본은 `backlog/`(회수 태스크)와
> `.github/branch-cleanup-request.txt`(삭제 배치)다. 선행 판정
> `unmerged_branch_verdict_2026-08-11.md`(같은 날·#785)와의 관계: 그 문서는 브리핑이
> "미해결 장기 미머지"로 띄운 7건의 판정이고, **이 문서는 원격 브랜치 46건 전수**를 대상으로
> 그 판정이 보지 못한 고립분을 찾은 결과다. 선행 문서를 수정하지 않는다(시점 스냅샷 원칙).

작성 계기: Kiki "깃허브에 머지되지 않고 떠도는 코드들이 있으면 검토해줘".

---

## 1. 방법 · 재현 명령

이 컨테이너는 shallow 클론으로 시작해 브리핑이 "판정 보류"를 냈다(HARN-28이 추적하는 그 상태).
`git fetch --unshallow origin`(793커밋 복원) 후 재측정한 것이 아래 수치의 근거다.

```bash
# ① 전제 복구
git rev-parse --is-shallow-repository          # false여야 신뢰 가능
git fetch --unshallow origin                   # shallow면 먼저 실행
git fetch --prune origin '+refs/heads/*:refs/remotes/origin/*'

# ② 브랜치별 ahead/behind + 내용 diff
git rev-list --left-right --count origin/main...origin/<branch>
git diff --name-only origin/main...origin/<branch> | wc -l

# ③ 고립 done 대조 (프로젝트 표준 지표 — #701 선례)
for f in $(git diff --name-only origin/main...origin/<branch> -- backlog/tasks/); do
  bs=$(git show origin/<branch>:$f | grep -m1 '^status:'); ms=$(git show origin/main:$f 2>/dev/null | grep -m1 '^status:')
  [ "$bs" = "status: done" ] && [ "$ms" != "status: done" ] && echo "ISOLATED: $f (main=${ms:-부재})"
done

# ④ 추적 여부 (main 백로그·문서에 브랜치 언급이 있는가)
git grep -l "<branch-suffix>" origin/main -- backlog/tasks docs
```

열린 PR 15건(#672~#800)은 GitHub API로 대조해 **PR이 한 번도 열린 적 없는 브랜치 31건**을
분리했고, 그중 ④에서 언급 0건인 브랜치를 "미추적"으로 판정했다.

---

## 2. 전수 판정표 (46건)

### 🔴 미추적 고립 — 이번 세션이 회수 태스크를 등재 (7건)

| # | 브랜치 (head) | 규모 | 고립 내용 | 실측 근거 | 등재 |
|---|---|---|---|---|---|
| A1 | `claude/whymath-issues-review-k20m0w` (2330a095) | 45커밋·133파일·+8,760 | **SEC-13~18**(미인증 노출·XFF·OCR 상한·프로덕션 /docs·outcome 소유권·harness-metrics 노출계약) + MOB-14/15·NS-01/02·S3-37/38/39/41/49/50·ARCH-29·OPS-25 — 고립 done **21건** | main `api/ocr.py`에 크기·MIME 검증 grep 0건 · `app.py`에 `docs_url=None`/CORS 동결 grep 0건 (§3-①) | **SEC-24**(보안·P1) + **MOB-18**(비보안·P2 — 최초 제안 MOB-17은 원격 8ap436 선점으로 CLI 재배정) |
| A2 | `claude/whymath-pedagogy-review-gdmwhk` (2915bf4e) | 31파일·+2,511 | **PED-18 교수전략 카탈로그 회수+소비 배선** — 코퍼스 YAML 10종 + schema/registry/selector/assembler + 테스트 3종. **uqyg79 회수의 3차 완성본**(§3-② 참조) | main에 `data/corpus/pedagogy_strategies_v1/` 0개·`schema/pedagogy_strategy.py` 부재. 브랜치 태스크가 `todo`라 고립-done 탐지기 사각(§4-1) | **PED-26** |
| A3 | `claude/whymath-visualization-review-28d0yx` (7ce40f4f) | 24파일 | VIZ-07 done(수직선 1D 축·좌석 7종) + 시각화 R4 문서 | `merge-base --is-ancestor` 실측: **PR #759(r3) head 4bb6cd10의 상위집합** — #759는 구버전 스냅샷 | 태스크 불요 — **PR #759를 이 브랜치로 교체** 권고(§5) |
| A4 | `claude/remaining-track-34zvse` (36d33e7e) | 18파일·코드 7 | OPS-29(CI 강제 상태 선언 계약)·CUR-04(성취기준 조인 축 이원화 해소)·CUR-05 고립 done | main 3건 전부 `status: todo` | **CUR-08**(최초 제안 CUR-07은 원 브랜치 자신이 선점 — CLI 재배정) |
| A5 | `claude/whymath-service-operations-review-5t5lmv` (7052c34a) | 17파일 | 서비스 운영 r2 문서 + `api/speech.py`·`schema/speech.py` 변경 + **전체 backend 스위트 통과 실측 기록** | 문서 전용 아님 — 코드 2파일 | **OPS-40** |
| A6 | `claude/whymath-coding-architecture-iws58k` (a8e01be2) | 16파일 | 코딩/정보 E축 후보(E7) 설계 + `scripts/harness/models.py` 변경 | subject-expansion 유일 설계 산출물 | **ARCH-30** |
| A7 | 08-11 설계문서 fleet 5건 — `a3ysut`·`8ap436`·`t608mk`·`p1hubt`·`azdnov` | 각 1커밋 | AI콘텐츠 R3 · 게임화 r3 · 데이터플랫폼 r2 · 학습경로 r3 · 헌법 통합감사+재채번 판정 | 전건 **PR 미오픈** — "산출물이 있으면 PR" 규칙(2026-08-11 신설) 위반분. `t608mk`는 OPS-38 acceptance ③(q8tvcx의 동명 r2 문서 판정)과 본문 대조 필요 | **OPS-41**(일괄 PR 백필) |

### 🟡 이미 추적 중 — 재등재 금지 (기존 태스크·PR이 소유)

| 브랜치 | 소유 태스크/PR |
|---|---|
| `claude/whymath-mvp-plan-architecture-trjg5x` (11,446문·233파일 — 최대) | **PB-06**(PR #795 회수조건 확정)·회수 실행은 Kiki 소유 |
| `claude/whymath-ai-recommendation-review-tv1f08` (REC-05·REC-08 done) | **REC-09** |
| `claude/whymath-solution-review-40xspg` (S4-09 2,153줄) | **SOL-01** — `6ybkis`(c5e25116)가 회수 이식 진행 중(원격 claim 활성) |
| `claude/whymath-ai-recommendation-review-q8tvcx` (OPS-19) | **OPS-38** |
| `claude/whymath-pedagogy-review-uqyg79` (PR #675) | **PED-22~25** — 단 §3-② 참조: gdmwhk가 상당 부분을 이미 실행했다 |
| `claude/admin-01-operator-seat-grant-audit` (PR #713) | **ADMIN-08** + PR #799·#800이 후속 수습 중 |
| `claude/openrouter-setup-guide-e98dw4` (S4-16·VIZ-03/04·S3-28) | **NLP-04·VIZ-06** |
| `claude/human-bottleneck-tasks-6dszy0` / `merge/human-bottleneck-6dszy0` | PR **#739**(+MISC-04 분리분 **#744**) |
| `claude/subject-problems-theory-check-7n9n72` (83파일) | **CUR-05·ARCH-28** 참조 + SOL-01 회수 진행 브랜치(원격 claim 활성 — 손대지 않음) |
| `claude/whymath-ai-content-design-vafylb` (S4-16 강등전 실측 기록) | **S4-16**·KG-02 notes가 참조 |
| 열린 PR 15건의 head 브랜치 (위와 중복 제외) | 각 PR이 소유 — 이 감사 범위 밖 |

### 🟢 삭제 후보 — 잃을 내용 없음 실측 (다음 배치 등재)

| 브랜치 (head) | 근거 |
|---|---|
| `claude/merge-failure-reflection-issues-560vwh` (e93d36bc) | ahead=0 · diff 0파일 — 전량 흡수됨 |
| `claude/path-05-me-tab-learning-path-consumption` (36e3eb13) | main `PATH-05 = done`(PR #728 포팅, artifacts가 이 브랜치 커밋 f9644016 직접 인용). 고립 done 0건 |
| `claude/mob-10-done-bookkeeping` (8af55fa5) | main `MOB-10-diagnosis-evidence-render = done` — 상태전이 전량 반영됨 |
| `claude/s3-17-suneung-prefilter-persona-fit-widen` (f23feb76) | 브랜치는 `blocked` 기록이나 main은 이미 **done**(교차 회수 착지·events 2426 참조) — 브랜치 기록이 낡음 |
| `claude/s3-24-shadow-recovery-bucket-b` (928b2ac4) | main도 동일 사유로 `blocked` — 반영 완료 |
| `claude/misc-02-prerequisite-coaching-misconception-link` (6d61321d) | block 사유(acceptance 필드 오류+교수학 결정 필요)를 **이 세션이 main에 이관 완료**(CLI `block` 경유) — 이관 후 잃을 내용 없음 |

### ⚪ 판정 대상 아님

- `harness-claims` — 하네스 소유 claim 저장소(#785에서 스캐너 제외 처리됨)
- `claude/whymath-nlp-design-my18a1`·`claude/whymath-math-engine-design-4qbaru` — 고유 내용이
  전부 main 머지 커밋(diff 8파일이 전부 merge 잔여). 2026-08-04 삭제 판정 계보에 이미 등재 —
  다음 배치에서 재확인 후 삭제 가능(이번 배치 미포함: 04 triage 문서가 소유)

---

## 3. 핵심 실측 2건 (등재 근거)

### ① A1 보안 고립 — main에 코드가 전혀 없다

```bash
git show origin/main:src/backend/whymath_backend/api/ocr.py | grep -cE 'content_type|max_bytes|413|415'   # → 0
git show origin/main:src/backend/whymath_backend/app.py     | grep -cE 'docs_url|allow_origins'           # → 0
```

브랜치 쪽은 OCR 업로드에 MIME 허용목록(415)·바이트 상한(413), `app.py`에 프로덕션 조건부
`docs_url=None`·CORS 동결 테스트(`test_cors_policy_freeze.py`)가 있다. **왜 여태 안 보였나**:
main의 **HARN-25**가 원인을 이미 규명해 뒀다 — `remote_claims.py`의
`_DOC_SERIES_SUFFIX='_review.md'` 필터가 k20m0w의 `functional_security_audit_2026-08-08.md`를
브리핑 후보에서 누락시켰다. 즉 **탐지 결함(HARN-25)은 등재됐지만, 그 결함이 가린 산출물
자체를 회수하는 태스크는 없었다.** 계정·보안 r2 세션이 SEC-14 중복 설계 직전까지 갔다가 수동
조사로 멈춘 것도 이 사각의 실피해다. main의 SEC 번호가 12에서 20으로 건너뛴 것은 그 세션이
브랜치의 SEC-13~18 번호를 피한 흔적이다 — **번호는 피했는데 내용은 회수하지 않았다.**

### ② A2 — 같은 카탈로그의 3차 구현이 떠 있고, main엔 4차 구현 태스크가 대기 중

교수전략 카탈로그의 계보:
1. **uqyg79**(PR #675, 2026-08-03) — 1차 구현(PED-04·05 done, 브랜치 번호 기준)
2. **enfkqt** — uqyg79의 진부분집합(#785가 삭제 배치 처리)
3. **gdmwhk**(2026-08-11) — uqyg79를 **회수하며 정정 4곳**(문서번호 04e→04f·mode_guard 판정을
   main PED-16으로 승계·낡은 파일 3건 hand-port·태스크 번호 재배정) + **소비 배선 신설**
   (runtime_selector.narrow_candidates·prompt_assembler.attach_strategy_card·플래그 OFF 캔어리)
4. main **PED-22~25**(#785 등재, todo) — uqyg79 기준의 회수 태스크

**gdmwhk가 PED-22·23의 실행분을 이미 포함하는데 PR이 없어**, PED-22~25가 그대로 실행되면
**4차 중복 구현**이 된다. 파일 겹침 실측: gdmwhk와 uqyg79의 diff 대상 파일이 코퍼스 11건·코드
10건 전건 일치(gdmwhk가 최신). 단 uqyg79의 **생성기 5파일은 gdmwhk에 없다** — PED-24(비유
생성기) 축은 여전히 uqyg79에서만 회수 가능하다. 추가 함정: gdmwhk가 등재한 태스크 번호
PED-18~21이 main의 PED-18(tutor-primary-operation-rate)·PED-19(concept-question-routing-seam)와
**충돌**한다(§4-3).

---

## 4. 구조적 발견 3건

1. **고립 탐지의 사각 — 구현은 있는데 `done` 표기가 없으면 안 보인다** (A2 실측).
   고립 검출이 전부 "브랜치 done vs main done" 대조라, 구현을 마치고 태스크를 닫지 않은(또는
   신규 등재만 한) 브랜치는 항구적으로 무시된다. gdmwhk의 PED-18은 브랜치에서도 `todo`였다.
   → **HARN-31 등재**(내용 신호 — 브랜치 고유의 src/tests 신규 파일 존재 — 를 보조 축으로).
2. **PR 증적 게이트는 소급이 없다** — `backlog.py done`의 PR 검사(2026-08-11 신설)는 앞으로의
   done만 막는다. 기존 재고 31건이 이 감사의 대상이었고, 관측 좌석은 **HARN-30 ③**이 이미
   소유한다(중복 등재하지 않음 — 이 감사의 회수 태스크들이 재고 소진을 맡는다).
3. **태스크 ID 충돌 9건 실측** — 브랜치와 main에서 같은 번호가 다른 태스크:
   `S4-19`·`S4-22`(trjg5x) · `MOB-14`·`OPS-25`(k20m0w) · `PED-15`·`PED-16`(7n9n72) ·
   `VIZ-04`(e98dw4) · **`PED-18`·`PED-19`(gdmwhk — 신규 발견)**. git도 validate도 잡지 못한다
   (full-ID가 슬러그 덕에 다름). PB-06 §2 ⑵·HARN-10이 이미 다루는 축이므로 별도 등재 없음 —
   각 회수 태스크 acceptance에 "원 번호 재사용 금지·CLI 재배정"을 고정했다.

---

## 5. 권고 (사람 결정 대기)

- **PR #759 교체**: head를 `claude/whymath-visualization-review-r3`(4bb6cd10)에서
  `claude/whymath-visualization-review-28d0yx`(7ce40f4f)로 — 후자가 전자의 상위집합(ancestor
  실측)이며 VIZ-07 done + R4 문서를 추가로 담는다. 브랜치 교체는 PR 재오픈이 필요하므로 Kiki 판단.
- **PED-22~25 처분**: PED-26(gdmwhk 회수) 실행 시 PED-22·23은 충족-폐기 또는 흡수 판정,
  PED-24·25는 잔존(생성기 축) — PED-26 acceptance에 대조 실측을 고정해 뒀다.
- **삭제 배치**: §2 🟢 6건을 `.github/branch-cleanup-request.txt`에 등재했다(head SHA 스냅샷 병기).
  머지 직전 라이브 재조회 필수(#785와 동일 경고).

## 6. 정직한 공백

- **코드 이식 0줄** — Kiki 결정(이 세션 범위 = 판정+등재). 등재된 태스크가 실행되지 않으면 고립은 그대로다.
- **각 브랜치 구현의 정확성은 보지 않았다** — 판정은 "고유한가·추적되는가"까지. 정확성은 이식 시 CI·리뷰가 판정한다.
- **A5·A6·A7 문서 본문의 채택 가치는 읽지 않았다** — 각 회수 태스크 acceptance ①이 본문 대조를 선행 조건으로 고정한다.
- **스냅샷이다** — 원격 claim 4건 활성(MISC-04·PB-08·REC-06·SOL-01), 다른 세션이 계속 푸시 중.
  삭제 배치 머지 직전 라이브 브랜치 목록 재조회 필수.
