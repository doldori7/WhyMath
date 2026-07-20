// latexToPlainSolution 단위 테스트 (MOB-06) — MathLive LaTeX→평문 수식 변환 동결.
//
// 순수 함수라 WebView·위젯 없이 검증한다(`normalizeLatexInput` 선례). 최상위 계약:
// ① 여러 줄(`\displaylines{... \\ ...}`)이 `'\n'` 구분 여러 스텝으로 분해된다(verify 전이 생성).
// ② LaTeX 원문이 남지 않는다(백슬래시 명령·중괄호 제거) — 학생 버블 평문 노출.
// ③ caret-less 지수(`x2`)를 절대 만들지 않는다(백엔드가 수열 표기와 모호해 보수 처리).
// 타깃 표기는 백엔드 `to_sympy_source`가 받는 자연 평문(ASCII 연산자·`^`·암묵곱·`=`·유니코드 부호).
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/domain/latex_to_plain.dart';

void main() {
  group('latexToPlainSolution', () {
    test('\\displaylines 여러 줄 → 줄바꿈 구분 스텝(Kiki 실측 대표 케이스)', () {
      // 2026-07-20 실기기: MathLive가 여러 줄을 이 형태로 직렬화 → verify 미결정 유발.
      expect(
        latexToPlainSolution(r'\displaylines{2x+3=7 \\ x=2}'),
        '2x+3=7\nx=2',
        reason: '행 구분자 \\\\ 를 \\n 으로 분해해야 인접 전이(2x+3=7→x=2)가 생긴다',
      );
    });

    test('\\displaylines 3줄도 순서대로 분해한다(캐럿 지수 x^2 는 그대로 유효)', () {
      expect(
        latexToPlainSolution(r'\displaylines{x^2-5x+6=0 \\ (x-2)(x-3)=0 \\ x=2, x=3}'),
        'x^2-5x+6=0\n(x-2)(x-3)=0\nx=2, x=3',
      );
    });

    test('분수 \\frac{a}{b} → ((a)/(b)) (백엔드 미러)', () {
      expect(latexToPlainSolution(r'\frac{1+3}{2}'), '((1+3)/(2))');
    });

    test('지수는 캐럿·그룹을 보존한다 — caret-less(x2) 금지', () {
      expect(latexToPlainSolution(r'x^{2}'), 'x^(2)');
      expect(latexToPlainSolution(r'x^{n+1}'), 'x^(n+1)');
    });

    test('곱셈 명령 → * (뒤 공백 삼킴)', () {
      expect(latexToPlainSolution(r'2\times x=6'), '2*x=6');
      expect(latexToPlainSolution(r'a\cdot b'), 'a*b');
    });

    test('나눗셈 \\div → /', () {
      expect(latexToPlainSolution(r'6\div 2=3'), '6/2=3');
    });

    test('\\left \\right 구획은 제거되고 괄호만 남는다', () {
      expect(
        latexToPlainSolution(r'\left(x-2\right)\left(x-3\right)=0'),
        '(x-2)(x-3)=0',
      );
    });

    test('근호 \\sqrt{x} → sqrt((x))', () {
      expect(latexToPlainSolution(r'\sqrt{x}'), 'sqrt((x))');
    });

    test('이미 평문인 입력은 멱등(trim만)', () {
      expect(latexToPlainSolution('2x+3=7'), '2x+3=7');
      expect(latexToPlainSolution('  x=2  '), 'x=2');
    });

    test('유니코드 부호는 그대로 통과한다(백엔드 to_sympy_source가 정규화)', () {
      // U+2212(−)·×·÷ 는 백엔드가 ASCII로 접으므로 클라가 손대지 않는다.
      expect(latexToPlainSolution('2x−3=7'), '2x−3=7');
    });

    test('간격 매크로·정렬 기호는 제거된다', () {
      expect(latexToPlainSolution(r'2x\,+\,3=7'), '2x+3=7');
      expect(latexToPlainSolution(r'2x+3 &= 7'), '2x+3 = 7');
    });

    test('빈/공백 입력은 빈 문자열', () {
      expect(latexToPlainSolution(''), '');
      expect(latexToPlainSolution('   '), '');
      expect(latexToPlainSolution(r'\displaylines{  \\  }'), '');
    });

    test('\\begin{aligned} 환경 껍데기를 벗기고 행을 분해한다', () {
      expect(
        latexToPlainSolution(r'\begin{aligned} 2x+3=7 \\ 2x=4 \end{aligned}'),
        '2x+3=7\n2x=4',
      );
    });
  });
}
