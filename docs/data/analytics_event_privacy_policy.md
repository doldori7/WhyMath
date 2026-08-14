# 분석 이벤트 개인정보·보존 정책 (v1)

- **적용 범위:** `AnalyticsEventEnvelope`를 통과하는 신규 분석 생산 이벤트
- **정본 코드:** `src/backend/whymath_backend/schema/analytics_event.py`
- **타입별 payload 정본:** `src/backend/whymath_backend/schema/event_data_contract.py`
- **보존 집행:** `src/backend/whymath_backend/privacy/retention.py`
- **상태:** P0 계약. DB 영속화와 event UUID unique constraint는 DP-03에서 추가한다.

## 목적 제한

이벤트는 제품 품질, 학습 흐름의 집계 분석, 운영 장애 진단에만 사용한다. 학생 원문이나 개인을 재식별할 수 있는 값을 분석 이벤트에 넣지 않는다. 학생 풀이 데이터를 모델 학습에 사용하려면 이 정책과 별도의 명시적 동의·목적·보존 정책을 충족해야 한다.

## 공통 envelope

| 필드 | 분류 | 목적 | 보존/삭제 소유자 |
|---|---|---|---|
| `event_uuid` | 가명 식별자 | 재전송 멱등성 | `privacy.retention.purge_expired_records` (DP-03 영속화 후) |
| `schema_version` | 비개인 | 계약 호환성 | 이벤트 보존과 함께 파기 |
| `occurred_at` | 저위험 메타 | 사건 시각 | 이벤트 보존과 함께 파기 |
| `received_at` | 저위험 메타 | 수신 지연·순서 분석 | 이벤트 보존과 함께 파기 |
| `source` | 비개인 | backend/mobile 신뢰 경계 | 이벤트 보존과 함께 파기 |
| `session_id` | 가명 식별자 | 세션 단위 집계 | 이벤트 보존과 함께 파기 |
| `correlation_id` | 가명 식별자 | 요청/흐름 상관관계 | 이벤트 보존과 함께 파기 |
| `event_type` | 비개인 | 타입별 집계 | 이벤트 보존과 함께 파기 |
| `payload` | 타입별 allowlist | 이벤트 의미 | 이벤트 보존과 함께 파기 |

## payload 규칙

1. `EventType`별 payload는 `EVENT_DATA_CONTRACT`에 등록된 Pydantic 모델만 허용한다.
2. 계약이 없는 휴면 이벤트 타입은 분석 producer가 만들 수 없다.
3. 다음 키와 동등 의미의 중첩 키는 금지한다.
   - 원문: 채팅, 메시지, 학생 답안, 풀이, 수식/LaTex, OCR 결과
   - 파일·링크: 이미지, 손글씨, 이미지 URL, URL query/query string
   - 정밀 행동·식별: x/y 좌표, 영구 기기 ID, 광고 ID, 설치 ID
4. allowlist에 없는 키는 `extra="forbid"`로 거부한다.
5. 이벤트에는 이름, 이메일, 전화번호, 학교/학년 조합 등 직접 식별자도 추가하지 않는다. 해당 데이터가 제품 기능에 필요하면 분석 이벤트와 별도 접근통제 저장소를 사용한다.

## 현재 생산 이벤트의 PII 등급

| EventType | 허용 payload | PII 등급 | 분석 저장 허용 |
|---|---|---|---|
| `검산결과` | `passed`, `error_kind`, `mode`, `persona` | 낮음 — 오류 분류만 | 허용 |
| `힌트제공` | `hint_level`, `mode`, `persona` | 낮음 — 노출 레벨만 | 허용 |
| `시각화조작` | 기존 봉투 계약 | **P0 보류** | payload 내부 자유형이므로 분석 envelope producer에 연결하지 않음 |
| 그 외 휴면 EventType | 없음 | 미정 | producer 금지 |

`시각화조작`의 기존 `payload`는 조작별 자유형이라 P0의 타입별 allowlist 원칙과 맞지 않는다. 해당 이벤트를 분석 envelope에 연결하기 전에 별도 세부 allowlist와 PII 검토를 추가한다.

## 보존·삭제

- PostgreSQL `AttemptEvent` 보존 파기는 `purge_expired_records()`가 `event_at` 기준으로 집행한다.
- 보존 연수는 `Settings.pii_retention_years`가 정하며 현재 구현 기본값은 3년이다.
- 외부 분석 저장소(ClickHouse, object store 등)를 도입하기 전에는 동일한 보존·삭제·백업·접근통제·정합성 검증 경로를 설계하고 검증해야 한다.
- `event_uuid`/`received_at`의 DB 영속 및 PostgreSQL unique 제약은 DP-03의 migration 전까지 완료로 간주하지 않는다.

## 검증

`tests/backend/schema/test_analytics_event.py`는 다음을 검증한다.

- 필수 envelope, schema version, 발생/수신 시각 의미
- unknown top-level field 거부
- 금지 PII 키 거부
- 타입별 payload allowlist 강제
- mobile source의 session ID 요구
- 수신 시각이 발생 시각보다 빠른 입력 거부
