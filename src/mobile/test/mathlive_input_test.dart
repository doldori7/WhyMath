// normalizeLatexInput 단위 테스트 — 웹→Flutter LaTeX 입력 정규화(순수 함수).
//
// WebView 자체(플랫폼 뷰)는 헤드리스 flutter test에서 렌더 불가라 pump하지 않는다 — 여기선
// Flutter/WebView 무관한 순수 정규화만 검증한다(graphing_calculator_webview_test 선례).
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/presentation/mathlive_input_webview.dart';

void main() {
  group('normalizeLatexInput', () {
    test('앞뒤 공백을 제거한다', () {
      expect(normalizeLatexInput('  x^2 + 1  '), 'x^2 + 1');
    });

    test('공백뿐이면 빈 문자열', () {
      expect(normalizeLatexInput('   '), '');
      expect(normalizeLatexInput('\n\t '), '');
    });

    test('빈 문자열은 빈 문자열', () {
      expect(normalizeLatexInput(''), '');
    });

    test('LaTeX 원문의 내부 구조는 보존한다(치환·의미추론 없음)', () {
      const latex = r'\frac{d}{dx}\left(x^2\right) = 2x';
      expect(normalizeLatexInput(latex), latex);
    });

    test('내부 공백은 그대로 둔다(앞뒤만 제거)', () {
      expect(normalizeLatexInput('  a  +  b  '), 'a  +  b');
    });
  });
}
