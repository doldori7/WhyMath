# EOS Curriculum Semantic Backbone 채택 ADR

> **상태**: 초안 (2026-08-25)
> **범위**: EOS 지향 교육앱을 위한 『1_교육과정 데이터베이스』 설계 검토(22개 항목)를 WhyMath 현행 설계와 대조하여 부분 수용
> **관련**: `docs/architecture/curriculum_module_gap_review_r2.md`, `docs/standards/eos_identity_layer_011_1_decision.md`, `schemas/v1.1/curriculum_entry.schema.yaml`, `backlog/tasks/CUR-04`~`CUR-09`

---

## 1. 결정 요약

**교육과정 DB를 EOS의 Core Reference Model(Semantic Backbone)로 격상**하는 방향은 채택한다.

그러나 WhyMath는 이미 `Concept` DAG를 영속 원본으로 두고, 교육과정/단원/성취기준을 **Overlay**로 취급하는 정본이 확립되어 있으므로, 검토안의 `curriculum_node` 1급 독립 트리를 신설하는 대신 **기존 개념 백본 위에 Curriculum Framework/Version/Alignment/Outcome을 레이어로 쌓는다**.

| 영역 | 판정 | 근거 |
|---|---|---|
| Curriculum Framework / Version 분리 | ✅ 채택 (Phase 1) | `CurriculumEntry`·`AchievementStandard`에 `framework_id`/`version_id` 식별자 정비 |
| Stable ID 체계 | ✅ 이미 충족 | `norm_id`·`entry_id`·`concept_id` 운영 중 |
| Curriculum Node + Learning Outcome 분리 | ⚠️ 부분 채택 | 개념 원본(`Concept`)은 유지. Outcome/Competency는 `AchievementStandard` 확장으로 단계적 분리 |
| Curriculum Alignment 별도 엔티티 | ⚠️ 부분 채택 | 기존 `ConceptStandardLink`·`CurriculumEntry.national_standard_codes`·`AtomNode.standard_codes`를 통합 뷰로 정리. 물리 테이블 추가는 Phase 2 |
| Source / Provenance 관리 | ✅ 이미 충족·확장 | `source_*`·`license_id`·`verified_by`·`confidence` 유지, `source` 1급 테이블은 Phase 2(011_1 후속) |
| Sequence ≠ Prerequisite 분리 | ✅ 이미 추적 중 | `CUR-09`에서 Sequence/Prerequisite 분리 가설 관측 중 |
| Subject-neutral API | ✅ 이미 충족·확장 | `/v1/curricula/{framework_id}/...` API 확장 |
| Competency 모델 | ⚠️ Phase 1.5 | `AchievementStandard`에 `cognitive_level`·`mastery_definition` 추가 |
| Curriculum-to-Curriculum Mapping | ⚠️ Phase 2 | 2015↔2022 개정 매핑은 `ConceptStandardLink.link_type="재매핑"`으로 부분 충족 |
| Concept Graph 연계 | ✅ 이미 충족 | `Concept` DAG + `AtomNode` 원자 백본 |
| Misconception 연계 | ✅ 이미 충족·확장 | `l4/misconception/` + `Concept` 연결 |
| Rubric / Mastery Criteria | ⚠️ Phase 2 | `AchievementLevelUnit`이 단원 단위 등급 보유(개별 성취기준 연결은 후속) |
| 국제 교육과정 매핑 | ⚠️ Phase 2~3 | `CurriculumEntry` 다국 매트릭스 셀이 토대. CCSS/IB/AP 즉시 확장은 Phase 3 |
| 1EdTech CASE 1.1 어댑터 | ❌ Phase 2 | 매핑표만 작성, 코드 어댑터는 Phase 2 |
| W3C Verifiable Credentials | ❌ Phase 2+ | ID/provenance 안정화로 향후 연결 가능 |

---

## 2. 검토안 22개 항목 × WhyMath 현행 매핑

### 2.1 관점 전환 (§1)

검토안이 제시한 "Curriculum Framework → Learning Outcome → Content/Assessment/Activity → Learner Event → Mastery State" 흐름은 WhyMath 7계층 아키텍처와 정렬된다.

- **WhyMath 현행**: L1 `Concept`·`AchievementStandard`·`CurriculumEntry`가 Framework/Outcome 역할. L2/L3/L4가 Content/Assessment/Activity/Tutor를 생성/소비. L5~L6가 이벤트를 생성. L2 `ConceptMasteryHistory`·`Assessment`가 Mastery State 역할.
- **차이**: WhyMath는 L1의 중심이 **개념(Concept)**이지 교육과정(Curriculum)이다. 교육과정은 개념 위의 Overlay로 봄.

### 2.2 핵심 8영역 (§2)

| 영역 | WhyMath 대응 | 상태 |
|---|---|---|
| Curriculum Framework | `CurriculumEntry`가 country_code/revision/source_name으로 암시적 운영 중 | `framework_id` 명시화 필요 |
| Subject | `CurriculumEntry.subject`, `AchievementStandard.subject`, `schema/enums.py` `Subject` | ✅ |
| Grade/Education Level | `introduced_grade`, `grade_band`, `school_type` | ✅ |
| Unit/Topic | `Concept` DAG + `atom_node.parent_code` + `UnitSpec` | ✅ |
| Learning Outcome | `AchievementStandard.statement` 계열 | 확장 필요 |
| Competency | 없음 | `AchievementStandard`에 추가 |
| Relationship | `ConceptEdge`(`PREREQUISITE`) | ✅ |
| Alignment | 흩어짐 | 통합 뷰 필요 |

### 2.3 권장 최상위 구조 (§3)

검토안:
```
curriculum_framework
 ├─ curriculum_version
 ├─ education_level
 ├─ subject
 ├─ domain
 ├─ curriculum_node
 ├─ competency
 ├─ prerequisite
 ├─ curriculum_relationship
 └─ curriculum_alignment
```

WhyMath 채택안:
```
CurriculumFramework (new)
 └─ CurriculumVersion (new)
      └─ CurriculumEntry (existing)   # concept × country × subject
           ├─ AchievementStandard (existing)  # KR column = national outcomes
           ├─ Concept (existing)              # universal concept backbone
           └─ ConceptEdge/AtomNode (existing) # relationship & prerequisite

CurriculumAlignment (view/report, not physical table yet)
 └─ ConceptStandardLink
    CurriculumEntry.national_standard_codes
    AtomNode.standard_codes
```

### 2.4 curriculum_node 중심 설계 (§4)

**의도적 미채택**. WhyMath는 `Concept`가 영속 원본이고 `CurriculumEntry`가 Overlay다. 별도 `curriculum_node` 트리를 두면 개념-교육과정 이중 표현이 생겨 `import-linter` 7계층 원칙과 CLAUDE.md "표현 ≠ 의미" 원칙에 위배될 수 있다.

대안: `CurriculumEntry`에 `domain_label`/`sub_domain_label`/`introduced_context` 등 검토안의 node 속성을 이미 갖추고 있음. 필요 시 `curriculum_node`는 **PostgreSQL 뷰**나 **read model**로만 제공.

### 2.5 Learning Outcome의 중요성 (§5)

**부분 채택**. `AchievementStandard`가 이미 official statement를 가지므로, Phase 1에서는 이를 Learning Outcome으로 간주. 추가 필드를 넣어 EOS 표현력을 높인다:

- `cognitive_level`: 블룸/인지수준
- `mastery_definition`: 숙달 기준 서술
- `observable`: 관찰 가능 여부
- `assessmentable`: 평가 가능 여부
- `knowledge_type`: 개념/절차/메타인지 등

### 2.6 Content ↔ Curriculum 직접 연결 금지 (§6)

**채택**. WhyMath는 `Problem`이 `unit_codes`·`achievement_standard_codes`(atom 노드)로 개념/성취기준을 참조하고, 직접 `curriculum_id`는 없다. `curriculum_alignment` 물리 테이블은 Phase 2에서 도입.

### 2.7 다중 교육과정 지원 (§7)

**이미 충족**. `CurriculumEntry`는 `(concept_id, country_code, subject)` 복합키로 다국 매트릭스를 표현. Phase 1은 KR/US/IMO 3축, Phase 3가 9~12개국 확장.

### 2.8 framework/version 분리 (§8)

**Phase 1 채택**. 현재 `CurriculumEntry.curriculum_revision`과 `AchievementStandard.version_id`가 있으나, 별도 `CurriculumFramework`/`CurriculumVersion` 테이블이 없다. `framework_id` 식별자를 도입하고 기존 컬럼은 하위호환용으로 유지.

### 2.9 temporal/역사적 보존 (§9)

**부분 채택**. `effective_from`/`effective_to`·`status`·`version_id`는 이미 존재. **DB 이력 테이블(audit trail)**은 현재 "YAML=소스, DB=산출물, git=이력" 원칙에 따라 Phase 2로 유보(2028 개정 시행이 트리거).

### 2.10 ID 체계 통합 (§10)

**이미 충족**. WhyMath는 의미론적 canonical ID(`math.<area>.<slug>`, `UC.<domain>.<topic>.<slug>`, `norm_id`)를 사용. CASE의 GUID 요구와도 충돌하지 않음(UUID PK는 내부용, canonical ID는 외부/논리용).

### 2.11 sequence ≠ prerequisite (§11)

**CUR-09에서 관측 중**. 현재 `db/models/`에 sequence 컬럼이 없음. `atom_node.parent_code`가 계층, `ConceptEdge.PREREQUISITE`가 의존성. `CurriculumEntry`에 `sequence_order`/`order_index` 추가를 가설로 관측.

### 2.12 Concept Graph 연결 (§12)

**이미 충족**. `Concept` DAG + `AtomNode` 원자 백본 + `ConceptStandardLink`가 이미 그래프 중심축.

### 2.13 Misconception 연결 (§13)

**이미 충족·확장**. `l4/misconception/` 모듈이 존재. `crosslink_standard_signal.py`가 성취기준 신호를 소비.

### 2.14 추천 핵심 테이블 (§14)

EOS MVP 추천 11개 테이블 중 WhyMath는 다음을 이미 갖춤:
- `education_level` → `CurriculumEntry.grade_band`, `AchievementStandard.school_type`
- `subject` → `CurriculumEntry.subject`, `AchievementStandard.subject`
- `curriculum_node` → `Concept` + `CurriculumEntry` 뷰
- `learning_outcome` → `AchievementStandard`
- `competency` → `AchievementStandard` 확장으로 대체
- `curriculum_relationship` → `ConceptEdge` + `CurriculumEntry.prerequisite_concept_ids`
- `curriculum_alignment` → 흩어진 링크들 → 통합 뷰로 정리

### 2.15 관계 구조 (§15)

WhyMath 현행도 유사한 구조를 갖추고 있으나, 중심이 **Concept**다. 본 ADR은 이 중심축을 유지하면서 Curriculum Framework/Version/Outcome을 명시적으로 겹쳐 표현.

### 2.16 AI가 교육과정을 직접 해석 금지 (§16)

**채택**. CLAUDE.md "검증 권위 서열"과 일치. AI는 candidate alignment만 제안하고, Rule/Validator/Human Review를 거쳐야 정식 alignment가 된다. `CurriculumEntry.confidence`·`verified_by` 필드가 이 gate를 표현.

### 2.17 Source of Truth / Tier (§17)

**채택**. WhyMath의 tier:
- TIER 0: 공식 고시 원문(NCIC PDF) + git
- TIER 1: `AchievementStandard`·`CurriculumEntry`
- TIER 2: `verified_by`가 채워진 alignment
- TIER 3: LLM candidate alignment(현재는 별도 저장 없음)
- TIER 4: AI inference

### 2.18 Source 상세화 (§18)

**부분 채택**. `CurriculumEntry`/`AchievementStandard`에 이미 `source_name`·`source_code`·`source_url`·`source_document`·`license_id`가 있음. `content_hash`·`document_locator`·`page`·`section`은 Phase 2 `source` 1급 테이블(011_1 후속)에서 추가.

### 2.19 Subject-neutral API (§19)

**채택·확장**. 신규 API:
- `GET /v1/curricula`
- `GET /v1/curricula/{framework_id}`
- `GET /v1/curricula/{framework_id}/nodes`
- `GET /v1/learning-outcomes/{norm_id}`
- `GET /v1/alignments`

기존 `/v1/me/target-progress`는 그대로 유지.

### 2.20 P0 개선사항 7개 (§20)

| # | 항목 | WhyMath 상태 |
|---|---|---|
| ① | Framework/Version 분리 | Phase 1 신규 테이블 |
| ② | Stable ID | ✅ |
| ③ | Node + Outcome 분리 | 부분 채택(Outcome 확장) |
| ④ | Alignment 별도 엔티티 | 통합 뷰(Phase 1) / 물리 테이블(Phase 2) |
| ⑤ | Source/Provenance | ✅ + Phase 2 1급 테이블 |
| ⑥ | Sequence ≠ Prerequisite | CUR-09 관측 |
| ⑦ | Subject-neutral API | Phase 1 확장 |

### 2.21 EOS 전체 위치 (§21)

WhyMath 7계층과의 대응:
```
L1: Concept + AchievementStandard + CurriculumEntry(Curriculum DB)
L2: ConceptMasteryHistory + TargetProgress
L3: Content Generation + Assessment Generation
L4: PolyaCoach + Misconception Engine
L5: HTTP API + Flutter client
L6: Learning scene / Tutor mode
L7: Community (Phase 3)
```

### 2.22 최종 결론 (§22)

**교육과정 DB는 WhyMath의 Core Reference Model로 격상되나, Concept 원본 위의 Overlay로 격상된다.**

---

## 3. Phase 1 실행 항목

1. **`CurriculumFramework` 테이블 신설**
   - `framework_id` PK(str, 의미 문자열)
   - `authority`, `country`, `title`, `description`
   - `effective_from`, `effective_to`, `status`
   - Alembic 마이그레이션 (additive)

2. **`CurriculumVersion` 테이블 신설**
   - `version_id` PK(UUID)
   - `framework_id` FK
   - `version_label`, `effective_from`, `effective_to`, `status`, `source_id`

3. **`CurriculumEntry`·`AchievementStandard`에 `framework_id` nullable 추가**
   - 기존 `curriculum_revision`은 deprecated 유지
   - 마이그레이션: 기존 행은 default framework(KR_NC_2022) 할당

4. **`AchievementStandard` Learning Outcome 확장**
   - `cognitive_level`·`mastery_definition`·`observable`·`assessmentable`·`knowledge_type` nullable 추가

5. **Subject-neutral Curriculum API 확장**
   - `/v1/curricula/*` 라우터 추가

6. **`CurriculumAlignment` 통합 조회 함수/리포트**
   - 기존 3개 축(`ConceptStandardLink`·`CurriculumEntry.national_standard_codes`·`AtomNode.standard_codes`)을 하나의 `get_alignments(concept_id, framework_id, outcome_id)` 함수로 통합
   - `api/coach.py`·`l2/target_progress.py`·`l3` 생성기가 이 함수를 경유하도록 리팩토링

7. **CASE 1.1 매핑표 작성**
   - `docs/standards/case_1_1_mapping.md` — Framework/Item/Association/Rubric ↔ WhyMath 엔티티 대응표

---

## 4. Phase 2 이관 항목

- `curriculum_node` 물리 테이블(필요 시)
- 별도 `LearningOutcome`/`Competency` 테이블
- `curriculum_alignment` 물리 테이블
- 1EdTech CASE 1.1 REST/JSON 어댑터
- W3C Verifiable Credentials 연결
- DB 이력(audit trail) 테이블

---

## 5. 결정 로그

- 2026-08-25: EOS Curriculum Semantic Backbone 검토안 부분 수용 결정. Concept 원본 위에 Curriculum Framework/Version/Outcome/Alignment를 Overlay로 쌓는 방향 확정.
