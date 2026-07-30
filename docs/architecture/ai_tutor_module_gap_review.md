# AI 튜터(AI Tutor) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-29)

> **범위**: 외부 참고 문서 『AI Tutor』(기능 37~41: 대화형 AI 튜터 · Socratic 질문 · 학습 코칭 ·
> 실시간 피드백 · 개인화 설명 — **WhyMath 전용이 아닌 일반적 EOS 틀**, Kiki 제공)을 현
> 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(교수학 5원칙·검증 권위
> 서열·컨텍스트 오염 방지·dead code 금기·미성년자 보호) 안에서 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(모듈 6~10, 2026-07-27) · `problem_bank_gap_review.md`
> (기능 18~22, 2026-07-28) · `solution_module_gap_review.md`(기능 23~27, 2026-07-29) 답습 — 4번째
> 자매편.
> **대전제 2가지**: ① WhyMath에는 **이미 작동하는 AI 튜터가 존재한다**(WH-1 하네스 primary 경로
> 2026-07-20 GA · Polya 4단계 결정론 엔진 · 소크라테스 6카테고리 · 오개념 카탈로그 64종 · 3상태
> 단계검증) — 이 문서는 무에서의 설계가 아니라 **격차 보완**이다. ② 튜터는 **매 턴 옳은 교수
> 결정을 계산하지만, 그 결정을 기록하지 않는다** — 진짜 갭의 대부분은 "무엇을 할지 모른다"가
> 아니라 "방금 무엇을 했는지 기억하지 못한다"는 축에 있다.
> **결론**: 기능 38(Socratic)·40(오류탐지 핵심)은 **문서보다 엄격**하다(결정론 선택·3상태
> 검증·OCR 게이팅). 37·41은 **턴 내(in-turn) 충족·턴 간·세션 간(across-turn) 공백**.
> **39가 최대 갭**이나 "전무"는 아니다 — 강도축·순서축은 이미 답하고, 없는 것은 **시간축·목표축**
> 이다. 진짜 갭 6건을 설계(D1~D6, D6은 페이퍼)하고 실행 4건을 백로그에 등재했다. 의도적
> 미채택 8건 · 정직한 공백 9종 · 유보 발화조건 9건. 정본 2곳(`04a` §5.1 · `02_learner_model.md`
> LearnerState)을 이번 설계에 맞춰 개정한다.

관련 정본: `04_pedagogy_engine.md`(Polya·소크라테스·답미루기 정본) · `04a_wh1_tutoring_harness.md`
(WH-1 하네스·도구 8종·전략 계층 §11) · `04d_adaptive_pedagogy_engine.md`(Runtime Selector·bandit
policy) · `02_learner_model.md`(LearnerState·MasteryState 계약) · `03a_l3_router_design.md`(LLM
라우팅) · `docs/standards/build_checkpoint_questions.md` 단계 8(AI 튜터 체크리스트) ·
`docs/strategy/core_feature_review_2026-07.md`(기존 "AI 튜터 🟢 완전 구현" 판정 — §0 무모순
설명) · `solution_module_gap_review.md`(힌트 내용 생성 D3 — 자매 갭) · `MEMORY.md` 결정 로그
(2026-07-29).

---

## §0. 전제 — 실측 현황 스냅샷 (2026-07-29 기준)

**이미 GA·가동 중**:
- **WH-1 primary**: `harness/wh1_primary.py:90` `run_wh1_primary_turn` — `wh1_primary_enabled`
  **기본 True**(`config.py:168`, 2026-07-20 GA). `/v1/coach/sessions(+/turns)`에서 학생과의 실제
  발화가 하네스 발화로 대체됨. 도구 8종(`read_student_state`·`verify_step`·`match_misconception`·
  `curate_hypothesis`·`query_curriculum`·`select_probe`·`log_evidence`·`end_turn`) 디스패치 +
  **verify 의무·정답 억제 백스톱·`end_turn` 독점** 불변식 강제(`harness/wh1_loop.py:517`).
- **Polya 4단계**: `l4/polya/engine.py:59` `PolyaCoach.decide` — LLM 0회 순수 결정. 전이 임계는
  숙달도별 가감(`l4/polya/transitions.py:20-24,51-54`).
- **소크라테스**: `l4/socratic/select.py:100` `select_category` — 단계 기본→발화신호 오버라이드→
  고신뢰(confidence≥0.65·recency≤2턴) 가설 시 ASSUMPTION. 6카테고리(`l4/socratic/categories.py:17-35`
  CLARIFICATION/ASSUMPTION/EVIDENCE/PERSPECTIVE/IMPLICATION/META)가 외부 문서 6유형(개념확인·근거
  확인·예측·반례·일반화·메타인지)과 거의 1:1.
- **답 미루기**: `l4/hint_deferral.py:24-79` `HintLevel 1~4`·`decide_hint_level`(좌절/답요구 토큰·
  5턴 막힘 임계·mastery ZPD 양방향 조정). Level 4는 PRD 척도 밖 안전망.
- **오개념 서브시스템**(약 40파일): 카탈로그 **64종**(`l4/misconception/catalog.py`, doc-first
  트랜치 누적) · 라벨 프로브 **162건**(`probes_v1.jsonl`) · pgvector semantic matcher ·
  `match_gate.py`(top1<0.65 비움·OCR<0.8 플래그) · `hypothesis_store.py`(감쇠·강화·최대5캡·영속) ·
  `evidence_store.py`(`log_evidence`) · `probe_selection.py`(정보이득+ε탐색) · `intervene.py`(개입
  4패턴) · `warmstart.py`.
- **실시간 단계 검증**: `l3/verify_step.py` **3상태**(correct/incorrect/**unverifiable**·SymPy
  단일권위) → `l3/verify_solution.py`(연쇄·`first_incorrect_index`·`unverified_ratio`) →
  `api/verify.py:73/118/206`. 오류 *위치* 인지 발화(`l4/metacognitive_trigger.py:114/156`, 정답·
  "틀렸다" 부재를 테스트로 가드) + OCR 저신뢰(<0.8) 시 `verification_ocr_gated`로 위치지목 보류.
- **대화 영속**: `POST /v1/coach`(stateless)·`POST /v1/coach/sessions`·`POST .../turns`·
  `GET .../{id}`(`api/coach.py:1264/1301/1509/1720`). `Dialogue`/`DialogueTurn` 본문·이미지 **봉투
  암호화**(SEC-01).
- **L2 학습자 모델**: BKT(`l2/bkt.py`, `p_forget` 포함)·IRT(`l2/irt.py`, JMLE·CAT·SE)·BKT↔IRT
  교차검증(`l2/concept_diagnosis.py:33`)·약점추천(`l2/weak_concept_recommendation.py:147`)·막힌
  선수개념 재귀 CTE(`l2/prerequisite_recommendation.py:338`)·학습경로 위상정렬
  (`l2/learning_path.py:143`)·`GET /me/next-problem`(IRT CAT + `measurement_sufficient`,
  `api/me.py:1609`).

**정직 자인이 이미 코드에 있는 곳**(신뢰의 근거): `l4/pedagogy/runtime_selector.py:96-112`가
"집중도·학습시간·선호 3개 신호는 생산자가 없어 필드로 만들지 않는다"고 명시 · `schema/enums.py:843`
가 "EventType 11종 중 3종만 생산·8종은 생산자 0이라 계약 면제(휴면)"라고 명시 ·
`harness/pilot_kpi_baseline.py:512`가 "KPI3 정서안전 = NO_DATA"를 정직 표기.

**기존 판정과의 무모순**: `docs/strategy/core_feature_review_2026-07.md:30` "AI 튜터(자연어 QA·단계
설명·힌트) 🟢 완전 구현"과 이 문서는 모순이 아니다. 그 판정의 층위는 **"지금 이 턴에 무엇을
할지"**(Polya 단계 결정·소크라테스 카테고리 선택·답 미루기 사다리·톤 필터 — 실제로 GA·완전
구현·LLM 0회 결정론)이고, 이 문서가 다루는 층위는 **"지난번에 무엇을 했고 언제 다시 볼지"**(교수
결정 기록·학습자 상태 조립·시간축·행동 텔레메트리 — 공백). `solution_module_gap_review.md:46`의
층위 구분 서술(레벨 결정 vs 레벨 내용)과 같은 형식이다.

---

## §1. 기능 37~41 ↔ WhyMath crosswalk 판정

### 기능 37. 대화형 AI 튜터 — **부분적(강함): 내부 흐름 6단 중 5단 실가동**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 자연어 QA·개념설명 | `POST /v1/coach` + 결정론 Polya 템플릿(`l4/polya/prompts.py:18-95`) | ✅ |
| 풀이 지원 | WH-1 도구 8종 + verify 의무 강제 | ✅ (문서보다 엄격) |
| 오답 분석 | 오개념 서브시스템 40파일 | ✅ |
| 복습 안내 | 강도축(`weak-concepts`) 실재 / **시간축 0** | ⚠️ → **D5** |
| 학습목표 관리 | `target_grade/target_score/target_exam_date` 컬럼 실재·**reader 0** | ⚠️ → **D5** |
| **이전 학습 기억 활용** | `warmstart.py`가 직전 증거 기반 가설 프리로드(confidence 0.4)로 부분 착지 / **대화·결정 이력 회상 0**(`wh1_llm_policy.py:298-326` 요약엔 턴인덱스·가설·도구이력만) | ⚠️ → **D1** (세션 간 reader) |
| ①질문(엔드포인트) | 3종 실재 | ✅ |
| ②의도 분석 | `DialogueTurn.student_intent` enum(답시도/질문/막힘표현/포기/이해확인) 실재·**writer 0** | ⚠️ → **D1** |
| ③관련 개념 검색 | `l1.atom_graph.search_atoms` + pgvector matcher | ✅ |
| ④**학생 모델 조회** | `LearnerState` 클래스 부재 — 소비처마다 조각 직접 조회 | ⚠️ → **D3** (근원 갭) |
| ⑤교수 전략 선택 | `PolyaCoach.decide`·`select_category`·`runtime_selector`(select≤gate) | ✅ (LLM 0회 — 엄격) |
| ⑥응답 생성 | 정적 템플릿 + 톤 필터 6패턴 + 정답 억제 백스톱 | ✅ |
| 스트리밍 응답 | SSE/WS 0 | §4-④ |

### 기능 38. Socratic 질문 — **대부분 충족(6유형 1:1 · 선택이 결정론)**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 6유형(개념확인·근거확인·예측·반례·일반화·메타인지) | `categories.py:17-35` 6종 — 거의 1:1 | ✅ |
| ①학생답변→②이해도 추정 | `DialogueTurn.student_understanding_signal`(Numeric(3,2)) 실재·**writer 0**. 실동작 근사=BKT/IRT 숙달도·막힘 카운트 | ⚠️ → **D1** |
| ③질문 유형 선택 | `select_category`(임계 0.65/2턴 명시) | ✅ (문서보다 엄격) |
| ④질문 생성 | 정적 템플릿 4개 + 카테고리별 발문 | ✅ |
| 질문 카탈로그 규모 | 외부 문서 요구(6유형)는 충족. 내부 목표 50+ 대비 6종×예시 1문장 | §4-⑨ |
| 답 대신 질문 원칙 | `HintLevel 1~4` + Level 4 안전망 | ✅ |

### 기능 39. 학습 코칭 — **최대 갭: 강도축·순서축 실재 / 시간축·목표축 전무**

> **가설 검증**: "39가 최대 갭"은 맞다. **"전무"는 부정확** — 출력 4종 중 "오늘 복습할 개념"은
> `GET /me/weak-concepts`가, "추천 학습순서"는 `learning_path`(Kahn 위상정렬)+
> `prerequisite_coaching.py:32`(막힌 선수 우선)가 **이미 답한다**. 전무한 것은 **언제(시간축)**
> 와 **목표까지 얼마나(목표축)** 다.

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 입력: 학습이력 | `concept_mastery_history`(live writer·`measured_at`)·`attempt_event` | ✅ |
| 입력: 약점 | `compute_concept_diagnoses`(BKT↔IRT 교차검증) | ✅ |
| 입력: 진도 | 성취기준·활성교과서·그림자 커리큘럼(L1) | ✅ |
| 입력: 목표점수 | 컬럼 실재·**reader 0** | ⚠️ → **D5** |
| 입력: 학습시간 | `learning_session` ORM **행 자체가 writer 0** | ⚠️ → **D4**(턴 간격 근사) |
| 출력: 오늘 복습할 개념 | 강도축 ✅ / **시간축(망각 기반 due) 0** | ⚠️ 부분 → **D5** |
| 출력: 추천 학습순서 | `learning_path`+`prerequisite_coaching` | ✅ |
| 출력: 이번주 목표 | 0(주 단위 목표 엔티티 0) | ⚠️ → **D5**(최소형) |
| 출력: 시험까지 남은 학습량 | 0(`target_exam_date` 미소비) | ⚠️ → **D5**(D-day+커버리지) |
| 복습 일정(간격 반복) | `apply_forgetting`은 다음 관측 시 prior 보정에만 — "언제"를 계산 안 함 | ⚠️ → **D5** |
| 학습계획(1년 사이클) | PRD FR-010 P0 — 코드 0 | ~~§4-⑤ 유보~~ → **2026-07-30 Kiki 결정으로 유보 해제**(PRD P0 정본 채택). `learning_path_module_gap_review.md` §3 **D7·D8**로 이관 — `PATH-04`·`PATH-05`. `study_plan` **엔티티** 불채택은 유지(파생 구현) |
| 학습습관 분석 | dead table 5종(`daily_learning_metrics` 등) 스키마만·쓰기 0 | 🚫 §2-③ |
| 동기부여 | 톤 필터·격려 발화만 | 🚫 §2-③ |
| 시험대비 전략(D-100) | PRD FR-020 P1 v1.5 | ⏸ §4-⑤ |

### 기능 40. 실시간 피드백 — **부분적(강함): 오류탐지·피드백생성 초과충족 / 텔레메트리·채널이 갭**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 분석: 답안/풀이과정/수식입력 | `verify_answer`·`verify_solution`(연쇄·`first_incorrect_index`) | ✅ (엄격) |
| 분석: 힌트 사용 | `attempt_event(힌트제공)` supply만 적재 / **demand(`힌트요청`) 미적재**(코드 자인, `coach.py:962`) | ⚠️ → **D4** |
| 분석: 오답 | 오개념 진단 파이프라인 | ✅ |
| 분석: 입력 시간 | EventType 휴면·응답시간 z-score 0 | ⚠️ → **D4** |
| 분석: 수정 횟수 | `지움` EventType 휴면·클라 계약 필요 | §4-⑥ |
| 피드백 "부호 확인" 류 | `first_incorrect_index`+메타인지 트리거 + OCR<0.8 게이팅 | ✅ (엄격) |
| 피드백 "공식을 잘못 선택" | 전략 오류 판정 좌석 0(오개념 judge가 부분 근사) | ⚠️ §4-① |
| 피드백 "그래프 축 확인" | 시각화 축 — `S4-03` 승계 | ⏸ |
| 피드백 "더 간단한 풀이" | `S4-10`(타세션 claim 중)·`S4-12` 승계 | ⏸ |
| ①행동→②분석→③탐지→④생성 | ②③④ 실가동. ①은 턴 단위(스트림 아님) | ⚠️ §4-④ |
| "실시간" 채널 | SSE/WS 0·fast path 0 | §4-④ |

### 기능 41. 개인화 설명 — **부분적: 6요소 중 2 착지 / '이전 성공 여부'는 좌석 자체 부재 / 4단 축 미채택**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 고려: 숙련도 | `mastery_to_level`·`adapt_lthc`·프롬프트 학습자 계층(MasteryLevel 라벨) | ✅ |
| 고려: 오개념 | 프롬프트 3계층(id+confidence만 — 본문 오염 차단) | ✅ (엄격) |
| 고려: 학년(grade) | `user_profile.grade` 실재. L4 소비는 **음성 낭독 1곳뿐** | ⚠️ → **D3** |
| 고려: 선행학습 | 진단·추천은 실재 / **설명 개인화 슬롯 미착지** | ⚠️ → **D3** |
| 고려: 학습 스타일 | 생산자 0 | 🚫 §2-⑦ |
| 고려: **이전 설명 성공 여부** | **좌석 자체 부재** — `socratic_strategy`·`targeted_step` writer 0(무엇을 썼는지 기록 안 함), `student_understanding_signal` writer 0(효과 관측 안 함), `PED-03` bandit 명시적 미승격 | ⚠️ → **D1**(근원) |
| 비유 생성 | 정의 레지스터(`S4-05`)·오개념 개입 패턴 | ⏸ 승계 |
| 초등/중등/고등/대학 4단 | 타깃 페르소나(한국 중·고, A 고3 MVP) 밖 | 🚫 §2-① |

**"이전 학습 기억"(37)·"이전 설명 성공 여부"(41)의 최종 배치**: 둘은 **같은 근원 갭의 두 얼굴**
이다 — 튜터가 매 턴 결정을 *계산*하지만 *기록하지 않는다*(`select_category`가 카테고리를 뽑는데
컬럼은 NULL). 둘 다 **D1**로 보낸다. 층위만 나눈다 — 37의 "기억"은 D1의 **세션 간 reader**
(warmstart가 절반 담당·D1이 나머지), 41의 "성공 여부"는 D1의 **턴 간 reader**(같은 전략 반복
회피 + `PED-03` 보상 신호 공급). **원문 재주입은 어느 쪽도 아니다**(§2-⑤).

---

## §2. 의도적 미채택 (8건)

| # | 문서 제안 | 불채택 근거 |
|---|---|---|
| ① | 초등(피자)→대학(유리함수) 4단 개인화 축 (41) | 타깃 페르소나 밖(한국 중·고, A 고3 MVP). `S4-05` 선례(초등·영재 레지스터는 페르소나 v1.5/v2.0 도달 시) 동형. 중·고 *내* 적응은 LTHC·mastery 양방향 조정 기존 축 |
| ② | 정서 상태의 **학생 대면 노출·감정 라벨링**("좌절한 것 같네") | 부정 피드백 정서 강화 금지 + "확실하지 않을 때 자신 있게 말함" 금지(추정 불확실성을 단정 발화로 전환). 정서 신호는 **내부 결정 입력**으로만 |
| ③ | 학습습관 게임화(스트릭·랭킹·학습시간 리더보드·푸시 압박) + dead table 5종 소생 | 무자비 게임화 금지 + "정답 빠르게" KPI 금지 + 미성년자 압박형 넛지 회피. dead table을 되살려 습관 대시보드를 만드는 경로도 목적이 게임화라면 함께 불채택 |
| ④ | SM-2/FSRS 등 카드형 간격 반복 알고리즘 도입 | 이중 진실원천 금지 — BKT `p_forget`이 이미 망각의 단일 권위(`l2/bkt.py:109`). 카드형 스케줄은 개념 그래프 축과 모델이 달라 두 진실원천이 생긴다. D5는 기존 망각 곡선의 시간축 노출로 대체 |
| ⑤ | `recall_dialogue`의 **대화 원문 LLM 재주입**(04a §5.1) | 미성년자 대화 평문 노출 최소화(SEC-01) + `LLMTutorPolicy`의 "학생 원문·정답은 사적 필드" GA 불변식(2026-07-20) + 컨텍스트 오염·예산 가드(`_MAX_PROMPT_TOKENS=3000`). 회상은 **구조화 메타 한정**(D1)으로 축소하고 `04a §5.1` 문구를 강등 개정한다(§5-⑥). 원문 복원은 사람(교사·연구) 감사 경로만(별도 축, 이번 범위 밖) |
| ⑥ | 멀티에이전트 튜터(향후확장) | 검증 권위 서열(기계증명>측정통과게이트>인간폴백) 붕괴 — 에이전트 상호 승인은 AI 자기승인과 동형. 현 하네스는 `end_turn` 독점으로 단일 권위를 구조화했고 이것이 정답 억제 백스톱의 전제 |
| ⑦ | 학습 스타일(VARK류) 진단·분류 (41) | 생산자 0 + `runtime_selector.py:96-112`의 명시 결정("생산자 없는 신호는 필드로 만들지 않는다"). 대체 축=숙달도·오개념·확신도 보정 3종 |
| ⑧ | 학생 대면 예상 점수·등급 시뮬레이션을 코칭 발화로 노출 (39 시험대비) | `solution_module_gap_review.md §2-①`(점수 서열화 금지) 승계. D5의 목표축은 점수 예측이 아니라 **목표 성취기준 커버리지**로 표현 |

---

## §3. 설계 D1~D6

**실행 순서**: **D1 → D3 → D4 → D5**, D2는 D1과 동일 슬라이스, D6은 페이퍼. D1이 41·37·38(이해도)의
공통 원천이고, D3의 "이전 설명 성공" 필드는 D1 없이는 항상 None이며, D4는 파일럿(S3-01) *개시
전*에 관측 기반을 깔아야 하므로 파일럿 잠금 대상이 아니다.

### D1. 교수 결정 로그 writer + 세션 간 구조화 회상 (백로그 `PED-04`)

**문제**: 결정은 이미 계산되는데 저장되지 않는다 → (a) 같은 전략을 반복해도 모른다 (b) 어떤
설명이 통했는지 모른다 (c) `PED-03` bandit이 보상 신호를 못 받아 영구 미승격 (d) 지난 세션
연속성이 warmstart(가설) 한 축뿐.

**⚠️ 설계 정정(실측 재확인, 2026-07-29)**: 당초 "`socratic_strategy` 컬럼에 `select_category`
반환값을 그대로 채운다"로 구상했으나, **두 값은 서로 다른 enum 공간**이다 —
`db/models/dialogue.py:181` `DialogueTurn.socratic_strategy`의 타입은 `schema/enums.py:921`
`SocraticStrategy`(조건확인·예시제시·반례제시·단계분해·유사문제·그래프그리기제안 — **교수
전략 실행 방식**)이고, `select_category`의 반환 타입은 `l4/socratic/categories.py:17`
`SocraticCategory`(CLARIFICATION·ASSUMPTION·EVIDENCE·PERSPECTIVE·IMPLICATION·META — **질문
유형**)로 서로 직교한다. 재계산 0 원칙(dead code 금지 대응)을 지키려면 **매핑을 새로 발명하지
않고, 두 값을 각자의 자리에 쓴다**: `targeted_step`(Polya 단계/`first_incorrect_index`)와
함께 **컬럼 자체 목적에 맞는 값만 채운다** — `socratic_strategy` 컬럼에는 발화가 실제로
사용한 교수 전략(예: 소크라테스 질문 생성 시 `단계분해`·`반례제시` 등 발화 구조를 결정하는
축, `l4/polya/prompts.py`·`intervene.py`의 개입 패턴과 대응)을 채우고, **질문 유형
(SocraticCategory)은 신규 컬럼 없이 `student_intent` 옆에 별도 nullable 텍스트 필드로 부기
하거나(스키마 변경 최소화 우선) 다음 우선순위로 미룬다** — 이는 D1 착수 시 **첫 확인
항목**으로 스키마 대조 후 확정한다(§ 불확실 항목 참조). 이 정정으로 인해 acceptance ①의
"컬럼 4개 NOT NULL" 목표는 **실제 대응 가능한 3개(`targeted_step`·`student_intent`·
`student_understanding_signal`) + `socratic_strategy`는 값 공간을 좁혀 채움**으로 조정한다.

**정합 설계**
- **writer**: `api/coach.py`의 세션 경로(`create_session`·`append_turns`)에서 이미 손에 든
  값을 채운다 — `targeted_step`(Polya 단계 인덱스 또는 `first_incorrect_index`),
  `student_intent`(`hint_deferral`의 답요구/좌절 토큰 분류 → `StudentIntent` 5종 매핑 —
  `답시도`/`질문`/`막힘표현`/`포기`/`이해확인`), `student_understanding_signal`(BKT posterior +
  verify verdict + 막힘 카운트의 **결정론 합성 스칼라** — 새 추정기 아님), `socratic_strategy`
  (개입/발화가 실제로 사용한 `SocraticStrategy` 값 — 소크라테스 질문 카테고리가 아니라 발화
  구조). `_log_hint_event` 선례 그대로 **재계산 0**.
- **reader ① 턴 간**: `select_category`에 `recent_categories: tuple[SocraticCategory, ...]`
  인자 추가 — 동일 카테고리 3연속 시 차선 카테고리로 회전(발화신호 오버라이드 우선순위 아래에
  삽입, 결정론 유지·LLM 0회). 이 회전 이력은 **컬럼이 아니라 세션 내 인메모리 상태**(하네스
  턴 시퀀스)로 유지 가능하면 신규 스키마를 더 줄일 수 있음 — 착수 시 재검토.
- **reader ② 세션 간 회상**: `recall_session_context(student_id) -> SessionRecall`(순수 조립) =
  `{last_polya_stage, unresolved_hypothesis_ids, last_socratic_strategies, turns_since}`.
  **원문 0·복호 0**(암호화 봉투를 열지 않는다 — 메타 컬럼은 평문). `wh1_llm_policy`의 사적
  컨텍스트로만 주입하고 기존 `_MAX_*` 예산 가드 안에 넣는다. `warmstart`와 **상보**(warmstart=
  무엇을 의심할지, recall=무엇을 이미 시도했는지).
- **정본 개정 동반**: `04a §5.1`의 "원문 재조회" → "원문은 보존, 회상은 메타 한정"으로 강등
  (§2-⑤ 근거, §5-⑥ 절차).

**dead code 금지 충족**: 신규 테이블 0. 컬럼은 기존 스키마 실재(4개 중 3~4개 소생). writer·reader
동일 슬라이스.
**측정 없는 도입 없음**: `harness/wh1_evaluation.py` 0단계 대리지표에 "전략 다양성"·"연속 반복률"
2종 추가 → `GET /v1/me/harness-metrics` 노출.

**acceptance 후보**
1. 세션 경로 2 엔드포인트가 턴 메타 컬럼(최소 `targeted_step`·`student_intent`·
   `student_understanding_signal` 3종, `socratic_strategy`는 값 공간 확정 후)을 채움(stateless
   `/v1/coach`는 DB 무접근 계약 유지) + 실 PG 통합에서 NULL 잔존 0 검증.
2. `select_category`가 `recent_categories` 3연속 시 회전 — 결정론 재현 테스트 + 발화신호
   오버라이드 우선순위 불변 회귀.
3. `recall_session_context`가 **암호화 본문 미복호**를 테스트로 동결(복호 함수 호출 0 assert) +
   `wh1_llm_policy` 프롬프트에 학생 원문 0(기존 사적 필드 테스트 확장) + 예산 초과 시
   `context_truncated` fail-closed.

**의존**: 없음(즉시 착수 가능). **`PED-03` 승격의 잠금 해제 조건**. **태스크**: 신설.

### D2. Polya 상태 서버 소유 — 세션 경로 한정 (백로그 `PED-04` 동일 슬라이스)

**문제**: `polya_state`·`turn_count`·`prev_hint_level`을 **클라이언트가 매 턴 실어보낸다**. S3
파일럿 KPI(전환 지표·도달 깊이·막힘 턴)가 이 값에 의존하므로 측정이 클라 버그·조작에 열려
있다. 지금 상환할 이유는 "클라 신뢰"가 아니라 **파일럿 측정의 신뢰**다.

**정합 설계**
- **세션 경로만** 서버 파생: `turn_count`는 이미 서버 소유(`dialogue.total_turns`) → 클라 값
  무시. `polya_state`는 D1이 적재하는 `targeted_step`·직전 턴 메타에서 **파생**(신규 컬럼 0).
  `prev_hint_level`은 `attempt_event(힌트제공)` 직전 행에서 조회.
- **stateless `POST /v1/coach`는 클라 제출 유지** — DB 무접근 계약·데모·테스트 경로 파괴 금지.
- 불일치 시 **서버 우선 + `client_state_mismatch` 응답 플래그 + 구조화 로그**(침묵 실패 금지).

**dead code 금지**: 신규 스키마 0. **측정**: `client_state_mismatch` 발생률을 harness-metrics에
계상.
**acceptance**: ① 세션 경로에서 클라 거짓 `polya_state` 제출 시 서버 파생값으로 결정 + 플래그
노출 ② stateless 경로 계약 무변경 회귀 ③ `turn_count` 이중 소유 제거(클라 필드 deprecated
표기·제거는 별도 클라 릴리즈).

### D3. `LearnerState` v0 실체화 — 생산자 실재 필드만 (백로그 `PED-05`)

**문제**: `02_learner_model.md`가 "L2가 L3/L4에 주입하는 단일 요약 상태"로 규정한 클래스가
없어 소비처마다 조각을 직접 조회한다. 그 결과 개인화 슬롯(학년·성취기준)이 **주입 경로 자체가
없어** 미착지다.

**핵심 판단**: 41의 근원은 절반만 D3다 — grade·goals·standard_code는 주입 경로 부재가 원인이라
D3가 원천이고, "이전 설명 성공 여부"는 D1이 원천이며, "학습스타일"은 §2-⑦로 영구 불채택이다.
→ **D3는 "개인화 주입 seam", D1은 "교수 기억 seam"** 으로 분리 유지한다.

**정합 설계**
- `l2/learner_state.py`에 `LearnerState` **v0 = 생산자 실재 필드만**: `student_id`·`timestamp`·
  `mastery`·`general_ability`(θ)·`domain_abilities`·`active_misconceptions`·`recent_struggles`·
  `recent_successes`·`grade`·`curriculum`·`goals`(target_* 사본).
  **제외 필드와 사유를 클래스 docstring에 명시**: `affect`(생산자 0 → D4/D6), `mastery_states`
  (`MasteryState` 자체가 스케치), `active_textbook_id`·`shadow_curriculum_progress`(L1 좌석
  실재하나 L4 소비처 0). → `runtime_selector.py:96-112` 결정의 **이행**(충돌 아님).
- **조립기**: `L2LearnerService.get_state()` — 기존 좌석 재사용만. 신규 계산 0.
- **소비처 전환 2곳**: `api/coach.py`(현 mastery+θ 따로 조회 → 1회 조립), `api/study.py`.
- **개인화 착지 2종만**: `prompt_assembler`의 학습자 상태 계층에 `grade` 라벨(중3/고1/고2/고3
  — 학교·지역·이름 등 준식별자 금지) + `standard_code` 추가. `{textbook}`·`{affect}`는 이번에
  열지 않는다. `docs/prompts/socratic_template.md`의 미착지 슬롯을 실측에 맞게 개정.
- **PII 경계**: `goals`(목표 등급·D-day)는 D5의 API 응답용이고 LLM 프롬프트로는 보내지 않는다
  (압박 발화 유발 회피·§2-⑧).

**dead code 금지**: 신규 테이블·컬럼 0. 클래스 신설이지만 동일 슬라이스에 소비처 2곳 전환.
**측정**: grade 주입 전/후 발화의 `pedagogical_rubric.py` 점수 비교 + 조립기 호출 1회화의 쿼리 수
감소 실측(N+1 제거).

**acceptance 후보**
1. `LearnerState` v0 + `get_state()` + `api/coach.py`·`api/study.py`가 조각 직접 조회를 버리고
   조립기 경유(직접 조회 잔존 0 테스트) + 제외 필드 사유 docstring·`02_learner_model.md` v0
   축소 개정.
2. `prompt_assembler`에 grade·standard_code 착지 + 프롬프트에 학교·지역·이름·목표점수 0을
   테스트로 가드 + `socratic_template.md` 슬롯 실측 정합.
3. 예산 회귀: 주입 증가분이 `_MAX_PROMPT_TOKENS=3000` 안 + `pedagogical_rubric` 점수 비퇴행.

**의존**: 없음(D1과 병행 가능). **태스크**: 신설.

### D4. 행동 텔레메트리 writer — 휴면 EventType 소생 (백로그 `S3-16`)

**문제**: 정서·몰입의 정본 입력 7종 중 코드가 관측하는 것은 0에 가깝다. `learning_session`은
행 자체가 없고, `focus_score`/`engagement_score`는 항상 NULL, KPI3 = `NO_DATA`.

**핵심 판단**: **분류기(AffectState 5분류)는 만들지 않는다. 생산자만 만든다.**
`runtime_selector.py:96-112`의 결정("생산자를 먼저 만들고 그때 필드를 연다")과 충돌 없이
이행. 파일럿 잠금 대상이 아니다 — 오히려 파일럿 *개시 전*에 깔아야 KPI3가 NO_DATA를 벗는다.

**정합 설계**
- 착지점은 `learning_session`이 아니라 **`attempt_event` hypertable**(live writer·
  `EVENT_DATA_CONTRACT` 단일 진실원). `focus_score`/`engagement_score`는 **계속 NULL로 둔다**
  (단일 스칼라 압축은 정본 5분류와 축이 안 맞아 해석 불가).
- 휴면 EventType 중 **서버가 이미 아는 것만** 3종 생산: `힌트요청`(demand — `decide_hint_level`
  답요구 토큰 검출 시. 기존 `힌트제공`(supply)과 쌍을 이뤄 supply/demand 비 산출), `막힘`
  (`stuck_turns` 임계 도달 시), `답입력`+`event_data.server_latency_ms`(서버 수신 시각 차 — 클라
  신뢰 불필요).
- `지움`(수정 횟수)·rage quit·스킵률은 클라 계약 필요해 유보(§4-⑥). 세션 지속시간은 턴 간격
  근사로만.
- 신규 EventType enum **0**(휴면 3종 소생) + `EVENT_DATA_CONTRACT`에 3종 페이로드 등재.

**dead code 금지**: 신규 테이블·컬럼·enum 0. **reader 동반**: `pilot_kpi_baseline.py` KPI3를
`NO_DATA`→`MEASURED` + `GET /v1/me/harness-metrics`에 supply/demand 비 노출.
**측정**: 이 태스크 자체가 측정 기반 구축이고 학생 대면 행동 변화 0(적재만).
**미성년자 경계**: 적재는 행동 메타뿐(원문 0)·`ConsentedUser` 게이트 기존 경로.

**acceptance 후보**
1. `힌트요청`·`막힘`·`답입력(server_latency_ms)` 3종이 세션 경로에서 적재 + `EVENT_DATA_CONTRACT`
   편입 + 신호 부재 시 행 미생성(날조 회피).
2. `pilot_kpi_baseline` KPI3가 NO_DATA를 벗고 집계 산출 + supply/demand 비 리포트 + 학생 대면
   응답 무변경 회귀.
3. `focus_score`/`engagement_score`·`learning_session` writer **미신설을 결정으로 명시**(코드
   주석·문서 기록·NULL 유지 동결 테스트).

**의존**: 없음. **S3-01 잠금 아님 — 오히려 선행 권장**. **태스크**: 신설.

### D5. 코칭 시간축·목표축 — 망각 역산 복습 큐 + D-day 컨텍스트 (백로그 `S4-18`)

**문제**: "무엇을 복습할지"(강도축)는 답하는데 **"언제"**가 없다. `target_*` 컬럼은 reader 0.

**정합 설계 — 신규 컬럼 0의 순수 파생**
- `concept_mastery_history`(live writer)의 `MAX(measured_at)` per concept + `bkt.apply_forgetting
  (mastery, elapsed_days, params)`를 **조회 시점에 적용** → `decayed_mastery`·`days_since_practice`·
  `due_rank`. **`next_review_at` 컬럼을 만들지 않는다**(파생값 영속화는 dead column + 이중
  진실원천).
- **reader 2곳**: `GET /v1/me/review-queue` 신설(due_rank 정렬) + 기존 `GET /me/weak-concepts`
  응답에 `days_since_practice`·`decayed_mastery` 필드 추가. 순서는 `learning_path`(위상정렬)
  재사용.
- **목표축 최소형**: `target_exam_date` → D-day, `target_grade`/`target_score` → **목표 성취기준
  커버리지 %**(점수 예측 없음·§2-⑧). "이번주 목표"는 due 개념 수 상한으로만.
- **하지 않는 것**: 학습계획 엔티티(`study_plan` 테이블)·시즌 플랜(FR-010)·dead table 5종 소생.

**dead code 금지**: 신규 테이블·컬럼·마이그레이션 0. 순수 계산 + 기존 컬럼 첫 reader.
**측정**: `p_forget` 파라미터 타당성은 실학생 재방문 데이터 필요 → 응답에 `decay_model=
'bkt_p_forget'`·`calibrated=false` 정직 표기(파라미터 튜닝은 §5-⑧).

**acceptance 후보**
1. `GET /v1/me/review-queue`가 파생으로 due 정렬 반환 + 신규 컬럼·마이그레이션 0 확인 + 관측
   이력 없는 개념은 due 산출 제외.
2. `target_exam_date`/`target_grade`의 첫 reader — D-day + 목표 성취기준 커버리지 %. 점수·등급
   예측 필드 부재를 테스트로 동결.
3. `calibrated=false`·`decay_model` 정직 신호 + 정렬 결정론 재현 + user_id 스코핑.

**의존**: 없음(D3 착지 시 `goals`를 조립기에서 받으면 코드가 얇아지므로 D3 후행 권장). **태스크**: 신설.

### D6. 정서·몰입 추정 페이퍼 설계 (코드 0 · 태스크 신설 없음)

`knowledge_module_gap_review.md D2`·`solution_module_gap_review.md D5` 선례 동형 — 설계만 확정.

- **입력 정합 표**: 정본 7종 ↔ D4 착지 3종 ↔ 미관측 4종(rage quit·스킵률·수정횟수·세션 지속) —
  각 미관측 항목의 필요 계약(L5 클라 이벤트 / `learning_session` writer) 기록.
- **분류기 형태 예판**: 5분류(FLOW/FRUSTRATED/BORED/OVERWHELMED/AT_RISK)는 **LLM 추론 금지·순수
  결정론 임계 규칙**(`decide_hint_level`·`select_category` 형제 관례). `AffectState`는 분류기
  (생산자)가 먼저 서야 `LearnerState`에 필드로 연다(D3 제외 사유와 정합).
- **소비 경계**: 학생 대면 감정 라벨 발화 금지(§2-②). 소비처는 ⑴ 개입 금지 타이머 정서 가드레일
  해제 조건 ⑵ 난이도 조정(BORED↑/OVERWHELMED↓) ⑶ AT_RISK 시 **사람 에스컬레이션**(자동 개입
  아님) 3곳만.
- **미성년자 경계**: 정서 추정치는 학생 프로필에 영속하지 않고 세션 스코프 파생으로 둘 것을
  예판(낙인·프로파일링 회피). 영속 필요 시 별도 동의 축 검토(**확인 필요** — 현 동의 문구가
  정서 추정을 포함하는지 미확인).
- **구현 트리거**: §5-③.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (9종)

1. **WH-1 전략 계층 §11 전체**(`strategy_nodes`·`strategy_evidence`·도구 #9 `log_strategy_event`)
   — ⑴ 전략 사용은 verify로 검증 불가(정본 스스로 confidence 상한 0.7) ⑵ `db/models/strategy_node.py`
   가 이미 다른 축(L1 전략그래프 투영)으로 이름 점유 ⑶ 증거 다수가 실학생 로그 의존.
2. **힌트 경제·개입 금지 타이머·페이딩 3→2→1→0**(`04a:452-468`) — `solution_module_gap_review.md
   §4-①` 승계(중복 등재 금지).
3. **`AffectState` 5분류 분류기** — D6 페이퍼만.
4. **스트리밍(SSE/WS)·fast path** — 현 학생 대면 발화는 결정론 정적 템플릿(LLM rephrase 기본
   OFF)이라 지연이 짧고, 파일럿 규모(5~10명)에서 사용자·측정 가치 0.
5. **PRD FR-010 1년 사이클·FR-014 내신+수능 통합 진도·FR-020 D-100 멘탈 코칭** — 실학생 진도·성적
   데이터 0이고 콘텐츠·운영 자산 성격. D5가 D-day·커버리지 최소 발판만 놓는다.
6. **`지움`(수정 횟수)·rage quit·스킵률** — L5 클라 입력 계약 필요(`S3-05` 축과 함께 판정).
7. **dead table 5종** — 되살리지 않고 새로 만들지도 않는다. `attempt_event`가 시계열 단일 원천.
8. **도구 #10 `elicit_prediction` UI 유발**(측정·코칭은 `calibration_coaching.py:32`에 실재) ·
   **#11 `assign_transfer_probe`**(`GET /me/next-problem` IRT CAT·`S4-15` 축과 중복 → 승계).
9. **Redis 세션 작업메모리·`run_persisted_turn` HTTP 배선** — `04a:651`의 의도적 미배선 유지
   (배선 시 이중 curate·단일진실원천 붕괴). **소크라테스 카탈로그 50+ 심화**·**PRM 단계 스코어러**
   (`solution_module_gap_review.md §4-②` 승계)·**Minimal Reasoning Subgraph**(`ARCH-11` blocked)도
   이 축.

## §5. 유보 항목의 발화 조건

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | WH-1 전략 계층·도구 #9 | 파일럿에서 "동일 오개념 교정 성공 후에도 낯선 표면 문제 실패"가 실관측 + D1 턴 메타 축적으로 전략 태깅 대상 이력이 생길 때 |
| ② | 힌트 경제·페이딩 | D3(힌트 내용 생성·`S4-11`) 착지 + `S3-01`에서 도달 깊이·supply/demand 비 분포 실측(D4가 계기판) |
| ③ | `AffectState` 분류기 | D4 신호가 파일럿 코호트 세션 N건 이상 축적 + 최소 2개 라벨의 근거 사건 실관측 + 동의 문구가 정서 추정 포괄 확인 |
| ④ | 스트리밍·fast path | `S4-04` LLM rephrase 또는 primary 발화 ON 승격 + p95 지연이 체감 임계 초과 실측 |
| ⑤ | ~~학습계획 엔티티·시즌 플랜(FR-010)~~ → **시즌 플랜은 발화됨** (2026-07-30 Kiki 결정) | 시즌 플랜은 `PATH-04`·`PATH-05`로 착수(`learning_path_module_gap_review.md` D7·D8). 여기 적었던 "진도 데이터 원천 확보" 조건은 **오판정이었다** — 고3 대입 축은 수능 범위(성취기준 과목)로 정의되어 교과서 진도와 무관하다(문항 2,647건 전건이 성취기준 코드 보유). 계속 유보되는 것은 `study_plan` **엔티티**(파생 구현이므로 불필요)와 **주간·일일 단위 쪼개기**(수요 미관측)뿐 |
| ⑥ | 대화 원문 회상 | 영구 불채택(§2-⑤). 교사·연구 감사 경로는 별도 축(L7·복호 권한 분리)으로 재론 |
| ⑦ | `MasteryState` 두꺼운 상세 | 어댑티브 출제 또는 선호 풀이 스타일 추적이 실소비처로 설 때(`solution_module_gap_review.md §4-⑤` 승계) |
| ⑧ | `p_forget` 파라미터 보정 | 파일럿에서 재방문 정답률 vs 공백 일수 곡선이 유의미하게 관측될 때(그때까지 `calibrated=false` 유지) |
| ⑨ | dead table 소생 | 소생하지 않는다. 시계열 집계 요구 시 `attempt_event` 위 뷰·ClickHouse 축으로 신설 판정 |

---

## 부록 — 실측 근거 (2026-07-29 재확인)

- `db/models/dialogue.py:181-192` — `DialogueTurn` 메타 4컬럼(`socratic_strategy`·`targeted_step`·
  `student_intent`·`student_understanding_signal`) 스키마 실재, `api/`·`l4/` 참조 0(writer 0) 확인.
- `schema/enums.py:918-943` — `SocraticStrategy`(6종, 교수 전략) ≠ `l4/socratic/categories.py:17-35`
  `SocraticCategory`(6종, 질문 유형) — **서로 다른 enum 공간**임을 재확인(D1 설계 정정 근거).
  `StudentIntent`(5종: 답시도/질문/막힘표현/포기/이해확인) 실재.
- `schema/enums.py:832-867` — `EventType` 11종 중 3종만 생산(검산결과·힌트제공·시각화조작), 8종
  휴면 자인. `api/coach.py:962` — `힌트제공`(supply)과 `힌트요청`(demand)이 다른 신호임을 코드가
  명시.
- `l4/misconception/catalog.py` — `Misconception(` 64건(grep 실측, 이전 보고된 "30종"은 stale).
  `probes_v1.jsonl` — 162건(JSONL 라인 파싱 확인).
- `l4/pedagogy/runtime_selector.py:96-112` — 정서·집중도·선호 3신호 미생산 자인 원문.
- `db/models/user.py:99,107-110` — `target_universities`·`target_grade`·`target_score`·
  `target_exam_date` 컬럼 실재.
- `config.py:168` — `wh1_primary_enabled` 기본 True(2026-07-20 GA).
