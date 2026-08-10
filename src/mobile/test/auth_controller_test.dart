// AuthController 단위테스트 — code 교환→토큰 저장→상태·로그아웃. OAuth-c1.
//
// 네트워크·플랫폼 채널 없이: fake AuthApi + fake TokenStore를 provider override로 주입한다
// (chat_controller_test 패턴). 토큰 발급·저장의 *배선*만 검증 — 수학·인증 결정은 서버.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/api_client.dart';
import 'package:korean_math_app/core/token_refresh_api.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/application/auth_controller.dart';
import 'package:korean_math_app/features/auth/data/auth_api.dart';

class _FakeAuthApi extends AuthApi {
  _FakeAuthApi({this.token, this.shouldThrow = false}) : super(Dio());

  final String? token;
  final bool shouldThrow;

  @override
  Future<AuthTokens> login({
    required String provider,
    required String code,
    required String redirectUri,
  }) async {
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/auth/$provider/callback'),
        error: '네트워크 실패(테스트)',
      );
    }
    // MOB-12: 서버는 액세스+리프레시 두 토큰을 함께 준다.
    return AuthTokens(accessToken: token!, refreshToken: 'refresh-$token');
  }
}

/// 인메모리 리프레시 토큰 저장소(MOB-12) — 플랫폼 채널 회피.
class _FakeRefreshTokenStore implements RefreshTokenStore {
  String? saved;
  bool cleared = false;

  @override
  Future<String?> readRefreshToken() async => saved;

  @override
  Future<void> saveRefreshToken(String token) async => saved = token;

  @override
  Future<void> clearRefreshToken() async {
    saved = null;
    cleared = true;
  }
}

/// 서버 로그아웃 호출을 캡처하는 fake — 실제 HTTP 없이 배선만 검증한다.
class _FakeTokenRefreshApi extends TokenRefreshApi {
  _FakeTokenRefreshApi() : super(Dio());

  final List<String> loggedOut = <String>[];

  @override
  Future<void> logout(String refreshToken) async => loggedOut.add(refreshToken);
}

/// 서버 로그아웃이 실패하는 fake — 오프라인 상황의 로컬 정리 보장을 검증한다.
class _ThrowingTokenRefreshApi extends TokenRefreshApi {
  _ThrowingTokenRefreshApi() : super(Dio());

  @override
  Future<void> logout(String refreshToken) async =>
      throw DioException(requestOptions: RequestOptions(path: '/v1/auth/logout'));
}

class _FakeTokenStore implements TokenStore {
  String? saved;
  bool cleared = false;

  @override
  Future<String?> readAccessToken() async => saved;

  @override
  Future<void> saveAccessToken(String token) async => saved = token;

  @override
  Future<void> clear() async {
    saved = null;
    cleared = true;
  }
}

/// 읽기에서 오류를 던지는 TokenStore — restore()의 방어적 처리(앱 안 죽음)를 검증한다.
class _ThrowingTokenStore implements TokenStore {
  @override
  Future<String?> readAccessToken() async => throw Exception('보안 저장소 오류(테스트)');

  @override
  Future<void> saveAccessToken(String token) async {}

  @override
  Future<void> clear() async {}
}

ProviderContainer _container(
  AuthApi api,
  TokenStore store, {
  RefreshTokenStore? refreshStore,
  TokenRefreshApi? refreshApi,
}) {
  final container = ProviderContainer(
    overrides: [
      authApiProvider.overrideWithValue(api),
      tokenStoreProvider.overrideWithValue(store),
      // MOB-12: 리프레시 토큰 저장·서버 로그아웃 호출도 fake로 — 실 구현은 플랫폼 채널/HTTP다.
      refreshTokenStoreProvider.overrideWithValue(refreshStore ?? _FakeRefreshTokenStore()),
      tokenRefreshApiProvider.overrideWithValue(refreshApi ?? _FakeTokenRefreshApi()),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('completeLogin 성공 → 액세스+리프레시 저장 + isAuthenticated', () async {
    final store = _FakeTokenStore();
    final refreshStore = _FakeRefreshTokenStore();
    final container = _container(_FakeAuthApi(token: 'tok'), store, refreshStore: refreshStore);
    await container
        .read(authControllerProvider.notifier)
        .completeLogin(provider: 'kakao', code: 'c', redirectUri: 'r');
    final state = container.read(authControllerProvider);
    expect(store.saved, 'tok');
    // MOB-12: 리프레시 토큰을 버리지 않고 저장해야 이후 무중단 갱신이 가능하다.
    expect(refreshStore.saved, 'refresh-tok');
    expect(state.isAuthenticated, isTrue);
    expect(state.isSubmitting, isFalse);
    expect(state.error, isNull);
  });

  test('completeLogin 실패 → error·미저장·미인증(앱 안 죽음)', () async {
    final store = _FakeTokenStore();
    final container = _container(_FakeAuthApi(shouldThrow: true), store);
    await container
        .read(authControllerProvider.notifier)
        .completeLogin(provider: 'kakao', code: 'c', redirectUri: 'r');
    final state = container.read(authControllerProvider);
    expect(store.saved, isNull);
    expect(state.error, isNotNull);
    expect(state.isAuthenticated, isFalse);
    expect(state.isSubmitting, isFalse);
  });

  test('logout → 서버 세션 취소 + 두 저장소 정리 + isAuthenticated=false', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final refreshStore = _FakeRefreshTokenStore()..saved = 'refresh-tok';
    final refreshApi = _FakeTokenRefreshApi();
    final container = _container(
      _FakeAuthApi(token: 'tok'),
      store,
      refreshStore: refreshStore,
      refreshApi: refreshApi,
    );
    await container.read(authControllerProvider.notifier).logout();
    // MOB-12: 로컬만 지우면 서버 리프레시 세션이 살아남아 재발급이 가능했다 — 서버도 끊는다.
    expect(refreshApi.loggedOut, ['refresh-tok']);
    expect(store.cleared, isTrue);
    expect(refreshStore.cleared, isTrue);
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('logout: 서버 호출 실패해도 로컬 정리·미인증은 반드시 수행된다', () async {
    // 오프라인 등으로 서버 취소가 실패해도 "로그아웃 눌렀는데 로그인 상태"가 되면 안 된다.
    final store = _FakeTokenStore()..saved = 'tok';
    final refreshStore = _FakeRefreshTokenStore()..saved = 'refresh-tok';
    final container = _container(
      _FakeAuthApi(token: 'tok'),
      store,
      refreshStore: refreshStore,
      refreshApi: _ThrowingTokenRefreshApi(),
    );
    await container.read(authControllerProvider.notifier).logout();
    expect(store.cleared, isTrue);
    expect(refreshStore.cleared, isTrue);
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('restore: 저장된 토큰 있으면 → isAuthenticated', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isTrue);
  });

  test('restore: 토큰 없으면(null) → 미인증', () async {
    final container = _container(_FakeAuthApi(token: 'tok'), _FakeTokenStore());
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('restore: 빈 문자열 토큰 → 미인증', () async {
    final store = _FakeTokenStore()..saved = '';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('restore: 저장소 오류 → 미인증·예외 없음(앱 안 죽음)', () async {
    final container = _container(_FakeAuthApi(token: 'tok'), _ThrowingTokenStore());
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });
}
