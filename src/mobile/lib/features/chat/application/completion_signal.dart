// 코치 완료 신호 — 서버 권위값 3필드의 클라 미러(problem_complete·awaiting_reflection·
// completed_attempt_id). S3-32의 *클라 절반*(MOB-20).
//
// 경계(CLAUDE.md · L5 = View Layer): 이 파일은 **어떤 판정도 하지 않는다.** "문제가 끝났는가",
// "돌아보기를 받아야 하는가"는 전부 서버(L4 코치)가 턴 응답에 실어 내려주는 값이고, 클라는 그
// 값을 *그대로* 보관해 화면 어포던스를 바꿀 뿐이다(점수 비교·정오 판정식 클라 금지).
//
// ⚠️ 재적재 금지: `problemComplete == true`면 서버가 이미 ProblemAttempt를 적재하고 숙달을
// 전파한 뒤다(api/coach.py `_complete_problem`). 그러므로 클라는 `POST /v1/me/attempts`를
// **부르지 않는다** — 부르면 attempt·숙달 이중 적재가 된다(계약 명문: api/coach.py
// `_PROBLEM_COMPLETE_DESC` "클라는 별도로 POST /v1/me/attempts를 부르지 않는다").
//
// 학습 세션(session_id) 축 — **미기록**(조용히 메우지 않는다):
//   `ProblemAttempt.session_id`(FK→learning_session)는 이 코치 완료 경로에서 *채워지지 않는다*.
//   서버 `_complete_problem`이 attempt를 적재할 때 session_id를 세팅하지 않고, 클라도 여기서
//   아무것도 제출하지 않으므로 실을 자리 자체가 없다. 코치 세션 식별자(`dialogue_id`)는
//   LearningSession PK가 *아니라* Dialogue PK이므로 그 자리에 대신 넣지 않는다 — 넣으면
//   존재하지 않는 세션을 가리키는 가짜 참조가 된다. 즉 "해당 없음"이 아니라 **알려진 미기록**이며,
//   메우는 일은 LearningSession writer가 생기는 시점의 *서버* 과제다(클라 우회 금지).
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/legacy.dart';

/// 코치 턴 1회가 남긴 완료 신호(서버 권위값 미러·불변).
///
/// - [problemComplete] : 이 턴에 문제가 완료됐는지 — *다음 문항으로 진행* 어포던스의 유일한 근거.
/// - [awaitingReflection] : 정답 도달 후 Polya 돌아보기(메타인지) 1턴을 대기 중인지 — 진행 보류 UX.
/// - [completedAttemptId] : 완료 시 서버가 적재한 ProblemAttempt PK(완료가 아니면 null).
///   학생에게 표시하지 않는다(UUID는 학습 정보가 아니다) — 완료 패널의 *동일성 키*로만 쓴다.
@immutable
class CoachCompletionSignal {
  const CoachCompletionSignal({
    this.problemComplete = false,
    this.awaitingReflection = false,
    this.completedAttemptId,
  });

  /// 신호 없음(초기값·턴 전송 시작 시 되돌아가는 상태).
  static const CoachCompletionSignal none = CoachCompletionSignal();

  /// 이 턴에 문제가 완료됐는지(서버 `problem_complete`·부재 시 false).
  final bool problemComplete;

  /// 돌아보기(메타인지) 응답 대기 중인지(서버 `awaiting_reflection`·부재 시 false).
  final bool awaitingReflection;

  /// 서버가 적재한 ProblemAttempt PK(서버 `completed_attempt_id`·완료 아니면 null).
  final String? completedAttemptId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CoachCompletionSignal &&
          other.problemComplete == problemComplete &&
          other.awaitingReflection == awaitingReflection &&
          other.completedAttemptId == completedAttemptId;

  @override
  int get hashCode =>
      Object.hash(problemComplete, awaitingReflection, completedAttemptId);

  @override
  String toString() => 'CoachCompletionSignal(problemComplete: $problemComplete, '
      'awaitingReflection: $awaitingReflection, '
      'completedAttemptId: $completedAttemptId)';
}

/// 마지막 코치 턴의 완료 신호 — 컨트롤러가 쓰고 채팅 화면이 읽는다.
///
/// `ChatState`(freezed)에 필드를 더하지 않고 별도 provider로 두는 이유: 이 값은 *서버 턴 응답의
/// 파생 신호*라 대화 누적(messages·polyaState)과 수명이 다르고, 활성 문제 전달과 같은 단방향
/// 표현 상태 1건이라 기존 `activeProblemProvider`와 같은 형태를 따른다(소비처가 늘면 Notifier 승격).
final coachCompletionSignalProvider = StateProvider<CoachCompletionSignal>(
  (ref) => CoachCompletionSignal.none,
);
