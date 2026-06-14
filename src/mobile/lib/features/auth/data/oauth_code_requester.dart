// OAuth authorization code 획득 경계 — provider 인가 → redirect 인터셉트로 code 취득. OAuth-c2.
//
// 경계(CLAUDE.md): 실제 코드 획득(provider 인가 화면·redirect 인터셉트)은 webview/네이티브라
// CI/로컬 검증 불가 → 주입 가능한 *seam*으로 둔다. 실 webview 구현은 후속(OAuth-c3)이고, 여기선
// placeholder가 명확한 미구현 오류를 던진다. 로그인 화면은 이 seam에서 code를 받아 AuthController
// (OAuth-c1)로 토큰을 교환한다 — code 획득과 토큰 교환을 분리해 후자를 검증 가능하게 한다.
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// provider redirect에서 얻은 authorization code + redirect_uri(토큰 교환 입력).
class OAuthCodeRequest {
  const OAuthCodeRequest({required this.code, required this.redirectUri});

  final String code;
  final String redirectUri;
}

/// 코드 획득 실패·취소(사용자 취소·webview 오류·미구현). 로그인 화면이 잡아 안내한다.
class OAuthCodeException implements Exception {
  const OAuthCodeException(this.message);

  final String message;

  @override
  String toString() => 'OAuthCodeException: $message';
}

/// provider 인가 흐름을 띄워 authorization code를 받아 오는 경계.
abstract interface class OAuthCodeRequester {
  /// [provider]('kakao'·'naver') 인가 화면을 띄우고 redirect에서 code를 얻는다.
  Future<OAuthCodeRequest> requestCode(String provider);
}

/// 미구현 placeholder — 실 webview/딥링크 코드 획득은 OAuth-c3. 호출 시 명확한 오류.
class UnsupportedOAuthCodeRequester implements OAuthCodeRequester {
  const UnsupportedOAuthCodeRequester();

  @override
  Future<OAuthCodeRequest> requestCode(String provider) async {
    throw const OAuthCodeException(
      '소셜 로그인 코드 획득(webview)이 아직 준비되지 않았어요 (OAuth-c3).',
    );
  }
}

/// 코드 획득 경계 provider — 실 구현은 OAuth-c3에서 교체(테스트는 fake override).
final oauthCodeRequesterProvider = Provider<OAuthCodeRequester>(
  (ref) => const UnsupportedOAuthCodeRequester(),
);
