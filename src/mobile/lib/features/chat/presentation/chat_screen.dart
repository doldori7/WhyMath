// 채팅 화면 — 학생 발화·코치 발화 버블·소크라테스 배지·입력/로딩/에러를 렌더한다.
//
// 경계(CLAUDE.md): 화면은 서버(L4)가 내린 결정을 *그대로 표시*만 한다(표현≠의미).
// 답을 강조하지 않는 톤 — 코치 발화(`decision.prompt`)는 메타인지 유도 발문이라
// 그 문장 자체를 버블로 보여줄 뿐, 정답·정오 강조 UI를 두지 않는다(절대 금기 준수).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';
import '../../ocr/data/ocr_models.dart';
import '../../problems/application/active_problem.dart';
import '../../problems/data/problem_models.dart';
import '../application/chat_controller.dart';
import '../domain/chat_message.dart';
import 'coach_signal_card.dart';
import 'scene_renderer.dart';

/// 슬로건 — 앱바 부제로 노출(브랜드 정체성·답이 아닌 이유).
const String _slogan = '답이 아닌, 이유를 묻는 수학';

/// 입력 모드 — 대화(단일 라인) 또는 풀이 단계(멀티라인·줄 분해 전송).
enum _InputMode {
  /// 자유 대화(기존 동작) — `send`로 학생 발화만 전송.
  conversation,

  /// 풀이 단계 입력 — 멀티라인을 줄 분해해 `sendSolution`으로 단계 전송.
  solution,
}

/// 메인 대화 화면.
///
/// 본문은 메시지 ListView(학생/코치 버블 구분)·하단 입력 행(TextField + 전송)으로 구성된다.
/// 라우팅(go_router)·인증·세션 영속은 후속 슬라이스다 — 이번엔 단일 화면 채팅 플로우만.
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _inputController = TextEditingController();

  /// 현재 입력 모드(기본=대화). 토글로 풀이 단계 모드와 전환한다.
  _InputMode _mode = _InputMode.conversation;

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  /// 입력 모드를 대화↔풀이 단계로 토글한다(입력 내용은 유지하지 않고 비운다).
  void _toggleMode() {
    setState(() {
      _mode = _mode == _InputMode.conversation
          ? _InputMode.solution
          : _InputMode.conversation;
      _inputController.clear();
    });
  }

  /// 입력 텍스트를 *현재 모드에 맞는* 컨트롤러 메서드로 보내고 입력 필드를 비운다.
  ///
  /// 대화 모드는 `send`(학생 발화), 풀이 단계 모드는 `sendSolution`(줄 분해→단계 전송).
  /// 줄 분해 자체는 컨트롤러(L5 책임·수동 세그먼트)에서 하고, 화면은 원문만 넘긴다.
  Future<void> _onSend() async {
    final text = _inputController.text;
    if (text.trim().isEmpty) {
      return;
    }
    _inputController.clear();
    final notifier = ref.read(chatControllerProvider.notifier);
    if (_mode == _InputMode.solution) {
      await notifier.sendSolution(text);
    } else {
      await notifier.send(text);
    }
  }

  /// 약점개념 학습 장면을 요청한다(서버 L2 진단→L4 장면·S5a 엔드포인트). 결과는 장면
  /// 메시지로 대화에 끼워져 [SceneRenderer]로 렌더된다(컨트롤러가 상태 전이·에러 처리).
  Future<void> _onRequestScene() async {
    await ref.read(chatControllerProvider.notifier).requestScene();
  }

  /// 풀이 사진 OCR 화면(`/ocr`)으로 진입하고, 돌아온 인식 결과를 코치에게 넘긴다(S1-d).
  ///
  /// OCR 화면은 채팅을 알지 못한 채 `context.pop(result)`로 [OcrResult]만 돌려준다(단방향
  /// chat→ocr 의존). 여기서 결과를 받아 `sendOcrSolution`으로 매핑·전송한다 — 사용자가 그냥
  /// 뒤로 가면(null) 아무 일도 하지 않는다.
  Future<void> _onCaptureSolution() async {
    final result = await context.push<OcrResult>(AppRoutes.ocrPath);
    if (result != null && mounted) {
      await ref.read(chatControllerProvider.notifier).sendOcrSolution(result);
    }
  }

  /// 수식(MathLive) 입력 화면(`/math-input`)으로 진입하고, 돌아온 LaTeX를 풀이로 넘긴다(S1).
  ///
  /// 입력 화면은 채팅을 알지 못한 채 `context.pop(latex)`로 LaTeX만 돌려준다(OCR과 동형·단방향
  /// chat→math-input 의존). 받은 LaTeX를 `sendSolution`으로 전송한다 — 취소(null)·빈 입력이면
  /// 아무 일도 하지 않는다(줄 분해·검증은 컨트롤러·백엔드가 한다).
  Future<void> _onMathInput() async {
    final latex = await context.push<String>(AppRoutes.mathInputPath);
    if (latex != null && latex.trim().isNotEmpty && mounted) {
      await ref.read(chatControllerProvider.notifier).sendSolution(latex);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatControllerProvider);

    // 에러가 생기면 SnackBar로 알리고(가용성·앱은 죽지 않음) 상태를 지운다.
    ref.listen<String?>(
      chatControllerProvider.select((s) => s.error),
      (previous, next) {
        if (next != null && context.mounted) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(SnackBar(content: Text(next)));
          ref.read(chatControllerProvider.notifier).clearError();
        }
      },
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('WhyMath'),
        actions: [
          // 풀이 사진 보내기 — OCR 화면으로 진입(전송 중엔 비활성·중복 진입 방지).
          IconButton(
            icon: const Icon(Icons.camera_alt_outlined),
            tooltip: '풀이 사진 보내기',
            onPressed: state.isSending ? null : _onCaptureSolution,
          ),
          // 약점개념 학습 장면 요청 — 전송 중엔 비활성(중복 요청 방지).
          IconButton(
            icon: const Icon(Icons.auto_awesome_outlined),
            tooltip: '약점 개념 장면 보기',
            onPressed: state.isSending ? null : _onRequestScene,
          ),
        ],
        // 슬로건을 부제로 — 답이 아닌 이유를 묻는다는 정체성을 항상 노출.
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(20),
          child: Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text(_slogan, style: TextStyle(fontSize: 12)),
          ),
        ),
      ),
      body: Column(
        children: [
          // 풀이 중인 문제를 채팅 위에 상시 노출(접기 가능) — 실기기 시연 피드백:
          // "문제가 한 화면에 같이 안 나옴". 학생이 문제를 다시 보러 화면을 떠나지 않게 한다.
          const _ActiveProblemBanner(),
          Expanded(
            child: state.messages.isEmpty
                ? const _EmptyHint()
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: state.messages.length,
                    itemBuilder: (context, index) =>
                        _MessageBubble(message: state.messages[index]),
                  ),
          ),
          // 코치 응답 대기 중 선형 인디케이터(은근한 로딩·도파민 카운트다운 아님).
          if (state.isSending) const LinearProgressIndicator(minHeight: 2),
          _InputBar(
            controller: _inputController,
            enabled: !state.isSending,
            mode: _mode,
            onSend: _onSend,
            onToggleMode: _toggleMode,
            onMathInput: _onMathInput,
          ),
        ],
      ),
    );
  }
}

/// 풀이 중인 문제 배너 — 활성 문제(발문·과목)를 채팅 상단에 접이식으로 상시 노출한다.
///
/// 활성 문제가 없으면(자유 대화 진입) 아무것도 그리지 않는다. 발문이 길면 접어서 채팅
/// 공간을 확보한다(기본 펼침 — 시연·풀이 맥락 우선). 정답·힌트는 어떤 형태로도 싣지
/// 않는다(서버가 답을 안 주는 계약과 동일·표현≠의미).
class _ActiveProblemBanner extends ConsumerStatefulWidget {
  const _ActiveProblemBanner();

  @override
  ConsumerState<_ActiveProblemBanner> createState() =>
      _ActiveProblemBannerState();
}

class _ActiveProblemBannerState extends ConsumerState<_ActiveProblemBanner> {
  /// 펼침 상태(기본 펼침) — 학생이 접으면 발문을 숨기고 한 줄 요약만 남긴다.
  bool _expanded = true;

  @override
  Widget build(BuildContext context) {
    final Problem? problem = ref.watch(activeProblemProvider);
    if (problem == null) {
      return const SizedBox.shrink();
    }
    final theme = Theme.of(context);
    final question = problem.questionText ?? problem.questionTextMd;

    return Material(
      color: theme.colorScheme.surfaceContainerHighest,
      child: InkWell(
        onTap: () => setState(() => _expanded = !_expanded),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.menu_book_outlined,
                    size: 18,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '풀이 중인 문제 · ${problem.subject}'
                      '${problem.subunit != null ? ' · ${problem.subunit}' : ''}',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              if (_expanded && question != null) ...[
                const SizedBox(height: 6),
                Text(question, style: theme.textTheme.bodyMedium),
                if (problem.choices != null && problem.choices!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  for (var i = 0; i < problem.choices!.length; i++)
                    Text(
                      '${i + 1}. ${problem.choices![i]}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// 메시지가 없을 때 보여줄 안내 — 답을 재촉하지 않는 톤.
class _EmptyHint extends StatelessWidget {
  const _EmptyHint();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          '어떤 문제를 함께 생각해 볼까요?',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 16),
        ),
      ),
    );
  }
}

/// 대화 한 줄 버블 — 학생은 오른쪽·코치는 왼쪽 정렬로 구분한다.
class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    // 장면 메시지면 SceneRenderer로만 렌더한다(빈 텍스트 버블 없이·S5e).
    final scene = message.scene;
    if (scene != null) {
      return SceneRenderer(scene: scene);
    }

    final theme = Theme.of(context);
    final isCoach = message.isCoach;
    final alignment = isCoach ? Alignment.centerLeft : Alignment.centerRight;
    final bubbleColor = isCoach
        ? theme.colorScheme.surfaceContainerHighest
        : theme.colorScheme.primaryContainer;
    final category = message.socraticCategory;
    final showBadge = isCoach && category != null && category.isNotEmpty;

    final bubble = Align(
      alignment: alignment,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        decoration: BoxDecoration(
          color: bubbleColor,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // 소크라테스 카테고리 배지(있을 때만) — 어떤 발문 전략인지 메타 표시.
            if (showBadge) _SocraticBadge(category: category),
            if (showBadge) const SizedBox(height: 6),
            Text(message.text),
          ],
        ),
      ),
    );

    // 코치 발화에 원본 응답이 있으면 버블 아래에 verify 신호 카드를 덧붙인다.
    // (학생 버블엔 response가 없어 카드가 붙지 않는다. 카드는 신호가 없으면 스스로
    //  빈 위젯을 반환하므로 여기선 단순히 존재 여부만 보고 끼워 넣는다.)
    final response = message.response;
    if (isCoach && response != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          bubble,
          CoachSignalCard(response: response),
        ],
      );
    }

    return bubble;
  }
}

/// 소크라테스 카테고리 배지 — 코치 발화의 발문 전략 라벨.
class _SocraticBadge extends StatelessWidget {
  const _SocraticBadge({required this.category});

  final String category;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        category,
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSecondaryContainer,
        ),
      ),
    );
  }
}

/// 하단 입력 행 — 모드별 입력(대화=단일/짧은 멀티라인, 풀이=멀티라인) + 전송 버튼.
///
/// 풀이 단계 모드는 줄바꿈으로 단계를 구분하므로 Enter를 전송에 묶지 않고(줄바꿈 허용)
/// 별도 "풀이 확인" 버튼으로만 보낸다. 대화 모드는 기존 동작(Enter 전송)을 유지한다.
class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.enabled,
    required this.mode,
    required this.onSend,
    required this.onToggleMode,
    required this.onMathInput,
  });

  final TextEditingController controller;
  final bool enabled;
  final _InputMode mode;
  final Future<void> Function() onSend;
  final VoidCallback onToggleMode;
  final Future<void> Function() onMathInput;

  @override
  Widget build(BuildContext context) {
    final isSolution = mode == _InputMode.solution;
    // 풀이 모드는 줄바꿈으로 단계를 구분하므로 Enter를 전송에 묶지 않는다(멀티라인 입력).
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 모드 토글 행 — 대화↔풀이 단계 전환(은근한 라벨·답 강조 없음).
            Row(
              children: [
                IconButton(
                  icon: Icon(
                    isSolution
                        ? Icons.chat_bubble_outline
                        : Icons.format_list_numbered,
                  ),
                  tooltip: isSolution ? '대화로 전환' : '풀이 단계로 전환',
                  onPressed: enabled ? onToggleMode : null,
                ),
                Text(
                  isSolution ? '풀이 단계' : '대화',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                // 풀이 모드에서만 — MathLive 수식 입력기로 진입(로드맵 S1 "MathLive 우선").
                // 텍스트 입력과 병행(OCR·plain 텍스트도 그대로 지원).
                if (isSolution) ...[
                  const Spacer(),
                  TextButton.icon(
                    icon: const Icon(Icons.functions, size: 18),
                    label: const Text('수식으로 입력'),
                    onPressed: enabled ? onMathInput : null,
                  ),
                ],
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: controller,
                    enabled: enabled,
                    minLines: isSolution ? 3 : 1,
                    maxLines: isSolution ? 8 : 4,
                    textInputAction: isSolution
                        ? TextInputAction.newline
                        : TextInputAction.send,
                    onSubmitted:
                        (!isSolution && enabled) ? (_) => onSend() : null,
                    decoration: InputDecoration(
                      hintText: isSolution
                          ? '한 줄에 한 단계씩 적어 주세요'
                          : '생각을 적어 보세요',
                      border: const OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                if (isSolution)
                  FilledButton(
                    onPressed: enabled ? onSend : null,
                    child: const Text('풀이 확인'),
                  )
                else
                  IconButton(
                    icon: const Icon(Icons.send),
                    tooltip: '보내기',
                    onPressed: enabled ? onSend : null,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
