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

/// 확인 보류 분포 케이스의 코치 응답(MATH-03) — nUnverifiable·사유 맵만 바꿔 재사용.
/// 전이 3회 고정·incorrect 0(보류 3분기 문구만 격리 검증).
CoachResponse _responseWithHolds({
  required int nUnverifiable,
  required Map<String, int> byReason,
}) =>
    _response(
      coaching: SolutionCoaching(
        trigger: _trigger(),
        arithmeticError: false,
        solutionVerification: SolutionVerificationResult(
          nCorrect: 3 - nUnverifiable,
          nIncorrect: 0,
          nUnverifiable: nUnverifiable,
          unverifiableByReason: byReason,
          nTransitions: 3,
          unverifiedRatio: nUnverifiable / 3,
          firstIncorrectIndex: null,
          hasIncorrect: false,
        ),
      ),
    );

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

  // ── MATH-03 — 확인 보류 사유 3분기(고칠 수 있음/고칠 것 없음/단정하지 않음) ──
  //
  // 운영 7종 코드(백엔드 VerifyStepReasonCode)와 학생 3분기의 비대칭은 의도다 — 검증기
  // 내부를 학생에게 노출하지 않고, *학생 행동이 갈리는* 구분만 문구로 낸다(acceptance ③).

  testWidgets('접힘 ② 재현 — 사유 분포가 없으면(구판) 원인 무관 한 문구로 접힌다',
      (tester) async {
    // 백엔드가 reason_code를 실어도(접힘 ① 해소) 분포가 클라에 안 오면(빈 맵 = MATH-03 이전
    // 서버) 표기 문제든 비대수 단계든 같은 '확인 보류 일부'만 보인다 — 손실이 두 군데임의
    // 클라 쪽 실측(한쪽만 고치면 학생 화면의 변별은 회복되지 않는다).
    await tester.pumpWidget(
      _wrap(_responseWithHolds(nUnverifiable: 2, byReason: const <String, int>{})),
    );

    expect(find.text('3단계 중 1단계 확인 · 확인 보류 일부'), findsOneWidget);
    // 세분 문구는 데이터가 없어 그려질 수 없다(무변별의 실체).
    expect(find.textContaining('표기를 한 번 확인해볼까요?'), findsNothing);
    expect(find.textContaining('건너뛰었어요'), findsNothing);
  });

  testWidgets('고칠 수 있는 것(parse_error) → 표기 확인 문구', (tester) async {
    await tester.pumpWidget(
      _wrap(_responseWithHolds(nUnverifiable: 1, byReason: const <String, int>{'parse_error': 1})),
    );

    expect(
      find.text('읽지 못한 단계가 있어요 — 표기를 한 번 확인해볼까요?'),
      findsOneWidget,
    );
    // 분포가 오면 legacy 접미사는 세분 행으로 대체된다(이중 표기 없음).
    expect(find.textContaining('확인 보류 일부'), findsNothing);
    // 다른 분기 문구는 없다.
    expect(find.textContaining('건너뛰었어요'), findsNothing);
    expect(find.text('확인을 보류한 단계가 있어요'), findsNothing);
  });

  testWidgets('고칠 게 없는 것(non_algebraic_step) → 건너뜀 안내 문구', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _responseWithHolds(
          nUnverifiable: 1,
          byReason: const <String, int>{'non_algebraic_step': 1},
        ),
      ),
    );

    expect(find.text('계산으로 확인하는 종류가 아닌 단계는 건너뛰었어요'), findsOneWidget);
    expect(find.textContaining('표기를 한 번 확인해볼까요?'), findsNothing);
    expect(find.text('확인을 보류한 단계가 있어요'), findsNothing);
  });

  testWidgets('단정하지 않는 것(undecidable 계열) → 보류 톤 문구', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _responseWithHolds(
          nUnverifiable: 2,
          byReason: const <String, int>{'undecidable': 1, 'subset_ambiguous': 1},
        ),
      ),
    );

    expect(find.text('확인을 보류한 단계가 있어요'), findsOneWidget);
    expect(find.textContaining('표기를 한 번 확인해볼까요?'), findsNothing);
    expect(find.textContaining('건너뛰었어요'), findsNothing);
  });

  testWidgets('변별력(MATH-03 ⑤) — parse_error와 non_algebraic_step은 서로 다른 문구',
      (tester) async {
    // 이 태스크의 존재 이유: "내 표기가 잘못됨"(고칠 수 있음)과 "원래 계산으로 확인 못 하는
    // 단계"(고칠 게 없음)는 학생 행동이 정반대다 — 두 입력이 같은 문구를 내면 red(위장).
    await tester.pumpWidget(
      _wrap(_responseWithHolds(nUnverifiable: 1, byReason: const <String, int>{'parse_error': 1})),
    );
    final parseErrorTexts = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => t.data)
        .whereType<String>()
        .toSet();

    await tester.pumpWidget(
      _wrap(
        _responseWithHolds(
          nUnverifiable: 1,
          byReason: const <String, int>{'non_algebraic_step': 1},
        ),
      ),
    );
    final nonAlgebraicTexts = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => t.data)
        .whereType<String>()
        .toSet();

    expect(parseErrorTexts, isNot(equals(nonAlgebraicTexts)));
  });

  testWidgets('미지의 사유 코드는 보류 톤으로 보수 폴백(단정 금지)', (tester) async {
    // 백엔드가 코드를 추가해도(폐쇄 enum 확장은 별도 결정) 구판 클라는 "고칠 수 있다"류의
    // 행동 지시를 지어내지 않고 단정하지 않는 분기로만 접는다.
    await tester.pumpWidget(
      _wrap(_responseWithHolds(nUnverifiable: 1, byReason: const <String, int>{'future_code': 1})),
    );

    expect(find.text('확인을 보류한 단계가 있어요'), findsOneWidget);
    expect(find.textContaining('표기를 한 번 확인해볼까요?'), findsNothing);
  });

  testWidgets('세 분기 공존 — 각 분기 행이 한 번씩 그려진다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _responseWithHolds(
          nUnverifiable: 3,
          byReason: const <String, int>{
            'parse_error': 1,
            'non_algebraic_step': 1,
            'heterogeneous_form': 1,
          },
        ),
      ),
    );

    expect(
      find.text('읽지 못한 단계가 있어요 — 표기를 한 번 확인해볼까요?'),
      findsOneWidget,
    );
    expect(find.text('계산으로 확인하는 종류가 아닌 단계는 건너뛰었어요'), findsOneWidget);
    expect(find.text('확인을 보류한 단계가 있어요'), findsOneWidget);
  });

  testWidgets('답 미루기 가드(MATH-03) — 3분기 문구에도 단정·낙인·정답이 없다', (tester) async {
    await tester.pumpWidget(
      _wrap(
        _responseWithHolds(
          nUnverifiable: 3,
          byReason: const <String, int>{
            'parse_error': 1,
            'non_algebraic_step': 1,
            'variable_mismatch': 1,
          },
        ),
      ),
    );

    // 부정 강화·낙인 어휘 금지(절대 금기) — 문구 어디에도 없어야 한다.
    expect(find.textContaining('틀렸'), findsNothing);
    expect(find.textContaining('오답'), findsNothing);
    expect(find.textContaining('잘못'), findsNothing);
    expect(find.textContaining('실수'), findsNothing);
    expect(find.textContaining('못 한'), findsNothing);
    // 운영 코드 원문(검증기 내부)도 학생 화면에 노출되지 않는다(7종↔3분기 비대칭 유지).
    expect(find.textContaining('parse_error'), findsNothing);
    expect(find.textContaining('variable_mismatch'), findsNothing);
  });
}
