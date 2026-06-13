// 온보딩·라우터 위젯 테스트 — go_router 셸의 첫 진입(온보딩)과 채팅 전이를 검증한다.
//
// 앱 첫 진입은 온보딩이다(initialLocation='/onboarding'). 페이지 넘김·"시작하기"/"건너뛰기"로
// 채팅(`/`)에 도달하는지 확인한다. 채팅 화면은 coachApiProvider를 읽으므로(컨트롤러가 주입)
// 네트워크 없이 빌드되도록 fake로 override한다(이 테스트는 네트워크 호출을 하지 않는다).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';

/// 호출되지 않는 fake — 채팅 화면이 빌드만 되도록 둔다(이 테스트는 전송하지 않음).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi() : super(Dio());

  @override
  Future<CoachResponse> coach(CoachRequest request) async {
    throw UnimplementedError('온보딩 테스트는 coach를 호출하지 않습니다.');
  }
}

Widget _app() {
  return ProviderScope(
    overrides: [coachApiProvider.overrideWithValue(_FakeCoachApi())],
    child: const WhyMathApp(),
  );
}

void main() {
  testWidgets('첫 진입은 온보딩 — 메타인지 안내가 보인다', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    // 첫 페이지(브랜드·답 미루기 안내)와 진행 버튼이 보인다. 아직 채팅은 아니다.
    expect(find.text('답이 아닌, 이유를 묻습니다'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '다음'), findsOneWidget);
    expect(find.byType(ChatScreen), findsNothing);
  });

  testWidgets('페이지를 넘기면 마지막에 "시작하기"가 나온다', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    // 페이지 1 → 2: "다음" 탭.
    await tester.tap(find.widgetWithText(FilledButton, '다음'));
    await tester.pumpAndSettle();
    expect(find.text('막혀도 괜찮아요'), findsOneWidget);

    // 페이지 2 → 3(마지막): "다음" 탭 후 "시작하기"가 나온다.
    await tester.tap(find.widgetWithText(FilledButton, '다음'));
    await tester.pumpAndSettle();
    expect(find.text('풀이를 함께 검산해요'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '시작하기'), findsOneWidget);
  });

  testWidgets('"시작하기"를 누르면 채팅 화면으로 전이한다', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    // 마지막 페이지까지 진행.
    await tester.tap(find.widgetWithText(FilledButton, '다음'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '다음'));
    await tester.pumpAndSettle();

    // "시작하기" → 채팅 화면(`/`)으로 이동.
    await tester.tap(find.widgetWithText(FilledButton, '시작하기'));
    await tester.pumpAndSettle();

    expect(find.byType(ChatScreen), findsOneWidget);
    // 채팅 화면의 슬로건 부제가 보인다(전이 성공 확인).
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
  });

  testWidgets('"건너뛰기"를 누르면 바로 채팅 화면으로 전이한다', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    // 첫 페이지의 "건너뛰기" → 채팅 화면으로 이동.
    await tester.tap(find.text('건너뛰기'));
    await tester.pumpAndSettle();

    expect(find.byType(ChatScreen), findsOneWidget);
  });
}
