// chat ↔ SceneRenderer 통합 테스트 — requestScene() 흐름 + AppBar 트리거 렌더. S5e.
//
// 라이브 네트워크 없음: 가짜 SceneApi 주입(sceneApiProvider override·기존 chat 테스트 패턴).
// 장면 생성·검증은 서버(L4)가 하고 클라는 받은 명세를 렌더만 한다(표현≠의미).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/data/scene_api.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';

/// 가짜 SceneApi — 정해진 장면 반환 또는 예외(SceneApi를 extends·coach 테스트 패턴).
class _FakeSceneApi extends SceneApi {
  _FakeSceneApi({this.scene, this.shouldThrow = false}) : super(Dio());

  final LearningScene? scene;
  final bool shouldThrow;

  @override
  Future<LearningScene> fetchWeakConceptScene() async {
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/scenes/weak-concept'),
        error: '네트워크 실패(테스트)',
      );
    }
    return scene!;
  }
}

LearningScene _scene() => const LearningScene(
      sceneId: 's1',
      conceptId: 'c1',
      layout: 'single',
      answerDeferralMaxLevel: 4,
      elements: [
        SceneElement(kind: 'socratic_prompt', promptText: '어디까지 이해됐어?'),
      ],
    );

ProviderContainer _container(SceneApi fake) {
  final container = ProviderContainer(
    overrides: [sceneApiProvider.overrideWithValue(fake)],
  );
  addTearDown(container.dispose);
  return container;
}

Widget _wrap(SceneApi fake) => ProviderScope(
      overrides: [sceneApiProvider.overrideWithValue(fake)],
      child: const MaterialApp(home: ChatScreen()),
    );

void main() {
  test('requestScene 성공 → 장면 메시지가 대화에 추가된다', () async {
    final container = _container(_FakeSceneApi(scene: _scene()));
    await container.read(chatControllerProvider.notifier).requestScene();
    final state = container.read(chatControllerProvider);
    expect(state.messages, hasLength(1));
    expect(state.messages[0].scene, isNotNull);
    expect(state.messages[0].isCoach, isTrue);
    expect(state.isSending, isFalse);
    expect(state.error, isNull);
  });

  test('requestScene 실패 → graceful 에러·메시지 미추가(앱 안 죽음)', () async {
    final container = _container(_FakeSceneApi(shouldThrow: true));
    await container.read(chatControllerProvider.notifier).requestScene();
    final state = container.read(chatControllerProvider);
    expect(state.messages, isEmpty);
    expect(state.error, isNotNull);
    expect(state.isSending, isFalse);
  });

  testWidgets('AppBar 장면 버튼 탭 → SceneRenderer가 렌더된다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeSceneApi(scene: _scene())));
    await tester.tap(find.byIcon(Icons.auto_awesome_outlined));
    await tester.pumpAndSettle();
    expect(find.byType(SceneRenderer), findsOneWidget);
    // 장면 안 소크라테스 발화(정본 유도 질문)가 렌더된다.
    expect(find.text('어디까지 이해됐어?'), findsOneWidget);
  });
}
