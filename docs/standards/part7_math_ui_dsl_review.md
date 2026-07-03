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
| ② 9블록 개념·오개념·행동영역 자동 분기 | **△ (재검토 정정 — 2/3 축)** | 개념·오개념 축은 분기하나 **행동영역(Skill)·학생모델 축은 미분기**·인터랙션 slider 단일·평가 장면 미합성. 상세 §재검토 |
| ③ Core로 UI/런타임 상태 역류 없음 | **✅(거버넌스 동결 신설)** | 단방향 파이프라인·읽기전용 스냅샷·역의존 회피 배치. Part 7 전용 계층-방향/순수성 동결 테스트 추가 |

구현 상태: Math UI DSL은 이미 `LearningScene` DSL로 **구현 완료**(S0~S5h·`l4/learning_scene.py`
cov 100%). 본 검토는 신규 기능이 아니라 *판정 + 발견된 갭 상환*이다.

> **⚠️ 재검토 정정(2026-07-03)**: 초판은 항목 ②를 "△→✅(크로스워크 명문화)"로 판정했으나, Kiki가
> 제시한 *구체 9블록 행동 명세*(블록별 자동 분기 동작·명명된 엔진·학생모델 기반 설명)로 재대조한
> 결과 **△로 하향 정정**한다. 초판은 9블록을 "기존 좌석으로 외부화됨"이라 처리해 지나치게 관대했다 —
> 외부화는 그 능력이 *장면 자동 분기에 배선되어 있음*을 뜻하지 않는다. 근거·정정 상세는 하단
> **## 재검토** 절 참조(항목 ①③ 판정은 유지).

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

## 재검토 (2026-07-03): 구체 9블록 행동 명세 대조 — 항목 ② △로 정정

Kiki가 제시한 재검토 관점은 9블록을 *이름*만이 아니라 **블록별 자동 분기 동작·명명된 엔진·개념→화면
매핑**까지 구체화한다. 핵심 명제: "어떤 개념인지·어떤 오개념이 있는지·**어떤 행동영역을 요구하는지**에
따라 UI가 자동으로 달라져야 한다." 체크리스트 ②의 **3개 분기 축**(개념·오개념·**행동영역**)을 현
코드에 정직하게 대조하면:

**분기 축 판정**

| 분기 축 | 현 구현 | 판정 |
|---|---|---|
| 개념(무엇을 배우나) | `cognitive_type`→소크라테스(`_COGNITIVE_SOCRATIC_MAP`)·`recommended_visual_styles`→시각화 | ✅ 분기함 |
| 오개념(무엇을 틀리나) | `active_hypothesis_ids ∩ CATALOG`→프로브(reactive·신뢰도로 개입 다양화) | ✅ 분기함(reactive) |
| **행동영역(어떤 행동을 요구하나)** | 없음 — Skill=`CognitiveType` 속성이 *소크라테스 매핑에만* 소비되고, 골격의 **독립 분기 입력이 아님** | ❌ **미분기** |

→ 3축 중 2축만 분기한다. 체크리스트 ②가 명시한 "행동영역" 축이 planner 입력이 아니므로 판정은
**△(부분)**이 정확하다. 초판의 "△→✅"는 9블록을 "외부화됨"으로 처리해 과대평가했다 — 능력이 다른
계층에 *존재*하는 것과 *장면 자동 분기에 배선*된 것은 다르다.

**관점 9블록 → 현 구현 능력 갭(실측)**

| 관점 블록 / 엔진 | 요구 동작 | 현 구현 | 판정 |
|---|---|---|---|
| VisualizationBlock · Visualization Selector | VizNode→자동 시각화(그래프·애니·트리·논리흐름) | `recommended_visual_styles`(16종)+4 `VisualizationType`(graph_2d·surface_3d·sim·anim) 자동선택 | 🟡 부분(경우의수 **트리**·증명 **논리흐름** 타입 부재) |
| InteractionBlock · Interaction Generator | slider·drag·tree expansion·단계선택 | `param_control`(slider)만 | 🔴 slider 단일(표의 5종 중 4종 미구현) |
| SkillBlock | 행동영역 UI(조건 강조·경우분할 트리) | 없음 | 🔴 미구현 |
| MisconceptionBlock | 오개념 "일부러 드러냄"(접근 vs 도달 대비) | reactive-only 사고 유도(preload·낙인 금지) | 🟡 설계 긴장(아래 해소) |
| TutoringBlock | AI 설명·힌트·소크라테스 | `socratic_prompt`(개념 `cognitive_type` 분기) | 🟢 개념적응(단 *학생*적응 아님) |
| AssessmentBlock | 장면 내 문제생성·행동영역 측정·오개념 진단 | 장면 미합성(`schema/assessment`·L2·gating 분산) | 🔴 장면 미합성 |
| AIExplanationBlock · Tutoring Adapter | 학생모델→설명 스타일(시각형→그래프·절차형→단계·직관형→비유) 자동선택 | 없음. **L2에 학습양식(modality) 신호 자체가 부재** | 🔴 미구현(상류 신호부터 없음) |

**항목 ① 재확인**: ✅ 유지하되 경계 명시 — "인지 인터페이스"의 *개념* 적응(cognitive_type)은 되나
*학생모델* 적응(Tutoring Adapter)은 아직 없다. 즉 현 DSL은 "개념→화면"은 자동이나 "학생→설명 스타일"은
미자동이다. 항목 ①의 "인지"는 절반(개념측)만 능동.

**항목 ③ 재확인**: ✅ 불변 — 재검토가 오히려 강화한다. `SceneLearnerContext`에 학습양식 축을 *추가하더라도*
읽기전용 스냅샷·단방향 원칙은 유지되어야 하며(역류 금지), Tutoring Adapter는 코어로 상태를 되쓰지 않는다.

**MisconceptionBlock 긴장 해소(안전 경계)**: 관점의 "오개념을 일부러 드러냄(접근 vs 도달 대비)"은
*개념 수준의 구조적 대비 교보재*(예: 기울기를 '두 점 변화율'로 *접근* vs 'y값 자체'로 *도달*하는 오개념
대비)로 표현하면 낙인이 아니며 CLAUDE.md와 양립한다. 그러나 *특정 학생*의 오개념을 근거 없이 preload해
"너는 이 오개념이 있다"고 드러내는 것은 여전히 금지(reactive·`active_hypothesis` 근거 필요·의사결정
우선순위 1 학생 안전). 즉 **"일부러 드러냄" = 개념 대비 교보재는 OK, 학생 낙인은 NOT** — 이 경계 안에서만
MisconceptionBlock을 확장한다.

**로드맵(설계 방향만·이번 구현 0·honest boundary)**

- **행동영역 분기 축 승격**: `CognitiveType`/Skill을 planner 골격의 *독립 분기 입력*으로 올린다(현재는
  소크라테스 매핑 부수효과). 조건 강조·경우분할 트리는 신규 element kind로 별도 슬라이스.
- **Tutoring Adapter**: *선행 조건 = L2 학습양식 신호 신설*(현재 부재). 신호 없이 explanationMode를
  자동선택하면 근거 없는 추측 → 금지(AI 신뢰 금기). 신호 확보 후에야 설명 element에 modality 축 추가.
- **Interaction/Viz 다양성(tree·drag·단계선택·트리/논리흐름 VizType)**: 기하·증명은 표기·작도 성숙도
  (WH-S Tier3/Lean)에 종속 — `05a` RS4 "초기 scope 제외"와 정합. 대수·함수 그래프부터 점증.
- **AssessmentBlock**: 장면 내 평가 합성은 답 미루기·"빠른 정답 KPI 금지" 불변식과의 충돌을 먼저 검토한
  뒤 슬라이스(평가가 사고 추적기를 문제은행으로 되돌리지 않도록).

**정정된 종합**: ① ✅(개념적응까지·학생적응은 미도달) · ② **△**(3축 중 행동영역·학생모델 축 미분기·
인터랙션 단일·평가 미합성) · ③ ✅(역류 없음·불변). 관점 문서는 아키텍처(표현≠의미·개념→자동화면)를
*재확인*하되, 현 구현이 그 비전의 **개념·오개념 2축 / slider 1인터랙션** 단계임을 드러낸다 — "전부 아니면
전무"가 아니라 회수 가능한 슬라이스로 나머지 축을 점증한다.

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
