// latexToPlainSolution 단위 테스트 (MOB-06) — MathLive LaTeX→평문 수식 변환 동결.
//
// 순수 함수라 WebView·위젯 없이 검증한다(`normalizeLatexInput` 선례). 최상위 계약:
// ① 여러 줄(`\displaylines{... \\ ...}`)이 `'\n'` 구분 여러 스텝으로 분해된다(verify 전이 생성).
// ② LaTeX 원문이 남지 않는다(백슬래시 명령·중괄호 제거) — 학생 버블 평문 노출.
// ③ caret-less 지수(`x2`)를 절대 만들지 않는다(백엔드가 수열 표기와 모호해 보수 처리).
// 타깃 표기는 백엔드 `to_sympy_source`가 받는 자연 평문(ASCII 연산자·`^`·암묵곱·`=`·유니코드 부호).
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/domain/latex_to_plain.dart';

/// 표기 계약 fixture 로드 — 백엔드 `l3/latex_to_plain`·웹 `latexToMath`와 **같은 파일**을 읽는다.
///
/// `flutter test`의 cwd는 패키지 루트(`src/mobile`)이므로 리포 루트 기준 상대경로가 성립한다
/// (`segmentation_contract_test.dart`·`scene_contract_test.dart` 선례와 동일 패턴).
/// 부재는 **조용한 skip이 아니라 실패**다 — fixture가 사라지면 계약이 사라진 것이고, 그때
/// green으로 보이면 그건 검증이 아니라 위장이다(CLAUDE.md).
Map<String, dynamic> _loadContract() {
  const String relPath = '../../data/notation_contract.json';
  final File file = File(relPath);
  if (!file.existsSync()) {
    fail(
      '표기 계약 파일을 찾지 못했습니다: ${file.absolute.path}\n'
      '(flutter test의 cwd는 src/mobile이어야 합니다 — `cd src/mobile && flutter test`)',
    );
  }
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

void main() {
  // MATH-01 ③ — LaTeX→평문 3자 교차 골든의 Dart 몫.
  //
  // 백엔드 `l3/symbolic_equivalence.latex_to_plain`이 같은 `latex`에 대해 같은 `plain`을 내는지를
  // 파이썬 측 `test_latex_to_plain_matches_contract`가 단언한다. 이 그룹이 Dart 측 대응물이며,
  // 둘이 같은 파일을 읽으므로 한쪽 규칙이 바뀌면 계약을 고치지 않는 한 반대편이 red가 된다
  // (드리프트 동결). 웹은 렌더 전용이라 문자열이 아니라 mathjs 수치로 같은 fixture를 검증한다.
  group('표기 계약 골든 (data/notation_contract.json ↔ latexToPlainSolution)', () {
    final Map<String, dynamic> contract = _loadContract();
    final List<dynamic> cases = contract['latex_cases'] as List<dynamic>;

    test('계약에 latex_cases가 실재한다 — 블록이 사라지면 아래 골든이 조용히 0건이 된다', () {
      // 빈 리스트면 for 루프가 테스트를 0개 만들고 그룹이 green이 된다 — 침묵 통과 방지 단언.
      expect(cases, isNotEmpty);
    });

    for (final dynamic raw in cases) {
      final Map<String, dynamic> c = raw as Map<String, dynamic>;
      final String id = c['id'] as String;
      test('$id: ${c['latex']}', () {
        expect(
          latexToPlainSolution(c['latex'] as String),
          c['plain'] as String,
          reason: '$id — 백엔드 latex_to_plain과 산출이 갈리면 표기 권위가 이원화된다',
        );
      });
    }
  });

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

    test('지수는 캐럿·그룹을 보존한다 — caret-less(x2) 금지', () {
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
