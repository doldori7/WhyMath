// 서버 최소버전 계약(OPS-17) 미달 판정의 **단일 좌석** — 426 Upgrade Required (OPS-35).
//
// 이전에는 diagnosis_controller만 426을 전용 문구로 분기하고 나머지 6개 컨트롤러(chat·auth·
// ocr·onboarding·me_tab·account_security)는 generic catch라, 임계(`min_app_version`) 상향 시
// 차단이 "일반 실패" 문구로 위장됐다 — 단일 실패 문구가 원인을 덮는 2026-07-20 인증 누락
// 사고와 같은 구조(`service_operations_gap_review_r2.md` §2 G2).
//
// 설계 판단(acceptance ③의 문자 vs 계약): acceptance는 판정 좌석으로 Dio *인터셉터*를
// 지목했지만, 인터셉터는 각 컨트롤러가 자기 상태에 담는 **고정 문구 문자열을 바꿔줄 수
// 없다**(컨트롤러 catch가 하드코딩 문구를 대입하는 구조) — 인터셉터만으로는 "앱 전역이
// 같은 문구"라는 계약이 성립하지 않고, 전역 배너 방식은 acceptance ⑥이 동결한 UI 작업이다.
// 따라서 판정을 이 파일의 [updateRequiredMessageOf] 1곳에 두고, 각 컨트롤러의 catch는
// `error: updateRequiredMessageOf(e) ?? '<기존 graceful 문구>'` 한 줄로 소비한다 — 426
// 검사 로직은 앱 어디에도 복제되지 않는다(계약 충족·문자 이탈은 태스크 증적에 기록).
import 'package:dio/dio.dart';

/// 서버 최소버전 계약 미달 사유코드 — `app.py _service_metrics_middleware`가 돌려주는
/// `426 Upgrade Required`. 401(미인증)/404/422/503과 구분되는 전용 코드라 이 매핑은
/// 수학·판정 로직이 아니라 HTTP 사유코드 → 문구 변환이다(클라 경계 안·수학 로직 0).
const int updateRequiredStatusCode = 426;

/// 앱 전역 공통 업데이트 안내 문구 — 서버 426 응답의 detail과 같은 내용(계약 정합).
/// 문구를 바꾸려면 서버(`app.py`)와 이 상수를 함께 바꾼다.
const String updateRequiredMessage = '앱을 최신 버전으로 업데이트해주세요.';

/// [error]가 서버 최소버전 계약 미달(426)이면 전용 안내 문구를, 아니면 null을 돌려준다.
///
/// 모든 컨트롤러의 catch에서 폴백 문구 앞에 끼운다:
/// `error: updateRequiredMessageOf(e) ?? '문제를 불러오지 못했어요. …'`.
/// 판정(426 검사)은 여기 한 곳이고, 소비 지점은 문구 대입 자리뿐이다.
String? updateRequiredMessageOf(Object error) =>
    error is DioException && error.response?.statusCode == updateRequiredStatusCode
    ? updateRequiredMessage
    : null;
