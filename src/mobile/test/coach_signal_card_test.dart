// coach 신호 카드 위젯 테스트 — 신호 유무·종류·요약 cue 렌더와 *답 미루기* 가드를 검증.
//
// canned CoachResponse(런타임 객체)로 네트워크 없이 확인한다. 정답값·"틀렸다" 단정이
// 렌더 텍스트에 *없음*을 단언해 답 미루기(절대 금기)를 지킨다.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/coach_signal_card.dart';

/// 항상 존재하는 핵심 결정(테스트 공통).
const _decision = PedagogyDecision(
  polyaStageToAdvance: 'stay',
  prompt: '같이 한 번 더 살펴볼까요?',
  system: '시스템(테스트)',
);

/// verify 포커스 트리거(focusStepIndex 옵션).
CoachingTrigger _trigger({int? focusStepIndex}) => CoachingTrigger(
      focus: 'verify',
      rationale: '근거(테스트)',
      prompt: '어디서 확신이 줄었는지 짚어 볼까요?',
      socraticCategory: '검증',
      focusStepIndex: focusStepIndex,
    );

/// solutionCoaching을 끼운 코치 응답을 만든다.
CoachResponse _response({SolutionCoaching? coaching}) =>
    CoachResponse(decision: _decision, solutionCoaching: coaching);

Widget _wrap(CoachResponse response) =>
    MaterialApp(home: Scaffold(body: CoachSignalCard(response: response)));

void main() {
  testWidgets('arithmeticError=true면 검산 칩이 렌더된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(),
            arithmeticError: true,
            errorKind: 'arithmetic',
          ),
        ),
      ),
    );

    expect(find.textContaining('스스로 검산해볼까?'), findsOneWidget);
    expect(find.textContaining('계산'), findsOneWidget);
  });

  testWidgets('focusStepIndex가 있으면 지점 마커가 렌더된다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(focusStepIndex: 2),
            arithmeticError: false,
          ),
        ),
      ),
    );

    expect(find.text('다시 살펴볼 지점이 있어요'), findsOneWidget);
    // 줄 번호(숫자) 노출은 후속 — 카드엔 "2" 같은 인덱스가 보이면 안 된다.
    expect(find.textContaining('2'), findsNothing);
  });

  testWidgets('solutionVerification(hasIncorrect)이면 단계 요약과 부드러운 안내가 보인다',
      (tester) async {
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(),
            arithmeticError: false,
            solutionVerification: const SolutionVerificationResult(
              nCorrect: 2,
              nIncorrect: 1,
              nUnverifiable: 0,
              nTransitions: 3,
              unverifiedRatio: 0.0,
              firstIncorrectIndex: 2,
              hasIncorrect: true,
            ),
          ),
        ),
      ),
    );

    expect(find.text('3단계 중 2단계 확인'), findsOneWidget);
    expect(find.text('다시 볼 단계가 있어요'), findsOneWidget);
  });

  testWidgets('verificationOcrGated=true면 재확인 문구가 보인다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(),
            arithmeticError: false,
            verificationOcrGated: true,
          ),
        ),
      ),
    );

    expect(find.text('풀이가 잘 안 보여요 — 다시 확인해볼까요?'), findsOneWidget);
  });

  testWidgets('신호가 전무하면 카드를 그리지 않는다(빈 위젯)', (tester) async {
    // solutionCoaching 자체가 null인 흔한 경우.
    await tester.pumpWidget(_wrap(_response()));
    expect(find.byType(Icon), findsNothing);
    expect(find.byType(Text), findsNothing);

    // solutionCoaching은 있지만 모든 신호가 비어 있는 경우도 카드 없음.
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(),
            arithmeticError: false,
          ),
        ),
      ),
    );
    expect(find.byType(Icon), findsNothing);
    expect(find.byType(Text), findsNothing);
  });

  testWidgets('답 미루기 가드 — 정답값·"틀렸다" 단정은 렌더되지 않는다', (tester) async {
    // 모든 신호를 켜도 정답/수정/단정 표현이 텍스트에 없어야 한다.
    await tester.pumpWidget(
      _wrap(
        _response(
          coaching: SolutionCoaching(
            trigger: _trigger(focusStepIndex: 1),
            arithmeticError: true,
            errorKind: 'inequality',
            validationSignal: '3 = 5 는 거짓',
            solutionVerification: const SolutionVerificationResult(
              nCorrect: 1,
              nIncorrect: 1,
              nUnverifiable: 0,
              nTransitions: 2,
              unverifiedRatio: 0.0,
              firstIncorrectIndex: 1,
              hasIncorrect: true,
            ),
            verificationOcrGated: true,
          ),
        ),
      ),
    );

    // "틀렸다"·"오답"·정답 누출(validationSignal 원문)은 절대 노출 안 함.
    expect(find.textContaining('틀렸'), findsNothing);
    expect(find.textContaining('오답'), findsNothing);
    expect(find.textContaining('거짓'), findsNothing);
    expect(find.textContaining('3 = 5'), findsNothing);
  });
}
