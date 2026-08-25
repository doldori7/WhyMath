# 204. EOS Education Event System

> **범위**: 학습자·교사·AI·콘텐츠·평가·지식그래프·운영 시스템에서 발생하는 교육적 사건을 표준화하여 기록·전달·재생하고, 학습자 모델·평가·개인화·AI Tutor·분석·감사가 소비할 수 있게 하는 EOS 공통 이벤트 인프라.
> **상태**: 설계 확정 진행 중 (2026-08-25). MVP는 Operational DB + Education Event Stream(Outbox) 구조.
> **관련**: `docs/architecture/44_eos_version_management.md`, `docs/architecture/90_audit_log.md`(ADMIN-10), `docs/architecture/02_learner_model.md`, `docs/standards/eos_identity_layer_011_1_decision.md`, `backlog/tasks/E204-02-education-event-system.yaml`

---

## 1. 핵심 정의

**Education Event System**은 EOS 내부에서 일어난 모든 교육적 상태 변화와 학습 상호작용을 표준 사건(event)으로 표현하고 전달하는 **공통 이벤트 백본**이다.

이것은 단순 클릭 로그나 학습이력 수집기가 아니다.

```
Student / Teacher / Parent / AI / CMS
              │
              ▼
       Domain Services (L1~L4)
 ┌────────────────────────────┐
 │ Problem / Tutor / Learning │
 │ Assessment / Content / KG  │
 └────────────────────────────┘
              │
              ▼
   204 Education Event SDK
              │
              ▼
 Canonical Education Event
              │
              ▼
       Event Gateway
              │
       Event Bus / Stream
              │
 ┌────────────┼────────────┬─────────────┐
 ▼            ▼            ▼             ▼
Learner     Analytics     Audit       AI/Agent
Model       Warehouse     Pipeline     Pipeline
 │
 ▼
Mastery / Misconception /
Recommendation / Learning Path
```

---

## 2. 핵심 설계 원칙 8가지

1. **Canonical Education Event**: EOS 내부 표준 봉투. 외부 표준(xAPI/Caliper/CloudEvents)은 Adapter로 연결.
2. **Event Taxonomy + Event Registry**: 모든 이벤트는 등록되고 버전/도메인/PII/보존/생산자/소비자가 명시.
3. **Concept/Skill/Objective/Misconception ID 연결**: 이벤트 payload에는 이름 대신 안정적 ID reference + version.
4. **Observation ↔ Inference ↔ Decision ↔ Intervention 분리**: 관찰·추론·결정·개입을 별도 이벤트 유형으로 분리.
5. **correlation / causation / trace 추적**: event_id, correlation_id, causation_id, trace_id, parent_event_id.
6. **Immutable + versioned event**: 이벤트는 수정하지 않고 정정 이벤트로 표현.
7. **Education Event ↔ Audit ↔ Telemetry 분리**: 교육 이벤트는 분석/개인화/AI에, 감사는 규제/보안에, 텔레메트리는 UI/제품에.
8. **xAPI / Caliper / CloudEvents는 내부 모델이 아닌 Adapter**: 외부 표준 변경이 EOS 내부를 흔들지 않게.

---

## 3. 7계층 아키텍처에서의 위치

204 Education Event System은 **횡단 관심사(cross-cutting)**다.

- **L5 상호작용**: 이벤트 생산 (학생 앱, coach API, OCR, 시각화)
- **L4 교수학 엔진**: 추론/결정/개입 이벤트 생성
- **L3 콘텐츠 생성·검증**: AI 이벤트 생성/검증
- **L2 학습자 모델**: 이벤트 소비 → 학습자 상태 projection
- **L1 데이터 기반**: 개념/성취기준/오개념/스킬 ID reference의 진실 원천
- **90 Audit**: 별도 감사 스트림. 일부 사건은 Canonical Event에서 Audit Projection으로 전달.

```
L5 ──produces──┐
L4 ──produces──┼──▶ 204 Education Event System ──▶ L2 Learner Model Projection
L3 ──produces──┤       (canonical event stream)        (current state DB)
L1 ──references┘
```

---

## 4. Canonical Education Event Envelope

### 4.1 봉투 필드

```python
class EducationEvent(BaseModel):
    event_id: str                    # UUIDv7 권장 (발생 시각 내장·정렬)
    event_type: str                  # "problem.answered" (domain.past-tense-action)
    event_version: str               # "1.2"

    occurred_at: datetime            # 도메인 사건 발생 시각 (클라/서버)
    recorded_at: datetime            # 서버가 수신/기록한 시각
    processed_at: datetime | None     # 처리 완료 시각 (선택)

    actor: Actor                     # {actor_type, actor_id}
    session: Session                 # {session_id, learning_session_id}
    object: Object                   # {entity_type, entity_id, entity_version}

    context: EducationContext        # subject_id, curriculum_id, grade,
                                     # unit_id, objective_id, concept_ids[], skill_ids[]

    payload: dict[str, Any]          # event_type별 계약 (event_data_contract)

    source: Source                   # {service, client}

    trace: Trace                     # {trace_id, correlation_id, causation_id, parent_event_id}

    privacy: Privacy                # {classification, contains_pii, consent_scope,
                                     #  retention_policy_id, ai_training_allowed}

    schema_version: str              # "education-event@1.0"
```

### 4.2 Actor / Session / Object / Context

```python
class Actor(BaseModel):
    actor_type: str                  # "learner" | "teacher" | "parent" | "ai" | "system"
    actor_id: str | None             # UUID 또는 의사ID (pseudonymized)

class Session(BaseModel):
    session_id: str | None           # API/장치 세션
    learning_session_id: str | None  # 학습 세션 (learning_session)

class Object(BaseModel):
    entity_type: str                 # "problem" | "concept" | "hint" | "solution" | "assessment" ...
    entity_id: str                   # 안정적 ID
    entity_version: str | None       # version_id (44_eos_version_management.md)

class EducationContext(BaseModel):
    subject_id: str | None
    curriculum_id: str | None
    grade: str | None
    unit_id: str | None
    objective_id: str | None
    concept_ids: list[str] = []
    skill_ids: list[str] = []
    misconception_ids: list[str] = []
    pedagogy: PedagogyContext | None = None

class PedagogyContext(BaseModel):
    strategy_id: str | None
    strategy_version: str | None
    intervention_reason: str | None
    explanation_mode: str | None     # "socratic" | "polya" | "direct" | ...
```

### 4.3 Privacy 메타데이터

```python
class Privacy(BaseModel):
    classification: str                # "anonymous" | "pseudonymous" | "pii" | "sensitive"
    contains_pii: bool
    consent_scope: str | None        # "learning_analytics" | "ai_training" | ...
    retention_policy_id: str | None  # "RET-LEARN-03"
    ai_training_allowed: bool | None
```

---

## 5. Event Taxonomy

### 5.1 최상위 분류

```
EDUCATION_EVENT
├── interaction          # problem.viewed, hint.requested, video.started
├── learning             # problem.attempted, concept.studied, skill.demonstrated
├── assessment           # assessment.started, response.scored, mastery.updated
├── knowledge            # concept.created, prerequisite.added, misconception.updated
├── curriculum           # curriculum.mapping.updated, curriculum.version.activated
├── learner_model        # ability.estimated, risk_score.updated
├── misconception        # misconception.detected, misconception.corrected
├── pedagogy             # pedagogy.strategy.selected
├── tutoring             # tutor.question.submitted, tutor.response.presented
├── content              # content.published, problem.approved
├── AI                   # ai.tutor.invoked, ai.response.validated
├── collaboration        # peer.discussion.joined
├── parent               # parent.report.viewed
├── teacher              # teacher.assignment.created
├── agent                # agent.action.executed
└── system               # vector.embedding.created, content.indexed

SECURITY_EVENT          # user.login.failed, permission.denied (별도)
AUDIT_EVENT             # admin.problem.deleted, user.role.changed (90 Audit)
OPERATIONAL_EVENT       # deployment.completed, db.backup.succeeded
```

### 5.2 이벤트 명명 규칙

- `<domain>.<past-tense-action>`
- 예: `problem.answered`, `hint.generated`, `misconception.detected`, `mastery.updated`
- Command와 Event 구분:
  - Command: `generate_hint`
  - Event: `hint.generated`

---

## 6. Event Registry

### 6.1 Registry 항목

```python
class EventRegistryEntry(BaseModel):
    event_type: str
    schema_version: str
    domain: str
    description: str

    producer: list[str]                # ["problem-service", "coach-service"]
    consumer: list[str]                # ["learner-model", "analytics"]

    required_fields: list[str]
    optional_fields: list[str]

    pii_classification: str           # "low" | "medium" | "high"
    retention_policy_id: str
    analytics_allowed: bool
    ai_training_allowed: bool

    status: str                        # "draft" | "active" | "deprecated" | "retired"
    deprecated_at: date | None
    replacement_event: str | None
```

### 6.2 Registry 저장

- YAML/JSON 파일: `data/education_event_registry.json`
- 런타임 로드 + 거버넌스 테스트: 모든 EventType은 registry에 등록되거나 명시적 exemption

---

## 7. Observation / Inference / Decision / Intervention

핵심 루프:

```
Observation
    ↓
Reasoning / Inference
    ↓
Decision
    ↓
Intervention
    ↓
Response
    ↓
New Observation
```

예시 체인:

```
evt100  problem.failed                  (Observation)
evt101  misconception.inferred          (Inference)
        → evidence: [evt100]
        → confidence: 0.87
evt102  pedagogy.strategy.selected    (Decision)
        → causation_id: evt101
evt103  hint.generated                (Intervention/Action)
        → causation_id: evt102
evt104  hint.viewed                   (Observation)
evt105  problem.solved                  (Observation)
        → correlation_id: learning_loop_123  (entire chain)
```

---

## 8. Causation / Trace

```python
class Trace(BaseModel):
    trace_id: str                      # 전체 흐름 식별
    correlation_id: str | None         # 관련 사건 그룹
    causation_id: str | None           # 직접 원인이 된 이벤트
    parent_event_id: str | None        # 상위 이벤트
```

---

## 9. Education Event vs Audit vs Telemetry

| 구분 | 목적 | 예시 | 소비처 |
|---|---|---|---|
| **Education Event** | 학습 분석·개인화·Mastery·AI Tutor·Knowledge Fabric | `problem.solved`, `hint.used`, `misconception.inferred` | L2, L4, Analytics, AI Pipeline |
| **Audit Log** | 보안·책임추적·규제 대응·포렌식 | `admin.problem.deleted`, `user.permission.changed` | Compliance, Admin Dashboard |
| **Product Telemetry** | UI/UX 제품 개선 | `button.clicked`, `page.loaded` | Product Analytics |

Canonical Event에서 일부 사건은 Audit Projection으로도 전달될 수 있다.

---

## 10. Event Store & State Projection

### 10.1 초기 MVP 구조

```
PostgreSQL
   │
   ├─ Transactional Tables
   │
   └─ Outbox Table
          ↓
      Event Bus (初期: PG queue / 큐비즈교체가능 인터페이스)
          ↓
   ┌────────┴────────┐
   ▼                 ▼
Learner Model     Analytics
Projection        Warehouse
```

### 10.2 완전 Event Sourcing은 초기 MVP에 권하지 않음

- 초기: Operational DB + Education Event Stream
- 향후: Event Store + State Projection + Replay Engine

---

## 11. Event Bus 기술

EventBus 인터페이스를 논리 설계에 두고 구현체는 교체 가능.

```python
class EventBus(Protocol):
    async def publish(self, event: EducationEvent) -> None: ...
    async def subscribe(self, event_type: str, handler: Handler) -> None: ...
```

초기 구현: PostgreSQL 기반 Outbox + Queue
성장 시: Kafka / Pulsar / Redpanda / Cloud Pub/Sub / Kinesis

---

## 12. 외부 표준 Adapter

```
EOS Canonical Event
       │
       ├── xAPI Adapter
       ├── Caliper Adapter
       ├── CloudEvents Adapter
       ├── LRS Adapter
       └── Research Export Adapter
```

- CloudEvents: infrastructure envelope 참고
- Caliper/xAPI: learning interoperability 참고
- EOS Event: 교육 의미 모델

---

## 13. Event SDK

```python
from whymath_backend.events.sdk import EducationEventSDK

sdk = EducationEventSDK(registry=registry)

event = sdk.emit(
    event_type="problem.answered",
    actor_type="learner",
    actor_id="usr_...",
    object_type="problem",
    object_id="prob_...",
    payload={...},
    context={...},
    trace={...},
    privacy={...},
)
```

SDK가 자동 처리:
- event_id 생성 (UUIDv7)
- occurred_at / recorded_at
- schema validation
- source metadata
- trace_id / correlation_id
- privacy classification lookup
- version 자동 적용

---

## 14. MVP 핵심 이벤트 20~30개

Phase 1~2에서 먼저 정의할 이벤트:

```
learning.session.started

problem.viewed
problem.attempted
problem.answered
problem.solved
problem.failed

hint.requested
hint.viewed

solution.viewed

response.scored

concept.practiced

misconception.inferred

mastery.updated

tutor.question.submitted
tutor.response.presented

pedagogy.strategy.selected

learning_path.generated
learning_path.adjusted

assessment.started
assessment.completed

ai.requested
ai.generated
ai.validated
ai.rejected
```

---

## 15. Idempotency & Ordering

- **Idempotency**: event_id / event_uuid 기준 중복 처리
- **Ordering**: 전역 순서 추종 금지. learner_id / learning_session_id / assessment_id를 partition key로 사용
- **Delivery**: 중복 허용 + idempotency key. "exactly once"보다 중복 처리 중심.

---

## 16. Replay Engine

향후 숙련도 모델 교체 시 historical events 재생 가능.

```
Historical Events
       ↓
Mastery Engine v3
       ↓
New Learner State
```

MVP에서는 replay 인터페이스 설계만.

---

## 17. PII & Privacy

- 이벤트에 원문 채팅·풀이·이미지·URL query·정밀 좌표·영구 기기 ID 금지
- PII는 pseudonymization / tokenization / crypto-shredding 별도 설계
- 보존 기간은 정책 엔진으로 관리

---

## 18. 관련 모듈 및 파일

| 파일 | 설명 |
|---|---|
| `src/backend/whymath_backend/schema/education_event.py` | Canonical Event Envelope |
| `src/backend/whymath_backend/schema/event_taxonomy.py` | Event Taxonomy enum |
| `src/backend/whymath_backend/schema/event_registry.py` | Registry loader + validator |
| `src/backend/whymath_backend/events/sdk.py` | Event SDK |
| `src/backend/whymath_backend/events/adapters/*.py` | xAPI/Caliper/CloudEvents adapters |
| `src/backend/whymath_backend/db/models/education_event.py` | EducationEvent ORM |
| `src/backend/whymath_backend/db/models/event_outbox.py` | Transactional Outbox ORM |
| `data/education_event_registry.json` | Event Registry 데이터 |
| `tests/backend/schema/test_education_event*.py` | 봉투/Registry 거버넌스 테스트 |

---

## 19. 구현 단계

| Phase | 내용 |
|---|---|
| Phase 1 | Canonical Event Envelope + Taxonomy + Registry |
| Phase 2 | Event SDK + Outbox + Event Bus 인터페이스 |
| Phase 3 | Concept/Skill/Objective/Misconception ID 연결 |
| Phase 4 | Observation/Inference/Decision/Intervention 분리 |
| Phase 5 | Problem/Hint/Tutor 핵심 이벤트 배선 |
| Phase 6 | Learner Model Projection |
| Phase 7 | xAPI/Caliper/CloudEvents Adapter |
| Phase 8 | Audit/Telemetry 분리 + Observability |

---

## 20. 참고

- 1EdTech Caliper Analytics 1.2 (Final)
- xAPI (Experience API / Tin Can API)
- CloudEvents 1.0 + CESQL 1.0
