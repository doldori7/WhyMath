// 라우트 가드 + 세션 복원 위젯 테스트 — 복원된 인증 세션의 채팅 전이·미인증 비파괴. OAuth-c2b.
//
// 플랫폼 채널 없이: fake TokenStore(메모리)+fake CoachApi를 주입한 ProviderContainer를 만들고
// runApp 전처럼 restore()를 *먼저* 호출한 뒤 UncontrolledProviderScope로 실 앱(WhyMathApp)을
// 띄운다 — main()의 restore-before-runApp을 그대로 재현한다. ChatScreen이 coachApiProvider를
// 읽으므로 fake로 override한다(이 테스트는 coach를 호출하지 않는다).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/application/auth_controller.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/onboarding/presentation/onboarding_screen.dart';

/// 메모리 TokenStore — 주입한 토큰을 그대로 돌려준다(보안 저장소 플랫폼 채널 회피).
class _FakeTokenStore implements TokenStore {
  String? saved;

  @override
  Future<String?> readAccessToken() async => saved;

  @override
  Future<void> saveAccessToken(String token) async => saved = token;

  @override
  Future<void> clear() async => saved = null;
}

/// 호출되지 않는 fake — 채팅 화면이 빌드만 되도록 둔다(이 테스트는 전송하지 않음).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi() : super(Dio());

  @override
  Future<CoachResponse> coach(CoachRequest request) async {
    throw UnimplementedError('가드 테스트는 coach를 호출하지 않습니다.');
  }
}

ProviderContainer _container({required String? token}) {
  final container = ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(_FakeTokenStore()..saved = token),
      coachApiProvider.overrideWithValue(_FakeCoachApi()),
    ],
  );
  addTearDown(container.dispose); // UncontrolledProviderScope는 컨테이너를 dispose하지 않는다.
  return container;
}

void main() {
  testWidgets('복원된 인증 세션은 온보딩 대신 채팅으로 전이한다(가드)', (tester) async {
    final container = _container(token: 'tok');
    // runApp 전처럼 복원을 먼저 끝내 첫 redirect 평가가 인증 상태를 보게 한다.
    await container.read(authControllerProvider.notifier).restore();

    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const WhyMathApp()),
    );
    await tester.pumpAndSettle();

    // 슬로건 문자열은 로그인 화면에도 있으므로 타입으로 단언한다.
    expect(find.byType(ChatScreen), findsOneWidget);
    expect(find.byType(OnboardingScreen), findsNothing);
  });

  testWidgets('미인증은 온보딩 흐름을 그대로 유지한다(비파괴)', (tester) async {
    final container = _container(token: null);
    await container.read(authControllerProvider.notifier).restore();

    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const WhyMathApp()),
    );
    await tester.pumpAndSettle();

    // 미인증이면 가드는 redirect하지 않는다 — 온보딩(첫 진입) 유지.
    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻습니다'), findsOneWidget); // 온보딩 전용 문구
    expect(find.byType(ChatScreen), findsNothing);
  });
}
