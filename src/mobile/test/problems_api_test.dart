// ProblemsApi 단위테스트 — 진단(CAT)→문제제시 배선 검증 + answer 비노출 안전 앵커. S1.
//
// 네트워크 없이: canned 응답 HttpClientAdapter로 경로·메서드·역직렬화를 검증한다(user_api_test
// 어댑터 패턴). 출제·진단 로직은 서버 — 클라는 구조 그대로 수신할 뿐이다.
//
// ⚠️ 핵심 안전 테스트: 백엔드 GET /v1/problems/{id}가 answer를 실어 보내도 클라 Problem 모델에
// 진입하지 않음을 회귀 앵커로 못박는다(problem_models.dart 안전 주석·CLAUDE.md 절대금기).
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';

/// 경로별 canned JSON을 돌려주는 어댑터 — 마지막 요청도 캡처한다.
class _Adapter implements HttpClientAdapter {
  _Adapter(this._bodyForPath);

  final Map<String, dynamic> Function(String path) _bodyForPath;
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    final body = _bodyForPath(options.path);
    return ResponseBody.fromString(
      jsonEncode(body['__list__'] ?? body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

ProblemsApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return ProblemsApi(dio);
}

void main() {
  test('getNextProblem: /v1/me/next-problem을 GET하고 응답을 역직렬화한다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        'problem_id': 'abc',
        'theta': 0.42,
        'difficulty': 3.0,
        'standard_error': 0.25,
        'measurement_sufficient': true,
      },
    );
    final api = _apiWith(adapter);

    final res = await api.getNextProblem();

    expect(adapter.captured!.path, '/v1/me/next-problem');
    expect(adapter.captured!.method, 'GET');
    expect(res.problemId, 'abc');
    expect(res.theta, 0.42);
    expect(res.difficulty, 3.0);
    expect(res.measurementSufficient, isTrue);
  });

  test('getNextProblem: 후보 없음(problem_id null)도 안전히 파싱한다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        'problem_id': null,
        'theta': 0.0,
        'measurement_sufficient': false,
      },
    );
    final res = await _apiWith(adapter).getNextProblem();
    expect(res.problemId, isNull);
    expect(res.theta, 0.0);
  });

  test('getNextProblem: prioritizeWeakConcepts=true면 쿼리 파라미터가 붙는다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{'theta': 0.0, 'measurement_sufficient': false},
    );
    await _apiWith(adapter).getNextProblem(prioritizeWeakConcepts: true);
    expect(
      adapter.captured!.queryParameters['prioritize_weak_concepts'],
      true,
    );
  });

  test('getProblem: /v1/problems/{id}를 GET하고 발문·맥락을 역직렬화한다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        'problem_id': 'p1',
        'source_type': '자체생성',
        'subject': '미적분',
        'subunit': '합성함수의 미분',
        'unit_codes': <String>['CAL-DIFF-COMP'],
        'question_text': '다음을 미분하시오.',
        'choices': <String>['1', '2', '3'],
      },
    );
    final api = _apiWith(adapter);

    final p = await api.getProblem('p1');

    expect(adapter.captured!.path, '/v1/problems/p1');
    expect(adapter.captured!.method, 'GET');
    expect(p.problemId, 'p1');
    expect(p.subject, '미적분');
    expect(p.subunit, '합성함수의 미분');
    expect(p.unitCodes, <String>['CAL-DIFF-COMP']);
    expect(p.questionText, '다음을 미분하시오.');
    expect(p.choices, <String>['1', '2', '3']);
  });

  test('안전 앵커: 백엔드가 answer를 보내도 클라 Problem 모델에 진입하지 않는다', () async {
    // 백엔드 GET problem은 answer/answer_explanation을 그대로 반환한다(response_model_exclude 없음).
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        'problem_id': 'p1',
        'source_type': '자체생성',
        'subject': '미적분',
        'unit_codes': <String>['CAL'],
        'question_text': '문제 발문',
        // ↓ 노출 금지 필드 — 클라 모델이 선언하지 않아 무시되어야 한다.
        'answer': '정답은 42',
        'answer_explanation': '왜냐하면 …',
        'answer_constraint': <String, dynamic>{'min': 1, 'max': 999},
        'multiple_answers': <String, dynamic>{'a': '1'},
      },
    );

    final p = await _apiWith(adapter).getProblem('p1');

    // 재직렬화(toJson)에 정답 계열 키가 하나도 없어야 한다(구조적 차단 증명).
    final round = p.toJson();
    expect(round.containsKey('answer'), isFalse);
    expect(round.containsKey('answer_explanation'), isFalse);
    expect(round.containsKey('answer_constraint'), isFalse);
    expect(round.containsKey('multiple_answers'), isFalse);
    // 정답 문자열이 직렬화 어디에도 없다.
    expect(jsonEncode(round).contains('정답은 42'), isFalse);
    // 발문·맥락은 정상 보존된다.
    expect(p.questionText, '문제 발문');
  });

  test('getDiagnosisConcepts: 리스트를 역직렬화하고 limit 쿼리를 싣는다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        '__list__': <dynamic>[
          <String, dynamic>{
            'concept_id': 'c1',
            'concept_name': '극한',
            'response_count': 4,
            'agreement': 'agree',
            'coaching': <String, dynamic>{
              'focus': 'verify',
              'rationale': '검산 필요',
              'prompt': '각 단계를 다시 확인해 볼까요?',
              'socratic_category': 'check',
            },
          },
        ],
      },
    );
    final api = _apiWith(adapter);

    final items = await api.getDiagnosisConcepts(limit: 20);

    expect(adapter.captured!.path, '/v1/me/diagnosis/concepts');
    expect(adapter.captured!.queryParameters['limit'], 20);
    expect(items, hasLength(1));
    expect(items.first.conceptId, 'c1');
    expect(items.first.coaching.focus, 'verify');
  });
}
