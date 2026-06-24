// GraphingCalculatorWebView — vendored 웹 계산기(src/web/graphing-calculator)를 WebView로 임베드.
//
// 경계(슬89 표현≠의미·국소 비상구): 백엔드가 검증해 내려준 Visualization.spec(Graph2dSpec 구조)을
// *그대로* 웹 계산기에 주입해 렌더만 한다 — Dart 측엔 수학 로직 0. 그래프 계산기는 클라 수학 평가의
// 국소 예외(자족 비상구)로, Flutter는 자산 번들(assets/graphing_calculator/)을 오프라인 로드한다.
//
// 주입 방식: loadFlutterAsset는 쿼리스트링(?spec=)을 못 싣는다 → 페이지 로드 완료(onPageFinished) 후
// 웹이 노출한 전역 훅 window.whymathApplySpec(base64(JSON))을 runJavaScript로 호출해 명세를 넣는다.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../data/scene_models.dart';

/// Graph2dSpec(Map) → 웹 계산기 `?spec=` 호환 base64(JSON) 파라미터.
///
/// 웹의 `parseSpecParam`(atob→JSON.parse)이 그대로 소비하는 **표준 base64**(urlsafe 아님)다.
/// JSON은 compact(공백 없음) — `jsonEncode`는 기본이 compact다.
String encodeGraph2dSpecParam(Map<String, dynamic> spec) =>
    base64.encode(utf8.encode(jsonEncode(spec)));

/// 웹이 보낸 상호작용 메시지(JSON)를 디코드한다(학습 로그 인바운드).
///
/// 웹 `emitInteraction`이 `WhymathInteraction` JS 채널로 보내는 `{type, payload, at}` JSON을
/// Map으로 돌려준다. JSON이 아니거나 객체가 아니거나 `type`이 문자열이 아니면 null(파손 흡수).
Map<String, dynamic>? decodeInteractionMessage(String raw) {
  try {
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic> && decoded['type'] is String) {
      return decoded;
    }
  } catch (_) {
    // 깨진 JSON은 학습 흐름을 막지 않는다(null로 무시).
  }
  return null;
}

/// 시각화 명세(`interactive_graph_2d`·`interactive_surface_3d`)를 실 WebView로 렌더하는 인라인 위젯.
///
/// 라우트를 추가하지 않고(인라인 임베드) `SceneRenderer` 안에서 고정 높이로 표시한다.
class GraphingCalculatorWebView extends StatefulWidget {
  const GraphingCalculatorWebView({
    required this.viz,
    this.height = 320,
    this.onInteraction,
    super.key,
  });

  /// 렌더할 시각화 명세(`spec`이 Graph2dSpec/Surface3dSpec 구조).
  final Visualization viz;

  /// 인라인 표시 높이(px).
  final double height;

  /// 학생 조작 이벤트 콜백(학습 로그 워이어용·기본 null이면 debugPrint만).
  final void Function(Map<String, dynamic> event)? onInteraction;

  @override
  State<GraphingCalculatorWebView> createState() => _GraphingCalculatorWebViewState();
}

class _GraphingCalculatorWebViewState extends State<GraphingCalculatorWebView> {
  late final WebViewController _controller;

  @override
  void initState() {
    super.initState();
    // base64는 영숫자 + '+/=' 뿐이라 작은따옴표 JS 리터럴에 안전(이스케이프 불요).
    final param = encodeGraph2dSpecParam(widget.viz.spec ?? const <String, dynamic>{});
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      // 학습 로그 인바운드 — 웹 emitInteraction이 보내는 학생 조작 이벤트 수신.
      ..addJavaScriptChannel(
        'WhymathInteraction',
        onMessageReceived: (JavaScriptMessage message) {
          final event = decodeInteractionMessage(message.message);
          if (event == null) return;
          widget.onInteraction?.call(event);
          debugPrint('[whymath] interaction ${event['type']}: ${event['payload']}');
        },
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            // 로드 완료 후 명세 주입(loadFlutterAsset는 ?spec= 쿼리 미지원).
            _controller.runJavaScript("window.whymathApplySpec('$param')");
          },
        ),
      )
      ..loadFlutterAsset('assets/graphing_calculator/index.html');
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
