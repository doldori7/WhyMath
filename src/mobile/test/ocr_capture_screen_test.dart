// OCR 캡처 화면 위젯 테스트 — 촬영 버튼→인식→결과 렌더·저신뢰 재확인 cue 검증.
//
// ocrApiProvider·imageSourceServiceProvider를 fake로 override해 네트워크·플랫폼 채널 없이
// 화면 동작을 확인한다(chat_screen_test 답습). 정서 안전(절대 금기) 가드도 단언한다 —
// 저신뢰여도 "틀렸다"·정답·빨강 경고 문구가 *렌더 텍스트에 없음*을 확인한다.
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/ocr/data/image_source_service.dart';
import 'package:korean_math_app/features/ocr/data/ocr_api.dart';
import 'package:korean_math_app/features/ocr/data/ocr_models.dart';
import 'package:korean_math_app/features/ocr/presentation/ocr_capture_screen.dart';

/// 미리 짠 결과를 돌려주는 fake OcrApi.
class _FakeOcrApi extends OcrApi {
  _FakeOcrApi(this.result) : super(Dio());

  final OcrResult result;

  @override
  Future<OcrResult> recognize(MultipartFile image) async => result;
}

/// 항상 한 장을 돌려주는 fake 선택 서비스(취소 없음).
class _FakeImageSourceService implements ImageSourceService {
  @override
  Future<PickedImage?> pick(OcrImageSource source) async => PickedImage(
        bytes: Uint8List.fromList(<int>[1, 2, 3]),
        path: '/tmp/s.jpg',
        fileName: 's.jpg',
      );
}

Widget _wrap(OcrResult result) {
  return ProviderScope(
    overrides: [
      ocrApiProvider.overrideWithValue(_FakeOcrApi(result)),
      imageSourceServiceProvider.overrideWithValue(_FakeImageSourceService()),
    ],
    child: const MaterialApp(home: OcrCaptureScreen()),
  );
}

OcrResult _result({
  required double overall,
  required double regionConf,
}) =>
    OcrResult(
      regions: [
        OcrRegion(
          bbox: const BBox(x: 0, y: 0, width: 10, height: 10),
          contentType: '수식',
          latex: r'D = b^2 - 4ac',
          confidence: regionConf,
        ),
      ],
      plainLatex: r'D = b^2 - 4ac',
      overallConfidence: overall,
      minConfidence: regionConf,
    );

/// 화면에 실제로 그려진 모든 텍스트(Text·SelectableText)의 문자열을 모은다.
///
/// MATH-05 누출 동결용 — "백슬래시 매크로가 *어디에도* 안 보인다"를 화면 단위로 단언하려면
/// 특정 위젯 하나가 아니라 렌더된 텍스트 전량을 봐야 한다(이 저장소 테스트는 파일마다
/// 자기 헬퍼를 갖는 관례라 mathlive_input_screen_test와 각자 보유한다).
List<String> _renderedTexts(WidgetTester tester) {
  final List<String> out = <String>[];
  for (final Text w in tester.widgetList<Text>(find.byType(Text))) {
    if (w.data != null) {
      out.add(w.data!);
    }
  }
  for (final SelectableText w
      in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
    if (w.data != null) {
      out.add(w.data!);
    }
  }
  return out;
}

void main() {
  testWidgets('초기엔 안내와 촬영/갤러리 버튼이 보인다', (tester) async {
    await tester.pumpWidget(_wrap(_result(overall: 0.9, regionConf: 0.9)));

    expect(find.text('풀이 사진 인식'), findsOneWidget);
    expect(find.text('풀이를 사진으로 찍으면 함께 살펴볼게요.'), findsOneWidget);
    expect(find.text('사진 찍기'), findsOneWidget);
    expect(find.text('갤러리에서 고르기'), findsOneWidget);
  });

  testWidgets('촬영→인식 후 인식 결과·영역 카드를 렌더한다', (tester) async {
    await tester.pumpWidget(_wrap(_result(overall: 0.95, regionConf: 0.95)));

    await tester.tap(find.text('사진 찍기'));
    await tester.pumpAndSettle();

    // 전체 요약·영역 본문(LaTeX 텍스트).
    expect(find.text('인식한 풀이'), findsOneWidget);
    expect(find.text(r'D = b^2 - 4ac'), findsWidgets);
    // 충분히 또렷할 땐 확인 cue.
    expect(find.text('또렷하게 읽었어요'), findsWidgets);
  });

  testWidgets('저신뢰(<0.8) 영역엔 재확인 cue를 부드럽게 단다', (tester) async {
    await tester.pumpWidget(_wrap(_result(overall: 0.6, regionConf: 0.6)));

    await tester.tap(find.text('사진 찍기'));
    await tester.pumpAndSettle();

    // 전체·영역 모두 재확인 권유(따뜻한 톤).
    expect(
      find.text('인식이 또렷하지 않은 부분이 있어요 — 다시 확인해볼까요?'),
      findsOneWidget,
    );
    expect(
      find.text('이 부분이 잘 안 보여요 — 다시 확인해볼까요?'),
      findsOneWidget,
    );
  });

  testWidgets('인식 결과는 원문 LaTeX 매크로를 노출하지 않고 평문 표기로 그린다 (MATH-05)',
      (tester) async {
    // `plainLatex`는 이름과 달리 평문이 아니다 — 백엔드 assemble.py가 region latex 원문을
    // 이어붙인 값이라 매크로가 그대로 들어온다. 전체 요약·영역 카드 둘 다 검사한다.
    const OcrResult macroResult = OcrResult(
      regions: [
        OcrRegion(
          bbox: BBox(x: 0, y: 0, width: 10, height: 10),
          contentType: '수식',
          latex: r'\frac{1}{2}',
          confidence: 0.95,
        ),
      ],
      plainLatex: r'\frac{1}{2} \times 4',
      overallConfidence: 0.95,
      minConfidence: 0.95,
    );

    await tester.pumpWidget(_wrap(macroResult));
    await tester.tap(find.text('사진 찍기'));
    await tester.pumpAndSettle();

    // ① 존재 단언 — 변환된 평문 표기가 실제로 그려진다(빈 화면 위장 방지).
    //    전체 요약: `\frac{1}{2} \times 4` → `((1)/(2)) *4`, 영역 카드: `((1)/(2))`.
    //    `) *4`의 공백은 변환기가 `\times`의 *뒤* 공백만 삼키는 데서 오는 기존 표기 산물이다
    //    (latex_to_plain.dart 주석 "값이 명시 기호라 뒤 공백 삼킴 안전") — 이 태스크가 만든
    //    것이 아니고, 그 파일은 MATH-01이 소유 중이라 여기서 손대지 않는다. 실제 산출값을
    //    그대로 동결한다(추정치를 적어 두면 계약이 아니라 희망이 된다).
    expect(find.text('((1)/(2)) *4'), findsOneWidget);
    expect(find.text('((1)/(2))'), findsOneWidget);
    // ② 부재 단언 — 렌더된 텍스트 어디에도 백슬래시 매크로가 없다(화면 단위 계약).
    expect(
      _renderedTexts(tester).where((String t) => t.contains(r'\')),
      isEmpty,
      reason: '학생 대면 표면에 LaTeX 원문 노출 금지(MATH-05)',
    );
  });

  testWidgets('정서 안전 — 정답·"틀렸다"·빨강 경고 문구가 없다', (tester) async {
    await tester.pumpWidget(_wrap(_result(overall: 0.6, regionConf: 0.6)));

    await tester.tap(find.text('사진 찍기'));
    await tester.pumpAndSettle();

    // 절대 금기: 부정 강화·정오 단정 표현 미노출.
    expect(find.textContaining('틀렸'), findsNothing);
    expect(find.textContaining('오답'), findsNothing);
    expect(find.textContaining('실패'), findsNothing);
  });
}
