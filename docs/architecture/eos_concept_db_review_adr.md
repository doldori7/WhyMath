# EOS 6_개념(Concept) DB 설계 검토 — WhyMath 수용 ADR

> **상태**: 초안 (2026-08-25) · r2 보강 검토 반영 (2026-08-25, §2.26·§3.6~3.10 추가) · r3 PR #897 리뷰 반영 (2026-08-28, §2.26-1·§3.6·§3.8·§3.10 보정 + §4 후속 7·8 추가)  
> **범위**: EOS 지향 교육앱을 위한 『6_개념(Concept) DB』 설계 검토(64항)를 WhyMath 현행 설계·원칙과 대조하여 부분 수용  
> **연관**: `docs/architecture/concept_node_layering_decision.md`, `docs/architecture/eos_curriculum_semantic_backbone_adr.md`, `docs/standards/eos_identity_layer_011_1_decision.md`, `docs/architecture/01_data_foundation.md`, `backlog/tasks/CUR-09-eos-unit-structure-review-adoption.yaml`

---

## 1. 결정 요약

검토안이 제시한 "Concept DB는 콘텐츠 저장소가 아니라 교육 의미 그래프의 기준 좌표계"라는 관점과 "Concept을 Curriculum·Standard·Objective·Skill·Definition·Formula·Problem·Misconception과 분리"하는 원칙은 **채택**한다.

그러나 WhyMath는 이미 `Concept` DAG를 **영속 원본**으로 두고, 교육과정/단원/성취기준/학습목표를 **Overlay**로 취급하는 정본이 확립되어 있으므로, 검토안의 일부 구현 제안(예: 교과별 Concept 분리, 별도 Graph DB, `curriculum_node` 1급 독립 트리, `Unified Entity` 슈퍼테이블)은 WhyMath 설계 정신과 충돌하여 **부분 채택 또는 거부**한다.

| 영역 | 판정 | 근거 |
|---|---|---|
| Concept = 의미 그래프 기준 좌표계 | ✅ 채택 | `Concept`가 L1 핵심 자산, 교육과정/언어/렌더러 무관 의미론 PK 운영 중 |
| Concept ≠ Curriculum/Standard/Objective/Skill/Definition/Formula/Problem/Misconception | ✅ 채택 | `concept_node_layering_decision.md` 9계층·12노드 taxonomy와 정합 |
| Immutable `concept_id` + 변경 가능한 `canonical_key` | ✅ 이미 충족 | `math.<area>.<slug>`가 의미론적 PK, `aliases`로 옛 키 보존 |
| Concept Granularity(독립 단위) | ✅ 채택 | 법칙: "노드 = 학생 사고가 바뀌는 최소 단위" |
| Concept ↔ Skill 분리 | ✅ 이미 충족 | SkillNode 1급 노드 승격(Phase 2a 완료) |
| Concept ↔ Objective 분리 | ✅ 이미 충족 | `AchievementStandard`가 Objective/Outcome 역할 |
| Curriculum-independent Concept | ✅ 이미 충족 | `CurriculumEntry`가 `(concept_id, country_code, subject)` 오버레이 |
| Concept Core + Label + Relation | ✅ 이미 충족 | `Concept`/`ConceptEdge` + locale 계층(`locales/{lang}.json`) |
| Prerequisite를 일반 Relation과 구별 | ⚠️ 부분 채택 | `ConceptEdge.PREREQUISITE`로 운영 중, 검토안의 추가 메타(dependency_level, minimum_mastery, curriculum_context)는 Phase 1.5 확장 |
| Definition/Formula/Theorem/Example/Explanation/Visualization 분리 | ✅ 이미 충족·확장 | 노드 순수성 원칙: 자유텍스트/성취기준 본문/렌더 명세 내장 금지, 참조 키만 보유 |
| Misconception 분리 + N:M | ✅ 이미 충족 | 독립 Misconception DB + `misconception_codes` 참조 |
| Problem ↔ Concept N:M | ✅ 이미 충족 | `problem_id` ↔ `concept_id` 다대다 매핑 운영 중 |
| Learner Concept State 분리 | ✅ 이미 충족 | `ConceptMasteryHistory`가 L2 역할 |
| Knowledge Component(KC) 분리 | ⚠️ Phase 2 | `AtomNode` 원자 백본이 KC 역할 일부 수행, 추가 KC 레이어는 후속 |
| Abstraction Level | ⚠️ 부분 채택 | `abstraction_level` 필드 후속 추가, 구체적 enum은 Phase 1.5 |
| Representation 관리 | ✅ 이미 충족 | `representations`를 semantic 계층 참조로 운영 중 |
| Concept Alias/동의어 | ✅ 이미 충족 | `aliases` + locale 계층 + `ids.yaml` registry |
| Concept 의미 충돌 관리(Resolver) | ⚠️ Phase 2 | 수학 외 과목 확장 시 `subject` 접두/namespace 적용 |
| Source/Provenance | ✅ 이미 충족·확장 | `source_*`·`license_id`·`verified_by`·`confidence` 운영 중 |
| Concept Lifecycle + Versioning | ⚠️ 부분 채택 | `status`·`version_id` 존재, merge/split 이력은 Phase 2 |
| Concept Merge/Split | ❌ Phase 2 | 현재 Concept 그래프 규모에서는 소수 수작업으로 충분 |
| Concept Confidence/Quality Score | ⚠️ Phase 2 | AI 생성 edge 관리 시 도입, MVP에서는 수작업 전문가 검증 |
| Evidence 관리 | ⚠️ Phase 2 | `evidence_source_id`·`evidence`는 `ConceptEdge`에 확장 예정 |
| Subject-neutral Concept Schema | ✅ 이미 충족 | 수학 전용 필드는 `Concept` Core에 두지 않음, MathConceptProfile 등은 Phase 2 |
| Concept API (조회/relations/prerequisites/misconceptions/problems/objectives/explanations/visualizations) | ⚠️ 부분 채택 | 기존 API에 일부 누락된 엔드포인트 확장 필요 |
| Concept Search API (semantic/context-aware) | ⚠️ Phase 1.5 | `embedding_search` 기반 resolver + curriculum context 추가 |
| RDB + Graph DB + Vector DB | ⚠️ 부분 채택 | PG 단일 평면이 정본, Graph DB(Neo4j)는 data-pipeline optional extra의 실험 경로뿐 |
| Vector DB를 Concept DB처럼 사용 | ❌ 거부 | Embedding similarity는 검색/보조 메타, identity 근거 불가 |
| AI 자동 생성 Concept 바로 배포 | ❌ 거부 | CLAUDE.md "검증 권위 서열" — Rule/Validator/Human Review 필수 |
| Cross-subject Concept Mapping | ❌ Phase 2+ | 수학 외 과목 확장 시 고려 |

---

## 2. 검토안 64항 × WhyMath 현행 매핑

### 2.1 관점 전환 (§1~§2)

검토안의 핵심 문장:

> "Concept DB는 콘텐츠 저장소가 아니라 교육 의미 그래프의 기준 좌표계이다."

WhyMath 현행과 정합한다. `01_data_foundation.md` §9에서 `Concept` DAG를 "왜 이 개념을 배우는가를 구조로 답기 위한 자산"으로 정의하고 있다.

**WhyMath의 추가 원칙**: `Concept`은 *renderer·curriculum·prompt·misconception·UI·embedding이 혼입되지 않는* 순수 개념 노드(`concept_node_layering_decision.md` §1). 검토안의 "Concept Core + Subject Extension" 구조는 이 원칙을 따른다.

### 2.2 Concept의 정의 (§3)

검토안:

> "Concept = 학습자가 이해하고, 구별하고, 다른 지식과 연결하여 사용할 수 있어야 하는 독립적인 지식 의미 단위"

WhyMath에서 이는 거의 동일하게 해석되며, 다만 "노드 = 학생 사고가 바뀌는 최소 단위(= 독립 오개념 발생 단위)"로 더 좁힌다. 이는 검토안 §5의 "독립 Concept 후보 7가지 기준"과 합치한다.

### 2.3 Concept ID (§4)

검토안은 `concept_id`를 불변으로, `canonical_key`를 변경 가능하게 두는 구조를 제안한다.

WhyMath는 이미 `concept_id` 자체를 의미론적 canonical ID(`math.<area>.<slug>`)로 사용 중이다. `ids.yaml` registry + `aliases`로 옛 키와 외부 ID를 보존한다. 따라서 검토안의 "ID에 의미를 넣지 말라"는 주장은 **수정하여 수용**한다:

> ID는 curriculum(학년/개정판), language(locale), renderer(표시 방식)에 종속되지 않는다. 단, 수학 개념의 의미적 정체성(`geometry`, `limit`, `calculus`)은 ID에 담는다.(`eos_identity_layer_011_1_decision.md` §4.1)

### 2.4 Concept Granularity (§5)

검토안의 7가지 기준은 WhyMath 노드 입도 결정과 정합한다. 다만 "꼭짓점"처럼 수학적으로는 이미 `quadratic_function`의 구성 요소(`part_of`)로 표현할 수 있는 개념까지 독립 노드로 승격하는 것은 `canonical·mastery 독립추정 가치` 기준을 통과할 때만 허용한다(`concept_node_layering_decision.md` §2).

### 2.5 Concept ↔ Skill 분리 (§6)

**이미 충족**. `SkillNode`는 1급 노드로 승격되었고, `concept_id` 참조를 통해 `requires`/`applies`/`produces` 관계를 표현한다. `behavior_skills`는 `Concept` 노드의 cognition 계층 참조로 운영 중이다.

### 2.6 Concept ↔ Objective 분리 (§7)

**이미 충족**. `AchievementStandard`가 Objective 역할을 하며, 하나의 `Concept`에 여러 `AchievementStandard`가 연결될 수 있다.

### 2.7 Concept ↔ Curriculum 분리 (§8)

**이미 충족**. `CurriculumEntry`가 `(concept_id, country_code, subject)` 복합 구조로 Overlay 역할을 한다. `2015 quadratic_function`과 `2022 quadratic_function`은 별도 Concept이 아니라 동일 `concept_id`에 대한 서로 다른 `CurriculumEntry`다.

### 2.8 Concept 핵심 데이터 모델 (§9)

검토안의 `concept` 테이블은 WhyMath `Concept` 모델과 대체로 일치하나, 다음은 수정한다:

- `subject_id`·`domain_id`는 `Concept` Core에 **두지 않는다**. Subject는 `CurriculumEntry`/교육과정 Overlay에 속한다. 단, canonical ID의 접두(`math.`)로 subject namespace는 암시적으로 드러난다.
- `language_neutral_semantics`는 **self-authored 1줄 `core_meaning`**으로 대체. 성취기준 본문 근접 텍스트는 내장 금지.
- `abstraction_level`은 Phase 1.5 추가.

### 2.9 Concept Label (§10)

**이미 충족**. WhyMath는 `canonical_name`을 `Concept`에 두지 않고, `locales/{lang}.json` + canonical key(`math.<area>.<slug>`)로 locale 계층에서 다국어·동의어를 관리한다. 이는 검토안의 `concept_label` 테이블과 논리적으로 동등하지만, DB 스키마 대신 locale 파일에 저장하여 렌더러-중립성을 유지한다.

### 2.10 Concept Relation (§11~§12)

WhyMath는 현재 7가지 관계 유형을 운영 중(`prerequisite`, `generalization`, `specialization`, `contrast`, `application`, `composition`, `notation_variant`).

검토안이 제안한 `broader_than`/`narrower_than`은 `generalization`/`specialization`으로 매핑, `part_of`는 `composition`으로 매핑, `derived_from`/`used_in`은 Phase 2에서 필요 시 검토. **신규 relation vocabulary 추가는 제한적으로** 유지한다(`concept_node_layering_decision.md` "관계 타입 5~8개" 원칙).

### 2.11 Prerequisite를 일반 Relation과 구별 (§13)

검토안은 `ConceptRelation`과 별도 `PrerequisiteEdge`를 제안한다.

WhyMath는 `ConceptEdge.PREREQUISITE`로 단일 테이블에 저장하지만, 검토안의 추가 메타(`required_strength`, `dependency_level`, `minimum_mastery`, `curriculum_context`, `learner_level`, `evidence`)는 `ConceptEdge` 컬럼 확장으로 수용한다. Phase 1.5에서 설계.

### 2.12 Concept Type (§14)

검토안의 `ENTITY/PROPERTY/PROCESS/RELATION/STRUCTURE/QUANTITY/REPRESENTATION/METHOD/PRINCIPLE/PHENOMENON`과 수학별 `OBJECT/PROPERTY/RELATION/OPERATION/REPRESENTATION`은 **과목별 enum으로 `Concept` Core에 주입하지 않는다**.

WhyMath는 `cognitive_type`과 같은 소수 스칼라만 `Concept`에 내장하고, subject-specific taxonomy는 별도 Registry(Phase 2)나 `Concept` 참조 확장으로 둔다.

### 2.13 Definition/Formula/Theorem/Example/Explanation/Visualization 분리 (§15~§20)

**이미 충족 또는 확장 중**. `concept_node_layering_decision.md` §1에서:

- `formal_definition_ref`는 참조(노드 내장 금지)
- `intuition`·`representations`는 self-authored semantic으로 복원
- `visualization_card_keys`는 참조 키
- `formula_refs`는 `FormulaNode` 참조(Phase 5a 완료)
- Theorem/Proof는 Phase 6에서 노드화 예정

### 2.14 Concept ↔ Misconception (§21)

**이미 충족**. Misconception은 독립 DB(`l4/misconception/`, 843개 카탈로그)로 운영되며, `Concept`는 `misconception_codes` 참조 배열로만 연결한다. `concept_node_layering_decision.md` §2.14 Phase 4a에서 `severity`·`behavior_skills` 필드 확장이 완료되었다.

### 2.15 Concept ↔ Problem (§22)

**이미 충족**. `Problem`은 `concept_ids` 또는 bridge table로 여러 `Concept`와 N:M 연결. `role`(PRIMARY/SECONDARY/PREREQUISITE/CONTEXT/DISTRACTOR)과 `weight`는 `problem_concept_mapping`에 둔다.

### 2.16 Concept ↔ Learner Mastery (§23)

**이미 충족**. `ConceptMasteryHistory`가 L2에서 Concept 단위 숙련도를 관리. Concept DB는 WHAT을, Learner Model은 HOW WELL LEARNED를 관리.

### 2.17 Knowledge Component (§24)

`AtomNode` 원자 백본(2,683노드·2,210엣지, `01_data_foundation.md`)이 KC의 상당 부분을 커버한다. 추가 KC 레이어는 Phase 2에서 검토.

### 2.18 Abstraction Level / Representation / Alias / Resolver (§25~§28)

- `abstraction_level`: Phase 1.5
- `Representation`: `representations` 참조로 이미 운영 중
- `Alias`: `aliases` + locale + `ids.yaml`로 운영 중
- `Resolver`: 현재 `embedding_search` + canonical key 우선. curriculum context-aware resolver는 Phase 1.5

### 2.19 Source/Provenance / Lifecycle / Versioning / Merge/Split (§29~§34)

- Source/Provenance: ✅ 이미 `source_*`·`license_id`·`verified_by`·`confidence`
- Lifecycle: `status` 운영 중. merge/split 상태는 Phase 2
- Versioning: `version_id` 존재. `valid_from`/`valid_to`는 Phase 2

### 2.20 Concept Confidence / Quality Score / Coverage / CMS / AI Tutor (§35~§53)

- Confidence/Quality Score: Phase 2 (AI 생성 KG 증가 시)
- Coverage 분석: Phase 1.5, 관리자 CMS 기능
- Concept Search API: Phase 1.5
- AI Tutor 연동: 이미 `prerequisite_concept_ids`·`misconception_codes`·`learner_mastery`를 LLM 프롬프트에 주입하는 구조 운영 중. `target_concepts`·`prerequisite_mastery` 구조는 검토안과 일치.

### 2.21 Event / Learning Path / Recommendation / Problem Graph 분리 (§51~§54)

- Event에 `concept_refs` 기록: ✅ `attempt_event`·`evidence_event`가 `concept_id`를 참조
- Learning Path: L4 PolyaCoach가 `ConceptEdge.PREREQUISITE` 기반으로 remediation 결정
- Recommendation: L2/L4 경유
- Concept Graph ↔ Problem Graph 분리: ✅ `Problem`은 `Concept`을 평가하지만 별도 그래프

### 2.22 Subject 경계 / Cross-subject Mapping (§55~§56)

현재 수학 외 과목 확장은 Phase 2+. 검토안의 "전략 B(과목별 분리 후 related_to 연결)"를 기본으로 채택한다. 즉, `math.vector`·`physics.vector`는 별도 Concept이며, 상위 ontology에서 cross-subject mapping으로 연결.

### 2.23 물리 DB 모델 / MVP vs EOS (§58~§59)

WhyMath 현행은 검토안의 MVP 범위를 상당 부분 이미 구현했으며, 초기 PostgreSQL 단일 평면을 채택한다. Graph DB(Neo4j)는 data-pipeline optional extra의 실험 경로뿐이며, 런타임에는 PG를 사용한다.

### 2.24 피해야 할 설계 (§60)

7가지 안티패턴은 WhyMath 설계 원칙과 정합한다. 특히:

- ① 단원명을 Concept로 사용 금지: ✅ `Concept`는 의미 단위, 단원은 `CurriculumEntry`/`UnitSpec`
- ③ 정의·공식·예제를 TEXT로 내장 금지: ✅ 노드 순수성 원칙
- ⑤ 교육과정별 Concept 복제 금지: ✅ `CurriculumEntry`가 Overlay
- ⑥ Vector DB를 Concept DB처럼 사용 금지: ✅ PG가 identity store, vector는 retrieval layer
- ⑦ AI 자동 생성 Concept 바로 배포 금지: ✅ 검증 권위 서열

### 2.25 EOS Concept Contract (§61)

12가지 계약 중 WhyMath가 이미 충족하거나 Phase 1/1.5/2로 확장할 항목으로 매핑한다. 이 계약을 `docs/standards/s1_structure_audit_2026-07.md` 및 Concept Purity 원칙 아래 두고 운영한다.

### 2.26 r2 보강 검토 — 검토안 자체의 내부 결함 6종 (2026-08-25)

r1 판정표(§1) 이후 검토안 문서를 대상으로 한 독립 재검토에서, r1이 명시하지 않은 검토안 자체의 결함 6종을 추가 식별했다. WhyMath 수용 시 아래 수정 없이 원문을 받으면 안 된다.

1. **§4↔§9 규칙 부재 (canonical_key UNIQUE + 변경 가능)** — 검토안은 `canonical_key`를 "변경 가능"이라 정의(§4)하면서 DDL에서는 `UNIQUE` 제약(§9)을 건다. UNIQUE 자체는 조회 모호성 방지로 유효하지만, 검토안에는 이 키를 참조(FK) 대상으로 쓰지 않는다는 규칙이 없어 키 갱신 시 참조 무결성 관리가 깨질 수 있다. WhyMath는 `concept_id` 불변 참조 + `aliases` 배열 + `ids.yaml` registry로 해결하므로, 규칙 부재 상태의 검토안 DDL은 그대로 수용하지 않는다(§3.10).
2. **§12 관계 타입 11종 — 검토안 자신의 원칙 위반** — 검토안은 "관계를 너무 많이 만들면 KG가 관리 불가능"이라 경고하면서 정작 11개 relation을 제안한다. 특히 `related_to`는 WhyMath가 traversal 금지로 봉인한 타입이다. r1의 기존 7종 매핑(§2.10)을 유지하고, 검토안 vocabulary는 그대로 받지 않는다(§3.5와 정합).
3. **§45 Rule 4 "가능하면 DAG" — 강제 수준 부족** — 선수관계 순환은 학습경로 엔진의 무한 루프·오진단을 만드는 치명 오류인데 검토안은 "가능하면" 수준의 권고에 그친다. WhyMath는 data-pipeline 검증기가 `prerequisite_cycle`을 **hard error**로 강제한다(`data_pipeline/graph_analytics/analytics.py:166`, `atom_graph/validate.py:9`, `skill_graph/validate.py:8`; 런타임 가정 주석 `api/me.py:1503`). 수용 시 "prerequisite는 DAG 강제(검증 게이트 hard error)"로 격상한다(§3.6).
4. **§46 Quality Score — 게이트 사용 금지** — 가중치(15/15/15/10/…)는 근거 없는 점추정이다. `superhuman_verification_standard.md`의 "점추정·인상 판정 금지" 원칙에 따라 대시보드 지표로는 허용하되, 배포·승격 게이트(exit 0/1 판정)로 사용하려면 측정 기반 임계값(Wilson 단측 경계 등)이 선행돼야 한다(§3.7).
5. **§51 이벤트 `concept_refs` 배열 — 비정규화 드리프트 위험** — 문항-개념 매핑이 수정되면 과거 이벤트의 배열과 불일치가 생긴다. WhyMath는 이벤트의 `concept_refs`를 **기록 시점 스냅샷**으로 명시하고, 분석·숙련 추정은 `problem_id` 조인으로 읽기 시점에 해석하는 규칙을 둔다(§3.8).
6. **노드 순수성(negative constraint) 부재** — 검토안은 Concept에 무엇을 *넣을지*만 다루고, 무엇을 *넣으면 안 되는지*(renderer·prompt·UI·embedding 혼입 금지)는 다루지 않는다. WhyMath의 `_FORBIDDEN_NODE_FIELDS` 정적 차단이 이 결함을 이미 보완하므로, Concept Contract(§61) 수용 시 "금지 필드 목록" 조항을 추가한다(§3.9).

---

## 3. WhyMath 수정 원칙

### 3.1 ID 정책: 의미는 유지, 교육과정/언어/렌더러만 분리

검토안의 "ID에 의미를 넣지 말라"는 WhyMath `part9_id_policy_review.md`와 충돌한다. WhyMath 정책은:

> ID는 curriculum(학년/개정판), language(locale), renderer(표시 방식)에 종속되지 않는다. 단, 수학 개념의 의미적 정체성(`geometry`, `limit`, `calculus`)은 ID에 담는다.

### 3.2 Concept Core에 subject-specific 필드 주입 금지

수학 전용 필드(`latex_formula`, `proof_required`, `graph_type`)는 `Concept` Core에 두지 않는다. Subject-specific profile은 별도 테이블/Registry에서 관리.

### 3.3 PG 단일 평면 유지

Concept identity의 authoritative store는 PostgreSQL이다. Graph DB(Neo4j)는 data-pipeline optional extra의 실험 경로뿐, 런타임 의존 금지.

### 3.4 AI 생성 Concept 검증 게이트

AI가 생성한 Concept/Relation은 `DRAFT`/`REVIEW` 상태로 두고, Rule/Validator/Human Review를 거쳐 `APPROVED`/`ACTIVE`로 전이. 바로 배포하지 않는다.

### 3.5 Relation vocabulary 상한

신규 relation type 추가는 7~8개 상한 내에서. 무분별한 edge type 증식은 KG 관리 불가능성을 초래.

### 3.6 Prerequisite DAG 강제 (r2)

선수관계 순환은 "가능하면 회피"가 아니라 **hard error**로 강제한다. data-pipeline 검증기의 `prerequisite_cycle` 규칙(concept_graph·atom_graph·skill_graph 공통)이 단일 권위이며, 런타임은 DAG 보장을 전제로 재귀 순회한다(`api/me.py:1503`). 신규 edge 유입 경로(수작업 YAML, AI 제안, API)는 모두 이 검증기를 통과해야 ACTIVE로 승격 가능하다.

현행 보장 경계를 명시한다: 순환 검증은 data-pipeline 변환 단계(graph.json 산출 시)에서 수행되고, 런타임 적재 CLI(`l1/concept_graph/populate.py` ④단계)는 `populate_backend_edges`를 검증 호출 없이 upsert하므로 임의 `--graph` 입력에는 hard-error 보장이 미적용이다. 적재 경로에도 동일 검증기를 배선하는 것을 후속 태스크로 둔다(§4).

### 3.7 품질 점수의 게이트 사용 금지 (r2)

Concept Quality Score류의 가중치 합산 점수는 대시보드·우선순위 지표로만 사용한다. 배포·승격·완료 판정의 게이트로 사용하려면 `superhuman_verification_standard.md`에 따라 측정 기반 임계값(Wilson 단측 경계, exit 0/1 판정)으로 재정의해야 하며, 점추정 점수 그대로의 게이트화는 금지한다.

### 3.8 이벤트 concept_refs는 스냅샷 (r2)

학습 이벤트에 기록하는 `concept_refs`는 **기록 시점 스냅샷**임을 스키마 주석으로 명시한다. 단, 현행 `AttemptEvent`·`EvidenceEvent` 모델은 `concept_refs`를 영속하지 않으므로(activity.py:238·evidence_event.py:54 — `objective_id`·`problem_id`만 보유), 이 원칙의 적용에는 이벤트 스키마에 `concept_refs` 영속 또는 버전드 매핑(versioned problem→concept mapping) 도입이 선행돼야 한다. 그 전까지 매핑 변경 후 재생(replay)되는 숙련 추정이 현행 매핑으로 소급 재귀속되는 한계를 인정하고, 현행 매핑 기준 재해석은 명시적 교정 마이그레이션으로 한정한다.

### 3.9 Concept Contract 금지 필드 조항 (r2)

EOS Concept Contract(검토안 §61) 수용 시 13번 조항으로 "Concept 노드는 renderer·curriculum·prompt·misconception·UI·embedding·외부 저작권 텍스트를 내장하지 않는다(`_FORBIDDEN_NODE_FIELDS` 정적 차단)"를 추가한다.

### 3.10 canonical_key 변경과 불변 참조 분리 (r2)

사람이 읽는 키(`canonical_key`)는 변경 가능성을 허용하되, 라이브 키의 UNIQUE 제약은 유지한다 — 변경 가능성과 UNIQUE는 모순이 아니며, UNIQUE는 두 개념이 동일 키로 해석되는 조회 모호성을 막는 장치다. 금지 대상은 이 키를 *참조 기준(FK 대상)*으로 삼는 것이고, 불변 참조는 `concept_id`(`math.<area>.<slug>`)가 담당한다. 개명된 옛 키는 `aliases` + `ids.yaml` registry가 흡수한다.

---

## 4. 후속 태스크

아래 태스크는 `scripts/harness/backlog.py add`로 등재한다:

1. **Prerequisite Edge 메타 확장**: `ConceptEdge`에 `required_strength`, `dependency_level`, `minimum_mastery`, `curriculum_context`, `evidence_source_id` 추가 설계.
2. **Concept Resolver API**: curriculum context-aware 개념 해석 API 설계(embedding + canonical key 우선).
3. **Concept Quality/Coverage 관리자 뷰**: 관리자 CMS에 Concept Coverage Matrix(Concept × Objective × Problem × Explanation × Misconception × Visualization) 표시.
4. **Concept Search API 확장**: `GET /concepts/{id}/relations|prerequisites|misconceptions|problems|objectives|explanations|visualizations` 및 `POST /concepts/resolve` 추가.
5. **Concept Lifecycle + Merge/Split 설계**: `status` 전이 룰, `merged_into`/`split_into` 관리, audit trail. Phase 2.
6. **Cross-subject Concept Mapping 설계**: 수학 외 과목 확장 시 `subject_node` 및 cross-subject `related_to` 정책. Phase 2+.
7. **런타임 적재 경로 DAG 검증 배선** (r2, PR #897 리뷰 반영): `l1/concept_graph/populate.py` ④단계 `populate_backend_edges`가 `prerequisite_cycle` 검증 호출 없이 upsert한다. data-pipeline 검증기와 동일 규칙을 적재 경로에도 적용해 임의 `--graph` 입력에도 hard-error가 적용되게 한다.
8. **이벤트 concept_refs 영속화** (r2, PR #897 리뷰 반영): `AttemptEvent`·`EvidenceEvent`에 `concept_refs` 스냅샷(또는 versioned problem→concept mapping)을 영속해 §3.8 원칙을 실제 replay에 적용 가능하게 한다.

---

## 5. 참고 문서

- `docs/architecture/concept_node_layering_decision.md` — ConceptNode 9계층·12노드 taxonomy
- `docs/architecture/eos_curriculum_semantic_backbone_adr.md` — EOS Curriculum DB 검토 수용 ADR
- `docs/standards/eos_identity_layer_011_1_decision.md` — EOS Identity & ID Domain 수용 결정
- `docs/architecture/01_data_foundation.md` — L1 데이터 기반, Concept Graph
- `docs/standards/part9_id_policy_review.md` — Concept canonical ID 정책
- `schemas/v1.1/concept.schema.yaml` — Concept 엔티티 명세
