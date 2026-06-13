// 채팅 컨트롤러 테스트 — send 흐름·Polya 전이·검산 코칭 추가 발화·에러 graceful 검증.
//
// 네트워크를 타지 않는다 — coachApiProvider를 미리 짠 CoachResponse를 반환(또는 throw)하는
// fake CoachApi로 override한다. 컨트롤러는 순수 상태 전이라 동기적으로 결과를 검증할 수 있다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/domain/chat_message.dart';

/// 미리 짠 응답을 그대로 돌려주는 fake — 또는 [shouldThrow]면 예외를 던진다.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  @override
  Future<CoachResponse> coach(CoachRequest request) async {
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/coach'),
        error: '네트워크 실패(테스트)',
      );
    }
    return response!;
  }
}

/// 최소 PedagogyDecision 빌더 — 테스트 가독성용.
PedagogyDecision _decision({
  String stage = 'stay',
  String prompt = '이 문제에서 무엇을 구해야 할까요?',
  String socraticCategory = '',
}) {
  return PedagogyDecision(
    polyaStageToAdvance: stage,
    prompt: prompt,
    system: '시스템 지시(테스트)',
    socraticCategory: socraticCategory,
  );
}

ProviderContainer _containerWith(CoachApi fake) {
  final container = ProviderContainer(
    overrides: [coachApiProvider.overrideWithValue(fake)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('ChatController.send', () {
    test('학생 발화와 코치 발화를 차례로 누적한다', () async {
      final container = _containerWith(
        _FakeCoachApi(
          response: CoachResponse(
            decision: _decision(
              prompt: '주어진 조건을 먼저 정리해 볼까요?',
              socraticCategory: '조건확인',
            ),
          ),
        ),
      );
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('판별식이 뭔지 모르겠어요');

      final state = container.read(chatControllerProvider);
      expect(state.messages.length, 2);
      expect(state.messages[0].role, ChatRole.student);
      expect(state.messages[0].text, '판별식이 뭔지 모르겠어요');
      expect(state.messages[1].role, ChatRole.coach);
      expect(state.messages[1].text, '주어진 조건을 먼저 정리해 볼까요?');
      expect(state.messages[1].socraticCategory, '조건확인');
      expect(state.isSending, isFalse);
      expect(state.error, isNull);
    });

    test('decision.polyaStageToAdvance가 next면 다음 단계로 전이한다', () async {
      final container = _containerWith(
        _FakeCoachApi(
          response: CoachResponse(decision: _decision(stage: 'next')),
        ),
      );
      final notifier = container.read(chatControllerProvider.notifier);

      // 초기 단계는 understand → next 적용 시 plan.
      expect(container.read(chatControllerProvider).polyaState, 'understand');
      await notifier.send('이해했어요');
      expect(container.read(chatControllerProvider).polyaState, 'plan');
    });

    test('understand에서 previous 전이는 단계를 유지한다(경계 보수)', () async {
      final container = _containerWith(
        _FakeCoachApi(
          response: CoachResponse(decision: _decision(stage: 'previous')),
        ),
      );
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('잘 모르겠어요');
      expect(container.read(chatControllerProvider).polyaState, 'understand');
    });

    test('solution_coaching.trigger.prompt가 있으면 추가 코치 발화로 잇는다', () async {
      final container = _containerWith(
        _FakeCoachApi(
          response: CoachResponse(
            decision: _decision(prompt: '풀이를 다시 한번 살펴볼까요?'),
            solutionCoaching: const SolutionCoaching(
              trigger: CoachingTrigger(
                focus: 'verify',
                rationale: '계산 슬립이 보임',
                prompt: '세 번째 줄의 계산을 검산해 볼까요?',
                socraticCategory: '단계분해',
              ),
              arithmeticError: true,
            ),
          ),
        ),
      );
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('답은 x=3 이에요');

      final state = container.read(chatControllerProvider);
      // student + coach(decision) + coach(검산 코칭) = 3.
      expect(state.messages.length, 3);
      expect(state.messages[2].role, ChatRole.coach);
      expect(state.messages[2].text, '세 번째 줄의 계산을 검산해 볼까요?');
      expect(state.messages[2].socraticCategory, '단계분해');
    });

    test('API 실패 시 error만 기록하고 앱은 죽지 않는다', () async {
      final container = _containerWith(_FakeCoachApi(shouldThrow: true));
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('도와주세요');

      final state = container.read(chatControllerProvider);
      // 학생 발화는 남고 코치 발화는 없으며 에러가 설정된다.
      expect(state.messages.length, 1);
      expect(state.messages[0].role, ChatRole.student);
      expect(state.isSending, isFalse);
      expect(state.error, isNotNull);
    });

    test('빈 입력은 무시한다(상태 불변)', () async {
      final container = _containerWith(
        _FakeCoachApi(response: CoachResponse(decision: _decision())),
      );
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('   ');
      expect(container.read(chatControllerProvider).messages, isEmpty);
    });

    test('clearError는 에러를 지운다', () async {
      final container = _containerWith(_FakeCoachApi(shouldThrow: true));
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('도와주세요');
      expect(container.read(chatControllerProvider).error, isNotNull);

      notifier.clearError();
      expect(container.read(chatControllerProvider).error, isNull);
    });
  });
}
