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

import '../data/scene_models.dart';
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
        margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
        return const _StepPanelSeed();
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
    const webViewTypes = {
      'interactive_graph_2d',
      'interactive_surface_3d',
      'simulation_probabilistic',
    };
    if (viz != null &&
        webViewTypes.contains(viz.type) &&
        viz.interactive &&
        viz.spec != null &&
        viz.spec!.isNotEmpty) {
      return GraphingCalculatorWebView(viz: viz);
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
        out.add(const SizedBox(height: 8));
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.insights_outlined, size: 18, color: theme.colorScheme.primary),
          const SizedBox(width: 8),
          Flexible(child: Text(label, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}

/// 단계 패널 seed — reveal_policy="deferred" → 접힌 [ExpansionTile](점층 노출·답 미루기).
class _StepPanelSeed extends StatelessWidget {
  const _StepPanelSeed();

  @override
  Widget build(BuildContext context) {
    return const Card(
      margin: EdgeInsets.zero,
      child: ExpansionTile(
        title: Text('단계별로 살펴보기'),
        childrenPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text('차근차근 단계를 펼쳐 볼 수 있어요.'),
          ),
        ],
      ),
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
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
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
            const SizedBox(width: 8),
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
        const SizedBox(width: 8),
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
