// DefectReportApi 단위테스트 — POST /v1/reports/defects 배선 검증(RPT-01).
//
// 네트워크 없이: canned 응답 HttpClientAdapter로 경로·메서드·요청 바디를 검증한다
// (problems_api_test 어댑터 패턴 답습). 적재 로직은 서버(L1) — 클라는 카테고리 6종 +
// (있으면) problem_id만 보낸다(자유서술 없음 — v0 범위 동결).
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/reports/data/defect_report_api.dart';

/// 요청을 캡처하고 단순 확인 응답을 돌려주는 어댑터.
class _Adapter implements HttpClientAdapter {
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    return ResponseBody.fromString(
      jsonEncode(<String, dynamic>{'status': 'ok'}),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

DefectReportApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))
    ..httpClientAdapter = adapter;
  return DefectReportApi(dio);
}

void main() {
  test(
    'reportDefect: POST /v1/reports/defects에 category·problem_id를 싣는다',
    () async {
      final adapter = _Adapter();
      final api = _apiWith(adapter);

      await api.reportDefect(
        category: DefectReportCategory.formulaError,
        problemId: 'p1',
      );

      expect(adapter.captured!.path, '/v1/reports/defects');
      expect(adapter.captured!.method, 'POST');
      expect(adapter.captured!.data, <String, dynamic>{
        'category': '수식오류',
        'problem_id': 'p1',
      });
    },
  );

  test('reportDefect: problemId 생략 시 null로 보낸다(자유 대화 신고)', () async {
    final adapter = _Adapter();
    final api = _apiWith(adapter);

    await api.reportDefect(category: DefectReportCategory.other);

    expect(adapter.captured!.data['category'], '기타');
    expect(adapter.captured!.data['problem_id'], isNull);
  });

  test('DefectReportCategory: 정확히 6종이고 라벨이 계약 문자열과 일치한다', () {
    expect(DefectReportCategory.values, hasLength(6));
    expect(DefectReportCategory.values.map((c) => c.label).toList(), <String>[
      '콘텐츠오류',
      'AI응답오류',
      '수식오류',
      '오답의심',
      'UI문제',
      '기타',
    ]);
  });
}
