// 채팅 화면 위젯 테스트 — 입력·전송 후 코치 버블·소크라테스 배지·로딩/에러 렌더 검증.
//
// coachApiProvider를 fake로 override해 네트워크 없이 화면 동작을 확인한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 미리 짠 응답을 돌려주는 fake(또는 throw) — 위젯 테스트용.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  DioException _fail() => DioException(
        requestOptions: RequestOptions(path: '/v1/coach/sessions'),
        error: '네트워크 실패(테스트)',
      );

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
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
    if (shouldThrow) {
      throw _fail();
    }
    return CoachTurnResult(
      dialogueId: dialogueId,
      response: response!,
      wh1TurnIndex: 2,
    );
  }
}

CoachResponse _response({
  String prompt = '먼저 무엇이 주어졌는지 정리해 볼까요?',
  String socraticCategory = '조건확인',
  SolutionCoaching? coaching,
}) {
  return CoachResponse(
    decision: PedagogyDecision(
      polyaStageToAdvance: 'stay',
      prompt: prompt,
      system: '시스템(테스트)',
      socraticCategory: socraticCategory,
    ),
    solutionCoaching: coaching,
  );
}

Widget _wrap(CoachApi fake) {
  return ProviderScope(
    overrides: [coachApiProvider.overrideWithValue(fake)],
    child: const MaterialApp(home: ChatScreen()),
  );
}

void main() {
  testWidgets('슬로건과 빈 안내가 보인다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    expect(find.text('WhyMath'), findsOneWidget);
    expect(find.text('답이 아닌, 이유를 묻는 수학'), findsOneWidget);
    expect(find.text('어떤 문제를 함께 생각해 볼까요?'), findsOneWidget);
  });

  testWidgets('입력·전송 후 코치 버블과 소크라테스 배지가 렌더된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _FakeCoachApi(
          response: _response(
            prompt: '주어진 조건을 먼저 적어 볼까요?',
            socraticCategory: '조건확인',
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), '판별식이 헷갈려요');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // 학생 입력·코치 발화·배지가 모두 보인다.
    expect(find.text('판별식이 헷갈려요'), findsOneWidget);
    expect(find.text('주어진 조건을 먼저 적어 볼까요?'), findsOneWidget);
    expect(find.text('조건확인'), findsOneWidget);
  });

  testWidgets('코치 응답에 검산 신호가 있으면 채팅에 신호 카드가 노출된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _FakeCoachApi(
          response: _response(
            prompt: '같이 한 번 더 살펴볼까요?',
            socraticCategory: '검증',
            coaching: const SolutionCoaching(
              // trigger.prompt는 비워 추가 코치 버블을 만들지 않는다(카드만 검증).
              trigger: CoachingTrigger(
                focus: 'verify',
                rationale: '근거(테스트)',
                prompt: '',
                socraticCategory: '검증',
              ),
              arithmeticError: true,
              errorKind: 'arithmetic',
            ),
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), '이 계산 맞나요?');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // 코치 버블 아래 신호 카드(검산 cue)가 채팅에 보인다.
    expect(find.textContaining('스스로 검산해볼까?'), findsOneWidget);
    // 답 미루기 — "틀렸다" 단정은 노출하지 않는다.
    expect(find.textContaining('틀렸'), findsNothing);
  });

  testWidgets('풀이 단계 모드로 토글해 멀티라인 전송하면 신호 카드가 노출된다',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        _FakeCoachApi(
          response: _response(
            prompt: '같이 한 번 더 살펴볼까요?',
            socraticCategory: '검증',
            coaching: const SolutionCoaching(
              trigger: CoachingTrigger(
                focus: 'verify',
                rationale: '근거(테스트)',
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
        ),
      ),
    );

    // 풀이 단계 모드로 토글한다(토글 아이콘 → 풀이 단계).
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 멀티라인 풀이를 입력하고 "풀이 확인"으로 전송한다.
    await tester.enterText(find.byType(TextField), 'a\nb\nc');
    await tester.tap(find.text('풀이 확인'));
    await tester.pumpAndSettle();

    // 단계 검증 요약 신호 카드가 노출된다(전이 수 표시).
    expect(find.textContaining('단계 확인'), findsOneWidget);
    expect(find.textContaining('다시 볼 단계가 있어요'), findsOneWidget);
    // 답 미루기 — "틀렸다" 단정은 노출하지 않는다.
    expect(find.textContaining('틀렸'), findsNothing);
  });

  testWidgets('풀이 모드에서만 "수식으로 입력"(MathLive) 진입 버튼이 보인다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    // 대화 모드에선 수식 입력 버튼이 없다.
    expect(find.text('수식으로 입력'), findsNothing);

    // 풀이 단계 모드로 토글하면 MathLive 진입 버튼이 나타난다(탭하면 WebView 화면이라
    // 여기선 존재만 확인한다 — WebView 렌더 통합은 후속).
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();
    expect(find.text('수식으로 입력'), findsOneWidget);
  });

  testWidgets('API 실패 시 SnackBar로 에러를 알린다(앱은 유지)', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(shouldThrow: true)));

    await tester.enterText(find.byType(TextField), '도와주세요');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pump(); // 상태 갱신.
    await tester.pump(); // SnackBar 프레임.

    // 학생 발화는 남고 SnackBar(에러)가 뜬다.
    expect(find.text('도와주세요'), findsOneWidget);
    expect(find.byType(SnackBar), findsOneWidget);
  });

  testWidgets('활성 문제가 있으면 채팅 상단 배너에 발문이 보인다(접기 가능)', (tester) async {
    // 실기기 시연 피드백 회귀 가드: "문제가 한 화면에 같이 안 나옴" — 풀이 중 문제를
    // 다시 보러 화면을 떠나지 않도록 채팅 위에 발문을 상시 노출한다.
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          coachApiProvider.overrideWithValue(_FakeCoachApi(response: _response())),
          activeProblemProvider.overrideWith(
            (ref) => const Problem(
              problemId: 'p-1',
              sourceType: '자체생성',
              subject: '공통',
              questionText: '이차방정식 x^2-5x+6=0의 두 근 중 큰 근을 구하시오.',
            ),
          ),
        ],
        child: const MaterialApp(home: ChatScreen()),
      ),
    );

    // 기본 펼침 — 발문이 보인다.
    expect(
      find.text('이차방정식 x^2-5x+6=0의 두 근 중 큰 근을 구하시오.'),
      findsOneWidget,
    );

    // 배너를 탭하면 접혀 발문이 숨고 요약 행만 남는다.
    await tester.tap(find.textContaining('풀이 중인 문제'));
    await tester.pump();
    expect(
      find.text('이차방정식 x^2-5x+6=0의 두 근 중 큰 근을 구하시오.'),
      findsNothing,
    );
    expect(find.textContaining('풀이 중인 문제'), findsOneWidget);
  });

  testWidgets('활성 문제가 없으면 배너가 그려지지 않는다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));
    expect(find.textContaining('풀이 중인 문제'), findsNothing);
  });
}
