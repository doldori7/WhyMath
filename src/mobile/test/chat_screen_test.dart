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
import 'package:korean_math_app/features/reports/data/defect_report_api.dart';

/// 미리 짠 응답을 돌려주는 fake(또는 throw) — 위젯 테스트용.
///
/// [lastRequest]에 마지막 요청을 기록한다 — 단계 리스트 편집기의 조인 결과가
/// 컨트롤러 계약(`student_input`·`solution_steps`) 그대로 전달되는지 검증용.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({this.response, this.shouldThrow = false}) : super(Dio());

  final CoachResponse? response;
  final bool shouldThrow;

  /// 마지막으로 받은 요청(조인·줄 분해 왕복 검증용).
  CoachRequest? lastRequest;

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

/// 호출을 기록만 하는 fake — 실제 네트워크 없이 신고 시점의 problemId를 검증한다.
class _FakeDefectReportApi extends DefectReportApi {
  _FakeDefectReportApi() : super(Dio());

  int callCount = 0;
  String? lastProblemId;

  @override
  Future<void> reportDefect({
    required DefectReportCategory category,
    String? problemId,
  }) async {
    callCount++;
    lastProblemId = problemId;
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

  testWidgets('풀이 단계 모드에서 단계들을 묶어 제출하면 신호 카드가 노출된다',
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

    // 풀이 단계 모드로 토글한다(토글 아이콘 → 단계 리스트 편집기).
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 초기 2개 필드에 "단계 추가"로 하나 더한 3개 단계를 입력하고 "3단계 제출"로 묶어
    // 전송한다(실기기 실측: 묶음 제출이어야 verify 전이가 생겨 correct/incorrect가
    // 결정된다 — 3단계=전이 2개가 위 가짜 응답 nTransitions: 2와 정합).
    await tester.tap(find.text('단계 추가'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'a');
    await tester.enterText(find.byType(TextField).at(1), 'b');
    await tester.enterText(find.byType(TextField).at(2), 'c');
    await tester.pump();
    await tester.tap(find.text('3단계 제출'));
    await tester.pumpAndSettle();

    // 단계 검증 요약 신호 카드가 노출된다(전이 수 표시).
    expect(find.textContaining('단계 확인'), findsOneWidget);
    expect(find.textContaining('다시 볼 단계가 있어요'), findsOneWidget);
    // 답 미루기 — "틀렸다" 단정은 노출하지 않는다.
    expect(find.textContaining('틀렸'), findsNothing);
  });

  testWidgets('단계 리스트 편집기 — 단계 추가/삭제가 동작하고 마지막 1개는 지울 수 없다',
      (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 초기 2개 단계 필드 — 묶음 제출(최소 전이 1개)이 기본 모양임을 시각적으로 유도한다.
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('예: 2x+3=7'), findsOneWidget); // 입력 형태 예시 힌트(MOB-05).

    // "단계 추가" → 3개.
    await tester.tap(find.text('단계 추가'));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsNWidgets(3));

    // 단계 삭제 → 다시 2개. (추가 직후 단계 영역이 아래로 스크롤되므로
    // 항상 화면에 보이는 *마지막* 행의 삭제 버튼을 탭한다.)
    await tester.tap(find.byIcon(Icons.remove_circle_outline).last);
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsNWidgets(2));

    // 1개까지 줄이면 — 마지막 단계의 삭제 버튼은 비활성(빈 편집기 방지).
    await tester.tap(find.byIcon(Icons.remove_circle_outline).last);
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsNWidgets(1));
    final deleteButton = tester.widget<IconButton>(
      find.widgetWithIcon(IconButton, Icons.remove_circle_outline),
    );
    expect(deleteButton.onPressed, isNull);

    // 대화로 나갔다 돌아오면 편집기가 초기 상태(2개 필드)로 리셋된다(토글=입력 비움과 동형).
    await tester.tap(find.byIcon(Icons.chat_bubble_outline));
    await tester.pump();
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();
    expect(find.byType(TextField), findsNWidgets(2));
  });

  testWidgets('단계 필드 Enter(다음) — 마지막 필드에서 누르면 새 단계가 추가된다',
      (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 마지막(2번째) 필드에 입력 후 Enter(next) → 3번째 필드가 자연스럽게 추가된다.
    await tester.enterText(find.byType(TextField).at(1), '마지막 단계');
    await tester.testTextInput.receiveAction(TextInputAction.next);
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsNWidgets(3));
  });

  testWidgets('"N단계 제출" 라벨이 실시간 반영되고, 1단계뿐이면 묶음 안내가 보인다',
      (tester) async {
    const helper = '단계를 나눠 적으면 풀이를 확인해 드릴 수 있어요';
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 전부 비어 있으면 "풀이 제출"(비활성) — 보낼 단계가 없다.
    expect(find.text('풀이 제출'), findsOneWidget);
    expect(find.text(helper), findsNothing);
    final emptySubmit = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '풀이 제출'),
    );
    expect(emptySubmit.onPressed, isNull);

    // 1단계 입력 → "1단계 제출" + 부드러운 묶음 안내(질책 표현 없음·제출은 허용).
    await tester.enterText(find.byType(TextField).at(0), '판별식을 계산한다');
    await tester.pump();
    expect(find.text('1단계 제출'), findsOneWidget);
    expect(find.text(helper), findsOneWidget);
    final oneStepSubmit = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '1단계 제출'),
    );
    expect(oneStepSubmit.onPressed, isNotNull); // 1단계 제출도 막지 않는다.

    // 2단계 입력 → "2단계 제출", 안내는 사라진다.
    await tester.enterText(find.byType(TextField).at(1), 'D>0이므로 근이 두 개');
    await tester.pump();
    expect(find.text('2단계 제출'), findsOneWidget);
    expect(find.text(helper), findsNothing);

    // 지우면 → 다시 "1단계 제출"(실시간 반영).
    await tester.enterText(find.byType(TextField).at(1), '');
    await tester.pump();
    expect(find.text('1단계 제출'), findsOneWidget);
  });

  testWidgets('제출은 비어있지 않은 단계들만 줄바꿈으로 합쳐 sendSolution 경로로 보낸다',
      (tester) async {
    final fake = _FakeCoachApi(response: _response());
    await tester.pumpWidget(_wrap(fake));

    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // "단계 추가"로 3개 필드를 만든 뒤 단계 1·3만 채우고 2는 비워 둔다
    // (초기 필드는 2개) — 빈 단계는 제출에서 제외된다.
    await tester.tap(find.text('단계 추가'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), '식을 정리한다');
    await tester.enterText(find.byType(TextField).at(2), '근을 구한다');
    await tester.pump();
    expect(find.text('2단계 제출'), findsOneWidget);

    await tester.tap(find.text('2단계 제출'));
    await tester.pumpAndSettle();

    // 컨트롤러 계약(무변경) 검증: 편집기 조인(`'\n'`) → sendSolution 줄 분해 왕복.
    expect(fake.lastRequest?.studentInput, '식을 정리한다\n근을 구한다');
    expect(fake.lastRequest?.solutionSteps, <String>['식을 정리한다', '근을 구한다']);

    // 제출 후 편집기는 초기 상태(빈 2필드·"풀이 제출")로 돌아온다(추가한 3번째도 사라짐).
    expect(find.text('풀이 제출'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
  });

  testWidgets('대화 모드 회귀 — 단계 편집기 UI 없이 Enter(전송)로 보낸다', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    // 대화 모드엔 단일 입력 필드 하나뿐, 단계 편집기 UI는 없다.
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('단계 추가'), findsNothing);
    expect(find.text('풀이 제출'), findsNothing);
    expect(find.byIcon(Icons.send), findsOneWidget);

    // Enter(전송 액션)로 보내는 기존 동작이 유지된다.
    await tester.enterText(find.byType(TextField), '이 문제 어렵네요');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();
    expect(find.text('이 문제 어렵네요'), findsOneWidget); // 학생 버블.
    expect(find.text('먼저 무엇이 주어졌는지 정리해 볼까요?'), findsOneWidget); // 코치 응답.
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

  testWidgets('풀이 단계 빈 필드에 입력 형태 예시 힌트가 보인다(MOB-05)', (tester) async {
    await tester.pumpWidget(_wrap(_FakeCoachApi(response: _response())));

    // 풀이 단계 모드로 토글하면 단계 편집기(초기 2필드)가 나타난다.
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();

    // 빈 필드 힌트가 "단계 N"이 아니라 입력 형태 예시로 안내된다(왼쪽 번호 라벨과 중복 제거).
    // 힌트는 빈 필드에 Text로 렌더되므로 find.text로 잡힌다(필드별 예시가 달라 각 1개).
    expect(find.text('예: 2x+3=7'), findsOneWidget);
    expect(find.text('예: x=2'), findsOneWidget);
    expect(find.textContaining('단계 1'), findsNothing);

    // 정서 안전(절대 금기): "틀렸다"류 부정 표현이 없다.
    expect(find.textContaining('틀'), findsNothing);
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

  testWidgets(
      '문제 전환 후 결함 신고는 새 문제로 접수된다(stale 이전 문제 problem_id 없음·MOB-12)',
      (tester) async {
    // 레드(수정 전) 재현 시나리오: 문제 A로 풀이하다 문제 B로 전환한 뒤 신고하면, 화면이
    // activeProblemProvider를 watch해 재렌더되므로 신고 시점의 최신 값(B)이 실려야 한다 —
    // problem_screen.onStart의 리셋 후 재세팅(MOB-12)이 이 전환을 만든다.
    final reportApi = _FakeDefectReportApi();
    final container = ProviderContainer(
      overrides: [
        coachApiProvider.overrideWithValue(_FakeCoachApi(response: _response())),
        defectReportApiProvider.overrideWithValue(reportApi),
        activeProblemProvider.overrideWith(
          (ref) => const Problem(
            problemId: 'p-old',
            sourceType: '자체생성',
            subject: '공통',
            questionText: '이전 문제',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: ChatScreen()),
      ),
    );
    await tester.pumpAndSettle();

    // 문제 전환(problem_screen.onStart와 동형 — null을 거쳐 새 문제로 재세팅)을 재현한다.
    container.read(activeProblemProvider.notifier).state = null;
    container.read(activeProblemProvider.notifier).state = const Problem(
      problemId: 'p-new',
      sourceType: '자체생성',
      subject: '공통',
      questionText: '새 문제',
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.flag_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '신고하기'));
    await tester.pumpAndSettle();

    expect(reportApi.callCount, 1);
    expect(reportApi.lastProblemId, 'p-new');
    expect(reportApi.lastProblemId, isNot('p-old'));
  });
}
