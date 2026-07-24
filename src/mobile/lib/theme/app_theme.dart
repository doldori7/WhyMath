// 앱 테마 — 디자인 토큰(색 롤·라이트/다크·정서 안전 팔레트)의 단일 정본. MOB-09.
//
// 정서 안전(CLAUDE.md·coding_flutter.md): 오답·오류를 *질책의 빨강*이 아니라 *주의의 앰버*로 표현한다.
// M3 `ColorScheme.error`(기본 빨강 계열)를 앰버로 재정의해, 코드 어디서 `colorScheme.error`를 쓰더라도
// 빨강이 나오지 않게 토큰에서 구조적으로 강제한다(현재 앱은 error 롤 미사용이나 향후 오용 차단).
// 라이트 외형은 기존 seed(indigo)를 유지해 변화가 없고, 다크는 시스템 설정에 따라 자동 적용된다.
import 'package:flutter/material.dart';

/// WhyMath 앱 테마 정본 — 라이트/다크 [ThemeData]와 seed·정서 안전(앰버) 색 토큰.
abstract final class WhyMathTheme {
  /// 브랜드 seed — 기존 인라인 테마와 동일(라이트 외형 보존).
  static const Color seed = Colors.indigo;

  // 정서 안전 앰버(주의) — M3 error 롤 재정의용. 빨강(hue≈0)이 아니라 앰버(hue≈40~44).
  // 라이트: 본문 대비 확보용 어두운 앰버 / 다크: 밝은 앰버.
  static const Color _cautionLight = Color(0xFF7A5900);
  static const Color _onCautionLight = Color(0xFFFFFFFF);
  static const Color _cautionContainerLight = Color(0xFFFFDF9E);
  static const Color _onCautionContainerLight = Color(0xFF261A00);
  static const Color _cautionDark = Color(0xFFF5C64D);
  static const Color _onCautionDark = Color(0xFF3F2E00);
  static const Color _cautionContainerDark = Color(0xFF5B4300);
  static const Color _onCautionContainerDark = Color(0xFFFFDF9E);

  /// 라이트 테마.
  static ThemeData get light => _build(Brightness.light);

  /// 다크 테마(시스템 다크 모드에서 자동 적용).
  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final isLight = brightness == Brightness.light;
    final scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: brightness,
    ).copyWith(
      // 정서 안전: error 계열을 앰버(주의)로 재정의 — 빨강 금지를 토큰에서 강제.
      error: isLight ? _cautionLight : _cautionDark,
      onError: isLight ? _onCautionLight : _onCautionDark,
      errorContainer: isLight ? _cautionContainerLight : _cautionContainerDark,
      onErrorContainer:
          isLight ? _onCautionContainerLight : _onCautionContainerDark,
    );
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
    );
  }
}
