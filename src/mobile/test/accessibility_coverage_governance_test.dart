// 접근성 커버리지 드리프트 가드 — 게이트 대상 ↔ 실제 화면 목록 대조 (A11Y-02).
//
// 배경(`service_operations_gap_review_r2.md` §2 G3 실측): `A11Y-01`이 WCAG 2.1 AA를 목표로
// *선언*한 직후 커버리지가 5개(explore/home/me + SceneRenderer·CoachSignalCard)에 고정됐다.
// 그 사이 화면은 16개로 늘었고, 주 학습 화면(chat·problem)과 `RPT-01`이 새로 만든 신고
// 다이얼로그가 게이트 밖으로 태어났는데 **아무 검사도 반응하지 않았다**.
//
// 이 가드의 목적은 "지금 전부 검증"이 아니다 — 16개 전수 편입은 과도하고(로그인·온보딩은
// 노출 빈도가 낮고 WebView 계열은 위젯 테스트로 내부 접근성을 볼 수 없다), 필요한 것은
// **어디까지 검증했는지가 기계로 고정되고 새 화면이 조용히 늘지 않는 것**이다. 미등록 화면은
// 반드시 아래 허용목록에 *사유와 함께* 올려야 통과한다(근거 없는 포괄 허용 금지 —
// `pubspec_dependency_usage_governance_test.dart` 허용목록 관용구 답습).
//
// 운영 r3 D9가 명명한 "정직 표기는 침묵 통과는 막지만 영구 미상환은 막지 못한다"에 대한
// 접근성 평면의 답이다 — 표기(06_design_system §7)는 사람이 읽고, 이 파일은 기계가 읽는다.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 접근성 스위트 파일 — 이 파일이 순회하는 대상이 곧 "검증된 커버리지"다.
const String _accessibilitySuitePath = 'test/accessibility_test.dart';

/// 화면 위젯이 사는 디렉터리 패턴 — `lib/features/*/presentation/`.
const String _presentationGlobRoot = 'lib/features';

/// 접근성 게이트에서 *의도적으로* 제외한 화면 — 각 항목은 "왜 제외가 합법인가"를 반드시
/// 병기한다. 근거 없는 포괄 허용 금지. 제외 사유가 소멸하면(예: WebView를 위젯 테스트로
/// 검증할 방법이 생기면) 이 목록에서 빼고 게이트에 편입한다.
const Map<String, String> _exemptScreens = <String, String>{
  'login_screen.dart':
      '네이버 브랜드색(초록 배경+흰 글자·≈2.3:1)이 사업자 규정색 예외라 대비 가드를 '
      '구조적으로 통과할 수 없다(brand_colors.dart·accessibility_test.dart 상단 주석). '
      '탭타깃·라벨만 별도 검증하는 것은 A11Y-02 범위 밖(login_screen_test.dart가 동작을 커버).',
  'mathlive_input_webview.dart':
      'WebView 래퍼 — 접근성 트리가 플랫폼 뷰 안에 있어 위젯 테스트가 내부를 볼 수 없다. '
      '위젯 테스트로 넣으면 "검사했다"는 위장이 된다(변별력 없는 검증 스텝 금지).',
  'graphing_calculator_webview.dart':
      'WebView 래퍼 — 위와 동일(플랫폼 뷰 내부 접근성 트리 접근 불가).',
  'mathlive_input_screen.dart':
      'WebView(MathLive)를 감싸는 화면이라 검사 가능한 표면이 앱바·버튼뿐이고 본문은 '
      '플랫폼 뷰다. 편입 실익이 낮아 유보 — 트리거: 수식 입력이 파일럿에서 주 입력 '
      '경로가 되면 앱바·컨트롤 축만이라도 편입한다.',
  'ocr_capture_screen.dart':
      '06_design_system.md §7이 "인식 후 cue 상태 미검증"으로 정직 표기한 화면. 그 상태를 '
      '재현하려면 카메라·OCR 응답 하네스가 필요해 A11Y-02 범위 밖(r2 §3-⑤) — 트리거: OCR '
      '실기기 경로가 파일럿에서 실사용될 때.',
  'onboarding_screen.dart':
      '1회성 진입 화면(가입 직후 한 번) — 노출 빈도가 낮아 우선순위 밖. onboarding_test.dart가 '
      '동작을 커버한다. 트리거: 온보딩에 입력 위젯이 추가되면(현재 선택 위젯만) 편입.',
  'account_security_screen.dart':
      '설정 하위의 저빈도 화면. account_security_screen_test.dart가 동작·탭타깃 주석'
      '(44dp+ 요구·48dp 검사)을 커버한다. 트리거: 설정 화면군을 넓힐 때 일괄 편입.',
  'coach_emphasis_text.dart':
      '화면이 아니라 텍스트 렌더 위젯(강조 구간 파싱) — 자체 탭타깃·대비 표면이 없고 '
      '부모(chat_screen·CoachSignalCard) 검증에 포함된다. coach_emphasis_text_test.dart가 '
      '파싱 계약을 커버.',
};

/// `lib/features/*/presentation/*.dart` 전수 — 파일명만 돌려준다.
List<String> _presentationWidgetFiles() {
  final Directory features = Directory(_presentationGlobRoot);
  expect(
    features.existsSync(),
    isTrue,
    reason: '$_presentationGlobRoot 없음 — 테스트 실행 디렉터리가 src/mobile이 아닌 듯',
  );
  final List<String> names = <String>[];
  for (final FileSystemEntity entity in features.listSync()) {
    if (entity is! Directory) {
      continue;
    }
    final Directory presentation = Directory('${entity.path}/presentation');
    if (!presentation.existsSync()) {
      continue;
    }
    for (final FileSystemEntity file in presentation.listSync()) {
      if (file is File && file.path.endsWith('.dart')) {
        names.add(file.uri.pathSegments.last);
      }
    }
  }
  return names..sort();
}

/// 접근성 스위트가 import하는 `presentation/` 파일명 집합 — 실제 순회 대상의 근사가 아니라
/// *정확한* 상한이다(import하지 않은 위젯은 순회할 수 없다).
Set<String> _screensImportedBySuite() {
  final File suite = File(_accessibilitySuitePath);
  expect(suite.existsSync(), isTrue, reason: '$_accessibilitySuitePath 없음');
  final RegExp importRe = RegExp(
    r"import\s+'package:korean_math_app/features/[^']*/presentation/([A-Za-z0-9_]+\.dart)'",
  );
  return importRe
      .allMatches(suite.readAsStringSync())
      .map((RegExpMatch m) => m.group(1)!)
      .toSet();
}

void main() {
  group('접근성 커버리지 드리프트 가드 (A11Y-02)', () {
    test('모든 presentation 위젯은 접근성 게이트에 있거나 사유가 달린 허용목록에 있다', () {
      final List<String> all = _presentationWidgetFiles();
      final Set<String> covered = _screensImportedBySuite();

      final List<String> undeclared = all
          .where((String f) => !covered.contains(f) && !_exemptScreens.containsKey(f))
          .toList();

      expect(
        undeclared,
        isEmpty,
        reason:
            '접근성 게이트에도 없고 허용목록에도 없는 위젯: $undeclared\n'
            '→ test/accessibility_test.dart에 편입하거나, '
            'accessibility_coverage_governance_test.dart의 _exemptScreens에 '
            '**제외 사유를 병기해** 등재하세요. 새 화면이 조용히 게이트 밖으로 늘어나는 것을 '
            '막는 가드입니다(A11Y-02).',
      );
    });

    test('허용목록은 실재하는 파일만 담는다 — 삭제·개명된 항목은 즉시 걷힌다', () {
      final Set<String> all = _presentationWidgetFiles().toSet();
      final List<String> stale =
          _exemptScreens.keys.where((String f) => !all.contains(f)).toList();

      expect(
        stale,
        isEmpty,
        reason:
            '허용목록에 있으나 실재하지 않는 파일: $stale\n'
            '→ 삭제·개명됐다면 _exemptScreens에서 빼세요. 죽은 허용 항목은 다음 세션에 '
            '"이미 검토된 제외"로 오독됩니다.',
      );
    });

    test('허용목록의 모든 사유는 비어있지 않다 — 근거 없는 포괄 허용 금지', () {
      for (final MapEntry<String, String> e in _exemptScreens.entries) {
        expect(
          e.value.trim().length,
          greaterThan(30),
          reason: '${e.key}의 제외 사유가 너무 짧다(근거로 읽히지 않는다): "${e.value}"',
        );
      }
    });

    test('게이트 대상과 허용목록은 겹치지 않는다 — 한 위젯이 양쪽에 있으면 판정이 모순', () {
      final Set<String> covered = _screensImportedBySuite();
      final List<String> both =
          _exemptScreens.keys.where(covered.contains).toList();

      expect(
        both,
        isEmpty,
        reason:
            '게이트에 편입됐는데 허용목록에도 남아 있는 위젯: $both\n'
            '→ 편입했다면 _exemptScreens에서 빼세요(제외 사유가 이미 무효).',
      );
    });
  });
}
