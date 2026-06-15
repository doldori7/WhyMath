// 인증 컨트롤러 — code 교환 → 토큰 저장 → auth 상태. OAuth-c1.
//
// 경계(CLAUDE.md): 토큰 발급·검증은 서버(L5). 이 컨트롤러는 (1) provider code를 백엔드 콜백으로
// 교환하고 (2) 받은 JWT를 보안 저장소(OAuth-b `tokenStore`)에 저장하며 (3) 실패를 graceful 처리할
// 뿐이다. provider 리다이렉트(code 획득·webview/딥링크)는 *호출자*(로그인 화면·c2)가 담당하고
// 여기엔 code만 들어온다. `ChatController`(@riverpod) 패턴을 따른다.
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/token_store.dart';
import '../data/auth_api.dart';
import 'auth_state.dart';

part 'auth_controller.g.dart';

/// 인증 세션을 관리하는 Riverpod Notifier.
@riverpod
class AuthController extends _$AuthController {
  @override
  AuthState build() => const AuthState();

  /// 앱 시작 시 보안 저장소(OAuth-b `tokenStore`)의 토큰으로 인증 세션을 복원한다.
  ///
  /// 재시작 후에도 로그인 세션을 유지한다 — `build()`는 항상 미인증으로 시작하므로, 시작 시
  /// 한 번 호출해 저장된 토큰이 있으면 인증 상태로 올린다(라우터 가드가 채팅으로 보냄·c2b).
  /// 토큰 *검증*은 서버(L5) — 여기선 존재만 보고 운반한다(만료 처리는 후속). 보안 저장소 오류는
  /// 미인증으로 처리해 앱이 죽지 않게 한다.
  Future<void> restore() async {
    try {
      final token = await ref.read(tokenStoreProvider).readAccessToken();
      if (token != null && token.isNotEmpty) {
        state = state.copyWith(isAuthenticated: true);
      }
    } on Object catch (_) {
      // 보안 저장소 미가용·오류(테스트의 MissingPluginException 포함) → 미인증 취급, 앱 안 죽음.
    }
  }

  /// authorization code를 토큰으로 교환하고 보안 저장소에 저장한다(로그인 완료).
  ///
  /// 흐름: ① 전송중 표시·에러 클리어 → ② `AuthApi.login`(백엔드 콜백) → ③ `tokenStore.saveAccessToken`
  /// → 인증 상태 → ④ 실패 시 graceful 에러(앱은 죽지 않는다). 토큰 저장 후엔 dio 인터셉터(OAuth-b)가
  /// 이후 모든 요청에 Bearer로 첨부한다.
  Future<void> completeLogin({
    required String provider,
    required String code,
    required String redirectUri,
  }) async {
    if (state.isSubmitting) {
      return; // 전송 중 재진입 방지.
    }
    state = state.copyWith(isSubmitting: true, error: null);
    try {
      final token = await ref.read(authApiProvider).login(
            provider: provider,
            code: code,
            redirectUri: redirectUri,
          );
      await ref.read(tokenStoreProvider).saveAccessToken(token);
      state = state.copyWith(isSubmitting: false, isAuthenticated: true);
    } catch (e) {
      state = state.copyWith(
        isSubmitting: false,
        error: '로그인에 실패했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 로그아웃 — 저장된 토큰을 지우고 미인증 상태로 되돌린다.
  Future<void> logout() async {
    await ref.read(tokenStoreProvider).clear();
    state = state.copyWith(isAuthenticated: false);
  }
}
