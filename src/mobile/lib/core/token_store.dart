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

/// flutter_secure_storage 기반 실 구현 — OS 보안 저장소에 토큰을 둔다.
///
/// 플랫폼 채널이라 `flutter test`에서 직접 검증 불가(통합/수동) — 소비자는 [TokenStore] fake로
/// 단위 테스트한다.
class SecureTokenStore implements TokenStore {
  const SecureTokenStore(this._storage);

  final FlutterSecureStorage _storage;

  static const _key = 'access_token';

  @override
  Future<String?> readAccessToken() => _storage.read(key: _key);

  @override
  Future<void> saveAccessToken(String token) => _storage.write(key: _key, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _key);
}

/// 앱 전역 토큰 저장소 provider — 실 구현([SecureTokenStore]) 주입.
final tokenStoreProvider = Provider<TokenStore>(
  (ref) => const SecureTokenStore(FlutterSecureStorage()),
);
