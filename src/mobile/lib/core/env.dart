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

  /// 시연 전용 사전주입 토큰(S1 실기기 시연 게이트 ①) — `--dart-define=DEMO_TOKEN=...`.
  ///
  /// 실 로그인 webview(OAuth-c3)가 미배선이라 보호 엔드포인트가 401로 막히는데, 시연에선 이
  /// 토큰을 주입해 인증 상태로 부팅한다(`AuthController.restore`가 저장소에 심어 인증). 미주입
  /// 시 빈 문자열 → prod 빌드는 이 define을 넘기지 않으므로 항상 빈 값(시연 경로 미실행·누출 없음).
  static const String demoToken = String.fromEnvironment('DEMO_TOKEN');

  /// 앱 버전(`X.Y.Z`, 빌드번호 없음) — 서버 `X-App-Version` 계약 헤더에 그대로 실린다(OPS-17).
  ///
  /// `pubspec.yaml`의 `version:`(예: `0.1.0+1`의 `+1` 앞부분)과 **손으로** 동기화한다 — Dart는
  /// 빌드타임에 pubspec.yaml을 읽을 수 없어(신규 코드생성 파이프라인은 과공학) 상수로 둔다.
  /// 드리프트는 `tests/infra/test_app_version_pubspec_sync.py`가 CI에서 잡는다(둘이 다르면
  /// fail) — pubspec의 `version:`을 올릴 땐 반드시 이 값도 함께 올린다.
  static const String appVersion = '0.1.0';
}
