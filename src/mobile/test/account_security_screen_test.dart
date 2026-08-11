// 계정 보안(내 기기 관리) 화면 위젯 테스트 — 목록 렌더·단건/전체 로그아웃. MOB-12.
//
// 네트워크 없이: fake AuthSessionsApi를 provider override로 주입한다(me_screen·login_screen
// 테스트 패턴). 검증 대상은 **좌석 호출 배선**과 **정서 안전 톤**이다.
//
// 정서 안전 축을 테스트로 동결하는 이유: 이 화면은 "낯선 기기 경고"로 흐르기 쉬운 주제다.
// CLAUDE.md·전역 UI 불변식이 불안 조장·게임화를 금지하므로, 위협 프레이밍 단어가 화면에
// 등장하지 않는 것을 회귀 테스트로 고정한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/auth/data/auth_sessions_api.dart';
import 'package:korean_math_app/features/auth/presentation/account_security_screen.dart';
import 'package:korean_math_app/theme/app_theme.dart';

/// fake 세션 API — 호출을 캡처하고 준비된 목록을 돌려준다.
class _FakeSessionsApi extends AuthSessionsApi {
  _FakeSessionsApi({List<AuthSessionInfo>? sessions, this.shouldThrow = false})
    : sessions = sessions ?? <AuthSessionInfo>[],
      super(Dio());

  List<AuthSessionInfo> sessions;
  final bool shouldThrow;

  int listCalls = 0;
  final List<String> revokedIds = <String>[];
  int revokeAllCalls = 0;

  @override
  Future<List<AuthSessionInfo>> listSessions() async {
    listCalls++;
    if (shouldThrow) {
      throw DioException(requestOptions: RequestOptions(path: '/v1/auth/sessions'));
    }
    return sessions;
  }

  @override
  Future<void> revokeSession(String sessionId) async {
    revokedIds.add(sessionId);
    sessions = sessions.where((s) => s.sessionId != sessionId).toList();
  }

  @override
  Future<void> revokeAllSessions() async {
    revokeAllCalls++;
    sessions = <AuthSessionInfo>[];
  }
}

/// 401을 던지는 fake — 미인증 안내 분기 검증용.
class _UnauthorizedSessionsApi extends AuthSessionsApi {
  _UnauthorizedSessionsApi() : super(Dio());

  @override
  Future<List<AuthSessionInfo>> listSessions() async {
    throw DioException(
      requestOptions: RequestOptions(path: '/v1/auth/sessions'),
      response: Response<void>(
        requestOptions: RequestOptions(path: '/v1/auth/sessions'),
        statusCode: 401,
      ),
    );
  }
}

AuthSessionInfo _session(String id, {String? platform}) => AuthSessionInfo(
  sessionId: id,
  platform: platform,
  issuedAt: DateTime.utc(2026, 8, 1, 9),
  expiresAt: DateTime.utc(2026, 9, 1, 9),
);

Widget _app(AuthSessionsApi api) {
  return ProviderScope(
    overrides: [authSessionsApiProvider.overrideWithValue(api)],
    child: MaterialApp(theme: WhyMathTheme.light, home: const AccountSecurityScreen()),
  );
}

void main() {
  testWidgets('진입하면 세션 목록을 조회해 렌더한다', (tester) async {
    final api = _FakeSessionsApi(
      sessions: [
        _session('s1', platform: 'iOS'),
        _session('s2', platform: 'Android'),
      ],
    );
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    expect(api.listCalls, 1);
    expect(find.text('내 기기 관리'), findsOneWidget);
    expect(find.text('iOS'), findsOneWidget);
    expect(find.text('Android'), findsOneWidget);
    expect(find.text('2026.08.01 로그인'), findsWidgets);
  });

  testWidgets('기기 없음은 오류가 아니라 정상 안내로 표시된다', (tester) async {
    await tester.pumpWidget(_app(_FakeSessionsApi()));
    await tester.pumpAndSettle();

    expect(find.text('지금 로그인되어 있는 기기가 없어요.'), findsOneWidget);
  });

  testWidgets('platform이 없으면 "기기 정보 없음"으로 표시한다(추측하지 않음)', (tester) async {
    await tester.pumpWidget(_app(_FakeSessionsApi(sessions: [_session('s1')])));
    await tester.pumpAndSettle();

    expect(find.text('기기 정보 없음'), findsOneWidget);
  });

  testWidgets('기기별 로그아웃 → DELETE 호출 + 목록 재조회', (tester) async {
    final api = _FakeSessionsApi(
      sessions: [
        _session('s1', platform: 'iOS'),
        _session('s2', platform: 'Android'),
      ],
    );
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('로그아웃').first);
    await tester.pumpAndSettle();

    expect(api.revokedIds, ['s1']);
    // 서버 상태가 단일 권위 — 클라가 목록을 지우는 게 아니라 다시 읽어 확인한다.
    expect(api.listCalls, 2);
    expect(find.text('iOS'), findsNothing);
    expect(find.text('Android'), findsOneWidget);
  });

  testWidgets('전체 로그아웃은 확인 후에만 실행된다 — 취소하면 호출 0', (tester) async {
    final api = _FakeSessionsApi(sessions: [_session('s1', platform: 'iOS')]);
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('모든 기기에서 로그아웃'));
    await tester.pumpAndSettle();
    expect(find.text('모든 기기에서 로그아웃할까요?'), findsOneWidget);

    await tester.tap(find.text('취소'));
    await tester.pumpAndSettle();
    expect(api.revokeAllCalls, 0);
  });

  testWidgets('전체 로그아웃 확인 → DELETE /v1/auth/sessions 호출', (tester) async {
    final api = _FakeSessionsApi(sessions: [_session('s1', platform: 'iOS')]);
    await tester.pumpWidget(_app(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('모든 기기에서 로그아웃'));
    await tester.pumpAndSettle();
    // 확인 버튼은 **다이얼로그 안**으로 한정해 찾는다 — 세션 행에도 같은 라벨의 버튼이 있어
    // 범위를 좁히지 않으면 어느 것을 눌렀는지 모호해진다.
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.widgetWithText(TextButton, '로그아웃'),
      ),
    );
    await tester.pumpAndSettle();

    expect(api.revokeAllCalls, 1);
  });

  testWidgets('401이면 오류가 아니라 로그인 안내로 구분해 표시한다', (tester) async {
    await tester.pumpWidget(_app(_UnauthorizedSessionsApi()));
    await tester.pumpAndSettle();

    expect(find.text('로그인하면 내 기기 목록을 볼 수 있어요.'), findsOneWidget);
  });

  testWidgets('401 외 실패는 재시도 안내를 준다', (tester) async {
    await tester.pumpWidget(_app(_FakeSessionsApi(shouldThrow: true)));
    await tester.pumpAndSettle();

    expect(find.text('다시 시도'), findsOneWidget);
  });

  group('정서 안전 — 불안 조장·게임화 프레이밍 부재(회귀 동결)', () {
    testWidgets('위협·경고 어휘가 화면에 등장하지 않는다', (tester) async {
      final api = _FakeSessionsApi(
        sessions: [
          _session('s1', platform: 'iOS'),
          _session('s2'),
        ],
      );
      await tester.pumpWidget(_app(api));
      await tester.pumpAndSettle();

      // "낯선 기기 경고"류 프레이밍은 학생 불안을 키운다 — 통제감 있는 "관리" 톤만 쓴다.
      const forbidden = <String>['경고', '위험', '의심', '침입', '해킹', '낯선', '비정상'];
      final texts = tester.widgetList<Text>(find.byType(Text)).map((t) => t.data ?? '').join(' ');
      for (final word in forbidden) {
        expect(texts.contains(word), isFalse, reason: '"$word"는 불안 조장 어휘다');
      }
    });

    testWidgets('전체 로그아웃 문구가 즉시 차단이라고 말하지 않는다(정직 표기)', (tester) async {
      // 서버는 리프레시 세션만 취소한다 — 액세스 토큰은 만료까지 유효하다(SEC-10 한계).
      final api = _FakeSessionsApi(sessions: [_session('s1', platform: 'iOS')]);
      await tester.pumpWidget(_app(api));
      await tester.pumpAndSettle();

      expect(find.text('모든 기기가 잠시 뒤 로그아웃돼요.'), findsOneWidget);
    });
  });
}
