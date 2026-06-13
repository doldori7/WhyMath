// 채팅 컨트롤러 — 학생 발화 전송·코치 응답 수신·Polya 단계 전이를 관장한다.
//
// 경계(CLAUDE.md): 수학·교수학 결정은 전부 서버(L4 `POST /v1/coach`)가 내린다. 이 컨트롤러는
// (1) 학생 입력을 요청으로 옮기고 (2) 받은 [CoachResponse]를 화면 메시지로 *렌더*하며
// (3) 서버가 내린 단계 전이 결정을 그대로 적용할 뿐이다(표현≠의미·수학 로직 클라 미구현).
// 부수효과는 [CoachApi] 호출 하나뿐 — 나머지는 순수 상태 전이다.
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../data/coach_api.dart';
import '../data/coach_models.dart';
import '../domain/chat_message.dart';
import 'chat_state.dart';

part 'chat_controller.g.dart';

/// Polya 4단계 순서("understand"→"plan"→"execute"→"review").
///
/// 서버 결정 `decision.polyaStageToAdvance`는 *전이*("stay"·"next"·"previous")라
/// 현재 단계에 적용해 다음 단계 문자열을 얻는다. 자동 후퇴는 서버만 지시한다(클라 판단 없음).
const List<String> _polyaOrder = <String>[
  'understand',
  'plan',
  'execute',
  'review',
];

/// 현재 단계에 서버 전이 결정을 적용해 다음 단계 문자열을 계산한다.
///
/// 알 수 없는 전이·범위를 벗어난 이동은 현재 단계를 유지한다(보수적·앱 안정성).
String _applyTransition(String current, String transition) {
  final idx = _polyaOrder.indexOf(current);
  if (idx < 0) {
    return current; // 알 수 없는 단계는 그대로 둔다.
  }
  switch (transition) {
    case 'next':
      final next = idx + 1;
      return next < _polyaOrder.length ? _polyaOrder[next] : current;
    case 'previous':
      final prev = idx - 1;
      return prev >= 0 ? _polyaOrder[prev] : current;
    case 'stay':
    default:
      return current;
  }
}

/// 채팅 화면 상태를 관리하는 Riverpod Notifier.
@riverpod
class ChatController extends _$ChatController {
  @override
  ChatState build() => const ChatState();

  /// 학생 발화를 보내고 코치 응답으로 상태를 갱신한다.
  ///
  /// 흐름: ① 학생 메시지 append·전송중 표시·에러 클리어 → ② 서버 호출 →
  /// ③ 성공 시 코치 발화 append·단계 전이 반영·검산 코칭 추가 발화 →
  /// ④ 실패 시 에러만 기록(앱은 죽지 않는다·가용성).
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isSending) {
      return; // 빈 입력·전송 중 재진입 방지.
    }

    // ① 학생 메시지를 즉시 반영하고 로딩 상태로 전환한다.
    state = state.copyWith(
      messages: [...state.messages, ChatMessage.student(trimmed)],
      isSending: true,
      error: null,
    );

    try {
      // ② 서버 호출 — 현재 Polya 단계를 함께 보낸다(나머지 신호는 후속 슬라이스).
      final api = ref.read(coachApiProvider);
      final response = await api.coach(
        CoachRequest(
          studentInput: trimmed,
          polyaState: PolyaState(currentStage: state.polyaState),
        ),
      );

      // ③ 코치 발화를 만든다 — `decision.prompt`(메타인지 유도 발화)를 그대로 표시한다.
      final decision = response.decision;
      final newMessages = <ChatMessage>[
        ...state.messages,
        ChatMessage.coach(
          decision.prompt,
          socraticCategory: decision.socraticCategory,
          response: response,
        ),
      ];

      // 검산 코칭(solution_coaching.trigger.prompt)이 있으면 *추가* 코치 발화로 잇는다.
      final coaching = response.solutionCoaching;
      if (coaching != null && coaching.trigger.prompt.isNotEmpty) {
        newMessages.add(
          ChatMessage.coach(
            coaching.trigger.prompt,
            socraticCategory: coaching.trigger.socraticCategory,
          ),
        );
      }

      // 서버가 내린 단계 전이를 그대로 적용한다(클라 교수학 판단 없음).
      final nextStage = _applyTransition(
        state.polyaState,
        decision.polyaStageToAdvance,
      );

      state = state.copyWith(
        messages: newMessages,
        polyaState: nextStage,
        isSending: false,
      );
    } catch (e) {
      // ④ 실패는 graceful — 에러만 기록하고 입력 상태를 복구한다(앱 안 죽음).
      state = state.copyWith(
        isSending: false,
        error: '코치와 연결하지 못했어요. 잠시 후 다시 시도해 주세요.',
      );
    }
  }

  /// 표시된 에러를 지운다(SnackBar 닫힘 등에서 호출).
  void clearError() {
    if (state.error != null) {
      state = state.copyWith(error: null);
    }
  }
}
