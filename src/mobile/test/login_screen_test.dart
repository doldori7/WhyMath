// 로그인 화면 위젯 테스트 — 버튼·code 교환 성공 전이·획득 실패 안내. OAuth-c2.
//
// 플랫폼 채널·네트워크·실 webview 없이: fake OAuthCodeRequester(code 반환 또는 OAuthCodeException)
// + fake AuthApi(token) + fake TokenStore를 provider override로 주입한다(auth_controller_test·
// onboarding_test 패턴). 테스트용 GoRouter(`/login`→LoginScreen·`/`→'CHAT' 마커)로 네비게이션을
// 검증한다 — 실 라우터의 온보딩 흐름은 건드리지 않는다(c2는 라우트 등록만·비파괴).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/data/auth_api.dart';
import 'package:korean_math_app/features/auth/data/oauth_code_requester.dart';
import 'package:korean_math_app/features/auth/presentation/login_screen.dart';

/// fake 코드 획득기 — 주입된 code를 돌려주거나 [OAuthCodeException]을 던진다(실 webview 대체).
class _FakeRequester implements OAuthCodeRequester {
  _FakeRequester({this.request, this.exception});

  final OAuthCodeRequest? request;
  final OAuthCodeException? exception;

  @override
  Future<OAuthCodeRequest> requestCode(String provider) async {
    if (exception != null) {
      throw exception!;
    }
    return request!;
  }
}

/// fake AuthApi — 네트워크 없이 토큰을 돌려준다(AuthController가 ref.read로 사용).
class _FakeAuthApi extends AuthApi {
  _FakeAuthApi(this.token) : super(Dio());

  final String token;

  @override
  Future<String> login({
    required String provider,
    required String code,
    required String redirectUri,
  }) async =>
      token;
}

/// fake TokenStore — 메모리 저장(플랫폼 채널 회피).
class _FakeTokenStore implements TokenStore {
  String? saved;

  @override
  Future<String?> readAccessToken() async => saved;

  @override
  Future<void> saveAccessToken(String token) async => saved = token;

  @override
  Future<void> clear() async => saved = null;
}

/// 테스트용 라우터 — `/login`(화면)·`/`('CHAT' 마커)만 둔다(전이 확인용).
GoRouter _router() {
  return GoRouter(
    initialLocation: AppRoutes.loginPath,
    routes: [
      GoRoute(
        path: AppRoutes.loginPath,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.chatPath,
        builder: (context, state) =>
            const Scaffold(body: Center(child: Text('CHAT'))),
      ),
    ],
  );
}

Widget _app({
  required OAuthCodeRequester requester,
  required AuthApi api,
  required TokenStore store,
}) {
  return ProviderScope(
    overrides: [
      oauthCodeRequesterProvider.overrideWithValue(requester),
      authApiProvider.overrideWithValue(api),
      tokenStoreProvider.overrideWithValue(store),
    ],
    child: MaterialApp.router(routerConfig: _router()),
  );
}

void main() {
  testWidgets('카카오·네이버 로그인 버튼이 보인다', (tester) async {
    await tester.pumpWidget(_app(
      requester: _FakeRequester(
        request: const OAuthCodeRequest(code: 'c', redirectUri: 'r'),
      ),
      api: _FakeAuthApi('tok'),
      store: _FakeTokenStore(),
    ));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, '카카오로 시작하기'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '네이버로 시작하기'), findsOneWidget);
  });

  testWidgets('카카오 탭 → code 교환 성공 → 토큰 저장·채팅 전이', (tester) async {
    final store = _FakeTokenStore();
    await tester.pumpWidget(_app(
      requester: _FakeRequester(
        request: const OAuthCodeRequest(code: 'c', redirectUri: 'r'),
      ),
      api: _FakeAuthApi('tok'),
      store: store,
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, '카카오로 시작하기'));
    await tester.pumpAndSettle();

    // 토큰이 저장되고(c1) 채팅('/')으로 전이했다.
    expect(store.saved, 'tok');
    expect(find.text('CHAT'), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('code 획득 실패 → 로그인 화면 유지·SnackBar 안내(앱 안 죽음)', (tester) async {
    final store = _FakeTokenStore();
    await tester.pumpWidget(_app(
      requester: _FakeRequester(
        exception: const OAuthCodeException('소셜 로그인 코드 획득이 아직 준비되지 않았어요.'),
      ),
      api: _FakeAuthApi('tok'),
      store: store,
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, '카카오로 시작하기'));
    await tester.pump(); // microtask: requestCode throws → catch → SnackBar 예약
    await tester.pump(const Duration(milliseconds: 750)); // SnackBar 슬라이드 인

    // 화면에 머물고, 안내가 뜨고, 토큰은 저장되지 않았다.
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.text('CHAT'), findsNothing);
    expect(find.text('소셜 로그인 코드 획득이 아직 준비되지 않았어요.'), findsOneWidget);
    expect(store.saved, isNull);
  });
}
