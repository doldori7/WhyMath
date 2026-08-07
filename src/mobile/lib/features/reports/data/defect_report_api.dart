// 학생 결함 신고 API 클라이언트 — `POST /v1/reports/defects` 호출 (RPT-01).
//
// 배경(docs/architecture/service_operations_gap_review.md §3 D1): 학생이 문항·AI응답·수식
// 오류를 알릴 경로가 앱에 전혀 없었다. 이 태스크는 REC-01/NLP-01과 달리 *상류 원인이 없고*
// 클라 버튼이 유일한 생산자다 — 버튼이 없으면 이 채널은 존재하지 않는 것과 같다.
//
// 경계(CLAUDE.md): 요청을 보내고 적재 성공 여부만 받는다. 서버는 append-only로 저장하며
// user_id·자유서술을 보유하지 않는다(설계 계약 — acceptance). 클라도 그 계약을 그대로
// 따른다 — 카테고리 6종 + 대상 참조(problem_id)만 싣고, 텍스트 입력은 v0 범위 밖(동결)이다.
//
// 기존 API 클래스 패턴(`problems_api.dart`·`coach_api.dart`)을 그대로 재사용한다 — retrofit
// 코드젠 대신 명시적 메서드, 공유 [dioProvider] 주입.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';

/// 학생 결함 신고 카테고리 — 정확히 6종(백엔드 enum과 문자열 일치, 한글).
///
/// v0는 이 6종 중 택1만 허용한다(자유서술 없음 — RPT-01 acceptance "범위 밖 동결").
enum DefectReportCategory {
  contentError('콘텐츠오류'),
  aiResponseError('AI응답오류'),
  formulaError('수식오류'),
  suspectedWrongAnswer('오답의심'),
  uiIssue('UI문제'),
  other('기타');

  const DefectReportCategory(this.label);

  /// 요청 바디 `category` 값 그대로 쓰이는 백엔드 enum 문자열(한글).
  final String label;
}

/// 결함 신고 엔드포인트 호출 래퍼 — Dio로 직렬화를 담당(응답은 단순 확인이라 역직렬화 불필요).
class DefectReportApi {
  DefectReportApi(this._dio);

  final Dio _dio;

  /// `POST /v1/reports/defects` — 카테고리 + (있으면) 대상 문제 PK만 적재 요청한다.
  ///
  /// [problemId]는 문제 화면·해당 문제로 진입한 코치 대화에서만 채워진다(자유 대화면 null —
  /// 서버가 대상 참조 없이도 적재). user_id는 서버가 저장하지 않으므로(설계) 요청 바디에도
  /// 신원 정보를 싣지 않는다 — 인증 헤더(Bearer)는 공유 Dio의 AuthInterceptor가 붙이지만
  /// 이 엔드포인트가 그것을 신고 레코드에 연결할지는 서버(L1) 몫이며 클라는 관여하지 않는다.
  Future<void> reportDefect({
    required DefectReportCategory category,
    String? problemId,
  }) async {
    await _dio.post<void>(
      '/v1/reports/defects',
      data: <String, dynamic>{
        'category': category.label,
        'problem_id': problemId,
      },
    );
  }
}

/// [DefectReportApi] provider — 공유 [dioProvider]를 주입받는다(기존 API provider와 동형).
final defectReportApiProvider = Provider<DefectReportApi>((ref) {
  return DefectReportApi(ref.watch(dioProvider));
});
