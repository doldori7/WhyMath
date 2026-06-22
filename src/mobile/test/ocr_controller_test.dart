// OCR 컨트롤러 테스트 — 선택·업로드 흐름·상태 전이·취소·graceful 에러 검증.
//
// 네트워크·플랫폼 채널을 타지 않는다 — ocrApiProvider를 미리 짠 OcrResult를 반환(또는 throw)
// 하는 fake OcrApi로, imageSourceServiceProvider를 미리 짠 PickedImage를 반환(또는 null/throw)
// 하는 fake ImageSourceService로 override한다(chat_controller_test 답습). 컨트롤러는 순수
// 상태 전이라 동기적으로 결과를 검증할 수 있다.
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/ocr/application/ocr_controller.dart';
import 'package:korean_math_app/features/ocr/application/ocr_state.dart';
import 'package:korean_math_app/features/ocr/data/image_source_service.dart';
import 'package:korean_math_app/features/ocr/data/ocr_api.dart';
import 'package:korean_math_app/features/ocr/data/ocr_models.dart';

/// 미리 짠 결과를 그대로 돌려주는 fake — 또는 [shouldThrow]면 예외를 던진다.
class _FakeOcrApi extends OcrApi {
  _FakeOcrApi({this.result, this.shouldThrow = false}) : super(Dio());

  final OcrResult? result;
  final bool shouldThrow;

  /// 업로드 호출 횟수(중복 업로드 방지·재진입 가드 검증).
  int calls = 0;

  @override
  Future<OcrResult> recognize(MultipartFile image) async {
    calls++;
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/ocr'),
        error: '인식 실패(테스트)',
      );
    }
    return result!;
  }
}

/// 미리 정한 선택 결과를 돌려주는 fake — [returnNull]이면 취소·[shouldThrow]면 권한 오류.
class _FakeImageSourceService implements ImageSourceService {
  _FakeImageSourceService({
    this.returnNull = false,
    this.shouldThrow = false,
  });

  final bool returnNull;
  final bool shouldThrow;

  /// 마지막으로 요청된 소스(카메라/갤러리 전달 검증).
  OcrImageSource? lastSource;

  @override
  Future<PickedImage?> pick(OcrImageSource source) async {
    lastSource = source;
    if (shouldThrow) {
      throw Exception('권한 거부(테스트)');
    }
    if (returnNull) {
      return null; // 사용자가 취소.
    }
    return PickedImage(
      bytes: Uint8List.fromList(<int>[1, 2, 3]),
      path: '/tmp/solution.jpg',
      fileName: 'solution.jpg',
    );
  }
}

/// 텍스트·수식 영역을 가진 최소 결과(테스트 가독성용).
OcrResult _result({double overall = 0.9, double regionConf = 0.9}) => OcrResult(
      regions: [
        OcrRegion(
          bbox: const BBox(x: 0, y: 0, width: 10, height: 10),
          contentType: '수식',
          latex: r'x = 1',
          confidence: regionConf,
        ),
      ],
      plainLatex: r'x = 1',
      solutionSteps: const <String>[r'x = 1'],
      overallConfidence: overall,
      minConfidence: regionConf,
    );

ProviderContainer _containerWith({
  required OcrApi api,
  required ImageSourceService picker,
}) {
  final container = ProviderContainer(
    overrides: [
      ocrApiProvider.overrideWithValue(api),
      imageSourceServiceProvider.overrideWithValue(picker),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('OcrController.pickAndRecognize — 성공', () {
    test('선택→업로드→result 상태로 전이하고 결과를 보관한다', () async {
      final api = _FakeOcrApi(result: _result());
      final picker = _FakeImageSourceService();
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.camera);

      final state = container.read(ocrControllerProvider);
      expect(state.status, OcrStatus.result);
      expect(state.result, isNotNull);
      expect(state.result!.plainLatex, r'x = 1');
      expect(state.error, isNull);
      expect(picker.lastSource, OcrImageSource.camera); // 소스 전달.
      expect(api.calls, 1);
    });

    test('갤러리 소스도 그대로 전달한다', () async {
      final api = _FakeOcrApi(result: _result());
      final picker = _FakeImageSourceService();
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.gallery);

      expect(picker.lastSource, OcrImageSource.gallery);
      expect(container.read(ocrControllerProvider).status, OcrStatus.result);
    });
  });

  group('OcrController.pickAndRecognize — 취소·에러', () {
    test('선택을 취소하면 유휴로 되돌리고 업로드하지 않는다(에러 아님)', () async {
      final api = _FakeOcrApi(result: _result());
      final picker = _FakeImageSourceService(returnNull: true);
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.camera);

      final state = container.read(ocrControllerProvider);
      expect(state.status, OcrStatus.idle);
      expect(state.result, isNull);
      expect(state.error, isNull);
      expect(api.calls, 0); // 업로드 없음.
    });

    test('선택 실패(권한 거부 등)는 graceful 에러로 기록한다', () async {
      final api = _FakeOcrApi(result: _result());
      final picker = _FakeImageSourceService(shouldThrow: true);
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.camera);

      final state = container.read(ocrControllerProvider);
      expect(state.status, OcrStatus.error);
      expect(state.error, isNotNull);
      expect(api.calls, 0);
    });

    test('업로드(503/401/네트워크) 실패는 error만 기록하고 앱은 죽지 않는다', () async {
      final api = _FakeOcrApi(shouldThrow: true);
      final picker = _FakeImageSourceService();
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.camera);

      final state = container.read(ocrControllerProvider);
      expect(state.status, OcrStatus.error);
      expect(state.result, isNull);
      expect(state.error, isNotNull);
      expect(api.calls, 1); // 업로드는 시도됨.
    });
  });

  group('OcrController — 재진입·리셋', () {
    test('reset은 유휴 상태로 되돌린다', () async {
      final api = _FakeOcrApi(result: _result());
      final picker = _FakeImageSourceService();
      final container = _containerWith(api: api, picker: picker);
      final notifier = container.read(ocrControllerProvider.notifier);

      await notifier.pickAndRecognize(OcrImageSource.camera);
      expect(container.read(ocrControllerProvider).status, OcrStatus.result);

      notifier.reset();
      final state = container.read(ocrControllerProvider);
      expect(state.status, OcrStatus.idle);
      expect(state.result, isNull);
    });
  });

  group('OcrState 파생', () {
    test('isBusy는 picking·uploading에서 true', () {
      expect(const OcrState(status: OcrStatus.picking).isBusy, isTrue);
      expect(const OcrState(status: OcrStatus.uploading).isBusy, isTrue);
      expect(const OcrState(status: OcrStatus.idle).isBusy, isFalse);
      expect(const OcrState(status: OcrStatus.result).isBusy, isFalse);
      expect(const OcrState(status: OcrStatus.error).isBusy, isFalse);
    });
  });
}
