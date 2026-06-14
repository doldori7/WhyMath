// dio AuthInterceptor 단위테스트 — 저장 토큰의 Bearer 첨부. OAuth-b.
//
// 플랫폼 채널 없이: fake TokenStore + capture HttpClientAdapter로 요청 헤더를 검증한다
// (SecureTokenStore 실 구현은 채널이라 통합/수동). 토큰 운반만 검증 — 발급·검증은 서버.
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/auth_interceptor.dart';
import 'package:korean_math_app/core/token_store.dart';

/// 인메모리 TokenStore — 플랫폼 채널 없이 인터셉터 로직을 검증한다.
class _FakeTokenStore implements TokenStore {
  _FakeTokenStore([this._token]);

  String? _token;

  @override
  Future<String?> readAccessToken() async => _token;

  @override
  Future<void> saveAccessToken(String token) async => _token = token;

  @override
  Future<void> clear() async => _token = null;
}

/// 요청을 가로채 RequestOptions를 캡처하는 가짜 어댑터(네트워크 없음).
class _CaptureAdapter implements HttpClientAdapter {
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    return ResponseBody.fromString(
      '{}',
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Dio _dioWith(TokenStore store, _CaptureAdapter adapter) {
  final dio = Dio()..httpClientAdapter = adapter;
  dio.interceptors.add(AuthInterceptor(store));
  return dio;
}

void main() {
  test('토큰이 있으면 Authorization: Bearer 헤더를 첨부한다', () async {
    final adapter = _CaptureAdapter();
    final dio = _dioWith(_FakeTokenStore('abc123'), adapter);
    await dio.get<dynamic>('http://x/y');
    expect(adapter.captured!.headers['Authorization'], 'Bearer abc123');
  });

  test('토큰이 없으면 Authorization 헤더를 붙이지 않는다(미인증 → 서버 401)', () async {
    final adapter = _CaptureAdapter();
    final dio = _dioWith(_FakeTokenStore(), adapter);
    await dio.get<dynamic>('http://x/y');
    expect(adapter.captured!.headers.containsKey('Authorization'), isFalse);
  });

  test('tokenStoreProvider는 TokenStore(SecureTokenStore)를 제공한다', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final store = container.read(tokenStoreProvider);
    expect(store, isA<TokenStore>());
    expect(store, isA<SecureTokenStore>());
  });
}
