// 로그인 화면 — 카카오·네이버 소셜 로그인 진입. OAuth-c2.
//
// 경계(CLAUDE.md): 화면은 (1) provider 인가를 띄워 code를 받고(`OAuthCodeRequester` seam)
// (2) 그 code를 `AuthController.completeLogin`(OAuth-c1)으로 토큰과 교환할 뿐이다 — 토큰 발급·
// 사용자 식별은 서버(L5). 실 code 획득(webview/딥링크)은 후속(OAuth-c3)이라, seam이 미구현
// placeholder면 명확히 안내하고 앱은 죽지 않는다(graceful). `ChatScreen`(ConsumerStatefulWidget)
// 패턴을 따른다.
//
// 비파괴(정직): c3 전엔 로그인이 작동하지 않으므로 기본 흐름(온보딩→채팅)을 강제하지 않는다.
// 이 화면은 `/login`에 등록만 되고, 흐름 강제(라우트 가드)·세션 복원은 후속(OAuth-c2b)이다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';
import '../application/auth_controller.dart';
import '../data/oauth_code_requester.dart';

/// 슬로건 — 로그인 화면에서도 브랜드 정체성을 노출한다.
const String _slogan = '답이 아닌, 이유를 묻는 수학';

/// 카카오 브랜드 색(노란 배경·어두운 글자) — 인지 가능한 표준 버튼 스타일.
const Color _kakaoColor = Color(0xFFFEE500);

/// 네이버 브랜드 색(초록 배경·흰 글자).
const Color _naverColor = Color(0xFF03C75A);

/// 소셜 로그인 화면.
///
/// 카카오/네이버 버튼으로 provider 인가를 시작한다. code 획득(seam)→토큰 교환(c1)이 성공하면
/// 채팅으로 이동하고, 실패·미구현은 SnackBar로 안내하며 화면에 머문다(앱 흐름 유지).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  /// 짧은 안내를 SnackBar로 띄운다(중복 방지 위해 이전 것을 먼저 감춘다).
  void _showSnack(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  /// provider 인가 → code 획득(seam) → 토큰 교환(c1) → 성공 시 채팅으로 이동한다.
  ///
  /// code 획득 실패·미구현([OAuthCodeException])과 토큰 교환 실패를 각각 SnackBar로 안내하고
  /// 화면에 머문다(앱은 죽지 않는다). 토큰 교환 자체는 `AuthController`가 내부에서 graceful
  /// 처리하므로, 여기선 결과 상태(isAuthenticated·error)만 읽어 분기한다.
  Future<void> _onLogin(String provider) async {
    final OAuthCodeRequest request;
    try {
      request =
          await ref.read(oauthCodeRequesterProvider).requestCode(provider);
    } on OAuthCodeException catch (e) {
      if (mounted) {
        _showSnack(e.message);
      }
      return;
    }

    await ref.read(authControllerProvider.notifier).completeLogin(
          provider: provider,
          code: request.code,
          redirectUri: request.redirectUri,
        );
    if (!mounted) {
      return;
    }
    final state = ref.read(authControllerProvider);
    if (state.isAuthenticated) {
      context.go(AppRoutes.chatPath);
    } else if (state.error != null) {
      _showSnack(state.error!);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // 전송 중엔 버튼을 비활성화해 중복 인가를 막는다(상태는 c1 컨트롤러가 관리).
    final isSubmitting =
        ref.watch(authControllerProvider.select((s) => s.isSubmitting));

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.functions, size: 72, color: theme.colorScheme.primary),
                const SizedBox(height: 16),
                Text(
                  'WhyMath',
                  style: theme.textTheme.headlineMedium
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                const Text(_slogan, textAlign: TextAlign.center),
                const SizedBox(height: 48),
                _ProviderButton(
                  label: '카카오로 시작하기',
                  background: _kakaoColor,
                  foreground: Colors.black87,
                  onPressed: isSubmitting ? null : () => _onLogin('kakao'),
                ),
                const SizedBox(height: 12),
                _ProviderButton(
                  label: '네이버로 시작하기',
                  background: _naverColor,
                  foreground: Colors.white,
                  onPressed: isSubmitting ? null : () => _onLogin('naver'),
                ),
                const SizedBox(height: 24),
                // 전송 중 은근한 로딩만 표시(카운트다운·보상 연출 없음·절대 금기 준수).
                if (isSubmitting) const LinearProgressIndicator(minHeight: 2),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 소셜 로그인 버튼 — 브랜드 색의 전체 너비 [FilledButton].
class _ProviderButton extends StatelessWidget {
  const _ProviderButton({
    required this.label,
    required this.background,
    required this.foreground,
    required this.onPressed,
  });

  final String label;
  final Color background;
  final Color foreground;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: background,
          foregroundColor: foreground,
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
        child: Text(label),
      ),
    );
  }
}
