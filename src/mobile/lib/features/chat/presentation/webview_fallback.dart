// WebView 생명주기 폴백 공유 자산(MOB-19) — vendored WebView 2종(그래프 계산기·MathLive 입력기)의
// 강등 판정과 폴백/로딩 외형을 한곳에 둔다.
//
// 배경: 두 WebView 모두 `loadFlutterAsset`로 오프라인 자산을 띄우지만, 저사양 안드로이드(미션
// 하한선)에서는 WebView+three.js 조합이 가장 먼저 죽는다. 로드 실패를 아무 처리 없이 두면 학생에게
// 빈 화면이 나간다 — 이 파일의 판정·위젯은 "실패 시에도 정적 캡션/안내가 화면을 채운다"를 보장한다.
//
// 테스트 심: WebView(플랫폼 뷰)는 헤드리스 flutter test에서 pump할 수 없다. 그래서 강등 *판정*
// (순수 함수)과 강등 *외형*(공개 위젯)을 분리해 둘을 테스트가 물고, WebView 본체는 이 둘을 조립만
// 한다(graphing_calculator_webview_test.dart의 순수 함수 선례와 같은 방침).
import 'package:flutter/material.dart';

import '../../../theme/spacing.dart';

/// WebView 리소스 오류가 강등 사유인지 판정한다(순수 — 플랫폼·WebView 무관).
///
/// 하위 자원(폰트·js chunk) 실패는 페이지를 죽이지 않으므로, `isForMainFrame == false`로 *명시*
/// 된 경우만 강등하지 않는다. null(일부 플랫폼 미보고)이면 강등 쪽으로 닫는다 — vendored 자산이
/// 통째로 실패한 경우를 놓쳐 빈 화면을 주는 것보다 정적 폴백이 낫다(빈 화면 금지가 미션 하한선).
bool shouldDemoteWebViewOnError({required bool? isForMainFrame}) => isForMainFrame != false;

/// WebView 로드 실패 시 강등되는 정적 폴백 타일(MOB-19).
///
/// scene_renderer의 비대화형 시각화 폴백(_VisualizationSeed)과 같은 모습을 유지해 강등이 "실패
/// 경고"가 아니라 정적 그림 설명·안내로 읽히게 한다(정서 안전 — 빨강·error 롤을 쓰지 않는다).
class WebViewFallbackTile extends StatelessWidget {
  const WebViewFallbackTile({
    required this.icon,
    required this.label,
    this.height,
    super.key,
  });

  /// 타일 좌측 아이콘(중립 톤 — primary 롤).
  final IconData icon;

  /// 학생에게 보이는 한 줄 문구(캡션 또는 안내).
  final String label;

  /// WebView가 차지했을 높이 — 주면 강등해도 스크롤이 뛰지 않게 같은 높이를 유지한다.
  /// null이면 부모 제약을 그대로 채운다(전체 높이 배치용).
  final double? height;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // 접근성(A11Y-01 선례): 아이콘+텍스트 조각 대신 블록 전체를 하나의 라벨로 읽게 한다.
    return Semantics(
      label: label,
      child: Container(
        height: height,
        width: double.infinity,
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 18, color: theme.colorScheme.primary),
                const SizedBox(width: AppSpacing.sm),
                Flexible(child: Text(label, style: theme.textTheme.bodyMedium)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 로딩 커버 — onPageFinished 전까지 WebView 위를 덮는 인디케이터(MOB-19).
///
/// 배경은 폴백과 같은 surfaceContainerHighest라 로딩→완료/강등 어디로 전환돼도 색이 끊기지 않는다.
class WebViewLoadingCover extends StatelessWidget {
  const WebViewLoadingCover({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: const Center(child: CircularProgressIndicator(strokeWidth: 2.5)),
    );
  }
}
