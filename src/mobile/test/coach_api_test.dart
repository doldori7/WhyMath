// CoachApi 단위테스트 — 영속 세션 HTTP 배선(경로·problem_id 주입·중첩 파싱) 검증. S1 Slice 2.
//
// 네트워크 없이: canned 응답 HttpClientAdapter로 경로·메서드·본문·역직렬화를 검증한다(user_api_test
// 어댑터 패턴). 컨트롤러 테스트는 fake를 쓰므로 실제 직렬화·경로는 여기서만 커버된다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';

/// 경로에 따라 canned JSON을 돌려주는 어댑터 — 마지막 요청도 캡처한다.
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
    return ResponseBody.fromString(
      jsonEncode(_bodyForPath(options.path)),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

CoachApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return CoachApi(dio);
}

Map<String, dynamic> _decisionJson() => <String, dynamic>{
      'decision': <String, dynamic>{
        'polya_stage_to_advance': 'stay',
        'prompt': '무엇이 주어졌나요?',
        'system': 's',
        'socratic_category': '조건확인',
      },
    };

void main() {
  test('createSession: POST /v1/coach/sessions에 problem_id를 실어 보내고 dialogue_id를 돌려준다',
      () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        ..._decisionJson(),
        'dialogue_id': 'd-1',
        'student_turn_id': 's-1',
        'assistant_turn_id': 'a-1',
        'wh1_turn_index': 1,
        'wh1_exploration_turn': false,
      },
    );
    final api = _apiWith(adapter);

    final result = await api.createSession(
      const CoachRequest(studentInput: '도와주세요'),
      problemId: 'prob-7',
    );

    expect(adapter.captured!.path, '/v1/coach/sessions');
    expect(adapter.captured!.method, 'POST');
    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body['student_input'], '도와주세요');
    expect(body['problem_id'], 'prob-7'); // 세션이 문제에 묶인다.
    expect(result.dialogueId, 'd-1');
    expect(result.response.decision.prompt, '무엇이 주어졌나요?');
    expect(result.wh1TurnIndex, 1);
  });

  test('createSession: problem_id가 없으면 본문에 키를 넣지 않는다(자유 대화)', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{..._decisionJson(), 'dialogue_id': 'd-2'},
    );
    await _apiWith(adapter).createSession(const CoachRequest(studentInput: 'x'));

    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body.containsKey('problem_id'), isFalse);
  });

  test('addTurn: POST /v1/coach/sessions/{id}/turns로 잇고 dialogue_id를 보존한다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        ..._decisionJson(),
        'student_turn_id': 's-2',
        'assistant_turn_id': 'a-2',
        'student_turn_order': 3,
        'assistant_turn_order': 4,
        'wh1_turn_index': 2,
        'wh1_exploration_turn': false,
      },
    );
    final api = _apiWith(adapter);

    final result = await api.addTurn(
      'd-1',
      const CoachRequest(studentInput: '다음 단계요'),
    );

    expect(adapter.captured!.path, '/v1/coach/sessions/d-1/turns');
    expect(adapter.captured!.method, 'POST');
    expect(result.dialogueId, 'd-1'); // URL의 dialogue_id를 그대로 싣는다.
    expect(result.wh1TurnIndex, 2);
  });

  test('getSession: GET하고 중첩 {dialogue, turns}를 풀어 스냅샷으로 옮긴다', () async {
    final adapter = _Adapter(
      (_) => <String, dynamic>{
        'dialogue': <String, dynamic>{
          'dialogue_id': 'd-1',
          'total_turns': 6,
        },
        'turns': <dynamic>[
          <String, dynamic>{
            'turn_order': 1,
            'role': 'student',
            'content': '질문1',
          },
          <String, dynamic>{
            'turn_order': 2,
            'role': 'assistant',
            'content': '발문1',
          },
        ],
      },
    );
    final api = _apiWith(adapter);

    final snap = await api.getSession('d-1');

    expect(adapter.captured!.path, '/v1/coach/sessions/d-1');
    expect(adapter.captured!.method, 'GET');
    expect(snap.dialogueId, 'd-1');
    expect(snap.totalTurns, 6);
    expect(snap.turns, hasLength(2));
    expect(snap.turns.first.turnOrder, 1);
    expect(snap.turns.first.role, 'student');
    expect(snap.turns[1].content, '발문1');
  });
}
