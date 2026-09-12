# ADR-002 — 학생 풀이 step 기록: attempt_event 확장이 아니라 별도 정규 엔티티

- **상태:** 채택
- **결정일:** 2026-08-30
- **대상:** EOS-46-solution-step-event (`docs/architecture/32_learning_history.md` §4 SolutionStep 갭)
- **관련:** ADR-001(이벤트 저장소 PostgreSQL 우선), `schemas/v1.0/schema_v1.0.md` §6.1, EOS-32(`answer_submission`)·EOS-45(`hint_usage`), `db/models/solution_node.py`(WH-S)

## 맥락

학생이 풀이를 *단계(step)* 단위로 제출할 때 "어느 단계에서 오류가 났는가"를 학습하는 데이터가 필요하다(32_learning_history §4 — 정오답 최종값만으로는 오개념 위치가 손실). 요구 필드는 attempt FK·sequence·expression·canonical_ast·validation·concept_ids다.

저장 형태의 후보는 둘이다:

- **(A) `attempt_event` 확장** — 기존 `event_type_enum`에 신규 타입(예: `단계제출`)을 추가하고 `event_data` JSONB에 expression·AST·검증 결과를 싣는다.
- **(B) 별도 정규 엔티티** — EOS-32(`answer_submission`)·EOS-45(`hint_usage`) 계열의 신규 테이블.

판정은 hypertable **정본**(schemas/v1.0)과 **실측**(ADR-001) 양쪽에 대조한다.

## 실측 대조

| 실측 대상 | 사실 | 근거 |
|---|---|---|
| hypertable 정본 | `attempt_event`는 `PRIMARY KEY (event_id, event_at)`·`create_hypertable(chunk 1 day)`로 선언된 **불변 시계열**("실시간 분석용") | `schemas/v1.0/schema_v1.0.md` §6.1 L672-687 |
| hypertable 실측 | 운영 DB는 pgvector/pg16 — TimescaleDB extension 없음. `create_hypertable`은 조건부 실행이라 현재 `attempt_event`는 일반 테이블이나, **정본 의도는 hypertable이며 전환 조건·절차가 ADR-001에 예약**돼 있다 | ADR-001 §근거·§TimescaleDB 전환 조건 |
| event_data 계약 | `_EventPayload` 서브클래스들은 **경량 신호**(int·str 태그 몇 개 — `hint_level`·`server_latency_ms`·`turn_count`)만 계약한다. 넓은 구조 페이로드 선례 0건 | `schema/event_data_contract.py` |
| EventType 확장 비용 | `event_type_enum`은 PG native enum — 신규 타입은 enum ALTER 마이그레이션을 부른다. 기존 코드가 이 비용 때문에 신규 이벤트 대신 payload 태그를 택한 선례가 명문화돼 있다("신규 EventType은 PG enum ALTER를 부르므로 JSONB 페이로드에 싣는다" — PED-04 D2) | `event_data_contract.py` `client_state_mismatch` 주석 |
| attempt_event 참조 무결성 | `attempt_id`·`user_id`·`problem_id` 전부 **FK 없음**(느슨참조·hypertable 제약) — EOS-32 PR #902 P1이 확립한 (attempt_id, user_id) 복합 FK 소유 정합을 적용할 수 없다 | `db/models/activity.py` AttemptEvent |
| 행 식별 | `attempt_event` PK는 `(BIGSERIAL, event_at)` 복합 — 외부(오개념 `evidence_links` 등)가 특정 step 행을 안정적으로 가리킬 UUID 정체성이 없다 | 같은 곳 |
| 동종 선례 | 다회 제출(EOS-32)·힌트 사용(EOS-45)이 같은 판단("이벤트 payload는 본문·판정을 담지 않는다 — 정규 엔티티 신설")으로 이미 착지 | `answer_submission`·`hint_usage`·32_learning_history §4 |
| 기존 step 흔적 | `problem_attempt.step_times` JSONB(시간만)·`attempt_event`의 `계산`·`그래프그리기` 등 telemetry(본문 없음) — step *내용*의 좌석은 현재 0 | §6.1 DDL·EventType enum |

## 결정

**(B) 별도 정규 엔티티 `student_solution_step`을 신설한다.** EOS-32/45 관례를 전부 적용한다: (attempt_id, user_id) 복합 FK 소유 정합(참조 대상 UNIQUE는 EOS-32 것 재사용)·JSONB `none_as_null=True`·privacy 3종 배선(red→green)·alembic 체인(EOS-45 head `0e148995e6e9` 뒤).

판정 기준별 근거:

1. **이벤트인가 엔티티인가** — step 기록은 발생 후 불변(append-only 관행·32 §6)이라는 점은 이벤트와 같으나, 행 하나가 **후속 소비의 1급 대상**이다: 오개념 `evidence_links`가 "3번째 step의 오류"를 가리키고, step 재구성 API가 attempt 단위로 정렬 조회한다. 안정 UUID PK·FK 정합이 필요한 *참조되는 데이터*는 엔티티다. `attempt_event`는 반대로 *집계되는 신호*다(복합 PK·FK 0·시계열 스캔).
2. **payload 폭** — `canonical_ast`(구조 정본)·`expression`(LaTeX 본문)은 hypertable 압축·경량 신호 계약(`_EventPayload`)에 정면으로 어긋난다. 정본 의도대로 attempt_event가 hypertable로 전환되는 순간(ADR-001 예약) 넓은 JSONB는 chunk 압축·보존 정책의 부채가 된다. 이벤트 계약의 무결성(경량 신호만)을 지키는 것이 계약 오염을 막는다.
3. **조회 패턴** — step 재구성은 `WHERE attempt_id ORDER BY sequence_no`(엔티티 읽기), attempt_event는 `WHERE user_id AND event_at 범위`(시계열 분석). 접근 패턴이 다른 데이터를 한 테이블에 두면 인덱스·보존 정책이 서로를 방해한다.
4. **EOS-32/45 정합** — 답 제출·힌트 사용·풀이 step은 전부 "attempt 내 학생 행위의 정규 기록"이라는 같은 부류다. 같은 부류가 같은 형태(복합 FK 소유 정합·privacy 3종 균일 경로)를 가져야 privacy 감사·완전성 스윕이 단일 패턴으로 동작한다.

## 기각 대안 — (A) attempt_event 확장

기각 근거(검토 결함):

- **enum ALTER 비용**: 신규 `event_type` = PG enum ALTER 마이그레이션. 기존 코드가 이 비용을 피해 payload 태그를 택한 선례(PED-04 D2)와 역행.
- **계약 위반**: `_EventPayload`는 경량 신호 계약이다. expression·canonical_ast·validation을 실으면 이벤트 계약의 "봉투 타이핑" 원칙이 무너지고, 하네스 지표 집계(⑤·⑫)가 읽는 스트림에 이질 페이로드가 섞인다.
- **소유 정합 불가**: FK 0(hypertable 제약)이라 "A의 attempt + B의 user_id" 오염을 DB가 못 막는다 — EOS-32 P1에서 실결함으로 판정된 바로 그 구멍을 신규 데이터에 다시 연다.
- **행 정체성 부재**: 복합 PK(BIGSERIAL, event_at)는 evidence_links의 안정 참조 대상이 될 수 없다.
- **erasure 비대칭**: attempt_event는 느슨참조라 고아 방지 트리거(20260604_0200)에 의존한다 — 정규 FK CASCADE + 명시 삭제 계획이 가능한 데이터를 굳이 약한 경로에 두지 않는다.

**부분 채택(하이브리드) 기각**: "본문은 테이블·발생 신호는 이벤트 병행 발행"도 검토했으나, 신호 소비자(하네스 지표)가 아직 step 신호를 요구하지 않는다 — 소비자 없는 이벤트 발행은 날조성 계측이다(필요해지면 payload 태그 방식으로 후속 추가 가능·enum ALTER 불요).

## 명칭·책임 구분 (혼동 금지 — 3자 대조)

| 이름 | 데이터 주체 | 책임 |
|---|---|---|
| **`student_solution_step`** (신설·EOS-46) | **학생**(미성년 PII 계열) | 학생이 제출한 풀이 단계의 정규 기록 — 오류 위치 학습·오개념 증거 입력 |
| `solution_nodes`(`SolutionNode`) | **시스템**(WH-S 솔버) | MCTS 탐색 트리 노드 — AI 내부 상태·학생 데이터 아님·API 노출 0 |
| `problem_step`(`ProblemStep`) | **콘텐츠**(저작) | 문항의 정본 풀이 단계(교수 설계) — 학생 제출물 아님 |

`student_` 접두가 데이터 주체를 이름에 박는다(32 §4 경고 "SolutionNode는 학생 데이터 아님 — 명칭·책임 명시 구분"의 이행). ORM docstring 양쪽에도 동일 구분을 명시한다.

## 결과

- 신설: `db/models/student_solution_step.py`·`schema/student_solution_step.py`·alembic `student_solution_step`(EOS-45 뒤 체인).
- privacy 3종: erasure(`user_id`·attempt보다 먼저)·retention(`submitted_at`)·export(`student_solution_steps`) — 완전성은 `test_erasure_plan_completeness`가 동결.
- 백필: 없음(의도적) — 과거 step *내용*의 원천이 존재하지 않는다(`step_times`는 시간만·telemetry 이벤트는 본문 없음). 재구성은 날조다(32 §4 이관 전략 EOS-46 항 참조).
- attempt_event·event_data_contract는 **무변경**.
