// VerifyApi 단위테스트 — 독립 3-tier 검증(POST /v1/verify-solution) 배선·역직렬화 검증. S1 Slice 4.
//
// 네트워크 없이: canned 응답 HttpClientAdapter로 경로·메서드·본문·역직렬화를 검증한다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/verify/data/verify_api.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter(this.body);

  final Map<String, dynamic> body;
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

VerifyApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return VerifyApi(dio);
}

void main() {
  test('verifySolution: /v1/verify-solution로 steps를 POST하고 결과를 역직렬화한다', () async {
    final adapter = _Adapter(<String, dynamic>{
      'n_transitions': 2,
      'n_correct': 1,
      'n_incorrect': 1,
      'n_unverifiable': 0,
      'unverified_ratio': 0.0,
      'first_incorrect_index': 1,
      'has_incorrect': true,
    });
    final api = _apiWith(adapter);

    final res = await api.verifySolution(<String>['x^2-4=0', '2x+3', 'x=2']);

    expect(adapter.captured!.path, '/v1/verify-solution');
    expect(adapter.captured!.method, 'POST');
    expect((adapter.captured!.data as Map<String, dynamic>)['steps'],
        <String>['x^2-4=0', '2x+3', 'x=2']);
    expect(res.hasIncorrect, isTrue);
    expect(res.firstIncorrectIndex, 1);
    expect(res.nIncorrect, 1);
  });

  test('verifySolution: step_types를 주면 본문에 함께 싣는다', () async {
    final adapter = _Adapter(<String, dynamic>{
      'n_transitions': 1,
      'n_correct': 1,
      'n_incorrect': 0,
      'n_unverifiable': 0,
      'unverified_ratio': 0.0,
      'has_incorrect': false,
    });
    await _apiWith(adapter).verifySolution(
      <String>['x=1', 'x=1'],
      stepTypes: <String?>['계산'],
    );
    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body['step_types'], <String?>['계산']);
  });
}
