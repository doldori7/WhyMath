# 풀이(Solution) 엔진 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-29 · 2차 재검증 2026-08-03)

> **범위**: 외부 참고 문서 『풀이(Solution) 엔진』(기능 23~27: 단계별 풀이 생성 · 다양한 풀이법
> 생성 · 힌트 생성 · AI 채점 · 풀이 비교 — **WhyMath 전용이 아닌 일반적 EOS 틀**, Kiki 제공)을
> 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(교수학 금기·검증 권위·
> dead code 금기·표현≠의미·무한 온톨로지 금지) 안에서 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(같은 EOS 틀 시리즈 모듈 6~10, 2026-07-27) 답습.
> **결론**: 기능 23(생성·검증)·26(채점)은 상당 충족 — 다수 항목이 문서보다 *엄격*하다(검산 강제
> finalize·3상태 판정·클라 채점 CI 게이트). **기능 25의 힌트 *내용* 생성이 최대 실행 갭**, 24는
> 설계만(프롬프트·스키마 완비·소비 코드 0), 27은 전무. `SolutionPath` 실체화의 명시적 유보
> 조건("다중 풀이 생성이라는 소비처가 설 때" — 03 문서)이 이번 설계로 성립한다.
> 의도적 미채택 6건, 진짜 갭 설계 D1~D5, 실행 4건을 백로그에 등재했다(S4-09~12).
> 2차에서 D6·`S4-19` 1건을 추가했다.
>
> **2차 재검증(2026-08-03·§5)**: 같은 문서로 재점검 요청이 들어와 ①1차 판정을 현행 코드에
> 재대조 ②1차가 표에 넣지 않은 문서 2절(전체 구조에서의 위치·EOS 연계 구조 = **배선 축**)을
> 추가 crosswalk 했다. 판정 뒤집기 0(D1~D5 전건 유효)이고, 배선 축에서 **신규 갭 1건**을 찾아
> D6로 설계·등재했다 — 코치가 학생 풀이에 대해 *이미 산출해 클라에 노출까지 하는* 3상태 단계
> 검증 결과가 **어디에도 적재되지 않는다**(적재되는 건 별도 binary 검산 1비트뿐).

관련 정본: `03_content_generation.md`(SolutionPath 정본·동치성 정직 경계) ·
`03b_wh_s_solver_harness.md`(WH-S 3-tier 검증) · `04_pedagogy_engine.md`·
`04a_wh1_tutoring_harness.md`(답 미루기·힌트 경제) · `docs/strategy/core_feature_review_2026-07.md`
(#1 힌트 판정 — §1 기능 25의 층위 구분 참조) · `MEMORY.md` 결정 로그(2026-07-29).

---

## §1. 기능 23~27 ↔ WhyMath crosswalk 판정

### 기능 23. 단계별 풀이 생성 — **부분적: 생성·검증 라인 실가동 / 구조 좌석은 유보 해제 조건 성립**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 생성 흐름(조건 분석→개념 확인→공식 선택→계산→검산→정답) | WH-S `whs/harness.py:422` `run_solver` + 액션 10종(`ParseProblem`→`RetrieveSimilar`→`Decompose`→`ApplyStrategy`→`Verify`→`Finalize`…) + **verify 없는 finalize 하네스 거부**(검산이 구조적으로 강제) + 3-tier 검증(Tier1 수치+Tier2 SymPy). 620문 전수 실가동(`S2-02` done·`whs/corpus_replay.py`) | ✅ (검산 강제 — 문서보다 엄격) |
| Step 관리(번호·설명·사용 개념·공식·이유 Why·중간 결과·예상 오개념) | `schemas/v1.1/solution_path.schema.yaml`에 완전 명세(order·content·concept_node_id·justification 3참조·common_errors·reasoning_type 7종). 단 **Pydantic·ORM·writer 0** — 현 저장 `verified_solutions.solution_path` JSONB는 평문 표현식 리스트(개념·Why 메타 0). `ReasoningType`만 `schema/enums.py:535`에 기실체화 | ⚠️ 갭 → **D1** |
| 단계 영속·조회 | `db/models/problem.py:314` `problem_step` 테이블 실재하나 **writer 0건**(빈 테이블 위 읽기 API `api/problems.py:122` `GET /v1/problems/{id}/steps`) · `l4/learning_scene.py:132` `solution_path_id` 참조가 댕글링(`l4/scene_generation.py:23` "SolutionPath Python 구현 후속" 자인) | ⚠️ 갭 → **D1** (writer·reader 동반 해소) |
| 단계별 시각화 자료 | 시각화는 참조 키 축(`visualization_card_keys` 선례) — 유형 확장은 기존 추적 | ⏸ `S4-03` 승계 |
| 학생 수준별 4단(초등 그림→중등 식→고등 논리→대학 증명) | 타깃 페르소나 밖(한국 중·고, A 고3 MVP). 중·고 *내* 적응은 기존 축 실재: LTHC 발화 조정(`l4/lthc/adapt.py`)·`decide_hint_level` mastery 양방향 조정·정의 레지스터(`S4-05`) | 🚫 4단 축 → **§2-②** / 중·고 내 적응 ✅ |
| LLM이 실제 "풀어내는" 두뇌 | `SolverPolicy` 실구현은 `ScriptedPolicy`(테스트)·`ChainReplayPolicy`(코퍼스 재생)뿐 — S2-02 정직 고지("replay 620/620 verified는 파이프라인 무결성 지표이지 풀이 능력 아님") 승계 | §4-③ 트리거 |

### 기능 24. 다양한 풀이법 생성 — **설계만: 프롬프트·스키마·경계 문서 완비, 소비 코드 0**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 전략 탐색→전략별 풀이 생성 | `docs/prompts/multi_solution_gen.md` 완성(접근 2~3개 선택·JSON 출력·"학생 본인 풀이 후 대안 노출" 원칙 내장) — **코드 소비처 0**. 프롬프트 접근 카테고리(`:28` "비유적")가 스키마 enum 6종(`visual` 포함·비유 없음)과 **불일치**(실측) | ⚠️ 갭 → **D2** (스키마 정본으로 정합) |
| 풀이 전략(approach) 관리 | `solution_path.schema.yaml:54` `approach_type` 6종(algebraic·geometric·combinatorial·inductive·visual·backward) 명세 완비. 코드에는 **거버넌스 테스트의 비교 상수로만** 존재(`tests/backend/l1/test_strategy_governance.py:42` — 3축 disjoint 동결) — 소비 enum 좌석 0. `l1/strategy_graph/`(StrategyNode 8종)는 **직교 축**(Polya 계획 발상 — 문서 자체가 disjoint 선언) | ⚠️ 갭 → **D2** |
| 난이도 평가·계산량·직관성·추천 대상 메타 | 프롬프트 출력에 `difficulty`·`elegance`(1-5)·`educational_value` 설계돼 있으나 저장 좌석·산출 코드 0 | ⚠️ → **D2**(생성 시 산출·`ai_estimated`) + **D4**(기계 지표) |
| 다중 풀이 저장 여지 | `db/models/verified_solution.py` — `problem_id` UNIQUE 없음(다중 허용) + `strategy_tag`(nullable) 좌석 기존재 | ✅ 부분 (여지만) |
| 교육과정 적합성 | 문항-성취기준 태그 축 기존재(콘텐츠 공통 규약 — 풀이 전용 축 불요) | ✅ |

### 기능 25. 힌트 생성 — **부분적: 레벨 *결정*은 구현·GA / 레벨별 *내용*은 정적 템플릿 — 최대 실행 갭**

> **층위 구분** (`core_feature_review_2026-07.md` #1 "AI 튜터(힌트) 🟢 완전 구현" 판정과 모순
> 아님): 그 판정은 *레벨 결정·답 미루기 사다리* 축이고, 이 절의 갭은 *레벨별 힌트 콘텐츠의
> 생성·검증·영속* 축이다. 현 발화는 문제 무관 정적 템플릿이라 "무엇을 물을지"는 있어도
> "이 문제의 이 단계에서 무엇을 가리킬지"가 없다.

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| Level 점층(1→2→3→4) | `l4/hint_deferral.py:24` `HintLevel Literal[1,2,3,4]`·`:79` `decide_hint_level`(막힘 5턴 임계·좌절/답 요구 토큰·mastery ZPD 양방향 조정) + `l4/metacognitive_trigger.py` hint 3·4 자가검산 점층 + `api/coach.py` `_log_hint_event` | ✅ |
| "Level 4 → 정답 공개" | 4단계(전체 풀이)는 **PRD 척도 밖 안전망**(`hint.schema.yaml:23` — Hint 엔티티 level enum은 1~3뿐·4는 "마지막 수단, 학습 곡선 분석과 함께만") + "가능한 가장 빠른 단계에서 멈춤"(`04_pedagogy_engine.md:35`) + 정답 억제 백스톱·`detect_answer_leakage` | ✅ (정답 공개를 기본 경로화하지 않음 — 문서보다 엄격) |
| 레벨별 힌트 **내용** 생성 | 실제 발화 = Polya 단계 정적 템플릿 4개(`l4/polya/prompts.py:43-76`) + verify 자가검산 점층 문구 2개가 전부. 문제·단계 맥락 힌트 생성기 0 | ⚠️ 갭 → **D3** (최대 실행 갭) |
| 힌트 영속·verified 게이팅 | `hints` 테이블 없음 — **HintNode Persistence 의도적 연기**(`MEMORY.md:1231` 2026-07-08: writer 0·reader 0 상태 신설은 dead code. 도입 전제 3종 ①generation ②validation ③serving 중 실 writer+reader 실재 시) | ⚠️ → **D3** (연기 해제 전제를 한 슬라이스로 충족) |
| 힌트 유형 6종(개념·공식·계산·그림·질문형·오개념 교정) | 신규 유형 enum 불채택 — 기존 3축이 전량 커버(§3 D3 crosswalk 표): 질문형=`socratic_category` 6종, 오개념 교정=`l4/misconception/intervene.py` 결정 트리(반례·거꾸로 등 패턴 개입 — 독립 축), 개념/공식/계산/그림 노출=`HintReveals` 4불리언+`revealed_concept_ids` 정량화 | 🚫 신규 분류축 → **§2-⑤** / 기존 축 ✅ |
| KPI "답 미루기 도달 깊이 2.5+" 측정 | 정수 `hint_level` 로깅만 — `reveal_score`(0~1·`hint.schema.yaml:172`) 미기록·측정 기반 없음 | ⚠️ → **D3** acceptance |
| 스캐폴딩 페이딩(3→2→1→0)·개입 금지 타이머 | `04a_wh1_tutoring_harness.md:452` §11.2 설계만(`hint_economy` 상태·도움 감소 곡선) — 파일럿 실측 없이 튜닝 불가 | §4-① 트리거 |

### 기능 26. AI 채점 — **부분적(강함): 검증·오류 위치·오개념 진단 실가동 / '점수'는 의도적 미채택**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 수식 파싱→정답 비교 | `l3/verify_answer.py`(Tier1 수치 검산) + `l3/solution_set.py`(해집합 보존 동치·연쇄 등식·근 나열·진부분집합 가드) | ✅ |
| 풀이 구조·계산 검증 | `l3/verify_step.py` **3상태**(correct/incorrect/unverifiable — 판정 불가를 정직 표시) + `l3/verify_solution.py:82` `first_incorrect_index`·`unverified_ratio` + `api/verify.py` 3 엔드포인트(stateless) | ✅ (3상태 — 문서보다 엄격) |
| 오류 위치·오개념·개선 방법 | `l4/solution_coaching.py` `error_span` + `l4/misconception/` ~40파일(diagnose→hypothesis→judge→intervene·pgvector 의미 매칭) + 선수 개념 코칭 추천 | ✅ |
| **점수·부분점수·등급** | 불채택 — 정본 대체 좌석: 3상태 검증 판정 + BKT/IRT 숙달도(`MasteryState`). (`harness/pedagogical_rubric.py`는 *튜터 발화* 채점 — 학생 채점 아님) | 🚫 → **§2-①** |
| 표현·서술 감점 | 부정 피드백 정서 강화 금지(`l4/tone_filter.py`가 최종 게이트) | 🚫 → **§2-⑥** |
| 논리 검증(근거 Why 확인) | 0 — 단 구조 좌석(justification 3참조)은 D1이 만들고, 1차 invariant(참조 실재·전방참조 금지·비순환)는 D1 테스트에 흡수 | ⚠️ → **D1**(1차) + **D5**(결선 페이퍼) |
| 누락 단계 검출 | 0 — `verify_solution`은 인접 전이만 검사. 모범 SolutionPath 정렬이 전제(D1 착지 전 불가능) | ⚠️ → **D5** (페이퍼 설계) |
| PRM 단계 스코어러 | `whs/prm_builder.py`는 학습셋 **빌더**만 — `data/corpus/whs_prm_v0/prm_dataset.jsonl` 1,282쌍 전건 `prm_score:null`(날조 금지)·`docs/prompts/prm_verification.md` 소비처 0·ROADMAP:68은 체크박스만(백로그 미등재 — 부록에 정직 기록) | §4-② 트리거 |
| 자유 텍스트→단계 분해 | 자동 분해는 백엔드("L5 책임" 유보)·L5 양쪽 0. **현행 정책은 자동 분해가 아니라 검증 가능 묶음 제출 유도**(`S3-05` 입력 UX + `S3-06` 자연 표기 확장 — done) | ⚠️ §4-④ 트리거 (인접 축이 현행 정책) |
| 손글씨(OCR) 채점 | `l5/ocr/` 파이프라인 실재(검출·라우팅·인식 4종·SymPy 파스 검증) + `api/ocr_handoff.py`(OCR→coach 변환) + 저신뢰(<0.8) 게이팅(`verification_ocr_gated` — 거짓 지적 방지) | ✅ |
| 서술형·증명 채점 | `verify_step`이 설계상 unverifiable 반환(04a R5) — 학생 대면 증명 교수는 기존 추적 | ⏸ `S4-02` 승계 (D5 참조 연결) |
| 채점 위치(서버 단일) | 클라이언트 수학 판정 금지 CI 게이트(`ARCH-10`) + QuizMode 데모 예외 공식화(`ARCH-12`) | ✅ (문서보다 엄격) |

### 기능 27. 풀이 비교 — **없음(코드 0): 동치성 정직 경계·비교 스키마는 정본 기존재, '자동 최적 선택'은 미채택**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 비교축(풀이 길이·계산량·직관성·오류 가능성·일반화·적합성) | 코드 0. `whs/solution_bank.py:52` `solution_fingerprint`는 **정확 일치 dedup만**(docstring "다중 풀이 본질적 동치는 못 잡는다" 자인 — 예고된 후속) | ⚠️ 갭 → **D4** (기계 산출 지표만 자동) |
| 동치 풀이 군집 | `equivalence_cluster_id` 스키마만(`solution_path.schema.yaml:115` — "확정 동치가 아니라 검수 거친 동치 후보 군집")·코드 0. 판정 설계 정본 기존재: `03_content_generation.md:155-169` 휴리스틱 1차(편집거리+코사인+최종답 SymPy+approach_type) + **사람 검수 2차** — "미해결 연구 난제·제품 기능으로 단정하지 않는다" | ⚠️ 갭 → **D4** (정본 설계의 구현화) |
| **AI 자동 추천·최적 풀이 선택** | 불채택 — 동치성 정직 경계 + AI 자기승인 금지 + 단일 '최적' 라벨은 다양성 학습 취지(`multi_solution_gen.md:3` "본인 풀이 후 노출되어 다양성 학습")와 충돌 | 🚫 → **§2-④** (노출 *순서* 개인화는 §4-⑤) |
| 학생 수준별 추천 | `02_learner_model.md:105` `MasteryState.preferred_solution_style` 스키마만·코드 0 — L2 추적이 선행돼야 함 | §4-⑤ 트리거 |
| 교사용 수업 설계·다중 풀이 갤러리 | L7 Phase 3(ROADMAP:164 — Live Problems 모델). 패드 플래그십 "다중 풀이 비교"(`05_interaction.md:30`)의 UI 착지도 동일 단계 | ⏸ Phase 3 승계 |

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

문서 틀의 다음 항목은 **채택하지 않는다**. 각각 CLAUDE.md 협상 불가 조항과 1:1 대응한다.

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | 학생 대면 점수·부분점수·등급 채점(기능 26 "채점 결과: 점수") | "정답을 빠르게" KPI 금지·학습 시간·정답률 우열 게임화 금지. 정본 대체 좌석: 3상태 검증 판정(unverifiable 정직 표시) + BKT/IRT 숙달도 추정(L2 `MasteryState`) — 점수는 서열화 신호, 숙달도는 학습 상태 추정으로 용도가 다르다 |
| ② | 초등 그림→대학 증명 4단 수준 축(기능 23) | 타깃 페르소나(한국 중·고, A 일반고 고3 MVP) 밖 — enum 선점은 소비처 없는 저작 부채. `S4-05` 선례("초등·영재 레지스터는 페르소나 v1.5/v2.0 도달 시 enum 추가") 동형 처리. 중·고 내 수준 적응은 LTHC·mastery 조정·정의 레지스터 기존 축 |
| ③ | AI 생성 풀이·힌트의 무검증 학생 노출(기능 23·25 함의) | LLM 응답을 검증 없이 학생에게 제공 금지 — 풀이는 SymPy 검증 통과분만 뱅크(WH-S 불변식), 힌트는 `verified=false` 서빙 불가(`hint.schema.yaml` invariant)·`ai_estimated` 검수 게이팅 |
| ④ | 동치 자동 확정·"최적 풀이" 자동 선정(기능 27) | 동치성은 미해결 연구 난제 — "휴리스틱으로 좁히고 사람이 닫는다"(03 정본)·AI 자기승인 금지·"확실하지 않을 때 자신 있게 말함" 금지. 군집은 후보+사람 검수, '최적' 단일 라벨은 다양성 학습 취지와 정면 충돌 |
| ⑤ | 힌트 유형 6종 신규 분류 enum(기능 25) | 소비처 없는 추상·무한 온톨로지 금지 — 기존 3축(socratic_category 6종·HintReveals 정량화·오개념 개입 패턴)이 전량 커버(§3 D3 crosswalk 표). 4번째 분류축 신설은 축 혼동(`test_strategy_governance.py` 3축 disjoint 동결의 취지) |
| ⑥ | 표현·서술 감점형 채점(기능 26 "채점 대상: 표현·서술") | 부정적 피드백 정서 강화 금지 — 서술 피드백은 감점이 아니라 구조 피드백·질문형(`S4-02` 축·04a R5 unverifiable 경계)으로만. 톤 필터가 최종 게이트 불변 |

---

## §3. 설계 D1~D5 (진짜 갭의 WhyMath 정합 설계)

> 실행 우선순위(문서 제안 23→25→26→24→27의 재배열): **D1(23 좌석) → D2(24)·D3(25) 병행 →
> D4(27)**, 26은 신규 실행 0(기존 실체 + D1 흡수 + D5 페이퍼). 재배열 근거: ⑴ 힌트 *내용*은
> 검증 앵커(sympy_verified 단계) 없는 즉석 생성이 §2-③ 위반이라 D1 산출물이 원천이어야 한다
> (문서의 23→25 순서가 WhyMath에선 *의존*으로 강화됨) ⑵ D2는 D1 유보 해제 조건(소비처) 그
> 자체라 직후로 승격 ⑶ 26은 이미 강함 ⑷ 비교(D4)는 다중 풀이 자산(D2)이 있어야 대상이 생긴다
> (현 뱅크는 정확 일치 dedup 후 사실상 문제당 1풀이).

### D1. SolutionPath/SolutionStep 실체화 (백로그 `S4-09`)

**목적**: 풀이 본문의 구조 좌석 — 단계당 사용 개념·이유(Why)·예상 오개념을 담는 자리를
만든다. 문서 기능 23의 "단계별 관리"를 표현≠의미(구조 정본·본문은 렌더러-중립 LaTeX) 안에서 수용.

- **유보 해제 논증**: `03_content_generation.md:151`은 "SolutionStep Pydantic/ORM 실체화는
  Phase 2 — *다중 풀이 생성이라는 소비처가 설 때*"로 유보했다. 이번에 그 조건이 성립한다:
  D2(`S4-10`)가 소비처로 서고, WH-S가 620문 실가동 중인 생산 라인의 출력이 평문 JSONB로
  새고 있다(신규 데이터 창조가 아니라 **이미 흐르는 데이터의 스키마 승격** — dead code 아님).
- **writer·reader 동반(협상 불가)**: writer = WH-S `bank_solution` 경로에 구조 승격 어댑터
  (평문 steps → Pydantic 검증 → 적재. 개념 ID 매칭 실패분은 사람 검수 큐 — L3 5개 핵심
  호출지점 중 "개념 ID 매칭" 규약). reader ① = `GET /v1/problems/{id}/steps`(`api/problems.py:122`
  — 현재 빈 테이블 위 dead API의 소생). reader ② = `l4/learning_scene.py:132`
  `solution_path_id` 댕글링 해소(`scene_generation.py:23` 자인 문구 삭제).
  **신규 학생 대면 노출 0** — 기존 표면의 소생·참조 무결성 회복만(파일럿 루프 비간섭).
- **좌석**: Pydantic은 `l3/`(스키마 yaml 1:1 — `SolutionPath`/`SolutionStep`/`Justification`).
  enum은 기존 단일 좌석 소비(`schema/enums.py:535` `ReasoningType` — 신설 금지). ORM은
  `solution_path` 테이블 신설(PK·problem_id·approach_type·concept_sequence·verified_by_human·
  equivalence_cluster_id nullable) + 기존 `problem_step`(`db/models/problem.py:314`)에 additive
  컬럼(solution_path_id FK·concept_node_id·reasoning_type·justification JSONB·common_errors·
  sympy_verified) — 테이블 증식 최소화.
- **경계**: `embedding` 컬럼은 **D4까지 유보**(소비처=군집이 설 때·임베딩 네임스페이스 거버넌스).
  수준별 4단 표현 미도입(§2-②). 본문 완전 AST화 미채택 승계(content = LaTeX+구조 태그).
- **검증**: 스키마 invariant 테스트(yaml `validation_invariants` 1:1 — order 1부터 연속·
  justification 전방/자기참조 금지·enum 폐쇄 밖 거부·참조 실재) + steps API 계약 테스트 +
  승격 카운트 리포트(620문 대비 매칭 성공/검수 큐 비율).

### D2. 다중 풀이 생성 파이프라인 (백로그 `S4-10`, depends `S4-09`)

**목적**: `docs/prompts/multi_solution_gen.md`의 **첫 소비처** — 전략 탐색→전략별 풀이→검증을
"라우터 경유 생성 → SymPy 전건 검증 → **통과분만** 뱅크"로 실행화한다. ROADMAP:67
"SolutionPath 다중 풀이" 체크박스의 백로그 실행화.

- **enum 실체화**: `ApproachType` 6종을 `schema/enums.py`에 신설(단일 좌석 규약 —
  `ReasoningType` 미러). `test_strategy_governance.py:42`의 리터럴 상수를 좌석 참조로 승격
  (3축 disjoint 동결 유지: strategy slug ∩ approach_type ∩ reasoning_type = ∅).
  `verified_solutions.strategy_tag` 자유 텍스트 → `approach_type` 승격.
- **프롬프트 정합**: 접근 카테고리를 스키마 정본 6종으로 정렬 — 실측 불일치 해소(프롬프트
  `:28` "비유적"은 enum에 없음·enum `visual`은 프롬프트에 없음. 스키마가 정본,
  "비유적"은 오개념 개입·정의 레지스터 `analogy` 축과 혼동 위험이라 제거).
- **산출·경계**: 문제당 approach_type 상이 2+ 풀이를 D1 `solution_path`로 적재. 주관 메타
  (`elegance`·`educational_value`·`difficulty`)는 저장하되 `ai_estimated`(학생 노출 게이팅).
  **오프라인 콘텐츠 공장 축** — 학생 대면 노출("본인 풀이 후 대안")은 §4-⑥ 유보.
- **검증**: 시드 스코프(예: `S2-01` 동등문제 일부) 실측 리포트 — 생성률·SymPy 검증 통과율·
  approach 다양성 분포. 검증 실패 건 뱅크 유입 0을 테스트로 동결.

### D3. 힌트 내용 생성기 + `hints` 영속 — HintNode 연기 해제 (백로그 `S4-11`, depends `S4-09`·`S3-01`)

**목적**: 레벨 *결정*(GA)과 레벨별 *내용*(정적 템플릿 4개) 사이의 최대 실행 갭. SolutionStep을
원천으로 graded 1~3 힌트를 **오프라인 사전 생성·검수**한다 — 검증 앵커(sympy_verified 단계)
없는 즉석 LLM 힌트는 §2-③ 위반이므로 D1 의존이 필연.

- **연기 해제 논증**: `MEMORY.md:1231`(2026-07-08 Deferred)의 도입 전제 3종을 **한 슬라이스로
  충족** — ① generation: 본 생성기(writer — `SolutionStep.hint` 원천 텍스트를 level 1~3으로
  전개: L1=주목할 개념 이름만(reveals_concept_names), L2=단계 흐름(reveals_step_flow·계산
  미노출), L3=부분 시연(reveals_partial_computation)) ② validation: 게이트 3종(level-reveals
  정합 invariant·`detect_answer_leakage` 재사용(`harness/pedagogical_rubric.py`)·정서 안전 톤
  필터 — 통과분만 `verified=true`) ③ serving: `api/coach.py` 답 미루기 결선이 정적 템플릿
  대신 해당 단계의 검수 힌트를 서빙(reader). 이때 비로소 `hints` 테이블 도입 — 연기 항목의
  미러 선례(구조=`curriculum_entry.py`·payload=`verified_solution.py`) 승계.
- **화해 승계**: spec level 1~3 ↔ runtime `hint_level` 1~4 — **Level 4(전체 풀이)는 Hint
  엔티티 밖 안전망 유지**(`hint.schema.yaml:23` 정본 그대로). `attempt_event`(힌트제공)와
  `hints`는 상보(이벤트 로그 ≠ 콘텐츠 카탈로그).
- **힌트 유형 crosswalk(§2-⑤의 근거)** — 문서 6유형은 기존 3축으로 전량 표현:

  | 문서 유형 | WhyMath 기존 축 |
  |---|---|
  | 질문형 힌트 | `socratic_category` 6종(clarification~meta) — "힌트는 질문으로 줄 때 가장 강력" |
  | 개념 힌트 | `reveals_concept_names=true` + `revealed_concept_ids`(level 1 전형) |
  | 공식 힌트 | 동일 축(공식=THEOREM/DEFINITION 개념 노드·formula 참조 키) |
  | 계산 힌트 | `reveals_partial_computation=true`(level 3 전형) |
  | 그림 힌트 | 시각화 참조 키 축(`S4-03` 유형 확장과 연동 — 별도 유형 아님) |
  | 오개념 교정 힌트 | `l4/misconception/intervene.py` 개입 패턴(반례·거꾸로) — 독립 축·reactive |

- **KPI**: `_log_hint_event`에 `reveal_score`(0~1) 기록 — "도달 깊이 2.5+"의 측정 기반 확보.
  `S3-04` 파일럿 측정 하네스 연동. 학생 대면 서빙 포함 → **`S3-01` 의존**(루프 검증 전 기능
  확장 금지 — `S4-05` 선례 동형).

### D4. 풀이 비교 메타·동치 군집 리포트 (백로그 `S4-12`, depends `S4-10`)

**목적**: 문서 기능 27을 "기계가 산출 가능한 것만 자동, 나머지는 후보+사람 검수"로 수용.
`solution_fingerprint` docstring이 예고한 후속의 실행.

- **3분할 원칙**: ⑴ **기계 산출 지표**(자동): 스텝 수·`concept_sequence` 길이(계산량 프록시)·
  `sympy_verified` 비율·`reasoning_type` 분포 — 빌드타임 비교 리포트(ARCH-17 오프라인 리포트
  동형·런타임 traversal 아님) ⑵ **주관 지표**(직관성·우아함): D2 생성 메타 인용(`ai_estimated`
  — 자체 산출기 안 만듦) ⑶ **동치 군집**: 휴리스틱 1차(`03:165` 정본 — 편집거리+최종답
  SymPy+approach_type+코사인) → `equivalence_cluster_id` **후보** 부여 → **사람 검수 2차 큐**
  (자동 확정 금지·crosswalk `ops promote` 선례 동형).
- **embedding 판정**: SolutionPath embedding 컬럼(D1 유보분) 도입 여부를 이 태스크에서 판정 —
  코사인이 휴리스틱 입력이므로 소비처 성립. 도입 시 임베딩 네임스페이스 거버넌스(cross-table
  코사인 금지) 준수.
- **미채택 재확인**: '최적 풀이' 라벨·자동 추천(§2-④) 없음. 학생 노출·갤러리 UI는 Phase 3
  유보(§4-⑥). 소비처: 콘텐츠 공장 검수 위생 + 향후 L2 `preferred_solution_style`의 재료.

### D5. 채점 심화 페이퍼 설계 — 누락 단계·논리 검증 결선 (태스크 신설 없음)

knowledge 리뷰 D2(P6 선행 설계) 선례 동형 — 설계만 확정하고 코드 0·태스크 0. 구현 트리거는
D1 데이터 축적 + `S3-04` 측정, 증명·서술 축은 기존 `S4-02`(notes에 본 설계 참조 연결).

- **누락 단계 검출**: 학생 스텝 시퀀스를 모범 `SolutionPath.concept_sequence`에 정렬(편집
  거리/LCS)해 미커버 필수 개념 노드를 "누락 **후보**"로만 산출 — 다중 풀이(동치 다양성) 때문에
  단정 금지(다른 approach로 건너뛴 것일 수 있음). 학생 대면은 소크라테스 질문형으로만
  ("이 단계에서 ○○는 어떻게 확인했어?" — unverifiable 정직 경계 동형).
- **논리 검증 결선**: justification 1차 invariant(참조 실재·전방참조 금지·비순환)는 D1 테스트에
  흡수. `reasoning_type`별 검증 결선(transformation→SymPy 동치, deduction→정리 참조 확인 등)은
  스키마 자체가 Phase 2 유보(`solution_path.schema.yaml:188`) — 유형별 결선은 §4-② PRM 축과
  함께 재론(지금 설계하지 않는다 경계 명시).

---

## §4. 잔여 연동 트리거 — 태스크화하지 않는 축 6종

지금 착수하지 않되, 어느 설계가 착지하면 자연히 풀리는 축. 등재 시점은 트리거 성립 시.

1. **스캐폴딩 페이딩·개입 금지 타이머·힌트 경제**(04a §11.2 전체) — 트리거: D3 착지 + `S3-01`
   파일럿의 도달 깊이·힌트 의존 분포 실측(데이터 없이 페이딩 정책 튜닝 불가).
2. **PRM 단계 스코어러**(`prm_dataset` 1,282쌍 축적 중·전건 score null) — 트리거: WH-S LLM
   정책 착륙(현 Ollama 도달 불가 실측) 또는 D2·D3 게이트에서 도구 검증만으로 부족이 실측될 때.
   ROADMAP:68은 체크박스만 — dead task 방지를 위해 지금 등재하지 않는다(부록 기록).
3. **WH-S LLM 솔버 정책**(Scripted/ChainReplay → LLM·MCTS-lite) — 트리거: 추론 인프라 도달
   해소(`S2-02` NOT 후속 승계). D2 생성 다양성의 상류이기도 하다.
4. **자유 텍스트/OCR→단계 자동 분해** — 트리거: 입력 계약 축(`S3-05`·`S3-06` — 현행 정책은
   묶음 제출 유도) 실측 한계 확인 + D1 구조 좌석. 학생 풀이 정렬은 D5 설계 참조.
5. **`preferred_solution_style` 추적·노출 순서 개인화**(L2→L4) — 트리거: D2 다중 풀이 자산 +
   파일럿 상호작용 데이터(추적할 대상과 신호가 먼저 있어야 함).
6. **학생 대면 다중 풀이 노출·비교 UI·갤러리** — 트리거: D2·D4 자산 + 파일럿. UI는 패드
   플래그십(`05:30`)·L7 Phase 3(ROADMAP:164). "본인 풀이 후 대안 노출" 원칙 유지.

---

## §5. 2차 재검증 (2026-08-03) — 판정 재대조 + 배선 축 crosswalk + D6

> 같은 외부 문서로 재점검 요청이 들어와 수행한 2차 패스. **1차(§1~§4)는 재작성하지 않는다** —
> 판정이 바뀐 것만 델타로 적고, 1차가 표에 넣지 않은 축을 추가한다.

### §5-1. 1차 판정 재검증 — **판정 변경 0**

1차 리뷰(07-29) 이후 머지된 커밋 중 풀이 축에 닿는 것을 대조했다.

| 커밋 | 풀이 축 영향 | 판정 델타 |
|---|---|---|
| `ARCH-21`(#662) QA 파이프라인 오케스트레이터 | `harness/qa_pipeline.py`가 기존 7축(코퍼스 감사·동치 canonicalize·개념그래프 도달성·크로스링크·prose leak·provenance·결함주입)을 **조립만**(신규 검사기 0·acceptance 제약) | 없음 — 검증 권위 서열의 게이트 조립이지 풀이 생성·검증 표면 변경 아님 |
| `S3-27`(#653) Problem↔ProblemType 백필 | 문항 *유형* 축 해금(ARCH-18) | 없음 — 풀이 *구조* 축(approach_type·reasoning_type)과 직교(3축 disjoint 동결 유지) |
| `VIZ-01`(#654) 시각화 공급원 적재 | 시각화 학생 도달 0회 해소 | 없음 — 1차 §1 기능 23 "단계별 시각화 자료 ⏸ `S4-03` 승계" 유지(적재 입도가 *문제* 단위·*단계* 단위 아님) |
| `SEC-07/08/09/11` | 인가·PII·감사 축 | 없음 |

**D1~D5 전건 유효.** 백로그 상태(2026-08-03 실측): `S4-09`·`S4-10`·`S4-11`·`S4-12` **전건 `todo`**.
`S4-10`은 **병렬 세션**(`claude/whymath-solution-review-40xspg`)이 원격 claim 중 — 본 세션 착수 금지
(CLAUDE.md 병렬 세션 규약).

1차의 핵심 판정 2건은 이번에 코드로 재확인했다:

- **기능 26의 "3상태 ✅"는 *학생 도달*까지 성립**한다 — 클라가 `solution_steps`를 실제로 보내고
  (`src/mobile/lib/features/chat/application/chat_controller.dart:107`) 코치가 그것으로
  `verify_solution`을 결선한다(`api/coach.py:507-523`). 최근 갭 리뷰 3건(VIZ-01·NLP-01·REC-01)이
  반복 발견한 **"기능은 있는데 학생 도달 0회"** 패턴이 이 축에는 **해당하지 않는다**.
- **잔여물 1건(태스크 미등재)**: 독립 검증 클라이언트 `verifyApiProvider`
  (`src/mobile/lib/features/verify/data/verify_api.dart:48`)는 **`lib/` 소비처 0**(테스트만).
  코치 경로가 같은 검증을 수행하므로 *기능 갭이 아니라 중복 표면*이다. 제거/유지 판단은 모바일
  리팩터 시점 소관이라 태스크로 등재하지 않고 기록만 남긴다(dead task 방지).

### §5-2. 배선 축 crosswalk — 1차가 표에 넣지 않은 문서 2절

문서의 「WhyMath 전체 구조에서의 위치」·「EOS 관점에서의 연계 구조」 두 다이어그램은 *기능*이
아니라 **모듈 간 화살표**를 그린다. 1차 §1은 기능 23~27만 표로 다뤄 이 축이 비어 있었다.

| 문서 엣지 | WhyMath 현행 | 판정 |
|---|---|---|
| 교육과정·개념 DB → 풀이 | 성취기준 태그(콘텐츠 공통 규약) + `l2.get_primary_concept_id`(문항→PRIMARY 개념) | ✅ |
| 오개념 DB → 풀이 | `l4/misconception/` reactive retrieval(진단→가설→judge→개입) — **preload 금지 준수** | ✅ |
| 문제은행 → 풀이 | WH-S `whs/harness.py:422` `run_solver` → `verified_solutions` 뱅크(SymPy 통과분만) | ✅ |
| 교수전략 → 풀이·힌트 | `l4/pedagogy/runtime_selector.decide`(전략 선택·GA) + `l2/pedagogy_evidence.py`(처치 기록·PED-03)는 실재하나, **힌트 발화 자체는 문제 무관 정적 템플릿**(`l4/polya/prompts.py:43-76`) | ⚠️ 기존 **D3**(`S4-11`)이 이미 덮는다 — 신규 등재 금지 |
| **채점 → 학생 모델 업데이트** | 숙달 전파는 `api/me.py:679` `record_problem_attempt_mastery`(문제 단위 `is_correct` **1비트**)뿐. 코치가 산출한 3상태 단계 검증은 **적재 0** | ⚠️ **신규 갭 → D6** |
| 풀이 비교 → 학생 모델 | `MasteryState.preferred_solution_style` 스키마만·코드 0 | ⏸ 1차 §4-⑤ 트리거 승계 |

### §5-3. D6 — 라이브 3상태 단계 검증 결과의 적재 좌석 (백로그 `S4-19`)

**갭의 정확한 진술**: 스테이트풀 코치는 학생 풀이 1건에 대해 **서로 다른 두 검증**을 돌린다.

| | 계산 | 산출 | 어디로 가는가 |
|---|---|---|---|
| ⑴ 단계 검증 | `recommend_coaching_for_solution` 내부 `verify_solution`(`api/coach.py:523`) | **3상태** — `n_correct`/`n_incorrect`/`n_unverifiable`·`unverified_ratio`·`first_incorrect_index`·단계별 `evidence_weight`(1.0/0.5) | **HTTP 응답으로만**(`solution_coaching.solution_verification`) — 적재 0 |
| ⑵ 텍스트 검산 | `_log_verify_event`의 `validate_response(arithmetic_validator(), …)`(`api/coach.py:919`) | **binary** — 거짓 수치관계 적발 여부 | `attempt_event(검산결과)`에 `passed`+`error_kind`로 적재(`schema/event_data_contract.py:35` `VerifyEventData`) |

즉 **시스템이 이미 가진 가장 정밀한 채점 신호가 응답과 함께 사라진다.** 그 결과:

- 측정 계층 ①(verify 통과율)은 ⑵의 binary만 읽는다 — `harness/wh1_evaluation.py:302`의 description이
  "…비율(**binary**)"이라고 스스로 밝힌다.
- L2 환류는 문제 단위 1비트만 받는다(`record_problem_attempt_mastery(…, body.is_correct)`).
  `verify_step`의 `evidence_weight`(`l3/verify_step.py:127`)는 **`l3/` 밖 소비처 0**(실측: 문서 인용만).
- 라이브 3상태 카운트가 관측되는 유일 경로는 **shadow 하네스**(`harness/wh1_shadow.py:187`
  `_count_verify_verdicts`·S3-07)인데, 이는 ⑴과 **다른 계산**(LLM 하네스 트레이스)이고
  플래그 게이팅·무영속(로그 sink)·오프라인 수확(`wh1_shadow_harvest`)이다. 결정론 라이브 경로에는
  대응 좌석이 없다.

**D6-1단계(태스크 범위) — 적재 좌석 + 이중 회계**

- **계약 확장(additive)**: `VerifyEventData`에 선택 필드를 더한다 — `n_correct`·`n_incorrect`·
  `n_unverifiable`·`unverified_ratio`·`first_incorrect_index`·`ocr_gated`. 전건 기본 `None`이라
  단계 미제출 턴·기존 픽스처·기존 라이브 이벤트가 무손상(하위호환). `extra="forbid"` 계약이므로
  필드 추가가 **정식 확장 경로**다(`mode`·`persona` 선례 동형·S3-03).
- **writer(재계산 0)**: `_log_verify_event`가 핸들러가 **이미 손에 쥔** `solution_verification`을
  인자로 받아 싣는다 — 검증을 다시 돌리지 않는 순수 데이터 운반. binary `passed`는 **그대로 유지**
  (기존 ① 시계열 연속성 보존 + 두 검증기의 **이중 회계** — CLAUDE.md "핵심 판정치는 인프로세스
  이중 회계"·`ops/cost_probe` 선례).
- **reader**: `wh1_evaluation` ①을 *교체가 아니라 병기*로 승격 — `verify_pass_rate`(binary) 불변 +
  파생 `step_decision_rate`=(n_correct+n_incorrect)/전체 전이·`step_incorrect_rate` 신설. 표본 0이면
  **NO_DATA 정직 표기**(가짜 0 금지·기존 규약 승계). shadow 원장의 같은 3상태 분포와 **대조 가능**해져
  두 회계가 서로를 검증한다.
- **경계**: 신규 테이블 0·마이그레이션 0(JSONB `event_data` 안)·**신규 학생 대면 표면 0**·
  숙달 갱신 경로(`record_problem_attempt_mastery`) **무변경**. 미성년 PII 규약 준수 — 싣는 것은
  정수 카운트·비율·인덱스뿐이고 **학생 풀이 원문·단계 텍스트는 담지 않는다**(shadow `shadow.py:14`
  규약 동형).
- **검증**: 계약 왕복 테스트(구필드만 있는 이벤트 파싱 통과 = 하위호환 동결·신규 필드 왕복) ·
  writer 회귀(단계 미제출 턴의 payload 키가 기존과 동일) · ① 지표 회귀(기존 값 불변) ·
  NO_DATA 경로 · 원문 미포함 동결 테스트.

**D6-2단계(설계만·태스크 0) — 부분 크레딧 승격 판정**

단계 신호를 BKT에 실제로 반영할지는 **측정 후** 판정한다. 승격 전제: ⑴ 파일럿(`S3-01`)·측정
하네스(`S3-04`) 데이터에서 단계 신호가 정/오답 대비 **예측력 증분**을 보일 것 ⑵ 가중 반영이 BKT
비퇴화 제약(`p_slip + p_guess < 1`·`l2/bkt.py:46,77`)과 모델 B(역할 비대칭 부분 크레딧)의 기존
불변식을 깨지 않을 것. **협상 불가 경계 3종**:

- **힌트 사용을 감점 신호로 쓰지 않는다** — 도움 요청을 억제하는 설계는 답 미루기 사다리의 취지와
  정면 충돌하고 부정 피드백 강화 금기에 걸린다. 힌트는 숙달 추정의 *맥락 변수*로만 관측한다
  (측정 축 ⑤·⑧은 이미 존재 — D6-1단계는 힌트를 건드리지 않는다).
- **`unverifiable`을 오답으로 강등하지 않는다** — `evidence_weight` 0.5는 *할인*이지 부정 증거가
  아니다(3상태 정직 경계).
- **학생 대면 점수·등급 노출 0** — §2-① 승계.

**중복 경계(등재 전 확인)**

| 인접 태스크 | 축 | D6와의 관계 |
|---|---|---|
| `NLP-02-server-answer-grading-shadow` | *답안* 채점(`verify_answer` 파생)의 클라 보고 대조 | 다른 검증기·다른 산출 — D6는 *단계* 검증(`verify_solution`)의 적재 |
| `S3-07-shadow-transition-aggregate` | shadow 하네스 트레이스의 전이 카운트 | D6는 그 **결정론 라이브 미러** — S3-07이 선례이자 대조 상대 |
| `S4-11-hint-content-generation` | 힌트 *콘텐츠* 생성·영속 | D6-1단계는 힌트 미포함(측정 축 ⑤·⑧ 기존재) |
| `S4-09`(D1) | SolutionPath 구조 좌석 | **비의존** — D6는 기존 이벤트만 읽고 쓴다(병렬 착수 가능) |

---

## 부록 — 실측 근거·관련 코드

- WH-S 솔버 루프: `src/backend/whymath_backend/whs/harness.py:422`(`run_solver`·verify 없는
  finalize 거부) · `whs/solution_bank.py:52`(`solution_fingerprint` 정확 일치 dedup 자인) ·
  `whs/corpus_replay.py`(620문 실가동·`S2-02`)
- 구조 좌석 부재 실측: `db/models/problem.py:314`(`problem_step` — writer 0) ·
  `api/problems.py:122`(빈 테이블 위 steps API) · `l4/learning_scene.py:132`(`solution_path_id`
  댕글링) · `l4/scene_generation.py:23`("SolutionPath Python 구현 후속" 자인) ·
  `schema/enums.py:535`(`ReasoningType` — 유일하게 기실체화된 조각)
- 힌트 축: `l4/hint_deferral.py:24,79`(레벨 결정 — 구현·GA) · `l4/polya/prompts.py:43-76`
  (정적 템플릿 4개 — 내용 생성기 부재의 실측) · `MEMORY.md:1231`(HintNode Deferred·도입 전제
  3종·미러 선례) · `schemas/v1.1/hint.schema.yaml`(D3 필드 정본)
- 채점 축: `l3/verify_step.py`·`l3/verify_solution.py:82`·`l3/verify_answer.py`·
  `l3/solution_set.py`·`api/verify.py` · `l4/solution_coaching.py`(error_span·OCR 게이팅) ·
  `l5/ocr/`·`api/ocr_handoff.py` · `whs/prm_builder.py`(+`data/corpus/whs_prm_v0/prm_dataset.jsonl`
  전건 prm_score null 실측)
- 다중 풀이·비교 축: `docs/prompts/multi_solution_gen.md:22-28`(카테고리 불일치 실측)·`:50`
  (본인 풀이 후 대안) · `schemas/v1.1/solution_path.schema.yaml:54,115`(approach_type 6종·
  equivalence_cluster_id) · `tests/backend/l1/test_strategy_governance.py:42`(6값이 거버넌스
  상수로만 존재) · `03_content_generation.md:151`(Phase 2 유보 문구)·`:155-169`(동치성 정직 경계)
- 기존 추적 승계(중복 등재 금지): `S4-02-proof-learning-support`(증명·서술 — D5 참조 연결) ·
  `S4-03-visualization-type-expansion`(단계 시각화·그림 힌트 슬롯) · `ARCH-10`/`ARCH-12`(클라
  채점 게이트) · L7 Phase 3 갤러리(ROADMAP:164) · ROADMAP:67-68 체크박스 중 67은 `S4-09/10`으로
  실행화, 68(PRM 후보 평가)은 §4-② 트리거 관리(백로그 미등재 상태 정직 기록)

**2차 재검증(§5) 추가 근거** — 배선 축·D6:

- 채점→학생 모델 엣지: `api/me.py:679`(`record_problem_attempt_mastery(…, body.is_correct)` —
  문제 단위 1비트) · `l2/mastery_tracking.py:202`(모델 B 역할 비대칭 부분 크레딧) ·
  `l2/bkt.py:46,77`(비퇴화 제약 `p_slip + p_guess < 1`) · `l2/pedagogy_evidence.py:13`
  ("결과 축은 `/v1/me`에 배선돼 살아 있으나" — 처치 축 공백을 닫은 PED-03의 자인. D6는 그
  *결과 축의 입도* 문제라 별개)
- 두 검증의 분기 실측: `api/coach.py:523`(`recommend_coaching_for_solution`에 `solution_steps`
  전달 → 내부 `verify_solution`) vs `api/coach.py:919`(`_log_verify_event`의
  `validate_response(arithmetic_validator(), …)` — binary) · `api/coach.py:888-899`
  (docstring이 "**binary 검산**이지 3-state verify가 아니다"라고 자인) ·
  `schema/event_data_contract.py:35`(`VerifyEventData` — `extra="forbid"`·`passed`/`error_kind`만) ·
  `l4/solution_coaching.py:119-127`(3상태 결과가 응답으로 노출되는 좌석) ·
  `harness/wh1_evaluation.py:302`(① description "…비율(binary)")
- 3상태 관측의 유일 기존 경로(축이 다름): `harness/wh1_shadow.py:20,187`
  (`_count_verify_verdicts` — LLM 하네스 트레이스·플래그 게이팅·무영속·S3-07) ·
  `harness/wh1_shadow_harvest.py:1-12`(로그 수확 오프라인 파이프라인)
- 클라 도달 실측: `src/mobile/lib/features/chat/application/chat_controller.dart:107`
  (`solutionSteps` 전송) · `src/mobile/lib/features/verify/data/verify_api.dart:48`
  (`verifyApiProvider` — `lib/` 소비처 0·중복 표면 기록만·태스크 미등재)
