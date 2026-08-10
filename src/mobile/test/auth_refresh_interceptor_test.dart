// AuthInterceptor 자동 갱신 테스트 — 401 → refresh → 원요청 재시도. MOB-12.
//
// 플랫폼 채널·네트워크 없이: fake 저장소 + fake TokenRefreshApi + capture HttpClientAdapter로
// **무중단 갱신 배선**을 검증한다(auth_interceptor_test 어댑터 패턴의 확장).
//
// 왜 이 테스트가 중요한가: 액세스 토큰은 짧게 만료되는데 갱신 배선이 없어서, 만료 순간 학생은
// 아무 예고 없이 모든 화면이 실패했다(`POST /v1/auth/refresh` 서버 좌석 완비·모바일 호출 0건 —
// OPS-22 실측). 여기서 검증하는 것은 그 만료가 **학생 눈에 보이지 않게** 처리되는가다.
import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/auth_interceptor.dart';
import 'package:korean_math_app/core/token_refresh_api.dart';
import 'package:korean_math_app/core/token_store.dart';

/// 인메모리 액세스 토큰 저장소.
class _FakeTokenStore implements TokenStore {
  _FakeTokenStore([this._token]);

  String? _token;
  bool cleared = false;

  @override
  Future<String?> readAccessToken() async => _token;

  @override
  Future<void> saveAccessToken(String token) async => _token = token;

  @override
  Future<void> clear() async {
    _token = null;
    cleared = true;
  }
}

/// 인메모리 리프레시 토큰 저장소.
class _FakeRefreshStore implements RefreshTokenStore {
  _FakeRefreshStore([this.token]);

  String? token;
  bool cleared = false;

  @override
  Future<String?> readRefreshToken() async => token;

  @override
  Future<void> saveRefreshToken(String value) async => token = value;

  @override
  Future<void> clearRefreshToken() async {
    token = null;
    cleared = true;
  }
}

/// 갱신 호출을 세고 회전 토큰을 돌려주는 fake(또는 실패를 던지는 fake).
///
/// [gate]를 주면 갱신이 그 Completer가 완료될 때까지 *멈춘다* — 두 요청의 갱신 구간을 확실히
/// 겹치게 만들어 단일 비행(single-flight) 검증을 타이밍에 의존하지 않게 한다.
class _FakeRefreshApi extends TokenRefreshApi {
  _FakeRefreshApi({this.shouldThrow = false, this.gate}) : super(Dio());

  final bool shouldThrow;
  final Completer<void>? gate;
  int calls = 0;

  @override
  Future<AuthTokens> refresh(String refreshToken) async {
    calls++;
    if (gate != null) {
      await gate!.future;
    }
    if (shouldThrow) {
      throw DioException(requestOptions: RequestOptions(path: '/v1/auth/refresh'));
    }
    return const AuthTokens(accessToken: 'new-access', refreshToken: 'new-refresh');
  }
}

/// 첫 요청은 401, 이후 요청은 200을 돌려주는 어댑터 — 만료→갱신→성공 흐름을 재현한다.
class _ExpiringAdapter implements HttpClientAdapter {
  _ExpiringAdapter({this.alwaysUnauthorized = false});

  final bool alwaysUnauthorized;
  final List<RequestOptions> requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final isFirst = requests.length == 1;
    if (alwaysUnauthorized || isFirst) {
      return ResponseBody.fromString('', 401);
    }
    return ResponseBody.fromString('', 200);
  }

  @override
  void close({bool force = false}) {}
}

/// 인증 인터셉터가 달린 Dio + 재시도용(인터셉터 없는) Dio를 **같은 어댑터**에 물린다.
Dio _dioWith(
  _ExpiringAdapter adapter, {
  required TokenStore store,
  required RefreshTokenStore refreshStore,
  required TokenRefreshApi refreshApi,
}) {
  final retryDio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))
    ..httpClientAdapter = adapter
    ..interceptors.add(
      AuthInterceptor(
        store,
        refreshApi: refreshApi,
        refreshStore: refreshStore,
        retryDio: retryDio,
      ),
    );
  return dio;
}

void main() {
  group('401 → 갱신 → 재시도(무중단)', () {
    test('만료된 액세스 토큰이면 갱신 후 원요청을 재시도해 성공한다', () async {
      final store = _FakeTokenStore('old-access');
      final refreshStore = _FakeRefreshStore('old-refresh');
      final refreshApi = _FakeRefreshApi();
      final adapter = _ExpiringAdapter();
      final dio = _dioWith(
        adapter,
        store: store,
        refreshStore: refreshStore,
        refreshApi: refreshApi,
      );

      final response = await dio.get<void>('/v1/me/sessions');

      // 학생 눈에는 성공 한 번으로 보인다 — 401이 표면화되지 않는다.
      expect(response.statusCode, 200);
      expect(refreshApi.calls, 1);
      // 회전된 두 토큰이 모두 저장돼야 한다(옛 리프레시를 남기면 재사용 탐지에 걸린다).
      expect(await store.readAccessToken(), 'new-access');
      expect(refreshStore.token, 'new-refresh');
      // 원요청 + 재시도 = 2회, 재시도는 새 토큰을 달고 나간다.
      expect(adapter.requests.length, 2);
      expect(adapter.requests.last.headers['Authorization'], 'Bearer new-access');
    });

    test('재시도가 다시 401이면 더는 갱신하지 않는다(무한 루프 차단)', () async {
      final refreshApi = _FakeRefreshApi();
      final adapter = _ExpiringAdapter(alwaysUnauthorized: true);
      final dio = _dioWith(
        adapter,
        store: _FakeTokenStore('old-access'),
        refreshStore: _FakeRefreshStore('old-refresh'),
        refreshApi: refreshApi,
      );

      await expectLater(dio.get<void>('/v1/me/sessions'), throwsA(isA<DioException>()));
      // 갱신은 정확히 1회 — 재시도 표식이 2차 갱신을 막는다.
      expect(refreshApi.calls, 1);
      expect(adapter.requests.length, 2);
    });

    test('동시 401 여러 건이 갱신을 1회만 발사한다(리프레시 토큰은 1회용)', () async {
      // 갱신을 gate로 붙잡아 두 요청의 갱신 구간이 **확실히 겹치게** 만든다(타이밍 비의존).
      final gate = Completer<void>();
      final refreshApi = _FakeRefreshApi(gate: gate);
      final adapter = _ExpiringAdapter(alwaysUnauthorized: true);
      final dio = _dioWith(
        adapter,
        store: _FakeTokenStore('old-access'),
        refreshStore: _FakeRefreshStore('old-refresh'),
        refreshApi: refreshApi,
      );

      // 동시 회전은 서버 재사용 탐지에 걸려 전체 세션이 취소된다 — 반드시 묶여야 한다.
      final pending = Future.wait([
        dio
            .get<void>('/a')
            .catchError((Object _) => Response<void>(requestOptions: RequestOptions(path: '/a'))),
        dio
            .get<void>('/b')
            .catchError((Object _) => Response<void>(requestOptions: RequestOptions(path: '/b'))),
      ]);

      // 갱신 구간 진입까지 기다린다(요청→401→인터셉터 체인은 여러 마이크로태스크가 걸린다).
      // gate가 닫혀 있으므로 진입한 갱신은 여기서 멈춰 있다 — 그 상태에서 호출 수를 센다.
      for (var i = 0; i < 100 && refreshApi.calls == 0; i++) {
        await Future<void>.delayed(Duration.zero);
      }
      // 두 요청 모두 401 처리에 도달할 여유를 더 준 뒤 확인한다(겹침 보장).
      for (var i = 0; i < 50; i++) {
        await Future<void>.delayed(Duration.zero);
      }
      expect(refreshApi.calls, 1, reason: '겹친 갱신은 하나의 비행으로 묶여야 한다');

      gate.complete();
      await pending;
      expect(refreshApi.calls, 1);
    });
  });

  group('갱신 불가 상황 — 정직한 실패', () {
    test('리프레시 토큰이 없으면 갱신을 시도하지 않고 401을 그대로 올린다', () async {
      final refreshApi = _FakeRefreshApi();
      final adapter = _ExpiringAdapter(alwaysUnauthorized: true);
      final dio = _dioWith(
        adapter,
        store: _FakeTokenStore('old-access'),
        refreshStore: _FakeRefreshStore(), // 저장된 리프레시 토큰 없음
        refreshApi: refreshApi,
      );

      await expectLater(dio.get<void>('/v1/me/sessions'), throwsA(isA<DioException>()));
      // 저장된 리프레시 토큰이 없으면 서버를 부르지도 않는다(헛된 왕복 0).
      expect(refreshApi.calls, 0);
      expect(adapter.requests.length, 1); // 재시도 없음
    });

    test('갱신 자체가 실패하면 저장분을 비우고 원래 401을 올린다', () async {
      final store = _FakeTokenStore('old-access');
      final refreshStore = _FakeRefreshStore('old-refresh');
      final adapter = _ExpiringAdapter(alwaysUnauthorized: true);
      final dio = _dioWith(
        adapter,
        store: store,
        refreshStore: refreshStore,
        refreshApi: _FakeRefreshApi(shouldThrow: true),
      );

      await expectLater(dio.get<void>('/v1/me/sessions'), throwsA(isA<DioException>()));
      // 다음 요청이 헛된 갱신을 반복하지 않도록 폐기한다(재로그인으로 수렴).
      expect(store.cleared, isTrue);
      expect(refreshStore.cleared, isTrue);
    });

    test('갱신 의존이 주입되지 않으면 기존 동작(헤더 첨부만) 그대로다', () async {
      // 후방호환 — 액세스 토큰만 다루던 기존 소비자·테스트가 깨지지 않아야 한다.
      final adapter = _ExpiringAdapter(alwaysUnauthorized: true);
      final dio = Dio(BaseOptions(baseUrl: 'http://x'))
        ..httpClientAdapter = adapter
        ..interceptors.add(AuthInterceptor(_FakeTokenStore('tok')));

      await expectLater(dio.get<void>('/v1/me/sessions'), throwsA(isA<DioException>()));
      expect(adapter.requests.length, 1);
      expect(adapter.requests.single.headers['Authorization'], 'Bearer tok');
    });
  });

  group('401이 아닌 오류', () {
    test('500은 갱신을 유발하지 않는다', () async {
      final refreshApi = _FakeRefreshApi();
      final adapter = _ServerErrorAdapter();
      final retryDio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
      final dio = Dio(BaseOptions(baseUrl: 'http://x'))
        ..httpClientAdapter = adapter
        ..interceptors.add(
          AuthInterceptor(
            _FakeTokenStore('tok'),
            refreshApi: refreshApi,
            refreshStore: _FakeRefreshStore('ref'),
            retryDio: retryDio,
          ),
        );

      await expectLater(dio.get<void>('/v1/me/sessions'), throwsA(isA<DioException>()));
      expect(refreshApi.calls, 0);
    });
  });
}

/// 항상 500을 돌려주는 어댑터 — 401 외 오류가 갱신을 유발하지 않는지 검증용.
class _ServerErrorAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async => ResponseBody.fromString('', 500);

  @override
  void close({bool force = false}) {}
}
