// 인증 화면 상태 — 로그인 진행·인증 여부·에러. OAuth-c1.
//
// `ChatState`(freezed) 패턴을 따른다. 화면 상태일 뿐 영속·전송 대상이 아니다(런타임 모델).
import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_state.freezed.dart';

/// 인증 흐름 상태.
///
/// - [isSubmitting] : code 교환 중(중복 요청 방지·로딩 표시).
/// - [isAuthenticated] : 토큰을 받아 저장했는가(라우트 가드·UI 분기는 후속 c2/c3).
/// - [error] : 로그인 실패 메시지(있으면 표시·null이면 없음).
@freezed
abstract class AuthState with _$AuthState {
  const factory AuthState({
    @Default(false) bool isSubmitting,
    @Default(false) bool isAuthenticated,
    String? error,
  }) = _AuthState;
}
