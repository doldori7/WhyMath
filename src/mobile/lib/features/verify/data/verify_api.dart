// 독립 검증 API 클라이언트 — POST /v1/verify-solution(3-tier 단계 검증). S1 Slice 4.
//
// 경계(CLAUDE.md): 분해된 풀이 단계를 보내고 검증 결과 구조를 그대로 받는다. 수학 검증(SymPy 동치)은
// 전부 서버(L3)가 하고 클라는 렌더만 한다(표현≠의미). 코치 응답의 solution_verification과 *독립*으로
// 호출해 정합(first_incorrect_index 일치)을 확인하는 데 쓴다(백엔드 E2E 앵커 6단계 미러).
//
// 응답 모델은 코치와 동일한 `SolutionVerificationResult`를 재사용한다(같은 백엔드 스키마·중복 모델 회피).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../chat/data/coach_models.dart';

/// 독립 3-tier 검증 호출 래퍼 — Dio로 직렬화·역직렬화를 담당(`coach_api.dart` 동형).
class VerifyApi {
  VerifyApi(this._dio);

  final Dio _dio;

  /// `POST /v1/verify-solution` — 분해된 풀이 [steps]의 단계 전이를 검증한다.
  ///
  /// [stepTypes]를 주면 길이는 `steps.length-1`이어야 한다(백엔드 422 방지). steps가 2개 미만이면
  /// 백엔드가 빈 결과(n_transitions=0)를 안전히 돌려준다. 정답을 알지 못하는 검증이라 응답엔 정답이
  /// 실리지 않는다(state·카운트·사유뿐).
  Future<SolutionVerificationResult> verifySolution(
    List<String> steps, {
    List<String?>? stepTypes,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/verify-solution',
      data: <String, dynamic>{
        'steps': steps,
        if (stepTypes != null) 'step_types': stepTypes,
      },
    );
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: 'verify 응답 본문이 비어 있습니다.',
      );
    }
    return SolutionVerificationResult.fromJson(data);
  }
}

/// [VerifyApi] provider — 공유 [dioProvider]를 주입받는다([coachApiProvider]와 동형).
final verifyApiProvider = Provider<VerifyApi>((ref) {
  return VerifyApi(ref.watch(dioProvider));
});
