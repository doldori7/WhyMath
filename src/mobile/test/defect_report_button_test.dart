// DefectReportButton 위젯 테스트 — 버튼 탭→카테고리 선택→제출이 실제로 API 호출을
// 트리거하는지 확인한다(RPT-01 acceptance "Flutter 버튼 1개(유일한 생산자) → POST 1개").
//
// defectReportApiProvider를 fake로 override해 네트워크 없이 화면 동작을 확인한다
// (problem_screen_test의 fake-provider 패턴 답습). 자유서술 입력 필드가 없음(v0 범위 동결)도
// 함께 앵커한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/reports/data/defect_report_api.dart';
import 'package:korean_math_app/features/reports/presentation/defect_report_button.dart';

/// 호출을 기록만 하는 fake — 실제 네트워크 없이 트리거 여부·인자를 검증한다.
class _FakeDefectReportApi extends DefectReportApi {
  _FakeDefectReportApi() : super(Dio());

  int callCount = 0;
  DefectReportCategory? lastCategory;
  String? lastProblemId;

  @override
  Future<void> reportDefect({
    required DefectReportCategory category,
    String? problemId,
  }) async {
    callCount++;
    lastCategory = category;
    lastProblemId = problemId;
  }
}

/// 항상 실패하는 fake — 실패해도 학습 흐름(다이얼로그 닫힘)을 막지 않음을 확인한다.
class _FailingDefectReportApi extends DefectReportApi {
  _FailingDefectReportApi() : super(Dio());

  @override
  Future<void> reportDefect({
    required DefectReportCategory category,
    String? problemId,
  }) async {
    throw DioException(requestOptions: RequestOptions(path: '/x'));
  }
}

Widget _wrap(DefectReportApi api, {String? problemId}) {
  return ProviderScope(
    overrides: [defectReportApiProvider.overrideWithValue(api)],
    child: MaterialApp(
      home: Scaffold(
        appBar: AppBar(actions: [DefectReportButton(problemId: problemId)]),
      ),
    ),
  );
}

void main() {
  testWidgets('신고 버튼 탭→카테고리 선택→"신고하기"가 API를 1회 호출한다(problemId 동반)', (
    tester,
  ) async {
    final api = _FakeDefectReportApi();
    await tester.pumpWidget(_wrap(api, problemId: 'p1'));

    await tester.tap(find.byIcon(Icons.flag_outlined));
    await tester.pumpAndSettle();

    // 6종 카테고리 라디오가 모두 보인다(자유서술 입력 필드는 없다).
    expect(find.text('콘텐츠오류'), findsOneWidget);
    expect(find.text('AI응답오류'), findsOneWidget);
    expect(find.text('수식오류'), findsOneWidget);
    expect(find.text('오답의심'), findsOneWidget);
    expect(find.text('UI문제'), findsOneWidget);
    expect(find.text('기타'), findsOneWidget);
    expect(find.byType(TextField), findsNothing); // 자유서술 없음(v0 범위 동결).

    await tester.tap(find.text('수식오류'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '신고하기'));
    await tester.pumpAndSettle();

    expect(api.callCount, 1);
    expect(api.lastCategory, DefectReportCategory.formulaError);
    expect(api.lastProblemId, 'p1');
    // 성공 안내 스낵바(질책 표현 없는 톤).
    expect(find.textContaining('접수됐어요'), findsOneWidget);
  });

  testWidgets('problemId 없이(자유 대화) 신고해도 null로 호출된다', (tester) async {
    final api = _FakeDefectReportApi();
    await tester.pumpWidget(_wrap(api));

    await tester.tap(find.byIcon(Icons.flag_outlined));
    await tester.pumpAndSettle();
    // 기본 선택(콘텐츠오류)인 채로 바로 제출.
    await tester.tap(find.widgetWithText(FilledButton, '신고하기'));
    await tester.pumpAndSettle();

    expect(api.callCount, 1);
    expect(api.lastCategory, DefectReportCategory.contentError);
    expect(api.lastProblemId, isNull);
  });

  testWidgets('취소하면 API를 호출하지 않는다', (tester) async {
    final api = _FakeDefectReportApi();
    await tester.pumpWidget(_wrap(api));

    await tester.tap(find.byIcon(Icons.flag_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, '취소'));
    await tester.pumpAndSettle();

    expect(api.callCount, 0);
  });

  testWidgets('신고 실패해도 조용히 안내만 하고 앱은 계속 쓸 수 있다', (tester) async {
    await tester.pumpWidget(_wrap(_FailingDefectReportApi()));

    await tester.tap(find.byIcon(Icons.flag_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '신고하기'));
    await tester.pumpAndSettle();

    // 다이얼로그는 닫히고(학습 흐름 차단 없음) 실패 안내만 뜬다(질책 표현 없음).
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.textContaining('실패'), findsOneWidget);
  });
}
