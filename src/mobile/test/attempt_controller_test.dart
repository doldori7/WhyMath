// AttemptController 테스트 — 정답 제출→서버 verification_state 소비·진행 판단·graceful 검증(G1·S3-09).
//
// 네트워크를 타지 않는다 — attemptsApiProvider를 미리 짠 결과(또는 throw)를 돌려주는 fake로 override하고
// (diagnosis_controller_test 답습), activeProblemProvider도 override해 problem_id를 주입한다. 컨트롤러는
// 정답을 판정하지 않는다 — 서버가 돌려준 verification_state를 상태로 노출할 뿐임을 못박는다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/attempt_controller.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/attempts_api.dart';
import 'package:korean_math_app/features/problems/data/attempts_models.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 미리 짠 채점 결과(또는 throw)를 돌려주는 fake — 마지막 인자도 캡처한다.
class _FakeAttemptsApi extends AttemptsApi {
  _FakeAttemptsApi({this.verificationState = 'correct', this.shouldThrow = false})
      : super(Dio());

  final String verificationState;
  final bool shouldThrow;

  /// 마지막 제출 인자(problem_id·student_answer) — 방어 로직(호출 자체 억제) 검증용.
  String? lastProblemId;
  String? lastStudentAnswer;
  int calls = 0;

  @override
  Future<AttemptSubmitResponse> submitAttempt({
    required String problemId,
    required String studentAnswer,
    int? durationSeconds,
    String? sessionId,
    double? confidenceSelfReported,
  }) async {
    calls++;
    lastProblemId = problemId;
    lastStudentAnswer = studentAnswer;
    if (shouldThrow) {
      throw DioException(requestOptions: RequestOptions(path: '/v1/me/attempts'));
    }
    return AttemptSubmitResponse(
      attemptId: 'att-x',
      isCorrect: verificationState == 'correct',
      verificationState: verificationState,
    );
  }
}

const _problem = Problem(
  problemId: 'p-1',
  sourceType: '자체생성',
  subject: '공통',
);

ProviderContainer _container(AttemptsApi api, {Problem? problem = _problem}) {
  final container = ProviderContainer(
    overrides: [
      attemptsApiProvider.overrideWithValue(api),
      activeProblemProvider.overrideWith((ref) => problem),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('correct: 결과에 correct를 노출하고 problem_id·최종답을 서버로 보낸다', () async {
    final api = _FakeAttemptsApi(verificationState: 'correct');
    final container = _container(api);

    await container.read(attemptControllerProvider.notifier).submit('x=3');

    final s = container.read(attemptControllerProvider);
    expect(s.isSubmitting, isFalse);
    expect(s.result, isNotNull);
    expect(s.result!.isVerifiedCorrect, isTrue); // 진행 허용 상태.
    expect(s.error, isNull);
    // 활성 문제 id·학생 최종답이 그대로 전달된다.
    expect(api.lastProblemId, 'p-1');
    expect(api.lastStudentAnswer, 'x=3');
  });

  test('incorrect: 진행 안 함(isVerifiedCorrect=false)·오답 상태 노출', () async {
    final container = _container(_FakeAttemptsApi(verificationState: 'incorrect'));

    await container.read(attemptControllerProvider.notifier).submit('x=1');

    final s = container.read(attemptControllerProvider);
    expect(s.result!.isVerifiedIncorrect, isTrue);
    expect(s.result!.isVerifiedCorrect, isFalse);
  });

  test('unverifiable: 미검증 상태 노출(진행 안 함)', () async {
    final container =
        _container(_FakeAttemptsApi(verificationState: 'unverifiable'));

    await container.read(attemptControllerProvider.notifier).submit('서술형');

    final s = container.read(attemptControllerProvider);
    expect(s.result!.isUnverifiable, isTrue);
    expect(s.result!.isVerifiedCorrect, isFalse);
  });

  test('활성 문제가 없으면 제출을 무시한다(API 호출조차 안 함)', () async {
    final api = _FakeAttemptsApi();
    final container = _container(api, problem: null);

    await container.read(attemptControllerProvider.notifier).submit('x=3');

    final s = container.read(attemptControllerProvider);
    expect(s.result, isNull);
    expect(api.calls, 0); // 채점 대상(problem_id) 없이 서버를 부르지 않는다.
  });

  test('빈 답이면 제출을 무시한다', () async {
    final api = _FakeAttemptsApi();
    final container = _container(api);

    await container.read(attemptControllerProvider.notifier).submit('   ');

    expect(container.read(attemptControllerProvider).result, isNull);
    expect(api.calls, 0);
  });

  test('예외: graceful 에러만 남기고 result는 없다(앱 안 죽음)', () async {
    final container = _container(_FakeAttemptsApi(shouldThrow: true));

    await container.read(attemptControllerProvider.notifier).submit('x=3');

    final s = container.read(attemptControllerProvider);
    expect(s.error, isNotNull);
    expect(s.result, isNull);
    expect(s.isSubmitting, isFalse);
  });

  test('clearResult: 결과 카드를 닫는다(오답·미검증에서 코치와 계속)', () async {
    final container = _container(_FakeAttemptsApi(verificationState: 'incorrect'));
    final notifier = container.read(attemptControllerProvider.notifier);

    await notifier.submit('x=1');
    expect(container.read(attemptControllerProvider).result, isNotNull);

    notifier.clearResult();
    expect(container.read(attemptControllerProvider).result, isNull);
  });
}
