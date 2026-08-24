// 성장 증거 API 클라이언트 — GET /v1/me/growth-evidence의 첫 모바일 소비자(MOB-17).
//
// 경계(CLAUDE.md): 요청을 보내고 [GrowthEvidenceResponse]를 구조 그대로 받는다. 지표 계산·
// 노출 판정·서술 변환은 전부 서버(L2/L4/노출 계약)가 내리고, 클라는 렌더링만 한다.
// 인증 헤더(Bearer)는 공유 dio의 AuthInterceptor가 자동으로 붙인다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'growth_evidence_models.dart';

/// 성장 증거 엔드포인트 호출 래퍼 — Dio로 직렬화·역직렬화를 담당.
///
/// retrofit 코드젠 대신 명시적 메서드를 둔다(보수적·디버깅 용이·problems_api.dart 동형).
class GrowthEvidenceApi {
  GrowthEvidenceApi(this._dio);

  final Dio _dio;

  /// `GET /v1/me/growth-evidence` — WH-1 대리 지표 학생 안전 노출.
  ///
  /// v0에서는 시간창·모드 필터를 받지 않고 서버 기본값을 그대로 쓴다(신규 쿼리 파라미터 0).
  /// 서버가 내려준 [GrowthEvidenceResponse.status]·[suppressedReason]·[narrative]를
  /// 화면에서 그대로 렌더한다(임계값 계산·라벨 판정·서술 생성 금지).
  Future<GrowthEvidenceResponse> getGrowthEvidence() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/v1/me/growth-evidence',
    );
    return GrowthEvidenceResponse.fromJson(_requireBody(response));
  }

  /// 응답 본문이 null이 아님을 보장하고 반환한다(빈 본문은 DioException으로 승격).
  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: '성장 증거 응답 본문이 비어 있습니다.',
      );
    }
    return data;
  }
}

/// [GrowthEvidenceApi] provider — 공유 [dioProvider]를 주입받는다.
final growthEvidenceApiProvider = Provider<GrowthEvidenceApi>((ref) {
  return GrowthEvidenceApi(ref.watch(dioProvider));
});
