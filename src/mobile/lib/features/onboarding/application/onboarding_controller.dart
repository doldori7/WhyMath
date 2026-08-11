// 온보딩 컨트롤러 — 폼 입력 수집·PATCH 전송·graceful 처리. S1-c.
//
// 경계(CLAUDE.md): 자동 커리큘럼 정렬 *엔진*은 L1+L6 책임이다. 이 컨트롤러(L5)는 온보딩
// 입력을 *수집*해 `StudentProfile`의 원천이 되는 프로필 필드로 *전달*만 한다 — 정렬 로직·
// 미성년 판정(`is_minor`)·화이트리스트 검증은 서버가 한다. `AuthController`(@riverpod) 패턴을
// 따르고, 부수효과는 [UserApi.patchMe] 호출 하나뿐(나머지는 순수 상태 전이)다.
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/update_required.dart';
import '../data/user_api.dart';
import 'onboarding_state.dart';

part 'onboarding_controller.g.dart';

/// 온보딩 폼 상태를 관리하는 Riverpod Notifier.
@riverpod
class OnboardingController extends _$OnboardingController {
  @override
  OnboardingState build() => const OnboardingState();

  /// 목표 등급(1~9)을 설정한다(null이면 미입력으로 되돌린다).
  void setTargetGrade(int? grade) {
    state = state.copyWith(targetGrade: grade);
  }

  /// 목표 표준점수를 설정한다(null이면 미입력).
  void setTargetScore(int? score) {
    state = state.copyWith(targetScore: score);
  }

  /// 목표 시험일을 설정한다(null이면 미입력).
  void setTargetExamDate(DateTime? date) {
    state = state.copyWith(targetExamDate: date);
  }

  /// 출생 연도를 설정한다(null이면 미입력).
  void setBirthYear(int? year) {
    state = state.copyWith(birthYear: year);
  }

  /// 입력을 PATCH로 전송한다 — 채워진 필드만 부분 수정, 실패해도 온보딩을 막지 않는다.
  ///
  /// 흐름: ① 빈 값을 제외한 본문 조립 → ② 본문이 비면(전부 미입력) 전송 없이 완료 처리
  /// (선택 입력·건너뛰기와 동치) → ③ 전송중 표시 → ④ `UserApi.patchMe` → ⑤ 성공/실패 모두
  /// `isSubmitted=true`로 온보딩을 진행시킨다. 403(미성년 미동의)·네트워크 실패는 삼켜
  /// 에러 메시지만 남긴다(앱은 죽지 않고 채팅으로 넘어간다·가용성).
  Future<void> submit() async {
    if (state.isSubmitting) {
      return; // 전송 중 재진입 방지.
    }
    final body = _buildBody();
    if (body.isEmpty) {
      // 채워진 필드가 없으면 보낼 게 없다 — 온보딩은 그대로 진행한다(선택 입력).
      state = state.copyWith(isSubmitted: true, error: null);
      return;
    }
    state = state.copyWith(isSubmitting: true, error: null);
    try {
      await ref.read(userApiProvider).patchMe(body);
      state = state.copyWith(isSubmitting: false, isSubmitted: true);
    } catch (e) {
      // graceful — 403(미성년 미동의)·네트워크 실패 모두 온보딩을 막지 않는다.
      // 426(최소버전 미달)만 전용 문구(판정 좌석 = core/update_required 단일·OPS-35).
      state = state.copyWith(
        isSubmitting: false,
        isSubmitted: true,
        error: updateRequiredMessageOf(e) ?? '입력을 저장하지 못했어요. 나중에 설정에서 다시 입력할 수 있어요.',
      );
    }
  }

  /// 현재 폼 상태에서 *채워진 필드만* 담은 PATCH 본문을 조립한다(순수·부수효과 없음).
  ///
  /// 미입력(null) 필드는 제외한다(부분 수정). 목표 시험일은 백엔드 `date` 타입에 맞춰
  /// `YYYY-MM-DD` 문자열로 직렬화한다(시각·타임존 없이 날짜만).
  Map<String, dynamic> _buildBody() {
    final body = <String, dynamic>{};
    final grade = state.targetGrade;
    if (grade != null) {
      body['target_grade'] = grade;
    }
    final score = state.targetScore;
    if (score != null) {
      body['target_score'] = score;
    }
    final examDate = state.targetExamDate;
    if (examDate != null) {
      body['target_exam_date'] = _formatDate(examDate);
    }
    final birthYear = state.birthYear;
    if (birthYear != null) {
      body['birth_year'] = birthYear;
    }
    return body;
  }

  /// [DateTime]을 백엔드 `date`(YYYY-MM-DD) 문자열로 직렬화한다(로컬 날짜 필드만 사용).
  static String _formatDate(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }
}
