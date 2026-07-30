// 정답 제출 플로우 위젯 테스트 — G1 학습 루프 닫힘의 클라이언트 축(S3-09) 화면 검증.
//
// 검증 축: ① 정답 제출 어포던스(활성 문제 있을 때만) → ② 최종답 시트 입력·제출 →
// ③ verification_state=="correct"면 "다음 문제로" 노출·탭 시 problemPath로 이동(루프 닫힘 지점)
//   / "incorrect"·"unverifiable"면 화면 유지·해당 안내(부정 강화 금지·정직).
//
// 네비게이션(problemPath 재-fetch 진입)을 실제로 확인하려고 MaterialApp.router + 최소 GoRouter를
// 쓴다(기존 chat_screen_test는 MaterialApp.home라 네비 미검증). attemptsApi는 fake로 주입한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/attempts_api.dart';
import 'package:korean_math_app/features/problems/data/attempts_models.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 미리 짠 채점 결과를 돌려주는 fake(네트워크 없이).
class _FakeAttemptsApi extends AttemptsApi {
  _FakeAttemptsApi({this.verificationState = 'correct'}) : super(Dio());

  final String verificationState;

  @override
  Future<AttemptSubmitResponse> submitAttempt({
    required String problemId,
    required String studentAnswer,
    int? durationSeconds,
    String? sessionId,
    double? confidenceSelfReported,
  }) async {
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
      GoRoute(
        path: AppRoutes.chatPath,
        builder: (_, __) => const ChatScreen(),
      ),
      GoRoute(
        path: AppRoutes.problemPath,
        builder: (_, __) => const _ProblemProbe(),
      ),
    ],
  );
}

Widget _app({required AttemptsApi attemptsApi, required Problem? problem}) {
  return ProviderScope(
    overrides: [
      attemptsApiProvider.overrideWithValue(attemptsApi),
      activeProblemProvider.overrideWith((ref) => problem),
    ],
    child: MaterialApp.router(routerConfig: _router()),
  );
}

/// 정답 제출 어포던스 탭 → 시트에 최종답 입력 → 제출까지의 공통 조작.
Future<void> _submitAnswer(WidgetTester tester, String answer) async {
  await tester.tap(find.byIcon(Icons.task_alt));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const Key('answer-input')), answer);
  await tester.tap(find.widgetWithText(FilledButton, '제출'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('correct: "다음 문제로" 노출·탭 시 문제 화면(problemPath)으로 이동한다',
      (tester) async {
    await tester.pumpWidget(
      _app(
        attemptsApi: _FakeAttemptsApi(verificationState: 'correct'),
        problem: _problem,
      ),
    );
    await tester.pumpAndSettle();

    await _submitAnswer(tester, 'x=3');

    // 정답 카드 + 명시적 진행 어포던스.
    expect(find.textContaining('정답이에요'), findsOneWidget);
    expect(find.text('다음 문제로'), findsOneWidget);

    // 탭하면 문제 화면으로 이동한다(루프 닫힘: ProblemScreen이 next-problem 재-fetch).
    await tester.tap(find.text('다음 문제로'));
    await tester.pumpAndSettle();
    expect(find.text('NEXT-PROBLEM-PROBE'), findsOneWidget);
  });

  testWidgets('incorrect: 화면 유지·부정 강화 없는 안내·진행 어포던스 없음', (tester) async {
    await tester.pumpWidget(
      _app(
        attemptsApi: _FakeAttemptsApi(verificationState: 'incorrect'),
        problem: _problem,
      ),
    );
    await tester.pumpAndSettle();

    await _submitAnswer(tester, 'x=1');

    expect(find.textContaining('살펴볼까요'), findsOneWidget);
    expect(find.text('다음 문제로'), findsNothing); // 진행 안 함.
    expect(find.textContaining('틀렸'), findsNothing); // 부정 강화 금지.

    // "계속하기"로 카드를 닫으면 화면 유지(코치 계속)·문제 화면으로 이동하지 않는다.
    await tester.tap(find.text('계속하기'));
    await tester.pumpAndSettle();
    expect(find.textContaining('살펴볼까요'), findsNothing);
    expect(find.text('NEXT-PROBLEM-PROBE'), findsNothing);
    expect(find.text('WhyMath'), findsOneWidget); // 여전히 코치 화면.
  });

  testWidgets('unverifiable: 정직 안내·화면 유지·진행 어포던스 없음', (tester) async {
    await tester.pumpWidget(
      _app(
        attemptsApi: _FakeAttemptsApi(verificationState: 'unverifiable'),
        problem: _problem,
      ),
    );
    await tester.pumpAndSettle();

    await _submitAnswer(tester, '설명형 답');

    expect(find.textContaining('확인하지 못했어요'), findsOneWidget);
    expect(find.text('다음 문제로'), findsNothing);
    expect(find.text('NEXT-PROBLEM-PROBE'), findsNothing);
  });

  testWidgets('활성 문제가 없으면 정답 제출 어포던스가 보이지 않는다', (tester) async {
    await tester.pumpWidget(
      _app(attemptsApi: _FakeAttemptsApi(), problem: null),
    );
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.task_alt), findsNothing);
  });
}
