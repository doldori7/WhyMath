// 위젯 스모크 테스트 — 앱이 빌드·렌더되고 ProviderScope가 정상 동작하는지 확인.
//
// flutter test가 의미 있게 동작하는 최소 위젯 테스트(후속 슬라이스에서 화면별 테스트 확장).
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';

void main() {
  testWidgets('WhyMathApp이 홈 화면과 슬로건을 렌더한다', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WhyMathApp()));

    // 앱바 타이틀과 슬로건이 보인다.
    expect(find.text('WhyMath'), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
  });
}
