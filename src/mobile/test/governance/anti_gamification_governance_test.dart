// L5 클라이언트 반게임화(anti-gamification) 거버넌스 게이트 (ARCH-26)
//
// 불변식(`docs/design/ui/00_index.md:41` 전역 UI 불변식 #2 · CLAUDE.md:33/106):
// "정답률 랭킹·스트릭·카운트다운·보상 연출 금지" — 도파민 유발형 게임화 UI는
// 이 프로젝트의 헌법상 하드 제약이다. 이 테스트는 그 규범을 소스 전수 스캔으로
// 동결한다 (`no_math_logic_governance_test.dart`(ARCH-10) 패턴 재사용).
//
// 정밀도 원칙: 발화 카테고리 라벨 등 정당한 UI 심볼은 금지하지 않는다.
// 예: `_SocraticBadge`(chat_screen.dart) — 소크라테스 대화 카테고리 칩이며
// 게임화 배지가 아니다. 금지 대상은 게임화 *개념*을 직접 지칭하는 합성어
// 식별자(`XpPoints`·`LevelUp`·`BadgeEarned`·`QuestUnlock`·`Leaderboard`·
// `StreakCounter`·`DailyStreak`·`CoinReward` 류)의 등장 자체이며, 단순
// substring이 아니라 `\b` 단어 경계 + 호출/식별자 형태로 좁혀 오탐을 방지한다.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 게임화 개념 식별자 — lib 어디에도 등장 금지 (선언·호출·타입 참조 모두 위반).
/// 합성어 경계로 좁혀 정당한 단일어(question·level(신뢰수준) 등)를 자연히 피한다.
/// `caseSensitive: false` — Dart 관례상 타입은 PascalCase(`BadgeEarnedEvent`),
/// 함수·변수는 camelCase(`badgeEarnedShow`)로 같은 합성어가 등장하므로 선행 대문자
/// 유무와 무관하게 잡아야 한다(대소문자 구분 시 camelCase 유입을 놓치는 실측 회귀 확인 후 수정).
final List<RegExp> _forbiddenGamificationIdentifiers = <RegExp>[
  RegExp(r'\bxpPoints?\b', caseSensitive: false),
  RegExp(r'\blevelUp\w*\b', caseSensitive: false),
  RegExp(r'\bbadgeEarned\w*\b', caseSensitive: false),
  RegExp(r'\bquestUnlock\w*\b', caseSensitive: false),
  RegExp(r'\bleaderboard\w*\b', caseSensitive: false),
  RegExp(r'\bstreakCounter\w*\b', caseSensitive: false),
  RegExp(r'\bdailyStreak\w*\b', caseSensitive: false),
  RegExp(r'\bcoinReward\w*\b', caseSensitive: false),
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
  group('L5 반게임화 거버넌스 (ARCH-26)', () {
    test('게임화 개념 식별자가 lib 어디에도 없다 (0건 동결)', () {
      final List<String> violations = <String>[];
      for (final File file in _libDartFiles()) {
        final String source = file.readAsStringSync();
        for (final RegExp pattern in _forbiddenGamificationIdentifiers) {
          if (pattern.hasMatch(source)) {
            violations.add('${file.path}: ${pattern.pattern}');
          }
        }
      }
      expect(
        violations,
        isEmpty,
        reason:
            '정답률 랭킹·스트릭·카운트다운·보상 연출형 게임화 UI 유입 금지 '
            '(docs/design/ui/00_index.md 전역 UI 불변식 #2 · CLAUDE.md). '
            '위반: $violations',
      );
    });

    test('정당한 발화 카테고리 라벨(_SocraticBadge)은 금지 패턴에 걸리지 않는다', () {
      final File chatScreen = File(
        'lib/features/chat/presentation/chat_screen.dart',
      );
      expect(
        chatScreen.existsSync(),
        isTrue,
        reason: '오탐 회귀 확인 대상 파일이 이동/삭제됨 — 테스트 경로 갱신 필요',
      );
      final String source = chatScreen.readAsStringSync();

      // _SocraticBadge 자체는 존재해야 함 (정당 심볼 실재 확인)
      expect(
        source.contains('_SocraticBadge'),
        isTrue,
        reason: '정당 심볼 _SocraticBadge가 사라짐 — 오탐 회귀 테스트 전제 무효',
      );

      // 그럼에도 금지 패턴에는 걸리지 않아야 함 (오탐 0건)
      for (final RegExp pattern in _forbiddenGamificationIdentifiers) {
        expect(
          pattern.hasMatch(source),
          isFalse,
          reason:
              'chat_screen.dart의 정당한 발화 카테고리 라벨이 '
              '게임화 금지 패턴(${pattern.pattern})에 오탐됨',
        );
      }
    });

    test('스캔 대상이 비어 있지 않다 (게이트 자체 무력화 방지)', () {
      // lib가 이동/개명되면 위 테스트들이 공허하게 green이 되는 것을 차단
      expect(
        _libDartFiles().length,
        greaterThan(30),
        reason: 'lib/**/*.dart 스캔 결과가 비정상적으로 적음 — 게이트 경로 확인 필요',
      );
    });
  });
}
