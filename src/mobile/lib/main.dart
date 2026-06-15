// 앱 진입점 — Riverpod 컨테이너를 만들고 인증 세션을 복원한 뒤 [WhyMathApp]을 실행한다.
//
// 시작 시 보안 저장소의 토큰으로 세션을 복원(OAuth-c2b)한 *후* 첫 프레임을 그린다 — 그래야
// 라우터 redirect 가드가 첫 평가에서 인증 상태를 즉시 보고 복원된 세션을 채팅으로 보낸다
// (로딩 프레임·refreshListenable 없이 결정론적). 컨테이너는 앱 수명 동안 소유하므로 dispose하지
// 않고 [UncontrolledProviderScope]로 트리에 넘긴다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'features/auth/application/auth_controller.dart';

Future<void> main() async {
  // 플러그인(보안 저장소) 사용 전 바인딩 초기화 — runApp 전 비동기 작업의 전제.
  WidgetsFlutterBinding.ensureInitialized();
  final container = ProviderContainer();
  // 저장된 토큰이 있으면 인증 상태로 복원(없거나 오류면 미인증 — graceful).
  await container.read(authControllerProvider.notifier).restore();
  runApp(
    UncontrolledProviderScope(container: container, child: const WhyMathApp()),
  );
}
