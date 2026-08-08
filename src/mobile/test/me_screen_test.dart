// MeScreen 위젯 테스트 — 학습 경로·진단 결과 실 API 렌더 + 정직 신호(has_cycle·빈 경로·401)
// 노출 검증 (PATH-05).
//
// problemsApiProvider를 fake로 override해 네트워크 없이 화면 동작을 확인한다
// (problem_screen_test 답습). 설정 섹션은 여전히 "준비 중"이라 그대로 남아 있는지도 확인한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/profile/presentation/me_screen.dart';

/// 미리 짠 응답(또는 지정한 상태코드로 throw)을 돌려주는 fake.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi({
    this.diagnoses = const <ConceptDiagnosisItem>[],
    this.diagnosisStatusCode,
    this.learningPath,
    this.learningPathStatusCode,
  }) : super(Dio());

  final List<ConceptDiagnosisItem> diagnoses;
  final int? diagnosisStatusCode;
  final LearningPath? learningPath;
  final int? learningPathStatusCode;

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async {
    if (diagnosisStatusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
          statusCode: diagnosisStatusCode,
        ),
      );
    }
    return diagnoses;
  }

  @override
  Future<LearningPath> getLearningPath(String conceptId) async {
    if (learningPathStatusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/weak-concepts/$conceptId/learning-path'),
        response: Response(
          requestOptions:
              RequestOptions(path: '/v1/me/weak-concepts/$conceptId/learning-path'),
          statusCode: learningPathStatusCode,
        ),
      );
    }
    return learningPath!;
  }
}

ConceptDiagnosisItem _diag({String conceptId = 'c1', String? name = '함수의 극한'}) =>
    ConceptDiagnosisItem(
      conceptId: conceptId,
      conceptName: name,
      coaching: const DiagnosisCoaching(
        focus: 'foundation',
        rationale: '기초 개념을 다시 확인해볼까요?',
        prompt: '이 개념을 어떻게 이해하고 있나요?',
      ),
    );

Widget _wrap(ProblemsApi api) {
  return ProviderScope(
    overrides: [problemsApiProvider.overrideWithValue(api)],
    child: const MaterialApp(home: MeScreen()),
  );
}

void main() {
  testWidgets('성공: 진단 결과·학습 경로 데이터를 그대로 렌더한다', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag(conceptId: 'weakest', name: '함수의 극한')],
      learningPath: const LearningPath(
        steps: <LearningStep>[
          LearningStep(position: 0, conceptId: 'p0', conceptName: '함수의 정의', depth: 1),
          LearningStep(position: 1, conceptId: 'p1', conceptName: '극한의 성질', depth: 1),
        ],
        orderingBasis: 'topological',
        orderingEdgeCount: 1,
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 진단 결과 섹션.
    expect(find.text('함수의 극한'), findsOneWidget);
    expect(find.text('기초 개념을 다시 확인해볼까요?'), findsOneWidget);
    // 학습 경로 섹션 — 순서대로 두 단계.
    expect(find.text('함수의 정의'), findsOneWidget);
    expect(find.text('극한의 성질'), findsOneWidget);
    // "준비 중" placeholder는 설정 섹션에만 남아 있어야 한다(1건).
    expect(find.text('준비 중'), findsOneWidget);
  });

  testWidgets('빈 학습 경로(steps==0)는 정상 안내로 표시한다(에러 문구 아님)', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('복습할 막힌 선수개념이 없어요'), findsOneWidget);
    expect(find.textContaining('불러오지 못했'), findsNothing);
  });

  testWidgets('진단 데이터 자체가 없으면 두 섹션 모두 "정상, 데이터 없음" 안내를 보인다', (tester) async {
    final api = _FakeProblemsApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('아직 진단 데이터가 없어요'), findsNWidgets(2));
  });

  testWidgets('has_cycle=true는 순환 경고를 그대로 노출한다(삼키지 않음)', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(
        steps: <LearningStep>[
          LearningStep(position: 0, conceptId: 'p0', conceptName: '개념 A', depth: 1),
        ],
        hasCycle: true,
        orderingBasis: 'tiebreak_only',
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('순환 구조가 감지'), findsOneWidget);
    // 순환이 있어도 단계 자체는 계속 보인다(잔여로라도 정직하게 보여줌).
    expect(find.text('개념 A'), findsOneWidget);
  });

  testWidgets('401(미인증)은 로그인 필요 안내로 명확히 구분한다(일반 오류 문구 아님)', (tester) async {
    final api = _FakeProblemsApi(diagnosisStatusCode: 401);
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('로그인이 필요해요.'), findsNWidgets(2)); // 학습 경로·진단 결과 둘 다.
    expect(find.textContaining('불러오지 못했'), findsNothing);
    expect(find.textContaining('오류가 발생'), findsNothing);
  });

  testWidgets('학습 경로만 일반 실패(401 외)면 재시도 버튼과 함께 error로 표시한다', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPathStatusCode: 500,
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('학습 경로를 불러오지 못했어요'), findsOneWidget);
    expect(find.widgetWithText(TextButton, '다시 시도'), findsOneWidget);
    // 진단 결과 섹션은 정상 렌더돼야 한다(섹션 독립성).
    expect(find.text('함수의 극한'), findsOneWidget);
  });
}
