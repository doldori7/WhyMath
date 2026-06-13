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
  /// 스테이트리스(DB 무접근·LLM 호출 0) 엔드포인트. 영속이 필요하면 후속에서
  /// `/v1/coach/sessions`를 호출한다(세션 생성·턴 추가는 후속 슬라이스).
  Future<CoachResponse> coach(CoachRequest request) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/coach',
      data: request.toJson(),
    );
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: 'coach 응답 본문이 비어 있습니다.',
      );
    }
    return CoachResponse.fromJson(data);
  }
}

/// [CoachApi] provider — 공유 [dioProvider]를 주입받는다.
final coachApiProvider = Provider<CoachApi>((ref) {
  return CoachApi(ref.watch(dioProvider));
});
