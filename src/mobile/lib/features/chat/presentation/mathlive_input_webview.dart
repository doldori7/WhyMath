// MathliveInputWebView — vendored MathLive(assets/mathlive_input)를 WebView로 임베드한 수식 입력기.
//
// 경계(슬89 표현≠의미·국소 비상구): 학생이 입력한 수식을 LaTeX 문자열로 *그대로* Flutter에 흘릴
// 뿐, 수학 판정·검증은 하지 않는다(백엔드 L3 verify가 검증). MathLive는 수식 입력의 국소 예외
// (자족 비상구)로, Flutter는 자산 번들(assets/mathlive_input/)을 오프라인 로드한다.
//
// 통신: 웹은 `WhymathMathInput` JS 채널로 LaTeX 변경을 push하고, Flutter는 `window.whymathClear()`·
// `window.whymathSetLatex(v)`를 runJavaScript로 호출한다(단방향 상태 + 명령 훅). MathLive 로드 실패
// 시 웹이 textarea로 폴백하므로 입력 자체는 끊기지 않는다(HTML 참조).
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

/// 웹이 보낸 LaTeX 입력 메시지를 정규화한다(순수·Flutter/WebView 무관 — 단위 테스트 대상).
///
/// 앞뒤 공백을 제거한다. 공백뿐이거나 빈 문자열이면 빈 문자열을 돌려준다(전송 판정은 호출자).
/// 수학 의미 추론·치환은 하지 않는다(LaTeX 원문 보존·검증은 백엔드).
String normalizeLatexInput(String raw) => raw.trim();

/// MathLive 수식 입력 WebView — 입력 변경을 [onChanged]로 콜백한다.
///
/// 플랫폼 뷰라 헤드리스 flutter test에서 렌더 불가 — 위젯 테스트는 pump하지 않고 순수
/// [normalizeLatexInput]만 검증한다(graphing_calculator_webview_test 선례). 화면 통합은 후속.
class MathliveInputWebView extends StatefulWidget {
  const MathliveInputWebView({
    required this.onChanged,
    this.height = 120,
    super.key,
  });

  /// 입력된 LaTeX(정규화 후)를 흘리는 콜백. 빈 문자열도 전달한다(호출자가 전송 여부 판정).
  final ValueChanged<String> onChanged;

  /// 인라인 표시 높이(px).
  final double height;

  @override
  State<MathliveInputWebView> createState() => MathliveInputWebViewState();
}

/// [MathliveInputWebView] 상태 — 외부에서 [clear]를 호출해 입력을 비울 수 있다(전송 후).
class MathliveInputWebViewState extends State<MathliveInputWebView> {
  late final WebViewController _controller;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      // 웹이 LaTeX 변경을 push하는 인바운드 채널 — 정규화해 콜백으로 흘린다.
      ..addJavaScriptChannel(
        'WhymathMathInput',
        onMessageReceived: (JavaScriptMessage message) {
          widget.onChanged(normalizeLatexInput(message.message));
        },
      )
      ..loadFlutterAsset('assets/mathlive_input/index.html');
  }

  /// 입력을 비운다(전송 후 초기화) — 웹의 `whymathClear` 훅을 호출한다.
  Future<void> clear() async {
    await _controller.runJavaScript('window.whymathClear && window.whymathClear()');
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        height: widget.height,
        width: double.infinity,
        child: WebViewWidget(controller: _controller),
      ),
    );
  }
}
