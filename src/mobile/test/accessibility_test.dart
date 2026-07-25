// 접근성 회귀 게이트 — 탭 타깃(48dp)·라벨·텍스트 대비(4.5:1) guideline. MOB-13.
//
// 로컬 flutter 없어 시각 검증 불가 → CI(flutter test)가 유일 게이트. 구조적으로 통과가
// 보장되는 단순 화면(explore/home/me)부터 얹는다. 복잡·경계선 화면(chat·ocr·scene)은
// 색 보정 후 후속.
//
// ⚠️ 대비 테스트는 반드시 *실제 테마*(`WhyMathTheme.light`/`.dark`)로 pump한다 — 기본
// `ThemeData`로 pump하면 앱 색(indigo seed·error=앰버)이 아닌 엉뚱한 팔레트를 검증해
// 거짓 통과가 난다. login은 네이버 브랜드색(초록 배경+흰 글자·≈2.3:1·WCAG AA 미달)이
// 사업자 규정색 예외(`brand_colors.dart`)라 대비 테스트에서 제외한다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/explore/presentation/explore_screen.dart';
import 'package:korean_math_app/features/home/presentation/home_screen.dart';
import 'package:korean_math_app/features/profile/presentation/me_screen.dart';
import 'package:korean_math_app/theme/app_theme.dart';

/// 화면을 *실제 테마*로 감싸 pump한다(대비 검증이 앱 색으로 이뤄지도록).
Widget _wrap(Widget screen, Brightness brightness) {
  return ProviderScope(
    child: MaterialApp(
      theme: brightness == Brightness.light
          ? WhyMathTheme.light
          : WhyMathTheme.dark,
      home: screen,
    ),
  );
}

/// 3대 guideline을 검사한다(대비는 옵션 — 브랜드 예외 화면 제외용).
Future<void> _expectAccessible(
  WidgetTester tester, {
  bool contrast = true,
}) async {
  final handle = tester.ensureSemantics();
  await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  if (contrast) {
    await expectLater(tester, meetsGuideline(textContrastGuideline));
  }
  handle.dispose();
}

void main() {
  for (final brightness in <Brightness>[Brightness.light, Brightness.dark]) {
    final mode = brightness == Brightness.light ? '라이트' : '다크';

    testWidgets('ExploreScreen 접근성($mode): 탭타깃·라벨·대비', (tester) async {
      await tester.pumpWidget(_wrap(const ExploreScreen(), brightness));
      await _expectAccessible(tester);
    });

    testWidgets('HomeScreen 접근성($mode): 탭타깃·라벨·대비', (tester) async {
      await tester.pumpWidget(_wrap(const HomeScreen(), brightness));
      await _expectAccessible(tester);
    });
  }

  // MeScreen — 기본(미인증) 상태: 플레이스홀더 타일(비탭) + 라벨. 라이트만.
  testWidgets('MeScreen 접근성(라이트): 탭타깃·라벨·대비', (tester) async {
    await tester.pumpWidget(_wrap(const MeScreen(), Brightness.light));
    await _expectAccessible(tester);
  });
}
