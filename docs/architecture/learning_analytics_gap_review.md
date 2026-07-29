# 학습 분석(Learning Analytics) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-29)

> **범위**: 외부 참고 문서 『학습 분석』(기능 32~36: 학습 이력 관리 · 약점 분석 · 실력 예측 ·
> 학습 리포트 · 추천 학습 — **WhyMath 전용이 아닌 일반적 EOS 틀**, Kiki 제공)을 현 코드베이스와
> 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(미성년 프라이버시·날조 금기·dead code
> 금기·측정 위장 금기·7계층 경계) 안에서 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(모듈 6~10, 2026-07-27) ·
> `problem_bank_gap_review.md`(11~22, 07-28) · `solution_module_gap_review.md`(23~27, 07-29)
> 답습 — 같은 EOS 틀 시리즈 **4편째**.
> **결론**: 이 모듈은 **"엔진은 있는데 계측이 비어 있는"** 비대칭이다. BKT·IRT·개념 진단·선수
> 추천·적응형 출제는 실가동하는데, 그 *아래*(수집)와 *위*(집계·서술) 두 층이 비어 있다. 최대
> 실행 갭은 **`LearningSession` writer 0** — 세션을 만드는 코드가 저장소 전체에 없어, 이미
> 완료된 두 측정 하네스(`pilot_kpi_baseline` KPI2 리텐션 · `wh1_evaluation` 지표 ③ 세션
> 완주율)가 **구조적으로 영원히 빈 입력**을 받는다. 파일럿(S3-01) 전에 닫지 않으면 소급 불가능한
> 학생 데이터를 잃는다. 의도적 미채택 6건, 진짜 갭 설계 D1~D6, 실행 5건을 백로그에 등재했다
> (S3-16·S3-17·S4-18·S4-19·S4-20).

관련 정본: `02_learner_model.md`(BKT·IRT·DKT 도입 임계) · `04_pedagogy_engine.md`(발화 톤) ·
`07_community.md`(교사·학부모 대시보드 Phase 3~4) · `docs/standards/superhuman_verification_standard.md`
(측정 권위 서열) · `docs/data/licensing_safety.md`(콘텐츠 추천 저작권 레일) ·
`MEMORY.md` 결정 로그(2026-07-29).

---

## §0. 전제 — 실측 현황 스냅샷 (2026-07-29)

§1~§3의 모든 판정 근거다. 수치·writer 유무는 전건 저장소 실측이며, 부록에 명령·행 번호를 남긴다.

| 축 | 실측 |
|---|---|
| **이벤트 write 전수** | `api/me.py:596` ProblemAttempt · `api/interactions.py:75` AttemptEvent(시각화조작) · `api/coach.py:922,977` AttemptEvent(검산결과·힌트제공) · `api/coach.py:1400` Dialogue · `l2/mastery_tracking.py:134`·`l2/skill_mastery_tracking.py:136` 숙달 시계열 · `api/me.py:923` AbilitySnapshot(**수동 POST** — 자동 산출 아님) · `l4/misconception/evidence_store.py:75` 증거(라이브 coach가 `coach.py:1469,1477,1680,1687`에서 실호출) |
| **writer 0 테이블 (5)** | `learning_session` · `assessment` · `daily_learning_metrics` · `user_behavior_metrics` · `problem_solve_time_distribution` — 인스턴스화가 `db/models`·`schema` 정의부 밖에 **0건** |
| **EventType** | 11종 중 **3종만 생산**(검산결과·힌트제공·시각화조작). `schema/enums.py:843`이 "나머지 8종은 생산자가 아직 0이라 계약 면제(휴면)"를 자인 |
| **ProblemAttempt 미기록 컬럼** | `started_at`·`attempt_mode`·`used_socratic`·`used_hint`·`used_solution_view`·`stuck_at_step`·`stuck_at_concept_id`·`time_vs_expected`·`step_times`(항상 `[]`) — 컬럼은 있고 삽입부(`api/me.py:596-607`)가 설정하지 않음 |
| **세션 생명주기** | `GET /v1/me/sessions`(`me.py:300`) · `PATCH /v1/me/sessions/{id}/end`(`me.py:1793`) · `DELETE`(`me.py:1849`) — **생성(POST)만 없음**. `ProblemAttempt.session_id`는 클라가 보낸 값을 그대로 받는데(`me.py:597`) 부모 행이 만들어진 적이 없다 |
| **측정 하네스 굶주림** | `harness/pilot_kpi_baseline.py:812` KPI2 리텐션 · `harness/wh1_evaluation.py:1052` 지표 ③ 세션 완주율 — 둘 다 `LearningSession` 질의 → 항상 0건 → `NO_DATA`(`wh1_evaluation.py:1078`) |
| **L4 자인** | `l4/pedagogy/runtime_selector.py:101` — "집중도(`LearningSession.focus_score`)·학습시간 … 컬럼은 있으나 **쓰는 코드가 없어 항상 NULL**이다 … 해당 축이 필요해지면 **생산자를 먼저** 만들고 그때 필드를 연다" |
| **망각** | `l2/bkt.py:109 apply_forgetting` 구현 + `l2/mastery_tracking.py:69` 실호출. 그러나 `_DEFAULT_P_FORGET = 0.0`(`bkt.py:40`)이고 **설정 주입 경로 0**(`config.py`에 BKT 파라미터 없음) → 감쇠 실효과 0 |
| **예측** | `db/models/assessment.py:98,99,100,105` `estimated_grade`·`estimated_score`·`estimated_percentile`·`admission_probability` 컬럼 실재 · **계산 코드 0** |
| **약점 축** | 개념 축 단일(`l2/concept_diagnosis.py:71 compute_concept_diagnoses` — BKT↔IRT 교차 판정). `l2/` 전체에 성취기준·문제유형 참조 **0건**(`achievement_standard`·`problem_type_node` 모델은 실재) |
| **성취기준 조인 축(중요)** | 살아 있는 축은 `atom_node.standard_codes`다. `api/gating.py:127-131`이 자인 — 구 4단계 조인(`concept_standard_link` → `achievement_standard`)은 **S2-03 원자 재연결 후 0행**. 신규 설계는 반드시 원자 축(`ProblemConcept→Concept→AtomNode`)을 쓴다 |
| **dead 모듈** | `l2/evidence_event_store.py`(`EvidenceEventStore`) — src 호출자 0, 테스트 2곳만(`tests/backend/l2/`·`tests/backend/api/test_e2e_pedagogy_pilot_integration.py`) |
| **리포트·역할** | 리포트 생성 코드 **0** · `db/models/user.py`에 role/teacher/parent 개념 없음(부모 *동의* 필드만) · **Celery beat 없음**(`config.py:632`가 "운영은 Celery beat·cron으로 일일 호출 권장"으로 외부 위임) |
| **추천** | 개념·문항 축 실가동(`l2/weak_concept_recommendation`·`prerequisite_recommendation`·`learning_path` → `api/me.py`·`api/coach.py`). **복습 타이밍(간격 반복) 없음**(`apply_forgetting`이 스케줄러에 미연결) |
| **피드백 루프** | 교수학 *처치* 축은 실재(`l2/pedagogy_evidence` ← `api/study.py:198,244` → `l4/pedagogy/adaptive/effectiveness.py:139`). **추천(개념·문항) 수용·성과 루프는 없음** |
| **GDPR 배선** | writer 0인 3 hypertable도 export·erasure·retention에 이미 등록(`privacy/export.py:103-104`·`erasure.py:92-93`·`retention.py:55-56`) — **지우고 내보낼 수는 있는데 채워지지 않는다** |
| **백로그** | 학습분석·리포트·추천·대시보드 **제품 기능 태스크 0건**. 인접: `S3-04`(측정 하네스·done)·`S4-15`(문항 측 난이도 루프·S3-01 잠금)·`ARCH-17`/`ARCH-18`(빌드타임 리포트 CLI 선례) |

---

## §1. 기능 32~36 ↔ WhyMath crosswalk 판정

### 기능 32. 학습 이력 관리 — **부분적: 이벤트 스키마는 문서보다 풍부 / 세션 계층 writer 0 = 최대 실행 갭**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 학습 세션 기록(시작·종료·소요시간·기기) | ORM `learning_session` 완비(`db/models/activity.py:67` — started_at·ended_at·duration_seconds·session_type·device_used·network_type·problems_attempted/completed/correct). **생성 코드 0**. 조회·종료·삭제 API만 존재(`me.py:300,1793,1849`) — *부모 없는 자식*(`ProblemAttempt.session_id`) | ⚠️ 갭 → **D1** |
| 문제 풀이 이력(정오답·소요시간·답안) | `api/me.py:596` 실적재(user·problem·is_correct·student_answer·duration_seconds·confidence·ended_at) + 숙달 전파 2축(개념·스킬) | ✅ |
| 풀이 과정 이벤트(단계·조작·힌트) | `attempt_event` TimescaleDB hypertable + `EVENT_DATA_CONTRACT` 페이로드 계약(문서에 없는 *엄격* 축). 단 11종 중 3종만 생산(`enums.py:843` 자인) | ⚠️ 부분 → **D2**(2종 한정) |
| 학습 모드·도움 사용 여부 기록 | `attempt_mode`·`used_hint`·`used_socratic`·`used_solution_view` 컬럼 실재·**전부 미기록**. 힌트 사실 자체는 `AttemptEvent.힌트제공`에 *따로* 쌓여 있어 **두 축이 서로 침묵 불일치** | ⚠️ 갭 → **D2** |
| 대화 이력 | `Dialogue`·`DialogueTurn` 실적재(`coach.py:1400`)·미성년 turn 암호화 좌석 | ✅ (문서보다 엄격) |
| 세션 품질(집중도·몰입도) | `focus_score`·`engagement_score` 컬럼 실재·산출 코드 0. L4가 이미 "생산자 없으므로 필드를 만들지 않는다"로 **명시 거부**(`runtime_selector.py:101`) | 🚫 → **§2-③** |
| 행동 로그 전용 분석 스토어 | 문서는 별도 로그 스토어를 상정. 우리는 `attempt_event`·`evidence_event`가 이미 hypertable | 🚫 → **§2-①** |
| 이력 보관·삭제·이동 | export/erasure/retention 3종 배선 완료(`privacy/*`) — 문서에 없는 축 | ✅ (초과) |

### 기능 33. 약점 분석 — **개념·오개념 축은 초과 충족 / 성취기준·문제유형 축은 0**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 개념별 취약점 도출 | `l2/concept_diagnosis.py:71` — BKT 숙달 ↔ IRT θ 프록시 **교차 판정**(`diagnosis_agreement`·불일치 시 추측/망각 의심). 문서의 단일 정답률 축보다 엄격 | ✅ (초과) |
| 오답 유형·원인 분석 | 오개념 카탈로그 + 매치 + 가설 큐레이션 + **증거 그래프**(+1 지지/−1 반박·`net_support`·거짓 낙인 차단 게이트) 실가동 — 라이브 coach가 생산·소비 양쪽 결선(`coach.py:1469,1477,1680,1687`) | ✅ (대폭 초과) |
| 성취기준(교육과정) 단위 약점 | `l2/` 참조 **0건**. 문항 측에는 살아 있는 축이 있다(`gating.py:121 _fetch_achievement_codes` — 원자 축). "모든 콘텐츠는 성취기준 코드 1개 이상 태그"라는 ALWAYS 원칙과 *진단 축*이 어긋나 있음 | ⚠️ 갭 → **D3** |
| 문제 유형별 약점 | `problem_type_node` 모델 실재·l2 참조 0 | ⚠️ → **D3**(같은 롤업 골격·2차) |
| 계산 실수 vs 개념 오류 구분 | 검산 신호(`검산결과` 이벤트·binary)는 있으나 *단계 귀속*이 없다 — `stuck_at_step` 미기록이라 어느 단계에서 틀렸는지 모름. 추측 분류는 날조 | ⏸ D2 선행 후 재판정 → **§4-⑤** |
| 취약 개념 우선순위화 | `l2/weak_concept_recommendation`·`prerequisite_recommendation` 실가동 | ✅ |
| 학습 속도·패턴 프로파일 | 응답시간 z·연속 오답 등 행동 신호는 실재. 장기 패턴 집계 좌석(`user_behavior_metrics`)은 writer 0 | ⚠️ → **D5** |

### 기능 34. 실력 예측 — **추정(현재 상태)은 실가동 / 예측(미래·시험점수)은 전무이며 대부분 의도적**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 숙달 확률 추정 | `l2/bkt.py` 4-파라미터 + 비퇴화 강제(`p_slip+p_guess<1` 위반 시 `ValueError`) | ✅ |
| 능력치 추정 | `l2/irt.py`·`ability_estimation`·`item_calibration`·`calibrate_items` — θ + **SE 동반** | ✅ |
| 시간 경과 반영(망각) | `apply_forgetting` 구현·호출까지 실배선. 단 λ=0 기본 + 주입 경로 0 → **실효과 0**(작동하는 코드가 아무 일도 안 함) | ⚠️ 갭 → **D4** |
| 예상 등급·점수·백분위 | 컬럼 4종 실재·산출 코드 0 | 🚫 → **§2-②** / 경계 문서화 **D6** |
| 합격 확률 | `admission_probability` 컬럼 실재·산출 코드 0 | 🚫 → **§2-②** |
| 딥러닝 지식추적(DKT) | `02_learner_model.md:39` 데이터 임계(N>10,000) 미달 — 파일럿 5~10명 | 🚫 → **§2-⑤** |
| 이탈 위험 예측 | `user_behavior_metrics.churn_risk` 좌석 설계됨·writer 0. 입력(세션·활동)이 D1 전엔 존재하지 않음 | ⏸ D1·D5 후 → **§5** |

### 기능 35. 학습 리포트 — **원자료 API는 완비(me.py 29 라우트) / 집계·기간비교·서술 계층 0 · 역할 개념 부재**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 학생 본인 학습 요약 | 개별 조회 API는 전부 있으나(시도·숙달·진단·경로) **주·월 단위 집계·기간 비교·서술이 0** | ⚠️ 갭 → **D5** |
| 일별/주별 집계 저장 | `daily_learning_metrics` 등 3 hypertable 실재·**writer 0**(GDPR 배선만 완료) | ⚠️ 갭 → **D5** |
| 성장 추이 시각화 데이터 | `concept_mastery_history`·`ability_snapshot` 시계열 실적재 — 리포트가 읽을 재료는 있음 | ✅ (재료) |
| 강점·약점 요약 서술 | 진단 데이터는 있으나 서술 생성 0. WhyMath는 발화 톤 게이트 보유(`l4/tone_filter.py:28 filter_tone` — 부정 강화 표현 차단) | ⚠️ → **D5**(톤 경유 필수) |
| 교사용 학급 대시보드 | `role` 개념 자체가 없음 · `07_community.md` Phase 4 B2B 정본 | 🚫 → **§2-④**·**§5** |
| 학부모 리포트 | 동상. 부모 *동의* 필드는 있으나 부모 *계정*은 없음 | 🚫 → **§2-④**·**§5** |
| 정기 발송 스케줄러 | Celery beat 없음(`config.py:632` 외부 cron 위임 정책) | ⚠️ → **D5**(CLI + 외부 cron·`ARCH-18` 선례) |

### 기능 36. 추천 학습 — **다음 문항·약개념·선수 경로는 실가동 / 복습 타이밍·추천 피드백 루프 부재**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 취약 개념 기반 추천 | `l2/weak_concept_recommendation` → `api/me.py` 실가동 | ✅ |
| 선수 개념 갭 추천 | `l2/prerequisite_recommendation` → `me.py`·`coach.py` 실가동 | ✅ |
| 학습 경로 생성 | `l2/learning_path.build_learning_path`(위상정렬·DAG) → `me.py:1442` | ✅ |
| 적응형 다음 문항 | `api/gating.py` 후보 게이팅 + 난이도 정합 + 수능 가중(L6) | ✅ |
| 복습 시점 추천(간격 반복) | **부재**. 재료(`apply_forgetting`·`concept_mastery_history`)는 있으나 "언제 다시"를 계산·노출하는 좌석 0 | ⚠️ 갭 → **D4** |
| 추천 수용·성과 피드백 루프 | 교수학 *처치* 축만 실재(`pedagogy_evidence`→`effectiveness`). 개념·문항 추천은 수용 여부조차 기록 안 함 | ⚠️ → **D5**(리포트 축이 첫 소비처) / 본격 루프는 §5 |
| 유사 학습자 기반 추천(협업필터링) | 데이터 임계 미달 | 🚫 → **§2-⑤** |
| 영상·읽을거리·외부 콘텐츠 추천 | 콘텐츠 자산 자체가 저작권 레일 밖(EBS·인강·교과서 본문 금지) | 🚫 → **§2-⑥** |

---

## §2. 의도적 미채택 (6건)

외부 틀에 있으나 WhyMath가 **의식적으로 채택하지 않는** 항목이다. "아직 안 함"이 아니라 "그렇게 하지 않기로 함"이며, 근거를 남겨 미래 세션이 갭으로 오인해 되살리지 않게 한다.

| # | 틀 제안 | 불채택 근거 + 대체 좌석 |
|---|---|---|
| ① | **행동 로그 전용 분석 스토어(ClickHouse 등) 도입** | pgvector 선례(2026-06-10 슬98)와 동일 판단 — *6번째 store 회피*. 이미 `attempt_event`·`evidence_event`·`concept_mastery_history`가 TimescaleDB hypertable로 배선돼 있고, 파일럿 규모(5~10명)에서 별도 OLAP은 운영 표면만 늘린다. **대체 좌석** = 기존 hypertable + D5의 일별 집계. 재검토 조건은 §5. |
| ② | **"예상 등급 2등급"·"합격 확률 68%" 수치 산출** | 문항 모수 캘리브레이션 표본도, 실채점 대조 표본도 없는 상태에서 산출하는 등급·확률은 **날조**다. "확실하지 않을 때 자신 있게 말함" 금기 + 의사결정 우선순위 1(학생 웰빙: 잘못된 합격 확률은 진로 결정을 왜곡)에 직접 저촉. **대체 좌석** = θ ± SE 구간 노출 + 표본 미달 시 `NO_DATA` 정직 표기(`wh1_evaluation` NO_DATA 선례). 발화 조건 §5. |
| ③ | **집중도·몰입도 센서 수집**(앱 전환·체류·시선 추적) | 미성년 개인정보 *최소 수집* 원칙 + "미성년자 개인정보를 분석·마케팅 외부 공유 금지". 앱 전환 감시는 학습 외 행동까지 프로파일링한다. L4가 이미 같은 결론을 코드로 고정("생산자를 먼저 만들고 그때 필드를 연다" — `runtime_selector.py:101`). **대체 좌석** = 이미 보유한 학습 내부 신호(응답시간·연속 오답·재시도·힌트 소비)만. `focus_score`·`engagement_score`·`avg_focus_score` 컬럼은 **영구 미충전**으로 동결. |
| ④ | **교사·학부모 대시보드 본체** | `07_community.md` L7 Phase 3~4 정본이고, `user_profile`에 role/teacher/parent **개념 자체가 없다**. 지금 만들면 소비처 없는 저작 부채 + 미성년 데이터의 제3자 노출 경로를 동의 체계 없이 여는 것. **대체 좌석** = D5(학생 *본인* 리포트)로 집계 계층을 먼저 세우고, 역할 계층이 설 때 뷰만 얹는다. §5. |
| ⑤ | **협업필터링·DKT 등 대규모 데이터 의존 모델** | `02_learner_model.md:39,53`이 지정한 데이터 임계(DKT N>10,000·유사군 형성) 미달. 파일럿 코호트는 5~10명이라 유사 학습자 개념이 성립하지 않는다. 소표본에 얹은 협업 추천은 노이즈를 개인화로 포장한다. **대체 좌석** = BKT/IRT 개인 내 추정(표본 1명에서도 정직). |
| ⑥ | **영상·읽을거리·외부 콘텐츠 추천** | 추천할 자산이 전부 금지 레일 안이다 — EBS 영상·교재 본문(상업 영리 금지), 학원·인강 자료(데이터화 금지), 검정 교과서 본문(복제 금지). 링크 추천이라도 큐레이션 자체가 2차 저작 판단을 요구한다. **대체 좌석** = 자체 개념 콘텐츠·시각화 장면(`l4/content_supply.py`)·자체 동등문제. |

---

## §3. 진짜 갭 설계 — D1~D6

배열 순서는 문서 기능 번호가 아니라 **실행 우선순위**다. 근거 3가지:
**⑴ 수집이 분석에 선행한다** — 비어 있는 입력 위에 리포트를 얹으면 "0건 통과"로 위장된다.
**⑵ 파일럿(S3-01) 전에 닫아야 하는 것이 먼저다** — 놓친 학생 행동은 소급 수집이 불가능하다.
**⑶ 이미 있는 엔진을 되살리는 것이 새 엔진보다 먼저다** — D4의 망각처럼 "구현돼 있으나 λ=0이라 아무 일도 안 하는" 코드가 우선.

### D1. 학습 세션 write-path 착륙 — 리텐션 KPI 소생 (백로그 `S3-16`)

**목적**: 세션 계층의 *생산자*를 만들어, 이미 완성된 두 측정 하네스가 실제 값을 내게 한다. 이 갭은 기능 누락이 아니라 **측정 위장**이다 — 하네스는 "0건"이 아니라 `NO_DATA`를 반환하도록 정직하게 짜여 있지만(`wh1_evaluation.py:1078`), 그 `NO_DATA`가 *영원히* 해소되지 않는다는 사실이 어디에도 드러나 있지 않았다.

- **좌석**: `POST /v1/me/sessions`(생성) — 기존 `PATCH /sessions/{id}/end`·`DELETE`와 짝을 이뤄 생명주기 3종을 완성한다. 별도 테이블·컬럼 신설 **0**.
- **채우는 필드**: `user_id`·`started_at`(서버 시각)·`session_type`·`target_concept_id`(선택)·`device_used`·`network_type`(클라 보고). 종료 시 서버가 `duration_seconds` + `problems_attempted`/`problems_completed`/`problems_correct`를 **`ProblemAttempt` 집계로 산출**(클라 보고 신뢰 금지 — 클라는 시각만 보고).
- **채우지 않는 필드(동결)**: `focus_score`·`engagement_score` — §2-③. 코드 주석과 테스트로 "의도적 미충전"을 고정해, 미래 세션이 NULL을 버그로 오인해 센서 수집을 도입하지 않게 한다.
- **`session_id` 결선**: 현재 `ProblemAttempt.session_id`는 클라가 보낸 값을 검증 없이 받는다(`me.py:597`). 실재하는 본인 세션인지 확인하는 게이트를 붙인다(타인 세션 id 주입 차단 — 미성년 데이터 경계).
- **writer·reader 동반(협상 불가)**: writer만 착륙시키지 않는다. reader 측 증거 = `pilot_kpi_baseline` KPI2 리텐션과 `wh1_evaluation` 지표 ③이 `NO_DATA`에서 `MEASURED`로 바뀌는 것을 테스트로 고정.
- **검증**: ① 세션 생성→시도 2건→종료 E2E에서 카운트 3종이 실제 시도와 일치 ② 종료 없이 남은 세션이 완주율 분모에는 들어가고 분자에는 안 들어감 ③ 타인 `session_id` 주입 시 거부 ④ `focus_score` NULL 동결 테스트.
- **anti-explosion**: 세션 유형(`SessionType`)은 기존 enum 그대로 — 신규 값 추가 금지. 세션 자동 분할(유휴 타임아웃) 같은 휴리스틱은 이번 범위 밖(파일럿 실데이터로 필요성이 보일 때).

### D2. 시도 계측 봉합 — 힌트·모드·시작시각 서버 파생 (백로그 `S3-17`)

**목적**: 한 학생의 한 시도에 대해 시스템이 **두 개의 서로 다른 이야기**를 갖고 있는 상태를 끝낸다. `AttemptEvent.힌트제공`은 "힌트를 4단계로 줬다"고 기록하는데, 같은 시도의 `ProblemAttempt.used_hint`는 NULL이다. 어느 쪽을 읽느냐에 따라 결론이 달라지는 것은 분석 이전에 데이터 무결성 문제다.

- **좌석**: `api/me.py`의 시도 적재부 + coach 이벤트 적재부. **신규 테이블·컬럼 0** — 이미 있는 컬럼을 채운다.
- **채우는 필드와 그 출처(전부 서버 파생 — 클라 자기보고 금지)**:
  - `used_hint` ← 같은 `attempt_id`의 `EventType.힌트제공` 존재 여부
  - `used_socratic` ← 해당 시도에 결선된 대화 턴 존재 여부
  - `used_solution_view` ← 풀이 열람 엔드포인트 호출 기록(없으면 이번엔 미충전 — 없는 신호를 지어내지 않는다)
  - `attempt_mode` ← 진입 경로(자유풀이/코치/진단)
  - `started_at` ← 문항 서빙 시각(서버 기록). 현재는 `ended_at`만 있어 **체류 시간의 서버측 근거가 없다**(`duration_seconds`는 클라 보고값).
- **유보**: `time_vs_expected`는 문항별 p50이 필요하므로 **D5의 `problem_solve_time_distribution` 착륙 이후**에 연다(짝). `stuck_at_step`은 단계 채점이 서는 시점(§4-⑤).
- **EventType 휴면 8종 — 일괄 부활 금지**: 소비처가 서는 **2종만** 생산한다 — `힌트요청`(demand·`힌트제공` supply와 짝이 맞아 도움 *요청↔공급* 격차를 볼 수 있음)·`막힘`(체류 임계 초과). 나머지 6종(`문제읽기`·`조건분석`·`그래프그리기`·`계산`·`지움`·`답입력`)은 휴면 유지 — 소비처 없는 이벤트는 스토리지·계약 표면만 늘린다. 생산하는 2종은 `EVENT_DATA_CONTRACT`에 페이로드를 등재해 계약 면제에서 뺀다.
- **writer·reader 동반**: reader 측 증거 = 힌트 사용 비율이 두 축(이벤트 집계 vs 시도 요약)에서 **일치**함을 검증하는 정합 테스트. 두 축이 어긋나면 실패하게 만든다.
- **검증**: ① 힌트 준 시도의 `used_hint`=True·안 준 시도 False(NULL 아님) ② 두 축 집계 일치 ③ `started_at ≤ ended_at` ④ 신규 2종 이벤트의 페이로드 계약 통과.
- **anti-explosion**: 이벤트 종류를 늘리는 게 아니라 *이미 정의된* 종류 중 소비처가 생긴 것만 깨운다.

### D3. 성취기준 축 약점 진단 롤업 (백로그 `S4-18`)

**목적**: "모든 콘텐츠는 성취기준 코드 1개 이상 태그"라는 ALWAYS 원칙이 문항 측에서는 지켜지는데(`gating.py`) 진단 측에는 없다. 학생·교사가 실제로 말하는 단위는 개념 원자가 아니라 성취기준("[10공수1-02-02]가 약하다")이므로, 진단 결과를 그 축으로 굴린다.

- **조인 축(중요·실측)**: `ProblemConcept → Concept → AtomNode.standard_codes`(원자 축). **`concept_standard_link → achievement_standard`를 쓰지 않는다** — S2-03 원자 재연결 이후 0행이며 `gating.py:127-131`이 이를 자인한다. 즉 `_fetch_achievement_codes`(`gating.py:121`)의 조인 패턴을 **재사용**한다(재구현 0).
- **좌석**: `GET /v1/me/diagnosis/standards` — 기존 `compute_concept_diagnoses` 결과를 성취기준 코드로 그룹핑·가중 평균.
- **새 추정기 없음**: BKT/IRT를 다시 짜지 않는다. 집계 축만 추가하는 순수 롤업이라 진단 권위가 하나로 유지된다(단일 진실 원천).
- **정직 규칙**: 성취기준 코드가 붙지 않은 개념은 롤업에서 **누락이 아니라 명시적 미분류**로 표기한다(조용히 사라지면 커버리지 착시). 표본 미달 성취기준은 값 대신 `NO_DATA`.
- **2차(같은 골격)**: `problem_type_node` 축 롤업. 같은 그룹핑 골격을 축만 바꿔 재사용하되, 문제유형 태깅 커버리지가 낮으면 그 사실을 응답에 병기.
- **검증**: ① 개념 축 진단과 성취기준 축 진단의 총량 정합(누락 0) ② 코드 없는 개념의 미분류 표기 ③ 단일 IN 일괄 쿼리(N+1 0 — `gating.py` 선례).
- **anti-explosion**: 새 관계 타입·새 노드 0. 조회 축 하나만 추가.

### D4. 망각 파라미터 실효화 + 복습 타이밍 추천 (백로그 `S4-19`)

**목적**: `apply_forgetting`은 구현·배선까지 끝났는데 λ=0이라 **아무 일도 하지 않는다**. 이는 "있는 줄 알았는데 없는" 부류로, 코드 리뷰에서는 통과하고 운영에서만 드러난다. 동시에 문서 틀 36의 복습 타이밍은 정확히 이 감쇠의 소비처다.

- **좌석 ①(실효화)**: `p_forget`을 설정으로 주입 가능하게 한다(`Settings`에 BKT 파라미터 좌석). **기본값은 0.0 유지** — 캘리브레이션 전에 임의 λ를 켜는 것은 §2-② 계열의 날조다. 켜는 것은 파일럿 데이터로 λ를 추정한 뒤.
- **좌석 ②(소비처)**: `GET /v1/me/review-due` — 각 개념의 현재 숙달을 경과일만큼 감쇠시켜 임계 아래로 떨어질(또는 떨어진) 개념과 그 시점을 반환. λ=0이면 **빈 목록 + "감쇠 미교정" 사유**를 반환한다(가짜 추천 금지·`NO_DATA` 계열 정직 표기).
- **캘리브레이션 경로**: `concept_mastery_history`의 (공백 기간, 재관측 정오답) 쌍에서 λ 추정 — `calibrate_items` CLI 선례를 답습한 결정론 배치. 실학생 응답이 필요하므로 **`S3-01` 잠금**(입력 없는 파이프라인 금지 — `S4-15` 선례).
- **경계**: 복습 알림 *발송*(푸시)은 이 범위 밖 — 조회 API까지. 알림은 중독성 설계 검토가 별도로 필요하다(게임화 금기 인접).
- **검증**: ① λ=0에서 `review-due`가 빈 목록 + 사유 반환 ② λ>0에서 경과일 증가에 따라 단조 감소 ③ 사전값(P(L0)) 이하로는 내려가지 않음(`apply_forgetting` 계약) ④ λ 추정 배치의 결정론.
- **anti-explosion**: 개념별 λ가 아니라 **전역 λ 하나**로 시작. 개념별 분화는 표본이 그것을 지지할 때(과적합 방지).

### D5. 일별 학습 집계 CLI + 학생 본인 주간 요약 (백로그 `S4-20`)

**목적**: 이미 GDPR 배선까지 마친 3개 hypertable을 채우고, 그 위에 학생이 실제로 읽을 주간 요약을 얹는다. **집계(writer)와 리포트(reader)를 한 태스크로 묶는 이유**: 둘 중 하나만 착륙하면 각각 "채워지지 않는 테이블" 또는 "원자료를 매번 재집계하는 API"라는 새 부채가 된다.

- **좌석 ①(writer)**: 일별 집계 CLI — `ARCH-18`(문제은행 커버리지 리포트) 선례를 답습한 결정론 배치, 외부 cron이 호출(`config.py:632` 정책 준수·Celery beat 신설 안 함).
  - `daily_learning_metrics` ← 세션·시도 집계(minutes_active·problems_attempted/correct·socratic_turns·concepts_practiced). **`avg_focus_score`는 채우지 않는다**(§2-③ 동결).
  - `user_behavior_metrics` ← 행동 지표(응답시간 중앙값·힌트 의존도·연속 학습일). **`churn_risk`는 이번에 채우지 않는다** — 이탈 예측은 표본이 설 때(§5).
  - `problem_solve_time_distribution` ← 문항×페르소나 p10/p50/p90 + `sample_size`. 이것이 D2의 `time_vs_expected`를 여는 짝이다. 표본 미달 문항은 **행을 만들지 않는다**(0 표본 분위수 = 날조).
- **좌석 ②(reader)**: `GET /v1/me/report/weekly` — 학습 시간·시도/정답·연습 개념·전주 대비 델타·강점 3·약점 3·다음 추천. 원자료 재집계가 아니라 ①의 일별 행을 읽는다.
- **표현 규칙(교수학)**: 서술 문구는 **`l4/tone_filter.filter_tone` 경유 필수** — 부정적 피드백을 정서적으로 강화하는 표현 금기. "정답률이 낮다"가 아니라 무엇을 다음에 하면 되는지로 끝난다. 리포트에 **순위·비교·연속 기록 압박을 넣지 않는다**(게임화 금기).
- **정직 규칙**: 데이터가 없는 주는 0이 아니라 `NO_DATA`. "이번 주 학습 0분"과 "측정 실패"는 다르다.
- **의존**: D1(세션)·D2(계측) 선행 — 그 전엔 집계할 입력이 없다.
- **검증**: ① 집계 CLI 결정론(같은 입력 → 같은 행) ② 재실행 멱등(복합 PK upsert) ③ 표본 0 문항의 분위수 행 부재 ④ 주간 리포트가 일별 행만 읽음(원자료 재집계 아님) ⑤ 톤 필터 통과 ⑥ `avg_focus_score`·`churn_risk` 미충전 동결.
- **anti-explosion**: 리포트 지표를 늘리지 않는다 — 위 항목이 전부. 새 지표는 "그것을 보고 학생이 무엇을 다르게 할 것인가"에 답할 수 있을 때만.

### D6. 실력 예측의 정직 경계 (**설계만 · 신규 태스크 없음**)

**목적**: `Assessment`의 `estimated_grade`·`estimated_score`·`estimated_percentile`·`admission_probability` 4컬럼을 **지금 채우지 않는 근거**를 문서로 동결한다. 컬럼이 비어 있는 것은 미완성이 아니라 판단이다.

- **왜 안 채우는가**: ① 문항 모수(난이도·변별도)가 실응답으로 캘리브레이션되지 않았다 — `S4-15`가 그 축이며 `S3-01` 잠금 ② 우리 θ를 실제 시험 점수로 사상하려면 **실채점 대조 표본**이 필요한데 0건 ③ 등급·합격 확률은 진로 결정을 바꾸는 수치라 오차가 그대로 피해가 된다(의사결정 우선순위 1).
- **그때까지 무엇을 노출하는가**: θ ± SE 구간과 개념별 숙달. "지금 어디에 있는가"는 말하되 "시험에서 몇 점일 것인가"는 말하지 않는다.
- **왜 태스크를 만들지 않는가**: 구현 트리거가 이미 다른 태스크(`S4-15` 캘리브레이션·`S3-01` 파일럿)에 있다. 같은 일을 두 번 추적하지 않는다(`knowledge` D2·`solution` D5 선례). 조건이 충족되면 그때 등재한다 — 조건은 §5.

---

## §4. 잔여 연동 트리거 — 태스크화하지 않는 축

| # | 항목 | 처리 |
|---|---|---|
| ① | `api/coach.py:1014` docstring이 "라이브 경로 증거 적재는 아직 하네스 몫"이라고 하는데, 바로 아래 `_log_match_evidence`·`_log_refutation_evidence`가 실제로 적재한다(`:1469,1477,1680,1687`) — **문구가 낡음** | 해당 파일을 다음에 만지는 슬라이스가 정정(문서 갭·기능 갭 아님) |
| ② | `l2/evidence_event_store.py` — src 호출자 0(테스트 2곳만) | D5의 집계 CLI가 첫 소비처가 되는지 먼저 판정. 안 되면 그때 제거 태스크(지금 지우면 PED-01 E2E 자산 손실) |
| ③ | `MasteryState.preferred_solution_style`(문서 스케치·코드 부재) | `S4-12`(풀이 클러스터링) 승계 |
| ④ | 정서 신호 5분류기 | §5 — D1·D2 신호가 실제로 쌓인 뒤 |
| ⑤ | 계산 실수 vs 개념 오류 자동 분류 | D2의 `stuck_at_step`(단계 채점 선행)이 조건. 그 전엔 추측 분류이므로 금지 |
| ⑥ | 스케줄러 매니페스트(cron 등록·운영) | ops 축(`OPS-*`)이며 본 모듈 밖. D5는 CLI까지만 책임 |
| ⑦ | 문항 측 난이도 실측 루프 | `S4-15` 승계(중복 등재 금지) |

---

## §5. 유보 항목의 발화 조건

| # | 항목 | 발화 조건 |
|---|---|---|
| 1 | 교사용 학급 대시보드 | `user_profile` role 계층 착륙 + B2B 계약 1건 이상(`07_community.md` Phase 4) |
| 2 | 학부모 주간 리포트 | role 계층 + 학생 본인 opt-in 동의 흐름(법정대리인 동의와 **별개** — 동의 절차는 기계 대체 금지 항목) |
| 3 | 예상 등급·점수·백분위 | `S4-15` 문항 모수 캘리브레이션 완료 **AND** 실채점 대조 표본 확보(그 전엔 D6대로 θ±SE만) |
| 4 | 합격 확률 | 3번 + 대학·전형 데이터의 라이선스 판정(`docs/data/licensing_safety.md` 등재) |
| 5 | 협업필터링·DKT | `02_learner_model.md` 데이터 임계(N>10,000·유사군 형성) 충족 |
| 6 | 이탈 위험(`churn_risk`) | D1·D5 착륙 후 실사용 표본이 쌓이고, **개입 설계가 먼저** 정해진 뒤(예측만 하고 할 일이 없으면 낙인) |
| 7 | 별도 OLAP 스토어(§2-①) | hypertable 집계 쿼리가 운영 SLO를 못 맞추는 것이 **실측**될 때 |
| 8 | 집중도·몰입도 수집(§2-③) | **없음 — 영구 유보**. 수집 자체가 금기이므로 조건부 해제가 아니다 |

---

## 부록 — 실측 근거·관련 코드

**재현 명령**(2026-07-29 기준·전건 실행 확인):

```bash
# writer 0 판정 — 정의부(db/models·schema) 밖 인스턴스화가 0건임을 확인
grep -rn "LearningSession(\|DailyLearningMetrics(\|UserBehaviorMetrics(\|ProblemSolveTimeDistribution(\|Assessment(" \
  --include=*.py src/ | grep -v "db/models\|schema/"

# 생산되는 EventType 전수 (3종)
grep -rn "EventType\." --include=*.py src/backend/whymath_backend/api/

# 망각 기본값·주입 경로
grep -n "_DEFAULT_P_FORGET" src/backend/whymath_backend/l2/bkt.py
grep -n "bkt\|forget" src/backend/whymath_backend/config.py

# l2에 성취기준·문제유형 축이 없음
grep -rn "achievement_standard\|problem_type_node" --include=*.py src/backend/whymath_backend/l2/
```

**핵심 행 번호**:

- 세션 계층 — `db/models/activity.py:67`(ORM) · `api/me.py:300`(GET) · `:1793`(PATCH end) · `:1849`(DELETE) · **생성 없음**
- 시도·이벤트 — `api/me.py:596`(ProblemAttempt) · `api/interactions.py:75` · `api/coach.py:922,977`(AttemptEvent) · `api/coach.py:1400`(Dialogue)
- 굶주린 하네스 — `harness/pilot_kpi_baseline.py:812`(KPI2 리텐션) · `harness/wh1_evaluation.py:1052,1078`(지표 ③·NO_DATA)
- L4 자인 — `l4/pedagogy/runtime_selector.py:101`("생산자를 먼저 만들고 그때 필드를 연다")
- 휴면 이벤트 자인 — `schema/enums.py:843`
- 망각 — `l2/bkt.py:40`(λ 기본 0.0) · `:109`(apply_forgetting) · `l2/mastery_tracking.py:69`(호출)
- 예측 컬럼 — `db/models/assessment.py:98,99,100,105`
- 진단 — `l2/concept_diagnosis.py:33`(agreement) · `:71`(compute_concept_diagnoses)
- 성취기준 조인(정본 축) — `api/gating.py:121-165`(`_fetch_achievement_codes`) · `:127-131`(구 축 0행 자인)
- 증거 그래프(라이브 결선) — `l4/misconception/evidence_store.py:75` ← `api/coach.py:1469,1477,1680,1687`
- 교수학 피드백 루프(기존) — `api/study.py:198,244` → `l2/pedagogy_evidence.py:98,127` → `l4/pedagogy/adaptive/effectiveness.py:139`
- 시계열 좌석 — `db/models/timeseries.py:64`(일별) · `:114`(풀이시간 분포) · `:161`(행동 지표)
- GDPR 배선(writer 0인데 이미 등록) — `privacy/export.py:103-104` · `privacy/erasure.py:92-93` · `privacy/retention.py:55-56`
- 톤 게이트 — `l4/tone_filter.py:28`
- 스케줄 정책 — `config.py:632`(외부 cron 위임)

**기존 추적 승계(중복 등재 금지)**: `S3-01`(파일럿 코호트 — D4 잠금·D1/D2 선행 권고) · `S3-04`(측정 하네스·done — D1이 그 입력을 소생) · `S4-15`(문항 측 난이도 루프 — D6 트리거) · `S4-12`(풀이 클러스터링 — §4-③) · `S1-11`(coach flip) · `ARCH-17`/`ARCH-18`(빌드타임 리포트 CLI 선례 — D5 골격).
