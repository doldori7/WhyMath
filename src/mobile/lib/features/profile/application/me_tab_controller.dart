// 나 탭 컨트롤러 — 진단 결과·학습 경로 두 섹션을 로드한다 (PATH-05).
//
// 경계(CLAUDE.md): 진단(BKT/IRT)·학습 경로 위상정렬 판정은 전부 서버(L2)가 내린다. 이
// 컨트롤러(L5)는 (1) 진단 목록을 조회하고 (2) 그 중 가장 약한(=목록 첫 항목, 서버가 이미
// 약점 먼저 정렬) 개념의 학습 경로를 조회할 뿐 — 어떤 수학·숙달 판정도 하지 않는다.
//
// **정직 원칙**: 401은 unauthenticated로, 그 외 실패는 error로 분리해 기록한다(일반 문구로
// 뭉개지 않음). has_cycle·빈 steps는 판정하지 않고 [LearningPath] 구조 그대로 상태에 담아
// 화면(presentation)이 직접 읽고 렌더하게 한다 — 컨트롤러가 "정상/이상"을 대신 요약하지 않는다.
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/update_required.dart';
import '../../problems/data/problem_models.dart';
import '../../problems/data/problems_api.dart';
import 'me_tab_state.dart';

part 'me_tab_controller.g.dart';

/// 진단 결과 조회 시 요청할 상한(대역폭·화면 — `diagnosis_controller.dart` 관례 답습).
const int _diagnosisLimit = 20;

/// 나 탭(학습 경로·진단 결과) 상태를 관장하는 Riverpod Notifier.
@riverpod
class MeTabController extends _$MeTabController {
  @override
  MeTabState build() => const MeTabState();

  /// 진단 결과를 조회하고, 있으면 가장 약한 개념의 학습 경로를 이어서 조회한다.
  ///
  /// 흐름: ① 진단 목록 로드 → ② 401이면 두 섹션 모두 unauthenticated로 정직 표시 → ③ 그 외
  /// 실패면 진단은 error, 학습 경로는 "진단 실패로 대상을 못 골랐다"는 명시적 error → ④ 진단이
  /// 비어 있으면(정상) 학습 경로도 "대상 없음" loaded(steps 없음이 아니라 애초에 조회 대상이
  /// 없었음을 [learningPath]==null·[learningPathConceptName]==null로 구분) → ⑤ 있으면 첫
  /// 항목(서버가 이미 약점 먼저 정렬)으로 학습 경로 조회.
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
        );
        return;
      }
      // 426(최소버전 미달)만 전용 문구(판정 좌석 = core/update_required 단일·OPS-35).
      state = state.copyWith(
        diagnosisStatus: SectionStatus.error,
        diagnosisError:
            updateRequiredMessageOf(e) ?? '진단 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
        learningPathStatus: SectionStatus.error,
        learningPathError: '진단 결과를 불러오지 못해 학습 경로를 확인할 수 없어요.',
      );
      return;
    } catch (_) {
      state = state.copyWith(
        diagnosisStatus: SectionStatus.error,
        diagnosisError: '진단 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
        learningPathStatus: SectionStatus.error,
        learningPathError: '진단 결과를 불러오지 못해 학습 경로를 확인할 수 없어요.',
      );
      return;
    }

    state = state.copyWith(
      diagnosisStatus: SectionStatus.loaded,
      diagnoses: diagnoses,
    );

    if (diagnoses.isEmpty) {
      // 진단 근거가 아직 없음(정상) — 학습 경로도 조회할 대상 개념이 없다는 것을 그대로 반영.
      state = state.copyWith(
        learningPathStatus: SectionStatus.loaded,
        learningPath: null,
        learningPathConceptName: null,
      );
      return;
    }

    // 서버가 이미 "약점 먼저" 정렬해 돌려준다(me.py get_my_concept_diagnosis 문서 계약).
    await _loadLearningPath(diagnoses.first);
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
        learningPathError:
            updateRequiredMessageOf(e) ?? '학습 경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    } catch (_) {
      state = state.copyWith(
        learningPathStatus: SectionStatus.error,
        learningPathError: '학습 경로를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  bool _isUnauthenticated(DioException e) => e.response?.statusCode == 401;
}
