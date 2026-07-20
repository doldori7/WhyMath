// 채팅 화면 — 학생 발화·코치 발화 버블·소크라테스 배지·입력/로딩/에러를 렌더한다.
//
// 경계(CLAUDE.md): 화면은 서버(L4)가 내린 결정을 *그대로 표시*만 한다(표현≠의미).
// 답을 강조하지 않는 톤 — 코치 발화(`decision.prompt`)는 메타인지 유도 발문이라
// 그 문장 자체를 버블로 보여줄 뿐, 정답·정오 강조 UI를 두지 않는다(절대 금기 준수).
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';
import '../../ocr/data/ocr_models.dart';
import '../../problems/application/active_problem.dart';
import '../../problems/data/problem_models.dart';
import '../application/chat_controller.dart';
import '../domain/chat_message.dart';
import '../domain/latex_to_plain.dart';
import '../domain/solution_steps.dart';
import 'coach_emphasis_text.dart';
import 'coach_signal_card.dart';
import 'scene_renderer.dart';

/// 슬로건 — 앱바 부제로 노출(브랜드 정체성·답이 아닌 이유).
const String _slogan = '답이 아닌, 이유를 묻는 수학';

// ── MOB-02 오버플로 방지 상한 ─────────────────────────────────────────────
// 근본 원인(실기기 실측 2026-07-19 M2007J20CG·125px 오버플로): body Column의
// 비신축 자식(문제 배너·입력 영역)의 고정 높이 합이, 키보드(IME)로
// resizeToAvoidBottomInset이 줄인 body 가용 높이를 넘으면 Expanded(메시지 리스트)가
// 0까지 줄어도 RenderFlex가 넘친다. 특히 배너는 발문·선택지 길이에 비례해 *상한 없이*
// 커지는 유일한 자식이라 대화 모드에서도 넘쳤다. 고정 px 상한 대신 *가용 높이 대비
// 비율* 상한을 걸어 어떤 화면·키보드 높이에서도 비신축 합이 body를 다 먹지 않게 한다.
// (resizeToAvoidBottomInset을 끄는 우회는 금지 — 입력이 키보드에 가려지면 안 된다.)

/// 문제 배너 최대 높이 — body 가용 높이 대비 비율. 초과분은 배너 내부 스크롤.
const double _bannerMaxHeightFraction = 0.3;

/// 풀이 단계 영역이 차지할 수 있는 body 가용 높이 비율 상한.
const double _stepAreaMaxHeightFraction = 0.25;

/// 단계 영역 절대 상한(px) — S3-05 값 유지(행 ~54px 3개 분량). 공간이 넉넉하면 이
/// 값이 걸리고, 키보드로 좁아지면 위 비율 상한이 먼저 걸린다(둘 중 작은 쪽).
const double _stepAreaMaxHeight = 162;

/// 빈 단계 필드 예시 힌트 (MOB-05) — 학생에게 *앱이 알아듣는 입력 형태*를 스스로 안내한다.
/// 등식 한 줄·근 나열 등 백엔드 verify가 결정하는 자연 표기(MOB-06·S3-06)라, 그대로 따라 쓰면
/// 검증 결정 구간에 들어간다. 왼쪽 번호 라벨과 중복되던 "단계 N"을 대체. 정오 강조·부정 표현 없음.
/// 필드가 늘어도 `index % length`로 순환한다.
const List<String> _stepHintExamples = <String>[
  '예: 2x+3=7',
  '예: x=2',
  '예: (x-2)(x-3)=0',
];

/// 입력 모드 — 대화(단일 라인) 또는 풀이 단계(단계 리스트 편집기·묶음 제출).
enum _InputMode {
  /// 자유 대화(기존 동작) — `send`로 학생 발화만 전송.
  conversation,

  /// 풀이 단계 입력 — 단계 리스트 편집기로 여러 단계를 *한 메시지로 묶어*
  /// `sendSolution`으로 전송(`'\n'` 조인 → 컨트롤러가 다시 줄 분해).
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

  /// 풀이 단계 편집기 상태 핸들 — MathLive "완료"가 입력 수식을 이 편집기의 단계 필드에
  /// 채우기 위해 쓴다(MOB-07). 편집기는 풀이 단계 모드에서만 트리에 있으므로 currentState는
  /// 그때만 유효하다(아니면 폴백).
  final GlobalKey<_SolutionStepsEditorState> _stepsEditorKey =
      GlobalKey<_SolutionStepsEditorState>();

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

  /// 대화 입력을 `send`(학생 발화)로 보내고 입력 필드를 비운다.
  ///
  /// 이 메서드는 *대화 모드 전용* — 풀이 단계 제출은 [_onSendSolutionSteps]가 담당한다
  /// (단계 리스트 편집기가 합친 원문을 받는다).
  Future<void> _onSend() async {
    final text = _inputController.text;
    if (text.trim().isEmpty) {
      return;
    }
    _inputController.clear();
    await ref.read(chatControllerProvider.notifier).send(text);
  }

  /// 단계 리스트 편집기가 합친 풀이 원문(`'\n'` 조인)을 `sendSolution`으로 보낸다.
  ///
  /// 조인은 편집기(UI)가, 줄 분해는 컨트롤러(`_splitSteps`)가 한다 — 기존 L5 계약
  /// (`sendSolution(String)` 시그니처·줄 분해 로직)은 완전 무변경이다. 실기기 실측
  /// (2026-07-19): verify는 *인접 두 단계의 전이*를 판정하므로 여러 단계를 한 메시지로
  /// 묶어야만 correct/incorrect가 결정된다 — 이 묶음 제출이 편집기의 존재 이유다.
  Future<void> _onSendSolutionSteps(String joined) async {
    if (joined.trim().isEmpty) {
      return;
    }
    await ref.read(chatControllerProvider.notifier).sendSolution(joined);
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
  /// chat→math-input 의존). 받은 LaTeX를 평문 수식(표기 매핑·MOB-06)으로 바꿔 **풀이 단계 편집기
  /// 필드에 채운다**(MOB-07) — 학생이 숨은 줄바꿈(⊕) 제스처 없이 눈에 보이는 단계 필드로 다단계를
  /// 쌓고 "풀이 제출"하게 한다. 여러 줄(⊕로 만든 `\displaylines`)이면 여러 필드에 분배된다. 편집기가
  /// 없거나(모드 전환 등) 채울 게 없으면 기존 즉시 제출 경로로 폴백한다(방어). 취소(null)·빈 입력이면
  /// 아무 일도 하지 않는다(변환·줄 분해·검증은 컨트롤러·백엔드가 한다).
  Future<void> _onMathInput() async {
    final latex = await context.push<String>(AppRoutes.mathInputPath);
    if (latex == null || latex.trim().isEmpty || !mounted) {
      return; // 취소·빈 입력.
    }
    final plain = latexToPlainSolution(latex);
    final filled =
        _stepsEditorKey.currentState?.fillFromMathInput(plain) ?? false;
    if (!filled) {
      // 편집기 미마운트(모드 전환 등)·빈 변환 → 기존 즉시 제출 경로 폴백(계약 유지).
      await ref
          .read(chatControllerProvider.notifier)
          .sendMathLiveSolution(latex);
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
      body: LayoutBuilder(
        builder: (context, constraints) {
          // 키보드(IME)가 올라오면 Scaffold(resizeToAvoidBottomInset 기본 true)가
          // body를 그만큼 줄인다. 그 *줄어든 실제 가용 높이*를 기준으로 비신축 자식
          // (배너·단계 영역)의 상한을 계산한다 — 입력은 키보드 위에 남고(리사이즈 유지)
          // Column은 넘치지 않는 근본 수정(MOB-02).
          final double bodyHeight = constraints.maxHeight;
          final double bannerMaxHeight = bodyHeight * _bannerMaxHeightFraction;
          final double stepAreaMaxHeight = math.min(
            _stepAreaMaxHeight,
            bodyHeight * _stepAreaMaxHeightFraction,
          );
          return Column(
            children: [
              // 풀이 중인 문제를 채팅 위에 상시 노출(접기 가능) — 실기기 시연 피드백:
              // "문제가 한 화면에 같이 안 나옴". 학생이 문제를 다시 보러 화면을 떠나지 않게 한다.
              _ActiveProblemBanner(maxHeight: bannerMaxHeight),
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
                stepsEditorKey: _stepsEditorKey,
                enabled: !state.isSending,
                mode: _mode,
                stepAreaMaxHeight: stepAreaMaxHeight,
                onSend: _onSend,
                onSendSolution: _onSendSolutionSteps,
                onToggleMode: _toggleMode,
                onMathInput: _onMathInput,
              ),
            ],
          );
        },
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
  const _ActiveProblemBanner({required this.maxHeight});

  /// 배너 최대 높이 — 화면(LayoutBuilder)이 body 가용 높이의 비율로 계산해 내려준다.
  /// 발문·선택지가 아무리 길어도 이 상한을 넘지 않고 초과분은 내부 스크롤로 가둔다
  /// (MOB-02 — 배너는 키보드 표시 시 Column을 넘치게 하던 유일한 *비유계* 자식이었다).
  final double maxHeight;

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
        // 상한 초과분은 내부 스크롤 — 키보드가 올라와도 발문 전체를 볼 수 있는 경로는
        // 유지하면서(스크롤) 배너가 채팅·입력 영역을 밀어내지 않게 한다(MOB-02).
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: widget.maxHeight),
          child: SingleChildScrollView(
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
                    if (problem.choices != null &&
                        problem.choices!.isNotEmpty) ...[
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
            // 코치 발화만 템플릿 `*...*` 강조를 굵게 렌더한다(MOB-04·표현≠의미).
            // 학생 버블은 원문 그대로 — 학생 입력의 별표는 곱셈 기호(`3*4`)일 수
            // 있어 어떤 해석도 하지 않는다.
            if (isCoach)
              CoachEmphasisText(message.text)
            else
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

/// 하단 입력 행 — 대화 모드는 단일 입력+전송, 풀이 모드는 단계 리스트 편집기.
///
/// 풀이 단계 모드는 [_SolutionStepsEditor]가 담당한다: 채팅 습관(한 메시지 한 줄)대로
/// 보내면 매 턴이 외톨이 단계(전이 0)라 verify가 전부 unverifiable이 되므로(실기기 실측),
/// 여러 단계를 한 메시지로 *묶는* 제출을 UI 구조로 유도한다(단계 구조의 시각화 =
/// 사고 구조화·메타인지 정합). 대화 모드는 기존 동작(Enter 전송)을 그대로 유지한다.
class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.stepsEditorKey,
    required this.enabled,
    required this.mode,
    required this.stepAreaMaxHeight,
    required this.onSend,
    required this.onSendSolution,
    required this.onToggleMode,
    required this.onMathInput,
  });

  /// 대화 모드 입력 컨트롤러(풀이 모드는 편집기가 자체 컨트롤러를 쓴다).
  final TextEditingController controller;

  /// 풀이 단계 편집기 상태 핸들 — MathLive 입력을 단계 필드에 채우는 데 쓴다(MOB-07).
  final GlobalKey<_SolutionStepsEditorState> stepsEditorKey;

  final bool enabled;
  final _InputMode mode;

  /// 풀이 단계 영역 최대 높이 — 화면(LayoutBuilder)이 키보드로 줄어든 body 가용
  /// 높이에 맞춰 계산해 내려준다(MOB-02 — 좁은 화면에서 입력 영역이 넘치지 않게).
  final double stepAreaMaxHeight;

  /// 대화 모드 전송(학생 발화 `send`).
  final Future<void> Function() onSend;

  /// 풀이 모드 제출 — 편집기가 합친 원문(`'\n'` 조인)을 받아 `sendSolution`으로 보낸다.
  final Future<void> Function(String joined) onSendSolution;

  final VoidCallback onToggleMode;
  final Future<void> Function() onMathInput;

  @override
  Widget build(BuildContext context) {
    final isSolution = mode == _InputMode.solution;
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
            if (isSolution)
              // 풀이 단계 모드 — 단계 리스트 편집기. 토글로 모드를 나가면 편집기가
              // 트리에서 제거돼 상태가 초기화된다(기존 "토글 시 입력 비움"과 동형).
              // GlobalKey로 MathLive 입력을 이 편집기 필드에 채운다(MOB-07).
              _SolutionStepsEditor(
                key: stepsEditorKey,
                enabled: enabled,
                stepAreaMaxHeight: stepAreaMaxHeight,
                onSubmit: onSendSolution,
              )
            else
              Row(
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
          ],
        ),
      ),
    );
  }
}

/// 풀이 단계 리스트 편집기 — 번호 매겨진 단계 필드·추가/삭제·"N단계 제출" 버튼.
///
/// 실기기 실측(2026-07-19·MEMORY): verify는 *인접 두 단계의 전이*를 판정하므로 단계를
/// 한 메시지로 묶어 보내야만 correct/incorrect가 결정된다(외톨이 단계=전부 unverifiable).
/// 이 편집기는 "여러 단계를 한 번에"가 기본 모양임을 UI 구조로 유도한다 — 초기 2개 필드·
/// 단계 번호·"N단계 제출" 미리보기. 1단계 제출도 막지 않는다(부드러운 안내만 — 백엔드가
/// 전이 0을 안전 처리·질책 표현 금지).
///
/// 경계: 편집기는 비어있지 않은 단계를 `'\n'`로 합쳐 [onSubmit]에 넘길 뿐이다 — 줄 분해는
/// 컨트롤러(`sendSolution`), 검증은 백엔드가 한다(표현≠의미·수학 로직 클라 미구현).
class _SolutionStepsEditor extends StatefulWidget {
  const _SolutionStepsEditor({
    super.key,
    required this.enabled,
    required this.stepAreaMaxHeight,
    required this.onSubmit,
  });

  /// 입력·버튼 활성 여부(전송 중엔 비활성 — 기존 입력 행과 동일 규칙).
  final bool enabled;

  /// 단계 필드 리스트 영역 최대 높이 — 넉넉하면 절대 상한(162px·행 3개 분량), 키보드로
  /// 좁아지면 body 가용 높이 비율로 줄어든 값이 내려온다(MOB-02). 초과분은 내부 스크롤.
  final double stepAreaMaxHeight;

  /// 제출 콜백 — 비어있지 않은 단계들을 `'\n'`로 합친 원문을 받는다.
  final Future<void> Function(String joined) onSubmit;

  @override
  State<_SolutionStepsEditor> createState() => _SolutionStepsEditorState();
}

class _SolutionStepsEditorState extends State<_SolutionStepsEditor> {
  /// 초기 단계 필드 수 — 묶음 제출이 기본 모양임을 시각적으로 유도한다(1개가 아님).
  /// 2개인 이유: ①2단계 = 검증 가능한 최소 모양(인접 전이 1개) — verify가 판정할 전이가
  /// 생기는 최소 단위라 "묶음이 기본" 유도는 유지된다 ②3개 대비 행 1개(~54px)만큼 풀이
  /// 모드 초기 높이를 줄여 기존 키보드 오버플로(MOB-02) 악화를 완화한다.
  static const int _initialStepCount = 2;

  final List<TextEditingController> _controllers = <TextEditingController>[];
  final List<FocusNode> _focusNodes = <FocusNode>[];
  final ScrollController _scrollController = ScrollController();

  /// 비어있지 않은 단계 수 — "N단계 제출" 라벨·묶음 안내 텍스트에 실시간 반영한다.
  int _filledCount = 0;

  @override
  void initState() {
    super.initState();
    for (var i = 0; i < _initialStepCount; i++) {
      _appendField();
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    for (final node in _focusNodes) {
      node.dispose();
    }
    _scrollController.dispose();
    super.dispose();
  }

  /// 새 단계 필드(컨트롤러+포커스 노드)를 리스트 끝에 만든다(카운터 리스너 부착).
  void _appendField() {
    final controller = TextEditingController();
    controller.addListener(_recount);
    _controllers.add(controller);
    _focusNodes.add(FocusNode());
  }

  /// 비어있지 않은 단계 수를 다시 세어 달라졌으면 라벨을 갱신한다(실시간 반영).
  void _recount() {
    final n = _controllers.where((c) => c.text.trim().isNotEmpty).length;
    if (n != _filledCount) {
      setState(() => _filledCount = n);
    }
  }

  /// "+ 단계 추가" — 필드를 하나 늘리고(요청 시) 새 필드로 포커스·스크롤을 옮긴다.
  void _addStep({bool focus = false}) {
    setState(_appendField);
    // 새 필드는 다음 프레임에야 트리에 붙으므로 포커스·스크롤을 프레임 뒤로 미룬다.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      if (focus && _focusNodes.isNotEmpty) {
        _focusNodes.last.requestFocus();
      }
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
  }

  /// MathLive "완료"로 받은 평문 수식(`'\n'` 여러 줄 가능)을 단계 필드에 채운다(MOB-07).
  ///
  /// [mergeStepTexts] 규칙으로 **빈 필드부터 채우고 남으면 필드를 추가**한다 — 학생이 숨은
  /// 줄바꿈(⊕) 제스처 없이도 눈에 보이는 단계 필드로 다단계를 쌓게 한다. 채운 줄이 하나라도
  /// 있으면 true를 돌려준다(호출부가 폴백 여부 판정). 구조 변경(필드 추가)만 setState로 감싸고,
  /// 텍스트는 컨트롤러 세팅으로 반영한다(TextField가 컨트롤러로 갱신·리스너가 카운트 라벨 갱신).
  /// 표기 배치만 한다 — 수학 판정·검증은 백엔드 몫(표현≠의미).
  bool fillFromMathInput(String plainText) {
    final lines = plainText
        .split('\n')
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .toList();
    if (lines.isEmpty) {
      return false; // 채울 게 없다(빈/공백 입력) — 호출부가 폴백한다.
    }
    final merged =
        mergeStepTexts(_controllers.map((c) => c.text).toList(), lines);
    // 늘어난 만큼 새 필드 추가(구조 변경이라 setState).
    final extra = merged.length - _controllers.length;
    if (extra > 0) {
      setState(() {
        for (var i = 0; i < extra; i++) {
          _appendField();
        }
      });
    }
    // 각 필드 텍스트 반영(달라진 것만 — 불필요한 커서 리셋·알림 방지).
    for (var i = 0; i < merged.length; i++) {
      if (_controllers[i].text != merged[i]) {
        _controllers[i].text = merged[i];
      }
    }
    _recount();
    // 채운 마지막 필드가 보이도록 스크롤한다(다음 프레임).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
    return true;
  }

  /// 단계 삭제 — 마지막 1개는 남긴다(빈 편집기 방지). dispose는 프레임 뒤로 미룬다
  /// (제거되는 TextField가 이번 프레임까지 이전 컨트롤러·노드를 참조하기 때문).
  void _removeStep(int index) {
    if (_controllers.length <= 1) {
      return;
    }
    final controller = _controllers[index];
    final node = _focusNodes[index];
    setState(() {
      _controllers.removeAt(index);
      _focusNodes.removeAt(index);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      controller.dispose();
      node.dispose();
    });
    _recount();
  }

  /// 단계 필드 Enter(next) — 다음 단계로 이동, 마지막 필드면 새 단계를 추가한다.
  void _handleStepSubmitted(int index) {
    if (index + 1 < _focusNodes.length) {
      _focusNodes[index + 1].requestFocus();
    } else {
      _addStep(focus: true);
    }
  }

  /// 비어있지 않은 단계들을 `'\n'`로 합쳐 제출하고 편집기를 초기 상태로 되돌린다.
  ///
  /// 합치기만 UI가 한다 — 컨트롤러 `sendSolution`이 다시 줄 분해하므로 왕복 무손실이다
  /// (컨트롤러/L5 계약 완전 무변경). 빈 단계(공백뿐)는 제출에서 제외한다.
  Future<void> _submit() async {
    final joined = _controllers
        .map((c) => c.text.trim())
        .where((t) => t.isNotEmpty)
        .join('\n');
    if (joined.isEmpty) {
      return;
    }
    _resetFields(); // 기존 입력 행과 동형 — 전송 전에 입력을 비운다.
    await widget.onSubmit(joined);
  }

  /// 필드들을 초기 개수의 빈 필드로 되돌린다(이전 컨트롤러·노드는 프레임 뒤 dispose).
  void _resetFields() {
    final oldControllers = List<TextEditingController>.of(_controllers);
    final oldNodes = List<FocusNode>.of(_focusNodes);
    setState(() {
      _controllers.clear();
      _focusNodes.clear();
      for (var i = 0; i < _initialStepCount; i++) {
        _appendField();
      }
      _filledCount = 0;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      for (final controller in oldControllers) {
        controller.dispose();
      }
      for (final node in oldNodes) {
        node.dispose();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 단계 필드 리스트 — 높이를 가둬 내부 스크롤(단계가 늘어도 화면을 안 밀어낸다).
        // 상한은 화면이 body 가용 높이에 맞춰 내려준 값(키보드 표시 시 축소·MOB-02).
        ConstrainedBox(
          constraints: BoxConstraints(maxHeight: widget.stepAreaMaxHeight),
          child: SingleChildScrollView(
            controller: _scrollController,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < _controllers.length; i++) _buildStepRow(i),
              ],
            ),
          ),
        ),
        // 한 단계뿐일 때 — 묶음 제출을 부드럽게 안내한다(질책 아님·제출은 막지 않음).
        if (_filledCount == 1)
          Padding(
            padding: const EdgeInsets.only(top: 2, bottom: 4),
            child: Text(
              '단계를 나눠 적으면 풀이를 확인해 드릴 수 있어요',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        Row(
          children: [
            TextButton.icon(
              icon: const Icon(Icons.add, size: 18),
              label: const Text('단계 추가'),
              onPressed: widget.enabled ? () => _addStep(focus: true) : null,
            ),
            const Spacer(),
            // "N단계 제출" — 제출 미리보기(몇 단계가 실제 전송되는지 상시 표시).
            // 비어있으면 보낼 게 없으므로 비활성(1단계 제출은 허용 — 백엔드 안전 처리).
            FilledButton(
              onPressed: (widget.enabled && _filledCount > 0) ? _submit : null,
              child: Text(
                _filledCount > 0 ? '$_filledCount단계 제출' : '풀이 제출',
              ),
            ),
          ],
        ),
      ],
    );
  }

  /// 단계 한 행 — 번호 라벨 + 단일라인 필드(Enter=다음 단계) + 삭제 버튼.
  Widget _buildStepRow(int index) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          // 번호 라벨 — 필드가 채워져도 단계 구조가 계속 보인다(사고 구조의 시각화).
          SizedBox(
            width: 24,
            child: Text(
              '${index + 1}',
              textAlign: TextAlign.center,
              style: theme.textTheme.labelLarge?.copyWith(
                color: theme.colorScheme.primary,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: TextField(
              controller: _controllers[index],
              focusNode: _focusNodes[index],
              enabled: widget.enabled,
              maxLines: 1,
              // Enter=다음 단계(마지막이면 추가) — 줄바꿈이 아니라 단계 이동이 자연 흐름.
              textInputAction: TextInputAction.next,
              onSubmitted: (_) => _handleStepSubmitted(index),
              decoration: InputDecoration(
                // 번호는 왼쪽 라벨에 있으므로 힌트는 *입력 형태 예시*로 안내한다(MOB-05).
                hintText: _stepHintExamples[index % _stepHintExamples.length],
                border: const OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.remove_circle_outline, size: 20),
            tooltip: '단계 삭제',
            onPressed: (widget.enabled && _controllers.length > 1)
                ? () => _removeStep(index)
                : null,
          ),
        ],
      ),
    );
  }
}
