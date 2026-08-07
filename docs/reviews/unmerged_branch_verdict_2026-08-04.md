# 미머지 브랜치 25건 — 본문 검토 후 병합/폐기 판정 (2026-08-04)

> **선행**: `unmerged_branch_triage_2026-08-04.md`(같은 날)가 파일 목록·blob 수준까지 분류했고,
> 그 §5에서 "내용 판정 없음 — 본문을 읽지 않았다"를 정직한 공백으로 남겼다. 이 문서가 그 공백을
> 닫는다. Kiki 지시로 25건의 **본문**(태스크 status·artifacts·설계 문서 결론부·구현 파일)을 읽고
> 처분을 판정했다.
>
> **결론 3줄**: ⑴ **폐기 판정은 25건 중 단 1건**(`bbyp3d` — 같은 세션의 수정판 `r2-retry`가 존재).
> 나머지 24건은 전부 고유 산출물이다. ⑵ **9개 브랜치가 이미 완료(`done`)된 작업 13건을 고립**시키고
> 있다 — 그중 `S3-26`은 **이 세션 브리핑이 "다음 착수 후보 3위"로 추천 중**이었다(이미 끝난 일을
> 다시 시키고 있었다). ⑶ 진짜 위험은 폐기 대상이 아니라 **병합 순서**다 — `02_learner_model.md`
> 4중 충돌과 AI 튜터 2개 브랜치의 13파일 중첩은 순서를 틀리면 앞선 작업이 조용히 덮인다.

---

## §0. 판정 기준

| 판정 | 의미 | 근거 |
|---|---|---|
| **🔴 최우선 병합** | 완료된 작업이 고립돼 있고, 그 태스크가 백로그에서 여전히 `todo`로 보인다 | 다음 세션이 **끝난 일을 다시 착수**한다. 실피해 진행 중 |
| **🟢 병합** | 고유 산출물이며 충돌·중복 없음 | 정상 경로 |
| **🟡 순서 주의 병합** | 고유하지만 다른 브랜치와 같은 파일을 고친다 | 순서를 정해야 앞선 판정이 안 덮인다 |
| **⚫ 폐기** | 같은 내용의 수정판이 별도 브랜치에 존재 | 유일한 폐기 사유 |

**폐기 판정의 문턱을 높게 뒀다.** "오래됐다"·"작다"는 폐기 사유가 아니다 — 이 저장소는 고립된
완료 작업이 실피해를 낸 전력이 3회 있다(`problem_bank_gap_review_r2.md` §0-① "고립 사고 3회차").

---

## §1. 🔴 최우선 병합 — 완료 작업이 고립된 9건

브랜치는 `done`인데 main은 `todo`(또는 태스크 자체가 없음)인 것들이다. **백로그가 거짓을 말하고
있는 상태**다.

| 브랜치 | 고립된 완료 작업 | 증적 | 실피해 |
|---|---|---|---|
| `whymath-visualization-review-zl2v1b` | `S3-26-concept-supply-integrity` · `VIZ-02-generator-render-contract-derive` · `OPS-16-l3-prompt-asset-audit` | 커밋 `0661203c`·`f9b2065a` · 신규 코드/테스트 **12파일** | 🚨 **S3-26이 이 세션 브리핑의 "다음 착수 후보 3위"** · `VIZ-02`도 직전 브리핑에 등장 |
| `whymath-ai-tutor-design-iu9qk5` | `PED-04-tutoring-decision-log` | artifacts에 "전체 백엔드 스위트 **8099 passed·0 failed**" 명기 · `l4/session_recall.py`·`l4/turn_meta.py` 신설 | PED-04가 백로그에 `todo`로 남아 재착수 위험 |
| `whymath-ai-tutor-design-953m1e` | `PED-05-learner-state-assembly` · `S3-16-behavior-telemetry-writers` | 커밋 `793ed7ed`·`99d60e28` · `l2/learner_state.py` 신설 | 동일 |
| `whymath-problem-bank-design-65tsm4` | `HARN-12-brief-unmerged-done-filter` · `S4-17-verify-tier-l1-promotion` · `S4-18-rephrase-lineage-identity-decision` | identity_id 마이그레이션 + 백필 스크립트 | **`HARN-12`가 바로 이 현상(브리핑의 미머지 done 미필터)을 고치는 태스크인데 그것 자체가 고립돼 있다** |
| `education-os-architecture-mr0fbq` | `ARCH-19-answer-distribution-latex-gates` · `S3-10-persona-fit-backfill` · `S3-13-suneung-prefilter-persona-fit-widen` | persona_fit 감사 데이터 6종 + 코드 29파일 | S3-10이 2개 브랜치에 중복 완료(아래 §3-③) |
| `s3-10-persona-fit-2xk548` | `S3-10-persona-fit-backfill` | 백필 산출 13파일 | ⚠ `mr0fbq`와 **같은 태스크 중복 완료** |
| `s4-14-skeleton-cat-re24tk` | `S4-14-variant-lineage-persist` | `harness/rephrase_lineage_backfill.py` + 관계 거버넌스 테스트 | `65tsm4`의 S4-18과 인접(계보 축) |
| `whymath-curriculum-design-b7qav0` | `PATH-02-learning-path-ordering-honesty` | 커밋 `0ffbf2e7` · `l2/learning_path.py` +55줄·테스트 +77줄 | |
| `whymath-data-platform-design-8ceaf5` | `OPS-17-supply-demand-reach-audit`(main에 태스크 없음) | `ops/reach_audit.py` + 배선 테스트 | ⚠ 번호가 main의 다른 `OPS-17`과 충돌(§4) |

**`HARN-12`의 아이러니**: 브리핑이 "이미 완료된 미머지 태스크"를 추천하지 않게 만드는 태스크가,
바로 그 이유로 아무도 못 보는 곳에 고립돼 있다. 이것이 §1 전체의 근본 원인이다.

---

## §2. ⚫ 폐기 — 1건

| 브랜치 | 폐기 사유 |
|---|---|
| `whymath-05-problem-bank-design-bbyp3d` | **`whymath-05-problem-bank-r2-retry`(PR #687)가 같은 문서의 수정판**이다. 둘의 `problem_bank_gap_review_r2.md`는 결론부까지 동일하고, 차이는 r2-retry가 **중복 등재를 제거**한 것뿐 — bbyp3d의 `PB-05-item-content-safety-scan`(문항 금칙어·PII 검사)은 main에 이미 착지한 `ARCH-24-output-safety-filter-axis`(학생 대면 출력 금칙어·PII 검사)와 **같은 축**이라 r2-retry가 의도적으로 뺐다. bbyp3d를 병합하면 ARCH-24와 이중 진실원천이 된다 |

**검증**: 두 태스크 제목을 나란히 확인했다 — bbyp3d `"문항 본문 금칙어·PII 검사 — 미성년자 대면
콘텐츠 2,647건에 내용 안전 검사기 0"` ↔ main `"학생 대면 출력 금칙어·PII 검사 축 — qa_pipeline
8번째 축 승격(현재 검사기 0)"`. 대상 범위만 다르고 축은 동일하다.

**폐기 전 확인 1건**: bbyp3d에만 있는 것이 PB-05 하나뿐인지 — r2-retry 병합 후 diff로 재확인 필요.

---

## §3. 🟡 순서 주의 — 병합 순서를 틀리면 손실이 나는 충돌

### ① AI 튜터 2개 브랜치 — **13개 실파일 중첩**

`953m1e`(5일·PED-05+S3-16 완료)와 `iu9qk5`(1일·PED-04 완료)는 **다른 태스크**를 했지만
`api/coach.py`·`api/me.py`·`l4/polya/engine.py`·`l4/hint_deferral.py`·`harness/wh1_evaluation.py`·
`schema/event_data_contract.py` + 테스트 4종 + 정본 문서 2종을 **둘 다** 고친다.

**권고 순서: `iu9qk5` → `953m1e`**. 근거는 iu9qk5가 1일 전 main 기준이라 리베이스 비용이 작고,
PED-04(교수 결정 로그 writer)가 PED-05(학습자 상태 조립)의 **입력**이기 때문이다. 역순으로 하면
953m1e가 PED-04 없는 상태를 전제로 짠 코드 위에 iu9qk5를 얹게 된다.

### ② `02_learner_model.md` — **4개 브랜치가 각자 수정**

`953m1e` · `jkwdzn` · `8ceaf5` · `gvku5q`. 계층 정본이라 순서대로 병합하면 뒤 3개가 전부 충돌하고,
해결 과정에서 **앞선 판정이 조용히 덮일 수 있다**. 이 파일만 따로 4개 diff를 한 번에 놓고 통합
편집하는 것을 권한다(순차 충돌 해결 금지).

### ③ `S3-10-persona-fit-backfill` — **2개 브랜치가 같은 태스크를 각각 완료**

`mr0fbq`(코드 29파일)와 `2xk548`(13파일)이 둘 다 `done`으로 처리했다. 산출 데이터(
`docs/data/persona_fit_backfill_audit/*.jsonl`)가 **6종 겹친다**. 둘 중 하나는 폐기 또는 흡수
대상이나, **어느 쪽 백필이 정확한지는 데이터를 봐야 판정 가능**하다 — 이 문서의 범위 밖(§5).

### ④ 그 외 같은 파일 충돌쌍

`ai_tutor_module_gap_review.md`(`iu9qk5`·`gvku5q`) · `04a_wh1_tutoring_harness.md`(`953m1e`·
`iu9qk5`) · `06_application_modes.md`(`jkwdzn`·`gvku5q`) · `problem_bank_gap_review.md`
(`bbyp3d`·`r2-retry`·`65tsm4`).

---

## §4. 🟢 병합 — 고유 산출물 (충돌 없음)

전건 **핵심 문서가 main에 존재하지 않음**을 확인했다(`git cat-file -e origin/main:<path>` 전건
`없음`). 즉 어느 것도 이미 흡수되지 않았다.

| 브랜치 | 산출물 | PR |
|---|---|---|
| `whymath-05-problem-bank-r2-retry` | `problem_bank_gap_review_r2.md` + PB-01~04 + 게이트 1 | **#687** ⚠ 머지 전 `HARN-14-gates-add-cli-path` 재배번 필요 |
| `whymath-misconception-review-h87afk` | `misconception_module_gap_review.md` + `04e_misconception_remediation_design.md` | **#667** |
| `whymath-math-engine-design-4qbaru` | `math_engine_gap_review.md` | **#678** |
| `whymath-nlp-design-my18a1` | `nlp_module_gap_review_r2.md` | **#697** |
| `whymath-learning-analytics-abk8ea` | PATH-04 등재 | **#673** |
| `whymath-solution-review-yvoctp` | 풀이 2차 재검증 | **#668** |
| `whymath-data-platform-design-8ceaf5` | `data_platform_module_gap_review.md`(**r1**) | - ⚠ §1에도 해당(OPS-17 고립) |
| `whymath-ai-recommendation-review-q8tvcx` | `data_platform_module_gap_review_r2.md` + `HARN-15-id-collision-cross-branch-scan` | - **8ceaf5(r1) 선행 필수** — r2가 "r1을 대체하지 않고 누적"이라 자기 선언 |
| `whymath-ai-recommendation-review-tv1f08` | `ai_recommendation_module_gap_review_2.md` | - |
| `whymath-learning-analytics-9t71oh` | `learning_analytics_gap_review.md` | - |
| `whymath-gamification-design-d9di3h` | `gamification_module_gap_review_r2.md` | - |
| `whymath-assessment-design-jkwdzn` | 평가 모듈 갭 리뷰 + ASM 태스크 | - ⚠ §3-② 충돌 |
| `whymath-learning-path-design-gvku5q` | 고교 유형별 학습경로 + 태스크 8건 | - ⚠ §3-②④ 충돌 |
| `whymath-collaboration-design-ur7l4v` | 잔여 문서 2건(4/7은 #696으로 이미 흡수) | - |
| `whymath-eos-review-iyev91` | 잔여 태스크 2건(4/8 흡수) | - |
| `whymath-eos-review-euolne` | `ARCH-22` 정정 1건 | - 최소 변경 |

**`q8tvcx` → `8ceaf5` 의존이 확정적이다**: r2 문서가 서두에서 *"r1이 이 틀의 84·85 전 항목을
빠짐없이 crosswalk 했다. 이 r2는 틀 항목을 다시 세지 않는다 … r1을 대체하지 않고 **누적**한다"*
라고 자기 선언한다. r1(8ceaf5) 없이 r2만 병합하면 참조가 끊긴다.

---

## §5. 권고 병합 순서

1. **§1의 고립 완료분 먼저** — 백로그가 거짓을 말하는 상태를 가장 먼저 끝낸다.
   순서: `65tsm4`(HARN-12 포함 — **이걸 먼저 넣어야 브리핑이 나머지 고립을 스스로 드러낸다**)
   → `zl2v1b`(S3-26·VIZ-02 — 재착수 위험 최고) → `iu9qk5` → `953m1e` → `b7qav0` → `re24tk`.
2. **열린 PR 6건** — #687(재배번 후)·#667·#678·#697·#673·#668.
3. **문서 계열** — `8ceaf5`(r1) → `q8tvcx`(r2) 순서 고정. 나머지는 순서 무관.
4. **`02_learner_model.md` 4중 충돌은 통합 편집으로** — 순차 충돌 해결 금지(§3-②).
5. **`bbyp3d` 폐기** — #687 병합 후 잔여 diff 재확인 뒤 삭제.
6. **`mr0fbq` vs `2xk548`(S3-10 중복)은 데이터 판정 후** — 이 문서 범위 밖.

---

## §6. 정직한 공백

- **S3-10 중복 완료의 승자 미판정**(§3-③) — 어느 백필이 정확한지는 `persona_fit` 산출
  `.jsonl` 6종을 실제로 비교해야 한다. 데이터 검증이라 별도 작업이다.
- **코드 리뷰 아님** — 각 브랜치의 구현이 *올바른지*는 보지 않았다. 본 판정은 "고유한가 ·
  완료됐는가 · 충돌하는가"까지다. 병합 시 CI와 리뷰가 정확성을 판정한다.
- **`953m1e`의 PED-04 미완 처리 확인 불충분** — 이 브랜치는 PED-04 yaml을 건드리지만
  `status: todo`로 남겼다. `iu9qk5`의 done과 병합 시 어느 쪽 yaml이 남는지 주의 필요.
- **`backlog-drive-next`·`harness-claims`는 25건 밖** — 전자는 용도 불명(소유자 확인 필요),
  후자는 claim 원장 인프라다.
- **이 판정은 2026-08-04 기준 스냅샷** — 다른 세션이 계속 푸시 중이므로(오늘만 3개 브랜치 갱신)
  병합 착수 시점에 재확인이 필요하다.
