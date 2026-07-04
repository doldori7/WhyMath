// 사용자 프로필 API 클라이언트 — 온보딩 입력을 본인 프로필에 부분 반영. S1-c.
//
// 경계(CLAUDE.md): 클라는 온보딩에서 모은 학습 목표(목표 등급·점수·시험일·출생연도)를
// 부분 수정 dict로 보내고, 서버(`users.py` `patch_me`)가 화이트리스트 검증·미성년 `is_minor`
// 파생·영속을 전담한다 — 클라는 *수집·전달*만 한다(판정 로직 클라 미구현·표현≠의미).
// `auth_api.dart` 구조를 그대로 따른다(Dio 주입·명시적 메서드·`dioProvider` 주입 provider).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';

/// 본인 프로필 부분 수정 호출 래퍼 — 온보딩 입력을 PATCH로 반영한다.
class UserApi {
  UserApi(this._dio);

  final Dio _dio;

  /// `PATCH /v1/users/me` — [body]의 화이트리스트 필드만 부분 수정한다.
  ///
  /// [body]는 *채워진 필드만* 담은 dict다(빈 값은 호출자가 제외한다·부분 수정). 백엔드는
  /// `ConsentedUser` 게이트(인증+미성년 동의) 뒤에 있고 화이트리스트 밖 키를 422로 거부하므로,
  /// 호출자는 `target_grade`·`target_score`·`target_exam_date`·`birth_year` 등 자가수정
  /// 가능 키만 넣는다. `is_minor`는 서버가 `birth_year`에서 파생하므로 클라가 보내지 않는다.
  ///
  /// If-Match(낙관적 동시성)는 초기 생략한다 — 백엔드 `ensure_if_match(None, ...)`는 헤더가
  /// 없으면 전제조건 없이 통과시킨다(비파괴·기존 클라 호환). 온보딩은 최초 1회 입력이라 동시
  /// 편집 충돌이 사실상 없어 GET ETag 선행을 두지 않는다(후속에서 조건부 PATCH 도입 가능).
  ///
  /// 인증 헤더(Bearer)는 공유 dio의 [AuthInterceptor]가 자동으로 붙인다(클라는 토큰 운반만).
  /// 미성년 미동의 시 403이 올 수 있으나 이 래퍼는 상태 코드를 [DioException]으로 올려 보내고,
  /// graceful 처리(온보딩 진행 유지)는 호출자(컨트롤러)가 한다.
  Future<void> patchMe(Map<String, dynamic> body) async {
    await _dio.patch<Map<String, dynamic>>('/v1/users/me', data: body);
  }
}

/// [UserApi] provider — 공유 [dioProvider]를 주입받는다([authApiProvider]와 동형).
final userApiProvider = Provider<UserApi>((ref) {
  return UserApi(ref.watch(dioProvider));
});
