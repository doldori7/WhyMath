# 평가(Assessment) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03)

> **범위**: 외부 참고 문서 『1단계: 평가(Assessment)』(모듈 49~53: 진단평가 생성 · 형성평가 생성 ·
> 총괄평가 생성 · 수행평가 관리 · AI 평가 문항 생성 + 확장 제안 54~58: 자동 채점 엔진 · 평가 결과
> 분석 · 문항 통계 관리 · 오답·오개념 분석 · 맞춤형 재평가 생성 — **WhyMath 전용이 아닌 일반적인
> EOS(Education Operating System) 틀**, Kiki 제공 docx)을 현 코드베이스와 대조해 빠진 부분을
> 점검하고, 진짜 갭을 WhyMath 불변식(Concept Purity·AI Context Slimming·정답을 빠르게 KPI 금지·
> 정답률 게임화 금지·LLM 응답 검증 없이 제공 금지·측정 없는 도입 없음) 안에서 설계한 기록.
> **형식**: `curriculum_module_gap_review.md`(같은 EOS 틀 시리즈, 2026-08-03) 답습 — 시리즈
> **12번째** 자매편(1.knowledge → 2.problem_bank → 3.ai_tutor → 4.solution → 5.operations →
> 6.account_security → 7.ai_content_generation → 8.visualization → 9.nlp → 10.ai_recommendation →
> 11.curriculum → **12.assessment**).
> **결론**: 착수 가설("평가가 거의 없다")은 **반증**된다 — 진단(IRT CAT+BKT 융합)·형성평가(3상태
> 검증·코칭)·AI 문항 생성+QA는 오히려 **초과 충족**이다. 진짜 그림은 정반대다: **평가 결과를
> 영속화하는 좌석(`assessment` 테이블 4종)이 스키마·API·프라이버시 배선까지 완비된 채로 writer가
> 0건**이라는, 이 시리즈에서 가장 완성도 높은 "완비된 소비 경로 + 미도달 공급원" 8회차 사례다(D1).
> 여기에 등급·백분위·합격예측 컬럼과 CLAUDE.md 게임화 금기가 정면으로 긴장하는데 그 긴장이 이제껏
> 어디에도 기록된 적이 없다(D2, Kiki 결정 필요). 총괄평가·수행평가는 콘텐츠 공급·PRM 실모델
> 부재로 **정직한 공백**이다. 진짜 갭 2건(D1·D2, `D2`는 owner=kiki)을 설계하고 페이퍼 갭 1건을
> 남겼다. 태스크 2건을 백로그에 등재했다(`ASM-01`·`ASM-02`). 의도적 미채택 8건 · 정직한 공백 7종 ·
> 유보 발화조건 6건. 정본 stale 2곳을 정정한다.

관련 정본: `02_learner_model.md`(BKT→IRT→DKT 단계 도입·`MasteryState` v0 축소) ·
`04b_misconception_judge_graduation.md`·`04c_misconception_seven_stage_separation.md`(오개념
reactive retrieval) · `problem_bank_gap_review.md`(기능 19~22, IRT·문항 통계 선례) ·
`ai_recommendation_module_gap_review.md`(§D1 θ=0 고정·§D4 목적 분리 — 같은 축, 승계) ·
`nlp_module_gap_review.md`(§D2 클라 채점 권위 — 같은 축, 승계) · `solution_module_gap_review.md`
(§2 점수·서술형 채점 불채택 — 승계) · `curriculum_module_gap_review.md`(시리즈 직전편·문서 골격
원본) · `docs/data/licensing_safety.md`(평가원·EBS 본문 금지) · `MEMORY.md` 결정 로그.

---

## §0. 두 가지 전제 정리

### ① 착수 가설이 정반대로 뒤집혔다 — "평가가 없다"가 아니라 "평가 분석은 초과·평가 영속은 죽음"

이 대조는 "WhyMath에 평가 기능이 빈약하다"는 가설로 시작했다. 실측 결과는 그 반대에 가깝다.
외부 틀이 요구하는 다섯 축 중 **셋(진단·형성·AI 문항 생성)은 이미 이 시리즈에서 가장 성숙한
축들**이다:

- **진단**: `l2/irt.py`의 2PL 골격(1PL 가동)·JMLE·Fisher 정보량 최대 CAT(`api/me.py:1675`
  `GET /v1/me/next-problem`)·BKT↔IRT 교차검증(`l2/concept_diagnosis.py`)이 테스트 100건+로
  완비돼 있다.
- **형성평가/즉시 피드백**: 3상태(pass/fail/unverifiable) 스텝·풀이·답 검증(`api/verify.py`,
  테스트 223건)이 완비돼 있다.
- **AI 문항 생성**: 생성 오케스트레이터(`l3/equivalent/orchestrator.py`) + QA 6축(정답·중복·
  난이도·수식·환각·저작권 검증) + `ARCH-21` 7축 단일 판정 파이프라인까지 CI에 배선돼 있다 — 이
  시리즈 전체를 통틀어 **가장 완성도 높은 개별 축**이다.

그런데 **정작 "평가"라는 이름이 붙은 유일한 테이블(`assessment`)은 텅 비어 있다.** 스키마·ORM·
5개 진단 산출물 JSONB(`concept_diagnosis`·`pattern_diagnosis`·`weak_points`·`strong_points`·
`recommended_path`)·조회/완료/삭제 API·프라이버시 내보내기/파기 배선까지 전부 있는데, **그 행을
만드는 코드가 `src/` 전체에 0건**이다(§부록). 즉 문제는 "평가 엔진이 없다"가 아니라 **"평가
엔진의 산출물이 영속되는 좌석과, 그 좌석을 실제로 쓰는 파이프라인이 끊겨 있다"**이다.

### ② 틀의 아키텍처와 정본의 차이 (갭 판정의 전제)

외부 틀은 평가를 **생성 중심 파이프라인**으로 그린다:

```
교육과정 → 성취기준 → 개념 그래프 → 문제은행 → 평가 생성 엔진 → 자동 채점 → 학습 분석 → AI Tutor 피드백
```

WhyMath 정본은 이 화살표의 **뒤쪽 절반(학습 분석)을 앞쪽 절반(평가 생성)보다 먼저** 만들었다.
BKT·IRT·오개념 카탈로그(L2)가 먼저 성숙했고, 그 결과를 소비하는 "평가 세션"이라는 1급 엔티티는
나중으로 미뤄졌다. 그래서 겉보기엔 "평가 모듈이 없다"처럼 읽히지만, 실제로는:

| 틀이 평가에 요구하는 순서 | WhyMath 현행 순서 |
|---|---|
| 평가 생성 → 시행 → 채점 → **그 결과로** 학습 분석 | 학습 분석(BKT·IRT·오개념)이 **먼저 완성**, 그 분석 엔진이 만드는 산출물을 담을 "평가" 그릇만 비어 있음 |
| "평가"는 채점 가능한 **문항 묶음 + 세션**(시작·종료·시간) | 문항은 개별 단위로만 존재(`Problem`), 세션 개념은 있으나(`learning_session`) writer 0, "평가 묶음"은 `assessment` row 1개 = 진단 결과 스냅샷일 뿐 시험지 개념이 아님 |
| 채점 = 평가 파이프라인의 필수 중간 단계 | 채점 권위가 **클라이언트**에 있다(`is_correct` 클라 보고) — 이미 `NLP-02`가 이 축을 소유 |
| 점수·등급·백분위가 평가의 **자연스러운 출력** | CLAUDE.md 교수학 금기(정답률 게임화 금지)와 정면 긴장 — 어디에도 기록된 적 없음(D2) |

**따라서 이 문서는 "평가 생성 엔진이 없다"를 갭으로 세지 않는다.** 그건 오히려 초과 충족이다.
갭은 **분석 엔진의 산출물이 영속·소비되는 지점**(D1)과 **점수 노출이라는 틀의 당연한 전제가
WhyMath 금기와 부딪히는데 그 충돌이 침묵당한 지점**(D2)에서만 성립한다.

---

## §1. 모듈 49~58 전수 대조

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·데이터* 없음) / ⚠️ 진짜 갭 → D /
🚫 의도적 미채택 → §2

### 모듈 49 — 진단평가 생성 (목적: 선수학습확인·오개념탐지·학습수준분류·맞춤경로 / 결과: 숙달도·약점개념·오개념목록·추천학습순서)

| 필요 요소 | WhyMath 현행 | 판정 |
|---|---|---|
| 선수학습 확인 | `l2/prerequisite_recommendation.py` + `/me/weak-concepts/{id}/prerequisites`(위상정렬) | ✅ |
| 학습 수준 분류 | IRT θ + BKT 융합(`l2/concept_diagnosis.py:71` `compute_concept_diagnoses` — agree/irt_higher/bkt_higher/insufficient 4상태) | ✅ |
| 개인 맞춤 학습경로 | `/me/weak-concepts/{id}/learning-path`(`l2/learning_path.py`) | ✅ |
| 문항 선택(랜덤 아님) | IRT CAT — θ 근방 후보 50개(`_CANDIDATE_POOL_SIZE`) → Fisher 정보량 최대(`select_weighted_item`, `l2/irt.py:236`) + SE 중단 규칙(`_TARGET_SE=0.3`) | ✅ |
| 개념 숙달도(결과) | `concept_mastery_history`(`db/models/assessment.py:169` 테이블) — writer `l2/mastery_tracking.py` 실재 | ✅ |
| 약점 개념(결과) | `/me/weak-concepts`(`api/me.py:1323`) | ✅ |
| **오개념 목록(결과)** | `compute_concept_diagnoses`는 BKT·IRT 수치만 산출 — **오개념은 진단 산출물에 포함되지 않는다**. 오개념은 `misconception_hypothesis`(코치 **대화** 턴에서만 갱신, `api/coach.py`)에 별도로 존재하며 채점 결과와 연결 안 됨 | ⚠️ → **D1** |
| 추천 학습순서(결과) | `recommended_path` JSONB 컬럼(`db/models/assessment.py:121`) — **컬럼은 있으나 채우는 코드 0** (learning_path API 결과가 이 컬럼에 영속되지 않음) | ⚠️ → **D1** |
| 평가 생성 기준(교육과정·학년·단원·성취기준·개념·난이도) | `AchievementStandard`↔`Concept` 링크(443건)로 간접 가능하나, 진단 세션이 "이 성취기준들을 이 기준으로 진단했다"를 기록하는 좌석(`assessment` 테이블) 자체가 writer 0 | ⚠️ → **D1** |

**모듈 49 종합**: 진단 **엔진**은 초과 충족, 진단 **결과의 영속·오개념 통합**이 D1의 핵심.

### 모듈 50 — 형성평가 생성 (특징: 짧은문제·즉시채점·즉시피드백·반복학습 / 피드백: 오답→오개념발견→설명제공→유사문제제공)

| 필요 요소 | WhyMath 현행 | 판정 |
|---|---|---|
| 즉시 피드백(설명 제공) | `POST /v1/coach`·`/coach/sessions/*`(정적 결정론 템플릿, LLM 발화 0 — S1 게이트③) | ✅ |
| 유사문제 제공 | `/me/next-problem`(IRT CAT 재추천) | ✅ |
| 반복 학습 | 코치 세션 다회 턴 + `attempt_event` 힌트 이벤트 적재 | ✅ |
| **즉시 채점(오답 발견)** | `is_correct`는 **클라이언트 보고**(`api/me.py:585-589` 자인) — 서버 검산기(`l3/verify_answer.py`, 82KB·테스트 92건)는 실재하나 attempt 경로에 연결 안 됨 | 🚫 §2 승계(`NLP-02` 소유) |
| **오답→오개념 발견 연결** | `misconception_hypothesis` 갱신은 **코치 대화 턴에서만** 일어난다(`api/coach.py`) — `POST /v1/me/attempts`(채점) 경로에는 오개념 갱신이 없다. 채점과 오개념 진단이 **두 개의 다른 파이프라인**으로 분리돼 있다 | 🚫 §2 승계(`NLP-02` 종속 결과 — 채점 권위 이관 후에만 의미 있음) |
| 개념별·난이도별·유형별 생성 | 생성 파이프라인(`l3/equivalent/*`)이 개념·난이도 태그 부여 | ✅ |
| AI Tutor / 자기주도 활용 | `wh1_primary` GA 3중 게이트 | ✅ |
| 교사용 수업 활용 | 교사 대시보드 자체가 Phase 3(L7) | 🚫 §2(로드맵 시점) |

**모듈 50 종합**: 서버 검증 인프라는 완비, 클라 도달·채점 권위·오개념 연결의 3중 단절은 **이미
`NLP-02`가 소유한 축**이라 이 문서는 신규 태스크를 만들지 않는다(§3 등재요약에 승계 명시).

### 모듈 51 — 총괄평가 생성 (대상: 단원평가·중간고사·기말고사·모의고사 / 구성: 객관식·단답·서술·논술 / 기준: 성취기준반영·난이도비율·유형비율·배점관리·시험시간 / 분석: 평균·표준편차·문항별정답률·성취도등급·교육과정달성률)

| 필요 요소 | WhyMath 현행 | 판정 |
|---|---|---|
| 단원평가·모의고사(엔티티) | `AssessmentType.단원진단`·`실전모의고사`(`schema/enums.py:965-966`) — **enum 선언만, 소비 코드 0건** | ⚠️(D1에 포함) |
| 시험지 조립(문항 묶음) | 전수 grep 0건. `learning_session`(writer 0)도 "시험" 단위가 아니라 학습 세션 단위 | 🚫 §4 정직한 공백 |
| 배점 관리 | `Problem.points`(`schema/problem.py:258`) 컬럼 존재 — **코퍼스 2,647건 전량 NULL** | 🚫 §4 |
| 시험 시간 | `time_limit`류 컬럼 0건 | 🚫 §4 |
| 난이도·유형 비율 통제 | 조립 로직 0건(개별 CAT 추천만 존재, "시험지 단위" 비율 개념 없음) | 🚫 §4 |
| 문항별 정답률·표준편차 분석 | `Problem.historical_correct_rate`(`db/models/problem.py:202`) 컬럼 존재 — **writer 0건**. ARCH-21 QA 파이프라인이 `statistical_outlier` 축을 **"코드 미구현(실측)"으로 이미 자인**(`harness/qa_pipeline.py:145`) | 🚫 §4 |
| 성취도 등급·교육과정 달성률 | `estimated_grade`(`db/models/assessment.py:98`) 컬럼 존재 — writer 0(D1) + 노출 여부는 D2 | ⚠️(D1·D2에 걸침) |

**모듈 51 종합**: **완전 부재.** 컬럼(배점·정답률·등급)은 산재해 있으나 전부 NULL/writer 0이고,
"시험지"라는 1급 엔티티 자체가 없다. 콘텐츠 공급 상한(코퍼스 2,647건, 초·중 단원 커버리지 0 —
`problem_bank_gap_review.md`)과 저작권 제약(평가원 기출 본문 조립 불가)이 겹쳐 지금 만들면
"입력 없는 파이프라인"이 된다. §4 정직한 공백으로 남긴다.

### 모듈 52 — 수행평가 관리 (유형: 프로젝트·탐구·발표·포트폴리오·보고서 / 요소: 창의성·문제해결력·논리성·협업·표현력 / 루브릭 관리 / 제출 관리: 파일·이미지·동영상·PDF·링크 / AI 지원: 초안피드백·표절검사연계·문장개선제안·루브릭기반평가보조)

| 필요 요소 | WhyMath 현행 | 판정 |
|---|---|---|
| 프로젝트·탐구·발표·포트폴리오·보고서 | 전수 검색 **0건**("수행평가" 자체가 저장소 전체에 등장한 적 없음) | 🚫 §4 정직한 공백 |
| 루브릭 관리 | `ScoringType.루브릭`·`ProblemType.PF 수행형`(`schema/enums.py:240-241,134,169`) enum만 존재. 유일 소비처 `l6/metacognition/gating.py:117,160`은 노출 가중치 신호일 뿐 채점 로직이 아니며, 코퍼스에 값이 없어 **런타임에 항상 거짓인 죽은 분기** | 🚫 §4 |
| 제출 관리(파일·이미지·동영상·PDF·링크) | 0건 | 🚫 §4 |
| AI 지원(초안피드백·문장개선) | `harness/pedagogical_rubric.py`는 **AI 튜터 발화 품질 자체평가용**이지 학생 산출물 채점용이 아님(`harness/prompt_asset_audit.py:3-5` 명시) | 🚫 §4 |
| 표절 검사 연계 | 0건. 학교 제출 인프라 연동은 개인 학습 앱 스코프 밖 | 🚫 §2-⑧(영구) |

**모듈 52 종합**: **완전 공백.** 서술형 채점이 PRM 실모델 부재(`whs/prm_builder.py`는 데이터셋
빌더만, `src/ml-models/`는 README뿐)로 막혀 있어, 루브릭 채점의 전제 조건 자체가 없다. §4·§5에서
정직한 공백 + 발화 조건으로 다룬다(태스크 신설 없음).

### 모듈 53 — AI 평가 문항 생성 (입력: 교육과정→성취기준→개념→난이도→문항수 / 생성유형: 객관식·단답·서술·증명·계산·실생활 / 옵션: 쉬움~경시형 / 결과: 문제·정답·해설·오답·오개념·힌트·관련개념 / 품질검증: 교육과정일치·정답검증·중복검사·난이도검증·수식검증·환각검사)

| 필요 요소 | WhyMath 현행 | 판정 |
|---|---|---|
| 객관식·단답·계산형·실생활 생성 | `l3/equivalent/*generator.py` 12종(스켈레톤·LLM·오개념MC·계산 등) | ✅ |
| 서술·증명형 생성 | 생성은 가능하나 **채점 불가**(PRM 부재) — 생성-검증 비대칭 | △ (§2 승계, `nlp §2-③`) |
| 정답 검증 | `l3/equivalent/acceptance.py:263` Tier1+Tier2 결합·근 선택·근합/곱 검증 | ✅ |
| 중복 검사 | 구조(`canonicalize.py` SymPy 정규형) + 임베딩(코사인 0.97) 이중 | ✅ |
| 난이도 검증 | `l3/equivalent/difficulty.py`(규칙기반) + `acceptance.py:437` 가중 게이트 | ✅ |
| 수식 검증 | `canonicalize.py:condition_dsl_violation`(조건 DSL 폐쇄성) | ✅ |
| 환각 검사 | `l3/pregenerate/validator.py` + `l3/cross_verify.py`(K≥3 독립 다관점, `_assert_independent` 기계 강제) | ✅ |
| 저작권 검증 | `acceptance.py:235` `_evaluate_copyright` + `ops/provenance_audit.py` | ✅ |
| 전체 오케스트레이션 | `ARCH-21` 7축 단일 판정(`harness/qa_pipeline.py`), CI 배선(`ci.yml:178`, 코퍼스 변경 시 트리거) | ✅ |
| 관련 개념 태그 | `ProblemConcept` 매핑 | ✅ |
| 오개념(선지) 태그 | `distractor_map`(1,536건) — **채점과 미연결**(D는 `NLP-02` 승계) | 🚫 §2 승계 |

**모듈 53 종합**: **초과 충족.** 이 시리즈 전체를 통틀어 가장 성숙한 축이며, 이번 문서는 여기서
어떤 신규 갭도 세우지 않는다. 유일한 주의점(`_axis_corpus_audit` 기본 임계=off·`statistical_outlier`
미구현)은 이미 `qa_pipeline.py` 자신이 `_NOT_MEASURED_AXES`로 자인하고 있어 침묵 실패가 아니다.

### (확장 제안) 모듈 54~58 대조

| # | 확장 제안 | WhyMath 현행 | 판정 |
|---|---|---|---|
| 54 | 자동 채점 엔진 | 검산기(`verify_answer`)는 완비, attempt 경로 미연결 | 🚫 §2 승계(`NLP-02`) |
| 55 | 평가 결과 분석 | `assessment` 4테이블(진단·숙달·능력 이력) 스키마 완비, writer 0 | ⚠️ → **D1**(모듈 49와 동일 좌석) |
| 56 | 문항 통계 관리 | IRT 2PL·JMLE·변별도(`discrimination_D`)·정답률(`historical_correct_rate`) 컬럼 존재, **writer 전량 0** — 이미 `S4-15-response-driven-difficulty-loop`가 실응답 축적 후 갱신 루프로 소유(`S3-01-pilot-cohort`에 잠김) | 🚫 §2 승계(`S4-15`, **재설계 금지**) |
| 57 | 오답·오개념 분석 | `distractor_map` 선지별 통계는 QA 생성 단계에만 있고, **학생 채점 결과 기반 오답 분석은 0**(채점 권위가 클라라 서버가 오답 패턴을 볼 수 없음) | 🚫 §2 승계(`NLP-02` 선결 조건) |
| 58 | 맞춤형 재평가 생성 | IRT CAT(`/me/next-problem`)이 매 요청마다 θ 재추정 후 재선택 — **"재평가 세션"이라는 별도 개념이 CAT과 별개로 필요한 근거가 없다** | 🚫 §2-⑦(영구) |

**확장 제안 종합**: 55는 D1과 같은 좌석이라 별도 갭이 아니라 모듈 49의 하류로 통합한다. 54·57은
`NLP-02`가, 56은 `S4-15`가 이미 소유한 축이므로 이 문서는 그 결정을 **재설계하지 않고 승계**만
한다(§3 등재요약에 승계 행 명시). 58은 CAT이 이미 그 역할을 하고 있어 별도 엔티티 신설이 오히려
Layer Separation 위반(진단/학습 경계 흐림) 소지가 있다고 판단해 미채택한다.

### (횡단) 등급·백분위·합격예측 노출

`assessment` 테이블에는 외부 틀에 없는 축이 이미 스키마로 존재한다 — `estimated_grade`(1~9)·
`estimated_score`·`estimated_percentile`·`target_university_id`·`admission_probability`(PRD
특성 #14/#15/#45/#86). 이 필드들을 학생에게 그대로 보여주면 CLAUDE.md 교수학 금기("정답을
빠르게"·"정답률만으로 우열 매기는 게임화 금지"·"부정적 피드백의 정서적 강화 금지")와 정면으로
부딪힌다. **현재 이 필드를 읽어 학생 대면 응답에 싣는 코드는 0건**이지만, 그 봉인이 왜 필요한지·
언제 풀리는지를 기록한 문서가 지금까지 없었다.

⚠️ → **D2**

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | 학생 대면 점수·부분점수·등급 채점(51 "구성"·58) | `solution_module_gap_review §2-①` **승계** — "정답을 빠르게" KPI 금지·정답률 게임화 금지. 정본 대체 좌석: 3상태 검증 판정 + BKT/IRT 숙달도 |
| ② | 서술형·증명형 채점(53 "생성가능문제")·수행평가 AI 채점 보조(52) | `nlp_module_gap_review §2-③` **승계** — PRM은 데이터셋 빌더만 있고 모델이 없다(`whs/prm_builder.py`·`src/ml-models/` 비어 있음). 검증기 없는 LLM 채점은 "LLM 응답 검증 없이 제공 금지" 정면 위반 |
| ③ | 표현·서술 감점형 채점(52 AI지원 "문장 개선 제안"의 감점 해석) | `solution_module_gap_review §2-⑥` **승계** — 서술 피드백은 감점이 아니라 구조 피드백·질문형으로만. 톤 필터(`l4/tone_filter.py`)가 최종 게이트 |
| ④ | 진단 시작 시 오개념 목록 사전 선반영(49 "오개념 탐지"의 preload 해석) | CLAUDE.md 명문 금기 — "오개념을 초기 context에 preload 금지, reactive retrieval만"(misconception contamination 방지). 영구 |
| ⑤ | 평가원 기출·EBS 본문 기반 총괄평가·모의고사 조립(51) | CLAUDE.md·`licensing_safety.md` — 평가원·EBS **본문은 상업 영리금지**(저작권법 §136·§140). 구조 메타(단원·코드·문항번호)만 참조 가능, 실제 조립은 **자체 생성 동등문제**로만. 영구 |
| ⑥ | AI 평가 문항 생성(53)에 별도 IRT/난이도 모델 신설 | 2축(규칙기반 `l3/equivalent/difficulty.py` + IRT JMLE 보정)이 이미 정본. 세 번째 축은 이중 진실원천 — `ai_recommendation_module_gap_review §2-⑨` 승계 |
| ⑦ | 맞춤형 재평가 세션(확장58)을 CAT과 별개 엔티티로 신설 | IRT CAT(`/me/next-problem`)이 매 호출마다 θ 재추정 후 재선택 — 이미 "재평가"다. 별도 세션 개념은 진단↔학습 경계를 흐려 Layer Separation 위반 소지 |
| ⑧ | 수행평가 표절 검사 연계(52 AI지원) | 페르소나 A~E 전원이 **개인 학습 앱** 이용 중·고등학생. 학교 제출 인프라(교사 채점 시스템) 연동은 스코프 밖 — `operations_module_gap_review` §범위와 동일 논리. Phase 3 교사 대시보드 진입 후 재검토 가능(§5) |

---

## §3. 진짜 갭 설계

### D1 — 평가 결과 영속 좌석(`assessment` 4테이블)이 스키마·API·프라이버시까지 완비된 채 writer 0 (최우선·`ASM-01`)

**문제**: `db/models/assessment.py:66-136`의 `assessment` 테이블은 진단 유형 5종(`AssessmentType`
— 초기진단·주간진단·단원진단·실전모의고사·D-100예측, `schema/enums.py:953-968`)과 5개 진단 산출물
JSONB(`concept_diagnosis`·`pattern_diagnosis`·`weak_points`·`strong_points`·`recommended_path`)를
담는 컬럼까지 갖췄다. 조회(`GET /v1/me/assessments`, `api/me.py:369`)·완료(`PATCH .../complete`,
`:2021`)·삭제(`DELETE`, `:2044`)·프라이버시 내보내기(`privacy/export.py:93`)·파기(`privacy/
retention.py:51`)·삭제 감사(`privacy/erasure.py:88`)까지 전부 배선돼 있다. 형제 테이블 3종
(`concept_mastery_history:169`·`skill_mastery_history:209`·`ability_snapshot:246`) 중
`ability_snapshot`만 writer가 있고(`api/me.py:965` POST), **`assessment` 본체는 `Assessment(...)`
생성 코드가 `src/` 전체에 0건**이다(전수 grep — 참조처는 SELECT/UPDATE/DELETE와 프라이버시 배선
뿐). 마이그레이션(`20260604_0400_a7b8c9d0e1f2` 인덱스까지)까지 있는데 **만드는 것만 없다**.

**왜 아무도 몰랐는가 — 소비 경로가 너무 완비돼서**: 조회 API가 정상 200을 반환한다(빈 리스트).
완료·삭제 API는 존재하는 assessment_id가 없으니 항상 404다. 두 응답 모두 "정상 동작"처럼 읽힌다.
게다가 실동작 진단(`/me/diagnosis/concepts`)이 **이 테이블을 아예 거치지 않고 즉석 계산**해서
학생에게 숙달도·약점 개념을 보여주기 때문에, "진단이 작동한다"는 체감과 "assessment 테이블이
비어 있다"는 사실이 서로 가려 왔다. 이 시리즈에서 이미 7회 확인된 패턴(`curriculum §6`)의
**8회차**이며, 지금까지 중 가장 강한 형태다 — 이전 사례들은 소비측이 API 1~2개였지만 여기는
**조회+완료+삭제+프라이버시 3종까지 전부** 완비돼 있었다.

**같은 좌석의 두 번째 결손 — 오개념 목록이 진단 산출물에 없다**: `compute_concept_diagnoses`
(`l2/concept_diagnosis.py:71`)는 BKT·IRT 수치 교차검증만 산출한다. 외부 틀이 요구하는 "오개념
탐지" 결과는 별도 파이프라인(`misconception_hypothesis`, 코치 **대화** 턴에서만 갱신)에 있고,
채점(`POST /v1/me/attempts`) 경로와 연결돼 있지 않다. 즉 "이 진단에서 발견된 오개념"이라는
합성 산출물 자체가 어디에도 존재하지 않는다.

**핵심 판단 — 활성화가 아니라 가시화다**: `NLP-01`(OCR 도달 관측)·`REC-01`(추천 도달 관측)과
동형이다. `assessment` row를 생성하는 API(POST)를 신설하는 것은 이 태스크 범위 밖이다 — 진단
세션의 시작·종료 시점을 무엇으로 정의할지(단일 next-problem 호출인가, 여러 문항 묶음인가)는
아직 결정된 적이 없고, 결정 없이 만들면 날조다. 지금 필요한 것은 **"비어 있음이 보이는 것"**이다.

**정합 설계** (신규 스키마 0 · 마이그레이션 0 · POST 엔드포인트 신설 0)
- **① 도달 리포트**: `assessment` 4테이블 각각의 행 수 + `AssessmentType`별 분포(전량 0으로
  나올 것)를 리포트에 낸다. **"0건"이 아니라 "생성 경로 부재"로 표시**한다(`ops/cost_probe`
  이중 회계 선례 — 인프라가 죽으면 "측정 실패"가 보여야지 "0건 통과"로 위장되면 안 된다).
- **② 오개념 통합 결손 표기**: `/me/diagnosis/concepts` 응답에 "오개념 목록"이라는 필드가
  없다는 사실 자체를 리포트에 명시한다(있는 것처럼 보이는 필드를 임의로 추가하지 않는다).
- **③ recommended_path 컬럼 결손 표기**: 컬럼은 있고 `learning_path` API 결과는 별도로
  존재하는데 둘이 연결되지 않는다는 사실을 리포트에 명시한다.

**dead code 금지 충족**: 신규 테이블·컬럼 0. 기존 좌석의 **읽기 전용 진단**만 추가한다.
**측정 없는 도입 없음**: 도달 카운터가 0이면 0으로 보인다(현재는 **아무것도 안 보인다**).
**변별력**: 비어 있는 상태와 (테스트에서) row를 넣은 상태가 서로 다른 값을 내는지 실측한다.

**acceptance 후보**
1. 현행 실측 고정: `Assessment(...)` 생성 코드 0건·`AssessmentType` 5종 소비 코드 0건을
   재현한다(주장 확인 또는 반증 — 반증되면 범위 재조정).
2. 정합 설계 본체: 좌석 도달 리포트(행 수·타입별 분포·오개념/추천경로 결손 표기), 신규 스키마 0.
3. CI 배선 실재 확인: 신규 워크플로 없이 기존 harness 잡에 편입되는지(OPS-03·OPS-10 —
   "저장소에 존재함"과 "돌아감"은 다르다).
4. 변별력: 테스트에서 의도적으로 `Assessment` row 하나를 만들어 카운터가 실제로 오르는지
   실측 → 제거해 0으로 복원되는지 실측. 성공/실패가 같은 값을 내면 검증이 아니다.
5. 범위 밖 명시: `POST /v1/me/assessments`(생성 API) 신설·활성화는 이 태스크에 포함하지
   않는다(활성화가 아니라 가시화가 목표). 채점 권위 이관(`NLP-02`)·문항 통계 갱신(`S4-15`)도
   포함하지 않는다.

**의존**: 없음(즉시 착수). **태스크**: 신설 — `ASM-01-assessment-seat-reachability-observability`.

---

### D2 — 등급·백분위·합격예측 좌석과 게임화 금기의 긴장이 기록된 적 없다 (`ASM-02`, owner=kiki)

**문제**: `assessment` 테이블은 `estimated_grade`(1~9)·`estimated_score`·`estimated_percentile`·
`target_university_id`·`admission_probability`(PRD 특성 #14/#15/#45/#86, `D-100예측` 진단 유형
전용)를 스키마로 이미 갖고 있다. 이 필드들이 그대로 학생에게 노출되면 CLAUDE.md 교수학 금기 —
"'정답을 빠르게'를 KPI로 사용 금지"·"학습 시간·정답률만으로 우열을 매기는 게임화 금지"·"부정적
피드백을 정서적으로 강화하는 표현 금지" — 와 정면으로 부딪힌다. 미성년 학생에게 등급 1~9·합격
확률을 그대로 보여주는 것은 서열화·불안 조장의 전형적 형태다.

**왜 지금까지 안 드러났는가**: D1과 같은 이유로 **이 필드들을 읽는 코드 자체가 0건**이라 실제
피해가 발생한 적이 없다. 그러나 "노출 경로가 없다"는 "긴장이 해소됐다"와 다르다 — 스키마가
이미 있고 PRD가 이 기능을 특성으로 명시(#86 "D-100 합격 예측")하고 있는 이상, 언젠가 소비 코드가
붙는 것은 시간 문제이며, 그때 **결정 없이 유입**되면 §6의 침묵 실패 패턴을 반복한다.

**핵심 판단 (범위: 결정만, 코드 0)**: 이 문서는 등급·백분위 노출 여부·형태를 **결정하지 않는다**
— 이것은 교수학·정서 안전(우선순위 ①)에 직결되는 판단이라 Kiki가 결정해야 한다(`ARCH-12`
QuizMode 채점 존치 결정 선례와 같은 급). 이 태스크는 **결정을 기록하는 태스크**다.

**정합 설계** (신규 스키마 0 · 결정 기록만)
- **① 옵션 정리**: (a) 원시 등급·백분위·합격확률을 그대로 노출 (b) 구간·방향성 서술로 감싸서
  노출(예: "상위권 수준" 대신 "이 개념은 안정적으로 다졌어요") (c) 학생에게는 비노출, 교사·
  학부모 대시보드(Phase 3)에만 조건부 노출 (d) 영구 비노출·필드 자체를 폐기.
- **② 결정 기록**: Kiki가 선택한 옵션과 근거를 MEMORY.md 결정 로그에 남긴다.
- **③ 봉인 방향 확정**: 결정 전까지는 이 필드를 읽어 학생 대면 응답에 싣는 신규 코드가 유입되면
  CI가 걸리도록 하는 게이트의 **설계 방향만** 문서화한다(`ARCH-12`의 화이트리스트 거버넌스
  테스트 선례) — 실제 게이트 구현은 결정 이후 별도 태스크로 분리한다.

**변별력**: 해당 없음(결정 태스크 — `ARCH-12` acceptance 패턴 승계, 그 태스크도 변별력 슬롯이
"결정 기록"으로 대체됐다).

**acceptance 후보**
1. 현행 실측 고정: `estimated_grade`·`estimated_score`·`estimated_percentile`·
   `admission_probability`를 읽어 학생 대면 응답에 싣는 코드가 현재 0건임을 재확인한다.
2. 결정 기록: 위 4개 옵션 중 하나(또는 변형)를 Kiki가 선택해 MEMORY.md 결정 로그에 기록한다.
3. 게이트 방향 문서화: 결정 전까지 신규 유입을 막을 게이트의 설계 방향(화이트리스트 vs 필드
   제거 vs 별도 스코프)을 문서로 남긴다. 실제 CI 게이트 코드 구현은 범위 밖(⑤).
4. 변별력: 해당 없음(결정 태스크).
5. 범위 밖 명시: 게이트 코드 구현·노출 UI 설계·`D-100예측` 알고리즘 자체 설계는 이 태스크에
   포함하지 않는다(결정 이후 별도 태스크로 분리).

**의존**: 없음. **태스크**: 신설 — `ASM-02-grade-exposure-policy-decision`(owner=kiki).

---

### 페이퍼 갭 — `MentalPhase` 6종(D-100 입시 코칭 D-day 구간) 미배선 (**페이퍼 — 코드 0 · 태스크 신설 없음**)

`assessment.mental_phase`(`db/models/assessment.py`)가 참조하는 `MentalPhase` enum 6종(D-day
구간별 정서·코칭 국면 — `schema/enums.py`)이 선언만 돼 있고 어떤 교수학 엔진·평가 로직도 이를
읽지 않는다. 이는 관계 타입 폭발과 무관하다 — 신호 자체가 없다(D-100예측 진단 유형이 아직
한 번도 생성된 적 없으니 D-day 구간을 구분할 근거 데이터가 없다). D1 해소 이후 `D-100예측`
진단이 실제로 만들어지기 시작하면, 그 시점에 자연스럽게 채워질 축이라 어휘만 준비된 상태로
남긴다(발화 조건은 §5-⑥).

### §3 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `ASM-01-assessment-seat-reachability-observability` | D1 | S3 | 2 | 평가 결과 영속 좌석 writer 0 — "완비된 소비 경로 + 미도달 공급원" 8회차(§6). 생성 API 신설은 범위 밖(acceptance ⑤) |
| `ASM-02-grade-exposure-policy-decision` | D2 | S1 | 3 | 등급·백분위·합격예측 노출과 게임화 금기의 미기록 긴장 — 결정 필요, owner=kiki. 게이트 구현은 범위 밖 |
| `NLP-02`(기존) | 모듈 50·54·57 채점 권위 축 | S3 | 2 | **승계·재설계 금지** — 클라 보고 `is_correct`, 서버 검산기 미연결. 이 문서가 재설계하지 않음 |
| `S4-15`(기존) | 확장 56 문항 통계 갱신 축 | S4(`S3-01` 잠금) | — | **승계·재설계 금지** — IRT/변별도/정답률 writer 0. 실응답 없이 만들면 dead code |
| `REC-04`(기존) | 진단 vs 학습 난이도 목적 분리 | S4 | 4 | **승계** — 정보량 최대(진단) vs 목표 성공률 밴드(학습)의 긴장. 이 문서가 재설계하지 않음 |

태스크는 전건 `backlog.py add` CLI 경유로 등재한다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (7종)

① **총괄평가(단원평가·중간·기말·모의고사 시험지 조립·배점·시험시간·난이도비율)** — 시험지라는
1급 엔티티, 배점(`points` 전량 NULL)·시간·비율 통제 코드 전부 0. 콘텐츠 공급 상한(코퍼스
2,647건, 초·중 단원 커버리지 0 — `problem_bank_gap_review.md`)과 저작권 제약(평가원 기출 본문
조립 불가)이 겹쳐 있어, 문항 공급이 늘기 전에는 만들어도 채울 것이 없다. 발화 조건 §5-①.

② **수행평가(모듈 52 전체 — 프로젝트·탐구·발표·포트폴리오·보고서·루브릭 채점)** — 저장소 전체
"수행평가" 언급 0건. 한국 중·고 내신에서 통상 20~40% 비중을 차지하는 축이지만, 서술형 채점의
전제 조건(PRM 실모델)이 아직 데이터셋 빌더 단계에 있어 지금 만들면 검증기 없는 채점을 노출하는
꼴이 된다. 발화 조건 §5-②.

③ **문항 노출 통제(exposure control) — 진단 풀과 학습 풀의 분리** — IRT CAT은 이미 미응답 문항만
후보로 삼지만(`attempted_ids` 제외, `api/me.py:1738`), "진단에 쓴 문항을 학습에 재사용해도
되는가"·"문항 소진율"을 관리하는 축은 없다. 실응답이 0행인 지금 만들면 `S4-15`와 같은 이유로
"입력 없는 파이프라인"이 된다. 발화 조건 §5-③(`S3-01` 파일럿과 같은 게이트).

④ **평가 자체의 심리측정 신뢰도·타당도(Cronbach α, 검사-재검사 신뢰도, 내용타당도)** — 저장소
전체 0건(E6 영어 확장 축의 Cohen's κ만 유일 예외). "진단이 실제로 맞았는가"를 사후 검증하는
루프가 없다. `04d_adaptive_pedagogy_engine.md`가 교수법 *효과* 측정은 설계했지만 진단 *정확도*
자체는 대상이 아니다.

⑤ **진단 정확도 자기검증 루프** — ④의 하위 항목. "이 θ 추정이 맞았는가"를 이후 실제 성취
(학교 시험·모의고사 결과)와 대조하는 경로가 없다.

⑥ **DKT(Deep Knowledge Tracing)** — `02_learner_model.md:26`이 명시한 도입 조건(N>10,000명)
미충족. `l2/__init__.py:10` 등 "후속 예정" 주석만 있고 `src/ml-models/`는 README 1개뿐.

⑦ **학부모·교사용 평가 결과 리포트 UI** — Phase 3(L7 커뮤니티·대시보드) 로드맵 시점. 리포트
내용은 LLM 요약이 아닌 SQL·증거 그래프 유래여야 한다는 원칙(`04a_wh1_tutoring_harness.md:133`)은
이미 정해져 있으나, 화면 자체는 착수 시점이 아니다.

---

## §5. 유보 항목의 발화 조건 (지금 안 만들되, 언제 만드는지)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | 총괄평가(시험지 조립) | S2 콘텐츠 공급 확대로 초·중 단원 커버리지가 유의미해지고, 페르소나 A의 D-100 임박 국면(PRD FR-012 "100분 모의고사 시뮬레이션")이 로드맵에 실제 진입할 때 |
| ② | 수행평가(루브릭 채점) | Phase 2 내신 대비 모드 진입 **또는** 페르소나 D(학종·세특) 로드맵 진입 — 둘 중 하나. 선결 조건: PRM 실모델(현재 데이터셋 빌더만)이 학습·검증까지 완료 |
| ③ | 문항 노출 통제 | `S3-01-pilot-cohort` 가동으로 실응답이 축적된 이후(`S4-15`와 같은 게이트) |
| ④ | DKT | 활성 학생 수 N>10,000 달성 |
| ⑤ | 등급·백분위·합격예측 노출 | `ASM-02` 결정이 (a)~(d) 중 하나로 완료된 이후에만. 결정 전 신규 유입은 게이트 대상 |
| ⑥ | `MentalPhase` 배선 | D1 해소로 `D-100예측` 진단이 실제로 생성되기 시작하고, D-day 코칭 축이 로드맵에 착수될 때 |

---

## §6. 반복 실수 — "완비된 소비 경로 + 미도달 공급원" 8회차 (재발방지 등재)

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| 4~6 | 추천 개인화·개념 추천 6종·응답 필드 미표기(REC-01) | 만들고 **입력 루프가 클라에서 끊김** |
| 7 | 학습목표(Objective) 커버리지 0.1%(CUR-02) | 만들고 **파일럿 이후 확장을 안 함** |
| 8 | **`assessment` 4테이블 중 본체가 조회·완료·삭제·프라이버시 3종까지 완비된 채 생성 코드 0**(D1) | 만들고 **생성 API 자체를 안 만듦** |

공통 구조는 이번에도 같다: **소비측이 완비돼 있어서 "존재함"이 "돌아감"으로 읽힌다.** 이번
사례가 특히 강한 이유는, 이전 7회는 소비측이 보통 1~2개 표면(엔드포인트 하나·클라 버튼 하나)
이었던 반면, 이번엔 **조회+완료+삭제+내보내기+파기까지 5개 표면**이 전부 완비돼 있었다는
점이다 — CRUD의 R/U/D는 다 있는데 C(생성)만 없는, 이 패턴의 가장 순수한 형태다.

CLAUDE.md의 "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" 규칙은 **검증 장치**에 한정돼
있었으나, `nlp_module_gap_review §6`이 이를 "학생 대면 기능"으로 이미 확장했다. 이번 사례는
그 확장이 **데이터 모델(테이블) 단위**에서도 성립함을 보여준다 — 판정 기준은 여전히 "코드가
있는가"가 아니라 "그 코드로 실제 행이 생기는가"다.

---

## §정정 — 정본 stale 2곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `docs/strategy/prd_v1.2.md:431,441` | "평가원 기출 30년치 ETL"을 콘텐츠 소스 **P0**로, "문항+정답+해설+메타데이터" 수집을 Phase 1 1순위 작업으로 서술 | `ROADMAP.md:56`·`docs/data/licensing_safety.md`가 이미 "**구조 메타데이터(단원·코드·문항번호)만** + 자체 생성 동등문제 대체"로 상위 결정(저작권 가이드 v2.0). PRD 원문 자체는 미정정 — 두 문서가 서로 다른 시점의 계획을 동시에 정본처럼 서술하는 상태 |
| `docs/architecture/02_learner_model.md:229-232` | "성공 기준 — Phase 3+: ✅ DKT 도입" | 전수 grep 결과 DKT 관련 코드는 "후속 예정" 주석뿐(`l2/__init__.py:10`·`l2/bkt.py:25`·`l4/lthc/models.py:24`), `src/ml-models/`는 README 1개뿐. **미착수 상태를 완료 표기(✅)로 서술**하고 있어 §4-⑥의 정직한 공백과 정면 모순 |

두 항목 모두 "실제보다 앞선 완료를 문서가 서술한다"는 curriculum 편의 stale 방향과 반대다 —
여기서는 문서가 **실제보다 앞서 있다**(계획을 완료로 착각하게 만든다). 두 곳 모두 병렬 세션이
claim한 범위와 겹치지 않아 이 PR에서 인라인 정정 대신 **본 문서에 실측을 병기**하는 것으로
정정한다(PRD·02_learner_model 원문 수정은 별도 세션의 광범위한 정합 작업이 필요해 이번 스코프
밖 — 코드 로직 변경 0 원칙과 마찬가지로 대규모 문서 재작성도 이번 커밋에 포함하지 않는다).

---

## 부록 — 실측 근거 (2026-08-03 실측)

**`assessment` 좌석**
- `src/backend/whymath_backend/db/models/assessment.py:66` `class Assessment(Base)`,
  `:78` `__tablename__ = "assessment"`. 형제 테이블: `:157-169` `ConceptMasteryHistory`,
  `:196-209` `SkillMasteryHistory`, `:236-246` `AbilitySnapshot`.
- `src/backend/whymath_backend/schema/enums.py:953-968` `class AssessmentType(str, Enum)` —
  초기진단·주간진단·단원진단·실전모의고사·D_100예측(값 `"D-100예측"`).
- `src/backend/whymath_backend/api/me.py:369` `GET /v1/me/assessments`, `:2021`
  `PATCH .../{id}/complete`, `:2044` `DELETE .../{id}`. **POST 없음**(전수 grep).
- `Assessment(...)` 생성자 호출 전수 grep 결과 0건. 참조처는 SELECT/UPDATE/DELETE(`api/me.py`)와
  `privacy/erasure.py:88`·`privacy/export.py:93`·`privacy/retention.py:51`뿐.
- 마이그레이션: `20260529_0224_bb30b816083d`(activity·dialogue·assessment·timeseries 신설),
  `20260604_0400_a7b8c9d0e1f2`(assessment_user_index), `20260605_1600_f2a3b4c5d6e7`
  (ability_snapshot).

**진단 엔진(초과 충족 확인)**
- `src/backend/whymath_backend/l2/irt.py` — `estimate_ability`·`fit_jmle:144`·
  `item_information:203`·`select_weighted_item:236`. 테스트 64건(`tests/backend/l2/test_irt.py`).
- `src/backend/whymath_backend/l2/concept_diagnosis.py:71` `compute_concept_diagnoses`.
- `src/backend/whymath_backend/api/me.py:1675` `GET /v1/me/next-problem` — θ 근방 50개
  (`_CANDIDATE_POOL_SIZE`) → 정보량 최대, `_TARGET_SE=0.3` 중단 규칙, `attempted_ids` 제외
  (`:1738,1816`).

**형성평가·검증(초과 충족 확인)**
- `src/backend/whymath_backend/api/verify.py:73,118,206` — `/verify-step`·`/verify-solution`·
  `/verify-answer`. 테스트: `test_verify_answer.py` 92건·`test_verify_step.py` 39건·
  `test_verify_solution.py` 23건·`test_verify.py`(API) 35건.

**AI 문항 생성 + QA(초과 충족 확인)**
- `src/backend/whymath_backend/l3/equivalent/orchestrator.py:178` `run_equivalent_generation`.
- `src/backend/whymath_backend/harness/qa_pipeline.py` — 7축(`:188,223,258,308,348,390,402`),
  `_NOT_MEASURED_AXES`(:142-147) `ui_golden`·`statistical_outlier`·`banned_words_pii`·
  `performance` 4축 명시적 미측정. CI 배선: `.github/workflows/ci.yml:178-187`(코퍼스 변경 시).

**채점 권위(NLP-02 승계 확인)**
- `src/backend/whymath_backend/api/me.py:585-589` — `is_correct`는 "v1: 클라이언트 보고" 자인.
- `src/backend/whymath_backend/db/models/activity.py:176` `student_answer` 컬럼(적재만, 미사용).
- `backlog/tasks/NLP-02-server-answer-grading-shadow.yaml` — status: todo, priority 2.

**문항 통계(S4-15 승계 확인)**
- `src/backend/whymath_backend/db/models/problem.py:194` `irt_difficulty_b`, `:199`
  `discrimination_D`, `:202` `historical_correct_rate` — 3필드 전수 writer grep 0건.
- `src/backend/whymath_backend/l2/calibrate_items.py:4-5` — "cron 미배선 시 전량 NULL로
  휴면" 자인. `infra/phaiakes9/systemd/`에 유닛 3개(api·worker·ollama)뿐, cron/timer 0건.
- `backlog/tasks/S4-15-response-driven-difficulty-loop.yaml` — `S3-01-pilot-cohort` 잠금.

**콘텐츠 공급 상한(총괄평가·수행평가 정직한 공백 근거)**
- `docs/architecture/problem_bank_gap_review.md` — 코퍼스 2,647건, 초·중 단원 커버리지 0.
- `Problem.points`·`scoring_type` 코퍼스 2,647건 전량 NULL(실측).
- `docs/data/licensing_safety.md:21-24` — 평가원·EBS 본문 상업 영리금지.

**등급·백분위 노출(D2 근거)**
- `src/backend/whymath_backend/db/models/assessment.py:98-105` `estimated_grade`·
  `estimated_score`·`estimated_percentile`·`target_university_id`·`admission_probability`.
- `backlog/tasks/ARCH-12-quizmode-grading-decision.yaml` — 유사 결정 태스크 선례(owner=kiki,
  화이트리스트 거버넌스 테스트).

**DKT 부재(§정정 근거)**
- `src/backend/whymath_backend/l2/__init__.py:10`·`l2/bkt.py:25`·`l4/lthc/models.py:24` —
  전부 "후속 예정" 주석. `src/ml-models/README.md` 1개뿐.
- `docs/architecture/02_learner_model.md:26,229-232` — "Phase 3+" 도입 조건(N>10,000) vs
  "성공 기준" 절 `✅ DKT 도입` 표기.
