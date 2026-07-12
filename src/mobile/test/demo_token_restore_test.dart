// DEMO_TOKEN 시연 인증 경로 단위테스트(S1 실기기 시연 게이트 ①) — restore()의 시연 분기.
//
// `AuthController.restore()`는 `demoTokenProvider`(기본 Env.demoToken)를 seam으로 읽는다. 여기선
// dart-define 없이 provider override로 시연 토큰을 주입해, 주입 시 저장소에 심고 인증하는 계약과
// 미주입(빈 값) 시 시연 분기가 미실행되는 계약을 검증한다(auth_controller_test 패턴·fake 저장소).
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/application/auth_controller.dart';

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

ProviderContainer _container(TokenStore store, {String demoToken = ''}) {
  final container = ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(store),
      demoTokenProvider.overrideWithValue(demoToken),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('restore: DEMO_TOKEN 주입 → 저장소에 심고 isAuthenticated', () async {
    final store = _FakeTokenStore();
    final container = _container(store, demoToken: 'demo-jwt-xyz');
    await container.read(authControllerProvider.notifier).restore();
    // 시연 토큰이 저장소에 심어져 인터셉터가 Bearer로 첨부할 수 있고, 인증 상태로 부팅한다.
    expect(store.saved, 'demo-jwt-xyz');
    expect(container.read(authControllerProvider).isAuthenticated, isTrue);
  });

  test('restore: DEMO_TOKEN 주입은 저장소 기존 토큰보다 우선', () async {
    // 저장소가 비어 있어도(신규 기기) 시연 토큰만으로 인증됨을 확인(시연 분기 우선).
    final store = _FakeTokenStore();
    final container = _container(store, demoToken: 'demo-only');
    await container.read(authControllerProvider.notifier).restore();
    expect(store.saved, 'demo-only');
    expect(container.read(authControllerProvider).isAuthenticated, isTrue);
  });

  test('restore: DEMO_TOKEN 미주입(빈 값) → 시연 분기 미실행(기존 저장소 경로)', () async {
    // prod 빌드 계약: demoToken 빈 값 → 저장소에 쓰지 않고, 저장된 토큰이 없으면 미인증.
    final store = _FakeTokenStore();
    final container = _container(store); // demoToken 기본 ''
    await container.read(authControllerProvider.notifier).restore();
    expect(store.saved, isNull); // 시연 분기가 저장소에 쓰지 않음.
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });
}
