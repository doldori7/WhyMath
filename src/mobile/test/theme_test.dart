// 테마/디자인 토큰 회귀 게이트 — 정서 안전(빨강 금지·error=앰버)·라이트/다크 빌드. MOB-09.
//
// 불변식(CLAUDE.md·coding_flutter.md): 오답·오류를 빨강으로 표현하지 않는다. WhyMathTheme가
// M3 error 롤을 앰버(주의)로 재정의하므로, 라이트·다크 둘 다 error/errorContainer의 색상(hue)이
// 빨강(≈0°)이 아니라 앰버(≈40~44°)여야 한다. 이 테스트가 향후 error를 빨강으로 되돌리는 회귀를 막는다.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/theme/app_theme.dart';

/// 앰버(주의) 허용 hue 범위 — 빨강(≈0°)은 확실히 배제하고 노랑까지 포함.
const double _amberHueMin = 30;
const double _amberHueMax = 75;

void _expectCaution(ColorScheme scheme, String label) {
  final roles = <String, Color>{
    'error': scheme.error,
    'errorContainer': scheme.errorContainer,
  };
  for (final entry in roles.entries) {
    final hue = HSVColor.fromColor(entry.value).hue;
    expect(
      hue,
      inInclusiveRange(_amberHueMin, _amberHueMax),
      reason: '$label ${entry.key} 색상(hue=$hue)이 앰버 범위를 벗어남 — '
          '정서 안전(빨강 금지) 위반 가능. error 롤은 앰버(주의)로 유지해야 한다.',
    );
  }
}

void main() {
  test('라이트 테마: M3 · error 롤이 앰버(빨강 아님)', () {
    final theme = WhyMathTheme.light;
    expect(theme.useMaterial3, isTrue);
    expect(theme.colorScheme.brightness, Brightness.light);
    _expectCaution(theme.colorScheme, '라이트');
  });

  test('다크 테마: M3 · error 롤이 앰버(빨강 아님)', () {
    final theme = WhyMathTheme.dark;
    expect(theme.useMaterial3, isTrue);
    expect(theme.colorScheme.brightness, Brightness.dark);
    _expectCaution(theme.colorScheme, '다크');
  });

  test('seed는 indigo(라이트 외형 보존)', () {
    expect(WhyMathTheme.seed, Colors.indigo);
  });
}
