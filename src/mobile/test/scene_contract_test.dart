// scene DSL 서버↔클라 계약 게이트 — 모바일 측 절반(MOB-14).
//
// `docs/architecture/dsl_integration_gap_review.md` §2-④ 실측: scene 응답의 서버↔Dart 계약
// 게이트가 0건이라(`scene_models.dart`를 참조하는 백엔드·크로스 테스트 0건), Dart
// `json_serializable`이 미지 키를 조용히 무시해 필드 드리프트 4건이 런타임 파손 없이 CI를
// 통과했다. 이 파일이 그 게이트의 모바일 절반이다(백엔드 절반 =
// `tests/backend/l4/test_scene_contract.py` — 둘이 합쳐 "코어 필드 ↔ 클라 파서 필드" drift를
// 막는다·`render_contract`·`notation_contract` 선례).
//
// 접근 방법: `@JsonKey` 애노테이션 이름을 정적으로 읽는 리플렉션은 Flutter에 없으므로, 각 모델의
// *최소 유효 인스턴스*를 만들어 `toJson()`을 호출하고 그 결과 Map의 key 집합을 계약과 비교한다.
// 이 모델들은 `includeIfNull` 미지정(기본값)이라 `toJson()`이 값이 null인 필드도 키로 포함한다
// (freezed .g.dart 실측 확인) — 즉 `toJson().keys`가 "이 모델이 실제로 직렬화하는 키 전체
// 집합"의 정확한 대조군이다. `SceneElement`는 백엔드 8종 kind를 단일 flat 모델로 받으므로
// (판별 유니온 표현 방침·scene_models.dart 상단 주석), 계약의 `scene_elements`가 나눠 선언한
// kind별 필드를 여기서는 합집합으로 모아 대조한다.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';

/// 계약 JSON을 리포 루트 기준(`data/scene_contract.json`)으로 로드한다.
///
/// `flutter test`의 cwd는 `src/mobile`이므로(governance 테스트 선례) 상대경로는
/// `../../data/scene_contract.json`. 조용한 skip 대신 명확한 에러로 실패시킨다(CLAUDE.md
/// "검증 없는 실행 안내 금지"의 테스트판 — segmentation_contract_test.dart 답습).
Map<String, dynamic> _loadContract() {
  const String relPath = '../../data/scene_contract.json';
  final File file = File(relPath);
  if (!file.existsSync()) {
    fail(
      'scene 계약 파일을 찾지 못했습니다: ${file.absolute.path}\n'
      '(flutter test의 cwd는 src/mobile이어야 합니다 — 리포 루트에서 '
      '`cd src/mobile && flutter test test/scene_contract_test.dart`로 실행하세요.)',
    );
  }
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

void main() {
  final Map<String, dynamic> contract = _loadContract();
  final Map<String, dynamic> models = contract['models'] as Map<String, dynamic>;
  final Map<String, dynamic> sceneElements =
      contract['scene_elements'] as Map<String, dynamic>;

  Set<String> fieldsOf(String modelName) =>
      (models[modelName] as List<dynamic>).cast<String>().toSet();

  group('scene 계약 (data/scene_contract.json ↔ scene_models.dart)', () {
    test('Visualization.toJson() 키 집합 == 계약', () {
      const Visualization viz = Visualization(type: 'interactive_graph_2d');
      expect(viz.toJson().keys.toSet(), fieldsOf('Visualization'));
    });

    test('SceneLearnerContext.toJson() 키 집합 == 계약', () {
      const SceneLearnerContext ctx = SceneLearnerContext();
      expect(ctx.toJson().keys.toSet(), fieldsOf('SceneLearnerContext'));
    });

    test('LearningScene.toJson() 키 집합 == 계약', () {
      const LearningScene scene = LearningScene(
        sceneId: 's1',
        conceptId: 'c1',
        layout: 'single',
        answerDeferralMaxLevel: 1,
      );
      expect(scene.toJson().keys.toSet(), fieldsOf('LearningScene'));
    });

    test('SceneElement.toJson() 키 집합 == 계약 8종 kind 필드의 합집합', () {
      // 백엔드는 kind별 판별 유니온 8종이지만 Dart는 단일 flat 모델(scene_models.dart 상단
      // 주석의 명시된 표현 방침) — 계약의 kind별 목록을 합집합으로 모아 대조한다.
      final Set<String> expected = <String>{};
      for (final dynamic fields in sceneElements.values) {
        expected.addAll((fields as List<dynamic>).cast<String>());
      }
      const SceneElement element = SceneElement(kind: 'visualization');
      expect(element.toJson().keys.toSet(), expected);
    });

    test('계약이 8종 kind를 모두 선언한다(정의 자체의 변별력 하한)', () {
      // 계약 파일이 텅 비어도 위 합집합 비교가 "우연히 통과"하지 않도록 하한을 명시한다
      // (CLAUDE.md "측정 없는 게이트" 축과 동형 — 최소 8개 kind가 있어야 진짜 대조다).
      expect(sceneElements.keys, hasLength(8));
    });
  });
}
