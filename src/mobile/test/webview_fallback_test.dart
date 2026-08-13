// MOB-19 WebView 생명주기 폴백 테스트 — 강등 판정(순수 함수)과 폴백/로딩 외형(공개 위젯)을 동결한다.
//
// WebView 본체(플랫폼 뷰)는 헤드리스 flutter test에서 pump할 수 없다(graphing_calculator_webview_
// test.dart 선례). 그래서 두 WebView(그래프 계산기·MathLive 입력기)가 공유하는 ①강등 판정 함수와
// ②폴백 타일·로딩 커버 위젯을 여기서 검증한다 — 본체는 이 둘을 조립할 뿐이라, 이 계약이 깨지면
// 저사양 단말에서 빈 화면이 나가는 회귀다.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/presentation/webview_fallback.dart';

void main() {
  group('shouldDemoteWebViewOnError — 주 프레임 실패만 강등', () {
    test('주 프레임 실패(isForMainFrame: true)는 강등한다', () {
      expect(shouldDemoteWebViewOnError(isForMainFrame: true), isTrue);
    });

    test('하위 자원 실패(false)는 강등하지 않는다 — 폰트·chunk 실패로 페이지는 안 죽는다', () {
      expect(shouldDemoteWebViewOnError(isForMainFrame: false), isFalse);
    });

    test('플랫폼 미보고(null)는 강등 쪽으로 닫는다 — vendored 자산 통째 실패를 놓치지 않기 위해', () {
      expect(shouldDemoteWebViewOnError(isForMainFrame: null), isTrue);
    });
  });

  group('WebViewFallbackTile — 강등 시 학생에게 보이는 정적 타일', () {
    Widget wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

    testWidgets('라벨 문구를 렌더하고 Semantics 라벨로도 읽는다(A11Y-01 선례)', (tester) async {
      await tester.pumpWidget(wrap(const WebViewFallbackTile(
        icon: Icons.insights_outlined,
        label: '그래프를 불러오지 못했어요',
        height: 320,
      )));
      expect(find.text('그래프를 불러오지 못했어요'), findsOneWidget);
      expect(find.byIcon(Icons.insights_outlined), findsOneWidget);
      // 접근성 계약은 "Semantics 라벨 부착" 자체다(A11Y-01: 부착 1줄, 제거 시 red) — 시맨틱
      // 트리 병합 규칙은 플랫폼·버전에 따라 갈리므로 위젯 속성으로 직접 단언한다. 타일 내부에
      // Semantics가 여러 개 생성되므로(Icon·Text 내부 래핑) 최상위 하나(.first)를 본다.
      final semantics = tester.widget<Semantics>(
        find
            .descendant(
              of: find.byType(WebViewFallbackTile),
              matching: find.byType(Semantics),
            )
            .first,
      );
      expect(semantics.properties.label, '그래프를 불러오지 못했어요');
    });

    testWidgets('WebView가 차지했을 높이를 유지한다(강등해도 스크롤 점프 없음)', (tester) async {
      await tester.pumpWidget(wrap(const WebViewFallbackTile(
        icon: Icons.insights_outlined,
        label: '캡션',
        height: 320,
      )));
      expect(tester.getSize(find.byType(WebViewFallbackTile)).height, 320);
    });

    testWidgets('정서 안전 — error 롤(빨강)을 쓰지 않고 중립 surface 색으로 그린다', (tester) async {
      await tester.pumpWidget(wrap(const WebViewFallbackTile(
        icon: Icons.edit_note_outlined,
        label: '수식 입력 도구를 불러오지 못했어요',
      )));
      final context = tester.element(find.byType(WebViewFallbackTile));
      final theme = Theme.of(context);
      final container = tester.widget<Container>(
        find.descendant(
          of: find.byType(WebViewFallbackTile),
          matching: find.byType(Container),
        ),
      );
      final decoration = container.decoration! as BoxDecoration;
      // 강등이 "실패 경고"로 읽히면 안 된다 — 배경은 error 롤이 아니라 중립 surface다.
      expect(decoration.color, theme.colorScheme.surfaceContainerHighest);
      expect(decoration.color, isNot(theme.colorScheme.error));
      expect(decoration.color, isNot(theme.colorScheme.errorContainer));
    });
  });

  group('WebViewLoadingCover — 로드 완료 전 빈 화면 차단', () {
    testWidgets('인디케이터를 얹고 배경은 폴백과 같은 중립 surface다(전환 시 색 불연속 없음)',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: WebViewLoadingCover())),
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      final context = tester.element(find.byType(WebViewLoadingCover));
      final container = tester.widget<Container>(find.byType(Container));
      expect(container.color, Theme.of(context).colorScheme.surfaceContainerHighest);
    });
  });
}
