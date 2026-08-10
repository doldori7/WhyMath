// AuthSessionsApi 단위테스트 — 내 기기 목록·단건/전체 로그아웃 호출. MOB-12.
//
// 네트워크 없이: capture HttpClientAdapter(canned 응답)로 **경로·메서드·파싱**을 검증한다
// (auth_api_test 어댑터 패턴). 세션 유효성·소유 판정은 서버 — 클라는 호출과 표시만 한다.
//
// 이 파일이 증명하는 것은 "그 좌석을 실제로 부른다"이다 — OPS-22 실측에서 이 3개 라우트의
// 모바일 호출이 0건이었고, 그래서 학생은 기기를 분실해도 세션을 끊을 방법이 없었다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/auth/data/auth_sessions_api.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter({Map<String, dynamic>? body, this.statusCode = 200}) : _body = body;

  final Map<String, dynamic>? _body;
  final int statusCode;
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    if (_body == null) {
      // 204 No Content — 취소 계열 응답(본문 없음).
      return ResponseBody.fromString('', statusCode);
    }
    return ResponseBody.fromString(
      jsonEncode(_body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

AuthSessionsApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return AuthSessionsApi(dio);
}

Map<String, dynamic> _session(String id, {String? platform}) => {
  'session_id': id,
  'platform': platform,
  'issued_at': '2026-08-01T09:00:00Z',
  'expires_at': '2026-09-01T09:00:00Z',
};

void main() {
  group('listSessions — GET /v1/auth/sessions', () {
    test('세션 목록을 파싱하고 서버 순서를 보존한다', () async {
      final adapter = _Adapter(
        body: {
          'sessions': [_session('s1', platform: 'iOS'), _session('s2', platform: 'Android')],
        },
      );
      final sessions = await _apiWith(adapter).listSessions();

      expect(adapter.captured!.path, '/v1/auth/sessions');
      expect(adapter.captured!.method, 'GET');
      // 서버가 발급 시각 내림차순으로 준 순서를 클라가 다시 정렬하지 않는다(단일 권위).
      expect(sessions.map((s) => s.sessionId), ['s1', 's2']);
      expect(sessions.first.platform, 'iOS');
      expect(sessions.first.issuedAt.toUtc().year, 2026);
    });

    test('platform이 null이면 null로 보존한다(임의 기본값 채우지 않음)', () async {
      final sessions = await _apiWith(
        _Adapter(
          body: {
            'sessions': [_session('s1')],
          },
        ),
      ).listSessions();
      expect(sessions.single.platform, isNull);
    });

    test('빈 목록도 정상 응답이다(오류 아님)', () async {
      final sessions = await _apiWith(_Adapter(body: {'sessions': <dynamic>[]})).listSessions();
      expect(sessions, isEmpty);
    });

    test('sessions 키가 없으면 DioException(조용히 빈 목록으로 위장 금지)', () async {
      await expectLater(
        _apiWith(_Adapter(body: {'unexpected': 1})).listSessions(),
        throwsA(isA<DioException>()),
      );
    });
  });

  group('revoke — DELETE 계열', () {
    test('revokeAllSessions는 DELETE /v1/auth/sessions를 부른다', () async {
      final adapter = _Adapter(statusCode: 204);
      await _apiWith(adapter).revokeAllSessions();
      expect(adapter.captured!.path, '/v1/auth/sessions');
      expect(adapter.captured!.method, 'DELETE');
    });

    test('revokeSession은 세션 id를 경로에 실어 DELETE한다', () async {
      final adapter = _Adapter(statusCode: 204);
      await _apiWith(adapter).revokeSession('abc-123');
      expect(adapter.captured!.path, '/v1/auth/sessions/abc-123');
      expect(adapter.captured!.method, 'DELETE');
    });
  });

  group('AuthSessionInfo.fromJson — 형식 방어', () {
    test('필수 필드 누락이면 FormatException', () {
      expect(() => AuthSessionInfo.fromJson({'session_id': 's1'}), throwsA(isA<FormatException>()));
    });
  });
}
