// InteractionLogger 단위테스트 — 디바운스 + POST /v1/interactions. 슬라이스 96-F.
//
// 네트워크 없이: capture HttpClientAdapter로 전송 경로·합침(디바운스)을 검증한다(auth_api_test
// 어댑터 패턴). 짧은 디바운스(10ms) 주입 + 실타이머 대기로 신규 의존성 없이 검증한다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/interaction_logger.dart';

class _CaptureAdapter implements HttpClientAdapter {
  final List<Map<String, dynamic>> posted = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    // 실제 직렬화된 요청 본문(JSON)을 디코드해 캡처(Dio 내부 동작에 비의존).
    final bytes = <int>[];
    if (requestStream != null) {
      await for (final chunk in requestStream) {
        bytes.addAll(chunk);
      }
    }
    final body = utf8.decode(bytes);
    posted.add({
      'path': options.path,
      'data': body.isEmpty ? null : jsonDecode(body),
    });
    return ResponseBody.fromString('', 204);
  }

  @override
  void close({bool force = false}) {}
}

class _FailAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    throw DioException(requestOptions: options, error: '네트워크 실패(테스트)');
  }

  @override
  void close({bool force = false}) {}
}

InteractionLogger _loggerWith(HttpClientAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return InteractionLogger(dio, debounce: const Duration(milliseconds: 10));
}

void main() {
  test('같은 키 연속 record는 디바운스 후 마지막 값 1건만 POST한다', () async {
    final adapter = _CaptureAdapter();
    final logger = _loggerWith(adapter);

    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 1}});
    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 2}});
    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 3}});

    await Future<void>.delayed(const Duration(milliseconds: 40));

    expect(adapter.posted, hasLength(1));
    expect(adapter.posted[0]['path'], '/v1/interactions');
    expect((adapter.posted[0]['data'] as Map)['payload'], {'name': 'a', 'value': 3});
  });

  test('서로 다른 키는 각각 POST된다', () async {
    final adapter = _CaptureAdapter();
    final logger = _loggerWith(adapter);

    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 1}});
    logger.record({'type': 'surface_change', 'payload': {'expr': 'x^2'}});

    await Future<void>.delayed(const Duration(milliseconds: 40));

    expect(adapter.posted, hasLength(2));
    final types = adapter.posted.map((p) => (p['data'] as Map)['type']).toSet();
    expect(types, {'param_change', 'surface_change'});
  });

  test('네트워크 실패는 throw 없이 흡수한다', () async {
    final logger = _loggerWith(_FailAdapter());
    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 1}});
    // 디바운스 후 _flush가 예외를 흡수 — 테스트가 throw 없이 통과해야 한다.
    await Future<void>.delayed(const Duration(milliseconds: 40));
    expect(true, isTrue);
  });

  test('dispose는 대기 중 타이머를 취소해 전송하지 않는다', () async {
    final adapter = _CaptureAdapter();
    final logger = _loggerWith(adapter);
    logger.record({'type': 'param_change', 'payload': {'name': 'a', 'value': 1}});
    logger.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 40));
    expect(adapter.posted, isEmpty);
  });
}
