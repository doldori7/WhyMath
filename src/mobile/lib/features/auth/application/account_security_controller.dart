// 계정 보안(내 기기 관리) 컨트롤러 — 활성 세션 조회·단건/전체 로그아웃. MOB-12.
//
// 배경(account_security_gap_review.md D4): "학생이 기기를 분실해도 자기 세션을 끊을 방법이 0"이
// 원 문제였다. SEC-10이 서버 좌석을 완비했지만 호출하는 화면이 없어 문제는 그대로였다 —
// 이 컨트롤러가 그 좌석을 학생 조작에 잇는다.
//
// 경계(CLAUDE.md): 세션 소유·유효성 판정은 전부 서버(L5)다. 이 컨트롤러는 목록을 받아 상태에
// 담고 취소를 *요청*할 뿐, 어떤 세션이 위험한지 스스로 판정하지 않는다(그런 판정 필드 자체가
// 상태에 없다 — 정서 안전·불안 유발 프레이밍 금지).
//
// 정직 원칙: 401(미인증)과 그 외 실패를 분리해 안내한다. 실패를 조용히 삼키지 않는다.
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/update_required.dart';
import '../data/auth_sessions_api.dart';
import 'account_security_state.dart';

part 'account_security_controller.g.dart';

/// 내 기기 관리 화면 상태를 관장하는 Riverpod Notifier.
@riverpod
class AccountSecurityController extends _$AccountSecurityController {
  @override
  AccountSecurityState build() => const AccountSecurityState();

  /// 활성 세션 목록을 조회한다(`GET /v1/auth/sessions`).
  ///
  /// 목록이 비어도 loaded다 — "기기 0대"는 오류가 아니라 정상 응답이다.
  Future<void> load() async {
    if (state.status == AccountSectionStatus.loading) {
      return; // 조회 중 재진입 방지.
    }
    state = state.copyWith(status: AccountSectionStatus.loading, error: null, notice: null);
    try {
      final sessions = await ref.read(authSessionsApiProvider).listSessions();
      state = state.copyWith(status: AccountSectionStatus.loaded, sessions: sessions);
    } on DioException catch (e) {
      if (_isUnauthenticated(e)) {
        state = state.copyWith(status: AccountSectionStatus.unauthenticated);
        return;
      }
      // 426(최소버전 미달)만 전용 문구(판정 좌석 = core/update_required 단일·OPS-35).
      state = state.copyWith(
        status: AccountSectionStatus.error,
        error: updateRequiredMessageOf(e) ?? '기기 목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    } on Object {
      // 426은 항상 DioException으로 도착하므로(위 블록이 처리) 여기는 그 외 예외 전용.
      state = state.copyWith(
        status: AccountSectionStatus.error,
        error: '기기 목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 특정 기기만 로그아웃한다(`DELETE /v1/auth/sessions/{id}`) — 성공 시 목록을 다시 읽는다.
  ///
  /// 목록을 클라에서 지우지 않고 **서버에서 다시 읽는다** — 서버 상태가 단일 권위이므로,
  /// 취소가 실제로 반영됐는지 서버 응답으로 확인하는 편이 정직하다.
  Future<void> revokeSession(String sessionId) async {
    if (state.revokingSessionId != null || state.isRevokingAll) {
      return; // 중복 조작 방지.
    }
    state = state.copyWith(revokingSessionId: sessionId, notice: null);
    try {
      await ref.read(authSessionsApiProvider).revokeSession(sessionId);
      state = state.copyWith(revokingSessionId: null, notice: '기기를 로그아웃했어요.');
      await load();
    } on Object catch (e) {
      state = state.copyWith(
        revokingSessionId: null,
        notice: updateRequiredMessageOf(e) ?? '기기를 로그아웃하지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 모든 기기에서 로그아웃한다(`DELETE /v1/auth/sessions`).
  ///
  /// **한계(정직 표기)**: 서버는 리프레시 세션만 취소한다 — 이미 발급된 액세스 토큰은 자체
  /// 만료까지 유효하다(SEC-10 서버 모듈 docstring 명시). 화면 문구가 "잠시 뒤"로 이 한계를
  /// 그대로 반영한다(즉시 차단이라고 말하지 않는다 — 확실하지 않은 것을 자신 있게 말하지 않는다).
  Future<void> revokeAllSessions() async {
    if (state.isRevokingAll || state.revokingSessionId != null) {
      return;
    }
    state = state.copyWith(isRevokingAll: true, notice: null);
    try {
      await ref.read(authSessionsApiProvider).revokeAllSessions();
      state = state.copyWith(
        isRevokingAll: false,
        sessions: const <AuthSessionInfo>[],
        notice: '모든 기기에서 로그아웃했어요. 이 기기도 잠시 뒤 다시 로그인이 필요해요.',
      );
    } on Object catch (e) {
      state = state.copyWith(
        isRevokingAll: false,
        notice: updateRequiredMessageOf(e) ?? '전체 로그아웃에 실패했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 스낵바 표시 후 안내 문구를 비운다(같은 문구가 재빌드마다 반복되지 않게).
  void clearNotice() {
    if (state.notice != null) {
      state = state.copyWith(notice: null);
    }
  }

  static bool _isUnauthenticated(DioException e) => e.response?.statusCode == 401;
}
