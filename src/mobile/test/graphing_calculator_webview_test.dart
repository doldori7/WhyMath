// encodeGraph2dSpecParam 단위 테스트 — Graph2dSpec(Map)→웹 ?spec= 호환 base64(JSON) 인코딩.
//
// WebView 자체(플랫폼 뷰)는 헤드리스 flutter test에서 렌더 불가라 pump하지 않는다 — 여기선
// Flutter·네트워크 무관한 순수 인코더만 검증한다(웹 parseSpecParam(atob→JSON.parse) 호환 보장).
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/presentation/graphing_calculator_webview.dart';

void main() {
  group('encodeGraph2dSpecParam', () {
    test('Graph2dSpec → 표준 base64(JSON) 왕복 디코드', () {
      final spec = <String, dynamic>{
        'function': 'a*x**2+b*x+c',
        'domain': <int>[-5, 5],
      };
      final param = encodeGraph2dSpecParam(spec);
      final decoded = jsonDecode(utf8.decode(base64.decode(param)));
      expect(decoded, spec);
    });

    test('compact JSON(공백 없음)으로 인코딩한다(웹 atob 호환)', () {
      final param = encodeGraph2dSpecParam(<String, dynamic>{'function': 'x**2'});
      expect(utf8.decode(base64.decode(param)), '{"function":"x**2"}');
    });

    test('빈 spec도 안전하게 인코딩한다', () {
      expect(encodeGraph2dSpecParam(const <String, dynamic>{}), base64.encode(utf8.encode('{}')));
    });
  });

  group('encodeVisualizationParam — {type, spec} 봉투(invariant ⑩)', () {
    test('type+spec 봉투로 왕복 디코드(웹 unwrapSpecEnvelope 호환)', () {
      final viz = Visualization(
        type: 'interactive_graph_2d',
        spec: <String, dynamic>{'function': 'a*x**2'},
      );
      final param = encodeVisualizationParam(viz);
      final decoded = jsonDecode(utf8.decode(base64.decode(param)));
      expect(decoded, <String, dynamic>{
        'type': 'interactive_graph_2d',
        'spec': <String, dynamic>{'function': 'a*x**2'},
      });
    });

    test('spec 없는 시각화도 안전(빈 spec 봉투)', () {
      final viz = Visualization(type: 'simulation_probabilistic');
      final decoded = jsonDecode(utf8.decode(base64.decode(encodeVisualizationParam(viz))));
      expect(decoded['type'], 'simulation_probabilistic');
      expect(decoded['spec'], <String, dynamic>{});
    });

    test('compact JSON(공백 없음)으로 인코딩(웹 atob 호환)', () {
      final viz = Visualization(
        type: 'interactive_surface_3d',
        spec: <String, dynamic>{'surface': 'x+y'},
      );
      expect(
        utf8.decode(base64.decode(encodeVisualizationParam(viz))),
        '{"type":"interactive_surface_3d","spec":{"surface":"x+y"}}',
      );
    });

    test('spec-only 인코더는 봉투와 별개로 존치(공유 링크 하위호환)', () {
      // encodeGraph2dSpecParam은 여전히 spec-only(공개 ?spec= 계약) — 봉투와 형식이 다르다.
      final specOnly = utf8.decode(
        base64.decode(encodeGraph2dSpecParam(<String, dynamic>{'function': 'x'})),
      );
      expect(specOnly, '{"function":"x"}');
    });
  });

  group('decodeInteractionMessage', () {
    test('유효한 상호작용 JSON → Map', () {
      final raw = jsonEncode({
        'type': 'param_change',
        'payload': {'name': 'a', 'value': 2},
        'at': 123,
      });
      final event = decodeInteractionMessage(raw);
      expect(event, isNotNull);
      expect(event!['type'], 'param_change');
      expect(event['payload'], {'name': 'a', 'value': 2});
    });

    test('type이 문자열이 아니면 null', () {
      expect(decodeInteractionMessage('{"type": 42}'), isNull);
    });

    test('JSON 객체가 아니면 null(배열·원시값)', () {
      expect(decodeInteractionMessage('[1, 2, 3]'), isNull);
      expect(decodeInteractionMessage('"just a string"'), isNull);
    });

    test('깨진 JSON은 흡수하고 null', () {
      expect(decodeInteractionMessage('not json'), isNull);
      expect(decodeInteractionMessage(''), isNull);
    });
  });
}
