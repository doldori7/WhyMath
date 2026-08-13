// 풀이 경로 단계 API 클라이언트 — `GET /v1/solution-paths/{id}/steps?up_to=n`(SOL-02) 호출.
//
// 경계(CLAUDE.md): 요청을 보내고 `SolutionStepsPage`를 구조 그대로 받는다. 단계 생성·검증은
// 전부 서버(L3/L4)가 하고, 클라는 받은 단계를 렌더만 한다(표현≠의미). 인증 헤더는 공유 Dio의
// AuthInterceptor가 Bearer로 첨부한다. `scene_api.dart`·`coach_api.dart` 패턴을 그대로 따른다
// (retrofit 코드젠 대신 명시적 메서드 — 보수적·디버깅 용이).
//
// 교수학 경계(SOL-02 ⑤·deferred): 호출자는 학생이 스스로 펼친 단계 수까지만 `upTo`로 요청한다
// — 미펼침 단계 내용을 클라 메모리에도 갖지 않는다(서버 측 점층 공개).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'solution_path_models.dart';

/// 풀이 경로 엔드포인트 호출 래퍼 — Dio로 역직렬화를 담당(`CoachApi` 관례).
class SolutionPathApi {
  SolutionPathApi(this._dio);

  final Dio _dio;

  /// `GET /v1/solution-paths/{solutionPathId}/steps?up_to=upTo` — 1..[upTo] 단계를 받는다.
  ///
  /// 서버는 요청한 `up_to`까지만 공개한다(점층 공개). 빈 본문이면 `DioException`으로 승격한다
  /// (`CoachApi._requireBody` 관례).
  Future<SolutionStepsPage> fetchSteps(
    String solutionPathId, {
    required int upTo,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/solution-paths/$solutionPathId/steps',
      queryParameters: <String, dynamic>{'up_to': upTo},
    );
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: 'solution-paths/$solutionPathId/steps 응답 본문이 비어 있습니다.',
      );
    }
    return SolutionStepsPage.fromJson(data);
  }
}

/// [SolutionPathApi] provider — 공유 [dioProvider]를 주입받는다([sceneApiProvider]와 동형).
final solutionPathApiProvider = Provider<SolutionPathApi>((ref) {
  return SolutionPathApi(ref.watch(dioProvider));
});
