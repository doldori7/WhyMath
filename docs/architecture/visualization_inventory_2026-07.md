# 시각화 엔진 인벤토리·커버리지 (ARCH-13 산출물)

> **목적**: 시각화 서브시스템을 빌드 하네스 소유(태스크 `ARCH-13`)로 **추적 등재**하고, 구현/spec-only/부재를 **커버리지 공백**으로 명시한다. `docs/strategy/core_feature_review_2026-07.md §3.2`("built but untracked" 부채)의 상환 산출물.
> **성격**: 코드 신규 없음 — 실측 인벤토리·문서화. 유형 확장 실작업은 `S4-03-visualization-type-expansion`(파일럿 이후 후순위).
> **정본**: `05_interaction.md`(L5 경계) · `05a_learning_scene_dsl.md`(장면 DSL) · `05b_visualization_classification.md`(유형 분류). 본 문서는 *현재 구현 상태 스냅샷*이며 정본을 대체하지 않는다.

---

## 1. 구성요소 인벤토리 (실측 2026-07-18)

| 계층 | 역할 | 파일 |
|---|---|---|
| L3 생성·검증 | 선언적 JSON spec **생성**(영상 bytes 반환 금지 — 경계 위반) + typed 검증 | `src/backend/whymath_backend/l3/visualization.py`(`generate_visualization_spec`·`visualization_spec_for_concept`) · `l3/viz_eval.py`(라이브 eval 하네스) |
| 스키마 | `VisualizationType` 4종 enum + type별 typed spec 모델 + 불변식 | `schema/visualization.py`(`Graph2dSpec`·`Surface3dSpec`·`SimulationSpec`·`AnimationSpec`·`_SPEC_MODEL_BY_TYPE`·`validate_spec_for_type`) · `schema/enums.py`(`VisualizationType`) |
| L4 장면·정책 | 개념 진단 → 장면 DSL·시각화 정책 결정 | `l4/scene_generation.py` · `l4/learning_scene.py` · `l4/visualization_policy.py` |
| API | 개념 진단·약개념 시각화·spec CRUD 엔드포인트 | `api/visualization.py` · `api/scene.py` |
| L5 웹 렌더러 | spec → 렌더 상태 변환·조작(국소 비상구) | `src/web/graphing-calculator/src/lib/graph2dSpec.js`(type→렌더러 디스패치) · `simulationExperiment.js` · `mathExpr.js`(mathjs) · `interactionEmitter.js` · three.js(3D) · mathlive(입력) |
| L5 모바일 렌더러 | WebView 브리지로 웹 계산기 임베드 | `src/mobile/lib/features/chat/presentation/scene_renderer.dart` · `graphing_calculator_webview.dart` · `mathlive_input_webview.dart` |

---

## 2. spec 유형 커버리지 (4 enum + 부재)

`VisualizationType` enum은 4종을 정의하며, `graph2dSpec.js`가 type→렌더러로 디스패치한다.

| VisualizationType | 생성·검증(L3) | 웹 렌더 | 상태 |
|---|---|---|---|
| `interactive_graph_2d` | ✅ `Graph2dSpec` | ✅ `graph2dSpecToState`(mathjs·2D 함수/관계 그래프·슬라이더 조작) | 🟢 **구현** |
| `interactive_surface_3d` | ✅ `Surface3dSpec` | ✅ `surface3dSpecToState`(three.js·회전/단면) | 🟢 **구현** |
| `simulation_probabilistic` | ✅ `SimulationSpec` | ✅ `simulationSpecToState`(`simulationExperiment.js`·시행 반복) | 🟢 **구현** |
| `animation_prerendered` | ✅ `AnimationSpec`(불변식: 조작 불가) | ❌ `→ null`(`graph2dSpec.js:180` "웹 계산기엔 Manim 재생 경로 없음"·Flutter도 폴백) | 🟡 **spec-only·렌더 경로 부재** |

**부재(enum 자체에 없음 — spec 타입·렌더러 모두 없음)**:
- **기하(작도)** — 컴퍼스·자 작도, 도형 변환
- **벡터** — 벡터 합·성분·내적 시각화
- **행렬 변환** — 선형변환의 격자·기저 시각화
- **미적분 과정 애니메이션** — 리만 합·접선 기울기·극한 과정 등 (현재 `animation_prerendered`(Manim) 경로가 유일한 후보이나 렌더 미구현)

---

## 3. 커버리지 공백 → 소유 태스크

| 공백 | 소유 태스크 | 스테이지 |
|---|---|---|
| 서브시스템 추적·문서화(본 문서) | **`ARCH-13-visualization-harness-tracking`**(infra-debt) | S3 (완료) |
| 기하·벡터·행렬변환·미적분 애니메이션 spec 타입 + 렌더러 · `animation_prerendered`(Manim) 렌더 경로 | **`S4-03-visualization-type-expansion`**(math-completion) | S4 (`S3-01` 파일럿 의존·후순위) |

**확장 원칙**(S4-03 착수 시 준수): 새 유형은 *선언적 spec + 렌더러 플러그인* 구조(`05_interaction.md`)를 유지해 **`VisualizationType` enum + typed spec 모델 + 렌더러 디스패치 케이스 추가**로만 해결한다. 구현체 이름(three.js·Manim)을 개념 노드에 넣지 않는다(렌더러는 플러그인·`05b` 분류 준수).

---

## 4. 아키텍처 경계 (유지 불변식)

- **L3 = spec 생성·검증, L5 = 렌더**. `generate_visualization_spec`은 선언적 JSON만 반환한다(영상 bytes 반환은 7계층 경계 위반).
- **표현 ≠ 의미**: `Visualization`은 화면 문자열이 아니라 구조(JSON)로 코어에 저장하고, 렌더는 각 클라(웹·모바일 WebView)가 담당한다(`system_deep_dive.md §1`).
- **불변식(슬90)**: `animation_prerendered`는 `interactive=False`(조작 불가) — `schema/visualization.py`의 `@model_validator`가 동결하고, 완전성(4종 전부 매핑)은 테스트가 단언한다.
- **미렌더는 조용한 폴백**: 렌더 경로 없는 type(`animation_prerendered`)은 `null` 반환으로 조용히 미렌더(에러 아님) — 향후 렌더 경로 추가 시 이 폴백 지점을 교체한다.

---

## 5. 근거 (실측 출처)

- 4 enum·typed 모델·불변식: `src/backend/whymath_backend/schema/visualization.py`(`_SPEC_MODEL_BY_TYPE`·`validate_spec_for_type`·`animation_prerendered` non-interactive validator) · `schema/enums.py`(`VisualizationType`)
- 생성·검증: `l3/visualization.py`(`generate_visualization_spec`) · `l3/viz_eval.py`
- 웹 디스패치·Manim 렌더 부재: `src/web/graphing-calculator/src/lib/graph2dSpec.js:169-181`(type→렌더러·`animation_prerendered → null`) · `simulationExperiment.js` · `mathExpr.js`
- 모바일 브리지: `src/mobile/lib/features/chat/presentation/{scene_renderer,graphing_calculator_webview}.dart`
- 상위 검토: `docs/strategy/core_feature_review_2026-07.md §3.2` · 정본 `05_interaction.md`·`05a`·`05b`
