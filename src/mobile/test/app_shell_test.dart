// 하단 탭 셸 위젯 테스트 — 홈/학습/탐구/나 탭 전환·셸 밖 라우트의 탭 바 부재(MOB-08).
//
// 실 앱(WhyMathApp)을 UncontrolledProviderScope로 띄우고(route_guard_test와 동형), 실 라우터를
// 컨테이너에서 읽어 `go`로 셸 진입을 구동한다. 채팅 브랜치가 coachApiProvider를, 인증이
// tokenStoreProvider를 읽으므로 fake로 override한다(네트워크·플랫폼 채널 없이 빌드).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/explore/presentation/explore_screen.dart';
import 'package:korean_math_app/features/home/presentation/home_screen.dart';
import 'package:korean_math_app/features/onboarding/presentation/onboarding_screen.dart';
import 'package:korean_math_app/features/profile/presentation/me_screen.dart';

/// 메모리 TokenStore — 플랫폼 채널 없이 인증 상태를 구동한다.
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
    throw UnimplementedError('셸 테스트는 coach를 호출하지 않습니다.');
  }
}

ProviderContainer _container() {
  final container = ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(_FakeTokenStore()),
      coachApiProvider.overrideWithValue(_FakeCoachApi()),
    ],
  );
  addTearDown(container.dispose); // UncontrolledProviderScope는 컨테이너를 dispose하지 않는다.
  return container;
}

/// NavigationBar 안의 탭 라벨을 눌러 탭을 전환한다(다른 화면의 동명 텍스트와 구분).
Future<void> _tapTab(WidgetTester tester, String label) async {
  await tester.tap(
    find.descendant(
      of: find.byType(NavigationBar),
      matching: find.text(label),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('하단 탭 셸이 홈/학습/탐구/나 전환을 렌더한다', (tester) async {
    final container = _container();
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const WhyMathApp()),
    );
    await tester.pumpAndSettle();

    // 셸 진입(홈 탭) — 실 라우터를 구동한다.
    container.read(goRouterProvider).go(AppRoutes.homePath);
    await tester.pumpAndSettle();

    // 하단 탭 바가 뜨고 홈 화면이 보인다.
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(HomeScreen), findsOneWidget);

    // 학습 탭 → 채팅 화면.
    await _tapTab(tester, '학습');
    expect(find.byType(ChatScreen), findsOneWidget);

    // 탐구 탭 → 탐구(준비 중) 화면.
    await _tapTab(tester, '탐구');
    expect(find.byType(ExploreScreen), findsOneWidget);

    // 나 탭 → 나(준비 중) 화면.
    await _tapTab(tester, '나');
    expect(find.byType(MeScreen), findsOneWidget);

    // 홈으로 복귀 — 셸이 브랜치 상태를 보존하며 되돌아온다.
    await _tapTab(tester, '홈');
    expect(find.byType(HomeScreen), findsOneWidget);
  });

  testWidgets('셸 밖 라우트(온보딩)에는 하단 탭 바가 없다', (tester) async {
    final container = _container();
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const WhyMathApp()),
    );
    await tester.pumpAndSettle();

    // 첫 진입은 온보딩(셸 밖) — 탭 바가 없어야 한다.
    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });
}
