// 위젯 스모크 테스트 — 앱이 빌드·렌더되고 ProviderScope가 정상 동작하는지 확인.
//
// 메인 홈은 채팅 화면([ChatScreen])이다. 빈 상태에서 앱바 타이틀·슬로건이 보이는지 확인한다
// (네트워크 호출 없는 정적 렌더만 — 전송·코치 응답은 chat_screen_test에서 fake로 검증).
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';

void main() {
  testWidgets('WhyMathApp이 채팅 홈과 슬로건을 렌더한다', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WhyMathApp()));

    // 앱바 타이틀과 슬로건이 보인다.
    expect(find.text('WhyMath'), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
  });
}
