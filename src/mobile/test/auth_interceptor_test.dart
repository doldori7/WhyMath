// dio AuthInterceptor 단위테스트 — 저장 토큰의 Bearer 첨부 + 401 처리(MOB-15). OAuth-b.
//
// 플랫폼 채널 없이: fake TokenStore + capture HttpClientAdapter로 요청 헤더를 검증한다
// (SecureTokenStore 실 구현은 채널이라 통합/수동). 토큰 운반만 검증 — 발급·검증은 서버.
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/api_client.dart';
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

/// 지정한 상태코드로 응답하는 가짜 어댑터(네트워크 없음) — 401 등 에러 응답 시나리오용.
///
/// dio는 4xx/5xx를 [DioException]으로 변환해 인터셉터의 `onError`로 넘긴다(기본
/// `validateStatus`가 2xx만 통과) — 이 어댑터는 그 변환이 일어나도록 상태코드만 그대로 낸다.
class _StatusAdapter implements HttpClientAdapter {
  _StatusAdapter(this.statusCode);

  final int statusCode;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      '{}',
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Dio _dioWithStatus(
  TokenStore store,
  _StatusAdapter adapter, {
  Future<void> Function()? onUnauthorized,
}) {
  final dio = Dio()..httpClientAdapter = adapter;
  dio.interceptors.add(AuthInterceptor(store, onUnauthorized: onUnauthorized));
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

  group('401 처리(MOB-15) — 만료·무효 토큰을 즉시 정리한다', () {
    test('401 응답 시 토큰을 클리어하고 onUnauthorized 콜백을 정확히 1회 호출한다', () async {
      final store = _FakeTokenStore('expired-token');
      var callCount = 0;
      final dio = _dioWithStatus(
        store,
        _StatusAdapter(401),
        onUnauthorized: () async {
          callCount++;
        },
      );

      await expectLater(dio.get<dynamic>('http://x/y'), throwsA(isA<DioException>()));

      expect(await store.readAccessToken(), isNull,
          reason: '401은 서버가 토큰을 거부했다는 뜻 — 클라도 즉시 미인증 상태로 맞춰야 한다');
      expect(callCount, 1,
          reason: '재로그인 유도 콜백이 정확히 1회 호출돼야 한다(중복 호출·누락 둘 다 오탐)');
    });

    test('200(정상) 응답에서는 onUnauthorized가 호출되지 않는다(오탐 방지)', () async {
      final store = _FakeTokenStore('valid-token');
      var called = false;
      final adapter = _CaptureAdapter();
      final dio = Dio()..httpClientAdapter = adapter;
      dio.interceptors.add(
        AuthInterceptor(store, onUnauthorized: () async => called = true),
      );

      await dio.get<dynamic>('http://x/y');

      expect(called, isFalse);
      expect(await store.readAccessToken(), 'valid-token',
          reason: '정상 응답 경로는 완전히 그대로여야 한다 — 토큰이 지워지면 안 된다');
    });

    test('onUnauthorized 미주입(null)이어도 401을 크래시 없이 처리한다(토큰 클리어는 그대로 일어남)', () async {
      final store = _FakeTokenStore('expired-token');
      final dio = _dioWithStatus(store, _StatusAdapter(401));

      await expectLater(dio.get<dynamic>('http://x/y'), throwsA(isA<DioException>()));

      expect(await store.readAccessToken(), isNull);
    });

    test('401이 아닌 에러(500)에서는 토큰을 클리어하지 않는다', () async {
      final store = _FakeTokenStore('valid-token');
      var called = false;
      final dio = _dioWithStatus(
        store,
        _StatusAdapter(500),
        onUnauthorized: () async => called = true,
      );

      await expectLater(dio.get<dynamic>('http://x/y'), throwsA(isA<DioException>()));

      expect(called, isFalse,
          reason: '토큰 문제가 아닌 서버 오류까지 로그아웃시키면 정상 세션을 부당하게 끊는다');
      expect(await store.readAccessToken(), 'valid-token');
    });
  });

  test('dioProvider의 BaseOptions에 sendTimeout이 설정돼 있다(MOB-15 — OCR 업로드 무한대기 방지)', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final dio = container.read(dioProvider);
    expect(dio.options.sendTimeout, isNotNull);
    expect(dio.options.sendTimeout, const Duration(seconds: 30));
  });
}
