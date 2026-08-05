// LearningScene 데이터 모델 테스트 — 8종 요소 파싱 + fromJson∘toJson 라운드트립.
//
// 백엔드 `LearningScene`(05a §3) 직렬화 계약을 클라가 *구조 그대로* 받는지 검증한다
// (coach_models_test 패턴). 네트워크 없이 canned JSON으로 확인.
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';

/// 8종 요소·중첩 ref·learner_context를 모두 담은 장면 JSON.
Map<String, dynamic> _sceneJson() => {
      'scene_id': '11111111-1111-1111-1111-111111111111',
      'concept_id': 'ALG-QUAD-DEF',
      'topic_label': '이차함수의 그래프',
      'layout': 'two_panel',
      'answer_deferral_max_level': 4,
      'learner_context': {
        'mastery_level': 0.4,
        'active_hypothesis_ids': ['distribution-over-power'],
        'theta': 0.2,
      },
      'elements': [
        {
          'kind': 'visualization',
          'ref': {
            'type': 'interactive_graph_2d',
            'spec': {
              'function': 'a*x**2',
              'parameters': [
                {'name': 'a'},
              ],
            },
            'caption': '포물선',
            'interactive': true,
          },
        },
        {
          'kind': 'param_control',
          'targets': ['a'],
          'bound_visualization_index': 0,
        },
        {
          'kind': 'step_panel',
          'solution_path_id': 'sp-1',
          'reveal_policy': 'deferred',
        },
        {
          'kind': 'misconception_probe',
          'misconception_id': 'distribution-over-power',
          'intervention': 'counterexample',
        },
        {
          'kind': 'socratic_prompt',
          'socratic_category': 'clarification',
          'polya_stage': 'understand',
          'hint_level': 1,
          'prompt_text': '어디까지 이해됐어?',
        },
        {
          'kind': 'annotation',
          'target_element_index': 0,
          'highlight_spec': {'color': 'blue'},
        },
        {
          'kind': 'skill_focus',
          'behavior_area': 'VERIFY',
          'focus_prompt': '결과가 조건을 만족하는지 반례·특수값으로 점검하세요.',
        },
        {
          'kind': 'tutoring_prompt',
          'role': 'entry',
          'prompt_text': '더 작은 경우부터 시작해볼까?',
        },
      ],
    };

void main() {
  test('8종 요소·중첩 ref·learner_context를 정확히 파싱한다', () {
    final scene = LearningScene.fromJson(_sceneJson());

    expect(scene.sceneId, '11111111-1111-1111-1111-111111111111');
    expect(scene.conceptId, 'ALG-QUAD-DEF');
    expect(scene.topicLabel, '이차함수의 그래프');
    expect(scene.layout, 'two_panel');
    expect(scene.answerDeferralMaxLevel, 4);
    expect(scene.elements, hasLength(8));

    // 학습자 컨텍스트(중첩).
    expect(scene.learnerContext, isNotNull);
    expect(scene.learnerContext!.masteryLevel, closeTo(0.4, 1e-9));
    expect(scene.learnerContext!.activeHypothesisIds, ['distribution-over-power']);
    expect(scene.learnerContext!.theta, closeTo(0.2, 1e-9));

    // visualization(중첩 ref).
    final viz = scene.elements[0];
    expect(viz.kind, 'visualization');
    expect(viz.ref, isNotNull);
    expect(viz.ref!.type, 'interactive_graph_2d');
    expect(viz.ref!.caption, '포물선');
    expect(viz.ref!.interactive, isTrue);

    // param_control.
    final pc = scene.elements[1];
    expect(pc.kind, 'param_control');
    expect(pc.targets, ['a']);
    expect(pc.boundVisualizationIndex, 0);

    // step_panel.
    final sp = scene.elements[2];
    expect(sp.kind, 'step_panel');
    expect(sp.revealPolicy, 'deferred');

    // misconception_probe.
    final probe = scene.elements[3];
    expect(probe.kind, 'misconception_probe');
    expect(probe.misconceptionId, 'distribution-over-power');
    expect(probe.intervention, 'counterexample');

    // socratic_prompt.
    final soc = scene.elements[4];
    expect(soc.kind, 'socratic_prompt');
    expect(soc.hintLevel, 1);
    expect(soc.promptText, '어디까지 이해됐어?');

    // annotation.
    final ann = scene.elements[5];
    expect(ann.kind, 'annotation');
    expect(ann.targetElementIndex, 0);

    // skill_focus(행동영역 focus·S5k).
    final skill = scene.elements[6];
    expect(skill.kind, 'skill_focus');
    expect(skill.behaviorArea, 'VERIFY');
    expect(skill.focusPrompt, '결과가 조건을 만족하는지 반례·특수값으로 점검하세요.');

    // tutoring_prompt(LTHC mastery 적응·S5l·promptText 공유 재사용).
    final tutoring = scene.elements[7];
    expect(tutoring.kind, 'tutoring_prompt');
    expect(tutoring.role, 'entry');
    expect(tutoring.promptText, '더 작은 경우부터 시작해볼까?');
  });

  test('fromJson∘toJson 라운드트립 — 동치', () {
    final scene = LearningScene.fromJson(_sceneJson());
    final roundTripped = LearningScene.fromJson(scene.toJson());
    expect(roundTripped, equals(scene));
  });

  test('빈 elements·learner_context 없음도 파싱한다', () {
    final scene = LearningScene.fromJson({
      'scene_id': 's1',
      'concept_id': 'c1',
      'layout': 'single',
      'answer_deferral_max_level': 1,
    });
    expect(scene.elements, isEmpty);
    expect(scene.learnerContext, isNull);
    expect(scene.topicLabel, isNull);
  });
}
