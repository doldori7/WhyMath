# 90. EOS Audit Log (감사 로그)

> **범위**: EOS/WhyMath 플랫폼 전체의 책임추적성·보안·AI 거버넌스·교육 콘텐츠 provenance를 위한 공통 감사 이벤트 Foundation.
> **상태**: 설계 확정 (2026-08-25). P0 MVP + P1/P2 확장 범위.
> **관련**: `docs/architecture/44_eos_version_management.md`, `docs/standards/security_privacy.md`, `docs/architecture/account_security_gap_review.md`, `src/backend/whymath_backend/db/models/audit.py`

---

## 1. 핵심 설계 원칙

1. **Audit Log는 독립 Foundation이다.** 보안·개인정보·콘텐츠·지식·AI·학습자 모델 변경 모두를 가로지르는 횡단 인프라로 설계한다.
2. **Actor는 사람만이 아니다.** `user`, `ai_agent`, `service_account`, `cron_job`, `migration`을 1급 Actor로 기록한다.
3. **구조화 이벤트로 저장한다.** 문자열 로그(`"kim changed problem"`)가 아니라 `actor`·`action`·`resource`·`result`·`context` 구조로 저장한다.
4. **Version과 Audit는 분리하되 연결한다.** Audit는 *누가·왜* 바꿨는지, Version은 *무엇이* 바뀌었는지를 각각 담당한다. Audit는 `version_id`만 참조한다.
5. **Audit Log는 append-only다.** UPDATE/DELETE API/route를 두지 않으며, DB role도 `INSERT`/`SELECT`만 허용한다.
6. **PII는 최소화한다.** 학생 이름·전화·이메일·답·프롬프트 원문 등은 Audit에 저장하지 않는다.
7. **request/trace/workflow ID로 사건을 재구성한다.** 하나의 관리자 작업이 여러 서비스를 거칠 때 correlation이 가능해야 한다.
8. **AI model/prompt/version/validation을 추적한다.** Prompt 원문은 저장하지 않고, `prompt_template_id`·`prompt_version`·`input_hash`·`output_hash`만 남긴다.
9. **Audit Log 조회·export 자체도 감사한다.** 감사 권한은 별도 역할로 제한하고, 감사 열람/반출은 다시 Audit에 남긴다(P1).
10. **장기적으로 Educational Knowledge Provenance로 확장한다.** Audit를 단순 보안 로그가 아니라 콘텐츠 출처·검증·승인·배포의 provenance 기반으로 발전시킨다.

---

## 2. WhyMath 현행 감사 인프라와의 관계

현재 `src/backend/whymath_backend/db/models/audit.py`에 세 개의 append-only 테이블이 운영 중이다.

| 테이블 | 목적 | 특성 |
|---|---|---|
| `deletion_audit` | 본인 리소스 삭제 이력 | 메타만, FK 아닌 plain UUID |
| `privacy_audit` | 개인정보 반출·동의·역할변경 | PII 미저장, `ip_hash`, 자유텍스트 0 |
| `defect_report` | 학생 콘텐츠 오류 신고 | `user_id` 컬럼 없음(PII 최소화) |

이들은 각각 전용 목적과 강한 불변식을 가지고 있으므로, **P0에서 즉시 통합하지 않는다**. 새로운 범용 `audit_event` 테이블을 추가하여 두 체계가 **병존**한다. 향후 통합 여부는 별도 태스크로 검토한다.

---

## 3. Audit Event 표준 스키마

### 3.1 필드 정의

```text
audit_event
  audit_event_id          UUID PK
  occurred_at             TIMESTAMPTZ NOT NULL

  actor_type              VARCHAR(32) NOT NULL   -- user / ai_agent / service_account / cron_job / migration
  actor_id                VARCHAR(128)           -- UUID 또는 서비스 식별자
  actor_role              VARCHAR(64)            -- content_admin 등

  action                  VARCHAR(128) NOT NULL  -- knowledge.concept.update, problem.answer.update

  resource_type           VARCHAR(64) NOT NULL
  resource_id             VARCHAR(128) NOT NULL

  before_version          VARCHAR(64)            -- version_id 참조
  after_version           VARCHAR(64)            -- version_id 참조
  changed_fields          VARCHAR(64)[]           -- 변경된 필드명 배열만

  authorization_decision  VARCHAR(32)            -- allow / deny
  reason_code             VARCHAR(64)            -- ERROR_FIX / CURRICULUM_UPDATE / AI_CORRECTION / ADMIN_OVERRIDE 등
  reason_text             VARCHAR(500)           -- 사람 입력 변경 사유(선택, PII 금지)

  request_id              VARCHAR(128)
  trace_id                VARCHAR(128)
  workflow_id             VARCHAR(128)
  source_service          VARCHAR(64) NOT NULL   -- problems / l3_router / role_grant_cli 등

  status                  VARCHAR(32) NOT NULL    -- success / failure
  severity                VARCHAR(16) NOT NULL    -- INFO / NOTICE / WARNING / HIGH / CRITICAL

  metadata                JSONB                   -- 확장, PII 금지
  retention_policy_id     VARCHAR(32) NOT NULL    -- RET_PRIVACY / RET_SECURITY / RET_CONTENT / RET_AI / RET_CRITICAL

  integrity_hash          VARCHAR(64)             -- P2
  previous_hash           VARCHAR(64)             -- P2
```

### 3.2 이벤트명 규칙

`<domain>.<resource>.<action>` 형태로 통일한다.

- `auth.login.success`
- `iam.role.assign`
- `privacy.student.export`
- `curriculum.objective.update`
- `knowledge.concept.merge`
- `knowledge.edge.delete`
- `problem.answer.update`
- `ai.problem.generate`
- `ai.content.approve`
- `assessment.score.override`
- `learner.mastery.override`
- `cms.content.publish`

### 3.3 Actor 유형

| actor_type | 의미 | 예 |
|---|---|---|
| `user` | 인증된 사람 사용자 | `usr_123` |
| `ai_agent` | AI 생성·수정·분류기 | 모델명 + prompt_version |
| `service_account` | 내부 서비스/Celery worker | `problem-bank-worker` |
| `cron_job` | 예약 작업 | `retention-purge` |
| `migration` | 데이터 마이그레이션 | `migration-2026-08` |

---

## 4. MVP(P0) 범위

### 4.1 P0 데이터 모델

- `audit_event` 테이블 및 ORM
- `AuditEventActorType`, `AuditEventSeverity` enum
- `audit.emit(...)` SDK

### 4.2 P0 이벤트

- **권한 변경**: `iam.role.assign`, `iam.role.revoke`
- **인증**: `auth.login.success`, `auth.login.failure`
- **콘텐츠 변경**: `curriculum.*`, `knowledge.concept.*`, `knowledge.edge.*`, `problem.*`
- **AI**: `ai.problem.generate`, `ai.content.approve`

### 4.3 P0 API/SDK

- `audit.emit(session, ...)` — Audit 행을 `session.add()`만 하고 commit은 호출자.
- `GET /v1/admin/audit-events` — 역할 기반 접근 제어(향후 CMS UI 연동).

---

## 5. P1/P2 확장

### P1

- `severity`, `retention_policy_id` 기반 조회/아카이브
- Audit Log 조회·export·archive 자체 감사
- CMS 검색/상세 UI 및 diff 보기(Version Management 연동)
- Alert 연동

### P2

- hash-chain / signed batch / WORM archive
- SIEM 연동
- anomaly detection

---

## 6. 보안·개인정보·보존

### 6.1 PII 최소화

- `metadata` JSONB 내부에 학생 이름, 전화, 이메일, 답, prompt 원문, 세션 토큰 등을 금지.
- `changed_fields`는 필드명 배열만 저장.
- 필요 시 원본은 version store나 별도 권한 통제 후 조회.

### 6.2 Append-only 보장

- `audit_event`에 대한 UPDATE/DELETE API/route 금지.
- DB application role에게 `INSERT`/`SELECT`만 부여.
- 향후 P2에서 PG trigger/hash-chain으로 강화.

### 6.3 보존 정책

코드에 하드코딩하지 않고 `retention_policy_id`로 관리.

| 정책 | 예시 보존기한 | 대상 |
|---|---|---|
| `RET_PRIVACY` | 3년 | 개인정보 접근·반출·동의 |
| `RET_SECURITY` | 3년 | 로그인·권한 변경 |
| `RET_CONTENT` | 3년 | 콘텐츠·지식그래프 변경 |
| `RET_AI` | 3년 | AI 생성/승인 |
| `RET_CRITICAL` | 7년 | 정답 변경·Audit 정책 변경 |

법적 최소 보존기한(국내 PIPA/안전성 확보조치 기준) 변동 시 정책 테이블만 갱신.

---

## 7. AI Audit

### 7.1 AI Audit Event 예시

```json
{
  "action": "ai.problem.generate",
  "actor_type": "ai_agent",
  "actor_id": "problem-generator",
  "ai": {
    "provider": "openai",
    "model": "model_xyz",
    "model_version": "2026-08",
    "prompt_template_id": "problem-gen",
    "prompt_version": "v21",
    "temperature": 0.2,
    "input_hash": "sha256:...",
    "output_hash": "sha256:..."
  },
  "resource": {
    "resource_type": "Problem",
    "resource_id": "prob_123"
  },
  "validation": {
    "validator_version": "math-validator-v8",
    "result": "pass"
  }
}
```

### 7.2 AI Trace 저장소

별도 저장소를 신설하지 않고, **Langfuse를 그대로 활용**한다. `audit_event`에는 `trace_id` 또는 `langfuse_trace_id`를 `metadata`에 넣어 Langfuse 원문을 참조한다.

---

## 8. 학습 이벤트와의 분리

학생 학습 행동(`student_answer_submitted`, `hint_requested`, `problem_viewed`, `concept_mastered`)은 `attempt_event` 등 분석 테이블에 남기고, `audit_event`에는 관리자 권한 변경·콘텐츠 변경·AI 승인 등 **책임추적 대상**만 남긴다.

---

## 9. 버전 관리와의 연결

Audit는 `before_version`/`after_version` 문자열 식별자만 저장하고, 실제 스냅샷은 `Version Store`에서 조회한다. `docs/architecture/44_eos_version_management.md`의 `VersionHeader`·`ProblemVersion`·`ConceptVersion`·`SolutionVersion` 설계를 따른다.

---

## 10. 구현 순서

1. `docs/architecture/90_audit_log.md` 작성 (본 문서)
2. `AuditEventActorType`, `AuditEventSeverity` enum 추가
3. `AuditEvent` Pydantic 스키마 및 ORM 모델 추가
4. Alembic 마이그레이션 생성
5. `audit.emit(...)` SDK 작성
6. P0 이벤트 배선
7. 회귀 테스트 작성
8. 조회 API 추가
9. CI 통과 후 PR 생성

---

## 11. 피해야 할 설계

1. Debug Log를 Audit Log로 사용하는 것
2. 문자열만 저장하는 것
3. Audit Log 수정/삭제 허용
4. 개인정보를 Audit에 중복 저장
5. AI 작업을 `system`으로 뭉개는 것 — `ai_agent`로 구분
6. Version Log와 Audit Log를 하나로 만드는 것
