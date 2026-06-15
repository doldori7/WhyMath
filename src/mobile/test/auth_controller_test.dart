// AuthController 단위테스트 — code 교환→토큰 저장→상태·로그아웃. OAuth-c1.
//
// 네트워크·플랫폼 채널 없이: fake AuthApi + fake TokenStore를 provider override로 주입한다
// (chat_controller_test 패턴). 토큰 발급·저장의 *배선*만 검증 — 수학·인증 결정은 서버.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/application/auth_controller.dart';
import 'package:korean_math_app/features/auth/data/auth_api.dart';

class _FakeAuthApi extends AuthApi {
  _FakeAuthApi({this.token, this.shouldThrow = false}) : super(Dio());

  final String? token;
  final bool shouldThrow;

  @override
  Future<String> login({
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
    return token!;
  }
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
  Future<String?> readAccessToken() async =>
      throw Exception('보안 저장소 오류(테스트)');

  @override
  Future<void> saveAccessToken(String token) async {}

  @override
  Future<void> clear() async {}
}

ProviderContainer _container(AuthApi api, TokenStore store) {
  final container = ProviderContainer(
    overrides: [
      authApiProvider.overrideWithValue(api),
      tokenStoreProvider.overrideWithValue(store),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('completeLogin 성공 → 토큰 저장 + isAuthenticated', () async {
    final store = _FakeTokenStore();
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container
        .read(authControllerProvider.notifier)
        .completeLogin(provider: 'kakao', code: 'c', redirectUri: 'r');
    final state = container.read(authControllerProvider);
    expect(store.saved, 'tok');
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

  test('logout → tokenStore.clear + isAuthenticated=false', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).logout();
    expect(store.cleared, isTrue);
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
    final container =
        _container(_FakeAuthApi(token: 'tok'), _ThrowingTokenStore());
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });
}
