# 개념(Knowledge) 관리 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-27)

> **범위**: 외부 참고 문서 『0단계 — 개념(Knowledge) 관리 모듈』(모듈 6~10: Concept DB ·
> Definition · Theorem · Formula · Knowledge Graph — **WhyMath 전용이 아닌 일반적 EOS 틀**,
> Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식
> (플레이북 2대 철칙·8대 구조원칙·저작권 redaction·검증 권위·dead code 금기) 안에서 설계한 기록.
> **형식**: `part2_node_design_review.md`·`edge_design_part3_review.md`(갭 분석→판정→설계) 답습.
> **결론**: 모듈 6·9·10은 대부분 충족(일부는 더 엄격하게 구현됨), 모듈 7이 최대 갭,
> 모듈 8은 의도적 연기이나 설계 공백. 문서 항목 다수는 **의도적 미채택**(협상 불가 불변식 충돌).
> 진짜 갭 5건을 설계(D1~D5)하고 실행 4건을 백로그에 등재했다.

관련 정본: `concept_node_layering_decision.md`(9계층 ADR·12노드 승격 이력) ·
`docs/data/concept_graph.md` §2.2b(관계 어휘 crosswalk) · `MEMORY.md` 결정 로그(2026-07-27).

---

## §1. 모듈 6~10 ↔ WhyMath crosswalk 판정

### 모듈 6. 개념(Concept) DB — **대부분 충족**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 표준 Concept 객체 | 런타임 정본 `db/models/concept.py:53`(`concept` 테이블) + 9계층 ADR. 원자 백본 2,697(runtime truth source) + 구 437(`legacy_snapshot`) | ✅ |
| Concept ID | canonical `math.<area>.<slug>`(교육과정·언어 독립·`ids.yaml` registry — Part 9 준수) | ✅ (문서의 `C-ALG-001`형보다 엄격) |
| 개념명·영문명·별칭 | `name_ko`/`name_en`/`aliases`. 저작 노드는 표시명 비내장 — `locales/{ko,en,ja}.json` 단일 진실 | ✅ |
| 학년·교육과정 | **노드 비내장** — `CurriculumEntry` Overlay(`db/models/curriculum_entry.py:76`)가 단일 진실. 노드의 `grade_introduced`·`subject`·`curriculum_version`은 제거됨 | 🚫 의도적 미채택 §2-①|
| 난이도 | `intrinsic_difficulty`(노드)·`difficulty_tier`(assessment 계층) | ✅ |
| 대표 기호·설명·그림 | 기호/표기 = semantic `representations`(self-authored). 설명 = `ConceptContent`(참조·본문 근접 서술 노드 금지). 그림 = `visualization_card_keys` 참조 키 | ✅ (Concept Purity 형태로) |
| 생성일·수정일·버전 | `created_at` + 코퍼스 버전(`*_v1`)·`_provenance.json`·`review_status`·git이 버전 정본. per-row 버전 필드 없음 | 🚫 의도적 미채택 §2-② |
| 다국어 관리 | locale 분리(P2d) — ko/en/ja | ✅ |
| 중복 개념 검사 | **부재** — 임베딩 기반 중복 후보 리포트 없음 | ⚠️ 갭 → **D4** |
| 유사 개념 탐색 | pgvector `ConceptEmbedding`/`AtomEmbedding` + `GET /v1/concepts/search`(`api/concepts.py:161`) | ✅ |
| 생성·수정·삭제 | populate 멱등 upsert + API PATCH/DELETE(`api/concepts.py:330,379`) | ✅ |

### 모듈 7. 정의(Definition) 관리 — **최대 갭**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 개념당 다중 정의(학교/대학/집합론/직관/비유/초등/영재) | `ConceptContent`에 단일 `formal_definition_internal`(학생 비노출)·`metaphor`·`explanation`만. 레지스터별 정의 변형 구조 부재 | ⚠️ 갭 → **D1** |
| 정의 저장 구조(종류·난이도·본문·수식·그림·예시·반례) | 예시·반례 슬롯 부재 | ⚠️ 갭 → **D1** |
| 난이도별 정의 선택 | 부재(소비 로직 없음) | ⚠️ 갭 → **D1** (소비처 슬라이스 동반) |
| 정의 비교·검색·버전 | 부재 — 단 검색은 D1 착지 후 기존 임베딩 축(chunk) 연동으로 해소(§4) | ⚠️ D1 후속 |
| 자동 정의 생성 | AI 생성 자체는 가능하나 **무검증 학생 노출 금지** — `review_status=ai_estimated` + 검수 게이팅 필수 | 🚫 의도적 제약 §2-③ |
| 교과서·교육과정 정의 인용 | **금지** — 성취기준·교과서 본문 근접 텍스트 저장 금지(redaction). self-authored만 | 🚫 의도적 미채택 §2-③ |

### 모듈 8. 정리(Theorem) 관리 — **의도적 연기 + 설계 공백**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| Theorem 노드(조건·결론·수식·증명·직관·활용·역사·난이도) | **미승격** — 12노드 taxonomy 중 유일 잔여(P6 `TheoremNode≠ProofNode`·scope 제외 판정 `math_dsl_principles_review.md` §3.8). `S4-02-proof-learning-support`(todo) 존재하나 노드·데이터 설계 백지 | ⚠️ 설계 공백 → **D2** (페이퍼 설계 선행·코드 0) |
| 증명 단계 저장·증명 유형 분류 | 부재(위와 동일 축) | D2에 포함 |
| AI 증명 생성 | 학생 대면 무검증 증명 확언 **금지**(unverifiable 정직 경계·"네 증명이 맞다" 허위 확언 금지). 형식증명은 WH-S Tier3(Lean)·S5 | 🚫 의도적 제약 §2-④ |
| 자동 증명 연결(선행/후속 정리·사용 공식·관련 문제·오개념) | 신규 엣지 타입 증식 금지 — 참조 키로만(D2) | §2-⑤와 결합 |

### 모듈 9. 공식(Formula) 관리 — **대부분 충족**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| Formula 독립 관리(정리와 별개) | ✅ P5a canonical-only `FormulaNode`(25수식·8 family·`formula_id=formula.<slug>` 사람 관리 ID·dsl SymPy-parseable) — `formula_graph/models.py:58` | ✅ |
| 수식·유도·증명 | 유도(derivation)·증명 슬롯 부재 — **D2 ProofNode 축으로 위임**(중복 축 금지) | ⚠️ → D2 |
| 조건·사용범위 | `constraints` 필드 부재(예: 로그공식 진수>0) | ⚠️ 갭 → **D3** |
| 암기팁·암기 카드 생성 | flashcards 113건(`ConceptContent.flashcards` JSONB) — 개념 축 기존재. 공식별 암기팁은 D3 선택 필드 | ✅ 부분 |
| 공식 검색·자동 추천 | concept→formula `formula_refs` 미충전 — **Phase 5b 기존 계획**(소비처 실재 시·ADR §Phase 5a "D2 분리") 승계, 중복 등재 안 함 | ⏸ 기존 추적 |
| 공식 변형·비교 | 변형식 노드화 **금지**(canonical-only 불변식) — 변형↔canonical 동치는 `l3/symbolic_equivalence`(SymPy) 런타임 판정 | 🚫 의도적 미채택 §2-⑥ |

### 모듈 10. Knowledge Graph — **의도적 차이 + 부분 갭**

문서의 관계 11종 → **기존 7종 어휘로 전량 crosswalk 가능·신규 엣지 타입 0** (관계 5~8 상한 협상 불가):

| 문서 관계 | WhyMath 대응 | 비고 |
|---|---|---|
| Prerequisite | `prerequisite` | ✅ 유일 실적재 관계(concept 581 + atom 2,213) |
| PartOf | `composition` | 어휘 기존재(적재는 소비처 대기) |
| Generalization / Specialization | `generalization`/`specialization` (backend 투영 `EXTENDS`) | 어휘 기존재 |
| Equivalent | `notation_variant` + 의미 동치는 SymPy 런타임(`l3/equivalent`) | 동치는 엣지가 아니라 도구 판정 |
| DependsOn | `prerequisite`와 의미 중복 — 별도 타입 불채택 | §2-⑤ |
| DerivedFrom | 참조 키(D2 `derivation_of` 등 FK/참조)로 표현 — 엣지 타입 불채택 | §2-⑤ |
| UsedIn | `application` | 어휘 기존재(DEFERRED) |
| MisconceptionOf | **금지** — 오개념은 그래프 노드가 아니라 독립 DB(`MisconceptionCatalog` 843)·reactive retrieval | §2-⑤ |
| Analogy | `ANALOGOUS_TO`(backend) — **traversal 제외 동결**(`relation_crosswalk.py:62`) | `similar_to`류 방어 |
| Contrast | `contrast` | 어휘 기존재 |

그래프 기능 10종 판정:

| 문서 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 선수학습 자동 계산 | `l2/prerequisite_recommendation.py`(재귀 CTE·`MAX_PREREQUISITE_DEPTH=5`·diamond dedup) | ✅ |
| 최단 학습 경로 탐색 / 학습 경로 생성 | `l2/learning_path.py`(위상정렬·결정론 tiebreak·cycle residual 표시) | ✅ |
| 개념 영향도·핵심 개념·허브 탐색 | **부재** — centrality/도달 분석 없음 | ⚠️ 갭 → **D5** |
| 오개념 전파 분석 | **부재** — 단 오개념 preload 금지 불변 안에서 빌드타임 분석은 가능 | ⚠️ 갭 → **D5** |
| AI 설명 경로 생성(subgraph→LLM) | 프롬프트 예산은 배선(nodes≤20·tokens≤3000·`wh1_llm_policy.py`), **traversal depth≤2 guard는 `ARCH-11`(blocked·소비처 착륙 대기)** | ⏸ 기존 추적(중복 등재 금지) |
| 교수 전략 최적화 | `StrategyNode` 8종(P6a) 승격 완료·소비처 연동 후속 | ⏸ 기존 계획 |
| 교육과정 자동 검증 | prerequisite DAG hard error(pipeline validate) + 참조무결 상시 거버넌스(초인간검증 S6) + Curriculum Overlay | ✅ |

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

문서 틀의 다음 항목은 **채택하지 않는다**. 각각 CLAUDE.md 협상 불가 조항과 1:1 대응한다.

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·ADR) |
|---|---|---|
| ① | 학년·교육과정을 Concept 노드에 내장 | **Curriculum은 Overlay**(8대 구조원칙 ⑤) — 개념은 영속, 교육과정 매핑만 교체. 이미 노드에서 제거한 선례(`drop_concept_subject_curriculum_version`) |
| ② | per-row 버전 필드(생성일·수정일·버전) | 단일 진실 원천 원칙 — 버전 정본은 git + 코퍼스 버전(`*_v1`) + `_provenance.json` + `review_status`. 노드 내 버전 메타 혼입은 유지보수 지옥(붕괴 연쇄 ④) 진입로 |
| ③ | 교과서/교육과정 정의 인용·무검증 자동 정의 생성 | 저작권 절대 금기(검정 교과서 본문 복제 금지·redaction) — **self-authored만**. AI 생성물은 `ai_estimated` + 사람 검수 게이팅(AI 자기승인 금지) 필수 |
| ④ | AI 증명 생성(학생 대면) | 검증 권위 — LLM 응답 무검증 제공 금지·"확실하지 않을 때 자신 있게" 금지. 증명 판정은 unverifiable 정직 경계(04a R5)·항등식만 SymPy 기계증명·형식증명은 Lean(S5) |
| ⑤ | 관계 11종(DependsOn·DerivedFrom·MisconceptionOf·Analogy traversal 등) | **관계 타입 5~8개 상한·신규 엣지 타입 0 목표**(붕괴 연쇄 ② 방어). MisconceptionOf는 오개념 독립 DB(#6)·reactive retrieval 원칙 정면 충돌. Analogy는 `similar_to`류 — traversal 사용 금지 동결 |
| ⑥ | 공식 변형 관리(변형 노드·변형 비교) | canonical-only 불변식(P5a·위험문서 2건 정식 개정) — 변형·항순서·표기 변이 노드화는 조합폭발. 동치는 SymPy 단일 권위 위임 |

---

## §3. 설계 D1~D5 (진짜 갭의 WhyMath 정합 설계)

### D1. 정의 레지스터 — `concept_definition` Overlay (백로그 `S4-05`)

**목적**: 하나의 개념을 학생 눈높이(레지스터)별로 설명하는 정의 변형 + 예시·반례 구조.
문서 모듈 7의 핵심 아이디어를 Concept Purity·redaction 안에서 수용한다.

- **좌석**: 노드 비내장. `ConceptContent`(`db/models/concept_content.py:55`)의 **자매 프로젝션
  테이블 `concept_definition`** — 복합 PK `(code, kind)`. 기존 콘텐츠 4종을 팽창시키지 않고
  (컬럼 폭발 방지) 1:N 구조로 분리한다.
- **kind 폐쇄 enum(초기 4종)**: `curriculum_register`(교육과정 눈높이·self-authored 재서술) ·
  `intuitive`(직관) · `rigorous_internal`(엄밀·**학생 비노출** — `formal_definition_internal`
  게이팅 규약 승계) · `analogy`(비유). *초등용·영재용 레지스터는 페르소나 단계(v1.5/v2.0)
  도달 시 enum에 추가* — 지금 넣으면 소비처 없는 저작 부채.
- **필드**: `code`(PK1·ConceptContent와 동일 키 공간) · `kind`(PK2) · `body`(self-authored만·
  교과서/성취기준 본문 근접 금지 — 성취기준 본문 슬롯을 두지 않아 구조적 차단, ConceptContent
  동형) · `examples`(JSONB list) · `counterexamples`(JSONB list — **반례는 오개념 교정 축**:
  `MisconceptionCatalog.correction_point`와 상보·중복 저작 금지, 오개념 kebab-id/mis_id 참조
  가능) · `difficulty_band` · `review_status`(상수 `ai_estimated` — 검수 게이팅) · `updated_at`.
- **소비처(구현 트리거)**: L4 코치의 눈높이 선택(설명 요청 시 학생 수준·정서 신호에 맞는
  레지스터 선택). **구현은 소비처 슬라이스와 동반** — 저작·적재만 먼저 하면 dead data.
- **선례 미러**: 적재기는 `l1/concept_content/projection.py`(code 키 멱등 upsert·sync 엔진 재사용)
  동형. 거버넌스: kind 폐쇄 집합 동결 + 본문 슬롯 부재 동결 테스트.

### D2. Theorem/Proof 페이퍼 설계 (P6 선행 설계 — 코드 0·태스크 신설 없음)

**목적**: 12노드 taxonomy의 마지막 잔여(P6)를 "설계 백지" 상태에서 "설계 확정·구현 대기"로
전환한다. 구현 트리거는 기존 `S4-02-proof-learning-support`(학생 대면)·S5(형식증명) — 신규
태스크를 만들지 않는다(중복 추적 금지).

- **TheoremNode ≠ ProofNode 분리**(ADR §2 판정 승계): 정리 1 : 증명 N.
  - `TheoremNode`: `theorem_id`(`theorem.<slug>` — **사람 관리 안정 code**, FormulaNode
    `ID≠Signature` 선례) · `name_ko` · `hypothesis`(조건·구조화 텍스트) · `conclusion`(결론) ·
    `latex` · `dsl`(SymPy-parseable 명제·가능한 경우만) · `standard_codes` · `aliases`.
    직관·활용·역사 서술은 노드 비내장 — ConceptContent/D1 축 참조(Concept Purity).
  - `ProofNode`: `proof_id` · `theorem_id`(참조) · `method`(폐쇄 enum: 직접·대우·귀류·귀납·
    작도 등 — `StrategyNode` 8종과 어휘 disjoint 명명) · `steps`(구조화·렌더러-중립) ·
    `depends_on_concept_ids`(참조 키 배열) · `uses_formula_ids`(참조 키) · `review_status`.
- **Formula 경계 규칙**: 재작성/계산 도구로 쓰는 등식 = `FormulaNode`(예: 곱셈공식) /
  가정을 갖는 명제 = `TheoremNode`(예: 중간값정리·"미분가능 ⇒ 연속"). 겹침(사인법칙 등)은
  **양쪽에 두되 상호 참조 키**(`formula_id`↔`theorem_id`)로 잇는다 — 신규 엣지 타입 0.
- **관계는 전부 참조 키**: 선행 정리·사용 공식·증명 필요 개념·관련 오개념 — 문서 모듈 8의
  "연결 정보"는 엣지가 아니라 배열 참조(`depends_on_*`·`uses_*`)로 표현. 오개념 연결은
  독립 DB 쪽(`MisconceptionCatalog.concept_src_id` 유사)에서 역참조.
- **검증 tier(검증 권위 서열 정합)**: ① 대수 항등식·수치 명제 → SymPy 기계증명(권위 1위)
  ② 학생 증명 피드백 → unverifiable 정직 경계(04a R5 — 구조 피드백만·정오 확언 금지)
  ③ 형식증명 → Lean·WH-S Tier3(S5). AI 생성 증명은 `ai_estimated` + 사람 검수 전 학생 비노출.
- **anti-explosion**: canonical 정리만 노드화(교과서 명명 정리·핵심 성질 위주 폐쇄적 시드),
  문제 풀이 중간 보조정리는 노드화 금지.

### D3. Formula 메타 보강 — `constraints` 필드 (백로그 `S4-06`)

- `formula_graph/models.py:58` `FormulaNode`에 `constraints: list[str]`(성립 조건·사용범위·
  자체작성 — 예: `"a>0, a≠1 (밑 조건)"`) 추가. 선택적으로 `mnemonic`(암기팁·self-authored) 1필드.
- 유도(derivation)는 **추가하지 않는다** — D2 ProofNode(`theorem/proof` 축)로 위임. Formula에
  유도 슬롯을 두면 증명 축 이중화(단일 진실 원천 위반).
- 코퍼스 `formula_graph_v1` 25건 backfill(자체작성·`ai_estimated`) + backend `formula_node`
  프로젝션 컬럼 동반. 5b(formula_refs 충전·검색/추천)는 기존 계획 그대로 승계.

### D4. 중복 개념 검수 게이트 (백로그 `ARCH-16`)

- **빌드타임** 임베딩 pairwise 유사도 리포트: 동일 코퍼스 스코프 내(cross-table 코사인 금지 —
  임베딩 네임스페이스 거버넌스 준수) cosine ≥ threshold(초기 보수값·실측 후 조정) 쌍을
  **검수 후보 큐**로 산출. data-pipeline validate/report 축(런타임 아님).
- **AI 자기승인 금지**: 후보는 자동 병합하지 않는다 — misconception crosswalk `ops promote`
  선례(사람 검수 경유 승격)와 동형의 사람 검수 경로.
- 소비처: 콘텐츠 공장 저작 위생(S4-01 초·중 확장 시 신규 개념 대량 유입 전 가동 가치).

### D5. 그래프 분석 리포트 — 허브·영향도·오개념 전파 (백로그 `ARCH-17`)

- **빌드타임 오프라인 리포트**(런타임 traversal 아님 — 예산 guard 논쟁 무관):
  prerequisite DAG 위에서 ① in/out-degree ② 하류 도달 가능 집합 크기(영향도) ③ 허브/핵심
  개념 랭킹. `l2/prerequisite_recommendation.py`의 재귀 CTE 패턴 재사용 또는 pipeline 측
  전체 DAG 1회 위상 스캔(전체 그래프 열람은 **분석 도구는 허용** — 금지 대상은 *LLM 컨텍스트
  투입*이지 오프라인 집계가 아님을 명시).
- **오개념 전파 분석**: `severity='blocking'` 오개념(P4a enrichment)의 대응 개념
  (`concept_src_id`→crosswalk)에서 하류 도달 개념 수 집계 — "이 오개념 방치 시 몇 개 개념이
  막히는가". **오개념 preload 금지 불변**: 산출물은 저작·검수·진단 우선순위 리포트이지 튜터링
  컨텍스트가 아니다.
- 소비처: 저작 우선순위(콘텐츠 공장 ops) · L2 진단/약점 추천 우선순위 보조 신호(후속).

---

## §4. 잔여 연동 트리거 — chunk 임베딩

CLAUDE.md 구조 붕괴 절의 "노드 embedding 전체 생성 금지 — chunk 단위(`limit.definition`/
`limit.intuition`/`limit.example`·150~500 tokens) 분리"는 **현재 미구현**이다(실측: 개념/원자당
벡터 1개·`chunk_type` 필드 0건 — `part8_context_architecture_review.md` "소비처 대기" 판정과
일치). **D1 정의 레지스터가 착지하면 `(code, kind)`가 자연스러운 chunk 키 공간이 된다** —
정의 레지스터별 임베딩(= chunk 임베딩)은 D1 소비처 슬라이스에 동반 검토한다(별도 태스크
없음·S4-05 acceptance에 명시).

---

## 부록 — 실측 근거·관련 코드

- 런타임 노드 정본: `src/backend/whymath_backend/db/models/concept.py:53` (제거 컬럼 사유 주석 포함)
- 관계 어휘 단일 계약: `src/data-pipeline/data_pipeline/concept_graph/relation_crosswalk.py:36`
  (`LOADED_RELATION="prerequisite"` · `FORBIDDEN_RELATION_TOKENS={similar_to, related_to}`)
- 실 traversal: `src/backend/whymath_backend/l2/prerequisite_recommendation.py:230` (재귀 CTE)
- 콘텐츠 프로젝션(D1 자매 대상): `src/backend/whymath_backend/db/models/concept_content.py:55`
- FormulaNode(D3 대상): `src/data-pipeline/data_pipeline/formula_graph/models.py:58`
- 오개념 독립 DB: `db/models/misconception_catalog.py:75`(843건) + reactive retrieval
  (`l4/misconception/combined.py`·preload 금지 강제 지점 다수)
- 성취기준 Overlay: `db/models/achievement_standard.py:66`(895건) + `concept_standard_link.py:55`(443건)
- 기존 추적 승계(중복 등재 금지): `ARCH-11-subgraph-depth-guard`(blocked) · Phase 5b
  formula_refs(ADR §Phase 5a) · `S4-02-proof-learning-support`(D2 구현 트리거)

---

## §5. 2026-08-03 재점검 — 도달 관측 렌즈 최초 적용

> 이 절은 `ai_recommendation_module_gap_review.md` §0("두 가지 전제 정리")·
> `visualization_module_gap_review.md`(학생 도달 0회 패턴)·`nlp_module_gap_review.md` D1이
> 이미 확립한 **"소비 경로 완비 여부와 무관하게 실제 클라 도달을 실측한다"** 렌즈를,
> **개념(Knowledge) 축에 처음 적용**한 재점검이다. §1~§4(2026-07-27)는 모듈 6~10과의
> crosswalk·설계였고 클라 도달은 별도로 다루지 않았다 — 이번에 그 공백을 채운다.
> 판정 기호는 §1과 동일(✅ 충족 / ⚠️ 진짜 갭 → 태스크 / 🚫 의도적 미채택 / ⏸ 기존 추적 승계)에
> **△ 재확인·변동 없음**을 추가한다(자매 문서들의 판정 기호 표 관례 승계).

### §5-1. 신규 갭 A — 개념 지식 자산의 학생 도달이 0회다 (최우선 → `KG-01`)

Flutter 학생 앱이 실제로 호출하는 `/v1/` 경로는 **20개뿐**이다(전수 grep, `src/mobile/lib/**/*.dart`).
개념 지식 자산 관련 표면은 그 20개 중 **단 하나도 없다**:

| 표면 | 실측 | 판정 |
|---|---|---|
| `POST/GET/PATCH/DELETE /v1/concepts`·`/v1/concepts/{id}`·`/v1/concepts/{id}/edges`(단건·목록·엣지·생성·수정·삭제 — `api/concepts.py`) | 클라 소비 **0**(20종 목록 부재) | ⚠️ 갭 → **KG-01** |
| `GET /v1/concepts/search`(pgvector 원자 유사도 조회 — `api/concepts.py:161`) | 클라 소비 **0**. 원래 설계도 "학생 직접 노출 아닌 L2/L4·교사 도구 좌석"(docstring)이라 *학생 경로 노출 자체가 목표가 아님* — 그런데 L2/L4·교사 도구 쪽 배선도 **0**(내부 소비자도 없음). 하위 함수 `search_atoms` 자체는 `l4/misconception/warmstart.py`가 이미 실소비 중이라 "능력이 죽은 것"이 아니라 "이 HTTP 래퍼가 죽은 것" | ⚠️ 갭 → **KG-01**(도달 관측만. 학생 노출은 `nlp_module_gap_review.md §5-⑤` 판정 승계 — `ARCH-11` 해제 전까지 하지 않는다) |
| `ConceptContent.flashcards`(암기카드 JSONB, 코퍼스 **113건** 적재 — `data/corpus/concept_graph_v1/flashcards.jsonl`) | 이를 읽는 API 엔드포인트 **0개**(`grep -rn flashcards src/backend/whymath_backend/api/` 무결과) — 저작된 113건이 어떤 표면으로도 학생·교사·L2/L4 어디에도 나가지 않는다 | ⚠️ 갭 → **KG-01** |
| `GET /v1/me/weak-concepts/{concept_id}/prerequisites`·`.../learning-path`(재귀 CTE 선수개념·Kahn 위상정렬 학습경로 — `l2/prerequisite_recommendation.py`·`l2/learning_path.py`, HTTP 표면 `api/me.py:1391,1507`) | 클라 소비 **0**(20종 목록 부재) | ⚠️ 갭 → **KG-01**(경계는 아래 참조) |

**REC-01과의 경계(중복 등재 회피)**: `ai_recommendation_module_gap_review.md` §0-①이 이미
"개념 추천(기능81) API 전군 클라 소비 0"을 지적했다. 그러나 그 문서·`REC-01` 태스크의 관측
축은 **요청량·개인화 가중치**(θ 기반 비율·`problem_attempt` 적재 건수·약점 가중 적용 건수)다.
`KG-01`은 **개념 콘텐츠·그래프 표면 자체**(라우트가 존재하는데 아무도 안 쓴다는 사실, flashcards
읽기 좌석 부재)의 도달 관측이다 — 관측 축이 다르므로 중복이 아니다. `api/me.py` 파일 경로가
겹치는 것은 하네스 `path_overlap` 정책(`backlog/policy.yaml` = `warn`, 아직 `block` 아님)상
허용 범위이며, 두 태스크는 같은 파일의 서로 다른 관측 축을 각자 손댄다.

**활성화가 아니라 가시화**(NLP-01·REC-01과 동형): 클라 배선·신규 화면·`/concepts/search`의 학생
노출은 이 재점검·`KG-01` 어느 쪽도 다루지 않는다.

### §5-2. B·D 재확인 — 변동 없음 (△)

- **chunk 단위 임베딩**(§4): `concept_embedding`/`atom_embedding` 여전히 엔티티당 벡터 1개·
  `chunk_type` 컬럼 0건. §4의 "D1(정의 레지스터) 착지 시 `(code, kind)`가 자연스러운 chunk 키
  공간이 된다"는 판단은 재확인 결과 **여전히 유효**하다. 신규 갭 아님·신규 태스크 없음.
- **`formula_refs`(concept↔formula 참조) 미충전**(§3 D3 하단): 여전히 0건 충전이나 이는
  기존 ADR(Phase 5a "D2 분리")이 이미 계획한 **의도적 유보**(Phase 5b). 재등재하지 않는다.

### §5-3. 스키마 정본 stale — `active_concepts`(YAML) vs `ConceptRole`(런타임) 정정 (문서 각주)

`schemas/v1.1/problem.schema.yaml:107,241-261`의 `ActiveConcepts`는 `primary`/`secondary`/
`arithmetic_only` **3분류**로 문항-개념 연결을 정의한다. 그러나 실제 런타임 정본
`ConceptRole`(`src/backend/whymath_backend/schema/enums.py:671`)은 `PRIMARY`·`SUPPORTING`·
`IMPLICIT`·`TESTED` **4종**이고, `ASSESSED_ROLES = (PRIMARY, TESTED)`가 BKT 숙달 갱신·IRT θ
추정·약점 가중의 **단일 대상 집합**이다(L2·L5 공유 단일 출처). YAML 명세가 구현을 반영하지
못하는 stale 상태다 — `ai_recommendation_module_gap_review.md §정정`이 확립한 선례(원인이
다른 곳을 가리키는 stale·"코드 변경 없이 사실만 기록하고 소유를 지정") 형식을 그대로 따른다.

**처리**: 이번 재점검의 산출물 범위는 "문서 추가 + 백로그 태스크 1건"으로 확정돼 있어(Kiki
합의) `problem.schema.yaml` 자체의 정정은 **이번 슬라이스에서 하지 않는다**. 별도 코드/스키마
태스크도 신설하지 않는다 — YAML 설명 필드 1줄 수정은 위험이 낮으나(런타임 로직 무영향·순수
문서), path_overlap 위험 회피 원칙(2026-07-27 병렬 세션 충돌 교훈)과 산출물 범위 규율을 함께
지키기 위해 **이 문서(§5-3)에 사실을 고정**해 두고, 다음으로 `problem.schema.yaml`을 만지는
세션(스키마 유지보수·v1.2 슬라이스 등)이 `ActiveConcepts` 블록에 각주("런타임 정본은
`ConceptRole` 4종 — `SUPPORTING`/`IMPLICIT`는 `secondary`에 대응, `TESTED`는 `primary`와
구분돼 `ASSESSED_ROLES`에 포함되나 이 3분류에는 대응 슬롯 없음. 정본 `schema/enums.py:671`
참조")을 추가하도록 소유를 지정한다.

### §5-4. 등재 요약

| 태스크 | 근거 | stage | priority | 비고 |
|---|---|---|---|---|
| `KG-01-concept-reach-observability` | §5-1 | S3 | 2 | **최우선 신규 갭** — concepts API 7라우트·flashcards 읽기 표면·prerequisites/learning-path 도달 0회 가시화. 활성화는 범위 밖 |

중복 등재 회피: `REC-01`(요청량·개인화 축, 승계) · `ARCH-11`(subgraph depth guard, blocked,
승계) · Phase 5b `formula_refs`(승계) · §5-3 스키마 stale(신규 태스크 없음, 소유만 지정).
