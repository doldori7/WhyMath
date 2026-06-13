// 앱 루트 — MaterialApp + 메인 채팅 화면.
//
// 라우팅(go_router)·인증·온보딩은 후속 슬라이스다. 이번 슬라이스는 coach API 통합
// 채팅 플로우가 목표라 홈을 [ChatScreen]으로 직결한다(MaterialApp.home).
import 'package:flutter/material.dart';

import 'features/chat/presentation/chat_screen.dart';

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
      home: const ChatScreen(),
    );
  }
}
