// MathliveInputScreen 화면 계약 위젯 테스트 (MOB-03)
//
// WebView(플랫폼 뷰)는 헤드리스 flutter test에서 렌더 불가 — 화면의 @visibleForTesting
// inputBuilder 시임으로 fake 입력 위젯을 주입해 *화면 계약*만 검증한다:
// ① pop(latex) 반환 계약(완료 = trim된 LaTeX, 취소 = null) ② 완료 버튼 활성화 판정
// ③ 입력 영역이 Expanded(잔여 전체 높이)로 배치됨 — MOB-03 키보드 잘림 재발 방지 동결
//   (고정 높이 스트립이면 MathLive 가상 키보드가 필드를 덮고 상단 행이 잘린다 — 실기기 실측).
// 실제 WebView 내부 렌더·키보드 도킹은 실기기 확인(태스크 notes 절차) 몫이다.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/presentation/mathlive_input_screen.dart';

/// fake 입력 자리 위젯 key — Expanded 배치 단언용.
const Key _fakeInputKey = Key('fake-math-input');

/// 화면을 push로 띄우고 pop 결과를 받는 하네스.
///
/// [emitRef]에 화면의 onChanged 콜백을 담아 테스트가 웹 입력을 흉내 낼 수 있게 한다.
class _Harness extends StatefulWidget {
  const _Harness({required this.onResult, required this.emitRef});

  final void Function(String? result) onResult;
  final List<ValueChanged<String>> emitRef;

  @override
  State<_Harness> createState() => _HarnessState();
}

class _HarnessState extends State<_Harness> {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: ElevatedButton(
        onPressed: () async {
          final String? result = await Navigator.of(context).push<String>(
            MaterialPageRoute<String>(
              builder: (_) => MathliveInputScreen(
                inputBuilder: (ValueChanged<String> onChanged) {
                  widget.emitRef
                    ..clear()
                    ..add(onChanged);
                  return const SizedBox.expand(key: _fakeInputKey);
                },
              ),
            ),
          );
          widget.onResult(result);
        },
        child: const Text('열기'),
      ),
    );
  }
}

/// 화면을 띄우고 (emit 콜백, 결과 컨테이너)를 돌려준다.
Future<List<ValueChanged<String>>> _openScreen(
  WidgetTester tester,
  void Function(String?) onResult,
) async {
  final List<ValueChanged<String>> emitRef = <ValueChanged<String>>[];
  await tester.pumpWidget(
    MaterialApp(home: _Harness(onResult: onResult, emitRef: emitRef)),
  );
  await tester.tap(find.text('열기'));
  await tester.pumpAndSettle();
  return emitRef;
}

/// '완료' FilledButton을 찾는다.
Finder get _submitButton => find.widgetWithText(FilledButton, '완료');

/// 화면에 실제로 그려진 모든 텍스트(Text·SelectableText)의 문자열을 모은다.
///
/// MATH-05 누출 동결용 — "백슬래시 매크로가 *어디에도* 안 보인다"를 화면 단위로 단언하려면
/// 특정 위젯 하나가 아니라 렌더된 텍스트 전량을 봐야 한다.
List<String> _renderedTexts(WidgetTester tester) {
  final List<String> out = <String>[];
  for (final Text w in tester.widgetList<Text>(find.byType(Text))) {
    if (w.data != null) {
      out.add(w.data!);
    }
  }
  for (final SelectableText w
      in tester.widgetList<SelectableText>(find.byType(SelectableText))) {
    if (w.data != null) {
      out.add(w.data!);
    }
  }
  return out;
}

void main() {
  group('MathliveInputScreen 화면 계약', () {
    testWidgets('타이틀·안내문이 렌더되고 완료는 초기 비활성', (WidgetTester tester) async {
      await _openScreen(tester, (_) {});

      expect(find.text('수식으로 풀이 입력'), findsOneWidget);
      expect(find.textContaining('풀이 수식을 입력해 주세요'), findsOneWidget);
      expect(
        tester.widget<FilledButton>(_submitButton).onPressed,
        isNull,
        reason: '빈 입력은 전송 무의미 — 완료 비활성',
      );
    });

    testWidgets('입력 영역은 Expanded(잔여 전체 높이) 배치다 — 키보드 잘림 재발 방지 동결',
        (WidgetTester tester) async {
      await _openScreen(tester, (_) {});

      // MOB-03 실기기 실측: MathLive 가상 키보드는 WebView 뷰포트 하단에 도킹하므로
      // 고정 높이(예: 140px) 스트립이면 키보드(약 300 CSS px)가 잘린다. Expanded 동결.
      expect(
        find.ancestor(
          of: find.byKey(_fakeInputKey),
          matching: find.byType(Expanded),
        ),
        findsOneWidget,
      );
    });

    testWidgets('LaTeX 입력 → 완료 활성 → pop이 trim된 LaTeX를 반환한다',
        (WidgetTester tester) async {
      String? popped = 'sentinel';
      final List<ValueChanged<String>> emit =
          await _openScreen(tester, (String? r) => popped = r);

      emit.single('  x^2 + 1  ');
      await tester.pump();

      expect(tester.widget<FilledButton>(_submitButton).onPressed, isNotNull);
      // 미리보기는 *평문 표기*로 그린다(MATH-05) — 이 입력엔 매크로가 없어 trim만 된 모습.
      expect(find.text('x^2 + 1'), findsOneWidget);

      await tester.tap(_submitButton);
      await tester.pumpAndSettle();

      expect(popped, 'x^2 + 1',
          reason: 'pop 반환 계약: trim된 LaTeX(채팅이 sendSolution으로 전송)');
    });

    testWidgets('미리보기는 원문 LaTeX 매크로를 노출하지 않고 평문 표기로 그린다 (MATH-05)',
        (WidgetTester tester) async {
      String? popped = 'sentinel';
      final List<ValueChanged<String>> emit =
          await _openScreen(tester, (String? r) => popped = r);

      emit.single(r'\frac{1}{2}');
      await tester.pump();

      // ① 존재 단언 — 변환된 평문 표기가 실제로 그려진다(화면이 아무것도 안 그려서
      //    "매크로 없음"이 통과하는 위장을 막는다).
      expect(find.text('((1)/(2))'), findsOneWidget);
      // ② 부재 단언 — 렌더된 텍스트 어디에도 백슬래시 매크로가 없다(화면 단위 계약).
      expect(
        _renderedTexts(tester).where((String t) => t.contains(r'\')),
        isEmpty,
        reason: '학생 대면 표면에 LaTeX 원문 노출 금지(MATH-05)',
      );

      // ③ 데이터 흐름은 원문 그대로 — pop 반환값은 변환되지 않는다(이중 변환 방지:
      //    chat_controller.sendMathliveLatex가 자기 쪽에서 변환한다).
      await tester.tap(_submitButton);
      await tester.pumpAndSettle();
      expect(popped, r'\frac{1}{2}',
          reason: '표시만 변환하고 pop 계약(원문 LaTeX)은 불변이어야 한다');
    });

    testWidgets('공백뿐인 입력은 완료 비활성 유지', (WidgetTester tester) async {
      final List<ValueChanged<String>> emit = await _openScreen(tester, (_) {});

      emit.single('   ');
      await tester.pump();

      expect(tester.widget<FilledButton>(_submitButton).onPressed, isNull);
    });

    testWidgets('취소(X)는 null을 반환한다 — 채팅 유지', (WidgetTester tester) async {
      String? popped = 'sentinel';
      bool completed = false;
      await _openScreen(tester, (String? r) {
        popped = r;
        completed = true;
      });

      await tester.tap(find.byTooltip('취소'));
      await tester.pumpAndSettle();

      expect(completed, isTrue);
      expect(popped, isNull);
    });

    testWidgets('정서 안전: 부정 표현·정오 강조 문구가 없다', (WidgetTester tester) async {
      await _openScreen(tester, (_) {});

      // 절대 금기(CLAUDE.md): "틀렸다"류 부정 피드백·정오 강조 문구 금지.
      expect(find.textContaining('틀'), findsNothing);
      expect(find.textContaining('오답'), findsNothing);
    });
  });
}
