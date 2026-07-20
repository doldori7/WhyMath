// L4 LearningScene DSL 데이터 모델 — 백엔드 `LearningScene`(05a §3) 계약을 *구조 그대로* 옮긴다.
//
// 정본: `src/backend/whymath_backend/l4/learning_scene.py`(`LearningScene`·`SceneElement` 7종
// 판별 유니온·`SceneLearnerContext`) + `schema/visualization.py`(`Visualization`).
//
// **경계(CLAUDE.md·슬라이스 89 표현≠의미)**: 이 클래스들은 *수신 컨테이너*일 뿐이다 — 장면의
// 조립·검증(불변식·참조 무결성)은 전부 서버(L4)에 있고, 클라는 검증된 명세를 받아 렌더만 한다.
// 정답·수정 같은 누출 위험 필드는 백엔드 스키마가 애초에 담지 않는다(misconception_probe엔 정답 없음).
//
// **판별 유니온 표현 방침**: 백엔드 `SceneElement`는 `kind` 판별 유니온 7종이지만, 클라는
// 코드젠 리스크(freezed union 선례 0)를 피해 **단일 flat 모델 + `kind` 문자열 + 변형별 nullable
// 필드**로 받는다. 렌더러가 `kind`로 분기한다(기존 String enum + nullable 관례·coach_models.dart).
import 'package:freezed_annotation/freezed_annotation.dart';

part 'scene_models.freezed.dart';
part 'scene_models.g.dart';

// ─────────────────────────────────────────────────────────────────────────
// 단일 시각화 명세 — Visualization (05 §5.2·schema/visualization.py)
// ─────────────────────────────────────────────────────────────────────────

/// 선언적 시각화 명세 — 렌더 기술(`type`) + 선언적 `spec`(자유 JSON).
///
/// 클라는 `type`/`caption`만으로 seed를 그린다(실 렌더는 후속 WebView·05a §6). `spec`은
/// 구조 그대로 보관만 한다(수학 로직 클라 미구현).
@freezed
abstract class Visualization with _$Visualization {
  const factory Visualization({
    /// 렌더 기술("interactive_graph_2d"·"interactive_surface_3d"·
    /// "simulation_probabilistic"·"animation_prerendered").
    @JsonKey(name: 'type') required String type,

    /// 선언적 렌더 명세(파라미터·데이터·축)·자유 JSON(클라는 보관만·없으면 null).
    @JsonKey(name: 'spec') Map<String, dynamic>? spec,

    /// 다국어 캡션·라벨(없으면 null).
    @JsonKey(name: 'caption') String? caption,

    /// 학생 파라미터 조작 가능 여부(animation_prerendered는 false).
    @JsonKey(name: 'interactive') @Default(true) bool interactive,
  }) = _Visualization;

  factory Visualization.fromJson(Map<String, dynamic> json) =>
      _$VisualizationFromJson(json);
}

// ─────────────────────────────────────────────────────────────────────────
// 학습자 컨텍스트 스냅샷 — SceneLearnerContext (05a §3.1)
// ─────────────────────────────────────────────────────────────────────────

/// 생성 시점 학습자 스냅샷 — *판정이 아니라* 장면 적응의 입력(읽기전용·낙인 근거 아님).
@freezed
abstract class SceneLearnerContext with _$SceneLearnerContext {
  const factory SceneLearnerContext({
    /// L2 BKT 숙달레벨(0~1)·없으면 null.
    @JsonKey(name: 'mastery_level') double? masteryLevel,

    /// WH-1 활성 오개념 가설 id(근거 있는 프로브 한정).
    @JsonKey(name: 'active_hypothesis_ids')
    @Default(<String>[]) List<String> activeHypothesisIds,

    /// L2 IRT 능력 추정치·없으면 null.
    @JsonKey(name: 'theta') double? theta,
  }) = _SceneLearnerContext;

  factory SceneLearnerContext.fromJson(Map<String, dynamic> json) =>
      _$SceneLearnerContextFromJson(json);
}

// ─────────────────────────────────────────────────────────────────────────
// 장면 요소 — SceneElement (flat·kind 판별·변형별 nullable)
// ─────────────────────────────────────────────────────────────────────────

/// 장면 합성 요소 1개 — `kind`로 7종을 구분한다(visualization·param_control·step_panel·
/// misconception_probe·socratic_prompt·annotation·skill_focus).
///
/// 백엔드 판별 유니온을 단일 flat 모델로 받는다 — 변형별 필드는 해당 kind에서만 채워지고
/// 나머지는 null. 렌더러는 `kind`로 분기한다.
///
/// **누출 안전(misconception_probe)**: `misconceptionId`·`intervention`만 담고 *정답·수정
/// 필드는 백엔드 스키마에 애초에 없다*(낙인/즉답 금지). 렌더러도 정답을 그리지 않는다.
@freezed
abstract class SceneElement with _$SceneElement {
  const factory SceneElement({
    /// 요소 종류 판별자(위 7종 중 하나).
    @JsonKey(name: 'kind') required String kind,

    // visualization
    /// 단일 시각화 명세(visualization kind).
    @JsonKey(name: 'ref') Visualization? ref,

    // param_control
    /// 조작 대상 파라미터 이름(param_control kind).
    @JsonKey(name: 'targets') @Default(<String>[]) List<String> targets,

    /// 조작 대상 visualization 요소의 인덱스(param_control kind).
    @JsonKey(name: 'bound_visualization_index') int? boundVisualizationIndex,

    // step_panel
    /// 참조 검증 풀이 경로 id(step_panel kind).
    @JsonKey(name: 'solution_path_id') String? solutionPathId,

    /// 노출 정책 — "deferred"만(step_panel kind·점층 노출).
    @JsonKey(name: 'reveal_policy') String? revealPolicy,

    // misconception_probe
    /// 오개념 카탈로그 id(misconception_probe kind·렌더 안 함·텔레메트리).
    @JsonKey(name: 'misconception_id') String? misconceptionId,

    /// 개입 패턴("counterexample"·"concrete_case"·"visualization"·"reverse_reasoning").
    @JsonKey(name: 'intervention') String? intervention,

    // socratic_prompt
    /// 소크라테스 6카테고리 문자열(socratic_prompt kind).
    @JsonKey(name: 'socratic_category') String? socraticCategory,

    /// Polya 단계 문자열(socratic_prompt kind).
    @JsonKey(name: 'polya_stage') String? polyaStage,

    /// 답 미루기 단계 1~4(socratic_prompt kind).
    @JsonKey(name: 'hint_level') int? hintLevel,

    /// 학생에게 던질 유도 질문(socratic_prompt kind·정답 아님).
    @JsonKey(name: 'prompt_text') String? promptText,

    // annotation
    /// 강조 대상 요소 인덱스(annotation kind).
    @JsonKey(name: 'target_element_index') int? targetElementIndex,

    /// 강조/라벨 선언 명세(annotation kind·자유 JSON).
    @JsonKey(name: 'highlight_spec') Map<String, dynamic>? highlightSpec,

    // skill_focus (행동영역 focus·S5k)
    /// 이 블록이 드러내는 행동영역(skill_focus kind·정본 BehaviorArea 6종).
    @JsonKey(name: 'behavior_area') String? behaviorArea,

    /// 선언적 행동 focus 지시(skill_focus kind·정답 아님).
    @JsonKey(name: 'focus_prompt') String? focusPrompt,
  }) = _SceneElement;

  factory SceneElement.fromJson(Map<String, dynamic> json) =>
      _$SceneElementFromJson(json);
}

// ─────────────────────────────────────────────────────────────────────────
// 학습 장면 — LearningScene (05a §3.1)
// ─────────────────────────────────────────────────────────────────────────

/// 학습 장면 한 장의 선언적 합성 명세 — 요소들의 조립.
///
/// `layout`은 배치 *힌트*(픽셀 아님)·`answerDeferralMaxLevel`은 힌트 상한(서버 불변식).
@freezed
abstract class LearningScene with _$LearningScene {
  const factory LearningScene({
    /// 장면 PK(UUID 문자열).
    @JsonKey(name: 'scene_id') required String sceneId,

    /// 이 장면이 가르치는 개념 code(UC).
    @JsonKey(name: 'concept_id') required String conceptId,

    /// 다국어 캡션·라벨(없으면 null).
    @JsonKey(name: 'topic_label') String? topicLabel,

    /// 배치 힌트("single"·"vertical_stack"·"two_panel"·"tabbed").
    @JsonKey(name: 'layout') required String layout,

    /// 장면이 허용하는 최대 힌트 단계(1~4·답 미루기 상한).
    @JsonKey(name: 'answer_deferral_max_level') required int answerDeferralMaxLevel,

    /// 생성 시점 학습자 스냅샷(없으면 null).
    @JsonKey(name: 'learner_context') SceneLearnerContext? learnerContext,

    /// 합성 요소(순서 = 렌더 순서).
    @JsonKey(name: 'elements') @Default(<SceneElement>[]) List<SceneElement> elements,
  }) = _LearningScene;

  factory LearningScene.fromJson(Map<String, dynamic> json) =>
      _$LearningSceneFromJson(json);
}
