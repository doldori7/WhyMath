/// 빌드 타임 환경 설정 — 시크릿·URL은 `--dart-define`으로 주입(하드코딩 금지·CLAUDE.md).
///
/// 독립 수학 코어(L1-L4)는 API로만 소비하므로 클라이언트가 아는 건 *베이스 URL*뿐이다.
/// 수학 로직·정답·검증 규칙은 절대 클라에 두지 않는다(표현≠의미·코어 API 소비).
class Env {
  Env._();

  /// 백엔드 API 베이스 URL. 기본값은 로컬 개발 서버(README 정합).
  /// 배포 시 `flutter run --dart-define=API_URL=https://api.example.com`로 덮어쓴다.
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://localhost:8000',
  );

  /// 에러 리포팅 DSN(옵션) — 미주입 시 빈 문자열(리포팅 비활성).
  static const String sentryDsn = String.fromEnvironment('SENTRY_DSN');
}
