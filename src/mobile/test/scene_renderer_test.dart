// SceneRenderer 위젯 테스트 — kind→위젯 렌더와 *답 미루기·낙인* 가드를 검증.
//
// canned LearningScene(런타임 객체)로 네트워크 없이 확인한다. misconception_probe에서 정답·
// 수정·오개념 id·"틀렸다" 단정이 *렌더 텍스트에 없음*을 단언해 절대 금기를 지킨다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/data/solution_path_api.dart';
import 'package:korean_math_app/features/chat/data/solution_path_models.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';

/// 가짜 SolutionPathApi — 고정 1단계 페이지를 돌려준다(step_panel은 실조회하므로
/// 레지스트리 테스트에도 주입이 필요하다. 점층 동작 전체는 step_panel_test.dart가 동결).
class _FakeSolutionPathApi extends SolutionPathApi {
  _FakeSolutionPathApi() : super(Dio());

  @override
  Future<SolutionStepsPage> fetchSteps(
    String solutionPathId, {
    required int upTo,
  }) async =>
      const SolutionStepsPage(
        steps: [SolutionStep(stepOrder: 1, content: '첫 단계 내용')],
        total: 2,
        upTo: 1,
      );
}

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

  testWidgets('spec 없는 2d 시각화는 caption seed를 렌더한다(WebView 폴백)', (tester) async {
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

  testWidgets('비대화형(interactive:false) 2d는 spec 있어도 seed로 폴백한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'visualization',
            ref: Visualization(
              type: 'interactive_graph_2d',
              spec: {'function': 'x^2'},
              caption: '정적 포물선',
              interactive: false,
            ),
          ),
        ]),
      ),
    );
    expect(find.text('정적 포물선'), findsOneWidget);
  });

  testWidgets('spec 없는 3d 시각화는 seed(caption)로 폴백한다', (tester) async {
    // 3d+spec은 WebView로 가지만(헤드리스 미pump·수동 검증), spec이 없으면 seed.
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'visualization',
            ref: Visualization(type: 'interactive_surface_3d', caption: '곡면'),
          ),
        ]),
      ),
    );
    expect(find.text('곡면'), findsOneWidget);
  });

  testWidgets('WebView 미지원 타입(animation_prerendered)은 seed(caption)로 폴백한다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'visualization',
            ref: Visualization(
              type: 'animation_prerendered',
              spec: {'asset_id': 'x'},
              caption: '애니메이션',
              interactive: false,
            ),
          ),
        ]),
      ),
    );
    expect(find.text('애니메이션'), findsOneWidget);
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

  testWidgets('solutionPathId 없는 step_panel은 조용히 생략한다(계약 방어)', (tester) async {
    // 서버는 solution_path 실재 시에만 step_panel을 방출한다(SOL-02 ③) — id 부재는
    // 계약 위반이라 빈 카드를 그리지 않는다. 실단계 점층 노출 동작 전체는
    // step_panel_test.dart가 동결한다.
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(kind: 'step_panel', revealPolicy: 'deferred'),
        ]),
      ),
    );
    expect(find.text('단계별로 살펴보기'), findsNothing);
    expect(find.text('다음 단계 보기'), findsNothing);
    expect(tester.takeException(), isNull);
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

  testWidgets('skill_focus는 행동 focus 지시 cue만·정답 없음', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'skill_focus',
            behaviorArea: 'VERIFY',
            focusPrompt: '결과가 조건을 만족하는지 반례·특수값으로 점검하세요.',
          ),
        ]),
      ),
    );
    expect(find.textContaining('반례·특수값으로'), findsOneWidget);
    // 정답/낙인 가드: 정답·틀렸 미렌더(선언적 행동 지시일 뿐).
    expect(find.textContaining('정답'), findsNothing);
    expect(find.textContaining('틀렸'), findsNothing);
  });

  testWidgets('tutoring_prompt는 역할 배지(진입점)+발화만·정답 없음', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'tutoring_prompt',
            role: 'entry',
            promptText: '더 작은 경우부터 시작해볼까?',
          ),
        ]),
      ),
    );
    expect(find.text('진입점'), findsOneWidget); // LTHC 역할 배지
    expect(find.textContaining('더 작은 경우부터'), findsOneWidget); // 정본 발화
    // 정답/낙인 가드: 정답·틀렸 미렌더(지원 발화일 뿐·판정 아님).
    expect(find.textContaining('정답'), findsNothing);
    expect(find.textContaining('틀렸'), findsNothing);
  });

  testWidgets('tutoring_prompt 미지 role은 배지 없이 발화만 렌더한다(전방호환)', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _scene(const [
          SceneElement(
            kind: 'tutoring_prompt',
            role: 'future_role',
            promptText: '이 발상을 다른 문제에도 쓸 수 있을까?',
          ),
        ]),
      ),
    );
    expect(find.textContaining('다른 문제에도'), findsOneWidget);
    expect(find.text('진입점'), findsNothing); // 미지 role → 배지 생략
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

  testWidgets('8종 요소가 한 장면에서 모두 렌더된다', (tester) async {
    await tester.pumpWidget(
      // step_panel은 solutionPathId로 실조회하므로 가짜 API를 주입한다(chat_scene_test 패턴).
      ProviderScope(
        overrides: [solutionPathApiProvider.overrideWithValue(_FakeSolutionPathApi())],
        child: _wrap(
          _scene(const [
            SceneElement(
              kind: 'visualization',
              ref: Visualization(type: 'interactive_graph_2d', caption: '그래프'),
            ),
            SceneElement(kind: 'param_control', targets: ['a']),
            SceneElement(
              kind: 'step_panel',
              solutionPathId: 'sp-1',
              revealPolicy: 'deferred',
            ),
            SceneElement(kind: 'misconception_probe', intervention: 'concrete_case'),
            SceneElement(kind: 'socratic_prompt', promptText: '왜 그렇게 생각했어?'),
            SceneElement(kind: 'annotation'),
            SceneElement(
              kind: 'skill_focus',
              behaviorArea: 'INTERPRET',
              focusPrompt: '주어진 조건을 먼저 수학 구조(식·관계)로 해석하세요.',
            ),
            SceneElement(
              kind: 'tutoring_prompt',
              role: 'scaffold',
              promptText: '어디서 막혔는지 같이 봐줄게.',
            ),
          ]),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('그래프'), findsOneWidget);
    expect(find.textContaining('파라미터 조작'), findsOneWidget);
    expect(find.text('단계별로 살펴보기'), findsOneWidget);
    expect(find.textContaining('첫 단계 내용'), findsOneWidget); // step_panel 1단계(deferred)
    expect(find.textContaining('구체적인 예'), findsOneWidget);
    expect(find.text('왜 그렇게 생각했어?'), findsOneWidget);
    expect(find.text('강조 표시'), findsOneWidget);
    expect(find.textContaining('수학 구조'), findsOneWidget);
    expect(find.text('비계'), findsOneWidget); // tutoring_prompt 역할 배지
    expect(find.textContaining('같이 봐줄게'), findsOneWidget);
  });
}
