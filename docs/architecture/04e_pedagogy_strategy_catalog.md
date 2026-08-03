# 04e. 교수전략 카탈로그와 격차 완결 — 외부 프레임워크 대조 판정 (L4/L3)

> **성격**: L4(교수학 엔진)의 서브 설계 — `04`(교수학 결정)·`04a`(WH-1 하네스)·`04b/04c`(오개념)·`04d`(교수법
> 선택·학습)에 이어 **`04e`(교수전략의 *서술 자산*과 잔여 격차의 완결)**. 04d는 참조하되 개정하지 않는다 —
> 04d = 전략을 *고르는 메커니즘*, 04e = 전략을 *서술하는 카탈로그* + 외부 대조에서 드러난 공백의 설계.
>
> **유래**: Kiki 제공 외부 일반 교수전략 프레임워크(2026-07-28 docx — WhyMath 전용이 아닌 일반 틀. 4기능:
> ⑭교수전략 라이브러리 ⑮설명 방식 선택 ⑯비유/예시 생성 ⑰질문 생성)를 **전 항목 대조**하여 수용/거부/변형을
> 판정했다(§2). 외부 틀은 체크리스트로만 쓴다 — WhyMath 방향(구축 플레이북 불변식·7계층·반게임화·reactive
> 오개념)이 항상 우선한다.
>
> **한 줄**: 전략은 카탈로그로 서술하고 선택은 규칙·게이트가 하며, 설명방식은 별도 축이 아니다 — 외부 4기능을
> 기존 3축(전략·슬롯/자산·L5 시각화)으로 분해 흡수한다.

---

## 1. 용어 3축 구분 (컨텍스트 오염 방어 — 이 표가 최상단에 오는 이유)

"전략(strategy)"이라는 낱말이 이 저장소에서 **서로 다른 3개 축**을 가리킨다. 특히 `ANALOGY`(비유·교수 전략)와
`strategy.analogy`(유추·문제 공략 전략)는 **같은 영단어·다른 개념**이다. 미래 세션·서브에이전트·LLM 프롬프트가
"전략"으로 검색하면 3축이 섞여 나오므로, 이 문서를 포함한 모든 신규 문서·모듈은 아래 구분을 전제한다.

| 축 | 무엇 | 주체 | 정본 | 예 |
|---|---|---|---|---|
| **교수전략** (`PedagogyStrategy`) | *교사가* 어떻게 가르칠까 — 실행용 교수법 폐쇄 10종 | 시스템(L4 선택·L3 렌더) | `03c §2.1`·`schema/enums.py` | `ANALOGY` = **비유**로 직관 형성 |
| **문제 공략 전략** (`StrategyNode`) | *학생이* 문제를 어떻게 공략할까 — Polya 계획 단계의 휴리스틱 8종 | 학생(학습 대상) | `data/corpus/strategy_graph_v1/`·`docs/data/strategy_graph_v1.md` | `strategy.analogy` = **유추**(비슷한 문제로 치환) |
| **전략 레퍼토리** (WH-1 §11) | 학생이 *보유·구사하는* 휴리스틱의 추적·페이딩·전이 측정 | 하네스(L4 관측) | `04a §11` | 레퍼토리 ~20종·스캐폴딩 페이딩 |

- `strategy_graph_v1.md` §4가 이미 세 축(`StrategyNode` ≠ `ReasoningType` ≠ `approach_type`)을 구별한다 —
  본 표는 거기에 **교수전략 축을 추가로 병치**한 것이다.
- 본 문서에서 "전략"은 별도 수식이 없으면 **교수전략**(`PedagogyStrategy`)을 뜻한다.

---

## 2. 외부 4기능 대조 판정표 (전수)

범례: ✅수용(기존 좌석 존재) · 🔀변형 수용(WhyMath 방향으로 바꿔 수용) · 🆕수용(신설 — 본 문서가 설계) ·
❌거부(§8에 근거 영구 기록) · ⏸보류(정직한 공백 — 조건 명시).

### 2.1 기능⑭ 교수전략 라이브러리 — 관리 항목 14종

| 외부 관리 항목 | 판정 | WhyMath 좌석 / 근거 |
|---|---|---|
| 교수전략 ID·이름·설명 | 🆕 | 카탈로그 YAML(§3) — enum 값 1:1·`name_ko`·`description` |
| 적용 대상 학년 | 🆕 | `target_grade_bands`(§3) — 생산자 `UserProfile.grade` 실재 확인 |
| 적용 개념 | 🔀 | 개념 *개별* 매핑 금지(노드 폭발) → **k_type(지식유형 7종) 단위**로 변형(`target_k_types`) |
| 적용 난이도 | 🆕 | `difficulty_range`(§3) |
| 적합한 오개념 | 🔀 | 오개념 *개별*(M-id) 매핑 금지(10×839 관계 폭발) → **`error_type` 6종 단위**로 변형(`suitable_error_types`) |
| 기대 효과 | 🔀 | 별도 필드 비신설 — `usage_notes` 서술에 흡수. *측정*은 04d §3.2/`adaptive/effectiveness.py` 소관(구현 2/4 지표 — 정직 부기) |
| 사용 조건 | 🔀 | 기계 판정은 `select()` 규칙표(04d §2)가 정본 — 카탈로그에는 **사람 서술만**(`usage_notes`·기계 배선 금지) |
| 금지 조건 | 🔀 | 기계 판정은 팩 `forbidden_modes`(폐쇄 어휘 7종)+`gate()` 2축이 정본 — 카탈로그 중복 금지(§3 제거 필드) |
| 선행/후속 전략 | ❌ | 페이딩 정본은 팩 `fading_schedule`(k_type 축) — 정본 이중화 금지(§8-③) |
| AI 추천 점수 | ❌ | 정적 점수는 bandit 무정보 사전 Beta(1,1)를 데이터 없이 오염 — PED-03 posterior가 유일 좌석(§8-①) |
| 연구 근거 | 🆕 | `research_basis`(§3) — 산문 산발(Sweller·NRICH·Schoenfeld·VanLehn)을 필드로 수렴 |

**대표 전략 10종 대조**: 직접 교수법=`DIRECT` ✅ · 소크라테스 문답=`SOCRATIC` ✅ · PBL=`PROBLEM_BASED` ✅ ·
유추(비유)=`ANALOGY` ✅ · 시각화=`VISUALIZATION` ✅(어댑터 미구현 — §10) · 반례 제시=🔀 전략이 아니라 **오개념
개입 패턴**(카탈로그 839+원자 전량이 `counterexample` 보유·`04c` reactive) · 오개념 교정=🔀 동일(개입 축이 더
정교) · Scaffolding=🔀 전략이 아니라 **답 미루기 4단계+팩 페이딩**(`04` 정본·graded Hint) · 발견학습=⏸(SOCRATIC·
PROBLEM_BASED와 경계 불명 — enum 폐쇄 거버넌스상 실수요 확인 전 미추가) · 구체물 활용=⏸(CRA의 C — 초등
확장(E축·`G-s5-subject-expansion` 뒤) 시점에 재검토. 04d §1의 "k_type별 CRA류 진행"은 설계용 축이라 별개).
WhyMath 고유 4종(RETRIEVAL·SPACING·INTERLEAVING·SELF_EXPLANATION — 인지과학 축)은 외부 틀에 없음 — 유지.

### 2.2 기능⑮ 설명 방식 선택

| 외부 항목 | 판정 | 근거 |
|---|---|---|
| 설명방식 10종 enum | ❌ | 독립 축이 아니라 기존 3축의 사영 — §5 분해표. 중첩 축=단일 진실 원천 붕괴+렌더 조합폭발 |
| 입력: 학생 수준·현재 개념·오개념·학습 이력·이전 설명 성공 여부 | ✅ | `StudentSignals`(mastery 3축·misconception_ids·시도/힌트 이력)+`pedagogy_evidence`(처치·결과, 2026-07-26) |
| 입력: 학년 | 🆕 | §4 — `grade` 신호 추가(생산자 실재) |
| 입력: 선호 학습 스타일 | ⏸ | 생산자 부재(`preferred_solution_style`은 유령 필드 — 04d §2.1 실측). **학생 명시 선택**(`requested_strategy` 힌트·§5)으로 대체 — 추정 선호 금지 |
| AI 선택 과정(학생모델→분석→후보→선택→생성) | ✅ | 04d §2 `select→gate→decide`+`supply()` — 기구현. 재설계 불요 |

### 2.3 기능⑯ 비유/예시 생성

| 외부 항목 | 판정 | 근거 |
|---|---|---|
| 실생활 예시 | 🆕 | `example_generator`(§6) — 목표-grain 슬롯 |
| 시각적 비유 | 🔀 | 비유 텍스트는 `metaphor` 축(§6)·시각화는 `VISUALIZATION`/L5 축 — 혼합 축 비신설 |
| 게임형 예시 | ❌ | 반게임화 정체성(CLAUDE.md 절대 금기·enum GAME 배제 선례) — 예시 축에서도 동일(§8-②) |
| 스토리텔링 | 🔀 | 독립 유형 비신설 — 실생활 예시의 서술 형식으로 흡수(별도 축이면 유형 폭발) |
| 학년별 예시 | 🔀 | 독립 생성기 비신설 — 정의 레지스터(S4-05 `concept_definition` Overlay·눈높이 4종)와 동일 축으로, 레지스터 파라미터로 흡수 |
| 생성 파이프라인 자체 | 🆕 | **진짜 공백** — §6. 단 "비유 0"이 아니라 자산 846행 실재·검수/생성 경로 부재가 정확한 진단 |

### 2.4 기능⑰ 질문 생성

| 외부 질문 유형 | 판정 | WhyMath 좌석 |
|---|---|---|
| 개념 확인("왜 그렇게 생각했나요?") | ✅ | 소크라테스 CLARIFICATION(명료화) — 6카테고리+선택 알고리즘 기구현 |
| 예측("결과는 어떻게 될까요?") | ⏸ | `04a §11.3` 도구#10 `elicit_prediction`+Brier 보정 — **설계 좌석 기점유·미구현**. 04e는 참조만(04a 소관 — 중복 등재 금지) |
| 반례("항상 성립할까요?") | ✅ | 오개념 개입 축 — 반례 자산 전량 보유·reactive 개입(`intervene.py` 결정트리) |
| 비교("두 방법의 차이는?") | ⏸ | PERSPECTIVE(관점) 카테고리+다중 풀이 `comparison` 부산물 — 연결 지점만 기록·실수요 대기 |
| 확장("조건을 바꾸면?") | ⏸ | IMPLICATION(함의)+LTHC `ExtensionPath` 스케치 — LTHC 심화와 묶어 별도 결정 |
| 메타인지("어떤 부분이 어려웠나요?") | ✅ | META 카테고리+`metacognitive_trigger` 기구현 |
| 오개념 교정("분모가 큰 분수가 항상 더 클까요?") | ✅ | ASSUMPTION 오버라이드(`select_category` — confidence≥0.65∧turns≤2·**낙인 없는 구조**: 카테고리만 반환·misconception_id 미노출) |
| 형성평가 문항 | 🆕 | **공백** — `diag_item` 슬롯 좌석만 존재·내용물 픽스처. §7 채움 파이프라인(atom_probe 재사용) |
| 생성 파이프라인(개념→수준→오개념→유형→생성) | ✅ | 유형 *선택*은 기구현(위 좌석들). 본문 생성은 LLM+톤 필터+루브릭 감사 — 재설계 불요 |

**외부 개발 우선순위(14→15→17→16)와의 차이**: WhyMath는 14·15의 골격(선택·게이트·측정)이 이미 done이므로
잔여 우선순위는 **⑭카탈로그(PED-05·06) ≈ ⑯생성(PED-09) > ⑰형성평가(PED-10)**이고, ⑮는 신설이 아니라 분해
흡수(§5)로 종결된다. 외부 틀의 피드백 루프(학생 반응 분석→추천 모델 업데이트)는 PED-03 Adaptive Engine과
동형 — 기설계·미승격(표본 게이트 대기)이므로 신규 작업 없음.

---

## 3. 전략 카탈로그 (기능⑭ 흡수 — PED-05·06)

### 3.1 자산 구조 — 팩 선례 미러

오개념(839+원자 전량×12필드)·문제 공략 전략(8종×5필드 데이터카드)에 비해 **교수전략만 enum+docstring**인
비대칭을 해소한다. 구조는 `pedagogy_pack` 선례(PED-01)를 그대로 미러한다:

```
data/corpus/pedagogy_strategies_v1/{direct,socratic,worked_example,problem_based,
  retrieval,spacing,interleaving,self_explanation,analogy,visualization}.yaml   ← 10건·enum 1:1
schema/pedagogy_strategy.py     ← Pydantic 계약(불변식 validator — 팩 계약 선례)
l4/pedagogy/strategy_registry.py ← lru_cache(maxsize=1)+reset seam·DB-free
```

- **enum ↔ YAML 1:1 거버넌스 테스트로 동결**(`test_render_governance.py` 선례) — 파일 누락·잉여 즉시 적발.
- 카탈로그는 **서술 자산**이다 — 로직은 코드(`runtime_selector`), 데이터는 YAML(하우스 스타일).

### 3.2 필드 — 소비처 지정표 (소비처 없는 필드는 착시·금지)

StudentSignals가 "항상 None인 필드는 착시"(04d §2.1)라며 3필드를 거부한 것과 동형으로, 카탈로그도 **소비처를
지정 못 하는 필드를 넣지 않는다**. 외부 14항목 중 수용분의 착지:

| 필드 | 형 | 소비처 (실재 좌석) |
|---|---|---|
| `strategy` | `PedagogyStrategy` 값(파일당 1) | registry 키·1:1 동결 테스트 |
| `name_ko` | str | 전략 카드(`prompt_assembler` 계층)·L5 표기 |
| `description` | str(1~2문장) | 전략 카드·문서화 |
| `research_basis` | list[str](인용 1줄씩) | 전략 카드(요약 1줄만 주입 — attention 절약)·문서화 |
| `target_grade_bands` | list[초등/중학/고등/대학] | `select()` 후보 필터(§4 — 생산자 `UserProfile.grade`) |
| `difficulty_range` | list[상/중/하] | `select()` 후보 필터(§4 — 문항 난이도 어휘 재사용) |
| `target_k_types` | list[KnowledgeType] | `select()` 후보 필터(§4 — `k_type_resolver` 산출 소비) |
| `suitable_error_types` | list[error_type 6종] | `select()` R2 정밀화(§4 — 오개념 가설의 error_type 대조) |
| `usage_notes` | str | **사람 서술 전용**(사용·금지 조건·기대 효과) — 기계 배선 금지 |

`suitable_error_types`의 어휘 = 오개념 코퍼스의 **`error_type` 6종**(개념혼동·절차오류·정의·표기오류·
과잉일반화·직관오류·역방향오류 — `misconception_catalog_v1.md`). ⚠️ 이전 논의의 "개입 패턴 어휘
(counterexample/concrete_example/visualization) 재사용"은 **유령 참조**였다 — 그런 폐쇄 상수는 코드에 없다.
실재 폐쇄 축인 error_type을 쓴다(유령 참조를 새로 만들지 않는다 — G7 재발 방지).

### 3.3 제거 필드 3종 — 정본 이중화 방지 (테스트로 부재 동결)

| 외부 항목 | 제거 근거 |
|---|---|
| AI 추천 점수 | bandit(`adaptive/policy.py`)의 무정보 사전 Beta(1,1)는 "특정 전략을 근거 없이 선호하지 않는다"를 코드로 강제한다 — 정적 점수는 이 사전을 데이터 없이 오염("측정 없는 도입 없음" 위반). 학습된 점수의 유일 좌석 = PED-03 posterior |
| 기계 판정용 사용/금지 조건 | 허용의 정본은 팩 `forbidden_modes`(폐쇄 어휘 7종)+`gate()` 2축. 카탈로그에 기계 조건을 또 두면 truth source 2개 — 7대 붕괴 연쇄의 "유지보수 지옥" 진입점 |
| 선행/후속 전략(페이딩) | 페이딩 정본은 팩 `fading_schedule`(k_type 축·예: PROCEDURE `{worked:2, completion:2, solo:3}`). 전략 간 선후를 카탈로그에 넣으면 페이딩이 2곳에 산다. 전략 간 관계가 실수요로 필요해지면 관계 타입 1종(`fades_to`)만 별도 결정으로 |

**불변식**: 카탈로그 스키마에 위 3필드가 *존재하지 않음*을 스키마 동결 테스트가 검사한다(부재의 동결 —
`test_pedagogy_dsl_schema_freeze.py` 선례). 미래 세션이 외부 틀을 다시 보고 재제안하는 것을 §8과 이중 방어.

---

## 4. 선택 입력 확장 (G5 — PED-06)

카탈로그의 적합성 필드를 `select()`가 **후보 필터**로 소비한다. 규칙표 v1(R1~R5)은 유지하고, 필터는 그 앞에서
후보 집합만 좁힌다:

```
candidates = registered_strategies()                       # 렌더 가능 전략(기존 거버넌스)
candidates = narrow(candidates, grade, difficulty, k_type)  # 카탈로그 적합성 — 좁힘만
strategy   = rule_table(signals, candidates)                # R1~R5 (기존 우선순위 그대로)
```

- **신호 추가는 생산자 먼저**(04d §2.1 원칙): `StudentSignals.grade`의 생산자는 `UserProfile.grade`
  (`db/models/user.py` — 실재 실측 확인). 난이도는 호출부의 문항/목표 메타(상/중/하)에서. 둘 다 None이면
  해당 필터는 조용히 건너뛴다(필수화 금지).
- **불변식 ① 필터는 좁힘만 한다** — 좁힌 결과가 공집합이면 필터를 무시하고 규칙표 원판정으로 폴백한다
  (신호 부재·카탈로그 공백이 선택 불능을 만들면 안 됨). 폴백은 `reason_code`로 기록(조용한 실패 아님).
- **불변식 ② 카탈로그는 select 전용 — `gate()` 입력 금지**. 게이트가 YAML 데이터를 읽기 시작하면 코퍼스
  편집만으로 "효과 ≤ 허용"이 우회된다 — 부재를 테스트로 동결한다(PED-06 acceptance).
- **불변식 ③ `select()` 출력 ⊆ `registered_strategies()`** — 기존 거버넌스 유지.
- R2 정밀화(v2): 오개념 가설이 있으면 일괄 `ANALOGY`가 아니라, 가설의 `error_type`을 카탈로그
  `suitable_error_types`와 대조해 후보를 고른다(예: 절차오류→`RETRIEVAL`, 개념혼동→`ANALOGY`).
  대조 불가(원자 오개념의 error_type None 등)면 기존 R2 그대로 — 좁힘만 원칙의 적용.

---

## 5. 설명방식 축 판정 — enum 비신설 (기능⑮ 종결)

### 5.1 결정

**`ExplanationMode` 류의 독립 폐쇄 enum을 신설하지 않는다.** 외부 10종을 실측 분해하면 독립 축이 아니라 기존
3축의 사영이며, 부분 중첩 축은 모든 소비처에서 "어느 축이 이기는가" 분쟁을 만든다(단일 진실 원천 붕괴).
어댑터 5종 × 방식 8종 = 40 렌더 경로 — 03c가 "저장은 곱이 아니라 합"으로 막은 조합폭발이 렌더 계층에서
부활한다. 또한 처치 기록 축이 전략 단위(`pedagogy_evidence.META_KEY_STRATEGY`)라 신설 축은 효과 측정
생산자가 없다("생산자 먼저" 위반) — 자동선택 승격 루프를 새로 달면 PED-03의 재발명이 된다.

### 5.2 10종 → 3축 분해표 (정본)

| 외부 설명방식 | 귀속 축 | WhyMath 좌석 |
|---|---|---|
| 정의 중심 | 전략 | `DIRECT`(definition 세그먼트) |
| 직관 중심 | 전략 | `ANALOGY`(`metaphor`→`ConceptDSL.intuition`) |
| 시각화 중심 | 전략 | `VISUALIZATION`(어댑터 미구현 — §10 공백) |
| 애니메이션 중심 | L5 시각화 | `05b` VisualizationType — 설명 "방식"이 아니라 렌더 매체 |
| 공식 유도 중심 | 슬롯/자산 | `SlotSpec.type` 신규 유형(예: `derivation`) — 자유 문자열이라 **enum 신설 0으로 확장** |
| 실생활 사례 중심 | 슬롯/자산(+ANALOGY 소재) | example 슬롯(§6 생성기 표적) |
| 역사적 배경 중심 | 슬롯/자산 | ⏸ 자산 0 — 정직한 공백(코퍼스 실수요 확인 전 보류) |
| 탐구 중심 | 전략 | `SOCRATIC`·`PROBLEM_BASED` |
| 단계별 설명 | 전략 | `WORKED_EXAMPLE`(+팩 페이딩) |
| 한 줄 핵심 | 슬롯/자산 | 요약 슬롯(flashcards 113건 인접 자산) |

### 5.3 학생 옵트인 — 추정 선호 대신 명시 요청

"선호 학습 스타일" 입력은 생산자가 없고(§2.2), 신호 없는 자동선택은 근거 없는 추측이다
(`part7_math_ui_dsl_review.md` 보류 결정). 대신 **학생 명시 선택**을 새 축 없이 흡수한다:

- `supply(requested_strategy: PedagogyStrategy | None)` 힌트 파라미터 — 학생이 "비유로 설명해줘"를 고르면
  L5가 이 힌트를 실어 보낸다. 힌트는 `select()`의 규칙표 판정을 **대체**하되, **`gate()`는 반드시 통과**한다
  — 학생 요청도 "효과 ≤ 허용"을 우회할 수 없다(막힌 학생이 완전예제를 요청하면 기존 2축 게이트가 SOCRATIC
  강등·reason_code).
- part7의 보류는 **해제가 아니라 사유 갱신**이다: "modality 신호 부재 → 자동선택 금지"는 유지되고, 명시
  요청은 추정이 아니므로 금지 대상이 아니다. 훗날 L2에 학습양식 신호 생산자가 실재하게 되면 그때 자동선택을
  별도 결정으로 재검토한다(part7 Tutoring Adapter 로드맵과 무모순).

---

## 6. 비유·예시 생성 (기능⑯ — PED-09)

### 6.1 정확한 진단과 정본 좌석 선언

"비유가 없다"가 아니다 — **자산 846행 실재**(`concept_content.metaphor` K-12 437+대학 409)·`l3/render/dsl.py`가
`metaphor → ConceptDSL.intuition`으로 매핑해 **AnalogyAdapter가 이미 렌더 중**이다. 진짜 공백은:
(a) 전량 `ai_estimated`류 검수 전 — 품질 게이트 부재 (b) `intuition` None인 개념의 렌더 불가
(c) 목표-grain 예시 슬롯의 LLM 생성 경로 부재(`slot_generator`가 의도적 연기해 둔 상태 — 본 설계가 그 연기의
해제 조건인 *소비처*를 명시한다) (d) 학년 레지스터 변형 부재.

**정본 좌석 선언(이 선언이 없으면 생성기는 죽은 콘텐츠를 만든다)**:

| grain | 정본 좌석 | 렌더 소비 경로 |
|---|---|---|
| 개념 비유(은유) | `concept_content.metaphor` — 생성기의 1차 표적은 **공백·저품질 채움** | `metaphor→intuition→AnalogyAdapter`(기존 경로·기소비) |
| 목표별 예시·보조 재료 | `pedagogy_content_slot`(DRAFT→prescreen→review 상태기계 재사용) | 발주서(`required_slots`) 잔여 슬롯 |

⚠️ 생성 산출을 슬롯에만 넣으면 AnalogyAdapter가 영원히 읽지 않는다(배선 없는 생성). 개념 비유는 반드시
`concept_content.metaphor`로 착지한다.

### 6.2 파이프라인 (L4=결정·L3=생성 준수)

```
L4 supply()/발주서 ──"이 개념·이 슬롯이 필요"──▶ l3/pedagogy/analogy_generator.py
                                                l3/pedagogy/example_generator.py
                                                  │  (라우터 경유·LLM — 직접 호출 금지)
                                                  ▼
                                          DRAFT → prescreen → review (기존 상태기계)
                                                  ▼
                                  metaphor 채움 / 슬롯 채움 (§6.1 좌석별)
```

### 6.3 검증 게이트 (콘텐츠 생성 경로 신설 의무)

- **`analogy_fidelity_eval` 결함주입 강등전 신설**(CLI exit 0/1·`pedagogy_pack_fidelity_eval` 선례). 핵심 결함
  축: ①**오개념 유발 비유**(예: "함수=자판기" 비유가 일대일대응 오개념을 심는 경우 — 비유 고유의 위험)
  ②정의 대체 비유(비유가 정의를 참칭) ③정답 유출 ④게임형 산출. 주입 결함의 검출률로 변별력을 측정한다.
- 기존 `coach_prose_leak_eval`(정답 유출)·톤 필터는 그대로 적용된다(발화 경로 공통 방어).
- 렌더측 상보: AnalogyAdapter가 이미 강제하는 **"비유는 정의를 대신하지 않는다" reflection 세그먼트**가
  생성측 게이트와 이중 방어를 이룬다(어느 한쪽 회귀에도 안전).

### 6.4 상한 불변식 (교육적 압축 — 콘텐츠 폭발 방지)

- 개념당 비유 1(+정의 레지스터 변형 소수 — S4-05 `concept_definition` Overlay와 동일 축·**패턴 참조지 의존
  아님**). 개념 846 × 레지스터 × 오개념의 사전 대량 생성 금지 — 공백·검수 탈락분만 발주(select-vs-generate).
- **오개념 교정 비유를 신설하지 않는다** — 그 역할은 반례 자산(`counterexample`)이 기담당하고 오개념은
  reactive-only다(preload 금지·`04c`).
- 게임형 산출 0 검사(§8-②)·스토리텔링은 실생활 예시의 서술 형식(독립 유형 아님)·학년별 변형은 레지스터
  파라미터(독립 생성기 아님).

---

## 7. 질문 유형 완결 (기능⑰ — PED-10 외)

### 7.1 외부 7유형 ↔ WhyMath 좌석 매핑 (정본)

§2.4 표가 정본이다 — 요지: **7유형 중 5유형은 기존 좌석 완비**(개념확인·반례·메타인지·오개념교정 + 유형
선택 알고리즘), 예측은 `04a §11.3` 도구#10이 설계 좌석을 기점유(참조만·중복 등재 금지), 비교·확장은 연결
지점 기록 후 실수요 대기. **별도 "질문 7유형" 축을 신설하지 않는다** — 소크라테스 6카테고리+오개념 개입
축이 상위 호환한다(§8-⑧).

### 7.2 형성평가 슬롯 채움 (PED-10 — 착지 완료·§10 부기 참조)

- 좌석: `pedagogy_content_slot.slot_type='diag_item'`(자유 문자열 — 테이블·스키마 신설 0).
- 원천: **atom_probe 전량(1,823 — 2026-07-28 dedup 14쌍 통합 후)** — 원자별 진단문항(발문·통과기준·오답신호)
  기보유. **생성이 아니라 투영**이다(문항을 새로 만들지 않는다 — 검증된 자산 재사용).
- **grain 다리 — 실측 정정(PED-10 구현 중 발견, crosswalk 불필요)**: 아래 초안은 "개념↔원자
  crosswalk 경유"를 그렸으나, 실측하면 그 다리가 이미 다른 곳에서 닫혀 있다. `learning_objective.
  concept_nodes`는 H2 계약(`db/models/pedagogy_dsl.py`)상 **원자 백본(atom_node) code 배열 그
  자체**이며(legacy 437/545 개념 그래프가 아니다), `l1/pedagogy/unit_compiler.py`가 컴파일 시점에
  `obj.concept_nodes`를 `valid_atom_codes`(원자 백본 전량)에 대조 검증한다 — 저작 단계에서 이미
  원자 code로 쓰인다. `atom_probe.code`도 같은 원자 세부개념 code 공간(K-12·대학 겹침 0)이므로,
  목표→원자의 다리는 **`concept_nodes`와 `atom_probe.code`의 직접 교집합**이다(정본 구현:
  `l3/pedagogy/diag_item_projector.py` 모듈 docstring). `data/corpus/concept_atom_crosswalk_v1`
  (구 437-개념-id ↔ 원자 code)는 다른 소비처(콘텐츠 이관 등) 용이지 이 bridging에는 쓰이지 않는다 —
  존재하지 않는 다리를 새로 놓지 않는다(§3.2의 "유령 참조 재사용 금지" G7과 동일 원칙).
- select-vs-generate: 이미 검수 결정이 난 슬롯(PRESCREENED/APPROVED/REJECTED)은 손대지 않고 그
  자리의 원자 후보도 소비하지 않는다 — 워킹 스켈레톤 픽스처가 있던 자리는 DRAFT일 때만 실제
  atom_probe 콘텐츠로 교체된다.
- 보고: 채움 건수·prescreen 통과율. 표본 0은 None(0% 위장 금지 — 정직한 공백 하우스 스타일).

---

## 8. 비수용 목록 — 외부 틀에서 받아들이지 않는 것 (재제안 방지 영구 기록)

| # | 외부 항목 | 거부 근거 |
|---|---|---|
| ① | AI 추천점수 정적 필드 | bandit 무정보 사전 오염·"측정 없는 도입 없음" 위반(§3.3) |
| ② | 게임형(전략·비유·예시 전 축) | 반게임화 정체성 — CLAUDE.md 절대 금기·enum GAME 배제 선례 |
| ③ | 전략×오개념 개별 매핑 | 10×839=8,390 엣지 — 관계 폭발. error_type 6종 단위로만(§3.2) |
| ④ | 설명방식 독립 enum 10종 | 중첩 축·렌더 조합폭발(5×8=40)·처치 생산자 부재(§5) |
| ⑤ | 애니메이션=설명방식 | L5 시각화 축(`05b`) 소관 — 계층 침범 |
| ⑥ | 역사적 배경 방식/유형 | 자산 0 — 정직한 공백(자산 실수요 확인 전 보류) |
| ⑦ | 관리 항목 14종 전량 미러링 | 소비처 없는 필드는 착시(§3.2 소비처 지정표가 정본) |
| ⑧ | 질문 7유형 별도 축 신설 | 6카테고리+오개념 개입 축이 상위 호환(§7.1) |
| ⑨ | 전략 프롬프트에 오개념 목록 사전 주입 | preload 금지·reactive retrieval만(`04c`·구축 플레이북) |

---

## 9. 배선·정정 (G6·G7)

| 항목 | 처리 | 태스크 |
|---|---|---|
| `mode_guard` 런타임 미배선 — `check_forbidden_modes` 프로덕션 호출 0(하네스·테스트만) | coach 응답 경로에 fail-closed 배선(`filter_tone` 앞·위반 시 폴백+reason_code). 플래그 옵트인·OFF 무변경. "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" 반복 사고 유형의 해소 | PED-07 |
| coach·study 경로 분기 — 설계용(팩) 축은 2026-07-27 GA 기배선, **실행용 축**(StudentSignals→decide→처치 기록)은 `/study`만 | ① study의 신호 조립을 공용 좌석으로 추출(101KB coach 직수정 회피 — 최고 위험이라 추출 슬라이스 선행) ② coach 턴에서 `decide()` 소비+`record_pedagogy_treatment` | PED-08 |
| adaptive policy 미승격(표본 미달 exit 1) | **신규 작업 없음** — 승격 게이트(`pedagogy_policy_eval`)가 정직하게 미달을 표기 중. 규칙표 v1이 정본(04d §3.3). 표본은 PED-08 착지로 자연 축적 | — |
| `preferred_solution_style` 유령 필드(`02_learner_model.md`·`03_content_generation.md`가 여전히 서술) | 04d §2.1 패턴("항상 None인 필드는 착시")의 실측 부기를 02·03에 확산 | PED-11 |
| 정본 이중화 — `.claude/agents/pedagogy-designer.md`(413줄)가 `04` 정본(195줄)보다 상세 | 관계 1줄 명시(에이전트 문서는 작업 지침·설계 정본은 `04` 계열). 내용 이관은 별도 결정 | PED-11 |

---

## 10. 현 구현 매핑 (편집자 부기 — 2026-07-28)

| 설계 요소 | 현 좌석 | 상태 |
|---|---|---|
| 전략 enum 10종 | `schema/enums.py::PedagogyStrategy` | ✅ 동결(거버넌스 테스트) |
| 선택·게이트 | `l4/pedagogy/runtime_selector.py` | ✅ R1~R5+2축 게이트(PED-02 done) |
| 공급 오케스트레이션 | `l4/content_supply.py::supply()` | ✅ decide 내부 호출 — 게이트 우회 불가 |
| 렌더 어댑터 | `l3/render/adapters.py` 5종 | ⚠️ 10종 중 5종(RETRIEVAL·SPACING·INTERLEAVING·SELF_EXPLANATION·VISUALIZATION 미구현 — `LookupError` 정직 실패). 어댑터 추가는 REND-01 후속 실수요 시 |
| 전략 카탈로그 | `schema/pedagogy_strategy.py`·`pedagogy_strategies_v1/` 10건·`strategy_registry.py` | ✅ 착지(PED-05 — 제거 필드 3계열 부재 이중 동결·enum 1:1 거버넌스) |
| 후보 필터·전략 카드 | `runtime_selector.narrow_candidates`·`prompt_assembler.attach_strategy_card`·`supply()` 생성 폴백 | ✅ 착지(PED-06 — 플래그 2종 기본 OFF 캔어리·공집합 3중 폴백 reason_code·gate 카탈로그 부재 동결. grade_band 생산자 배선·난이도는 kwargs 축만(생산자 부재)·R2 정밀화는 error_type 순수 경로 생산자 부재로 보류) |
| 비유 자산 | `concept_content.metaphor` 846행 | ⚠️ 전량 검수 전 — PED-09가 채움·검수 파이프라인(§6) |
| 비유·예시 생성기 | — | 🆕 PED-09(`l3/pedagogy/` — slot_generator 형제) |
| 형성평가 | `l3/pedagogy/diag_item_projector.py`(계획·행 빌드·오케스트레이션) | ✅ 착지(PED-10 — atom_probe↔concept_nodes 직접 code 교집합·crosswalk 불필요(§7.2 실측 정정)·select-vs-generate·표본 0=None) |
| mode_guard | `l4/pedagogy/mode_guard.py`(검출 1종/7모드) | ✅ 런타임 배선(PED-07 — WH-1 primary 톤필터 직전·`mode_guard_runtime_enabled` 옵트인 기본 OFF 캔어리·위반 시 소크라테스 재질문 폴백. GA flip은 측정+사인오프 후 별도) |
| 처치·효과 측정 | `l2/pedagogy_evidence.py`·`adaptive/effectiveness.py`(지표 2/4 구현) | ✅ 좌석 가동·표본 축적 중(04d §3) |
| 예측 질문 | `04a §11.3` 도구#10 | ⏸ 설계만 — WH-1 하네스 소관(04e 범위 밖) |

---

## 11. 실행 정본 참조

- 실행 정본: `backlog/` — **PED-04**(본 문서·이 세션)·**PED-05/06**(카탈로그·소비)·**PED-07**(mode_guard 배선)·
  **PED-08**(coach 실행용 축 수렴)·**PED-09**(비유·예시 생성기)·**PED-10**(형성평가 슬롯 채움)·**PED-11**(문서
  부채 정정).
- 교차링크: `04d`(선택·학습 메커니즘 — 상위 정본)·`03c`(전략 enum·렌더·select-vs-generate)·`04a §11`(전략
  레퍼토리·예측 도구)·`04c`(오개념 reactive)·`docs/data/strategy_graph_v1.md` §4(축 구분)·
  `docs/standards/superhuman_verification_standard.md`(결함주입 강등전 규격).
- 결정 로그: `MEMORY.md` 2026-07-28(설계·문서·PED-04) — ExplanationMode 비신설·카탈로그 제거 필드 3종·용어
  3축 구분이 핵심 결정 3건.

---

**버전**: 1.0 | **작성**: 2026-07-28 | **다음 검토**: PED-05 착수 시점
