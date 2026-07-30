// 완료 통합 위젯 테스트 — S3-27(원 S3-10) 클라 축(완료를 오직 *풀이 제출*을 통해서만·별도 정답
// 제출 버튼 제거).
//
// Kiki 교수학 지적: 별도 "정답 제출" 버튼은 학생이 Polya 돌아보기(사고 추적)를 우회하게 한다. 그래서
// 완료는 서버가 풀이 제출→정답 도달→돌아보기 1턴을 거쳐 내려주는 신호로만 일어나고, 클라는 그 신호를
// 소비해 "다음 문제로" 진행만 얹는다(정답 판정·완료는 전부 서버 권위·수학 로직 클라 금지).
//
// 검증 축: ① problem_complete=true → "다음 문제로" 노출·탭 시 problemPath 이동(루프 닫힘)
//   ② awaiting_reflection=true → 완료 어포던스 미노출·대화 지속(코치 발화가 이미 메타인지 프롬프트)
//   ③ 별도 '정답 제출' 버튼(task_alt)이 더 이상 없다.
//
// 네비게이션(problemPath 진입)을 실제로 확인하려고 MaterialApp.router + 최소 GoRouter를 쓴다.
// coachApi는 fake로 주입한다(네트워크 없음).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 미리 짠 완료 신호를 실은 [CoachTurnResult]를 돌려주는 fake(네트워크 없이).
///
/// 완료 신호(problem_complete·awaiting_reflection)는 *서버가* 내려주는 것이라, 클라 렌더 검증에서는
/// 어떤 발화로 유발됐는지와 무관하게 신호만 실어 보낸다(클라는 신호를 소비만 함·서버 권위).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({
    required this.prompt,
    this.problemComplete = false,
    this.awaitingReflection = false,
    this.completedAttemptId,
  }) : super(Dio());

  final String prompt;
  final bool problemComplete;
  final bool awaitingReflection;
  final String? completedAttemptId;

  CoachTurnResult _result(String dialogueId, int idx) => CoachTurnResult(
        dialogueId: dialogueId,
        response: CoachResponse(
          decision: PedagogyDecision(
            polyaStageToAdvance: 'stay',
            prompt: prompt,
            system: '시스템(테스트)',
          ),
        ),
        wh1TurnIndex: idx,
        problemComplete: problemComplete,
        awaitingReflection: awaitingReflection,
        completedAttemptId: completedAttemptId,
      );

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async =>
      _result('d-1', 1);

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async =>
      _result(dialogueId, 2);
}

const _problem = Problem(
  problemId: 'p-1',
  sourceType: '자체생성',
  subject: '공통',
  questionText: '이차방정식 x^2-5x+6=0의 두 근 중 큰 근을 구하시오.',
);

/// problemPath 진입을 확인하기 위한 프로브 화면(진짜 ProblemScreen 대신 관측 지점).
class _ProblemProbe extends StatelessWidget {
  const _ProblemProbe();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('NEXT-PROBLEM-PROBE')));
  }
}

GoRouter _router() {
  return GoRouter(
    initialLocation: AppRoutes.chatPath,
    routes: [
      GoRoute(path: AppRoutes.chatPath, builder: (_, __) => const ChatScreen()),
      GoRoute(
        path: AppRoutes.problemPath,
        builder: (_, __) => const _ProblemProbe(),
      ),
    ],
  );
}

Widget _app(CoachApi api) {
  return ProviderScope(
    overrides: [
      coachApiProvider.overrideWithValue(api),
      activeProblemProvider.overrideWith((ref) => _problem),
    ],
    child: MaterialApp.router(routerConfig: _router()),
  );
}

/// 대화 발화 하나를 보내 코치 응답(완료 신호 포함)을 유발한다.
Future<void> _sendMessage(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.testTextInput.receiveAction(TextInputAction.send);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('problem_complete=true → "다음 문제로" 노출·탭 시 problemPath로 이동한다',
      (tester) async {
    await tester.pumpWidget(
      _app(
        _FakeCoachApi(
          prompt: '좋아, 근거가 분명하네 — 다음 문제로 가보자!',
          problemComplete: true,
          completedAttemptId: 'att-1',
        ),
      ),
    );
    await tester.pumpAndSettle();

    // 별도 '정답 제출' 버튼은 더 이상 없다(완료는 풀이 제출을 통해서만·사고 추적 우회 방지).
    expect(find.byIcon(Icons.task_alt), findsNothing);

    await _sendMessage(tester, '판별식이 양수라 근이 두 개예요');

    // 완료 발화(코치 버블)는 서버가 decision.prompt로 내려 이미 렌더돼 있고, 화면은 "다음 문제로"만 얹는다.
    expect(find.text('좋아, 근거가 분명하네 — 다음 문제로 가보자!'), findsOneWidget);
    expect(find.text('다음 문제로'), findsOneWidget);

    // 탭하면 문제 화면으로 이동한다(루프 닫힘: ProblemScreen이 next-problem 재-fetch).
    await tester.tap(find.text('다음 문제로'));
    await tester.pumpAndSettle();
    expect(find.text('NEXT-PROBLEM-PROBE'), findsOneWidget);
  });

  testWidgets('awaiting_reflection=true → 완료 어포던스 미노출·대화 지속',
      (tester) async {
    await tester.pumpWidget(
      _app(
        _FakeCoachApi(
          prompt: '답에 도착했네! 이 답이 어떻게·왜 나왔는지 설명해줄래?',
          awaitingReflection: true,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await _sendMessage(tester, 'x=3이에요');

    // 메타인지 프롬프트(코치 발화)는 보이지만 "다음 문제로"(완료 어포던스)는 없다(완료 아님).
    expect(find.textContaining('설명해줄래?'), findsOneWidget);
    expect(find.text('다음 문제로'), findsNothing);

    // 대화는 지속된다 — 입력 필드가 그대로 있어 학생이 근거를 계속 답할 수 있다.
    expect(find.byType(TextField), findsOneWidget);
    // problemPath로 넘어가지 않았다(진행 없음).
    expect(find.text('NEXT-PROBLEM-PROBE'), findsNothing);
  });
}
