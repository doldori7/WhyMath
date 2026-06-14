// L5 학습 장면 API 클라이언트 — `POST /v1/scenes/weak-concept`(약점개념→LearningScene) 호출.
//
// 경계(CLAUDE.md): 요청을 보내고 `LearningScene` 명세를 구조 그대로 받는다. 장면의 생성·검증
// (결정론 골격·불변식·참조 무결성)은 전부 서버(L4·S2/S3/S5a)가 하고, 클라는 받은 명세를
// `SceneRenderer`로 렌더만 한다(표현≠의미). 인증 헤더는 후속(OAuth 인터셉터 도입 시) — 실
// 호출은 인증 후. `coach_api.dart` 패턴을 그대로 따른다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import 'scene_models.dart';

/// 장면 엔드포인트 호출 래퍼 — Dio로 역직렬화를 담당(`CoachApi` 관례).
class SceneApi {
  SceneApi(this._dio);

  final Dio _dio;

  /// `POST /v1/scenes/weak-concept` — 인증 학생의 *가장 약한 개념* 맞춤 학습 장면을 받는다.
  ///
  /// 요청 본문은 없다(서버가 토큰으로 학생을 식별·L2 진단으로 약점 선택). 응답은 검증된
  /// `LearningScene` 명세(서버 불변식 통과). 빈 본문이면 `DioException`.
  Future<LearningScene> fetchWeakConceptScene() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/scenes/weak-concept',
    );
    final data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        error: 'scenes/weak-concept 응답 본문이 비어 있습니다.',
      );
    }
    return LearningScene.fromJson(data);
  }
}

/// [SceneApi] provider — 공유 [dioProvider]를 주입받는다([coachApiProvider]와 동형).
final sceneApiProvider = Provider<SceneApi>((ref) {
  return SceneApi(ref.watch(dioProvider));
});
