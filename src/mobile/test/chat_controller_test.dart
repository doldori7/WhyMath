// 채팅 컨트롤러 테스트 — send 흐름·Polya 전이·검산 코칭 추가 발화·세션 영속·에러 graceful 검증.
//
// 네트워크를 타지 않는다 — coachApiProvider를 미리 짠 CoachResponse를 반환(또는 throw)하는
// fake CoachApi로 override한다. 컨트롤러는 영속 세션 경로(createSession→addTurn)를 쓰므로 fake는
// 그 두 메서드를 구현한다. 컨트롤러는 순수 상태 전이라 동기적으로 결과를 검증할 수 있다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/domain/chat_message.dart';
import 'package:korean_math_app/features/ocr/data/ocr_models.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 미리 짠 응답을 그대로 돌려주는 fake — 또는 [shouldThrow]면 예외를 던진다.
///
/// 보낸 [CoachRequest]를 [lastRequest]에 캡처해 solution_steps 전송을 검증할 수 있다. 첫 발화는
/// [createSession]으로, 이후 발화는 [addTurn]으로 온다(호출 횟수·problem_id를 캡처).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  /// 마지막으로 받은 요청(테스트에서 전송 페이로드를 단언).
  CoachRequest? lastRequest;

  /// createSession에 전달된 problem_id(세션이 문제에 묶였는지 단언).
  String? lastProblemId;

  /// 세션 생성·턴 추가 호출 횟수(첫 발화=create·이후=turn 검증).
  int createCalls = 0;
  int turnCalls = 0;

  DioException _fail() => DioException(
        requestOptions: RequestOptions(path: '/v1/coach/sessions'),
        error: '네트워크 실패(테스트)',
      );

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    lastRequest = request;
    lastProblemId = problemId;
    createCalls++;
    if (shouldThrow) {
      throw _fail();
    }
    return CoachTurnResult(
      dialogueId: 'test-dialogue',
      response: response!,
      wh1TurnIndex: 1,
    );
  }

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    lastRequest = request;
    turnCalls++;
    if (shouldThrow) {
      throw _fail();
    }
    return CoachTurnResult(
      dialogueId: dialogueId,
      response: response!,
      wh1TurnIndex: turnCalls + 1,
    );
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

  group('ChatController.sendMathLiveSolution', () {
    test('MathLive \\displaylines LaTeX를 평문 스텝으로 변환해 전송한다(MOB-06)', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // MathLive 여러 줄 직렬화 원문(2026-07-20 실기기 실측 형태).
      await notifier.sendMathLiveSolution(r'\displaylines{2x+3=7 \\ x=2}');

      // acceptance ⓑ: 여러 스텝으로 분해돼 인접 전이가 생긴다(단일 0-전이 blob 아님 → verify 결정 도달).
      expect(fake.lastRequest, isNotNull);
      expect(fake.lastRequest!.solutionSteps, <String>['2x+3=7', 'x=2']);

      // acceptance ⓐ: 학생 버블에 LaTeX 원문 미노출(평문 수식) — \displaylines·백슬래시 없음.
      final state = container.read(chatControllerProvider);
      expect(state.messages.first.role, ChatRole.student);
      expect(state.messages.first.text, '2x+3=7\nx=2');
      expect(state.messages.first.text.contains(r'\displaylines'), isFalse);
      expect(state.messages.first.isSolution, isTrue);
    });

    test('변환 결과가 비면(유효 스텝 0) 전송하지 않는다', () async {
      final fake = _FakeCoachApi(
        response: CoachResponse(decision: _decision()),
      );
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.sendMathLiveSolution(r'\displaylines{  \\  }');

      expect(fake.lastRequest, isNull);
      expect(container.read(chatControllerProvider).messages, isEmpty);
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

  group('ChatController 영속 세션', () {
    test('첫 발화는 세션을 생성하고 dialogue_id를 보관한다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // 진입 시점엔 세션이 없다.
      expect(container.read(chatControllerProvider).dialogueId, isNull);

      await notifier.send('첫 질문이에요');

      expect(fake.createCalls, 1);
      expect(fake.turnCalls, 0);
      expect(container.read(chatControllerProvider).dialogueId, 'test-dialogue');
    });

    test('두 번째 발화부터는 같은 세션에 턴으로 잇는다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('첫 질문');
      await notifier.send('두 번째 질문');

      // 세션은 한 번만 생성되고, 이후는 턴 추가로 간다.
      expect(fake.createCalls, 1);
      expect(fake.turnCalls, 1);
      expect(container.read(chatControllerProvider).dialogueId, 'test-dialogue');
    });

    test('활성 문제가 있으면 그 problem_id로 세션을 묶는다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = ProviderContainer(
        overrides: [
          coachApiProvider.overrideWithValue(fake),
          activeProblemProvider.overrideWith(
            (ref) => const Problem(
              problemId: 'prob-99',
              sourceType: '자체생성',
              subject: '미적분',
              unitCodes: <String>['CAL'],
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      final notifier = container.read(chatControllerProvider.notifier);

      await notifier.send('이 문제 도와주세요');

      expect(fake.lastProblemId, 'prob-99');
    });
  });

  // S3-30(원 S3-14) — 코치 dialogue가 문제 간에 리셋되지 않던 버그의 회귀 방어.
  //
  // 실기기 내비게이션(코치→"다음 문제로"→풀이 시작→코치)에서 컨트롤러 autoDispose 리셋이
  // 신뢰성 있게 일어나지 않아, 새 문제 B의 발화가 이전 문제 A의 dialogue에 append되던 버그를
  // 명시적 문제별 리셋으로 바로잡는다. 활성 문제(activeProblemProvider)를 바꿔 가며 create/turn
  // 분기와 대화 비움·problemId 저장을 관측한다. activeProblem은 legacy StateProvider라 `.notifier`
  // 로 값을 직접 바꾼다(진단→문제제시가 세팅하는 흐름을 테스트에서 재현).
  group('ChatController 문제 전환 시 세션 리셋 (S3-30, 원 S3-14)', () {
    Problem prob(String id) => Problem(
          problemId: id,
          sourceType: '자체생성',
          subject: '미적분',
          unitCodes: const <String>['CAL'],
        );

    test('문제가 바뀌면 새 세션(createSession)으로 강제하고 이전 대화를 비운다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // ① 문제 A 활성 → 첫 발화 = createSession(problemId=A)·problemId·dialogueId 확보.
      container.read(activeProblemProvider.notifier).state = prob('prob-A');
      await notifier.send('A 첫 발화');
      expect(fake.createCalls, 1);
      expect(fake.turnCalls, 0);
      expect(fake.lastProblemId, 'prob-A');
      expect(container.read(chatControllerProvider).problemId, 'prob-A');
      expect(
        container.read(chatControllerProvider).dialogueId,
        'test-dialogue',
      );

      // ② 같은 A로 다시 발화 = addTurn(새 세션 아님·회귀 0).
      await notifier.send('A 두 번째 발화');
      expect(fake.createCalls, 1);
      expect(fake.turnCalls, 1);
      // A 대화 누적: student·coach·student·coach = 4.
      expect(container.read(chatControllerProvider).messages.length, 4);
      expect(container.read(chatControllerProvider).problemId, 'prob-A');

      // ③ 문제 B로 전환 후 발화 = createSession(problemId=B)·addTurn 아님·이전 대화 비움.
      container.read(activeProblemProvider.notifier).state = prob('prob-B');
      await notifier.send('B 첫 발화');
      expect(fake.createCalls, 2); // 새 세션 생성됨.
      expect(fake.turnCalls, 1); // addTurn은 증가하지 않는다.
      expect(fake.lastProblemId, 'prob-B');

      final state = container.read(chatControllerProvider);
      expect(state.problemId, 'prob-B');
      // 이전 A 대화는 사라지고 B의 새 대화만 남는다: student(B)·coach(B) = 2.
      expect(state.messages.length, 2);
      expect(state.messages[0].role, ChatRole.student);
      expect(state.messages[0].text, 'B 첫 발화');
      expect(state.messages[1].role, ChatRole.coach);
    });

    test('풀이 제출(sendSolution)도 같은 문제 전환 리셋을 탄다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      container.read(activeProblemProvider.notifier).state = prob('prob-A');
      await notifier.sendSolution('x=1\nx=2');
      expect(fake.lastProblemId, 'prob-A');

      // 문제 B로 전환 후 풀이 제출도 새 세션으로 나가야 한다(공통 경로 리셋).
      container.read(activeProblemProvider.notifier).state = prob('prob-B');
      await notifier.sendSolution('y=3\ny=4');
      expect(fake.createCalls, 2);
      expect(fake.lastProblemId, 'prob-B');
      expect(container.read(chatControllerProvider).problemId, 'prob-B');
    });

    test('자유 대화(활성 문제 없음)는 problemId null·append 유지(회귀 0)', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // 활성 문제가 없으면 problemId는 계속 null이라 전환으로 보지 않는다.
      await notifier.send('자유 질문 1');
      await notifier.send('자유 질문 2');

      expect(fake.createCalls, 1);
      expect(fake.turnCalls, 1);
      expect(container.read(chatControllerProvider).problemId, isNull);
    });

    test('자유 대화 중 문제가 활성화되면 그 첫 발화는 새 세션으로 묶인다', () async {
      final fake = _FakeCoachApi(response: CoachResponse(decision: _decision()));
      final container = _containerWith(fake);
      final notifier = container.read(chatControllerProvider.notifier);

      // 자유 대화로 세션이 먼저 생긴 뒤(problemId null),
      await notifier.send('그냥 궁금해서요');
      expect(container.read(chatControllerProvider).problemId, isNull);

      // 문제가 활성화되면(null→A) 전환으로 판정해 새 세션을 만든다.
      container.read(activeProblemProvider.notifier).state = prob('prob-A');
      await notifier.send('이 문제 풀래요');

      expect(fake.createCalls, 2);
      expect(fake.turnCalls, 0);
      expect(fake.lastProblemId, 'prob-A');
      expect(container.read(chatControllerProvider).problemId, 'prob-A');
    });
  });
}
