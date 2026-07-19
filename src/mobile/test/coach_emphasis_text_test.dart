// 코치 발화 `*...*` 강조 렌더 테스트 (MOB-04).
//
// 실측 증상(2026-07-19 실기기): 코치 버블에 결정론 Polya 템플릿의 마크다운 강조가
// 원문 그대로 노출 — "좋아, 이제 *어떻게 풀지* 계획을 세워보자."의 별표가 평문으로 보였다.
//
// 검증 축: ①코치 버블의 짝 별표는 별표 미노출 + 해당 구간 굵게 ②비짝 별표(`3*4`·
// `*미완`·`**`)는 원문 그대로(안전 폴백) ③학생 버블은 무변경 — 별표 원문 유지
// (곱셈 기호 보존·변별력: 강조가 적용되면 별표가 사라져 반드시 실패한다).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/chat/presentation/coach_emphasis_text.dart';

/// 미리 짠 코치 응답을 돌려주는 fake — 네트워크 없이 화면 동작 검증용
/// (chat_screen_test.dart의 fake와 동형·이 파일 자립을 위해 최소만 복제).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi(this.response) : super(Dio());

  final CoachResponse response;

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    return CoachTurnResult(
      dialogueId: 'test-dialogue',
      response: response,
      wh1TurnIndex: 1,
    );
  }

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    return CoachTurnResult(
      dialogueId: dialogueId,
      response: response,
      wh1TurnIndex: 2,
    );
  }
}

/// 지정한 프롬프트로 코치 응답을 만든다(배지 없는 최소 응답 — 강조 렌더만 검증).
CoachResponse _response(String prompt) {
  return CoachResponse(
    decision: PedagogyDecision(
      polyaStageToAdvance: 'stay',
      prompt: prompt,
      system: '시스템(테스트)',
      socraticCategory: '',
    ),
  );
}

Widget _wrap(String coachPrompt) {
  return ProviderScope(
    overrides: [
      coachApiProvider.overrideWithValue(_FakeCoachApi(_response(coachPrompt))),
    ],
    child: const MaterialApp(home: ChatScreen()),
  );
}

/// Text 위젯의 textSpan에서 본문이 있는 TextSpan들을 순서대로 수집한다(굵기 단언용).
List<TextSpan> _collectSpans(WidgetTester tester, String plainText) {
  final Text textWidget = tester.widget<Text>(find.text(plainText));
  final List<TextSpan> spans = <TextSpan>[];
  textWidget.textSpan!.visitChildren((span) {
    if (span is TextSpan && span.text != null) {
      spans.add(span);
    }
    return true;
  });
  return spans;
}

void main() {
  group('parseCoachEmphasis — 초소형 파서 규칙', () {
    test('짝 별표는 강조 조각으로, 앞뒤는 평문 조각으로 잘린다', () {
      expect(
        parseCoachEmphasis('좋아, 이제 *어떻게 풀지* 계획을 세워보자.'),
        const <EmphasisSegment>[
          EmphasisSegment('좋아, 이제 ', emphasized: false),
          EmphasisSegment('어떻게 풀지', emphasized: true),
          EmphasisSegment(' 계획을 세워보자.', emphasized: false),
        ],
      );
    });

    test('비짝 별표는 원문 그대로 — 무손실 안전 폴백', () {
      // 닫는 별표 없음(곱셈 기호 모양) — 강조 조각 0개·원문 보존.
      for (final String raw in <String>['3*4', '*미완', '**', '* 공백 경계 *']) {
        final segments = parseCoachEmphasis(raw);
        expect(
          segments.any((s) => s.emphasized),
          isFalse,
          reason: '"$raw"에서 강조가 생기면 안 된다',
        );
        expect(
          segments.map((s) => s.text).join(),
          raw,
          reason: '"$raw"는 글자 하나 잃지 않고 원문 그대로여야 한다',
        );
      }
    });

    test('줄바꿈을 사이에 둔 별표 쌍은 강조로 인정하지 않는다', () {
      final segments = parseCoachEmphasis('*첫 줄\n둘째 줄*');
      expect(segments.any((s) => s.emphasized), isFalse);
      expect(segments.map((s) => s.text).join(), '*첫 줄\n둘째 줄*');
    });

    test('곱셈 기호와 강조 혼합 — 공백 경계 내용은 거부되고 진짜 강조만 살아남는다', () {
      // 첫 별표의 닫는 후보까지 내용("4를 곱하고 ")이 공백으로 끝나 쌍 인정 거부 →
      // 문자 그대로. 그 뒤 *다시*만 강조(왼쪽부터 한 번 훑는 결정론 파서).
      expect(
        parseCoachEmphasis('3*4를 곱하고 *다시* 보자'),
        const <EmphasisSegment>[
          EmphasisSegment('3*4를 곱하고 ', emphasized: false),
          EmphasisSegment('다시', emphasized: true),
          EmphasisSegment(' 보자', emphasized: false),
        ],
      );
    });

    test('연속 강조 쌍은 각각 독립적으로 인정된다', () {
      expect(
        parseCoachEmphasis('*이해*와 *계획*'),
        const <EmphasisSegment>[
          EmphasisSegment('이해', emphasized: true),
          EmphasisSegment('와 ', emphasized: false),
          EmphasisSegment('계획', emphasized: true),
        ],
      );
    });

    test('빈 문자열은 빈 조각 리스트 — 예외 없이 안전하다', () {
      expect(parseCoachEmphasis(''), isEmpty);
    });
  });

  group('CoachEmphasisText 위젯 — 렌더 폴백', () {
    testWidgets('강조가 없으면 원문 그대로의 평문 Text로 렌더된다', (tester) async {
      for (final String raw in <String>['3*4', '*미완', '**']) {
        await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: CoachEmphasisText(raw))),
        );
        // 안전 폴백 — 별표 포함 원문이 정확히 그대로 보인다.
        expect(find.text(raw), findsOneWidget, reason: '"$raw" 원문 유지');
      }
    });

    testWidgets('짝 별표는 별표 미노출 + 해당 구간만 굵게 렌더된다', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: CoachEmphasisText('무엇을 *구해야* 할까?')),
        ),
      );
      // 별표는 화면에서 사라지고 평문 합성 결과만 보인다.
      expect(find.text('무엇을 *구해야* 할까?'), findsNothing);
      expect(find.text('무엇을 구해야 할까?'), findsOneWidget);
      final spans = _collectSpans(tester, '무엇을 구해야 할까?');
      expect(
        spans
            .where((s) => s.style?.fontWeight == FontWeight.w700)
            .map((s) => s.text),
        <String>['구해야'],
        reason: '강조 구간만 굵게 — 나머지는 기본 굵기',
      );
    });
  });

  group('채팅 화면 통합 — 코치 버블만 강조, 학생 버블은 무변경', () {
    testWidgets('코치 버블: 짝 별표 미노출 + 해당 구간 굵게 (실측 증상 회귀 가드)',
        (tester) async {
      await tester.pumpWidget(_wrap('좋아, 이제 *어떻게 풀지* 계획을 세워보자.'));

      await tester.enterText(find.byType(TextField), '문제를 읽었어요');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // 실측 증상 그대로의 별표 평문 버블은 더 이상 없다.
      expect(find.text('좋아, 이제 *어떻게 풀지* 계획을 세워보자.'), findsNothing);
      // 별표가 제거된 본문이 한 버블로 보인다.
      expect(find.text('좋아, 이제 어떻게 풀지 계획을 세워보자.'), findsOneWidget);
      // 강조 구간("어떻게 풀지")만 굵게 — 앞뒤 조각은 기본 굵기.
      final spans = _collectSpans(tester, '좋아, 이제 어떻게 풀지 계획을 세워보자.');
      expect(
        spans
            .where((s) => s.style?.fontWeight == FontWeight.w700)
            .map((s) => s.text),
        <String>['어떻게 풀지'],
      );
      expect(
        spans
            .where((s) => s.style?.fontWeight != FontWeight.w700)
            .map((s) => s.text),
        <String>['좋아, 이제 ', ' 계획을 세워보자.'],
      );
    });

    testWidgets('코치 버블: 비짝 별표(곱셈 기호 모양)는 원문 그대로 노출된다', (tester) async {
      await tester.pumpWidget(_wrap('3*4는 어떻게 계산할까?'));

      await tester.enterText(find.byType(TextField), '곱셈이 헷갈려요');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // 안전 폴백 — 강조로 오인하지 않고 별표 포함 원문 그대로.
      expect(find.text('3*4는 어떻게 계산할까?'), findsOneWidget);
    });

    testWidgets('학생 버블: 별표 원문 유지 — 곱셈 기호가 절대 강조로 해석되지 않는다',
        (tester) async {
      await tester.pumpWidget(_wrap('식을 어떻게 세웠는지 말해 줄래?'));

      // 변별력: '3*4*5'가 강조 파서를 타면 "4"가 굵어지며 별표가 사라져
      // 아래 원문 일치 단언이 반드시 실패한다(우연 통과 불가).
      await tester.enterText(find.byType(TextField), '3*4*5를 계산했어요');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // 학생 버블은 별표 포함 원문 그대로(입력 필드는 전송 시 비워지므로 버블 1개).
      expect(find.text('3*4*5를 계산했어요'), findsOneWidget);
      // 별표가 벗겨진 변형본은 어디에도 없다.
      expect(find.text('345를 계산했어요'), findsNothing);
    });
  });
}
