// AuthApi 단위테스트 — OAuth 콜백 code→토큰 교환. OAuth-c1.
//
// 네트워크 없이: capture HttpClientAdapter(canned 응답)로 콜백 경로·토큰 파싱을 검증한다
// (auth_interceptor_test 어댑터 패턴). 발급은 서버 — 클라는 토큰을 받아 쓸 뿐이다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/auth/data/auth_api.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter(this._body);

  final Map<String, dynamic> _body;
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    return ResponseBody.fromString(
      jsonEncode(_body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

AuthApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return AuthApi(dio);
}

void main() {
  test('login: 액세스+리프레시 토큰을 반환하고 콜백 경로로 POST한다', () async {
    final adapter = _Adapter({
      'access_token': 'tok',
      'refresh_token': 'ref',
      'token_type': 'bearer',
    });
    final api = _apiWith(adapter);
    final tokens = await api.login(provider: 'kakao', code: 'c', redirectUri: 'r');
    expect(tokens.accessToken, 'tok');
    // MOB-12: 예전에는 리프레시 토큰을 버렸다 — 이제 함께 돌려줘야 갱신 배선이 성립한다.
    expect(tokens.refreshToken, 'ref');
    expect(adapter.captured!.path, '/v1/auth/kakao/callback');
    expect(adapter.captured!.method, 'POST');
  });

  test('login: access_token이 없으면 DioException', () async {
    final api = _apiWith(_Adapter({'token_type': 'bearer'}));
    await expectLater(
      api.login(provider: 'kakao', code: 'c', redirectUri: 'r'),
      throwsA(isA<DioException>()),
    );
  });

  test('login: refresh_token이 없으면 DioException(MOB-12)', () async {
    // 리프레시 토큰이 빠진 응답을 조용히 통과시키면 갱신이 영구히 불가한 상태로 로그인된다.
    final api = _apiWith(_Adapter({'access_token': 'tok', 'token_type': 'bearer'}));
    await expectLater(
      api.login(provider: 'kakao', code: 'c', redirectUri: 'r'),
      throwsA(isA<DioException>()),
    );
  });
}
