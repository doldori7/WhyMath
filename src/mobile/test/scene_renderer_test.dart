// SceneRenderer 위젯 테스트 — kind→위젯 렌더와 *답 미루기·낙인* 가드를 검증.
//
// canned LearningScene(런타임 객체)로 네트워크 없이 확인한다. misconception_probe에서 정답·
// 수정·오개념 id·"틀렸다" 단정이 *렌더 텍스트에 없음*을 단언해 절대 금기를 지킨다.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';

/// 요소 리스트로 최소 장면을 만든다(테스트 공통).
LearningScene _scene(List<SceneElement> elements, {String? topicLabel}) =>
    LearningScene(
      sceneId: 's1',
      conceptId: 'c1',
      topicLabel: topicLabel,
      layout: 'vertical_stack',
      answerDeferralMaxLevel: 4,
      elements: elements,
    );

Widget _wrap(LearningScene scene) =>
    MaterialApp(home: Scaffold(body: SceneRenderer(scene: scene)));

void main() {
  testWidgets('socratic_prompt는 promptText(유도 질문)를 렌더한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'socratic_prompt', promptText: '어디까지 이해됐어?'),
        ]),
      ),
    );
    expect(find.text('어디까지 이해됐어?'), findsOneWidget);
  });

  testWidgets('visualization은 caption seed를 렌더한다(실 WebView 아님)', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'visualization',
            ref: Visualization(type: 'interactive_graph_2d', caption: '포물선'),
          ),
        ]),
      ),
    );
    expect(find.text('포물선'), findsOneWidget);
  });

  testWidgets('param_control은 대상 파라미터 cue를 렌더한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'param_control', targets: ['a', 'b']),
        ]),
      ),
    );
    expect(find.textContaining('파라미터 조작'), findsOneWidget);
    expect(find.textContaining('a, b'), findsOneWidget);
  });

  testWidgets('step_panel은 접힌 단계 패널을 렌더한다(deferred)', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'step_panel', revealPolicy: 'deferred'),
        ]),
      ),
    );
    expect(find.text('단계별로 살펴보기'), findsOneWidget);
    // 접힘 — 펼침 내용은 탭 전엔 트리에 없다(답 미루기·점층 노출).
    expect(find.text('차근차근 단계를 펼쳐 볼 수 있어요.'), findsNothing);
  });

  testWidgets('misconception_probe는 사고 유도 cue만·정답/낙인 없음', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'misconception_probe',
            misconceptionId: 'distribution-over-power',
            intervention: 'counterexample',
          ),
        ]),
      ),
    );
    expect(find.textContaining('반례를 떠올려'), findsOneWidget);
    // 답 미루기·낙인 가드: 오개념 id 원문·"틀렸"·정답·수정 미렌더.
    expect(find.textContaining('distribution-over-power'), findsNothing);
    expect(find.textContaining('틀렸'), findsNothing);
    expect(find.textContaining('정답'), findsNothing);
  });

  testWidgets('annotation은 강조 라벨을 렌더한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'annotation', targetElementIndex: 0),
        ]),
      ),
    );
    expect(find.text('강조 표시'), findsOneWidget);
  });

  testWidgets('topicLabel 헤더를 렌더한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(
          const [SceneElement(kind: 'socratic_prompt', promptText: '질문')],
          topicLabel: '이차함수',
        ),
      ),
    );
    expect(find.text('이차함수'), findsOneWidget);
  });

  testWidgets('빈 elements는 아무것도 렌더하지 않는다(SizedBox.shrink)', (tester) async {
    await tester.pumpWidget(_wrap(_scene(const [])));
    expect(find.byType(Card), findsNothing);
    expect(find.byType(ExpansionTile), findsNothing);
  });

  testWidgets('미지 kind는 조용히 생략한다(전방호환)', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'future_unknown_kind'),
          SceneElement(kind: 'socratic_prompt', promptText: '알려진 발화'),
        ]),
      ),
    );
    expect(find.text('알려진 발화'), findsOneWidget);
  });

  testWidgets('6종 요소가 한 장면에서 모두 렌더된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'visualization',
            ref: Visualization(type: 'interactive_graph_2d', caption: '그래프'),
          ),
          SceneElement(kind: 'param_control', targets: ['a']),
          SceneElement(kind: 'step_panel'),
          SceneElement(kind: 'misconception_probe', intervention: 'concrete_case'),
          SceneElement(kind: 'socratic_prompt', promptText: '왜 그렇게 생각했어?'),
          SceneElement(kind: 'annotation'),
        ]),
      ),
    );
    expect(find.text('그래프'), findsOneWidget);
    expect(find.textContaining('파라미터 조작'), findsOneWidget);
    expect(find.text('단계별로 살펴보기'), findsOneWidget);
    expect(find.textContaining('구체적인 예'), findsOneWidget);
    expect(find.text('왜 그렇게 생각했어?'), findsOneWidget);
    expect(find.text('강조 표시'), findsOneWidget);
  });
}
