// 토큰 수명주기 API — 액세스 토큰 갱신(회전)·로그아웃 세션 취소. MOB-12.
//
// 배경(OPS-22 declared_unwired_audit 실측): `POST /v1/auth/refresh`·`POST /v1/auth/logout`은
// 서버 좌석이 완비된 지 오래인데 **모바일 호출 0건**이었다. 그 결과 액세스 토큰이 만료되면
// 학생은 아무 예고 없이 전 화면이 실패하고(401), 로그아웃해도 리프레시 세션은 서버에 살아
// 있었다(기기 분실 시 취소 불가).
//
// **왜 core에 있는가**: 토큰 수명주기는 [AuthInterceptor]가 소비하는 *코어* 관심사다. 이 호출을
// `features/auth/data`에 두면 core → features 역방향 import가 생겨 순환이 된다
// (`features/auth/data/auth_api.dart`가 이미 `core/api_client.dart`를 import한다). 세션 *목록·
// 취소* UI 계층 호출은 반대로 화면에 붙는 관심사라 `features/auth/data/auth_sessions_api.dart`에
// 둔다 — 계층 방향으로 갈랐다.
//
// 경계(CLAUDE.md): 클라는 토큰을 *운반*만 한다. 회전·재사용 탐지(탈취 신호)·세션 취소 판정은
// 전부 서버(L5)다 — 이 클래스는 만료 여부를 스스로 판정하지 않고, 서버가 401을 줄 때 반응한다.
import 'package:dio/dio.dart';

/// 토큰 교환 결과 — 서버가 회전 발급한 액세스/리프레시 한 쌍.
///
/// 서버는 회전 시 **기존 리프레시 세션을 취소하고 새 것을 발급**하므로, 클라는 반드시 둘 다
/// 저장해야 한다(옛 리프레시 토큰 재제출은 재사용 탐지에 걸려 전체 세션이 취소된다).
class AuthTokens {
  const AuthTokens({required this.accessToken, required this.refreshToken});

  /// 액세스 토큰(Authorization: Bearer).
  final String accessToken;

  /// 리프레시 토큰(다음 갱신에 쓰인다 — 1회용).
  final String refreshToken;
}

/// `/v1/auth/refresh`·`/v1/auth/logout` 호출 래퍼.
///
/// 주입되는 [Dio]는 **[AuthInterceptor]가 붙지 않은 것**이어야 한다 — 갱신 요청 자체가 401을
/// 받아 다시 갱신을 유발하는 무한 재귀를 구조적으로 막는다(api_client.dart가 그렇게 조립한다).
/// 두 엔드포인트 모두 미인증 표면이라 Bearer 헤더가 필요 없다.
class TokenRefreshApi {
  TokenRefreshApi(this._dio);

  final Dio _dio;

  /// `POST /v1/auth/refresh` — 리프레시 토큰 회전으로 새 액세스+리프레시를 받는다.
  ///
  /// 서버가 401을 주면 그 리프레시 토큰은 만료·취소·재사용 탐지 대상이다(구분은 서버만 안다) —
  /// 호출자는 저장된 토큰을 버리고 재로그인으로 유도해야 한다.
  Future<AuthTokens> refresh(String refreshToken) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/refresh',
      data: <String, dynamic>{'refresh_token': refreshToken},
    );
    final access = response.data?['access_token'];
    final rotated = response.data?['refresh_token'];
    if (access is! String || access.isEmpty || rotated is! String || rotated.isEmpty) {
      throw DioException(requestOptions: response.requestOptions, error: '토큰 갱신 응답이 올바르지 않습니다.');
    }
    return AuthTokens(accessToken: access, refreshToken: rotated);
  }

  /// `POST /v1/auth/logout` — 이 기기의 리프레시 세션을 서버에서 취소한다(204).
  ///
  /// 서버는 행이 없거나 이미 취소됐어도 멱등하게 204를 준다. 취소된 리프레시 토큰은 이후
  /// `/refresh`에서 거부된다(만료를 기다리지 않는다).
  Future<void> logout(String refreshToken) async {
    await _dio.post<void>(
      '/v1/auth/logout',
      data: <String, dynamic>{'refresh_token': refreshToken},
    );
  }
}
