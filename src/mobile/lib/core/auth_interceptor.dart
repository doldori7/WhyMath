// dio 인증 인터셉터 — 저장된 액세스 토큰을 모든 코어 API 요청에 Bearer로 첨부. OAuth-b.
//
// 경계(CLAUDE.md): 클라는 토큰을 *운반*만 한다(발급·검증은 서버 L5). 토큰이 없으면 헤더를
// 붙이지 않는다(미인증 요청은 서버가 401로 처리). 401 자동 클리어·재로그인 유도는 이
// 인터셉터가 배선(MOB-15). 리프레시(재발급)는 여전히 후속.
import 'package:dio/dio.dart';

import 'token_store.dart';

/// 저장된 액세스 토큰을 요청 헤더(Authorization: Bearer)에 첨부하고, 서버가 401로 거부하면
/// 즉시 로컬 토큰을 지우는 dio 인터셉터.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._store, {Future<void> Function()? onUnauthorized})
      : _onUnauthorized = onUnauthorized;

  final TokenStore _store;

  /// 401 수신 시 호출되는 콜백(선택) — 인증 상태를 미인증으로 되돌리는 등 상위 정리를 수행.
  ///
  /// nullable + 기본 null: `TokenStore`만 넘겨 인터셉터를 만드는 기존 테스트 관례를 깨지
  /// 않기 위함(생성자 하위호환). Riverpod `Ref`를 이 낮은 계층에 직접 넣지 않고 콜백으로
  /// 주입받아 프레임워크 결합을 최소화하고 테스트하기 쉽게 유지한다.
  final Future<void> Function()? _onUnauthorized;

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

  /// 서버가 토큰을 거부하면(401) 클라도 즉시 같은 상태(미인증)로 맞춘다 — 만료·무효 토큰을
  /// 계속 들고 있으면 이후 모든 요청이 조용히 401만 반복한다(학생 입장에선 "아무것도 안 되는"
  /// 무증상 실패). 401이 아닌 에러(500 등)는 토큰 문제가 아니므로 손대지 않는다.
  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode == 401) {
      await _store.clear();
      await _onUnauthorized?.call();
    }
    handler.next(err);
  }
}
