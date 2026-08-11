# 미해결 장기 미머지 브랜치 판정 — 2026-08-11

> **이 문서는 시점 스냅샷이며 정본이 아니다.** 실행 정본은 `backlog/`(회수 태스크)와
> `.github/branch-cleanup-request.txt`(삭제 배치)다. 판정의 *근거*를 남기는 것이 이 문서의 목적.

작성 계기: Kiki "미해결 장기 미머지 브랜치 9건 결정". 착수해 보니 **결정 이전에 판정의 입력
자체가 망가져 있었다** — §1이 그 실측이고, §2가 고친 뒤의 판정이다.

---

## 1. 브리핑 수치가 틀렸다 — 탐지기 결함 4종

세션 시작 브리핑은 "⚠️ 미해결 장기 미머지 브랜치 (Kiki 결정 필요) — **19건**"을 냈다.
GitHub 라이브 실측과 대조한 결과 그 목록은 절반이 허구였다.

| # | 결함 | 실측 | 방향 |
|---|---|---|---|
| ① | **shallow clone 맹점** | 이 컨테이너 클론이 shallow(`--is-shallow-repository`=true·`origin/main` 50커밋·경계 2026-08-06). 흡수 커밋이 절단면 밖이라 `_find_ported_evidence`의 grep이 못 봄 → **이미 포팅된 브랜치가 "미해결"로 승격**. `ahead` 수치도 657~720까지 부풀었다 | 미탐 |
| ② | **`--prune` 누락** | fetch refspec에 `--prune`이 없어 원격에서 삭제된 브랜치의 remote-tracking ref가 잔존. `git fetch --prune` 1회에 **유령 23건**이 사라졌다 | 유령 |
| ③ | **needle이 좁다** | `_SESSION_SUFFIX_RE = -([a-z0-9]{6})$` — 6자 세션 접미사가 없는 브랜치(`claude/harn-14-…`·`claude/admin-01-…`·`worktree-agent-…`)는 **시도조차 못 해** 항구적 "미해결" | 미탐 |
| ④ | **needle이 헐겁다 (가장 위험)** | 같은 6자 needle이 평범한 영단어도 잡는다(`…-metrics-writer`의 "writer"). 게다가 grep이 커밋 **본문**까지 훑어, *"이 브랜치들은 미해결이다"*라고 적은 판정 문서 커밋이 그 브랜치를 **"해결됨"으로 뒤집었다** | **오탐** |

### ④의 실제 피해 (하마터면)

`claude/whymath-solution-review-40xspg`는 브리핑에서 **"이미 포팅됨 — 원본 정리만 필요, 결정
불요"** 로 분류돼 있었다. 근거로 잡힌 커밋 `807aa479`는 `MEMORY.md`·`backlog`·`docs`만 고친
판정 문서였다. 그런데 이 브랜치는 **미회수 S4-09 완료분**(2,153줄)을 안고 있다 — 그대로
삭제 배치에 들어갔으면 실작업이 사라졌다.

### 헌법 판정

네 결함 모두 **성공/실패 양쪽에서 그럴듯한 목록을 낸다**. CLAUDE.md 위반 3건:
"침묵 실패 금지" · "변별력 없는 검증 스텝 금지"(*성공/실패에 같은 값을 내면 검증이 아니라
위장*) · "간접 신호를 성공 판정으로 쓰는 안내 금지".

### 수정 (같은 PR)

- **shallow 감지 → 판정 보류**(`status="shallow"` + 복구 명령 `git fetch --unshallow origin`을
  브리핑 화면에 노출). 가드는 fetch *앞*에 둔다 — 못 믿을 결과를 위해 90초 예산을 쓰지 않는다.
  `--unshallow` 자동 실행은 채택하지 않았다(SessionStart 훅이 매번 도는 경로 · 훅은 stderr를
  버려 진행이 안 보임 · 컨테이너가 매번 새로 생겨 1회성 비용이 아님).
- **fetch 5곳에 `--prune`**.
- **needle을 브랜치 basename 전체로** + 길이 하한 12자 + **원장 전용 커밋 배제**
  (`MEMORY.md`/`backlog`/`docs`/`.github`/`ROADMAP.md`/`README.md`/`CLAUDE.md`만 고친 커밋은
  "언급"이지 "흡수"가 아니다). 실측 10건에서 진짜 흡수 5건은 전건 유지, 문서 언급 5건은 전건 제거.
- **`harness-claims` 브랜치 제외** — 하네스가 스스로 만드는 claim 저장소이지 사람이 결정할
  작업 브랜치가 아니다(claim이 3일만 조용하면 "Kiki 결정 필요"로 뜨던 구멍).

수정 후 브리핑: 미해결 19건 → **7건**, 40xspg는 "미해결"로 정정, worktree-agent·harn-14는
"이미 포팅됨"으로 정정.

### 정직한 잔존 한계

- **미탐은 남긴다(의도된 비대칭)** — 순수 문서·백로그 PR로 정리된 브랜치, 트렁크의 진짜 머지
  커밋(`--name-only`가 빈 목록)은 검출되지 않고 `unresolved`로 남는다. **과보고는 사람이 훑으면
  되고 과소보고는 사고가 된다.** 실제로 `q8tvcx`·`h87afk`가 이 경우다(§2에서 사람이 판정).
- **오탐이 완전히 사라지진 않았다** — 코드 커밋이 다른 브랜치를 *충돌 상대*로 언급하는 경우는
  텍스트로 구분 불가다. 그래서 브리핑은 `ported` 항목에 근거 커밋을 항상 함께 노출한다.
- **full clone 실측은 이 세션에서만 했다** — 이 컨테이너를 `--unshallow`한 뒤 770커밋 위에서
  확인했고, Kiki 로컬(항상 full)에서는 재확인되지 않았다.
- **모든 세션 컨테이너가 shallow라면 이 스캐너는 다시는 목록을 내지 않는다.** 그 경우 이 수정은
  문제를 해결한 게 아니라 침묵을 *정직한* 침묵으로 바꾼 것이다. 다만 보류는 무기한 침묵이
  아니라 매 세션 화면에 뜨는 미측정 신고 + 복구 명령이므로 "만료 없는 유예"에 해당하지 않는다.

---

## 2. 브랜치별 판정

판정 지표(#701 선례): 브랜치의 태스크 `status`와 main의 같은 태스크 `status` 대조 → 고립된
`done` 검출. 라이브 main 확인은 GitHub API로 교차했다.

### 🔴 회수 — 고립된 완료 작업이 있다 (5건, 전부 삭제 보류)

| 브랜치 (head) | 고립 완료분 | 처분 |
|---|---|---|
| `claude/admin-01-operator-seat-grant-audit` (53a06c4f) | **ADMIN-01 done**(`8924a2e2` — role_grant_cli + role_change 감사). 라이브 main = `todo`·`artifacts: []` | **ADMIN-08** 신규 등재 |
| `claude/whymath-pedagogy-review-uqyg79` (5dc040b3) | **PED-04·05·06·07·09·10·11·12 + OPS-15 done — main에 파일 자체가 없음.** 신규 파일 21건(카탈로그 YAML 10 + schema + registry + 생성기 5 + 04e 문서) | **PED-22·23·24·25** 신규 등재 |
| `claude/whymath-ai-recommendation-review-q8tvcx` (e1835c0c) | **OPS-19 done**(`592c961f` CI 게이트 도달 가능성 계약) — main에 태스크 파일 부재. 설계 문서 1건도 부재 | **OPS-34** 신규 등재 |
| `claude/whymath-solution-review-40xspg` (707c5665) | **S4-09 done**(`86212c43` 2,153줄). 라이브 main = `todo` | **SOL-01 기등재**(2026-08-11·priority 1) — 신규 등재 불요 |
| `claude/admin-02-dead-tenancy-billing-columns` (d42fbd40) | 고립 done 0건이나 **태스크 전제를 반증하는 실측**을 담은 block 사유 | ADMIN-02를 `blocked`로 전이해 사유 이관 완료(CLI 경유) |

> **PED-04~12는 main의 동명 태스크와 번호만 같고 내용이 다르다**(ID 이중 배정 계보 —
> MEMORY 2026-08-04 13건). 회수 태스크는 전부 신규 번호를 받았고 원 번호 매핑을 notes에 남겼다.
> 재채번 실행 판정은 Kiki 전권 유보 사항이라 이 세션이 결정하지 않았다.

### 🟢 삭제 — 잃을 내용이 없다 (6건)

| 브랜치 (head) | 근거 |
|---|---|
| `claude/whymath-teaching-strategy-enfkqt` (469ee9ad) | uqyg79의 **진부분집합**(고유 커밋 0건 실측). uqyg79가 PED-22~25로 보존됨 |
| `claude/whymath-probe-supply-h87afk` (b849bb04) | REC-02 **중복 구현의 패자**. main의 REC-02는 done — 다른 브랜치(`human-bottleneck-tasks-6dszy0`·`d554ddad`)에서 회수돼 착지 |
| `claude/harn-14-doc-series-duplicate-detection` (215b45ff) | PR #714로 포팅(`b4b0153d`). main HARN-14 = done |
| `claude/backlog-drive-next` (de446ec3) | trunk 대비 **ahead=0** |
| `claude/whymath-account-security-973iv1` (8810bc8b) | trunk 대비 **ahead=0** |
| `worktree-agent-a6e26595b30efb856` (6059043d) | PR #728로 포팅(`4adc6870`). main PATH-05 = done이며 artifacts가 이 브랜치 커밋 `f9644016`을 직접 인용 |

`worktree-agent-*`는 삭제 워크플로 허용 패턴 밖이라 그동안 삭제 경로가 아예 없었다 —
이번에 패턴을 추가했다(기계 생성 접두라 사람 브랜치와 섞이지 않는다).

### ⚠ 통째 머지 금지 (실측)

판정 대상 전건이 main 대비 **44,000~170,000줄 삭제**로 나온다 — 브랜치가 main보다 *낡았다*는
뜻이다. `git merge`하면 main의 완료분을 되돌린다. 등재된 회수 태스크는 전부 **파일 단위 이식**을
acceptance에 고정했다(NLP-04 선례: `app.py`·`coach.py`가 브랜치 쪽이 낡아 통째 채택 시 회귀).

---

## 3. 정직한 공백

- **코드 이식은 하지 않았다.** 이 세션은 판정·등재·삭제 요청까지다. 등재된 5개 태스크
  (ADMIN-08·OPS-34·PED-22~25 + 기등재 SOL-01)가 실행되지 않으면 고립은 그대로다.
- **각 브랜치 구현이 *올바른지*는 보지 않았다.** 판정은 "고유한가·완료됐는가·중복인가"까지다.
  정확성은 이식 시 CI와 리뷰가 판정한다.
- **PED 계열 4분할은 산출물 응집도 기준의 판단**이며, 실제 이식 시 경계가 달라질 수 있다.
  PED-25는 "지금도 결함인지 먼저 실측하고 아니면 제외"를 acceptance ①로 고정했다.
- **q8tvcx의 설계 문서 1건**(`data_platform_module_gap_review_r2.md`)의 회수/폐기는 본문을
  읽어야 판정된다 — OPS-34 acceptance ③으로 넘겼다(추측으로 정하지 않았다).
- **스냅샷이다.** 다른 세션이 계속 푸시 중이므로(원격 claim 3건 활성) 삭제 배치 머지 직전에
  라이브 브랜치 목록을 재조회해야 한다.
