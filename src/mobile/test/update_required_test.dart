// 서버 최소버전 계약(426) 판정 단일 좌석 테스트 — core/update_required (OPS-35).
//
// 배경: OPS-17이 426 게이트를 서버에 착지시켰을 때 클라 분기는 diagnosis_controller 1곳뿐
// 이었고, 그 분기를 검증하는 테스트도 0건이었다(임계 상향 시 나머지 화면에서는 차단이
// "일반 실패" 문구로 위장 — `service_operations_gap_review_r2.md` §2 G2). 이 파일이
// ⑴ 판정 함수 자체의 계약(426만 문구·그 외 null)과 ⑵ 컨트롤러 레벨에서 426 vs 일반
// 실패가 **실제로 다른 문구**를 내는지(변별력 양방향)를 함께 동결한다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/update_required.dart';
import 'package:korean_math_app/features/problems/application/diagnosis_controller.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';

/// 지정한 statusCode의 응답을 담은 DioException을 만든다(판정 입력 표본).
DioException _dioWithStatus(int statusCode) {
  final options = RequestOptions(path: '/x');
  return DioException(
    requestOptions: options,
    response: Response<void>(requestOptions: options, statusCode: statusCode),
  );
}

/// next-problem 조회가 지정한 예외를 던지는 fake — 컨트롤러 catch 경로 검증용.
class _ThrowingProblemsApi extends ProblemsApi {
  _ThrowingProblemsApi(this.toThrow) : super(Dio());

  final Object toThrow;

  @override
  Future<NextProblemResponse> getNextProblem({
    bool prioritizeWeakConcepts = false,
  }) async {
    throw toThrow;
  }
}

ProviderContainer _containerWith(ProblemsApi api) {
  final container = ProviderContainer(
    overrides: [problemsApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('updateRequiredMessageOf — 판정 함수 계약', () {
    test('426 DioException → 전용 업데이트 문구', () {
      expect(updateRequiredMessageOf(_dioWithStatus(426)), updateRequiredMessage);
    });

    test('426이 아닌 상태코드(401·404·503)는 null — 다른 실패를 가로채지 않는다', () {
      for (final code in const [401, 404, 422, 503]) {
        expect(updateRequiredMessageOf(_dioWithStatus(code)), isNull, reason: 'status $code');
      }
    });

    test('응답 없는 DioException(네트워크 실패)·비Dio 예외는 null', () {
      expect(
        updateRequiredMessageOf(DioException(requestOptions: RequestOptions(path: '/x'))),
        isNull,
      );
      expect(updateRequiredMessageOf(StateError('boom')), isNull);
    });
  });

  group('컨트롤러 소비 — 426 vs 일반 실패가 다른 문구를 낸다(변별력 양방향)', () {
    test('426: 전용 업데이트 문구가 상태에 실린다', () async {
      final container = _containerWith(_ThrowingProblemsApi(_dioWithStatus(426)));

      await container.read(diagnosisControllerProvider.notifier).load();

      expect(container.read(diagnosisControllerProvider).error, updateRequiredMessage);
    });

    test('일반 실패(500): 기존 graceful 문구 유지 — 426 문구가 새지 않는다', () async {
      final container = _containerWith(_ThrowingProblemsApi(_dioWithStatus(500)));

      await container.read(diagnosisControllerProvider.notifier).load();

      final error = container.read(diagnosisControllerProvider).error;
      expect(error, isNot(updateRequiredMessage));
      expect(error, contains('문제를 불러오지 못했어요'));
    });
  });
}
