/// 앱 루트 — MaterialApp + 최소 홈 화면(빌드/analyze 통과용 스캐폴드).
///
/// 실제 UI(채팅·OCR·풀이 진단·라우팅·인증)는 후속 슬라이스다. 이번 슬라이스는
/// *coach API 통합 기반 + CI 검증 게이트*가 목표라 화면은 플레이스홀더 하나만 둔다.
import 'package:flutter/material.dart';

/// WhyMath 앱 루트 위젯.
class WhyMathApp extends StatelessWidget {
  const WhyMathApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'WhyMath',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const _HomePlaceholderScreen(),
    );
  }
}

/// 임시 홈 화면 — 후속 슬라이스에서 채팅 화면으로 교체된다.
class _HomePlaceholderScreen extends StatelessWidget {
  const _HomePlaceholderScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('WhyMath')),
      body: const Center(
        // 슬로건: "답이 아닌, 이유를 묻는 수학"
        child: Text('답이 아닌, 이유를 묻는 수학'),
      ),
    );
  }
}
