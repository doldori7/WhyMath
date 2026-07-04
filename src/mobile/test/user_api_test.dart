// UserApi 단위테스트 — 온보딩 입력 PATCH /v1/users/me 배선 검증. S1-c.
//
// 네트워크 없이: capture HttpClientAdapter(canned 200 응답)로 PATCH 경로·메서드·본문을
// 검증한다(auth_api_test 어댑터 패턴). 화이트리스트 검증·미성년 파생·영속은 서버 —
// 클라는 채워진 필드만 부분 수정 dict로 보낼 뿐이다.
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/onboarding/data/user_api.dart';

class _Adapter implements HttpClientAdapter {
  RequestOptions? captured;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    captured = options;
    // patch_me는 갱신된 프로필을 돌려주지만 patchMe는 본문을 쓰지 않는다 — 빈 객체면 충분.
    return ResponseBody.fromString(
      jsonEncode(<String, dynamic>{}),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

UserApi _apiWith(_Adapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://x'))..httpClientAdapter = adapter;
  return UserApi(dio);
}

void main() {
  test('patchMe: /v1/users/me로 PATCH하고 본문을 그대로 싣는다', () async {
    final adapter = _Adapter();
    final api = _apiWith(adapter);

    await api.patchMe(<String, dynamic>{
      'target_grade': 2,
      'target_score': 130,
      'target_exam_date': '2026-11-19',
      'birth_year': 2008,
    });

    expect(adapter.captured, isNotNull);
    expect(adapter.captured!.path, '/v1/users/me');
    expect(adapter.captured!.method, 'PATCH');

    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body['target_grade'], 2);
    expect(body['target_score'], 130);
    // 목표 시험일은 YYYY-MM-DD 문자열로 전달된다(백엔드 date 타입).
    expect(body['target_exam_date'], '2026-11-19');
    expect(body['birth_year'], 2008);
    // is_minor는 서버가 birth_year에서 파생 — 클라는 보내지 않는다.
    expect(body.containsKey('is_minor'), isFalse);
  });

  test('patchMe: 부분 본문(일부 키만)도 그대로 전송한다', () async {
    final adapter = _Adapter();
    final api = _apiWith(adapter);

    await api.patchMe(<String, dynamic>{'target_grade': 1});

    final body = adapter.captured!.data as Map<String, dynamic>;
    expect(body.keys, <String>['target_grade']);
    expect(body['target_grade'], 1);
  });
}
