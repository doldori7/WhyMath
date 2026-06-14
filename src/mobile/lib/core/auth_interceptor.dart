// dio 인증 인터셉터 — 저장된 액세스 토큰을 모든 코어 API 요청에 Bearer로 첨부. OAuth-b.
//
// 경계(CLAUDE.md): 클라는 토큰을 *운반*만 한다(발급·검증은 서버 L5). 토큰이 없으면 헤더를
// 붙이지 않는다(미인증 요청은 서버가 401로 처리). 401 자동 클리어·리프레시는 후속 슬라이스.
import 'package:dio/dio.dart';

import 'token_store.dart';

/// 저장된 액세스 토큰을 요청 헤더(Authorization: Bearer)에 첨부하는 dio 인터셉터.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._store);

  final TokenStore _store;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _store.readAccessToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}
