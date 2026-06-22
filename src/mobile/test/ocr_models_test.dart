// ocr_models 역직렬화·라운드트립·신뢰도 플래깅 테스트.
//
// 백엔드 `OcrResult` 샘플 JSON(한국어 content_type "텍스트"·"수식" 포함)을 `fromJson`으로
// 파싱해 필드를 단언하고, `toJson` 라운드트립으로 키·값 보존을 검증한다(백엔드 계약과 클라
// 모델의 비트 정합 게이트·coach_models_test 답습). 더불어 재확인 임계(0.8) 플래깅을 단언한다.
//
// 로컬 SDK 부재로 이 테스트는 CI Flutter 잡에서만 실행된다(build_runner codegen 후).
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/ocr/data/ocr_models.dart';

void main() {
  group('OcrResult.fromJson — 영역·집계·한국어 content_type 포함 샘플', () {
    // 백엔드 schema/ocr.py OcrResult 직렬화 형태를 모사한 샘플.
    // 텍스트 영역(고신뢰)·수식 영역(저신뢰) + 집계 필드(plain_latex·steps·step_types).
    Map<String, dynamic> sampleJson() => <String, dynamic>{
          'regions': <Map<String, dynamic>>[
            <String, dynamic>{
              'bbox': <String, dynamic>{
                'x': 10.0,
                'y': 20.0,
                'width': 100.0,
                'height': 30.0,
              },
              'content_type': '텍스트',
              'latex': '판별식을 구하면',
              'confidence': 0.95,
              'verified': null,
            },
            <String, dynamic>{
              'bbox': <String, dynamic>{
                'x': 10.0,
                'y': 60.0,
                'width': 120.0,
                'height': 40.0,
              },
              'content_type': '수식',
              'latex': r'D = b^2 - 4ac',
              'confidence': 0.62, // < 0.8 → 재확인 후보.
              'verified': true,
            },
          ],
          'plain_latex': r'판별식을 구하면 D = b^2 - 4ac',
          'solution_steps': <String>[r'D = b^2 - 4ac'],
          'solution_step_types': <String>[],
          'markdown': r'판별식을 구하면 $D = b^2 - 4ac$',
          'overall_confidence': 0.785, // 평균(<0.8).
          'min_confidence': 0.62,
        };

    test('영역·유형·집계 필드를 정확히 파싱한다', () {
      final res = OcrResult.fromJson(sampleJson());

      expect(res.regions, hasLength(2));
      // 텍스트 영역(한국어 enum 값 그대로).
      final text = res.regions[0];
      expect(text.contentType, '텍스트');
      expect(text.isText, isTrue);
      expect(text.isFormula, isFalse);
      expect(text.latex, '판별식을 구하면');
      expect(text.confidence, closeTo(0.95, 1e-9));
      expect(text.verified, isNull);
      expect(text.bbox.x, closeTo(10.0, 1e-9));
      expect(text.bbox.width, closeTo(100.0, 1e-9));

      // 수식 영역.
      final formula = res.regions[1];
      expect(formula.contentType, '수식');
      expect(formula.isFormula, isTrue);
      expect(formula.latex, r'D = b^2 - 4ac');
      expect(formula.verified, isTrue);

      // 집계.
      expect(res.plainLatex, r'판별식을 구하면 D = b^2 - 4ac');
      expect(res.solutionSteps, <String>[r'D = b^2 - 4ac']);
      expect(res.solutionStepTypes, isEmpty);
      expect(res.overallConfidence, closeTo(0.785, 1e-9));
      expect(res.minConfidence, closeTo(0.62, 1e-9));
    });

    test('toJson 라운드트립 — fromJson∘toJson 동치', () {
      final res = OcrResult.fromJson(sampleJson());
      final roundTripped = OcrResult.fromJson(res.toJson());
      // freezed 값 동치(==)로 라운드트립 보존을 단언한다.
      expect(roundTripped, equals(res));
    });
  });

  group('OcrResult.fromJson — 최소(빈 인식) 응답', () {
    test('필드가 비어도 기본값으로 안전 파싱한다', () {
      // 백엔드가 빈 인식을 내면 default_factory/0.0에 대응.
      final res = OcrResult.fromJson(<String, dynamic>{
        'regions': <Map<String, dynamic>>[],
        'plain_latex': '',
        'solution_steps': <String>[],
        'solution_step_types': <String>[],
        'markdown': '',
        'overall_confidence': 0.0,
        'min_confidence': 0.0,
      });

      expect(res.regions, isEmpty);
      expect(res.plainLatex, '');
      expect(res.solutionSteps, isEmpty);
      expect(res.overallConfidence, 0.0);
    });

    test('키가 아예 누락돼도 기본값으로 파싱한다(전방호환)', () {
      final res = OcrResult.fromJson(<String, dynamic>{});
      expect(res.regions, isEmpty);
      expect(res.plainLatex, '');
      expect(res.overallConfidence, 0.0);
    });
  });

  group('신뢰도 재확인 플래깅 — 임계 0.8', () {
    OcrRegion region(double confidence) => OcrRegion(
          bbox: const BBox(x: 0, y: 0, width: 1, height: 1),
          contentType: '수식',
          latex: 'x',
          confidence: confidence,
        );

    test('영역 신뢰도가 0.8 미만이면 저신뢰로 표시한다', () {
      expect(region(0.79).isLowConfidence, isTrue);
      expect(region(0.8).isLowConfidence, isFalse); // 경계: 0.8은 충분.
      expect(region(0.95).isLowConfidence, isFalse);
    });

    test('전체 신뢰도가 0.8 미만이면 결과를 저신뢰로 플래깅한다', () {
      final res = OcrResult(
        regions: [region(0.9)],
        overallConfidence: 0.7,
      );
      expect(res.hasLowConfidenceRegion, isTrue);
    });

    test('영역 중 하나라도 저신뢰면 결과를 저신뢰로 플래깅한다', () {
      final res = OcrResult(
        regions: [region(0.95), region(0.5)],
        overallConfidence: 0.9, // 전체는 높아도 약한 영역이 있으면 재확인.
      );
      expect(res.hasLowConfidenceRegion, isTrue);
    });

    test('전체·영역 모두 0.8 이상이면 저신뢰가 아니다', () {
      final res = OcrResult(
        regions: [region(0.9), region(0.85)],
        overallConfidence: 0.88,
      );
      expect(res.hasLowConfidenceRegion, isFalse);
    });
  });
}
