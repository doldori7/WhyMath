// ProblemScreen 위젯 테스트 — 문제 렌더·후보없음 안내·"풀이 시작" 전이·answer 미노출 검증. S1.
//
// problemsApiProvider를 fake로 override해 네트워크 없이 화면 동작을 확인한다(ocr_capture_screen_test
// 답습). go_router 전이가 필요하므로 최소 라우터(/problem·/)로 감싼다. 정서 안전·절대금기 가드로
// 정답·정오 강조가 렌더 텍스트에 없음을 단언한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/problems/presentation/problem_screen.dart';

/// 미리 짠 next-problem·problem을 돌려주는 fake.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi({required this.next, this.problem}) : super(Dio());

  final NextProblemResponse next;
  final Problem? problem;

  @override
  Future<NextProblemResponse> getNextProblem({
    bool prioritizeWeakConcepts = false,
  }) async =>
      next;

  @override
  Future<Problem> getProblem(String problemId) async => problem!;

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async =>
      const <ConceptDiagnosisItem>[];
}

/// ProblemScreen을 최소 라우터(/problem 진입·/ 채팅 placeholder)로 감싼다.
Widget _wrap(ProblemsApi api) {
  final router = GoRouter(
    initialLocation: AppRoutes.problemPath,
    routes: [
      GoRoute(
        path: AppRoutes.problemPath,
        builder: (_, __) => const ProblemScreen(),
      ),
      GoRoute(
        path: AppRoutes.chatPath,
        builder: (_, __) => const Scaffold(body: Text('채팅 화면')),
      ),
    ],
  );
  return ProviderScope(
    overrides: [problemsApiProvider.overrideWithValue(api)],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  testWidgets('추천 문제를 로드해 발문·맥락·"풀이 시작"을 렌더한다', (tester) async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: 'p1'),
      problem: const Problem(
        problemId: 'p1',
        sourceType: '자체생성',
        subject: '미적분',
        subunit: '합성함수의 미분',
        unitCodes: <String>['CAL'],
        questionText: '다음 함수를 미분하시오.',
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('다음 함수를 미분하시오.'), findsOneWidget);
    expect(find.text('미적분'), findsOneWidget);
    expect(find.text('합성함수의 미분'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '풀이 시작'), findsOneWidget);
  });

  testWidgets('추천 후보 없음이면 코치 대화 안내로 graceful 처리한다', (tester) async {
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: null),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('추천할 문제가 없어요'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '코치와 대화하기'), findsOneWidget);
  });

  testWidgets('"풀이 시작"은 활성 문제를 세팅하고 코치로 전이한다', (tester) async {
    final container = ProviderContainer(
      overrides: [
        problemsApiProvider.overrideWithValue(
          _FakeProblemsApi(
            next: const NextProblemResponse(problemId: 'p1'),
            problem: const Problem(
              problemId: 'p1',
              sourceType: '자체생성',
              subject: '미적분',
              unitCodes: <String>['CAL'],
              questionText: '문제',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    final router = GoRouter(
      initialLocation: AppRoutes.problemPath,
      routes: [
        GoRoute(
          path: AppRoutes.problemPath,
          builder: (_, __) => const ProblemScreen(),
        ),
        GoRoute(
          path: AppRoutes.chatPath,
          builder: (_, __) => const Scaffold(body: Text('채팅 화면')),
        ),
      ],
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    // 진입 시점엔 활성 문제가 비어 있다.
    expect(container.read(activeProblemProvider), isNull);

    await tester.tap(find.widgetWithText(FilledButton, '풀이 시작'));
    await tester.pumpAndSettle();

    // 활성 문제가 세팅되고 채팅 화면으로 전이한다.
    expect(container.read(activeProblemProvider)?.problemId, 'p1');
    expect(find.text('채팅 화면'), findsOneWidget);
  });

  testWidgets(
      '이미 활성 문제(A)가 있어도 "풀이 시작"은 새 문제(B)로 전환한다(stale A 없음·MOB-12)',
      (tester) async {
    final container = ProviderContainer(
      overrides: [
        problemsApiProvider.overrideWithValue(
          _FakeProblemsApi(
            next: const NextProblemResponse(problemId: 'p2'),
            problem: const Problem(
              problemId: 'p2',
              sourceType: '자체생성',
              subject: '수학I',
              unitCodes: <String>['ALG'],
              questionText: '문제 B',
            ),
          ),
        ),
        // 이미 문제 A로 풀이 중이던 상태를 재현한다(예: 문제 화면에 다시 진입하기 전).
        activeProblemProvider.overrideWith(
          (ref) => const Problem(
            problemId: 'p1',
            sourceType: '자체생성',
            subject: '수학I',
            unitCodes: <String>['ALG'],
            questionText: '문제 A',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    final router = GoRouter(
      initialLocation: AppRoutes.problemPath,
      routes: [
        GoRoute(
          path: AppRoutes.problemPath,
          builder: (_, __) => const ProblemScreen(),
        ),
        GoRoute(
          path: AppRoutes.chatPath,
          builder: (_, __) => const Scaffold(body: Text('채팅 화면')),
        ),
      ],
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    // 진입 시점엔 여전히 A(직전 문제)가 활성이다.
    expect(container.read(activeProblemProvider)?.problemId, 'p1');

    // 전환 도중 실제로 null을 거치는지(리셋 후 재세팅) 상태 변화 시퀀스를 직접 기록한다 —
    // A→B 직접 덮어쓰기(수정 전 코드)만으로도 최종값은 이미 B라 최종값 단언만으론 레드를
    // 재현하지 못한다. 이 리스너가 그 차이를 드러낸다.
    final transitions = <Problem?>[];
    final subscription = container.listen<Problem?>(
      activeProblemProvider,
      (previous, next) => transitions.add(next),
      fireImmediately: false,
    );
    addTearDown(subscription.close);

    await tester.tap(find.widgetWithText(FilledButton, '풀이 시작'));
    await tester.pumpAndSettle();

    // 새로 시작한 B로 전환되고, A의 흔적이 남지 않는다(결함 신고 등의 오귀속 방지).
    expect(container.read(activeProblemProvider)?.problemId, 'p2');
    expect(container.read(activeProblemProvider)?.problemId, isNot('p1'));
    // 리셋 후 재세팅 — 전환 도중 null을 반드시 거친다(직접 덮어쓰기였다면 이 이벤트가 없다).
    expect(transitions, contains(isNull));
  });

  testWidgets('안전: 문제 화면에 정답 문자열이 렌더되지 않는다', (tester) async {
    // Problem 모델은 answer를 담지 않으므로 화면이 정답을 그릴 방법이 없다(구조적 차단 확인).
    final api = _FakeProblemsApi(
      next: const NextProblemResponse(problemId: 'p1'),
      problem: const Problem(
        problemId: 'p1',
        sourceType: '자체생성',
        subject: '미적분',
        unitCodes: <String>['CAL'],
        questionText: '문제 발문',
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 정오 강조·정답 문구가 없다(절대 금기).
    expect(find.textContaining('정답'), findsNothing);
    expect(find.textContaining('틀렸'), findsNothing);
  });
}
