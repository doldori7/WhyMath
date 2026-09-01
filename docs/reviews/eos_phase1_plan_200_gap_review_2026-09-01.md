# 계획서 200 「Phase 1 — EOS Core Contract」 ↔ 저장소 실측 대조 (2026-09-01)

> **대상 문서**: `200_Phase 1 — EOS Core Contract 상세 실행계획`(Kiki 제공·저장소 외부).
> 기준일 2026-08-27 작성 · 대상기간 2026-09-07~09-27 · Gate 1 10조건 · Week 1~3 · §1~§40.
>
> **대조 시점**: `claude/review-2hi01y` @ `b1cd138f`(#946) · 2026-09-01 · 원격 브랜치 38 · 최신 PR #953.
> **성격**: 조사 전용(코드 변경 0). 대장 변경 없음 — 신규 태스크 등재는 §7의 판단 대기 항목이 정해진 뒤.
>
> **선행 문서와의 관계**: 저장소는 이미 계획서 006·100을 흡수한 정본
> `docs/strategy/eos_transition_declaration_2026-08-30.md`(선언)와 그 대조
> `docs/reviews/eos_source_docs_gap_review_2026-08-31.md`(계획서 006·100 축)를 가진다.
> 본 문서는 그 다음 권(200 = Phase 1)을 **같은 방법으로** 되짚는다.

---

## §0. 결론 3줄

1. **문서의 Gate 1 10조건 중 6건은 이미 충족 또는 초과 달성**, 2건은 부분, **2건은 "미완"이 아니라 어휘 충돌**이다. 특히 문서가 Phase 1의 3주를 걸어 만들려는 **Subject Contract와 Core→Math 경계 분리는 2026-08-31에 이미 착지**했고(`EOS-66`·`EOS-67`·`EOS-69`), 경계 위반은 오늘 실측 **0건**이다. 선행 리뷰가 006·100에 내린 진단("첨부 문서가 저장소를 보지 않고 쓰였다")이 200에도 그대로 성립한다.
2. **가장 큰 문제는 미완이 아니라 전제 충돌 3건**이다 — ⓐ 12/31의 정의(문서=출시일 / 선언=내부 검증 판정일) ⓑ 같은 날짜(9/27)에 **서로 다른 Gate 1** ⓒ 주차 번호 1칸 어긋남. 셋 다 문서를 그대로 실행하면 **선언이 최우선으로 못박은 축(AI 콘텐츠 생산 가능성·HIT)이 9월 계획에서 통째로 빠진다.**
3. 문서가 **옳게 짚은 진짜 갭은 3건**(Entity Version 규칙 미착지 · Skill 그래프 27건으로 얇음 · 추천 이유코드 부분)이며, **되돌리기 비싼 제안 5건**(ID 재설계·이벤트 어휘·디렉터리 물리 이동·ADR 트리 신설·Epic 재편)은 이미 저장소가 근거를 남기고 판정한 축을 다시 여는 것이라 채택 전 명시적 결정이 필요하다.

---

## §1. 방법

- 판정 근거는 **실파일 경로·명령 출력·태스크 ID** 중 하나여야 한다. 문서 언급만으로 "충족"한 행은 없다.
- **"trunk 부재 ≠ 미구현"** 절차 준수: 갭 판정 전 `backlog/tasks/**`(491건)·원격 브랜치 38을 교차 조회했다.
- **"식별자 부재 ≠ 기능 부재"** 절차 준수: 문서가 제안한 *이름*으로 0건이 나온 항목(이벤트 12종 등)은 **역할로 재검색**한 뒤에 판정했다. 재검색으로도 0인 항목만 갭이다.
- 재현 명령:

```bash
python3 scripts/analysis/eos_core_adapter_boundary_scan.py          # CORE→ADAPTER 위반
grep -n "importlinter" -A6 src/backend/pyproject.toml               # 정적 계약 3건
sed -n '1223,1275p' src/backend/whymath_backend/schema/enums.py     # EventType 정본
sed -n '994,1020p' src/backend/whymath_backend/schema/enums.py      # EdgeType 정본
python3 scripts/harness/backlog.py next --n 500 --json              # 전건(절단 금지)
```

---

## §2. Gate 1 10조건 대조 (문서 §2)

| # | 문서의 Gate 1 조건 | 판정 | 실측 근거 |
|---|---|---|---|
| 1 | EOS Entity ID 체계 고정 | **충돌** | 정본이 **이미 있다**: concept `math.<area>.<slug>` · skill `skill.<slug>`(`data/corpus/skill_graph_v1/graph.json`) · 오개념 `M0425` + kebab crosswalk. 유사 제안은 2026-08-17 `docs/standards/eos_identity_layer_011_1_decision.md`가 **부분 수용·부분 거부**로 판정 완료. 문서 §7의 `concept.math.quadratic-function`은 접두 순서가 **반대인 제3의 어휘** — §4-A 참조 |
| 2 | Entity Version 규칙 고정 | **부분(진짜 갭)** | `EOS-44` done(설계·foundation schema)·`EOS-72` done(ContentLifecycleState 배선/폐기 판정). 그러나 `EOS-49`(ConceptVersion 계약)는 **todo·priority 3**이고 `concept_node`에 `version` 컬럼이 없다(`review_status` reviewed/pending 2값뿐). 문서 §8의 지적("엔티티마다 별도 버전 시스템을 만들지 말라")은 **유효한 경고** |
| 3 | Subject Contract v1 확정 | **초과 달성** | `EOS-66` done — `schema/subject_adapter.py`가 **2층 계약**(필수층 3메서드 + 선택층 `verification_capabilities.py` Protocol 8종). 계약 표면은 `test_subject_adapter_two_tier_contract.py`가 **기계 동결**. 문서 §9의 5분할 제안보다 세분화가 앞서 있다 |
| 4 | Curriculum Contract 작동 | **충족** | `curriculum_framework`·`curriculum_version`·`curriculum_entry` 3모델 + `api/curricula.py`·`api/alignments.py`. 문서 §13이 경고한 "Concept에 교육과정을 박아 넣지 말라"는 **이미 준수**(`concept_standard_link` 별도 테이블 + `standard_codes` 코드만) |
| 5 | Concept/Skill Graph 작동 | **충족·단 Skill 얇음** | 개념 437 · 원자 백본 2,683노드/2,210엣지 · **Skill 27건**. `EdgeType` 6종 정본(PREREQUISITE·COMPOSED_OF·ANALOGOUS_TO·EXTENDS·CONTRASTS·TRIGGERS_DISTRACTOR). 문서 §14의 5종 제안과 **어휘 불일치** + `related_to`는 CLAUDE.md 명시 금지 — §4-B |
| 6 | Problem/Misconception 연결 작동 | **충족** | 오개념 843건(M-id) · kebab 64 · `misconception_catalog`/`_crosslink`/`_hypothesis`/`_relation` 4모델. 승인·적재 게이트는 `docs/standards/crosswalk_gate_contract.md`가 **코드 동결** |
| 7 | Learner State 최소 모델 작동 | **충족** | `ConceptMasteryHistory`·`SkillMasteryHistory`(append-only 이력). 문서 §23이 "Digital Twin 불요·Contract만"이라 한 수준을 이미 넘는다 |
| 8 | EOS Event Schema 실제 저장 | **충족·어휘 충돌** | `attempt_event`(TimescaleDB hypertable) + `evidence_event`·`hint_usage`·`review_timer_event` + `EVENT_DATA_CONTRACT`(payload 단일 진실원). `EventType`은 **한국어 11종**(풀이 단계축). 문서 §22의 영어 12종은 전 저장소 **0건** — 역할 재검색 결과 대응물이 전부 실재하므로 갭이 아니라 **제2 어휘 제안** — §4-C |
| 9 | Math Adapter Core와 분리 | **달성** | `EOS-69` done. 오늘 실측 **CORE→ADAPTER import 위반 0건**(CORE 305모듈·sympy import 0·수학어휘 0.8/kloc vs ADAPTER 34.3/kloc). `EOS-67`의 import-linter 계약 3건이 CI lint 스텝에서 매 PR 판정 |
| 10 | Contract Test CI 자동 검증 | **충족·이름 다름** | `tests/contract`·`tests/architecture` 디렉터리는 **없다**. 역할은 ① import-linter 3계약 ② `tests/infra` 배선 동결 ③ `declared_unwired_audit`(선언≠배선 4축 정적 감사) ④ 결함주입 강등전 게이트 8종 ⑤ E2E 관통 슬라이스 잡이 수행. 문서가 요구한 검사(§27 6항·§28 무결성 7항)보다 **강하다** |

**분포**: 충족·초과 **6** · 부분(진짜 갭) **1** · 어휘 충돌 **3**(1·5·8).

> **핵심**: 문서는 Phase 1 3주를 "Core Contract를 만드는 기간"으로 설계했으나, **Gate 1이 요구하는 것의 대부분은 이미 서 있다.** 그 3주를 그대로 쓰면 이미 있는 것을 다시 만들거나, 더 나쁘게는 **작동 중인 어휘를 제2 어휘로 덮는 데** 쓴다.

---

## §3. 전제 충돌 3건 — Kiki 판단이 필요한 항목

### A. 12/31의 정의 (가장 중요)

| | 문서 200 | 저장소 정본 |
|---|---|---|
| 12/31 | **출시일** — "Math EOS v1.0 출시" | **내부 검증 판정일** — 앱스토어·결제·마케팅·CS는 전부 2027 범위 (선언 §0-2) |
| 12월 목표 | 제품 완성 | **Go / Conditional Go / No-Go 판정** (선언 §0-4) |
| 최우선 축 | 학습 폐쇄루프 완성 | **AI 콘텐츠 생산 가능성** — "출시 등급 CU 1건의 인간 개입 시간(HIT) 중앙값 4분 미만인가". **폐쇄루프는 목적이 아니라 계측기로 강등**되어 깊이앵커 1개에서만 완결 (선언 §0-3) |

선언은 근거를 남긴 **의도적 재정의**다(2026-08-30·PR #904, 값 일치는 `test_declaration_canon_consistency.py`가 기계 동결). 문서 200은 그 재정의 **이전**의 전제 위에 서 있다.

이 충돌은 산술적으로 조정되지 않는다. 폐쇄루프를 12월 목표로 되돌리면 HIT·실패코드 측정이 부차가 되고, 그 반대도 마찬가지다. **먼저 정해야 하는 것은 Phase 1 주간계획이 아니라 이 한 줄이다.**

### B. 같은 날짜(9/27), 서로 다른 Gate 1

| | 문서 200의 Gate 1 | 저장소 G1 (선언 부록 E) |
|---|---|---|
| 조건 | Core Contract **10조건** | **3조건** — ① 앵커 1개 E2E ② **HIT·실패코드 이벤트 적재** ③ Core→Math 정적 의존 0 |
| 성격 | 구조 계약의 완성도 | 계측 가능한 파이프라인 |
| 교집합 | 문서 #9 ↔ 저장소 ③ (**오늘 이미 충족**) | |

**문서의 Gate 1에는 HIT·실패코드 축이 통째로 없다.** 그것이 선언의 최우선 목표(②)이자 12/31 판정의 유일한 재료인데, 문서대로 9월을 운영하면 **G1 통과 여부를 잴 계측기가 9/27까지 안 선다.** 반대로 저장소 G1에는 Curriculum·Learner·Recommendation 계약 조건이 없다 — 다만 §2가 보였듯 그것들은 이미 작동하므로 실질 손실은 작다.

`EOS-69`가 남긴 잔여의 **재확인 지점도 "G1(2026-09-27)"**로 적혀 있어, 저장소는 이미 저장소판 G1을 참조하는 코드·문서를 갖고 있다. 게이트 정의를 문서판으로 바꾸면 그 참조들이 전부 결정 불가가 된다.

### C. 주차 번호 1칸 어긋남

| 기간 | 문서 200 | 저장소 선언 |
|---|---|---|
| 8/31~9/6 | (Phase 0 꼬리) | **W1** — "헌법 고정" |
| 9/7~9/13 | **Week 1** | **W2** — "되돌릴 수 없는 스키마 확정" |
| 9/14~9/20 | Week 2 | W3 |

이미 대장에 흔적이 있다 — `EOS-57` 제목: *"problem_attempted skill_ids[] 복수 영속 — 소급 불가 스키마(**W2** 되돌릴 수 없는 결정 ①)"*. 문서를 그대로 쓰면 "W2 태스크"가 문서의 Week 2(9/14~)로 읽혀 **일주일 밀린다.** 무해해 보이지만 소급 불가 스키마 결정의 착지 시점이 걸린 항목이다.

---

## §4. 되돌리기 비싼 제안 5건 — 채택 시 실제 비용

### A. ID 체계 재설계 (§7 — Week 1 안에 "반드시 고정")

문서 제안 vs 실재:

| 대상 | 문서 §7 | 저장소 실재 | 영향 규모 |
|---|---|---|---|
| 개념 | `concept.math.quadratic-function` | `math.<area>.<slug>` (접두 순서 반대) | 개념 437 + 원자 2,683 + 엣지 2,210 |
| Skill | `skill.math.factor-quadratic-expression` (subject 세그먼트 있음) | `skill.polynomial-arithmetic` (없음) | 27 |
| 오개념 | `misconception.math.quadratic.zero-product-error` | `M0425` + kebab 64 | 843 + **코드 동결된 crosswalk 게이트** |

문서 자신이 §7에서 "내부 PK는 UUID, 외부는 stable EOS ID를 하나 더 둔다"고 했는데 — **저장소는 이미 그 구조다.** 재설계가 사는 것은 *표기 통일*뿐이고, 잃는 것은 843건 오개념 crosswalk 게이트 계약과 2,683노드 백본의 키다. **2026-08-17 결정이 이미 "전면 수용 거부"로 판정한 축**이므로, 다시 열려면 그 결정을 뒤집는 근거가 필요하다.

### B. 관계 어휘 5종 (§14)

문서: `prerequisite_of` · `part_of` · `related_to` · `equivalent_to` · `contrasts_with`

저장소 `EdgeType`(6종)과 3건은 대응하나(`PREREQUISITE`·`COMPOSED_OF`·`CONTRASTS`), **`related_to`는 CLAUDE.md 절대 금기**다 — *"`similar_to`/`related_to`를 traversal에 사용 금지"*(관계 폭발 방어). 문서는 "제한할 수 있습니다"라는 완화된 표현을 쓰지만, 핵심 5종에 넣는 순간 그것이 정본이 된다. **`equivalent_to`는 저장소에 대응물이 없다** — 신설하려면 `ANALOGOUS_TO`/`EXTENDS`와의 경계를 먼저 정의해야 한다.

### C. 이벤트 어휘 12종 (§22)

문서의 12종(`session_started`~`session_completed`)은 전 저장소 **0건**이다. 그러나 역할로 재검색하면 대응물이 전부 있다:

| 문서 §22 | 저장소 실재 |
|---|---|
| problem_attempted / answer_submitted | `attempt_event`(hypertable) + `AnswerSubmission`(`EOS-32` done) |
| answer_evaluated | `검산결과` EventType + `EVENT_DATA_CONTRACT` |
| hint_requested / (hint 제공) | `힌트요청`·`힌트제공` EventType + `hint_usage` |
| misconception_detected | `misconception_hypothesis` |
| mastery_updated | `ConceptMasteryHistory`·`SkillMasteryHistory` |

즉 **갭이 아니라 제2 어휘 제안**이다. 채택하면 payload 계약(`EVENT_DATA_CONTRACT`)·휴면 enum 관리·`analytics_event` 정규화가 전부 두 벌이 된다. 필요한 것이 "생애주기 축 이벤트"라면 기존 `EventType`에 **값을 추가**하는 편이 계약을 하나로 유지한다.

### D. 디렉터리 물리 이동 (§4·W1-1의 `eos/core|contracts|adapters|apps` 트리)

선언 §1.3-③가 **"물리 대이동 보류"**로 이미 판정했고, `EOS-65`가 그 대안(현행 `l1`~`l6`에 Core/Adapter/Infra **표기** 배정)을 실행해 `docs/architecture/eos_core_adapter_boundary.md`로 착지시켰다. 문서 자신도 "중요한 것은 디렉터리명이 아니라 Dependency Direction"이라 적었는데 — **그 Dependency Direction은 이미 기계가 강제한다**(import-linter 3계약·위반 0). 물리 이동은 위반 수를 줄이지 못하고 850+ PR 분량의 blame·미머지 브랜치 38개의 충돌만 만든다.

### E. ADR 10건 트리 신설 (§31) · Epic 13개 재편 (§29)

- **ADR**: 선행 리뷰가 `docs/adr/` 신설을 **"의도적 미채택"**으로 기록했다(이중 진실원천 방지). 저장소의 결정 기록 정본은 `MEMORY.md` 결정 로그 + `docs/architecture/*_adr.md` + 태스크 acceptance다. 문서가 든 10개 주제 중 **ADR-001·004·006·007·008은 이미 그 형태로 존재**한다(경계 문서·subject_adapter docstring·crosswalk 계약 등).
- **Epic**: 작업 정본은 `backlog/`(491태스크·`backlog.py`가 착수 후보를 계산)다. Epic 축을 새로 만들면 **대장이 둘**이 되고, `selector.py`는 Epic을 읽지 않는다(2026-09-01 등재 규칙: "선행 조건을 산문에만 적고 대장에 집행하지 않기 금지"의 같은 함정).

---

## §5. 문서가 옳게 짚은 것 (진짜 갭 3건)

| # | 문서 위치 | 갭 | 실측 |
|---|---|---|---|
| **G-1** | §8 Version 규칙 | Entity 공통 버전·상태 전이가 **미착지** | `EOS-49`(ConceptVersion 계약) **todo·priority 3**. `concept_node`에 `version` 없음. 문서의 경고("엔티티마다 별도 버전 시스템 금지")가 정확히 이 상태를 가리킨다. **우선도 재검토 후보** |
| **G-2** | §15 Skill Graph | Concept/Skill 분리는 됐으나 **Skill이 27건**(개념 437 대비) — "숙련도 추정"의 분모가 얇다 | `SkillNode` 실재·`SkillMasteryHistory` 실재. 그러나 `EOS-63`(attempt_event.skill_ids 소비 전환) **todo**이며 **타 세션 원격 claim 중**(`claude/status-f6qz0c`) — 병렬 착수 금지 |
| **G-3** | §25 Recommendation reason_code | 추천 이유의 **구조화가 부분** | `l6/blueprint/assembly.py:519`에 `reason` Literal 실재. 다만 추천 응답 전반의 `reason_code`+`evidence`+`score` 3종 세트는 아님. CLAUDE.md "작동한 비율" 원칙(알고리즘이 실제로 작동했는지를 응답이 말해야 한다)과 같은 방향의 지적 |

**§34 "하지 말아야 할 것" 5종은 전부 저장소 결정과 일치한다** — ① Graph DB 전환 금지 = 2026-08-03 Neo4j 런타임 미도입 확정 ② 완벽 Ontology 금지 = EdgeType 6종 제한 ③ Microservices 금지 = 현행 modular monolith ④ Agent 후순위 ⑤ 선행 추상화 금지 = `EOS-66`이 `explain`을 v1에서 뺀 바로 그 근거. **이 절은 문서에서 가장 값어치 있는 부분이고 채택에 비용이 없다.**

---

## §6. 사실 오류·stale 수치

| 문서 진술 | 실측 | 성격 |
|---|---|---|
| "현재 시점인 2026년 8월 27일" | 오늘 2026-09-01 — **Phase 0 잔여 5일** | 작성일 기준·정보성 |
| "850 PR 누적" (§30) | 최신 **#953** | stale(작성 후 100+) |
| "기존 120여 개 기능" (§1) | 기계 장부 `backlog/inventory/feature_inventory.yaml` = **서빙 기능 23건**(KEEP 4·REFACTOR 17·HEAVY 1·REPLACE 1) | **모집단 불일치** — 120은 외부 추적표 수치. 선행 리뷰가 "270→53 축소 경위 미문서화"로 이미 지적한 것과 같은 뿌리 |
| "향후 270개 EOS 기능" (§1) | `EOS-53` crosswalk가 **53항목**으로 전수 판정 | 동상 |
| Gate 1 "10개 중 8개가 아니라 10개 모두" (§2) | 취지는 옳으나 **대상 10조건 자체가 저장소 G1과 다르다** | §3-B |

경계 스캔 출력의 *"집행은 EOS-67"* 이라는 자기 주석은 `EOS-67` 완료(2026-08-31) 이후 **stale**이다 — 사소하나 정정 대상.

---

## §7. 권고

### 즉시 (Kiki 판단 — 9/6 G0 판정에 얹을 것)

1. **§3-A 12/31의 정의를 하나로 확정한다.** 선언 유지(내부 검증 판정일)가 권고다 — 실패 정의 F-Ⅰ~Ⅴ가 G0(9/6)에 동결되고 12월에 수정 금지이므로, 이 결정을 미루면 **동결할 대상 자체가 흔들린다.**
2. **§3-B Gate 1을 하나로 병합한다.** 권고안: 저장소 G1 3조건을 **차단 조건**으로 유지하고, 문서의 10조건 중 미충족 2건(#2 Version·#1 ID 표기)만 **비차단 관측 항목**으로 얹는다. 근거 — 나머지 8건은 이미 충족이라 차단 조건으로 세워도 정보가 0이고, HIT 축을 빼면 12월 판정 재료가 없다.
3. **§3-C 주차 번호는 저장소(W1=8/31~9/6)를 정본으로 한다.** 이미 `EOS-57` 제목이 그 번호를 쓴다. 문서를 인용할 때는 "문서 Week 1 = W2"로 환산 표기.

### 채택 전 결정 (§4 — 되돌리기 비싼 순)

| 제안 | 권고 | 사유 |
|---|---|---|
| A. ID 재설계 | **미채택** | 2026-08-17 결정이 이미 판정 · 4,000+ 키 영향 · crosswalk 게이트 코드 동결 |
| B. `related_to` 관계 | **미채택** | CLAUDE.md 절대 금기 직접 위반 |
| C. 이벤트 12종 | **부분 채택** — 필요한 생애주기 축은 기존 `EventType`에 값 추가로 | 계약 이중화 회피 |
| D. 디렉터리 물리 이동 | **미채택** | 선언 §1.3-③ 판정 유지 · `EOS-65` 표기 대안이 이미 착지 · 위반 이미 0 |
| E. ADR 트리 / Epic 재편 | **미채택** | 이중 진실원천 · `selector.py`가 Epic을 읽지 않음 |

### 등재 후보 (§5 — Kiki 승인 시 `backlog.py add`)

- **G-1** `EOS-49` 우선도 재검토(3 → 1~2). Gate 1 #2의 유일한 미충족분이고, 문서 §8이 옳게 짚었다.
- **G-3** 추천 응답의 `reason_code`+`evidence`+`score` 구조화 — 신규 태스크 후보.
- **G-2**는 **등재 금지** — `EOS-63`이 이미 있고 타 세션이 원격 claim 중이다.

### 문서 자체에 대한 평가

문서 200은 **아키텍처 원칙으로는 대체로 옳고**(§5 Dependency Rule의 CI 강제·§10 Core/Adapter 귀속 목록·§24 Attempt≠Evaluation≠Assessment≠Mastery 4분·§34 하지 말 것 5종은 저장소 결정과 독립적으로 같은 결론에 도달했다), **저장소 실상에 대해서만 틀렸다.** 그 결과 3주 계획의 상당 부분이 이미 완료된 일의 재실행이거나 작동 중인 어휘의 교체가 된다.

→ **문서를 Phase 1 실행계획으로 그대로 채택하지 말고, §5의 3건 + §7의 게이트 병합안만 흡수하는 것을 권한다.** 9월 3주는 문서가 비워 둔 축 — **앵커 1개 E2E와 HIT·실패코드 계측기** — 에 쓰는 것이 12/31 판정에 직결된다.

---

**작성**: 2026-09-01 · 조사 전용(코드 변경 0) · 대장 변경 0
**정본 관계**: 선언(`eos_transition_declaration_2026-08-30.md`) > 본 문서. 충돌 시 선언 우선이며, 선언을 바꾸는 것은 Kiki 판단이다.
