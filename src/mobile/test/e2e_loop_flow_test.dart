// S1 E2E 학습 루프 *앱 계층 관통* 플로우 테스트 — 온보딩→진단→문제→코치(세션)→turn→verify.
//
// 백엔드 `tests/backend/api/test_e2e_vertical_slice_integration.py`의 호출 순서·불변식을 *앱 측에서
// 미러*한다. fake가 아니라 **실 api 클라이언트·실 컨트롤러**를 하나의 라우팅 Dio 어댑터(경로별 canned
// 응답)에 물려, 실제 직렬화·경로·모델 매핑을 한 번에 관통 검증한다(라이브 키 전의 회귀 앵커).
//
// 검증 불변식(백엔드 앵커와 동형):
//  ① answer 비노출 — GET problem이 answer를 보내도 클라 Problem/코치 응답에 진입하지 않는다.
//  ② verify 신호 정합 — 코치 solution_verification.first_incorrect_index == 독립 verify와 일치.
//  ③ 턴 영속 — 세션 생성(2턴)+turn(2턴)=… getSession이 누적 턴을 돌려준다.
//  ④ 세션 problem_id 배선 — 활성 문제가 createSession 본문 problem_id로 실린다.
//  ⑤ is_minor 서버파생 — 온보딩 PATCH 본문에 is_minor를 싣지 않는다(서버가 birth_year에서 파생).
//  ⑥ 완료 신호 소비(MOB-20) — 세션 턴은 돌아보기 대기, 다음 턴은 완료를 내리고 클라 상태가
//     그대로 따라간다. 완료여도 클라는 `POST /v1/me/attempts`를 부르지 않는다(중복 적재 금지).
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/application/completion_signal.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/onboarding/data/user_api.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/application/diagnosis_controller.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/verify/data/verify_api.dart';

const String _answerSentinel = '정답은-42-절대노출금지';

/// 경로·메서드로 canned 응답을 라우팅하는 어댑터 — 요청도 경로별로 캡처한다.
class _RoutingAdapter implements HttpClientAdapter {
  final Map<String, RequestOptions> captured = <String, RequestOptions>{};

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    final method = options.method;
    captured['$method $path'] = options;
    return _json(_bodyFor(method, path));
  }

  @override
  void close({bool force = false}) {}

  Map<String, dynamic> _bodyFor(String method, String path) {
    if (method == 'PATCH' && path == '/v1/users/me') {
      return <String, dynamic>{};
    }
    if (path == '/v1/me/next-problem') {
      return <String, dynamic>{
        'problem_id': 'prob-1',
        'theta': 0.3,
        'measurement_sufficient': false,
      };
    }
    if (path == '/v1/me/diagnosis/concepts') {
      return <String, dynamic>{'__list__': <dynamic>[]};
    }
    if (path == '/v1/problems/prob-1') {
      // ① 백엔드는 answer를 그대로 반환한다 — 클라 모델이 걸러야 한다.
      return <String, dynamic>{
        'problem_id': 'prob-1',
        'source_type': '자체생성',
        'subject': '미적분',
        'subunit': '합성함수의 미분',
        'unit_codes': <String>['CAL-DIFF-COMP'],
        'question_text': '다음 함수를 미분하시오.',
        'answer': _answerSentinel,
        'answer_explanation': '풀이 설명 $_answerSentinel',
      };
    }
    if (path == '/v1/coach/sessions') {
      // 세션 생성 — 코치 결정 + 영속 식별자 + verify 신호(answer는 결코 싣지 않는다).
      // ⑥ 정답 도달 직후라 *돌아보기 1턴 대기*다(완료 아님·서버 계약 순서 그대로).
      return _coachBody(
        dialogueId: 'dlg-1',
        wh1: 1,
        awaitingReflection: true,
      );
    }
    if (path == '/v1/coach/sessions/dlg-1/turns') {
      // ⑥ 학생의 돌아보기 응답 턴에서 완료된다 — 서버가 attempt를 적재하고 id를 돌려준다.
      return _coachBody(
        wh1: 2,
        problemComplete: true,
        completedAttemptId: 'att-e2e-1',
      );
    }
    if (method == 'GET' && path == '/v1/coach/sessions/dlg-1') {
      // ③ 생성 2턴 + turn 2턴 = 4턴이 누적 영속됨.
      return <String, dynamic>{
        'dialogue': <String, dynamic>{'dialogue_id': 'dlg-1', 'total_turns': 4},
        'turns': <dynamic>[
          <String, dynamic>{'turn_order': 1, 'role': 'student', 'content': 'a'},
          <String, dynamic>{
            'turn_order': 2,
            'role': 'assistant',
            'content': 'p1',
          },
          <String, dynamic>{'turn_order': 3, 'role': 'student', 'content': 'b'},
          <String, dynamic>{
            'turn_order': 4,
            'role': 'assistant',
            'content': 'p2',
          },
        ],
      };
    }
    if (path == '/v1/verify-solution') {
      // ② 코치 solution_verification과 동일 위치(first_incorrect_index=1)를 가리킨다.
      return _verifyBody();
    }
    return <String, dynamic>{};
  }

  /// 코치 응답(세션/turn 공통) — decision + solution_verification + 영속 필드. answer 없음.
  Map<String, dynamic> _coachBody({
    String? dialogueId,
    required int wh1,
    bool problemComplete = false,
    bool awaitingReflection = false,
    String? completedAttemptId,
  }) {
    return <String, dynamic>{
      'decision': <String, dynamic>{
        'polya_stage_to_advance': 'stay',
        'prompt': '세 번째 줄의 계산을 다시 살펴볼까요?',
        'system': 's',
        'socratic_category': '단계분해',
      },
      'solution_coaching': <String, dynamic>{
        'trigger': <String, dynamic>{
          'focus': 'verify',
          'rationale': '단계 검증 결과',
          'prompt': '',
          'socratic_category': '검증',
        },
        'arithmetic_error': true,
        'solution_verification': _verifyBody(),
      },
      if (dialogueId != null) 'dialogue_id': dialogueId,
      'student_turn_id': 's-$wh1',
      'assistant_turn_id': 'a-$wh1',
      'wh1_turn_index': wh1,
      'wh1_exploration_turn': false,
      // S3-32 완료 신호 3필드(MOB-20 클라 소비 대상).
      'problem_complete': problemComplete,
      'awaiting_reflection': awaitingReflection,
      'completed_attempt_id': completedAttemptId,
    };
  }

  Map<String, dynamic> _verifyBody() => <String, dynamic>{
        'n_transitions': 2,
        'n_correct': 1,
        'n_incorrect': 1,
        'n_unverifiable': 0,
        'unverified_ratio': 0.0,
        'first_incorrect_index': 1,
        'has_incorrect': true,
      };

  ResponseBody _json(Map<String, dynamic> body) => ResponseBody.fromString(
        jsonEncode(body['__list__'] ?? body),
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
}

void main() {
  test('온보딩→진단→문제→코치(세션)→turn→getSession→verify를 앱 계층에서 관통한다', () async {
    final adapter = _RoutingAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://x'))
      ..httpClientAdapter = adapter;

    final container = ProviderContainer(
      overrides: [
        problemsApiProvider.overrideWithValue(ProblemsApi(dio)),
        coachApiProvider.overrideWithValue(CoachApi(dio)),
      ],
    );
    addTearDown(container.dispose);

    // autoDispose 컨트롤러가 await 중 폐기되지 않도록 리스너로 살려 둔다(실제 앱에선 화면이
    // watch로 구독을 유지하는 것과 동형). 구독 없이 read만 하면 await 사이에 폐기돼 상태가 리셋된다.
    container.listen(diagnosisControllerProvider, (_, __) {}, fireImmediately: true);
    container.listen(chatControllerProvider, (_, __) {}, fireImmediately: true);

    // ── 1) 온보딩: PATCH /v1/users/me (⑤ is_minor 미포함) ────────────────────
    await UserApi(dio).patchMe(<String, dynamic>{
      'birth_year': 2008,
      'target_grade': 2,
    });
    final patchBody =
        adapter.captured['PATCH /v1/users/me']!.data as Map<String, dynamic>;
    expect(patchBody.containsKey('is_minor'), isFalse); // ⑤ 서버 파생.

    // ── 2) 진단(CAT)→문제 로드: DiagnosisController ─────────────────────────
    await container.read(diagnosisControllerProvider.notifier).load();
    final diag = container.read(diagnosisControllerProvider);
    expect(diag.problem, isNotNull);
    expect(diag.problem!.problemId, 'prob-1');
    // ① answer 비노출 — 문제 모델 재직렬화에 정답 sentinel이 없다.
    final problemJson = jsonEncode(diag.problem!.toJson());
    expect(problemJson.contains(_answerSentinel), isFalse);
    expect(diag.problem!.questionText, '다음 함수를 미분하시오.');

    // ── 3) 활성 문제 세팅(진단→코치 핸드오프) ───────────────────────────────
    container.read(activeProblemProvider.notifier).state = diag.problem;

    // ── 4) 코치: 첫 풀이 전송 → 세션 생성(problem_id 배선·verify 신호) ────────
    final chat = container.read(chatControllerProvider.notifier);
    await chat.sendSolution('a\nb\nc');
    final afterCreate = container.read(chatControllerProvider);
    expect(afterCreate.dialogueId, 'dlg-1'); // 세션 생성됨.
    // ④ 세션이 활성 문제에 묶였다.
    final coachBody =
        adapter.captured['POST /v1/coach/sessions']!.data as Map<String, dynamic>;
    expect(coachBody['problem_id'], 'prob-1');
    // 코치 응답에 정답 sentinel이 없다(answer 비노출).
    final coachMsg = afterCreate.messages.firstWhere((m) => m.response != null);
    final coachFirstIncorrect = coachMsg
        .response!.solutionCoaching!.solutionVerification!.firstIncorrectIndex;
    expect(coachFirstIncorrect, 1);
    expect(jsonEncode(coachMsg.text).contains(_answerSentinel), isFalse);
    // ⑥ 이 턴은 돌아보기 대기 — 완료가 아니다(클라가 서버 순서를 그대로 따라간다).
    final afterCreateSignal = container.read(coachCompletionSignalProvider);
    expect(afterCreateSignal.awaitingReflection, isTrue);
    expect(afterCreateSignal.problemComplete, isFalse);
    expect(afterCreateSignal.completedAttemptId, isNull);

    // ── 5) 다음 발화 → 같은 세션에 turn 추가 ────────────────────────────────
    await chat.send('이 부분이 맞나요?');
    expect(
      adapter.captured.containsKey('POST /v1/coach/sessions/dlg-1/turns'),
      isTrue,
    );
    expect(container.read(chatControllerProvider).dialogueId, 'dlg-1');
    // ⑥ 다음 턴에 완료 — 서버가 적재한 attempt id까지 클라 상태에 실린다.
    final afterTurnSignal = container.read(coachCompletionSignalProvider);
    expect(afterTurnSignal.problemComplete, isTrue);
    expect(afterTurnSignal.awaitingReflection, isFalse);
    expect(afterTurnSignal.completedAttemptId, 'att-e2e-1');
    // ⑥ 완료여도 클라는 attempt를 재적재하지 않는다 — 이 경로로 나간 요청이 0건이어야 한다.
    expect(
      adapter.captured.keys.where((k) => k.contains('/v1/me/attempts')),
      isEmpty,
    );

    // ── 6) 세션 조회: ③ 턴 영속 확인 ────────────────────────────────────────
    final snapshot = await CoachApi(dio).getSession('dlg-1');
    expect(snapshot.turns, hasLength(4));
    expect(snapshot.totalTurns, 4);

    // ── 7) 독립 verify: ② 코치 신호와 first_incorrect_index 정합 ────────────
    final verdict =
        await VerifyApi(dio).verifySolution(<String>['x^2-4=0', '2x+3', 'x=2']);
    expect(verdict.hasIncorrect, isTrue);
    expect(verdict.firstIncorrectIndex, coachFirstIncorrect); // ② 정합.
  });
}
