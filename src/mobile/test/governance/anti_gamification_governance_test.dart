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

/// 비교 파생(사회적 비교) 식별자 — 5원칙 #2 "남과 비교하지 않는다"의 클라측 기계 강제
/// (ARCH-27). 위 목록이 *게임 메커니즘* 축이라면 이쪽은 *서열·또래 대비* 축이다.
///
/// 파이썬 게이트(`tests/backend/l1/test_anti_gamification_governance.py`)와 같은 계약을
/// 클라에도 건다 — 서버만 막으면 클라가 자체 계산해 노출하는 경로가 열린다.
///
/// 설계 메모 두 가지:
///  ① `\b`를 앞에 두지 않는다. Dart `\b`는 밑줄을 단어문자로 보므로 `\bclassRank`는
///     `studentClassRank` 같은 더 큰 camelCase 식별자 *안*의 등장을 놓친다. 아래 합성어는
///     충분히 특이해서 우연한 부분일치가 없다(2026-08-09 실측: `lib/**` 57파일에서 후보
///     단어를 포함한 식별자 **0종** — 오탐 여지가 애초에 없는 깨끗한 상태에서 건다).
///  ② `[_]?`로 camelCase(`classRank`)와 snake_case(`class_rank`)를 함께 잡는다. 후자는
///     서버 JSON 키가 문자열 리터럴로 클라에 들어오는 경로라 실제 유입 벡터다.
final List<RegExp> _forbiddenComparisonIdentifiers = <RegExp>[
  RegExp(
    r'peer[_]?(average|avg|mean|percentile|rank|ranking|score|comparison|compare)',
    caseSensitive: false,
  ),
  RegExp(
    r'(class|school|national|grade|cohort)[_]?(ranks?|rankings?)',
    caseSensitive: false,
  ),
  RegExp(
    r'(class|school|national|grade|cohort)[_]?(average|avg|mean)\b',
    caseSensitive: false,
  ),
  RegExp(r'percentile[_]?(ranks?|rankings?)', caseSensitive: false),
  RegExp(r'ranks?[_]?percentile', caseSensitive: false),
  RegExp(r'(top|upper|bottom)[_]?percent(ile)?\b', caseSensitive: false),
  RegExp(r'(better|worse)[_]?than', caseSensitive: false),
  RegExp(
    r'(compared|versus|vs)[_]?(to|with)?[_]?(peers?|average|others|classmates)',
    caseSensitive: false,
  ),
];

/// 두 목록의 합 — 스캔은 항상 전체를 돈다.
List<RegExp> get _allForbiddenIdentifiers => <RegExp>[
      ..._forbiddenGamificationIdentifiers,
      ..._forbiddenComparisonIdentifiers,
    ];

/// 비교 파생 게이트의 변별력 고정 — 이 문자열들이 잡히지 않으면 게이트는 위장이다.
const List<String> _comparisonTruePositives = <String>[
  'classRank',
  'class_rank',
  'peerAverage',
  'peer_average_score',
  'percentileRank',
  'topPercentile',
  'betterThan',
  'comparedToPeers',
  'vsAverage',
  'schoolRanking',
];

/// 정당 어휘 — red를 내면 안 된다(오탐 방어).
const List<String> _comparisonBenign = <String>[
  'className', // Flutter/JSON 관용
  'classroom',
  'topK', // 검색 상위 K
  'topLevel',
  'nationalStandardCode', // 성취기준 코드 — 전국 순위 아님
  'compareDigest',
  'timeVsExpected', // 예상 시간 대비 — 또래 대비 아님
  'percentile', // 단일어는 금지 대상 아님
  'rank',
  'peerReview',
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
        for (final RegExp pattern in _allForbiddenIdentifiers) {
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

    test('비교 파생 식별자가 lib 어디에도 없다 (ARCH-27 · 0건 동결)', () {
      final List<String> violations = <String>[];
      for (final File file in _libDartFiles()) {
        final String source = file.readAsStringSync();
        for (final RegExp pattern in _forbiddenComparisonIdentifiers) {
          if (pattern.hasMatch(source)) {
            violations.add('${file.path}: ${pattern.pattern}');
          }
        }
      }
      expect(
        violations,
        isEmpty,
        reason:
            '또래·집단 대비 비교 파생 유입 금지 (5원칙 #2 "남과 비교하지 않는다"). '
            '서버측 짝: tests/backend/l1/test_anti_gamification_governance.py. 위반: $violations',
      );
    });

    test('비교 파생 패턴이 실제 위반 문자열을 잡는다 (변별력 — 이게 없으면 위 검사는 위장)', () {
      for (final String sample in _comparisonTruePositives) {
        final bool caught = _forbiddenComparisonIdentifiers.any(
          (RegExp p) => p.hasMatch(sample),
        );
        expect(caught, isTrue, reason: '비교 파생 위반 "$sample"을 어떤 패턴도 잡지 못함');
      }
    });

    test('정당 어휘는 비교 파생 패턴에 오탐되지 않는다', () {
      for (final String sample in _comparisonBenign) {
        for (final RegExp p in _forbiddenComparisonIdentifiers) {
          expect(
            p.hasMatch(sample),
            isFalse,
            reason: '정당 어휘 "$sample"이 패턴(${p.pattern})에 오탐됨',
          );
        }
      }
    });
  });
}
