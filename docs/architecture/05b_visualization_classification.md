# 시각화 가능성 분류 · 5상태 분리 · Renderer 독립 (Part 5 검토 정본)

> **목적**: 구축 플레이북 **Part 5. 시각화 시스템** 법칙 — *4분류(직접/동적/부분/추상) ·
> Renderer 독립 · 5상태 분리* — 에 대한 코드베이스 **검토 판정**을 기록하고, 그 결과 도입한
> **시각화 가능성 4분류**(`Visualizability`)와 **5상태 분리 거버넌스**의 설계 정본을 고정한다.
>
> **정본 상위 문서**: `05_interaction.md`(§시각화 스택·선언적 `Visualization`)·`05a_learning_scene_dsl.md`
> (합성 계층 `LearningScene`). 본 문서는 그 위에 *개념→시각화 판별 축*을 얹는다.
>
> 작성일: 2026-07-02 | 근거: `docs/standards/playbook_part_review_questions.md` Part 5 ·
> `docs/standards/build_checkpoint_questions.md` 단계 5.

---

## 0. 검토 판정 요약

| 체크포인트 | 판정 | 근거 |
|---|---|---|
| **CP1** 개념을 시각화 4분류로 판별하나, 전부 똑같이 그리려 하나? | ✅ **해소**(도입 전 ❌) | 인지 기준 4분류가 정의·구현 전무였다 → `Visualizability` enum + 생성 게이트 도입 |
| **CP2** VisualizationNode에 Desmos/Canvas/WebGL 구현체 이름이 없나? | ✅ **충족** | 개념 노드·`Visualization` 스키마엔 구현체명 0. 구현체명은 `render_contract.json` family·L5 어댑터에만 |
| **CP3** Math/Pedagogy/Interaction/Animation/UI 5상태 분리 + 단방향? | ✅ **강제됨**(도입 전 🟡) | 사실상 분리돼 있었으나 CI 강제 부재 → `test_visualization_state_separation.py` 거버넌스 추가 |

핵심: 재료(선언적 spec·dumb 렌더러·계층 경계)는 이미 성숙했고, 부족한 것은 ① **개념→"그릴지/어떻게"
판별 축**과 ② **5상태 분리를 CI로 동결하는 게이트**였다. 본 검토가 이 둘을 못박는다.

---

## 1. 시각화 가능성 4분류 (CP1) — `Visualizability`

**세 개의 "분류" 축이 공존하므로 혼동을 금한다.** 이들은 서로 다른 질문에 답한다:

| 축 | enum | 질문 | 위치 |
|---|---|---|---|
| **콘텐츠 태그** | `VisualType`(그래프/도형/표/좌표평면) | 문제에 어떤 그림이 *들어있나* | 문제 메타 |
| **교수학 양식** | `VisualizationStyle`(단위원·수형도 …16종) | 개념을 어떤 *표상 형식*으로 잘 드러내나 | `Concept.recommended_visual_styles` |
| **렌더 기술** | `VisualizationType`(interactive_graph_2d …4종) | 명세를 *어떤 도구*로 그리나(=Intent) | `Visualization.type` |
| **★가능성(신규)** | `Visualizability`(직접/동적/부분/추상) | 이 개념을 *어떤 시각화 전략으로* 그리나(인지 파악 방식) | **시각화 계층 Overlay** `concept_visualization`(code 키·노드 비내장) |

### 배치 — 노드 비내장 Overlay (엄격 재검토 결정 2026-07-02)

시각화 4분류는 개념 *정체성*이 아니라 **시각화 계층**의 판별 정보다. 같은 날 채택된 ADR
`concept_node_layering_decision.md` §1("visualization 계층=노드 비내장")과 `CurriculumEntry`
Overlay 선례(rev f3a4b5c6d7e8이 `subject`를 노드에서 제거)에 따라, `Concept` 노드가 아니라 별도
Overlay `concept_visualization`(code 키·loose ref·FK 없음)에 둔다. 한 행 존재=분류됨, 행 부재=미태깅
(하위호환). 노드 재내장은 `test_concept.py::_FORBIDDEN_NODE_FIELDS`가 차단한다.

### 4분류 정의 (플레이북 Part 5-1 — 인지 행동 기준·표면 표현 아님)

**핵심: 모든 개념이 똑같이 시각화되지 않는다. 어느 것도 "불가"가 아니라 *각기 다른 전략*을 요구한다.**
억지 리터럴 시각화는 오개념을 유발한다("그릴 수 있다 ≠ 교육적으로 좋다").

| 분류 | 의미 | 대표 개념 | 렌더 전략 |
|---|---|---|---|
| **직접** | 형태 자체가 보임 | 도형·함수그래프·좌표·벡터 | Geometry2D(정적) |
| **동적** ★ | 변화 과정 표현 (**AI 교육 핵심**) | 극한·미분·적분·함수변환 | 애니메이션·슬라이더 |
| **부분** | 일부 의미만 담김 | 확률·벡터공간·복소수·수렴 | AnalogyVisual(비유 + coverage 표시) |
| **추상** | 구조가 추상적 | 군론·위상·범주론·논리 | StructureGraph(메타포 중심) |

> **★동적**(극한·미분·적분·함수변환)이 AI 수학교육의 진짜 핵심 — 한국 학생이 가장 어려워하고 정적
> 그림으로는 이해가 안 되는 영역이다. **추상**은 리터럴 그래프가 거짓 구체성으로 오개념을 부르므로
> StructureGraph/메타포로만 그린다. **부분**은 일부 의미를 담는 표상(예: 확률→수형도)이 있어 억지가 아니다.

### 생성 게이트 (핵심 — "전부 똑같이 그리려" 방지)

정책은 순수 함수 `l4/visualization_policy.py`에 있고(L4 교수학 결정), 개념 노드가 아니라 시각화 4분류
*값*(`Visualizability | None`)을 입력받는다 — 값은 Overlay `concept_visualization`에서 호출자(L5)가
`get_visualizability(session, code)`로 조회해 넘긴다(노드 비내장·행 부재→None):

- `is_visualizable(v)` — **추상 → False**(리터럴 그래프 보류·StructureGraph 목표). 직접·동적·**부분**·
  **None(미태깅) → True**(부분은 AnalogyVisual 부분 시각화·None은 하위호환).
- `prefers_static_visual(v)` — **직접 → True**(Geometry2D 정적·슬라이더 생략). 동적·부분·None → False.

| 소비 지점 | 게이트 효과 |
|---|---|
| `l4/scene_generation.py::generate_learning_scene` | `visualizability` 파라미터로 게이트: 추상 → 리터럴 `visualization`/`param_control` 생략·소크라테스 폴백. 직접 → viz만(정적). 동적·부분·None → viz(+슬라이더) |
| `api/scene.py`·`api/visualization.py` | `get_visualizability(session, concept.code)`로 Overlay 조회 후 게이트 전달. 추상 → viz 생략 / `/weak-concept`는 None→404 |

의사결정 우선순위(CLAUDE.md): **3.교수학 정확성**이 6.비용·7.속도를 이긴다 — 억지 그림보다 정직한
"다른 접근"이 옳다.

---

## 2. 5상태 분리 (CP3) — Math → … → UI 단방향

플레이북 법칙: **Math / Pedagogy / Interaction / Animation / UI** 5상태가 분리되고 의존이 단방향.

| 상태 | 소재 좌석 | 성격 |
|---|---|---|
| **Math** | `Visualization.spec`(선언적 JSON) | stateless 구조 — 함수식·정의역·파라미터 선언(가변 런타임 아님) |
| **Pedagogy** | `LearningScene`·`learner_context`·답 미루기 불변식 | 스냅샷·판정 아님(낙인 금지)·`misconception_probe`엔 정답 필드 부재 |
| **Interaction** | `param_control`·`interactionEmitter`(웹) | 학생 조작 *선언*(어떤 파라미터를 조작 가능한가) |
| **Animation** | `animation_prerendered`(interactive=False 불변식) | 사전 렌더·조작 불가 |
| **UI** | dumb `SceneRenderer`(Flutter)·웹 어댑터 | 수학 로직 0 — 명세 → 위젯만 |

**단방향**: Math(schema)는 L3/L4/L5를 import하지 않고, 교수학 합성(L4 scene)은 L5(api)를 import하지
않는다. 화면은 코어 산출물이 아니라 *명세의 렌더 결과*다(슬89 표현≠의미).

**CI 강제**(`tests/backend/schema/test_visualization_state_separation.py`, hermetic):
① `Visualization` 필드 동결 + `spec`이 구조(dict) — 런타임 상태 필드 유입 시 red.
② 코어 시각화·장면 명세 필드에 런타임/UI 상태 부분문자열(current_/selected/hover/pixel/widget/
   playback…) 부재.
③ `VisualizationType` *값*은 Intent이지 구현체 이름 아님(CP2 보강).
④ 단방향 의존(schema<l4<api)은 레포 **import-linter 7계층 layers 계약**(`pyproject`·`lint-imports`
   CI)이 강제 — 거버넌스 테스트는 이를 재구현하지 않고 계약이 못 잡는 모델 필드·enum 값만 동결.

---

## 3. Renderer 독립 (CP2) — Concept → Intent → Adapter 3계층

구현체 이름을 *노드에 넣지 않는다*(플레이북·CLAUDE.md 8대 원칙 4). 현 파이프라인:

```
Concept.recommended_visual_styles   (교수학 힌트 — 단위원·수형도, 렌더러 아님)
        ↓
Visualization.type                  (Intent — interactive_graph_2d …, 구현체명 아님)
        ↓
data/render_contract.json  family   (Adapter 선택 — D3/Plotly/Desmos·three.js·Manim)
        ↓
L5 어댑터(specToStateForType·scene_renderer)  (구현체 실행 — WebView 국소 비상구)
```

구현체명(Desmos/three.js/WebGL/Canvas/Manim/D3/Plotly)은 **오직 `render_contract.json`과 L5 어댑터**에만
존재한다. 개념 노드(`concepts.jsonl`)·`Visualization` 스키마엔 0(검증: `test_concept.py` 금지필드 집합·
`test_visualization_state_separation.py` ③).

---

## 4. Visualization Intent 목표 아키텍처 (Part 5-2·5-4 — 현재 vs 목표)

> Part 5-2·5-4는 현재 구현보다 **더 깊은 목표 상태**를 규정한다. 아래는 정본 목표와 현 자산의 정직한
> 대조 + 로드맵이다("그래픽 시스템이 아니라 교육 ontology 시스템으로 봐야 함").

### 4.1 6계층 렌더러 독립 파이프라인 (5-2)

정본 목표(단 하나의 원칙: **VisualizationNode에 Desmos/WebGL/Canvas를 넣지 마라**):

```
Concept → Visualization Intent → Abstract Scene Graph → Capability Resolver → Renderer Adapter → Rendering Engine
          (intent: limit_approach)  (math_objects·interactions)  (runtime 선택)   (Desmos/Canvas/WebGL)  (픽셀·plugin 교체)
```

| 계층 | 목표(5-2) | 현재 자산 | 델타 |
|---|---|---|---|
| Visualization Intent | `intent: limit_approach`(구현체명 0) | `Visualization.type`(interactive_graph_2d) | 🟡 type이 intent 역할이나 렌더기술 명명(intent 어휘 미도입) |
| Abstract Scene Graph | `math_objects:[function_curve, movable_point, limit_indicator]`·renderer 독립 | `Visualization.spec`(타입별 typed·자유 JSON) | 🔴 renderer-독립 *math primitive* 어휘 미표준화 |
| Capability Resolver | runtime이 renderer 선택 | `data/render_contract.json`(type→family 정적 매핑) | 🟡 정적 계약은 있으나 런타임 capability 해석 없음 |
| Renderer Adapter | Desmos/Canvas/WebGL/SVG/Three.js Adapter | `specToStateForType`·`scene_renderer.dart`(L5) | 🟢 어댑터 존재(2D/3D) |
| Rendering Engine | plugin 교체 가능 | WebView 국소 비상구(D3/three.js) | 🟢 |

**표준 renderer-독립 math primitives(목표)**: `function_curve · point · vector · matrix · surface ·
implicit_curve · region · particle_field · limit_indicator · tangent_line`. Interaction도 추상화
(`onMouseMove` ❌ → `interaction:{type: drag_parameter}` ⭕·현 `param_control.targets`가 근사), Animation도
추상화(`fps:60` ❌ → `animation_intent: approach_limit` ⭕·현재 미도입).

### 4.2 KG 연결 (5-4)

목표 연결: `ConceptNode → VisualizationNode → InteractionNode → MisconceptionNode`
(relation: `visualizes` · `corrects` · `supports` · `requires` · `interacts_with`).

현재: Concept은 `visualization_card_keys`(참조 키)로 시각화를 가리키고, `LearningScene`이 viz +
`misconception_probe`를 한 장면으로 조립한다. **전용 `InteractionNode` 엔티티·타입드 관계(visualizes/
corrects…)는 미도입** — `param_control`(상호작용)·`misconception_probe`(교정)가 장면 요소로 근사한다.

### 4.3 로드맵 (Phase 2+ DSL)

Intent 어휘·Abstract Scene Graph(math primitives)·animation_intent·AnalogyVisual/StructureGraph
렌더러·InteractionNode는 **Math UI DSL(Part 7·`05a` LearningScene 확장) 후속**이다. 본 검토는
① 4분류 판별 축(Overlay) ② 억지 리터럴 방지 게이트 ③ Renderer 독립·5상태 CI 강제를 못박고, 위
목표는 정직한 델타로 남긴다(측정 없는 전면 전환 지양·`05a` §8 단계 로드맵과 정합).

## 5. 구현 매핑

| 요소 | 좌석 | 상태 |
|---|---|---|
| 4분류 enum | `schema/enums.py::Visualizability` | 🟢 4종·한글 값 |
| **시각화 Overlay**(노드 비내장) | ORM `db/models/concept_visualization.py`(code PK·loose ref)·마이그레이션 `..._concept_visualization_overlay.py` | 🟢 테이블·enum |
| 조회·적재 | `l1/concept_visualization`(`get_visualizability` async·`populate_concept_visualization` 시드) | 🟢 조회·upsert |
| 대표 시드(4분류) | `data/corpus/concept_visualization_v1/visualizability.json`(직접/동적/부분/추상 각 1) | 🟢 end-to-end 실증 |
| 생성 게이트 | `l4/visualization_policy.py`(값 입력) + `l4/scene_generation.py`·`api/scene.py`·`api/visualization.py`(Overlay 조회) | 🟢 추상 폴백·부분 시각화·직접 정적 |
| 노드 순수성 동결 | `test_concept.py::_FORBIDDEN_NODE_FIELDS`(visualizability 재내장 차단) | 🟢 CI |
| 5상태 거버넌스 | `tests/backend/schema/test_visualization_state_separation.py` | 🟢 hermetic·CI |

## 6. 범위·후속

- **점진 태깅**: 기존 개념은 `visualizability=None`(미태깅)이라 기존 시각화 동작을 유지한다. L1 데이터
  작업에서 개념별 4분류를 점진 태깅하면 추상이 걸러진다(측정 없는 전면 전환 지양).
- **추상 표상 후속**: `추상`은 현재 *자동 생성 시각화만* 보류한다. 구조도·비유 다이어그램 전용
  렌더(개념적 표상)는 후속 — 지금 억지 리터럴 렌더를 막는 것이 우선.

## 참고
- 상위: `docs/architecture/05_interaction.md`·`05a_learning_scene_dsl.md`
- 원칙: `CLAUDE.md`(8대 구조원칙 4 Renderer=Plugin·슬89 표현≠의미·의사결정 우선순위)
- 체크리스트: `docs/standards/playbook_part_review_questions.md` Part 5 · `build_checkpoint_questions.md` 단계 5
