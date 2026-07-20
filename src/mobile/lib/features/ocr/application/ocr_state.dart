// OCR 화면 상태 — 진행 단계(유휴·선택중·업로드중·결과·에러)를 담는 불변 상태.
//
// 경계(CLAUDE.md): 순수 표현 상태다. 인식·신뢰도 판단은 서버(L5)가 끝낸 `OcrResult`를
// 그대로 보관할 뿐, 클라가 수학·인식 로직을 돌리지 않는다(표현≠의미).
import 'package:freezed_annotation/freezed_annotation.dart';

import '../data/ocr_models.dart';

part 'ocr_state.freezed.dart';

/// OCR 흐름의 진행 단계.
///
/// idle → picking(카메라/갤러리 선택) → uploading(서버 인식) → result/error.
/// result·error는 다시 idle/picking으로 되돌아갈 수 있다(재촬영·재시도).
enum OcrStatus {
  /// 시작 전(버튼만 보이는 초기 상태).
  idle,

  /// 카메라·갤러리에서 이미지를 고르는 중(플러그인 모달 대기).
  picking,

  /// 고른 이미지를 서버로 보내 인식 중(로딩 인디케이터).
  uploading,

  /// 인식 완료 — [OcrState.result]에 구조가 채워진다.
  result,

  /// 실패(선택 취소가 아닌 오류) — [OcrState.error]에 사용자 메시지.
  error,
}

/// OCR 화면의 단일 상태 트리.
@freezed
abstract class OcrState with _$OcrState {
  const factory OcrState({
    /// 현재 진행 단계(기본=유휴).
    @Default(OcrStatus.idle) OcrStatus status,

    /// 인식 결과 구조(완료 전·실패 시 null). 서버가 검증해 내려준 `OcrResult`를 그대로 보관.
    OcrResult? result,

    /// 마지막 실패 메시지(없으면 null). 가용성을 위해 앱은 죽지 않는다.
    String? error,
  }) = _OcrState;

  const OcrState._();

  /// 서버 호출(선택·업로드) 진행 중인지 — 버튼 비활성·로딩 인디케이터 표시.
  bool get isBusy =>
      status == OcrStatus.picking || status == OcrStatus.uploading;
}
