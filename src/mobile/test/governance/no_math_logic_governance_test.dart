// L5 클라이언트 무-수학로직 거버넌스 게이트 (ARCH-10 · 감사 갭 A 상환)
//
// 불변식(CLAUDE.md 슬라이스 89): "수학 로직을 클라에 넣지 않는다" — 채점·정오 판정·
// 수식 동치·오개념 매칭의 단일 권위는 백엔드(L1~L4 독립 코어)이며, 클라이언트는
// API 호출 + 렌더만 담당한다. 이 테스트는 그 규범을 소스 전수 스캔으로 동결한다
// (backend `test_scene_dsl_layer_governance.py` 금지 토큰 방식의 Dart판).
//
// 정밀도 원칙: 백엔드 판정 결과를 *수신*하는 필드(is_correct·misconception_id 등)는
// 로직이 아니므로 금지하지 않는다. 금지 대상은 (a) 판정 로직 식별자의 등장 자체
// (현재 lib에 0건 — 등장 = 유입 신호), (b) 수식 평가 패키지 import,
// (c) Problem 모델의 정답 계열 필드 선언이다.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 판정 로직 식별자 — lib 어디에도 등장 금지 (선언이든 호출이든 유입 자체가 위반).
/// 현재 실측 0건이므로 전수 부재를 동결한다.
final List<RegExp> _forbiddenJudgementIdentifiers = <RegExp>[
  RegExp(r'\bcheckAnswer\w*\s*\('),
  RegExp(r'\bgradeAnswer\w*\s*\('),
  RegExp(r'\bscoreAnswer\w*\s*\('),
  RegExp(r'\bisAnswerCorrect\w*\s*\('),
  RegExp(r'\bjudgeCorrect\w*\s*\('),
  RegExp(r'\bsameGraph\s*\('), // 웹 계산기 QuizMode의 채점 심볼 — Dart 유입 금지
  RegExp(r'\bdiagnoseMisconception\w*\s*\('),
  RegExp(r'\bmatchMisconception\w*\s*\('),
];

/// 수식 평가/CAS 패키지 — 클라 로컬 수식 판정의 기반이 되므로 import 금지.
final List<RegExp> _forbiddenMathPackages = <RegExp>[
  RegExp("import\\s+'package:math_expressions/"),
  RegExp("import\\s+'package:petitparser/"),
  RegExp("import\\s+'package:function_tree/"),
  RegExp("import\\s+'package:expressions/"),
];

/// Problem 모델 정답 계열 금지 키 — 서버가 보내더라도 모델 미선언으로 구조 차단
/// (기존 런타임 앵커 problems_api_test.dart의 소스 레벨 이중화).
/// 주의: `answer_format`(렌더 힌트)은 합법 — 정확히 아래 5종만 금지.
const List<String> _forbiddenAnswerJsonKeys = <String>[
  'answer',
  'answer_explanation',
  'answer_constraint',
  'answer_transform',
  'multiple_answers',
];

List<File> _libDartFiles() {
  // 테스트 실행 cwd = src/mobile (flutter test 규약)
  final Directory lib = Directory('lib');
  return lib
      .listSync(recursive: true)
      .whereType<File>()
      .where((File f) => f.path.endsWith('.dart'))
      .toList()
    ..sort((File a, File b) => a.path.compareTo(b.path));
}

void main() {
  group('L5 무-수학로직 거버넌스 (ARCH-10)', () {
    test('판정 로직 식별자가 lib 어디에도 없다 (0건 동결)', () {
      final List<String> violations = <String>[];
      for (final File file in _libDartFiles()) {
        final String source = file.readAsStringSync();
        for (final RegExp pattern in _forbiddenJudgementIdentifiers) {
          if (pattern.hasMatch(source)) {
            violations.add('${file.path}: ${pattern.pattern}');
          }
        }
      }
      expect(
        violations,
        isEmpty,
        reason: '클라이언트에 채점/판정 로직 유입 금지 — 판정은 백엔드 verify(L3) 호출로. '
            '위반: $violations',
      );
    });

    test('수식 평가 패키지 import가 lib 어디에도 없다', () {
      final List<String> violations = <String>[];
      for (final File file in _libDartFiles()) {
        final String source = file.readAsStringSync();
        for (final RegExp pattern in _forbiddenMathPackages) {
          if (pattern.hasMatch(source)) {
            violations.add('${file.path}: ${pattern.pattern}');
          }
        }
      }
      expect(
        violations,
        isEmpty,
        reason: '수식 동치의 단일 권위는 백엔드 SymPy(L3) — 클라 CAS 도입 금지. '
            '위반: $violations',
      );
    });

    test('Problem 모델 소스에 정답 계열 필드 선언이 없다 (answer_format은 합법)', () {
      final String source =
          File('lib/features/problems/data/problem_models.dart')
              .readAsStringSync();
      for (final String key in _forbiddenAnswerJsonKeys) {
        // JsonKey(name: '<금지 키>') 선언 — 정확 일치만 (answer_format 오탐 방지)
        expect(
          RegExp("@JsonKey\\(name:\\s*'$key'\\)").hasMatch(source),
          isFalse,
          reason: "Problem 모델은 '$key'를 선언하지 않는다 — 미선언 = 정답 구조 차단",
        );
      }
      // camelCase 필드 선언도 차단 (JsonKey 없이 암시 매핑되는 경로)
      for (final String field in <String>[
        'answer,',
        'answer;',
        'answerExplanation',
        'answerConstraint',
        'answerTransform',
        'multipleAnswers',
      ]) {
        expect(
          RegExp('\\b(?:String|dynamic|Object|List<[^>]*>)\\??\\s+$field')
              .hasMatch(source),
          isFalse,
          reason: 'Problem 모델에 정답 파생 필드($field) 선언 금지',
        );
      }
    });

    test('스캔 대상이 비어 있지 않다 (게이트 자체 무력화 방지)', () {
      // lib가 이동/개명되면 위 테스트들이 공허하게 green이 되는 것을 차단
      expect(_libDartFiles().length, greaterThan(30),
          reason: 'lib/**/*.dart 스캔 결과가 비정상적으로 적음 — 게이트 경로 확인 필요');
    });
  });
}
