// 풀이 채점 제출 API 클라이언트 — `POST /v1/me/attempts` 배선(G1 학습 루프 닫힘의 클라이언트 축).
//
// 경계(CLAUDE.md "수학 로직을 클라에 넣지 않는다"): 클라는 학생 최종답을 *제출*만 하고, 서버가 서버
// 권위로 채점한다. 응답 `verification_state`만 읽어 다음 문항 진행 여부를 화면이 결정한다(정답 판정은
// 독립 수학 코어가 권위·클라는 판정하지 않는다·표현≠의미). `problems_api.dart`/`coach_api.dart` 스타일을
// 그대로 따른다(Dio 주입·명시적 메서드·`dioProvider` 주입 provider).
//
// 인증 헤더(Bearer)는 공유 dio의 AuthInterceptor가 자동으로 붙인다(보호 엔드포인트·/v1/me/*).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'attempts_models.dart';

/// 풀이 채점 제출 엔드포인트 호출 래퍼 — Dio로 직렬화·역직렬화를 담당.
///
/// 읽기(문항·진단)는 [ProblemsApi], 채점 제출(쓰기)은 이 클래스로 나눈다(관심사 분리).
class AttemptsApi {
  AttemptsApi(this._dio);

  final Dio _dio;

  /// `POST /v1/me/attempts` — 학생 최종답을 서버에 제출해 서버 권위로 채점한다(성공 201).
  ///
  /// 서버 계약(잠금·S3-09):
  /// - [problemId] : 채점 대상 문제 FK(필수·현재 활성 문제 id).
  /// - [studentAnswer] : 학생 최종답(서버 채점에 **필수**) — 서버가 기대정답과 동치 검증한다.
  ///   예: "x=3", "a=2", "2개", "x=(5+1)/2=3".
  /// - `is_correct` : 스키마상 필수이나 **student_answer가 있으면 서버가 override**하므로 클라는
  ///   판정 못 하는 중립 기본값 `false`를 보낸다(서버 권위가 항상 이김·데모 문항은 기대정답 보유라
  ///   항상 override). 클라는 정답을 판정하지 않는다(수학 로직 클라 금지).
  /// - 선택: [durationSeconds](≥0)·[sessionId]·[confidenceSelfReported](0~1) — 있으면 싣고 없으면 생략.
  ///
  /// 백엔드는 `extra="forbid"`라 정의되지 않은 키를 거부한다 — 알려진 키만 싣는다.
  Future<AttemptSubmitResponse> submitAttempt({
    required String problemId,
    required String studentAnswer,
    int? durationSeconds,
    String? sessionId,
    double? confidenceSelfReported,
  }) async {
    final body = <String, dynamic>{
      'problem_id': problemId,
      'student_answer': studentAnswer,
      // 서버 override 전제 — 클라는 정답을 판정하지 않으므로 중립값(false)을 보낸다.
      // student_answer+기대정답이 있으면 서버 판정이 이 값을 덮어쓴다(S3-09 계약).
      'is_correct': false,
      if (durationSeconds != null) 'duration_seconds': durationSeconds,
      if (sessionId != null) 'session_id': sessionId,
      if (confidenceSelfReported != null)
        'confidence_self_reported': confidenceSelfReported,
    };
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/me/attempts',
      data: body,
    );
    return AttemptSubmitResponse.fromJson(_requireBody(response));
  }

  /// 응답 본문이 null이 아님을 보장하고 반환한다(빈 본문은 DioException으로 승격).
  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '채점 응답 본문이 비어 있습니다.',
      );
    }
    return data;
  }
}

/// [AttemptsApi] provider — 공유 [dioProvider]를 주입받는다(`problemsApiProvider`와 동형).
final attemptsApiProvider = Provider<AttemptsApi>((ref) {
  return AttemptsApi(ref.watch(dioProvider));
});
