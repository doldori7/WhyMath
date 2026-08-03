# 교육과정 관리(Curriculum Foundation) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03)

> **범위**: 외부 참고 문서 『0단계: 교육과정 관리』(①교육과정 데이터베이스 ②단원 구조 관리
> ③성취기준 관리 ④학습목표(Objective) 관리 ⑤선수학습 관계 그래프, 5모듈 — **WhyMath 전용이
> 아닌 일반적인 EOS(Education Operating System) 틀**, Kiki 제공 docx)을 현 코드베이스와 대조해
> 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(Concept Purity·Curriculum은 Overlay·
> Layer Separation·관계 타입 최소화·교수학 날조 금지·측정 없는 도입 없음) 안에서 설계한 기록.
> **형식**: `ai_recommendation_module_gap_review.md`(같은 EOS 틀 시리즈, 2026-08-01) 답습 —
> 시리즈 **11번째** 자매편(1.knowledge → 2.problem_bank → 3.ai_tutor → 4.solution →
> 5.operations → 6.account_security → 7.ai_content_generation → 8.visualization → 9.nlp →
> 10.ai_recommendation → **11.curriculum**).
> **결론**: 이 틀이 그리는 "교육과정이 원본, 개념·AI 엔진은 그 하류"라는 세계관은 WhyMath 정본과
> **정반대**다(§0). 정본은 개념을 영속 원본으로 두고 교육과정을 갈아끼우는 Overlay로 둔다(원칙5).
> 따라서 "교육과정 버전이 1급 엔티티가 아니다"는 갭이 아니라 설계다. 진짜 갭은 그 Overlay
> 설계가 **표기 분열·커버리지 미달**로 스스로 무너지는 지점에서만 성립한다. 진짜 갭 3건을
> 설계(D1~D3)하고 페이퍼 갭 1건을 남겼다. 실행 3건을 백로그에 등재했다(`CUR-01`~`CUR-03`,
> `CUR-03`은 owner=kiki). 의도적 미채택 6건 · 정직한 공백 7종 · 유보 발화조건 6건. 정본 stale
> 6곳을 이번 대조에서 실측으로 잡아 정정한다.

관련 정본: `01_data_foundation.md`(L1 데이터 기반·성취기준/개념그래프/다국 매트릭스 목표 명세) ·
`docs/data/concept_graph.md`(개념 그래프 스키마 정본·Concept Purity) ·
`docs/data/curriculum_matrix.md`(`CurriculumEntry` 30/31필드 명세) ·
`docs/data/achievement_standards_v1.md`(성취기준 895건 정본) ·
`docs/architecture/concept_node_layering_decision.md`(9계층 ADR) ·
`knowledge_module_gap_review.md`(기능 6~10·원자 백본 2,697 truth source 선례) ·
`ai_recommendation_module_gap_review.md`(§6 반복 실수 4~6회차 선례) · `MEMORY.md` 결정 로그
(2026-05-13~2026-07-30 교육과정·개념그래프 계보).

---

## §0. 두 가지 전제 정리

### ① 착수 가설이 절반만 맞았다 — "교육과정 관리가 없다"는 반증됐다

이 대조는 "WhyMath에 교육과정 관리 자체가 빈약하다"는 가설로 시작했다. 실측 결과 **성취기준
축은 오히려 초과 충족**이다 — 895건이 정합 스키마(`norm_id` PK, `curriculum_revision` ×
`official_code` UNIQUE, 153건 코드 충돌 해소 이력)로 이미 적재돼 있고, 데이터 카드
(`achievement_standards_v1.md`)까지 정본화됐다. 반면 **그 위(학습목표 분해)와 옆(단원 연산·
버전 정합)은 설계는 있는데 데이터·연산이 거의 없다.** 즉 문제는 "관리가 없다"가 아니라
"관리 축마다 성숙도가 극단적으로 다르다"이다(성취기준 100% vs 학습목표 0.1%).

### ② 틀의 아키텍처와 정본의 차이 (갭 판정의 전제)

외부 틀은 교육과정을 **최상위 원본**으로 두고 하위로 흘려보낸다:

```
교육과정 DB → 단원 구조 → 성취기준 → Objective → 선수학습 그래프 → AI 엔진들
```

WhyMath 정본은 **개념(Concept)이 영속 원본**이고 교육과정은 그 위에 갈아끼우는 **Overlay**다
(CLAUDE.md 8대 원칙 ⑤ "Curriculum은 Overlay — 개념은 영속, 교육과정 매핑만 교체"). 실제로
`Concept` 노드에서 `subject`·`curriculum_version`·`grade_introduced`·`semester_introduced`는
**의도적으로 제거**됐고(마이그레이션 `20260630_1200_d1e2f3a4b5c6`·`20260630_1600_f3a4b5c6d7e8`),
그 신호는 별도 `CurriculumEntry`(개념×국가×과목 셀)로 이관됐다. `curriculum_loader.py:4-8`이
이 설계를 직접 명문화한다:

> "`Concept`에서 제거된 교육과정 필드(`subject`·`curriculum_version`·`grade_introduced`·
> `semester_introduced`)를 대신해 교육과정 분류를 담는 단일 진실이 `curriculum_entry`
> Overlay다(math_dsl_risk_register Q5·Q8·Q10-③ '노드는 의미만·교육과정은 Overlay')."

이 방향 전도가 §1 판정의 축이다:

| 틀이 교육과정에 요구하는 것 | WhyMath 정본의 자리 |
|---|---|
| 교육과정 버전이 국가·과목·학년의 **루트 엔티티** | 교육과정은 **개념에 매달리는 셀**(`CurriculumEntry`) — 개념이 루트 |
| 단원 트리가 **1급 관리 대상**(이동·병합·분리) | 단원은 원자 백본(`atom_node`)의 **파생 뷰** — 읽기 전용 코퍼스 |
| 사람이 GUI(Drag&Drop)로 편집 | **YAML=소스, DB=산출물**(CLI populate 단방향, 사람 편집 경로 없음) |
| 선수학습 그래프의 관계 6종을 **동등하게** 관리 | `PREREQUISITE`만 진짜 traversal 관계, 나머지는 **의도적 미채택/유보**(§2) |

**따라서 이 문서는 "교육과정이 1급 엔티티가 아니다"·"관리 GUI가 없다"를 갭으로 세지 않는다.**
그건 §2의 미채택이거나 §4의 유보다. 갭은 **Overlay 설계 자체가 내부적으로 어긋난 지점**
(D1: 표기 분열)과 **하류 소비 경로가 완비됐는데 공급이 안 뚫린 지점**(D2: 학습목표 커버리지)
에서만 성립한다.

---

## §1. 5모듈 전수 대조

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·데이터* 없음) / ⚠️ 진짜 갭 → D /
🚫 의도적 미채택 → §2

### 모듈 1 — 교육과정 데이터베이스 (관리 항목: 버전·국가·학교급·과목·학년·학기·적용년도·폐기여부)

| 관리 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 교육과정 버전(엔티티) | 1급 테이블 없음. `curriculum_revision`이 4곳(`achievement_standard`·`curriculum_entry`·`unit_spec.curriculum_rev`·`schema/enums.py Curriculum`)에 **자유 문자열로 분열**(`"2022 개정"`/`"2022"`/`"2022_REVISION"`) | ⚠️ → **D1** |
| 국가 | `curriculum_entry.country_code` + `license_id` enum(`KR-NCIC`/`US-CCSS`/`INT-IMO`/`JP-MEXT`/`GB-NC`) | ✅ |
| 학교급 | `achievement_standard.school_type`(초/중/고, 실측 249/121/525) | ✅ |
| 과목 | `curriculum_entry.subject`(교과 단위) + `achievement_standard.subject`(NCIC 과목 단위, granularity 다름 — docstring 교차 명기) | ✅ |
| 학년 | `curriculum_entry.introduced_grade`(1~12)·`grade_band` | ✅ |
| 학기 | 컬럼 자체가 **의도적으로 삭제**됨(`Concept.semester_introduced` 드롭, 마이그레이션 `20260630_1200`) | 🚫 §2-① |
| 적용년도 | `effective_from`(Date) — **시작일만**, 종료일 없음 | △ (§4-③) |
| 폐기여부 | 없음(`is_active`/`deprecated`/`superseded` 플래그 0). 유일한 유사 개념은 `unit_spec.status` CHECK(`SUPERSEDED` 포함)뿐 | △ (§4-③) |

### 모듈 2 — 단원 구조 관리 (필요 기능: Drag&Drop 이동·병합·분리·Tree/Graph 보기)

| 필요 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 계층 트리(대/중/소단원) | 원자 백본 3계층(`atom_node.level` = 단원/소단원/세부개념, `parent_code`, 실측 217/643/1,823) | ✅(단, FK 없는 파생 뷰) |
| 단원 순서(sort order) | 컬럼 자체가 `db/models/` 전체에 **0개** | ⚠️(§4-①, 우선순위 밖) |
| 단원 이동 | 없음 | 🚫 §2-⑥ |
| 단원 병합 | 없음(있는 것은 `dedup_merges_v1.json` — *중복 원자 제거* 배치일 뿐 단원 재구조화 아님) | 🚫 §2-⑥ |
| 단원 분리 | 없음 | 🚫 §2-⑥ |
| Tree 보기 | 사람 편집 GUI 0 — API로 노출은 됨(`GET /v1/concepts/{id}/edges`) | △ (§4-②) |
| Graph 보기 | 동상 | △ (§4-②) |
| 버전 비교(diff) | `UnitSpec`이 `(unit_id, unit_version)` 복합 PK로 버전을 *보존*만 함. 비교 연산 없음 | ⚠️(§4-①, 데이터 1건뿐이라 비교할 대상 자체가 없음) |

### 모듈 3 — 성취기준 관리 (관리 정보: 코드·설명·단원연결·난이도·중요도·키워드·개념태그·평가유형·임베딩)

| 관리 정보 | WhyMath 현행 | 판정 |
|---|---|---|
| 코드 | `official_code`(예 `[9수01-01]`) + 충돌 해소용 `norm_id` PK(`2022_2수_01_01`) | ✅ **초과**(외부 틀보다 정교 — 개정 간 코드 충돌 153건을 실제로 해소) |
| 설명 | `statement`(Text, 895건 전량 비어있지 않음) | ✅ |
| 관련 단원 연결 | `ConceptStandardLink`(443건, FK CASCADE) + `atom_node.standard_codes[]`(역방향) | ✅ |
| 난이도 | 컬럼 0. 유사 스케일 3종이 **다른 노드**에 분열(`atom_node.intrinsic_difficulty` 1~5 / `concept_node.difficulty_tier` 0~24 / `problem.irt_difficulty_b`) | △ (§4-④) |
| 중요도 | 컬럼 0. 유사한 것은 `concept.weight_in_curriculum`·`concept.exam_frequency`(개념 쪽에만) | △ (§4-④) |
| 키워드 | 컬럼 0 | △ (§4-④) |
| 개념 태그 | 직접 컬럼은 없으나 `ConceptStandardLink` 443건 + `atom_node.standard_codes[]`로 역방향 연결 완비 | ✅(간접 충족) |
| 평가 유형 | 성취기준엔 없음. `curriculum_entry.is_assessed`(bool)·`assessment_format`(str)에만 존재(개념 셀 쪽) | △ (§4-④) |
| AI 임베딩 | `concept_embedding`·`atom_embedding`·`problem_embedding`·`misconception_embedding` 4종은 있으나 **`standard_embedding`은 없음** | △ (§4-④) |
| (외부 틀엔 없으나 실측된 축) 성취수준(A~E)·평가기준(상/중/하) | 저장소 전체 **0건**. 상류 도구(`curriculum-node-builder` 스킬)는 이미 산출 가능하나 반입 안 됨 | ⚠️ → **D3** |

### 모듈 4 — 학습목표(Objective) 관리 (메타데이터: 행동동사·Bloom Level·난이도·선수학습·평가방법·교수전략추천·AI생성Prompt)

| 메타데이터 | WhyMath 현행 | 판정 |
|---|---|---|
| 성취기준→Objective 세분화(스키마·컴파일러·런타임) | `LearningObjective`+`UnitDSL`+`unit_compiler.py`+런타임 API(`/v1/me/objectives/{id}/study`,`/outcome`)까지 **완비** | ✅ |
| 성취기준→Objective 세분화(**데이터**) | 895건 중 **1건**(4개 목표)만 분해 — 커버리지 ≈0.1% | ⚠️ → **D2** |
| 행동동사 | `source_verb`(자유 텍스트 1칸, 사람이 수기 병기). 동사→k_type 자동 매핑 사전 없음 | △ (§4-⑦) |
| Bloom Level | `schema/enums.py BloomLevel` 6단계 **존재하나 `Problem.bloom_level`에만 부착**, `LearningObjective`엔 컬럼 없음 | ⚠️(§4-⑥, 이관 신호 부재) |
| 난이도 | `LearningObjective`엔 없음(위 성취기준 난이도 분열과 동일 공백) | △ (§4-④) |
| 선수학습 | `LearningObjective.concept_nodes[]`(atom_node code 배열)로 간접 연결 | ✅ |
| 평가방법 | `exit_evidence`(JSONB) — 목표별 종료 증거 슬롯 | ✅ |
| 교수전략 추천 | `k_type`(7유형: CONCEPT/PROCEDURE/REPRESENT/PROOF/MODELING/SPATIAL/STOCHASTIC) → `l4/pedagogy/k_type_resolver.py`가 전략 조회에 소비 | ✅ |
| AI 생성 Prompt | `slot_manifest`·`phase_overrides`(JSONB) — 목표별 생성 슬롯 재정의 | ✅ |

### 모듈 5 — 선수학습 관계 그래프 (관계: prerequisite·related·similar·extends·contains·equivalent)

| 관계/기능 | WhyMath 현행 | 판정 |
|---|---|---|
| `prerequisite` | `EdgeType.PREREQUISITE` 실적재(원자 백본 2,210건 + 개념 축 581건), **재귀 CTE 다단계 traversal + Kahn 위상정렬**까지 완비(`l2/prerequisite_recommendation.py`·`l2/learning_path.py`) | ✅ **초과**(외부 틀은 단순 방향 그래프만 요구, WhyMath는 위상정렬 학습 순서까지 생성) |
| `related`/`similar` | 없음 — CLAUDE.md 명문 금지("`similar_to`/`related_to`를 traversal에 사용 금지") | 🚫 §2-② |
| `extends` | `EdgeType.EXTENDS` **어휘만 선언**, 적재 0(적재기가 명시적으로 skip) | ⚠️(페이퍼, §3 페이퍼 갭) |
| `contains` | 그래프 엣지로 표현 안 함 — 계층 포함은 `atom_node.parent_code`/`concept.parent_concept_id` **컬럼**으로 이미 표현 중 | 🚫 §2-③ |
| `equivalent` | 그래프 엣지로 표현 안 함 — 동치는 `l3/equivalent/canonicalize`(SymPy)가 유일 권위(CLAUDE.md "동치 판정은 구조가 정본") | 🚫 §2-④ |
| 부족한 선수학습 자동 탐지 | `recommend_prerequisite_gaps`(mastery 조인 + depth 재귀) | ✅ |
| 맞춤 복습 추천 | 동상 + `AxisExclusions`(축 밖 투명 집계) | ✅ |
| 개념 경로 추천 | `l2/learning_path.py`(Kahn 위상정렬, 사이클 방어 잔여 처리) | ✅ **초과** |
| 학습 로드맵 생성 | 동상 | ✅ |
| 오개념 원인 추론 | 오개념은 독립 DB(`misconception_catalog`)로 원칙6에 따라 분리 — 그래프 엣지가 아니라 reactive retrieval | ✅(설계상 대체 경로) |

### (횡단) 관리·편집 인터페이스

`/v1/concepts` CRUD 5개(`RequireContentAdmin`)가 유일한 사람-편집 경로. 성취기준·단원·목표·
교육과정 셀 편집 API는 **0** — 전부 CLI 배치 populate(YAML→upsert 단방향, `l1/standards/populate.py`
등 6개 모듈). 이는 §2-⑥(의도적 미채택)으로 분류한다.

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | 학기(semester) 축 재도입 | **영구 불채택.** 원칙5 Curriculum-as-Overlay에 따라 마이그레이션 `20260630_1200_d1e2f3a4b5c6`으로 `Concept.semester_introduced`를 이미 드롭. `curriculum_loader.py:4-8`이 "노드는 의미만·교육과정은 Overlay"로 재도입을 명시적으로 막는다. |
| ② | `related`/`similar`를 선수학습 그래프 traversal 관계로 채택 | **영구 불채택.** CLAUDE.md 구조 붕괴 방어 절칙: "`similar_to`/`related_to`를 traversal에 사용 금지" — 관계 폭발(N²)의 1순위 원인으로 명문 금지. |
| ③ | `contains`를 별도 그래프 엣지 타입으로 신설 | **영구 불채택(중복 표현 금지).** 계층 포함은 `atom_node.parent_code`/`concept.parent_concept_id` 컬럼으로 이미 표현 중 — 같은 의미를 엣지+컬럼 이중 표현하면 유지보수 지옥(7대 붕괴 연쇄 ③)의 시작점. |
| ④ | `equivalent`를 별도 그래프 엣지 타입으로 신설 | **영구 불채택(이중 진실 원천 금지).** CLAUDE.md "표현≠의미": 동치 판정은 `l3/equivalent/canonicalize`(SymPy)가 유일 정본. 그래프 엣지로 병행 표현하면 진실 원천이 둘이 된다. |
| ⑤ | 다국가 교육과정 풀스케일(9~12개국) 즉시 구축 | **조건부 유보(Phase 3).** `docs/data/curriculum_matrix.md`가 이미 "Phase 1 = 한국 + 참고용 미국·IMO만"으로 축소 확정(2026-05-14 MEMORY 결정 로그). 이번 리뷰는 재론하지 않고 기존 결정을 승계한다. 발화 조건은 §5-①. |
| ⑥ | 사람 편집 GUI(Drag&Drop 트리 편집·단원 이동/병합/분리) | **조건부 유보.** 콘텐츠 파이프라인 전체가 "YAML=소스, DB=산출물, 단방향 populate"로 통일돼 있다(`l1/standards/populate.py`·`l1/pedagogy/populate.py`·`l1/atom_graph/populate.py` 등 6개 모듈 동일 골격). 사람 편집이 필요하다는 신호(populate 오류율·수작업 요청 빈도)가 실측되기 전까지 GUI를 만들면 "입력 없는 파이프라인"이 된다. 발화 조건은 §5-②. |

---

## §3. 진짜 갭 설계

### D1 — 교육과정 개정판 표기 3어휘 분열 (최우선·`CUR-01`)

**문제**: 같은 의미("2022 개정 교육과정")를 가리키는 문자열이 3개 어휘 공간에 흩어져 있다.

| 위치 | 표기 |
|---|---|
| `achievement_standard.curriculum_revision`, `curriculum_entry.curriculum_revision` | `"2022 개정"`(한글, 공백 포함) |
| `unit_spec.curriculum_rev` | `"2022"`(연도만) |
| `schema/enums.py Curriculum`(→ `Problem.curriculum_version`) | `"2022_REVISION"`(영문 enum 값) |

세 번째 것만 진짜 Python enum이고 나머지 둘은 자유 문자열(str/String)이라 오탈자·공백 변형에도
DB 제약이 걸리지 않는다. `l6/school_progress/gating.py:187-189`가 이미 `normalize_enum_value`로
`Problem.curriculum_version`과 게이팅 인자를 비교하며 방어하고 있지만, 이는 **그 한 지점의
국소 방어**일 뿐 세 어휘 공간 전체의 정합은 한 번도 관측된 적이 없다.

**왜 지금까지 안 드러났는가**: `AchievementStandard`↔`UnitSpec`↔`Problem`이 서로 다른 조인
경로로 소비되고(성취기준 코드 매칭·gating 필터·문항 태깅), 세 축을 동시에 교차 조회하는 코드
경로가 존재하지 않는다. 각 축은 자기 안에서는 일관돼 보인다(`AchievementStandard` 내부는
`curriculum_revision` UNIQUE 제약으로 정합, `Problem.curriculum_version`은 enum이라 오탈자
불가). **분열은 축 사이(cross-table)에서만 보인다** — 이것이 ARCH-13(개념/원자 이중 진실
원천)과 같은 형태의 문제이며, ARCH-13이 code 문자열 조인에서 겪었던 것과 동일한 종류의 위험을
표기 문자열에서 겪고 있다.

**정합 설계(신규 스키마 0)**: 3어휘 공간을 함께 스캔해 발산 지점을 세는 **관측 리포트**를
`harness/`에 추가한다(`problem_bank_coverage.py`가 이미 쓰는 빌드타임 집계 패턴 재사용 — 신규
로직은 정규화 매핑 표 하나뿐). 스키마·마이그레이션 변경은 0이다 — 지금은 "몇 건이 어느 축에서
불일치하는가"만 드러내는 게 목표다(측정 없는 도입 없음).

**dead code 금지 충족**: 리포트는 기존 3개 테이블을 그대로 읽고 기존 정규화 유틸
(`_shared.normalize_enum_value` 패턴)을 재사용한다. 신규 상수는 3어휘 crosswalk 매핑 표
하나뿐이며 즉시 리포트에 소비된다.

**변별력**: 세 어휘 중 하나를 의도적으로 다른 값으로 바꿔 발산 건수가 실제로 증가/감소하는지
확인한다. 성공/실패가 같은 값을 내면 검증이 아니라 위장이다.

**acceptance 후보**:
1. 현행 실측 고정: 3개 테이블에서 각 축의 고유 표기 값 집합을 뽑아 실제로 3어휘인지 재현
   (주장 확인 또는 반증 — 반증되면 범위 재조정)
2. 정합 설계 본체: crosswalk 매핑 표 + 발산 건수 리포트, 신규 스키마 0
3. CI 배선 실재 확인: 신규 워크플로 없이 기존 harness 잡에 편입되는지(OPS-03·OPS-10 선례 —
   "저장소에 존재함"과 "돌아감"은 다르다)
4. 변별력: 위 서술대로
5. 범위 밖 명시: 3어휘를 1어휘로 **통합하는 마이그레이션**은 이 태스크에 포함하지 않는다
   (발산 규모가 관측되기 전에는 통합 방식(FK 신설 vs 정규화 함수)을 결정할 수 없다)

**의존**: 없음(즉시 착수). **태스크**: 신설 — `CUR-01-curriculum-revision-vocabulary-consistency`.

---

### D2 — 학습목표(Objective) 커버리지 0.1% (`CUR-02`)

**문제**: `LearningObjective` 스키마·`unit_compiler.py` 컴파일러·런타임 API
(`/v1/me/objectives/{id}/study`, `/outcome`)까지 **완비**됐는데, 실데이터는 성취기준 895건 중
**1건**(소단원 `10공수1-이차함수-최대최소`, 목표 4개: CONCEPT/PROCEDURE/REPRESENT/MODELING
4유형 파일럿)뿐이다. 이는 NLP/REC 갭 리뷰 §6이 누적해 온 "완비된 소비 경로 + 미도달 공급원"
패턴의 **7회차**다(아래 §6 참조).

**왜 아무도 몰랐는가 — 변별력 없는 실패**: 소단원 DSL 컴파일러는 파일럿 1건에 대해 완벽하게
동작한다(`unit_compiler.py` E2E 확인 완료 — `_provenance.json`이 "소단원 DSL 컴파일러 v0.1
E2E 확인용 단일 소단원"이라고 스스로 밝힘). 즉 **파이프라인이 고장난 게 아니라 파일럿 스코프가
의도적으로 1건이었고, 그 이후 확장이 없었을 뿐**이다. 실패가 아니라 정지 상태라 오류 신호가
전혀 없다 — 이것이 "완비된 소비 경로 + 미도달 공급원"이 3~6회차와 다른 점이다(OCR·시각화·추천은
런타임 실패/미배선이었지만, 이건 **파일럿 성공 이후 확장이 안 된 것**이다).

**핵심 판단**: 목표 분해를 자동 생성하는 파이프라인을 지금 만들지 않는다(REC D3·D4 "입력 없는
파이프라인을 만들지 않는다" 선례 준수 — 성취기준→Objective 분해는 사람 검수가 필요한 교수학적
판단이라 LLM 자동생성 전에 "몇 건이 이미 됐고 몇 건이 남았는가"부터 드러나야 한다).

**정합 설계(신규 스키마 0)**: `ARCH-18`(문제은행 커버리지 리포트, `harness/problem_bank_coverage.py`)
패턴을 그대로 재사용해 **성취기준 × Objective 커버리지**를 빌드타임 관측 리포트로 낸다 —
895건 중 몇 건이 `UnitSpec.standard_codes`에 걸려 있는지, k_type별 분포는 어떤지.

**변별력**: 소단원 1건을 추가 반입했을 때 커버리지 % 수치가 실제로 움직이는지 확인한다.

**acceptance 후보**:
1. 현행 실측 고정: 895건 중 1건(0.11%) 커버리지 재현
2. 정합 설계 본체: 커버리지 % + k_type 분포 리포트, 신규 스키마 0
3. CI 배선 실재 확인(OPS-03·OPS-10 패턴 재사용)
4. 변별력: 위 서술대로
5. 범위 밖 명시: 목표 분해 **자동 생성**은 이 태스크에 포함하지 않는다(§5-⑥에 발화조건 기록)

**의존**: 없음. **태스크**: 신설 — `CUR-02-objective-coverage-observability`.

---

### D3 — 성취수준(A~E)·평가기준(상/중/하) 데이터 반입 (`CUR-03`, owner=kiki)

**문제**: `curriculum-node-builder` 스킬(사용자 전역 `~/.claude/skills/curriculum-node-builder/`)은
KICE(한국교육과정평가원) 평가기준·성취수준 개발 보고서 PDF를 `교과→영역→성취기준→평가기준(상/중/하)
또는 성취수준(A~E)` 노드 엑셀로 변환하는 **완성된 도구**다. 산출 시트명 `성취기준_목록`은
`achievement_standards_v1.md`가 인용하는 File A xlsx의 시트명과 **정확히 같다** — 동형 도구
계보일 가능성이 높다. 그런데 이 축(등급 A~E, 상/중/하)이 `AchievementStandard` 정본 스키마
(Pydantic·ORM 모두)에 **필드 0**, 코퍼스에 **0건**이다. NCIC 교육과정 원문 자체도 이 축을 갖지
않는다 — 평가기준·성취수준은 KICE가 **별도로** 개발·공표하는 보고서이지 교육과정 고시 본문이
아니다.

**핵심 판단(NCIC 403 차단 선례 적용)**: `docs/data/ncic.md` §3.1이 이미 기록한 대로, NCIC
포털은 자동 크롤을 차단한다("NCIC PDF는 반드시 사람이 다른 환경에서 받아 레포에 반입"). KICE
평가기준·성취수준 개발 보고서도 동일하게 **사람이 직접 확보해야 하는 소스**다. "측정 없는 도입
없음" 원칙상, 데이터가 반입되기 전에 스키마(`assessment_criteria`·`achievement_level` 컬럼 등)
부터 만들지 않는다 — 스키마가 어떤 모양이어야 하는지는 실제 반입된 데이터의 구조(성취기준 1개당
등급이 몇 개인지, 상/중/하 3단과 A~E 5단이 공존하는지)를 보고 나서 정해야 날조를 피한다.

**정합 설계**: 이 태스크는 **반입까지만**을 스코프로 하고, owner=kiki로 등재한다.

**acceptance 후보**:
1. Kiki가 KICE 평가기준/성취수준 개발 보고서 PDF를 확보
2. `curriculum-node-builder` 스킬로 노드 엑셀(`노드_계층표`·`노드_트리구조`·`성취기준_목록`)
   변환 완료
3. 산출 엑셀을 `data/` 아래 반입 + 라이선스·출처 카드 동반(공공누리 유형 확인 — KICE 보고서의
   실제 라이선스는 NCIC와 다를 수 있어 반입 시 재확인 필요)
4. 반입 후 `AchievementStandard` 스키마 확장(신규 컬럼·마이그레이션)은 **별도 후속 태스크로
   분리 등재**한다 — 이 태스크의 done 조건에 포함하지 않는다(스코프 고정, 데이터가 먼저·스키마가
   나중)

**의존**: 없음(사람 액션 우선, 즉시 착수 가능). **태스크**: 신설 —
`CUR-03-achievement-level-data-intake` (owner: kiki).

---

### 페이퍼 갭 — `PREREQUISITE` 외 5종 관계 타입 미적재 (**페이퍼 — 코드 0 · 태스크 신설 없음**)

`EdgeType` enum에 `COMPOSED_OF`/`ANALOGOUS_TO`/`EXTENDS`/`CONTRASTS`/`TRIGGERS_DISTRACTOR`
5종이 이미 선언돼 있지만 적재기(`l1/concept_graph/backend_edge.py:29`,
`l1/atom_graph/atom_backend_edge.py:75`)가 `relation == "prerequisite"`가 아니면 명시적으로
skip한다. 이는 관계 타입 폭발(CLAUDE.md 금기)과 무관하다 — 6종은 이미 5~8개 범위 안이고, 문제는
**소스 코퍼스에 해당 관계의 신호 자체가 없다**는 것이다. 신호 없이 채우면 교수학 날조가 된다
(원칙: "오개념을 초기 context에 preload 금지 — reactive retrieval만"과 같은 계열의 금기 —
근거 없는 관계를 미리 채우지 않는다).

**의도**: 이 5종은 데이터가 아니라 **어휘가 먼저 준비된 상태**로 유지한다. 실제 소스(예: 오개념
교차링크가 `TRIGGERS_DISTRACTOR`로 재해석될 수 있는 시점, 심화 개념 데이터가 `EXTENDS`로 적재될
시점)가 생기면 그때 적재기 필터 한 줄만 풀면 된다 — 스키마·enum은 이미 완비돼 있다. 발화 조건은
§5-④.

### §3 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `CUR-01-curriculum-revision-vocabulary-consistency` | D1 | S3 | 2 | 3어휘 표기 분열 — 유지보수 지옥(7대 붕괴 연쇄 ③) 선행 관측. 스키마 통합은 범위 밖(acceptance ⑤) |
| `CUR-02-objective-coverage-observability` | D2 | S3 | 2 | 학습목표 커버리지 0.1% — "완비된 소비 경로 + 미도달 공급원" 7회차(§6). 자동 생성은 범위 밖 |
| `CUR-03-achievement-level-data-intake` | D3 | S1 | 3 | 성취수준·평가기준 축 0건 + 상류 도구 존재. NCIC 403 선례에 따라 owner=kiki, 데이터가 스키마보다 먼저 |

태스크는 전건 `backlog.py add` CLI 경유로 등재한다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (7종)

① **단원 순서(sort order)·이동/병합/분리·버전 비교 연산** — `db/models/` 전체에 순서 컬럼이
   0개이고 관리 API 자체가 없는 현 단계에서는 "무엇을 이동/병합/비교할 화면"이 없다(`UnitSpec`이
   버전을 *보존*만 할 뿐 비교 연산은 없는 것도 같은 공백). 발화 조건 §5-②.
② **단원 Tree/Graph 뷰어(GUI)** — API(`GET /v1/concepts/{id}/edges`)는 있으나 사람이 보는
   화면이 없다. §2-⑥과 같은 사유로 유보. 발화 조건 §5-②.
③ **적용년도 종료일(`effective_to`)·폐기여부(`deprecated`) 필드** — 2015/2022 개정은 **공존**
   상태이지 한쪽이 다른 쪽을 "대체(폐기)"한 것으로 데이터에 표시된 적이 없다. 폐기 신호가 실측된
   적 없는 상태에서 필드를 만들면 항상 NULL인 죽은 컬럼이 된다(dead code 금지). 발화 조건 §5-③.
④ **성취기준 난이도·중요도·키워드·평가유형·임베딩** — `curriculum_loader.py:35-38`가 이미
   같은 원칙을 명문화했다: "미매핑(소스에 신호 없음·날조 금지)" 목록에 `cognitive_level`·
   `is_assessed`·`assessment_format` 등을 열거하며 채우지 않는다고 선언한다. 성취기준 쪽도
   동일하다 — NCIC 원문에 난이도·중요도 숫자가 없다(`LearningObjective`의 난이도 공백도 동일
   가족). 발화 조건 §5-⑤.
⑤ **학습목표(Objective) 자동 생성 파이프라인** — 성취기준→Objective 분해는 교수학적 판단이라
   사람 검수가 선행돼야 한다(REC D3·D4 "입력 없는 파이프라인을 만들지 않는다" 선례). CUR-02가
   먼저 "몇 건 남았는지"를 드러낸 뒤에 논의한다. 발화 조건 §5-⑥.
⑥ **Bloom Level을 `LearningObjective`에 부착** — 현재 `Problem.bloom_level`에만 있고
   `LearningObjective`엔 컬럼이 없다. 이관 필요성 신호(예: k_type_resolver가 Bloom을 소비하려는
   시도)가 실측된 적 없어 지금 컬럼을 추가하면 죽은 컬럼이 된다.
⑦ **행동동사(behavioral verb) → k_type 자동 매핑 사전** — `source_verb`는 사람이 자유 텍스트로
   수기 입력한다(예: `"이해한다"` + `k_type: CONCEPT`을 YAML에 병기). 파일럿 1건(4개 동사)만으로
   사전을 만들면 과적합이다 — CUR-02가 반입량을 늘린 뒤 재논의.

---

## §5. 유보 항목의 발화 조건 (지금 안 만들되, 언제 만드는지)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | **다국가 풀스케일**(§2-⑤) | 한국 외 2개국 이상의 실사용 신호(해외 학생 유입·제휴 협의)가 실측되면. 순서를 바꾸지 않는다 — 수요가 먼저다. |
| ② | **단원 관리 GUI·이동/병합/분리**(§2-⑥·§4-①②) | `CUR-01`·`CUR-02` 관측 결과 CLI populate만으로 감당 안 되는 수작업 신호(반복 오류·수동 보정 빈도 상승)가 실측되면. |
| ③ | **폐기여부/종료일 필드**(§4-③) | 다음 교육과정 개정(2028 예정)이 시행돼 특정 성취기준이 실제로 "대체(superseded)"로 표시돼야 하는 순간. 미리 필드를 만들지 않는다 — 이벤트가 먼저다. |
| ④ | **`PREREQUISITE` 외 5종 관계 적재**(§3 페이퍼) | 오개념 교차링크(`misconception_crosslink`)·심화 개념 데이터(`EXTENDS` 후보)·유사문제 계보 중 하나라도 소스 신호가 실측되면. 적재기 필터 한 줄만 풀면 되도록 어휘는 이미 준비돼 있다. |
| ⑤ | **성취기준 메타(난이도·중요도·키워드·평가유형·임베딩) 파생**(§4-④) | 원자/개념/문항 3개로 분열된 난이도 스케일이 통합(ARCH-13류 감사)된 이후, 그 통합 규칙으로 성취기준 난이도를 **파생**할 수 있게 되면(직접 입력이 아니라 파생임을 명시). |
| ⑥ | **학습목표 자동 생성**(§4-⑤) | `CUR-02` 관측이 커버리지 확대 필요를 수치로 보여주고, 사람 검수 워크플로(리뷰 큐)가 먼저 설계된 뒤. 순서를 바꾸지 않는다 — 관측이 먼저다. |

---

## §6. 반복 실수 — "완비된 소비 경로 + 미도달 공급원" 4~7회차 (재발방지 등재)

`ai_recommendation_module_gap_review.md` §6의 6회차 표를 7회차로 확장한다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| 4 | `POST /v1/me/attempts` 클라 호출 0회 → 학습자 모델 입력 0(REC D1) | 만들고 **입력을 잇지 않음** |
| 5 | 개인화 가중 기본 off · 개념 추천 API 6종 클라 소비 0(REC D1) | 만들고 **켜지 않음** |
| 6 | `select_probe` 후보 공급원 0 → 도구6 상시 실패(REC D2) | 만들고 **공급원을 잇지 않음** |
| **7** | **`LearningObjective` 스키마·컴파일러·런타임 API 완비 + 실데이터 895건 중 1건(D2)** | 만들고 **분해하지 않음** |

7회차는 앞선 여섯과 다른 점이 하나 있다: **처음부터 "파일럿"이라고 스스로 밝힌 상태**다
(`_provenance.json` "E2E 확인용 단일 소단원"). 즉 이번 사례는 "고장났는데 몰랐다"가 아니라
"파일럿 성공 이후 확장 논의가 없었다"는, 앞의 여섯과 다른 종류의 정지다. 그래도 공통 구조는
같다 — **소비측(런타임 API·컴파일러)이 완비돼 있어서 "존재함"이 "돌아감"으로 읽힌다.**

---

## §정정 — 정본 stale 6곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `docs/data/concept_graph.md:5` | "**상태: 미구축.** 이 카드는 *목표 명세*다. Phase 1에 고1 미적분 영역만 착수한다." 목표 500노드·2,000엣지 | `concept_graph_v1` 437노드·581엣지 커밋·적재 완료(2026-06-20 e2e 승격). `atom_graph_v1` 2,683노드·2,210엣지. `knowledge_module_gap_review.md`가 이미 "원자 백본 2,697(runtime truth source)"로 정본화 |
| `docs/architecture/01_data_foundation.md:14,192`·`docs/data/ncic.md:19` | 성취기준 "약 150~180개"(2022 개정 수학과) | 코퍼스 실측 **895건**(2022:435/2015:460) — `achievement_standards_v1.md`가 이미 정본화. 같은 `ncic.md` 문서 §2.2 안에서도 895건 DDL이 서술돼 **문서 내부 모순** |
| `docs/architecture/00_overview.md:165,173`·`01_data_foundation.md:73` | 개념 그래프 저장소 = **Neo4j**(배포 토폴로지 DB 블록) | `l1/concept_graph/retrieval.py:16`·`l1/concept_graph/node_projection.py:14` "메타 브리지 = PG 프로젝션(**확정 설계 결정 — backend↔Neo4j 런타임 연결 안 함**)". 프로덕션 compose에 Neo4j 서비스 없음 |
| `docs/data/curriculum_matrix.md` §2.2/§2.4 | `CurriculumEntry` "**30필드**", 셀 PK "(`concept_id`,`country_code`)" 2-튜플, 모델 위치 "**(미구현)**" | `schemas/v1.1/curriculum_entry.schema.yaml:35` `field_count: 31`("PRD 30개 + subject 1개"). ORM PK는 `entry_id` 단일 PK + `UniqueConstraint(concept_id, country_code, subject)` 3-튜플(`db/models/curriculum_entry.py:9-11`). 백엔드 loader·resolver·마이그레이션 구현 완료 |
| `docs/strategy/prd_v1.2.md` 전반 | "2015 개정 → 2022 개정" 전환을 **미래(2027~2028년 v2.0 분기)** 대응 대상으로 서술 | `docs/data/curriculum_2022_revision.md`(2026-05-27)가 이미 "핵심 K-12 학년 9개 중 7개가 2022 개정 적용 → 백본은 반드시 2022 우선"으로 확정. `ncic.md`·`achievement_standards_v1.md`도 2022를 현재 백본으로 취급 |
| `docs/architecture/01_data_foundation.md:159`(원칙: "모든 데이터셋은 `docs/data/[name].md`에 카드 작성") | 규칙만 있고 예외 없음 | `data/corpus/units_v1/`(소단원 DSL 파일럿, `_provenance.json` 보유)에 대응 데이터 카드가 **없음** — 이번 PR에서 `docs/data/units_v1.md` 신설로 정정 |

세 번째(Neo4j)와 다섯 번째(2015 개정 현행 전제) 두 항목은 "실제보다 낡은 세계관을 정본이 계속
서술한다"는 같은 방향의 stale이다 — 코드·데이터는 이미 앞서 있는데 문서가 과거 계획 시점에
멈춰 있다. **stale을 고치는 행위 자체가 다른 규칙과 부딪히는 지점은 없었다** — 6곳 모두 병렬
세션이 claim한 범위(`PED-10`·`S3-24/25`·`S4-10`)와 겹치지 않아 이 PR에서 바로 인라인 정정한다.

---

## 부록 — 실측 근거 (2026-08-03 실측)

**성취기준 코퍼스**
- `data/corpus/standards_v1/standards.json` — `standards` 895건, `curriculum_revision` 분포
  `{"2022 개정": 435, "2015 개정": 460}`, `school_type` 분포 `{고등학교: 525, 초등학교: 249,
  중학교: 121}`, `subject` 27종. `effective_from`·`commentary`·`big_idea`·`parent_codes`
  전량 미충전(0건) — 미매핑 명시 정책과 일치.
- `data/corpus/standards_v1/concept_standard_links.json` — `links` 443건, 전량 `link_type: "직접"`.
- `data/corpus/standards_v1/_provenance.json` — 출처 "교육부 고시 제2022-33호, NCIC", 라이선스
  공공누리 제1유형.

**개념·원자 그래프**
- `data/corpus/atom_graph_v1/graph.json` — `concepts` 2,683건, `edges` 2,210건(전량
  `relation: "prerequisite"`).
- `data/corpus/concept_graph_v1/graph.json` — `concepts` 437건, `edges` 581건(전량
  `relation: "선수(prereq)"`).
- `src/backend/whymath_backend/schema/enums.py` `EdgeType` — 6종 선언(`PREREQUISITE`·
  `COMPOSED_OF`·`ANALOGOUS_TO`·`EXTENDS`·`CONTRASTS`·`TRIGGERS_DISTRACTOR`), 적재는
  `PREREQUISITE`뿐(`l1/concept_graph/backend_edge.py:29`·`l1/atom_graph/atom_backend_edge.py:75`).

**소단원 DSL·학습목표**
- `data/corpus/units_v1/quadratic_maxmin.unit.yaml` + `_provenance.json` — `{"units": 1,
  "objectives": 4}`, 4목표 4유형(CONCEPT/PROCEDURE/REPRESENT/MODELING) 파일럿.
- `src/backend/whymath_backend/db/models/pedagogy_dsl.py` `UnitSpec`·`LearningObjective` —
  복합 PK/FK, `k_type`·`k_type_secondary`(PG native enum) 스키마 완비.
- `src/backend/whymath_backend/api/study.py` — `/v1/me/objectives/{id}/study`,`/outcome`
  런타임 소비 확인.

**교육과정 버전 표기**
- `src/backend/whymath_backend/db/models/achievement_standard.py` — `curriculum_revision:
  sa.String(16)`, 값 `"2022 개정"`/`"2015 개정"`.
- `src/backend/whymath_backend/db/models/pedagogy_dsl.py` `UnitSpec.curriculum_rev` — `Text`,
  값 `"2022"`.
- `src/backend/whymath_backend/schema/enums.py` `class Curriculum(str, Enum)` — 값
  `"2022_REVISION"`(`Problem.curriculum_version` 전용).
- `src/backend/whymath_backend/l6/school_progress/gating.py:187-189` — `normalize_enum_value`로
  `curriculum_version` 비교, 국소 방어만 존재.

**교육과정 Overlay 설계**
- `src/backend/whymath_backend/db/models/curriculum_entry.py` — `CurriculumEntry`
  31필드, PK `entry_id`, `UniqueConstraint(concept_id, country_code, subject)`.
- `src/backend/whymath_backend/l1/curriculum/curriculum_loader.py:4-38` — Overlay 설계 근거
  및 "미매핑(소스에 신호 없음·날조 금지)" 필드 목록 명문화.
- 마이그레이션 `20260630_1200_d1e2f3a4b5c6`(semester/grade 드롭)·`20260630_1600_f3a4b5c6d7e8`
  (subject/curriculum_version 드롭).

**관리 API**
- `src/backend/whymath_backend/app.py:792-806` — 등록 라우터 목록, 교육과정/단원/목표 전용
  라우터 부재 확인.
- `src/backend/whymath_backend/api/concepts.py` — `Concept` CRUD 5개(`RequireContentAdmin`),
  유일한 사람-편집 경로.

**상류 도구**
- `~/.claude/skills/curriculum-node-builder/SKILL.md` — KICE 평가기준/성취수준 PDF→노드 엑셀
  변환 도구, 산출 시트 `노드_계층표`·`노드_트리구조`·`성취기준_목록`(File A xlsx 시트명과 일치).
