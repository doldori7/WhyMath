// 계정 보안(내 기기 관리) 화면 상태 — 활성 세션 목록·취소 진행. MOB-12.
//
// 경계(CLAUDE.md): 순수 표현 상태다. 어떤 세션이 유효한지·누구 소유인지 판정은 전부 서버(L5)가
// 내리고, 이 상태는 응답을 그대로 보관할 뿐이다.
//
// 정서 안전(CLAUDE.md·전역 UI 불변식): 이 화면은 *경고 화면이 아니다*. "낯선 기기 감지" 같은
// 불안 유발 프레이밍 대신 "내 기기 관리"라는 통제감 있는 프레이밍을 쓴다 — 상태에도 위협
// 점수·의심도 같은 판정 필드를 두지 않는다(그런 판정은 서버도 하지 않고 우리도 만들지 않는다).
import 'package:freezed_annotation/freezed_annotation.dart';

import '../data/auth_sessions_api.dart';

part 'account_security_state.freezed.dart';

/// 세션 목록 조회 진행 단계 — `SectionStatus`(me_tab_state)와 같은 정직 구분 원칙.
///
/// 401(미인증)을 일반 오류와 분리한다 — 원인이 다르면 안내도 달라야 한다.
enum AccountSectionStatus {
  /// 아직 조회하지 않음(화면 진입 전).
  idle,

  /// 서버 조회 중.
  loading,

  /// 조회 성공 — 목록이 비어도 loaded다(정상 신호).
  loaded,

  /// 401 — 미인증. "로그인이 필요해요"로 안내한다.
  unauthenticated,

  /// 401 외 실패(네트워크·5xx 등).
  error,
}

/// 내 기기(활성 세션) 관리 화면 상태.
@freezed
abstract class AccountSecurityState with _$AccountSecurityState {
  const factory AccountSecurityState({
    @Default(AccountSectionStatus.idle) AccountSectionStatus status,

    /// 활성 세션 목록(서버가 발급 시각 내림차순으로 준 순서 그대로).
    @Default(<AuthSessionInfo>[]) List<AuthSessionInfo> sessions,

    /// 조회 실패(401 외) 메시지·없으면 null.
    String? error,

    /// 취소 요청 중인 세션 id — 해당 행만 진행 표시(전체 목록을 잠그지 않는다).
    String? revokingSessionId,

    /// 전체 로그아웃 진행 중인지.
    @Default(false) bool isRevokingAll,

    /// 방금 완료된 조작의 안내 문구(스낵바)·없으면 null. 성공/실패 모두 담긴다.
    ///
    /// 전체 로그아웃 성공 여부를 별도 플래그로 두지 않는다 — 화면이 그것으로 하는 일이 없기
    /// 때문이다(자동 로그인 화면 전환은 이 슬라이스 범위 밖). 쓰지 않는 상태를 두면 "이 신호로
    /// 무언가 한다"는 잘못된 인상을 준다.
    String? notice,
  }) = _AccountSecurityState;
}
