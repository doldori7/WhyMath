// 액세스 토큰 영속 — flutter_secure_storage 래퍼(OS 보안 저장소). OAuth-b.
//
// 경계(CLAUDE.md): 미성년자 민감정보·토큰은 평문 저장 금지 — OS 보안 저장소(iOS Keychain·
// Android EncryptedSharedPreferences)에 둔다. 토큰은 클라가 *운반*만 하고 발급·검증은 서버(L5).
// 테스트 가능성을 위해 추상 인터페이스(TokenStore)로 감싸고, 플랫폼 채널을 타는 실 구현
// (SecureTokenStore)은 통합/수동 검증·소비자(인터셉터 등)는 fake TokenStore로 단위 테스트한다.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// 액세스 토큰 저장소 경계 — 읽기·쓰기·삭제(로그아웃).
abstract interface class TokenStore {
  /// 저장된 액세스 토큰(없으면 null).
  Future<String?> readAccessToken();

  /// 액세스 토큰 저장(로그인 성공 시).
  Future<void> saveAccessToken(String token);

  /// 토큰 삭제(로그아웃·만료).
  Future<void> clear();
}

/// 리프레시 토큰 저장소 경계 — 액세스 토큰 만료 시 무중단 갱신(MOB-12)에 쓰인다.
///
/// **[TokenStore]와 별도 인터페이스인 이유**: 액세스 토큰만 다루던 기존 계약에 메서드를 더하면
/// 이미 `implements TokenStore`로 선언된 테스트 fake 7종이 전부 깨진다. 리프레시 토큰은 수명·
/// 용도(갱신 전용·서버 allowlist 대상)가 다른 별개 자산이므로 계약도 분리해 둔다 — 실 구현
/// ([SecureTokenStore])은 두 계약을 함께 만족하고, 액세스 토큰만 필요한 소비자(인터셉터의 헤더
/// 첨부 등)는 기존 계약만 알면 된다(인터페이스 분리 원칙).
///
/// 경계(CLAUDE.md): 리프레시 토큰도 *운반*만 한다 — 회전·재사용 탐지·취소 판정은 전부 서버(L5)다.
abstract interface class RefreshTokenStore {
  /// 저장된 리프레시 토큰(없으면 null).
  Future<String?> readRefreshToken();

  /// 리프레시 토큰 저장(로그인·회전 성공 시).
  Future<void> saveRefreshToken(String token);

  /// 리프레시 토큰 삭제(로그아웃·재사용 탐지로 서버가 거부했을 때).
  Future<void> clearRefreshToken();
}

/// flutter_secure_storage 기반 실 구현 — OS 보안 저장소에 토큰을 둔다.
///
/// 플랫폼 채널이라 `flutter test`에서 직접 검증 불가(통합/수동) — 소비자는 [TokenStore] fake로
/// 단위 테스트한다. 액세스·리프레시 두 토큰을 *다른 키*로 저장한다(용도·수명이 다르므로 한쪽만
/// 지우는 조작이 가능해야 한다 — 예: 갱신 실패 시 액세스만 버리고 재로그인 유도).
class SecureTokenStore implements TokenStore, RefreshTokenStore {
  const SecureTokenStore(this._storage);

  final FlutterSecureStorage _storage;

  static const _key = 'access_token';
  static const _refreshKey = 'refresh_token';

  @override
  Future<String?> readAccessToken() => _storage.read(key: _key);

  @override
  Future<void> saveAccessToken(String token) => _storage.write(key: _key, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _key);

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  @override
  Future<void> saveRefreshToken(String token) => _storage.write(key: _refreshKey, value: token);

  @override
  Future<void> clearRefreshToken() => _storage.delete(key: _refreshKey);
}

/// 앱 전역 토큰 저장소 provider — 실 구현([SecureTokenStore]) 주입.
final tokenStoreProvider = Provider<TokenStore>(
  (ref) => const SecureTokenStore(FlutterSecureStorage()),
);

/// 앱 전역 리프레시 토큰 저장소 provider — 같은 [SecureTokenStore]의 다른 계약 면(MOB-12).
///
/// `const` 생성자라 별도 provider여도 동작상 동일한 저장소를 가리킨다(OS 보안 저장소는 키 기준).
/// 테스트는 이 provider만 override해 갱신 경로를 검증하고, 액세스 토큰만 쓰는 기존 테스트는
/// [tokenStoreProvider]만 override하던 방식을 그대로 유지한다.
final refreshTokenStoreProvider = Provider<RefreshTokenStore>(
  (ref) => const SecureTokenStore(FlutterSecureStorage()),
);
