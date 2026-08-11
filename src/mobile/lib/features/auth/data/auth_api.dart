// 인증 API 클라이언트 — OAuth 콜백으로 authorization code → 액세스 토큰 교환. OAuth-c1.
//
// 경계(CLAUDE.md): 클라는 provider가 준 code를 백엔드 콜백(`POST /v1/auth/{provider}/callback`,
// OAuth-a)에 넘기고 발급된 JWT를 받는다 — 토큰 발급·사용자 식별은 전부 서버(L5)다. `coach_api`·
// `scene_api` 패턴을 따른다. 응답은 {access_token, token_type} 2필드라 모델 없이 직접 파싱한다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/token_refresh_api.dart';

/// OAuth 콜백 호출 래퍼 — code 교환으로 액세스·리프레시 토큰을 받는다.
class AuthApi {
  AuthApi(this._dio);

  final Dio _dio;

  /// `POST /v1/auth/{provider}/callback` — authorization code → 액세스+리프레시 토큰.
  ///
  /// [provider]='kakao'·'naver', [code]=provider redirect의 code, [redirectUri]=인가 요청과 동일.
  /// 응답에 두 토큰 중 하나라도 없으면 [DioException].
  ///
  /// MOB-12: 예전에는 액세스 토큰만 꺼내 쓰고 **리프레시 토큰을 버렸다**. 그래서 액세스가 만료되면
  /// 갱신할 재료가 아예 없어 학생이 재로그인 외엔 방법이 없었다(서버는 처음부터 두 토큰을 줬다).
  /// 이제 둘 다 돌려주고 호출자가 함께 저장한다.
  Future<AuthTokens> login({
    required String provider,
    required String code,
    required String redirectUri,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/$provider/callback',
      data: {'code': code, 'redirect_uri': redirectUri},
    );
    final token = response.data?['access_token'];
    if (token is! String || token.isEmpty) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '로그인 응답에 access_token이 없습니다.',
      );
    }
    final refreshToken = response.data?['refresh_token'];
    if (refreshToken is! String || refreshToken.isEmpty) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '로그인 응답에 refresh_token이 없습니다.',
      );
    }
    return AuthTokens(accessToken: token, refreshToken: refreshToken);
  }
}

/// [AuthApi] provider — 공유 [dioProvider]를 주입받는다([coachApiProvider]와 동형).
final authApiProvider = Provider<AuthApi>((ref) {
  return AuthApi(ref.watch(dioProvider));
});
