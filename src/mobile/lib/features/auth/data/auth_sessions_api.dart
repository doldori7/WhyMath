// 계정 세션 API 클라이언트 — 내 기기(활성 세션) 목록·단건/전체 로그아웃 호출. MOB-12.
//
// 배경(account_security_gap_review.md D4 · OPS-22 실측): SEC-10이 `GET/DELETE /v1/auth/sessions`·
// `DELETE /v1/auth/sessions/{jti}` 서버 좌석을 완비했으나 **모바일 호출 0건**이라, "학생이 기기를
// 분실해도 자기 세션을 끊을 방법이 0"이라는 원 문제가 서버 좌석이 생긴 뒤에도 그대로 남아 있었다.
// 이 클래스가 그 좌석을 학생 화면에 잇는다.
//
// 경계(CLAUDE.md): 세션 소유 판정(본인 스코핑)·취소는 전부 서버(L5)다 — 클라는 목록을 받아
// 표시하고 취소를 *요청*할 뿐, 어떤 세션이 유효한지 스스로 판단하지 않는다.
//
// 최소 수집: 응답에 IP·User-Agent 원문이 없다(서버가 애초에 주지 않는다). `platform`은
// "iOS"/"Android"/"Web" 수준의 좁은 요약뿐이다 — 미성년자 정보 최소 수집 원칙의 클라측 준수.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';

/// 활성 세션 1건 — 학생에게 "내 기기 하나"로 보이는 단위.
///
/// 서버 `SessionInfo` 스키마 4필드를 그대로 받는다(파생·재계산 없음 — 표시 전용).
class AuthSessionInfo {
  const AuthSessionInfo({
    required this.sessionId,
    required this.issuedAt,
    required this.expiresAt,
    this.platform,
  });

  /// JSON 1건 → 모델. 필수 필드가 없거나 형식이 다르면 [FormatException].
  factory AuthSessionInfo.fromJson(Map<String, dynamic> json) {
    final sessionId = json['session_id'];
    final issuedAt = json['issued_at'];
    final expiresAt = json['expires_at'];
    if (sessionId is! String || issuedAt is! String || expiresAt is! String) {
      throw const FormatException('세션 정보 형식이 올바르지 않습니다.');
    }
    final platform = json['platform'];
    return AuthSessionInfo(
      sessionId: sessionId,
      issuedAt: DateTime.parse(issuedAt),
      expiresAt: DateTime.parse(expiresAt),
      platform: platform is String && platform.isNotEmpty ? platform : null,
    );
  }

  /// 세션 식별자(리프레시 토큰의 jti) — 단건 로그아웃 시 경로에 실린다.
  final String sessionId;

  /// 로그인·갱신 시각(발급 시점).
  final DateTime issuedAt;

  /// 만료 시각.
  final DateTime expiresAt;

  /// 좁은 플랫폼 요약("iOS"/"Android"/"Web"). 판별 불가·구버전 세션은 null.
  final String? platform;
}

/// 계정 세션 엔드포인트 호출 래퍼 — 공유 [dioProvider](Bearer 자동 첨부) 위에서 동작한다.
class AuthSessionsApi {
  AuthSessionsApi(this._dio);

  final Dio _dio;

  /// `GET /v1/auth/sessions` — 내 활성 세션 목록(서버가 발급 시각 내림차순으로 준다).
  ///
  /// 정렬을 클라에서 다시 하지 않는다 — 서버 순서를 그대로 보존한다(단일 권위).
  Future<List<AuthSessionInfo>> listSessions() async {
    final response = await _dio.get<Map<String, dynamic>>('/v1/auth/sessions');
    final sessions = response.data?['sessions'];
    if (sessions is! List) {
      throw DioException(requestOptions: response.requestOptions, error: '세션 목록 응답이 올바르지 않습니다.');
    }
    return sessions
        .whereType<Map<String, dynamic>>()
        .map(AuthSessionInfo.fromJson)
        .toList(growable: false);
  }

  /// `DELETE /v1/auth/sessions` — 전체 로그아웃(내 모든 활성 세션 취소).
  ///
  /// 기기 분실·계정 탈취 의심 시 쓴다. **한계(정직 표기)**: 리프레시 토큰만 취소된다 — 이미
  /// 발급된 액세스 토큰은 자체 만료까지 유효하다(서버 SEC-10 모듈 docstring 명시). 화면 문구도
  /// 이 한계를 "잠시 뒤"로 정직하게 반영한다.
  Future<void> revokeAllSessions() async {
    await _dio.delete<void>('/v1/auth/sessions');
  }

  /// `DELETE /v1/auth/sessions/{session_id}` — 특정 기기만 로그아웃(본인 소유만·타인 것은 404).
  Future<void> revokeSession(String sessionId) async {
    await _dio.delete<void>('/v1/auth/sessions/$sessionId');
  }
}

/// [AuthSessionsApi] provider — 공유 [dioProvider] 주입([authApiProvider]와 동형).
final authSessionsApiProvider = Provider<AuthSessionsApi>((ref) {
  return AuthSessionsApi(ref.watch(dioProvider));
});
