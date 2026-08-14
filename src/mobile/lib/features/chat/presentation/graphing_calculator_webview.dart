// GraphingCalculatorWebView — vendored 웹 계산기(src/web/graphing-calculator)를 WebView로 임베드.
//
// 경계(슬89 표현≠의미·국소 비상구): 백엔드가 검증해 내려준 Visualization.spec(Graph2dSpec 구조)을
// *그대로* 웹 계산기에 주입해 렌더만 한다 — Dart 측엔 수학 로직 0. 그래프 계산기는 클라 수학 평가의
// 국소 예외(자족 비상구)로, Flutter는 자산 번들(assets/graphing_calculator/)을 오프라인 로드한다.
//
// 주입 방식: loadFlutterAsset는 쿼리스트링(?spec=)을 못 싣는다 → 페이지 로드 완료(onPageFinished) 후
// 웹이 노출한 전역 훅 window.whymathApplySpec(base64(JSON))을 runJavaScript로 호출해 명세를 넣는다.
//
// 생명주기 하드닝(MOB-19): 저사양 안드로이드(미션 하한선)에서 WebView+three.js는 가장 무거운 조합이다.
// 그래서 ① onPageFinished 전까지 로딩 인디케이터로 흰 플래시·빈 화면을 가리고, ② 주 프레임 로드 실패
// (onWebResourceError) 또는 웹 앱 기동 실패(applySpec 훅 부재 — 번들/three.js 초기화 사망) 시 WebView를
// 걷어내고 캡션 시드로 강등한다. 정서 안전: 실패를 빨강·경고로 표현하지 않는다 — 학생에게는 정적
// 캡션이 "원래 정적인 그림 설명"과 같은 중립 톤으로 보인다.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../data/interaction_logger.dart';
import '../data/scene_models.dart';
import 'webview_fallback.dart';

/// Graph2dSpec(Map) → 웹 계산기 `?spec=` 호환 base64(JSON) 파라미터.
///
/// 웹의 `parseSpecParam`(atob→JSON.parse)이 그대로 소비하는 **표준 base64**(urlsafe 아님)다.
/// JSON은 compact(공백 없음) — `jsonEncode`는 기본이 compact다.
/// (spec-only 인코더 — 공개 `?spec=` 공유 링크 계약과 동형. 봉투는 아래 참조.)
String encodeGraph2dSpecParam(Map<String, dynamic> spec) =>
    base64.encode(utf8.encode(jsonEncode(spec)));

/// Visualization → `{type, spec}` 봉투 base64(JSON) 파라미터 — 렌더 선택 단일 진실원(invariant ⑩).
///
/// 코어 `Visualization.type`이 렌더러를 정하는 단일 권위다(`data/render_contract.json`). 과거엔
/// 이 경계가 spec만 실어(encodeGraph2dSpecParam) 웹이 spec 모양으로 렌더러를 재추론(experiment→sim
/// 등)했고, experiment 없는 유효 sim이 2D로 오라우팅되는 drift가 있었다. 이제 `type`을 함께 실어
/// 웹의 `unwrapSpecEnvelope`+`specToStateForType`가 type을 우선 소비하게 한다(웹은 봉투가 없는
/// 레거시 spec-only도 shape 폴백으로 계속 수용 — 하위호환). spec-only 인코더는 공유 링크용으로 존치.
String encodeVisualizationParam(Visualization viz) => base64.encode(
      utf8.encode(
        jsonEncode(<String, dynamic>{
          'type': viz.type,
          'spec': viz.spec ?? const <String, dynamic>{},
        }),
      ),
    );

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
///
/// 생명주기(MOB-19): 로드 완료 전까지 로딩 인디케이터를 얹고, 주 프레임 로드 실패·웹 앱 기동 실패 시
/// 캡션 시드 폴백으로 강등한다(빈 화면 미노출 — 저사양 단말이 미션 하한선).
class GraphingCalculatorWebView extends ConsumerStatefulWidget {
  const GraphingCalculatorWebView({
    required this.viz,
    this.conceptId,
    this.sceneId,
    this.height = 320,
    super.key,
  });

  /// 렌더할 시각화 명세(`spec`이 Graph2dSpec/Surface3dSpec 구조).
  final Visualization viz;

  /// 탐구 중인 개념(scene.conceptId·호스트측 학습 로그 컨텍스트·선택). 슬라이스 96-J.
  final String? conceptId;

  /// 조작이 일어난 학습 장면(scene.sceneId·선택). 슬라이스 96-J.
  final String? sceneId;

  /// 인라인 표시 높이(px).
  final double height;

  @override
  ConsumerState<GraphingCalculatorWebView> createState() => _GraphingCalculatorWebViewState();
}

class _GraphingCalculatorWebViewState extends ConsumerState<GraphingCalculatorWebView> {
  late final WebViewController _controller;

  /// 로딩 인디케이터 표시 여부 — onPageFinished(로드 완료) 전까지만 true(MOB-19).
  bool _loading = true;

  /// 강등 여부 — 주 프레임 로드 실패·웹 앱 기동 실패 시 캡션 시드로 내린다(빈 화면 금지).
  bool _fallBackToCaption = false;

  @override
  void initState() {
    super.initState();
    // base64는 영숫자 + '+/=' 뿐이라 작은따옴표 JS 리터럴에 안전(이스케이프 불요).
    // {type, spec} 봉투로 실어 웹이 type을 우선 소비하게 한다(invariant ⑩·렌더 선택 단일 진실원).
    final param = encodeVisualizationParam(widget.viz);
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      // 학습 로그 인바운드 — 웹 emitInteraction이 보내는 학생 조작 이벤트를 백엔드로 적재.
      ..addJavaScriptChannel(
        'WhymathInteraction',
        onMessageReceived: (JavaScriptMessage message) {
          final event = decodeInteractionMessage(message.message);
          if (event == null) return;
          // 개념 컨텍스트는 호스트(Flutter)가 scene에서 주입한다 — 웹은 모른다(슬89·J).
          ref.read(interactionLoggerProvider).record(
                event,
                conceptId: widget.conceptId,
                sceneId: widget.sceneId,
              );
          debugPrint('[whymath] interaction ${event['type']}: ${event['payload']}');
        },
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) => _onPageFinished(param),
          onWebResourceError: _onWebResourceError,
        ),
      )
      ..loadFlutterAsset('assets/graphing_calculator/index.html');
  }

  /// 로드 완료 처리 — 웹 앱 기동을 확인한 뒤 인디케이터를 거두고 명세를 주입한다.
  Future<void> _onPageFinished(String param) async {
    // 이미 강등됐거나 dispose된 뒤 늦게 도착한 콜백은 무시한다(빈 화면으로 되돌리지 않음).
    if (_fallBackToCaption || !mounted) return;
    // 웹 앱 기동 확인(MOB-19): three.js·번들 초기화가 저사양 단말에서 죽으면 페이지 로드는
    // "성공"이지만 applySpec 훅이 없는 빈 캔버스만 남는다 — 훅 부재를 감지해 캡션으로 강등한다.
    // 반환 표기는 플랫폼마다 다르다(안드로이드는 JSON 인코딩 문자열 '"1"', iOS는 숫자 1) —
    // 그래서 동등 비교가 아니라 포함 여부로 본다.
    final hookAlive =
        await _controller.runJavaScriptReturningResult('window.whymathApplySpec ? 1 : 0');
    if (!mounted) return;
    if (!hookAlive.toString().contains('1')) {
      debugPrint('[whymath] 그래프 웹 앱 기동 실패(applySpec 훅 부재) → 캡션 폴백');
      setState(() {
        _loading = false;
        _fallBackToCaption = true;
      });
      return;
    }
    setState(() => _loading = false);
    // 로드 완료 후 명세 주입(loadFlutterAsset는 ?spec= 쿼리 미지원).
    await _controller.runJavaScript("window.whymathApplySpec('$param')");
  }

  /// 리소스 로드 실패 처리 — 주 프레임 실패만 캡션으로 강등한다(판정은 공유 순수 함수).
  void _onWebResourceError(WebResourceError error) {
    if (!shouldDemoteWebViewOnError(isForMainFrame: error.isForMainFrame)) return;
    // 침묵 실패 금지 — 강등 사유를 로그로 남긴다(학생 표면은 중립 톤 유지).
    debugPrint(
      '[whymath] 그래프 WebView 주 프레임 로드 실패 → 캡션 폴백: '
      'code=${error.errorCode} ${error.description}',
    );
    if (_fallBackToCaption || !mounted) return;
    setState(() {
      _loading = false;
      _fallBackToCaption = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    // 강등 — WebView 대신 캡션 시드. scene_renderer의 비대화형 시각화 폴백(_VisualizationSeed)과
    // 같은 모습이라 학생은 "실패 경고"가 아니라 정적 그림 설명을 본다(정서 안전).
    if (_fallBackToCaption) {
      final cap = widget.viz.caption;
      return WebViewFallbackTile(
        icon: Icons.insights_outlined,
        label: (cap != null && cap.isNotEmpty) ? cap : '그래프를 불러오지 못했어요',
        height: widget.height,
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        height: widget.height,
        width: double.infinity,
        child: Stack(
          children: [
            WebViewWidget(controller: _controller),
            // 로드 완료 전까지 웹뷰 위를 덮는다 — 초기 흰 프레임·빈 화면을 숨기는 인디케이터.
            if (_loading) const Positioned.fill(child: WebViewLoadingCover()),
          ],
        ),
      ),
    );
  }
}
