// L5 OCR API 데이터 모델 — 백엔드 `POST /v1/ocr`(`OcrResult`) 계약을 *구조 그대로* 옮긴다.
//
// 정본: `src/backend/whymath_backend/schema/ocr.py`(`OcrResult`·`OcrRegion`·`BBox`) +
// enum(`schema/enums.py` `ContentType`: 텍스트/수식).
//
// **경계(CLAUDE.md·슬라이스 89 표현≠의미)**: 이 클래스들은 *수신 컨테이너*일 뿐이다 — 손글씨
// 인식·영역 분해·신뢰도 산출·단계 분해 *로직*은 전부 서버(L5 OCR 파이프라인)에 있고, 클라는
// 받은 `OcrResult` 구조를 *렌더*만 한다. 미성년 풀이 데이터(민감정보)는 클라가 평문 장기
// 저장하지 않는다 — 화면 표시 후 휘발(영속·재학습은 서버 책임·CLAUDE.md).
//
// **enum 표현 방침(coach_models.dart 답습)**: 백엔드 문자열 enum(`content_type`)은 한국어 값
// ("텍스트"·"수식")을 그대로 `String`으로 받는다(과확장 회피·백엔드 값 그대로 보존·codegen
// 리스크 최소화). UI 분기(아이콘·라벨)는 이 문자열로 한다 — 의미 해석은 서버가 끝냈다.
import 'package:freezed_annotation/freezed_annotation.dart';

part 'ocr_models.freezed.dart';
part 'ocr_models.g.dart';

// ─────────────────────────────────────────────────────────────────────────
// 응답 — OcrResult (ocr.py) + 중첩(OcrRegion·BBox)
// ─────────────────────────────────────────────────────────────────────────

/// 한 장의 풀이 이미지 OCR 결과 — 영역 목록 + 집계 뷰(LaTeX·단계·마크다운·신뢰도).
///
/// `regions`는 *읽기 순서*(위→아래·좌→우)로 정렬돼 내려온다. 집계 필드(`plainLatex`·
/// `solutionSteps`·`overallConfidence` 등)는 영역에서 파생된 편의 뷰로, L4 코치 핸드오프
/// 매핑의 착지점이다(student_solution·ocr_confidence·solution_steps 등). 클라는 화면 표시와
/// 후속 `/v1/coach` 호출 페이로드 조립에만 쓴다(수학 로직 미구현·표현≠의미).
@freezed
abstract class OcrResult with _$OcrResult {
  const factory OcrResult({
    /// 읽기순(위→아래·좌→우) 정렬된 인식 영역 목록(없으면 빈 리스트).
    @JsonKey(name: 'regions') @Default(<OcrRegion>[]) List<OcrRegion> regions,

    /// 영역 인식 결과를 읽기순으로 이은 단일 문자열 — `CoachRequest.studentSolution` 착지점.
    @JsonKey(name: 'plain_latex') @Default('') String plainLatex,

    /// 공간정보로 분해한 풀이 단계 시퀀스 — `CoachRequest.solutionSteps` 착지점(없으면 빈 리스트).
    @JsonKey(name: 'solution_steps')
    @Default(<String>[]) List<String> solutionSteps,

    /// 전이별 단계 유형(조건해석/케이스분류/그래프스케치/계산/검산) — 길이는 전이 수
    /// (`solutionSteps.length-1`)·미지정이면 빈 리스트. `CoachRequest.solutionStepTypes` 착지점.
    @JsonKey(name: 'solution_step_types')
    @Default(<String>[]) List<String> solutionStepTypes,

    /// 영역을 사람이 읽기 좋게 이은 마크다운(텍스트는 그대로·수식은 $...$). 표시용.
    @JsonKey(name: 'markdown') @Default('') String markdown,

    /// 전체 신뢰도(영역 신뢰도의 평균·0~1) — `CoachRequest.ocrConfidence` 착지점.
    /// <0.8이면 coach가 §3.3 게이트로 재확인을 유도한다(coach.py 규약). 클라도 같은 임계로
    /// 재확인 cue를 보인다([isLowConfidence]).
    @JsonKey(name: 'overall_confidence') @Default(0.0) double overallConfidence,

    /// 영역 신뢰도의 최솟값(0~1) — 가장 약한 영역(재확인 우선 후보)을 가린다.
    @JsonKey(name: 'min_confidence') @Default(0.0) double minConfidence,
  }) = _OcrResult;

  const OcrResult._();

  factory OcrResult.fromJson(Map<String, dynamic> json) =>
      _$OcrResultFromJson(json);

  /// 인식 신뢰도가 낮은 영역이 하나라도 있는가(재확인 유도 판단).
  ///
  /// 백엔드 §3.3 게이트와 동일하게 전체 신뢰도가 [lowConfidenceThreshold] 미만이거나,
  /// 영역별 신뢰도 중 하나라도 임계 미만이면 true다(가장 약한 영역까지 재확인 권유).
  /// *판단 기준은 표시 cue용일 뿐* — 코치의 실제 게이트(verification_ocr_gated)는 서버가 낸다.
  bool get hasLowConfidenceRegion =>
      overallConfidence < lowConfidenceThreshold ||
      regions.any((r) => r.isLowConfidence);
}

/// 인식된 영역 1개 — 위치(`BBox`) + 유형(`contentType`) + 인식 텍스트(`latex`) + 신뢰도.
///
/// `contentType`은 한국어 문자열 "텍스트"(한글 산문)·"수식"(LaTeX) 중 하나다(분해 단위라
/// 둘 중 하나·이미지/혼합 없음). `latex`는 수식이면 LaTeX, 텍스트면 한글 산문 그대로다
/// (필드명은 수식이 본질이라 latex지만 텍스트도 같은 필드).
@freezed
abstract class OcrRegion with _$OcrRegion {
  const factory OcrRegion({
    /// 영역의 이미지 좌표 경계 상자.
    @JsonKey(name: 'bbox') required BBox bbox,

    /// 영역 유형 — "텍스트"(한글 산문)·"수식"(LaTeX). 백엔드 `ContentType` 한국어 값 그대로.
    @JsonKey(name: 'content_type') required String contentType,

    /// 인식 결과 문자열 — 수식이면 LaTeX, 텍스트면 한글 산문(빈 문자열 허용·인식 실패/공백).
    @JsonKey(name: 'latex') @Default('') String latex,

    /// 이 영역의 인식 신뢰도(0~1). 검증 실패 시 강등될 수 있다.
    @JsonKey(name: 'confidence') @Default(0.0) double confidence,

    /// 수식 영역의 SymPy 왕복 파싱 검증 결과(True=성공·False=파싱 불가·null=미검증·텍스트 등).
    @JsonKey(name: 'verified') bool? verified,
  }) = _OcrRegion;

  const OcrRegion._();

  factory OcrRegion.fromJson(Map<String, dynamic> json) =>
      _$OcrRegionFromJson(json);

  /// 이 영역이 수식인지(contentType 분기 편의·UI 아이콘/라벨).
  bool get isFormula => contentType == ocrContentTypeFormula;

  /// 이 영역이 텍스트인지.
  bool get isText => contentType == ocrContentTypeText;

  /// 신뢰도가 재확인 임계 미만인지(재확인 cue 표시 판단).
  bool get isLowConfidence => confidence < lowConfidenceThreshold;
}

/// 이미지 좌표계의 직사각형 경계 상자 — 영역의 위치(픽셀·좌상단 원점).
///
/// `(x, y)`는 좌상단 꼭짓점·`(width, height)`는 크기다. 클라는 영역 정렬·표시 좌표로만 쓴다
/// (IoU·조립 같은 계산은 서버가 끝냈다·수학 로직 미구현).
@freezed
abstract class BBox with _$BBox {
  const factory BBox({
    /// 좌상단 x(픽셀·좌→우 증가).
    @JsonKey(name: 'x') @Default(0.0) double x,

    /// 좌상단 y(픽셀·위→아래 증가).
    @JsonKey(name: 'y') @Default(0.0) double y,

    /// 상자 너비(픽셀).
    @JsonKey(name: 'width') @Default(0.0) double width,

    /// 상자 높이(픽셀).
    @JsonKey(name: 'height') @Default(0.0) double height,
  }) = _BBox;

  factory BBox.fromJson(Map<String, dynamic> json) => _$BBoxFromJson(json);
}

/// 백엔드 `ContentType`(enums.py) 한국어 값 — "텍스트"(한글 산문).
const String ocrContentTypeText = '텍스트';

/// 백엔드 `ContentType`(enums.py) 한국어 값 — "수식"(LaTeX).
const String ocrContentTypeFormula = '수식';

/// OCR 신뢰도 재확인 임계(0~1). 백엔드 §3.3 게이트(`ocr_confidence < 0.8`)와 동일하게
/// *미만*이면 재확인을 유도한다 — coach.py 규약·coach_signal_card "④ OCR 재확인" cue와 일치.
const double lowConfidenceThreshold = 0.8;
