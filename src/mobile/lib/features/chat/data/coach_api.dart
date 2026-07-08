// L4 코치 API 클라이언트 — `POST /v1/coach`(스테이트리스 통합 결정) 호출.
//
// 경계(CLAUDE.md): 요청을 보내고 `CoachResponse`를 구조 그대로 받는다. 수학·교수학 결정은
// 전부 서버(L4)가 내리고, 클라는 결과를 렌더링만 한다(표현≠의미). 인증 헤더·세션 토큰은
// 후속 슬라이스(인증 플로우 도입 시 인터셉터로 추가).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'coach_models.dart';

/// 코치 엔드포인트 호출 래퍼 — Dio로 직렬화·역직렬화를 담당.
///
/// retrofit 코드젠 대신 명시적 메서드를 둔다(보수적·디버깅 용이·이번 슬라이스 범위 최소).
/// 엔드포인트가 늘면 retrofit `@RestApi`로 전환 검토.
class CoachApi {
  CoachApi(this._dio);

  final Dio _dio;

  /// `POST /v1/coach` — 학생 발화·상태를 보내고 통합 교수학 결정을 받는다.
  ///
  /// 스테이트리스(DB 무접근·LLM 호출 0) 엔드포인트. 세션 영속이 필요 없는 자유 대화·단건
  /// 진단에 쓴다. S1 학습 루프는 영속이 필요해 [createSession]/[addTurn]을 쓴다(턴·가설 누적).
  Future<CoachResponse> coach(CoachRequest request) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/coach',
      data: request.toJson(),
    );
    return CoachResponse.fromJson(_requireBody(response));
  }

  /// `POST /v1/coach/sessions` — 대화 세션을 생성하고 첫 교환을 영속한다.
  ///
  /// [problemId]가 있으면 대화를 그 문제에 묶는다(dialogue.problem_id). 반환된 dialogue_id를
  /// 이후 [addTurn]·[getSession]에 재사용한다. 응답은 `CoachResponse` + 영속 식별자(상위 스키마)라
  /// [CoachTurnResult]로 렌더 가능한 결정과 dialogue_id를 함께 돌려준다.
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    final body = request.toJson();
    if (problemId != null) {
      body['problem_id'] = problemId;
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/sessions',
      data: body,
    );
    final data = _requireBody(response);
    return CoachTurnResult.fromJson(
      data,
      dialogueId: data['dialogue_id'] as String,
    );
  }

  /// `POST /v1/coach/sessions/{id}/turns` — 기존 세션에 학생·AI 턴 한 쌍을 추가한다.
  ///
  /// 요청은 순수 `CoachRequest`(problem_id는 세션에서 조회). 소유권 불일치·부재 시 백엔드는
  /// 404(존재 노출 회피)를 내며, 호출자(컨트롤러)가 graceful 처리한다. dialogue_id는 URL이라
  /// 응답 본문에 없으므로 [dialogueId]를 그대로 결과에 싣는다.
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/sessions/$dialogueId/turns',
      data: request.toJson(),
    );
    return CoachTurnResult.fromJson(
      _requireBody(response),
      dialogueId: dialogueId,
    );
  }

  /// `GET /v1/coach/sessions/{id}` — 세션 메타 + 턴 목록(turn_order ASC). 턴 영속 확인용.
  ///
  /// 백엔드 응답은 `{dialogue: {...}, turns: [...]}` 중첩 구조라 여기서 풀어 [CoachSessionSnapshot]
  /// 으로 옮긴다(모델의 flat fromJson에 의존하지 않는다).
  Future<CoachSessionSnapshot> getSession(String dialogueId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/coach/sessions/$dialogueId',
    );
    final data = _requireBody(response);
    final dialogue =
        (data['dialogue'] as Map<String, dynamic>?) ?? const <String, dynamic>{};
    final turns = ((data['turns'] as List<dynamic>?) ?? <dynamic>[])
        .map((e) => CoachTurn.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
    return CoachSessionSnapshot(
      dialogueId: (dialogue['dialogue_id'] as String?) ?? dialogueId,
      totalTurns: (dialogue['total_turns'] as num?)?.toInt(),
      turns: turns,
    );
  }

  /// 응답 본문이 null이 아님을 보장하고 반환한다(빈 본문은 DioException으로 승격).
  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '코치 응답 본문이 비어 있습니다.',
      );
    }
    return data;
  }
}

/// [CoachApi] provider — 공유 [dioProvider]를 주입받는다.
final coachApiProvider = Provider<CoachApi>((ref) {
  return CoachApi(ref.watch(dioProvider));
});
