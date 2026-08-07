// 문제·진단 API 클라이언트 — S1 루프의 진단(CAT)→문제제시 구간 배선.
//
// 경계(CLAUDE.md): 요청을 보내고 구조를 그대로 받는다. 출제·진단(IRT/BKT) 로직은 전부 서버(L2)가
// 내리고, 클라는 결과 JSON을 렌더링만 한다(수학 로직 클라 미구현·표현≠의미). `coach_api.dart`
// 구조를 그대로 따른다(Dio 주입·명시적 메서드·`dioProvider` 주입 provider).
//
// 인증 헤더(Bearer)는 공유 dio의 AuthInterceptor가 자동으로 붙인다(클라는 토큰 운반만).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'problem_models.dart';

/// 문제/진단 엔드포인트 호출 래퍼 — Dio로 직렬화·역직렬화를 담당.
///
/// retrofit 코드젠 대신 명시적 메서드를 둔다(보수적·디버깅 용이·`coach_api.dart` 동형).
class ProblemsApi {
  ProblemsApi(this._dio);

  final Dio _dio;

  /// `GET /v1/me/next-problem` — IRT 적응 출제(CAT). 다음 문항 추천 + 능력 스냅샷.
  ///
  /// [prioritizeWeakConcepts]가 true면 약개념 가중 정보량을 우선한다(서버 판정). 응답
  /// `problem_id`가 null이면 추천 후보가 없다(호출자가 graceful 처리).
  Future<NextProblemResponse> getNextProblem({
    bool prioritizeWeakConcepts = false,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/me/next-problem',
      queryParameters: <String, dynamic>{
        if (prioritizeWeakConcepts) 'prioritize_weak_concepts': true,
      },
    );
    return NextProblemResponse.fromJson(_requireBody(response));
  }

  /// `GET /v1/problems/{id}` — 문제 단건 조회.
  ///
  /// ⚠️ 백엔드는 answer를 응답에 실어 보내지만 [Problem] 모델이 그 키를 선언하지 않아
  /// 클라 객체에 진입하지 않는다(problem_models.dart 안전 주석). 정오 판단은 verify/coach 신호로만.
  Future<Problem> getProblem(String problemId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/problems/$problemId',
    );
    return Problem.fromJson(_requireBody(response));
  }

  /// `GET /v1/me/diagnosis/concepts` — BKT↔IRT 개념 진단 목록(coaching_focus 후보).
  ///
  /// [limit]으로 상위 N건만 받는다(대역폭·화면). 항목이 0개면 빈 리스트(진단 근거 부족·정상).
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async {
    final response = await _dio.get<List<dynamic>>(
      '/v1/me/diagnosis/concepts',
      queryParameters: <String, dynamic>{
        if (limit != null) 'limit': limit,
      },
    );
    final data = response.data ?? <dynamic>[];
    return data
        .map((e) => ConceptDiagnosisItem.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
  }

  /// `GET /v1/me/weak-concepts/{concept_id}/learning-path` — 약개념의 막힌 선수개념 학습 경로.
  ///
  /// 서버 기본 쿼리(threshold=0.7·weak_only=true·max_depth=1)를 그대로 쓴다(PATH-05 —
  /// 신규 파라미터 도입 없이 기존 단일-개념 API만 소비). 응답 `has_cycle`·빈 `steps`는 이
  /// 메서드가 그대로 통과시킨다(호출자가 정직하게 렌더 — 삼켜서 뭉개지 않음).
  Future<LearningPath> getLearningPath(String conceptId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/me/weak-concepts/$conceptId/learning-path',
    );
    return LearningPath.fromJson(_requireBody(response));
  }

  /// 응답 본문이 null이 아님을 보장하고 반환한다(빈 본문은 DioException으로 승격).
  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '응답 본문이 비어 있습니다.',
      );
    }
    return data;
  }
}

/// [ProblemsApi] provider — 공유 [dioProvider]를 주입받는다([coachApiProvider]와 동형).
final problemsApiProvider = Provider<ProblemsApi>((ref) {
  return ProblemsApi(ref.watch(dioProvider));
});
