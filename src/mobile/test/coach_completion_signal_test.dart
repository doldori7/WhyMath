// 코치 완료 신호 3필드(problem_complete·awaiting_reflection·completed_attempt_id)의
// **파싱 → 상태 → UI 동작** 관통 테스트 (MOB-20 · S3-32의 클라 절반).
//
// 변별력 원칙(CLAUDE.md 2026-09-01): "정상 입력에서 초록"은 보호의 증거가 아니다. 그래서
// 이 파일은 값의 *존재*가 아니라 **값이 다르면 화면이 다르다**를 단언한다 —
//  · 신호 없음 → 선택지 목록이 보이고, 두 패널 모두 없다(대조군).
//  · awaiting_reflection=true → 선택지가 사라지고 돌아보기 안내가 뜬다(진행 보류).
//  · problem_complete=true → 선택지가 사라지고 '다음 문항으로' 어포던스가 뜬다.
//  · 그 버튼을 누르면 실제로 문제 화면으로 이동하고 신호가 비워진다.
// 서버 부재 필드는 서버 기본값(false/false/null)으로 폴백하는지도 함께 고정한다.
//
// ⚠️ 이 흐름은 `POST /v1/me/attempts`를 **부르지 않는다** — 완료 턴에서 서버가 이미 attempt를
// 적재했다(중복 적재 금지·api/coach.py 계약). 그 부재도 아래에서 단언한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:korean_math_app/core/router.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/application/completion_signal.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 완료 신호를 테스트가 정하는 fake — 다음 턴이 돌려줄 3필드를 그대로 싣는다.
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi({required this.response}) : super(Dio());

  final CoachResponse response;

  /// 다음 응답에 실을 서버 권위값(테스트가 턴 사이에 바꾼다).
  bool problemComplete = false;
  bool awaitingReflection = false;
  String? completedAttemptId;

  /// true면 네트워크 실패를 흉내낸다(실패 시 신호가 남지 않는지 검증용).
  bool shouldThrow = false;

  int calls = 0;

  CoachTurnResult _result(String dialogueId) {
    calls++;
    return CoachTurnResult(
      dialogueId: dialogueId,
      response: response,
      wh1TurnIndex: calls,
      problemComplete: problemComplete,
      awaitingReflection: awaitingReflection,
      completedAttemptId: completedAttemptId,
    );
  }

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
    return _result('dlg-1');
  }

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    if (shouldThrow) {
      throw _fail();
    }
    return _result(dialogueId);
  }
}

CoachResponse _response() => const CoachResponse(
      decision: PedagogyDecision(
        polyaStageToAdvance: 'stay',
        prompt: '지금까지 한 걸 한 줄로 정리해 볼까요?',
        system: '시스템(테스트)',
        socraticCategory: '조건확인',
      ),
    );

/// 객관식 활성 문항 — 선택지 목록의 존재/부재로 UI 변화를 관측하기 위한 고정 픽스처.
const Problem _mcProblem = Problem(
  problemId: 'p-mc',
  sourceType: '자체생성',
  subject: '공통',
  questionFormat: '객관식',
  questionText: '서로 다른 실근의 개수는?',
  choices: <String>['0', '1', '2', '3'],
);

/// 코치 응답 JSON 한 벌(완료 3필드는 [extra]로 덮어쓴다).
Map<String, dynamic> _coachJson([Map<String, dynamic> extra = const {}]) =>
    <String, dynamic>{
      'decision': <String, dynamic>{
        'polya_stage_to_advance': 'stay',
        'prompt': '어떻게 그렇게 됐는지 말해 볼까요?',
        'system': 's',
        'socratic_category': '검증',
      },
      'wh1_turn_index': 2,
      ...extra,
    };

/// 채팅 화면 + 실제 라우터(문제 화면은 표식만 있는 대역)로 감싼다.
///
/// '다음 문항으로'가 *진짜 이동*하는지 보려면 라우터가 필요하다 — 버튼 존재만 확인하면
/// 어포던스가 죽어 있어도 초록이 된다(변별력 없는 검증 금지).
Widget _wrap(ProviderContainer container) {
  final router = GoRouter(
    initialLocation: AppRoutes.chatPath,
    routes: [
      GoRoute(
        path: AppRoutes.chatPath,
        builder: (_, __) => const ChatScreen(),
      ),
      GoRoute(
        path: AppRoutes.problemPath,
        builder: (_, __) => const Scaffold(body: Text('문제 화면(대역)')),
      ),
    ],
  );
  return UncontrolledProviderScope(
    container: container,
    child: MaterialApp.router(routerConfig: router),
  );
}

ProviderContainer _container(_FakeCoachApi fake) {
  final container = ProviderContainer(
    // 타입 주석 없이 둔다 — riverpod 3에서 `Override`는 공개 타입명이 아니고,
    // 이 저장소의 다른 테스트도 전부 `overrides: [...]` 형태다.
    overrides: [
      coachApiProvider.overrideWithValue(fake),
      activeProblemProvider.overrideWith((ref) => _mcProblem),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('CoachTurnResult 파싱 — 서버 완료 신호 3필드', () {
    test('3필드가 실려 오면 그 값을 그대로 파싱한다', () {
      final result = CoachTurnResult.fromJson(
        _coachJson(<String, dynamic>{
          'problem_complete': true,
          'awaiting_reflection': false,
          'completed_attempt_id': '8f14e45f-ceea-467a-9f3a-1a2b3c4d5e6f',
        }),
        dialogueId: 'dlg-1',
      );

      expect(result.problemComplete, isTrue);
      expect(result.awaitingReflection, isFalse);
      expect(result.completedAttemptId, '8f14e45f-ceea-467a-9f3a-1a2b3c4d5e6f');
    });

    test('돌아보기 대기 턴은 awaiting_reflection만 참이고 attempt id가 없다', () {
      final result = CoachTurnResult.fromJson(
        _coachJson(<String, dynamic>{
          'problem_complete': false,
          'awaiting_reflection': true,
          'completed_attempt_id': null,
        }),
        dialogueId: 'dlg-1',
      );

      expect(result.awaitingReflection, isTrue);
      expect(result.problemComplete, isFalse);
      expect(result.completedAttemptId, isNull);
    });

    test('3필드가 아예 없으면 서버 기본값(false·false·null)으로 폴백한다', () {
      final result = CoachTurnResult.fromJson(
        _coachJson(),
        dialogueId: 'dlg-1',
      );

      expect(result.problemComplete, isFalse);
      expect(result.awaitingReflection, isFalse);
      expect(result.completedAttemptId, isNull);
    });
  });

  group('컨트롤러 → 완료 신호 provider', () {
    test('턴 응답의 완료 신호가 provider 상태로 그대로 옮겨진다', () async {
      final fake = _FakeCoachApi(response: _response())
        ..problemComplete = true
        ..completedAttemptId = 'att-77';
      final container = _container(fake);
      container.listen(chatControllerProvider, (_, __) {}, fireImmediately: true);

      await container.read(chatControllerProvider.notifier).send('x=2인 것 같아요');

      final signal = container.read(coachCompletionSignalProvider);
      expect(signal.problemComplete, isTrue);
      expect(signal.awaitingReflection, isFalse);
      expect(signal.completedAttemptId, 'att-77');
    });

    test('돌아보기 대기 → 완료 순서를 턴마다 갱신한다', () async {
      final fake = _FakeCoachApi(response: _response())..awaitingReflection = true;
      final container = _container(fake);
      container.listen(chatControllerProvider, (_, __) {}, fireImmediately: true);

      await container.read(chatControllerProvider.notifier).send('x=2');
      expect(container.read(coachCompletionSignalProvider).awaitingReflection, isTrue);
      expect(container.read(coachCompletionSignalProvider).problemComplete, isFalse);

      // 학생의 돌아보기 응답 다음 턴에 완료된다(서버 계약·MVP 1턴).
      fake
        ..awaitingReflection = false
        ..problemComplete = true
        ..completedAttemptId = 'att-88';
      await container.read(chatControllerProvider.notifier).send('인수분해로 풀었어요');

      final signal = container.read(coachCompletionSignalProvider);
      expect(signal.awaitingReflection, isFalse);
      expect(signal.problemComplete, isTrue);
      expect(signal.completedAttemptId, 'att-88');
    });

    test('턴이 실패하면 이전 완료 신호가 남지 않는다(낡은 완료 패널 방지)', () async {
      final fake = _FakeCoachApi(response: _response())
        ..problemComplete = true
        ..completedAttemptId = 'att-99';
      final container = _container(fake);
      container.listen(chatControllerProvider, (_, __) {}, fireImmediately: true);

      await container.read(chatControllerProvider.notifier).send('첫 턴');
      expect(container.read(coachCompletionSignalProvider).problemComplete, isTrue);

      fake.shouldThrow = true;
      await container.read(chatControllerProvider.notifier).send('두 번째 턴');

      expect(
        container.read(coachCompletionSignalProvider),
        CoachCompletionSignal.none,
      );
    });
  });

  group('화면 동작 — 완료 신호가 어포던스를 바꾼다', () {
    testWidgets('대조군: 신호가 없으면 선택지가 보이고 두 패널 모두 없다', (tester) async {
      final fake = _FakeCoachApi(response: _response());
      final container = _container(fake);
      await tester.pumpWidget(_wrap(container));

      await tester.enterText(find.byType(TextField), '이거 어떻게 시작해요?');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      expect(find.text('보기 번호를 골라 보세요'), findsOneWidget);
      expect(find.byType(OutlinedButton), findsNWidgets(4));
      expect(find.textContaining('돌아보기 차례'), findsNothing);
      expect(find.text('다음 문항으로'), findsNothing);
    });

    testWidgets('awaiting_reflection=true → 선택지가 사라지고 돌아보기 안내가 뜬다',
        (tester) async {
      final fake = _FakeCoachApi(response: _response())..awaitingReflection = true;
      final container = _container(fake);
      await tester.pumpWidget(_wrap(container));

      await tester.enterText(find.byType(TextField), 'x=2');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // 진행 보류 — 번호 선택으로 다음 턴을 흘려보낼 수 없다.
      expect(find.text('보기 번호를 골라 보세요'), findsNothing);
      expect(find.byType(OutlinedButton), findsNothing);
      expect(find.textContaining('돌아보기 차례'), findsOneWidget);
      // 아직 완료가 아니므로 '다음 문항으로'는 뜨지 않는다.
      expect(find.text('다음 문항으로'), findsNothing);
    });

    testWidgets('problem_complete=true → 선택지가 사라지고 다음 문항 어포던스가 뜬다',
        (tester) async {
      final fake = _FakeCoachApi(response: _response())
        ..problemComplete = true
        ..completedAttemptId = 'att-1';
      final container = _container(fake);
      await tester.pumpWidget(_wrap(container));

      await tester.enterText(find.byType(TextField), '인수분해로 풀었어요');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      expect(find.text('보기 번호를 골라 보세요'), findsNothing);
      expect(find.text('다음 문항으로'), findsOneWidget);
      // 완료 패널은 서버가 준 attempt id로 식별된다(학생 화면엔 UUID를 쓰지 않는다).
      final panel = find.byKey(const ValueKey<String>('completion-panel-att-1'));
      expect(panel, findsOneWidget);
      // 패널 안에 정답·점수·attempt id는 어떤 형태로도 싣지 않는다(절대 금기·UUID 무의미).
      expect(
        find.descendant(of: panel, matching: find.textContaining('정답')),
        findsNothing,
      );
      expect(
        find.descendant(of: panel, matching: find.textContaining('att-1')),
        findsNothing,
      );
    });

    testWidgets("'다음 문항으로'를 누르면 문제 화면으로 이동하고 신호가 비워진다",
        (tester) async {
      final fake = _FakeCoachApi(response: _response())
        ..problemComplete = true
        ..completedAttemptId = 'att-2';
      final container = _container(fake);
      await tester.pumpWidget(_wrap(container));

      await tester.enterText(find.byType(TextField), '다 풀었어요');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      await tester.tap(find.text('다음 문항으로'));
      await tester.pumpAndSettle();

      expect(find.text('문제 화면(대역)'), findsOneWidget);
      expect(
        container.read(coachCompletionSignalProvider),
        CoachCompletionSignal.none,
      );
    });
  });
}
