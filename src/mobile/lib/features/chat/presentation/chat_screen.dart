// 채팅 화면 — 학생 발화·코치 발화 버블·소크라테스 배지·입력/로딩/에러를 렌더한다.
//
// 경계(CLAUDE.md): 화면은 서버(L4)가 내린 결정을 *그대로 표시*만 한다(표현≠의미).
// 답을 강조하지 않는 톤 — 코치 발화(`decision.prompt`)는 메타인지 유도 발문이라
// 그 문장 자체를 버블로 보여줄 뿐, 정답·정오 강조 UI를 두지 않는다(절대 금기 준수).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/chat_controller.dart';
import '../domain/chat_message.dart';
import 'coach_signal_card.dart';

/// 슬로건 — 앱바 부제로 노출(브랜드 정체성·답이 아닌 이유).
const String _slogan = '답이 아닌, 이유를 묻는 수학';

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

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  /// 입력 텍스트를 컨트롤러로 보내고 입력 필드를 비운다.
  Future<void> _onSend() async {
    final text = _inputController.text;
    if (text.trim().isEmpty) {
      return;
    }
    _inputController.clear();
    await ref.read(chatControllerProvider.notifier).send(text);
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
            onSend: _onSend,
          ),
        ],
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

/// 하단 입력 행 — TextField + 전송 IconButton.
class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.enabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool enabled;
  final Future<void> Function() onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                enabled: enabled,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: enabled ? (_) => onSend() : null,
                decoration: const InputDecoration(
                  hintText: '생각을 적어 보세요',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              icon: const Icon(Icons.send),
              tooltip: '보내기',
              onPressed: enabled ? onSend : null,
            ),
          ],
        ),
      ),
    );
  }
}
