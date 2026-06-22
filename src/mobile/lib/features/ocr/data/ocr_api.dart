// L5 OCR API 클라이언트 — `POST /v1/ocr`(손글씨 풀이 이미지 → `OcrResult`) 호출.
//
// 경계(CLAUDE.md): 이미지를 보내고 `OcrResult`를 구조 그대로 받는다. 손글씨 인식·영역 분해·
// 신뢰도 산출은 전부 서버(L5 파이프라인·PaddleOCR+Qwen3-VL)가 하고, 클라는 결과를 렌더만
// 한다(표현≠의미·수학 로직 클라 미구현). 인증(Bearer)·baseUrl은 공유 [dioProvider]를 그대로
// 쓴다(`coach_api.dart`·`scene_api.dart` 관례) — `ConsentedUser` 보호 엔드포인트라 인증
// 인터셉터가 붙인 토큰으로만 200이 온다(미인증 401·OCR 비활성 503·이미지 누락 422).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'ocr_models.dart';

/// OCR 엔드포인트 호출 래퍼 — multipart 업로드·역직렬화를 담당(`CoachApi` 관례).
///
/// retrofit 코드젠 대신 명시적 메서드를 둔다(`coach_api.dart`와 동일 방침·디버깅 용이·범위 최소).
class OcrApi {
  OcrApi(this._dio);

  final Dio _dio;

  /// `POST /v1/ocr` — 손글씨 풀이 이미지를 보내고 인식 구조(`OcrResult`)를 받는다.
  ///
  /// 백엔드 계약: multipart/form-data·필드명 **`image`**(PNG/JPEG). 인증 헤더는 공유 dio의
  /// [AuthInterceptor]가 저장된 Bearer 토큰을 붙인다(클라는 토큰을 운반만 함). 이 요청은
  /// JSON 본문이 아니라 multipart라 기본 `Content-Type: application/json`을 덮어쓴다(dio가
  /// FormData면 boundary 포함 multipart 헤더를 자동 설정하도록 명시 헤더를 비운다).
  ///
  /// 응답 본문이 비면 `DioException`을 던진다(`coach_api.dart`·`scene_api.dart`와 동형).
  /// 503/401/422 같은 상태 코드는 dio가 `DioException`으로 올려 호출자(컨트롤러)가
  /// graceful 에러로 처리한다(앱은 죽지 않는다).
  Future<OcrResult> recognize(MultipartFile image) async {
    final formData = FormData.fromMap(<String, dynamic>{'image': image});
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/ocr',
      data: formData,
      // multipart는 boundary를 포함한 Content-Type을 dio가 FormData에서 자동 채우게 둔다
      // (공유 dio 기본값 application/json을 이 요청에 한해 제거).
      options: Options(contentType: 'multipart/form-data'),
    );
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: 'ocr 응답 본문이 비어 있습니다.',
      );
    }
    return OcrResult.fromJson(data);
  }
}

/// [OcrApi] provider — 공유 [dioProvider]를 주입받는다([coachApiProvider]와 동형).
final ocrApiProvider = Provider<OcrApi>((ref) {
  return OcrApi(ref.watch(dioProvider));
});
