# 운영 플랫폼(Operations Platform) 모듈 — 외부 EOS 틀 대조 **2차 재점검(r2)** (2026-08-11)

> **범위**: 외부 참고 문서 『21. 운영 플랫폼』(1단계 모듈 86 권한 관리 · 87 조직 관리 ·
> 88 학교 관리 · 89 라이선스 관리 · 90 감사(Audit) 로그 — **WhyMath 전용이 아닌 일반 SaaS 틀**,
> Kiki 제공)의 **3번째 제출**. 세부 항목 **91개**(86=22 · 87=17 · 88=16 · 89=18 · 90=18)로
> v1이 대조한 집합과 **동일**하다.
> **형식**: 처음부터의 재대조가 아니라 **델타 재점검**이다 —
> `learning_path_module_gap_review_r2.md`·`problem_bank_gap_review_r2.md`·
> `solution_module_gap_review_r3.md`가 확립한 별도 파일 관례를 따른다.
> **결론**: 기능 판정은 거의 그대로인데 **최대 갭이 "기능 부재"에서 "대장·코드·브랜치 4자
> 분기"로 이동**했다. ① `ADMIN-01`은 815줄 구현이 브랜치에 고립돼 있고 main 대장은 `todo`다
> (미병합 고립 5회차). ② `ADMIN-03`은 **이미 main에 착지했는데** 대장만 `todo`였고, 그 사이
> 다른 브랜치가 **같은 일을 다시 구현**했다. ③ `ADMIN-02`는 main에 병합된 정정 판정을 거슬러
> 4컬럼 전량 드롭이 브랜치에 구현됐다 — **정정이 대장에 도달하지 못했기 때문**이다(반복 실수
> **11회차**·새로운 축). 판정 뒤집기 3건 · 신규 설계 D5~D8 · 신규 태스크 3건 · 게이트 1건 ·
> 대장 정정 2건 · 정본 정정 3곳. **`src/` 변경 0.**

관련 정본: `docs/architecture/operations_platform_gap_review.md`(**모체 v1** + §독립검증 —
본 문서가 그 델타) · `docs/architecture/operations_module_gap_review_r3.md`(§6이 같은 고립을
발견하고 권고만 남긴 지점 — 본 문서가 그 판정을 정정) · `docs/architecture/
account_security_gap_review.md`(§4-⑦ 정정 대상) · `docs/design/ui/04_admin_console_
architecture.md`·`03_admin_console_plan.md`(관리 콘솔 정본) · `docs/legal/pipa_data_matrix.md`
+ `data/access_matrix.json`(COLLAB-01 — 2차원 인가 계약) · `docs/standards/security_privacy.md`
· `docs/standards/build_harness.md` · `CLAUDE.md` 절대 금기 · `MEMORY.md`(2026-08-03·08-04·08-11).

**판정 기호**: `✅` 충족·초과 / `⚠️` 부분·진짜 갭 → D / `△` 부품은 있으나 소비 0 /
`⏸` 기존 추적 승계 / `🚫` 의도적 미채택

---

## §0. 전제

### ①-a 이 틀은 이미 두 번 대조됐다 — 새로 쓰면 3중 착수다

| 회차 | 산출 | 커밋 | 성격 |
|---|---|---|---|
| **v1** (2026-08-03) | `operations_platform_gap_review.md` 본문 — D1~D4 + `ADMIN-01`~`03` 등재 | `b31ded26` (#663) | 최초 전수 대조 |
| **§독립검증** (2026-08-04) | 같은 파일에 append — D1·D3 독립 재현 + **D2 스코프 정정** | `c3376c42` (#698) | 교차 검증(중복 착수를 작성 전에 발견) |
| **r2** (2026-08-11·본 문서) | 별도 파일 | — | **델타 재점검** |

### ①-b 왜 v1을 in-place로 고치지 않는가

v1 본문은 **`ADMIN-01`~`03`의 `notes`가 가리키는 판정 근거 정본**이다. 완료·인용 대상 태스크의
근거를 소급 변조하면 *"왜 그렇게 결정했는가"* 의 기록이 사라진다
(`arch_audit_2026-07-09.md → _r2/…/_r8` 리비전 관례). 게다가 v1은 이미 §독립검증이라는 append
층을 한 번 얹었다 — **4번째 층을 같은 파일에 쌓으면 "언제 무엇이 참이었나"가 뭉갠다.**
v1에는 포인터 배너 1줄만 추가한다.

> §독립검증 자신은 "r2 파일을 새로 만들지 않은 이유"를 *"이 문서는 미머지이고 참조 태스크 3건이
> 전부 `todo`"* 로 적었다. 그 전제는 **둘 다 무너졌다** — v1은 `b31ded26`으로 병합됐고,
> 참조 태스크 3건 중 1건은 이미 완료됐다. 따라서 이번엔 별도 파일이 맞다.

### ①-c 재점검이 필요했던 실제 사유 3종

| # | 사유 | 실측 |
|---|---|---|
| ⑴ | **v1 D 3건의 착지 상태가 main·브랜치에서 서로 모순** | 아래 §3 4자 분기표 — 최대 사유 |
| ⑵ | **v1 §독립검증 ③이 "설계 근거가 얇다"며 등재를 미룬 갭이 실피해로 발화** | `b3a58b02`가 정정 전 acceptance를 그대로 집행 → §4 D8 |
| ⑶ | **v1이 보지 않은 평면 = 수집 항목 대장** | `gender`·`school_region`이 어느 대장에도 없음 → §4 D7 |

### ①-d 승계 선언 — 재판정하지 않는 것

- **§2 의도적 미채택 15건** — 트리거만 재심(§2), 근거 재판정 없음
- **§4 정직한 공백 7종**·**§5 발화조건 6건** — §6·§7에서 델타만
- **D4(조직·학교·라이선스 테넌시) 페이퍼** — §5에서 실측 재확인만, 설계 재작성 없음
- **`ADMIN-01`·`ADMIN-02`의 원 acceptance** — 수정하지 않는다(§4 D6·D8 참조)

---

## §1. 기능 86~90 델타 재대조 — **판정 뒤집기 3건**

### 정정 ① 기능 90 「장기 보관」 — ⚠️ **D3** → ✅ **상환**

| | v1 (2026-08-03) | r2 실측 (2026-08-11) |
|---|---|---|
| 근거 | "`deletion_audit`·`privacy_audit`은 `_RETENTION_PLAN`에 **미포함 = 사실상 무기한**. 그 결정이 문서 어디에도 명문화되지 않음" | **`ADMIN-03` 착지** — `7dbf40c5`(PR #716, 2026-08-08, Kiki 병합) |
| 판정 | ⚠️ **D3** | ✅ **상환** |

착지 실물 3종:
- `privacy/retention.py:20-34` — 모듈 docstring에 "감사 2테이블 의도적 제외 — 무기한 보존의
  *명문화된* 침묵 (ADMIN-03)" 15줄. v1 D3이 지목한 *"코드·문서 어디에도 없다"* 가 **과거형으로
  그 문단 안에 인용**돼 있다.
- `docs/standards/security_privacy.md:177-198` — 편집자 부기. 기존 `# 보존: 5년` 주석을
  "**잠정 참조값이며 아직 기계적으로 시행되지 않는다**"로 명시 정정 + 연한 확정은 `MGMT-02` 선행.
- `tests/backend/privacy/test_audit_retention_exclusion.py` — 동결 테스트. `:93`
  `test_sweep_flags_injected_audit_table_then_clears_after_removal`이 **변별력(④)** 을 담당.

**r2 실행 확인(배선 실재성)**: 이 문서 작성 세션이 `python3 -m pytest
tests/backend/privacy/test_audit_retention_exclusion.py` 를 직접 실행 → **5 passed, EXIT=0**.
"저장소에 존재함 ≠ 돌아감"을 실측으로 닫았다.

**단, 범위는 v1이 정한 그대로다** — 보존 **연한 숫자**는 여전히 미확정이고 `MGMT-02`(변호사
회신·blocked)가 선행한다. 상환된 것은 "침묵"이지 "연한"이 아니다.

### 정정 ② 기능 86 「세분화된 권한(Granular Permission)」 — △(설계 문서만) → ✅ **계약 기계화** / △ **소비 0**

| | v1 | r2 실측 |
|---|---|---|
| 근거 | "2차원(역할×데이터항목) 매트릭스는 `pipa_data_matrix.md`에 **설계만** 있고 인가 코드로 구현되지 않음"(v1 §1·§4-③) | **`COLLAB-01`(done, `e937f42d`, 2026-08-05)** — `data/access_matrix.json`(9,632바이트) 신설 |
| 판정 | △ | ✅ **계약은 기계 강제** / △ **소비 좌석 0** |

- 구조: `resolutions`(full/summary/none) + `roles`(student·content_admin = `active` /
  teacher·parent = `planned`, `role_enum_value: null`) + `items` 9행 + 각 항목 `produced_by`
  (실제 L2 함수·`/v1/me/*` 필드 경로)
- 거버넌스 게이트 `tests/backend/schema/test_access_matrix.py` — 계약↔문서 동기 · `Role` enum↔
  roles 축 정합 · **선형 서열 비전제** · `produced_by` 누락 검출
- **`content_admin`은 9항목 전부 `none`** — "운영자는 학생 PII 뷰어가 아니다"가 산문이 아니라
  **코드로** 못박혔다.

v1 §4-③("그 표의 각 셀을 실제 인가 체크로 구현한 코드는 아직 없다")은 **계약 축에서 반증**됐다.
다만 **응답 필터링을 실제로 수행하는 소비 좌석은 여전히 0**이므로 △가 함께 남는다 —
`COLLAB-01` acceptance ⑦이 "역할 신설 금지, 계약만 동결"로 경계를 확정한 결과이지 누락이 아니다.

### 정정 ③ 기능 86 「콘텐츠 관리자」·기능 90 「권한 변경」 — ⚠️ **D1 유지, 단 원인이 바뀌었다**

| | v1 | r2 실측 |
|---|---|---|
| 근거 | "`Role.CONTENT_ADMIN`을 부여하는 코드 경로가 저장소 전체에 **0건** — **만들지 않았다**" | **만들었는데 main에 없다** — `ops/role_grant_cli.py`(231줄)·`AuditEventKind.role_change`·`record_role_change_audit`가 `8924a2e2`에 실재하나 main 전건 부재 |
| 판정 | ⚠️ D1 | ⚠️ **D1 유지** — 증상 동일, 원인은 "미구현"이 아니라 **"고립"** |

main 재현(전건 v1 그대로):
- `grep -rE '\.role\s*=[^=]|role\s*=\s*Role\.' src/ scripts/` → **0건**
  (`role=Role.CONTENT_ADMIN` 히트는 전부 `tests/`)
- `api/auth.py:159-166` `resolve_user` — `UserProfile(...)` 생성 kwargs에 `role` 없음
- `api/_auth.py:123-124` `require_content_admin`/`RequireContentAdmin` → 부착 라우터 **정확히 6곳**
  (`api/concepts.py:244/342/391` · `api/problems.py:57/184/231`)
- `schema/enums.py` `AuditEventKind` **3값**(`export_data`·`consent_change`·`admin_access`) —
  `role_change` 저장소 전수 0건
- `ops/` 12파일 중 role 관련 0

**이 원인 전환이 중요한 이유**: v1의 처방(설계·구현)은 이제 틀렸다. 필요한 것은 **회수**다(§4 D5).

### 승계 (변화 없음 — 재대조 생략)

기능 86의 나머지 20항목 · 기능 87 전 17항목 · 기능 88 전 16항목 · 기능 89 전 18항목 ·
기능 90의 나머지 15항목은 v1 §1 판정을 그대로 승계한다. 기능 87·88·89의 근거인 **조직 엔티티
0**은 §5에서 실측 재확인했다.

### v1 본문 줄번호 드리프트 (판정 무변경 — 인용 위치만)

| v1 인용 | 현행 |
|---|---|
| `schema/enums.py:1163-1194` `Role` | `:1217`(값 `:1245` STUDENT · `:1248` CONTENT_ADMIN) — **+51** |
| `schema/enums.py:1114` `AuditEventKind` | `:1138`(값 `:1151`/`:1154`/`:1157`) |
| `api/auth.py:146` `resolve_user` | `:138`(생성부 `:159`) |
| `privacy/retention.py:46` `_RETENTION_PLAN` | `:66-84` — 10모델 → **11모델**(`ProblemSolveTimeDistribution` 추가) |

v1 본문은 고치지 않는다(위 ①-b) — 미래 세션은 이 표로 위치를 보정한다.

---

## §2. 의도적 미채택 15건 — 트리거 재심: **전건 유지**

v1 §2의 ①~⑮ 전건 재확인. 근거를 재판정하지 않고 **발화 여부만** 본다.

| # | 미채택 항목 | 재심 결과 |
|---|---|---|
| ①②③ | 8단 선형 역할 · 학부모 역할 승격 · `SYSTEM_ADMIN` 신설 | 유지. `access_matrix.json`의 `roles` 축이 teacher·parent를 `planned`+`role_enum_value: null`로 두어 **선형 서열 비전제를 기계가 검사**한다(근거 강화) |
| ④⑤⑥⑦ | 메뉴 접근 권한 · 보고서 조회 권한 · 런타임 설정 편집 · API 키 | 유지. `cost_report`·`cost_probe` HTTP 미노출 재현, `config.py` env 단일 진실원천 무변경 |
| ⑧⑨⑩ | 권한 상속 · 임시 권한(TTL) · 다중 조직 권한 | 유지. 조직 엔티티 0(§5) |
| ⑪ | 시간표·성적·출석 연동(NEIS 등) | 유지. 미도달 |
| ⑫ | **학교 성취도 분석·학급 비교·교사 활동 분석** | 유지 — **근거 강화**. v1은 `pipa_data_matrix.md` #8(또래 비교)의 산문 근거만 들었으나, 이제 `access_matrix.json`이 `content_admin`을 **9항목 전부 `none`** 으로 못박아 "기관 단위로 게임화 금기를 우회"하는 경로가 **코드 차원에서** 막혔다 |
| ⑬ | 로그인/로그아웃·계정 생성 감사 | 유지. `AuditEventKind` 3값 무변경 |
| ⑭ | 감사 보고서 자동 생성 | 유지 |
| ⑮ | 이상 행위 탐지 | 유지 |

**신규 미채택 없음.** 틀의 91개 항목 중 이번 재점검이 새로 거절한 것은 0건이다.

---

## §3. 최대 갭 — 운영 플랫폼 3태스크의 **4자 분기**

### ①-a 실측표

| 태스크 | main 대장 | main 코드 | 브랜치 상태 | 실제 판정 |
|---|---|---|---|---|
| `ADMIN-01` | `todo` | **부재** | `claude/admin-01-…` = **done**(`8924a2e2` 815줄·`53a06c4f` YAML 전이) | **고립** — 회수 필요 |
| `ADMIN-02` | `todo` | 4컬럼 잔존 | `claude/admin-02-…` = **blocked**(정확한 판정) / `…mvp-plan-architecture-trjg5x` = **done**(`b3a58b02` 4컬럼 전량 드롭) | **판정 분기** |
| `ADMIN-03` | `todo` | **착지**(`7dbf40c5`/#716) | `…trjg5x` = **done**(`53c1d7b2` 36줄) | **대장만 stale + 중복 구현 발생** |

브랜치 실측(추론 아님 — `git show`·`git merge-base --is-ancestor`로 직접 확인):

| 커밋 | 브랜치 | main 조상? | 내용 |
|---|---|---|---|
| `8924a2e2` | `admin-01` | **NO** | `ops/role_grant_cli.py` 231줄 + `role_change` enum + `record_role_change_audit` + 테스트 20건 |
| `d42fbd40` | `admin-02` | **NO** | 코드 0줄 — `status: todo→blocked` + 차단 사유만 |
| `b3a58b02` | `trjg5x` | **NO** | `user_profile` 4컬럼 드롭 + alembic `d8559726a87a` |
| `53c1d7b2` | `trjg5x` | **NO** | ADMIN-03 재구현 36줄 |
| **`7dbf40c5`** | (병합됨) | **YES** | ADMIN-03 정본 148줄 + 전용 테스트 파일 |

세 브랜치 모두 **열린 PR 없음**, main 대비 **50커밋 뒤쳐짐**.

### ①-b 이 분기가 지금 내고 있는 실피해 4건

*(“머지 대기 중”과 “피해 발생 중”을 가르는 지점 — `problem_bank_gap_review_r2.md` §0-① 형식)*

1. **인가 데드락 상시(9일째)** — CUD 6라우터 전건 403. **봉인이 정상 작동 중인 상태**와
   **운영자를 못 만들어 아무도 못 쓰는 상태**가 같은 상태코드를 낸다(v1 D1 원문 승계). 열쇠는
   이미 만들어졌는데 브랜치에 있다.

2. **정정된 판정을 거스른 구현이 브랜치에 존재** — `b3a58b02`(2026-08-08)가 `school_id`뿐
   아니라 `subscription_tier`/`_started_at`/`_renewed_at`까지 드롭했다. 이 커밋의 조상에는
   **정정을 담은 `c3376c42`(#698)가 이미 들어 있다.** 병합되면 ⑴ `OPS-18`(done) acceptance ④의
   유예 판정과 충돌 ⑵ `l3/escalation_defaults.py:12,40`의 자기서술이 stale ⑶ 마이그레이션 왕복
   2회 확정. **Kiki 판정 = 폐기·병합 금지**(§4 D6).

3. **같은 일을 두 번 했다** — ADMIN-03이 **같은 날(2026-08-08)** 두 곳에서 구현됐다:
   `7dbf40c5`(main, 148줄, 전용 테스트 파일 109줄) vs `53c1d7b2`(trjg5x, 36줄,
   `test_retention.py`에 7줄 혼입). 폐기량은 작지만 **2026-07-27 `OPS-07` 병렬 구현(735줄
   폐기)과 동일 기전**이다.

4. **Kiki 게이트가 브랜치와 함께 사라졌다** — `admin-02` 세션이 식별한
   *"prod DB(`whymath-pg:5433`) 비영행 확인이 샌드박스에서 불가"* 가 `backlog/gates.yaml`에
   없어 main에서 **불가시**였다. 사람 소유 선결 조건을 **태스크 `block`으로만 기록하면 브랜치와
   함께 사라진다** — 살아남으려면 `gates.yaml`에 있어야 한다.

### ①-c 왜 하네스가 못 막았는가 — 경고의 사유가 틀렸다

착수 시점 `backlog.py next` 실측:

```
⚠ 후보 제외 ADMIN-01… — 이미 완료(미머지): claude/admin-01-operator-seat-grant-audit   ← 맞음
⚠ 후보 제외 ADMIN-02… — 이미 완료(미머지): claude/whymath-mvp-plan-architecture-trjg5x  ← 틀림(실제로는 blocked 판정)
⚠ 후보 제외 ADMIN-03… — 이미 완료(미머지): claude/whymath-mvp-plan-architecture-trjg5x  ← 틀림(미머지가 아니라 **병합됨**)
```

`next`는 **브랜치 YAML의 `done`만** 본다. 그래서 ⑴ *잘못된 구현*의 `done`과 *올바른 구현*의
`done`을 구분하지 못하고 ⑵ **이미 트렁크에 착지한 작업**을 "미머지"로 오분류한다. 후자는
`solution_module_gap_review_r3.md`가 명명한 고립(*"코드도 done도 브랜치에"*)의 **역방향** —
**코드는 트렁크에, `done`만 브랜치에** 있는 형태다. PR #716이 3파일(코드·문서·테스트)만
스쿼시하고 `backlog/tasks/*.yaml`·`events.ndjson`을 빠뜨린 것이 원인이다.

---

## §4. 진짜 갭 설계 (D5~D8 — v1의 D1~D4에 연속)

### D5 — `ADMIN-01` 고립분 회수 (**최우선**)

**문제**: §3 ①-a·정정 ③. D1의 유일한 실물 구현이 `8924a2e2`에 6일째 고립.

**왜 신규 태스크인가(판정 정정)**: `operations_module_gap_review_r3.md` §6이 **같은 고립을
이미 발견**하고 *"필요한 것은 새 태스크가 아니라 회수 실행이고, `ADMIN-01`이 이미 그 좌석"*
이라며 **권고만** 남겼다. 그리고 아무도 실행하지 않았다. r2가 같은 권고를 반복하면 3번째
권고이고, CLAUDE.md 실수 관리 규약이 금지하는 *"다음엔 조심한다"* 와 같아진다.

`SOL-01` 선례가 답을 준다 — **회수는 원 태스크와 acceptance가 다르다**(드리프트 흡수·증적
재수행·충돌 해소는 원 acceptance에 없다). 따라서 별도 좌석으로 분리한다. r3 §6의 "좌석 이미
있음" 판정을 **이 근거로 정정**한다.

**정합 설계**(신규 설계 0 — 이식만):
1. 대상 = `8924a2e2`의 5파일. **merge가 아니라 이식(re-port)** — 브랜치가 50커밋 뒤쳐졌다.
2. `53a06c4f`(YAML `done` 전이)는 **이식하지 않는다** — 대장 전이는 이식 대상이 아니라
   이 태스크의 *산출*이다(§3 ①-c가 지적한 형태의 재발 방지).
3. `schema/enums.py` 드리프트 흡수 — main에서 enum 추가가 잦은 파일이다(#752·#768 등).
   `admin_access`의 "현재 호출부 0곳" 자인 문구가 `role_change` 추가로 stale이 되지 않는지 확인.
4. **원 커밋 증적 승계 금지** — 전체 스위트 재수행.

**변별력**: 부여 전 403 → 부여 후 200/201 → 회수 후 다시 403의 **3상태 왕복**을 이식 후 main
코드에서 재실측. 같은 값이면 이식이 실패한 것이다.

→ **`ADMIN-08-operator-seat-grant-recovery`**(S4 · priority **1**)

### D6 — `ADMIN-02` 스코프 3분할 확정 + Kiki 게이트 가시화

**문제**: 현 acceptance ②가 *"드롭 마이그레이션 작성"* 으로 **4컬럼 일괄 드롭을 지시**하고
있고, `trjg5x` 세션이 정확히 그대로 집행했다. 정정(§독립검증 ②)은 **문서에만** 있었다.

**정정된 3분할**:

| # | 대상 | 처분 | 근거 |
|---|---|---|---|
| (a) | `school_id`(`db/models/user.py:93`) | **드롭 후보 유지** | FK 없는 고아 컬럼. 런타임 read/write 0(히트는 스키마 미러 `schema/user.py:145`·마이그레이션·테스트 3곳뿐). D4가 `organization`으로 school을 흡수하므로 **테넌시 착지 시에도 재사용되지 않는다** — 재도입 비용 0의 근거가 D4에서 나온다 |
| (b) | `subscription_tier`/`_started_at`/`_renewed_at`(`:142-146`) | **드롭 금지 — 예약 좌석 명문화** | dead가 아니다. `l3/escalation_defaults.py:12,40`이 *"실 `subscription_tier` DB 읽기·결제 연동은 이 함수의 내부만 바뀌면 된다"* 로 **미래 소비처를 자기선언**했고, `OPS-18`(done) acceptance ④가 *"결제 도입 결정 이후"* 로 **유예를 이미 판정**했으며, 결제는 `ROADMAP.md:119,153` Phase 2 M2.3로 **일정이 잡혀** 있다. 처분 = 자인 주석 + `escalation_defaults` 링크 + **"런타임 reader 0" 동결 테스트**(몰래 읽기가 생기면 실패) |
| (c) | **`school_region`(`:92`)·`gender`(`:87`)** — **r2 신규 발견** | **D7 선행 후 판정** | 같은 기준을 적용하면 이 둘도 런타임 소비 0이다. **게다가 API 수집 경로도 0**이다(`api/` 전수 grep 무일치). 그런데 이 둘은 dead code 축이 아니라 **데이터 최소화 축**(의사결정 우선순위 **2** 법적·윤리적 준수)이다 — 처분 근거는 §4 D7의 대장이 있어야 성립한다 |

> **경계(v1 승계)**: `school_type`·`grade`는 **실 소비처가 있다** — `l2/target_progress.py:92,95`
> (성취기준 스코프 필터) · `l2/learner_state.py:187`·`api/coach.py:898`(PED-05 프롬프트 개인화).
> 유지한다. `db/models/user.py:179` `idx_user_school`도 이 살아있는 두 컬럼만 인덱싱한다.

**처리(대장 정정 — 실행 완료)**: `ADMIN-02`를 `block --reason`으로 전환했다.
- `cancel` + 재등재를 쓰지 **않은** 이유: 태스크 ID 계보를 끊는다(D8이 지적한 문제를 스스로 저지르게 된다).
- `HARN-20`이 고친 notes **append** 덕에 정정 스코프가 원 notes를 지우지 않고 쌓인다 —
  실측 확인: 원문의 "SEC-07이 좌석 없는 역할 3종은…"·"반복 실수 8회차" 문구 **보존됨**.
- `blocked`는 **잘못된 착수를 실제로 막는다**(`next` 후보에서 제외됨 — 실측 확인).
- acceptance 본문 정정은 **불가**(D8) → notes에 *"착수 세션은 이 notes를 acceptance ②에
  우선한다"* 를 명시.

**게이트 신설(실행 완료)**: `G-prod-dead-column-check`(kiki/human · remind 7일) — prod DB
비영행 확인. §3 ①-b-4가 지적한 "브랜치와 함께 사라지는 게이트"를 `gates.yaml`로 영속화.

### D7 — 프로필 수집 항목 대장 부재 (**v1이 보지 않은 평면 · PIPA 축**)

**문제**: `data/access_matrix.json`(COLLAB-01)은 **학습 데이터 9항목의 노출 해상도**만
계약한다. `user_profile`의 **수집 항목**(어떤 개인정보를 왜 받는가)은 어느 대장에도 없다.

실측:

| 컬럼 | ORM·스키마 | API 수집 경로 | 런타임 소비 | `pipa_data_matrix` | `access_matrix.json` |
|---|---|---|---|---|---|
| `gender` | `user.py:87`(`sa.String(32)`)·`schema/user.py:126` | **0** | **0** | **미등재** | **미등재** |
| `school_region` | `user.py:92`·`schema/user.py:139` | **0** | **0** | **미등재** | **미등재** |
| `school_id` | `user.py:93`·`schema/user.py:145` | **0** | **0** | **미등재** | **미등재** |

**왜 갭인가 — dead code보다 상위 축이다**: `pipa_data_matrix.md` §3.2가
*"동의 시 수집 항목·이용 목적·보유 기간·제3자 제공 여부를 명확히 고지(PIPA 고지 의무)"* 를
명령하는데, **그 수집 항목 목록의 진실 원천이 없다**. §1의 *"데이터 최소 수집: 학습 코칭에
불필요한 데이터는 수집하지 않는다"* 는 원칙도 **기계로 검증되지 않는다**. 그리고
`MGMT-02`(이용약관·처리방침 문안·blocked)가 회신될 때 **참조할 대장이 없다**.

`pipa_data_matrix.md` §2.4는 *"새 데이터 항목 추가 시 반드시 이 매트릭스에 행을 추가하고
변호사 검토를 거친다"* 고 명령하지만, 그 매트릭스의 축은 **학습 데이터 9항목**이라 프로필
속성은 애초 대상이 아니다 — 누락이 아니라 **범위 밖으로 취급된 채 한 번도 재검토되지 않은 것**
(v1 D3이 감사 테이블에서 발견한 것과 **같은 형태**가 프로필 평면에서 재발했다).

**정합 설계**(신규 테이블 0 · 신규 컬럼 0 · 수집 시작 0):
1. `data/collection_inventory.json` — `user_profile` 전 컬럼 × {수집 여부 · 수집 경로(엔드포인트
   또는 `none`) · 목적 · 런타임 소비처 · 보존 계획 · PII 등급}. **값을 날조하지 않는다**:
   소비처가 없으면 `none`으로 적고 그것이 정직한 상태다.
2. 거버넌스 테스트 — ORM `UserProfile` 컬럼 집합 ↔ 대장 키 집합 **동기 강제**
   (`test_access_matrix.py` 패턴 답습). 신규 컬럼이 대장 없이 추가되면 실패, 대장에만 있는
   유령 항목도 실패.
3. **법령 판단은 하지 않는다** — 목적·법적 근거 문구의 법률적 확정은 `MGMT-02` 소관
   (CLAUDE.md "법령 유래 절차의 기계 대체 금지"). 이번 범위는 **기계 대장 + 동기 강제**까지.

**dead code 금지 충족**: 신규 런타임 코드 0(데이터 파일 + 테스트). **변별력**: 컬럼을 하나
추가하거나 대장에서 하나 제거했을 때 테스트가 실제로 실패하는지 **양방향** 확인.

→ **`ADMIN-09-profile-collection-inventory-contract`**(S4 · priority 2)

### D8 — 태스크 판정 정정의 CLI 경로 부재 (**v1 §독립검증 ③이 예견 → 실피해로 발화**)

**문제**: `HARN-20`(done)이 `review`/`cancel` 상태와 `block --reason`의 notes **append** 보존은
만들었으나, **acceptance를 고치는 verb는 여전히 0**이다. 실측 — `backlog.py`의 `cmd_`
서브커맨드 전수 **18개**: `status`·`next`·`start`·`done`·`block`·`unblock`·`review`·`cancel`·
`gates`·`add`·`validate`·`brief`·`check-stop`·`check-edit`·`claims`·`overlap`·`policy`·`seed`.

**v1 §독립검증 ③은 이 공백을 정확히 예견했다**:

> *"완료 전 태스크의 판정이 바뀌었을 때 그것을 대장에 반영할 정규 경로가 없다. 이번에는
> '문서가 소유자'라는 우회가 성립했으나, 문서 소유자가 없는 태스크에서 같은 일이 생기면
> 손편집 유혹이 생긴다. **지금 등재하지 않는 이유는 실사례가 1건(그것도 우회 성립)뿐이라
> 설계 근거가 얇기 때문이다.**"*

**2번째 사례가 발생했고, 이번엔 우회가 실패했다.** `trjg5x` 세션은 정정 문서를 읽지 않고
YAML acceptance를 그대로 집행해 `subscription_*` 3컬럼까지 드롭했다(`b3a58b02`).

**일반형(남길 원칙)**:
> **"문서가 소유자"라는 우회는 착수 세션이 그 문서를 읽을 때만 성립한다. 태스크 YAML은
> 반드시 읽히지만, 참조 문서는 선택이다. 따라서 판정 정정은 문서가 아니라 대장에 착지해야 한다.**

부수 실측 — **게이트 부착 경로도 없다**: `requires_gates`는 `add` 시점 외에 붙일 방법이 없어,
이번에 신설한 `G-prod-dead-column-check`를 `ADMIN-02`에 **부착하지 못했다**(notes에 문자열로만
적었다). 같은 verb가 이 축도 함께 열어야 한다.

**정합 설계**: `backlog.py amend <id> --append-acceptance "…" [--gate <id>]`
- 기존 acceptance를 **파괴하지 않고** 정정 항을 append(HARN-20 notes 교훈 승계)
- `events.ndjson`에 `amend` 액션 + 사유 기록
- **범위 밖**: 태스크 삭제·ID 변경·acceptance 개별 항목 제거는 열지 않는다(대장 손편집 우회
  표면이 된다). `cancel`+재등재를 정본 경로로 승격하지도 않는다 — 계보를 끊는다.

**변별력 필수**: 정정 전/후 YAML을 착수 세션이 실제로 다르게 읽는지. amend 후 acceptance
목록에 정정 항이 나타나고 되돌리면 사라져야 한다.

→ **`HARN-24-task-acceptance-amend-cli`**(S4 · priority 2 · layer infra)

---

## §5. D4(조직·학교·라이선스 테넌시) 재확인 — **페이퍼 유지 · 신규 태스크 0**

ORM **64테이블 전수** `organization`/`tenant`/`class_group`/`classroom`/`license`/`seat`
**무일치** 재현. 실재하는 것은 컬럼 3종(`school_type`·`school_region`·`school_id`)뿐이다.

**혼동 주의(r2 부기)**: `atom_node.py:96`·`atom_probe.py:70`·`misconception_catalog.py:94`의
`school_level`과 `achievement_standard.py:73`의 `school_type`은 **학교급(초/중/고) 필터·교육과정
메타**이지 조직 축이 아니다. grep에서 함께 잡히므로 미래 세션이 "부분 구현"으로 오독하기 쉽다.

v1 D4의 목표 스케치(3엔티티 — 조직이 학교를 흡수)·인가 설계(2차원 매트릭스에 스코프 축만
추가·선형 서열 재도입 금지)·§2-⑫ 대체 방향(순위 아닌 개념 커버리지)·라이선스는
`subscription_tier` 부활이 아님 — **전건 승계, 재설계 없음**.

발화조건 §5-③(**B2B 계약 1건 체결**·Phase 4) **미도달** → 지금 태스크를 만들면 dead task다.

---

## §6. 정직한 공백 — 지금 하지 않는 것 (v1 §4 7종 승계 + 델타)

1. **학교/교육청/학원 관리자 좌석** — 승계(조직 엔티티 0·§5)
2. **AI 기능 세분화 권한** — 승계. `POST /v1/generate`는 인증만 요구(`CurrentUser`)
3. **2차원 RBAC 매트릭스의 코드화** — **부분 해소**(§1 정정 ②): 계약은 `access_matrix.json` +
   거버넌스 테스트로 기계 강제됐다. **남은 것은 응답 필터링 소비 좌석 0** — 교사·부모 축이
   열릴 때(§7-②) 첫 구현체가 필요해진다
4. **조직·학교·반 테넌시** — 승계(D4 페이퍼·§5)
5. **좌석·사용률 대시보드** — 승계
6. **로그인/로그아웃·계정 생성 감사** — 승계(§2-⑬)
7. **콘텐츠 CUD 감사(변경 이력)** — 승계. `ADMIN-08` 착지 후 CUD에 실 트래픽이 생기면 §7-② 재심
8. **(r2 신규) `gender`·`school_region` 처분 실행** — D7 대장이 선행돼야 근거를 갖는다.
   지금 드롭하면 "왜 지웠는가"의 기록이 D2와 같은 형태로 다시 비어 있게 된다
9. **(r2 신규) 감사 보존 *연한 숫자*** — `ADMIN-03`이 상환한 것은 "침묵"이지 "연한"이 아니다.
   `MGMT-02` 회신 선행(§7-④ 승계)

---

## §7. 유보 항목의 발화 조건 — v1 §5 6건 재심

| # | 유보 항목 | 발화 트리거 | r2 재심 |
|---|---|---|---|
| ① | 관리자 HTTP API·콘솔 UI·`SYSTEM_ADMIN` | `CONTENT_ADMIN` 좌석 **실발급 1명 이상** + CLI 조작 빈도 실측 | **미발화** — 좌석 발급 자체가 `ADMIN-08` 대기. 유지 |
| ② | 콘텐츠 CUD 감사 · 2차원 매트릭스 **소비 좌석** | 좌석 실발급 + 콘솔 Phase B | **미발화**. 단 ②의 절반(계약)은 `COLLAB-01`로 착지 — 트리거는 이제 *"계약을 소비하는 응답이 필요해질 때"* 로 좁혀진다 |
| ③ | 조직·학교·반 테넌시(D4) | **B2B 계약 1건 체결**(Phase 4) | **미발화**. 유지 |
| ④ | 감사 보존 연한 확정·자동 파기 | `MGMT-02` 회신 **+** 감사 행수 증가 추세 | **미발화**(`MGMT-02` blocked). `ADMIN-03` 착지로 *"연한 미확정"* 이 코드·문서에 명문화돼 이 트리거가 **가시화**됨 |
| ⑤ | 라이선스·좌석·엔타이틀먼트 | 결제 시스템 착지(Phase 2 M2.3) | **미발화**. D6-(b)의 예약 좌석 판정 근거 |
| ⑥ | 관리자 MFA·IP 허용목록·재인증 | 관리자 계정 실발급 시 동시 발화 | **미발화** — `ADMIN-08`과 동시 발화 예정. 재판정하지 않는다 |
| **⑦** | **(r2 신규) 프로필 컬럼 드롭 실행** | `ADMIN-09` 대장 착지 **+** `G-prod-dead-column-check` 통과 | 둘 중 하나만으로는 처분 근거가 서지 않는다 |

---

## §8. 반복 실수 — **11회차** (새로운 축 · 재발방지 등재)

프로젝트 전역 카운터는 **10회차**(`operations_module_gap_review_r3.md` §7)까지 갔다. 이어받는다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1~8 | CI 배선·적재·배포·입력·켜기·공급원·인가 통로·스키마 읽기 | 만들고 **X하지 않음** |
| 9 | `ordering_basis`가 영속·렌더 경계에서 소실(`learning_path` r2) | 만들고 켰는데 **경계에서 흘림** |
| 10 | 런북 3종의 자인 공백 25종 무추적(`operations_module` r3) | **자기 문서가 자인한 공백을 판정이 읽지 않음** |
| **11** | 병합된 정정(`c3376c42`)이 acceptance에 도달하지 못해, 정정 전 지시가 그대로 집행됨(`b3a58b02`) | **정정 자체가 도달 실패** |

**왜 새로운 축인가**: 1~8은 *공급·입력·인가*가 끊긴 사례, 9는 *경계 통과*, 10은 *판정의 독해
범위*다. 11은 셋 다 아니다 — **정보는 정확했고, 병합됐고, 착수 세션의 조상에 들어 있었다.
그런데 그 세션이 읽는 자리(태스크 YAML)에 없었다.** 정확한 정보가 잘못된 매체에 있으면
없는 것과 같다.

**재발방지 대책 3형**(CLAUDE.md 규약 — "다음엔 조심한다"는 대책이 아니다):

| 형태 | 대책 |
|---|---|
| **코드** | `HARN-24` — `amend` verb로 정정이 대장에 착지하는 경로를 연다 |
| **게이트** | `G-prod-dead-column-check` — 사람 소유 선결 조건을 `gates.yaml`로 영속화(태스크 `block`은 브랜치와 함께 사라진다) |
| **태스크** | `ADMIN-08`(회수 실행) · `ADMIN-02` blocked 전환(잘못된 착수 차단) |

**CLAUDE.md 등재 후보(이번 커밋에서 헌법은 고치지 않는다)**:
> *"판정을 정정했으면 그 정정이 **집행자가 읽는 자리**에 착지했는지 확인한다. 설계 문서는
> 근거를 담고 태스크 대장은 지시를 담는다 — 근거만 고치고 지시를 그대로 두면, 다음 세션은
> 정정 전 지시를 집행한다."*

헌법 개정은 별도 판단이므로 제안만 한다(`learning_path_module_gap_review_r2.md` §9 선례).

**부수 관측 ⓐ(중복 등재 없음)**: 미머지 브랜치 `claude/whymath-account-security-dw9lww`가 지적한
`remote_claims.py:1274` `_DOC_SERIES_SUFFIX='_review.md'` 사각에 **이 문서 자신이 해당**한다 —
`..._r2.md`는 중복 탐지 브리핑에 뜨지 않는다. 즉 **이 시리즈의 모든 r2/r3 문서가 구조적으로
비가시**다. 그 브랜치가 이미 좌석을 들고 있으므로 **근거 사례로만 부기**하고 등재하지 않는다.

> ⚠️ **좌석은 번호가 아니라 브랜치로 지목한다** — 그 브랜치가 이 태스크에 붙인 번호(`HARN-22`)는
> main의 **`HARN-22-id-number-suggestion-race`와 이중 배정 상태**다(슬러그가 달라 `validate`는
> 통과한다). 따라서 이 문서는 접미어 사각 좌석을 **번호로 인용하지 않는다** — 번호로 쓰면
> 머지 후 틀린 참조가 된다.

**부수 관측 ⓑ — 이 문서를 쓰는 동안 그 사고가 재발했다**: main의 `HARN-22-id-number-suggestion-race`
("번호 가드의 예약 부재 — 두 세션에 같은 빈 번호를 동시 제안")가 예측한 경합이 **이 문서의
등재 과정에서 실제로 발생**했다 — 병렬 세션이 `ADMIN-08`을 같은 ID·같은 슬러그·같은 목적으로
동시 등재했다(§9 말미). **회차를 새로 만들지 않는다** — 이미 그 태스크가 좌석이고, 이 건은
그 태스크의 실사례 증거로 기록한다.

---

## §정정 — stale 정본 3곳 (이번 대조에서 실측 발견 · 원본 1줄 정정)

| 위치 | 착수 시 표기 | 실측·조치 |
|---|---|---|
| `docs/design/ui/03_admin_console_plan.md` §2 관리 자원 인벤토리 | "`api/concepts.py`·`api/problems.py`(CRUD 존재·**무인증** ⚠️)" | **v1 §정정이 "이미 정정 완료"로 판정했으나 §2 인벤토리 표는 미수정이었다** — `99dfc3a`가 고친 것은 §7 부기뿐이다. 즉 **v1의 §정정 판정 자체가 부분 오류**였다. 이번에 1줄 정정 |
| `docs/architecture/account_security_gap_review.md` §4-⑦ | "Admin BFF·콘솔 UI·역할 관리 화면 — `04_admin_console_architecture.md` §8 승계" | v1 §정정이 *"후속 세션이 이 표를 근거로 1줄 정정"* 을 요청했으나 **8일째 미반영**. 우리가 그 후속 세션이다 → "CLI 경로가 화면보다 먼저" 1줄 부기 |
| `backlog/tasks/ADMIN-03-…yaml` | `status: todo` · `artifacts: []` · `updated: 2026-08-03` | 코드는 main 착지(#716·`7dbf40c5`). **PR이 코드만 스쿼시하고 backlog 전이를 빠뜨린 형태** → `done --artifact 7dbf40c5`로 정정(실행 완료) |

**정정 원칙**: v1 본문(`operations_platform_gap_review.md`)은 **한 글자도 고치지 않았다** —
헤더에 r2 포인터 배너 1줄만 추가했다.

---

## §9. 등재 요약

### 신규 태스크 3건 (전건 `backlog.py add` CLI 경유 — 번호 추론 금지·HARN-10/15)

| 태스크 | 설계 | stage | prio | layer | 근거 |
|---|---|---|---|---|---|
| `ADMIN-08-operator-seat-grant-recovery` | D5 | S4 | **1** | backend | 고립 815줄 이식 — 회수는 3번째 권고가 아니라 **좌석**이어야 한다. ⚠️ **병렬 세션과 ID 충돌**(아래 ⓒ) |
| `ADMIN-09-profile-collection-inventory-contract` | D7 | S4 | 2 | backend | 수집 항목 대장 + ORM↔대장 동기 게이트 |
| `HARN-24-task-acceptance-amend-cli` | D8 | S4 | 2 | infra | 정정 도달 경로 — 11회차 재발방지의 코드 축 |

**번호 가드 실동작**: 최초 `ADMIN-04` 등재 시도를 CLI가 **거부** — 원격 브랜치
`claude/whymath-webpage-plan-8pma1f`의 인플라이트 `ADMIN-04-module-registry`가 선점하고 있었다.
CLI 제안대로 `ADMIN-08`을 수용했다. **로컬 백로그만 봤다면 비어 보였을 번호**이므로 눈으로
골랐다면 중복이 났다(HARN-15가 막아낸 실사례 — v1 시리즈에서 반복 확인되는 패턴).

**ⓒ 그런데 그 제안 번호에서 충돌이 났다 — `ADMIN-08` 이중 등재(미해소·병합 순서에 위임)**

| | 이 문서(브랜치 `claude/whymath-operations-platform-i5iu61`) | 병렬 세션(브랜치 `claude/unresolved-long-term-branches-ph1ad7`·`9d002a1a`) |
|---|---|---|
| 파일 | `backlog/tasks/ADMIN-08-operator-seat-grant-recovery.yaml` | **완전 동일 경로** |
| 목적 | `ADMIN-01` 고립분(`8924a2e2`) 회수 | **동일** |
| `ADMIN-02` 처분 | `blocked` + 3분할 정정 | **같은 판정에 독립 도달** |
| 병합 상태 | 미머지 | 미머지(main 대비 3커밋) |

**이것은 판정 충돌이 아니라 수렴이다** — 두 세션이 같은 근거(`admin-02` 브랜치 `d42fbd40`)에서
같은 결론에 독립 도달했으므로 서로가 서로의 교차검증이다. 다만 **같은 번호를 동시에 받았다**:
`backlog.py add`의 번호 가드는 *이미 쓰인* 번호는 막지만 **자신이 방금 제안한 번호를 예약하지
않는다**. 이것이 정확히 main `HARN-22-id-number-suggestion-race`가 등재한 결함이며,
**그 태스크가 머지되기도 전에 재발**했다(§8 ⓑ).

**해소 규칙(둘 다 미머지이므로 순서에 위임)**: 나중에 머지되는 쪽은 **새 번호를 만들지 않고
흡수**한다 — add/add 충돌이 나면 양쪽 acceptance를 **합쳐 한 파일로** 만들고 중복 좌석을
만들지 않는다(`PB-01` 편집자 부기 선례). 회수 대상 커밋(`8924a2e2`)이 하나뿐이므로 좌석도
하나여야 한다.

> 부기: 착수 시점에 `ADMIN-01`은 **또 다른 세션**(`claude/whymath-eos-review-64f81f`)이
> claim 중이었다. 회수 실행 전에 그 세션의 산출을 먼저 확인한다 — 3중 착수 위험.

### 기존 태스크 처분 2건 (신규 등재 없음)

| 태스크 | 처분 | 사유 |
|---|---|---|
| `ADMIN-02-dead-tenancy-billing-columns` | `todo` → **`blocked`** | 정정 3분할 스코프 + `G-prod-dead-column-check` 선결 + `trjg5x` 폐기 권고를 notes에 **append**(원문 보존 실측). `cancel`+재등재를 쓰지 않은 이유 = ID 계보 보존 |
| `ADMIN-03-audit-retention-policy` | `todo` → **`done`**(`7dbf40c5`) | 코드가 main에 착지했는데 대장만 stale. `start --ignore-remote-claim` → `done` 경유(사유: `trjg5x`의 중복 done은 폐기 대상 — CLI가 명시한 예외 조건에 해당) |

### 게이트 1건

| 게이트 | kind | 내용 |
|---|---|---|
| `G-prod-dead-column-check` | human/kiki (remind 7일) | prod DB(`whymath-pg:5433`) `user_profile` 미소비 컬럼 비영행 확인 — `ADMIN-02` acceptance ① 선결 |

### 중복 등재 금지 대장

| 주제 | 기존 추적 |
|---|---|
| 운영자 좌석 발급 자체 | `ADMIN-01`(회수 대상 — `ADMIN-08`이 실행) |
| 컬럼 처분 | `ADMIN-02`(blocked 유지 — 신규 태스크 아님) |
| 감사 보존 명문화 | `ADMIN-03`(**완료**) / 연한 숫자 = `MGMT-02` |
| 문서 접미어 탐지 사각 | 미머지 브랜치 `claude/whymath-account-security-dw9lww`(§8 ⓐ — **번호 인용 금지**: 그 번호는 main `HARN-22`와 이중 배정) |
| 번호 가드 예약 부재 | `HARN-22-id-number-suggestion-race`(main·todo — §8 ⓑ가 실사례) |
| 2차원 인가 계약 | `COLLAB-01`(done) |
| Admin BFF·콘솔 UI·모듈 레지스트리 | `04_admin_console_architecture.md` §8 (발화 전 **미등재가 의도**) · `ADMIN-04-module-registry`(타 브랜치 인플라이트) |
| 조직·라이선스 테넌시 | D4 페이퍼 — **태스크 없음** |
| 결함 신고 판독 | `RPT-02`(운영 EOS r3 소관) |

### 폐기 권고 (Kiki 판정 2026-08-11)

| 대상 | 판정 |
|---|---|
| `origin/claude/whymath-mvp-plan-architecture-trjg5x`의 `b3a58b02`(4컬럼 전량 드롭) | **폐기 · 병합 금지** — §3 ①-b-2 |
| 같은 브랜치의 `53c1d7b2`(ADMIN-03 재구현 36줄) | **폐기** — `7dbf40c5`가 정본(148줄·전용 테스트) |
| `origin/claude/harn-14-doc-series-duplicate-detection` | **폐기** — main `backlog.py:1018-1027`이 3-dot 오탐을 명시 판정, main의 `scan_doc_series_duplicates`가 정본 |
| `origin/claude/admin-02-dead-tenancy-billing-columns` | 코드 0줄 — 판정 내용은 본 문서 §4 D6이 흡수했으므로 **정리 대상** |

---

## 부록 — 실측 근거 (2026-08-11 확인 · 재현 명령 그대로)

| 주장 | 확인 명령·위치 |
|---|---|
| `CONTENT_ADMIN` 부여 경로 0건 | `grep -rE '\.role\s*=[^=]\|role\s*=\s*Role\.' --include=*.py src/ scripts/` → 무일치 |
| `RequireContentAdmin` 6라우터 | `api/concepts.py:244/342/391` · `api/problems.py:57/184/231` |
| `AuditEventKind` 3값·`role_change` 0건 | `schema/enums.py:1138`(`:1151`/`:1154`/`:1157`) · `grep -rn role_change src/ tests/` → 0 |
| `ops/`에 role CLI 없음 | `ls src/backend/whymath_backend/ops/` → 12파일, role 관련 0 |
| 4컬럼 런타임 소비 0 | `db/models/user.py:93`·`:142-146`; 히트는 `schema/user.py`·alembic·`tests/` 뿐 |
| `subscription_*` 미래 소비처 자기선언 | `l3/escalation_defaults.py:12,40` |
| `school_type`·`grade`는 살아있음 | `l2/target_progress.py:92,95` · `l2/learner_state.py:187` · `api/coach.py:898` |
| `gender`·`school_region` 수집·소비 0 | `grep -rn 'gender\|school_region' src/backend/whymath_backend/api/` → 무일치 |
| 감사 2테이블 파기 계획 미포함 | `privacy/retention.py:66-84`(11모델) · `privacy/erasure.py:92-111`(18모델) — 둘 다 무일치 |
| ADMIN-03 동결 테스트가 **돈다** | `python3 -m pytest tests/backend/privacy/test_audit_retention_exclusion.py` → **5 passed, EXIT=0** |
| 조직 엔티티 0 | ORM 64테이블 `__tablename__` 전수 — `organization`/`tenant`/`class_group`/`license`/`seat` 무일치 |
| `7dbf40c5`만 main 조상 | `git merge-base --is-ancestor <sha> origin/main` — `7dbf40c5`=YES · `8924a2e2`/`b3a58b02`/`53c1d7b2`/`d42fbd40`=NO |
| PR #716이 3파일만 스쿼시 | `git show --stat 7dbf40c5` → `security_privacy.md`·`retention.py`·`test_audit_retention_exclusion.py` (backlog 미포함) |
| `cmd_` 서브커맨드 18개·amend 없음 | `grep -n '^def cmd_' scripts/harness/backlog.py` |
| 대장 정정 변별력 | `next` 출력 diff — ADMIN-02·03 "이미 완료(미머지)" 2줄 **사라짐**, ADMIN-01만 잔존 |
| 등재 후 무결성 | `backlog.py validate` → 태스크 **258**건 · 게이트 **11**건 · **EXIT=0** |

---

**버전**: 1.0 | **작성**: 2026-08-11 (r2 · 델타 재점검) | **모체**: `operations_platform_gap_review.md`(v1 2026-08-03 + §독립검증 2026-08-04)
**교차링크**: `operations_module_gap_review_r3.md` §6(판정 정정 대상) · `problem_bank_gap_review_r2.md` §0-①(고립 처리 선례) · `solution_module_gap_review_r3.md` §3-①(고립 4회차) · `account_security_gap_review.md` §4-⑦(정정 대상) · `04_admin_console_architecture.md` §8
