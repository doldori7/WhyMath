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
//
// 배율 축(A11Y-01): 밝기 축과 별개로 텍스트 배율(1.0×/1.3×/2.0×)도 곱해 돈다 — 학생이
// 시스템 글자 크기를 키워도 탭 타깃·라벨·대비 가드가 여전히 통과하는지 확인한다. 뷰포트
// 크기 등 나머지 MediaQueryData는 보존한 채 `textScaler`만 덮어쓴다(`_TextScaleOverride`).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/presentation/coach_signal_card.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';
import 'package:korean_math_app/features/explore/presentation/explore_screen.dart';
import 'package:korean_math_app/features/home/presentation/home_screen.dart';
import 'package:korean_math_app/features/profile/presentation/me_screen.dart';
import 'package:korean_math_app/theme/app_theme.dart';

/// 기존 `MediaQueryData`(뷰포트 크기·기기 픽셀비 등)는 그대로 둔 채 `textScaler`만
/// 덮어써 배율 축(A11Y-01)을 표현한다. deprecated `textScaleFactor`가 아니라 현행
/// `TextScaler`/`MediaQueryData.copyWith(textScaler: ...)`를 쓴다.
class _TextScaleOverride extends StatelessWidget {
  const _TextScaleOverride({required this.scale, required this.child});

  /// 강제할 배율(1.3·2.0 등). 1.0은 호출부에서 아예 이 위젯을 안 씀(무변경 경로 보존).
  final double scale;

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    return MediaQuery(
      data: media.copyWith(textScaler: TextScaler.linear(scale)),
      child: child,
    );
  }
}

/// 화면을 *실제 테마*로 감싸 pump한다(대비 검증이 앱 색으로 이뤄지도록).
/// [textScale]이 1.0이 아니면 배율 축(A11Y-01)을 얹는다.
Widget _wrap(Widget screen, Brightness brightness, {double textScale = 1.0}) {
  return ProviderScope(
    child: MaterialApp(
      theme: brightness == Brightness.light
          ? WhyMathTheme.light
          : WhyMathTheme.dark,
      home: textScale == 1.0 ? screen : _TextScaleOverride(scale: textScale, child: screen),
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

/// 조밀 위젯(장면·신호 카드)을 실 테마 + Scaffold surface 위에 얹어 pump한다.
/// [textScale]이 1.0이 아니면 배율 축(A11Y-01)을 얹는다.
Widget _wrapWidget(Widget child, Brightness brightness, {double textScale = 1.0}) {
  final content = textScale == 1.0 ? child : _TextScaleOverride(scale: textScale, child: child);
  return MaterialApp(
    theme: brightness == Brightness.light ? WhyMathTheme.light : WhyMathTheme.dark,
    home: Scaffold(body: Center(child: content)),
  );
}

/// 대비 위험 요소(뷰 seed·행·소크라테스 버블)를 담은 최소 장면.
LearningScene _denseScene() => LearningScene(
      sceneId: 's1',
      conceptId: 'c1',
      topicLabel: '이차함수',
      layout: 'vertical_stack',
      answerDeferralMaxLevel: 4,
      elements: const [
        SceneElement(kind: 'socratic_prompt', promptText: '어디까지 이해됐어?'),
        SceneElement(
          kind: 'visualization',
          ref: Visualization(type: 'interactive_graph_2d', caption: '포물선 개형'),
        ),
        SceneElement(kind: 'param_control', targets: ['a', 'b']),
        SceneElement(
          kind: 'skill_focus',
          behaviorArea: 'VERIFY',
          focusPrompt: '결과가 조건을 만족하는지 반례로 점검하세요.',
        ),
      ],
    );

/// 신호 행(onSurfaceVariant 소형 텍스트 on tonal 컨테이너)을 렌더하는 코치 응답.
CoachResponse _signalResponse() => CoachResponse(
      decision: const PedagogyDecision(
        polyaStageToAdvance: 'stay',
        prompt: '같이 한 번 더 살펴볼까요?',
        system: '테스트',
      ),
      solutionCoaching: SolutionCoaching(
        trigger: CoachingTrigger(
          focus: 'verify',
          rationale: '근거(테스트)',
          prompt: '어디서 확신이 줄었는지 짚어 볼까요?',
          socraticCategory: '검증',
          focusStepIndex: 2,
        ),
        arithmeticError: true,
        errorKind: 'arithmetic',
      ),
    );

void main() {
  // 배율 축(A11Y-01): 1.0×(기존 동작 그대로)·1.3×·2.0×. 시스템 글자 크기를 키운 학생도
  // 탭 타깃·라벨·대비 가드를 통과해야 한다.
  const textScales = <double>[1.0, 1.3, 2.0];

  for (final textScale in textScales) {
    final scaleLabel = '${textScale}x';

    for (final brightness in <Brightness>[Brightness.light, Brightness.dark]) {
      final mode = brightness == Brightness.light ? '라이트' : '다크';

      testWidgets('ExploreScreen 접근성($mode·배율$scaleLabel): 탭타깃·라벨·대비', (tester) async {
        await tester.pumpWidget(
          _wrap(const ExploreScreen(), brightness, textScale: textScale),
        );
        await _expectAccessible(tester);
      });

      testWidgets('HomeScreen 접근성($mode·배율$scaleLabel): 탭타깃·라벨·대비', (tester) async {
        await tester.pumpWidget(
          _wrap(const HomeScreen(), brightness, textScale: textScale),
        );
        await _expectAccessible(tester);
      });
    }

    // MeScreen — 기본(미인증) 상태: 플레이스홀더 타일(비탭) + 라벨. 라이트만.
    testWidgets('MeScreen 접근성(라이트·배율$scaleLabel): 탭타깃·라벨·대비', (tester) async {
      await tester.pumpWidget(
        _wrap(const MeScreen(), Brightness.light, textScale: textScale),
      );
      await _expectAccessible(tester);
    });

    // 조밀 위젯 — onSurfaceVariant 소형 텍스트 on tonal 컨테이너 대비를 실 테마로 검증.
    for (final brightness in <Brightness>[Brightness.light, Brightness.dark]) {
      final mode = brightness == Brightness.light ? '라이트' : '다크';

      testWidgets('SceneRenderer 접근성($mode·배율$scaleLabel): 대비·라벨', (tester) async {
        await tester.pumpWidget(
          _wrapWidget(SceneRenderer(scene: _denseScene()), brightness, textScale: textScale),
        );
        await _expectAccessible(tester);
      });

      testWidgets('CoachSignalCard 접근성($mode·배율$scaleLabel): 대비', (tester) async {
        await tester.pumpWidget(
          _wrapWidget(CoachSignalCard(response: _signalResponse()), brightness, textScale: textScale),
        );
        await _expectAccessible(tester);
      });
    }
  }
}
