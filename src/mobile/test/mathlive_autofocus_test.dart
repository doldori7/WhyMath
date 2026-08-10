// 수식 입력 자동 포커스 배선 테스트 (S3-37)
//
// 무엇을 막는가: 학생이 "수식으로 풀이 입력" 화면에 들어가면 곧바로 타이핑할 수 있어야
// 하는데, 진입 후 필드를 한 번 더 탭해야 하는 마찰이 있었다. 웹 자산(index.html)에는
// `window.whymathFocus` 훅이 *이미 정의돼 있었지만 Dart 쪽 호출처가 0건*이었다 — 이
// 프로젝트가 반복해서 겪은 "선언만 되고 배선 안 됨" 패턴이다(OPS-22 계열).
//
// 왜 위젯 테스트가 아니라 계약·소스 스캔인가: WebView는 플랫폼 뷰라 헤드리스 flutter test
// 에서 컨트롤러 생성조차 불가하다(mathlive_input_screen_test·graphing_calculator_webview_test
// 가 같은 이유로 pump를 피한다). 그래서 이 파일은 자동 포커스가 성립하기 위한 *두 축*을
// 각각 동결한다 — ①웹이 훅을 제공하는가(자산 스캔) ②Dart가 그 훅을 실제로 부르는가
// (소스 스캔, cwd = src/mobile). 실기기에서의 실제 포커스 이동은 실기기 확인 몫이다.
//
// 스캔 술어(`_definesFocusHook*`·`_wiresFocusOnPageFinished`·`_optsIntoAutofocus`)는 모두
// 결함주입 테스트를 동반한다 — 배선이 빠진 소스에서 실제로 false를 내는지 확인해야 스캔이
// "항상 통과하는 위장 검사"가 아님이 보장된다(CLAUDE.md 변별력 없는 검증 스텝 금지).
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/presentation/mathlive_input_webview.dart';

/// MathLive 경로가 포커스 훅을 정의하는가 — `window.whymathFocus = () => mf.focus()`.
bool _definesFocusHookForMathfield(String html) =>
    RegExp(r'window\.whymathFocus\s*=\s*\(\)\s*=>\s*mf\.focus\(\)').hasMatch(html);

/// textarea 폴백 경로가 포커스 훅을 정의하는가 — `window.whymathFocus = () => ta.focus()`.
///
/// MathLive 로드가 실패해 강등된 상태에서도 자동 포커스가 살아 있어야 한다(폴백은 구버전
/// WebView·자산 누락 시 실제로 타는 경로다).
bool _definesFocusHookForFallback(String html) =>
    RegExp(r'window\.whymathFocus\s*=\s*\(\)\s*=>\s*ta\.focus\(\)').hasMatch(html);

/// WebView가 *페이지 로드 완료 후*에 포커스 스크립트를 부르는가.
///
/// 단순 포함이 아니라 **순서**를 본다 — `onPageFinished`보다 앞에서 부르면 index.html이
/// 아직 훅을 정의하기 전이라 조용히 아무 일도 일어나지 않는다(무증상 실패).
bool _wiresFocusOnPageFinished(String source) {
  final int onPageFinishedAt = source.indexOf('onPageFinished');
  final int focusCallAt = source.indexOf('runJavaScript(mathliveFocusScript)');
  if (onPageFinishedAt < 0 || focusCallAt < 0) return false;
  return focusCallAt > onPageFinishedAt;
}

/// 수식 입력 전용 화면이 자동 포커스를 opt-in 하는가 — `autofocus: true` 전달.
bool _optsIntoAutofocus(String source) =>
    RegExp(r'autofocus:\s*true').hasMatch(source);

void main() {
  // 테스트 실행 cwd = src/mobile (mathlive_input_asset_config_test 선례)
  final String indexHtml =
      File('assets/mathlive_input/index.html').readAsStringSync();
  final String webviewSource =
      File('lib/features/chat/presentation/mathlive_input_webview.dart')
          .readAsStringSync();
  final String screenSource =
      File('lib/features/chat/presentation/mathlive_input_screen.dart')
          .readAsStringSync();

  group('웹 계약 — index.html이 포커스 훅을 제공한다', () {
    test('MathLive 경로에 window.whymathFocus가 정의돼 있다', () {
      expect(
        _definesFocusHookForMathfield(indexHtml),
        isTrue,
        reason: 'Dart의 자동 포커스 배선이 부르는 훅이다 — 사라지면 자동 포커스가 '
            '무증상으로 죽는다(JS 쪽은 `&&` 가드라 예외도 안 난다)',
      );
    });

    test('textarea 폴백 경로에도 window.whymathFocus가 정의돼 있다', () {
      expect(
        _definesFocusHookForFallback(indexHtml),
        isTrue,
        reason: 'MathLive 로드 실패로 강등된 상태(구버전 WebView·자산 누락)에서도 '
            '자동 포커스는 동작해야 한다',
      );
    });
  });

  group('Dart 배선 — 훅을 실제로 부른다', () {
    test('포커스 스크립트는 존재 확인 가드를 포함한다', () {
      expect(mathliveFocusScript, contains('window.whymathFocus'));
      expect(
        mathliveFocusScript,
        contains('&&'),
        reason: '훅 정의 전에 onPageFinished가 먼저 도달하면 ReferenceError로 죽는다 — '
            'whymathClear 호출과 동일한 방어 패턴을 유지한다',
      );
    });

    test('WebView가 onPageFinished 이후에 포커스 스크립트를 부른다', () {
      expect(
        _wiresFocusOnPageFinished(webviewSource),
        isTrue,
        reason: '로드 완료 전에 부르면 훅이 아직 없어 조용히 무시된다(무증상 실패)',
      );
    });

    test('수식 입력 전용 화면이 autofocus: true로 opt-in 한다', () {
      expect(
        _optsIntoAutofocus(screenSource),
        isTrue,
        reason: 'autofocus 기본값은 false(인라인 임베드 보호)이므로, 전용 화면이 '
            '명시적으로 켜지 않으면 배선이 있어도 동작하지 않는다',
      );
    });

    test('autofocus 기본값은 false다 — 인라인 임베드가 키보드를 띄우지 않는다', () {
      // 위젯 생성만 한다(pump 금지 — 컨트롤러가 플랫폼 뷰를 요구한다).
      const MathliveInputWebView inline = MathliveInputWebView(onChanged: _noop);
      expect(
        inline.autofocus,
        isFalse,
        reason: '기본값이 true면 인라인 임베드에서 학생이 의도하지 않은 시점에 '
            '키보드가 떠 다른 콘텐츠를 덮는다(opt-in 계약)',
      );
    });
  });

  group('결함주입 — 스캔 술어가 변별력을 갖는다', () {
    test('훅이 없는 html은 검출된다(MathLive·폴백 각각)', () {
      const String noHooks = '<html><script>const mf = 1;</script></html>';
      expect(_definesFocusHookForMathfield(noHooks), isFalse);
      expect(_definesFocusHookForFallback(noHooks), isFalse);
    });

    test('한쪽 경로에만 훅이 있으면 나머지 한쪽은 false다', () {
      const String onlyMathfield = 'window.whymathFocus = () => mf.focus();';
      expect(_definesFocusHookForMathfield(onlyMathfield), isTrue);
      expect(
        _definesFocusHookForFallback(onlyMathfield),
        isFalse,
        reason: '두 경로를 한 술어가 뭉뚱그리면 폴백 강등 시 무증상 실패를 놓친다',
      );
    });

    test('포커스 호출이 아예 없는 소스는 검출된다', () {
      const String noCall = 'NavigationDelegate(onPageFinished: (_) {})';
      expect(_wiresFocusOnPageFinished(noCall), isFalse);
    });

    test('포커스 호출이 onPageFinished보다 *앞*이면 검출된다(순서 변별)', () {
      const String wrongOrder = '''
        _controller.runJavaScript(mathliveFocusScript);
        ..setNavigationDelegate(NavigationDelegate(onPageFinished: (_) {}))
      ''';
      expect(
        _wiresFocusOnPageFinished(wrongOrder),
        isFalse,
        reason: '순서를 보지 않으면 "로드 전 호출"이라는 실제 실패 모드를 통과시킨다',
      );
    });

    test('autofocus를 켜지 않은 화면 소스는 검출된다', () {
      const String notOptedIn = 'MathliveInputWebView(onChanged: _onLatexChanged)';
      expect(_optsIntoAutofocus(notOptedIn), isFalse);
    });

    test('autofocus: false만 있는 소스도 검출된다', () {
      const String explicitlyOff =
          'MathliveInputWebView(onChanged: _x, autofocus: false)';
      expect(_optsIntoAutofocus(explicitlyOff), isFalse);
    });
  });
}

/// 위젯 생성용 무동작 콜백(const 생성자 인자 — 톱레벨 함수여야 const가 된다).
void _noop(String _) {}
