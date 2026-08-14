// SceneRenderer — LearningScene 명세를 위젯 트리로 렌더하는 *레지스트리*(kind→위젯).
//
// 경계(CLAUDE.md·슬라이스 89 표현≠의미): 이 위젯은 **dumb**다 — 수학 로직 0, 검증된 명세를
// 받아 위젯으로 그리기만 한다. 같은 `LearningScene`이 Flutter·웹·PDF에서 각자 렌더된다.
//
// 답 미루기·낙인 금지(절대 금기): `misconception_probe`는 정답·수정·오개념 id를 *그리지 않고*
// 개입 패턴별 부드러운 *사고 유도* cue만 보인다. `socratic_prompt`는 정본 유도 질문만.
//
// 정직(범위): 시각화는 실 WebView가 아니라 caption/type *seed*다(05a §6 — D3/Desmos/three.js
// WebView·postMessage 연동은 후속). layout(two_panel·tabbed) 전용 렌더도 후속 — seed는 세로 스택.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/spacing.dart';
import '../application/step_panel_controller.dart';
import '../application/step_panel_state.dart';
import '../data/scene_models.dart';
import '../domain/latex_to_plain.dart';
import 'graphing_calculator_webview.dart';

/// `LearningScene`을 받아 요소들을 세로로 렌더하는 레지스트리 위젯.
///
/// `scene.elements`가 비면 [SizedBox.shrink]를 반환한다(빈 카드 없음). 미지 `kind`는 조용히
/// 생략한다(전방호환 — 백엔드가 새 kind를 추가해도 클라가 깨지지 않음).
class SceneRenderer extends StatelessWidget {
  /// 렌더할 학습 장면 명세.
  const SceneRenderer({required this.scene, super.key});

  /// 백엔드가 검증해 내려준 장면 명세.
  final LearningScene scene;

  /// 실 WebView(D3.js/Plotly/Desmos·three.js)로 렌더하는 `Visualization.type` 집합.
  ///
  /// `data/render_contract.json`의 `renderers`에서 `interactive: true`인 3개 키(즉
  /// `animation_prerendered` 제외)와 *일치해야 한다*(invariant ⑩ 렌더 선택 단일 진실원).
  /// 결선 방식(MOB-14·2026-08-10): 런타임에 JSON을 읽지 않는다 — 이 위젯은 단순 kind 분기라
  /// 프로덕션 빌드 메서드에 파일 I/O를 넣는 게 과공학이다. 대신 이 상수를 `@visibleForTesting`로
  /// 노출해 `scene_render_contract_test.dart`가 *테스트 시점*에 계약 파일과 대조·동결한다
  /// (`segmentation_contract_test.dart`가 확립한 "런타임 번들링이 아니라 테스트 시점 교차검증"
  /// 관례를 답습).
  @visibleForTesting
  static const Set<String> webViewTypes = {
    'interactive_graph_2d',
    'interactive_surface_3d',
    'simulation_probabilistic',
  };

  @override
  Widget build(BuildContext context) {
    if (scene.elements.isEmpty) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final children = <Widget>[];

    final topic = scene.topicLabel;
    if (topic != null && topic.isNotEmpty) {
      children.add(Text(topic, style: theme.textTheme.titleSmall));
    }
    for (final element in scene.elements) {
      children.add(_buildElement(element));
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.xs6, horizontal: AppSpacing.xs),
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm10),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: _withGaps(children),
        ),
      ),
    );
  }

  /// kind→위젯 레지스트리. 미지 kind는 [SizedBox.shrink](조용히 생략·전방호환).
  Widget _buildElement(SceneElement element) {
    switch (element.kind) {
      case 'visualization':
        return _buildVisualization(element.ref);
      case 'param_control':
        return _SceneRow(
          icon: Icons.tune,
          label: element.targets.isEmpty
              ? '파라미터 조작'
              : '파라미터 조작: ${element.targets.join(', ')}',
        );
      case 'step_panel':
        // reveal_policy='deferred' — 학생이 스스로 펼친 단계까지만 서버에서 조회·노출한다.
        return _StepPanel(solutionPathId: element.solutionPathId);
      case 'misconception_probe':
        // 답 미루기·낙인 금지 — 정답·수정·오개념 id 미렌더, 사고 유도 cue만.
        return _SceneRow(
          icon: Icons.lightbulb_outline,
          label: _probeCue(element.intervention),
        );
      case 'socratic_prompt':
        return _SocraticBubble(text: element.promptText ?? '');
      case 'annotation':
        return const _SceneRow(icon: Icons.label_outline, label: '강조 표시');
      case 'skill_focus':
        // 행동영역 focus(S5k) — 정답 아님, *어떤 인지 행동을 하라*는 선언적 지시 cue만.
        return _SceneRow(
          icon: Icons.flag_outlined,
          label: element.focusPrompt ?? '',
        );
      case 'tutoring_prompt':
        // LTHC mastery 적응(S5l) — 역할 배지(진입점/비계/확장) + 정본 발화(정답 아님).
        return _TutoringRow(role: element.role, text: element.promptText ?? '');
      default:
        return const SizedBox.shrink();
    }
  }

  /// 시각화 렌더 선택: 대화형 2D 그래프·3D 곡면(spec 보유)은 실 WebView, 그 외는 caption seed로 폴백.
  ///
  /// `interactive_graph_2d`(2D 함수)·`interactive_surface_3d`(3D 곡면) + `interactive` + 비어있지
  /// 않은 `spec`일 때만 임베드 계산기를 띄운다(확률·사전렌더 애니메이션·spec 없는 명세는 아직 seed —
  /// 점층 확장·전방호환). 인코더/WebView는 type-무관이라 spec Map을 그대로 웹에 주입한다.
  Widget _buildVisualization(Visualization? viz) {
    if (viz != null &&
        webViewTypes.contains(viz.type) &&
        viz.interactive &&
        viz.spec != null &&
        viz.spec!.isNotEmpty) {
      // 개념 컨텍스트(concept_id/scene_id)를 호스트측에서 학습 로그에 싣는다(슬라이스 96-J).
      return GraphingCalculatorWebView(
        viz: viz,
        conceptId: scene.conceptId,
        sceneId: scene.sceneId,
      );
    }
    return _VisualizationSeed(viz: viz);
  }

  /// 개입 패턴별 *부드러운 사고 유도* 문구 — 정답·수정 금지(낙인/즉답 금지).
  static String _probeCue(String? intervention) {
    switch (intervention) {
      case 'counterexample':
        return '반례를 떠올려 볼까요?';
      case 'concrete_case':
        return '구체적인 예로 확인해 볼까요?';
      case 'visualization':
        return '그림으로 살펴볼까요?';
      case 'reverse_reasoning':
        return '거꾸로 생각해 볼까요?';
      default:
        return '다시 한 번 생각해 볼까요?';
    }
  }

  /// 요소 사이 간격(첫 요소 위는 비우고 사이만 8px).
  static List<Widget> _withGaps(List<Widget> items) {
    final out = <Widget>[];
    for (var i = 0; i < items.length; i++) {
      if (i > 0) {
        out.add(const SizedBox(height: AppSpacing.sm));
      }
      out.add(items[i]);
    }
    return out;
  }
}

/// 시각화 seed — 실 WebView 대신 caption/type cue만(05a §6 시드·렌더는 후속).
class _VisualizationSeed extends StatelessWidget {
  const _VisualizationSeed({required this.viz});

  /// 시각화 명세(없으면 일반 라벨).
  final Visualization? viz;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final caption = viz?.caption;
    final label = (caption != null && caption.isNotEmpty) ? caption : '인터랙티브 시각화';
    // 접근성(A11Y-01): 아이콘+텍스트로 흩어진 자식 대신 이 placeholder 블록 전체를 스크린리더가
    // 하나의 일관된 라벨로 읽도록 명시 부착(구조는 그대로, 시맨틱만 보강).
    return Semantics(
      label: label,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.lg),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.insights_outlined, size: 18, color: theme.colorScheme.primary),
            const SizedBox(width: AppSpacing.sm),
            Flexible(child: Text(label, style: theme.textTheme.bodyMedium)),
          ],
        ),
      ),
    );
  }
}

/// 단계 패널 — step_panel 요소를 실제 단계 점층 노출 UI로 렌더한다(SOL-02 ⑤).
///
/// 교수학 경계(협상 불가):
/// - reveal_policy='deferred' 불변 — 최초 1단계만 조회(up_to=1)하고, "다음 단계 보기" 탭으로
///   한 단계씩만 늘린다. 전체 풀이를 한 번에 펼치는 경로는 없다(버튼·제스처 모두 부재).
/// - 미펼침 단계 내용은 서버가 내려주지 않아 위젯 트리에도 없다(펼치기 전 정답·내용 미렌더).
/// - 단계 내용은 MATH-05 정본 [latexToPlainSolution]으로 평문 표기 변환 후 보인다
///   (원문 LaTeX 노출 금지).
/// - 정서 안전: 로딩·실패 모두 중립 톤(error 롤·빨강 미사용). "단계 n/N" 진행 표시는
///   위치 정보일 뿐 점수·등급이 아니다.
class _StepPanel extends ConsumerWidget {
  const _StepPanel({required this.solutionPathId});

  /// 서버가 검증해 내려준 풀이 경로 id. null/빈 문자열이면 조용히 생략한다(SOL-02 ③:
  /// 서버는 solution_path 실재 시에만 step_panel을 방출 — id 부재는 계약 위반이라 빈
  /// 껍데기를 그리지 않는다. 침묵 실패 금지로 로그는 남긴다).
  final String? solutionPathId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final id = solutionPathId;
    if (id == null || id.isEmpty) {
      debugPrint('step_panel에 solution_path_id가 없어 렌더를 생략한다(서버 계약 위반).');
      return const SizedBox.shrink();
    }
    final asyncState = ref.watch(stepPanelControllerProvider(id));
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.sm,
        ),
        child: asyncState.when(
          loading: () => _neutralLine(theme, '단계를 불러오고 있어요.'),
          error: (Object e, _) {
            debugPrint('단계 패널 초기 조회 실패(${e.runtimeType}) — 중립 재시도로 폴백한다.');
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                _neutralLine(theme, '단계를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'),
                TextButton(
                  onPressed: () =>
                      ref.invalidate(stepPanelControllerProvider(id)),
                  child: const Text('다시 시도'),
                ),
              ],
            );
          },
          data: (panelState) => _StepPanelBody(
            solutionPathId: id,
            panelState: panelState,
          ),
        ),
      ),
    );
  }

  /// 중립 톤 안내 한 줄 — 실패·로딩도 채점이 아니라 안내다(정서 안전).
  static Widget _neutralLine(ThemeData theme, String text) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        text,
        style: theme.textTheme.bodySmall
            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
      ),
    );
  }
}

/// 조회 성공 상태의 단계 패널 본문 — 펼친 단계 목록 + 진행 표시 + "다음 단계 보기".
class _StepPanelBody extends ConsumerWidget {
  const _StepPanelBody({required this.solutionPathId, required this.panelState});

  final String solutionPathId;
  final StepPanelState panelState;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final page = panelState.page;
    final children = <Widget>[
      Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.format_list_numbered,
            size: 16,
            color: theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: AppSpacing.sm),
          Text('단계별로 살펴보기', style: theme.textTheme.titleSmall),
          const SizedBox(width: AppSpacing.sm),
          // 위치 정보("단계 2/5") — 점수·등급이 아니다(SOL-02 ⑤ 점수 노출 0).
          Text(
            '단계 ${page.upTo}/${page.total}',
            style: theme.textTheme.labelSmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    ];

    if (page.steps.isEmpty) {
      // 계약상 solution_path 실재 시 단계도 실재 — 방어적 중립 문구(빈 껍데기 금지와 별개로
      // 서버 데이터 이상에 앱이 죽지 않게 한다).
      children.add(_StepPanel._neutralLine(theme, '아직 보여 줄 단계가 없어요.'));
    } else {
      for (final step in page.steps) {
        children.add(
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '${step.stepOrder}.',
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
                const SizedBox(width: AppSpacing.sm),
                // 학생 표면은 평문 표기 — 원문 LaTeX 노출 금지(MATH-05 정본 변환).
                Flexible(
                  child: Text(
                    latexToPlainSolution(step.content),
                    style: theme.textTheme.bodyMedium,
                  ),
                ),
              ],
            ),
          ),
        );
      }
    }

    if (panelState.revealFailed) {
      // 실패도 채점이 아니다 — 중립 안내 후 같은 버튼으로 재시도(펼친 단계는 그대로).
      children.add(
        Padding(
          padding: const EdgeInsets.only(top: AppSpacing.sm),
          child: _StepPanel._neutralLine(
            theme,
            '다음 단계를 불러오지 못했어요. 다시 시도해 주세요.',
          ),
        ),
      );
    }

    if (page.upTo < page.total) {
      children.add(
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: panelState.isRevealingNext
                ? null
                : () => ref
                    .read(stepPanelControllerProvider(solutionPathId).notifier)
                    .revealNext(),
            child: panelState.isRevealingNext
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('다음 단계 보기'),
          ),
        ),
      );
    }
    // 마지막 단계 도달 시 버튼은 사라진다 — 전체 일괄 노출 버튼은 어디에도 없다.

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: children,
    );
  }
}

/// 소크라테스 발화 버블 — 정본 유도 질문(promptText)만(정답 아님).
class _SocraticBubble extends StatelessWidget {
  const _SocraticBubble({required this.text});

  /// 학생에게 던질 유도 질문.
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
        decoration: BoxDecoration(
          color: theme.colorScheme.primaryContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.psychology_outlined,
              size: 16,
              color: theme.colorScheme.onPrimaryContainer,
            ),
            const SizedBox(width: AppSpacing.sm),
            Flexible(
              child: Text(
                text,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onPrimaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// LTHC 튜터링 프롬프트 한 줄 — 역할 배지(진입점/비계/확장) + 정본 발화(정답 아님·S5l).
///
/// mastery 적응 발화(`adapt_lthc` 정본)를 그린다 — `role`은 *지원 선택이지 판정이 아니다*(낙인
/// 회피). 정답·수정은 백엔드 스키마에 애초에 없어 여기서도 그릴 수 없다(발화 텍스트만).
class _TutoringRow extends StatelessWidget {
  const _TutoringRow({required this.role, required this.text});

  /// LTHC 축 역할("entry"/"scaffold"/"extension"·판정 아님·없으면 배지 생략).
  final String? role;

  /// `adapt_lthc` 정본 발화(정답 아님).
  final String text;

  /// 역할 코드 → 학생용 한국어 배지 라벨. 미지/누락 role은 null(배지 생략·전방호환).
  static String? _roleLabel(String? role) {
    switch (role) {
      case 'entry':
        return '진입점';
      case 'scaffold':
        return '비계';
      case 'extension':
        return '확장';
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurfaceVariant;
    final badge = _roleLabel(role);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.school_outlined, size: 16, color: color),
        const SizedBox(width: AppSpacing.sm),
        if (badge != null) ...[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
            decoration: BoxDecoration(
              color: theme.colorScheme.secondaryContainer,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              badge,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSecondaryContainer,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
        ],
        Flexible(
          child: Text(text, style: theme.textTheme.bodySmall?.copyWith(color: color)),
        ),
      ],
    );
  }
}

/// 장면 신호 한 줄 — 아이콘 + 부드러운 라벨(coach_signal_card `_SignalRow` 스타일).
class _SceneRow extends StatelessWidget {
  const _SceneRow({required this.icon, required this.label});

  /// 요소 종류를 암시하는 아이콘.
  final IconData icon;

  /// 학생에게 보일 부드러운 문구(cue만·정답 강조 없음).
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurfaceVariant;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: AppSpacing.sm),
        Flexible(
          child: Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(color: color),
          ),
        ),
      ],
    );
  }
}
