// 단계 패널 컨트롤러 — step_panel 장면 요소(SOL-02)의 단계 조회·점층 노출을 관장한다.
//
// 경계(CLAUDE.md): 수학·교수학 결정은 전부 서버가 내린다. 이 컨트롤러는 (1) 학생이 펼친
// 만큼만 `up_to`로 조회하고 (2) 받은 페이지를 상태로 옮길 뿐이다(표현≠의미).
//
// 교수학 경계(SOL-02 acceptance ⑤·협상 불가):
// - reveal_policy='deferred' 불변 — 최초 up_to=1, 학생이 "다음 단계"를 누를 때만 +1.
// - 전체 풀이 일괄 노출 금지 — 한 번에 전부 펼치는 경로는 여기에 없다(메서드 자체 부재).
// - 미펼침 단계 내용 미보유 — 서버가 up_to까지만 내려주므로, 클라 메모리에도 다음 단계
//   내용이 없다(클라 측 캐시·prefetch 없음).
import 'package:flutter/foundation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../data/solution_path_api.dart';
import 'step_panel_state.dart';

part 'step_panel_controller.g.dart';

/// 프레임워크 자동 재시도를 끈다 — 실패는 지수 백오프 속 로딩으로 숨기지 않고, 즉시 중립
/// 폴백(안내 문구 + 학생이 누르는 "다시 시도")으로 드러낸다(정서 안전·결정론적 동작).
Duration? _noRetry(int retryCount, Object error) => null;

/// step_panel 단계 노출을 관리하는 Riverpod Notifier(solutionPathId 단위 family).
@Riverpod(retry: _noRetry)
class StepPanelController extends _$StepPanelController {
  /// 최초 진입 — 1단계만 조회한다(up_to=1·deferred 시작점).
  @override
  Future<StepPanelState> build(String solutionPathId) async {
    final page = await ref
        .watch(solutionPathApiProvider)
        .fetchSteps(solutionPathId, upTo: 1);
    return StepPanelState(page: page);
  }

  /// "다음 단계 보기" — 펼친 단계 수를 +1해 서버에 재조회한다(서버 측 점층 공개).
  ///
  /// 실패해도 이미 펼친 단계는 유지하고 중립 재시도 문구만 올린다(정서 안전 — 앱이 죽거나
  /// 빨강으로 채점하지 않는다). 침묵 실패 금지: 예외 타입명을 로그에 남긴다.
  Future<void> revealNext() async {
    final current = state.value;
    // 중복 탭·마지막 단계 도달 시 아무 것도 하지 않는다(조용한 무시가 아니라 UI 상
    // 버튼이 비활성/미표시라 도달 자체가 예외 흐름).
    if (current == null || current.isRevealingNext) {
      return;
    }
    if (current.page.upTo >= current.page.total) {
      return;
    }
    state = AsyncData(
      current.copyWith(isRevealingNext: true, revealFailed: false),
    );
    try {
      final page = await ref
          .read(solutionPathApiProvider)
          .fetchSteps(solutionPathId, upTo: current.page.upTo + 1);
      state = AsyncData(StepPanelState(page: page));
    } catch (e) {
      debugPrint('다음 단계 조회 실패(${e.runtimeType}) — 펼친 단계는 유지하고 재시도를 열어 둔다.');
      state = AsyncData(
        current.copyWith(isRevealingNext: false, revealFailed: true),
      );
    }
  }
}
