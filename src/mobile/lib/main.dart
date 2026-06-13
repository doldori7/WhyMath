/// 앱 진입점 — ProviderScope로 Riverpod 상태 트리를 래핑하고 [WhyMathApp]을 실행한다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  // ProviderScope — 앱 전역 Riverpod 컨테이너(dioProvider·coachApiProvider 등).
  runApp(const ProviderScope(child: WhyMathApp()));
}
