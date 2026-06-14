// 앱 라우팅 셸 — go_router 설정과 라우트 상수.
//
// 단일 화면(MaterialApp.home)에서 go_router 기반 셸로 전환한다. 첫 진입은 온보딩
// (메타인지 철학 안내·기대 관리)이고, "시작하기"로 채팅 화면에 진입한다.
//
// 정직(범위): 로그인 화면(`/login`·OAuth-c2)은 라우트로 *등록*만 됐다 — 실 code 획득(c3)
// 전엔 작동하지 않으므로 기본 흐름은 여전히 온보딩→채팅이고 로그인을 강제하지 않는다(앱 유지).
// 온보딩 1회-노출 영속(shared_preferences)·인증 흐름 강제(가드)·세션 복원·딥링크·하단 탭은
// *후속 슬라이스*다 — pubspec에 shared_preferences가 없어 이번엔 의존성을 추가하지 않는다.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/presentation/login_screen.dart';
import '../features/chat/presentation/chat_screen.dart';
import '../features/onboarding/presentation/onboarding_screen.dart';

/// 앱 라우트 경로·이름 상수.
///
/// 문자열 리터럴 분산을 막아 라우트 정의·네비게이션 호출이 같은 상수를 참조하게 한다.
abstract final class AppRoutes {
  /// 온보딩(첫 진입) 경로.
  static const String onboardingPath = '/onboarding';

  /// 온보딩 라우트 이름.
  static const String onboardingName = 'onboarding';

  /// 채팅(메인) 경로.
  static const String chatPath = '/';

  /// 채팅 라우트 이름.
  static const String chatName = 'chat';

  /// 로그인(소셜) 경로 — OAuth-c2. 등록만 하고 기본 흐름은 강제하지 않는다.
  static const String loginPath = '/login';

  /// 로그인 라우트 이름.
  static const String loginName = 'login';
}

/// 앱 전역 [GoRouter] provider.
///
/// `initialLocation`은 온보딩 — 첫 진입에서 메타인지 접근을 먼저 안내한다. 라우터 인스턴스는
/// 앱 수명 동안 1개만 유지되도록 plain [Provider]로 둔다(코드 생성 의존 없이 기존 provider
/// 패턴과 일치). `/login`(OAuth-c2)은 등록만 했고, 라우트 가드(미인증 redirect)·온보딩 영속
/// redirect는 후속 슬라이스다(기본 흐름은 온보딩→채팅 유지).
final goRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.onboardingPath,
    routes: [
      GoRoute(
        path: AppRoutes.onboardingPath,
        name: AppRoutes.onboardingName,
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: AppRoutes.chatPath,
        name: AppRoutes.chatName,
        builder: (context, state) => const ChatScreen(),
      ),
      // 소셜 로그인(OAuth-c2) — 라우트로 등록만 한다. 실 code 획득(c3) 전엔 작동하지 않으므로
      // initialLocation·온보딩 흐름은 건드리지 않는다(흐름 강제·세션 복원은 c2b).
      GoRoute(
        path: AppRoutes.loginPath,
        name: AppRoutes.loginName,
        builder: (context, state) => const LoginScreen(),
      ),
    ],
    // 미정의 경로 안전 처리 — 잘못된 딥링크/오타로 앱이 죽지 않게 채팅으로 안내한다.
    errorBuilder: (context, state) => const ChatScreen(),
  );
});
