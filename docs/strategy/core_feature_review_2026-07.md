# 교육앱 핵심 기능 목록 검토 — 저장소 실측 대조 (정본)

> **검토 대상**: 「교육앱으로 구현 가능한 핵심 기능 6종 + 현재 기술로 어려운 영역 4종」(2026-07-18 Kiki 제시 목록 — 학년 무관 공통 고가치 기능 카탈로그)
> **검토 방법**: 목록의 각 기능·난제 주장을 저장소 정본(코드·백로그·스키마·설계 문서 실측)과 1:1 대조해 **① 이미 구현 ② 부분/스텁 ③ 진짜 공백 ④ 정직하게 경계지어진 난제**로 분류.
> **자매 문서**: `docs/strategy/subject_expansion_roadmap_review.md`(동일 "실측 대조" 형식 선례) · `docs/architecture/system_deep_dive.md`(영역별 현재 상태 심화)
> **상태**: 2026-07-18 검토 완료. 공백 2건은 §5 하네스 권고에 따라 백로그 등재(`ARCH-13`·`S4-02`·`S4-03`).

---

## 1. 총평

**제시된 6기능 분류는 타당하며, 그중 4종은 WhyMath의 L1–L4 독립 코어에 이미 실질 구현돼 있다.** 난제 4종도 저장소가 이미 정직하게 범위 밖으로 경계짓고 있어, 이 목록은 "우리가 지금 무엇을 만들지"의 신규 계획이라기보다 **기존 코어를 외부 일반론 렌즈로 재확인**하는 성격이다. `system_deep_dive.md §1`의 자기진단 그대로 — **"코어는 과잉 성숙, 제품 루프는 미성숙"**이며, 코어 기능의 존재가 아니라 *실사용 검증*이 현 단계 리스크다.

다만 이 일반론 프레이밍을 **그대로 채택하면 WhyMath의 정체성을 과소평가**하는 지점이 3곳 있고, **진짜 공백 2건**(증명 학습·시각화 유형 확장)이 있다. 아래가 그 목록이다.

**과소평가 위험 3건**(일반 표현 ↔ WhyMath 실제):

| # | 일반 목록 표현 | 과소평가/왜곡 위험 | WhyMath 정본 |
|---|---|---|---|
| A | #1 "힌트 제공" | 차별점(**답 미루기 4단계**·소크라테스 6종·정서안전)을 평면화. WhyMath는 "빠른 답"이 KPI가 아니라 *답 미루기 도달 깊이* ≥2.5가 KPI | `l4/hint_deferral.py`(방향→의사코드→부분풀이→전체풀이, 4는 PRD 척도 밖 안전망) · CLAUDE.md "정답 바로 제공 금지" |
| B | #4 "정의·정리 연결" | *새 관계 타입 신설* 유혹 → 7대 붕괴 1번(관계 폭발). "정의·정리"는 **엣지가 아니라 노드 인지유형** | `schema/concept.py:150`(DEFINITION/THEOREM/TECHNIQUE/PATTERN/VISUAL_REASONING) — 인지유형은 노드 속성, 관계는 별개 |
| C | #4 "학습 경로 추천" | "전체 그래프 순회"로 오해 위험 → attention dilution | Minimal Reasoning Subgraph(depth≤2·nodes≤12~20·tokens≤3000) 코드 동결. 순회는 `prerequisite`만 (`l2/prerequisite_recommendation.py` 재귀 CTE) |

---

## 2. 기능별 실측 대조표 (6종)

| # | 기능 | 판정 | 근거 위치 | 비고 |
|---|---|---|---|---|
| 1 | **AI 튜터**(자연어 QA·단계 설명·힌트) | 🟢 **완전 구현** | `api/coach.py`(`coach_decide`·`create_session`·`append_turns`) · `l4/polya/engine.py`(이해→계획→실행→검토) · `l4/socratic/select.py`(6종) · `l4/hint_deferral.py`(4단계) · `l4/tone_filter.py`(정서안전) · `l3/router.py`(LLM 라우터 경유) · WH-1 튜터링 하네스 | 일반 "힌트"를 훨씬 초과 — 답 미루기·소크라테스·Polya·정서안전이 코어. 라이브 LLM 키는 S1 사람 병목(Phaiakes9) |
| 2 | **문제 생성기**(난이도·유형·오답 재출제) | 🟡 **구현(스켈레톤+규칙), LLM 경로 스텁** | `l3/equivalent/orchestrator.py`(생성→수용게이트→임베딩중복제거→저장) · `skeleton_generator.py` 외 유형별 20+(삼각·수열·미적분·지수로그…) · `difficulty.py`(규칙기반) · `llm_generator.py`(결정론적 placeholder — 키 대기) · `l6/retake/gating.py`(재수/N수 선택) | "오답 기반 재출제"는 **부분** — MC 오답지→오개념 역추적 + 재수 트랙 선택은 있으나, *학생 특정 오답에서 새 문제 폐루프 재생성*은 미구현. 저작권: 교과서·평가원 본문 미복제, 자체 **동등문제**로 대체 |
| 3 | **오개념 DB**(분류·원인·교정전략) | 🟢 **완전 구현** | `l1/misconception/`(카탈로그 로더·populate) · `l4/misconception/`(~40파일: `diagnose.py`·`hypothesis.py`·`intervene.py`·`judge.py`·`semantic/matcher.py` pgvector) · coach 연동(`_compute_matches`·`_apply_hypotheses`) | M-id 코퍼스 839. **Reactive retrieval**(초기 preload 금지·가설 감쇠 ×0.85)로 오염 방지. 부채: canonical ID 수렴(kebab 30 ↔ M-id 839 3중 표현) 진행 중 |
| 4 | **개념 그래프**(선수학습·정의정리·경로추천) | 🟢 **구현**(Postgres/pgvector 투영) | `l1/concept_graph/`+형제(`atom/formula/skill/strategy_graph`) · `l2/prerequisite_recommendation.py`(재귀 CTE 다홉) · `l2/learning_path.py`(Kahn 위상정렬) · `api/concepts.py` | 원자 백본 1,837노드·선수 3,220엣지(`system_deep_dive.md`). 라이브 **Neo4j 미채택**(pgvector 단일평면). 관계 타입: 코드 5종(`schema/concept.py:256` PREREQUISITE/COMPOSED_OF/ANALOGOUS_TO/EXTENDS/CONTRASTS) vs 설계 정본 7종 — **명명/세분화 divergence(수렴 필요)**. 순회는 `prerequisite`만 (원칙 준수) |
| 5 | **증명 학습 지원**(구조 시각화·단계 피드백·다중증명 비교) | 🔴 **부재(진짜 공백)** | 학생 대면 컴포넌트 0건. 인접: `whs/`(WH-S 솔버가 검증된 단계풀이 생성 — **오프라인·SFT용·학생 경로 미개입**) · `l3` `lean_verified` 태그·`Justification` 블록(얇은 벽돌) · `l4/lthc/adapt.py`("증명"은 NRICH 확장 프롬프트 문자열로만 존재) | §3.1 상세. 서술형·증명 스텝은 `verify_step`이 설계상 `unverifiable` 반환(`04a` R5) → 학생 기능은 *이 정직 경계 안에서만* 가능 |
| 6 | **시각화 엔진**(함수·기하·벡터·행렬·미적분 애니) | 🟡 **부분 구현 + 백로그 미추적** | 생성: `l3/visualization.py`(spec 4종: `interactive_graph_2d`·`interactive_surface_3d`·`simulation_probabilistic`·`animation_prerendered`) · 렌더: `web/graphing-calculator/`(mathjs·three.js) · `l4/{scene_generation,learning_scene,visualization_policy}.py` · mobile `scene_renderer.dart` | §3.2 상세. **구현**: 2D함수그래프·3D곡면·확률시뮬. **부재**: 기하·벡터·행렬변환·미적분 애니메이션, `animation_prerendered`(Manim) 렌더 경로. **부채**: 상당 코드가 존재하나 소유 백로그 태스크 없음 |

**핵심 요지**: 6기능 중 5기능(1·2·3·4·6)은 코어에 실재하며, 진짜 공백은 **#5(증명 학습) 1건 + #6의 유형 확장/추적**뿐이다. 즉 이 목록은 "미구현 로드맵"이 아니라 **"이미 지은 것의 재확인 + 2개 정직한 공백"**이다.

---

## 3. 진짜 공백 2건 상세

### 3.1 #5 증명 학습 지원 — 학생 대면 기능 부재 (형식증명은 솔버측·S5)

**분리해서 봐야 한다.** 저장소에는 *시스템측 증명 인프라*가 있으나 *학생 대면 증명 교수*는 없다.

- **있는 것(시스템측)**: WH-S 솔버 하네스(`whs/harness.py`·`solution_bank.py`·`db/models/verified_solution.py`)가 검증된 단계별 풀이를 생성하고, `l3/verify_step.py`가 SymPy로 스텝을 검증한다. 형식증명(Lean 4+Mathlib)은 `03b_wh_s_solver_harness.md` Tier3에 설계됐으나 **오프라인 자기진화(SFT/PRM 데이터)용이며 학생 세션 경로에 개입하지 않는다.** 로드맵상 S5(마지막)이고, 전제 난제(자동형식화)로 인해 장기 보류다.
- **없는 것(학생측)**: 증명 구조 시각화·증명 단계 피드백·여러 증명 방식 비교 — 어느 것도 학생 UI/API로 존재하지 않는다. "증명"이라는 문자열은 `l4/lthc/adapt.py`의 NRICH 확장 후보(일반화·변형·**증명**·다른 풀이)로만 등장한다.
- **정직 경계(설계 제약)**: `04a` R5에 따라 서술형 논증·증명·보조선 기하·경우 나누기 스텝은 `verify_step`이 **`unverifiable`을 반환**하고, 하네스는 그 경우 답을 누설하지 않도록 설계됐다. → **학생 대면 증명 기능은 "네 증명이 맞다"류 허위 확언을 할 수 없는 경계 안에서만** 만들어야 한다(CLAUDE.md AI 금기: "확실하지 않을 때 자신 있게 말함 금지"). 이 제약이 이 기능을 실제로 어렵게 만들며, 파일럿 이후로 미루는 근거다.

→ 등재: `S4-02-proof-learning-support`(math-completion·후순위).

### 3.2 #6 시각화 엔진 — 유형 확장 공백 + 백로그 미추적 부채

- **구현됨**: `l3/visualization.py`가 선언적 JSON spec 4종을 생성·검증하고(`animation_prerendered`는 슬90 불변식으로 *조작 불가*), 웹 계산기(`graph2dSpec.js`)가 2D 함수그래프·3D 곡면(three.js)·확률 시뮬레이션을 렌더한다. 아키텍처 경계 준수(L3=spec 생성·검증, L5=렌더; 영상 bytes 반환은 경계 위반으로 금지).
- **부재**: 기하(작도)·벡터·행렬 변환·미적분 과정 애니메이션에 대응하는 spec 타입·렌더러가 없다. `animation_prerendered`(Manim)는 spec 타입만 있고 **렌더 경로가 어디에도 없다**(`graph2dSpec.js`에서 `null` 반환·"웹 렌더 경로 없음").
- **부채(추적 공백)**: 이 서브시스템은 상당한 코드가 있으나 **소유하는 백로그 태스크가 없다**("built but untracked"). 유일한 백로그 접점은 ARCH-12(QuizMode 클라이언트 채점 결정)의 방계 언급뿐이다.
- **확장 원칙**: 새 유형은 *선언적 spec + 렌더러 플러그인* 구조(`05_interaction.md`)를 유지해 **spec 타입 추가로만** 해결한다(새 추상·구현체 이름을 노드에 넣지 않음 — 렌더러는 플러그인).

→ 등재: `ARCH-13-visualization-harness-tracking`(infra-debt·지금 가능·기존 코드 추적화) + `S4-03-visualization-type-expansion`(math-completion·후순위·신규 유형).

---

## 4. 난제 4종 — 이미 정직하게 경계지어짐 (확인)

제시된 4개 난제는 **저장소가 이미 범위 밖으로 정직하게 경계**짓고 있다. 이 목록을 계기로 *과장 주장*을 하지 않는 것이 검토의 핵심 결론이다.

| 난제 | 저장소 경계 정본 | 판정 |
|---|---|---|
| 독창적 새 증명 자동발견 / 형식증명 | `03b` R-S5: 자동형식화(한국어 문장→Lean 명제)를 장기 트랙으로 분리·초기 역량 주장에서 제외. Tier3 Lean은 로드맵 S5(마지막) | ✅ 경계됨 — 초기 주장 없음 |
| 연구수준 창의적 직관 생성 | 어디에도 주장 없음. 가장 가까운 정직 선언은 **개념 시퀀스 동치성 자동판정 = "미해결 연구 난제"**(`03_content_generation.md`·`system_deep_dive.md §4`) — 필요·충분조건 아님, 휴리스틱 1차 분류 + 사람 확정, *제품 기능으로 단정 금지* | ✅ 경계됨 |
| 완전히 새로운 이론 체계 제안 | 주장 없음. `knowledge_fabric_vision_v1.md §4`: **"OS 조기 정체성화 금지"** — Metadata OS는 내부 지향, 대외 정체성은 fabric 수렴 전까지 기존 전략 문서 준수 | ✅ 경계됨 |
| 여러 미해결 문제 일반적 자동해결 | `03b §10`: "검증 가능한 해결"의 정직한 경계는 초기 **Tier1+2**(답 중심 문항·수능 전 범위). 미해결/열린 문제 해결은 결코 주장하지 않음. "새 유형" 진척은 *미학습 패턴 초견 정답률*로만 측정 | ✅ 경계됨 |

**지배 원칙**(`superhuman_verification_standard.md` · CLAUDE.md 검증 권위 서열): 기계 권위는 *측정으로 증명된 곳*에만, **"측정 미달·판정 불가(undecidable)는 인간 큐로 정직 폴백 — 모르면 모른다."** 의사결정 우선순위상 학생 안전·정확성(1·3위)이 개발 속도(7위)에 우선하므로, 난제 영역의 과장은 구조적으로 금지된다.

---

## 5. 하네스 정합 권고 (백로그 재정렬 금지)

- **백로그 재정렬 없음.** 이 검토는 착수 순서를 바꾸지 않는다(최신 main 기준 파일럿 측정 하네스 `S3-04`는 이미 타 세션이 `done` 처리). 기능 확장(#5·#6b)은 **E2E 루프가 실학생으로 검증된 이후**의 후순위이며, `system_deep_dive.md`의 최대 리스크(검증 부채)와 정합한다. `ARCH-13`(시각화 추적·infra-debt)은 신규 구현이 아니라 위생 작업이라 근시일 후보로 떠도 파일럿 작업을 선점하지 않는다.
- **후순위 강제**: `S4-02`·`S4-03`은 `S3-01-pilot-cohort`(파일럿 실주행)에 의존시켜, selector가 파일럿 검증 전에는 후보로 노출하지 않게 한다 — "루프 검증 전 기능 확장 금지"를 사람 기억이 아니라 **알고리즘으로 강제**.
- **feature-depth ↔ breadth 관찰**: #5·#6은 *교수 기능 깊이* 항목인데, 내부 사다리 S0–S5는 *breadth/검증*(정합성→슬라이스→콘텐츠→파일럿→K-12→확장) 축이라 자연스러운 자리가 없다. 편의상 S4에 배치하되, 향후 feature-depth 축이 필요해지면 재분류 대상임을 기록한다.
- **모든 신규 작업은 CLI + MEMORY 로그 경유** — 대장 손편집 금지(S1-14 사고 교훈).

---

## 6. 검토 근거 (실측 출처)

- AI 튜터: `src/backend/whymath_backend/api/coach.py` · `l4/polya/engine.py` · `l4/socratic/select.py` · `l4/hint_deferral.py`(`decide_hint_level`·`HintLevel = Literal[1,2,3,4]`) · `l4/tone_filter.py` · `l3/router.py`
- 문제 생성기: `l3/equivalent/orchestrator.py`·`skeleton_generator.py`·`difficulty.py`·`llm_generator.py` · `l6/retake/gating.py`
- 오개념 DB: `l1/misconception/` · `l4/misconception/`(`diagnose.py`·`hypothesis.py`·`intervene.py`·`semantic/matcher.py`) · `04b_misconception_judge_graduation.md`
- 개념 그래프: `l1/concept_graph/` · `l2/prerequisite_recommendation.py`·`l2/learning_path.py` · `schema/concept.py:150`(인지유형)·`:256`(관계 5종) · 원자 백본 수치 `docs/architecture/system_deep_dive.md §2`
- 증명 학습(부재): `whs/harness.py`·`db/models/verified_solution.py`(솔버측) · `l3/verify_step.py` · `l4/lthc/adapt.py`(NRICH 확장) · `docs/architecture/03b_wh_s_solver_harness.md` Tier3·§10 · `04a_wh1_tutoring_harness.md` R5(`unverifiable`)
- 시각화: `l3/visualization.py`(spec 4종·슬90 불변식) · `src/web/graphing-calculator/src/lib/graph2dSpec.js` · `l4/{scene_generation,learning_scene}.py` · `docs/architecture/05_interaction.md`·`05b_visualization_classification.md`
- 난제 경계: `03b §10`·R-S5 · `03_content_generation.md`(동치성 미해결) · `system_deep_dive.md §4·§9` · `knowledge_fabric_vision_v1.md §4` · `docs/standards/superhuman_verification_standard.md` · CLAUDE.md(검증 권위 서열·AI 금기)
