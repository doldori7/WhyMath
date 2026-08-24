// 성장 증거(WH-1 대리 지표) 데이터 모델 — GET /v1/me/growth-evidence 응답 계약.
//
// 경계(CLAUDE.md): 요청을 보내고 구조를 그대로 받는다. 지표 계산·노출 판정·서술 변환은
// 전부 서버(L2/L4/노출 계약)가 내리고, 클라는 받은 필드를 렌더링만 한다(표현≠의미).
//
// 안전(5원칙 #1·반게임화): [GrowthEvidenceMetricView.value]는 원시 확률/비율 스칼라라
// 화면에 직접 노출하지 않는다. 학생에게 보이는 것은 [status]·[suppressedReason]·
// [GrowthEvidenceBrierView.narrative]뿐이다.
import 'package:freezed_annotation/freezed_annotation.dart';

part 'growth_evidence_models.freezed.dart';
part 'growth_evidence_models.g.dart';

/// 성장 증거 지표 1종 — 서버 노출 계약을 거친 학생 안전 뷰.
///
/// [value]는 클라 내부 판단용이지 학생 대면 숫자가 아니다(5원칙 #1). 화면에는
/// [status] 또는 [suppressedReason]만 노출한다.
@freezed
abstract class GrowthEvidenceMetricView with _$GrowthEvidenceMetricView {
  const factory GrowthEvidenceMetricView({
    /// 계측 상태 — 'measured'·'no_data'·'not_instrumented'·'requires_data'·
    /// 'requires_tool' 등 서버 enum 그대로(클라는 해석·번역하지 않는다).
    required String status,

    /// 실측값(미계측·노출 보류 시 null). 학생에게 직접 보이지 않는다.
    @JsonKey(name: 'value') double? rawValue,

    /// 이번 판정에서 실제로 노출 가능한지.
    @JsonKey(name: 'exposable_now') required bool exposableNow,

    /// exposable_now=False인 경우의 서버/서빙층 한국어 서술.
    @JsonKey(name: 'suppressed_reason') String? suppressedReason,
  }) = _GrowthEvidenceMetricView;

  factory GrowthEvidenceMetricView.fromJson(Map<String, dynamic> json) =>
      _$GrowthEvidenceMetricViewFromJson(json);
}

/// 보정 점수(Brier) — 원 스칼라가 없고 3버킷 서술만 존재(역방향 스칼라 오독 방지).
@freezed
abstract class GrowthEvidenceBrierView with _$GrowthEvidenceBrierView {
  const factory GrowthEvidenceBrierView({
    /// '아직 예측 확신도 데이터가 없어요.' 등 서버 생성 서술.
    required String narrative,
  }) = _GrowthEvidenceBrierView;

  factory GrowthEvidenceBrierView.fromJson(Map<String, dynamic> json) =>
      _$GrowthEvidenceBrierViewFromJson(json);
}

/// `GET /v1/me/growth-evidence` 응답 — 성장 증거 학생 안전 노출 전체.
@freezed
abstract class GrowthEvidenceResponse with _$GrowthEvidenceResponse {
  const factory GrowthEvidenceResponse({
    @JsonKey(name: 'window_start') DateTime? windowStart,
    @JsonKey(name: 'window_end') DateTime? windowEnd,

    /// 항상 true — 본인 집계만(타 학생 데이터 0).
    @JsonKey(name: 'user_scoped') @Default(true) bool userScoped,

    /// 응용 모드 스코프(예: suneung). 미지정이면 null.
    @JsonKey(name: 'mode_filter') String? modeFilter,

    // STUDENT_VISIBLE 9지표(②·④는 INTERNAL_ONLY라 스키마에 필드 자체가 없음).
    @JsonKey(name: 'verify_pass_rate')
    required GrowthEvidenceMetricView verifyPassRate,
    @JsonKey(name: 'session_completion_rate')
    required GrowthEvidenceMetricView sessionCompletionRate,
    @JsonKey(name: 'help_reduction_slope')
    required GrowthEvidenceMetricView helpReductionSlope,
    @JsonKey(name: 'help_demand_supply_ratio')
    required GrowthEvidenceMetricView helpDemandSupplyRatio,
    @JsonKey(name: 'transfer_score')
    required GrowthEvidenceMetricView transferScore,
    @JsonKey(name: 'hint_depth_reached')
    required GrowthEvidenceMetricView hintDepthReached,
    @JsonKey(name: 'mastery_gain_rate')
    required GrowthEvidenceMetricView masteryGainRate,
    @JsonKey(name: 'misconception_resolution_rate')
    required GrowthEvidenceMetricView misconceptionResolutionRate,
    @JsonKey(name: 'self_solve_rate')
    required GrowthEvidenceMetricView selfSolveRate,

    /// ⑥ 보정 점수 — 원 스칼라 대신 서술만.
    @JsonKey(name: 'calibration_brier')
    required GrowthEvidenceBrierView calibrationBrier,
  }) = _GrowthEvidenceResponse;

  factory GrowthEvidenceResponse.fromJson(Map<String, dynamic> json) =>
      _$GrowthEvidenceResponseFromJson(json);
}
