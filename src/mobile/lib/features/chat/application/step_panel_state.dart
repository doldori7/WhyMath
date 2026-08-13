// 단계 패널 상태 — step_panel 장면 요소(SOL-02)의 점층 노출 스냅샷.
//
// 경계(CLAUDE.md): 순수 표현 상태다. 어떤 단계를 언제 공개할지는 서버(up_to 점층 공개)와
// 학생(펼치기 액션)이 정하고, 클라는 판단하지 않는다.
import 'package:freezed_annotation/freezed_annotation.dart';

import '../data/solution_path_models.dart';

part 'step_panel_state.freezed.dart';

/// step_panel 하나의 단계 노출 상태(solutionPathId 단위로 family 관리).
@freezed
abstract class StepPanelState with _$StepPanelState {
  const factory StepPanelState({
    /// 지금까지 펼친 단계 페이지(서버는 `upTo`까지만 내려준다 — 미펼침 단계 내용은
    /// 이 객체에 애초에 없다. SOL-02 ⑤ deferred 불변).
    required SolutionStepsPage page,

    /// 다음 단계 조회 중인지(버튼 로딩 표시 — 이미 펼친 단계는 그대로 보인다).
    @Default(false) bool isRevealingNext,

    /// 다음 단계 조회가 실패했는지(중립 재시도 문구 표시 — 정서 안전: 실패를
    /// 빨강/error 롤로 채점하지 않는다. 이미 펼친 단계는 유지).
    @Default(false) bool revealFailed,
  }) = _StepPanelState;
}
