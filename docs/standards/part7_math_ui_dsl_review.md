# Part 7. Math UI DSL — 준수 검토 판정 (2026-07-03)

> `docs/standards/playbook_part_review_questions.md`의 **Part 7. Math UI DSL** 체크리스트 3항목을
> 현재 코드베이스에 대해 검토한 판정 리포트. 정본 설계 문서: `docs/architecture/05a_learning_scene_dsl.md`
> (LearningScene DSL)·상위 `05_interaction.md`(§5.2 선언적 시각화). 결정 로그는 `MEMORY.md`.

법칙: *"디자인 DSL"이 아니라 "인지 인터페이스 생성 언어". 9블록. UI Planner 파이프라인.*

---

## 판정 요약

| 항목 | 판정 | 조치 |
|---|---|---|
| ① 인지 인터페이스 생성 언어인가 | **✅** | `generate_learning_scene`=결정론 골격(UI Planner)·인지 인터페이스를 스키마 불변식으로 강제 |
| ② 9블록 개념·오개념·행동영역 자동 분기 | **△→✅(크로스워크 명문화)** | 자동 분기 구현됨. 택소노미는 6 element kind(9블록 아님)—Skill/Assessment/AIExplanation 의도적 외부화를 크로스워크로 명문화 + 표류 감지 테스트 |
| ③ Core로 UI/런타임 상태 역류 없음 | **✅(거버넌스 동결 신설)** | 단방향 파이프라인·읽기전용 스냅샷·역의존 회피 배치. Part 7 전용 계층-방향/순수성 동결 테스트 추가 |

구현 상태: Math UI DSL은 이미 `LearningScene` DSL로 **구현 완료**(S0~S5h·`l4/learning_scene.py`
cov 100%). 본 검토는 신규 기능이 아니라 *판정 + 발견된 갭(크로스워크·거버넌스 동결) 상환*이다.

---

## 항목 ① — "DSL이 개념 → 자동 화면 인지 인터페이스 생성 언어로 설계됐나?"

**판정 ✅.**

- **UI Planner = 결정론 골격**: `l4/scene_generation.py::generate_learning_scene`이 개념 노드(L1
  `Concept`)의 구조 메타(`recommended_visual_styles`·`cognitive_type`)에서 *어떤 요소 kind를 둘지*를
  **코드가 결정**한다. LLM은 `visualization` 요소의 `spec`만 채운다(`l3.generate_visualization_spec`
  다운콜·라우터·Langfuse·캐시). "화면을 만들지 말고 수학 구조를 만들어라"의 직접 구현 — 개념 →
  자동 장면 명세(`LearningScene` JSON/AST)다.
- **"디자인 DSL"이 아니라 "인지 인터페이스"**임을 스키마가 강제한다: 소크라테스 발화(`hint_level=1`
  유도 질문·정본 `EXAMPLE_QUESTION`)·답 미루기 상한(`answer_deferral_max_level`)·`misconception_probe`
  (정답·수정 필드 부재·사고 유도만). 외부 문서의 범용 `warning_overlay`(붉은 강조·정답 자동 생성)·
  `steps:true`(즉답)를 *교정해* 수용(`05a` §2·§10) — 의사결정 우선순위 1(학생 안전)·3(교수학 정확성)을
  표현 계층에 못박는다.
- 정리: 파이프라인 `개념(L1) → generate_learning_scene(UI Planner·L4) → LearningScene(DSL) →
  SceneRenderer(L5)`가 플레이북의 "인지 인터페이스 생성 언어"에 정합한다.

## 항목 ② — "9블록이 개념·오개념·행동영역에 따라 자동 분기하나?"

**판정 △ → ✅ (자동 분기는 구현, 택소노미 크로스워크를 명문화).**

**자동 분기는 구현되어 있다**(코드 결정론):
- `_COGNITIVE_SOCRATIC_MAP`: `cognitive_type`(DEFINITION/THEOREM/TECHNIQUE/PATTERN/VISUAL_REASONING)
  → (소크라테스 카테고리 × Polya 단계) 분기.
- `recommended_visual_styles` 유무 → `visualization`(+graph_2d면 `param_control`) 분기.
- `learner_context.active_hypothesis_ids ∩ CATALOG_BY_ID` → `misconception_probe` 분기(오개념·근거
  있는 가설), 신뢰도로 개입 패턴(반례/거꾸로/보류) 재분기(`select_intervention`).
- `_decide_layout` → 배치(single/two_panel/vertical_stack) 분기.

**택소노미 갭**: 플레이북은 9블록을 명명하나, 구현은 **6 element kind**다. 이는 `05a` §2·§10의
*의도적 설계*(anti-explosion·Concept Purity — 신규 엔진 0·기존 좌석 참조). 9블록 → 현 구현 크로스워크:

| 플레이북 9블록 | 현 구현 좌석 | 형태 |
|---|---|---|
| **Scene** | `LearningScene`(`l4/learning_scene.py`) | 최상위 합성 명세 |
| **Concept** | L1 `schema/concept.py`(`concept_id`로 *참조*) | 코어 개념(UI 블록 아님·참조가 정상) |
| **Visualization** | `VisualizationElement`(kind=`visualization`) | element kind |
| **Interaction** | `ParamControlElement`·`AnnotationElement` | element kind(조작·강조) |
| **Skill** | `CognitiveType` enum 속성 + L2 숙달(`bkt`/`irt`) | 속성·모델(전용 블록 아님·Part 2 판정 동형) |
| **Misconception** | `MisconceptionProbeElement`(kind=`misconception_probe`) | element kind |
| **Tutoring** | `SocraticPromptElement` + `StepPanelElement` | element kind(발화·단계) |
| **Assessment** | `schema/assessment.py`·`api/gating.py`·L2 | 별도 좌석(장면 요소 아님·외부화) |
| **AIExplanation** | 같은 `LearningScene`을 AI가 렌더하는 *타깃*(`05a` §1) | 렌더 채널(전용 블록 아님) |

- Skill/Assessment/AIExplanation을 *전용 scene 블록으로 승격하지 않는 것*이 판정의 핵심이다:
  승격은 노드/관계 폭발(플레이북 7대 붕괴 연쇄 #1·#2)이며, 각 관심사는 이미 순수 좌석(속성·별도
  스키마·렌더 타깃)에 산다. 갭의 실체는 *커버리지 누락*이 아니라 **9블록에 대한 명시적 크로스워크
  부재**였고, 본 표로 상환한다.
- 회귀 방지: `test_scene_dsl_layer_governance.py::test_scene_kind_taxonomy_matches_crosswalk`가
  6 kind 집합을 동결 — 블록 추가/삭제 시 red → 본 크로스워크 동반 갱신을 강제한다.

> 재검토 트리거: 실제 사용에서 Assessment/Skill/AIExplanation을 *장면 요소로* 합성해야 하는
> 요구(예: 장면 내 즉석 평가 위젯)가 확인되면, 신규 element kind는 별도 기능 슬라이스(`05a` S5+
> 로드맵)로 설계-비판-반례를 거쳐 승격한다. 이 검토 범위에서는 추가하지 않는다(정직한 경계).

## 항목 ③ — "파이프라인에서 Core로 UI/런타임 상태가 역류하지 않나?"

**판정 ✅ (거버넌스 동결 신설로 회귀까지 차단).**

- **단방향 흐름**: `api/scene.py`가 L1 Concept(read)+L2 진단(read)+L4 오개념/가설(read)을 *조합*해
  `generate_learning_scene`(L4)에 넘기고 → `LearningScene`(JSON/AST) → L5 `SceneRenderer`(수학 로직
  0·dumb). 코어로 쓰기 없음. `SceneLearnerContext`는 **읽기전용 스냅샷**("판정 아님"·생성 입력일 뿐).
- **역의존 회피가 배치로 강제**: `schema.*`는 L레이어 import 0 → `LearningScene`을 schema가 아니라
  **L4**에 배치. 생성기도 L3 아닌 **L4**에 두고 L3를 다운콜(L4→L3)한다(`scene_generation.py` ★배치
  정정 주석). L3(`l3.visualization`)는 L4를 import하지 않음(확인됨).
- **런타임/interaction state 누출 0**: `LearningScene`·6 element kind에 세션·클릭·현재값 등 런타임
  상태 필드 부재. `layout`은 "선언적 배치 힌트(픽셀 아님)". 기존 방어: `TestConceptPurity`가 Concept
  노드에서 renderer·layout·`figure_spec` 슬롯 *부재* 단언, `math_dsl_risk_register.md`가 "interaction
  state 누출 0" 감사.
- **신규 동결**(`tests/backend/l4/test_scene_dsl_layer_governance.py`): (a) L3 scene 좌석 L4 import 0,
  (b) schema scene 좌석 L레이어 import 0, (c) SceneElement 6종 필드 화이트리스트 + 정답/판정/런타임
  토큰 부재, (d) 9블록→6 kind 크로스워크 표류 감지. 검토 판정을 코드가 스스로 지킨다.

---

## 조치 산출물

- 본 판정 리포트(`docs/standards/part7_math_ui_dsl_review.md`).
- 거버넌스 동결 테스트(`tests/backend/l4/test_scene_dsl_layer_governance.py`).
- `MEMORY.md` 결정 로그 1건(항목 ② △→✅ 근거·항목 ③ 동결 신설).
- 코드 로직 변경 0 — 검토는 판정·문서·동결이며 DSL 동작을 바꾸지 않는다.

## 메타 질문 (플레이북 Part 7 마감)

- *이 DSL이 실제 서비스에서 실패하는 이유는?* — 가장 큰 실패 축은 (i) LLM이 정답을 spec에 흘리는
  낙인/즉답 우회(→ §4 스키마 필드 부재 + `parse_learning_scene` 게이트로 차단), (ii) element kind
  폭발로 인한 택소노미 붕괴(→ 6 kind 동결·신규는 슬라이스 승급). 두 축 모두 스키마 불변식 + 거버넌스
  테스트로 *구조적으로* 막혀 있음을 이 검토가 확인했다.
