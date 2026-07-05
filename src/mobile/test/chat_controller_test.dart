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
import 'package:korean_math_app/features/ocr/data/ocr_models.dart';

/// 미리 짠 응답을 그대로 돌려주는 fake — 또는 [shouldThrow]면 예외를 던진다.
///
/// 보낸 [CoachRequest]를 [lastRequest]에 캡처해 solution_steps 전송을 검증할 수 있다.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  /// 마지막으로 받은 요청(테스트에서 전송 페이로드를 단언).
  CoachRequest? lastRequest;

  @override
  Future<CoachResponse> coach(CoachRequest request) async {
    lastRequest = request;
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

  group('ChatController.sendSolution', () {
    test('줄 분해해 solution_steps로 전송한다(공백 trim·빈 줄 제외)', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // 가운데 빈 줄·앞뒤 공백이 섞인 풀이 — 순수 줄 분해 결과를 단언한다.
      await notifier.sendSolution('  a  \n\n b \nc\n');

      expect(fake.lastRequest, isNotNull);
      expect(fake.lastRequest!.solutionSteps, <String>['a', 'b', 'c']);
      // 풀이 원문은 studentInput으로도 함께 보낸다(trim된 원문).
      expect(fake.lastRequest!.studentInput, isNotEmpty);
    });

    test('학생 메시지를 isSolution=true로 남긴다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendSolution('x=1\nx=2');

      final state = container.read(chatControllerProvider);
      expect(state.messages.first.role, ChatRole.student);
      expect(state.messages.first.isSolution, isTrue);
    });

    test('solution_verification이 채워지면 신호를 보관한 코치 발화가 잇는다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(
          decision: _decision(prompt: '같이 한 번 더 살펴볼까요?'),
          solutionCoaching: const SolutionCoaching(
            trigger: CoachingTrigger(
              focus: 'verify',
              rationale: '단계 검증 결과',
              prompt: '', // 추가 버블 없이 신호 카드만 검증.
              socraticCategory: '검증',
            ),
            arithmeticError: false,
            solutionVerification: SolutionVerificationResult(
              nCorrect: 1,
              nIncorrect: 1,
              nUnverifiable: 0,
              nTransitions: 2,
              unverifiedRatio: 0,
              firstIncorrectIndex: 1,
              hasIncorrect: true,
            ),
          ),
        ),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendSolution('a\nb\nc');

      final state = container.read(chatControllerProvider);
      // student(풀이) + coach(decision·response 보관) = 2.
      expect(state.messages.length, 2);
      final coach = state.messages[1];
      expect(coach.role, ChatRole.coach);
      expect(coach.response, isNotNull);
      expect(
        coach.response!.solutionCoaching!.solutionVerification!.hasIncorrect,
        isTrue,
      );
    });

    test('유효한 줄이 하나도 없으면(전부 공백) 전송하지 않는다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendSolution('   \n\n  ');

      expect(fake.lastRequest, isNull);
      expect(container.read(chatControllerProvider).messages, isEmpty);
    });

    test('단계가 1개여도(전이 0) 그대로 전송한다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendSolution('x=1');

      expect(fake.lastRequest, isNotNull);
      expect(fake.lastRequest!.solutionSteps, <String>['x=1']);
    });
  });

  group('ChatController.sendOcrSolution', () {
    // 영역이 있는 인식 결과(정상 손글씨 풀이) — 착지점이 모두 채워진다.
    OcrResult filledResult({double overall = 0.6}) => OcrResult(
          regions: [
            OcrRegion(
              bbox: const BBox(x: 0, y: 0, width: 10, height: 10),
              contentType: '수식',
              latex: r'D = b^2 - 4ac',
              confidence: overall,
            ),
          ],
          plainLatex: r'D = b^2 - 4ac',
          solutionSteps: const <String>['x^2-4=0', 'x=2'],
          solutionStepTypes: const <String>['계산'],
          overallConfidence: overall,
          minConfidence: overall,
        );

    test('regions가 있으면 OCR 착지점을 정전 매핑대로 전송한다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendOcrSolution(filledResult(overall: 0.6));

      final req = fake.lastRequest!;
      expect(req.studentSolution, r'D = b^2 - 4ac');
      // regions가 있으므로 overall_confidence를 그대로 넘긴다(게이트 정상 판정).
      expect(req.ocrConfidence, 0.6);
      expect(req.solutionSteps, <String>['x^2-4=0', 'x=2']);
      expect(req.solutionStepTypes, <String>['계산']);

      // 학생 버블은 인식 풀이를 풀이 입력(isSolution)으로 남긴다.
      final state = container.read(chatControllerProvider);
      expect(state.messages.first.role, ChatRole.student);
      expect(state.messages.first.isSolution, isTrue);
      expect(state.messages.first.text, r'D = b^2 - 4ac');
    });

    test('regions가 비면 ocr_confidence를 null로 낮춘다(게이트 거짓 발동 방지)', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // 빈 인식 — 모든 착지점이 dormant(null)여야 한다(overall 0.0을 넘기지 않는다).
      await notifier.sendOcrSolution(const OcrResult());

      final req = fake.lastRequest!;
      expect(req.studentSolution, isNull);
      expect(req.ocrConfidence, isNull);
      expect(req.solutionSteps, isNull);
      expect(req.solutionStepTypes, isNull);
    });

    test('studentInput(대화 발화)은 그대로 전달한다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendOcrSolution(
        filledResult(),
        studentInput: '이 풀이가 맞나요?',
      );

      expect(fake.lastRequest!.studentInput, '이 풀이가 맞나요?');
    });
  });
}
