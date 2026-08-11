// 진단 컨트롤러 — CAT 추천(next-problem)으로 문제를 확보하고 개념 진단을 함께 로드한다.
//
// 경계(CLAUDE.md): 출제·진단(IRT/BKT) 결정은 전부 서버(L2)가 내린다. 이 컨트롤러(L5)는
// (1) next-problem을 조회해 problem_id를 얻고 (2) 그 문제 상세를 로드하며 (3) 개념 진단 목록을
// 곁들일 뿐이다 — 어떤 수학·능력 판정도 하지 않는다(수학 로직 클라 미구현·표현≠의미).
//
// 흐름(백엔드 E2E 테스트 미러): GET /v1/me/next-problem → (problem_id 있으면) GET
// /v1/problems/{id} + GET /v1/me/diagnosis/concepts. problem_id가 null이면 후보 없음으로
// graceful 종료(noCandidate)한다 — 앱은 코치 없이도 진행 가능해야 한다(가용성).
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/update_required.dart';
import '../data/problem_models.dart';
import '../data/problems_api.dart';
import 'diagnosis_state.dart';

part 'diagnosis_controller.g.dart';

/// 진단(CAT)→문제제시 흐름을 관장하는 Riverpod Notifier.
@riverpod
class DiagnosisController extends _$DiagnosisController {
  @override
  DiagnosisState build() => const DiagnosisState();

  /// CAT 추천으로 다음 문제를 확보하고 상세·진단을 로드한다.
  ///
  /// ① next-problem 조회 → ② problem_id가 null이면 noCandidate로 종료(정상) →
  /// ③ 있으면 문제 상세 로드 + 개념 진단 목록 로드(진단 실패는 문제 로드를 막지 않는다) →
  /// ④ 실패는 에러만 남기고 앱을 막지 않는다(가용성). 중복 호출(isLoading)은 무시한다.
  Future<void> load({bool prioritizeWeakConcepts = false}) async {
    if (state.isLoading) {
      return; // 조회 중 재진입 방지.
    }
    state = state.copyWith(isLoading: true, error: null, noCandidate: false);
    try {
      final next = await ref
          .read(problemsApiProvider)
          .getNextProblem(prioritizeWeakConcepts: prioritizeWeakConcepts);

      final pid = next.problemId;
      if (pid == null) {
        // 추천 후보 없음 — 문제 없이 정상 종료(측정 충분·또는 미시딩).
        state = state.copyWith(
          isLoading: false,
          nextProblem: next,
          problem: null,
          noCandidate: true,
        );
        return;
      }

      final problem = await ref.read(problemsApiProvider).getProblem(pid);
      // 개념 진단은 곁들이는 정보 — 실패해도 문제 제시를 막지 않는다.
      final diagnoses = await _loadDiagnosesSafely();

      state = state.copyWith(
        isLoading: false,
        nextProblem: next,
        problem: problem,
        diagnoses: diagnoses,
        noCandidate: false,
      );
    } catch (e) {
      // OPS-17·35: 서버 최소버전 계약 미달(426)은 전용 문구(판정 좌석은 core/update_required
      // 단일) — 그 외 네트워크·인증 실패는 graceful 문구로 앱을 막지 않는다.
      state = state.copyWith(
        isLoading: false,
        error: updateRequiredMessageOf(e) ?? '문제를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 개념 진단 목록을 안전하게 로드한다 — 실패 시 빈 리스트(문제 제시는 계속된다).
  Future<List<ConceptDiagnosisItem>> _loadDiagnosesSafely() async {
    try {
      return await ref
          .read(problemsApiProvider)
          .getDiagnosisConcepts(limit: 20);
    } catch (_) {
      return const <ConceptDiagnosisItem>[];
    }
  }
}
