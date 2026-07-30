// 정답 제출 컨트롤러 — 학생 최종답을 서버에 제출해 서버 권위로 채점하고 진행 여부를 노출한다.
//
// 학습 루프 닫힘의 클라이언트 축(G1·S3-09): "정답 제출 → 서버 correct면 → 다음 문항 진행"을 담당한다.
// 서버 축(G2)이 정답을 서버 권위로 채점하고 ProblemAttempt를 적재하므로, 그 문항이 next-problem의
// 미시도 필터(NOT IN)에서 제외된다 — 클라는 correct 확정 시 문제 화면으로 돌아가기만 하면(재-fetch)
// 루프가 닫힌다(전환은 화면이 `context.go(problemPath)`로 한다).
//
// 경계(CLAUDE.md "수학 로직을 클라에 넣지 않는다"): 이 컨트롤러는 정답 여부를 *판단하지 않는다*. 학생
// 최종답을 [AttemptsApi]로 제출하고, 서버가 돌려준 verification_state만 상태로 노출할 뿐이다(진행
// 결정은 화면이 verification_state를 읽어 내린다). 부수효과는 [AttemptsApi] 호출 하나뿐.
//
// 코드젠 방침: chat_controller(@riverpod)와 달리 이 얇은 컨트롤러는 수동 Notifier로 둔다
// (active_problem의 수동 provider 선례) — 자립적 슬라이스라 새 build_runner 산출물을 더하지 않는다.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../problems/application/active_problem.dart';
import '../../problems/data/attempts_api.dart';
import '../../problems/data/attempts_models.dart';

/// 정답 제출 화면 상태 — 제출 중·서버 채점 결과·에러(불변).
class AttemptSubmitState {
  const AttemptSubmitState({
    this.isSubmitting = false,
    this.result,
    this.error,
  });

  /// 서버 채점 응답 대기 중인지(중복 제출 방지·로딩 표시).
  final bool isSubmitting;

  /// 마지막 서버 채점 결과(없으면 아직 제출 안 함). verification_state로 진행 여부를 판단한다.
  final AttemptSubmitResponse? result;

  /// 마지막 제출 실패 메시지(없으면 null). 가용성을 위해 앱은 죽지 않는다.
  final String? error;

  /// 불변 갱신 — 필드별 덮어쓰기. nullable 필드를 null로 *비우려면* [clearResult]/[clearError]
  /// 플래그를 쓴다(freezed 없이 "값 유지 vs 명시적 null"을 구분하기 위한 수동 copyWith 관용구).
  AttemptSubmitState copyWith({
    bool? isSubmitting,
    AttemptSubmitResponse? result,
    String? error,
    bool clearResult = false,
    bool clearError = false,
  }) {
    return AttemptSubmitState(
      isSubmitting: isSubmitting ?? this.isSubmitting,
      result: clearResult ? null : (result ?? this.result),
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// 정답 제출 흐름을 관장하는 수동 Riverpod Notifier.
class AttemptController extends Notifier<AttemptSubmitState> {
  @override
  AttemptSubmitState build() => const AttemptSubmitState();

  /// 학생 최종답을 서버에 제출해 서버 권위로 채점한다(G1).
  ///
  /// 흐름: ① 빈 답·전송 중·활성 문제 없음 방어 → ② 제출중 표시(이전 결과·에러 클리어) →
  /// ③ `POST /v1/me/attempts` → ④ 성공 시 결과 노출(화면이 verification_state로 진행 판단) →
  /// ⑤ 실패는 graceful(에러만 기록·앱 안 죽음). 정답 여부는 서버가 판정한다 — 이 메서드는 어떤
  /// 수학 판단도 하지 않는다(표현≠의미). 활성 문제 id는 [activeProblemProvider]에서 읽는다.
  Future<void> submit(String studentAnswer) async {
    final trimmed = studentAnswer.trim();
    if (trimmed.isEmpty || state.isSubmitting) {
      return; // 빈 답·전송 중 재진입 방지.
    }
    final problemId = ref.read(activeProblemProvider)?.problemId;
    if (problemId == null) {
      return; // 활성 문제가 없으면 채점 대상(problem_id)이 없다(방어).
    }
    state = state.copyWith(
      isSubmitting: true,
      clearError: true,
      clearResult: true,
    );
    try {
      final result = await ref.read(attemptsApiProvider).submitAttempt(
            problemId: problemId,
            studentAnswer: trimmed,
          );
      state = state.copyWith(isSubmitting: false, result: result);
    } catch (e) {
      state = state.copyWith(
        isSubmitting: false,
        error: '답을 제출하지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 결과 카드를 닫는다(오답·미검증에서 코치와 계속 이어갈 때·정답 진행 직전 정리).
  void clearResult() {
    if (state.result != null) {
      state = state.copyWith(clearResult: true);
    }
  }

  /// 표시된 에러를 지운다(SnackBar 닫힘 등에서 호출).
  void clearError() {
    if (state.error != null) {
      state = state.copyWith(clearError: true);
    }
  }
}

/// [AttemptController] provider — 수동 [NotifierProvider](코드젠 없이 이 슬라이스를 자립시킨다).
final attemptControllerProvider =
    NotifierProvider<AttemptController, AttemptSubmitState>(
  AttemptController.new,
);
