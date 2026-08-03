// pubspec.yaml 선언↔사용 거버넌스 게이트 (MOB-08 — TTS/STT 제거에 이은 2회차)
//
// 왜 이 테스트가 있는가
// --------------------
// firebase_messaging·firebase_core는 `pubspec.yaml`에 *선언*만 되고 `lib/`·`test/` 어디에도
// import 한 줄 없이 방치돼 있었다(google-services.json 0·Gradle 플러그인 미적용·ios/ 부재로
// 플랫폼 설정조차 안 걸림). speech_to_text·flutter_tts가 겪은 것과 완전히 같은 패턴("의존을
// 선언하고, 실제로 배선한 적은 없다")의 2회차 반복이다. 이 테스트는 그 패턴을 소스 전수
// 스캔으로 상시 동결한다(`test/governance/no_math_logic_governance_test.dart`의 금지 토큰
// 방식을 "허용목록 있는 선언↔사용 대응" 방식으로 변형).
//
// 검사 범위·방법
// --------------
// `pubspec.yaml`의 최상위 `dependencies:`(`dev_dependencies:`는 제외 — build_runner·
// flutter_lints 등은 설계상 lib/에서 "미사용"이 정상이라 대상이 아니다) 각 패키지가
// `lib/`·`test/` 아래 어느 `.dart` 파일에서든 `import 'package:<name>/...'` 또는
// `import 'package:<name>.dart'` 형태로 최소 1회 등장하는지만 확인한다("올바르게" 쓰였는지는
// 증명하지 않는다 — "등장했는지"만). 등장하지 않으면 아래 allowlist에 근거 주석과 함께
// 있어야 한다(SDK 결합·패키지 재노출 등 정당한 이유가 있는 소수만 — 포괄 허용 금지).
//
// 검증 계약
// --------
// ① lib/test에 import가 있는 의존은 통과, 없는 의존은 allowlist에 없으면 실패(정확히 어떤
//    패키지인지 나열).
// ② 파서가 위장하지 않는다 — `dependencies:` 블록을 못 찾거나 파싱 결과가 비면 조용한 통과가
//    아니라 예외로 실패한다.
// ③ 변별력 — 실제 미사용 문자열(제거된 firebase_messaging)은 실제로 "미검출"되고, 실제 사용
//    문자열(dio)은 실제로 "검출"된다(자동화된 반증 — 검출 로직 자체가 항상 같은 값을 내는
//    위장 검사가 아님을 확인).

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// `pubspec.yaml`의 최상위 `dependencies:` 블록(`dev_dependencies:` 등 다음 최상위 키 전까지)에서
/// 선언된 패키지명을 추출한다. SDK 의존(`flutter:\n    sdk: flutter`)도 이름만 뽑는다.
///
/// 블록을 못 찾거나 결과가 비면 조용히 넘어가지 않고 예외로 실패한다(위장 통과 차단 —
/// `tests/infra/test_app_version_pubspec_sync.py`의 "AssertionError 우선" 관용구의 Dart판).
List<String> _parsePubspecDependencyNames(String pubspecContent) {
  final List<String> lines = pubspecContent.split('\n');
  final int startIdx = lines.indexWhere((String l) => l == 'dependencies:');
  if (startIdx == -1) {
    throw StateError("pubspec.yaml에서 최상위 'dependencies:' 블록을 찾을 수 없다 — 파서 경로 확인 필요.");
  }
  int endIdx = lines.length;
  for (int i = startIdx + 1; i < lines.length; i++) {
    final String line = lines[i];
    // 들여쓰기 없는 비공백 줄 = 다음 최상위 키(dev_dependencies: 등) 등장 = 블록 종료.
    if (line.isNotEmpty && !line.startsWith(' ') && !line.startsWith('\t')) {
      endIdx = i;
      break;
    }
  }

  // 정확히 2-space 들여쓰기 + 식별자 + ':' 만 최상위 의존 키로 인정한다.
  // (4-space 이상 들여쓰기인 `sdk: flutter` 같은 하위 필드, `  # ...` 주석 줄은 자동 제외됨 —
  // 둘 다 이 패턴과 매치되지 않는다.)
  final RegExp topLevelKeyRe = RegExp(r'^  ([A-Za-z0-9_]+):');
  final List<String> names = <String>[];
  for (int i = startIdx + 1; i < endIdx; i++) {
    final Match? m = topLevelKeyRe.firstMatch(lines[i]);
    if (m != null) {
      names.add(m.group(1)!);
    }
  }

  if (names.isEmpty) {
    throw StateError(
      'dependencies 블록 파싱 결과가 비어있다 — 파서가 조용히 위장 통과하지 않도록 예외로 막는다.',
    );
  }
  return names;
}

/// `lib/`·`test/` 아래 모든 `.dart` 파일(재귀). 테스트 실행 cwd = src/mobile(flutter test 규약,
/// `no_math_logic_governance_test.dart`와 동형). CI 순서(pub get → build_runner → analyze →
/// test)상 이 시점엔 codegen 산출물(*.g.dart·*.freezed.dart)도 lib/에 이미 생성돼 있어 함께
/// 스캔된다 — freezed_annotation이 재노출하는 심볼(예: json_annotation)의 실사용 흔적이
/// 코드젠 산출물에 있다면 그것도 유효한 증거로 잡힌다.
List<File> _dartSourceFiles() {
  final List<File> files = <File>[];
  for (final String dirName in <String>['lib', 'test']) {
    final Directory dir = Directory(dirName);
    if (!dir.existsSync()) continue;
    files.addAll(
      dir
          .listSync(recursive: true)
          .whereType<File>()
          .where((File f) => f.path.endsWith('.dart')),
    );
  }
  return files;
}

/// `import 'package:<name>/...'` 또는 `import 'package:<name>.dart'` 형태(단일·이중 인용
/// 모두)를 잡는 패턴. "존재 등장"만 증거로 삼는다 — 올바른 사용 여부는 증명하지 않는다.
RegExp _importPattern(String packageName) {
  final String escaped = RegExp.escape(packageName);
  return RegExp("import\\s+['\"]package:$escaped(?:/|\\.dart['\"])");
}

bool _isPackageReferenced(RegExp pattern, List<File> sourceFiles) {
  for (final File f in sourceFiles) {
    if (pattern.hasMatch(f.readAsStringSync())) {
      return true;
    }
  }
  return false;
}

void main() {
  group('pubspec.yaml dependencies 선언↔사용 거버넌스 (MOB-08)', () {
    // SDK 결합·패키지 재노출 등으로 lib/test에 *직접* import가 없어도 합법인 항목만 명시한다.
    // 각 항목은 "왜 0인데도 합법인가"의 근거를 반드시 병기한다 — 근거 없는 포괄 허용 금지.
    const Map<String, String> allowlist = <String, String>{
      'flutter':
          'Flutter SDK 자체(map 형태 SDK 의존, `flutter:\\n    sdk: flutter`) — 문서화 목적으로 '
              '명시(실제로도 lib 전역에서 package:flutter/ import가 매우 흔하다).',
      'flutter_localizations':
          'SDK 의존 — pubspec.yaml의 `flutter:` `generate: true`(l10n) 결합용으로 선언되며 '
              'lib/test에 직접 import 없이 SDK 조합으로만 소비된다.',
      'intl':
          'flutter_localizations가 전이 의존(pubspec.yaml intl 항목 주석 — "앱 코드에서 직접 쓰지 '
              '않고 flutter_localizations가 전이 의존한다" — SDK 버전 격자를 맞추기 위한 선언).',
      'json_annotation':
          'freezed_annotation이 전체 재노출한다(freezed_annotation.dart가 '
              "export 'package:json_annotation/json_annotation.dart'; 를 포함). lib 전역의 "
              '@JsonKey 사용(예: lib/features/chat/data/scene_models.dart)은 이 재노출 경유이며 '
              'lib/test에 package:json_annotation/ 직접 import는 없다.',
    };

    // 위 allowlist와는 성격이 다르다 — "합법적으로 0"이 아니라 "이미 0이었고 아직 안 치웠다"는
    // 뜻이다. 이 게이트를 신설하며 firebase 2종 외에 5종이 이미 같은 패턴(선언만·사용처 0)으로
    // 방치돼 있음을 발견했으나, MOB-08의 acceptance는 firebase 2종 제거로 스코프가 한정돼 있어
    // 이 5종의 처분(제거 또는 실사용 착수)은 별도 태스크(MOB-09)로 분리했다. 여기 grandfather
    // 없이 그대로 뒀다면 이 신규 게이트 자체가 착지 첫날부터 CI red였을 것이다 — 그렇다고
    // allowlist에 "정당한 이유"로 섞어 넣으면 다음 사람이 "합법적 예외"로 오해한다. 각 항목은
    // 반드시 처분 태스크 id를 달아야 하며(ARCH-25 grandfather 관용구의 Dart판), MOB-09가
    // 완료되면 이 맵에서 해당 항목을 지워 allowlist와 혼동될 여지를 남기지 않는다.
    const Map<String, String> pendingRemovalGrandfather = <String, String>{
      'retrofit': 'MOB-09 — coach_api.dart가 수동 메서드를 채택해 codegen 미사용(정합 재확인 대상).',
      'cached_network_image': 'MOB-09 — lib/features/ 실 사용처 0.',
      'video_player': 'MOB-09 — lib/features/ 실 사용처 0.',
      'flutter_math_fork': 'MOB-09 — lib/features/ 실 사용처 0.',
      'fl_chart': 'MOB-09 — lib/features/ 실 사용처 0.',
    };

    test('dependencies 선언 패키지가 모두 사용되거나 허용목록/grandfather에 있다', () {
      final String pubspecContent = File('pubspec.yaml').readAsStringSync();
      final List<String> declared = _parsePubspecDependencyNames(pubspecContent);
      final List<File> sourceFiles = _dartSourceFiles();

      final List<String> violations = <String>[];
      for (final String pkg in declared) {
        if (allowlist.containsKey(pkg)) continue;
        if (pendingRemovalGrandfather.containsKey(pkg)) continue;
        if (!_isPackageReferenced(_importPattern(pkg), sourceFiles)) {
          violations.add(pkg);
        }
      }

      expect(
        violations,
        isEmpty,
        reason:
            '선언만 있고 lib/·test/ 사용처가 0인 의존: $violations — firebase_messaging·'
            'firebase_core 제거 전례(MOB-08)와 동일 패턴이다. 기능 착수 전이면 pubspec.yaml에서 '
            '제거하고 착수 시 재도입할 것. SDK 결합·재노출 등 정당한 이유로 합법인 경우에만 이 '
            '테스트의 allowlist에 근거 주석과 함께 추가할 것(포괄 허용 금지).',
      );
    });

    test('dependencies 파서가 dev_dependencies로 새지 않는다 (파서 경계 확인)', () {
      final String pubspecContent = File('pubspec.yaml').readAsStringSync();
      final List<String> declared = _parsePubspecDependencyNames(pubspecContent);
      // build_runner는 dev_dependencies 전용 — dependencies 파서 결과에 있으면 파서 경계 오류.
      expect(
        declared,
        isNot(contains('build_runner')),
        reason: 'dev_dependencies 전용 패키지가 dependencies 파서에 유입됐다 — 블록 경계 파싱 오류.',
      );
      // dio는 알려진 실제 최상위 의존 — 파서가 이를 못 찾으면 회귀.
      expect(
        declared,
        contains('dio'),
        reason: 'dependencies 파서가 알려진 실제 의존(dio)을 못 찾았다 — 파서 회귀.',
      );
    });

    test('스캔 대상이 비어 있지 않다 (게이트 자체 무력화 방지)', () {
      // lib·test가 이동/개명되면 위 테스트가 공허하게 green이 되는 것을 차단
      // (no_math_logic_governance_test.dart의 동형 가드).
      expect(
        _dartSourceFiles().length,
        greaterThan(30),
        reason: 'lib/test .dart 스캔 결과가 비정상적으로 적음 — 게이트 경로(cwd) 확인 필요',
      );
    });

    test('변별력 — 실제 미사용 문자열은 미검출, 실제 사용 문자열은 검출된다 (자동화된 반증)', () {
      final List<File> sourceFiles = _dartSourceFiles();

      // firebase_messaging은 MOB-08에서 pubspec.yaml에서 실제로 제거된 미사용 의존이었다.
      // 검출 로직이 이를 "사용됨"으로 오판하면(거짓 음성) 게이트 자체가 상시 무력화된다.
      expect(
        _isPackageReferenced(_importPattern('firebase_messaging'), sourceFiles),
        isFalse,
        reason:
            'firebase_messaging은 lib/test 어디에도 import가 없다(MOB-08 제거 전례) — 검출 로직이 '
            '이를 "사용됨"으로 오판하면 게이트가 무력화된다.',
      );

      // dio는 광범위하게 실사용되는 의존 — 검출 로직이 이를 "미사용"으로 오판하면(거짓 양성)
      // 게이트가 상시 red로 고장난다.
      expect(
        _isPackageReferenced(_importPattern('dio'), sourceFiles),
        isTrue,
        reason: 'dio는 실제로 광범위하게 사용되는 의존 — 검출 로직이 이를 "미사용"으로 오판했다.',
      );
    });
  });
}
