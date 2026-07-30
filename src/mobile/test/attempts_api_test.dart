// AttemptsApi 단위테스트 — 채점 제출(POST /v1/me/attempts) 배선·본문·역직렬화 검증(G1·S3-09).
//
// 네트워크 없이: canned 응답 HttpClientAdapter로 경로·메서드·본문·응답 파싱을 검증한다(problems_api_test
// 어댑터 패턴). 컨트롤러 테스트는 fake를 쓰므로 실제 직렬화·경로·중립 is_correct는 여기서만 커버된다.
//
// 핵심 계약 앵커: ① 학생 최종답을 student_answer로 싣는다 ② is_correct는 **중립 false**를 보낸다
// (서버 override 전제·클라는 판정하지 않는다) ③ verification_state를 그대로 수신해 진행 판단에 쓴다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/attempts_api.dart';

/// canned JSON을 돌려주는 어댑터 — 마지막 요청도 캡처한다(201 Created).
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
      201,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

AttemptsApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return AttemptsApi(dio);
}

Map<String, dynamic> _resBody(String state, {bool isCorrect = false}) =>
    <String, dynamic>{
      'attempt_id': 'att-1',
      'is_correct': isCorrect,
      'verification_state': state,
      'mastery_updates': <dynamic>[],
      'skill_mastery_updates': <dynamic>[],
    };

void main() {
  test('submitAttempt: POST /v1/me/attempts에 최종답을 싣고 응답을 역직렬화한다', () async {
    final adapter = _Adapter(_resBody('correct', isCorrect: true));
    final api = _apiWith(adapter);

    final res =
        await api.submitAttempt(problemId: 'p-1', studentAnswer: 'x=3');

    expect(adapter.captured!.path, '/v1/me/attempts');
    expect(adapter.captured!.method, 'POST');
    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body['problem_id'], 'p-1');
    expect(body['student_answer'], 'x=3');
    // 서버 override 전제 — 클라는 판정 못 하므로 중립값 false를 보낸다.
    expect(body['is_correct'], false);
    // 응답 파싱 — 진행 판단의 유일 근거는 verification_state.
    expect(res.attemptId, 'att-1');
    expect(res.verificationState, 'correct');
    expect(res.isVerifiedCorrect, isTrue);
    expect(res.isCorrect, isTrue);
  });

  test('submitAttempt: incorrect 상태를 그대로 노출한다(진행 안 함)', () async {
    final res = await _apiWith(_Adapter(_resBody('incorrect')))
        .submitAttempt(problemId: 'p', studentAnswer: 'x=1');
    expect(res.isVerifiedIncorrect, isTrue);
    expect(res.isVerifiedCorrect, isFalse);
  });

  test('submitAttempt: unverifiable 상태를 그대로 노출한다(미검증)', () async {
    final res = await _apiWith(_Adapter(_resBody('unverifiable')))
        .submitAttempt(problemId: 'p', studentAnswer: '서술형 답');
    expect(res.isUnverifiable, isTrue);
    expect(res.isVerifiedCorrect, isFalse);
  });

  test('submitAttempt: 선택 필드가 있으면 본문에 싣고 없으면 생략한다', () async {
    final adapter = _Adapter(_resBody('correct', isCorrect: true));
    await _apiWith(adapter).submitAttempt(
      problemId: 'p',
      studentAnswer: 'x=3',
      durationSeconds: 42,
      confidenceSelfReported: 0.8,
    );
    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body['duration_seconds'], 42);
    expect(body['confidence_self_reported'], 0.8);
    // 미제공 선택 필드는 본문에 넣지 않는다(extra="forbid" 안전·불필요 키 억제).
    expect(body.containsKey('session_id'), isFalse);
  });

  test('submitAttempt: verification_state가 없으면 방어적으로 unverifiable로 낮춘다', () async {
    final res = await _apiWith(
      _Adapter(<String, dynamic>{'attempt_id': 'a', 'is_correct': false}),
    ).submitAttempt(problemId: 'p', studentAnswer: 'x=3');
    // correct를 함부로 가정하지 않는다 — 진행 오작동보다 미검증 안내가 안전·정직.
    expect(res.isUnverifiable, isTrue);
  });
}
