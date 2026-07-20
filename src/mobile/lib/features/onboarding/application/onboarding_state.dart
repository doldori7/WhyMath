// 온보딩 입력 폼 상태 — 학습 목표(목표 등급·점수·시험일·출생연도) + 전송/에러. S1-c.
//
// `AuthState`·`ChatState`(freezed) 패턴을 따른다. 화면 상태일 뿐 영속·전송 대상이 아니다
// (런타임 모델) — 서버 전송 계약은 PATCH 본문 dict(`UserApi.patchMe`)가 전담한다.
import 'package:freezed_annotation/freezed_annotation.dart';

part 'onboarding_state.freezed.dart';

/// 온보딩 폼 상태.
///
/// 모든 입력은 *선택*이라 폼 필드는 전부 nullable이다(미입력=null → PATCH 본문에서 제외).
///
/// - [targetGrade] : 목표 등급(1~9·수능 등급 척도, 백엔드 `target_grade`). 학년(school year)이
///   아니라 목표 *등급*이다 — 자가수정 화이트리스트(`users.py` `_SELF_EDITABLE`)의 필드다.
/// - [targetScore] : 목표 표준점수(≥0).
/// - [targetExamDate] : 목표 시험일. 전송 시 `YYYY-MM-DD`(백엔드 `date`)로 직렬화한다.
/// - [birthYear] : 출생 연도(연 단위·월일 미수집·미성년 개인정보 최소화). 서버가 이 값에서
///   `is_minor`를 파생하므로 클라가 `is_minor`를 직접 보내지 않는다.
/// - [isSubmitting] : PATCH 전송 중(중복 전송 방지·로딩 표시).
/// - [isSubmitted] : 전송이 끝났는가(성공·graceful 실패 모두 true — 온보딩은 계속 진행).
/// - [error] : 저장 실패 메시지(있으면 표시·null이면 없음). 실패해도 온보딩을 막지 않는다.
@freezed
abstract class OnboardingState with _$OnboardingState {
  const factory OnboardingState({
    int? targetGrade,
    int? targetScore,
    DateTime? targetExamDate,
    int? birthYear,
    @Default(false) bool isSubmitting,
    @Default(false) bool isSubmitted,
    String? error,
  }) = _OnboardingState;
}
