// step_panel 점층 노출 위젯 테스트 (SOL-02 acceptance ⑤) — deferred 불변·점수 노출 0·
// 정서 안전 폴백을 위젯 수준에서 동결한다.
//
// 핵심 동결: **펼치기 전 단계 내용(정답) 문자열은 위젯 트리에 없다.** 서버 측 점층 공개
// (up_to까지만 응답)를 가짜 API로 흉내내, "학생이 펼친 만큼만 요청·보유"를 함께 증명한다.
// 라이브 네트워크 없음 — solutionPathApiProvider override(chat_scene_test 패턴).
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/chat/data/scene_models.dart';
import 'package:korean_math_app/features/chat/data/solution_path_api.dart';
import 'package:korean_math_app/features/chat/data/solution_path_models.dart';
import 'package:korean_math_app/features/chat/presentation/scene_renderer.dart';

/// 가짜 SolutionPathApi — 서버 측 점층 공개를 흉내낸다(요청 upTo까지만 슬라이스해 응답).
class _FakeSolutionPathApi extends SolutionPathApi {
  _FakeSolutionPathApi({required this.allSteps}) : super(Dio());

  /// 서버에 존재하는 전체 단계(테스트 픽스처 — 클라에는 upTo 이하만 내려간다).
  final List<SolutionStep> allSteps;

  /// 실패를 유발할 upTo 값 집합(네트워크 오류 시뮬레이션).
  final Set<int> failingUpTos = <int>{};

  /// 실제로 요청받은 up_to 기록 — "펼친 만큼만 요청했다"의 증거.
  final List<int> requestedUpTos = <int>[];

  @override
  Future<SolutionStepsPage> fetchSteps(
    String solutionPathId, {
    required int upTo,
  }) async {
    requestedUpTos.add(upTo);
    if (failingUpTos.contains(upTo)) {
      throw DioException(
        requestOptions:
            RequestOptions(path: '/v1/solution-paths/$solutionPathId/steps'),
        error: '네트워크 실패(테스트)',
      );
    }
    return SolutionStepsPage(
      steps: allSteps.where((s) => s.stepOrder <= upTo).toList(),
      total: allSteps.length,
      upTo: upTo,
    );
  }
}

/// 3단계 풀이 픽스처 — 2·3단계 내용이 "펼치기 전엔 없어야 할 정답 문자열" 역할을 한다.
_FakeSolutionPathApi _threeStepApi() => _FakeSolutionPathApi(
      allSteps: const [
        SolutionStep(stepOrder: 1, content: '양변에서 4를 빼면 2x = 6'),
        SolutionStep(stepOrder: 2, content: '양변을 2로 나누면 x = 3'),
        SolutionStep(stepOrder: 3, content: '검산하면 2*3 + 4 = 10'),
      ],
    );

/// step_panel 요소 하나를 담은 장면을 SceneRenderer로 감싼다(실서빙 경로와 동일 진입).
Widget _wrap(_FakeSolutionPathApi api, {String? solutionPathId = 'sp-1'}) {
  return ProviderScope(
    overrides: [solutionPathApiProvider.overrideWithValue(api)],
    child: MaterialApp(
      home: Scaffold(
        body: SceneRenderer(
          scene: LearningScene(
            sceneId: 's1',
            conceptId: 'c1',
            layout: 'single',
            answerDeferralMaxLevel: 4,
            elements: [
              SceneElement(
                kind: 'step_panel',
                solutionPathId: solutionPathId,
                revealPolicy: 'deferred',
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('최초엔 1단계만 보이고 2·3단계 내용 문자열은 부재다(deferred 불변)', (tester) async {
    final api = _threeStepApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 펼친 1단계만 보인다.
    expect(find.textContaining('양변에서 4를 빼면'), findsOneWidget);
    // 펼치기 전 단계 내용·정답은 위젯 트리에 없다(acceptance ⑤ 핵심 동결).
    expect(find.textContaining('양변을 2로 나누면'), findsNothing);
    expect(find.textContaining('검산하면'), findsNothing);
    // 위치 정보(점수 아님)와 단일 점층 액션만 보인다.
    expect(find.text('단계 1/3'), findsOneWidget);
    expect(find.text('다음 단계 보기'), findsOneWidget);
    // 클라는 펼친 만큼만 요청했다 — 최초 up_to=1 한 번(미펼침 단계를 미리 가져오지 않음).
    expect(api.requestedUpTos, <int>[1]);
  });

  testWidgets('다음 단계 보기 탭 → 2단계만 추가로 보이고 3단계는 여전히 부재다', (tester) async {
    final api = _threeStepApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('다음 단계 보기'));
    await tester.pumpAndSettle();

    expect(find.textContaining('양변을 2로 나누면'), findsOneWidget);
    // 한 단계씩만 열린다 — 다음 단계는 아직 없다(일괄 노출 아님).
    expect(find.textContaining('검산하면'), findsNothing);
    expect(find.text('단계 2/3'), findsOneWidget);
    // 탭 1회 = up_to +1 재조회(서버 측 점층 공개).
    expect(api.requestedUpTos, <int>[1, 2]);
  });

  testWidgets('마지막 단계에 도달하면 점층 버튼이 사라진다(전체 일괄 노출 경로 부재)', (tester) async {
    final api = _threeStepApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('다음 단계 보기'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('다음 단계 보기'));
    await tester.pumpAndSettle();

    expect(find.textContaining('검산하면'), findsOneWidget);
    expect(find.text('단계 3/3'), findsOneWidget);
    // 더 펼칠 단계가 없으면 버튼이 없다 — 그 외 "모두 보기"류 일괄 노출 진입점도 없다.
    expect(find.text('다음 단계 보기'), findsNothing);
    expect(find.textContaining('모두 보기'), findsNothing);
    expect(find.textContaining('전체 보기'), findsNothing);
  });

  testWidgets('초기 조회 실패 → 중립 문구로 폴백하고 다시 시도로 복구한다(정서 안전)', (tester) async {
    final api = _threeStepApi()..failingUpTos.add(1);
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 실패는 채점이 아니라 중립 안내다 — 어떤 단계 내용도 없고 빨강/error 롤도 쓰지 않는다.
    expect(find.text('단계를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'), findsOneWidget);
    expect(find.textContaining('양변에서 4를 빼면'), findsNothing);

    api.failingUpTos.clear();
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    expect(find.textContaining('양변에서 4를 빼면'), findsOneWidget);
  });

  testWidgets('다음 단계 조회 실패 → 펼친 단계는 유지하고 중립 재시도 문구를 보인다', (tester) async {
    final api = _threeStepApi()..failingUpTos.add(2);
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('다음 단계 보기'));
    await tester.pumpAndSettle();

    // 이미 펼친 1단계는 그대로, 실패한 2단계는 여전히 부재(부분 공개 실패 없음).
    expect(find.textContaining('양변에서 4를 빼면'), findsOneWidget);
    expect(find.textContaining('양변을 2로 나누면'), findsNothing);
    expect(find.text('다음 단계를 불러오지 못했어요. 다시 시도해 주세요.'), findsOneWidget);

    // 같은 버튼으로 재시도하면 열린다.
    api.failingUpTos.clear();
    await tester.tap(find.text('다음 단계 보기'));
    await tester.pumpAndSettle();
    expect(find.textContaining('양변을 2로 나누면'), findsOneWidget);
  });

  testWidgets('단계 내용은 평문 표기로 변환해 보인다(원문 LaTeX 노출 금지·MATH-05)', (tester) async {
    final api = _FakeSolutionPathApi(
      allSteps: const [
        SolutionStep(stepOrder: 1, content: r'분수로 나타내면 \frac{6}{2} = 3'),
      ],
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 원문 LaTeX 제어어는 학생 표면에 없고, MATH-05 정본 평문 표기로 변환된다.
    expect(find.textContaining(r'\frac'), findsNothing);
    expect(find.textContaining('((6)/(2))'), findsOneWidget);
  });

  testWidgets('solutionPathId 없는 step_panel은 조용히 생략한다(계약 방어·빈 껍데기 금지)',
      (tester) async {
    // 서버는 solution_path 실재 시에만 step_panel을 방출한다(SOL-02 ③) — id 부재는 계약
    // 위반이므로 빈 카드를 그리지 않는다. ProviderScope 없는 기존 렌더 경로에서도 깨지지 않는다.
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SceneRenderer(
            scene: LearningScene(
              sceneId: 's1',
              conceptId: 'c1',
              layout: 'single',
              answerDeferralMaxLevel: 4,
              elements: [SceneElement(kind: 'step_panel', revealPolicy: 'deferred')],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('단계별로 살펴보기'), findsNothing);
    expect(find.text('다음 단계 보기'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
