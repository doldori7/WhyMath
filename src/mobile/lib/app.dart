// 앱 루트 — go_router 셸을 얹은 MaterialApp.router.
//
// 단일 화면(MaterialApp.home=ChatScreen)에서 라우팅 셸로 전환했다. 첫 진입은 온보딩
// (메타인지 철학 안내·기대 관리)이고, "시작하기"로 채팅 화면에 진입한다(라우터 정의는
// [goRouterProvider] 참조). 인증·온보딩 1회-노출 영속·딥링크·하단 탭 네비게이션은 후속.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router.dart';
import 'theme/app_theme.dart';

/// WhyMath 앱 루트 위젯.
///
/// [goRouterProvider]를 watch해 `MaterialApp.router`에 주입한다. 라우터 인스턴스는
/// provider 수명 동안 1개라 watch해도 재생성되지 않는다(상태 안정).
class WhyMathApp extends ConsumerWidget {
  const WhyMathApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(goRouterProvider);
    return MaterialApp.router(
      title: 'WhyMath',
      theme: WhyMathTheme.light,
      darkTheme: WhyMathTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
