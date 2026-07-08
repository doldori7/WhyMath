// 위젯 스모크 테스트 — 앱이 빌드·렌더되고 go_router 셸·ProviderScope가 정상 동작하는지 확인.
//
// 첫 진입은 온보딩([OnboardingScreen])이다(라우터 initialLocation=/onboarding). 온보딩
// 안내가 보이는지, "건너뛰기"로 학습 루프(진단→문제 `/problem`)에 도달하는지 정적 렌더만 확인한다
// (네트워크 호출 없음 — problemsApiProvider를 fake로 override해 CAT 조회를 결정론화한다).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/app.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';

/// 후보 없음을 돌려주는 fake — 문제 화면이 스피너에 갇히지 않고 안내로 정착한다.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi() : super(Dio());

  @override
  Future<NextProblemResponse> getNextProblem({
    bool prioritizeWeakConcepts = false,
  }) async =>
      const NextProblemResponse(problemId: null);

  @override
  Future<Problem> getProblem(String problemId) async =>
      throw UnimplementedError();

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async =>
      const <ConceptDiagnosisItem>[];
}

void main() {
  testWidgets('WhyMathApp이 온보딩으로 시작하고 학습 루프로 넘어간다', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          problemsApiProvider.overrideWithValue(_FakeProblemsApi()),
        ],
        child: const WhyMathApp(),
      ),
    );
    await tester.pumpAndSettle();

    // 첫 진입은 온보딩 — 메타인지 철학 안내(첫 페이지 제목)가 보인다.
    expect(find.text('답이 아닌, 이유를 묻습니다'), findsOneWidget);

    // "건너뛰기"로 학습 루프(문제 화면)에 진입한다. 추천 후보가 없으면 코치 대화 안내가 보인다.
    await tester.tap(find.text('건너뛰기'));
    await tester.pumpAndSettle();

    expect(find.text('오늘의 문제'), findsOneWidget);
    expect(find.textContaining('추천할 문제가 없어요'), findsOneWidget);
  });
}
