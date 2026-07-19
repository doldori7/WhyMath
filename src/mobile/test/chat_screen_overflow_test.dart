// MOB-02 회귀 가드 — 키보드(IME) 표시 상태에서 채팅 화면 RenderFlex 오버플로 0.
//
// 실기기 실측(2026-07-19 M2007J20CG·flutter 콘솔): 키보드가 올라오면 body Column이
// "A RenderFlex overflowed by 125 pixels on the bottom"으로 넘쳤다(대화 모드 포함).
//
// 근본 원인: body Column의 비신축 자식(문제 배너·입력 영역)의 고정 높이 합이,
// resizeToAvoidBottomInset이 키보드만큼 줄인 body 가용 높이를 초과 —
// Expanded(메시지 리스트)는 0까지밖에 못 줄어들어 초과분이 그대로 오버플로가 된다.
//
// 변별력 근거(이 테스트는 수정 *전* 코드에서 실패한다 — 산술 근거):
//   - 창 411×756 + viewInsets.bottom 300 → body 가용 높이
//     = 756 − 76(AppBar 56 + 슬로건 부제 20) − 300 = 380px
//   - 수정 전 배너는 상한이 없다: 아래 긴 발문(≈340자 ≈ 13줄 × 20px ≈ 260px)
//     + 선택지 5개(≈80px) + 헤더·패딩(≈50px) ≈ 390px
//   - 대화 모드: 배너 ≈390 + 입력 영역 ≈112 = 502 > 380 → ≈122px 오버플로(실측 125px와
//     같은 자릿수). 풀이 모드: 배너 ≈390 + 입력 영역 ≈274(토글 48+단계영역 162+버튼 48
//     +패딩 16) = 664 > 380 → 더 크게 넘친다.
//   - 수정 후: 배너 = body 30% 상한(114px)+내부 스크롤, 단계 영역 = min(162, body 25%=95)
//     → 비신축 합이 어느 모드에서도 380px 미만이라 예외 0.
//
// 전송(네트워크)은 하지 않는다 — 레이아웃만 검증하므로 CoachApi는 호출되면 즉시
// 실패하는 가드 fake로 둔다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/chat/presentation/chat_screen.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

/// 이 테스트는 전송을 하지 않는다 — 호출 자체가 테스트 결함이므로 즉시 실패시킨다.
class _UnusedCoachApi extends CoachApi {
  _UnusedCoachApi() : super(Dio());

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    throw StateError('오버플로 레이아웃 테스트는 네트워크 전송을 하지 않는다');
  }

  @override
  Future<CoachTurnResult> addTurn(
    String dialogueId,
    CoachRequest request,
  ) async {
    throw StateError('오버플로 레이아웃 테스트는 네트워크 전송을 하지 않는다');
  }
}

/// 실기기 시나리오 재현용 긴 발문 — 수정 전 배너는 상한이 없어 이 발문+선택지만으로
/// 키보드가 줄인 body 가용 높이(≈380px)를 사실상 다 차지한다(파일 머리 주석의 산술).
final String _longQuestion = List<String>.filled(
  6,
  '이차함수 f(x)=x²-4x+3의 그래프와 직선 y=k가 서로 다른 두 점에서 만나도록 하는 '
  '실수 k의 값의 범위를 구하시오.',
).join(' ');

/// 활성 문제(긴 발문+객관식 5지) — 배너를 최대로 키우는 현실적 최악 케이스.
final Problem _longProblem = Problem(
  problemId: 'p-mob02-overflow',
  sourceType: '자체생성',
  subject: '공통',
  subunit: '이차방정식과 이차함수',
  questionText: _longQuestion,
  choices: const <String>['k<-1', 'k=-1', '-1<k<3', 'k=3', 'k>3'],
);

/// 폰급 논리 크기(411×756·dpr 1.0)로 창을 잡고 IME 300px을 시뮬레이트한다.
///
/// tester.view.viewInsets는 MaterialApp의 MediaQuery로 흘러 들어가 Scaffold
/// (resizeToAvoidBottomInset 기본 true)가 body를 정확히 300px 줄인다 — 실기기에서
/// 키보드가 올라온 상태와 같은 레이아웃 경로다.
void _simulatePhoneWithKeyboard(WidgetTester tester) {
  tester.view.physicalSize = const Size(411, 756);
  tester.view.devicePixelRatio = 1.0;
  tester.view.viewInsets = const FakeViewPadding(bottom: 300);
  addTearDown(tester.view.reset);
}

Widget _app() {
  return ProviderScope(
    overrides: [
      coachApiProvider.overrideWithValue(_UnusedCoachApi()),
      activeProblemProvider.overrideWith((ref) => _longProblem),
    ],
    child: const MaterialApp(home: ChatScreen()),
  );
}

void main() {
  testWidgets('대화 모드 — 키보드 표시 + 긴 문제 배너에서 오버플로 예외 0', (tester) async {
    _simulatePhoneWithKeyboard(tester);
    await tester.pumpWidget(_app());

    // 첫 레이아웃부터 RenderFlex 오버플로 예외가 없어야 한다(수정 전엔 여기서 실패).
    expect(tester.takeException(), isNull);

    // 키보드 사용 시나리오 그대로 — 입력해도 예외가 없어야 한다.
    await tester.enterText(find.byType(TextField), '판별식부터 정리해 볼게요');
    await tester.pump();
    expect(tester.takeException(), isNull);

    // 배너는 접히지 않고 상한+내부 스크롤로 살아 있다(발문 접근 경로 유지).
    expect(find.textContaining('풀이 중인 문제'), findsOneWidget);
  });

  testWidgets('풀이 모드 — 단계 편집기·단계 추가 후에도 오버플로 예외 0', (tester) async {
    _simulatePhoneWithKeyboard(tester);
    await tester.pumpWidget(_app());

    // 풀이 단계 모드로 토글 — S3-05 편집기(초기 2필드)가 나타나는 순간부터 예외 0.
    await tester.tap(find.byIcon(Icons.format_list_numbered));
    await tester.pump();
    expect(tester.takeException(), isNull);

    // "단계 추가"를 여러 번 눌러도 — 단계 영역은 상한+내부 스크롤로 가둬져
    // 화면을 밀어내지 않는다(S3-05 UX 유지: 리스트·추가·N단계 제출 그대로).
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.text('단계 추가'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }
    expect(find.byType(TextField), findsNWidgets(5)); // 초기 2 + 추가 3.

    // 단계를 채워도(제출 라벨 실시간 갱신 경로) 예외가 없어야 한다.
    await tester.enterText(find.byType(TextField).at(0), '식을 표준형으로 정리한다');
    await tester.enterText(find.byType(TextField).at(1), '판별식 D를 계산한다');
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(find.text('2단계 제출'), findsOneWidget);
  });
}
