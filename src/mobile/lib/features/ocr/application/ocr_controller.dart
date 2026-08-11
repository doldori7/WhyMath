// OCR 컨트롤러 — 풀이 사진 선택·서버 인식 요청·결과 상태 관장.
//
// 경계(CLAUDE.md·슬라이스 89): 손글씨 인식·영역 분해·신뢰도 산출·단계 분해는 전부 서버
// (L5 `POST /v1/ocr`)가 한다. 이 컨트롤러는 (1) 이미지를 고르고 (2) multipart로 보내고
// (3) 받은 [OcrResult]를 화면 상태로 *렌더*할 뿐이다(표현≠의미·수학 로직 클라 미구현).
// 부수효과는 [ImageSourceService] 선택 + [OcrApi] 업로드 둘뿐 — 나머지는 순수 상태 전이다.
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/update_required.dart';
import '../data/image_source_service.dart';
import '../data/ocr_api.dart';
import '../data/ocr_models.dart';
import 'ocr_state.dart';

part 'ocr_controller.g.dart';

/// OCR 화면 상태를 관리하는 Riverpod Notifier(`ChatController` 관례).
@riverpod
class OcrController extends _$OcrController {
  @override
  OcrState build() => const OcrState();

  /// 카메라·갤러리에서 사진을 고르고(취소면 유휴 복귀) 서버로 보내 인식한다.
  ///
  /// 흐름: ① picking(선택 모달) → ② 취소면 idle 복귀(에러 아님) →
  /// ③ uploading(서버 인식) → ④ 성공 시 result·실패 시 error(graceful·앱 안 죽음).
  /// 진행 중 재진입은 막는다(중복 업로드 방지).
  Future<void> pickAndRecognize(OcrImageSource source) async {
    if (state.isBusy) {
      return; // 선택·업로드 중 재진입 방지.
    }

    // ① 선택 단계로 전환(이전 결과·에러는 새 시도 시작이라 비운다).
    state = const OcrState(status: OcrStatus.picking);

    final PickedImage? picked;
    try {
      picked = await ref.read(imageSourceServiceProvider).pick(source);
    } catch (e) {
      // 선택 자체가 실패(권한 거부 등) — graceful 에러.
      state = const OcrState(
        status: OcrStatus.error,
        error: '사진을 불러오지 못했어요. 권한을 확인하고 다시 시도해 주세요.',
      );
      return;
    }

    // ② 사용자가 취소하면 유휴로 되돌린다(에러가 아님·재시도 가능).
    if (picked == null) {
      state = const OcrState();
      return;
    }

    await _recognize(picked);
  }

  /// 고른 이미지를 multipart로 보내 인식한다(선택과 분리·테스트 진입점).
  ///
  /// 이미지 바이트를 `image` 필드로 업로드하고, 성공하면 [OcrResult]를 결과 상태로 보관한다.
  /// 인식·검증 로직은 전혀 돌리지 않는다(서버가 끝낸 구조를 받기만 함·CLAUDE.md).
  Future<void> _recognize(PickedImage picked) async {
    state = const OcrState(status: OcrStatus.uploading);
    try {
      final multipart = MultipartFile.fromBytes(
        picked.bytes,
        filename: picked.fileName,
      );
      final result = await ref.read(ocrApiProvider).recognize(multipart);
      state = OcrState(status: OcrStatus.result, result: result);
    } on DioException catch (e) {
      // 503(OCR 비활성)은 학생 잘못이 아니라 "기능이 꺼져 있음"이라 문구를 분리한다
      // (변별력 없는 에러 메시지 금지 — CLAUDE.md). 그 외(401 미인증·422 이미지 누락·
      // 네트워크 실패 등)는 기존 graceful 문구를 유지한다.
      if (e.response?.statusCode == 503) {
        state = const OcrState(
          status: OcrStatus.error,
          error: '지금은 손글씨 인식 기능을 이용할 수 없어요. 잠시 후 다시 시도해 주세요.',
        );
      } else {
        // 426(최소버전 미달)만 전용 문구(판정 좌석 = core/update_required 단일·OPS-35).
        state = OcrState(
          status: OcrStatus.error,
          error: updateRequiredMessageOf(e) ?? '풀이를 인식하지 못했어요. 잠시 후 다시 시도해 주세요.',
        );
      }
    } catch (e) {
      // DioException이 아닌 그 외 예외도 graceful 에러로 기록한다(회귀 방지).
      state = const OcrState(
        status: OcrStatus.error,
        error: '풀이를 인식하지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 초기 상태로 되돌린다(다른 사진 찍기·결과 화면 닫기).
  void reset() {
    state = const OcrState();
  }
}
