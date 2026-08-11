// OCR 캡처 화면 — 풀이 사진 촬영/선택 → 서버 인식 → 구조(OcrResult) 렌더.
//
// 경계(CLAUDE.md): 화면은 서버(L5)가 인식·검증해 내려준 `OcrResult`를 *그대로 표시*만 한다
// (표현≠의미). 영역별 인식 결과(LaTeX/한글)·신뢰도를 보이고, 신뢰도가 낮은 영역엔 *재확인*
// cue를 부드럽게 단다(coach_signal_card "④ OCR 재확인"·§3.3 게이트와 같은 임계 0.8).
//
// 정서 안전(절대 금기): 빨강·"틀렸다"·정오 강조·게임화 없음. 낮은 신뢰도는 "다시 확인해볼까요?"
// 같은 따뜻한 권유로만 표시한다(부정 강화 금지). 모든 인터랙티브 요소는 접근성 라벨·충분한
// 터치 타깃(IconButton/FilledButton 기본 48dp)을 가진다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../theme/spacing.dart';
import '../../chat/domain/latex_to_plain.dart';
import '../application/ocr_controller.dart';
import '../application/ocr_state.dart';
import '../data/image_source_service.dart';
import '../data/ocr_models.dart';

/// 풀이 사진 OCR 화면 — 촬영/선택 후 인식 결과를 구조로 보여 준다.
///
/// 표준 화면이라 단독 라우팅 없이도 push해 쓸 수 있다(라우팅 진입은 후속 슬라이스).
class OcrCaptureScreen extends ConsumerWidget {
  const OcrCaptureScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(ocrControllerProvider);

    // 에러는 SnackBar로 알리고(가용성·앱은 죽지 않음) 상태는 화면이 그대로 보여 준다.
    ref.listen<String?>(
      ocrControllerProvider.select((s) => s.error),
      (previous, next) {
        if (next != null && context.mounted) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(SnackBar(content: Text(next)));
        }
      },
    );

    return Scaffold(
      appBar: AppBar(title: const Text('풀이 사진 인식')),
      body: SafeArea(
        child: Column(
          children: [
            if (state.isBusy) const LinearProgressIndicator(minHeight: 2),
            Expanded(child: _Body(state: state)),
            _CaptureBar(enabled: !state.isBusy),
          ],
        ),
      ),
    );
  }
}

/// 본문 — 상태에 따라 안내·로딩·결과를 그린다.
class _Body extends StatelessWidget {
  const _Body({required this.state});

  final OcrState state;

  @override
  Widget build(BuildContext context) {
    final result = state.result;
    switch (state.status) {
      case OcrStatus.idle:
      case OcrStatus.error:
        return const _EmptyHint();
      case OcrStatus.picking:
      case OcrStatus.uploading:
        return const _BusyHint();
      case OcrStatus.result:
        if (result == null) {
          return const _EmptyHint();
        }
        return _ResultView(result: result);
    }
  }
}

/// 시작 안내 — 답을 재촉하지 않는 톤.
class _EmptyHint extends StatelessWidget {
  const _EmptyHint();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Text(
          '풀이를 사진으로 찍으면 함께 살펴볼게요.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyLarge,
        ),
      ),
    );
  }
}

/// 선택·인식 진행 안내.
class _BusyHint extends StatelessWidget {
  const _BusyHint();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Text(
          '풀이를 읽고 있어요…',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyLarge,
        ),
      ),
    );
  }
}

/// 인식 결과 — 전체 요약 + 영역별 카드 목록.
class _ResultView extends StatelessWidget {
  const _ResultView({required this.result});

  final OcrResult result;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        _OverallSummary(result: result),
        const SizedBox(height: AppSpacing.sm),
        // 인식된 영역이 있으면 코치에게 넘기는 진입을 준다(빈 인식이면 넘길 게 없어 숨긴다).
        if (result.regions.isNotEmpty) ...[
          _CoachHandoffButton(result: result),
          const SizedBox(height: AppSpacing.sm),
        ],
        // 영역이 없으면(빈 인식) 부드러운 안내만.
        if (result.regions.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
            child: Text(
              '읽을 수 있는 내용을 찾지 못했어요. 더 또렷하게 다시 찍어볼까요?',
              textAlign: TextAlign.center,
            ),
          )
        else
          for (var i = 0; i < result.regions.length; i++)
            _RegionCard(index: i, region: result.regions[i]),
      ],
    );
  }
}

/// 코치 핸드오프 버튼 — 인식 결과를 호출자(채팅)에게 돌려주고 복귀한다(S1-d).
///
/// OCR 화면은 채팅을 *알지 못한다*(단방향 chat→ocr 의존 유지) — 여기선 `context.pop(result)`로
/// [OcrResult]만 돌려주고, 매핑(정전 미러)·전송은 호출자(`chat_controller.sendOcrSolution`)가
/// 한다. 저신뢰 인식이어도 넘길 수 있다(재확인 게이트는 서버 코치가 낸다·정서 안전 톤 유지).
class _CoachHandoffButton extends StatelessWidget {
  const _CoachHandoffButton({required this.result});

  final OcrResult result;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        icon: const Icon(Icons.send_outlined),
        label: const Text('이 풀이로 코치에게'),
        onPressed: () => context.pop(result),
      ),
    );
  }
}

/// 전체 요약 — 인식 텍스트(plain_latex)와 전체 신뢰도 cue.
class _OverallSummary extends StatelessWidget {
  const _OverallSummary({required this.result});

  final OcrResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md14),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('인식한 풀이', style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.xs6),
          // 인식 결과 본문 — 선택 가능 텍스트(복사·다시 확인 편의)이되, 학생이 읽을 *평문
          // 표기*로 되돌려 보여준다(MATH-05).
          //
          // ⚠️ `plainLatex`는 이름과 달리 평문이 아니다 — 백엔드 `l5/ocr/assemble.py`가
          // `" ".join(r.latex for r in regions)`로 *원문 region LaTeX를 이어붙인* 값이라
          // 백슬래시 매크로가 그대로 들어온다. 이름이 만든 착시 때문에 이 표면이 오래
          // 뚫려 있었다. 표시만 변환하고 데이터 경로(chat_controller가 코치로 넘기는
          // `result.plainLatex`)는 건드리지 않는다 — 그쪽은 백엔드 verify 계약 소관.
          if (latexToPlainSolution(result.plainLatex).isNotEmpty)
            SelectableText(latexToPlainSolution(result.plainLatex))
          else
            Text(
              '아직 인식된 내용이 없어요.',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          const SizedBox(height: AppSpacing.sm10),
          // 전체 신뢰도 — 낮으면 재확인 권유(빨강·"실패" 단정 없음).
          if (result.hasLowConfidenceRegion)
            const _RecheckCue(
              label: '인식이 또렷하지 않은 부분이 있어요 — 다시 확인해볼까요?',
            )
          else
            const _ClarityCue(),
        ],
      ),
    );
  }
}

/// 영역 카드 1개 — 유형(텍스트/수식)·인식 결과·신뢰도 cue.
class _RegionCard extends StatelessWidget {
  const _RegionCard({required this.index, required this.region});

  final int index;
  final OcrRegion region;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final low = region.isLowConfidence;
    final typeLabel = region.isFormula ? '수식' : '텍스트';

    return Semantics(
      label: '${index + 1}번째 $typeLabel 영역'
          '${low ? ', 다시 확인이 필요해요' : ''}',
      child: Card(
        // 낮은 신뢰도는 *따뜻한* surfaceContainerHighest 톤으로만 구분(경고색·빨강 금지).
        color: low
            ? theme.colorScheme.surfaceContainerHighest
            : theme.colorScheme.surfaceContainer,
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Icon(
                    region.isFormula
                        ? Icons.functions_outlined
                        : Icons.notes_outlined,
                    size: 18,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(
                    '${index + 1}. $typeLabel',
                    style: theme.textTheme.labelLarge,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs6),
              // 영역 본문도 평문 표기로 되돌린다(MATH-05) — `_OverallSummary`와 같은 누출
              // 지점이다. 태스크 acceptance는 `plainLatex` 한 곳만 지목했지만, 같은 화면에서
              // 영역 카드가 `region.latex` 원문을 그대로 노출하고 있어 한쪽만 닫으면 화면
              // 단위 계약("이 화면은 원문 LaTeX를 학생에게 보이지 않는다")이 성립하지 않는다.
              if (latexToPlainSolution(region.latex).isNotEmpty)
                SelectableText(latexToPlainSolution(region.latex))
              else
                Text(
                  '(읽은 내용 없음)',
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              const SizedBox(height: AppSpacing.sm),
              if (low)
                const _RecheckCue(label: '이 부분이 잘 안 보여요 — 다시 확인해볼까요?')
              else
                const _ClarityCue(),
            ],
          ),
        ),
      ),
    );
  }
}

/// 재확인 cue — 낮은 신뢰도일 때 부드러운 권유(coach_signal_card "④ OCR 재확인"과 톤 일치).
class _RecheckCue extends StatelessWidget {
  const _RecheckCue({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurfaceVariant;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.photo_camera_outlined, size: 16, color: color),
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

/// 또렷함 cue — 충분히 또렷할 때 은근한 확인 표시(숫자 강조·게임화 없음).
///
/// 일부러 신뢰도 *수치*를 노출하지 않는다 — 점수화·게임화 금지(CLAUDE.md). 판단(임계 0.8)은
/// 호출부가 [OcrRegion.isLowConfidence]/[OcrResult.hasLowConfidenceRegion]로 끝낸다.
class _ClarityCue extends StatelessWidget {
  const _ClarityCue();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurfaceVariant;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.check_circle_outline, size: 16, color: color),
        const SizedBox(width: AppSpacing.sm),
        Text(
          '또렷하게 읽었어요',
          style: theme.textTheme.bodySmall?.copyWith(color: color),
        ),
      ],
    );
  }
}

/// 하단 촬영/선택 바 — 카메라·갤러리 두 진입(충분한 터치 타깃·접근성 라벨).
class _CaptureBar extends ConsumerWidget {
  const _CaptureBar({required this.enabled});

  final bool enabled;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(ocrControllerProvider.notifier);
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
        child: Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: enabled
                    ? () => notifier.pickAndRecognize(OcrImageSource.camera)
                    : null,
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('사진 찍기'),
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: enabled
                    ? () => notifier.pickAndRecognize(OcrImageSource.gallery)
                    : null,
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('갤러리에서 고르기'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
