# 011_1 EOS Identity & ID Domain 수용 결정

> **범위**: 첨부된 EOS 설계안(`Entity/Content/Subject/Learner/Event/Version/Source ID`)을 WhyMath 현행 설계와 대비하여 검토·부분 수용.
> **상태**: 2026-08-17 Kiki 지시로 부분 수용 결정.
> **관련**: `docs/standards/part9_id_policy_review.md`, `schemas/v1.0/schema_v1.0.md`, `src/backend/whymath_backend/schema/problem.py`

---

## 1. 요약

첨부 내용은 **방향은 맞으나 전면 수용은 거부**한다. WhyMath는 Phase 1(MVP)이며, 이미 `Concept` canonical ID(`math.<area>.<slug>`), locale 분리, `ids.yaml` registry 등 강력한 ID 정책이 정착되어 있다. 따라서 첨부안의 몇 가지 원칙(특히 “ID는 무의미하다”, “Unified Entity 슈퍼테이블”)은 WhyMath 설계 정신과 직접 충돌한다.

**최종 판정**: 7개 ID Domain을 `011_1 EOS Identity & ID Domain`으로 채택하되, 세부 구현은 WhyMath 원칙에 맞게 수정하고 Phase 2 이관 항목은 별도 태스크로 분리한다.

---

## 2. WhyMath 현행 상태

| ID Domain | 현재 구현 | 파일 |
|---|---|---|
| **Entity ID** | 통합 슈퍼타입 없음. 도메인별 독립 UUID PK(`problem_id`, `concept_id`, `user_id` 등) | `src/backend/whymath_backend/schema/*.py` |
| **Content ID** | `Problem.problem_id`(UUID) + `identity_id`(변형 계열) + `external_id`(외부 원본) | `src/backend/whymath_backend/schema/problem.py` |
| **Version ID** | `Problem.curriculum_version`(교육과정 버전), `EvidenceEvent.pack_version`. 명시적 `content_version`은 없음. | `src/backend/whymath_backend/db/models/evidence_event.py` |
| **Subject ID** | `Subject` enum(`공통/미적분/확통/기하/인공지능수학`)을 `problem.subject`에 직접 사용. 수학 외 확장은 보류. | `src/backend/whymath_backend/schema/enums.py` |
| **Learner ID** | `UserProfile.user_id`만 존재. 역할 분리 없음. | `src/backend/whymath_backend/schema/user.py` |
| **Event ID** | `AnalyticsEventEnvelope.event_uuid`(멱등키), `attempt_event.event_id`(BIGSERIAL+time PK), `evidence_event` 하이퍼테이블. 통합 Event Entity는 없음. | `src/backend/whymath_backend/schema/analytics_event.py`, `src/backend/whymath_backend/db/models/evidence_event.py` |
| **Source ID** | `Problem.source_type`(enum) + `source_detail`(JSONB). 별도 `Source` 객체/Provenance 그래프는 없음. | `src/backend/whymath_backend/schema/problem.py`, `src/backend/whymath_backend/schema/enums.py` |
| **Identifier Registry** | `Concept`에 `ids.yaml` + `aliases`로 canonical ID 및 옛 키 매핑 보존. `Problem`에는 없음. | `docs/standards/part9_id_policy_review.md`, `data/corpus/concept_graph_v1/ids.yaml` |

---

## 3. 첨부 설계안 항목별 판정

| # | 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | **7개 ID Domain 정의 (011_1)** | ✅ 채택 | EOS Identity Layer 범위 확정 |
| 2 | **Unified `Entity` 슈퍼테이블 (방법 B)** | ❌ 보류 | 7계층 독립성 해치고 마이그레이션 비용 큼. WhyMath는 도메인별 UUID PK 유지 |
| 3 | **“ID는 의미를 포함하지 않는다”** | ❌ 거부/수정 | WhyMath는 curriculum/language/renderer 무관하되 **의미론적 canonical ID** 사용. `part9_id_policy_review.md`에서 `math.<area>.<slug>`로 확정 |
| 4 | **Content ID ≠ Content Version ID** | ✅ 채택 | `identity_id`로 변형 계열은 묶지만 명시적 content_version은 없음. 별도 태스크로 구현 |
| 5 | **Subject = Ontology (`parent_subject_id`)** | ⚠️ 부분 채택 | 수학 외 과목 확장 시 `subject_node` 신설. 현재는 `Concept` DAG로 일부 충족 |
| 6 | **Learner ID ≠ User ID** | ⚠️ 부분 채택 | Role 분리로 점진 적용. MVP에서는 `user_id` 유지 |
| 7 | **Event = raw fact** | ✅ 채택 | `AnalyticsEventEnvelope` allowlist + 금지 키 차단 정신과 일치 |
| 8 | **Source 객체 + Provenance Chain** | ⚠️ 부분 채택 | `source_type`/`source_detail` → 별도 `source` 테이블로 점진 이관 |
| 9 | **External ID Registry / CASE / W3C PROV** | ❌ Phase 2 이관 | MVP 범위 밖 |
| 10 | **Identifier Registry 일반화** | ⚠️ Phase 2 이관 | `ids.yaml` 패턴을 Problem/Subject/Source까지 확장하는 것은 후속 |

---

## 4. WhyMath 수정 원칙

### 4.1 ID 정책: 의미는 유지, 교육과정/언어/렌더러만 분리

첨부안의 “ID에 의미를 넣지 말라”는 WhyMath `part9_id_policy_review.md`와 충돌한다. WhyMath 정책은:

> ID는 curriculum(학년/개정판), language(locale), renderer(표시 방식)에 종속되지 않는다. 단, 수학 개념의 의미적 정체성(`geometry`, `limit`, `calculus`)은 ID에 담는다.

따라서 다음 안티패턴만 금지한다:

- `MATH-HIGH-ALG-001`(학년/교육과정 결합)
- `KR2022.math2.limit`(언어·교육과정 결합)
- `CONTENT_001_V3`(버전을 ID에 포함)

### 4.2 Unified Entity 슈퍼테이블 보류

모든 객체를 단일 `entity` 테이블로 묶는 설계는 장기적으로 매력적이나, WhyMath 7계층 아키텍처는 L1~L4가 독립 수학 코어이며 상위가 하위를 호출하는 단방향 의존(import-linter)을 강제한다. 슈퍼테이블은 계층 간 결합을 증가시키고, `entity_type` 판별 로직이 모든 계층에 퍼지게 된다.

**대안**: 논리적으로는 `entity_id` namespace를 인정하되, 물리적으로는 각 도메인이 독자 UUID PK를 유지한다. 교차 참조가 필요할 때는 `correlation_id`·`external_id`·별도 Identifier Registry(Phase 2)를 사용한다.

### 4.3 MVP vs Phase 2 경계

| 단계 | 채택 항목 | 보류/이관 항목 |
|---|---|---|
| **Phase 1 (MVP)** | Content Version 분리 설계, Event raw fact 강화, Source 객체화 착수 | — |
| **Phase 2** | Learner/User 역할 분리, Subject ontology 확장(수학 외), External ID Registry, CASE/W3C PROV 연결 | Unified Entity 슈퍼테이블(필요성 재검토) |

---

## 5. 후속 태스크

아래 태스크는 `scripts/harness/backlog.py add`로 등재한다:

1. **Content Version 분리**: `Problem`에 nullable `content_version_id` 추가, `ContentVersion` 스키마/ORM/마이그레이션 설계.
2. **Source 엔티티 분리**: 별도 `source` 테이블(Pydantic + ORM + Alembic) 설계, `Problem.source_type`/`source_detail` 이관 계획 수립.
3. **Learner/User 역할 분리**: `Role` 테이블 및 `learner_profile` 분리 설계. 점진 적용 방안.
4. **Subject ontology 확장 설계**: 수학 외 과목(물리·화학·생물·지구과학 등)용 `subject_node` 모델링.
5. **External ID Registry 및 CASE/W3C PROV 연결 (Phase 2)**: `ids.yaml` 패턴을 Problem/Subject/Source로 확장, 1EdTech CASE/W3C PROV 매핑 설계.

---

## 6. 참고 문서

- `docs/standards/part9_id_policy_review.md` — Concept canonical ID, locale 분리, `ids.yaml` registry
- `schemas/v1.0/schema_v1.0.md` — v1.0 DDL 및 도메인 설계
- `src/backend/whymath_backend/schema/problem.py` — Problem ID/Identity/External ID
- `src/backend/whymath_backend/db/models/evidence_event.py` — Event 시계열 모델
- `src/backend/whymath_backend/schema/analytics_event.py` — Event envelope
- `src/backend/whymath_backend/schema/enums.py` — `SourceType`, `Subject`
