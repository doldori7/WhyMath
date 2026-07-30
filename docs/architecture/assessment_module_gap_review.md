# 평가(Assessment) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-30)

> **범위**: 외부 참고 문서 『평가(Assessment)』(기능 49~53: 진단평가 생성 · 형성평가 생성 ·
> 총괄평가 생성 · 수행평가 관리 · AI 평가문항 생성, + 확장 후보 54~58: 자동채점 엔진 ·
> 평가결과 분석 · 문항통계 관리 · 오답·오개념 분석 · 맞춤형 재평가 — **WhyMath 전용이 아닌
> 일반적 EOS 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath
> 불변식(교수학 5원칙·검증 권위 서열·저작권 3중 레일·미성년자 보호·dead code 금기) 안에서
> 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(기능 6~10, 2026-07-27) · `problem_bank_gap_review.md`
> (기능 18~22, 2026-07-28) · `solution_module_gap_review.md`(기능 23~27) ·
> `ai_tutor_module_gap_review.md`(기능 37~41, 2026-07-29) 답습 — **5번째 자매편**.
> **대전제 2가지**: ① WhyMath에는 **이미 대량의 평가 자산이 존재한다**(IRT CAT 노출 · BKT↔IRT
> 교차검증 진단 · 원자 프로브 1,837건 · 3계층 SymPy 검산 약 1,900행 · 오개념 42파일/카탈로그
> 64종 · 문항 생성 25파일) — 이 문서는 무에서의 설계가 아니라 **격차 보완**이다. ② 틀은 평가를
> "출제→시행→채점→점수"로 프레이밍하지만, WhyMath에서 평가는 *점수 산출*이 아니라 **"무엇을 알고
> 무엇을 오해하는지의 측정"**이다("답이 아닌, 이유를 묻는 수학" · CLAUDE.md "정답을 빠르게를
> KPI로 사용 금지") — 틀의 10개 모듈을 1:1 신설하지 않고 **측정 신호로 재해석**한다.
> **결론**: 기능 53(AI 문항 생성)·57(오답·오개념 자산)은 **틀보다 엄격**하다(수용 게이트 4종·
> 독립 감사·Wilson 6축·강등전 / 카탈로그 64종·pgvector matcher·가설 감쇠). 그러나 **틀이
> "확장 후보"로 분류한 54(자동채점)가 실제로는 이 저장소의 근원 갭**이다 — 서버가 채점하지
> 않고 `is_correct`를 **클라이언트가 신고**하며(`api/me.py:601`), 저장된 정답을 읽는 채점기가
> 0건이다. 그 위에 ① 진단이 *시행 사건*으로 남지 않고(`Assessment` writer 0) ② 문항을 *세트로*
> 묶는 구조가 전무하고(grep 전량 0) ③ 오답 선지→오개념 결선이 명시적 보류 상태다. 진짜 갭 7건을
> 설계(D1~D7)하고 실행 6건을 백로그에 등재했다(D3은 타 세션 중복 회피로 등재 보류). 의도적 미채택 7건 · 정직한 공백 6종 · 유보
> 발화조건 6건. 정본 2곳(`02_learner_model.md` · `06_application_modes.md`)을 이번 설계에 맞춰
> 부기한다.

관련 정본: `02_learner_model.md`(BKT·IRT·LearnerState 계약) · `06_application_modes.md`(모드별
출제·7차원 자동 정렬) · `01_data_foundation.md`(성취기준 대장) · `03_content_generation.md`(생성·
검증) · `04a_wh1_tutoring_harness.md`(대리지표 11종·R5 unverifiable 경계) ·
`problem_bank_gap_review.md`(진단↔연습 역할 분담 · D9 문항통계 · 성취기준 분모 정정) ·
`ai_tutor_module_gap_review.md`(형성적 피드백 D1~D6 — 자매 갭) ·
`docs/data/problem_bank_coverage_2026-07.md`(ARCH-18 공급측 커버리지 실측) ·
`docs/standards/superhuman_verification_standard.md`(검증 권위 서열) ·
`docs/data/licensing_safety.md`(저작권 가이드 v2.0) · `MEMORY.md` 결정 로그(2026-07-30).

---

## §0 전제 — 실측 현황 스냅샷 (2026-07-30 기준)

### 0.1 이미 가동 중인 평가 자산

| 축 | 자산 | 상태 |
|---|---|---|
| **개인 진단 신호** | `l2/bkt.py`+`l2/mastery_tracking.py`→`ConceptMasteryHistory`(live writer) · `l2/irt.py`·`l2/ability_estimation.py`·`l2/ability_tracking.py`→`AbilitySnapshot` · `l2/skill_mastery_tracking.py`→`SkillMasteryHistory` | 🟢 가동 |
| **교차검증 진단** | `l2/concept_diagnosis.py` `compute_concept_diagnoses`(BKT↔IRT agreement 4상태) → `GET /v1/me/diagnosis/concepts`·`/diagnosis/summary` | 🟢 가동 |
| **적응 출제(CAT)** | `GET /v1/me/next-problem`(`api/me.py:1604`) — θ 근방 후보 50 → Fisher 정보량 최대 · 중단규칙 `_TARGET_SE=0.3` · `measurement_sufficient` · 약점 가중(옵트인) · 수능 모드는 `l6/suneung/recommendation.py`가 게이팅×CAT 결합 | 🟢 가동 |
| **약점·선수·경로** | `l2/weak_concept_recommendation.py` · `l2/prerequisite_recommendation.py`(재귀 CTE) · `l2/learning_path.py`(Kahn 위상정렬) — API 4좌석 | 🟢 가동 |
| **검산 3계층** | `l3/verify_answer.py`(Tier1 수치·1,575행) · `l3/verify_step.py`(Tier2 SymPy·3상태) · `l3/verify_solution.py`(`first_incorrect_index`) · `l3/symbolic_equivalence.py` · `l3/equivalent/canonicalize.py` — `POST /v1/verify-{step,solution,answer}` | 🟢 가동 |
| **오개념** | `l4/misconception/` 42파일 — 카탈로그 64종 · 코퍼스 843 · 프로브 162 · pgvector matcher · `match_gate` · `hypothesis_store`(감쇠 ×0.85) · `intervene` 4패턴 · `probe_selection` — coach 라이브 배선 | 🟢 가동 |
| **문항 생성** | `l3/equivalent/` 25파일 — 스켈레톤 9+종 · `llm_generator` · `acceptance`(수용 게이트) · `counterexample_fuzz` · `defect_seeder` · `orchestrator` — 코퍼스 6종 2,667문 | 🟢 가동(배치·CLI) |
| **문항 난이도 보정** | `l2/item_calibration.py`(JMLE 전수 적합 → `Problem.irt_difficulty_b`) + `l2/calibrate_items.py` CLI | 🟡 수동 CLI·응답 없으면 휴면 |
| **진단문항 자산** | `atom_probe` 1,837건(`diagnostic_item`·`diagnostic_answer`·통과기준·오답신호) | 🟡 적재 완료·서빙 0 |
| **모드별 게이팅** | `l6/{school_progress,suneung,thinking,gifted,metacognition,retake}/gating.py` — 순수·결정론 오버레이 · `l6/_shared.py:141 is_exposable()`(저작권 최종 게이트) | 🟢 가동 |
| **코호트 리포트** | `harness/wh1_evaluation.py`(대리지표 11종) · `harness/surrogate_baseline_report.py` · `harness/pilot_kpi_baseline.py`(파일럿 KPI 5종·NO_DATA 정직 표기) · `harness/wilson.py` | 🟢 가동(입력 대기) |
| **공급측 커버리지** | `harness/problem_bank_coverage.py`(ARCH-18) → `docs/data/problem_bank_coverage_2026-07.{md,json}` 커밋됨 | 🟢 완주 |

### 0.2 근원 갭 — **서버 자동채점이 존재하지 않는다**

이 문서의 가장 중요한 실측이다. 틀은 자동채점을 "확장 후보 54"로 뒤에 두었지만, 이 저장소에서는
**모든 평가 신호의 입력**이 여기에 달려 있다.

- `is_correct`는 **클라이언트가 신고**한다 — `api/me.py:601`·`:625`(`is_correct=body.is_correct`),
  `api/study.py:100`(`correct: bool`). `src/` 전체에서 `ProblemAttempt(` 생성은 `api/me.py:596`
  **한 곳뿐이며 서버 판정이 없다**.
- 정답 대조 코드 grep **전량 0건**: `correct_answer` 0 · `grade_answer` 0 · `auto_grade` 0 ·
  `자동채점` 0 · `student_answer ==` 0. 객관식 선지 index 비교 0건. 단답형 정규화 비교 0건.
- 정답 키는 **저장돼 있다** — `schema/problem.py:299` `Problem.answer`,
  `db/models/atom_probe.py:78` `AtomProbe.diagnostic_answer`. **읽는 채점기가 없다.**
- 강력한 검산 스택은 **방향이 반대**다 — `api/verify.py:15`("stateless — DB 무접근·LLM 호출 0"),
  `:224`("**서버 정답을 조회하지도, 누출하지도 않는다**"). 즉 학생이 조건과 답을 *둘 다* 넣는
  **자기검산 도구**이고, 문항의 저장된 정답과 대조하는 자동채점이 아니다. 이 설계는 의도적이며
  올바르다(정답 누출 방지) — 문제는 **채점 경로가 그 옆에 따로 없다**는 것이다.
- **파급**: IRT 문항 보정(`l2/item_calibration.py:82`)·BKT 숙달 갱신(`l2/mastery_tracking.py`)·
  WH-1 대리지표 11종·파일럿 KPI 5종이 전부 클라이언트 신고값을 입력으로 쓴다. 이는 ARCH-10
  (클라이언트 무-수학로직 CI 게이트)·ARCH-12(QuizMode 클라 채점 결정)가 막으려 한 것의
  **미완성 절반**이다 — 게이트는 "클라에 채점 *코드*를 두지 마라"를 강제하지만, "채점 *판정*을
  클라에서 받지 마라"는 아직 아무것도 강제하지 않는다.

### 0.3 진단은 "상시 추정"으로만 있고 "시행 사건"으로 남지 않는다

- `assessment` 테이블은 **실재**한다 — ORM `db/models/assessment.py:66`, 마이그레이션
  `20260529_0224_bb30b816083d_activity_dialogue_assessment_timeseries_.py:116` +
  `20260604_0400_a7b8c9d0e1f2_assessment_user_index.py`.
- 라이프사이클 표면도 실재 — `GET /v1/me/assessments`(`api/me.py:353`) ·
  `PATCH …/{id}/complete`(`:1952`) · `DELETE`(`:1975`) · privacy export/erasure/retention 3종
  등록(`privacy/{export,erasure,retention}.py`).
- **행을 만드는 코드가 저장소 전체에 0건이다** — `session.add(Assessment` / `Assessment.from_schema`
  src grep 0(히트는 전부 `tests/`). `POST /assessments` 부재(`api/me.py`의 POST는 `/attempts`·
  `/ability/snapshots` 2개뿐).
- `AssessmentType` 30히트 중 17건이 `tests/` — **프로덕션 writer·reader 0**. 5종(초기진단·주간진단·
  단원진단·실전모의고사·D-100예측) 전부 미발화. 결과 5필드(`concept_diagnosis`·`pattern_diagnosis`·
  `weak_points`·`strong_points`·`recommended_path`)·예측 3필드(`estimated_grade`·`estimated_score`·
  `estimated_percentile`)·`admission_probability`·`mental_phase` 전부 writer 0.
- 형제 3테이블은 **live writer 보유** → **4테이블 중 `Assessment`만 고아**다.
- 귀결: `GET /me/assessments`는 영구히 빈 배열이고, "이번 진단 결과를 지난 진단과 비교"라는
  성장 서사가 성립할 수 없다.

### 0.4 그 외 확정 사항

| 축 | 실측 |
|---|---|
| **시험지·세트 구조** | **전량 0건** — `blueprint`·`test_paper`·`exam_paper`·`exam_set`·`item_set`·`problem_set`·`total_score`·`time_limit`·`answer_sheet` src grep 모두 0. `시험지` 26히트는 **전부 `docs/`**(Phase 3+ 계획: `06_application_modes.md:190` "시험지 빌더·SEO는 PC 웹 작업·Phase 3+"). l6 6모드는 `list[Problem]`·`limit≤200` 필터+안정정렬뿐(`api/gating.py:296,319,367`) — 배점 총합·시험시간·비율 제약을 표현할 **필드 자체가 없다** |
| **배점·부분점수** | `points`(`schema/problem.py:258`) **src 소비처 0**(정의만) → 총점 계산 불가. `ScoringType` 5종(정오답·진단·부분점수·시간·루브릭, `schema/enums.py:220`) 중 실소비는 `l6/metacognition/gating.py:121,162` 한 곳(추천 가중치), **채점 디스패치 0**. `partial_credit` 0건 |
| **문항 통계** | `irt_difficulty_b`만 writer 보유(`l2/item_calibration.py:82`). `historical_correct_rate`(3히트)·`discrimination_D`(8)·`rate_top/mid/low_grade`(3씩)·`irt_a` **writer 0 → 전량 NULL** |
| **오답→오개념 결선** | `distractor_map` 122히트지만 실소비는 `l6/metacognition/gating.py:118,157`의 **`len()*2.0` 개수 세기**뿐 — 오개념 id를 꺼내지 않는다. `l4/misconception/distractor.py:13`이 "**객관식에서 *실시간 distractor→진단* 결선은 *모달리티 추가*라 후속으로 보류한다**"고 명시. 매처 입력은 `student_solution: str` 자유서술 전용 — 선지 index 오버로드 0 |
| **진단문항 서빙** | `atom_probe` 1,837건 적재 완료. 그러나 **api·l2·l4·l6 소비 0건**(히트 전부 `db/models`·`l1/atom_probe/projection.py`) → 진단문항이 학생에게 나가는 경로가 없다 |
| **유사문제 재출제** | `SocraticStrategy.유사문제`(`schema/enums.py:930`) **enum 라벨만**. `l4/` 내 0건 · `similar_problem` 0 · `재출제` 0. `CoachResponse`에 문항 반환 필드 없음 — coach는 텍스트만 낸다 |
| **재평가 사이클** | `재평가`·`retest`·`reassess` **0건**. "같은 성취기준 재측정" 구조 없음. `l6/retake/`는 **재수생(N수) 페르소나 트랙**이지 재시험이 아니다(`l6/retake/gating.py:5`) |
| **수행평가·루브릭** | `portfolio`·`project_assess`·`plagiarism`·`essay` **전량 0**. `rubric` 히트는 *LLM 프롬프트 품질 자체평가 루브릭*(`harness/pedagogical_rubric.py` 등 — 학생 산출물 채점 무관). `서술형` 26히트는 전부 "**SymPy 검증 불가 → `unverifiable`**"이라는 거부 선언(`l3/verify_step.py:39,97,223`) |
| **성취기준 달성도** | 성취기준 축 학생 mastery 테이블 **없음**. L2 16파일에서 `성취기준` grep 3건 전부 docstring 산문. 영속 축은 concept/skill/θ |
| **성취수준 A~E·평가기준** | 코퍼스 필드부터 **없음**(`achievement_level`/`성취수준`/`평가기준` src·schemas grep 0) → 틀의 "성취도 등급"은 **데이터부터 부재** |

### 0.5 문서·코드 불일치 3건 (이 문서가 정정한다)

1. **`schema/assessment.py:7`** — "코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) …
   SQLAlchemy/alembic 매핑은 후속 Phase"는 **스테일**이다. ORM·마이그레이션·인덱스가 이미
   배포됐다(§0.3). 후속 조사자를 오도하므로 정정 대상 — **D2 acceptance에 편입**.
2. **4단 조인 서술** — `schema/problem.py:492-494`(코드 주석)은 값 주입 경로를
   `Problem → problem_concept → concept → concept_standard_link → achievement_standard` 4단이라
   서술하지만, `api/gating.py:126-128`이 "**원자 축 전환(S2-03)** … 구 4단계 조인
   (`concept_standard_link` → `achievement_standard` — 구 437 code 공간·**재연결 후 0행**)을
   원자 축으로 교체했다"고 자인한다. 실가동 경로는 `problem_concept` → `concept` →
   `atom_node.standard_codes` **3단**이며, 그것도 **학교진도 게이팅 핸들러 전용**이다
   (`api/gating.py:257-258` — retake·suneung·thinking은 이 조인을 지지 않는다).
   `06_application_modes.md:89`의 "성취기준 코드 주입과 동형 계약"도 이 경로를 전제한다.
   → 코드 주석 정정은 D7 acceptance에 편입하고, 이 문서가 사실을 기록한다.
3. **"성취기준 895"는 레코드 수**다(2015 개정 460 + 2022 개정 435, 고유 코드 742 —
   153건이 양쪽 중복 등재). 커버율 분모는 **2022 개정 435**가 정본
   (`problem_bank_coverage_2026-07.md:36-48`). ARCH-18 실측 커버율 **72/435 = 16.6%**
   (초등 4.1% · 중 40.0% · 고 16.9%)이며, ROADMAP Phase 2 종료 게이트 "성취기준 100% 커버"
   (`ROADMAP.md:152`)와 직접 대비된다.

### 0.6 무모순 서술 — 기존 판정과 어긋나지 않는다

`core_feature_review_2026-07.md`는 "**코어는 과잉 성숙, 제품 루프는 미성숙**"이라 자기진단했고,
6기능 중 5기능을 🟢/🟡로 판정했다. 이 문서는 그 판정을 뒤집지 않는다 — **층위가 다르다**.

- 코어가 성숙한 축 = **신호 계산**(BKT·IRT·오개념 매칭·동치 판정·문항 생성). 실제로 성숙하다.
- 이 문서의 층위 = **그 신호의 ① 입력이 신뢰 가능한가(채점) ② 시행 단위로 남는가(Assessment)
  ③ 묶여서 나가는가(세트) ④ 다시 측정되는가(재평가)**. 이 4축은 "계산 품질"이 아니라
  **"측정 파이프라인의 연결"** 문제이고, 정확히 "제품 루프 미성숙"의 평가 영역 단면이다.

또한 `problem_bank_gap_review.md:70-72`가 확정한 역할 분담을 승계한다 — **"진단은 원자 프로브가,
연습·모드별 출제는 문제은행이 담당"**. 이 문서에서 "진단문항"은 `atom_probe`를 뜻하고,
"평가 세트 문항"은 문제은행 코퍼스를 뜻한다. 둘을 섞지 않는다.

---

## §1 기능 49~58 ↔ WhyMath crosswalk 판정

판정 어휘: ✅ 충족(틀 이상) · ⚠️ 부분·갭 → **Dn** · 🚫 의도적 미채택 → §2 · ⏸ 기존 추적 승계

| # | 틀 기능 | 틀이 요구하는 것 | WhyMath 실측 | 판정 |
|---|---|---|---|---|
| **49** | 진단평가 생성 | 수준 진단 문항 자동 구성 · 결과 4종(숙달도·약점·오개념·추천 학습순서) · 적응형 종료 | 결과 4종 산출 경로 **전부 실재**(`compute_concept_diagnoses`·`weak_concept_recommendation`·오개념 가설저장소·`learning_path`) · CAT 종료규칙 `_TARGET_SE=0.3`·`measurement_sufficient` 실재. 그러나 **시행 단위 영속 0**(§0.3) · **진단문항 서빙 0**(§0.4) | ⚠️ → **D2**(시행 단위) · **D3**(문항 서빙) |
| **50** | 형성평가 생성 | 학습 중 이해 확인 · 즉시 피드백 · 오답 시 설명 · 유사문제 제공 | **재해석 충족** — WhyMath에서 형성평가는 별도 평가 객체가 아니라 **튜터링 루프 자체**다(Polya 4단계·소크라테스 6종·힌트 사다리 4단·`verify_step` 3상태·오개념 진단→개입). 틀보다 엄격(답 미루기·정서 안전). 별 엔티티 신설은 🚫 §2-④. 잔여 갭 = **유사문제 제공**(enum 라벨만) | ✅ 재해석 충족 / 잔여 → **D6** |
| **51** | 총괄평가 생성 | 단원·학기 총괄 시험지 · 배점·시험시간 · 성취기준·유형 비율 · 난이도 분포 | **시험지·배점·시간·비율 전량 0건**(§0.4). `AssessmentType.실전모의고사` 라벨만 존재. 평가원 기출 조립은 🚫 §2-① | ⚠️ **최대 구조 갭** → **D4** |
| **52** | 수행평가 관리 | 루브릭 채점 · 포트폴리오 · 프로젝트·발표·협업 · 제출물 업로드 · 표절검사 | **전량 0건**. `ScoringType.루브릭`은 라벨뿐(채점기 0). 서술형은 `verify_step`이 설계상 `unverifiable` 반환 | 🚫 §2-⑤⑥ / 서술형·증명 채점만 ⏸ `S4-02-proof-learning-support` |
| **53** | AI 평가문항 생성 | 문항 생성(문제·정답·해설·오답·오개념·힌트·관련개념) · 품질검증 6종(교육과정 일치·정답·중복·난이도·수식·환각) | **초과 충족** — `l3/equivalent/` 25파일 · 스켈레톤 9+종 · 수용 게이트(`acceptance.py`) · `counterexample_fuzz` · `defect_seeder` · 독립 감사 · Wilson 6축 · 강등전. 코퍼스 6종 2,667문. 저작권: 본문 미복제·자체 동등문제 | ✅ **초과 충족**. 생성 학년 범위는 ⏸ `ME-06`(타 세션 in-flight) |
| **54** | 자동 채점 엔진 | 객관식·단답형 자동채점 · 수식 동치 인정 · 부분점수 · 서술형 | **근원 갭 — 서버 채점 0건**(§0.2). 수식 동치 *능력*은 최상급이나 자기검산 방향. 부분점수·배점 소비처 0. 서술형은 정직 경계 | ⚠️ **최우선** → **D1** |
| **55** | 평가 결과 분석 | 개인 성취도 리포트 · 문항별 정답률 · 학급·학교 통계 · 교육과정 달성률 | 개인 축 **부분**(진단·숙달·θ API 다수). **성취기준 달성률(교육과정 달성률) 0** · 코호트 교육통계(평균·표준편차·백분위) 코드 0. 학급·학교 축은 🚫 §2-② | ⚠️ → **D7** |
| **56** | 문항통계 관리 | 정답률·변별도·오답 선지 분포 · 문항 개선 환류 | 필드 실재·writer 0(§0.4). **`S4-15-response-driven-difficulty-loop`가 이미 등재**(정답률·`rate_*`·경험 변별도 + `distractor_map` 선택률 통계, `depends_on: S3-01-pilot-cohort`) | ⏸ **`S4-15` 승계** — 단 **D1이 그 입력 신뢰의 선결**임을 명기 |
| **57** | 오답·오개념 분석 | 오답 패턴 분류 · 오개념 자동 진단 · 교정 전략 제시 | **자산 초과 충족**(카탈로그 64종·코퍼스 843·42파일·프로브 162·pgvector·LLM judge·가설 감쇠·개입 4패턴, coach 라이브). 그러나 **선지→오개념 결선이 명시적 보류**(`distractor.py:13`) | ✅ 자산 / 결선 → **D5** |
| **58** | 맞춤형 재평가 생성 | 약점 기반 재출제 · 동일 성취기준 재측정 · 성장 비교 | 약점 가중 CAT **부분 충족**(옵트인 `?prioritize_weak_concepts`, 기본 false). **재측정 축 0건**(§0.4). 성장 비교는 D2 없이는 비교 대상 자체가 없음 | ⚠️ → **D7**에 병합 · ⏸ `S4-18` 층위 구분 |

**요지**: 10기능 중 **2기능(53·57)은 초과 충족**, **1기능(50)은 재해석 충족**, **1기능(52)은 대부분
의도적 미채택**, **1기능(56)은 기존 추적 승계**다. 진짜 갭은 **5기능(49·51·54·55·58)이며 그 중
54(자동채점)가 나머지 전부의 선결**이다. 즉 이 틀은 "미구현 로드맵"이 아니라 **"측정 파이프라인의
끊긴 4곳"**을 가리킨다.

---

## §2 의도적 미채택 판정 (7건 — 협상 불가 근거와 1:1)

| # | 틀 항목 | 미채택 근거 (CLAUDE.md 협상 불가 조항) |
|---|---|---|
| **①** | 평가원·EBS 기출 기반 모의고사 조립 | 저작권 3중 레일 — 저작권법 §32(시험문제 복제)의 단서 "**영리 목적 제외**"가 상업 앱에 적용 불가, §136(권리침해죄)·§140(영리·상습 비친고죄)·§125-2(법정손해배상 1건당 최대 5천만 원), 2024.8 대법원 KICE 판결. **구조 메타데이터(단원·코드·문항번호)만 보유하고 자체 동등문제로 본문 대체**. D4의 세트 조립은 자체 코퍼스만 입력으로 받는다 |
| **②** | 학급·학교 단위 집계·석차·백분위·랭킹 | "미성년자 개인정보를 분석·마케팅 외부 공유 금지" · "학교·학년 정보로 개인 식별 가능한 분석 결과 외부 노출 금지" · "학습 시간·정답률만으로 우열을 매기는 게임화 금지" · L7 안전선 "❌ 랭킹, ✅ 익명·집계만"(`07_community.md`). 교사 대시보드는 Phase 3+(`ROADMAP.md:162`) |
| **③** | 표절 검사 연계 | 학생 데이터 외부 공유 금지 · 소비처 0(제출물 관리 자체가 없음) · 수학 풀이의 "표절" 판정은 다중 풀이 동치성과 충돌(같은 풀이가 정답인 것이 정상) |
| **④** | 형성평가를 별도 평가 엔티티로 신설 | **추상 이중화 금지** — 형성적 피드백의 truth source는 이미 튜터링 루프(coach 4엔드포인트·Polya·소크라테스·오개념 개입)다. 평가 객체를 새로 세우면 "학습 중 확인"이 두 곳에 살고 유지보수 지옥(7대 붕괴 4번 "truth source가 하나가 아님")을 부른다. 틀의 50은 **기존 루프에 매핑**한다 |
| **⑤** | 루브릭·서술형 "정답 확언" 채점 | `l3/verify_step.py:223`이 비대수 단계(서술형·경우나누기·기하)에 **`unverifiable`을 반환**하도록 설계됐고, `04a` R5가 그 경우 답을 누설하지 않게 한다. 여기에 루브릭 점수를 얹으면 "확실하지 않을 때 자신 있게 말함 금지"(AI 금기)를 정면 위반한다. 서술형·증명 축은 ⏸ `S4-02-proof-learning-support` 승계(MEMORY 2026-07-29 결정 로그가 "증명·서술 채점 = S4-02 승계"로 이미 확정) |
| **⑥** | 수행평가 제출물(파일·동영상·PDF)·프로젝트·발표·협업 평가 | 학생앱(패드 중심 학습 루프) 우선 · 소비처 0 · 교사·학교 B2B 축이며 Phase 3+ · PRD 우선순위상 페르소나 A(일반고 고3) 밖 |
| **⑦** | 성취도 등급(A~E)·백분위·합격 확률 예측 | **데이터부터 0** — 성취수준·평가기준 필드가 코퍼스에 없다(§0.4). 그 위에 `Assessment`의 `estimated_grade`·`estimated_score`·`estimated_percentile`·`admission_probability`를 채우면 근거 없는 예측이 되어 "확실하지 않을 때 자신 있게 말함 금지"·"장기 숙달 > 단기 점수"(의사결정 우선순위 4)를 위반한다. **D2는 이 4필드를 명시적으로 채우지 않는다**(반-스코프 동결) |

---

## §3 설계 — 진짜 갭 7건 (D1~D7)

### D1. 서버 자동채점 — 정답 대조 경로 신설 **(최우선)**

**갭**: §0.2. 서버가 채점하지 않는다. `is_correct`는 클라이언트 신고이고, 저장된 정답
(`Problem.answer`·`AtomProbe.diagnostic_answer`)을 읽는 채점기가 0건이다.

**왜 최우선인가**: 이 한 지점이 **모든 하류 측정의 입력**이다 — IRT 문항 보정(`S4-15`)·BKT 숙달
전파·WH-1 대리지표 11종·파일럿 KPI 5종·D2 진단 결과·D4 세트 채점·D5 오개념 결선이 전부 여기서
받는다. 파일럿(`S3-01`)에서 실학생 응답을 받기 시작하는 순간 **신뢰할 수 없는 입력으로 영구
오염된 시계열**이 쌓이므로, 파일럿 *전에* 착지해야 한다.

**설계 — 기존 자산 조립, 신규 수학 로직 0**:
1. **채점 위치**: `POST /v1/me/attempts` 경로에 서버 채점을 삽입한다. `/v1/verify-*` 3엔드포인트는
   **건드리지 않는다** — stateless·DB 무접근·정답 비누출 계약(`api/verify.py:15,224`)은 학생
   자기검산 도구로서 올바른 설계이므로 그대로 존치한다. 채점은 **별 경로**다.
2. **형식별 판정**:
   - 객관식 — 저장된 선지 index 대조. 수학 로직이 아니라 단순 동등 비교(클라 금지 대상 아님).
   - 단답형 — 정규화 후 비교. 정규화는 기존 `l3/equivalent/canonicalize.py` 재사용.
   - 수식 — 기존 `l3/symbolic_equivalence.py`(SymPy 단일권위) 호출. 학생 답 ↔ **서버 보유 정답**.
   - 서술형·증명 — `unverifiable` 유지(§2-⑤). 채점하지 않고 그 사실을 기록한다.
3. **정답 누출 금지**: 채점 응답은 판정(+틀린 경우 오개념 신호)만 반환하고 **정답 자체를 담지
   않는다**. Polya 답 미루기와 정합 — 틀렸다는 사실이 곧 정답 공개가 되어서는 안 된다.
4. **클라 신고값 강등 순서**: `is_correct`를 즉시 제거하지 않는다. 먼저 **서버 판정과 클라 신고의
   불일치율을 계측**하고, 측정 후에 클라 필드를 강등한다("측정 없는 도입 없음" 원칙의 역방향
   적용). ARCH-12가 공식화한 데모 예외 화이트리스트 2건은 그대로 존중한다.

**반-스코프 동결**: `/verify-*` 계약 무변경 · 서술형 채점 미포함 · 부분점수는 D4 · 신규 테이블 0
(`ProblemAttempt`에 서버 판정 컬럼 추가만) · LLM 호출 0(SymPy 결정론).

**백로그**: `ASM-01-server-side-grading`

---

### D2. 진단 시행 단위 착지 — `Assessment` writer 실체화

**갭**: §0.3. 테이블·인덱스·조회/완료/삭제 API·privacy 3종이 다 있는데 행을 만드는 코드가 0건.

**설계 — 신규 계산 0·조립만**: 진단 결과 5필드를 **기존 산출물로 채운다**.

| `Assessment` 필드 | 채우는 기존 자산 |
|---|---|
| `concept_diagnosis` | `l2/concept_diagnosis.py compute_concept_diagnoses`(BKT↔IRT agreement) |
| `weak_points` | `l2/weak_concept_recommendation.py recommend_weak_concepts_detailed` |
| `strong_points` | 같은 산출물의 상위 숙달 개념(신규 계산 0) |
| `recommended_path` | `l2/learning_path.py`(Kahn 위상정렬) |
| `pattern_diagnosis` | 오개념 가설저장소(`l4/misconception/hypothesis_store.py`) 활성 가설 |

- **발화 대상은 `AssessmentType` 2종만** — **초기진단**(온보딩 CAT 웜스타트 종료 시) ·
  **단원진단**(단원 마감 시). 나머지 3종은 발화 조건을 §5에 기록한다(주간진단=시간축 필요 ·
  실전모의고사=D4 필요 · D-100예측=§2-⑦로 미채택).
- **종료 시점**은 신설하지 않고 기존 `measurement_sufficient`(`_TARGET_SE=0.3`)를 그대로 쓴다.
- **상시 추정 ↔ 시점 스냅샷의 역할 분담**을 명시한다: `/diagnosis/concepts`는 *지금 상태*를 계산
  (실시간·항상 최신), `Assessment`는 *그때 상태*를 동결(비교 가능·불변). 둘은 경쟁하지 않는다.
- `PED-05-learner-state-assembly`(타 세션 in-flight)와 **층위가 다르다** — PED-05는 런타임 코칭용
  *휘발* 조립(`LearnerState`), D2는 *영속* 시점 스냅샷. 중복이 아니며 D2가 PED-05의 조립기를
  재사용할 수 있다.
- `schema/assessment.py:7`의 스테일 docstring 정정을 acceptance에 편입한다(§0.5-1).

**반-스코프 동결**: 예측 4필드(`estimated_grade`·`estimated_score`·`estimated_percentile`·
`admission_probability`)·`mental_phase` **미충전**(§2-⑦) · 신규 계산 로직 0 · 신규 테이블 0 ·
신규 마이그레이션 0(테이블이 이미 있다).

**백로그**: `ASM-02-assessment-session-persist`

---

### D3. 진단문항 서빙 배선 — `atom_probe` 소비처 0 해소

**갭**: 1,837건이 적재 완료인데 api·l2·l4·l6 소비 0건. 진단문항이 학생에게 나가는 경로가 없다.

**설계**: `atom_probe`의 `diagnostic_item`을 **진단 세션(D2) 전용 노출 경로**로 배선한다. 문항
선택은 신규 알고리즘을 만들지 않고 기존 `l4/misconception/probe_selection.py`(정보이득 + ε탐색)를
재사용한다. `problem_bank_gap_review.md:70-72`의 역할 분담을 유지 — **진단은 프로브, 연습은
문제은행**이며 두 풀을 섞지 않는다.

**⏸ 중복 위험 — 등재 보류**: `PED-10-diag-item-slot-fill`이 타 세션(`claude/whymath-teaching-
strategy-enfkqt`)에서 in-flight다. 슬롯 *충전*과 서빙 *배선*은 다른 작업이지만 인접하므로,
이 문서는 **갭만 확정하고 신규 등재를 하지 않는다.** `PED-10` 머지 후 잔여분이 남으면 그때
등재한다(선례의 "기존 추적 승계" 원칙 · 병렬 세션 중복 구현 사고 재발 방지).

**백로그**: 등재 없음 (⏸ `PED-10` 이후 재평가)

---

### D4. 평가 blueprint — 총괄평가 세트 조립 + 배점·세트 채점

**갭**: §0.4. 시험지 구조 전량 0. `points` 소비처 0 → 총점 계산 불가.

**설계**:
1. **선언적 blueprint 명세** — 성취기준×난이도 밴드×유형 비율 · 문항 수 · 배점 배분 · 시험시간을
   **선언 JSON**으로 표현하고, 조립기가 그 제약을 만족하는 세트를 자체 동등문제 코퍼스에서 뽑는다.
   `l6/_shared.py:141 is_exposable()`을 최종 게이트로 통과시켜 저작권 레일을 유지한다(§2-①).
2. **CAT vs blueprint 역할 분담(중요)** — 학습 중 노출은 **CAT 단건**이 정본이다(적응·정보량 최대·
   WhyMath 정체성). blueprint는 **"단원 마감 측정"에만** 쓴다. 즉 세트는 CAT을 대체하지 않고
   *특정 목적의 예외*다. 이 경계를 코드 주석·테스트로 동결한다.
3. **세트 채점·배점** — `points` 첫 소비처로 총점을 합산한다. 부분점수는 **신규 채점기를 만들지
   않고** 기존 `l3/verify_solution.py`의 `first_incorrect_index`(어느 단계까지 맞았는가)를
   부분 인정 근거로 재사용한다. 루브릭은 제외(§2-⑤).
4. **좌석 증설 회피** — 세트를 새 테이블로 만들지 않고 `Assessment` 행(D2) + 문항 id 배열로
   표현한다. `AssessmentType.실전모의고사`가 이때 처음 발화한다.

**의존**: D1(채점)·D2(Assessment 좌석). **반-스코프 동결**: 평가원·EBS 본문 0 · 교사용 시험지
빌더 UI 미포함(§5) · 인쇄·PDF 출력 미포함 · 루브릭 미포함 · 신규 테이블 0.

**백로그**: `ASM-03-assessment-blueprint`

---

### D5. 오답 선지 → 오개념 결선

**갭**: `distractor_map` 122히트지만 오개념 id를 꺼내는 코드 0. `distractor.py:13`이 "모달리티
추가라 후속 보류"로 명시 선언.

**설계 — 모달리티 추가가 아닌 결정론 조회로 우회**: 매처(`diagnose`·`semantic/matcher`)에 선지
경로를 *추가하지 않는다*(그것이 "모달리티 추가"였고 보류 사유였다). 대신 학생이 고른 선지 →
**`distractor_map` 조회로 M-id를 직접 얻는다** — LLM 0·임베딩 0·결정론. 이미 검증된 매핑을
읽는 것이므로 매처의 신뢰 문제(top1 임계·OCR 신뢰도)가 발생하지 않는다. 얻은 M-id는 기존
`hypothesis_store`에 같은 규약(감쇠 ×0.85)으로 투입해 자유서술 경로와 **하나의 가설 세트로 합류**
시킨다. `match_gate` 규약을 준용한다.

**즉시 소비처**: `misconception_mc_v0` 1,080문(선지별 오개념 태깅 보유) + 메타인지 모드 게이팅이
이미 `distractor_map` 보유 문항을 우선 노출한다.

**의존**: D1(어떤 선지를 골랐는지 서버가 알아야 한다 — 현재 `student_answer`는 자유 텍스트).
**반-스코프 동결**: 매처 입력 시그니처 무변경 · 새 EdgeType 발화 0(`TRIGGERS_DISTRACTOR`는 어휘만
존치) · 오개념 초기 preload 금지 원칙 유지(reactive retrieval).

**백로그**: `ASM-04-distractor-misconception-wiring`

---

### D6. 유사문제 재출제 폐루프

**갭**: `SocraticStrategy.유사문제`가 enum 라벨만이고 생성기·조회기 0. `CoachResponse`에 문항
반환 필드 없음. `core_feature_review_2026-07.md`가 이미 "학생 특정 오답에서 새 문제 폐루프
재생성은 미구현"으로 판정했다.

**설계**: 오개념이 확정된 뒤(D5) **같은 오개념을 유발하는 형제 문항을 재선택**한다. 문항을
새로 *생성*하지 않는다 — 생성은 `l3/equivalent/` 배치의 일이고, 여기서는 기존 코퍼스에서
고르기만 한다. 형제 관계는 `S4-14-variant-lineage-persist`(타 세션 in-flight)가 착지시키는
`problem_relation` 계보를 **소비**한다.

**의존**: `S4-14`(계보 영속) · D5(오개념 확정). **반-스코프 동결**: 문항 생성 0 · LLM 0 ·
같은 문항 반복 노출 금지(직전 오답 문항 자체는 제외) · 정답 누출 금지(유사문제 제시가 원 문항의
답을 알려주지 않도록).

**백로그**: `ASM-05-similar-problem-retry`

---

### D7. 성취기준 축 달성도 관측 + 재측정 축

**갭**: 성취기준 단위 학생 달성도 집계 코드 0(§0.4). 문서(`02_learner_model.md:29` "성취기준당
1개 BKT 모델" · `:141` `mastery` 키가 `"[9수01-01]"` · `:199-211` SQL의 `standard_code`)와
구현(개념/원자 축)이 **다른 축을 쓴다**. 재측정 구조도 0.

**설계**:
1. **축 결정을 먼저 한다** — 구현이 쓰는 **개념/원자 축을 정본으로 확정**하고, 성취기준은
   *투영(projection)*으로 다룬다. 근거: 원자 백본이 runtime 진실 원천으로 이미 단일화됐고
   (2026-07-04), 성취기준은 교육과정 오버레이(8대 원칙 5 "Curriculum은 Overlay")다. 개념 축
   숙달을 `atom_node.standard_codes`로 투영해 성취기준 달성률을 **파생 계산**한다 — 새 mastery
   테이블을 만들지 않는다. `02_learner_model.md`의 성취기준 축 서술을 이에 맞춰 부기한다(§6).
2. **ARCH-18의 수요측 쌍** — `harness/problem_bank_coverage.py`가 *공급*(문항 재고)을 관측하듯,
   학생 *달성*을 같은 형식(결정론·정직 회계·NO_DATA 표기)으로 관측한다. 틀의 "교육과정 달성률"이
   이것이다. 분모는 **2022 개정 435**(§0.5-3).
3. **재측정 축** — "같은 성취기준을 언제 다시 *측정*하는가". `S4-18-review-time-axis`는 복습
   (=학습) due를 계산하고, D7은 측정 due를 다룬다 — **층위가 다르다**. 다만 둘 다 BKT 망각
   역산을 입력으로 쓰므로, D7은 `S4-18`이 착지시키는 `decayed_mastery`·`days_since_practice`를
   **소비**하고 자체 시간축을 만들지 않는다.
4. **성장 비교** — D2의 `Assessment` 스냅샷 2개를 비교해 성취기준별 달성률 변화를 낸다.

**의존**: `S3-01-pilot-cohort`(실학생 응답 0 — 지금 만들면 입력 없는 파이프라인) · `S4-18`(시간축) ·
D2(스냅샷). **반-스코프 동결**: 성취수준 A~E·백분위·석차 미포함(§2-⑦·§4) · 코호트·학급 집계
미포함(§2-②) · 새 mastery 테이블 0.

**백로그**: `ASM-06-standard-attainment-observation` (`--depends S3-01-pilot-cohort`)

---

## §4 정직한 공백 (측정 불가·데이터 부재 — 지금 만들면 dead code)

| 공백 | 왜 지금 못 하는가 | 해소 조건 |
|---|---|---|
| 코호트 교육통계(평균·표준편차·백분위·문항별 정답률) | **실학생 응답 0** — 통계량의 입력이 없다. `historical_correct_rate`·`rate_*`·`discrimination_D` 전량 NULL | `S3-01` 후 `S4-15`(등재됨) |
| 성취수준 A~E · 평가기준(상/중/하) | **코퍼스 필드부터 없음** — `achievement_level` grep 0. `curriculum-node-builder` 스킬은 있으나 산출물 미적재 | 성취수준 데이터 적재 후(§5-⑥) |
| 서술형·논술형·증명 채점 | `verify_step`이 설계상 `unverifiable`(§2-⑤). 허위 확언 금지 | ⏸ `S4-02-proof-learning-support` |
| 행동 로그 기반 평가 분석(ClickHouse) | **미가동** — src 참조 14건 전부 "여기엔 없다"는 부정 서술(`privacy/export.py:25` 등), compose 프로비저닝 0. 실 로그 축은 `attempt_event`(EventType 11종 중 3종만 생산) | ⏸ `S3-16-behavior-telemetry-writers` |
| 정서 신호 기반 평가 맥락 | 생산자 0 → `pilot_kpi_baseline` KPI3 = NO_DATA(`:512` 자인) | ⏸ `S3-16` → `02_learner_model.md:166-169` 발화 조건 |
| 학생·학부모용 리포트 렌더 | 생성기 0건. Phase 3 계획(부모 주간 보고서 `ROADMAP.md:161` · 교사 대시보드 `:162`) | Phase 3 |

**정직 표기 규약 승계**: `harness/pilot_kpi_baseline.py:18-23`("빈 값·가짜 0으로 위장하지 않는다")
를 D7 관측에도 적용한다 — 측정 불가는 **NO_DATA + 사유 문자열**이며 0으로 위장하지 않는다.

---

## §5 유보 항목의 발화 조건

| # | 유보 항목 | 발화 조건 |
|---|---|---|
| **①** | `AssessmentType.실전모의고사` 전면 가동 | D4(blueprint) 착지 + 자체 동등문제 코퍼스가 수능 범위 성취기준을 충분히 덮을 때(현 커버율 16.6%) |
| **②** | `AssessmentType.주간진단` | D7 재측정 축 + `S4-18` 시간축 착지 후 |
| **③** | `AssessmentType.D-100예측`·`admission_probability` | §2-⑦로 **미채택**. 재검토는 실학생 성적 데이터 + 예측 보정(Brier) 실측이 있을 때만 |
| **④** | 교사용 시험지 빌더 UI | Phase 3+ · 별도 웹(React/Next.js) · `06_application_modes.md:190` |
| **⑤** | 수행평가·포트폴리오·루브릭 | 교사 대시보드(Phase 3) 착지 + §2-⑤의 정직 경계를 지키는 채점 설계가 나올 때 |
| **⑥** | 성취수준 A~E 기반 성취도 등급 | KICE 성취기준·평가기준 보고서를 `curriculum-node-builder`로 적재해 코퍼스에 필드가 생긴 뒤 |

---

## §6 정본 개정 (이번 커밋에 반영)

1. **`docs/architecture/02_learner_model.md`** — ① `Assessment` 시행 단위 writer 0(§0.3)
   ② 성취기준 축 ↔ 개념/원자 축 불일치와 D7의 축 결정(개념 축 정본 + 성취기준은 투영)을 부기.
2. **`docs/architecture/06_application_modes.md`** — ① 모드 출제는 게이팅 리스트/CAT 단건이고
   세트가 아님(+ D4 참조) ② 성취기준 코드 주입의 실가동 경로는 원자 축 3단이며 학교진도 전용
   (§0.5-2)을 부기.
3. **`docs/architecture/00_overview.md`** §참조 — 이 문서를 1줄 인덱스로 등재.

`schema/assessment.py:7`·`schema/problem.py:492-494`의 스테일 **코드 주석**은 **이번 커밋에서 고치지
않고**(코드 변경 0 원칙) 위 §0.5에 사실로 기록하고, 정정을 각각 D2·D7 acceptance에 편입했다.

---

## 부록 A — 실측 근거 (재현 명령)

```bash
# §0.2 서버 채점 부재
grep -rn "is_correct=body.is_correct" src/backend/whymath_backend/api/       # me.py:601,625
grep -rn "correct_answer\|grade_answer\|auto_grade\|자동채점" src/           # 0건
grep -n "DB 무접근\|서버 정답을 조회" src/backend/whymath_backend/api/verify.py  # :15,:224

# §0.3 Assessment writer 0
grep -rn "session.add(Assessment\|Assessment.from_schema" src/               # 0건
grep -rn "@router.post" src/backend/whymath_backend/api/me.py                # /attempts·/ability/snapshots 2개

# §0.4 세트 구조 부재
grep -rn "blueprint\|test_paper\|exam_set\|total_score\|time_limit" src/      # 0건
grep -rn "\.points" src/                                                      # 0건
grep -rn "distractor_map" src/backend/whymath_backend/l6/ src/backend/whymath_backend/api/  # 개수 세기만

# §0.5 스테일 주석·조인 정정
grep -n "Pydantic-schema-only" src/backend/whymath_backend/schema/assessment.py   # :7
grep -n "재연결 후 0행" src/backend/whymath_backend/api/gating.py                  # :128
```

## 부록 B — 중복 등재 회피 대장

이 문서는 아래 기존 태스크를 **재등재하지 않고 승계**한다.

| 기존 태스크 | 이 문서와의 관계 |
|---|---|
| `S4-15-response-driven-difficulty-loop` | 틀 56(문항통계) 전체. D1이 그 입력 신뢰의 선결 |
| `S4-02-proof-learning-support` | 틀 52·54의 서술형·증명 채점 축(§2-⑤) |
| `S4-18-review-time-axis` | 복습(=학습) 시간축. D7은 측정 축으로 층위 구분·소비만 |
| `S4-14-variant-lineage-persist` (타 세션) | D6이 소비하는 형제 문항 계보 |
| `S3-16-behavior-telemetry-writers` | §4 행동 로그·정서 신호 공백 |
| `PED-05-learner-state-assembly` (타 세션) | 런타임 휘발 조립. D2는 영속 스냅샷으로 층위 구분 |
| `PED-10-diag-item-slot-fill` (타 세션) | D3 등재 보류 사유 |
| `ME-06-problem-generation-grade-scope` (타 세션) | 틀 53의 생성 학년 범위 |
| `S3-01-pilot-cohort` | D7의 잠금 노드(실학생 응답 0) |
| `ARCH-18-problem-bank-coverage-report` | D7의 공급측 쌍·형식 선례 |
| `ARCH-10-client-mathlogic-gate`·`ARCH-12-quizmode-grading-decision` | D1이 완성하는 절반 |
