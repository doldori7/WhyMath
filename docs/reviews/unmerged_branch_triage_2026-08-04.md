# 미머지 브랜치 분류 판단표 (2026-08-04)

> **목적**: 원격 브랜치 82개를 정리하면서, 남은 25개 각각이 ⑴ 이미 main에 흡수됐는지 ⑵ 진짜
> 미병합 작업인지 ⑶ 다른 브랜치와 중복인지를 **실측**으로 분류하고, 처분 판단의 근거를 남긴다.
> 인상 판정 금지 — 전건 blob 단위 비교(`git rev-parse origin/<b>:<file>` ↔ `origin/main:<file>`).
>
> **선행 실행**: 같은 날 41개 브랜치를 삭제했다(Kiki 로컬 실행). 손실 0 — 열린 PR 15개 head·
> `harness-claims`·계보 연결 25개 전건 생존을 삭제 후 재확인했다.
>
> **결론 3줄**: ⑴ **25개 전부 진짜 미병합**이다 — 완전 흡수된 브랜치는 0개다(부분 흡수는 4개).
> ⑵ 진짜 위험은 방치가 아니라 **태스크 ID 이중 배정 13건**이다 — 슬러그가 달라 `validate`는
> 통과하므로 번호 참조만 조용히 결정 불가가 된다. ⑶ 이 문서를 쓰는 세션 자신이 그 결함에
> 걸렸다(§4) — 가드가 보는 표면과 실제 위험 표면이 다르다는 증거.

---

## §0. 분류 방법과 그 한계

### 쓴 지표

| 지표 | 계산 | 왜 |
|---|---|---|
| **실질 델타** | 브랜치가 건드린 파일 중 blob이 main과 **다른** 개수. `MEMORY.md`·`backlog/events.ndjson` 제외 | 이 둘은 append-only 원장이라 **항상** 다르다 — 포함하면 모든 브랜치가 "미병합"으로 보여 변별력이 0이 된다 |
| **부분 흡수** | 건드린 파일 중 blob이 main과 **같은** 개수 | 그 브랜치 작업의 일부가 이미 다른 경로로 main에 들어갔다는 뜻 |

### 폐기한 지표 (기록 — 같은 실수 방지)

첫 시도는 "브랜치가 추가한 파일이 main에 **존재하는가**"로 흡수를 판정했다. **틀렸다** —
파일명이 같아도 내용이 다르면 흡수가 아니다. 이 지표로는 `collaboration-design-ur7l4v`가
"완전 흡수"로 나왔으나, blob 비교에서는 실질 델타 2개가 남아 있었다. **존재 ≠ 동일**.

### 이 분류가 보지 못하는 것

- **의미 중복**: 파일 경로가 달라도 같은 내용을 다시 쓴 경우는 기계적으로 안 잡힌다. §3의
  중복 쌍은 *같은 파일 경로*를 만드는 브랜치만 검출한 것이다.
- **처분 판정**: 이 문서는 "무엇이 남아 있는가"까지다. 병합할지 폐기할지는 각 브랜치의
  내용을 읽어야 하는 판단이며 Kiki 소유다.

---

## §1. 판단표 — 25개 전건

`실질` = 실질 델타 · `문서`/`코드`/`태스크` = 그 내부 분해 · `PR` = 열린 PR 존재 여부 ·
`흡수` = 이미 main과 같아진 파일 수.

| # | 브랜치 | 일 | 실질 | 문서 | 코드 | 태스크 | 흡수 | PR | 성격 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `education-os-architecture-mr0fbq` | 5 | **44** | 9 | 29 | 6 | 2 | - | 코드 대량 + persona_fit 감사 데이터 |
| 2 | `whymath-problem-bank-design-65tsm4` | 5 | **36** | 2 | 29 | 5 | **32** | - | **절반 이상 흡수됨** · identity_id 마이그레이션 잔존 |
| 3 | `whymath-visualization-review-zl2v1b` | 4 | **36** | 4 | 28 | 3 | 0 | - | 프롬프트 4종 + 개념평가 인덱스 |
| 4 | `whymath-ai-tutor-design-iu9qk5` | 1 | **27** | 2 | 24 | 1 | 0 | - | PED-04 세션 회상·턴 메타 구현 |
| 5 | `whymath-ai-tutor-design-953m1e` | 5 | **26** | 3 | 21 | 2 | 3 | - | PED-05 · `l2/learner_state.py` |
| 6 | `s3-10-persona-fit-2xk548` | 5 | **22** | 8 | 13 | 1 | 0 | - | persona_fit 백필 |
| 7 | `s4-14-skeleton-cat-re24tk` | 4 | **16** | 0 | 15 | 1 | 0 | - | rephrase 계보 백필 |
| 8 | `whymath-learning-path-design-gvku5q` | 3 | **13** | 4 | 0 | 8 | 0 | - | 고교 유형별 학습경로 · 태스크 8건 |
| 9 | `whymath-data-platform-design-8ceaf5` | 0 | **12** | 3 | 4 | 3 | 0 | - | 데이터 플랫폼 갭 리뷰 v1 + `ops/reach_audit.py` |
| 10 | `whymath-05-problem-bank-design-bbyp3d` | 0 | **11** | 3 | 0 | 7 | 0 | - | ⚠ #11과 중복 (§3-①) |
| 11 | `whymath-05-problem-bank-r2-retry` | 0 | **10** | 3 | 0 | 6 | 0 | **#687** | ⚠ #10의 재시도판 |
| 12 | `whymath-assessment-design-jkwdzn` | 5 | **10** | 4 | 0 | 6 | 0 | - | 평가 모듈 갭 리뷰 |
| 13 | `whymath-misconception-review-h87afk` | 1 | **9** | 3 | 0 | 6 | 0 | **#667** | 오개념 갭 리뷰 + 04e 설계 |
| 14 | `whymath-ai-recommendation-review-q8tvcx` | 0 | **6** | 1 | 0 | 5 | 0 | - | 데이터 플랫폼 **r2** (브랜치명과 내용 불일치) |
| 15 | `whymath-learning-analytics-9t71oh` | 5 | **6** | 1 | 0 | 5 | 0 | - | 학습 분석 갭 리뷰 |
| 16 | `whymath-math-engine-design-4qbaru` | 0 | **6** | 1 | 0 | 5 | 0 | **#678** | 수식 엔진 갭 리뷰 |
| 17 | `whymath-nlp-design-my18a1` | 0 | **6** | 2 | 1 | 2 | 0 | **#697** | NLP r2 |
| 18 | `whymath-gamification-design-d9di3h` | 0 | **4** | 1 | 0 | 3 | 0 | - | 게임화 r2 |
| 19 | `whymath-ai-recommendation-review-tv1f08` | 0 | **4** | 1 | 0 | 3 | 0 | - | AI 추천 2차 |
| 20 | `whymath-curriculum-design-b7qav0` | 0 | **4** | 0 | 3 | 1 | 0 | - | PATH-02 학습경로 정렬 |
| 21 | `whymath-learning-analytics-abk8ea` | 0 | **3** | 2 | 0 | 1 | 0 | **#673** | PATH-04 등재 |
| 22 | `whymath-collaboration-design-ur7l4v` | 4 | **2** | 2 | 0 | 0 | **4** | - | **대부분 흡수됨**(#696 경유) |
| 23 | `whymath-eos-review-iyev91` | 0 | **2** | 0 | 0 | 2 | **4** | - | **대부분 흡수됨** · 태스크 2건만 잔존 |
| 24 | `whymath-solution-review-yvoctp` | 1 | **2** | 1 | 0 | 1 | 0 | **#668** | 풀이 2차 재검증 |
| 25 | `whymath-eos-review-euolne` | 5 | **1** | 0 | 0 | 1 | 0 | - | ARCH-22 정정 1건 |

**완전 흡수(실질 0) 브랜치는 없다.** 25개 전부 main에 없는 내용을 갖고 있다.

---

## §2. 처분 권고 — 위험도순

### A. 열린 PR 6개 (#687·#667·#678·#697·#673·#668) — **정상 경로, 조치 불요**

리뷰·머지 절차를 타고 있다. 단 **#687은 §3-①·§4 때문에 머지 전 확인 필요**.

### B. 대부분 흡수됨 2개 — **잔여만 확인 후 폐기 가능**

- `collaboration-design-ur7l4v`: 7개 중 4개가 이미 main(#696 경유). 잔여 2개는 문서.
- `eos-review-iyev91`: 8개 중 4개 흡수. 잔여는 태스크 2건.

두 브랜치 모두 **잔여가 태스크·문서 소량**이라, 그것만 새 브랜치로 옮기면 폐기해도 손실이 없다.

### C. 코드 대량 보유 5개 — **읽지 않고 폐기 금지**

`education-os-architecture-mr0fbq`(코드 29) · `problem-bank-design-65tsm4`(29) ·
`visualization-review-zl2v1b`(28) · `ai-tutor-design-iu9qk5`(24) · `ai-tutor-design-953m1e`(21).

특히 **`problem-bank-design-65tsm4`는 70개 중 32개가 이미 흡수**됐다 — 부분 병합이 진행되다
멈춘 형태다. 남은 38개가 무엇인지 확인 없이는 폐기도 병합도 위험하다.

### D. 문서·태스크만 있는 나머지 — **중복 판정 후 처분**

§3의 중복 쌍을 먼저 정리해야 판정 가능하다.

---

## §3. 중복 쌍 — 같은 파일을 만드는 브랜치

| # | 충돌 파일 | 브랜치 | 판정 |
|---|---|---|---|
| ① | `problem_bank_gap_review_r2.md` | `bbyp3d` · `r2-retry`(#687) | **`r2-retry`가 후속판**(이름의 "retry"·태스크 1건 적음·중복 등재 회피 커밋 존재). `bbyp3d`는 폐기 후보 |
| ② | `problem_bank_gap_review.md` | `bbyp3d` · `r2-retry` · `65tsm4` | v1을 셋이 각각 수정 — 병합 시 충돌 확정 |
| ③ | `ai_tutor_module_gap_review.md` | `ai-tutor-design-iu9qk5` · `learning-path-design-gvku5q` | 서로 다른 주제 브랜치가 같은 문서 수정 |
| ④ | `04a_wh1_tutoring_harness.md` | `ai-tutor-design-953m1e` · `-iu9qk5` | 같은 주제 2세대 |
| ⑤ | `02_learner_model.md` | `953m1e` · `jkwdzn` · `8ceaf5` · `gvku5q` | **4개 브랜치가 동일 문서 수정** — 최대 충돌 지점 |
| ⑥ | `06_application_modes.md` | `jkwdzn` · `gvku5q` | 2개 |

**⑤가 가장 위험하다** — 계층 정본(`02_learner_model.md`)을 4개 브랜치가 각자 고쳤다. 순서대로
병합하면 뒤쪽은 전부 충돌하고, 해결 과정에서 앞선 판정이 조용히 덮일 수 있다.

---

## §4. 태스크 ID 이중 배정 13건 — **이 정리의 최대 발견**

`backlog.py add`의 번호 충돌 가드(HARN-10)는 **로컬 백로그 + 원격 claim 대장**만 본다
(`backlog.py:718-743` `_taken_id_numbers`). 미머지 브랜치의 `backlog/tasks/`는 **구조적으로
안 보인다** — claim은 `in_progress`만 기록하므로 "등재만 되고 미착수"인 번호는 어느 경로로도
보이지 않는다.

| main | 미머지 브랜치 | 브랜치 |
|---|---|---|
| `ASM-01-assessment-seat-reachability-observability` | `ASM-01-server-side-grading` | `jkwdzn` |
| `ASM-02-grade-exposure-policy-decision` | `ASM-02-assessment-session-persist` | `jkwdzn` |
| **`HARN-14-doc-series-duplicate-detection`** | `HARN-14-gates-add-cli-path` | `bbyp3d`·`r2-retry`(#687) |
| **`HARN-15`**(등재 시도) | `HARN-15-id-collision-cross-branch-scan` | `q8tvcx` |
| `OPS-17-client-version-contract-gate` | `OPS-17-supply-demand-reach-audit` | `8ceaf5` |
| `OPS-18-cloud-escalation-reach-observability` | `OPS-18-qa-verdict-retention` | `8ceaf5` |
| `PATH-01~03` (3건) | `PATH-01/02/03` 서로 다른 슬러그 | `gvku5q` |
| `S3-13`·`S3-16` | 서로 다른 슬러그 | `65tsm4`·`8ceaf5` |
| `S4-18-review-time-axis` | `S4-18-rephrase-lineage-identity-decision` · `S4-18-standard-axis-diagnosis-rollup` | `65tsm4`·`mr0fbq` |

### 이 세션 자신이 같은 결함에 걸렸다

이 문서를 쓰는 세션은 **중복 착수 방지**를 위해 `HARN-14`를 등재했고(PR #698로 머지 완료),
이어 `HARN-15`를 등재했다. 그런데 **둘 다 미머지 브랜치의 기존 번호와 충돌**했다:

- `HARN-14-doc-series-duplicate-detection`(내 것, **이미 main**) ↔ `HARN-14-gates-add-cli-path`(#687)
- `HARN-15-branch-delete-403-runbook`(내 것) ↔ `HARN-15-id-collision-cross-branch-scan`(`q8tvcx`)

CLI는 두 번 다 **정상 통과**시켰다 — 볼 수 없는 표면이었기 때문이다. 두 번째 것은 커밋 전에
발견해 되돌리고 **`HARN-16`으로 재등재**했다(전 ref 스캔으로 빈 번호 확인). 첫 번째는 이미
머지돼 되돌릴 수 없다.

더 나아가 `q8tvcx`의 `HARN-15-id-collision-cross-branch-scan`은 **내가 발견한 것과 정확히 같은
결함을, 더 정밀한 진단(`backlog.py:718-743` 지목)과 함께 이미 등재해 둔 태스크**다. 즉 이
세션은 ⑴ 같은 결함을 중복 발견하고 ⑵ 그 결함에 스스로 걸리고 ⑶ 걸린 사실을 통해 그 결함의
실재를 증명했다.

### 처분 권고

1. **`HARN-15-id-collision-cross-branch-scan`(`q8tvcx`)이 이 문제의 정본 소유자**다 — 내
   `HARN-14`는 *브리핑 노출* 축, 그것은 *번호 배정* 축으로 상보적이다. 중복 등재 아님.
2. **#687 머지 전 `HARN-14-gates-add-cli-path` 재배번 필요** — main의 `HARN-14`가 먼저 착지했다.
3. 나머지 11건은 `HARN-15`(q8tvcx) acceptance ④가 이미 "재배번 대상·시점은 Kiki 판정"으로
   유보해 둔 범위다. **이 문서는 목록을 13건으로 확장해 넘긴다.**

---

## §5. 정직한 공백

- **내용 판정 없음** — 25개 각 브랜치가 *무엇을* 담고 있는지는 파일 목록·경로까지만 봤고
  본문을 읽지 않았다. 병합/폐기 판단에는 읽기가 선행돼야 한다.
- **의미 중복 미검출** — §3은 같은 *파일 경로*만 본다. 경로가 다른 동일 주제 재작업은 못 잡는다.
- **`claude/backlog-drive-next` 미판정** — main과 blob이 완전히 같아 삭제 안전으로 나왔으나
  이름·용도가 불명확해 삭제 목록에서 제외했다. 소유자 확인 필요.
- **삭제 41건의 사후 검증은 목록 대조까지만** — 지운 브랜치들의 내용을 사전에 읽지는 않았다.
  근거는 "main과 공통 조상 없음(리라이트 이전 유물) + 열린 PR·활성 claim 무일치"였다.

---

## §6. 실행

- **등재**: `HARN-16-branch-delete-403-runbook`(S4·p4·layer infra) — 컨테이너 세션의 브랜치 삭제
  403 차단을 표준 문서에 명문화. 번호는 **전 ref 스캔 후** 배정(§4 재발 방지).
- **미등재(의도)**: 번호 재배번·브랜치 처분·§3 충돌 해소는 **전부 Kiki 판정** — 기계가 정할 수
  없고, `HARN-15`(q8tvcx)가 이미 유보 범위로 선언해 둔 영역이다. 중복 등재하지 않는다.

**다음 검토 트리거**: #687 머지 시점(§4-2 재배번 확인) 또는 §3-⑤ `02_learner_model.md` 4중
충돌 브랜치 중 하나가 병합될 때.
