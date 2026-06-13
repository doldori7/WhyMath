// 채팅 화면 위젯 테스트 — 입력·전송 후 코치 버블·소크라테스 배지·로딩/에러 렌더 검증.
//
// coachApiProvider를 fake로 override해 네트워크 없이 화면 동작을 확인한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';

/// 미리 짠 응답을 돌려주는 fake(또는 throw) — 위젯 테스트용.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  @override
  Future<CoachResponse> coach(CoachRequest request) async {
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/coach'),
        error: '네트워크 실패(테스트)',
      );
    }
    return response!;
  }
}

CoachResponse _response({
  String prompt = '먼저 무엇이 주어졌는지 정리해 볼까요?',
  String socraticCategory = '조건확인',
}) {
  return CoachResponse(
    decision: PedagogyDecision(
      polyaStageToAdvance: 'stay',
      prompt: prompt,
      system: '시스템(테스트)',
      socraticCategory: socraticCategory,
    ),
  );
}

Widget _wrap(CoachApi fake) {
  return ProviderScope(
    overrides: [coachApiProvider.overrideWithValue(fake)],
    child: const MaterialApp(home: ChatScreen()),
  );
}

void main() {
  testWidgets('슬로건과 빈 안내가 보인다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    expect(find.text('WhyMath'), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
    expect(find.text('어떤 문제를 함께 생각해 볼까요?'), findsOneWidget);
  });

  testWidgets('입력·전송 후 코치 버블과 소크라테스 배지가 렌더된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _FakeCoachApi(
          response: _response(
            prompt: '주어진 조건을 먼저 적어 볼까요?',
            socraticCategory: '조건확인',
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), '판별식이 헷갈려요');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // 학생 입력·코치 발화·배지가 모두 보인다.
    expect(find.text('판별식이 헷갈려요'), findsOneWidget);
    expect(find.text('주어진 조건을 먼저 적어 볼까요?'), findsOneWidget);
    expect(find.text('조건확인'), findsOneWidget);
  });

  testWidgets('API 실패 시 SnackBar로 에러를 알린다(앱은 유지)', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(shouldThrow: true)));

    await tester.enterText(find.byType(TextField), '도와주세요');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pump(); // 상태 갱신.
    await tester.pump(); // SnackBar 프레임.

    // 학생 발화는 남고 SnackBar(에러)가 뜬다.
    expect(find.text('도와주세요'), findsOneWidget);
    expect(find.byType(SnackBar), findsOneWidget);
  });
}
