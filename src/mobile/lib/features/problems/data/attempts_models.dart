// 풀이 채점 제출 응답 모델 — `POST /v1/me/attempts` 계약을 구조 그대로 옮긴다(G1 학습 루프 닫힘).
//
// 정본: `src/backend/whymath_backend/api/me.py`(`AttemptSubmitRequest`·`AttemptSubmitResponse`).
//
// **경계(CLAUDE.md "수학 로직을 클라에 넣지 않는다")**: 정답 여부는 *서버 권위*가 판정한다. 클라는
// 학생 최종답을 제출하고, 서버가 돌려준 [verificationState]만 읽어 다음 문항 진행 여부를 결정한다
// (표현≠의미·클라는 채점하지 않는다). [isCorrect]도 서버가 override한 최종값을 그대로 수신할 뿐이다.
//
// **코드젠 미도입**(coach_models.dart `CoachTurnResult` 선례): 응답 수신 홀더라 얇은 수동 fromJson로
// 충분하고, 새 build_runner 산출물(.freezed/.g)을 더하지 않아 이 슬라이스를 자립시킨다.

/// 서버 최종답 검증 상태 문자열 상수(l3/verify_final_answer.py `FinalAnswerState` 미러).
///
/// enum 대신 문자열 상수 — coach_models·problem_models의 "백엔드 문자열 enum은 String 유지" 방침과
/// 동일(codegen 리스크·과확장 회피·백엔드 값 보존). 클라는 오직 [correct]에서만 다음 문항으로 진행한다.
abstract final class VerificationState {
  /// 서버가 정답 동치를 결정론으로 확인 — *유일하게* 다음 문항 진행을 허용하는 상태.
  static const String correct = 'correct';

  /// 서버가 기대정답과 불일치를 확인 — 오답(코치 계속·진행 안 함).
  static const String incorrect = 'incorrect';

  /// 서버가 판정 불가(기대정답 미보유·파싱 불가 등) — 미검증(정직 안내·코치 계속).
  static const String unverifiable = 'unverifiable';
}

/// `POST /v1/me/attempts` 응답 — 적재된 attempt 식별자 + 서버 권위 채점 결과.
///
/// 이 슬라이스(G1)가 소비하는 필드만 선언한다: [attemptId]·[isCorrect]·[verificationState].
/// 백엔드가 함께 내리는 `mastery_updates`·`skill_mastery_updates`·`calibration_coaching`는 진행
/// 판단에 불필요해 수신하지 않는다(수동 fromJson는 미선언 키를 자연히 무시). 필요해지면 확장한다.
class AttemptSubmitResponse {
  const AttemptSubmitResponse({
    required this.attemptId,
    required this.isCorrect,
    required this.verificationState,
  });

  /// 적재된 attempt PK(UUID 문자열).
  final String attemptId;

  /// 서버가 적재한 최종 정답 여부(서버 검증 가능하면 서버 판정값·불가면 클라 폴백값).
  /// **진행 판단엔 쓰지 않는다** — 진행은 오직 [verificationState]로만 결정한다(S3-09 계약).
  final bool isCorrect;

  /// 서버 최종답 검증 상태("correct"·"incorrect"·"unverifiable"). 진행 판단의 유일 근거.
  final String verificationState;

  /// 서버가 정답을 *확인*했는가 — 다음 문항 진행을 허용하는 유일 조건(correct).
  bool get isVerifiedCorrect => verificationState == VerificationState.correct;

  /// 서버가 오답으로 *확인*했는가(incorrect) — 코치 계속·진행 안 함.
  bool get isVerifiedIncorrect =>
      verificationState == VerificationState.incorrect;

  /// 서버가 판정하지 *못했는가*(unverifiable) — 정직 안내·코치 계속.
  bool get isUnverifiable => verificationState == VerificationState.unverifiable;

  /// 응답 JSON을 옮긴다(미선언 키 무시). `verification_state` 부재 시 방어적으로 unverifiable로
  /// 낮춘다 — correct를 함부로 가정하지 않는다(진행 오작동보다 미검증 안내가 안전·정직).
  factory AttemptSubmitResponse.fromJson(Map<String, dynamic> json) {
    return AttemptSubmitResponse(
      attemptId: json['attempt_id'] as String? ?? '',
      isCorrect: json['is_correct'] as bool? ?? false,
      verificationState: json['verification_state'] as String? ??
          VerificationState.unverifiable,
    );
  }
}
