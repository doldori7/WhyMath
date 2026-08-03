# 데이터 플랫폼 모듈 — 외부 틀 대조 갭 점검·설계 (2026-08-03)

> **범위**: 외부 참고 문서 『1단계 데이터 플랫폼』(모듈 **84 이벤트 분석** · **85 품질 모니터링**
> — **WhyMath 전용이 아닌 일반적 데이터 플랫폼 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진
> 부분을 점검하고, 진짜 갭을 WhyMath 불변식(미성년자 PII 금기·"정답을 빠르게" KPI 금지·이중
> 회계·소비처 없는 설계 금지·검증 권위 서열·1인 capacity 가드) 안에서 설계한 기록.
> **형식**: `operations_module_gap_review.md`·`ai_recommendation_module_gap_review.md`(갭 분석→
> 판정→설계) 답습 — 같은 외부 틀 대조 시리즈(모듈 6~10 → 18~22 → 23~27 → 42~50 → 80~83)의
> 자매편이자 **11번째**.
>
> **결론**: 85(품질 모니터링)의 *검사기 자산*은 틀보다 **엄격하다** — `qa_pipeline` 7축·Wilson
> 경계 게이트·결함주입 강등전·야간 전수 재검증이 이미 돌고, 시스템 축은 `OPS-01`/`OPS-04`로
> 상환 완료. 84(이벤트 분석)는 **좌석은 완비인데 입력이 끊겼다** — 스키마·테이블·페이로드 계약이
> 전부 실재하는데 학생 앱이 `POST /v1/me/attempts`를 호출하지 않아 `ProblemAttempt`가 0행이다.
> 다만 그 개별 축들은 이미 `REC-01`·`NLP-01`·`S3-16`이 추적 중이므로 **신규 갭으로 세지 않는다**.
>
> 진짜 갭 3건을 설계했다 — **D3 문항 중복 감사**(코퍼스 전수 집계로 **이미 발생한 결함** 발견:
> 은행 간 slug 충돌 392건·발문 동일 279그룹, 그중 **1쌍은 데모·파일럿 문제 풀에 살아 있다**),
> **D1 공급↔소비 도달 대장**(6회 반복된 "만들고 입력을 잇지 않음"의 첫 *기계* 탐지기),
> **D2 QA 판정 보존·비집행 가시화**(가장 비싼 게이트가 `continue-on-error`로 판정도 안 하고
> artifact 업로드도 없어 기록도 안 남는 상태). 신규 태스크 3건 등재.
>
> **이 문서의 초고는 D3을 "✅ 충족"으로 오판했다** — 생성 시점 가드의 *존재*를 위험의 *부재*로
> 읽었기 때문이다. 코퍼스 전수 집계가 그 판정을 뒤집었다(§1-85① 정정 기록).

관련 정본: `docs/standards/superhuman_verification_standard.md`(검증 권위 서열·6축) ·
`docs/standards/incident_response_slo.md`(SLO·정직한 미측정 표기) ·
`docs/standards/measurement_line_enablement.md`(계측선 가동 순서) ·
`docs/architecture/operations_module_gap_review.md`(모듈 42~50, 본 문서의 직전 자매편) ·
`docs/architecture/ai_recommendation_module_gap_review.md`(모듈 80~83, attempt 0행 최초 규명) ·
`MEMORY.md` 결정 로그(2026-08-03).

---

## §0. 선결 — 이 틀의 어휘를 그대로 쓰지 않는 이유

첨부 문서는 **일반적 데이터 플랫폼 틀**이라 "퍼널·완료율·목표 달성률·이탈률"처럼 **범용 SaaS
그로스 어휘**를 그대로 싣고 있다. 이 어휘는 WhyMath에서 **중립적이지 않다** — CLAUDE.md 교수학
금기가 *"「정답을 빠르게」를 KPI로 사용 금지"*·*"학습 시간·정답률만으로 우열을 매기는 게임화
금지"*를 최상위 규범으로 못 박고 있기 때문이다. 지표는 조직이 무엇을 최적화하는지를 결정하므로,
어휘를 무비판적으로 수입하면 **금기가 KPI 대시보드를 통해 뒷문으로 들어온다**.

따라서 이 문서는 틀의 항목을 ①**그대로 채택** ②**재정의 후 채택** ③**의도적 미채택**으로 나눠
판정하며, ②·③에는 반드시 근거를 단다. 새 계층(L8)도 만들지 않는다 — 데이터 플랫폼은 CLAUDE.md가
규정한 **횡단 관심사**(로깅·모니터링·에러는 별도 인프라)이고, 이벤트 계약은 L1(데이터 기반)·
L2(학습자 모델)에 이미 좌석이 있다.

---

## §1. 모듈 84·85 ↔ WhyMath crosswalk 판정

### 모듈 84. 이벤트 분석 — **좌석 완비, 입력 단절** (개별 축은 기존 태스크가 추적 중)

#### ① 학습 이벤트 수집

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 이벤트 페이로드 계약 | `schema/event_data_contract.py` — `EVENT_DATA_CONTRACT` + `build_event_data()` seam, `extra="forbid"`로 stray key 구조적 차단. 생산자(`api/coach.py`·`api/interactions.py`)가 반드시 경유 | ✅ (틀에 없는 축을 우리가 더 갖춤) |
| 저장 좌석 | PostgreSQL + TimescaleDB — `learning_session`·`problem_attempt`·`attempt_event`(복합 PK·hypertable)·`evidence_event`(AES-256-GCM 봉투 암호화)·`dialogue`/`dialogue_turn` | ✅ |
| 힌트 사용 | `EventType.힌트제공` — `api/coach.py` 매 응답 턴 적재(`decision.hint_level`) | ✅ |
| AI Tutor 대화 | `dialogue`/`dialogue_turn` 암호화 적재 | ✅ |
| 문제 제출 / 정답·오답 / 풀이 시간 | 좌석 완비(`ProblemAttempt.is_correct`·`duration_seconds`·`step_times`) + `POST /v1/me/attempts` 서버 구현 완료. **그러나 Flutter가 호출하지 않아 0행** | ⚠️ → **기존 추적**(`REC-01`·`NLP-02`) |
| 문제 시작·읽기 / 막힘 / 힌트 요청(demand) | `EventType` 좌석 있으나 **휴면 8종**(`_CONTRACT_EXEMPT`) — 생산자 0 | ⚠️ → **기존 추적**(`S3-16`) |
| 개념 학습 완료 / 복습 완료 | 이벤트 좌석 없음. 분산복습은 `PedagogyMode` 어휘로만 존재하고 **복습 루프 기능 자체가 미구현** | 🚫 §2-⑦ (소비처 없음) |

#### ② 사용자 행동 분석

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 클릭 스트림 · 화면 이동 경로 · UI 사용 패턴 · 기능 사용 빈도 | 0건 | 🚫 **§2-②** (미성년자 PII 금기·수동적 설계 금지) |
| 학습 세션 분석 | `LearningSession` 테이블 실재하나 **writer 미신설**, `focus_score`/`engagement_score` NULL | 🚫 §2-② 부분 — `S3-16`이 "**미신설을 결정으로 명시**"(NULL 유지 동결 테스트)로 처리 중 |
| 이탈 지점 분석 | 교수학적 등가물 = `EventType.막힘`·`ProblemAttempt.stuck_at_step` 좌석 보유(휴면) | ⚠️ → **기존 추적**(`S3-16`). 이탈=마케팅 축이 아니라 **막힘=교수학 축**으로 재정의 채택 |

#### ③ 학습 퍼널 분석

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 학습 시작률·문제 완료율·복습 완료율·**목표 달성률**·학습 중단률 | 퍼널 엔진 없음. 대신 `harness/wh1_evaluation.py`의 **대리 지표 11종**(답 미루기 단계 깊이·도움 감소·전이·verify 통과율 등) + `harness/pilot_kpi_baseline.py` | 🚫 **§2-③** (원형 그대로는 금기 충돌) / ✅ **재정의 채택**(대리 지표가 정본) |

> **왜 이 항목이 가장 위험한가**: "문제 완료율"·"목표 달성률"을 KPI로 올리는 순간, 시스템을
> 개선하는 가장 쉬운 길은 *더 쉬운 문제를 주고 더 빨리 답을 알려주는 것*이 된다 — 이는
> CLAUDE.md 교수학 금기 3개(즉답 금지·"빠르게" KPI 금지·게임화 금지)를 동시에 위반한다.
> WhyMath의 성공은 "완주"가 아니라 **"학생이 스스로 얼마나 깊이 갔는가"**(답 미루기 단계 깊이)로
> 측정한다. 퍼널 수치는 그 하위 관측치로만 존재할 수 있고, 독립 KPI로 승격하지 않는다.

#### ④ 실시간 이벤트 스트림

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| Event Queue · **Event Bus(Streaming)** · Data Lake · Analytics DB 분리 | 없음. Kafka류 0건 | 🚫 **§2-①** |
| **ClickHouse**(행동 로그) | 스택 표·인프라 문서에는 있으나 **클라이언트 코드 0건** — `privacy/erasure.py`·`privacy/export.py`에 "삭제·반출 미수행 대상" 문자열로만 등장 | 🚫 §2-① (의도된 지연) |
| Event Store | **`attempt_event`가 사실상의 Event Store다** — append-only·복합 PK `(event_id, event_at)`·FK 없는 느슨참조·hypertable | ✅ (다른 형태로 충족) |
| 실시간 Dashboard · 실시간 이상 탐지 | 없음 | 🚫 §2-④ (`operations_module_gap_review.md` §2-④ 승계) |
| 이벤트 재처리 | 없음 — 대신 **빌드타임 결정론 리포트**(같은 입력→같은 출력)가 재처리 요구를 흡수 | 🚫 §2-① |

#### ⑤ AI 분석 활용

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 오개념 탐지 | `MisconceptionCatalog` 843건 + 탐지 인코딩 64종 + reactive retrieval + crosswalk 강등전 | ✅ (틀보다 성숙) |
| 추천 모델 학습 데이터 | 파이프라인 완비(BKT·IRT·CAT)·**입력 0행** | ⚠️ → **기존 추적**(`REC-01`) |
| 난이도 추정 | IRT 구현 완비(`l2/irt.py`)이나 응답 0 → θ가 `initial=0.0`으로 고정(`l2/irt.py:64,76`)·`irt_difficulty_b` 코퍼스 0건 | 🚫 §2-⑥ (입력 없는 파이프라인 = dead code) |
| A/B Test 분석 | 전용 A/B 프레임 없음. 대신 **shadow 계측 9종** + `harness/agreement_gate.py`(**McNemar 유의검정** — 베이스라인 대비 유의 개선만 PASS) | ✅ (다른 형태로, 통계적으로 더 엄격) |
| 개인화 모델 개선 | 좌석 완비·입력 0 | ⚠️ → **기존 추적**(`REC-01`) |

**84 종합**: 이 틀이 요구하는 **수집·계약·저장 좌석은 전부 있거나 우리가 더 엄격하다**
(페이로드 계약의 `extra="forbid"` seam은 틀에 아예 없는 축이다). 없는 것은 자재가 아니라
**입력의 연결**이며, 그 개별 축은 이미 `REC-01`·`NLP-01`·`NLP-02`·`S3-16`이 각자 추적한다.
따라서 **개별 축을 신규 갭으로 재등재하지 않는다**(중복 등재 금지). 진짜 신규 갭은 한 층 위에
있다 — 아래 §1-C.

### 모듈 85. 품질 모니터링 — **틀보다 엄격, 공백은 "이력"뿐**

#### ① 콘텐츠 품질

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 문제 오류·정답 오류 검출 | `l3/verify_answer.py`(3상태 `AnswerVerdict` — pass/fail/**unverifiable**)·`verify_solution.py`·`verify_step.py` + `l3/equivalent/acceptance.py` 4성분 수용 게이트 | ✅ (틀보다 엄격 — "미검증"을 "통과"로 위장하지 않는 3상태) |
| 수식 렌더링 검사 | `l3/notation_coverage.py`(코퍼스 표기 ⊆ 지원 표기, CI 상시) + `l3/equivalent/canonicalize.py`(DSL 폐쇄성) + `rephrase_hygiene.py`(발문 위생) | ✅ 부분 — LaTeX 파스 게이트는 `ARCH-19`가 추적 |
| **중복 문제 탐지** | 생성 시점 가드는 실배선(`find_near_duplicates` → `l3/equivalent/orchestrator.py:273` `rejected_duplicate`). **그러나 그 가드는 생성 오케스트레이터 경로만 덮는다** — 코퍼스 전수 집계 결과 **은행 간 slug 충돌 392건**·**발문 완전 동일 279그룹/566레코드**가 실재하고, 그중 **1쌍은 데모·파일럿 문제 풀에 살아 있다** | 🔴 **최대 갭 → D3** |
| 난이도 이상 탐지 | 입력 0 | 🚫 §2-⑥ |
| 이미지 품질 검사 | 이미지 자산 자체를 보유하지 않음(`figure.spec` 선언적 명세·렌더는 클라) | 🚫 §2-⑤ (소비처 없음) |

#### ② AI 품질

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| AI Tutor 응답 품질 | `harness/pedagogical_rubric.py`(정답 유출 결정론 부정지표) + `coach_prose_leak_eval.py`(결함주입 + 실서빙 경로 + Wilson **상한** 게이트, CI 상시) | ✅ |
| 생성 콘텐츠 평가 | `corpus_audit_eval.py`(S5 결함율 Wilson 상한 2%) + `defect_detection_eval.py`(결함 6종 주입 강등전) | ✅ (틀보다 엄격) |
| **Hallucination 탐지** | 전용 확률적 탐지기 **없음**. 대신 **구조적 대체**: SymPy 권위 이전(`symbolic_equivalence.py`)·K≥3 독립 다관점(`l3/cross_verify.py`, 생성자≠검증자 강제)·PRM UNVERIFIED 격리 | 🚫 **§2-⑨** (권위 서열상 상위 수단으로 이미 해결) |
| 응답 시간 측정 | `l3/router.py` `SLA_GATE_MS=2000`·`est_latency_ms` vs `latency_ms` 병기 + `ops/cost_report.py` p50/p90 | ✅ |
| 모델 버전 비교 | `agreement_gate.py`(McNemar) + shadow 9종 | ✅ (§2-⑩) |
| AI 추천 정확도 | 입력 0 | 🚫 §2-⑥ |

#### ③ 시스템 품질 — **`OPS-01`/`OPS-04`로 상환 완료**

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| API 성공률·오류 발생률·서버 응답 시간 | `ops/service_health.py` `ServiceMetrics` — **슬라이딩 창** error_rate·p95(전 기간 평균이 최근 악화를 희석하는 것 방지)·uptime. 프로브 경로(`_OPS_PROBE_PATHS`)는 표본에서 제외 | ✅ |
| DB 성능·Cache Hit Rate | `/health/ready` 딥체크(DB `SELECT 1`·Redis PING·LLM 라우터) + `CacheDegradationCounter` 이중 회계 | ✅ |
| 장애 탐지·SLA | `evaluate_alerts()` + `docs/standards/incident_response_slo.md`(SLO 5종, **미측정 항목은 미측정으로 정직 표기**하고 `test_slo_contract.py`가 기계 동결) | ✅ — 잔여는 §4 |

#### ④ 데이터 품질

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 스키마 검증 | `schemas/v1.1/*.schema.yaml` 계약 + Pydantic 런타임 + alembic 75본 | ✅ |
| ETL 검증·데이터 일관성 | data-pipeline **`validate.py` 11종**(선수 관계 순환 탐지 포함) | ✅ |
| 누락 데이터 탐지 | `ops/provenance_audit.py`(CI 상시)·`problem_bank_coverage.py`·`notation_coverage.py`·`visualization_reach_report.py` | ✅ |
| 중복 데이터 검사 | 개념·원자 축 `l1/atom_graph/dedup_candidates.py`(ARCH-16) ✅ · 풀이 축 `S4-12` 추적 중 · **문항 축은 실중복 발생**(위 ①) | 🔴 → **D3** |
| **이상값 탐지** | 콘텐츠 축만 존재. 학습 데이터(정답률·이탈) 축은 0 | 🚫 §2-⑥ (실학생 0) |

#### ⑤ 운영 대시보드

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 실시간 KPI · 운영 통계 UI | 없음 — 운영 CLI 산출 리포트가 배치 관측 대행 | 🚫 §2-④ (`operations_module_gap_review.md` §2-④ 승계) |
| SLA 모니터링 | `/health/ready` `alerts[]` + SLO 계약 동결 | ✅ |
| 품질 경고(Alert) | `AlertLogNotifier` — **로그 warning만**(채널 미배선) | ⚠️ → §4 (`incident_response_slo.md` §6에 이미 정직 기록) |
| 자동 리포트 | `qa_pipeline`(7축 단일 판정)·`corpus_reverify`(야간 cron)·커버리지 리포트 3종 | ✅ |
| **품질 이력 관리** | **0건** — `qa_pipeline`은 `--json qa_report.json`을 러너 작업 디렉터리에 쓸 뿐 **아티팩트 업로드도 커밋도 하지 않는다**(`ci.yml:187` 실측). 게다가 그 스텝은 현재 `continue-on-error: true`(S3-28 대기) | 🔴 **최대 갭 → D2** |

**85 종합**: 검사기 자산은 틀의 요구를 **대부분 초과 충족**한다(①②는 3상태 판정·Wilson 경계·
결함주입 강등전까지 간다). 공백은 둘이다 — ⑴ **중복 축의 사각지대**: 생성 시점 가드는 있으나
*은행 간·적재 시점*은 무방비라 이미 실중복이 발생해 있다(**D3**). ⑵ **판정의 시간축**: 매 실행의
판정이 휘발해서 `superhuman_verification_standard.md` §5가 명령한 *"롤링 결함율 상한 3% 초과 시
자동 재잠금"*을 **계산할 입력이 없다**(그래서 그 규약은 문서에만 있고 코드가 없다) — 게다가
그 게이트는 현재 `continue-on-error: true`라 **판정도 하지 않고 기록도 남기지 않는다**(**D2**).

> **초안 판정의 정정 기록**: 이 문서의 초고는 중복 축을 "생성 시점 가드가 실배선되어 있으므로
> ✅ 충족"으로 판정했다. 코퍼스 **전수 집계**로 재검증한 결과 그 판정은 **틀렸다** — 가드가
> 덮는 범위(생성 오케스트레이터 경로)와 실제 위험 표면(은행 간·`populate` 적재 시점)이 다르다.
> "방어 코드가 존재한다"를 "위험이 없다"로 읽은 것이고, 이 저장소가 반복해 온 *"존재함 ≠
> 돌아감"* 오류의 변종이다. **코드 존재 확인이 아니라 데이터 전수 집계가 판정 근거**여야 했다.

### §1-C. 두 모듈을 관통하는 진짜 갭 — "만들고 입력을 잇지 않음"의 **반복**

개별 축(OCR·추천·시각화·텔레메트리)의 미도달은 각자 태스크가 추적 중이라 신규 갭이 아니다.
그러나 **같은 사고가 반복된다는 사실 자체**는 어느 태스크도 다루지 않는다 — 저장소가 스스로
기록한 회차만 봐도:

| 회차 | 사고 | 추적 |
|---|---|---|
| 1~2 | `tests/infra` 199건을 어떤 CI 잡도 실행하지 않음 / 브랜치 보호 required check 통째 미강제 | `OPS-03`·`OPS-08` |
| 3 | 시각화 공급원 적재 0행 → 학생 도달 0회 | `VIZ-01` |
| 4 | OCR 배포 경로 양쪽 비활성 → 학생 도달 0회 | `NLP-01` |
| 5 | 학생 앱이 `POST /v1/me/attempts` 미호출 → 추천 입력 0행 | `REC-01` |

`NLP-01` notes는 이를 *"'완비된 소비 경로 + 미도달 공급원' 3회차"*, `REC-01` notes는
*"반복 실수 4·5회차 — '만들고 입력을 잇지 않음'·'만들고 켜지 않음'"*이라고 자인한다.

CLAUDE.md 실수 관리 규범은 **반복 실수(동일 유형 2회 이상)의 재발방지대책 등재를 의무**로 하고,
대책은 *"규칙(자동 로드)·코드(테스트 동결)·태스크(추적) 중 하나의 형태"*여야 한다고 못 박는다.
5회차에 이른 이 유형에 대해 현재 존재하는 대책은 **사후 관측 태스크뿐**이고, **사전 차단 장치가
없다**. 여기가 이 문서가 발견한 진짜 신규 갭이며 **D1**이 그 대책이다.

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 틀 제안 | 불채택 근거 |
|---|---|---|
| ① | 실시간 Event Bus·Data Lake·Analytics DB 분리·**ClickHouse**·이벤트 재처리 | **6번째 store 회피** — ChromaDB→pgvector 통합(2026-06-10 슬98)과 동일 논리. 실학생 0명·1인 운영에서 스트리밍 인프라 신설은 과공학이고, 운영 대상이 늘면 "측정 실패"가 아니라 "무증상 침묵"으로 죽는다(2026-07-16 Langfuse v2 8일 전멸 선례). `attempt_event`(append-only·hypertable)가 Event Store 역할을 이미 수행. **재판정 트리거는 §5** |
| ② | 클릭 스트림·화면 이동 경로·UI 사용 패턴·기능 사용 빈도 | CLAUDE.md 데이터 금기 — *미성년자 개인정보를 분석 목적으로 수집·외부 공유 금지* + 우리가 만들지 않는 것 *"학생을 수동적으로 만드는 설계"*. 행동 추적 전면 수집은 **교수학적 소비처 없이 프라이버시 표면만 키운다**. 교수학적 의미가 있는 축(**막힘**·stuck_at_step)은 이미 좌석 보유 |
| ③ | 학습 퍼널(완료율·목표 달성률·중단률)을 **KPI로 승격** | CLAUDE.md 교수학 금기 3개와 정면 충돌(§1-③ 블록쿼트 참조). **재정의 후에만 채택** — 정본 KPI는 `wh1_evaluation` 대리 지표 11종이고 퍼널 수치는 하위 관측치. 별도 퍼널 엔진 신설 안 함 |
| ④ | 실시간 KPI 대시보드·운영 통계 UI | **1인 capacity 가드** — `operations_module_gap_review.md` §2-④ 판정 승계(운영자 1인은 CLI 리포트로 감내). 계획은 `docs/design/ui/03_admin_console_plan.md` Phase A에 실재하고, 그 문서의 원칙 *"게이트 판정을 UI에서 손편집으로 우회하지 않는다"*를 유지 |
| ⑤ | 이미지 품질 검사 | **소비처 없는 설계 금지** — 이미지 자산을 보유하지 않는다(표현≠의미 원칙에 따라 `figure.spec` 구조로 저장하고 렌더는 클라) |
| ⑥ | 난이도 이상 탐지 · AI 추천 정확도 · 통계 이상값(정답률·이탈) | **입력 0 = dead code** — `problem_bank_gap_review.md` D9·`operations_module_gap_review.md` §2-⑦과 동일 사유. `S3-01` 파일럿 이후 |
| ⑦ | 개념 학습 완료·복습 완료 이벤트 | **복습 루프 기능 자체가 미구현** — 이벤트만 먼저 만들면 생산자 없는 휴면 enum이 하나 더 늘 뿐(현재 이미 8종 휴면). 기능이 생길 때 함께 |
| ⑧ | 중복 판정을 **SymPy 동치(verify 서명)로** 하기 | **측정된 반례로 기각** — `wm-skel-f50f96b5a691`(이차방정식 `x²+2x-48=0`의 큰 근)과 `wm-calc-ext-8c193941df77`(삼차함수 `x³+3x²-144x`의 극소점)은 **`verify.conditions`가 문자 그대로 같다**(극값 문제의 도함수가 그 이차식). 교수학적으로 완전히 다른 문항이다. 서명 동일을 게이트로 걸면 정상 문항을 중복으로 죽인다 — D3의 T3는 **관측만** |
| ⑨ | Hallucination 전용(확률적) 탐지기 | **검증 권위 서열 역행** — 초인간 검증 기준 v1의 서열은 ①기계 증명 ②측정 통과 기계 게이트 ③인간 폴백이다. 수학 주장의 진위는 SymPy(①)가 판정하고, 서술 축은 K≥3 독립 다관점(②)이 잡는다. 그 위에 확률적 탐지기를 얹으면 상위 권위의 판정을 하위 권위가 흐리는 구조가 된다 |
| ⑩ | 별도 A/B Test 프레임 | `agreement_gate.py`의 **McNemar 유의검정**(점추정 비교가 아니라 유의성 판정)과 shadow 계측 9종이 이미 그 실질. 신규 프레임은 truth source를 둘로 만든다 |

---

## §3. 설계 D1~D3 (진짜 갭의 WhyMath 정합 설계)

우선순위: **D3(이미 발생한 결함) → D1(반복 실수의 첫 기계 탐지기) → D2(비집행·무보존 가시화)**.

D3이 1순위인 이유는 단순하다 — **다른 둘은 "관측 좌석이 없다"이고 D3만 "결함이 이미 학생
노출 경로에 있다"**이다. 교수학적 정확성은 의사결정 우선순위 3위이고, 같은 문제를 두 번 내는
것은 진단 신호를 오염시킨다. D1은 5회 반복된 사고의 재발방지대책이라 CLAUDE.md 실수 관리
규범상 **등재 의무**에 해당한다.

### D3. 문항 수준 중복 감사 (신규 태스크 · 최우선)

**갭(전수 집계 실측)**: 문제은행 7종 2,647문 전수 —

```
은행 간 slug 충돌            392건  (generated_v0 ∩ rephrased_v0 — rephrased 429건의 91%)
발문(question_text) 완전 동일 279그룹 / 566레코드   (전부 은행 간, 은행 내부는 0)
  ├ 278  generated_v0 ↔ rephrased_v0   (재서술이 무동작이었던 건)
  └   1  problem_bank_v1 ↔ generated_v0  ← slug가 달라 양쪽 다 적재된다
```

그 **1건이 결정적**이다. `wm-quad-eq-larger-root`(v1)와 `wm-skel-92cd1ba2bbf5`(generated_v0)는
발문·정답(`3`)·난이도(`2.0`)가 동일한데 slug만 다르고, `scripts/demo/seed_demo.py`의 `_CORPORA`가
**두 은행을 모두 적재한다** — 즉 **지금 데모·파일럿 문제 풀에 완전 중복 문항 1쌍이 들어 있다**.

**잠재 위험(아직 터지지 않은 것)**: `seed_demo.py` 주석은 *"4문제만 시드하면 후보가 고갈돼 같은
문제 반복 체감(2026-07-22 실기기)"*라 적어 **풀 확대 동기가 이미 있다**. 그런데 `rephrased_v0`를
`_CORPORA`에 추가하는 순간 `populate.py`의 `ON CONFLICT(slug) DO UPDATE`가 **392행을 조용히
덮어쓴다**. 현재 slug 유일성 테스트는 `generated_v0` **내부**만 검사하므로 은행 간 충돌은
구조적으로 미측정이다.

**설계**: `harness/problem_duplication_audit.py` — 빌드타임 결정론(`problem_bank_coverage.py`의
코퍼스 전수 스캔·정직 회계 관례 답습). **3계층 판정의 분리가 설계의 본체다**:

| 계층 | 기준 | 현행 실측 | 판정 규약 |
|---|---|---|---|
| **T1** `slug_collision` | 은행 간 동일 slug | 392 | **exit 1**. 기존 392는 `pending-task:S4-14`로 유예(변형 계보 영속 미착지가 같은 근원) · 신규 충돌은 즉시 red |
| **T2** `identical_question_text` | 발문 정규화 후 완전 동일 | 279그룹 | **exit 1**. v1↔generated 1건(파일럿 실중복)은 red · 278건은 T1과 근원 동일이라 `S4-14` 승계 |
| **T3** `equivalent_verify_signature` | canonical verify 서명 동일 | — | **게이트 절대 금지 · 분포 관측만** |

**T3을 게이트로 만들지 않는 이유를 모듈 도크스트링에 반례 slug와 함께 박아 둔다**(§2-⑧).
이것이 없으면 다음 세션이 "SymPy 동치로 중복 잡자"는 **틀린 탐지기**를 만든다.

- **소비처(리포트로 끝내지 않는 지점)**: `_CORPORA`에 코퍼스를 추가할 때 **덮어쓰기 예상 건수를
  사전 보고**한다. `populate.py`는 배치 *내부* 중복만 "마지막 우선" dedup하고 배치 *간* 덮어쓰기는
  침묵하므로, "이 은행을 추가하면 392행이 덮인다"를 말해주는 것이 실사용 가치다.
- **CI 배선**: `qa_pipeline`의 **8번째 축**(`problem_duplication`) — 새 잡·새 스텝을 만들지 않고
  ARCH-21이 만든 좌석을 재사용(in-process import·subprocess 0 관례 준수).
- **범위 밖**: 실중복 1쌍의 *해소*(어느 쪽을 은퇴시킬지)는 콘텐츠 판정이라 별건 — **가시화까지**.

### D1. 공급↔소비 도달 대장 (신규 태스크 — 반복 실수의 첫 *기계* 탐지기)

**갭**: 서버에 write-path 엔드포인트가 있는데 **클라이언트가 호출하지 않는다는 사실을 아무도
기계로 잡지 않는다.** 그래서 매번 *사후에* 축별로 발견된다(§1-C 5회차). 기존 태스크들은 각자
**자기 축의 런타임 도달률**을 관측할 뿐, 축을 가로지르는 **빌드타임 구조 차단**은 없다.

**왜 "축별 리포트 조립"이 아닌가**: 초안은 `VIZ-01`/`NLP-01`/`REC-01`의 도달 리포트를 조립하는
층을 구상했으나 **기각한다** — 셋 중 둘이 아직 `todo`라 조립할 자산이 하나뿐이고(`qa_pipeline`이
성립한 이유는 검사기가 *먼저* 38개 있었기 때문), 세 리포트가 전부 **런타임 카운터**(DB 필요)라
조립 층도 DB에 묶여 결정론을 잃는다. 대신 **빌드타임 정적 대장**으로 간다.

**설계**: `ops/reach_audit.py` — 전 축 정적(DB 0·LLM 0·HTTP 0), **새 판정 로직 신설 0**.

| 축 | 공급(선언) | 소비(도달) 판정 |
|---|---|---|
| `http_routes` | `create_app()` 라우트 표 | `src/mobile/lib/**/*.dart`의 `/v1/…` 리터럴(`$var`→`{param}` 정규화) |
| `event_types` | `EventType` 11종 | `build_event_data` 생산 좌석 3종 |
| `timeseries_writers` | hypertable 모델(`db/models/timeseries.py`) | ORM 쓰기 경로 존재 |
| `harness_clis` | `main()` 보유 CLI | `ci.yml`의 `python -m …` **또는 in-process import**(`qa_pipeline`이 `corpus_audit_eval`을 import하는 경우를 도달로 계산 — 미계산 시 오탐) |

> **재구현 금지 — 이미 해결된 함정**: 라우트 표는 `tests/backend/ops/test_slo_contract.py:132`의
> `_app_route_paths()`를 **공용 헬퍼로 승격해 재사용**한다. FastAPI 0.140부터 `include_router()`가
> 하위 라우트를 평탄화하지 않고 `_IncludedRouter` 래퍼만 얹기 때문에, 순진하게 `app.routes`의
> `path`만 모으면 **`/v1/**` 전체가 통째로 누락된다**(그 파일의 도크스트링이 실측으로 기록).
> 이 문서 초안도 그 함정에 그대로 빠져 있었다.

**판정 규약 — 미도달 *수*가 아니라 *미분류*가 exit 1이다.** 미도달률 자체를 게이트로 걸면
즉시 영구 red이고 의미도 없다(콘텐츠 저작 API는 원래 클라가 부르지 않는다). 대신 **모든 공급
항목이 아래 4분류 중 하나를 반드시 가져야 한다**:

| 분류 | 의미 |
|---|---|
| `student-reached` | 클라 호출 실측(자동 판정) |
| `server-only-by-design` | 저작·관리·법정 권리 API 등 — **사유 문자열 필수** |
| `pending-task:<id>` | 미도달이나 백로그가 추적 중(`/v1/me/attempts`→`REC-01`, `/v1/ocr/pages`→`NLP-01` 등) |
| `unclassified` | ← **이것이 exit 1** |

이 규약의 예방 성질: **새 라우트를 추가하면 분류를 선언하기 전까지 CI가 red**다. 반복 실수의
구조("소비측이 완비돼 있어서 *존재함*이 *돌아감*으로 읽힌다")를 커밋 시점에 기계가 막는다.
이는 `EVENT_DATA_CONTRACT ∪ _CONTRACT_EXEMPT == 전체`를 거버넌스 테스트로 고정한 기존 패턴을
**라우트 축으로 확장**하는 것이다 — 새 발명이 아니라 검증된 패턴의 이식.

**유예 대장 규약(D1·D2 공유)**: `pending-task:<id>`는 `backlog/tasks/<id>.yaml`이 **실재하고
status가 done이 아닐 때만** 유효하다. 태스크가 사라지거나 done이 되면 exit 1 — **유예가 조용히
영구화되는 것을 막는다**. `backlog/`가 단일 진실 원천이므로 별도 대장 파일을 만들지 않는다.

- **변별력 검증(양방향 실측 의무)**: ⑴ 더미 라우트 추가 → **exit 1**(unclassified) ⑵ dart에서
  호출 1건 삭제 → `student-reached`가 무너지며 **exit 1** ⑶ `pending-task:`를 done 태스크로
  바꿈 → **exit 1**(유예 만료). 성공/실패가 같은 값을 내면 위장이다.
- **수집기 자체 위장 방어**: 라우트·클라 호출 수가 하한 미만이면 **exit 2**(추출기 파손 —
  정규식이 깨져 "0건 미도달"이 되는 것을 통과로 읽지 않는다. `test_slo_contract.py` 선례).
- **CI 배선**: `backend` 잡의 `provenance_audit` 스텝 뒤, **상시 실행**(라우트·클라 변경은 코퍼스
  변경이 아니므로 코퍼스 트리거 금지) + `tests/infra/`에 배선 실재성 동결(OPS-03/10/11 선례).
- **범위 밖(명시 동결)**: 클라이언트 attempt POST 실배선(`REC-01`·`NLP-02`) · 휴면 EventType
  소생(`S3-16`) · 개인화 기본값 전환. **가시화·차단이지 활성화가 아니다**(`NLP-01`과 동형).

### D2. QA 판정 보존·비집행 가시화 (신규 태스크)

**갭**: §1-85⑤ — `qa_pipeline`의 판정이 **완전히 휘발한다**. 결함율·검출률의 **추세**를 볼 수
없어 회귀 시점의 사후 규명이 불가능하고, `superhuman_verification_standard.md` §5의 *"롤링 결함율
상한 3% 초과 시 자동 재잠금"*은 계산할 입력이 없어 **문서 규약으로만 존재**한다.

> D2는 `S3-28`(canonicalize 축 결함 130건 판정)과 **층위가 다르다** — S3-28은 한 축의 판정
> *정확도*를 고치는 일이고, D2는 모든 축의 판정을 *시간축에 남기는* 일이다.

**목적 재정의(초안 축소)**: 초안은 "회귀 추세"를 목적으로 걸었으나 **좁힌다** — `qa_pipeline`은
코퍼스 변경 트리거라 원장 행이 드물게 쌓여 추세는 당분간 통계적으로 무의미하다(추세를 목적으로
걸면 그 자체가 소비처 없는 설계다). 진짜 목적은 **"가장 비싼 게이트가 며칠째 판정하지 않는지가
어디에도 보이지 않는다"**이다 — 2026-07-16 Langfuse 8일 무증상 전멸과 **같은 구조**다.

**설계**: 작은 것부터 세 조각.

1. **판정 보존** — `ci.yml`의 qa_pipeline 스텝에 `upload-artifact`(`qa_report.json`) 추가.
   커버리지 XML이 이미 하는 것과 동형이며, "판정이 러너와 함께 증발"을 몇 줄로 해소한다.
2. **비집행 waiver 동결** — `tests/infra/`에 신설. `ci.yml`에서 `continue-on-error: true`가 붙은
   **게이트성** 스텝마다 ⑴사유 주석 ⑵**열린 backlog 태스크 id**를 요구하고, 그 태스크가
   done/부재면 실패시킨다. 현 대상은 qa_pipeline 스텝(→`S3-28`) 1건이며, shellcheck처럼
   *의도적 조언* 스텝은 제외한다. **`S3-28`이 닫히는 순간 `continue-on-error` 제거가 강제된다.**
   D1의 유예 대장 규약과 **같은 메커니즘·같은 진실 원천**(`backlog/`).
3. **판정 원장(후행·선택)** — `qa_pipeline --ledger` → 커밋되는 NDJSON 1줄 = 1판정(커밋 sha ·
   축별 status · `overall.pass` · **enforced 불리언**). **새 store를 만들지 않는다**(§2-①과
   동일 논리). 원장 로드·append·부식 라인 회계는 `harness/wh1_shadow_harvest.py`의
   기존 함수를 **그대로 재사용**한다(부식 라인을 세어 보고하되 축적을 막지 않는 관례).

- **"검사 안 함"과 "통과"를 절대 혼동하지 않는다** — `not_measured_axes`·`no_snapshot`·`error`
  구분을 원장에 그대로 보존한다(침묵 통과 금지).
- **이중 회계 준수**: 파일 기반·인프로세스 — SaaS가 죽어도 판정치가 산출된다(`ops/cost_probe` 원칙).
- **변별력 검증**: ⑵에 대해 — `S3-28`을 임시 `done`으로 바꾸면 테스트가 **실패**해야 하고,
  `continue-on-error` 줄을 지우면 **통과**해야 한다. 양방향이 갈리지 않으면 위장이다.
- **범위 밖**: 대시보드 UI(§2-④ 유지) · 서비스 지표 영속화(OPS 축 — §4).

> **우선순위 주의**: D2는 `S3-28` 자체를 대체하지 않는다. 품질 축에서 가장 가치 있는 행동은
> 여전히 `equivalence_canonicalize` 130건 오탐 해소(`S3-28`)이며, D2는 그것이 미해소인 동안
> **비집행 상태가 잊히지 않게** 하는 장치다.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (사유 명시)

| 공백 | 사유 | 해소 시점 |
|---|---|---|
| 알림 채널(로그 warning만) | `incident_response_slo.md` §6에 이미 정직 기록 — *"로그를 보고 있지 않으면 알림이 아니다"*. 채널 선택(푸시·메신저)은 Kiki 결정 선행 | 온콜 체계 도입 시 |
| 서비스 지표 영속화(월간 오류 예산) | OPS 축이라 D2(콘텐츠 품질 이력)와 결이 다르다 — 한 원장에 섞으면 truth source가 둘이 된다 | OPS 후속 |
| 경로별(T1/T2/T3) 지연·외부 업타임 프로브 | SLO S4·S5를 **미측정으로 정직 표기 중**이고 `test_slo_contract.py`가 동결 | 프로브 도입 시 |
| 금칙어·PII·교육과정 위반 검사기 | 실 학생 대화 데이터 0 (`operations_module_gap_review.md` §4 승계) | 파일럿 축적 후 |
| 통계 이상값(정답률·이탈) | `S3-01` 이후 D9/`S4-15` 범위 | 파일럿 완료 |
| 실중복 1쌍의 **해소**(어느 쪽 은퇴) | D3는 가시화까지 — 어느 문항을 은퇴시킬지는 콘텐츠 판정 | D3 리포트 착지 직후 별건 |
| 서비스 지표 영속화·외부 업타임 프로브 | **`SEC-12`가 스케줄 진입점을 소유** — 여기서 따로 설계하면 배선 위치를 두 번 결정하게 된다 | `SEC-12` 착지 |
| ClickHouse·Event Bus | §2-① | §5 재판정 트리거 |
| **`privacy/erasure.py`·`export.py`의 `store="clickhouse"` `pending_external` 선언** | **역방향 거짓** — 존재하지 않는 store를 "못 지웠다"고 삭제 요청 학생에게 보고하는 셈이다. 없는 위험을 있다고 말한다. 이 문서는 **기록만 하고 코드는 손대지 않는다**(범위 밖) | §2-①로 ClickHouse 미채택이 확정됐으므로, 매니페스트에서 제거하거나 "미도입" 사유를 병기 — 별건 등재 대상 |

---

## §5. 실행 — 백로그 등재·재판정 트리거

### 백로그 신규 등재 (실제 ID는 `backlog.py add`가 배정 — 번호 추론 금지, HARN-10 준수)

- **D3 → 문항 수준 중복 감사** (`harness/problem_duplication_audit.py` 3계층 · T3 게이트 금지 ·
  `S4-14` 유예 · `qa_pipeline` 축 8 · `_CORPORA` 덮어쓰기 사전 보고)
  — track `infra-debt` · stage S3 · layer backend · **priority 2**.
- **D1 → 공급↔소비 도달 대장** (`ops/reach_audit.py` 4축 정적 · 4분류 미분류=exit 1 ·
  유예 대장 규약 · `_app_route_paths` 승격 재사용 · `backend` 잡 상시 · exit 2 파손 방어)
  — track `infra-debt` · stage S3 · layer backend · **priority 2**.
- **D2 → QA 판정 보존·비집행 가시화** (artifact 업로드 · `continue-on-error` waiver 동결 ·
  선택적 판정 원장) — track `infra-debt` · stage S3 · layer infra · **priority 3** ·
  D1 의존(유예 대장 규약 공유).

### 중복 등재 금지 대장 (이 설계가 건드리지 않는 기존 추적)

`S3-16-behavior-telemetry-writers`(휴면 EventType 소생·writer 미신설 동결) ·
`REC-01-recommendation-reach-observability`(추천 축 런타임 도달률) ·
`NLP-01-ocr-reachability-observability`(OCR 축) · `NLP-02-server-answer-grading-shadow`(채점 권위) ·
`ARCH-19`(LaTeX 파스·답 분포 게이트) · `OPS-16`(프롬프트 자산 감사 CI 배선) ·
`SEC-12`(보존 파기 스케줄·**외부 업타임 프로브의 선행 소유자**) · `S3-28`(canonicalize 축 결함
130건) · `S3-01`/`S4-15`(실응답 통계) · `S4-12`(풀이 축 클러스터링) · `S4-14`(rephrase 변형 계보
영속 — D3 T1/T2 유예의 근원).

**학습 퍼널에서 태스크를 만들지 않는 이유**(§2-③ 보강): 퍼널이 답하려는 질문("어디서 끊겼나")의
WhyMath 등가물은 **완료의 퍼널이 아니라 이해의 지형도**이며 이미 존재한다 —
`/v1/me/diagnosis/concepts`(BKT 개념별)·`wh1_evaluation`의 도움 감소 곡선·도달 깊이·숙달 델타.
비어 있는 이유는 지표 부재가 아니라 **입력 부재(attempt 0행)**이고 그건 `REC-01`이 추적한다.
여기서 태스크를 만들면 `REC-01`과 중복이면서 방향은 금기 쪽이다.

**D1과 이들의 경계**: 각 태스크는 자기 축의 **런타임 도달률**을 관측한다. D1은 축을 가로지르는
**빌드타임 계약 회귀 차단**이다 — 관측이 아니라 예방이고, 대상이 데이터가 아니라 코드 구조다.

### 재판정 트리거 (등재하지 않는 것)

| 항목 | 트리거 |
|---|---|
| ① ClickHouse·Event Bus·Data Lake | `attempt_event` 일 적재량이 Postgres 단일 인스턴스 분석 쿼리를 압박하거나(체감 지연), 파일럿 코호트가 상시 100명 이상 |
| ② 행동 분석(세션·이탈) 확대 | 교수학적 소비처가 먼저 실증될 때만 — 지표가 소비처를 만들지 않는다 |
| ③ 퍼널 지표 | 대리 지표 11종이 MEASURED로 채워진 뒤, 그 하위 관측치로만 |
| ④ 운영 대시보드 | `operations_module_gap_review.md` §5 트리거 승계(결제 도입·운영자 2인·CS 유입) |
| ⑥ 난이도·추천 정확도·통계 이상치 | `S3-01` 파일럿에서 실응답 축적 개시 |
| 알림 채널 | 온콜 담당이 실제로 생길 때(현재 온콜 0명) |

---

## 부록 — 실측 근거 (2026-08-03 실측)

- **클라이언트 호출 경로 13종**: `grep -rhno "'/v1/[^']*'" src/mobile/lib --include=*.dart | sort -u`
  → `/v1/auth/$provider/callback`·`/v1/coach`·`/v1/coach/sessions`(+`/$id`·`/$id/turns`)·
  `/v1/interactions`·`/v1/me/diagnosis/concepts`·`/v1/me/next-problem`·`/v1/ocr`·
  `/v1/problems/$problemId`·`/v1/scenes/weak-concept`·`/v1/users/me`·`/v1/verify-solution`.
  **`/v1/me/attempts`·`/v1/study/*`·`/v1/me/ability/snapshots` 부재.**
- **write-path 라우트 37개**: `api/*.py`의 `@router.{post,put,patch,delete}` 전수 — `me.py` 9건
  (`POST /attempts`·`POST /ability/snapshots` 포함)·`study.py` 2건·`concepts.py`/`problems.py`
  각 3건(운영 CRUD) 등. 라우터 등록은 `app.py:792-806`(`include_router` 15건).
- **θ 고정**: `l2/irt.py:64`(`initial: float = 0.0`)·`:76`(`if not responses: return initial`).
- **EventType 11종·휴면 8종**: `schema/enums.py:836-880`(도크스트링이 계약 면제를 자인) +
  `schema/event_data_contract.py`(`_CONTRACT_EXEMPT`).
- **ClickHouse 코드 0건**: `privacy/erasure.py:117-173`·`privacy/export.py:130-145`에
  `store="clickhouse"` 문자열(삭제·반출 **미수행** 대상 매니페스트)로만 등장. OpenTelemetry는
  `pyproject.toml:45-46` 의존성만 있고 `import opentelemetry` 0건.
- **qa_pipeline 휘발**: `.github/workflows/ci.yml:178-187` — `if: needs.changes.outputs.corpus ==
  'true'` · `continue-on-error: true`(S3-28 대기) · `--json qa_report.json`을 러너 작업
  디렉터리에 쓸 뿐 upload-artifact 스텝 없음.
- **S5 재잠금 규약 원문**: `docs/standards/superhuman_verification_standard.md:134-135`
  ("롤링 결함율 상한이 **3% 초과** 시 해당 게이트를 자동 재잠금").
- **문항 중복 — 코퍼스 전수 집계**(`data/corpus/problem_bank_*/problems.jsonl` 7종 2,647건):
  은행별 `conceptual_v0` 360 · `generated_v0` 620 · `killer_v0` 120 · `misconception_mc_v0` 1080 ·
  `probability_finite_v0` 34 · `rephrased_v0` 429 · `v1` 4.
  **은행 간 slug 충돌 392건**(전부 `generated_v0` ∩ `rephrased_v0`) ·
  **발문 완전 동일 279그룹/566레코드**(278 = generated↔rephrased · **1 = v1↔generated**, 은행
  내부 중복은 0). 실중복 1쌍 = `wm-quad-eq-larger-root`(v1) ↔ `wm-skel-92cd1ba2bbf5`(generated_v0),
  발문·`answer="3"`·`difficulty_overall=2.0` 동일(`verify` 블록만 상이).
- **그 1쌍이 학생 노출 경로에 있는 근거**: `scripts/demo/seed_demo.py`의 `_CORPORA`가
  `problem_bank_v1` + `generated_v0` + `misconception_mc_v0`를 **모두 적재**(주석: 4문제만
  시드하면 후보 고갈로 "같은 문제 반복" 체감 — 2026-07-22 실기기).
- **T3 반례(서명 동일 ≠ 중복)**: `wm-skel-f50f96b5a691`(이차방정식 큰 근·answer 6)과
  `wm-calc-ext-8c193941df77`(삼차함수 `x³+3x²-144x` 극소점·answer 6)이 **`verify.conditions`가
  둘 다 `x**2 + 2*x - 48 = 0`**(극값 문제의 도함수).
- **생성 시점 가드의 범위**: `l1/problem_bank/embedding.py`(`find_near_duplicates`·
  `is_near_duplicate`) → 소비처 `l3/equivalent/orchestrator.py:38`(import)·`:273`(호출)·
  `:195`(도크스트링 "과유사면 `rejected_duplicate`"). **생성 오케스트레이터 경로 전용** —
  은행 간·`populate` 적재 시점은 덮지 않는다(위 실측이 그 증거).
- **라우트 표 함정(D1 재사용 근거)**: `tests/backend/ops/test_slo_contract.py:132-154`
  `_app_route_paths()` — FastAPI 0.140에서 `include_router()`가 평탄화하지 않고 `_IncludedRouter`
  래퍼만 얹어 `original_router` 재귀가 없으면 `/v1/**`이 통째로 누락된다(도크스트링에 실측 기록).
- **ClickHouse 역방향 거짓**: `privacy/erasure.py:117-137` — `ExternalErasureTarget(store=
  "clickhouse", data="학습 행동 로그(이벤트 스트림·분석)", reason="별도 분석 store·비동기 배치
  삭제")를 `pending_external`로 반환하나 **그 store는 존재하지 않는다**.
- **품질 게이트 CI 배선**: `ci.yml` — `defect_detection_eval`·`coach_prose_leak_eval`·
  `pedagogy_pack_fidelity`·`l3.notation_coverage`·`ops.provenance_audit`(상시) ·
  `corpus_reverify`(`e2e-nightly` cron `0 18 * * *`) · `qa_pipeline`(코퍼스 변경 시).
- **반복 실수 자인**: `backlog/tasks/NLP-01-ocr-reachability-observability.yaml` notes
  ("3회차") · `backlog/tasks/REC-01-recommendation-reach-observability.yaml` notes
  ("반복 실수 4·5회차 — '만들고 입력을 잇지 않음'·'만들고 켜지 않음'").
- **선례 리포트 구조**: `harness/visualization_reach_report.py:1-30`(빌드타임 결정론·게이트 아님·
  "100% 도달은 목표가 아니다") · `harness/qa_pipeline.py:1-57`(subprocess 0·in-process import·
  새 판정 로직 신설 0·`not_measured_axes` 침묵 통과 금지) · `:142-147`(미측정 4축 선언).
