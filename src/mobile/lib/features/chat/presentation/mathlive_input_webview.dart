// MathliveInputWebView — vendored MathLive(assets/mathlive_input)를 WebView로 임베드한 수식 입력기.
//
// 경계(슬89 표현≠의미·국소 비상구): 학생이 입력한 수식을 LaTeX 문자열로 *그대로* Flutter에 흘릴
// 뿐, 수학 판정·검증은 하지 않는다(백엔드 L3 verify가 검증). MathLive는 수식 입력의 국소 예외
// (자족 비상구)로, Flutter는 자산 번들(assets/mathlive_input/)을 오프라인 로드한다.
//
// 통신: 웹은 `WhymathMathInput` JS 채널로 LaTeX 변경을 push하고, Flutter는 `window.whymathClear()`·
// `window.whymathSetLatex(v)`·`window.whymathFocus()`를 runJavaScript로 호출한다(단방향 상태 +
// 명령 훅). MathLive 로드 실패 시 웹이 textarea로 폴백하므로 입력 자체는 끊기지 않는다(HTML 참조).
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

/// 웹이 보낸 LaTeX 입력 메시지를 정규화한다(순수·Flutter/WebView 무관 — 단위 테스트 대상).
///
/// 앞뒤 공백을 제거한다. 공백뿐이거나 빈 문자열이면 빈 문자열을 돌려준다(전송 판정은 호출자).
/// 수학 의미 추론·치환은 하지 않는다(LaTeX 원문 보존·검증은 백엔드).
String normalizeLatexInput(String raw) => raw.trim();

/// 웹의 포커스 훅을 부르는 JS — 자동 포커스(S3-37→S3-50) 배선의 유일한 호출 문자열.
///
/// 훅은 index.html이 MathLive 경로(`mf.focus()` + 가상 키보드 `show()`)와 textarea 폴백
/// 경로(`ta.focus()`) *양쪽*에 정의한다 — MathLive가 로드 실패해 강등돼도 자동 포커스는
/// 그대로 동작한다. 호출 시점은 `WhymathMathReady` 신호 수신 직후(훅 정의 완료가 보장됨 —
/// S3-50)지만, `&&` 존재 가드는 방어적으로 유지한다(`whymathClear` 호출과 동일 패턴).
/// 포커스는 코스메틱이라 실패해도 입력 자체는 탭 한 번으로 정상 진행된다.
const String mathliveFocusScript = 'window.whymathFocus && window.whymathFocus()';

/// MathLive 수식 입력 WebView — 입력 변경을 [onChanged]로 콜백한다.
///
/// 플랫폼 뷰라 헤드리스 flutter test에서 렌더 불가 — 위젯 테스트는 pump하지 않고 순수
/// [normalizeLatexInput]만 검증한다(graphing_calculator_webview_test 선례). 화면 통합은 후속.
class MathliveInputWebView extends StatefulWidget {
  const MathliveInputWebView({
    required this.onChanged,
    this.height,
    this.autofocus = false,
    super.key,
  });

  /// 입력된 LaTeX(정규화 후)를 흘리는 콜백. 빈 문자열도 전달한다(호출자가 전송 여부 판정).
  final ValueChanged<String> onChanged;

  /// 웹 훅 준비 완료(WhymathMathReady) 시 입력 필드에 자동으로 포커스를 줄지 (S3-37→S3-50).
  ///
  /// 수식 입력 *전용 화면*(MathliveInputScreen)처럼 "진입했다 = 지금 입력하려는 것"이 확실한
  /// 자리에서만 true로 준다 — 학생이 화면에 들어와서 필드를 한 번 더 탭해야 하는 마찰을 없앤다.
  /// 인라인 임베드(`height` 지정)에서 true면 학생이 의도하지 않은 시점에 키보드가 떠 다른
  /// 콘텐츠를 덮으므로 **기본값은 false**다(opt-in).
  final bool autofocus;

  /// 인라인 표시 높이(px). null이면 부모 제약을 그대로 채운다(전체 높이 배치용).
  ///
  /// MathLive 가상 키보드는 *WebView 자체 뷰포트*의 하단에 도킹한다(웹 번들 실측 —
  /// index.html 주석 참조). 키보드 자연 높이(약 300 CSS px)보다 낮은 고정 높이를 주면
  /// 키보드 상단이 잘리고 필드를 덮으므로, 키보드를 쓰는 화면은 null(Expanded 배치)로 쓴다.
  final double? height;

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
      // 자동 포커스(S3-50·원 S3-19) — 웹이 명령 훅 정의를 *마친 뒤* 보내는 WhymathMathReady
      // 신호에서 훅을 부른다. S3-37이 쓰던 onPageFinished는 이 자산에선 타이밍이 틀렸다:
      // index.html의 모듈 스크립트는 top-level await로 비동기 실행되므로 페이지 로드 완료
      // 시점엔 whymathFocus가 아직 미정의일 수 있고, && 가드 때문에 *무증상 no-op*이 된다
      // (헤드리스 테스트로는 못 잡는 실기기 전용 실패 — fa08081 원본 대조로 발견).
      // ready 신호는 MathLive 경로·textarea 폴백 경로 양쪽에서 온다(자산 계약 테스트가 동결).
      ..addJavaScriptChannel(
        'WhymathMathReady',
        onMessageReceived: (JavaScriptMessage message) {
          if (widget.autofocus) {
            _controller.runJavaScript(mathliveFocusScript);
          }
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
    // height가 null이면 SizedBox는 높이 제약을 추가하지 않는다 — 부모(Expanded 등)가
    // 준 제약을 WebView가 그대로 채운다(가상 키보드 하단 도킹 공간 확보).
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
