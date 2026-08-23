// 나 탭 — 학습 경로·진단 결과·성장의 증거 섹션 상태 (PATH-05 · MOB-17).
//
// 경계(CLAUDE.md): 순수 표현 상태다. 진단(BKT/IRT)·학습 경로 위상정렬·성장 지표 계산은 전부
// 서버(L2/L4)가 내리고, 이 상태는 응답 구조를 그대로 보관할 뿐이다(표현≠의미·수학 로직
// 클라 미구현).
//
// 정직 원칙(CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지"): 401(미인증)·has_cycle(그래프
// 순환)·빈 경로(steps==0)·NO_DATA 지표는 각각 다른 의미의 *정상/이상* 신호라 하나의 "오류"
// 문구로 뭉개지 않는다. [SectionStatus]가 그 구분을 상태 트리에 그대로 반영한다 —
// unauthenticated는 error와 별개 값이고, has_cycle·빈 steps·지표 suppressed_reason은
// loaded 상태의 데이터에서 그대로 읽는다.
import 'package:freezed_annotation/freezed_annotation.dart';

import '../../problems/data/problem_models.dart';
import '../data/growth_evidence_models.dart';

part 'me_tab_state.freezed.dart';

/// 한 섹션(학습 경로 또는 진단 결과)의 조회 진행 단계.
///
/// idle → loading → loaded(정상, 데이터가 비어도 loaded — 빈 것도 정직한 서버 응답) 또는
/// unauthenticated(401 — 일반 error와 구분) 또는 error(그 외 실패: 네트워크·5xx 등).
enum SectionStatus {
  /// 아직 조회하지 않음(화면 진입 전 초기 상태).
  idle,

  /// 서버 조회 중(로딩 인디케이터).
  loading,

  /// 조회 성공 — 데이터가 비어 있어도(예: 진단 0건·학습 경로 steps 0건) loaded다(정상 신호).
  loaded,

  /// 401 — 미인증. 일반 오류(error)와 분리해 "로그인이 필요해요"로 정직하게 안내한다.
  unauthenticated,

  /// 401 외 실패(네트워크·5xx 등) — 일반 안내 + 재시도.
  error,
}

/// 나 탭의 학습 경로·진단 결과 섹션 상태 트리.
///
/// 두 섹션은 서로 다른 실패를 독립적으로 겪을 수 있다(예: 진단은 성공했지만 학습 경로만
/// 실패) — 그래서 상태를 섹션별로 분리해 둔다(하나가 죽어도 다른 하나는 정상 렌더).
@freezed
abstract class MeTabState with _$MeTabState {
  const factory MeTabState({
    // ── 진단 결과 섹션 (GET /v1/me/diagnosis/concepts) ──
    @Default(SectionStatus.idle) SectionStatus diagnosisStatus,

    /// 개념 진단 목록(약점 먼저 정렬·서버 계약). loaded인데 비어 있으면 "진단 근거 부족"(정상).
    @Default(<ConceptDiagnosisItem>[]) List<ConceptDiagnosisItem> diagnoses,

    /// 진단 실패(401 외) 메시지·없으면 null.
    String? diagnosisError,

    // ── 학습 경로 섹션 (GET /v1/me/weak-concepts/{id}/learning-path) ──
    @Default(SectionStatus.idle) SectionStatus learningPathStatus,

    /// 학습 경로 응답(steps·has_cycle 등 서버 정직 신호 그대로 보관). 미조회면 null.
    LearningPath? learningPath,

    /// 학습 경로를 조회한 대상 개념의 표시명(헤더용)·없으면 null.
    String? learningPathConceptName,

    /// 학습 경로 실패(401 외) 메시지·없으면 null.
    String? learningPathError,

    // ── 성장의 증거 섹션 (GET /v1/me/growth-evidence) ──
    @Default(SectionStatus.idle) SectionStatus growthEvidenceStatus,

    /// 성장 증거 응답(서버 노출 계약을 거친 지표 뷰 그대로 보관). 미조회면 null.
    GrowthEvidenceResponse? growthEvidence,

    /// 성장 증거 실패(401 외) 메시지·없으면 null.
    String? growthEvidenceError,
  }) = _MeTabState;

  const MeTabState._();

  /// 세 섹션 중 하나라도 조회 중인지(진입 시 전체 로딩 인디케이터 판단용).
  bool get isLoading =>
      diagnosisStatus == SectionStatus.loading ||
      learningPathStatus == SectionStatus.loading ||
      growthEvidenceStatus == SectionStatus.loading;
}
