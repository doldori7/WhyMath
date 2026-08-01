# AI 추천(AI Recommendation) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-01)

> **범위**: 외부 참고 문서 『19. AI 추천』(기능 80 문제 추천 · 81 개념 추천 · 82 학습 시간 추천 ·
> 83 난이도 자동 조절, 세부 기능 57개 — **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki 제공)을 현
> 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(Layer Separation ·
> Concept Purity · reactive retrieval · 교수학 금기 · dead code 금지 · 침묵 실패 금지 · 측정 없는
> 도입 없음) 안에서 설계한 기록.
> **형식**: `nlp_module_gap_review.md`(같은 EOS 틀 시리즈 기능 66~69, 2026-07-31) 답습 —
> 시리즈 **10번째** 자매편.
> **결론**: 착수 가설("AI 추천이 거의 없다")은 **반증됐다** — `GET /v1/me/next-problem`이 IRT CAT ×
> BKT 약점 가중 × L6 모드 게이팅을 곱 결합해 이미 돌고 있다. 그런데 실측 중에 **더 큰 것이
> 뒤집혔다**: **추천 엔진의 입력 루프가 클라이언트에서 끊겨 있다**(§0-②). 학생 앱은
> `POST /v1/me/attempts`를 **한 번도 호출하지 않으며**, 그 결과 `problem_attempt`가 0행이라
> 추천 4기능 전부가 콜드스타트 기본값 위에서 돈다. 진짜 갭 4건을 설계(D1~D5, D5는 페이퍼)하고
> 실행 4건을 백로그에 등재했다. 의도적 미채택 9건 · 정직한 공백 9종 · 유보 발화조건 8건.
> 정본 stale 4곳을 이번 대조에서 실측으로 잡아 정정한다.

관련 정본: `02_learner_model.md`(L2 BKT·IRT·추천 인터페이스) · `04_pedagogy_engine.md`·
`04d_adaptive_pedagogy_engine.md`(교수법 선택·bandit) · `06_application_modes.md`(모드 게이팅·
자동 커리큘럼 정렬) · `04a_wh1_tutoring_harness.md`(§2.2 도구6 `select_probe`·ε-탐색 불변식) ·
`nlp_module_gap_review.md`(기능 66~69 · `NLP-02` 채점 권위 · §6 반복 실수 표) ·
`ai_tutor_module_gap_review.md`(기능 37~41 · `PED-04`·`PED-05` 승계) ·
`visualization_module_gap_review.md`(§6 반복 실수 선례) · `MEMORY.md` 결정 로그(2026-08-01).

---

## §0. 두 가지 전제 정리

### ① 착수 가설이 반증됐다 — 추천 알고리즘은 이미 프로덕션이다

이 문서는 "무에서의 설계"가 아니다. 대조 전에 **이미 가동 중인 자산**을 파일:라인으로 고정한다.
이 절이 없으면 다음 세션이 이미 있는 것을 다시 만든다.

| 축 | 실재 위치 | 내용 |
|---|---|---|
| **적응 출제(CAT)** | `api/me.py:1680` `recommend_next_problem` | θ 추정 → θ 근방 후보 **50개**(`_CANDIDATE_POOL_SIZE`, `:1555`) SQL 선별 → `l2/irt.py:236` `select_weighted_item`으로 (가중)정보량 최대 1건 |
| **측정 정밀도·중단 규칙** | `api/me.py:1666-1671` | `standard_error` + `measurement_sufficient`(SE ≤ `_TARGET_SE=0.3`, `:1559`) — CAT 중단 권고를 응답에 실어 호출자가 루프를 닫는다 |
| **약점 가중(BKT×IRT 융합)** | `api/me.py:1598` `_weak_concept_weights` · `:1619` `_load_weak_concept_weights` | `weight = 1 + BOOST·(1 − 최저숙달)`(`_WEAK_CONCEPT_BOOST=1.0`) — 평가 개념(`ASSESSED_ROLES`)만 |
| **모드 게이팅(L6)** | `l6/suneung/recommendation.py:54` `recommend_suneung_index` | L6 진실 게이트 재수행 × L2 CAT. `api/gating.py`에 **6개 모드** 엔드포인트(`/retake`·`/suneung`·`/school-progress`·`/thinking`·`/metacognition`·`/gifted`) |
| **개념 추천(기능 81)** | `l2/concept_diagnosis.py:71` · `weak_concept_recommendation.py:147/245` · `prerequisite_recommendation.py:230`(재귀 CTE) · `learning_path.py:143`(Kahn 위상정렬) | `/me/diagnosis/concepts` · `/me/weak-concepts` · `.../prerequisites` · `.../coaching` · `.../learning-path` |
| **교수법 추천(처치 축)** | `api/study.py` 공급 + `l2/pedagogy_evidence.py`(`evidence_event` 최초 writer) | 처치↔결과를 `session_id`로 묶는 좌석 |
| **오개념 표적 진단(선택 로직)** | `l4/misconception/probe_selection.py:175` `select_probe` · `:219` `plan_probe` | 정보이득 근사 + ε-탐색. 순수 함수·완비 |

**코퍼스 실측**(2026-08-01, `data/corpus/**`): 문항 **2,647건** · `distractor_map` 보유 **1,616건**
(오개념 id **64종**) · `difficulty_overall` **2,647/2,647**(100%) · **`irt_difficulty_b` 0건** ·
원자 그래프 **2,683노드 / 2,210엣지(전부 `prerequisite`)** · 개념 그래프 437노드 / 581엣지
(전부 `선수(prereq)`) · 오개념 카탈로그 **843건**.

즉 **"추천이 없다"가 아니라 "추천은 있는데 먹일 것이 없다"** 가 정확한 진단이다.

### ② 더 큰 반증 — 추천 엔진의 입력 루프가 클라이언트에서 끊겨 있다

Flutter 학생 앱이 호출하는 `/v1/` 엔드포인트는 **13개뿐이다**(전수 실측, 부록). 그 안에
**`POST /v1/me/attempts`가 없다.** 이것이 `ProblemAttempt`의 **서버측 유일 writer**이며
(`api/me.py:644`), 데모 시드(`scripts/demo/`)도 attempt를 넣지 않는다.

따라서 실사용에서 `problem_attempt`는 **0행**이고, 그 위에 선 모든 것이 콜드스타트 기본값으로
고정된다:

| 귀결 | 실측 근거 |
|---|---|
| θ = **0.0 고정** | `l2/irt.py:76` — `if not responses: return initial`(=0.0) |
| `standard_error` = null · `measurement_sufficient` = **항상 False** | `api/me.py:1666-1671`(응답 0 → SE 무한) |
| BKT 숙달 이력 0행 → 약점 가중이 켜져도 **전 후보 중립 1.0** | `api/me.py:1598-1615` — `1 + BOOST·(1−최저숙달)`에 먹일 숙달이 없다 |
| `irt_difficulty_b` **코퍼스 0건** → JMLE 보정이 한 번도 돌지 않음 → 난이도는 항상 휴리스틱 폴백 | `l2/ability_estimation.py:38` `resolve_item_difficulty_b`(COALESCE 폴백) |
| 앱이 실제로 부르는 `/me/diagnosis/concepts`가 **항상 빈 결과** | `l2/concept_diagnosis.py:71`(채점 이력 기반) |
| `POST /v1/scenes/weak-concept`이 **항상 404** | `api/scene.py:174` — "진단할 개념이 없습니다(채점 이력 부족)" |

**구조적 원인은 "클라가 호출을 빼먹었다"가 아니다 — 앱은 `is_correct`를 알 수 없다.**
`/v1/verify-solution`은 *단계 전이* 검증이고 **정답을 응답에 싣지 않으며**(`verify_api.dart:23`
— "정답을 알지 못하는 검증이라 응답엔 정답이 실리지 않는다"), `Problem` 클라 모델은 백엔드가
보내는 `answer` 키를 **의도적으로 선언하지 않는다**(`problems_api.dart:40-41`). 즉 이것은
**채점 권위 공백(`NLP-02`)의 하류 증상**이다.

`nlp_module_gap_review.md` D2는 이 축을 "학습자 모델 전체가 **미검증 클라이언트 불리언** 위에
서 있다"고 적었다. 이번 실측은 그보다 한 칸 더 나쁘다 — **그 불리언조차 오지 않는다**(§정정).

---

## §1. 기능 80~83 전수 대조 (세부 57개)

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·정본* 없음) / ⚠️ 진짜 갭 → D /
⏸ 기존 태스크 승계 / 🚫 의도적 미채택 → §2

### 기능 80 — 문제 추천

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 수준별 문제 추천 | IRT CAT — θ 근방 후보 50 → 정보량 최대(`api/me.py:1680`) | ✅ **단, θ=0 고정** → **D1** |
| 약점 기반 추천 | `_weak_concept_weights`(BKT 최저 숙달 가중) 실재 | ✅ **단, 기본 off·숙달 0행** → **D1** |
| 유형별 추천 | `problem_type_graph_v1` 17종 실재. 추천 축으로 미배선 | △ (§4-⑧) |
| 오답 유사 문제 | `problem_relation` 테이블 + `GET /problems/{id}/relations` 리더 실재, **writer 0**. `content_provenance.parent_problem_id`도 writer 0 | ⚠️ §4-③ |
| 심화 문제 추천 | 난이도 상향은 CAT이 θ 상승으로 자동 처리 | ✅ (경로 다름) |
| 복습 문제 추천 | 망각 역산 복습 큐 | ⏸ `S4-18` 승계 |
| 시험 대비 추천 | `mode=suneung` 게이팅 실재(단건). "세트"(묶음 출제) 개념 없음 | △ §4-④ |
| 개인 맞춤 추천 | 위 3축의 곱 결합이 정본 | ✅ **단, 도달 0회** → **D1** |

### 기능 81 — 개념 추천

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 선수 개념 추천 | `prerequisite_recommendation.py:230` 재귀 CTE(깊이 제한) | ✅ **단, 클라 소비 0** → **D1** |
| 연관 개념 추천 | 그래프에 `related_to`/`similar_to` traversal 없음(현행이 플레이북 준수) | 🚫 §2-⑥ |
| 심화 개념 추천 | `EXTENDS` enum·crosswalk 매핑은 있으나 **코퍼스 엣지 0건**(2,210 전부 `prerequisite`) | ⚠️ §4-① |
| 보충 개념 추천 | 선수가 아닌 *병렬 보강* 축 자체가 없음 | ⚠️ §4-② |
| 학습 순서 추천 | `learning_path.py:143` Kahn 위상정렬 + 순환 잔여 처리 | ✅ **초과 · 클라 소비 0** → **D1** |
| 개념 연결 추천 | 개념 점화 지도(그래프) | ⏸ `ARCH-11` 승계 |
| 취약 개념 추천 | `weak_concept_recommendation.py` + BKT×IRT 합의도(`concept_diagnosis.py:33`) | ✅ **초과 · 숙달 0행** → **D1** |
| 개념 복습 추천 | 시간축 복습 | ⏸ `S4-18` 승계 |

### 기능 82 — 학습 시간 추천

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 최적 학습 시간 | 없음 | 🚫 §2-⑧ |
| 학습량 추천 | 없음 | 🚫 §2-⑧ |
| 휴식 시간 추천 | 없음 | 🚫 §2-⑤ |
| 집중 시간 예측 | `focus_score`/`engagement_score` 컬럼 실재, **writer 영구 미신설 결정** | 🚫 §2-④⑤ |
| 학습 주기 추천 | 복습 간격(BKT `p_forget` 역산) | ⏸ `S4-18` 승계 → **D5** |
| 시간대별 효율 | 생산자 0(`learning_session` writer 0) | 🚫 §2-④ |
| 학습 스케줄 | 없음 | 🚫 §2-⑧ |
| 목표 시간 설정 | `target_*` 컬럼 실재, **reader 0** | ⏸ `S4-18` 승계 |

### 기능 83 — 난이도 자동 조절

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 실시간 난이도 조절 | CAT이 매 추천마다 θ 재추정 후 재선택 | ✅ **단, θ 갱신 입력 0** → **D1** |
| 정답률 기반 조절 | IRT 정보량 최대 = Rasch에서 **P≈0.5 지향**. 목표 정답률 밴드 개념 없음 | ⚠️ → **D4** |
| 속도 기반 조절 | `time_spent_seconds` 슬롯 실재(`AttemptSubmitRequest`), 추천 축 미배선 | ⏸ `S3-16` 승계 |
| 오답 패턴 반영 | `distractor_map` → 오개념 역추적은 실재(`l4/misconception/distractor.py`). **문항 추천으로 되먹임되는 경로 0** | ⚠️ → **D2** |
| 난이도 예측 | 규칙기반(`l3/equivalent/difficulty.py`) + IRT JMLE 보정 2축이 정본 | 🚫 §2-⑨ |
| 적응형 난이도 | 동상(CAT) | ✅ |
| 난이도 밸런싱 | 후보 풀 50 내 정보량 비교가 사실상의 밸런싱 | ✅ (경로 다름) |
| 학습자 반응 분석 | 정서·행동 텔레메트리 | ⏸ `S3-16` 승계 |

### 추천 요소·기준·분석 데이터·조절 기준 (틀의 4개 보조 목록 25항)

| 목록 | 항목 | 판정 요약 |
|---|---|---|
| **추천 요소**(7) | 학습 이력 · 정답률 · 소요 시간 · 오답 패턴 · 학습 목표 · 취약 영역 · 학습 스타일 | 앞 4개는 스키마 실재·입력 0(**D1**) / 학습 목표 ⏸`S4-18` / 취약 영역 ✅ / **학습 스타일 🚫 §2-⑩** |
| **추천 기준**(5) | 난이도 적합성 · 개념 연관성 · 학습 효과 · 시급성 · 다양성 | 난이도 ✅(**D4**) / 연관성 ✅(prerequisite) / **학습 효과 = 회계 0 → D3** / 시급성 ⏸`S4-18` / **다양성 = 축 없음 §4-⑧** |
| **분석 데이터**(6) | 풀이 이력 · 시간 데이터 · 오답 데이터 · 학습 패턴 · 진도 현황 · 목표 달성도 | 전부 **입력 0**(D1). 진도 현황은 L6 커리큘럼 오버레이가 별도 정본 |
| **조절 기준**(7) | 연속 정답 · 연속 오답 · 평균 정답률 · 소요 시간 · 힌트 사용 · 포기율 · 자신감 | 힌트 사용은 `l4/hint_deferral.py`가 이미 소비 ✅ / 자신감 = `confidence_self_reported` 슬롯 실재·Brier 좌석 실재(`harness/wh1_evaluation.py:35`)·입력 0 / 나머지 **입력 0**(D1) |

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | **단일 "AI Recommendation Engine" 컴포넌트** | **7계층 위반.** 정본은 L2(무엇이 약한가·능력) · L4(어떻게 가르칠까) · L6(어느 모드·커리큘럼 정렬)의 **분산**이다. 틀의 단일 박스는 개념도이지 배치도가 아니며, 하나로 합치면 L6가 수학 로직을 갖게 되고(`06_application_modes.md` "L6에 수학 로직 침투 금지") truth source가 이중화된다(유지보수 지옥) |
| ② | **협업 필터링**(유사 학생 기반 추천) | `02_learner_model.md:24` 기판정 — 임계 사용자 수 미만에서 신호가 없다. 더해 미성년 학습 데이터를 **학생 간 교차 활용**하는 설계라 "학생 풀이 데이터를 명시적 동의 없이 사용 금지"·"미성년자 개인정보 외부 공유 금지"와 직접 닿는다. 발화 조건은 §5-③ |
| ③ | **SM-2/FSRS 카드형 SRS** | 2026-07-29 결정 **승계** — 복습 간격의 단일 권위는 BKT `p_forget`이다. 별도 SRS 스케줄러는 같은 판단을 두 번 구현하는 이중 진실원천 |
| ④ | **`learning_session` 행 writer · `focus_score`/`engagement_score` 생산** | 2026-07-29 **영구 미신설** 결정 승계(`S3-16` acceptance ③). 컬럼이 있다는 것은 좌석이 있다는 뜻이지 채워야 한다는 뜻이 아니다 |
| ⑤ | **집중 가능 시간 예측 · 피로도 추정 · 휴식 타이머** | 생산자 0인 데다, 학생 대면으로 정서·피로 라벨을 붙이는 설계다. "부정적 피드백을 정서적으로 강화하는 표현 금지" + "무자비한 게임화·중독성 설계 금지"의 인접 영역이라 측정 근거 없이 열지 않는다 |
| ⑥ | **연관 개념 추천**(`ANALOGOUS_TO`/`CONTRASTS` traversal) | **구축 플레이북 금기** — `similar_to`/`related_to`를 traversal에 사용 금지(관계 폭발 → 순환참조 → AI 추론 실패 연쇄). 현행 백엔드에 해당 traversal 소비처가 **0건**이라 이미 준수 상태이며, 이를 "빠진 기능"으로 오독해 채우면 불변식을 깨뜨린다 |
| ⑦ | **성장 곡선 예측 · 목표 점수 예측** | 2026-07-29 "점수·등급 예측 미채택" 승계. "정답을 빠르게"를 KPI로 쓰지 않는다는 금기의 연장 — 예측 점수는 곧 서열이다 |
| ⑧ | **주간 학습 스케줄 · 하루 학습량 자동 생성**(82) | "학습 시간·정답률만으로 우열을 매기는 게임화 금지"에 정면으로 닿고, 생산자(시간 데이터)도 0이다. 시간축에서 정본이 인정하는 것은 **분량**이 아니라 **간격**이다(D5) |
| ⑨ | **별도 "AI 난이도 예측" 모델**(83) | 규칙기반(`l3/equivalent/difficulty.py`)과 IRT JMLE 보정(`l2/irt.py`)의 **2축이 이미 정본**이다. 세 번째 축은 이중 진실원천이고, JMLE는 실응답이 쌓이면 자동으로 정밀해진다 — 필요한 것은 새 모델이 아니라 응답이다(D1) |
| ⑩ | **학습 스타일**(시각형/청각형 등) 기반 추천 | 학습 스타일 이론은 교육 연구에서 **효과가 반복 반증**된 축이다. 정본이 개인차로 인정하는 것은 스타일이 아니라 **숙달 상태·오개념·Polya 단계**다. "교수학적 정확성"(우선순위 #3)이 "사용자 경험"(#5)을 이긴다 |

---

## §3. 진짜 갭 설계

### D1 — 추천 엔진의 입력 루프가 클라에서 끊겨 있고, 그 사실이 어디에도 안 보인다 (최우선·`REC-01`)

**문제**: §0-②가 실측 그 자체다. `problem_attempt` 0행 → 추천 4기능 전부가 콜드스타트 기본값
위에서 돈다. 그런데 **그 상태가 어떤 리포트에서도 "미도달"로 보이지 않는다** — 추천은 성공적으로
문항을 돌려주고(θ=0 근방), 진단은 빈 배열을 돌려주고, 씬은 404를 돌려준다. 전부 *정상 응답*처럼
읽힌다.

**같은 축의 두 번째·세 번째 미도달** — 셋 다 "켜져 있는지 보이지 않는다"라서 한 태스크로 묶는다:

1. **개인화 스위치가 기본 off** — `?prioritize_weak_concepts` 기본 false(`api/me.py:1566-1571`,
   "slice 12~15 동작 보존"). 모바일은 `problems_api.dart:27` 기본값 그대로이고,
   `diagnosis_controller.dart:29` `load()`를 `problem_screen.dart:36/68`이 **인자 없이** 호출한다
   → 약점 가중이 학생에게 적용된 적 **0회**. `?mode=suneung`도 호출 0회다.
2. **개념 추천(기능 81) API 전군이 클라 소비 0** — `/me/weak-concepts` · `.../prerequisites` ·
   `.../coaching` · `.../learning-path` · `/gating/*` **6종** · `/study/{objective_id}/study`.
   학생 도달은 `POST /v1/scenes/weak-concept`이 내부적으로 최약점 1개를 쓰는 **간접 경로 하나**
   뿐이고, 그것마저 attempt 0행 때문에 항상 404다.
3. **응답이 무엇이 적용됐는지 말하지 않는다** — `NextProblemResponse`(`api/me.py:1653`)의 5필드
   어디에도 "어떤 가중 축이 실제로 붙었는가"가 없다.

**정직한 부분과 아닌 부분을 가른다**: **단건 응답은 이미 정직하다** — `standard_error=null` ·
`measurement_sufficient=false`가 표본 0을 구분해 준다. 없는 것은 **집계 도달 관측**이다.
"추천이 몇 번 요청됐고 / 그 중 몇 번이 실측 θ 위에서 계산됐고 / attempt가 몇 건 적재됐는가"를
답하는 좌석이 없다.

**핵심 판단**: **클라 배선(답 제출 UI·attempt POST)은 이 태스크 범위 밖이다.** 앱이 `is_correct`를
알 수 없는 것은 `NLP-02`(서버측 채점 shadow)가 다루는 축이고, 권위 이관 판단은 그 관측의 결과로
한다(`NLP-02` §5-②). 이 태스크의 목표는 **꺼져 있음을 보이게 하는 것**이다 — `NLP-01`의
"활성화가 아니라 가시화" 판단과 동형.

**정합 설계** (신규 스키마 0 · 마이그레이션 0 · 신규 EventType 0 · 클라 배선 0)
- **① 응답 정직 표기**: 적용된 가중 축 목록 · 후보 풀 크기 · 약점 가중이 실제로 붙은 개념 수 ·
  후보 0 사유. **"적용 안 됨"과 "적용했는데 신호가 없음"이 구분**되어야 한다.
- **② 추천 도달 리포트**: 추천 요청 수 / 실측 θ 기반 비율 / `problem_attempt` 적재 건수 /
  개인화 가중 적용 건수 / 후보 0 사유별. **0건일 때 "0건 통과"가 아니라 "미도달"**로 표시하는
  이중 회계(`VIZ-01` 적재 0행 · `NLP-01` OCR 비활성 · `ops/cost_probe` 선례).
- **③ `NLP-02` 전제 정정**: `NLP-02` acceptance ①은 "`POST /v1/me/attempts`에 `student_answer`가
  온다"를 전제하는데 **호출 자체가 0회**다. 전제 미성립을 태스크 notes에 실측으로 등재한다.

**dead code 금지 충족**: 신규 테이블 0. 추천 엔진·개념 추천 API는 이미 실재 — 관측만 추가한다.
**측정 없는 도입 없음**: 도달 카운터가 0이면 0으로 보인다(현재는 **아무것도 안 보인다**).
**변별력**: attempt를 1건 주입하면 "미도달"이 실제로 해제되는지 실측 → 되돌려 다시 "미도달"이
나오는지 실측. 성공/실패가 같은 값을 내면 이 설계 자체가 실패다.

**acceptance 후보**
1. 도달 리포트가 attempt 0행 상태에서 **"미도달"**을 내고, 1건 주입 시 해제됨을 실측(양방향).
2. `next-problem` 응답이 적용 가중 축을 정직하게 싣고, `prioritize_weak_concepts` on/off가
   응답에서 구분됨(회귀 0 — 기존 5필드 불변).
3. 리포트가 **CI에서 실제로 실행**되는지 확인(OPS-03·OPS-10 — "저장소에 존재함"과 "돌아감"은 다르다).
4. 범위 밖 동결: 클라 기본값 전환·attempt POST 배선·화면 신설은 하지 않는다(`NLP-02` 결과로 판정).

**의존**: 없음(즉시 착수). **태스크**: 신설 — `REC-01-recommendation-reach-observability`.

---

### D2 — 오개념 축이 문항 추천에 연결된 적이 없다 (`REC-02`)

**문제**: WH-1 도구 8종 중 **도구6 `select_probe`가 라이브 경로에서 구조적으로 항상 실패한다.**

`harness/wh1_llm_policy.py:143`의 `probe_candidates: Sequence[ProbeCandidate] = ()`를 채우는
**프로덕션 호출자가 0건**이다. `LLMTutorPolicy`를 구성하는 곳은 저장소 전체에 둘뿐이고
(`wh1_primary.py:115`·`wh1_shadow.py:261`), **둘 다 `outside_mids`만 넘기고 `probe_candidates`는
넘기지 않는다.** 따라서:

```
probe_candidates = ()  →  SelectProbeAction(candidates=[])  (wh1_llm_policy.py:420)
                       →  plan_probe([], ...)               (wh1_loop.py:453)
                       →  selection is None
                       →  "판별 문항 없음(억지 매칭 금지)"   (wh1_loop.py:472)
```

**변별력 0**: `:472`의 문구는 *정상 폴백*처럼 읽힌다. 후보를 공급했는데 매칭에 실패한 경우와,
후보가 애초에 0개인 경우가 **같은 값**을 낸다. CLAUDE.md "변별력 없는 검증 스텝 금지"(2026-07-17
등재)의 런타임판이며, `NLP-01` D1(OCR 503 무변별)과 **같은 형태**다.

더해 ε-탐색 턴(`wh1_loop.py:463`)에서는 `is_exploration=True`인 선택이 없으면 **거부**되므로,
후보 0 상태에서는 ε 턴마다 도구6이 두 번 실패한다(거부 → 없음).

**재료는 이미 적재돼 있다** — 신규 컬럼·마이그레이션 0으로 착지 가능하다:

| 필요한 것 | 실재 위치 | 규모(실측) |
|---|---|---|
| 문항↔오개념 태그 | `Problem.distractor_map` JSONB(`db/models/problem.py:151`) — 원소 = `{choice_index, misconception_id, op_code?}` | **1,616문항 · 오개념 64종** |
| 난이도 | `difficulty_overall` → `l2/ability_estimation.py:38` `resolve_item_difficulty_b` | **2,647/2,647(100%)** |
| **프로브 후보 자격(둘 다 보유)** | 위 둘의 교집합 | **1,616문항** |
| 선택 로직 | `probe_selection.py:175/219` — 정보이득 근사 + ε-탐색 | 완비·순수 |
| 활성 가설 | `l4/misconception/hypothesis_store.py`(감쇠·강화·최대5캡·영속) | 완비 |

`distractor_map`의 현 유일 소비처는 `l6/metacognition/gating.py:118/157`이 **개수만** 세는 것이고,
**`misconception_id` 값을 읽는 코드는 0**이다. 오개념↔문항 역인덱스는 데이터로 존재하나 한 번도
질의된 적이 없다.

**정합 설계** (신규 스키마 0 · 마이그레이션 0 · L4 순수 계약 유지)
- **① L1 역인덱스 조회 좌석**: `distractor_map` JSONB 값 매칭으로 `mids → 문항`을 조회한다
  (미응답 제외 · 난이도 보유만). **조회 좌석이며 선택 로직은 담지 않는다.**
- **② 하네스 주입**: `wh1_primary`가 **활성 가설이 선 뒤** 가설 mids + θ로 후보 풀을 조립해
  정책에 전달한다. **reactive retrieval 준수** — 오개념을 초기 context에 preload하지 않는다는
  불변식은 유지된다(후보는 프롬프트가 아니라 정책 보유값이며, 기존 `outside_mids`와 같은
  "사적 probe 컨텍스트" 계약을 그대로 따른다).
- **③ ε-탐색 성립**: 탐색 턴에는 활성 세트 **밖** mids도 후보에 포함해야 §2.2 규칙2가 성립한다.
  안 하면 ε 턴마다 probe가 거부된다.
- **④ 후보 0의 사유별 계상**: (가설 없음 / 오개념 미태깅 / 난이도 부재 / 전부 응답함)을 구분해
  구조화 로그·리포트에 남긴다. **침묵 실패 금지** — `l2/axis_exclusions.py` 사유 계상 패턴 답습.
- **⑤ 7계층**: L1 조회 → 하네스 주입 → L4 순수 선택. **L4는 DB를 계속 모른다.**

**dead code 금지 충족**: `select_probe`/`plan_probe`/`ProbeCandidate`가 이미 실재하고 테스트도
있다 — 없는 것은 **공급선 하나**다.
**변별력**: 배선 전후로 `select_probe`의 `ok=True` 건수가 **0 → >0**으로 달라져야 한다.

**acceptance 후보**
1. 활성 가설이 있는 턴에서 후보 풀이 실제로 비지 않음을 실측(코퍼스 1,616문항 기준).
2. ε-탐색 턴에서 활성 세트 밖 후보가 실려 `is_exploration=True` 선택이 성립(거부 0).
3. 후보 0의 4개 사유가 **서로 다른 값**을 냄 — 같은 값이면 이 설계가 실패다.
4. 오개념 preload 0 유지를 회귀 테스트로 동결(프롬프트·코칭 context·레코드에 mid 미노출).

**의존**: `REC-01`과 독립(오개념 가설은 attempt가 아니라 코치 대화에서 선다).
**태스크**: 신설 — `REC-02-misconception-probe-supply`.

---

### D3 — 추천의 폐루프 회계가 없다 (`REC-03`)

**문제**: `next-problem`이 추천한 문항을 학생이 실제로 풀었는지 잇는 기록이 **어디에도 없다.**
`AttemptSubmitRequest`(`api/me.py:582`)에 추천 출처 필드가 없고, `EventType` 11종에도 추천 관련이
없다. 그 결과 ①추천 수용률 ②추천 문항의 실제 정답률(난이도 적합의 사후 검증) ③약점 가중이
실제로 약점을 줄였는지를 **잴 수 없고**, `l4/pedagogy/adaptive/policy.py`의 bandit이 보상 신호
부재로 영구 미승격이다.

**정합 설계 — 신규 테이블 0으로 기존 좌석 재사용**: `l2/pedagogy_evidence.py`(`PED-03`)가 이미
`evidence_event`의 최초 writer이며 그 좌석의 계약이 이 축에 **그대로 맞는다**:

1. 처치↔결과를 **`session_id` 축**으로 묶는다(`user_id` 컬럼 없음 — 가명화 유지).
2. `meta` JSONB에 **비민감 메타만**(전략명·경로·개념 code·게이트 사유코드).
3. **"가짜 처치 금지"** — 학생에게 *실제로 렌더된 것*만 기록한다.

문항 추천은 이 계약에 `{problem_id, theta, pool_size, applied_weights, mode, gate_reason}`을 싣는
**동형 적용**이며, `api/study.py`의 `record_pedagogy_treatment` 호출 패턴을 답습한다. 학생 원문·
풀이는 시그니처에 슬롯이 없어 **구조적으로 차단**된다(미성년 PII).

**정직한 한계(범위 선언)**: 결과 결합에는 `session_id`가 추천→풀이로 이어져야 하는데
`AttemptSubmitRequest.session_id`는 optional이고 클라가 보내지 않으며(D1), `learning_session`
writer도 0이다(§2-④). 따라서 이 태스크의 범위는 **처치 기록 좌석 + 리포트까지**이고, 결과 결합·
효과 판정(bandit 승격)은 **`S3-01-pilot-cohort` 이후**로 명시적으로 미룬다("입력 없는 파이프라인
금지").

**acceptance 후보**
1. 추천 1건마다 `evidence_event` 처치 행 1건 — **실제로 학생에게 반환된 추천만**(가짜 처치 금지).
2. `meta`에 학생 원문·풀이·`user_id`가 **들어갈 수 없음**을 시그니처·테스트로 동결.
3. 리포트가 처치 건수와 "결과 미결합(파일럿 대기)"을 **구분해** 표시 — 결합 0을 효과 0으로
   읽히게 하지 않는다.
4. 범위 밖 동결: bandit 승격·보상 계산은 하지 않는다(`PED-03` 잠금 해제 조건임을 notes에 교차 링크).

**의존**: `PED-03` 좌석 재사용. **태스크**: 신설 — `REC-03-recommendation-outcome-accounting`.

---

### D4 — 목표 정답률 밴드 vs 정보량 최대: 목적이 한 엔드포인트에 겸해 있다 (`REC-04`)

**문제**: 틀은 "목표 정답률 유지(70~85%)"를 요구하는데, 현행 CAT은 Fisher 정보량 최대
(`l2/irt.py:203` `item_information`)이고 이는 Rasch에서 **P≈0.5 지향**이다. 즉 **학생이 절반을
틀리도록 설계된 출제**가 학습 세션에도 그대로 적용된다.

의사결정 우선순위 **#1(학생 안전·웰빙)이 #6(비용·효율)을 이기는 축**이며, 금기 "부정적 피드백을
정서적으로 강화하는 표현 금지"와 닿는다. 다만 **밴드 상수를 넣는 것이 답이 아니다** — 근원은
**진단(측정 정밀도) 목적과 학습(생산적 고투) 목적이 한 엔드포인트에 겸해 있다는 것**이다.
진단 세션에서 P≈0.5는 옳다(SE를 가장 빨리 줄인다).

**정합 설계** (신규 스키마 0 · 마이그레이션 0 · 새 선택기 0)
- **① 목적 파라미터**: 진단(현행 정보량 최대) / 학습(목표 성공률 밴드)을 열되 **기본값은 현행
  동작 보존**(회귀 0). 값 공간은 `Literal`로 닫는다(오타 → 422 — `mode` 파라미터 선례
  `api/me.py:1573-1577`).
- **② 기존 곱 결합 축에 얹는다**: 학습 목적의 규칙은 후보의 예상 정답확률
  `probability_correct(θ, item)`(`l2/irt.py:46`)이 밴드에 드는지를 **가중으로 표현**해
  `select_weighted_item`에 그대로 곱한다. 약점 가중·수능 가중과 **같은 축**이며 새 선택기를
  만들지 않는다.
- **③ 밴드 임계는 미보정 정직 표기**: 실학생 응답 0건에서 임계를 측정으로 정할 수 없다. 초기값은
  문헌값으로 두고 응답·리포트에 `band_calibrated=false`를 싣는다(`S4-18`의 `calibrated=false`
  표기 선례). 보정은 `S4-15`(실응답 난이도 루프)에 잇는다.
- **④ 금기 무모순**: 밴드는 "쉬운 문제로 정답률을 꾸미는 장치"가 아니다. **밴드 하한**을 두어
  지나치게 쉬운 후보도 배제하고, *생산적 고투*는 힌트 사다리(`l4/hint_deferral.py`)가 계속 담당한다.

**acceptance 후보**
1. 목적 미지정 시 현행과 **바이트 동일** 추천(회귀 0 동결).
2. 학습 목적에서 선택 문항의 예상 정답확률이 밴드에 드는 비율이 진단 목적보다 유의하게 높음(실측).
3. `band_calibrated=false`가 응답·리포트에 실려 **미보정 상태가 보임**.
4. 밴드 하한이 실제로 너무 쉬운 후보를 배제함을 실측(하한 제거 시 배제가 풀리는지 양방향).

**의존**: 없음. 보정은 `S4-15` 승계. **태스크**: 신설 — `REC-04-difficulty-purpose-separation`.

---

### D5 — 학습 시간 추천(기능 82)의 WhyMath판 (**페이퍼 — 코드 0 · 태스크 신설 없음**)

기능 82의 세부 8개 중 6개는 §2에서 미채택됐다(④⑤⑧). 남는 둘을 WhyMath 어휘로 번역하면
**"분량·스케줄"이 아니라 ①간격(복습 due) ②개입 시점(좌절 감지)**이고, **둘 다 이미 태스크
좌석이 있다**:

- **간격** — `S4-18-review-time-axis`: BKT 망각 역산으로 `review-queue`를 만들고 `target_*`
  컬럼의 **첫 reader**가 된다. 틀의 "학습 주기 추천"·"목표 시간 설정"이 여기로 흡수된다.
- **개입 시점** — `S3-16-behavior-telemetry-writers`: 막힘·힌트요청 writer. 틀의 "휴식 시간
  추천"이 정본에서 취하는 유일한 형태는 *타이머*가 아니라 **좌절 신호에 대한 교수학적 개입**이다.

시간축에서 정본이 인정하는 축은 **분량이 아니라 간격**이라는 것이 이 페이퍼의 결론이다. 신규
태스크 0, 승계로 처리한다.

---

### 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `REC-01-recommendation-reach-observability` | D1 | S3 | 2 | **입력 루프 미도달 + 개인화 미적용이 안 보임** — 최우선. 클라 배선·활성화는 범위 밖(§5-①) |
| `REC-02-misconception-probe-supply` | D2 | S3 | 2 | 도구6이 **구조적으로 항상 실패** · 재료 1,616문항 실재 · 신규 스키마 0 |
| `REC-03-recommendation-outcome-accounting` | D3 | S4 | 4 | 효과 측정 불가 → bandit 영구 미승격 · `PED-03` 좌석 재사용 |
| `REC-04-difficulty-purpose-separation` | D4 | S4 | 4 | 진단/학습 목적 겸함 · 회귀 0 기본값 보존 |
| `NLP-02`(기존) | 채점 권위 = D1의 상류 원인 | — | — | **승계·재설계 금지** (전제 미성립을 notes에 정정) |
| `S4-18`·`S3-16`(기존) | 기능 82 간격·개입 시점(D5) | — | — | **승계·재설계 금지** |
| `PED-03`·`PED-04`·`PED-05`·`S4-15`(기존) | bandit · 결정 로그 · LearnerState · 난이도 보정 | — | — | **승계·재설계 금지** |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다. `validate` green 152건.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (9종)

1. **심화 개념 추천이 데이터로 불가능하다** — `EXTENDS`(심화) 관계는 enum·crosswalk 매핑에
   존재하지만 **코퍼스 엣지가 0건**이다(원자 2,210 · 개념 581이 **전부 선수 관계**). 즉 이것은
   "구현 안 함"이 아니라 **적재 안 됨**이다. 엣지 없이 API만 만들면 항상 빈 결과를 내는 dead
   경로가 된다.
2. **보충 개념(선수가 아닌 병렬 보강) 축이 없다** — 관계 타입 5~8개 제한(플레이북) 안에서 새
   타입을 열 만한 근거가 아직 없다. `prerequisite` 깊이 조절로 대체 가능한지 먼저 측정해야 한다.
3. **오답 유사 문제 추천의 재료가 비어 있다** — 계보 좌석이 **둘인데 둘 다 writer 0**이다:
   `problem_relation`(변형/유사/선수/심화/대조 · `GET /problems/{id}/relations` 리더 실재)과
   `content_provenance.parent_problem_id`(`schema/provenance.py:172`). 생성기들은
   `ContentProvenance`를 만들되 `parent_problem_id`를 채우지 않고, ORM `db/models/provenance.py`는
   `__init__.py`에서만 import되고 **소비처가 0**이다. 원본→생성 계보가 소실된다.
4. **시험 대비 "세트"(묶음 출제) 개념이 없다** — 수능 게이팅은 단건 추천이다. 세트는 난이도
   분포·시간 배분·커버리지 제약이 걸리는 별도 최적화 문제이며, 단건 추천이 검증되기 전에 열지
   않는다.
5. **DKT·협업 필터링은 Phase 3+다** — §2-② 참조. 발화 조건은 §5-③.
6. **BKT 4파라미터 EM 적합을 하지 않는다** — 전 개념 동일 기본값(`l2/bkt.py`)이다. 적합에는
   실응답이 필요하고, 그것이 D1이다.
7. **`persona_fit`이 전 문항 `{}`다** — 페르소나 적합도를 추천 가중으로 쓰는 축이 실질 무효다.
   L6 게이팅이 페르소나를 다르게(자격 판정으로) 쓰고 있어 당장의 공백은 아니다.
8. **"다양성"(추천 기준 5번째) 축이 없다** — 같은 유형·같은 개념이 연속 추천되는 것을 막는 장치가
   없다. `problem_type_graph_v1` 17종이 재료지만, 다양성 제약은 **정보량 최대와 정면 충돌**하므로
   D4(목적 분리)가 착지한 뒤에 논해야 한다. 지금 넣으면 세 목적이 한 엔드포인트에 겸하게 된다.
9. **ClickHouse 행동 로그는 클라이언트 코드가 0이다** — 스택 표에 있으나 배선이 없다.
   `attempt_event`도 EventType 11종 중 3종만 생산된다.

---

## §5. 유보 항목의 발화 조건 (지금 안 만들되, 언제 만드는지)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | **클라 attempt 제출 배선**(D1 범위 밖) | `NLP-02` 관측이 착지해 **서버가 채점 권위를 가질 수 있음**이 확인됐을 때. 순서를 바꾸지 않는다 — 클라가 모르는 `is_correct`를 억지로 보고하게 만드는 것이 지금의 구조적 문제다 |
| ② | **개인화 기본값 on 전환**(D1 범위 밖) | D1 도달 리포트에서 attempt가 실제로 쌓이는 것이 관측된 뒤. 숙달 0행 상태에서 켜면 전 후보 중립 1.0이라 **켜도 아무 일이 안 일어난다** — 켠 줄 알고 넘어가는 것이 더 나쁘다 |
| ③ | **협업 필터링·DKT**(§2-②) | `S3-01-pilot-cohort` N이 임계를 넘고, **동의 범위가 학생 간 교차 활용을 포함**하도록 갱신됐을 때. 두 조건 모두 필요하다 |
| ④ | **심화 개념 추천**(§4-①) | 코퍼스에 `EXTENDS` 엣지가 적재되고 큐레이션 검수를 통과했을 때. API가 먼저가 아니라 데이터가 먼저다 |
| ⑤ | **오답 유사 문제 추천**(§4-③) | `l3/equivalent` 오케스트레이터가 원본→생성 계보를 기록하기 시작할 때(둘 중 어느 좌석이 정본인지 먼저 결정 — 좌석이 둘인 채로 채우면 이중 진실원천) |
| ⑥ | **밴드 임계 보정**(D4-③) | 파일럿 실응답 누적 후 `S4-15`에서. 그전에는 `band_calibrated=false`로 미보정임을 표시한다 |
| ⑦ | **bandit 승격**(D3 후속) | D3의 처치 기록이 결과와 결합되고(파일럿 `session_id` 축), 보상 신호의 분산이 정책 비교를 지지할 때 |
| ⑧ | **다양성 제약**(§4-⑧) | D4의 목적 분리가 착지한 뒤. 목적이 분리되지 않은 엔드포인트에 세 번째 목적을 얹지 않는다 |

---

## §6. 반복 실수 — "완비된 소비 경로 + 미도달 공급원" 4~6회차 (재발방지 등재)

`nlp_module_gap_review.md` §6의 3회차 표를 6회차로 확장한다. 이번 대조에서 **세 개의 새 형태**가
나왔다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| **4** | **`POST /v1/me/attempts` 클라 호출 0회 → 학습자 모델 입력 0**(D1) | 만들고 **입력을 잇지 않음** |
| **5** | **개인화 가중 기본 off · 개념 추천 API 6종 클라 소비 0**(D1) | 만들고 **켜지 않음** |
| **6** | **`select_probe` 후보 공급원 0 → 도구6 상시 실패**(D2) | 만들고 **공급원을 잇지 않음** |

공통 구조는 여전히 하나다: **소비측이 완비돼 있어서 "존재함"이 "돌아감"으로 읽힌다.** 그리고
6회 전부 **graceful 실패**가 증상을 덮었다 — 이번엔 빈 배열, 404, θ=0, "판별 문항 없음"이 그
역할을 했다.

4·5회차가 앞선 셋과 다른 점 하나를 기록해 둔다: **여기서는 "미도달"이 정상 응답과 같은 모양이다.**
OCR은 503이라도 냈다. 추천은 **문항을 정상적으로 돌려준다** — 다만 그 문항이 θ=0 근방에서 아무
개인화 없이 뽑힌 것일 뿐이다. 실패 신호가 아예 없는 형태이므로, 판정 기준은 응답 코드가 아니라
**"입력이 몇 건 들어왔는가"**여야 한다. D1의 도달 리포트가 그 판정을 기계화한다.

---

## §정정 — stale 정본 4곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `l4/misconception/probe_selection.py:24` | "문항-오개념 **태그 스키마(현 레포 부재)** — 하네스가 후보를 공급" | 스키마는 **실재**한다(`Problem.distractor_map` · 코퍼스 1,616문항 태깅 · 오개념 64종). 부재한 것은 스키마가 아니라 **공급하는 하네스 쪽**이다 — 서술이 원인을 반대로 지목하고 있다 |
| `backlog/tasks/NLP-02-...yaml` notes | "학습자 모델 전체가 **미검증 클라이언트 불리언** 위에 서 있다" | **그 불리언조차 오지 않는다** — `POST /v1/me/attempts` 클라 호출 0회. 전제(`student_answer`가 온다)가 미성립 |
| `docs/architecture/02_learner_model.md:193` | `L2LearnerService.select_next_item`이 L2 인터페이스 | 실제 조립은 `api/me.py:1680`(L5 표면)이 하고 L2는 순수 함수(`select_weighted_item`)를 제공한다. 계약 서술 정합 필요 |
| `docs/architecture/02_learner_model.md:218` | Phase 1 성공기준 "오개념 카탈로그 **30개** 매칭" | 카탈로그 **843건** · 탐지 인코딩 **64종** · 문항 태깅 1,616건. 기준이 실측보다 한참 낮게 남아 있다 |

앞의 두 항목은 `nlp` 편이 지적한 것과 **같은 방향의 stale**이다 — "실제보다 못하다"고 말하는
쪽이 아니라, **원인을 다른 곳에 지목하는** 형태다. 이런 stale은 더 나쁘다: 다음 세션이 없는
스키마를 만들거나(첫 항목), 이미 성립한다고 믿고 후속을 설계한다(둘째 항목).

**첫 두 항목의 소스/YAML 반영은 이 문서에서 하지 않는다**(의도적):
- `probe_selection.py:24` — 이 파일은 병렬 세션 `claude/s3-02-live-remeasurement-tlthrr`가 claim한
  `S3-24`의 작업 범위이고, 하네스 `path_overlap` 정책이 동시 편집 위험을 경고했다. 경고를 넘기지
  않고 **주석 정정을 `REC-02` 범위로 접는다**(같은 파일의 공급선을 다루는 태스크가 정정의
  자연스러운 소유자다). 2026-07-27 병렬 세션 충돌 교훈의 적용.
- `NLP-02` notes — 백로그 YAML은 `backlog.py` CLI가 유일 조작 창구이고 notes 갱신 서브커맨드가
  없다. 손편집으로 우회하지 않고(**거부의 우회 금지**) 정정 사실을 이 표에 남기며, `REC-01`
  acceptance ⑤·notes가 그 전제 미성립을 참조한다.

두 경우 모두 **stale을 고치는 행위 자체가 다른 규칙과 부딪힐 때 규칙이 이긴다** — 대신 정정
사실이 사라지지 않도록 여기 기록하고 소유 태스크에 연결한다.

---

## 부록 — 실측 근거 (2026-08-01 실측)

**입력 루프(D1)**
- 모바일이 호출하는 `/v1/` 엔드포인트 **전수 13종**: `/v1/auth/$provider/callback` ·
  `/v1/coach` · `/v1/coach/sessions` · `/v1/coach/sessions/$dialogueId` ·
  `/v1/coach/sessions/$dialogueId/turns` · `/v1/interactions` · `/v1/me/diagnosis/concepts` ·
  `/v1/me/next-problem` · `/v1/ocr` · `/v1/problems/$problemId` · `/v1/scenes/weak-concept` ·
  `/v1/users/me` · `/v1/verify-solution` — **`/v1/me/attempts` 부재**
- `api/me.py:644` — `POST /me/attempts`(`ProblemAttempt` 유일 writer) · `:582` 요청 6필드 ·
  `:665` 적재 · `:679` `record_problem_attempt_mastery`
- `l2/irt.py:76` — `if not responses: return initial`(θ=0.0)
- `api/me.py:1566-1571`(`prioritize_weak_concepts` 기본 false) · `:1573-1577`(`mode` Literal) ·
  `:1653-1671`(`NextProblemResponse` 5필드) · `:1598/1619`(약점 가중)
- `api/scene.py:174` — "진단할 개념이 없습니다(채점 이력 부족)"
- `src/mobile/.../problems_api.dart:27`(기본값) · `:40-41`(`answer` 키 미선언) ·
  `diagnosis_controller.dart:29` · `problem_screen.dart:36,68`(인자 없이 호출) ·
  `verify_api.dart:23`("정답을 알지 못하는 검증")
- `db/models/activity.py:161` — `ProblemAttempt.session_id` FK → `learning_session`(writer 0)

**프로브 공급(D2)**
- `harness/wh1_llm_policy.py:143`(`probe_candidates = ()` 기본) · `:174` · `:420-421`
- `harness/wh1_primary.py:115` · `harness/wh1_shadow.py:261` — **둘 다 `outside_mids`만 전달**
- `harness/wh1_loop.py:453`(`plan_probe`) · `:462-469`(ε 거부) · `:472`("판별 문항 없음")
- `l4/misconception/probe_selection.py:24`(stale 주석) · `:45`(`ProbeCandidate`) · `:175` · `:219`
- `db/models/problem.py:151`(`distractor_map`) · `l6/metacognition/gating.py:118,157`(개수만 사용)
- `l2/ability_estimation.py:38`(`resolve_item_difficulty_b`)

**회계(D3)·난이도(D4)**
- `l2/pedagogy_evidence.py:1-40` — `evidence_event` 최초 writer · `session_id` 축 · `user_id` 없음 ·
  "가짜 처치 금지" · 비민감 meta만
- `l2/irt.py:46`(`probability_correct`) · `:203`(`item_information`) · `:236`(`select_weighted_item`)
- `api/me.py:1555`(`_CANDIDATE_POOL_SIZE=50`) · `:1559`(`_TARGET_SE=0.3`) · `:1563`(`_WEAK_CONCEPT_BOOST=1.0`)

**계보 좌석(§4-③)**
- `schema/provenance.py:95-172`(`ContentProvenance`·`parent_problem_id`) — 생성기 7종이 생성하되
  `parent_problem_id` 미기입 · `db/models/provenance.py`는 `db/models/__init__.py:112`에서만 import
- `schema/problem.py:689-720`(`ProblemRelation` 복합 PK) · `api/problems.py:162-171`(리더)

**코퍼스 실측**(`data/corpus/**`)
- 문항 2,647 / `distractor_map` 1,616 / 오개념 id 64종 / `difficulty_overall` 2,647(100%) /
  **`irt_difficulty_b` 0건**
- `atom_graph_v1/graph.json` — concepts 2,683 · edges 2,210(**전부 `prerequisite`**)
- `concept_graph_v1/` — concepts 437 · prerequisite_edges 581(**전부 `선수(prereq)`**)
- `misconceptions_v1/misconceptions.json` — `count` 843

**모드 게이팅(대조군)**
- `api/gating.py` — `/retake`·`/suneung`·`/school-progress`·`/thinking`·`/metacognition`·`/gifted`
  (6종·클라 소비 0)
- `l6/suneung/recommendation.py:54` `recommend_suneung_index`
