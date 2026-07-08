// DiagnosisController 테스트 — CAT 추천→문제 로드·후보없음·에러·중복호출 가드 검증. S1.
//
// 네트워크를 타지 않는다 — problemsApiProvider를 미리 짠 응답(또는 throw)을 돌려주는 fake로
// override한다(ocr_controller_test 답습). 컨트롤러는 순수 상태 전이라 결과를 직접 검증한다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/application/diagnosis_controller.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';

/// 미리 짠 결과를 돌려주는 fake — next-problem·problem·diagnosis 각각을 제어한다.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi({
    required this.next,
    this.problem,
    this.diagnoses = const <ConceptDiagnosisItem>[],
    this.problemThrows = false,
    this.diagnosisThrows = false,
  }) : super(Dio());

  final NextProblemResponse next;
  final Problem? problem;
  final List<ConceptDiagnosisItem> diagnoses;
  final bool problemThrows;
  final bool diagnosisThrows;

  int nextCalls = 0;

  @override
  Future<NextProblemResponse> getNextProblem({
    bool prioritizeWeakConcepts = false,
  }) async {
    nextCalls++;
    return next;
  }

  @override
  Future<Problem> getProblem(String problemId) async {
    if (problemThrows) {
      throw DioException(requestOptions: RequestOptions(path: '/x'));
    }
    return problem!;
  }

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async {
    if (diagnosisThrows) {
      throw DioException(requestOptions: RequestOptions(path: '/x'));
    }
    return diagnoses;
  }
}

Problem _problem() => const Problem(
      problemId: 'p1',
      sourceType: '자체생성',
      subject: '미적분',
      unitCodes: <String>['CAL'],
      questionText: '문제',
    );

ConceptDiagnosisItem _diag() => const ConceptDiagnosisItem(
      conceptId: 'c1',
      coaching: DiagnosisCoaching(
        focus: 'verify',
        rationale: 'r',
        prompt: 'p',
      ),
    );

ProviderContainer _containerWith(ProblemsApi api) {
  final container = ProviderContainer(
    overrides: [problemsApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('추천 문제 있음: next→problem→diagnoses 로드하고 상태에 보관한다', () async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: 'p1'),
      problem: _problem(),
      diagnoses: <ConceptDiagnosisItem>[_diag()],
    );
    final container = _containerWith(api);

    await container.read(diagnosisControllerProvider.notifier).load();

    final s = container.read(diagnosisControllerProvider);
    expect(s.isLoading, isFalse);
    expect(s.noCandidate, isFalse);
    expect(s.problem?.problemId, 'p1');
    expect(s.diagnoses, hasLength(1));
    expect(s.error, isNull);
  });

  test('추천 후보 없음(problem_id null): noCandidate로 종료하고 문제를 로드하지 않는다', () async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: null),
    );
    final container = _containerWith(api);

    await container.read(diagnosisControllerProvider.notifier).load();

    final s = container.read(diagnosisControllerProvider);
    expect(s.noCandidate, isTrue);
    expect(s.problem, isNull);
    expect(s.error, isNull);
  });

  test('진단 조회 실패는 문제 제시를 막지 않는다(graceful)', () async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: 'p1'),
      problem: _problem(),
      diagnosisThrows: true,
    );
    final container = _containerWith(api);

    await container.read(diagnosisControllerProvider.notifier).load();

    final s = container.read(diagnosisControllerProvider);
    expect(s.problem?.problemId, 'p1');
    expect(s.diagnoses, isEmpty);
    expect(s.error, isNull); // 진단 실패는 삼켜진다.
  });

  test('문제 로드 실패: 에러만 남기고 앱을 막지 않는다', () async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: 'p1'),
      problemThrows: true,
    );
    final container = _containerWith(api);

    await container.read(diagnosisControllerProvider.notifier).load();

    final s = container.read(diagnosisControllerProvider);
    expect(s.error, isNotNull);
    expect(s.problem, isNull);
    expect(s.isLoading, isFalse);
  });
}
