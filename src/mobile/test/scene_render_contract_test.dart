// SceneRenderer.webViewTypes ↔ data/render_contract.json 결선 게이트 — 모바일 측(MOB-14 ③).
//
// `docs/architecture/dsl_integration_gap_review.md`가 실측한 잔여: `scene_renderer.dart:107`의
// 하드코딩 `webViewTypes`(대화형 WebView로 렌더할 `Visualization.type` 집합)가 공유 계약
// `data/render_contract.json`(invariant ⑩ 렌더 선택 단일 진실원)과 *결선되지 않았다* — 백엔드
// (`test_render_contract.py`)·웹(`render_contract.test.js`)은 이미 이 계약을 소비하지만 Flutter
// 잔여 1/3이 비어 있었다.
//
// 결선 방식: 이 위젯은 단순 kind 분기 위젯이라 프로덕션 코드에 파일 I/O(런타임 JSON 로드)를
// 넣는 건 과공학이다(segmentation_contract_test.dart가 확립한 관례 — 런타임 자산 번들링이
// 아니라 *테스트 시점* 교차검증). `SceneRenderer.webViewTypes`를 `@visibleForTesting`로 노출해
// 이 테스트가 계약 파일의 `interactive: true` 키 집합과 정확히 일치하는지 동결한다.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';

/// 계약 JSON을 리포 루트 기준(`data/render_contract.json`)으로 로드한다.
///
/// `flutter test`의 cwd는 `src/mobile`이므로(governance 테스트 선례) 상대경로는
/// `../../data/render_contract.json`. 조용한 skip 대신 명확한 에러로 실패시킨다(CLAUDE.md
/// "검증 없는 실행 안내 금지"의 테스트판 — segmentation_contract_test.dart 답습).
Map<String, dynamic> _loadContract() {
  const String relPath = '../../data/render_contract.json';
  final File file = File(relPath);
  if (!file.existsSync()) {
    fail(
      '렌더 계약 파일을 찾지 못했습니다: ${file.absolute.path}\n'
      '(flutter test의 cwd는 src/mobile이어야 합니다 — 리포 루트에서 '
      '`cd src/mobile && flutter test test/scene_render_contract_test.dart`로 실행하세요.)',
    );
  }
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

void main() {
  final Map<String, dynamic> contract = _loadContract();
  final Map<String, dynamic> renderers = contract['renderers'] as Map<String, dynamic>;

  group('렌더 계약 (data/render_contract.json ↔ scene_renderer.dart webViewTypes)', () {
    test('계약이 4종 렌더러를 선언한다(정의 자체의 변별력 하한)', () {
      // 계약이 텅 비면 아래 등식 비교가 "우연히 통과"할 수 있다 — CLAUDE.md "측정 없는 게이트"
      // 축과 동형인 최소 하한.
      expect(renderers.keys, hasLength(4));
    });

    test('SceneRenderer.webViewTypes == 계약상 interactive:true 타입 집합', () {
      final Set<String> interactiveTypes = renderers.entries
          .where((entry) => (entry.value as Map<String, dynamic>)['interactive'] == true)
          .map((entry) => entry.key)
          .toSet();

      expect(SceneRenderer.webViewTypes, interactiveTypes);
    });

    test('animation_prerendered는 webViewTypes에 없다(계약상 interactive:false)', () {
      // 위 등식 테스트로 이미 함의되지만, "왜 제외됐는지"를 명시적으로 이름 붙여 고정한다
      // (코어 Visualization._prerendered_not_interactive 불변식과 정합).
      expect(
        renderers['animation_prerendered']?['interactive'],
        isFalse,
        reason: '계약이 이 전제를 바꾸면 위 등식 테스트가 먼저 잡아야 한다',
      );
      expect(SceneRenderer.webViewTypes.contains('animation_prerendered'), isFalse);
    });
  });
}
