// 나 탭 컨트롤러 — 진단 결과·학습 경로·성장의 증거 세 섹션을 로드한다 (PATH-05 · MOB-17).
//
// 경계(CLAUDE.md): 진단(BKT/IRT)·학습 경로 위상정렬·성장 지표 계산·노출 판정은 전부 서버
// (L2/L4/노출 계약)가 내린다. 이 컨트롤러(L5)는 세 엔드포인트를 호출하고 응답 구조를 그대로
// 상태에 담을 뿐 — 어떤 수학·숙달·지표 판정도 하지 않는다.
//
// **정직 원칙**: 401은 unauthenticated로, 그 외 실패는 error로 분리해 기록한다(일반 문구로
// 뭉개지 않음). has_cycle·빈 steps·NO_DATA/suppressed_reason·Brier narrative는 판정하지
// 않고 해당 모델 구조 그대로 상태에 담아 화면(presentation)이 직접 읽고 렌더하게 한다 —
// 컨트롤러가 "정상/이상"을 대신 요약하지 않는다.
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../problems/data/problem_models.dart';
import '../../problems/data/problems_api.dart';
import '../data/growth_evidence_api.dart';
import 'me_tab_state.dart';

part 'me_tab_controller.g.dart';

/// 진단 결과 조회 시 요청할 상한(대역폭·화면 — `diagnosis_controller.dart` 관례 답습).
const int _diagnosisLimit = 20;

/// 나 탭(학습 경로·진단 결과·성장의 증거) 상태를 관장하는 Riverpod Notifier.
@riverpod
class MeTabController extends _$MeTabController {
  @override
  MeTabState build() => const MeTabState();

  /// 진단 결과를 조회하고, 성공하면 학습 경로와 성장의 증거를 병렬로 이어서 조회한다.
  ///
  /// 흐름: ① 진단 목록 로드 → ② 401이면 세 섹션 모두 unauthenticated로 정직 표시 → ③ 그 외
  /// 실패면 진단은 error, 학습 경로·성장의 증거는 "진단 실패로 대상/지표를 못 받았다"는 명시적
  /// error → ④ 진단이 비어 있으면(정상) 학습 경로는 "대상 없음" loaded, 성장의 증거는 독립적으로
  /// 로드 → ⑤ 있으면 첫 항목(서버가 이미 약점 먼저 정렬)의 학습 경로 + 성장의 증거를 병행 조회.
  Future<void> load() async {
    if (state.isLoading) {
      return; // 조회 중 재진입 방지.
    }
    state = state.copyWith(
      diagnosisStatus: SectionStatus.loading,
      diagnosisError: null,
    );

    final List<ConceptDiagnosisItem> diagnoses;
    try {
      diagnoses = await ref
          .read(problemsApiProvider)
          .getDiagnosisConcepts(limit: _diagnosisLimit);
    } on DioException catch (e) {
      if (_isUnauthenticated(e)) {
        state = state.copyWith(
          diagnosisStatus: SectionStatus.unauthenticated,
          learningPathStatus: SectionStatus.unauthenticated,
          growthEvidenceStatus: SectionStatus.unauthenticated,
        );
        return;
      }
      state = state.copyWith(
        diagnosisStatus: SectionStatus.error,
        diagnosisError: '진단 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
        learningPathStatus: SectionStatus.error,
        learningPathError: '진단 결과를 불러오지 못해 학습 경로를 확인할 수 없어요.',
        growthEvidenceStatus: SectionStatus.error,
        growthEvidenceError: '진단 결과를 불러오지 못해 성장의 증거를 확인할 수 없어요.',
      );
      return;
    } catch (_) {
      state = state.copyWith(
        diagnosisStatus: SectionStatus.error,
        diagnosisError: '진단 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
        learningPathStatus: SectionStatus.error,
        learningPathError: '진단 결과를 불러오지 못해 학습 경로를 확인할 수 없어요.',
        growthEvidenceStatus: SectionStatus.error,
        growthEvidenceError: '진단 결과를 불러오지 못해 성장의 증거를 확인할 수 없어요.',
      );
      return;
    }

    state = state.copyWith(
      diagnosisStatus: SectionStatus.loaded,
      diagnoses: diagnoses,
    );

    if (diagnoses.isEmpty) {
      // 진단 근거가 아직 없음(정상) — 학습 경로는 조회할 대상 개념이 없음을 그대로 반영.
      state = state.copyWith(
        learningPathStatus: SectionStatus.loaded,
        learningPath: null,
        learningPathConceptName: null,
      );
    } else {
      // 서버가 이미 "약점 먼저" 정렬해 돌려준다(me.py get_my_concept_diagnosis 문서 계약).
      // 학습 경로와 성장의 증거는 서로 독립이므로 병렬로 조회한다.
      await Future.wait(<Future<void>>[
        _loadLearningPath(diagnoses.first),
        _loadGrowthEvidence(),
      ]);
      return;
    }

    // 진단이 비어 있어도 성장의 증거는 별도로 조회한다(독립 좌석).
    await _loadGrowthEvidence();
  }

  /// [weakest] 개념의 학습 경로를 조회해 상태에 그대로 반영한다(steps·has_cycle 가공 없음).
  Future<void> _loadLearningPath(ConceptDiagnosisItem weakest) async {
    state = state.copyWith(
      learningPathStatus: SectionStatus.loading,
      learningPathError: null,
    );
    try {
      final path = await ref
          .read(problemsApiProvider)
          .getLearningPath(weakest.conceptId);
      state = state.copyWith(
        learningPathStatus: SectionStatus.loaded,
        learningPath: path,
        learningPathConceptName: weakest.conceptName,
      );
    } on DioException catch (e) {
      if (_isUnauthenticated(e)) {
        state = state.copyWith(learningPathStatus: SectionStatus.unauthenticated);
        return;
      }
      state = state.copyWith(
        learningPathStatus: SectionStatus.error,
        learningPathError: '학습 경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    } catch (_) {
      state = state.copyWith(
        learningPathStatus: SectionStatus.error,
        learningPathError: '학습 경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 성장의 증거를 조회해 상태에 그대로 반영한다(지표 노출 판정·서술 가공 없음).
  Future<void> _loadGrowthEvidence() async {
    state = state.copyWith(
      growthEvidenceStatus: SectionStatus.loading,
      growthEvidenceError: null,
    );
    try {
      final evidence = await ref
          .read(growthEvidenceApiProvider)
          .getGrowthEvidence();
      state = state.copyWith(
        growthEvidenceStatus: SectionStatus.loaded,
        growthEvidence: evidence,
      );
    } on DioException catch (e) {
      if (_isUnauthenticated(e)) {
        state = state.copyWith(growthEvidenceStatus: SectionStatus.unauthenticated);
        return;
      }
      state = state.copyWith(
        growthEvidenceStatus: SectionStatus.error,
        growthEvidenceError: '성장의 증거를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    } catch (_) {
      state = state.copyWith(
        growthEvidenceStatus: SectionStatus.error,
        growthEvidenceError: '성장의 증거를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  bool _isUnauthenticated(DioException e) => e.response?.statusCode == 401;
}
