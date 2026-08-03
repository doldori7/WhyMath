# 학습 경로(Learning Path) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03)

> **범위**: 외부 참고 문서 『1단계: 학습 경로(Path)』(기능 54 개인별 학습 경로 생성 ·
> 55 선수학습 자동 추천 · 56 복습 스케줄 생성 · 57 목표 기반 학습 플랜, 4모듈 —
> **WhyMath 전용이 아닌 일반적인 EOS(Education Operating System) 틀**, Kiki 제공 docx)을
> 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(LTHC 기초 우선·
> 이중 진실원천 금지·측정 없는 도입 없음·교수학 날조 금지·침묵 실패 금지·서열화 금지)
> 안에서 설계한 기록.
> **형식**: `curriculum_module_gap_review.md`(같은 EOS 틀 시리즈, 2026-08-03) 답습 —
> 시리즈 **12번째** 자매편(1.knowledge → 2.problem_bank → 3.ai_tutor → 4.solution →
> 5.operations → 6.account_security → 7.ai_content_generation → 8.visualization → 9.nlp →
> 10.ai_recommendation → 11.curriculum → **12.learning_path**).
> **결론**: 착수 가설("학습 경로가 없다")은 **반증**됐다. Kahn 위상정렬(`l2/learning_path.py`)·
> 재귀 CTE 선수 traversal(`l2/prerequisite_recommendation.py`)·HTTP 노출까지 이미 프로덕션이다.
> 진짜 문제는 **"있는데 기본 파라미터에서 죽어 있고, 죽었다는 사실이 응답에 안 나온다"**이다 —
> 엔드포인트 기본값 `max_depth=1`에서 위상 제약 엣지가 0인 사례가 **96.4%**이고, 그때 응답은
> `_tiebreak` 정렬로 조용히 강등되는데 **호출자가 구별할 수 없다**(§0-①). 진짜 갭 3건을
> 설계(D1~D3)하고 페이퍼 갭 3건을 남겼다. 실행 3건을 백로그에 등재했다(`PATH-01`~`PATH-03`).
> 의도적 미채택 9건 · 정직한 공백 6종 · 유보 발화조건(전역 경로 4조건 AND) · 정본 stale 3곳.
> **기능 56·57은 신규 태스크 0** — 이미 `S4-18`이 설계를 보유한다(§1).

관련 정본: `02_learner_model.md`(L2 학습자 모델·BKT/IRT/망각곡선 단계 도입) ·
`ai_tutor_module_gap_review.md`(§2-④ SM-2/FSRS 영구 미채택 · §3 D5 → `S4-18`) ·
`ai_recommendation_module_gap_review.md`(§0-② 입력 루프 클라 미도달 → `REC-01`) ·
`06_application_modes.md`(자동 커리큘럼 정렬 7차원) · `docs/data/atom_graph_v1.md`(runtime
truth source) · `curriculum_module_gap_review.md`(§6 반복 실수 7회차 표) · `MEMORY.md` 결정
로그(2026-06-20 학습 경로 위상정렬 · 2026-06-21 HTTP 노출).

---

## §0. 두 가지 전제 정리

### ① 착수 가설이 반증됐다 — 없는 게 아니라 기본값으로 꺼져 있다

이 대조는 "WhyMath에 학습 경로 기능이 빈약하다"는 가설로 시작했다. 실측 결과 **네 좌석이
모두 실재**한다:

| 좌석 | 파일 | 상태 |
|---|---|---|
| 순수 위상정렬 | `l2/learning_path.py:143` `order_learning_path` | Kahn·완전 결정론·사이클 정직 잔여 |
| 선수 traversal | `l2/prerequisite_recommendation.py:230` `build_prerequisite_stmt` | 재귀 CTE·`MAX_PREREQUISITE_DEPTH=5`·MIN depth dedup |
| 약점 융합 | `l2/concept_diagnosis.py` `compute_concept_diagnoses` | BKT × IRT 교차검증 |
| HTTP 노출 | `api/me.py:1506` `GET /v1/me/weak-concepts/{id}/learning-path` | 200 정상·테스트 18건 green |

그런데 **그 위상정렬이 실사용 기본 파라미터에서 거의 아무것도 정렬하지 못한다.**
원자 백본(`data/corpus/atom_graph_v1/graph.json`, 2,683노드·2,210 prerequisite 엣지) 전수 실측:

| 항목 | 값 |
|---|---|
| 직접 선수 개수 분포 | 0개 **915** / 1개 **1,412** / 2개 **278** / 3개 **70** / 4개 **8** |
| 직접 선수 2개 이상(= 순서화가 성립할 수 있는 모집단) | **356건 (13.3%)** |
| `max_depth=1`(**엔드포인트 기본값**)에서 집합 내부 *직접* 엣지 보유 | **96/356 (27.0%)** |
| → 전체 2,683 대비 | **3.6%** |
| `max_depth=2` | 집합≥2가 1,712건, 그 중 내부 엣지 보유 **1,711 (99.9%)** |

즉 기본값에서 **96.4%의 개념에 대해 in-degree가 전부 0**이고, Kahn 루프는 제약 없이 풀을
`_tiebreak`(weakness asc · depth desc · edge_strength desc · uuid)로 정렬해 방출한다.
그것은 위상정렬이 아니라 **가중 정렬**이다. 선수 추천 엔드포인트와 정렬 *방향*만 반대일 뿐
(추천은 depth asc, 경로는 depth desc) 같은 종류의 연산이다.

**왜 아무도 몰랐는가 — 세 겹의 무증상**:
1. 단위테스트 18건(`tests/backend/l2/test_learning_path.py`)이 **엣지가 있는 fixture** 중심이다.
   엣지 0 경로를 덮는 테스트는 있지만, 그것이 **실사용의 96.4%**라는 사실은 어디에도 없다.
2. 코퍼스 위상 통계를 낸 리포트가 없다. `ARCH-17` 그래프 분석 리포트는 허브·하류 도달·오개념
   전파를 재지만 **"이 집합이 순서화 가능한가"** 축이 없다.
3. **클라 소비 0** — Flutter 실사용 엔드포인트 13종에 `learning-path`·`prerequisites`·
   `weak-concepts`가 전부 없다(`ai_recommendation_module_gap_review.md` §0-② 전수 실측).
   사용자 신고 경로 자체가 존재하지 않는다.

이것이 §6에 8회차로 등재하는 **새로운 형태의 반복 실수**다 — 앞의 일곱은 "돌지 않아서"
안 보였고, **8회차는 "돌아서" 안 보였다.**

### ② 틀의 아키텍처와 정본의 차이 (갭 판정의 전제)

외부 틀은 학습 경로를 **학생에게 제시하는 최종 산출물**로 본다:

```
진단평가 → 수준분석 → Knowledge Graph → [선수추천·경로생성·복습일정] → 목표플랜 → 학생 대시보드
```

WhyMath 정본에서 학습 경로는 **진단의 파생 *조회* 좌석**이지 학생 대면 산출물이 아니다.
증거는 스키마 자체에 있다 — `LearningStep`에는 `description`·`formal_definition`·
`intuitive_explanation` **슬롯이 구조적으로 없다**(frozen pydantic·redaction 계약,
`learning_path.py:65-98`). 본문을 담을 자리가 없으므로 이 응답만으로는 화면을 만들 수 없다.
학생 대면은 L4 코칭(`/v1/coach`)·L5 Scene(`/v1/scenes/weak-concept`)이 소유한다.

| 틀이 경로에 요구하는 것 | WhyMath 정본의 자리 |
|---|---|
| 경로가 **학생 대시보드의 콘텐츠** | 경로는 **내부 조회·순서화 좌석**(본문 슬롯 없음) |
| "다음에 뭘 풀까"를 **경로 트리에서 선택** | **IRT CAT 적응 출제**(`GET /me/next-problem`)가 소유 — 트리 선택이 아니다 |
| 복습 일정을 **별도 스케줄러**가 계산 | 망각의 단일 권위는 **BKT `p_forget`**(`bkt.py:109`) — 별도 SRS는 이중 진실원천 |
| 목표 점수를 **예측**해 역산 | 점수·등급 **예측 금지**(서열화) — 목표축은 **성취기준 커버리지**로만 표현 |
| 학생 수준에 맞춰 **단원 생략** | **생략하지 않는다** — 경로의 임무는 *건너뛸 것* 찾기가 아니라 *메울 것* 찾기(LTHC) |

**따라서 이 문서는 "경로가 학생 화면에 없다"·"스케줄러가 없다"·"점수 예측이 없다"를 갭으로
세지 않는다.** 그건 §2의 미채택이다. 갭은 **경로 좌석 자신이 약속한 것(위상정렬)을 실제로는
하지 않고, 그 사실을 말하지도 않는 지점**에서만 성립한다.

---

## §1. 기능 54~57 전수 대조

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·데이터·기본값* 없음) / ⚠️ 진짜 갭 → D /
🚫 의도적 미채택 → §2

### 기능 54 — 개인별 학습 경로 생성

**입력 데이터 7종**

| 틀의 입력 | WhyMath 현행 | 판정 |
|---|---|---|
| 진단평가 결과 | `compute_concept_diagnoses`(BKT×IRT 교차검증·`l2/concept_diagnosis.py`) | ✅ |
| 학교 학년 | `User.grade` 존재. 경로에는 **의도적으로 미적용** | 🚫 §2-⑥ |
| 학습 이력 | `problem_attempt` **0행**(클라가 `POST /v1/me/attempts` 미호출) | ⚠️ **`REC-01` 소관 — 중복 등재 금지** |
| 오답 기록 | 동상(`is_correct`가 서버에 도달 안 함 — 근본 원인 `NLP-02` 채점 권위 공백) | ⚠️ 동상 |
| 문제 해결 시간 | `ProblemAttempt.duration_seconds`·`step_times` 스키마 있음·데이터 0행 | ⚠️ 동상 |
| 오개념 | `misconception_catalog` **843건** + 가설 추적(`MisconceptionHypothesis`) | ✅ |
| 학습 목표 | `User.target_*` 4컬럼 존재·**reader 0** | △ **`S4-18` ② 보유 → 신규 0** |

**AI 기능 4종**

| 틀의 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 난이도 조절 | IRT CAT(`select_next_item`·정보량 최대) × `_WEAK_CONCEPT_BOOST` 약점 가중 | ✅ **초과** (단, *출제* 좌석이지 *경로* 좌석이 아님) |
| **최적 학습 순서 생성** | Kahn 위상정렬 실재하나 **기본값에서 96.4% 제약 0 · 강등이 응답에서 구분 불가** | ⚠️ → **D1·D2·D3** |
| 단원 생략 여부 판단 | 없음 | 🚫 §2-① |
| 약점 우선 학습 | weakness asc 정렬 + `weak_only=True` 기본 | ✅ |

**출력(전역 순서)**

| 틀의 출력 | WhyMath 현행 | 판정 |
|---|---|---|
| 학생 1인당 **단일 관통 순서**(분수→소수→비율→비례식→함수) | 없음 — 경로는 **약개념 1건의 막힌 선수집합 내부 순서**만. 전역 병합 좌석 0 | △ **유보**(§5 — 4조건 AND) |

**최상위 판정: ⚠️ 진짜 갭.** 기능이 없어서가 아니라, 있는 기능이 기본값에서 무력화돼 있고
그 사실이 관측되지도 표기되지도 않기 때문이다.

### 기능 55 — 선수학습 자동 추천

| 틀의 요구 | WhyMath 현행 | 판정 |
|---|---|---|
| Prerequisite Graph 보유 | `concept_edge`(`EdgeType.PREREQUISITE`) — 원자 2,210엣지·개념 581엣지 | ✅ |
| 자동 탐색(traversal) | 재귀 CTE(`build_prerequisite_stmt:230`)·다단계 depth 1~5·MIN depth dedup(diamond 방어) | ✅ **초과** |
| "이차함수를 모르겠다" → "원인은 인수분해 부족" | `recommend_prerequisite_gaps` + L4 결선(`GET .../coaching` → `prerequisite_review` 트리거) | ✅ |
| DAG 보장 | `validate.py` `prerequisite_cycle` hard error + 런타임 방어적 잔여 처리 | ✅ **초과** |

**틀에 없는데 WhyMath에 더 있는 3축**: ① BKT×IRT 약점 융합(막힌 선수만 선별) ② 원자 축
울타리(`ARCH-13` — 이중 진실 조인 해소) ③ **제외 사유 계상**(`l2/axis_exclusions.py`
`AxisExclusions` — 침묵 실패 금지의 이행).

**판정: ✅ 충족·초과.** 갭 아님. 기본값 `max_depth=1`이라 "자동 탐색"이 실질 1-hop인 것은
사실이나, 이는 **파라미터 기본값 판단**이지 기능 부재가 아니다(§4 페이퍼 P1).

### 기능 56 — 복습 스케줄 생성

| 틀의 요구 | WhyMath 현행 | 판정 |
|---|---|---|
| Spaced Repetition / SM-2 / FSRS | 없음 — **영구 미채택** 확정(`ai_tutor_module_gap_review.md` §2-④) | 🚫 §2-④ |
| 망각곡선 | **있음** — `l2/bkt.py:109` `apply_forgetting(mastery, elapsed_days, params)`·`BktParameters.p_forget` | ✅ |
| 복습 일정 산출(8/1 → 8/2·8/5·8/12·8/26·9/20) | 없음. `apply_forgetting`의 유일한 소비처는 `mastery_tracking.py:69`의 **다음 관측 시 prior 보정**뿐 | △ **`S4-18` ① 보유** |
| 정답이면 간격↑·오답이면 앞당김 | BKT 사후확률이 구조적으로 동등한 효과(숙달↑ → 감쇠 후에도 높음) | ✅(다른 모델로 충족) |
| `next_review_at` 컬럼 | 없음 — **미채택**(순수 파생으로만 산출) | 🚫 §2-④ |

**판정: 🚫 미채택(알고리즘 축) + △(시간축 — `S4-18` 보유).**
**이번 리뷰에서 신규 태스크 0.** `S4-18-review-time-axis` acceptance ①이 이미
`GET /v1/me/review-queue`(`MAX(measured_at)` + `apply_forgetting` 조회시점 적용 →
`decayed_mastery`·`days_since_practice`·`due_rank`·신규 컬럼 0)를 소유한다.

### 기능 57 — 목표 기반 학습 플랜

| 틀의 요구 | WhyMath 현행 | 판정 |
|---|---|---|
| 시험 일정·남은 기간(D-day) | `User.target_exam_date`(`db/models/user.py:108`) 존재·**reader 0** | △ **`S4-18` ② 보유** |
| 목표 점수 | `target_score`·`target_grade` 존재·reader 0 | △ 동상(단, **점수 예측은 🚫 §2-⑤**) |
| 필요 학습량 산출(112개 개념·340문제) | 성취기준 커버리지 %로 대체 예정(`S4-18` ②) | △ 동상 |
| 하루 학습 가능 시간 | 컬럼·입력 경로 0 | 🚫 §2-② |
| 요일별 학습량 생성(월 개념3·문제20 …) | 없음 | 🚫 §2-③ |
| 현재 실력·취약 영역 | BKT/IRT·약개념 좌석 완비 | ✅ |
| 학교 진도 | `l6/school_progress/gating.py` + `curriculum_entry` Overlay | ✅ |
| 모의고사 일정 | 없음 | 🚫 §2-② 계열(생산자 0) |

**판정: 🚫 대부분 미채택 + △(D-day·커버리지 — `S4-18` ② 보유). 신규 태스크 0.**

### (횡단) 틀의 시스템 아키텍처 다이어그램 대조

틀은 `진단 → 수준분석 → KG분석 → [선수추천·경로생성·복습일정] → 목표플랜 → 학생 대시보드`
5단 파이프라인을 그린다. WhyMath는 이 중 **1~3단이 실재**하고(진단·KG·선수추천·경로생성),
4단(복습·목표)은 `S4-18`이 보유하며, **5단(학생 대시보드)은 클라 소비 0**이라 파이프라인
끝단이 열려 있다(`REC-01` 소관). 즉 아키텍처는 어긋나지 않았고 **끝에서 두 마디가 아직
연결되지 않았을 뿐**이다.

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 항목 | 근거 |
|---|---|---|
| ① | **단원 생략 여부 판단**(54) | LTHC(기초 우선) 정면 충돌. "이미 안다"를 근거 없이 판정해 단원을 건너뛰면 결손을 *생성*한다. 경로 좌석의 임무는 *건너뛸 것* 찾기가 아니라 *메울 것* 찾기다. 게다가 `problem_attempt` 0행이라 판정 신호 자체가 없다 |
| ② | **하루 학습 가능 시간**(57) | "생산자 없는 신호는 필드로 만들지 않는다"(`l4/pedagogy/runtime_selector.py:96-112` 결정·`PED-05` ②가 승계). 자기보고 시간 예산은 신뢰도 검증 수단이 0 |
| ③ | **요일별 학습량 생성**(57) | ②에 전적으로 의존하는 2차 파생 — 없는 신호 위에 쌓는다. 또한 학습량 할당은 압박 발화를 유발한다(CLAUDE.md "학습 시간·정답률만으로 우열을 매기는 게임화 금지" 계열) |
| ④ | **SM-2 / FSRS / `next_review_at` 컬럼**(56) | `ai_tutor_module_gap_review.md` §2-④ **영구 미채택** 재확인. 망각의 단일 권위는 `l2/bkt.py:109 apply_forgetting`의 `p_forget`. 카드형 스케줄은 개념 그래프 축과 모델이 달라 **두 진실원천**이 생긴다(7대 붕괴 연쇄 ④ 유지보수 지옥) |
| ⑤ | **점수·등급 예측**(57) | `ai_tutor` §2-⑧(← `solution_module` §2-① 서열화 금지) **영구 미채택**. 목표축은 **성취기준 커버리지**로만 표현한다(`S4-18` ②가 "점수·등급 예측 필드 부재를 테스트로 동결"을 명시) |
| ⑥ | **학습 경로에 학년 게이팅 적용**(54 "학년" 입력) | **선수개념은 정의상 현재 학년 *아래*에 있다.** 학년 필터는 LTHC가 찾아낸 근본 결손을 정확히 골라 지운다 — 기능이 아니라 결함이 된다. 게이팅이 필요한 지점은 *출제*(L6 6모드·`api/gating.py`)이지 *복습 경로*가 아니다. 현행 경로의 `reviewed_only`가 **검수** 게이팅일 뿐 학년 게이팅이 아닌 것은 **설계이지 누락이 아니다** |
| ⑦ | **`max_nodes` 노드 수 상한** | 깊이 예산이 이미 bound한다 — 실측 depth5 최대 **55**·p99 33·평균 6.2, depth1 최대 4. 신설 상수는 즉시 소비돼야 하는데 상한을 넘는 실사례가 **0건**이다. `MAX_PREREQUISITE_DEPTH` docstring(`prerequisite_recommendation.py:118-123`)이 이미 "이것은 그래프 traversal 깊이 예산이지 LLM 컨텍스트 예산(max_nodes)이 아니다"를 명문화했고, 후자는 소비처가 생긴 뒤 canonical seam으로 간다 |
| ⑧ | **`subunit_code`를 "교과서 단원 배열"(L6 차원⑥)로 사용** | 2,683노드 중 **2,466개**가 `<영역>-U#-S#` 꼴 번호를 갖고 있어 **순서 신호처럼 보인다.** 그러나 그것은 원자 백본 *저작 순서*이지 출판사 목차 배열이 아니다. `06_application_modes.md` 차원⑥은 "교과서 단원 배열 따름"이고 대조 대상이 출판사별 차이다 — 출판사 데이터 0인 상태에서 저작 순서를 교과서 배열로 재라벨하면 **교수학 날조**다. *그럴듯한 신호가 실재한다*는 점에서 특히 위험하다 |
| ⑨ | **전이 엣지에 합성 `edge_strength` 부여**(D3 내부 판단) | 경로 강도의 곱·최소·평균 어느 것도 데이터에 근거가 없다. 전이 관계는 **순서 제약으로만** 쓰고 **강도로는 쓰지 않는다** |

⑧에 딸린 판단 하나 더: `_tiebreak`의 최종 키인 `str(concept_id)`(UUID·자의적)를
`subunit_code` 순서로 바꾸는 것도 **하지 않는다**. 실측상 진짜 병렬 집합(순서가 없는 것이
정답인 경우)이 depth1에서 **107~260건** 존재한다(도달 예산에 따라). 그럴 때
**가짜 순서를 부여하는 것보다 "이들은 병렬"이라고 표기하는 편(D2)이 엄격히 더 정직하다.**

---

## §3. 진짜 갭 설계

### D1 — 위상 제약 밀도가 한 번도 관측된 적 없다 (최우선·`PATH-01`)

**문제**: `order_learning_path`는 "Kahn 위상정렬"로 문서화·홍보되지만, 기본 파라미터에서
제약 엣지가 0인 사례가 96.4%다. 이 밀도는 **코드·테스트·문서 어디에도 수치로 존재하지 않는다.**
`ARCH-17` 그래프 분석 리포트는 허브·하류 도달·오개념 전파를 재지만 "이 집합이 순서화
가능한가" 축이 없다.

**왜 지금까지 안 드러났는가**: §0-①의 세 겹(엣지 있는 fixture 중심 테스트 · 위상 통계 리포트
부재 · 클라 소비 0). 특히 결정적인 것은 **실패 신호가 없다**는 점이다 — 엔드포인트는 200을
반환하고 응답 형태는 완전하며 테스트 18건이 전부 green이다.

**정합 설계(신규 스키마 0 · DB 접근 0 · LLM 0 · 네트워크 0)**:
`src/backend/whymath_backend/harness/learning_path_orderability_report.py` 신설 —
`visualization_reach_report.py`가 확립한 **"코퍼스 JSON을 읽고 프로덕션 판정 함수를 그대로
재호출"** 패턴의 답습이다.

재사용 좌석:
- 코퍼스 로딩 — `data/corpus/atom_graph_v1/graph.json`, `visualization_reach_report` 로딩 관례
- **`l2.learning_path.order_learning_path` 직접 호출** — 신규 Kahn 구현 **0**. 리포트가
  프로덕션 정렬기를 그대로 돌리므로 **리포트와 런타임이 갈라질 수 없다**
- `l2.prerequisite_recommendation.MAX_PREREQUISITE_DEPTH` — 깊이 축 단일 출처
- `PrerequisiteGap` 합성은 code → `uuid5` 결정론 매핑(순수)

산출 3축:
1. **깊이별 순서화 가능 비율** — `max_depth` 1·2·5 각각의 (집합≥2 노드 수 / 제약 보유 수 / 비율)
2. **직접 엣지 vs 전이 도달 병기** — 두 값이 다르다는 것 자체가 D3의 근거 수치
3. **결정도 분포** — 완전 결정 / 부분 결정 / **진짜 병렬**

**리포트가 반드시 자기 한계를 표기할 것**: 이 수치는 `weak_only=True` 필터 *이전*의
**구조적 상한**이다. 런타임에서는 막힌 선수만 노드가 되므로 집합이 더 작아지고 순서화 비율은
**이 값 이하**다. 그리고 병렬 집합은 순서가 없는 것이 정답이므로 **100%를 목표로 두면 안 된다**
(`visualization_reach_report`가 "100% 도달은 목표가 아니다"를 명시한 것과 같은 결).

**dead code 금지 충족**: 신규 로직은 도달 판정 순수 함수 하나뿐이며 즉시 리포트에 소비된다.
그 함수는 D3(`derive_ordering_edges`)가 런타임에서 재사용하므로 **리포트 전용 코드가 되지 않는다**.

**변별력**: ① 코퍼스 엣지 1개를 제거/추가해 순서화 카운트가 **양방향으로** 움직이는지.
② **직접 축과 전이 축이 서로 다른 값을 내는지**(depth1에서 96 vs 249/310). 두 축이 같은 값을
내면 그 리포트는 축이 하나뿐인 위장이다.

**acceptance 후보**:
1. 현행 실측 고정 — 2,683노드/2,210엣지에서 직접선수 분포(915/1,412/278/70/8)·depth1 순서화
   96/356(27.0%) 재현(주장 확인 **또는 반증** — 반증되면 범위 재조정)
2. 정합 설계 본체 — 깊이별 × (직접·전이) × 결정도 3축 리포트. `order_learning_path` 재호출로
   신규 정렬 로직 0, 신규 스키마·DB 접근 0
3. **상한 표기** — 산출값이 `weak_only` 이전 **구조적 상한**이며 병렬 집합 때문에 100%가
   목표가 아님을 리포트 본문·JSON 필드로 명시(런타임 실측과 혼동 불가하게)
4. CI 배선 실재 확인 — 신규 워크플로 없이 기존 harness 잡에 편입되는지(OPS-03·OPS-10 —
   "저장소에 존재함"과 "돌아감"은 다르다)
5. 변별력 — 위 서술대로 양방향 이동 + 두 축 분기
6. **범위 밖 명시** — 엔드포인트 응답 변경(D2)·정렬 알고리즘 변경(D3)·`max_depth` 기본값
   변경(§4 P1)·전역 경로(§5)는 포함하지 않는다

**의존**: 없음(즉시 착수 — 코퍼스만 읽으므로 `problem_attempt` 0행과 무관하다.
"입력 없는 파이프라인 금지"를 정면으로 만족한다). **태스크**: 신설 —
`PATH-01-learning-path-orderability-report` (S3·priority 3).

---

### D2 — 위상정렬 강등이 응답에서 구분 불가 (`PATH-02`)

**문제**: `LearningPath.has_cycle`·`LearningStep.is_cycle_residual`은 "사이클 때문에 정렬을
못 했다"를 정직하게 표기한다. 그런데 그보다 **훨씬 흔한 실패 모드**인 "제약이 0이라 정렬할
것이 없었다"는 표기가 **없다**. 96.4%에서 응답은 정상적인 순서화 결과와 **비트 단위로
구별 불가**하다. 호출자는 `position=0`을 "위상적으로 가장 근본인 선수"로 읽지만, 실제로는
"가장 weakness가 낮은 선수"다.

**왜 지금까지 안 드러났는가 — 정직 표기가 정확히 뒤집혀 있다**: 정직 표기가 **사이클 축에만**
설계됐다. 그런데 사이클은 데이터셋 v1에서 `validate.py`가 hard error로 막아 **실제 발생 0건**인
방어적 코드이고, 제약 0은 **96.4%**다. **발생하지 않는 쪽에만 표기가 붙어 있다.**

**정합 설계(순수 · 추가 순회 0 · 추가 쿼리 0 · 마이그레이션 0)**:
`order_learning_path` 내부에는 이미 `adj`·`indeg`가 있다. 거기서 파생한다.

- `LearningPath.ordering_edge_count: int` — Kahn이 실제로 소비한 집합 내부 제약 엣지 수
  (집합 밖 엣지·중복 엣지 제외 후). `sum(len(v) for v in adj.values())` — O(n)·신규 순회 0
- `LearningPath.ordering_basis: Literal["topological", "tiebreak_only", "empty"]` —
  `edge_count > 0` → `topological` / `== 0`이고 steps 있음 → **`tiebreak_only`** / steps 없음 → `empty`

**`ordering_basis`가 파생값인데 dead 아닌가**: `has_cycle`이 이미 `is_cycle_residual`의 파생
불리언인데도 공존하는 선례가 **같은 파일 안**에 있다(`learning_path.py:114`·`:95`).
정직 표기를 놓칠 수 없게 만드는 중복은 이 저장소의 확립된 관례다. 다만 최소주의를 택한다면
`ordering_edge_count` 하나로도 판정 가능하다는 점은 정직하게 남긴다.

동형 선례: `l2/axis_exclusions.py` `AxisExclusions`(거기선 *제외*를 세고 여기선 *제약*을 센다).
응답 정직 표기 선례: `REC-01` acceptance ②(`NextProblemResponse`에 적용 가중 축·후보 풀
크기·후보 0 사유). **클라 소비 0인 상태에서 응답 필드를 더하는 정당성도 REC-01이 이미 세웠다.**

**하지 말 것**: step별 "이 단계가 제약으로 정해졌나" 플래그는 과공학이다 — 제약은 쌍 관계라
단계 단위로 참이 되지 않는다. 경로 전체 1쌍이면 족하다.

**변별력(이번 리뷰 최대 핵심)**: **fixture 두 개가 "같은 `steps` 순서"를 내면서 두 필드는
달라야 한다.** 순서만 비교하는 검사는 **원리적으로** 이 결함을 못 잡는다 — 그게 문제의 본질이다.
구체적으로: 노드 A·B의 weakness를 조정해 tiebreak 순서와 위상 순서가 우연히 일치하게 만든
fixture 쌍 — 하나는 엣지 있음(`topological`·count=1), 하나는 엣지 없음(`tiebreak_only`·count=0),
`steps` 튜플은 **동일**.

**acceptance 후보**:
1. 현행 실측 고정 — 엣지 0 집합에서 현행 응답이 정상 경로와 구분 불가함을 테스트로 먼저 고정(결함 재현)
2. 정합 설계 본체 — 2필드 추가. **`_tiebreak`·Kahn 루프·엣지 공급 로직 변경 0**, 기존 테스트
   18건 회귀 0, frozen·본문 슬롯 부재 계약 불변
3. 변별력 — 위의 "같은 순서·다른 표기" fixture 쌍(성공/실패가 같은 값을 내지 않음을 구조적으로 보장)
4. 계약 안정 — 추가 필드는 default 보유(기존 소비자 회귀 0)·OpenAPI 가산 변경만
5. 정본 정정 동반 — `learning_path.py` 모듈 docstring과 `api/me.py get_my_learning_path`
   docstring의 무조건적 "위상정렬" 서술을 조건부로 정정(§정정 ①②)
6. **범위 밖 명시** — 순서 알고리즘·엣지 공급은 건드리지 않는다(D3). `prerequisites`·
   `coaching` 엔드포인트 응답도 변경하지 않는다

**의존**: 없음(D1과 병렬 가능). **태스크**: 신설 —
`PATH-02-learning-path-ordering-honesty` (S3·priority 3).

---

### D3 — 비-막힌 중간 노드 경유 전이 의존 미반영 (`PATH-03`)

**문제**: `fetch_internal_prerequisite_edges`(`learning_path.py:222`)는 `from`·`to`가 **둘 다
막힌 선수 집합 안**인 직접 엣지만 조회한다. `A→X→B`에서 X가 막히지 않았으면 A·B 사이 순서가
사라진다. `build_learning_path` docstring(`learning_path.py:256-258`)이 이 한계를 **스스로
적어두고 "후속 범위"라고 했으나 백로그에 등재된 적이 없다.**

실측 결과 **이것이 무력화의 지배적 원인**이다. 모집단 356건(직접 선수 2개 이상) 고정 ·
후보 집합 불변:

| 도달 예산 | 순서화 가능 | 순서쌍 | 완전결정/부분/병렬 |
|---|---|---|---|
| 1홉(= 현행 직접 엣지) | **96 (27.0%)** | 106 | 64 / 32 / 260 |
| **5홉(`MAX_PREREQUISITE_DEPTH` 재사용 — 실제 구현 예산)** | **249 (69.9%)** | **304** | 201 / 48 / 107 |
| 무한(구조적 천장·구현 불가) | 310 (87.1%) | 428 | 285 / 25 / 46 |

**27.0% → 69.9%.** 87.1%는 도달 불가능한 천장이므로 목표치로 인용하지 않는다.

**왜 지금까지 안 드러났는가**: ① docstring이 정직하게 고백했다는 사실이 오히려 방어막이 됐다 —
"알고 있고 후속으로 미뤘다"는 기록이 있으면 재점검 압력이 사라진다. ② 그 후속이 **얼마나
큰지**가 수치화된 적이 없다("일부 케이스" 정도로 읽힌다). ③ 테스트 18건 중 "중간 노드가
비-막힘"인 fixture가 **0건**이다.

**정합 설계 — 핵심: `order_learning_path`를 한 줄도 고치지 않는다.**
Kahn 코어는 `internal_edges: Sequence[tuple[UUID, UUID]]`를 **받기만** 한다. 바꿀 것은
**무엇을 공급하는가**뿐이다. `l2/learning_path.py`에 2개를 추가하고 `build_learning_path`의
배선만 교체한다:

1. `fetch_ordering_subgraph(session, concept_ids, *, max_hops)` — 집합 노드들에서 **선수
   방향(ancestor)** 으로 bounded 재귀 CTE traversal, 통과한 엣지 전체 반환.
   `build_prerequisite_stmt`(`prerequisite_recommendation.py:230`)의 재귀 CTE 패턴을 그대로
   답습(SQLAlchemy Core·원시 SQL 0·읽기 전용). `max_hops`는 **`MAX_PREREQUISITE_DEPTH` 재사용**
   (신규 상수 0). 다만 이것은 *후보 선택 깊이*가 아니라 **순서 도달 예산**이라는 구분을
   docstring에 명시한다(같은 파일이 이미 "traversal 깊이 예산 ≠ LLM 컨텍스트 예산" 구분을
   세워둔 선례가 있다).
2. `derive_ordering_edges(node_ids, subgraph_edges) -> list[tuple[UUID, UUID]]` — **순수 함수**.
   subgraph 안에서 도달가능성을 계산해 `(a, b)` 중 a·b 둘 다 `node_ids`에 있고 a가 b에
   도달하는 쌍만 방출. DB·async 0 → 단위테스트 직접 가능하고 **D1 리포트가 이 함수를 그대로
   재사용**한다(리포트와 런타임 동일 로직 보장).
3. `build_learning_path` — `fetch_internal_prerequisite_edges` 호출을 위 둘의 조합으로 교체
   (얇은 조합 유지).

**안전성 논증**:
- **사이클 도입 없음** — bounded 도달 관계는 참 ancestor 관계의 부분집합이고, ancestor 관계는
  DAG 위에서 비순환이다. `has_cycle` 계약 불변, 방어적 잔여 메커니즘도 그대로 유효하다.
- **bounded reachability는 전이적이지 않다** — A→B 3홉 + B→C 3홉인데 A→C가 6홉이면 누락된다.
  Kahn은 임의 DAG를 받으므로 정합성 문제는 없고 순서가 덜 결정될 뿐이다. **이 한계를
  docstring에 정직히 남긴다.**
- **후보 집합 불변** — 학생에게 보이는 선수 개수·구성이 전혀 바뀌지 않는다
  (`recommend_prerequisite_gaps` 미변경). **교수학 리스크가 구조적으로 0**인 개입이다.
- **비용** — prerequisite 엣지가 전 코퍼스 2,210행이고 depth1 후보 집합은 최대 4노드,
  depth5도 p99 33·최대 55다. bounded CTE가 유의미하게 비쌀 수 없다.
- **날조 금지** — 전이 엣지에 합성 `edge_strength`를 **부여하지 않는다**(§2-⑨).
  `LearningStep.edge_strength`는 원래 origin C로부터의 직접 엣지 강도이므로 이 변경으로 값이
  바뀌지 않는다 — 테스트로 동결한다.

**변별력**: `A→X→B`(X 비-막힘) fixture에서 **순서가 실제로 역전되어야 한다**:
- before: `ordering_edge_count=0` · `tiebreak_only` · weakness(B) < weakness(A)면 **B가 먼저**
- after: `ordering_edge_count=1` · `topological` · **A가 먼저**

순서가 뒤집히지 않는 fixture(tiebreak와 위상이 우연히 일치)만으로 검증하면 위장이다.
**D2의 두 필드가 여기서 계측기로 소비된다** — D2가 dead field가 아니라는 증명이기도 하다.

**acceptance 후보**:
1. 현행 실측 고정 — `A→X→B`(X 비-막힘) fixture에서 현행이 순서를 못 잡음을 먼저 테스트로 재현.
   D1 리포트의 96/356(27.0%) → **249/356(69.9%, 5홉)** 예측치를 문서에 고정
   (87.1%는 무한 도달 천장으로만 병기)
2. 정합 설계 본체 — `fetch_ordering_subgraph` + `derive_ordering_edges`(순수) +
   `build_learning_path` 배선 교체. **`order_learning_path`·`_tiebreak` 수정 0**, 기존 테스트
   18건 무수정 통과, 스키마·마이그레이션 0, 후보 집합(`recommend_prerequisite_gaps`) 불변
3. 변별력 — 위 서술의 **순서 역전** 양방향 + D2 필드 0→1 동반 변화
4. 날조 방지 — 전이 엣지에 합성 강도 부여 0을 테스트로 동결. `has_cycle`·`is_cycle_residual`
   계약 회귀 0. bounded reachability가 전이적이지 않다는 한계를 docstring 명시
5. **범위 밖 명시** — `max_depth` 기본값 변경(§4 P1)·전역 경로(§5)·`Assessment.recommended_path`
   소생(§4 P3)·`prerequisites`/`coaching` 엔드포인트 정렬 변경은 포함하지 않는다

**의존**: `PATH-01`(개선폭을 수치로 확정 — 측정 없는 도입 없음)·`PATH-02`(런타임 계측기 —
변별력 확보). **태스크**: 신설 — `PATH-03-transitive-ordering-edges` (S4·priority 4).

---

### 페이퍼 갭 3건 (**코드 0 · 태스크 신설 없음**)

**P1 — `max_depth` 기본값 1→2 전환.**
수치는 유혹적이다(직접 엣지 기준 27.0% → 99.9%). 그러나 후보 집합이 356 → 1,712 사례군으로
넓어져 **학생에게 제시되는 막힌 선수 개수 자체**가 바뀐다. 게다가 이 파라미터는
`prerequisites`·`coaching`·`learning-path` **3 엔드포인트가 공유**한다(`api/me.py` `MaxDepth`) —
경로 하나 고치자고 코칭 발화 대상까지 바꾸는 개입이다. recall↑ vs 노이즈↑의 트레이드오프를
판정할 학습자 신호가 0행이다. 그리고 **D3가 후보 집합을 전혀 건드리지 않고 69.9%를 얻으므로
순서는 D3가 먼저다.**
*발화 조건*: D3 착지 후에도 `ordering_basis=tiebreak_only`가 실사용에서 유의미 비율로
관측되고, `REC-01` 도달 리포트가 '미도달'을 해제해 경로 길이·완주 신호를 볼 수 있게 됐을 때.
그때 엔드포인트별 기본값 분리(`learning-path`만 2)도 함께 검토한다.

**P2 — L6 자동 커리큘럼 정렬 차원⑥ '인접 개념 순서'.**
`06_application_modes.md`가 이미 "잔여(후속)"로 잡아둔 항목이다. 미구현의 원인은 코드가
아니라 **데이터 0**이다 — 출판사별 목차 순서 데이터가 없고, `curriculum_entry.textbook_unit_refs`는
배열이지 순서가 아니며, `atom_node`에 순서 컬럼이 없다. §2-⑧의 함정(그럴듯한 `<영역>-U#-S#`
번호 2,466건)까지 있어 **지금 태스크를 열면 날조로 끝난다.**
*발화 조건*: 출판사별 교과서 목차 순서 데이터가 실제로 반입되고 데이터 카드(`docs/data/*.md`)가
서면. 그 전에는 차원③(깊이)만 구현된 현 상태가 **정직한 상태**다.

**P3 — `Assessment.recommended_path` JSONB 소생.**
`db/models/assessment.py:122`의 이 컬럼은 **writer 0 · reader 0**이다(소비처는 스키마 왕복
테스트뿐). `S4-18` notes가 "dead table 소생은 범위 밖"을 이미 선언했다. 전역 경로가 발화하면
자연스러운 착지점이지만, **지금 writer만 붙이면 reader 없는 컬럼이 다시 생긴다** — 반복 실수의
재생산이다.
*발화 조건*: 전역 경로 4조건(§5)이 모두 충족돼 **reader가 먼저 실재**할 때.
**writer가 reader보다 먼저 가지 않는다.**

### §3 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `PATH-01-learning-path-orderability-report` | D1 | S3 | 3 | 위상 제약 밀도 미관측. 코퍼스만 읽으므로 입력 루프와 무관하게 즉시 착수 가능. 응답 변경·알고리즘 변경은 범위 밖 |
| `PATH-02-learning-path-ordering-honesty` | D2 | S3 | 3 | 정직 표기가 발생 0건인 사이클 축에만 붙어 있고 96.4%인 제약 0 축에는 없음. D3의 계측기 |
| `PATH-03-transitive-ordering-edges` | D3 | S4 | 4 | `learning_path.py:258`이 스스로 "후속 범위"라 적고 등재하지 않은 항목. 27.0%→69.9%·후보 집합 불변 |

태스크는 전건 `backlog.py add` CLI 경유로 등재한다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다.

**중복 회피 확인**: 복습 시간축·목표축 = `S4-18` 보유 / attempt 입력 루프·도달 관측 = `REC-01`
보유 / 학년·목표 조립 = `PED-05` 보유 / 그래프 허브·전파 분석 = `ARCH-17`(done) 보유.
**어느 것도 침범하지 않는다.**

---

## §4. 정직한 공백 — 지금 하지 않는 것 (6종)

| # | 항목 | 왜 지금 아닌가 |
|---|---|---|
| ① | 경로 완주율·이탈 지점 계측 | 클라 소비 0이라 완주 이벤트의 생산자가 없다. `REC-01` 도달 해제가 선행 |
| ② | `edge_strength` 기반 런타임 weight pruning | `edge_design_part3_review.md`가 "학습경로 랭킹 소비처가 생길 때"로 이미 유보. 소비처가 아직 0 |
| ③ | `EdgeType` 6종 중 `PREREQUISITE` 외 5종의 경로 활용 | 적재 0건(`curriculum_module_gap_review.md` 페이퍼 갭과 동일 판정) — 신호 없이 쓰면 날조 |
| ④ | 경로 단계별 예상 소요 시간 | §2-② 계열(생산자 없는 신호). `duration_seconds`는 스키마만 있고 0행 |
| ⑤ | 개념 그래프 437 축(legacy)에서의 경로 | `LEGACY_SNAPSHOT` 격하 — 런타임 read 금지. 원자 백본이 단일 truth source |
| ⑥ | 경로 결과 캐싱 | 조회당 쿼리 2회(gaps + 내부 엣지)·집합 최대 55노드. 캐시가 필요하다는 측정이 없다 |

---

## §5. 유보 항목의 발화 조건 — 학생 전역 학습 경로 (기능 54의 핵심)

**판정: 지금 만들지 않는다.** 네 개의 독립된 사유가 있고 어느 하나만으로도 충분하다.

1. **입력이 0이다.** 전역 경로의 노드 공급원은 "이 학생의 모든 약개념"인데
   `problem_attempt` 0행 → `/me/diagnosis/concepts`가 **항상 빈 결과**다(`REC-01` 실측).
   만들면 **항상 빈 배열을 반환하는 엔드포인트**가 된다 — §6 반복 실수 4·5회차의 재현이다.
2. **소비처가 0이다.** 개념별 경로조차 Flutter 실사용 13종에 없다. 소비되지 않는 것 위에 더
   큰 것을 얹는 건 "만들고 켜지 않음"의 확대재생산이다.
3. **순서 근거가 아직 무력하다.** 단건 경로가 96.4%에서 제약 0인데 그 위에 전역 병합을 올리면
   "정렬됐다"는 착시가 훨씬 커진다. D1~D3로 **단건 순서의 정직성이 먼저** 서야 한다.
4. **전역 경로는 필연적으로 미채택 항목을 부른다.** 여러 약개념을 하나의 순서로 관통하려면
   "무엇을 건너뛸까"(§2-①)와 "각각에 얼마를 배분할까"(§2-②③)를 피할 수 없다. 셋 다 영구 미채택이다.

**발화 조건 — 4개 모두(AND, any 아님)**:

| # | 조건 | 검증 방법 |
|---|---|---|
| ① | `REC-01` 도달 리포트가 `problem_attempt` **'미도달' 해제** + 학습자당 약개념 **2건 이상** 실측 | 전역 경로는 약개념 2건 이상에서만 정의상 의미가 있다(1건이면 개념별 경로와 동일) |
| ② | 클라이언트가 `weak-concepts` 또는 `learning-path`를 **실제 호출** | 소비처 실재 확인 — "존재함"과 "돌아감"의 구분 |
| ③ | `PATH-01` 리포트가 **다중 약개념 교차 집합**의 제약 밀도를 산출하고, 전역 병합이 개념별 나열보다 **순서를 더 결정한다**는 수치를 낼 것 | 병합이 순서를 더 안 정하면 전역 경로는 순수한 복잡도 증가다. 이 축은 `PATH-01` 확장으로 가능(신규 태스크 0) |
| ④ | `PED-05` LearnerState 착지 — 학년·목표를 **단일 조립기**로 받을 수 있을 것 | 조각 직접 조회 중복 방지(PED-05 ①이 그 계약을 소유) |

③이 특히 중요하다: **전역 경로의 가치는 측정 가능한 명제**다("병합이 순서를 더 결정하는가").
그 수치가 나오기 전에 만드는 것은 "측정 없는 도입 없음" 위반이다. 그리고 이 측정은
**`PATH-01` 리포트의 축 하나 추가로 가능**하므로 유보 결정에 별도 비용이 들지 않는다.

---

## §6. 반복 실수 — "완비된 소비 경로 + 미도달 공급원" 8회차 (새로운 형태·재발방지 등재)

`curriculum_module_gap_review.md` §6의 7회차 표를 8회차로 확장한다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| 4 | `POST /v1/me/attempts` 클라 호출 0회 → 학습자 모델 입력 0(REC D1) | 만들고 **입력을 잇지 않음** |
| 5 | 개인화 가중 기본 off · 개념 추천 API 6종 클라 소비 0(REC D1) | 만들고 **켜지 않음** |
| 6 | `select_probe` 후보 공급원 0 → 도구6 상시 실패(REC D2) | 만들고 **공급원을 잇지 않음** |
| 7 | `LearningObjective` 스키마·컴파일러·런타임 API 완비 + 실데이터 895건 중 1건(CUR D2) | 만들고 **분해하지 않음** |
| **8** | **Kahn 위상정렬 완비 + 기본 `max_depth=1`이 96.4% 사례에서 제약을 0으로 만듦(D1)** | 만들고 **기본값으로 껐음** |

8회차는 앞의 일곱과 **결정적으로 다르다**: 배선도 됐고 적재도 됐고 켜져 있다. 엔드포인트는
200을 반환하고, 응답 형태가 완전하며, 테스트 18건이 전부 green이다. 꺼진 것은 **파라미터
기본값 한 개**이고, 그 결과 알고리즘이 자기 자신의 fallback으로 조용히 강등된다.
**앞의 일곱은 "돌지 않아서" 안 보였고, 8회차는 "돌아서" 안 보였다.**

**재발방지 형태로 남길 원칙**:
> **알고리즘을 붙였으면, 그 알고리즘이 *실제로 작동한 비율*을 응답이나 리포트가 말해야 한다.**
> "정상 응답 200"은 "알고리즘이 일했다"의 증거가 아니다.

D1(리포트)·D2(응답 표기)가 그 이행이다.

**부수 관찰(태스크 신설 없음)**: `learning_path.py:258`이 스스로 "후속 범위"라 기록한 항목이
백로그에 없었다. 다만 백엔드 전수에서 이 표기는 **1건뿐**이므로 "docstring TODO 일제 점검"
태스크는 **만들지 않는다** — 패턴이 아니라 단발이다. 대신 원칙만 남긴다:
> **docstring은 백로그를 대신하지 못한다.** 코드가 "후속"이라 적었으면 태스크로 등재하거나,
> 등재하지 않기로 한 판단(페이퍼·미채택)을 문서에 남긴다.

---

## §정정 — 정본 stale 3곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 | 처리 |
|---|---|---|---|
| `l2/learning_path.py:1-6` 모듈 docstring | "막힌 선수개념들의 *선수 위상정렬*(근본→말단) 순서화"를 **무조건적으로** 서술 | 기본 파라미터(`max_depth=1`)에서 **96.4%가 tiebreak 강등**. 위상정렬은 3.6%에서만 비자명 | `PATH-02` 안에서 조건부 서술로 정정(이 문서는 `src/` 변경 0) |
| `api/me.py get_my_learning_path` docstring | "**추천의 depth/strength 정렬과 다르다**"를 강조 | 기본값에서는 *대부분 다르지 않다* — 둘 다 tiebreak 정렬이고 depth 방향만 반대 | `PATH-02` 안에서 정정 |
| `06_application_modes.md` 차원⑥ 잔여 서술 | "잔여(후속): 차원 1·2·4~7 …"로만 적혀 있고 **막힌 이유**가 없다 | 차원⑥이 막힌 원인은 코드가 아니라 **출판사별 목차 순서 데이터 0**이며, `subunit_code` 2,466건이 오인 유도 함정이다 | **이 커밋에서 정정**(docs 변경) |

---

## 부록 — 실측 근거 (2026-08-03 실측)

대상: `data/corpus/atom_graph_v1/graph.json` — **2,683 concepts · 2,210 edges(전량 `prerequisite`)**.
아래 스크립트로 본문의 모든 수치가 재현된다(읽기 전용·DB 접근 0).

```python
import json, collections
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
E = [(e['from_code'], e['to_code']) for e in g['edges'] if e.get('relation') == 'prerequisite']
pred = collections.defaultdict(set); succ = collections.defaultdict(set)
for f, t in E:
    pred[t].add(f); succ[f].add(t)
nodes = {c['code'] for c in g['concepts']}
Eset = set(E)

def reach(a, hops):                      # a에서 후행 방향 hops 이내 도달 노드
    seen = set(); frontier = {a}; d = 0
    while frontier and d < hops:
        d += 1; nxt = set()
        for x in frontier:
            for y in succ[x]:
                if y not in seen:
                    seen.add(y); nxt.add(y)
        frontier = nxt
    return seen

for hops in (1, 5, 99):                  # 1홉=현행 직접 / 5홉=구현 예산 / 무한=천장
    tot = direct = trans = full = partial = parallel = 0
    for c in nodes:
        S = set(pred[c])
        if len(S) < 2:                   # 순서화가 성립할 수 있는 모집단만
            continue
        tot += 1
        R = {a: reach(a, hops) & S for a in S}
        if any((a, b) in Eset for a in S for b in S if a != b):
            direct += 1
        if any(b != a for a in S for b in R[a]):
            trans += 1
        srt = sorted(S); npairs = len(S) * (len(S) - 1) // 2
        det = sum(1 for i, a in enumerate(srt) for b in srt[i + 1:] if b in R[a] or a in R[b])
        full += det == npairs; partial += 0 < det < npairs; parallel += det == 0
    print(hops, tot, direct, trans, full, partial, parallel)
```

**산출**

| 지표 | 값 |
|---|---|
| 직접 선수 개수 분포 | 0개 915 · 1개 1,412 · 2개 278 · 3개 70 · 4개 8 |
| 직접 선수 2개 이상(모집단) | **356** (전체의 13.3%) |
| 1홉 순서화 가능 / 순서쌍 | **96 (27.0%)** / 106 |
| 5홉 순서화 가능 / 순서쌍 | **249 (69.9%)** / 304 |
| 무한 순서화 가능 / 순서쌍 | 310 (87.1%) / 428 |
| 결정도(1홉 / 5홉 / 무한) | 64·32·260 / 201·48·107 / 285·25·46 |
| `max_depth=2` 집합≥2 · 내부 직접 엣지 보유 | 1,712 · **1,711 (99.9%)** |
| 선수집합 크기 | depth2 최대 11·p99 8 / depth5 최대 55·p99 33·평균 6.2 |
| `subunit_code` 보유 노드 | 2,466 / 2,683 (§2-⑧ 함정) |
| `"후속 범위"` 표기 전수(`src/`) | **1건** — `l2/learning_path.py:258` |
| `tests/backend/l2/test_learning_path.py` 테스트 수 | 18 |

**자체 정정 기록**: 설계 검토 중 전이 도달 수치를 **87.1%**로 잡았으나, 그것은 **무한 도달**
기준이었다. 제안된 구현 예산(`MAX_PREREQUISITE_DEPTH=5`)에서의 정직한 값은 **69.9%**다.
본문·acceptance는 69.9%를 쓰고 87.1%는 도달 불가능한 천장으로만 병기한다.
(교훈: 개선폭을 인용할 때는 **실제로 구현할 예산에서의 값**을 쓴다 — 천장 수치는 설득력이
크지만 acceptance에 넣으면 달성 불가 기준이 된다.)
