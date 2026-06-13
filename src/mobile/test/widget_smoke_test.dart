// 위젯 스모크 테스트 — 앱이 빌드·렌더되고 go_router 셸·ProviderScope가 정상 동작하는지 확인.
//
// 첫 진입은 온보딩([OnboardingScreen])이다(라우터 initialLocation=/onboarding). 온보딩
// 안내가 보이는지, "건너뛰기"로 채팅 홈(슬로건)에 도달하는지 정적 렌더만 확인한다
// (네트워크 호출 없음 — 전송·코치 응답은 chat_screen_test에서 fake로 검증).
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';

void main() {
  testWidgets('WhyMathApp이 온보딩으로 시작하고 채팅 홈으로 넘어간다', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WhyMathApp()));
    await tester.pumpAndSettle();

    // 첫 진입은 온보딩 — 메타인지 철학 안내(첫 페이지 제목)가 보인다.
    expect(find.text('답이 아닌, 이유를 묻습니다'), findsOneWidget);

    // "건너뛰기"로 채팅 홈에 진입하면 앱바 타이틀·슬로건이 보인다.
    await tester.tap(find.text('건너뛰기'));
    await tester.pumpAndSettle();

    expect(find.text('WhyMath'), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
  });
}
